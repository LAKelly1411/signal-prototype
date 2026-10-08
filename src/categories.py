"""Category canonicalisation.

`category` was free text, and Claude spelled the same theme a different way
almost every time: 350 distinct labels across 972 signals, with a single wave
of gambling-sector insolvencies split across "insolvency filing",
"winding-up petition", "winding up petition", "company winding-up",
"insolvency/liquidation" and ten more. That made cross-company theme
detection impossible and turned the dashboard's category chips into noise.

New signals are constrained to the sector's taxonomy by the scoring prompt. Signals scored
before that are mapped here by keyword, so the existing store can be
backfilled without paying to re-score it.

Rule order matters: the first matching theme wins, so the more specific
framing is listed first. "AML/licence enforcement" is an AML story, not a
licence story.

Categories are per sector. A core set, below, applies everywhere. A sector's
config adds its own categories, each slotted in ahead of a named core rule
(`before`), so rule priority is under the sector's control. Gambling's
additions - Illegal gambling, Advertising ruling, Player protection, Licence
action - live in config/sectors/gambling.yaml.
"""

import re
from dataclasses import dataclass
from functools import lru_cache

AML = "AML and compliance failures"
BOARD = "Board and director changes"
CONSULTATION = "Consultation"
CORPORATE_FILING = "Corporate filing"
DISQUALIFICATION = "Director disqualification"
ENFORCEMENT = "Enforcement action"
RESULTS = "Financial results"
INSOLVENCY = "Insolvency"
MERGER = "Merger and acquisition"
POLICY = "Policy and legislation"
SHAREHOLDING = "Shareholding disclosure"
TAX = "Tax and levy"
OTHER = "Other"

# Gambling-only names, kept as constants for callers and tests; their rules
# live in config/sectors/gambling.yaml.
ADVERTISING = "Advertising ruling"
ILLEGAL = "Illegal gambling"
LICENCE = "Licence action"
PLAYER_PROTECTION = "Player protection"

# (theme, pattern) in priority order. Patterns run against the legacy category
# label first, and against the title only if the label decides nothing.
_CORE_RULES: list[tuple[str, re.Pattern]] = [
    (AML, re.compile(r"\baml\b|money laundering|anti-money", re.I)),
    (DISQUALIFICATION, re.compile(r"disqualif", re.I)),
    (INSOLVENCY, re.compile(
        r"insolven|winding.?up|wound.?up|liquidat|administrat|receivership|"
        r"creditors|dissolution|struck off", re.I)),
    (ENFORCEMENT, re.compile(
        r"enforcement|penalt|fine|sanction|settlement|regulatory action|"
        r"compliance failure|breach", re.I)),
    (MERGER, re.compile(
        r"acquisit|merger|takeover|scheme document|scheme of arrangement|"
        r"court meeting|divest|disposal|delisting|offer for|restructur", re.I)),
    (SHAREHOLDING, re.compile(
        r"shareholding|shareholder|share buyback|buy.?back|voting rights|"
        r"major holding|\bpdmr\b|\btr.?1\b|director dealing|issuance of shares",
        re.I)),
    (BOARD, re.compile(
        r"director (change|appointment|resignation)|board|directorate|"
        r"officer filing|\bpsc\b|person with significant", re.I)),
    (TAX, re.compile(r"\btax|duty|levy|\bhmrc\b|treasury", re.I)),
    (CONSULTATION, re.compile(r"consultation|call for evidence|white paper", re.I)),
    (RESULTS, re.compile(
        r"results|trading (update|statement)|earnings|interim|annual report|"
        r"\bagm\b|financial performance", re.I)),
    (CORPORATE_FILING, re.compile(
        r"accounts filing|confirmation statement|charge (filing|release)|"
        r"registered office|company filing|mortgage|capital", re.I)),
    (POLICY, re.compile(
        r"policy|legislat|parliament|debate|regulation|reform|speech|"
        r"select committee|statistics|government", re.I)),
]
CORE_RULE_NAMES = {name for name, _ in _CORE_RULES}

# signal_type is a coarse fallback when nothing matches. A sector can
# override entries (gambling maps regulatory to Licence action).
_CORE_FALLBACK = {
    "insolvency": INSOLVENCY,
    "enforcement": ENFORCEMENT,
    "consultation": CONSULTATION,
    "corporate_filing": CORPORATE_FILING,
    "policy": POLICY,
    "regulatory": OTHER,
}


@dataclass(frozen=True)
class Ruleset:
    taxonomy: list[str]
    rules: list[tuple[str, re.Pattern]]
    fallback: dict[str, str]


@lru_cache(maxsize=1)
def default_sector():
    """Gambling, the sector every sector=None call means."""
    from src.sectors import load_sector
    return load_sector("gambling")


_RULESETS: dict[str, Ruleset] = {}


def ruleset(sector=None) -> Ruleset:
    sector = sector or default_sector()
    cached = _RULESETS.get(sector.slug)
    if cached is not None:
        return cached
    rules = list(_CORE_RULES)
    for cat in sector.categories:
        position = next(i for i, (name, _) in enumerate(rules) if name == cat["before"])
        rules.insert(position, (cat["name"], re.compile(cat["pattern"], re.I)))
    names = sorted(CORE_RULE_NAMES | {cat["name"] for cat in sector.categories})
    built = Ruleset(
        taxonomy=names + [OTHER],
        rules=rules,
        fallback={**_CORE_FALLBACK, **sector.signal_type_fallback},
    )
    _RULESETS[sector.slug] = built
    return built


def taxonomy(sector=None) -> list[str]:
    return list(ruleset(sector).taxonomy)


def canonical_category(
    category: str | None,
    title: str = "",
    signal_type: str | None = None,
    sector=None,
) -> str:
    """Map a signal onto its sector's taxonomy. Already-canonical values pass
    straight through, so re-running this is a no-op."""
    rs = ruleset(sector)
    if category:
        lookup = {t.lower(): t for t in rs.taxonomy}
        exact = lookup.get(category.strip().lower())
        if exact:
            return exact

    for text in (category or "", title or ""):
        if not text.strip():
            continue
        for theme, pattern in rs.rules:
            if pattern.search(text):
                return theme

    return rs.fallback.get(signal_type or "", OTHER)


def category_of(signal: dict, sector=None) -> str:
    """Canonical theme for a stored signal, preferring the value the pipeline
    already resolved so the dashboard doesn't recompute it every render."""
    resolved = signal.get("canonical_category")
    if resolved:
        return resolved
    return canonical_category(
        signal.get("category"), signal.get("title", ""), signal.get("signal_type"),
        sector=sector,
    )
