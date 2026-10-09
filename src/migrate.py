"""Move today's single-sector data into data/gambling/, tagging every
signal with its sector. No re-scoring, no API calls. Safe to re-run: a
migrated repo is left untouched.

The pipeline calls migrate() on its first run after the sector change
lands, so the move happens on main's own latest data.
`python -m scripts.migrate_to_sectors` runs it by hand.
"""

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from src import sectors

SLUG = "gambling"


def _read(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def _tag(signals: list[dict]) -> list[dict]:
    for s in signals:
        s["sector"] = SLUG
    return signals


def _untagged(signals: list[dict]) -> list[dict]:
    return [{k: v for k, v in s.items() if k != "sector"} for s in signals]


def _same_records(old: Path, new: Path) -> bool:
    """Same records in the same order, ignoring the sector tag."""
    return new.exists() and _untagged(_read(old)) == _untagged(_read(new))


def _target_holds_old_content(data_dir: Path, target: Path, year_files: list[Path]) -> bool:
    """True only if every record in the old layout is already in the target,
    so deleting the old archive loses nothing."""
    old_signals = data_dir / "signals.json"
    if old_signals.exists() and not _same_records(old_signals, target / "signals.json"):
        return False
    for year_file in year_files:
        if not _same_records(year_file, target / "archive" / year_file.name):
            return False
    old_ids = data_dir / "archive" / "ids.json"
    if old_ids.exists():
        new_ids = target / "archive" / "ids.json"
        if not new_ids.exists() or _read(old_ids) != _read(new_ids):
            return False
    return True


def _ids_missing_from_target(data_dir: Path, target: Path) -> set[str]:
    """Ids in the old live store that the target holds neither live nor archived."""
    old_signals = data_dir / "signals.json"
    if not old_signals.exists():
        return set()
    known = {s["id"] for s in _read(target / "signals.json")}
    target_ids = target / "archive" / "ids.json"
    if target_ids.exists():
        known |= set(_read(target_ids))
    return {s["id"] for s in _read(old_signals)} - known


def _finish(data_dir: Path, signal_count: int) -> None:
    """Final steps, after the commit marker: drop the old archive and index."""
    old_archive = data_dir / "archive"
    if old_archive.exists():
        shutil.rmtree(old_archive)
    sectors.update_index(SLUG, name="Gambling & gaming", status="ready",
                         signal_count=signal_count,
                         last_run_at=datetime.now(timezone.utc).isoformat(), error=None)


def _report(status: str, signals: int = 0, archived: int = 0, files=(), **extra) -> dict:
    return {"status": status, "signals": signals, "archived": archived,
            "files": list(files), **extra}


def migrate(data_dir: Path = Path("data"), dry_run: bool = False) -> dict:
    target = data_dir / SLUG
    old_archive = data_dir / "archive"
    year_files = sorted(old_archive.glob("signals-*.json")) if old_archive.exists() else []
    old_ids = old_archive / "ids.json"

    # target/signals.json is the commit marker: it is written last, after every
    # other target file, so its presence means the copy is complete.
    if (target / "signals.json").exists():
        if not old_archive.exists():
            missing = _ids_missing_from_target(data_dir, target)
            if missing:
                # The old live store moved on after the copy (e.g. a merge
                # brought in newer data): report it, change nothing.
                return _report("stale", stale_ids=len(missing))
            return _report("already migrated")
        if _target_holds_old_content(data_dir, target, year_files):
            # Interrupted after the marker: finish the cleanup only.
            count = len(_read(target / "signals.json"))
            if not dry_run:
                _finish(data_dir, count)
            return _report("migrated", signals=count)
        # The old layout holds records the target lacks (an incomplete copy, or
        # data that moved on since): redo the full copy (copies overwrite).

    old_signals = data_dir / "signals.json"
    if not old_signals.exists():
        return _report("nothing to migrate")

    signals = _tag(_read(old_signals))
    files = []
    archived = 0

    for year_file in year_files:
        batch = _tag(_read(year_file))
        archived += len(batch)
        files.append(target / "archive" / year_file.name)
        if not dry_run:
            _write(target / "archive" / year_file.name, batch)
    if old_ids.exists():
        files.append(target / "archive" / "ids.json")
        if not dry_run:
            (target / "archive").mkdir(parents=True, exist_ok=True)
            shutil.copyfile(old_ids, target / "archive" / "ids.json")
    old_status = data_dir / "run_status.json"
    if old_status.exists():
        files.append(target / "run_status.json")
        if not dry_run:
            _write(target / "run_status.json", {**_read(old_status), "sector": SLUG})
    files.append(target / "signals.json")
    if not dry_run:
        _write(target / "signals.json", signals)  # commit marker, last
        # The top-level signals.json/run_status.json stay untouched as the
        # dashboard's compatibility copy.
        _finish(data_dir, len(signals))

    return _report("migrated", signals=len(signals), archived=archived,
                   files=[str(f) for f in files])
