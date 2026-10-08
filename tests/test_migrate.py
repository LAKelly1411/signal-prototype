import json
from pathlib import Path

import pytest

from scripts.migrate_to_sectors import migrate


@pytest.fixture(autouse=True)
def _isolated_index(tmp_path, monkeypatch):
    from src import sectors
    monkeypatch.setattr(sectors, "INDEX_PATH", tmp_path / "sectors.json")


def seed(data: Path):
    (data / "archive").mkdir(parents=True)
    live = [{"id": "a", "published_at": "2026-09-01T00:00:00+00:00", "newsworthiness_score": 50},
            {"id": "b", "published_at": "2026-09-02T00:00:00+00:00", "newsworthiness_score": 20}]
    (data / "signals.json").write_text(json.dumps(live))
    (data / "run_status.json").write_text(json.dumps({"live_signals": 2}))
    (data / "archive" / "signals-2025.json").write_text(json.dumps([{"id": "z", "published_at": "2025-01-01"}]))
    (data / "archive" / "ids.json").write_text(json.dumps(["z"]))
    return live


def test_moves_everything_and_tags_sector(tmp_path):
    live = seed(tmp_path)
    report = migrate(tmp_path)
    assert report["status"] == "migrated" and report["signals"] == 2 and report["archived"] == 1
    moved = json.loads((tmp_path / "gambling" / "signals.json").read_text())
    assert [s["id"] for s in moved] == ["a", "b"]
    assert all(s["sector"] == "gambling" for s in moved)
    assert moved[0]["newsworthiness_score"] == live[0]["newsworthiness_score"]  # not re-scored
    arch = json.loads((tmp_path / "gambling" / "archive" / "signals-2025.json").read_text())
    assert arch[0]["sector"] == "gambling"
    assert json.loads((tmp_path / "gambling" / "archive" / "ids.json").read_text()) == ["z"]
    assert json.loads((tmp_path / "gambling" / "run_status.json").read_text())["sector"] == "gambling"
    # The old top-level files stay: they are the dashboard's compat copy.
    assert (tmp_path / "signals.json").exists()
    assert not (tmp_path / "archive").exists()


def test_writes_the_index(tmp_path):
    from src import sectors
    seed(tmp_path)
    migrate(tmp_path)
    assert sectors.read_index()["gambling"]["status"] == "ready"


def test_second_run_is_a_no_op(tmp_path):
    seed(tmp_path)
    migrate(tmp_path)
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    assert migrate(tmp_path)["status"] == "already migrated"
    after = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    assert before == after


def test_dry_run_writes_nothing(tmp_path):
    seed(tmp_path)
    before = sorted(p for p in tmp_path.rglob("*"))
    assert migrate(tmp_path, dry_run=True)["status"] == "migrated"
    assert sorted(p for p in tmp_path.rglob("*")) == before


def test_nothing_to_migrate(tmp_path):
    assert migrate(tmp_path)["status"] == "nothing to migrate"
