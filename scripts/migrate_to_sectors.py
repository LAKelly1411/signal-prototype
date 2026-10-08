"""One-off: move today's single-sector data into data/gambling/, tagging
every signal with its sector. No re-scoring, no API calls. Safe to re-run:
a migrated repo is left untouched.

    python -m scripts.migrate_to_sectors --dry-run
    python -m scripts.migrate_to_sectors
"""

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

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


def _finish(data_dir: Path, signal_count: int) -> None:
    """Final steps, after the commit marker: drop the old archive and index."""
    old_archive = data_dir / "archive"
    if old_archive.exists():
        shutil.rmtree(old_archive)
    from src import sectors
    sectors.update_index(SLUG, name="Gambling & gaming", status="ready",
                         signal_count=signal_count,
                         last_run_at=datetime.now(timezone.utc).isoformat(), error=None)


def migrate(data_dir: Path = Path("data"), dry_run: bool = False) -> dict:
    target = data_dir / SLUG
    old_archive = data_dir / "archive"
    year_files = sorted(old_archive.glob("signals-*.json")) if old_archive.exists() else []
    old_ids = old_archive / "ids.json"

    # target/signals.json is the commit marker: it is written last, after every
    # other target file, so its presence means the copy is complete.
    if (target / "signals.json").exists():
        if not old_archive.exists():
            return {"status": "already migrated", "signals": 0, "archived": 0, "files": []}
        needed = [target / "archive" / p.name for p in year_files]
        if old_ids.exists():
            needed.append(target / "archive" / "ids.json")
        if all(p.exists() for p in needed):
            # Interrupted after the marker: finish the cleanup only.
            count = len(_read(target / "signals.json"))
            if not dry_run:
                _finish(data_dir, count)
            return {"status": "migrated", "signals": count, "archived": 0, "files": []}
        # Marker present but the copy is incomplete: redo it (copies overwrite).

    old_signals = data_dir / "signals.json"
    if not old_signals.exists():
        return {"status": "nothing to migrate", "signals": 0, "archived": 0, "files": []}

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

    return {"status": "migrated", "signals": len(signals), "archived": archived,
            "files": [str(f) for f in files]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    report = migrate(dry_run=args.dry_run)
    print(json.dumps(report, indent=2))
    if args.dry_run:
        print("Dry run — nothing written.")


if __name__ == "__main__":
    main()
