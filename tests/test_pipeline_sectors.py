import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from src import pipeline, sectors
from src.collectors.base import RawItem
from src.sectors import PROMPT_FIELDS


def sector_yaml(slug, **extra):
    data = {"slug": slug, "name": slug.title(), "brief": f"The {slug} sector.",
            "prompt": {f: f"{slug} {f}" for f in PROMPT_FIELDS},
            "sources": {"gazette": {}}}
    data.update(extra)
    return data


class FakeCollector:
    def __init__(self, items): self.items = items
    def collect(self): return self.items


def item(n, source="gazette"):
    return RawItem(source=source, source_url=f"https://x/{n}", title=f"Item {n}",
                   raw_summary="s", published_at="2026-10-01T00:00:00+00:00",
                   signal_type="insolvency")


class FakeClient:
    """Answers every Claude call with a fixed, valid payload."""
    def __init__(self):
        self.messages = SimpleNamespace(create=self._create)
        self.systems = []

    def _create(self, model, max_tokens, system, messages):
        self.systems.append(system)
        payload = {"newsworthiness_score": 55, "signal_type": "insolvency",
                   "entities": ["Acme Ltd"], "category": "Insolvency",
                   "why_it_matters": "x", "summary": "y", "pattern_type": "routine",
                   "coherent": True, "significance": 10, "key_points": [], "direction": "steady"}
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=json.dumps(payload))],
                               stop_reason="end_turn", usage=SimpleNamespace(output_tokens=5))


@pytest.fixture
def repo(tmp_path, monkeypatch):
    config = tmp_path / "config" / "sectors"
    config.mkdir(parents=True)
    data = tmp_path / "data"
    monkeypatch.setattr(sectors, "CONFIG_DIR", config)
    monkeypatch.setattr(sectors, "DATA_DIR", data)
    monkeypatch.setattr(sectors, "INDEX_PATH", data / "sectors.json")
    monkeypatch.setattr(pipeline, "COMPAT_SIGNALS_PATH", data / "signals.json")
    monkeypatch.setattr(pipeline, "COMPAT_STATUS_PATH", data / "run_status.json")
    client = FakeClient()
    monkeypatch.setattr(pipeline, "build_client", lambda: client)
    monkeypatch.setattr(pipeline, "load_dotenv", lambda: None)
    feeds = {}
    monkeypatch.setattr(pipeline, "build_collectors",
                        lambda sector: [FakeCollector(feeds.get(sector.slug, []))])
    return SimpleNamespace(config=config, data=data, feeds=feeds, client=client)


def write(repo, slug, **extra):
    (repo.config / f"{slug}.yaml").write_text(yaml.safe_dump(sector_yaml(slug, **extra)), encoding="utf-8")


def test_each_sector_writes_only_its_own_data(repo):
    write(repo, "alpha"); write(repo, "beta")
    repo.feeds["alpha"] = [item(1), item(2)]
    repo.feeds["beta"] = [item(3)]
    assert pipeline.main([]) == 0
    alpha = json.loads((repo.data / "alpha" / "signals.json").read_text())
    beta = json.loads((repo.data / "beta" / "signals.json").read_text())
    assert len(alpha) == 2 and len(beta) == 1
    assert {s["sector"] for s in alpha} == {"alpha"} and {s["sector"] for s in beta} == {"beta"}
    assert json.loads((repo.data / "alpha" / "run_status.json").read_text())["sector"] == "alpha"


def test_prompts_use_each_sectors_wording(repo):
    write(repo, "alpha")
    repo.feeds["alpha"] = [item(1)]
    pipeline.main(["--sector", "alpha"])
    assert any("alpha newsroom" in s for s in repo.client.systems)


def test_sector_flag_runs_only_that_sector(repo):
    write(repo, "alpha"); write(repo, "beta")
    repo.feeds["alpha"] = [item(1)]; repo.feeds["beta"] = [item(2)]
    assert pipeline.main(["--sector", "beta"]) == 0
    assert not (repo.data / "alpha" / "signals.json").exists()
    assert (repo.data / "beta" / "signals.json").exists()


def test_unknown_sector_exits_2_and_runs_nothing(repo, capsys):
    write(repo, "alpha")
    assert pipeline.main(["--sector", "nope"]) == 2
    assert not (repo.data / "alpha").exists()
    assert "alpha" in capsys.readouterr().err


def test_one_bad_sector_does_not_stop_the_rest(repo):
    write(repo, "alpha")
    (repo.config / "broken.yaml").write_text("slug: broken\nname: Broken\n", encoding="utf-8")
    repo.feeds["alpha"] = [item(1)]
    assert pipeline.main([]) == 1
    assert (repo.data / "alpha" / "signals.json").exists()
    index = sectors.read_index()
    assert index["alpha"]["status"] == "ready" and index["alpha"]["signal_count"] == 1
    assert index["broken"]["status"] == "error" and "brief" in index["broken"]["error"]
    assert "error" in json.loads((repo.data / "broken" / "run_status.json").read_text())


def test_a_run_exception_is_isolated(repo, monkeypatch):
    write(repo, "alpha"); write(repo, "beta")
    repo.feeds["beta"] = [item(1)]
    real = pipeline.run_sector
    def flaky(sector, client):
        if sector.slug == "alpha":
            raise RuntimeError("boom")
        return real(sector, client)
    monkeypatch.setattr(pipeline, "run_sector", flaky)
    assert pipeline.main([]) == 1
    assert sectors.read_index()["alpha"]["error"] == "boom"
    assert sectors.read_index()["beta"]["status"] == "ready"


def test_gambling_writes_the_compat_copy(repo):
    write(repo, "gambling")
    repo.feeds["gambling"] = [item(1), item(2)]
    assert pipeline.main(["--sector", "gambling"]) == 0
    assert (repo.data / "signals.json").read_text() == (repo.data / "gambling" / "signals.json").read_text()
    assert (repo.data / "run_status.json").read_text() == (repo.data / "gambling" / "run_status.json").read_text()


def test_other_sectors_do_not_touch_the_compat_copy(repo):
    write(repo, "alpha")
    repo.feeds["alpha"] = [item(1)]
    pipeline.main([])
    assert not (repo.data / "signals.json").exists()


def test_existing_signals_are_kept_and_not_rescored(repo):
    write(repo, "alpha")
    repo.feeds["alpha"] = [item(1)]
    pipeline.main([])
    calls_first = len(repo.client.systems)
    pipeline.main([])
    alpha = json.loads((repo.data / "alpha" / "signals.json").read_text())
    assert len(alpha) == 1
    # Second run: nothing new to score; summaries are cached.
    assert len(repo.client.systems) == calls_first
