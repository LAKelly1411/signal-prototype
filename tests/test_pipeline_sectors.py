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


def test_an_unreadable_config_does_not_stop_the_rest(repo):
    # Invalid UTF-8 raises UnicodeDecodeError, not SectorConfigError.
    write(repo, "alpha")
    (repo.config / "garbled.yaml").write_bytes(b"slug: garbled\nname: \xff\xfe\n")
    repo.feeds["alpha"] = [item(1)]
    assert pipeline.main([]) == 1
    assert (repo.data / "alpha" / "signals.json").exists()
    index = sectors.read_index()
    assert index["alpha"]["status"] == "ready"
    assert index["garbled"]["status"] == "error"


def test_a_failed_compat_copy_keeps_the_good_status(repo, monkeypatch):
    write(repo, "gambling")
    repo.feeds["gambling"] = [item(1)]
    def broken_copy(sector):
        raise OSError("disk full")
    monkeypatch.setattr(pipeline, "write_compat_copy", broken_copy)
    assert pipeline.main(["--sector", "gambling"]) == 1
    status = json.loads((repo.data / "gambling" / "run_status.json").read_text())
    assert "error" not in status and status["live_signals"] == 1
    entry = sectors.read_index()["gambling"]
    assert entry["status"] == "ready" and entry["error"] is None


def test_a_config_whose_name_is_not_a_slug_never_runs(repo):
    write(repo, "alpha")
    (repo.config / "..yaml").write_text("slug: x\n", encoding="utf-8")
    repo.feeds["alpha"] = [item(1)]
    assert pipeline.main([]) == 0
    assert not (repo.data / "run_status.json").exists()
    assert not (repo.data / "signals.json").exists()
    assert set(sectors.read_index()) == {"alpha"}
    assert pipeline.main(["--sector", ".."]) == 2


def test_cluster_summaries_are_cached_across_runs(repo):
    # Two items naming the same company form a cluster, so the first run
    # summarises it; the second run has nothing new and must reuse that.
    write(repo, "alpha")
    repo.feeds["alpha"] = [item(1), item(2)]
    pipeline.main([])
    alpha = json.loads((repo.data / "alpha" / "signals.json").read_text())
    assert all(s.get("cluster_summary_for") for s in alpha)
    calls_first = len(repo.client.systems)
    assert calls_first > 2  # two scores plus at least one summary
    pipeline.main([])
    assert len(repo.client.systems) == calls_first


def old_layout(repo):
    """The pre-sector layout: data/signals.json, run_status.json and
    data/archive/, with no data/gambling/ yet. Built from a real gambling run
    so the signals carry every field the pipeline expects."""
    import shutil
    write(repo, "gambling")
    repo.feeds["gambling"] = [item(1)]
    assert pipeline.main(["--sector", "gambling"]) == 0
    shutil.rmtree(repo.data / "gambling")
    (repo.data / "sectors.json").unlink()
    old = json.loads((repo.data / "signals.json").read_text())
    for s in old:
        s.pop("sector", None)
    (repo.data / "signals.json").write_text(json.dumps(old))
    (repo.data / "archive").mkdir()
    (repo.data / "archive" / "signals-2025.json").write_text(json.dumps([{"id": "old", "published_at": "2025-01-01"}]))
    (repo.data / "archive" / "ids.json").write_text(json.dumps(["old"]))
    repo.feeds["gambling"] = [item(1), item(2)]
    return [s["id"] for s in old]


def test_first_run_migrates_the_old_layout(repo):
    old_ids = old_layout(repo)
    assert pipeline.main([]) == 0
    live = json.loads((repo.data / "gambling" / "signals.json").read_text())
    assert set(old_ids) < {s["id"] for s in live} and len(live) == 2
    arch = repo.data / "gambling" / "archive"
    assert json.loads((arch / "ids.json").read_text()) == ["old"]
    assert json.loads((arch / "signals-2025.json").read_text())[0]["sector"] == "gambling"
    assert not (repo.data / "archive").exists()
    assert sectors.read_index()["gambling"]["status"] == "ready"


def test_sector_flag_gambling_also_migrates(repo):
    old_layout(repo)
    assert pipeline.main(["--sector", "gambling"]) == 0
    assert (repo.data / "gambling" / "archive" / "ids.json").exists()
    assert not (repo.data / "archive").exists()


def test_another_sector_alone_does_not_migrate(repo):
    old_layout(repo)
    write(repo, "alpha")
    assert pipeline.main(["--sector", "alpha"]) == 0
    assert not (repo.data / "gambling").exists()
    assert (repo.data / "archive" / "ids.json").exists()


def test_no_migration_once_the_gambling_store_exists(repo, monkeypatch):
    write(repo, "gambling")
    repo.feeds["gambling"] = [item(1)]
    assert pipeline.main([]) == 0
    def must_not_run(data_dir):
        raise AssertionError("migrate called")
    monkeypatch.setattr(pipeline, "migrate", must_not_run)
    assert pipeline.main([]) == 0


def test_no_migration_without_an_old_store(repo, monkeypatch):
    def must_not_run(data_dir):
        raise AssertionError("migrate called")
    monkeypatch.setattr(pipeline, "migrate", must_not_run)
    write(repo, "gambling")
    repo.feeds["gambling"] = [item(1)]
    assert pipeline.main([]) == 0


def test_a_corrupt_index_does_not_stop_the_run(repo):
    write(repo, "alpha")
    repo.feeds["alpha"] = [item(1)]
    repo.data.mkdir()
    (repo.data / "sectors.json").write_text("{not json", encoding="utf-8")
    assert pipeline.main([]) == 0
    assert sectors.read_index()["alpha"]["status"] == "ready"
