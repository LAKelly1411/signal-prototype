import hashlib
from collections import defaultdict
from datetime import datetime, timedelta, timezone

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

    entity_to_indices: dict[str, list[int]] = defaultdict(list)
    for idx, s in enumerate(eligible):
        for entity in signal_entities(s, alias_map):
            if is_excluded(entity):
                continue
            entity_to_indices[_normalize_entity(entity)].append(idx)

    for indices in entity_to_indices.values():
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


def compute_heat(
    members: list[dict],
    now: datetime | None = None,
    window_days: int = CLUSTER_WINDOW_DAYS,
) -> float:
    """Rules-based heat: signal count, source diversity (weighted heaviest —
    a cluster spanning multiple sources is far more interesting than the same
    number of signals from one source), and recency of the latest signal.

    Recency decays linearly across the full clustering window rather than over
    a fixed 30 days: with a 90-day window a fixed ramp would bottom out a
    third of the way in, leaving two thirds of eligible clusters tied on the
    recency term. Its ceiling stays at RECENCY_MAX so widening the window
    changes how recency is *distributed*, not how much heat it can contribute
    — which keeps existing heat values and the dashboard's tiers valid."""
    now = now or datetime.now(timezone.utc)
    num_signals = len(members)
    num_sources = len({m["source"] for m in members})
    most_recent = max(_parse_date(m["published_at"]) for m in members)
    days_since = max(0, (now - most_recent).days)
    recency_score = RECENCY_MAX * max(0, window_days - days_since) / window_days
    return num_signals * 10 + num_sources * 20 + recency_score
