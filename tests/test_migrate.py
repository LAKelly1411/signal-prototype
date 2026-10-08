import json
from pathlib import Path

import pytest

from src.migrate import migrate


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


def test_top_level_compat_files_are_untouched(tmp_path):
    seed(tmp_path)
    before = {n: (tmp_path / n).read_bytes() for n in ("signals.json", "run_status.json")}
    migrate(tmp_path)
    assert before == {n: (tmp_path / n).read_bytes() for n in before}


def test_crash_before_marker_is_redone(tmp_path, monkeypatch):
    from src import migrate as m
    from src import sectors
    seed(tmp_path)
    real_write = m._write

    def crashing(path, payload):
        if path == tmp_path / "gambling" / "signals.json":
            raise RuntimeError("boom")
        real_write(path, payload)

    monkeypatch.setattr(m, "_write", crashing)
    with pytest.raises(RuntimeError):
        migrate(tmp_path)
    monkeypatch.setattr(m, "_write", real_write)
    assert not (tmp_path / "gambling" / "signals.json").exists()
    assert (tmp_path / "archive").exists()  # not removed before the marker

    assert migrate(tmp_path)["status"] == "migrated"
    assert (tmp_path / "gambling" / "signals.json").exists()
    assert json.loads((tmp_path / "gambling" / "archive" / "ids.json").read_text()) == ["z"]
    assert (tmp_path / "gambling" / "archive" / "signals-2025.json").exists()
    assert (tmp_path / "gambling" / "run_status.json").exists()
    assert not (tmp_path / "archive").exists()
    assert sectors.read_index()["gambling"]["status"] == "ready"


def test_marker_written_but_old_archive_left_is_cleaned_up(tmp_path):
    from src import sectors
    seed(tmp_path)
    migrate(tmp_path)
    # Recreate the crash state: marker and full target copy exist, and the
    # old archive, with the same content, remains.
    (tmp_path / "archive").mkdir()
    (tmp_path / "archive" / "signals-2025.json").write_text(json.dumps([{"id": "z", "published_at": "2025-01-01"}]))
    (tmp_path / "archive" / "ids.json").write_text('["z"]')
    assert migrate(tmp_path, dry_run=True)["status"] == "migrated"
    assert (tmp_path / "archive").exists()  # dry run changes nothing
    assert migrate(tmp_path)["status"] == "migrated"
    assert not (tmp_path / "archive").exists()
    assert sectors.read_index()["gambling"]["status"] == "ready"
    assert migrate(tmp_path)["status"] == "already migrated"


def test_old_layout_that_moved_on_is_recopied_not_deleted(tmp_path):
    """Reviewer's reproduction: main keeps running after the first migrate,
    then the old layout comes back with newer data. Nothing may be lost."""
    seed(tmp_path)
    x = {"id": "x", "published_at": "2026-01-01"}
    (tmp_path / "archive" / "signals-2026.json").write_text(json.dumps([x]))
    (tmp_path / "archive" / "ids.json").write_text(json.dumps(["z", "x"]))
    migrate(tmp_path)
    # Main moves on: a new live signal, one newly archived into the existing
    # 2026 file, ids updated, and data/archive present again.
    live = json.loads((tmp_path / "signals.json").read_text())
    live.append({"id": "c", "published_at": "2026-09-03T00:00:00+00:00", "newsworthiness_score": 70})
    (tmp_path / "signals.json").write_text(json.dumps(live))
    (tmp_path / "archive").mkdir()
    (tmp_path / "archive" / "signals-2025.json").write_text(json.dumps([{"id": "z", "published_at": "2025-01-01"}]))
    (tmp_path / "archive" / "signals-2026.json").write_text(json.dumps([x, {"id": "y", "published_at": "2026-02-01"}]))
    (tmp_path / "archive" / "ids.json").write_text(json.dumps(["z", "x", "y"]))

    assert migrate(tmp_path)["status"] == "migrated"
    moved = json.loads((tmp_path / "gambling" / "signals.json").read_text())
    assert [s["id"] for s in moved] == ["a", "b", "c"]
    assert all(s["sector"] == "gambling" for s in moved)
    arch = tmp_path / "gambling" / "archive"
    assert [s["id"] for s in json.loads((arch / "signals-2026.json").read_text())] == ["x", "y"]
    assert [s["id"] for s in json.loads((arch / "signals-2025.json").read_text())] == ["z"]
    assert json.loads((arch / "ids.json").read_text()) == ["z", "x", "y"]
    assert not (tmp_path / "archive").exists()


def test_changed_record_in_old_archive_is_recopied(tmp_path):
    seed(tmp_path)
    migrate(tmp_path)
    (tmp_path / "archive").mkdir()
    changed = [{"id": "z", "published_at": "2025-01-01", "newsworthiness_score": 90}]
    (tmp_path / "archive" / "signals-2025.json").write_text(json.dumps(changed))
    (tmp_path / "archive" / "ids.json").write_text('["z"]')
    assert migrate(tmp_path)["status"] == "migrated"
    arch = json.loads((tmp_path / "gambling" / "archive" / "signals-2025.json").read_text())
    assert arch == [{**changed[0], "sector": "gambling"}]
    assert not (tmp_path / "archive").exists()


def test_stale_target_is_reported_and_left_alone(tmp_path):
    seed(tmp_path)
    migrate(tmp_path)
    # A merge brings in a newer top-level store; no old archive this time.
    live = json.loads((tmp_path / "signals.json").read_text())
    live += [{"id": "c", "published_at": "2026-09-03"}, {"id": "d", "published_at": "2026-09-04"}]
    (tmp_path / "signals.json").write_text(json.dumps(live))
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    report = migrate(tmp_path)
    assert report["status"] == "stale" and report["stale_ids"] == 2
    assert before == {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}


def test_ids_archived_in_target_are_not_stale(tmp_path):
    seed(tmp_path)
    migrate(tmp_path)
    live = json.loads((tmp_path / "signals.json").read_text())
    live.append({"id": "z", "published_at": "2025-01-01"})  # archived in the target
    (tmp_path / "signals.json").write_text(json.dumps(live))
    assert migrate(tmp_path)["status"] == "already migrated"


def test_script_warns_on_stale(tmp_path, monkeypatch, capsys):
    from scripts import migrate_to_sectors as script
    seed(tmp_path)
    migrate(tmp_path)
    live = json.loads((tmp_path / "signals.json").read_text())
    live.append({"id": "c", "published_at": "2026-09-03"})
    (tmp_path / "signals.json").write_text(json.dumps(live))
    monkeypatch.chdir(tmp_path.parent)
    monkeypatch.setattr("sys.argv", ["migrate_to_sectors"])
    monkeypatch.setattr(script, "migrate", lambda dry_run: migrate(tmp_path, dry_run=dry_run))
    script.main()
    out = capsys.readouterr()
    assert '"status": "stale"' in out.out
    assert "WARNING" in out.err and "1 signal id(s)" in out.err
