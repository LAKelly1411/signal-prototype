"""Where the dashboard's data comes from, and which sector it shows.

Each sector's data sits in the repo at data/<slug>/ and is read over GitHub
raw from DATA_BASE_URL; data/sectors.json lists the sectors. Until main has
that index (the first pipeline run after the stage 1 merge creates it), the
dashboard falls back to the single gambling file it has always read.

No Streamlit here, so all of this is unit tested; dashboard/app.py wraps the
loaders in st.cache_data.
"""

from __future__ import annotations

import logging

import requests

from src.sectors import SLUG_RE, SectorConfigError, load_sector

logger = logging.getLogger(__name__)

GAMBLING = "gambling"
LEGACY_INDEX = [{"slug": GAMBLING, "name": "Gambling & gaming", "status": "ready"}]


class DataError(Exception):
    """A sector's signals couldn't be loaded (other than not existing yet)."""


def _is_slug(value) -> bool:
    # fullmatch, not match: SLUG_RE's "$" also accepts a trailing newline.
    return isinstance(value, str) and SLUG_RE.fullmatch(value) is not None


def _get_json(url: str):
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()
    return resp.json()


def _base(url: str | None) -> str | None:
    """DATA_BASE_URL with exactly one trailing slash, or None when unset."""
    if not url or not url.strip():
        return None
    return url.strip().rstrip("/") + "/"


def load_index(base_url: str | None) -> list[dict] | None:
    """The sector index, or None to mean "use the legacy single file"."""
    base_url = _base(base_url)
    if not base_url:
        return None
    try:
        index = _get_json(base_url + "sectors.json")
    except Exception:
        logger.info("No sector index at %s — using the legacy data file", base_url)
        return None
    if not isinstance(index, list):
        logger.warning("Sector index is not a list — using the legacy data file")
        return None
    return index


def load_signals(base_url: str, slug: str) -> list[dict]:
    """A sector's live signals. Not there yet (404) is an empty list: the
    sector is still setting up."""
    if not _is_slug(slug):
        raise DataError(f"Not a sector slug: {slug!r}")
    url = f"{_base(base_url)}{slug}/signals.json"
    try:
        resp = requests.get(url, timeout=20)
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        raise DataError(f"Couldn't load {url}: {exc}") from exc


def load_run_status(base_url: str, slug: str) -> dict | None:
    if not _is_slug(slug):
        return None
    try:
        return _get_json(f"{_base(base_url)}{slug}/run_status.json")
    except Exception:
        return None


def load_legacy_signals(url: str) -> list[dict]:
    try:
        return _get_json(url)
    except Exception as exc:
        raise DataError(f"Couldn't load {url}: {exc}") from exc


def load_legacy_status(url: str | None) -> dict | None:
    if not url:
        return None
    try:
        return _get_json(url)
    except Exception:
        return None


def order_index(entries: list[dict]) -> list[dict]:
    """Gambling first (the original sector), then alphabetical by slug. Entries
    without a valid slug are dropped: a slug ends up in URLs and file paths.
    Non-dict entries (a malformed remote index) are dropped too. The result can
    be empty; the caller then substitutes LEGACY_INDEX."""
    valid = [e for e in entries if isinstance(e, dict) and _is_slug(e.get("slug"))]
    return sorted(valid, key=lambda e: (e["slug"] != GAMBLING, e["slug"]))


def pick_sector(entries: list[dict], requested: str | None) -> str:
    """The sector to show: the requested one if it's listed, else gambling,
    else the first. Only ever returns a slug from the index.

    Expects entries from order_index. An empty list raises ValueError: the
    caller replaces an empty ordered index with LEGACY_INDEX before calling."""
    if not entries:
        raise ValueError("no sectors")
    slugs = [e["slug"] for e in entries]
    if requested in slugs:
        return requested
    if GAMBLING in slugs:
        return GAMBLING
    return slugs[0]


def sector_note(entry: dict) -> str:
    """The muted note beside a sector in the switcher."""
    status = entry.get("status")
    if status == "setting_up":
        return "Setting up…"
    if status == "error":
        return "Update failed"
    count = entry.get("signal_count")
    return str(count) if count is not None else ""


def view_state(entry: dict, signals: list[dict]) -> str:
    """What the page shows under the header for this sector."""
    if entry.get("status") == "error":
        return "error_with_data" if signals else "error_empty"
    return "ready" if signals else "setting_up"


def sector_rules(slug: str):
    """The sector's config, for exclusions and theme heat. A sector listed in
    the index but without a config in this deploy falls back to gambling's
    rules rather than breaking the page. An invalid slug gets gambling's rules too."""
    if not _is_slug(slug):
        return load_sector(GAMBLING)
    try:
        return load_sector(slug)
    except SectorConfigError:
        logger.warning("No usable config for sector %r — using gambling's rules", slug)
        return load_sector(GAMBLING)


def user_watchlist_path(slug: str) -> str:
    """Where the dashboard's "Add to watchlist" writes for this sector."""
    if not _is_slug(slug):
        raise ValueError(f"Not a sector slug: {slug!r}")
    return f"config/sectors/{slug}.user.yaml"
