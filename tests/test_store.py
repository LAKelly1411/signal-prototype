import json
from datetime import datetime, timedelta, timezone

from src import store

NOW = datetime(2026, 8, 27, tzinfo=timezone.utc)


def signal(sid, days_ago=1):
    return {
        "id": sid,
        "published_at": (NOW - timedelta(days=days_ago)).isoformat(),
        "title": f"Signal {sid}",
    }


def paths(tmp_path):
    return {
        "path": tmp_path / "signals.json",
        "archive_dir": tmp_path / "archive",
        "ids_path": tmp_path / "archive" / "ids.json",
    }


class TestMergeNew:
    def test_appends_only_unseen_ids(self):
        existing = [signal("a")]
        merged, added = store.merge_new(existing, [signal("a"), signal("b")])
        assert [s["id"] for s in merged] == ["a", "b"]
        assert [s["id"] for s in added] == ["b"]

    def test_known_ids_block_reingest(self):
        # A source that still lists an archived item must not resurrect it.
        merged, added = store.merge_new([], [signal("old")], known_ids={"old"})
        assert merged == [] and added == []

    def test_never_overwrites_existing(self):
        existing = [{"id": "a", "published_at": NOW.isoformat(), "title": "original"}]
        merged, _ = store.merge_new(existing, [signal("a")])
        assert merged[0]["title"] == "original"


class TestRetention:
    def test_keeps_recent_and_archives_old(self, tmp_path):
        p = paths(tmp_path)
        live = store.save(
            [signal("recent", days_ago=10), signal("old", days_ago=300)],
            retention_days=120,
            now=NOW,
            **p,
        )
        assert [s["id"] for s in live] == ["recent"]
        assert json.loads(p["path"].read_text(encoding="utf-8"))[0]["id"] == "recent"

        archived = json.loads(
            (p["archive_dir"] / "signals-2025.json").read_text(encoding="utf-8")
        )
        assert [s["id"] for s in archived] == ["old"]

    def test_archived_ids_are_recorded_and_readable(self, tmp_path):
        p = paths(tmp_path)
        store.save([signal("old", days_ago=300)], retention_days=120, now=NOW, **p)
        assert store.load_archived_ids(p["ids_path"]) == {"old"}

    def test_archiving_is_idempotent(self, tmp_path):
        p = paths(tmp_path)
        old = signal("old", days_ago=300)
        store.save([old], retention_days=120, now=NOW, **p)
        store.save([old], retention_days=120, now=NOW, **p)
        archived = json.loads(
            (p["archive_dir"] / "signals-2025.json").read_text(encoding="utf-8")
        )
        assert len(archived) == 1

    def test_splits_archive_by_published_year(self, tmp_path):
        p = paths(tmp_path)
        store.save(
            [signal("a", days_ago=300), signal("b", days_ago=700)],
            retention_days=120,
            now=NOW,
            **p,
        )
        assert (p["archive_dir"] / "signals-2025.json").exists()
        assert (p["archive_dir"] / "signals-2024.json").exists()

    def test_retention_disabled_keeps_everything(self, tmp_path):
        p = paths(tmp_path)
        live = store.save(
            [signal("old", days_ago=3000)], retention_days=None, now=NOW, **p
        )
        assert len(live) == 1
        assert not p["archive_dir"].exists()

    def test_archived_signal_is_not_reingested_or_rescored(self, tmp_path):
        """The end-to-end guard: age a signal out, then have the collector
        return it again — it must not come back as new and unscored."""
        p = paths(tmp_path)
        old = signal("old", days_ago=300)
        old["newsworthiness_score"] = 70
        store.save([old], retention_days=120, now=NOW, **p)

        live = store.load(p["path"])
        merged, added = store.merge_new(
            live, [signal("old", days_ago=300)], store.load_archived_ids(p["ids_path"])
        )
        assert added == []
        assert not [s for s in merged if s.get("newsworthiness_score") is None]


class TestLoad:
    def test_missing_file_is_empty_not_an_error(self, tmp_path):
        assert store.load(tmp_path / "nope.json") == []
        assert store.load_archived_ids(tmp_path / "nope.json") == set()
