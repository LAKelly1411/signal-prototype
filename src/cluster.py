import hashlib
from collections import defaultdict
from datetime import datetime, timedelta, timezone

# Regulators/institutions that get extracted as "entities" simply because
# they're the authority being discussed, not the subject of the signal.
# Clustering on these would just group "everything that mentions the
# regulator" rather than surfacing company-specific patterns.
EXCLUDED_ENTITIES = {
    "gambling commission",
    "dcms",
    "department for culture, media and sport",
    "hmrc",
    "hm revenue & customs",
    "hm revenue and customs",
    "companies house",
    "the gazette",
}


def _normalize_entity(name: str) -> str:
    return name.strip().lower()


def _parse_date(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def assign_clusters(
    signals: list[dict], window_days: int = 30, now: datetime | None = None
) -> None:
    """Recomputed fresh every run: sets cluster_id on signals that share a
    named entity with at least one other signal published within the rolling
    window, clears it on everything else. Entity matching is exact (case-
    insensitive) by design for v1 — legible and no false positives, at the
    cost of missing near-duplicate names Claude didn't normalise itself."""
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
        for entity in s["entities"]:
            normalized = _normalize_entity(entity)
            if normalized in EXCLUDED_ENTITIES:
                continue
            entity_to_indices[normalized].append(idx)

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


def compute_heat(members: list[dict], now: datetime | None = None) -> float:
    """Rules-based heat: signal count, source diversity (weighted heaviest —
    a cluster spanning multiple sources is far more interesting than the same
    number of signals from one source), and recency of the latest signal."""
    now = now or datetime.now(timezone.utc)
    num_signals = len(members)
    num_sources = len({m["source"] for m in members})
    most_recent = max(_parse_date(m["published_at"]) for m in members)
    days_since = max(0, (now - most_recent).days)
    recency_score = max(0, 30 - days_since)
    return num_signals * 10 + num_sources * 20 + recency_score
