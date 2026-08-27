import hashlib
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from src.categories import OTHER, category_of
from src.entities import canonicalise, match_key

# Regulators, government bodies and trade associations that get extracted as
# "entities" simply because they're the authority being discussed, not the
# subject of the signal. Clustering on these would just group "everything that
# mentions the regulator" rather than surfacing company-specific patterns.
# Matched against the canonical form, so both the bare and expanded names of
# the same body need listing.
EXCLUDED_ENTITIES = {
    "gambling commission",
    "ukgc",
    "dcms",
    "department for culture, media and sport",
    "department for culture media and sport",
    # DCMS's former name, still attached to older policy documents.
    "department for digital, culture, media and sport",
    "department for digital culture media and sport",
    "dcms select committee",
    "hmrc",
    "hm revenue & customs",
    "hm revenue and customs",
    "hm treasury",
    "treasury",
    "companies house",
    "the gazette",
    "gazette",
    "betting and gaming council",
    "bgc",
    "illegal gambling taskforce",
    "advertising standards authority",
    "asa",
    "cap",
    "committee of advertising practice",
    "insolvency service",
    "financial conduct authority",
    "fca",
    "british horseracing authority",
    "bha",
    "horserace betting levy board",
    "gamble aware",
    "gambleaware",
    "gamcare",
    "parliament",
    "uk parliament",
    "house of commons",
    "house of lords",
    "government",
    "uk government",
    "cabinet office",
    "home office",
}


def is_excluded(name: str) -> bool:
    """True for institutions that shouldn't anchor or label a cluster."""
    return match_key(name) in EXCLUDED_ENTITIES or name.strip().lower() in EXCLUDED_ENTITIES


def signal_entities(signal: dict, alias_map: dict[str, str] | None = None) -> list[str]:
    """Canonical entities for a signal, preferring the values the pipeline
    already resolved and falling back to canonicalising the raw extraction so
    signals stored before canonicalisation existed still cluster."""
    resolved = signal.get("canonical_entities")
    if resolved:
        return resolved
    return canonicalise(signal.get("entities") or [], alias_map)


def _normalize_entity(name: str) -> str:
    return name.strip().lower()


def _parse_date(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# Clustering and heat must use the same window: a cluster whose latest signal
# sits beyond the recency ramp would score as if it were dormant. Defined once
# so the two can't drift apart.
CLUSTER_WINDOW_DAYS = 90

# Ceiling on recency's contribution to heat. Deliberately independent of the
# window: recency should decay across the whole window, but never outweigh
# signal count and source diversity, which are the substantive terms.
RECENCY_MAX = 30

# Score a signal must reach to count toward a cluster's volume. Matches the
# dashboard's default "Medium and above" feed filter, so a pattern is built
# from the same signals a journalist would have chosen to read.
SIGNIFICANT_SCORE = 40

# Ceiling on the contribution of the cluster's single best signal. Volume and
# source spread describe how *sustained* a pattern is; this is what stops a
# two-signal cluster containing a record fine from being buried under a month
# of routine filings.
PEAK_SCORE_MAX = 30

# Ceiling on how much Claude's own read of a cluster can move it. Capped so a
# confident model can promote a genuinely important two-signal pattern without
# being able to override the evidence entirely.
MODEL_SIGNIFICANCE_MAX = 25

# A signal naming more companies than this is a roundup, not a connection
# between them, so it doesn't bridge clusters.
MAX_BRIDGING_ENTITIES = 4

# An entity appearing in this share of the window is behaving like an
# institution rather than a subject, and won't join signals together.
HUB_ENTITY_SHARE = 0.25
MIN_HUB_SIGNALS = 8

# Distinct companies a category must touch before it counts as a sector-wide
# theme rather than one company's run of filings.
MIN_THEME_COMPANIES = 3

# Themes need their own, lower bar. A wave is made of individually
# unremarkable events — no single small operator being wound up is worth
# reading about, which is exactly why the aggregate is the story — so judging
# theme membership at SIGNIFICANT_SCORE would filter out the very pattern it
# exists to find. At 40 the insolvency wave collapses to 3 signals; at 20 it
# is 22 signals across 21 companies, and every one of the Gazette's
# non-gambling false positives is still excluded, because Claude reliably
# scores those in single figures.
THEME_SIGNIFICANT_SCORE = 20


def assign_clusters(
    signals: list[dict],
    window_days: int = CLUSTER_WINDOW_DAYS,
    now: datetime | None = None,
    alias_map: dict[str, str] | None = None,
) -> None:
    """Recomputed fresh every run: sets cluster_id on signals that share a
    named entity with at least one other signal published within the rolling
    window, clears it on everything else. Entities are matched on their
    canonical form (see src.entities), so "Entain" and "Entain Holdings (UK)
    Limited" count as the same company."""
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=window_days)

    for s in signals:
        s["cluster_id"] = None

    eligible = [
        s
        for s in signals
        if s.get("newsworthiness_score") is not None
        and s.get("entities")
        and _parse_date(s["published_at"]) >= cutoff
    ]
    if not eligible:
        return

    parent = list(range(len(eligible)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    # A roundup naming a dozen operators is not evidence that those operators
    # are connected, but union-find treats it as exactly that and welds them
    # into one supercluster. Such signals still cluster on their own entities;
    # they just don't act as bridges.
    bridging = [
        idx
        for idx, s in enumerate(eligible)
        if len([e for e in signal_entities(s, alias_map) if not is_excluded(e)])
        <= MAX_BRIDGING_ENTITIES
    ]

    entity_to_indices: dict[str, list[int]] = defaultdict(list)
    for idx in bridging:
        for entity in signal_entities(eligible[idx], alias_map):
            if is_excluded(entity):
                continue
            entity_to_indices[_normalize_entity(entity)].append(idx)

    # An entity naming a large share of the window is behaving like an
    # institution the exclusion list hasn't caught yet — a trade body, a
    # regulator's spokesperson, a law firm acting on every case. Joining on it
    # groups "everything that mentions them" rather than a real pattern.
    hub_limit = max(MIN_HUB_SIGNALS, len(eligible) * HUB_ENTITY_SHARE)

    for entity, indices in entity_to_indices.items():
        if len(indices) >= hub_limit:
            continue
        for i in indices[1:]:
            union(indices[0], i)

    groups: dict[int, list[int]] = defaultdict(list)
    for idx in range(len(eligible)):
        groups[find(idx)].append(idx)

    for indices in groups.values():
        if len(indices) < 2:
            continue
        members = [eligible[i] for i in indices]
        cluster_id = hashlib.sha256(
            "|".join(sorted(m["id"] for m in members)).encode("utf-8")
        ).hexdigest()[:16]
        for m in members:
            m["cluster_id"] = cluster_id


def assign_themes(
    signals: list[dict],
    window_days: int = CLUSTER_WINDOW_DAYS,
    now: datetime | None = None,
    min_companies: int = MIN_THEME_COMPANIES,
    alias_map: dict[str, str] | None = None,
) -> None:
    """Group signals by what happened rather than who it happened to.

    Entity clustering can only ever surface patterns about a single company,
    so a sector-wide wave is invisible to it: 67 insolvency signals naming 57
    different companies register as 57 unrelated events. This is the other
    axis — signals sharing a canonical category across *different* companies.

    A theme needs `min_companies` distinct companies to qualify, which is what
    separates a wave from one company's run of filings. Membership is judged
    at THEME_SIGNIFICANT_SCORE rather than the higher bar used for company
    clusters — see that constant for why — which still excludes the Gazette's
    keyword false positives without discarding the wave itself.

    theme_id is the category itself: stable across runs, unlike cluster_id,
    so a theme keeps its identity as signals join and leave.
    """
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=window_days)

    for s in signals:
        s["theme_id"] = None

    by_theme: dict[str, list[dict]] = defaultdict(list)
    for s in signals:
        if (s.get("newsworthiness_score") or 0) < THEME_SIGNIFICANT_SCORE:
            continue
        if _parse_date(s["published_at"]) < cutoff:
            continue
        theme = category_of(s)
        if theme == OTHER:
            continue
        by_theme[theme].append(s)

    for theme, members in by_theme.items():
        companies = {
            _normalize_entity(e)
            for m in members
            for e in signal_entities(m, alias_map)
            if not is_excluded(e)
        }
        if len(companies) < min_companies:
            continue
        for m in members:
            m["theme_id"] = theme


def compute_theme_heat(
    members: list[dict],
    now: datetime | None = None,
    window_days: int = CLUSTER_WINDOW_DAYS,
    alias_map: dict[str, str] | None = None,
) -> float:
    """Heat for a theme. Breadth replaces source diversity: what makes a wave
    interesting is how many separate companies it touches, not how many feeds
    reported it."""
    now = now or datetime.now(timezone.utc)
    companies = {
        _normalize_entity(e)
        for m in members
        for e in signal_entities(m, alias_map)
        if not is_excluded(e)
    }
    best_score = max((m.get("newsworthiness_score") or 0) for m in members)
    most_recent = max(_parse_date(m["published_at"]) for m in members)
    days_since = max(0, (now - most_recent).days)

    return (
        len(members) * 5
        + len(companies) * 10
        + PEAK_SCORE_MAX * best_score / 100
        + RECENCY_MAX * max(0, window_days - days_since) / window_days
    )


def compute_heat(
    members: list[dict],
    now: datetime | None = None,
    window_days: int = CLUSTER_WINDOW_DAYS,
) -> float:
    """Rules-based heat: signal count, source diversity (weighted heaviest —
    a cluster spanning multiple sources is far more interesting than the same
    number of signals from one source), and recency of the latest signal.

    Volume and source spread count only signals that cleared
    SIGNIFICANT_SCORE. Counting every signal let routine corporate filings
    dominate — half of all RNS items are "Holding(s) in Company", "Total
    Voting Rights" and similar, scoring in the teens and twenties — so a month
    of boilerplate outranked a two-signal cluster containing a record fine.
    Scoring already judged that; heat now uses it.

    Recency decays linearly across the full clustering window rather than over
    a fixed 30 days: with a 90-day window a fixed ramp would bottom out a
    third of the way in, leaving two thirds of eligible clusters tied on the
    recency term. Its ceiling stays at RECENCY_MAX so widening the window
    changes how recency is *distributed*, not how much heat it can contribute.
    """
    now = now or datetime.now(timezone.utc)

    significant = [
        m
        for m in members
        if (m.get("newsworthiness_score") or 0) >= SIGNIFICANT_SCORE
    ]
    num_signals = len(significant)
    num_sources = len({m["source"] for m in significant})

    best_score = max((m.get("newsworthiness_score") or 0) for m in members)
    peak_score = PEAK_SCORE_MAX * best_score / 100

    # Recency stays keyed on the whole cluster: a burst of routine filings
    # still means the company is active, even if none of them is the story.
    most_recent = max(_parse_date(m["published_at"]) for m in members)
    days_since = max(0, (now - most_recent).days)
    recency_score = RECENCY_MAX * max(0, window_days - days_since) / window_days

    # Claude's read of the cluster, where it has one. Counts for less than the
    # evidence, but it's the only term that can tell a genuine two-signal
    # escalation from two filings that share a name.
    significance = next(
        (
            m["cluster_significance"]
            for m in members
            if m.get("cluster_significance") is not None
        ),
        None,
    )
    model_score = (
        MODEL_SIGNIFICANCE_MAX * significance / 100 if significance is not None else 0
    )

    return (
        num_signals * 10 + num_sources * 20 + peak_score + recency_score + model_score
    )
