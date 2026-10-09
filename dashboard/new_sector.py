"""Pure helpers for the dashboard's new-sector dialog."""

from __future__ import annotations

from src.drafting import DEFAULT_SOURCE_SETTINGS, GENERIC_SOURCES, MAX_COMPANIES, MIN_COMPANIES
from src.entities import match_key

# The review form's company table: its column names, mapped to config keys.
NAME_COL, NUMBER_COL, VERIFIED_COL = "Name", "Companies House number", "Verified"
_COLUMNS = {NAME_COL: "name", NUMBER_COL: "company_number"}


def apply_review(config: dict, *, name: str, brief: str, keywords: list[str],
                 companies: list[dict], sources: list[str]) -> dict:
    """The draft with the review form's edits applied. Company numbers come
    back as text or None (verification happens separately, on create)."""
    out = dict(config)
    out["name"] = name.strip() or config["name"]
    out["brief"] = brief.strip() or config["brief"]
    out["keywords"] = [k.strip() for k in keywords if isinstance(k, str) and k.strip()]
    rows, seen = [], set()
    for c in companies:
        cname = str(c.get("name") or "").strip()
        key = match_key(cname) or cname.lower()
        if not cname or key in seen:
            continue
        seen.add(key)
        number = c.get("company_number")
        number = str(number).strip() if number not in (None, "") else None
        rows.append({"name": cname, "company_number": number or None,
                     "aliases": list(c.get("aliases") or [])})
    out["companies"] = rows[:MAX_COMPANIES]
    out["sources"] = {s: dict(config["sources"].get(s, DEFAULT_SOURCE_SETTINGS[s]))
                      for s in sources if s in GENERIC_SOURCES}
    return out


def review_problem(config: dict) -> str | None:
    """What stops the reviewed config (apply_review's output) being saved, in
    the form's words; None if it can be saved."""
    if not config.get("keywords"):
        return "Add at least one keyword."
    if not MIN_COMPANIES <= len(config.get("companies") or []) <= MAX_COMPANIES:
        return f"Keep between {MIN_COMPANIES} and {MAX_COMPANIES} companies."
    if not config.get("sources"):
        return "Choose at least one source."
    return None


def merge_pending(index: list[dict] | None, pending: list[dict]) -> list[dict] | None:
    """Sectors created this session but not yet in the (cached, CDN-delayed)
    remote index, appended to it. The remote entry wins once it appears."""
    if index is None:
        return None
    have = {e.get("slug") for e in index if isinstance(e, dict)}
    return list(index) + [p for p in pending if p["slug"] not in have]


def _number(value) -> str:
    return str(value).strip().upper() if value not in (None, "") else ""


def editor_rows(companies: list[dict], drafted: list[dict]) -> list[dict]:
    """The company table as shown. A row keeps its Verified tick only while its
    name and number still match a drafted row Companies House confirmed; any
    edit clears it (saving re-verifies every number either way)."""
    confirmed = {(c.get("name"), _number(c.get("company_number")))
                 for c in drafted if c.get("verified") and _number(c.get("company_number"))}
    return [{NAME_COL: c.get("name") or "",
             NUMBER_COL: c.get("company_number") or "",
             VERIFIED_COL: "✓" if (c.get("name"), _number(c.get("company_number"))) in confirmed
             else "–"}
            for c in companies]


def apply_editor_changes(companies: list[dict], changes: dict | None) -> list[dict]:
    """The company rows with a data editor's change set applied (edited, then
    deleted, then added rows, as Streamlit reports them). Pure: the input
    list is left as it was."""
    if not changes:
        return [dict(c) for c in companies]
    rows = [dict(c, aliases=list(c.get("aliases") or [])) for c in companies]
    for index, edits in (changes.get("edited_rows") or {}).items():
        i = int(index)
        if 0 <= i < len(rows):
            for col, value in edits.items():
                if col in _COLUMNS:
                    rows[i][_COLUMNS[col]] = value
    deleted = {int(i) for i in changes.get("deleted_rows") or []}
    rows = [r for i, r in enumerate(rows) if i not in deleted]
    for added in changes.get("added_rows") or []:
        rows.append({"name": added.get(NAME_COL) or "",
                     "company_number": added.get(NUMBER_COL) or None, "aliases": []})
    return rows
