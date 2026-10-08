"""Drafting a new sector with Claude, for the dashboard's premium "New sector"
flow. Claude proposes the whole config through one tool call; we normalise it
(slug, generic sources only, safe category patterns), check every company
number against Companies House, and validate the result with the same rules
as a hand-written config before anyone sees it.

No Streamlit here: dashboard/app.py calls draft_sector and shows the result.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import requests

from src.categories import CORE_RULE_NAMES
from src.entities import match_key
from src.sectors import PROMPT_FIELDS, SLUG_RE, SectorConfigError, parse_sector

GENERIC_SOURCES = ("companies_house", "gazette", "dcms", "parliament", "asa",
                   "insolvency_service", "lse_rns")
MAX_PATTERN = 200
MIN_COMPANIES, MAX_COMPANIES = 3, 12
MIN_DESCRIPTION, MAX_DESCRIPTION = 10, 300
NUMBER_RE = re.compile(r"[0-9A-Z]{8}")

# Settings each source gets in a drafted sector (the fintech values).
DEFAULT_SOURCE_SETTINGS = {
    "companies_house": {"items_per_page": 25, "sleep_seconds": 0.6, "lookback_days": 365},
    "gazette": {"results_per_term": 20, "sleep_seconds": 1.0},
    "dcms": {"results_per_term": 20},
    "parliament": {"results_per_term": 20},
    "asa": {},
    "insolvency_service": {"sleep_seconds": 1.0},
    "lse_rns": {"skip_titles": [
        "holding(s) in company", "notification of major holdings",
        "director/pdmr shareholding", "transaction in own shares",
        "total voting rights", "block listing",
    ]},
}


class DraftError(Exception):
    """Claude's draft couldn't be turned into a valid sector, even on retry."""


@dataclass
class Draft:
    slug: str
    config: dict
    companies: list[dict] = field(default_factory=list)  # with "verified"


def slugify(name: str) -> str:
    text = str(name).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40].strip("-")
    return slug if slug and SLUG_RE.fullmatch(slug) else "sector"


def unique_slug(name: str, existing: set[str]) -> str:
    base = slugify(name)
    slug, n = base, 2
    while slug in existing:
        suffix = f"-{n}"
        slug = base[: 40 - len(suffix)] + suffix
        n += 1
    return slug


class CompaniesHouse:
    URL = "https://api.company-information.service.gov.uk/company/{}"

    def __init__(self, api_key: str, get=requests.get):
        self.api_key = api_key
        self._get = get

    def lookup(self, number: str) -> dict | None:
        try:
            resp = self._get(self.URL.format(number), auth=(self.api_key, ""), timeout=10)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return None


def _names_match(a: str, b: str) -> bool:
    ka, kb = match_key(a), match_key(b)
    return bool(ka and kb) and (ka == kb or ka in kb or kb in ka)


def verify_companies(companies: list[dict], ch: CompaniesHouse | None) -> list[dict]:
    """Each company with its number kept only if Companies House confirms it
    (active, matching name). Everything else is tracked by name alone."""
    out = []
    for company in companies:
        row = dict(company)
        raw = row.get("company_number")
        number = raw.strip().upper() if isinstance(raw, str) else None
        verified = False
        if ch is not None and number and NUMBER_RE.fullmatch(number):
            record = ch.lookup(number)
            verified = bool(record) and record.get("company_status") == "active" and \
                _names_match(record.get("company_name", ""), row.get("name", ""))
        row["company_number"] = number if verified else None
        row["verified"] = verified
        out.append(row)
    return out


def _require(cond: bool, message: str) -> None:
    if not cond:
        raise ValueError(message)


def normalise_draft(raw: dict, existing: set[str], now: datetime | None = None) -> dict:
    """Claude's proposal → a sector config dict. Raises ValueError for shapes
    that can't be repaired; drops parts that are merely unsafe."""
    _require(isinstance(raw, dict), "proposal must be an object")
    name = raw.get("name")
    _require(isinstance(name, str) and name.strip(), "name is required")
    _require(isinstance(raw.get("brief"), str) and raw["brief"].strip(), "brief is required")
    prompt = raw.get("prompt")
    _require(isinstance(prompt, dict), "prompt must be an object")
    for key in ("keywords", "companies", "excluded_bodies", "categories", "sources"):
        _require(isinstance(raw.get(key, []), list), f"{key} must be a list")
    _require(isinstance(raw.get("tickers", {}), dict), "tickers must be an object")
    _require(isinstance(raw.get("signal_type_fallback", {}), dict), "signal_type_fallback must be an object")

    companies, seen = [], set()
    for c in raw.get("companies", []):
        _require(isinstance(c, dict) and isinstance(c.get("name"), str), "each company needs a name")
        key = match_key(c["name"])
        if not key or key in seen:
            continue
        seen.add(key)
        aliases = c.get("aliases") or []
        companies.append({
            "name": c["name"].strip(),
            "company_number": c.get("company_number"),
            "aliases": [a for a in aliases if isinstance(a, str)] if isinstance(aliases, list) else [],
        })
    companies = companies[:MAX_COMPANIES]
    _require(len(companies) >= MIN_COMPANIES, f"need at least {MIN_COMPANIES} companies")

    categories = []
    for cat in raw.get("categories", []):
        if not (isinstance(cat, dict) and isinstance(cat.get("name"), str)
                and isinstance(cat.get("pattern"), str) and len(cat["pattern"]) <= MAX_PATTERN
                and cat.get("before") in CORE_RULE_NAMES):
            continue
        try:
            re.compile(cat["pattern"], re.I)
        except re.error:
            continue
        categories.append({"name": cat["name"], "pattern": cat["pattern"], "before": cat["before"]})
    allowed = CORE_RULE_NAMES | {c["name"] for c in categories} | {"Other"}
    fallback = {k: v for k, v in raw.get("signal_type_fallback", {}).items() if v in allowed}

    sources = {}
    for key in raw.get("sources", []):
        if key in GENERIC_SOURCES and key not in sources:
            sources[key] = dict(DEFAULT_SOURCE_SETTINGS[key])
    _require(bool(sources), "at least one generic source is required")
    org = raw.get("dcms_organisation")
    if "dcms" in sources and isinstance(org, str) and re.fullmatch(r"[a-z0-9-]{3,80}", org):
        sources["dcms"]["organisation"] = org

    now = now or datetime.now(timezone.utc)
    return {
        "slug": unique_slug(name, existing),
        "name": name.strip(),
        "brief": raw["brief"].strip(),
        "created_at": now.isoformat(),
        "prompt": {k: prompt.get(k) for k in PROMPT_FIELDS},
        "keywords": [k for k in raw.get("keywords", []) if isinstance(k, str) and k.strip()],
        "companies": companies,
        "tickers": {str(k): str(v) for k, v in raw.get("tickers", {}).items()},
        "categories": categories,
        "signal_type_fallback": fallback,
        "excluded_bodies": [b.lower() for b in raw.get("excluded_bodies", []) if isinstance(b, str)],
        "sources": sources,
    }


_EXAMPLE = Path("config/sectors/gambling.yaml")

PROPOSE_SECTOR_TOOL = {
    "name": "propose_sector",
    "description": "Propose a complete Sector Signal sector config.",
    "input_schema": {
        "type": "object",
        "required": ["name", "brief", "prompt", "keywords", "companies", "sources"],
        "properties": {
            "name": {"type": "string", "description": "Short display name, e.g. 'Energy retail'"},
            "brief": {"type": "string", "description": "One sentence on what the newsroom covers"},
            "prompt": {"type": "object", "required": list(PROMPT_FIELDS),
                       "properties": {f: {"type": "string"} for f in PROMPT_FIELDS}},
            "keywords": {"type": "array", "items": {"type": "string"}},
            "companies": {"type": "array", "items": {"type": "object", "required": ["name"], "properties": {
                "name": {"type": "string", "description": "Registered UK company name"},
                "company_number": {"type": ["string", "null"],
                                   "description": "8-character Companies House number, only if certain; else null"},
                "aliases": {"type": "array", "items": {"type": "string"}}}}},
            "tickers": {"type": "object", "additionalProperties": {"type": "string"},
                        "description": "LSE ticker -> company name, only certain ones"},
            "categories": {"type": "array", "items": {"type": "object", "required": ["name", "pattern", "before"],
                           "properties": {"name": {"type": "string"}, "pattern": {"type": "string"},
                                          "before": {"type": "string", "enum": sorted(CORE_RULE_NAMES)}}}},
            "signal_type_fallback": {"type": "object", "additionalProperties": {"type": "string"}},
            "excluded_bodies": {"type": "array", "items": {"type": "string"}},
            "sources": {"type": "array", "items": {"type": "string", "enum": list(GENERIC_SOURCES)}},
            "dcms_organisation": {"type": "string",
                                  "description": "GOV.UK organisation slug whose publications to search, "
                                                 "e.g. department-for-energy-security-and-net-zero"},
        },
    },
}


def _system_prompt() -> str:
    example = _EXAMPLE.read_text(encoding="utf-8") if _EXAMPLE.exists() else ""
    return (
        "You design sector configs for Sector Signal, a B2B newsroom tool that collects UK "
        "regulatory, corporate and parliamentary items about one industry and scores them for "
        "newsworthiness. Propose a config for the industry the user describes by calling "
        "propose_sector exactly once.\n\n"
        "Rules:\n"
        f"- prompt needs all of: {', '.join(PROMPT_FIELDS)}. Match the tone and length of the example.\n"
        f"- companies: {MIN_COMPANIES}-{MAX_COMPANIES} of the most important UK companies, using registered "
        "names. Give company_number only if you are certain of it; otherwise null.\n"
        f"- sources: choose from {', '.join(GENERIC_SOURCES)} only.\n"
        f"- categories: 2-4 industry-specific ones; each pattern a short case-insensitive regex "
        f"(at most {MAX_PATTERN} characters) that won't match routine corporate filings; before must be one "
        f"of: {', '.join(sorted(CORE_RULE_NAMES))}.\n"
        "- excluded_bodies: the industry's regulators and trade bodies, lower case.\n"
        "- tickers: only LSE tickers you are certain of.\n\n"
        "This is the existing gambling sector, as a worked example of the format and tone:\n\n" + example
    )


def _tool_input(response) -> dict:
    for block in getattr(response, "content", []) or []:
        if getattr(block, "type", None) == "tool_use" and getattr(block, "name", None) == "propose_sector":
            return block.input
    raise ValueError("no propose_sector tool call in the response")


def draft_sector(description: str, existing_slugs: set[str], client,
                 ch: CompaniesHouse | None = None, now: datetime | None = None) -> Draft:
    """Draft, normalise, verify and validate a sector. One retry with the
    validation error fed back; then DraftError."""
    description = (description or "").strip()
    if not (MIN_DESCRIPTION <= len(description) <= MAX_DESCRIPTION):
        raise ValueError(f"description must be {MIN_DESCRIPTION}-{MAX_DESCRIPTION} characters")
    model = os.environ.get("ANTHROPIC_MODEL") or "claude-sonnet-5"
    messages = [{"role": "user", "content": f"Industry to track: {description}"}]
    request = f"Industry to track: {description}"
    last_error = None
    for _ in range(2):
        response = client.messages.create(
            model=model, max_tokens=4000, system=_system_prompt(),
            messages=[{"role": "user", "content": request}],
            tools=[PROPOSE_SECTOR_TOOL], tool_choice={"type": "tool", "name": "propose_sector"},
        )
        try:
            config = normalise_draft(_tool_input(response), existing_slugs, now=now)
            rows = verify_companies(config["companies"], ch)
            config["companies"] = [{k: v for k, v in r.items() if k != "verified"} for r in rows]
            parse_sector(config, config["slug"])
            return Draft(slug=config["slug"], config=config, companies=rows)
        except (ValueError, SectorConfigError, KeyError, TypeError, AttributeError) as exc:
            last_error = exc
            # One user turn: the API doesn't take consecutive user messages.
            request = (f"Industry to track: {description}\n\n"
                       f"That proposal was invalid: {exc}. Call propose_sector again, fixing it.")
    raise DraftError(str(last_error))
