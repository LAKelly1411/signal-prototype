"""One-off backfill: add canonical_entities to signals scored before
canonicalisation existed, and report what it does to clustering.

No re-scoring and no API calls — it only rewrites the entity lists that
scoring already extracted, so it costs nothing to run.

    python -m scripts.backfill_canonical_entities --dry-run
    python -m scripts.backfill_canonical_entities
"""

import argparse
from collections import Counter, defaultdict

from src import cluster, store
from src.entities import build_alias_map, canonicalise
from src.pipeline import load_watchlist


def summarise(signals: list[dict], alias_map: dict, use_canonical: bool) -> dict:
    """Cluster a copy of the store and report the shape of the result."""
    working = [dict(s) for s in signals]
    if not use_canonical:
        for s in working:
            s.pop("canonical_entities", None)

    cluster.assign_clusters(working, alias_map=alias_map if use_canonical else None)

    grouped = defaultdict(list)
    for s in working:
        if s.get("cluster_id"):
            grouped[s["cluster_id"]].append(s)

    key = "canonical_entities" if use_canonical else "entities"
    return {
        "distinct_entities": len({e for s in working for e in (s.get(key) or [])}),
        "clustered_signals": sum(len(m) for m in grouped.values()),
        "clusters": len(grouped),
        "multi_source_clusters": sum(
            1 for m in grouped.values() if len({x["source"] for x in m}) > 1
        ),
        "top_labels": [
            Counter(
                e
                for x in m
                for e in (x.get(key) or [])
                if not cluster.is_excluded(e)
            ).most_common(1)
            for m in sorted(grouped.values(), key=len, reverse=True)[:5]
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    signals = store.load()
    alias_map = build_alias_map(load_watchlist())

    before = summarise(signals, alias_map, use_canonical=False)

    changed = 0
    for signal in signals:
        resolved = canonicalise(signal.get("entities") or [], alias_map)
        if signal.get("canonical_entities") != resolved:
            signal["canonical_entities"] = resolved
            changed += 1

    after = summarise(signals, alias_map, use_canonical=True)

    for name, stats in (("BEFORE", before), ("AFTER", after)):
        print(f"\n{name}")
        for k in (
            "distinct_entities",
            "clustered_signals",
            "clusters",
            "multi_source_clusters",
        ):
            print(f"  {k:24} {stats[k]}")
        print(f"  top clusters: {[c[0][0] if c else '-' for c in stats['top_labels']]}")

    print(f"\n{changed} signals updated.")
    if args.dry_run:
        print("Dry run — nothing written.")
        return

    # Retention off: this backfill must not silently archive a decade of
    # history as a side effect. The next pipeline run applies retention.
    store.save(signals, retention_days=None)
    print("Written to data/signals.json.")


if __name__ == "__main__":
    main()
