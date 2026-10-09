"""Move today's single-sector data into data/gambling/ by hand. The pipeline
does this itself on its first run after the sector change; this is for
local use.

    python -m scripts.migrate_to_sectors --dry-run
    python -m scripts.migrate_to_sectors
"""

import argparse
import json
import sys

from src.migrate import migrate


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    report = migrate(dry_run=args.dry_run)
    print(json.dumps(report, indent=2))
    if report["status"] == "stale":
        print(
            f"WARNING: data/signals.json holds {report['stale_ids']} signal id(s) "
            "that data/gambling/ does not have. data/gambling/ is older than the "
            "top-level store; nothing was changed. Resolve by hand (e.g. remove "
            "data/gambling/signals.json to re-run the full copy).",
            file=sys.stderr,
        )
    if args.dry_run:
        print("Dry run — nothing written.")


if __name__ == "__main__":
    main()
