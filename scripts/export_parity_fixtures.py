"""Write the Next.js port's parity fixtures from the Python dashboard logic.

Python is the reference: web/test/*.parity.test.ts checks the TypeScript port
against these files. Re-run after changing any ported logic:

    .venv/bin/python scripts/export_parity_fixtures.py
"""
import json
import shutil
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dashboard import app, overview  # noqa: E402
from src import sectors  # noqa: E402
from src.cluster import compute_heat, compute_theme_heat, is_excluded, signal_entities  # noqa: E402

OUT = ROOT / "web" / "test" / "fixtures" / "parity"
# The inputs are snapshotted here so the parity tests don't depend on the live
# data/, which the pipeline rewrites several times a day.
SNAP_DATA = OUT / "data"
SNAP_CONFIG = OUT / "config" / "sectors"


def _snapshot(slugs):
    """Copy the inputs (no archive) from data/ and config/ into the fixtures dir."""
    shutil.rmtree(SNAP_DATA, ignore_errors=True)
    shutil.rmtree(SNAP_CONFIG, ignore_errors=True)
    SNAP_DATA.mkdir(parents=True)
    SNAP_CONFIG.mkdir(parents=True)
    shutil.copy2(ROOT / "data" / "sectors.json", SNAP_DATA / "sectors.json")
    for slug in slugs:
        (SNAP_DATA / slug).mkdir()
        for name in ("signals.json", "run_status.json"):
            shutil.copy2(ROOT / "data" / slug / name, SNAP_DATA / slug / name)
        for name in (f"{slug}.yaml", f"{slug}.user.yaml"):
            src = ROOT / "config" / "sectors" / name
            if src.exists():
                shutil.copy2(src, SNAP_CONFIG / name)


def _groups_patterns(scored, sector, now):
    grouped = app.group_by_cluster(scored)
    coherent = [m for m in grouped.values() if app._cluster_verdict(m)["coherent"]]
    clusters = sorted(((compute_heat(m, now=now), m) for m in coherent), key=lambda p: p[0], reverse=True)
    out = []
    for heat, members in clusters:
        verdict = app._cluster_verdict(members)
        counts = Counter(e for m in members for e in signal_entities(m))
        companies = [n for n, _ in counts.most_common() if not is_excluded(n, sector)]
        sources = {m["source"] for m in members}
        out.append({
            "id": members[0]["cluster_id"],
            "title": companies[0] if companies else "Unnamed pattern",
            "heat": heat,
            "tier": app.heat_tier(heat)[0],
            "active": app.heat_tier(heat)[0] != "Low" and verdict["pattern_type"] != "routine",
            "summary": verdict["summary"],
            "pattern_type": verdict["pattern_type"],
            "meta": f"{len(members)} signals · {len(sources)} {'source' if len(sources) == 1 else 'sources'} · {app._date_span(members)}",
            "companies": companies[1:],
            "member_ids": [m["id"] for m in members],
            "weekly_counts": app._weekly_counts(members, now),
        })
    return out


def _groups_themes(signals, sector, now):
    grouped = defaultdict(list)
    for s in signals:
        if s.get("theme_id"):
            grouped[s["theme_id"]].append(s)
    themes = sorted(((compute_theme_heat(m, now=now, sector=sector), t, m) for t, m in grouped.items()),
                    reverse=True, key=lambda t: t[0])
    out = []
    for heat, theme, members in themes:
        counts = Counter(e for m in members for e in signal_entities(m) if not is_excluded(e, sector))
        companies = [n for n, _ in counts.most_common()]
        first = lambda f, d=None: next((m.get(f) for m in members if m.get(f)), d)  # noqa: E731
        out.append({
            "id": theme,
            "heat": heat,
            "tier": app.theme_heat_tier(heat)[0],
            "summary": first("theme_summary"),
            "direction": first("theme_direction"),
            "key_points": first("theme_key_points", []),
            "meta": f"{len(members)} signals · {len(companies)} {'company' if len(companies) == 1 else 'companies'} · {app._date_span(members)}",
            "companies": companies,
            "member_ids": [m["id"] for m in members],
            "weekly_counts": app._weekly_counts(members, now),
        })
    return out


def _filters(scored):
    opts = app._filter_options(scored)
    dates = opts["dates"]
    base = {"sources_off": [], "categories_off": [], "companies": [], "min_score": app.DEFAULT_MIN_SCORE,
            "days": None, "search": ""}
    cases = {
        "default": base,
        "min_score_0": {**base, "min_score": 0},
        "first_source_off": {**base, "min_score": 0, "sources_off": opts["sources"][:1]},
        "first_category_off": {**base, "min_score": 0, "categories_off": opts["categories"][:1]},
        "top_company": {**base, "min_score": 0, "companies": opts["entities"][:1]},
        "search_commission": {**base, "min_score": 0, "search": "commission"},
    }
    out = []
    for name, crit in cases.items():
        live = {**crit, "sources_off": set(crit["sources_off"]), "categories_off": set(crit["categories_off"])}
        out.append({"name": name, "criteria": crit, "ids": [s["id"] for s in app._filter_signals(scored, dates, live)]})
    return {"options": {"sources": opts["sources"], "categories": opts["categories"], "entities": opts["entities"]},
            "cases": out}


def _insights(scored, sector, status, now, patterns):
    """Mirrors render_insights + overview.weekly_volume_html / category_heatmap_html.
    Everything is built from `scored` (as render_insights does) on the fixed clock."""
    # Themes, as render_insights builds them (from scored signals), in its order.
    by_theme = defaultdict(list)
    for s in scored:
        if s.get("theme_id"):
            by_theme[s["theme_id"]].append(s)
    themes = []
    for name, members in by_theme.items():
        direction, recent, prior = overview.theme_trend(members, now)
        themes.append({"name": name, "heat": compute_theme_heat(members, now=now, sector=sector),
                       "direction": direction, "recent": recent, "prior": prior})
    themes.sort(key=lambda t: -t["heat"])
    healthy = total = None
    if status and "error" not in status:
        healthy, total = status.get("healthy_sources"), status.get("total_sources")
    # Not app._active_pattern_count: it reads the real clock. The patterns list
    # was built with the fixture's clock and carries `active`.
    active = sum(1 for p in patterns if p["active"])
    tiles = overview.headline_tiles(
        scored, now, active, sum(1 for t in themes if t["direction"] == "building"), healthy, total)

    # weekly_volume_html's counting: counts, and the top story per week (strict >).
    starts = overview.week_starts(now)
    counts = [0] * overview.WEEKS
    top = {}
    for s in scored:
        i = overview.week_index(s, starts)
        if i is None:
            continue
        counts[i] += 1
        if (s.get("newsworthiness_score") or 0) > (top.get(i, {}).get("newsworthiness_score") or -1):
            top[i] = s
    marks = [i for i in sorted(top) if (top[i].get("newsworthiness_score") or 0) >= overview.MARK_SCORE]

    # category_heatmap_html's grid, sort and thresholds.
    grid = defaultdict(lambda: [0] * overview.WEEKS)
    for s in scored:
        i = overview.week_index(s, starts)
        if i is None:
            continue
        grid[s.get("canonical_category") or "Other"][i] += 1
    heat_rows = sorted(grid.items(), key=lambda kv: (-sum(kv[1]), kv[0]))
    thresholds = overview.heat_thresholds([c for _, cs in heat_rows for c in cs])

    movers = overview.company_movers(scored, now, signal_entities, lambda e: is_excluded(e, sector))
    return {
        "tiles": [{"label": t.label, "value": t.value, "note": t.note} for t in tiles],
        "volume": {"counts": counts, "marks": marks, "top": overview.nice_top(max(counts) or 1)},
        "heatmap": {"rows": [{"category": c, "counts": cs, "total": sum(cs)} for c, cs in heat_rows],
                    "thresholds": list(thresholds)},
        "movers": movers,
        "themes": themes,
    }


def export(slug: str) -> None:
    signals = json.loads((SNAP_DATA / slug / "signals.json").read_text())
    status = json.loads((SNAP_DATA / slug / "run_status.json").read_text())
    sector = sectors.load_sector(slug, SNAP_CONFIG)
    now = datetime.fromisoformat(status["finished_at"])
    scored = [s for s in signals if s.get("newsworthiness_score") is not None]
    scored.sort(key=lambda s: s["published_at"], reverse=True)
    patterns = _groups_patterns(scored, sector, now)
    themes = _groups_themes(signals, sector, now)
    values = [0, 1, 39, 40, 59, 60, 69, 70, 89, 90, 129, 130, 199, 200, 500]
    entity_names = sorted({e for s in scored for e in signal_entities(s)})
    fixture = {
        "slug": slug,
        "now": status["finished_at"],
        "tiers": [{"value": v, "score_tier": app.score_tier(v)[0], "heat_tier": app.heat_tier(v)[0],
                   "theme_heat_tier": app.theme_heat_tier(v)[0]} for v in values],
        "nice_scale": [{"peak": p, "scale": app._nice_scale(p)} for p in [0, 1, 2, 3, 5, 9, 13, 21, 45, 99, 150]],
        "relative_time": [{"published_at": s["published_at"], "text": app._relative_time(s["published_at"], now)}
                          for s in scored[:25]],
        "full_date": [{"published_at": s["published_at"], "text": app._full_date(s["published_at"])} for s in scored[:25]],
        "date_bucket": [{"days_ago": d, "bucket": app._date_bucket(now.date() - timedelta(days=d), now.date())}
                        for d in [0, 1, 2, 7, 8, 30]],
        "patterns": patterns,
        "pattern_scale": app._nice_scale(max((max(p["weekly_counts"]) for p in patterns), default=0)),
        "themes": themes,
        "theme_scale": app._nice_scale(max((max(t["weekly_counts"]) for t in themes), default=0)),
        "filters": _filters(scored),
        "insights": _insights(scored, sector, status, now, patterns),
        "entities": [{"name": n, "is_person": app._is_person(n), "excluded": is_excluded(n, sector)}
                     for n in entity_names],
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{slug}.json").write_text(json.dumps(fixture, indent=1, ensure_ascii=False, default=str) + "\n")
    print(f"wrote {OUT / (slug + '.json')}: {len(patterns)} patterns, {len(themes)} themes")


if __name__ == "__main__":
    slugs = sys.argv[1:] or ["gambling", "fintech"]
    _snapshot(slugs)
    for slug in slugs:
        export(slug)
