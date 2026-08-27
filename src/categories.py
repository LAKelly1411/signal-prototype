"""Category canonicalisation.

`category` was free text, and Claude spelled the same theme a different way
almost every time: 350 distinct labels across 972 signals, with a single wave
of gambling-sector insolvencies split across "insolvency filing",
"winding-up petition", "winding up petition", "company winding-up",
"insolvency/liquidation" and ten more. That made cross-company theme
detection impossible and turned the dashboard's category chips into noise.

New signals are constrained to TAXONOMY by the scoring prompt. Signals scored
before that are mapped here by keyword, so the existing store can be
backfilled without paying to re-score it.

Rule order matters: the first matching theme wins, so the more specific
framing is listed first. "AML/licence enforcement" is an AML story, not a
licence story.
"""

import re

AML = "AML and compliance failures"
ADVERTISING = "Advertising ruling"
BOARD = "Board and director changes"
CONSULTATION = "Consultation"
CORPORATE_FILING = "Corporate filing"
DISQUALIFICATION = "Director disqualification"
ENFORCEMENT = "Enforcement action"
RESULTS = "Financial results"
ILLEGAL = "Illegal gambling"
INSOLVENCY = "Insolvency"
LICENCE = "Licence action"
MERGER = "Merger and acquisition"
PLAYER_PROTECTION = "Player protection"
POLICY = "Policy and legislation"
SHAREHOLDING = "Shareholding disclosure"
TAX = "Tax and levy"
OTHER = "Other"

TAXONOMY = [
    AML,
    ADVERTISING,
    BOARD,
    CONSULTATION,
    CORPORATE_FILING,
    DISQUALIFICATION,
    ENFORCEMENT,
    RESULTS,
    ILLEGAL,
    INSOLVENCY,
    LICENCE,
    MERGER,
    PLAYER_PROTECTION,
    POLICY,
    SHAREHOLDING,
    TAX,
    OTHER,
]

# (theme, pattern) in priority order. Patterns run against the legacy category
# label first, and against the title only if the label decides nothing.
_RULES: list[tuple[str, re.Pattern]] = [
    (AML, re.compile(r"\baml\b|money laundering|anti-money", re.I)),
    (DISQUALIFICATION, re.compile(r"disqualif", re.I)),
    (INSOLVENCY, re.compile(
        r"insolven|winding.?up|wound.?up|liquidat|administrat|receivership|"
        r"creditors|dissolution|struck off", re.I)),
    (ILLEGAL, re.compile(r"illegal|black market|unlicensed|untaxed", re.I)),
    (ADVERTISING, re.compile(r"advertis|\basa\b|marketing standard|promotion", re.I)),
    (PLAYER_PROTECTION, re.compile(
        r"social responsib|player protect|safer gambling|problem gambling|"
        r"self.?exclu|affordability|harm", re.I)),
    (LICENCE, re.compile(r"licen[cs]e|licensing", re.I)),
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

# signal_type is a coarse fallback when nothing above matches.
_SIGNAL_TYPE_FALLBACK = {
    "insolvency": INSOLVENCY,
    "enforcement": ENFORCEMENT,
    "consultation": CONSULTATION,
    "corporate_filing": CORPORATE_FILING,
    "policy": POLICY,
    "regulatory": LICENCE,
}

_TAXONOMY_LOOKUP = {t.lower(): t for t in TAXONOMY}


def canonical_category(
    category: str | None,
    title: str = "",
    signal_type: str | None = None,
) -> str:
    """Map a signal onto one of TAXONOMY. Already-canonical values pass
    straight through, so re-running this is a no-op."""
    if category:
        exact = _TAXONOMY_LOOKUP.get(category.strip().lower())
        if exact:
            return exact

    for text in (category or "", title or ""):
        if not text.strip():
            continue
        for theme, pattern in _RULES:
            if pattern.search(text):
                return theme

    return _SIGNAL_TYPE_FALLBACK.get(signal_type or "", OTHER)


def category_of(signal: dict) -> str:
    """Canonical theme for a stored signal, preferring the value the pipeline
    already resolved so the dashboard doesn't recompute it every render."""
    resolved = signal.get("canonical_category")
    if resolved:
        return resolved
    return canonical_category(
        signal.get("category"), signal.get("title", ""), signal.get("signal_type")
    )
