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


def migrate(data_dir: Path = Path("data"), dry_run: bool = False) -> dict:
    target = data_dir / SLUG
    if (target / "signals.json").exists():
        return {"status": "already migrated", "signals": 0, "archived": 0, "files": []}
    old_signals = data_dir / "signals.json"
    if not old_signals.exists():
        return {"status": "nothing to migrate", "signals": 0, "archived": 0, "files": []}

    signals = _tag(_read(old_signals))
    files = [target / "signals.json"]
    archived = 0
    old_archive = data_dir / "archive"
    year_files = sorted(old_archive.glob("signals-*.json")) if old_archive.exists() else []

    if not dry_run:
        _write(target / "signals.json", signals)
    for year_file in year_files:
        batch = _tag(_read(year_file))
        archived += len(batch)
        files.append(target / "archive" / year_file.name)
        if not dry_run:
            _write(target / "archive" / year_file.name, batch)
    if (old_archive / "ids.json").exists():
        files.append(target / "archive" / "ids.json")
        if not dry_run:
            shutil.copyfile(old_archive / "ids.json", target / "archive" / "ids.json")
    old_status = data_dir / "run_status.json"
    if old_status.exists():
        files.append(target / "run_status.json")
        if not dry_run:
            _write(target / "run_status.json", {**_read(old_status), "sector": SLUG})

    if not dry_run:
        # The top-level signals.json/run_status.json stay as the dashboard's
        # compatibility copy; the old archive now lives under data/gambling/.
        if old_archive.exists():
            shutil.rmtree(old_archive)
        from src import sectors
        sectors.update_index(SLUG, name="Gambling & gaming", status="ready",
                             signal_count=len(signals),
                             last_run_at=datetime.now(timezone.utc).isoformat(), error=None)

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
