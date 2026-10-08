"""Records what today's (pre-sector) code does for gambling, so the sector
refactor can prove it changed nothing. Run once, before the refactor:

    .venv/bin/python -m tests.fixtures.make_gambling_baseline
"""

import copy
import json
import os
from datetime import timedelta
from pathlib import Path

from src import categories, cluster, score, store
from src.entities import build_alias_map
from src.pipeline import build_collectors, load_sources, load_watchlist

OUT = Path("tests/fixtures/gambling_baseline.json")

# Labels and titles that exercise every rule and the fallbacks, on top of
# whatever the live store holds.
EXTRA_CATEGORY_INPUTS = [
    ["AML/licence enforcement", "", None],
    ["illegal gambling enforcement", "", None],
    ["ASA ruling - irresponsible advertising", "", None],
    ["safer gambling", "", None],
    ["personal licence revocation", "", None],
    ["", "Publication of the Scheme Document", None],
    [None, "Untitled", "regulatory"],
    [None, "Untitled", "insolvency"],
    ["", "", None],
    ["nonsense label", "some title", None],
]


def collector_snapshot(collector) -> dict:
    attrs = {k: v for k, v in vars(collector).items() if k != "api_key"}
    return {
        "class": type(collector).__name__,
        "attrs": json.loads(json.dumps(attrs, default=str, sort_keys=True)),
    }


def main() -> None:
    os.environ.setdefault("COMPANIES_HOUSE_API_KEY", "baseline-test-key")
    signals = [s for s in store.load() if s.get("newsworthiness_score") is not None]
    operators = load_watchlist()
    alias_map = build_alias_map(operators)

    category_inputs = [
        [s.get("category"), s.get("title", ""), s.get("signal_type")] for s in signals
    ] + EXTRA_CATEGORY_INPUTS
    entities = sorted(
        {e for s in signals for e in (s.get("entities") or []) + (s.get("canonical_entities") or [])}
        | set(cluster.EXCLUDED_ENTITIES)
        | {"Entain", "bet365 Group Limited", "Rank Group", "HM Treasury", "The Gazette"}
    )
    now = max(cluster._parse_date(s["published_at"]) for s in signals) + timedelta(days=1)

    working = copy.deepcopy(signals)
    cluster.assign_clusters(working, now=now, alias_map=alias_map)
    cluster.assign_themes(working, now=now, alias_map=alias_map)
    by_theme: dict[str, list[dict]] = {}
    for s in working:
        if s.get("theme_id"):
            by_theme.setdefault(s["theme_id"], []).append(s)

    baseline = {
        "prompts": {
            "system": score.SYSTEM_PROMPT,
            "cluster": score.CLUSTER_SYSTEM_PROMPT,
            "theme": score.THEME_SYSTEM_PROMPT,
        },
        "versions": {
            "cluster": score.CLUSTER_SUMMARY_VERSION,
            "theme": score.THEME_SUMMARY_VERSION,
        },
        "taxonomy": categories.TAXONOMY,
        "category_inputs": category_inputs,
        "categories": [categories.canonical_category(*i) for i in category_inputs],
        "entities": entities,
        "excluded": [cluster.is_excluded(e) for e in entities],
        "now": now.isoformat(),
        "signals": signals,
        "alias_operators": operators,
        "cluster_ids": {s["id"]: s.get("cluster_id") for s in working},
        "theme_ids": {s["id"]: s.get("theme_id") for s in working},
        "theme_heat": {
            t: cluster.compute_theme_heat(m, now=now, alias_map=alias_map)
            for t, m in by_theme.items()
        },
        "collectors": [collector_snapshot(c) for c in build_collectors(load_sources())],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(baseline, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {OUT}: {len(signals)} signals, {len(category_inputs)} category inputs, "
          f"{len(entities)} entities, {len(baseline['collectors'])} collectors")


if __name__ == "__main__":
    main()
