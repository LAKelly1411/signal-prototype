"""One-off backfill: add canonical_entities and canonical_category to signals
scored before canonicalisation existed, and report what it does to clustering.

No re-scoring and no API calls — it only rewrites the entity and category
labels that scoring already produced, so it costs nothing to run.

    python -m scripts.backfill_canonical_entities --sector gambling --dry-run
    python -m scripts.backfill_canonical_entities --sector gambling
"""

import argparse
from collections import Counter, defaultdict

from src import cluster, store
from src.categories import canonical_category
from src.entities import build_alias_map, canonicalise
from src.sectors import load_sector


def summarise(signals: list[dict], alias_map: dict, use_canonical: bool, sector=None) -> dict:
    """Cluster a copy of the store and report the shape of the result."""
    working = [dict(s) for s in signals]
    if not use_canonical:
        for s in working:
            s.pop("canonical_entities", None)

    cluster.assign_clusters(
        working, alias_map=alias_map if use_canonical else None, sector=sector
    )

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
                if not cluster.is_excluded(e, sector)
            ).most_common(1)
            for m in sorted(grouped.values(), key=len, reverse=True)[:5]
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--sector", default="gambling")
    args = parser.parse_args()

    sector = load_sector(args.sector)
    signals = store.load(sector.signals_path)
    alias_map = build_alias_map(sector.companies)

    before = summarise(signals, alias_map, use_canonical=False, sector=sector)

    raw_categories = len({s.get("category") for s in signals if s.get("category")})

    changed = 0
    for signal in signals:
        resolved = canonicalise(signal.get("entities") or [], alias_map)
        theme = canonical_category(
            signal.get("category"), signal.get("title", ""), signal.get("signal_type"),
            sector=sector,
        )
        if (
            signal.get("canonical_entities") != resolved
            or signal.get("canonical_category") != theme
        ):
            signal["canonical_entities"] = resolved
            signal["canonical_category"] = theme
            changed += 1

    after = summarise(signals, alias_map, use_canonical=True, sector=sector)

    cluster.assign_themes(signals, alias_map=alias_map, sector=sector)
    themes = defaultdict(list)
    for s in signals:
        if s.get("theme_id"):
            themes[s["theme_id"]].append(s)

    print(f"\nCATEGORIES\n  {raw_categories} free-text labels -> "
          f"{len({s.get('canonical_category') for s in signals})} themes")
    print(f"\nCROSS-COMPANY THEMES ({len(themes)})")
    for theme, members in sorted(
        themes.items(), key=lambda kv: -cluster.compute_theme_heat(kv[1], sector=sector)
    ):
        companies = {
            e
            for m in members
            for e in (m.get("canonical_entities") or [])
            if not cluster.is_excluded(e, sector)
        }
        print(f"  {cluster.compute_theme_heat(members, sector=sector):6.1f}  {len(members):3d} signals, "
              f"{len(companies):3d} companies  {theme}")

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
    # With retention off save() never touches the archive, so nothing is
    # written outside this sector's signals file.
    store.save(signals, path=sector.signals_path, retention_days=None)
    print(f"Written to {sector.signals_path}.")


if __name__ == "__main__":
    main()
