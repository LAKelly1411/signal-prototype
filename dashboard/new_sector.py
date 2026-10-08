"""Pure helpers for the dashboard's new-sector dialog."""

from __future__ import annotations

from src.drafting import DEFAULT_SOURCE_SETTINGS, GENERIC_SOURCES


def apply_review(config: dict, *, name: str, brief: str, keywords: list[str],
                 companies: list[dict], sources: list[str]) -> dict:
    """The draft with the review form's edits applied. Company numbers come
    back as text or None (verification happens separately, on create)."""
    out = dict(config)
    out["name"] = name.strip() or config["name"]
    out["brief"] = brief.strip() or config["brief"]
    out["keywords"] = [k.strip() for k in keywords if isinstance(k, str) and k.strip()]
    rows = []
    for c in companies:
        cname = str(c.get("name") or "").strip()
        if not cname:
            continue
        number = c.get("company_number")
        number = str(number).strip() if number not in (None, "") else None
        rows.append({"name": cname, "company_number": number or None,
                     "aliases": list(c.get("aliases") or [])})
    out["companies"] = rows
    out["sources"] = {s: dict(config["sources"].get(s, DEFAULT_SOURCE_SETTINGS[s]))
                      for s in sources if s in GENERIC_SOURCES}
    return out


def merge_pending(index: list[dict] | None, pending: list[dict]) -> list[dict] | None:
    """Sectors created this session but not yet in the (cached, CDN-delayed)
    remote index, appended to it. The remote entry wins once it appears."""
    if index is None:
        return None
    have = {e.get("slug") for e in index if isinstance(e, dict)}
    return list(index) + [p for p in pending if p["slug"] not in have]
