import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

DEFAULT_PATH = Path("data/signals.json")
ARCHIVE_DIR = Path("data/archive")
ARCHIVE_IDS_PATH = ARCHIVE_DIR / "ids.json"

# How much history the live store keeps. Everything older rolls into
# data/archive/signals-YYYY.json. Four months keeps the file the dashboard
# downloads on every session small while staying ahead of the 90-day
# clustering window — every signal eligible to cluster is still live, with a
# month of headroom. Keep this comfortably above the window if either moves.
RETENTION_DAYS = 120

logger = logging.getLogger(__name__)


def load(path: Path = DEFAULT_PATH) -> list[dict]:
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def load_archived_ids(path: Path = ARCHIVE_IDS_PATH) -> set[str]:
    """Ids of signals that have aged out of the live store.

    Sources keep listing old items — Companies House returns the last 25
    filings regardless of age, and the Gazette and ASA listings carry older
    entries — so without this an archived signal would be re-ingested, re-
    scored at cost, and resurface in the feed as if it were new.
    """
    if not path.exists():
        return set()
    with open(path, "r", encoding="utf-8") as f:
        return set(json.load(f))


def _parse_date(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _archive(signals: list[dict], archive_dir: Path, ids_path: Path) -> None:
    """Append aged-out signals to their published-year file. Append-only and
    idempotent — an id already present in a year file is never rewritten."""
    if not signals:
        return

    by_year: dict[str, list[dict]] = {}
    for signal in signals:
        year = signal["published_at"][:4]
        by_year.setdefault(year, []).append(signal)

    archived_ids = load_archived_ids(ids_path)

    for year, batch in sorted(by_year.items()):
        year_path = archive_dir / f"signals-{year}.json"
        existing = load(year_path)
        existing_ids = {s["id"] for s in existing}
        additions = [s for s in batch if s["id"] not in existing_ids]
        if additions:
            _write_json(year_path, existing + additions)
        archived_ids.update(s["id"] for s in batch)

    _write_json(ids_path, sorted(archived_ids))
    logger.info("Archived %d signals past the %d-day window", len(signals), RETENTION_DAYS)


def save(
    signals: list[dict],
    path: Path = DEFAULT_PATH,
    retention_days: int | None = RETENTION_DAYS,
    now: datetime | None = None,
    archive_dir: Path = ARCHIVE_DIR,
    ids_path: Path = ARCHIVE_IDS_PATH,
) -> list[dict]:
    """Persist the live store, rolling anything older than the retention window
    into the archive first so an interrupted run can't drop signals. Returns
    the signals that remain live."""
    if retention_days is None:
        _write_json(path, signals)
        return signals

    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=retention_days)

    live, aged_out = [], []
    for signal in signals:
        (live if _parse_date(signal["published_at"]) >= cutoff else aged_out).append(
            signal
        )

    # Archive is written first: a crash between the two writes leaves a
    # duplicate, which _archive tolerates, rather than a hole.
    _archive(aged_out, archive_dir, ids_path)
    _write_json(path, live)
    return live


def merge_new(
    existing: list[dict],
    new_signals: list[dict],
    known_ids: set[str] | None = None,
) -> tuple[list[dict], list[dict]]:
    """Append signals whose id isn't already present, in the live store or in
    `known_ids` (the archive). Never overwrites history."""
    seen_ids = {s["id"] for s in existing} | (known_ids or set())
    added = [s for s in new_signals if s["id"] not in seen_ids]
    return existing + added, added
