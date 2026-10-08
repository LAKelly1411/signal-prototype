"""Sectors: one config file per sector (config/sectors/<slug>.yaml) defining
what the pipeline collects, how Claude scores it, and what counts as a company.
Dashboard additions live beside it in <slug>.user.yaml, so the app never edits
the hand-curated file. Data for each sector lives under data/<slug>/."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

CONFIG_DIR = Path("config/sectors")
DATA_DIR = Path("data")
INDEX_PATH = DATA_DIR / "sectors.json"

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")

logger = logging.getLogger(__name__)

# Sector wording slotted into the Claude prompts; see src/score.py.
PROMPT_FIELDS = (
    "newsroom", "coverage", "audience", "materiality", "key_players",
    "entity_hint", "company_word", "significance_audience", "theme_scope",
)

KNOWN_SOURCES = (
    "gambling_commission", "companies_house", "gazette", "dcms", "parliament",
    "asa", "bgc", "insolvency_service", "lse_rns",
)


class SectorConfigError(ValueError):
    """A sector config that can't be used, naming the file and the field."""

    def __init__(self, path: Path, field_name: str, message: str):
        super().__init__(f"{path}: {field_name}: {message}")
        self.path = path
        self.field_name = field_name


@dataclass
class Sector:
    slug: str
    name: str
    brief: str
    prompt: dict[str, str]
    sources: dict[str, dict]
    keywords: list[str] = field(default_factory=list)
    companies: list[dict] = field(default_factory=list)
    tickers: dict[str, str] = field(default_factory=dict)
    categories: list[dict] = field(default_factory=list)
    signal_type_fallback: dict[str, str] = field(default_factory=dict)
    excluded_bodies: list[str] = field(default_factory=list)
    created_at: str | None = None

    @property
    def data_dir(self) -> Path:
        return DATA_DIR / self.slug

    @property
    def signals_path(self) -> Path:
        return self.data_dir / "signals.json"

    @property
    def run_status_path(self) -> Path:
        return self.data_dir / "run_status.json"

    @property
    def archive_dir(self) -> Path:
        return self.data_dir / "archive"

    @property
    def archive_ids_path(self) -> Path:
        return self.archive_dir / "ids.json"


def _read_yaml(path: Path) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        raise SectorConfigError(path, "yaml", str(exc)) from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise SectorConfigError(path, "yaml", "top level must be a mapping")
    return data


def _companies(path: Path, items, where: str) -> list[dict]:
    if items is None:
        return []
    if not isinstance(items, list):
        raise SectorConfigError(path, where, "must be a list")
    out = []
    for i, company in enumerate(items):
        if not isinstance(company, dict) or not str(company.get("name") or "").strip():
            raise SectorConfigError(path, f"{where}[{i}].name", "each company needs a name")
        number = company.get("company_number")
        if number is not None and not isinstance(number, str):
            raise SectorConfigError(
                path, f"{where}[{i}].company_number",
                "must be a quoted string (YAML drops the leading zeros of a bare number)")
        out.append(company)
    return out


def _build(path: Path, raw: dict, user: dict, user_path: Path) -> Sector:
    from src.categories import CORE_RULE_NAMES, OTHER

    for key in ("slug", "name", "brief", "prompt", "sources"):
        if key not in raw or raw[key] in (None, "", {}, []):
            raise SectorConfigError(path, key, "is required")

    slug = raw["slug"]
    if slug != path.stem or not SLUG_RE.match(str(slug)):
        raise SectorConfigError(path, "slug", f"must match the filename ({path.stem}) and be [a-z0-9-]")

    prompt = raw["prompt"]
    if not isinstance(prompt, dict):
        raise SectorConfigError(path, "prompt", "must be a mapping")
    for key in PROMPT_FIELDS:
        if not isinstance(prompt.get(key), str) or not prompt[key].strip():
            raise SectorConfigError(path, f"prompt.{key}", "is required")

    sources = raw["sources"]
    if not isinstance(sources, dict):
        raise SectorConfigError(path, "sources", "must be a mapping")
    for key, settings in sources.items():
        if key not in KNOWN_SOURCES:
            raise SectorConfigError(path, f"sources.{key}", f"unknown source (known: {', '.join(KNOWN_SOURCES)})")
        if settings is not None and not isinstance(settings, dict):
            raise SectorConfigError(path, f"sources.{key}", "settings must be a mapping")
    sources = {k: (v or {}) for k, v in sources.items()}

    categories = raw.get("categories") or []
    names = set()
    for i, cat in enumerate(categories):
        where = f"categories[{i}]"
        if not isinstance(cat, dict) or not cat.get("name") or not cat.get("pattern"):
            raise SectorConfigError(path, where, "needs name and pattern")
        if cat.get("before") not in CORE_RULE_NAMES:
            raise SectorConfigError(path, f"{where}.before", f"must name a core category rule, got {cat.get('before')!r}")
        try:
            re.compile(cat["pattern"], re.I)
        except re.error as exc:
            raise SectorConfigError(path, f"{where}.pattern", f"invalid regex: {exc}") from exc
        names.add(cat["name"])

    fallback = raw.get("signal_type_fallback") or {}
    allowed = CORE_RULE_NAMES | names | {OTHER}
    for key, value in fallback.items():
        if value not in allowed:
            raise SectorConfigError(path, f"signal_type_fallback.{key}", f"unknown category {value!r}")

    for key, kind in (("keywords", list), ("excluded_bodies", list), ("tickers", dict)):
        if raw.get(key) is not None and not isinstance(raw[key], kind):
            raise SectorConfigError(path, key, f"must be a {kind.__name__}")

    companies = _companies(path, raw.get("companies"), "companies")
    # The dashboard's watchlist form writes "operators"; accept both.
    for key in ("companies", "operators"):
        companies += _companies(user_path, user.get(key), key)

    return Sector(
        slug=slug,
        name=raw["name"],
        brief=str(raw["brief"]).strip(),
        prompt={k: prompt[k] for k in PROMPT_FIELDS},
        sources=sources,
        keywords=list(raw.get("keywords") or []),
        companies=companies,
        tickers=dict(raw.get("tickers") or {}),
        categories=list(categories),
        signal_type_fallback=dict(fallback),
        excluded_bodies=list(raw.get("excluded_bodies") or []),
        created_at=raw.get("created_at"),
    )


def load_sector(slug: str, config_dir: Path | None = None) -> Sector:
    config_dir = config_dir or CONFIG_DIR
    path = config_dir / f"{slug}.yaml"
    if not path.exists():
        raise SectorConfigError(path, "file", "not found")
    user_path = config_dir / f"{slug}.user.yaml"
    user = _read_yaml(user_path) if user_path.exists() else {}
    return _build(path, _read_yaml(path), user, user_path)


def list_sector_slugs(config_dir: Path | None = None) -> list[str]:
    """Slugs of every sector config. A file whose stem isn't a valid slug is
    skipped: the slug becomes a path under data/, so `..yaml` must never run."""
    config_dir = config_dir or CONFIG_DIR
    slugs = []
    for p in sorted(config_dir.glob("*.yaml")):
        if p.name.endswith(".user.yaml"):
            continue
        if not SLUG_RE.match(p.stem):
            logger.warning("Skipping %s: %r is not a valid sector slug", p, p.stem)
            continue
        slugs.append(p.stem)
    return slugs


def read_index() -> dict[str, dict]:
    if not INDEX_PATH.exists():
        return {}
    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        return {e["slug"]: e for e in json.load(f)}


def _write_index(index: dict[str, dict]) -> None:
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump([index[k] for k in sorted(index)], f, indent=2, ensure_ascii=False)


def update_index(slug: str, **fields) -> None:
    """Merge fields into a sector's index entry (data/sectors.json)."""
    index = read_index()
    entry = index.get(slug, {"slug": slug})
    entry.update(fields)
    index[slug] = entry
    _write_index(index)


def refresh_index(slugs: list[str]) -> None:
    """Make sure every configured sector has an entry; new ones start as
    setting_up until their first run lands."""
    index = read_index()
    for slug in slugs:
        if slug in index:
            continue
        try:
            sector = load_sector(slug)
            index[slug] = {"slug": slug, "name": sector.name, "brief": sector.brief,
                           "created_at": sector.created_at, "status": "setting_up"}
        except Exception as exc:  # any unreadable config is that sector's error, not the run's
            index[slug] = {"slug": slug, "status": "error", "error": str(exc)}
    _write_index(index)
