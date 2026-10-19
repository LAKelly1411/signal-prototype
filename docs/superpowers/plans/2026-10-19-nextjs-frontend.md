# Next.js frontend implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Next.js app in `web/` that replaces the Streamlit dashboard's read-only views (Feed, Patterns, Themes, Insights, sign-in). It reads the pipeline's existing JSON files and matches Streamlit's numbers.

**Architecture:**
- Next.js 16 App Router with server components. Pages read only through a `DataSource` interface; v1's `FileDataSource` reads `../data` and `../config` from disk, or the same files over HTTP.
- The display logic from `dashboard/app.py`, `dashboard/overview.py` and `src/cluster.py` is ported to TypeScript in `lib/signals/`. It's pinned by fixtures generated from the Python code, which stays the reference.
- Sign-in is Auth.js with Microsoft Entra, plus a dev-only password provider.

**Tech stack:**
- Next.js 16.2, React 19.2, TypeScript 5, pnpm 10.32.0, Node 20.
- `next-auth` 5.0.0-beta.32 for sign-in, `zod` 3 for parsing, `js-yaml` 4 for config.
- Vitest 4 with Testing Library and jsdom for tests.
- Python 3.11 for the parity fixture script.

**Spec:** `docs/superpowers/specs/2026-10-19-nextjs-frontend-design.md`

## Global constraints

- **Location:** everything new lives in `web/`, except `scripts/export_parity_fixtures.py`, `.gitignore` entries and a short section in the root `README.md`. Nothing in `src/`, `dashboard/`, `config/`, `data/` or `tests/` changes.
- **Versions:**
  - `next` 16.2.4, `react` and `react-dom` 19.2.4, `next-auth` 5.0.0-beta.32;
  - `vitest` ^4.1.5, `typescript` ^5;
  - `.nvmrc` = `20`, `packageManager` = `pnpm@10.32.0`.
- **Build:** `next.config.ts` sets `output: 'standalone'`.
- **Python is the reference.** If TypeScript and Python disagree, the TypeScript is wrong.
- **Styling:**
  - no CSS framework, no chart library;
  - styles come from `web/styles/pa-brand.css` (copied verbatim from `docs/pa-design-kit/pa-brand.css`) plus CSS modules;
  - flat and square, cobalt `#004FFF` only on interactive elements.
- **Slugs** are validated against `^[a-z0-9-]+$` before any path or URL is built.
- **Data caching:** `revalidate: 300` (5 minutes).
- **Dev password provider:** exists only when `process.env.NODE_ENV === "development"` **and** `AUTH_DEV_PASSWORD` is set.
- **Score words:** `ACTIVITY_LABELS = { High: "Very active", Medium: "Active", Low: "Quiet" }`; `RELEVANCE_LABELS = { High: "Highly relevant", Medium: "Relevant", Low: "Low relevance" }`.
- **Copy:** sentence case, plain words, dates like `6 Oct` and `13 Jul – 6 Oct`, middle dot `·` separators.
- **Every commit message** ends with:
  ```
  Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_016YJv2T4yhVoixtyDTkv1fZ
  ```

## Review focus

1. **Sector listed but its files aren't there** (new sector setting up, or `signal_count: 0`). Expect the calm state "This sector is being set up" or "No signals yet", not an error page. Pinned in Task 10.
2. **Signals with missing optional fields:**
   - no `canonical_category` counts as "Other";
   - no `canonical_entities` falls back to `entities`;
   - `newsworthiness_score: null` is left out of every view, as in Python;
   - `published_at` with no time zone is treated as UTC.

   Pinned in Task 3 and Task 7.
3. **Unknown or hostile sector slug in the URL** (`/nope/feed`, `/..%2F/feed`). Expect a 404 with no file read or fetch attempted. Pinned in Task 3 and Task 10.
4. **Production build with Entra not configured.** Expect `/login` to show "Sign-in isn't set up yet", no password form, and every page to redirect to `/login`. Pinned in Task 9.
5. **Data URL unreachable on stage.** Expect pages to show "We couldn't load the latest signals. Try again in a few minutes." and `/api/ready` to return 503. Pinned in Task 3 and Task 10.

---

## File map

| File | Responsibility | Task |
|---|---|---|
| `web/package.json`, `tsconfig.json`, `next.config.ts`, `vitest.config.ts`, `vitest.setup.ts`, `.nvmrc`, `.gitignore` | project setup | 1 |
| `web/app/layout.tsx`, `web/app/api/health/route.ts`, `web/styles/pa-brand.css`, `web/public/pa-logo.svg` | shell, health, brand | 1 |
| `scripts/export_parity_fixtures.py`, `web/test/fixtures/parity/{gambling,fintech}.json` | Python oracle | 2 |
| `web/lib/data/{types,source,files,errors}.ts` | data access | 3 |
| `web/lib/signals/{tiers,time}.ts` | tiers, weeks, scales, dates | 4 |
| `web/lib/signals/{entities,heat}.ts`, `web/lib/brand.ts` | names, icons, heat formulas | 5 |
| `web/lib/signals/groups.ts` | patterns and themes | 6 |
| `web/lib/signals/filters.ts` | feed filters, sort, date buckets | 7 |
| `web/lib/signals/insights.ts` | Insights numbers | 8 |
| `web/auth.ts`, `web/middleware.ts`, `web/app/login/*`, `web/app/api/auth/[...nextauth]/route.ts`, `web/components/LoginArt.tsx` | sign-in | 9 |
| `web/app/page.tsx`, `web/app/[sector]/layout.tsx`, `web/components/{Masthead,SectorMenu,StatusStrip,Tabs,EmptyState}.tsx`, `web/app/api/ready/route.ts`, `web/lib/load.ts` | app shell | 10 |
| `web/components/{SignalCard,Tag,RelevanceRing,ActivityPill,SourceLogo}.tsx`, `web/app/api/logo/[domain]/route.ts` | shared pieces | 11 |
| `web/app/[sector]/feed/*`, `web/components/FeedFilters.tsx` | Feed | 12 |
| `web/app/[sector]/{patterns,themes}/*`, `web/components/{GroupCard,PreviewPane,SignalList,Sparkline}.tsx` | Patterns, Themes | 13 |
| `web/app/[sector]/insights/*`, `web/components/insights/*` | Insights | 14 |
| `web/Dockerfile`, `web/.dockerignore`, `web/README.md`, root `README.md` | deploy readiness, docs | 15 |

---

### Task 1: Scaffold `web/`

**Files:**
- Create: `web/package.json`, `web/tsconfig.json`, `web/next.config.ts`, `web/vitest.config.ts`, `web/vitest.setup.ts`, `web/.nvmrc`, `web/.gitignore`, `web/next-env.d.ts` (generated)
- Create: `web/app/layout.tsx`, `web/app/page.tsx` (temporary), `web/app/api/health/route.ts`
- Create: `web/styles/pa-brand.css` (verbatim copy of `docs/pa-design-kit/pa-brand.css`), `web/public/pa-logo.svg` (verbatim copy of `docs/pa-design-kit/pa-logo.svg`)
- Modify: `.gitignore` (root): add `web/node_modules/`, `web/.next/`, `web/coverage/`
- Test: `web/test/health.test.ts`

**Interfaces:**
- Produces: `GET /api/health` → `{ ok: true, tag: string }`, where `tag` is `process.env.BUILD_TAG ?? "dev"`. Also the `pnpm test` and `pnpm typecheck` scripts.

- [ ] **Step 1: Create `web/package.json`**

```json
{
  "name": "sector-signal-web",
  "private": true,
  "packageManager": "pnpm@10.32.0",
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "typecheck": "tsc --noEmit",
    "test": "vitest run",
    "test:watch": "vitest"
  },
  "dependencies": {
    "js-yaml": "^4.1.0",
    "next": "16.2.4",
    "next-auth": "5.0.0-beta.32",
    "react": "19.2.4",
    "react-dom": "19.2.4",
    "zod": "^3.25.0"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.6.0",
    "@testing-library/react": "^16.3.0",
    "@testing-library/user-event": "^14.6.0",
    "@types/js-yaml": "^4.0.9",
    "@types/node": "^20",
    "@types/react": "^19",
    "@types/react-dom": "^19",
    "@vitejs/plugin-react": "^5.0.0",
    "jsdom": "^26.0.0",
    "typescript": "^5",
    "vitest": "^4.1.5"
  }
}
```

- [ ] **Step 2: Create the config files**

`web/next.config.ts`:
```ts
import type { NextConfig } from "next";

const config: NextConfig = {
  output: "standalone",
};

export default config;
```

`web/tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["dom", "dom.iterable", "es2023"],
    "allowJs": false,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": { "@/*": ["./*"] }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

`web/vitest.config.ts`:
```ts
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": path.resolve(__dirname, ".") } },
  test: {
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    include: ["test/**/*.test.{ts,tsx}"],
  },
});
```

`web/vitest.setup.ts`:
```ts
import "@testing-library/jest-dom/vitest";
```

`web/.nvmrc`: `20`

`web/.gitignore`:
```
node_modules/
.next/
coverage/
next-env.d.ts
*.tsbuildinfo
.env*.local
```

- [ ] **Step 3: Write the failing health test** (`web/test/health.test.ts`)

```ts
import { describe, expect, it, vi, afterEach } from "vitest";
import { GET } from "@/app/api/health/route";

describe("/api/health", () => {
  afterEach(() => vi.unstubAllEnvs());

  it("reports ok and the build tag", async () => {
    vi.stubEnv("BUILD_TAG", "2026-10-19.abc1234");
    const res = await GET();
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ ok: true, tag: "2026-10-19.abc1234" });
  });

  it("says dev when no tag is set", async () => {
    vi.stubEnv("BUILD_TAG", "");
    expect((await (await GET()).json()).tag).toBe("dev");
  });
});
```

- [ ] **Step 4: Install and run the test to see it fail**

Run: `cd web && pnpm install && pnpm test`
Expected: FAIL, because `@/app/api/health/route` can't be resolved.

- [ ] **Step 5: Implement the health route, layout and temporary home page**

`web/app/api/health/route.ts`:
```ts
export const dynamic = "force-dynamic";

export async function GET() {
  return Response.json({ ok: true, tag: process.env.BUILD_TAG || "dev" });
}
```

`web/app/layout.tsx`:
```tsx
import type { Metadata } from "next";
import "@/styles/pa-brand.css";

export const metadata: Metadata = {
  title: "Sector Signal",
  description: "Sector signals, scored for newsworthiness.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
```

`web/app/page.tsx` (replaced in Task 10):
```tsx
export default function Home() {
  return <main style={{ padding: 32 }}>Sector Signal</main>;
}
```

Copy the brand files:
```bash
cp docs/pa-design-kit/pa-brand.css web/styles/pa-brand.css
cp docs/pa-design-kit/pa-logo.svg web/public/pa-logo.svg
```

Append to the root `.gitignore`:
```
web/node_modules/
web/.next/
web/coverage/
```

- [ ] **Step 6: Run the tests, the type check and the build**

Run: `cd web && pnpm test && pnpm typecheck && pnpm build`
Expected: 2 tests pass, no type errors, and the build prints `Route (app)` with `/api/health`.

- [ ] **Step 7: Commit**

```bash
git add .gitignore web/
git commit -m "web: scaffold the Next.js app with a health route"
```

---

### Task 2: Parity fixtures from Python

**Files:**
- Create: `scripts/export_parity_fixtures.py`
- Create (generated): `web/test/fixtures/parity/gambling.json`, `web/test/fixtures/parity/fintech.json`
- Create: `web/test/fixtures/parity/README.md`

**Interfaces:**
- Produces: one JSON fixture per sector, in exactly this shape (later tasks' tests read these keys):

```jsonc
{
  "slug": "gambling",
  "now": "2026-10-16T14:20:23.285341+00:00",      // run_status finished_at, the fixed clock for every number
  "tiers": [ { "value": 0, "score_tier": "Low", "heat_tier": "Low", "theme_heat_tier": "Low" }, … ],
  "nice_scale": [ { "peak": 0, "scale": 2 }, … ],
  "relative_time": [ { "published_at": "…", "text": "12 hours ago" }, … ],
  "full_date": [ { "published_at": "…", "text": "…" }, … ],
  "date_bucket": [ { "days_ago": 0, "bucket": "Today" }, … ],
  "patterns": [ {                                    // every coherent cluster, hottest first
      "id": "…", "title": "…", "heat": 123.4, "tier": "High", "active": true,
      "summary": "…" | null, "pattern_type": "escalation" | null,
      "meta": "4 signals · 2 sources · 13 Jul – 6 Oct",
      "companies": ["…"], "member_ids": ["…"],
      "weekly_counts": [0, 1, …]                     // 13 weeks, SPARK_WEEKS
  } ],
  "pattern_scale": 4,                               // _nice_scale over every group's peak week
  "themes": [ {
      "id": "Policy and legislation", "heat": 210.0, "tier": "High",
      "summary": "…" | null, "direction": "building" | null, "key_points": ["…"],
      "meta": "62 signals · 20 companies · 13 Jul – 6 Oct",
      "companies": ["…"], "member_ids": ["…"], "weekly_counts": [ … ]
  } ],
  "theme_scale": 12,
  "filters": [ { "name": "default", "criteria": { … }, "ids": ["…"] }, … ],
  "insights": {
      "tiles": [ { "label": "…", "value": "…", "note": "…" | null } ],
      "volume": { "counts": [ … 18 … ], "marks": [ … indexes … ], "top": 50 },
      "heatmap": { "rows": [ { "category": "…", "counts": [ … ], "total": 3 } ], "thresholds": [1,2,3,4,5] },
      "movers": [ { "name": "…", "top": 78, "count": 1, "change": 0, "weekly": [ … ] } ],
      "themes": [ { "name": "…", "direction": "building", "recent": 11, "prior": 5 } ]
  },
  "entities": [ { "name": "…", "is_person": false, "excluded": false } ]
}
```

- [ ] **Step 1: Write `scripts/export_parity_fixtures.py`**

It imports the real functions. Nothing is reimplemented except collecting the outputs.

```python
"""Write the Next.js port's parity fixtures from the Python dashboard logic.

Python is the reference: web/test/*.parity.test.ts checks the TypeScript port
against these files. Re-run after changing any ported logic:

    .venv/bin/python scripts/export_parity_fixtures.py
"""
import json
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


def _insights(signals, scored, sector, status, now, patterns):
    # Not app._active_pattern_count: it scores heat against the real clock
    # (compute_heat with no `now`), which would make the fixture drift. The
    # patterns list was built with the fixture's clock and carries `active`.
    active = sum(1 for p in patterns if p["active"])
    tiles = overview.headline_tiles(
        scored, now, active, 0,
        (status or {}).get("healthy_sources"), (status or {}).get("total_sources"))
    starts = overview.week_starts(now)
    counts = [0] * len(starts)
    marks = set()
    for s in scored:
        i = overview.week_index(s, starts)
        if i is not None:
            counts[i] += 1
            if (s.get("newsworthiness_score") or 0) >= overview.MARK_SCORE:
                marks.add(i)
    by_cat = defaultdict(lambda: [0] * len(starts))
    for s in scored:
        i = overview.week_index(s, starts)
        if i is not None:
            by_cat[s.get("canonical_category") or "Other"][i] += 1
    rows = sorted(({"category": c, "counts": v, "total": sum(v)} for c, v in by_cat.items()),
                  key=lambda r: (-r["total"], r["category"]))
    movers = overview.company_movers(scored, now, signal_entities, lambda e: is_excluded(e, sector))
    themes = defaultdict(list)
    for s in signals:
        if s.get("theme_id"):
            themes[s["theme_id"]].append(s)
    trends = []
    for name, members in themes.items():
        direction, recent, prior = overview.theme_trend(members, now)
        trends.append({"name": name, "direction": direction, "recent": recent, "prior": prior})
    return {
        "tiles": [{"label": t.label, "value": t.value, "note": t.note} for t in tiles],
        "volume": {"counts": counts, "marks": sorted(marks), "top": overview.nice_top(max(counts or [0]))},
        "heatmap": {"rows": rows, "thresholds": list(overview.heat_thresholds([c for r in rows for c in r["counts"]]))},
        "movers": [{k: m[k] for k in ("name", "top", "count", "change", "weekly") if k in m} for m in movers],
        "themes": sorted(trends, key=lambda t: t["name"]),
    }


def export(slug: str) -> None:
    signals = json.loads((ROOT / "data" / slug / "signals.json").read_text())
    status = json.loads((ROOT / "data" / slug / "run_status.json").read_text())
    sector = sectors.load_sector(slug)
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
        "insights": _insights(signals, scored, sector, status, now, patterns),
        "entities": [{"name": n, "is_person": app._is_person(n), "excluded": is_excluded(n, sector)}
                     for n in entity_names],
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{slug}.json").write_text(json.dumps(fixture, indent=1, ensure_ascii=False, default=str) + "\n")
    print(f"wrote {OUT / (slug + '.json')}: {len(patterns)} patterns, {len(themes)} themes")


if __name__ == "__main__":
    for slug in sys.argv[1:] or ["gambling", "fintech"]:
        export(slug)
```

- [ ] **Step 2: Bring `data/` up to date with `main` and run the script**

The fixtures must come from the same JSON the app reads in tests, so they're generated from the branch's committed `data/`. First check the branch has current data:
```bash
git fetch origin && git checkout origin/main -- data/ && git status --short data/
```
Expected: data files show as modified (newer runs). Commit them in step 4 so fixtures and data agree.

Run: `.venv/bin/python scripts/export_parity_fixtures.py`
Expected: two lines like `wrote …/gambling.json: N patterns, M themes`.

If a name in the script doesn't exist, check its line in `dashboard/app.py` before changing anything. Known lines:
- `_weekly_counts` 2737, `_nice_scale` 2732, `_date_span` 2717;
- `_cluster_verdict` 2672, `_filter_options` 2409, `_filter_signals` 2439;
- `_relative_time` 2163, `_full_date` 2200, `_date_bucket` 2586;
- `_is_person` 2229, `_active_pattern_count` 3920.

Also check `sectors.load_sector` in `src/sectors.py`. Then adjust the call only, never the logic. If `company_movers` returns keys other than those listed, keep the ones it has. The TypeScript tests read only `name`, `top`, `count` and `change`.

- [ ] **Step 3: Write `web/test/fixtures/parity/README.md`**

```markdown
Generated by `scripts/export_parity_fixtures.py` from the Python dashboard
logic and the committed `data/`. Don't edit by hand. Regenerate after
changing ported logic or refreshing `data/`:

    .venv/bin/python scripts/export_parity_fixtures.py
```

- [ ] **Step 4: Commit**

```bash
git add scripts/export_parity_fixtures.py web/test/fixtures/parity/ data/
git commit -m "Parity fixtures: Python dashboard logic as the oracle for the Next.js port"
```

---

### Task 3: Data access

**Files:**
- Create: `web/lib/data/types.ts`, `web/lib/data/errors.ts`, `web/lib/data/source.ts`, `web/lib/data/files.ts`
- Test: `web/test/data.test.ts`, `web/test/fixtures/data/` (tiny hand-made sector)

**Interfaces:**
- Produces:
  ```ts
  // types.ts: zod schemas and inferred types
  export const SignalSchema; export type Signal
  export const SectorEntrySchema; export type SectorEntry
  export const RunStatusSchema; export type RunStatus
  export type SectorRules = {
    slug: string; name: string;
    categories: string[];
    companies: { name: string; company_number?: string | null; aliases: string[] }[];
    excludedBodies: string[];   // from `excluded_bodies` (all lists flattened)
  }
  // errors.ts
  export class DataError extends Error { kind: "not_found" | "invalid" | "unreachable" }
  export const isSlug = (v: unknown): v is string
  // source.ts
  export interface DataSource {
    listSectors(): Promise<SectorEntry[]>;
    getSignals(slug: string): Promise<Signal[]>;
    getRunStatus(slug: string): Promise<RunStatus | null>;
    getSectorRules(slug: string): Promise<SectorRules>;
  }
  export function getDataSource(): DataSource   // FileDataSource from env, memoised
  // files.ts
  export class FileDataSource implements DataSource {
    constructor(opts: { dataDir?: string; configDir?: string; dataBaseUrl?: string; configBaseUrl?: string; fetchFn?: typeof fetch })
  }
  ```

- [ ] **Step 1: Write the test fixture sector**

`web/test/fixtures/data/sectors.json`:
```json
[
  { "slug": "demo", "name": "Demo & co", "status": "ready", "signal_count": 2, "last_run_at": "2026-10-16T14:20:23+00:00", "error": null, "brief": "A demo.", "created_at": null },
  { "slug": "newbie", "name": "New sector", "status": "setting_up", "signal_count": 0, "last_run_at": null, "error": null, "brief": "", "created_at": "2026-10-18T09:00:00+00:00" }
]
```

`web/test/fixtures/data/demo/signals.json`:
```json
[
  { "id": "a1", "source": "gazette", "source_id": null, "source_url": "https://www.thegazette.co.uk/notice/1", "title": "Winding-up petition", "raw_summary": "", "published_at": "2026-10-15T00:00:00+00:00", "ingested_at": "2026-10-15T08:00:00+00:00", "signal_type": "insolvency", "entities": ["Acme Ltd"], "newsworthiness_score": 45, "why_it_matters": "Signals distress.", "category": "insolvency", "cluster_id": "c1", "status": "seen", "canonical_entities": ["Acme"], "canonical_category": "Insolvency", "theme_id": null, "sector": "demo" },
  { "id": "a2", "source": "asa", "source_url": "https://www.asa.org.uk/r/2", "title": "Ruling", "raw_summary": "", "published_at": "2026-10-14T00:00:00", "ingested_at": "2026-10-14T08:00:00+00:00", "signal_type": "enforcement", "entities": ["Acme"], "newsworthiness_score": null, "why_it_matters": null, "category": null, "cluster_id": null, "status": "seen", "theme_id": null, "sector": "demo" }
]
```

`web/test/fixtures/data/demo/run_status.json`:
```json
{ "sector": "demo", "started_at": "2026-10-16T14:19:15+00:00", "finished_at": "2026-10-16T14:20:23+00:00", "sources": { "GazetteCollector": { "items": 3, "ok": true, "error": false }, "ASACollector": { "items": 0, "ok": false, "error": false } }, "healthy_sources": 1, "total_sources": 2, "raw_items": 3, "new_signals": 1, "unscored": 1, "live_signals": 2, "clusters": 1 }
```

`web/test/fixtures/config/sectors/demo.yaml`:
```yaml
slug: demo
name: Demo & co
categories: ["Insolvency", "Enforcement action"]
companies:
  - name: Acme
    company_number: "01234567"
    aliases: ["Acme Ltd"]
excluded_bodies:
  regulators: ["Gambling Commission"]
```

`web/test/fixtures/config/sectors/demo.user.yaml`:
```yaml
operators:
  - name: Beta Corp
    company_number: null
    aliases: []
    notes: ""
```

- [ ] **Step 2: Write the failing tests** (`web/test/data.test.ts`)

```ts
import { describe, expect, it, vi } from "vitest";
import path from "node:path";
import { FileDataSource } from "@/lib/data/files";
import { DataError, isSlug } from "@/lib/data/errors";

const dataDir = path.join(__dirname, "fixtures/data");
const configDir = path.join(__dirname, "fixtures/config");
const disk = () => new FileDataSource({ dataDir, configDir });

describe("isSlug", () => {
  it.each(["gambling", "fintech", "a-b-2"])("accepts %s", (s) => expect(isSlug(s)).toBe(true));
  it.each(["", "../etc", "Gambling", "a/b", "a%2Fb", "a b", null, 3])("rejects %s", (s) => expect(isSlug(s)).toBe(false));
});

describe("FileDataSource on disk", () => {
  it("lists sectors", async () => {
    const sectors = await disk().listSectors();
    expect(sectors.map((s) => s.slug)).toEqual(["demo", "newbie"]);
  });

  it("reads signals, keeping optional fields optional", async () => {
    const signals = await disk().getSignals("demo");
    expect(signals).toHaveLength(2);
    expect(signals[1].newsworthiness_score).toBeNull();
    expect(signals[1].canonical_category).toBeUndefined();
  });

  it("reads run status, and null when there is none", async () => {
    expect((await disk().getRunStatus("demo"))?.healthy_sources).toBe(1);
    expect(await disk().getRunStatus("newbie")).toBeNull();
  });

  it("reads sector rules and merges the dashboard watchlist", async () => {
    const rules = await disk().getSectorRules("demo");
    expect(rules.categories).toEqual(["Insolvency", "Enforcement action"]);
    expect(rules.companies.map((c) => c.name)).toEqual(["Acme", "Beta Corp"]);
    expect(rules.excludedBodies).toEqual(["Gambling Commission"]);
  });

  it("throws not_found for a sector with no signals file", async () => {
    await expect(disk().getSignals("newbie")).rejects.toMatchObject({ kind: "not_found" });
  });

  it("refuses a bad slug without touching the disk", async () => {
    await expect(disk().getSignals("../../etc")).rejects.toMatchObject({ kind: "not_found" });
  });

  it("throws invalid for malformed JSON shapes", async () => {
    const bad = new FileDataSource({ dataDir: path.join(__dirname, "fixtures/bad-data"), configDir });
    await expect(bad.listSectors()).rejects.toMatchObject({ kind: "invalid" });
  });
});

describe("FileDataSource over HTTP", () => {
  it("fetches from the base URLs", async () => {
    const fetchFn = vi.fn(async (url: string) =>
      new Response(url.endsWith("sectors.json") ? JSON.stringify([{ slug: "x", name: "X", status: "ready" }]) : "{}"),
    );
    const src = new FileDataSource({ dataBaseUrl: "https://example.test/data/", configBaseUrl: "https://example.test/config/", fetchFn: fetchFn as unknown as typeof fetch });
    expect((await src.listSectors())[0].slug).toBe("x");
    expect(fetchFn).toHaveBeenCalledWith("https://example.test/data/sectors.json", expect.anything());
  });

  it("maps 404 to not_found and network failure to unreachable", async () => {
    const notFound = new FileDataSource({ dataBaseUrl: "https://e.test/data/", configBaseUrl: "https://e.test/config/", fetchFn: (async () => new Response("", { status: 404 })) as unknown as typeof fetch });
    await expect(notFound.getSignals("demo")).rejects.toMatchObject({ kind: "not_found" });
    const down = new FileDataSource({ dataBaseUrl: "https://e.test/data/", configBaseUrl: "https://e.test/config/", fetchFn: (async () => { throw new TypeError("fetch failed"); }) as unknown as typeof fetch });
    await expect(down.listSectors()).rejects.toMatchObject({ kind: "unreachable" });
  });
});
```

Create `web/test/fixtures/bad-data/sectors.json` containing `{"not": "a list"}`.

- [ ] **Step 3: Run to see it fail**

Run: `cd web && pnpm test test/data.test.ts`
Expected: FAIL, because the modules aren't found.

- [ ] **Step 4: Implement**

`web/lib/data/errors.ts`:
```ts
export type DataErrorKind = "not_found" | "invalid" | "unreachable";

export class DataError extends Error {
  constructor(public kind: DataErrorKind, message: string) {
    super(message);
    this.name = "DataError";
  }
}

const SLUG = /^[a-z0-9-]+$/;
export const isSlug = (v: unknown): v is string => typeof v === "string" && SLUG.test(v);
```

`web/lib/data/types.ts`: schemas use `.passthrough()` so new pipeline fields never break parsing.
```ts
import { z } from "zod";

export const SignalSchema = z
  .object({
    id: z.string(),
    source: z.string(),
    source_url: z.string().nullable().optional(),
    title: z.string(),
    raw_summary: z.string().nullable().optional(),
    published_at: z.string(),
    published_at_estimated: z.boolean().optional(),
    ingested_at: z.string().optional(),
    signal_type: z.string().nullable().optional(),
    entities: z.array(z.string()).optional().default([]),
    newsworthiness_score: z.number().nullable().optional(),
    why_it_matters: z.string().nullable().optional(),
    category: z.string().nullable().optional(),
    canonical_entities: z.array(z.string()).optional(),
    canonical_category: z.string().nullable().optional(),
    cluster_id: z.string().nullable().optional(),
    cluster_summary: z.string().nullable().optional(),
    cluster_pattern_type: z.string().nullable().optional(),
    cluster_coherent: z.boolean().nullable().optional(),
    cluster_significance: z.number().nullable().optional(),
    theme_id: z.string().nullable().optional(),
    theme_summary: z.string().nullable().optional(),
    theme_key_points: z.array(z.string()).nullable().optional(),
    theme_direction: z.string().nullable().optional(),
    sector: z.string().optional(),
  })
  .passthrough();
export type Signal = z.infer<typeof SignalSchema>;

export const SectorEntrySchema = z
  .object({
    slug: z.string(),
    name: z.string(),
    status: z.string().optional().default("ready"),
    brief: z.string().nullable().optional(),
    signal_count: z.number().nullable().optional(),
    last_run_at: z.string().nullable().optional(),
    error: z.string().nullable().optional(),
    created_at: z.string().nullable().optional(),
  })
  .passthrough();
export type SectorEntry = z.infer<typeof SectorEntrySchema>;

export const RunStatusSchema = z
  .object({
    sector: z.string().optional(),
    started_at: z.string().optional(),
    finished_at: z.string(),
    sources: z.record(z.string(), z.object({ items: z.number(), ok: z.boolean(), error: z.boolean() }).passthrough()),
    healthy_sources: z.number(),
    total_sources: z.number(),
  })
  .passthrough();
export type RunStatus = z.infer<typeof RunStatusSchema>;

export type SectorRules = {
  slug: string;
  name: string;
  categories: string[];
  companies: { name: string; company_number?: string | null; aliases: string[] }[];
  excludedBodies: string[];
};
```

`web/lib/data/source.ts`:
```ts
import type { RunStatus, SectorEntry, SectorRules, Signal } from "./types";
import { FileDataSource } from "./files";

export interface DataSource {
  listSectors(): Promise<SectorEntry[]>;
  getSignals(slug: string): Promise<Signal[]>;
  getRunStatus(slug: string): Promise<RunStatus | null>;
  getSectorRules(slug: string): Promise<SectorRules>;
}

let memo: DataSource | null = null;

/** The app's one data source. v1: the pipeline's JSON files, from disk or a base URL. */
export function getDataSource(): DataSource {
  if (!memo) {
    memo = new FileDataSource({
      dataDir: process.env.DATA_DIR,
      configDir: process.env.CONFIG_DIR,
      dataBaseUrl: process.env.DATA_BASE_URL,
      configBaseUrl: process.env.CONFIG_BASE_URL,
    });
  }
  return memo;
}
```

`web/lib/data/files.ts`:
```ts
import { readFile } from "node:fs/promises";
import path from "node:path";
import yaml from "js-yaml";
import { z } from "zod";
import { DataError, isSlug } from "./errors";
import { RunStatusSchema, SectorEntrySchema, SignalSchema, type RunStatus, type SectorEntry, type SectorRules, type Signal } from "./types";

type Opts = { dataDir?: string; configDir?: string; dataBaseUrl?: string; configBaseUrl?: string; fetchFn?: typeof fetch };

const REVALIDATE = 300;

export class FileDataSource {
  private dataDir: string;
  private configDir: string;
  private dataBaseUrl?: string;
  private configBaseUrl?: string;
  private fetchFn: typeof fetch;

  constructor(opts: Opts = {}) {
    this.dataDir = opts.dataDir || path.resolve(process.cwd(), "../data");
    this.configDir = opts.configDir || path.resolve(process.cwd(), "../config");
    this.dataBaseUrl = opts.dataBaseUrl?.replace(/\/?$/, "/");
    this.configBaseUrl = opts.configBaseUrl?.replace(/\/?$/, "/");
    this.fetchFn = opts.fetchFn ?? fetch;
  }

  /** Raw text of a file under data/ or config/, or null when it doesn't exist. */
  private async read(root: "data" | "config", rel: string): Promise<string | null> {
    const base = root === "data" ? this.dataBaseUrl : this.configBaseUrl;
    if (base) {
      let res: Response;
      try {
        res = await this.fetchFn(base + rel, { next: { revalidate: REVALIDATE } } as RequestInit);
      } catch (e) {
        throw new DataError("unreachable", `Couldn't reach ${base + rel}: ${(e as Error).message}`);
      }
      if (res.status === 404) return null;
      if (!res.ok) throw new DataError("unreachable", `${base + rel} answered ${res.status}`);
      return res.text();
    }
    const dir = root === "data" ? this.dataDir : this.configDir;
    try {
      return await readFile(path.join(dir, rel), "utf8");
    } catch (e) {
      if ((e as NodeJS.ErrnoException).code === "ENOENT") return null;
      throw new DataError("unreachable", `Couldn't read ${rel}: ${(e as Error).message}`);
    }
  }

  private parse<T>(schema: z.ZodType<T>, text: string, what: string): T {
    let raw: unknown;
    try {
      raw = JSON.parse(text);
    } catch {
      throw new DataError("invalid", `${what} isn't valid JSON`);
    }
    const result = schema.safeParse(raw);
    if (!result.success) throw new DataError("invalid", `${what} doesn't match the expected shape: ${result.error.message}`);
    return result.data;
  }

  private slug(slug: string): string {
    if (!isSlug(slug)) throw new DataError("not_found", `Not a sector: ${JSON.stringify(slug)}`);
    return slug;
  }

  async listSectors(): Promise<SectorEntry[]> {
    const text = await this.read("data", "sectors.json");
    if (text === null) throw new DataError("not_found", "data/sectors.json is missing");
    return this.parse(z.array(SectorEntrySchema), text, "sectors.json");
  }

  async getSignals(slug: string): Promise<Signal[]> {
    const s = this.slug(slug);
    const text = await this.read("data", `${s}/signals.json`);
    if (text === null) throw new DataError("not_found", `No signals for ${s} yet`);
    return this.parse(z.array(SignalSchema), text, `${s}/signals.json`);
  }

  async getRunStatus(slug: string): Promise<RunStatus | null> {
    const s = this.slug(slug);
    const text = await this.read("data", `${s}/run_status.json`);
    return text === null ? null : this.parse(RunStatusSchema, text, `${s}/run_status.json`);
  }

  async getSectorRules(slug: string): Promise<SectorRules> {
    const s = this.slug(slug);
    const main = await this.read("config", `sectors/${s}.yaml`);
    if (main === null) throw new DataError("not_found", `No config for ${s}`);
    const user = await this.read("config", `sectors/${s}.user.yaml`);
    const cfg = (yaml.load(main) ?? {}) as Record<string, unknown>;
    const extra = user ? ((yaml.load(user) ?? {}) as Record<string, unknown>) : {};
    const companies = [
      ...((cfg.companies as SectorRules["companies"]) ?? []),
      ...(((extra.operators ?? extra.companies) as SectorRules["companies"]) ?? []),
    ].map((c) => ({ name: c.name, company_number: c.company_number ?? null, aliases: c.aliases ?? [] }));
    const excluded = cfg.excluded_bodies;
    const excludedBodies = Array.isArray(excluded)
      ? (excluded as string[])
      : Object.values((excluded as Record<string, string[]>) ?? {}).flat();
    return {
      slug: s,
      name: String(cfg.name ?? s),
      categories: (cfg.categories as string[]) ?? [],
      companies,
      excludedBodies,
    };
  }
}
```

Before relying on `excluded_bodies` and `categories`, open `config/sectors/gambling.yaml` and check their shapes. `categories` may be a list of objects with a `name`. If so, map to names: `(cfg.categories as ({name:string}|string)[]).map(c => typeof c === "string" ? c : c.name)`. Then check `src/sectors.py` (`excluded_entities`), and make `excludedBodies` hold exactly the names it uses.

- [ ] **Step 5: Run the tests**

Run: `cd web && pnpm test test/data.test.ts && pnpm typecheck`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add web/lib/data web/test/data.test.ts web/test/fixtures/data web/test/fixtures/config web/test/fixtures/bad-data
git commit -m "web: data access over the pipeline's JSON, from disk or a base URL"
```

---

### Task 4: Tiers, weeks, scales and dates

**Files:**
- Create: `web/lib/signals/tiers.ts`, `web/lib/signals/time.ts`
- Test: `web/test/tiers-time.parity.test.ts`

**Interfaces:**
- Consumes: `Signal` (Task 3), the parity fixtures (Task 2).
- Produces:
  ```ts
  // tiers.ts
  export type Tier = "High" | "Medium" | "Low";
  export const SCORE_TIERS, HEAT_TIERS, THEME_HEAT_TIERS: [number, Tier, string, string][];  // [min, tier, bg, fg]
  export function scoreTier(score: number): { tier: Tier; bg: string; fg: string };
  export function heatTier(heat: number): { tier: Tier; bg: string; fg: string };
  export function themeHeatTier(heat: number): { tier: Tier; bg: string; fg: string };
  export const ACTIVITY_LABELS: Record<Tier, string>;   // High "Very active", Medium "Active", Low "Quiet"
  export const ACTIVITY_RING: Record<Tier, number>;     // High 90, Medium 60, Low 30
  export const RELEVANCE_LABELS: Record<Tier, string>;
  // time.ts
  export const SPARK_WEEKS = 13;
  export function parseDate(iso: string): Date;          // no zone → UTC
  export function niceScale(peak: number): number;       // _NICE_SCALES
  export function weeklyCounts(members: Signal[], now: Date): number[];   // length SPARK_WEEKS
  export function weekIndex(signal: Signal, now: Date): number | null;
  export function weekRange(start: Date): string;
  export function relativeTime(publishedAt: string, now: Date): string;
  export function fullDate(publishedAt: string): string;
  export function dateBucket(pub: Date, today: Date): "Today" | "Yesterday" | "This week" | "Earlier";
  export function dateSpan(members: Signal[]): string;    // "13 Jul – 6 Oct" or "6 Oct"
  export function humaniseAge(deltaSeconds: number): string;
  ```

- [ ] **Step 1: Write the failing parity test** (`web/test/tiers-time.parity.test.ts`)

```ts
import { describe, expect, it } from "vitest";
import gambling from "./fixtures/parity/gambling.json";
import fintech from "./fixtures/parity/fintech.json";
import { heatTier, scoreTier, themeHeatTier } from "@/lib/signals/tiers";
import { dateBucket, fullDate, niceScale, parseDate, relativeTime } from "@/lib/signals/time";

describe.each([gambling, fintech])("$slug: tiers and time match Python", (fx) => {
  const now = parseDate(fx.now);

  it.each(fx.tiers)("tiers for $value", (t) => {
    expect(scoreTier(t.value).tier).toBe(t.score_tier);
    expect(heatTier(t.value).tier).toBe(t.heat_tier);
    expect(themeHeatTier(t.value).tier).toBe(t.theme_heat_tier);
  });

  it.each(fx.nice_scale)("nice scale for peak $peak", ({ peak, scale }) => expect(niceScale(peak)).toBe(scale));

  it("relative times", () => {
    for (const r of fx.relative_time) expect(relativeTime(r.published_at, now)).toBe(r.text);
  });

  it("full dates", () => {
    for (const r of fx.full_date) expect(fullDate(r.published_at)).toBe(r.text);
  });

  it("date buckets", () => {
    const today = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()));
    for (const b of fx.date_bucket) {
      const pub = new Date(today.getTime() - b.days_ago * 86_400_000);
      expect(dateBucket(pub, today)).toBe(b.bucket);
    }
  });
});

describe("parseDate", () => {
  it("treats a date with no zone as UTC", () => {
    expect(parseDate("2026-10-14T00:00:00").toISOString()).toBe("2026-10-14T00:00:00.000Z");
  });
});
```

Weekly counts, date spans and scales are checked against groups in Task 6.

- [ ] **Step 2: Run to see it fail**

Run: `cd web && pnpm test test/tiers-time.parity.test.ts`
Expected: FAIL, because the modules aren't found.

- [ ] **Step 3: Port the code**

Translate line by line, keeping names in camelCase:
- `tiers.ts` from `dashboard/app.py` lines 41–91 (`SCORE_TIERS`, `HEAT_TIERS`, `THEME_HEAT_TIERS`, `_tier`, `score_tier`, `heat_tier`, `theme_heat_tier`). Add `ACTIVITY_LABELS` and `_ACTIVITY_RING` (lines 2698–2699) and `RELEVANCE_LABELS` (line 2157).
- `time.ts` from `dashboard/app.py`:
  - `_relative_time` 2163–2183, `_full_date` 2200–2211, `_date_bucket` 2586–2595;
  - `_date_span` 2717–2723, `SPARK_WEEKS`, `_NICE_SCALES` and `_nice_scale` 2725–2736;
  - `_weekly_counts` 2737–2749, `_week_index` 2750–2759, `_week_range` 2821–2830, `_humanise_age` 3321–3331.

`_tier` as a guide:
```ts
function tierOf(value: number, tiers: [number, Tier, string, string][]) {
  for (const [min, tier, bg, fg] of tiers) if (value >= min) return { tier, bg, fg };
  const last = tiers[tiers.length - 1];
  return { tier: last[1], bg: last[2], fg: last[3] };
}
```

Date rules:
- `parseDate(iso)`: if the string has no `Z` and no `±hh:mm` offset, append `Z`. Then `new Date(iso)`.
- Python's `fromisoformat` accepts microseconds (`.285341`), which JavaScript ignores past milliseconds. That's fine for every comparison here.
- Any calendar formatting that Python does in `Europe/London` (check `_full_date`; it imports `ZoneInfo`) uses `Intl.DateTimeFormat("en-GB", { timeZone: "Europe/London", … })` and must produce the identical string.

- [ ] **Step 4: Run the tests**

Run: `cd web && pnpm test test/tiers-time.parity.test.ts && pnpm typecheck`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add web/lib/signals/tiers.ts web/lib/signals/time.ts web/test/tiers-time.parity.test.ts
git commit -m "web: port tiers, weeks, scales and dates, pinned to Python"
```

---

### Task 5: Entities, brand data and heat formulas

**Files:**
- Create: `web/lib/brand.ts`, `web/lib/signals/entities.ts`, `web/lib/signals/heat.ts`
- Test: `web/test/entities-heat.parity.test.ts`

**Interfaces:**
- Consumes: `Signal`, `SectorRules` (Task 3); `parseDate` (Task 4).
- Produces:
  ```ts
  // brand.ts: data copied from dashboard/brand.py
  export const SOURCE_NAMES: Record<string, [string, string]>;   // key → [display name, short]
  export const SOURCE_DOMAINS: Record<string, string>;
  export const COMPANY_DOMAINS: Record<string, string>;
  export const PEOPLE: Set<string>;
  export const ICON_PATHS: Record<string, { d: string; viewBox: string }>;   // _MS + GAVEL_20, CORPORATE_FARE_20, LINK_16
  export function categoryIconName(category: string | null | undefined): string;
  // entities.ts
  export function matchKey(name: string): string;             // src/entities.py match_key + strip_legal_suffixes + _tokens
  export function signalEntities(signal: Signal): string[];   // canonical_entities, else entities
  export function isExcluded(name: string, rules: SectorRules | null): boolean;
  export function isPerson(name: string): boolean;
  export function sourceName(source: string): string;
  export function initials(name: string): string;
  // heat.ts
  export const CLUSTER_WINDOW_DAYS = 90, RECENCY_MAX = 30, SIGNIFICANT_SCORE = 40, MIN_THEME_COMPANIES = 3;
  export function computeHeat(members: Signal[], now: Date): number;
  export function computeThemeHeat(members: Signal[], now: Date, rules: SectorRules | null): number;
  ```

- [ ] **Step 1: Write the failing parity test** (`web/test/entities-heat.parity.test.ts`)

```ts
import { describe, expect, it } from "vitest";
import path from "node:path";
import gambling from "./fixtures/parity/gambling.json";
import fintech from "./fixtures/parity/fintech.json";
import { FileDataSource } from "@/lib/data/files";
import { isExcluded, isPerson, signalEntities } from "@/lib/signals/entities";
import { computeHeat, computeThemeHeat } from "@/lib/signals/heat";
import { parseDate } from "@/lib/signals/time";

const repo = path.resolve(__dirname, "../..");
const src = new FileDataSource({ dataDir: path.join(repo, "data"), configDir: path.join(repo, "config") });

describe.each([gambling, fintech])("$slug: entities and heat match Python", (fx) => {
  it("person and exclusion checks", async () => {
    const rules = await src.getSectorRules(fx.slug);
    for (const e of fx.entities) {
      expect(isPerson(e.name), e.name).toBe(e.is_person);
      expect(isExcluded(e.name, rules), e.name).toBe(e.excluded);
    }
  });

  it("pattern heat", async () => {
    const signals = await src.getSignals(fx.slug);
    const byId = new Map(signals.map((s) => [s.id, s]));
    for (const p of fx.patterns) {
      const members = p.member_ids.map((id: string) => byId.get(id)!);
      expect(computeHeat(members, parseDate(fx.now))).toBeCloseTo(p.heat, 6);
    }
  });

  it("theme heat", async () => {
    const [signals, rules] = await Promise.all([src.getSignals(fx.slug), src.getSectorRules(fx.slug)]);
    const byId = new Map(signals.map((s) => [s.id, s]));
    for (const t of fx.themes) {
      const members = t.member_ids.map((id: string) => byId.get(id)!);
      expect(computeThemeHeat(members, parseDate(fx.now), rules)).toBeCloseTo(t.heat, 6);
    }
  });
});

describe("signalEntities", () => {
  it("prefers canonical entities and falls back to raw ones", () => {
    expect(signalEntities({ canonical_entities: ["Entain"], entities: ["Entain plc"] } as never)).toEqual(["Entain"]);
    expect(signalEntities({ entities: ["Acme"] } as never)).toEqual(["Acme"]);
    expect(signalEntities({} as never)).toEqual([]);
  });
});
```

- [ ] **Step 2: Run to see it fail**

Run: `cd web && pnpm test test/entities-heat.parity.test.ts`
Expected: FAIL, because the modules aren't found.

- [ ] **Step 3: Port the code**

**`brand.ts`:** copy the data from `dashboard/brand.py`:
- `_MS` (line 45) and the `GAVEL_20` / `CORPORATE_FARE_20` / `LINK_16` path strings, with their viewBoxes (Material Symbols use `"0 -960 960 960"`, the 20px ones `"0 0 20 20"`, `LINK_16` `"0 0 16 16"`);
- `_CATEGORY_ICON_NAMES` (line 80) → `categoryIconName`;
- `SOURCE_DOMAINS` (126), `COMPANY_DOMAINS` (143), `PEOPLE` (194), `SOURCE_NAMES` (249).

Skip `SOURCE_LOGOS` (a data URI). Copy `dashboard/assets/gambling_commission.png` to `web/public/logos/gambling_commission.png` and reference it by path.

**`entities.ts`:**
- `matchKey` from `src/entities.py` line 91, plus the helpers it calls (`strip_legal_suffixes`, `_tokens`, and their regexes or suffix lists in the same file). `matchKey` must give Python's output for every entity name in both fixtures.
- `isExcluded` from `src/cluster.py` line 57. It's true when `matchKey(name)` or `name.trim().toLowerCase()` is in the set built from `rules.excludedBodies`. Build that set the way `excluded_entities` in `src/cluster.py` builds it, with each name keyed through both forms.
- `isPerson` from `dashboard/app.py` lines 2226–2232.
- `sourceName` from line 2474.
- `initials` from line 2942.

**`heat.ts`:** port `src/cluster.py`, keeping the constants' values:
- `compute_theme_heat` (272–300);
- `compute_heat` (301 to the end of the function, including the `significance` term and `PEAK_SCORE_MAX`);
- `CLUSTER_WINDOW_DAYS`, `RECENCY_MAX`, `SIGNIFICANT_SCORE`, `MIN_THEME_COMPANIES`, `PEAK_SCORE_MAX`.

Python's `(now - most_recent).days` is floor division of the timedelta into days. Use `Math.floor((now - recent) / 86_400_000)`.

- [ ] **Step 4: Run the tests**

Run: `cd web && pnpm test test/entities-heat.parity.test.ts && pnpm typecheck`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add web/lib/brand.ts web/lib/signals/entities.ts web/lib/signals/heat.ts web/public/logos web/test/entities-heat.parity.test.ts
git commit -m "web: port entity names, brand data and heat formulas, pinned to Python"
```

---

### Task 6: Patterns and themes

**Files:**
- Create: `web/lib/signals/groups.ts`
- Test: `web/test/groups.parity.test.ts`

**Interfaces:**
- Consumes: Tasks 3–5.
- Produces:
  ```ts
  export type Flag = { text: string; icon: string | null; accent: boolean };
  export type Group = {
    id: string; kind: "pattern" | "theme";
    title: string; tier: Tier; heat: number;
    summary: string | null; meta: string;
    members: Signal[]; flags: Flag[];
    companies: string[]; keyPoints: string[];
    primaryCompany: string | null;            // patterns: for the logo tile
    themeIcon: string | null;                 // themes: categoryIconName(title)
    weeklyCounts: number[];
    active: boolean;                           // patterns: tier !== "Low" && pattern_type !== "routine"; themes: true
  };
  export function clusterVerdict(members: Signal[]): { summary: string | null; patternType: string | null; significance: number | null; coherent: boolean };
  export function buildPatterns(scored: Signal[], rules: SectorRules | null, now: Date): Group[];   // every coherent cluster, hottest first
  export function buildThemes(signals: Signal[], rules: SectorRules | null, now: Date): Group[];
  export function sharedScale(groups: Group[]): number;   // niceScale of the highest weekly count
  export const NOTABLE_PATTERN_TYPES = { escalation: "Escalating", wave: "Sector-wide" };
  export const DIRECTION_TAGS = { building: ["Building","trending_up",true], steady: ["Steady","trending_flat",false], easing: ["Easing","trending_down",false] };
  ```

- [ ] **Step 1: Write the failing parity test** (`web/test/groups.parity.test.ts`)

```ts
import { describe, expect, it } from "vitest";
import path from "node:path";
import gambling from "./fixtures/parity/gambling.json";
import fintech from "./fixtures/parity/fintech.json";
import { FileDataSource } from "@/lib/data/files";
import { buildPatterns, buildThemes, sharedScale } from "@/lib/signals/groups";
import { parseDate } from "@/lib/signals/time";

const repo = path.resolve(__dirname, "../..");
const src = new FileDataSource({ dataDir: path.join(repo, "data"), configDir: path.join(repo, "config") });

describe.each([gambling, fintech])("$slug: groups match Python", (fx) => {
  const now = parseDate(fx.now);

  it("patterns: same clusters, order, titles, tiers, meta, companies, weeks", async () => {
    const [signals, rules] = await Promise.all([src.getSignals(fx.slug), src.getSectorRules(fx.slug)]);
    // Newest first, as the Python side sorts before grouping (stable sort on the ISO string).
    const scored = signals.filter((s) => s.newsworthiness_score != null).sort((a, b) => b.published_at.localeCompare(a.published_at));
    const got = buildPatterns(scored, rules, now);
    expect(got.map((g) => g.id)).toEqual(fx.patterns.map((p) => p.id));
    got.forEach((g, i) => {
      const p = fx.patterns[i];
      expect({ title: g.title, tier: g.tier, active: g.active, summary: g.summary, meta: g.meta, companies: g.companies, weekly: g.weeklyCounts, members: g.members.map((m) => m.id) })
        .toEqual({ title: p.title, tier: p.tier, active: p.active, summary: p.summary, meta: p.meta, companies: p.companies, weekly: p.weekly_counts, members: p.member_ids });
    });
    expect(sharedScale(got)).toBe(fx.pattern_scale);
  });

  it("themes: same themes, order, tiers, meta, companies, direction, key points, weeks", async () => {
    const [signals, rules] = await Promise.all([src.getSignals(fx.slug), src.getSectorRules(fx.slug)]);
    const got = buildThemes(signals, rules, now);
    expect(got.map((g) => g.id)).toEqual(fx.themes.map((t) => t.id));
    got.forEach((g, i) => {
      const t = fx.themes[i];
      expect({ tier: g.tier, summary: g.summary, meta: g.meta, companies: g.companies, keyPoints: g.keyPoints, weekly: g.weeklyCounts, direction: g.flags[0]?.text ?? null })
        .toEqual({ tier: t.tier, summary: t.summary, meta: t.meta, companies: t.companies, keyPoints: t.key_points, weekly: t.weekly_counts, direction: t.direction ? ({ building: "Building", steady: "Steady", easing: "Easing" } as Record<string, string>)[t.direction] ?? null : null });
    });
    expect(sharedScale(got)).toBe(fx.theme_scale);
  });
});
```

- [ ] **Step 2: Run to see it fail**

Run: `cd web && pnpm test test/groups.parity.test.ts`
Expected: FAIL, because the module isn't found.

- [ ] **Step 3: Port the code**

Port from `dashboard/app.py`:
- `group_by_cluster` (2571);
- `_cluster_verdict` (2672–2696);
- the group-building parts of `render_patterns` (3167–3247) and `render_themes` (3256–3319). Leave out the Streamlit calls and HTML.

Keep these exactly:
- **Patterns:**
  - drop incoherent clusters;
  - sort by `computeHeat` descending (stable);
  - `active` as in the interface;
  - title is the most-mentioned non-excluded company, else `"Unnamed pattern"`;
  - companies are the rest;
  - flags come from `NOTABLE_PATTERN_TYPES`, or `{ text: "Routine filings", icon: null, accent: false }` for `"routine"`;
  - meta is `"N signals · M source(s) · <dateSpan>"`.
- **Themes:**
  - group every signal (scored or not) by `theme_id`;
  - sort by `computeThemeHeat` descending (stable);
  - companies are counted from non-excluded entities;
  - the direction flag comes from `DIRECTION_TAGS`;
  - meta is `"N signals · M company/companies · <dateSpan>"`;
  - `keyPoints` is the first member's non-empty `theme_key_points`, else `[]`.
- **Tie order:** `Counter.most_common()` keeps first-seen order for ties. In TypeScript, count with a `Map` (insertion-ordered), then sort the entries by count descending with a stable sort.
- **`weeklyCounts`** is `weeklyCounts(members, now)` from Task 4.

- [ ] **Step 4: Run the tests**

Run: `cd web && pnpm test test/groups.parity.test.ts && pnpm typecheck`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add web/lib/signals/groups.ts web/test/groups.parity.test.ts
git commit -m "web: port pattern and theme grouping, pinned to Python"
```

---

### Task 7: Feed filters, sort and date buckets

**Files:**
- Create: `web/lib/signals/filters.ts`
- Test: `web/test/filters.parity.test.ts`

**Interfaces:**
- Consumes: Tasks 3–5.
- Produces:
  ```ts
  export const DEFAULT_MIN_SCORE = 40;
  export const DATE_PRESETS: Record<string, number | null> = { "All time": null, "Last 30 days": 30, "Last 7 days": 7 };
  export type Criteria = { sourcesOff: string[]; categoriesOff: string[]; companies: string[]; minScore: number; days: number | null; search: string };
  export type FilterOptions = { sources: string[]; categories: string[]; entities: string[]; entityCounts: Map<string, number> };
  export function scoredSignals(signals: Signal[]): Signal[];        // score != null, newest first
  export function filterOptions(scored: Signal[]): FilterOptions;
  export function filterSignals(scored: Signal[], crit: Criteria, today: Date): Signal[];
  export function sortSignals(list: Signal[], order: "recent" | "score"): Signal[];
  export function criteriaFromSearchParams(sp: URLSearchParams, opts: FilterOptions): Criteria;
  export function criteriaToSearchParams(crit: Criteria): URLSearchParams;   // omits defaults
  ```

- [ ] **Step 1: Write the failing parity test** (`web/test/filters.parity.test.ts`)

```ts
import { describe, expect, it } from "vitest";
import path from "node:path";
import gambling from "./fixtures/parity/gambling.json";
import fintech from "./fixtures/parity/fintech.json";
import { FileDataSource } from "@/lib/data/files";
import { criteriaFromSearchParams, criteriaToSearchParams, DEFAULT_MIN_SCORE, filterOptions, filterSignals, scoredSignals } from "@/lib/signals/filters";
import { parseDate } from "@/lib/signals/time";

const repo = path.resolve(__dirname, "../..");
const src = new FileDataSource({ dataDir: path.join(repo, "data"), configDir: path.join(repo, "config") });

describe.each([gambling, fintech])("$slug: filters match Python", (fx) => {
  it("options", async () => {
    const opts = filterOptions(scoredSignals(await src.getSignals(fx.slug)));
    expect(opts.sources).toEqual(fx.filters.options.sources);
    expect(opts.categories).toEqual(fx.filters.options.categories);
    expect(opts.entities).toEqual(fx.filters.options.entities);
  });

  it.each(fx.filters.cases)("case $name", async (c) => {
    const scored = scoredSignals(await src.getSignals(fx.slug));
    const crit = { sourcesOff: c.criteria.sources_off, categoriesOff: c.criteria.categories_off, companies: c.criteria.companies, minScore: c.criteria.min_score, days: c.criteria.days, search: c.criteria.search };
    expect(filterSignals(scored, crit, parseDate(fx.now)).map((s) => s.id)).toEqual(c.ids);
  });
});

describe("date presets and URL round trip", () => {
  const signals = [
    { id: "new", source: "a", title: "t", published_at: "2026-10-15T00:00:00Z", newsworthiness_score: 50, entities: [] },
    { id: "old", source: "a", title: "t", published_at: "2026-08-01T00:00:00Z", newsworthiness_score: 50, entities: [] },
  ] as never[];
  const today = parseDate("2026-10-16T12:00:00Z");
  const base = { sourcesOff: [], categoriesOff: [], companies: [], minScore: 0, search: "" };

  it("last 30 days drops older signals", () => {
    expect(filterSignals(signals, { ...base, days: 30 }, today).map((s) => s.id)).toEqual(["new"]);
    expect(filterSignals(signals, { ...base, days: null }, today)).toHaveLength(2);
  });

  it("defaults leave the URL empty and survive a round trip", () => {
    const opts = filterOptions(signals);
    const def = criteriaFromSearchParams(new URLSearchParams(), opts);
    expect(def.minScore).toBe(DEFAULT_MIN_SCORE);
    expect(criteriaToSearchParams(def).toString()).toBe("");
    const custom = { ...def, search: "fine", sourcesOff: ["a"], days: 7 };
    expect(criteriaFromSearchParams(criteriaToSearchParams(custom), opts)).toEqual(custom);
  });

  it("ignores unknown values in the URL", () => {
    const opts = filterOptions(signals);
    const crit = criteriaFromSearchParams(new URLSearchParams("off=zzz&company=Nobody&min=abc&days=999"), opts);
    expect(crit).toMatchObject({ sourcesOff: [], companies: [], minScore: DEFAULT_MIN_SCORE, days: null });
  });
});
```

- [ ] **Step 2: Run to see it fail**

Run: `cd web && pnpm test test/filters.parity.test.ts`
Expected: FAIL, because the module isn't found.

- [ ] **Step 3: Port the code**

Port `_filter_options` (2409–2424) and `_filter_signals` (2439–2472) from `dashboard/app.py`, plus the sort in `render_feed` (2597 onwards): "Most recent" sorts by `published_at` descending, "Highest score" by score descending, then recency.

Details:
- `Counter.most_common()` ties keep first-seen order (as in Task 6).
- The entities sort is `(-count, name.toLowerCase())`.
- The sources sort is by `sourceName(s).toLowerCase()`.
- `today` replaces Python's `datetime.now()`. The start date is `today` minus `days` (UTC calendar days), and `pub < start` excludes.

URL parameters for `criteriaToSearchParams` and `criteriaFromSearchParams`:
- `q` = search;
- `off` = source to switch off (repeated);
- `catoff` = category to switch off (repeated);
- `company` (repeated);
- `min` = min score (an integer 0–100);
- `days` = `7` or `30`.

Values not in `opts` (or out of range) are dropped. Defaults are omitted.

- [ ] **Step 4: Run the tests**

Run: `cd web && pnpm test test/filters.parity.test.ts && pnpm typecheck`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add web/lib/signals/filters.ts web/test/filters.parity.test.ts
git commit -m "web: port feed filters and sorting with URL state, pinned to Python"
```

---

### Task 8: Insights numbers

**Files:**
- Create: `web/lib/signals/insights.ts`
- Test: `web/test/insights.parity.test.ts`, `web/test/insights.test.ts` (ports of `tests/test_overview.py`)

**Interfaces:**
- Consumes: Tasks 3–6.
- Produces:
  ```ts
  export const WEEKS = 18, HIGH_SCORE = 70, MARK_SCORE = 75, TREND_DAYS = 28;
  export const HEAT_RAMP = ["#93afff","#668eff","#3b6bff","#124ced","#0033ad"], HEAT_EMPTY = "#efede6";
  export type Tile = { label: string; value: string; note: string | null };
  export function weekStarts(now: Date, weeks?: number): Date[];
  export function weekIndexIn(signal: Signal, starts: Date[]): number | null;
  export function niceTop(peak: number): number;
  export function headlineTiles(scored: Signal[], now: Date, activePatterns: number, themesBuilding: number, healthy: number | null, total: number | null): Tile[];
  export function weeklyVolume(scored: Signal[], now: Date): { starts: Date[]; counts: number[]; marks: number[]; top: number; markTitles: Record<number, string[]> };
  export function categoryHeatmap(scored: Signal[], now: Date): { starts: Date[]; rows: { category: string; counts: number[]; total: number }[]; thresholds: number[] };
  export function heatThresholds(counts: number[]): number[];
  export function heatStep(count: number, thresholds: number[]): string;
  export function companyMovers(scored: Signal[], now: Date, rules: SectorRules | null): { name: string; top: number; count: number; change: number; weekly: number[] }[];
  export function themeTrend(members: Signal[], now: Date): ["building" | "steady" | "easing", number, number];
  export function activePatternCount(scored: Signal[], now: Date): number;   // app.py _active_pattern_count
  ```

- [ ] **Step 1: Write the failing tests**

`web/test/insights.parity.test.ts`:
```ts
import { describe, expect, it } from "vitest";
import path from "node:path";
import gambling from "./fixtures/parity/gambling.json";
import fintech from "./fixtures/parity/fintech.json";
import { FileDataSource } from "@/lib/data/files";
import { scoredSignals } from "@/lib/signals/filters";
import { activePatternCount, categoryHeatmap, companyMovers, headlineTiles, themeTrend, weeklyVolume } from "@/lib/signals/insights";
import { parseDate } from "@/lib/signals/time";

const repo = path.resolve(__dirname, "../..");
const src = new FileDataSource({ dataDir: path.join(repo, "data"), configDir: path.join(repo, "config") });

describe.each([gambling, fintech])("$slug: insights match Python", (fx) => {
  const now = parseDate(fx.now);
  const load = async () => {
    const [signals, rules, status] = await Promise.all([src.getSignals(fx.slug), src.getSectorRules(fx.slug), src.getRunStatus(fx.slug)]);
    return { signals, rules, status, scored: scoredSignals(signals) };
  };

  it("headline tiles", async () => {
    const { scored, status } = await load();
    expect(headlineTiles(scored, now, activePatternCount(scored, now), 0, status?.healthy_sources ?? null, status?.total_sources ?? null)).toEqual(fx.insights.tiles);
  });

  it("weekly volume", async () => {
    const { scored } = await load();
    const v = weeklyVolume(scored, now);
    expect({ counts: v.counts, marks: v.marks, top: v.top }).toEqual(fx.insights.volume);
  });

  it("category heat map", async () => {
    const { scored } = await load();
    const h = categoryHeatmap(scored, now);
    expect({ rows: h.rows, thresholds: h.thresholds }).toEqual(fx.insights.heatmap);
  });

  it("company movers", async () => {
    const { scored, rules } = await load();
    const got = companyMovers(scored, now, rules).map(({ name, top, count, change }) => ({ name, top, count, change }));
    expect(got).toEqual(fx.insights.movers.map(({ name, top, count, change }: { name: string; top: number; count: number; change: number }) => ({ name, top, count, change })));
  });

  it("theme trends", async () => {
    const { signals } = await load();
    const byTheme = new Map<string, typeof signals>();
    for (const s of signals) if (s.theme_id) byTheme.set(s.theme_id, [...(byTheme.get(s.theme_id) ?? []), s]);
    const got = [...byTheme].map(([name, m]) => { const [direction, recent, prior] = themeTrend(m, now); return { name, direction, recent, prior }; }).sort((a, b) => a.name.localeCompare(b.name));
    expect(got).toEqual(fx.insights.themes);
  });
});
```

`web/test/insights.test.ts`: port **every** test in `tests/test_overview.py` that covers logic (not HTML), keeping its inputs and expected values. These are:
- `TestWeeks`, all 3;
- `TestTiles.test_counts_and_comparisons` and `test_no_status_drops_the_sources_tile`;
- `TestHeatmap.test_steps` and `test_small_counts_use_one_step_each`;
- `TestMovers.test_ranks_by_best_relevance_and_excludes_regulators` (using `rules = { excludedBodies: ["Gambling Commission"], … }`) and `test_ties_on_top_score_go_to_more_total_relevance`;
- `TestThemes.test_trend_from_the_data`.

Use the same `NOW = 2026-10-08T12:00:00Z` and a `sig(daysAgo, score = 40, category = "Insolvency", entities = [], title = "t")` helper:
```ts
const NOW = new Date("2026-10-08T12:00:00Z");
const sig = (daysAgo: number, score = 40, category = "Insolvency", entities: string[] = [], title = "t") =>
  ({ id: `${daysAgo}-${score}-${title}-${Math.random()}`, source: "x", title, published_at: new Date(NOW.getTime() - daysAgo * 86_400_000).toISOString(), newsworthiness_score: score, canonical_category: category, entities, canonical_entities: entities }) as never;
```

- [ ] **Step 2: Run to see them fail**

Run: `cd web && pnpm test test/insights`
Expected: FAIL, because the module isn't found.

- [ ] **Step 3: Port the code**

**From `dashboard/overview.py`** (the numbers only, never the HTML):
- lines 22–68 (constants, `_dt`, `week_starts`, `week_index`, `_week_label`, `nice_top`);
- 70–100 (`Tile`, `_change`, `headline_tiles`);
- 215–244 (`heat_step`, `heat_thresholds`);
- 311–340 (`company_movers`);
- 382–399 (`DIRECTION_WORDS`, `TREND_DAYS`, `theme_trend`);
- the counting parts of `weekly_volume_html` (118–205) and `category_heatmap_html` (245–310), giving `weeklyVolume` and `categoryHeatmap`. `markTitles` collects the titles of signals at or above `MARK_SCORE` in each week, for the tooltip.

**From `dashboard/app.py`:** `activePatternCount(scored, now)` is `_active_pattern_count` (3920–3930) with an explicit clock. It reuses `buildPatterns(scored, null, now)` and counts `active`. Python's version reads the real clock, which is why the fixture counts `active` from its own pattern list instead.

The heat map rows sort busiest first, then by category name. Check this against `category_heatmap_html` and follow Python if it differs.

- [ ] **Step 4: Run the tests**

Run: `cd web && pnpm test test/insights && pnpm typecheck`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add web/lib/signals/insights.ts web/test/insights.parity.test.ts web/test/insights.test.ts
git commit -m "web: port the Insights numbers, pinned to Python and its tests"
```

---

### Task 9: Sign-in

**Files:**
- Create: `web/auth.ts`, `web/middleware.ts`, `web/app/api/auth/[...nextauth]/route.ts`
- Create: `web/app/login/page.tsx`, `web/app/login/login.module.css`, `web/app/login/actions.ts`, `web/components/LoginArt.tsx`, `web/components/LoginArt.module.css`, `web/lib/loginArt.ts`
- Test: `web/test/auth.test.ts`, `web/test/loginArt.test.ts`, `web/test/login.test.tsx`

**Interfaces:**
- Produces:
  ```ts
  // auth.ts
  export function buildProviders(env: NodeJS.ProcessEnv): Provider[];   // pure, for tests
  export function entraConfigured(env: NodeJS.ProcessEnv): boolean;
  export function devLoginEnabled(env: NodeJS.ProcessEnv): boolean;
  export const { handlers, auth, signIn, signOut };                     // NextAuth(...)
  // lib/loginArt.ts: data for the timeline art, deterministic
  export function loginArt(): { values: number[]; cells: { col: number; row: number; alpha: number; spark: boolean; dur: number; delay: number }[]; picks: { idx: number; value: number; label: string; count: number }[]; shift: number; cols: number; rows: number };
  ```
- Uses these environment variables:
  - `AUTH_SECRET`, `AUTH_URL`;
  - `AUTH_MICROSOFT_ENTRA_ID_ID`, `AUTH_MICROSOFT_ENTRA_ID_SECRET`, `AUTH_MICROSOFT_ENTRA_ID_ISSUER`;
  - `AUTH_REQUIRED_GROUP_ID`;
  - `AUTH_DEV_PASSWORD`.

- [ ] **Step 1: Write the failing auth tests** (`web/test/auth.test.ts`)

```ts
import { describe, expect, it } from "vitest";
import { buildProviders, devLoginEnabled, entraConfigured } from "@/auth";

const entra = {
  AUTH_MICROSOFT_ENTRA_ID_ID: "id",
  AUTH_MICROSOFT_ENTRA_ID_SECRET: "secret",
  AUTH_MICROSOFT_ENTRA_ID_ISSUER: "https://login.microsoftonline.com/tenant/v2.0",
};
const ids = (env: Record<string, string>) => buildProviders(env as NodeJS.ProcessEnv).map((p) => (typeof p === "function" ? p().id : p.id));

describe("providers", () => {
  it("offers Entra when it is configured", () => {
    expect(entraConfigured(entra as never)).toBe(true);
    expect(ids({ ...entra, NODE_ENV: "production" })).toEqual(["microsoft-entra-id"]);
  });

  it("never offers the dev password outside development", () => {
    expect(devLoginEnabled({ NODE_ENV: "production", AUTH_DEV_PASSWORD: "x" } as never)).toBe(false);
    expect(devLoginEnabled({ NODE_ENV: "test", AUTH_DEV_PASSWORD: "x" } as never)).toBe(false);
    expect(ids({ NODE_ENV: "production", AUTH_DEV_PASSWORD: "x" })).toEqual([]);
  });

  it("needs both development and a password for the dev provider", () => {
    expect(devLoginEnabled({ NODE_ENV: "development" } as never)).toBe(false);
    expect(ids({ NODE_ENV: "development", AUTH_DEV_PASSWORD: "local" })).toEqual(["dev-password"]);
  });

  it("offers nothing when nothing is configured", () => {
    expect(ids({ NODE_ENV: "production" })).toEqual([]);
  });
});
```

- [ ] **Step 2: Run to see it fail**

Run: `cd web && pnpm test test/auth.test.ts`
Expected: FAIL, because `@/auth` isn't found.

- [ ] **Step 3: Implement `web/auth.ts`, the route and the middleware**

`web/auth.ts`:
```ts
import NextAuth, { type NextAuthConfig } from "next-auth";
import type { Provider } from "next-auth/providers";
import MicrosoftEntraID from "next-auth/providers/microsoft-entra-id";
import Credentials from "next-auth/providers/credentials";
import { timingSafeEqual } from "node:crypto";

export const entraConfigured = (env: NodeJS.ProcessEnv) =>
  Boolean(env.AUTH_MICROSOFT_ENTRA_ID_ID && env.AUTH_MICROSOFT_ENTRA_ID_SECRET && env.AUTH_MICROSOFT_ENTRA_ID_ISSUER);

export const devLoginEnabled = (env: NodeJS.ProcessEnv) =>
  env.NODE_ENV === "development" && Boolean(env.AUTH_DEV_PASSWORD);

function samePassword(given: string, expected: string): boolean {
  const a = Buffer.from(given);
  const b = Buffer.from(expected);
  return a.length === b.length && timingSafeEqual(a, b);
}

export function buildProviders(env: NodeJS.ProcessEnv): Provider[] {
  const providers: Provider[] = [];
  if (entraConfigured(env)) {
    providers.push(
      MicrosoftEntraID({
        clientId: env.AUTH_MICROSOFT_ENTRA_ID_ID,
        clientSecret: env.AUTH_MICROSOFT_ENTRA_ID_SECRET,
        issuer: env.AUTH_MICROSOFT_ENTRA_ID_ISSUER,
        authorization: { params: { scope: "openid profile email" } },
      }),
    );
  }
  if (devLoginEnabled(env)) {
    providers.push(
      Credentials({
        id: "dev-password",
        name: "Dev password",
        credentials: { password: { label: "Password", type: "password" } },
        authorize: (creds) =>
          typeof creds?.password === "string" && samePassword(creds.password, env.AUTH_DEV_PASSWORD!)
            ? { id: "dev", name: "Local developer", email: "dev@localhost" }
            : null,
      }),
    );
  }
  return providers;
}

const config: NextAuthConfig = {
  providers: buildProviders(process.env),
  pages: { signIn: "/login" },
  session: { strategy: "jwt" },
  callbacks: {
    // Staff only: with a required group set, the Entra token must carry it.
    signIn({ account, profile }) {
      const group = process.env.AUTH_REQUIRED_GROUP_ID;
      if (account?.provider !== "microsoft-entra-id" || !group) return true;
      const groups = (profile as { groups?: string[] } | undefined)?.groups ?? [];
      return groups.includes(group);
    },
    authorized({ auth }) {
      return Boolean(auth?.user);
    },
  },
};

export const { handlers, auth, signIn, signOut } = NextAuth(config);
```

**Entra groups claim:** the app registration must emit the `groups` claim (Token configuration → Add groups claim → Security groups). Note this in `web/README.md` (Task 15). Before finalising, compare with `aie-ai-gateway`'s auth file (`grep -rn "AUTH_REQUIRED_GROUP_ID" ~/code/aie-ai-gateway --include=*.ts`) and copy its group check if it differs, e.g. if it reads groups from the `id_token` or Microsoft Graph.

`web/app/api/auth/[...nextauth]/route.ts`:
```ts
import { handlers } from "@/auth";
export const { GET, POST } = handlers;
```

`web/middleware.ts`:
```ts
import { auth } from "@/auth";
import { NextResponse } from "next/server";

const PUBLIC = [/^\/login(\/|$)/, /^\/api\/(health|ready|auth)(\/|$)/, /^\/_next\//, /^\/favicon/, /^\/pa-logo\.svg$/, /^\/logos\//];

export default auth((req) => {
  const { pathname, search } = req.nextUrl;
  if (PUBLIC.some((re) => re.test(pathname))) return NextResponse.next();
  if (!req.auth?.user) {
    const url = new URL("/login", req.nextUrl);
    url.searchParams.set("next", pathname + search);
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
});

export const config = { matcher: ["/((?!_next/static|_next/image).*)"] };
```

- [ ] **Step 4: Write the failing art and page tests**

`web/test/loginArt.test.ts`:
```ts
import { describe, expect, it } from "vitest";
import { loginArt } from "@/lib/loginArt";

describe("loginArt", () => {
  it("is deterministic", () => expect(loginArt()).toEqual(loginArt()));
  it("has 22 weekly values between 0.08 and 0.9, drawn twice", () => {
    const art = loginArt();
    expect(art.values).toHaveLength(22);
    for (const v of art.values) expect(v).toBeGreaterThanOrEqual(0.08), expect(v).toBeLessThanOrEqual(0.9);
    expect(art.cols).toBe(45);
    expect(art.shift).toBeCloseTo(22 / 45, 6);
  });
  it("starts every animation mid-cycle (negative delays) so it moves on the first frame", () => {
    for (const c of loginArt().cells) expect(c.delay).toBeLessThanOrEqual(0);
  });
  it("picks the 3 busiest weeks, at least 5 apart", () => {
    const idx = loginArt().picks.map((p) => p.idx).sort((a, b) => a - b);
    expect(idx).toHaveLength(3);
    expect(idx[1] - idx[0]).toBeGreaterThanOrEqual(5);
    expect(idx[2] - idx[1]).toBeGreaterThanOrEqual(5);
  });
});
```

`web/test/login.test.tsx`: render the page's presentational part, `LoginPanel`, exported from `web/app/login/page.tsx`. Its props are `{ entra: boolean; dev: boolean; error?: string }`:
```tsx
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { LoginPanel } from "@/app/login/page";

describe("LoginPanel", () => {
  it("shows the Microsoft button when Entra is set up", () => {
    render(<LoginPanel entra dev={false} />);
    expect(screen.getByRole("button", { name: "Sign in with Microsoft" })).toBeInTheDocument();
    expect(screen.queryByLabelText("Password")).toBeNull();
  });
  it("shows the dev password form only when enabled", () => {
    render(<LoginPanel entra={false} dev />);
    expect(screen.getByLabelText("Password")).toBeInTheDocument();
  });
  it("says sign-in isn't set up when neither is available", () => {
    render(<LoginPanel entra={false} dev={false} />);
    expect(screen.getByText("Sign-in isn't set up yet.")).toBeInTheDocument();
  });
  it("shows the wrong-password message", () => {
    render(<LoginPanel entra={false} dev error="CredentialsSignin" />);
    expect(screen.getByText("That password isn't right. Try again.")).toBeInTheDocument();
  });
});
```

- [ ] **Step 5: Run to see them fail**

Run: `cd web && pnpm test test/loginArt.test.ts test/login.test.tsx`
Expected: FAIL, because the modules aren't found.

- [ ] **Step 6: Implement the art, the page and the sign-in actions**

**`web/lib/loginArt.ts`:** port the data side of `_login_art` (`dashboard/app.py` 1940–2038).
- Use the same `n = 22`, `rows = 14`, `SCROLL = 40` and the same formulas (wave, jag, clamp, warmth, fade, alpha, spark threshold, durations and delays, busiest-3 picks spaced 5 or more apart, `count = round(6 + v*40)`, labels "Week of {d} {Mon}").
- For `noise`, Python uses `hashlib.blake2b`. Node's `crypto` supports it: `createHash("blake2b512")`. Use it with the same input encoding as Python. Read the Python `noise` to get the encoding exactly.

**`web/components/LoginArt.tsx`:** a server component rendering the same DOM and classes as `_login_art`'s HTML:
- `.login-line > .la-track > .la-heat (cells) + svg.la-track-line (polyline) + .la-at…`;
- per-pick `@keyframes` in an inline `<style>`.

**`web/components/LoginArt.module.css`:** translate the sign-in CSS (`dashboard/app.py` 1695–1896), keeping only what belongs to the art and hero. CSS module class names replace the global ones.

**`web/app/login/page.tsx`:** a server component that renders a two-column layout (1.15 : 1, 100vh, full bleed).
- Left: the cobalt hero with kicker "Sector Signal", headline "Spot the story before it breaks.", the lede from Streamlit, and `<LoginArt/>`.
- Right: `<LoginPanel entra={entraConfigured(process.env)} dev={devLoginEnabled(process.env)} error={searchParams.error} />`.
- `LoginPanel` (exported, presentational) shows the masthead lockup (`/pa-logo.svg` plus the wordmark "Sector" / "Signal"), "Sign in", one line of copy, then one of:
  - `entra`: a form posting to the `signInWithEntra` server action, button text "Sign in with Microsoft";
  - `dev`: a form with a labelled "Password" field posting to `signInWithDev`;
  - neither: "Sign-in isn't set up yet.".
- `error === "CredentialsSignin"` shows "That password isn't right. Try again.".
- The footer reads "A Press Association prototype".
- Below 760px the art is hidden.

`web/app/login/actions.ts`:
```ts
"use server";
import { signIn } from "@/auth";

const safeNext = (next: FormDataEntryValue | null) =>
  typeof next === "string" && next.startsWith("/") && !next.startsWith("//") ? next : "/";

export async function signInWithEntra(form: FormData) {
  await signIn("microsoft-entra-id", { redirectTo: safeNext(form.get("next")) });
}

export async function signInWithDev(form: FormData) {
  await signIn("dev-password", { password: form.get("password"), redirectTo: safeNext(form.get("next")) });
}
```

Pass `next` through as a hidden input from `searchParams.next`.

- [ ] **Step 7: Run the tests and check in the browser**

Run: `cd web && pnpm test && pnpm typecheck`
Expected: all pass.

Then run `cd web && AUTH_SECRET=dev-secret AUTH_DEV_PASSWORD=local pnpm dev` and open `http://localhost:3000`. Expect a redirect to `/login`, the art already moving, and the password "local" signing you in (landing on the temporary home page).

- [ ] **Step 8: Commit**

```bash
git add web/auth.ts web/middleware.ts web/app/api/auth web/app/login web/components/LoginArt* web/lib/loginArt.ts web/test/auth.test.ts web/test/loginArt.test.ts web/test/login.test.tsx
git commit -m "web: sign-in with Microsoft Entra, a dev-only password, and the hero art"
```

---

### Task 10: App shell (header, sector routing, empty states, readiness)

**Files:**
- Create: `web/lib/load.ts`, `web/app/page.tsx` (replace), `web/app/[sector]/layout.tsx`, `web/app/[sector]/page.tsx`, `web/app/[sector]/not-found.tsx`, `web/app/api/ready/route.ts`
- Create: `web/components/{Masthead,SectorMenu,StatusStrip,Tabs,EmptyState}.tsx`, `web/components/shell.module.css`
- Test: `web/test/load.test.ts`, `web/test/shell.test.tsx`, `web/test/ready.test.ts`

**Interfaces:**
- Consumes: `getDataSource`, `DataError`, `isSlug` (Task 3); `humaniseAge` (Task 4); `sourceName` (Task 5).
- Produces:
  ```ts
  // lib/load.ts
  export type SectorView =
    | { state: "ready"; sector: SectorEntry; sectors: SectorEntry[]; signals: Signal[]; status: RunStatus | null; rules: SectorRules | null; now: Date }
    | { state: "setting_up" | "empty"; sector: SectorEntry; sectors: SectorEntry[]; status: RunStatus | null }
    | { state: "unavailable"; sectors: SectorEntry[] };
  export function loadSector(slug: string, src?: DataSource): Promise<SectorView>;  // calls notFound() for an unknown or invalid slug
  export const TABS = [["feed","Feed"],["patterns","Patterns"],["themes","Themes"],["insights","Insights"]] as const;
  ```
- `now` is `new Date()` at request time. Tests pass a fixed clock through the components' props.

- [ ] **Step 1: Write the failing tests**

`web/test/load.test.ts` uses a fake `DataSource`:
```ts
import { describe, expect, it, vi } from "vitest";
import { DataError } from "@/lib/data/errors";
import { loadSector } from "@/lib/load";

vi.mock("next/navigation", () => ({ notFound: () => { throw new Error("NEXT_NOT_FOUND"); } }));

const sectors = [
  { slug: "demo", name: "Demo", status: "ready", signal_count: 1 },
  { slug: "newbie", name: "New", status: "setting_up", signal_count: 0 },
];
const fake = (over: Partial<Record<string, unknown>> = {}) => ({
  listSectors: async () => sectors,
  getSignals: async (s: string) => { if (s === "newbie") throw new DataError("not_found", "x"); return [{ id: "a", source: "x", title: "t", published_at: "2026-10-15T00:00:00Z", newsworthiness_score: 50, entities: [] }]; },
  getRunStatus: async () => null,
  getSectorRules: async () => ({ slug: "demo", name: "Demo", categories: [], companies: [], excludedBodies: [] }),
  ...over,
}) as never;

describe("loadSector", () => {
  it("loads a ready sector", async () => expect((await loadSector("demo", fake())).state).toBe("ready"));
  it("reports setting up rather than erroring", async () => expect((await loadSector("newbie", fake())).state).toBe("setting_up"));
  it("404s an unknown sector without reading signals", async () => {
    const getSignals = vi.fn();
    await expect(loadSector("nope", fake({ getSignals }))).rejects.toThrow("NEXT_NOT_FOUND");
    expect(getSignals).not.toHaveBeenCalled();
  });
  it("404s a hostile slug without reading anything", async () => {
    const listSectors = vi.fn(async () => sectors);
    await expect(loadSector("..%2F", fake({ listSectors }))).rejects.toThrow("NEXT_NOT_FOUND");
    expect(listSectors).not.toHaveBeenCalled();
  });
  it("says unavailable when the data can't be reached", async () => {
    const down = fake({ listSectors: async () => { throw new DataError("unreachable", "down"); } });
    expect((await loadSector("demo", down)).state).toBe("unavailable");
  });
});
```

`web/test/shell.test.tsx`:
```tsx
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatusStrip } from "@/components/StatusStrip";
import { EmptyState } from "@/components/EmptyState";
import { Tabs } from "@/components/Tabs";

const now = new Date("2026-10-16T16:20:23Z");

describe("StatusStrip", () => {
  it("says when it updated and how many sources worked", () => {
    render(<StatusStrip now={now} status={{ finished_at: "2026-10-16T14:20:23Z", healthy_sources: 8, total_sources: 9, sources: { AsaCollector: { items: 0, ok: false, error: false } } } as never} />);
    expect(screen.getByText(/Updated 2 hours ago · 8\/9 sources/)).toBeInTheDocument();
    expect(screen.getByText("Which sources returned nothing?")).toBeInTheDocument();
  });
  it("renders nothing without a status", () => {
    const { container } = render(<StatusStrip now={now} status={null} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("EmptyState", () => {
  it("shows the unavailable message", () => {
    render(<EmptyState kind="unavailable" />);
    expect(screen.getByText("We couldn't load the latest signals. Try again in a few minutes.")).toBeInTheDocument();
  });
});

describe("Tabs", () => {
  it("links each tab and marks the current one", () => {
    render(<Tabs slug="gambling" current="themes" />);
    expect(screen.getByRole("link", { name: "Themes" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Feed" })).toHaveAttribute("href", "/gambling/feed");
  });
});
```

`web/test/ready.test.ts`:
```ts
import { describe, expect, it, vi } from "vitest";

describe("/api/ready", () => {
  it("is 200 when sectors load and 503 when they don't", async () => {
    vi.resetModules();
    vi.doMock("@/lib/data/source", () => ({ getDataSource: () => ({ listSectors: async () => [] }) }));
    expect((await (await import("@/app/api/ready/route")).GET()).status).toBe(200);
    vi.resetModules();
    vi.doMock("@/lib/data/source", () => ({ getDataSource: () => ({ listSectors: async () => { throw new Error("down"); } }) }));
    expect((await (await import("@/app/api/ready/route")).GET()).status).toBe(503);
  });
});
```

- [ ] **Step 2: Run to see them fail**

Run: `cd web && pnpm test test/load.test.ts test/shell.test.tsx test/ready.test.ts`
Expected: FAIL, because the modules aren't found.

- [ ] **Step 3: Implement**

**`web/lib/load.ts`:**
1. Check `isSlug` first, then `listSectors()`; an unknown slug goes to `notFound()`.
2. `DataError("unreachable" | "invalid")` from `listSectors` gives `{ state: "unavailable", sectors: [] }`.
3. A sector whose status isn't `"ready"`, or whose `getSignals` throws `not_found`, gives `"setting_up"`.
4. Zero signals gives `"empty"`.
5. Rules that fail to load become `rules: null`, and the views still work.

The logic is the same as `view_state` and `sector_note` in `dashboard/data.py` (161–181); match their wording.

**`web/app/api/ready/route.ts`:**
```ts
import { getDataSource } from "@/lib/data/source";
export const dynamic = "force-dynamic";
export async function GET() {
  try {
    await getDataSource().listSectors();
    return Response.json({ ready: true });
  } catch {
    return Response.json({ ready: false }, { status: 503 });
  }
}
```

**`web/app/page.tsx`:** load the sectors, order them like `order_index` (`dashboard/data.py` 136), and redirect to `/<first ready sector>/feed`. If the data is unavailable, render `<EmptyState kind="unavailable"/>`.

**`web/app/[sector]/page.tsx`:** `redirect(\`/${params.sector}/feed\`)`.

**`web/app/[sector]/layout.tsx`:** call `loadSector`, then render:
- `<Masthead>` (the lockup, as in `render_masthead` 1897–1919);
- `<SectorMenu>` (a `<details>` listing sectors as links to the same tab, as `_sector_switcher` 1920–1938 does, without the "New sector" row);
- the `.pa-title` sector name with the "Sector" kicker and the sector note;
- `<StatusStrip>`, with the logic from `render_health_strip` 3332–3390;
- `<Tabs>`;
- then `children`, or `<EmptyState>` for the non-ready states.

**`Tabs`:** a client component using `useSelectedLayoutSegment()` to find the current tab, so the layout doesn't need to know it.

**CSS:** translate the masthead (121–247), section heading (248–277) and freshness strip (910–925) styles into `shell.module.css`.

**`web/app/[sector]/not-found.tsx`:** "We couldn't find that sector." with a link home.

- [ ] **Step 4: Run the tests and check in the browser**

Run: `cd web && pnpm test && pnpm typecheck`
Expected: all pass.

In `pnpm dev` (signed in):
- `/` redirects to `/gambling/feed`;
- the sector menu switches to fintech;
- `/nope/feed` shows the not-found page;
- the status strip shows real numbers.

- [ ] **Step 5: Commit**

```bash
git add web/lib/load.ts web/app/page.tsx web/app/[sector] web/app/api/ready web/components web/test/load.test.ts web/test/shell.test.tsx web/test/ready.test.ts
git commit -m "web: app shell with sector routing, status strip, tabs and empty states"
```

---

### Task 11: Shared pieces (signal card, tags, ring, pill, logos)

**Files:**
- Create: `web/components/{SignalCard,Tag,Icon,RelevanceRing,ActivityPill,SourceLogo}.tsx`, `web/components/card.module.css`
- Create: `web/app/api/logo/[domain]/route.ts`
- Test: `web/test/cards.test.tsx`, `web/test/logo.test.ts`

**Interfaces:**
- Consumes: `scoreTier`, `RELEVANCE_LABELS`, `ACTIVITY_LABELS`, `ACTIVITY_RING`, `relativeTime`, `fullDate` (Task 4); `ICON_PATHS`, `categoryIconName`, `SOURCE_DOMAINS`, `COMPANY_DOMAINS`, `sourceName`, `isPerson`, `initials` (Task 5).
- Produces:
  ```tsx
  <Icon name="trending_up" size={16} />
  <RelevanceRing score={45} />                                  // 20px donut, arc = score%
  <ActivityPill tier="High" />                                  // ring at 90 + "Very active"
  <Tag kind="entity" | "accent" | "plain" icon?="person" | "corporate" | iconName>{text}</Tag>
  <SourceLogo source="gambling_commission" />                   // logo, else initials
  <CompanyLogo name="Entain" />                                 // logo via /api/logo, else initials
  <SignalCard signal={s} now={now} clusterInfo?={{ heat, size }} compact?={false} />
  ```
- `GET /api/logo/[domain]` proxies `https://img.logo.dev/<domain>?token=…&size=64&format=png` with `LOGO_DEV_TOKEN`. The response is cached for a day (`Cache-Control: public, max-age=86400`). It returns 404 when there's no token or the domain isn't in `SOURCE_DOMAINS`/`COMPANY_DOMAINS` values.

- [ ] **Step 1: Write the failing tests**

`web/test/cards.test.tsx`:
```tsx
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { RelevanceRing } from "@/components/RelevanceRing";
import { ActivityPill } from "@/components/ActivityPill";
import { SignalCard } from "@/components/SignalCard";

const now = new Date("2026-10-16T14:20:23Z");
const signal = {
  id: "a1", source: "gazette", source_url: "https://www.thegazette.co.uk/notice/1", title: "Winding-up petition against Acme",
  published_at: "2026-10-16T02:00:00Z", newsworthiness_score: 45, why_it_matters: "Signals distress.",
  canonical_category: "Insolvency", canonical_entities: ["Acme", "Beta", "Gamma", "Delta", "Epsilon"], entities: [],
} as never;

describe("RelevanceRing", () => {
  it("draws an arc proportional to the score", () => {
    const { container } = render(<RelevanceRing score={50} />);
    const arc = container.querySelectorAll("circle")[1];
    const [len, total] = arc.getAttribute("stroke-dasharray")!.split(" ").map(Number);
    expect(len / total).toBeCloseTo(0.5, 3);
  });
});

describe("ActivityPill", () => {
  it("names the tier in words", () => {
    render(<ActivityPill tier="High" />);
    expect(screen.getByText("Very active")).toBeInTheDocument();
  });
});

describe("SignalCard", () => {
  it("shows title, why it matters, relevance, time and a safe source link", () => {
    render(<SignalCard signal={signal} now={now} />);
    expect(screen.getByText("Winding-up petition against Acme")).toBeInTheDocument();
    expect(screen.getByText("Signals distress.")).toBeInTheDocument();
    expect(screen.getByText(/Relevant/)).toBeInTheDocument();
    expect(screen.getByText(/12 hours ago/)).toBeInTheDocument();
    const link = screen.getByRole("link", { name: /Source/ });
    expect(link).toHaveAttribute("href", "https://www.thegazette.co.uk/notice/1");
    expect(link).toHaveAttribute("rel", expect.stringContaining("noopener"));
  });

  it("caps entity tags at 4 with a +N more", () => {
    render(<SignalCard signal={signal} now={now} />);
    expect(screen.getByText("+1 more")).toBeInTheDocument();
  });

  it("drops a javascript: source URL", () => {
    render(<SignalCard signal={{ ...signal, source_url: "javascript:alert(1)" } as never} now={now} />);
    expect(screen.queryByRole("link", { name: /Source/ })).toBeNull();
  });
});
```

`web/test/logo.test.ts`:
```ts
import { describe, expect, it, vi, afterEach } from "vitest";
import { GET } from "@/app/api/logo/[domain]/route";

const call = (domain: string) => GET(new Request(`http://x/api/logo/${domain}`), { params: Promise.resolve({ domain }) });

describe("/api/logo", () => {
  afterEach(() => { vi.unstubAllEnvs(); vi.unstubAllGlobals(); });

  it("404s without a token", async () => {
    vi.stubEnv("LOGO_DEV_TOKEN", "");
    expect((await call("gamblingcommission.gov.uk")).status).toBe(404);
  });

  it("404s a domain we don't know", async () => {
    vi.stubEnv("LOGO_DEV_TOKEN", "t");
    expect((await call("evil.example")).status).toBe(404);
  });

  it("proxies a known domain without exposing the token", async () => {
    vi.stubEnv("LOGO_DEV_TOKEN", "secret-token");
    const fetchMock = vi.fn(async () => new Response(new Uint8Array([1, 2, 3]), { headers: { "content-type": "image/png" } }));
    vi.stubGlobal("fetch", fetchMock);
    const domain = (await import("@/lib/brand")).SOURCE_DOMAINS.gambling_commission;
    const res = await call(domain);
    expect(res.status).toBe(200);
    expect(res.headers.get("cache-control")).toContain("max-age=86400");
    expect(JSON.stringify([...res.headers])).not.toContain("secret-token");
  });
});
```

Before writing the third test, check `SOURCE_DOMAINS` in `dashboard/brand.py` (line 126) for the key of the Gambling Commission entry. Use whichever key exists; the test only needs a known domain.

- [ ] **Step 2: Run to see them fail**

Run: `cd web && pnpm test test/cards.test.tsx test/logo.test.ts`
Expected: FAIL, because the modules aren't found.

- [ ] **Step 3: Implement**

Port from `dashboard/app.py`:
- `safe_url` (2143–2156): only `http:` and `https:` survive;
- `_relevance_ring` (2259–2273);
- `_activity_pill` (2710–2715);
- `_source_logo` (2212–2224), `_entity_icon` (2233–2237), `_company_logo` (2246–2258);
- `render_card` (2275–2342) and its constants `MAX_ENTITY_TAGS = 4`, `RELEVANCE_LABELS`.

The cluster line on a card ("Part of a pattern · N signals") comes from `clusterInfo`.

Translate the CSS:
- signal card (`dashboard/app.py` 278–422);
- the tag rules inside it (`.sc-tag*`, around 375–404);
- motion for cards (1456–1541, the `.signal-card` parts);

into `card.module.css`, or reuse the `pa-*` classes from `pa-brand.css` where they match exactly (`pa-tag`, `pa-pill`, `pa-card`).

Logos go through `/api/logo/<domain>`; the token never reaches the browser. `SourceLogo` uses `/logos/gambling_commission.png` for the Gambling Commission (as `SOURCE_LOGOS`).

- [ ] **Step 4: Run the tests**

Run: `cd web && pnpm test && pnpm typecheck`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add web/components web/app/api/logo web/test/cards.test.tsx web/test/logo.test.ts
git commit -m "web: signal card, tags, relevance ring, activity pill and server-side logos"
```

---

### Task 12: Feed

**Files:**
- Create: `web/app/[sector]/feed/page.tsx`, `web/app/[sector]/feed/feed.module.css`, `web/components/FeedFilters.tsx`, `web/components/FeedToolbar.tsx`
- Test: `web/test/feed.test.tsx`

**Interfaces:**
- Consumes: `loadSector` (Task 10); `scoredSignals`, `filterOptions`, `filterSignals`, `sortSignals`, `criteriaFromSearchParams`, `criteriaToSearchParams` (Task 7); `dateBucket` (Task 4); `buildPatterns` and `computeHeat` (Tasks 5–6) for each card's `clusterInfo`; `SignalCard` (Task 11).
- Produces: `/[sector]/feed?q=&off=&catoff=&company=&min=&days=&sort=score`.

- [ ] **Step 1: Write the failing tests** (`web/test/feed.test.tsx`)

`FeedFilters` is a client component that reads and writes the URL. Test it with a mocked router:
```tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FeedFilters } from "@/components/FeedFilters";

const replace = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
  usePathname: () => "/gambling/feed",
  useSearchParams: () => new URLSearchParams("q=fine"),
}));

const options = { sources: ["gazette", "asa"], categories: ["Insolvency", "Other"], entities: ["Entain", "Rank"], entityCounts: new Map([["Entain", 3], ["Rank", 1]]) };

describe("FeedFilters", () => {
  it("shows the current search from the URL", () => {
    render(<FeedFilters options={options} />);
    expect(screen.getByRole("searchbox", { name: "Search signals" })).toHaveValue("fine");
  });

  it("switching a source off writes it to the URL", async () => {
    render(<FeedFilters options={options} />);
    await userEvent.click(screen.getByRole("checkbox", { name: "The Gazette" }));
    expect(replace).toHaveBeenLastCalledWith(expect.stringContaining("off=gazette"), { scroll: false });
  });

  it("clear all resets the URL", async () => {
    render(<FeedFilters options={options} />);
    await userEvent.click(screen.getByRole("button", { name: "Clear all" }));
    expect(replace).toHaveBeenLastCalledWith("/gambling/feed", { scroll: false });
  });
});
```

The label "The Gazette" must come from `sourceName("gazette")`. Check `SOURCE_NAMES` and use whatever name it returns in the test.

- [ ] **Step 2: Run to see it fail**

Run: `cd web && pnpm test test/feed.test.tsx`
Expected: FAIL, because the module isn't found.

- [ ] **Step 3: Implement**

**`page.tsx`** (server component):
1. Call `loadSector`.
2. Take `scoredSignals`, `filterOptions`, then `criteriaFromSearchParams(searchParams)`, `filterSignals` with today and `sortSignals`.
3. Group into date buckets (`Today`, `Yesterday`, `This week`, `Earlier`) with `<h2>` headings.
4. Render `<SignalCard>` for each signal, with `clusterInfo` from the pattern each signal belongs to.
5. Add a toolbar ("Showing X of Y scored signals." plus the sort control, ported from `_feed_toolbar` 2556 and `_sort_control` 2562) and `<FeedFilters>` in the sidebar.

Empty results show "No signals match these filters." with a Clear all link.

**`FeedFilters.tsx`** (client) ports `apply_filters` (2478–2555) as plain HTML controls:
- a search box (`type="search"`, label "Search signals");
- collapsible `<details>` sections for Sources, Categories and Companies, each with checkboxes. Companies are a checkbox list of the top entities with counts; the Streamlit multiselect is replaced, and the first 10 show with "Show all";
- a minimum relevance select (0, 40, 70, labelled as Streamlit does);
- a published select (All time, Last 30 days, Last 7 days);
- "Clear all".

Each change calls `router.replace(pathname + "?" + criteriaToSearchParams(next), { scroll: false })`. The search box is debounced by 300ms.

**CSS:** translate the sidebar filters (1007–1209) and feed filter bar (1210–1348) into `feed.module.css`.

- [ ] **Step 4: Run the tests and check in the browser**

Run: `cd web && pnpm test && pnpm typecheck`
Expected: all pass.

In `pnpm dev`, put `/gambling/feed` next to Streamlit's Feed at the default filters. The "Showing X of Y" count must match. Search "commission" must match Streamlit's count.

- [ ] **Step 5: Commit**

```bash
git add web/app/[sector]/feed web/components/FeedFilters.tsx web/components/FeedToolbar.tsx web/test/feed.test.tsx
git commit -m "web: Feed with URL-based filters, sorting and date groups"
```

---

### Task 13: Patterns, Themes and the preview panel

**Files:**
- Create: `web/app/[sector]/patterns/page.tsx`, `web/app/[sector]/themes/page.tsx`
- Create: `web/components/{GroupCard,GroupList,PreviewPane,SignalList,Sparkline}.tsx`, `web/components/groups.module.css`, `web/components/pane.module.css`
- Test: `web/test/groups-ui.test.tsx`, `web/test/sparkline.test.tsx`

**Interfaces:**
- Consumes: `buildPatterns`, `buildThemes`, `sharedScale` (Task 6); `weekIndex`, `weekRange`, `dateSpan`, `fullDate`, `relativeTime` (Task 4); `Tag`, `ActivityPill`, `RelevanceRing`, `CompanyLogo`, `Icon`, `SourceLogo` (Task 11).
- Produces: `/[sector]/patterns?pattern=<id>&quiet=1` and `/[sector]/themes?theme=<id>`. With no `pattern`/`theme`, no panel is shown.

- [ ] **Step 1: Write the failing tests**

`web/test/groups-ui.test.tsx`:
```tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { GroupList } from "@/components/GroupList";

const push = vi.fn();
let search = new URLSearchParams();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: push }),
  usePathname: () => "/gambling/themes",
  useSearchParams: () => search,
}));

const now = new Date("2026-10-16T14:20:23Z");
const member = (id: string, d: string) => ({ id, source: "parliament", title: `Signal ${id}`, published_at: d, newsworthiness_score: 45, why_it_matters: "Why.", canonical_category: "Policy and legislation", canonical_entities: ["Lisa Nandy"], entities: [] });
const group = {
  id: "Policy and legislation", kind: "theme", title: "Policy and legislation", tier: "High", heat: 210,
  summary: "Parliamentary scrutiny intensified.", meta: "2 signals · 1 company · 1 Oct – 6 Oct",
  members: [member("a", "2026-10-06T00:00:00Z"), member("b", "2026-10-01T00:00:00Z")],
  flags: [{ text: "Building", icon: "trending_up", accent: true }],
  companies: ["Lisa Nandy", "A", "B", "C", "D", "E", "F"], keyPoints: ["Point one."],
  primaryCompany: null, themeIcon: "account_balance", weeklyCounts: [0,0,0,0,0,0,0,0,0,0,0,1,1], active: true,
} as never;

describe("GroupList", () => {
  it("opens the panel when a card is clicked, via the URL", async () => {
    search = new URLSearchParams();
    render(<GroupList groups={[group]} param="theme" scale={2} now={now} />);
    expect(screen.queryByRole("complementary", { name: /Policy and legislation/ })).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Preview Policy and legislation" }));
    expect(push).toHaveBeenLastCalledWith("/gambling/themes?theme=Policy+and+legislation", { scroll: false });
  });

  it("shows the panel for the selected group, signals newest first", () => {
    search = new URLSearchParams("theme=Policy and legislation");
    render(<GroupList groups={[group]} param="theme" scale={2} now={now} />);
    const pane = screen.getByRole("complementary", { name: /Policy and legislation/ });
    const titles = [...pane.querySelectorAll("[data-signal-title]")].map((e) => e.textContent);
    expect(titles).toEqual(["Signal a", "Signal b"]);
    expect(screen.getByRole("button", { name: "Policy and legislation, showing in preview" })).toHaveAttribute("aria-pressed", "true");
  });

  it("closes with the ×", async () => {
    search = new URLSearchParams("theme=Policy and legislation");
    render(<GroupList groups={[group]} param="theme" scale={2} now={now} />);
    await userEvent.click(screen.getByRole("button", { name: "Close preview" }));
    expect(push).toHaveBeenLastCalledWith("/gambling/themes", { scroll: false });
  });

  it("keeps the summary behind Show summary, and swaps in every company when open", async () => {
    search = new URLSearchParams("theme=Policy and legislation");
    render(<GroupList groups={[group]} param="theme" scale={2} now={now} />);
    const pane = screen.getByRole("complementary", { name: /Policy and legislation/ });
    const toggle = pane.querySelector("details.sp-toggle") as HTMLDetailsElement;
    expect(toggle.open).toBe(false);
    expect(pane.textContent).toContain("+2 more");
    await userEvent.click(screen.getByText("Show summary"));
    expect(toggle.open).toBe(true);
  });

  it("ignores a selection that isn't in the list", () => {
    search = new URLSearchParams("theme=Nope");
    render(<GroupList groups={[group]} param="theme" scale={2} now={now} />);
    expect(screen.queryByRole("complementary")).toBeNull();
  });
});
```

`web/test/sparkline.test.tsx`:
```tsx
import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { Sparkline } from "@/components/Sparkline";

describe("Sparkline", () => {
  it("plots one point per week on the shared scale, with a dot on the latest", () => {
    const { container } = render(<Sparkline counts={[0, 2, 4]} scale={4} start={new Date("2026-09-28T00:00:00Z")} />);
    const pts = container.querySelector("polyline")!.getAttribute("points")!.trim().split(/\s+/);
    expect(pts).toHaveLength(3);
    const lastY = Number(pts[2].split(",")[1]);
    const firstY = Number(pts[0].split(",")[1]);
    expect(lastY).toBeLessThan(firstY);
    expect(container.querySelector("[data-latest]")).not.toBeNull();
  });
});
```

- [ ] **Step 2: Run to see them fail**

Run: `cd web && pnpm test test/groups-ui.test.tsx test/sparkline.test.tsx`
Expected: FAIL, because the modules aren't found.

- [ ] **Step 3: Implement**

Port the presentation from `dashboard/app.py`:
- `_group_html` (2965–2990), `_toggle_html` (2991–3007), `_group_card` (3009–3038);
- `_preview_pane` (3123–3148), `_render_groups` (3150–3165);
- `_signal_rows_html` (2763–2819), `_timeline` (2831–2921);
- `_company_tags` (2923–2933), `_flag_tag` (2935–2940);
- `MAX_COMPANY_TAGS = 3` and `SP_COMPANY_TAGS = 5`.

Behaviour:
- **`GroupList`** (client) reads `param` from `useSearchParams()`. Clicking a card calls `router.push(pathname + "?" + param + "=" + id, { scroll: false })`, and × removes the parameter. It renders `GroupCard`s and, if one is selected, a single `PreviewPane`. The pane keeps its key whatever is selected, so it updates in place.
- **`GroupCard`:**
  - the whole card is a `<button aria-pressed>` labelled `Preview <title>`, or `<title>, showing in preview` when selected;
  - the selected card gets the cobalt left edge;
  - it shows the tile (company logo for patterns, an orange icon tile for themes), title, `ActivityPill`, summary, meta, `Sparkline` and tags (flags, then the first 3 companies, then "+N more").
- **`PreviewPane`:** an `<aside aria-label="<title>">` fixed to the right edge with the resting shadow. It contains:
  - **The pinned header** (`position: sticky`): title row with pill and ×, the × vertically centred on the title row; meta; `<details class="sp-toggle">` ("Show summary" / "Show less") holding the summary and key points; `Sparkline`; flags, the first 5 companies and "+N more" (`gc-tags`), plus a hidden row with every company (`gc-tags-all`).
  - **CSS swaps:** while the toggle is open, the trimmed tag row is swapped for the full one, and the header stops sticking (`:has(.sp-toggle[open])`).
  - **`SignalList`:** members newest first, as `<details name="sp-<id>">` rows. Each row has the date column, the rail, a dot, a title with `data-signal-title`, a two-line body and meta (source logo · category · ring + %). Opened, it shows companies, the full date and the source link.
  - **Hovering a row** sets `data-week` on the pane, which highlights that week's point on the sparkline. This is CSS plus a small `onMouseEnter`, replacing Streamlit's script.
  - **Below 768px** the pane is a bottom sheet at 55vh with the header hidden.
- **`Sparkline`:** ported from `_timeline`. It draws a 2px cobalt line over a 10% fill, uses the shared `scale`, puts a `data-latest` dot on the last point, and labels each end ("10 Jul" … "This week").
- **Pages:**
  - `patterns/page.tsx` uses `buildPatterns` and shows only `active` patterns unless `?quiet=1`. Its caption is "N active patterns of M." / "All N patterns.", with a "Show quieter patterns" link toggling `quiet`.
  - `themes/page.tsx` uses `buildThemes` with the Streamlit caption.
  - The empty states use the Streamlit wording (3171–3175 and the themes message).

**CSS:** translate pattern/theme cards (423–579), the preview pane (580–909, including `.sp-*`, `.sp-toggle` and `.gc-tags-all`), and the card motion parts of 1456–1541, into `groups.module.css` and `pane.module.css`. The `sp-toggle` and `sp-more` class names must not collide; that bug happened in Streamlit.

- [ ] **Step 4: Run the tests and check in the browser**

Run: `cd web && pnpm test && pnpm typecheck`
Expected: all pass.

In `pnpm dev`, side by side with Streamlit on gambling:
- the same patterns and themes appear in the same order;
- opening "Policy and legislation" shows the same 62 signals;
- "Show summary" works, and the header unpins while it's open;
- the × lines up with the title;
- the URL is shareable: paste it into a new tab and the same panel opens.

- [ ] **Step 5: Commit**

```bash
git add web/app/[sector]/patterns web/app/[sector]/themes web/components web/test/groups-ui.test.tsx web/test/sparkline.test.tsx
git commit -m "web: Patterns and Themes with the URL-driven preview panel"
```

---

### Task 14: Insights

**Files:**
- Create: `web/app/[sector]/insights/page.tsx`, `web/components/insights/{StatTiles,WeeklyVolume,HeatMap,Movers,ThemeMomentum,TableView}.tsx`, `web/components/insights/insights.module.css`
- Test: `web/test/insights-ui.test.tsx`

**Interfaces:**
- Consumes: everything in `lib/signals/insights.ts` (Task 8); `buildThemes` (Task 6); `CompanyLogo`, `RelevanceRing` (Task 11).
- Produces: `/[sector]/insights`.

- [ ] **Step 1: Write the failing tests** (`web/test/insights-ui.test.tsx`)

```tsx
import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { StatTiles } from "@/components/insights/StatTiles";
import { HeatMap } from "@/components/insights/HeatMap";
import { WeeklyVolume } from "@/components/insights/WeeklyVolume";
import { ThemeMomentum } from "@/components/insights/ThemeMomentum";

describe("Insights components", () => {
  it("makes the first tile the hero", () => {
    const { container } = render(<StatTiles tiles={[{ label: "A", value: "1", note: null }, { label: "B", value: "2", note: "x" }]} />);
    expect(container.querySelectorAll("[data-hero]")).toHaveLength(1);
  });

  it("weekly volume offers a table and escapes titles", () => {
    render(<WeeklyVolume starts={[new Date("2026-10-05T00:00:00Z")]} counts={[3]} marks={[0]} top={4} markTitles={{ 0: ["<b>Big</b>"] }} />);
    expect(screen.getByText("Show as a table")).toBeInTheDocument();
    expect(document.body.innerHTML).not.toContain("<b>Big</b>");
    expect(screen.getByText(/scoring 75% or more/)).toBeInTheDocument();
  });

  it("heat map lists rows busiest first with totals and the darkest step on the peak", () => {
    const rows = [{ category: "Policy and legislation", counts: [3, 0], total: 3 }, { category: "Insolvency", counts: [1, 0], total: 1 }];
    render(<HeatMap starts={[new Date("2026-09-28T00:00:00Z"), new Date("2026-10-05T00:00:00Z")]} rows={rows} thresholds={[1, 2, 3, 4, 5]} />);
    const labels = screen.getAllByRole("rowheader").map((e) => e.textContent);
    expect(labels).toEqual(["Policy and legislation", "Insolvency"]);
  });

  it("theme momentum states direction in words", () => {
    render(<ThemeMomentum themes={[{ name: "Insolvency", heat: 200, direction: "building", recent: 11, prior: 5 }, { name: "Tax", heat: 50, direction: null }]} />);
    const row = screen.getByText("Insolvency").closest("[data-theme]")!;
    expect(within(row as HTMLElement).getByText("Building")).toBeInTheDocument();
    expect(within(row as HTMLElement).getByText("11 vs 5")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run to see it fail**

Run: `cd web && pnpm test test/insights-ui.test.tsx`
Expected: FAIL, because the modules aren't found.

- [ ] **Step 3: Implement**

Port the HTML of the Insights functions in `dashboard/overview.py` to components:
- `tiles_html` (102–116) → `StatTiles`;
- `weekly_volume_html` (118–205) → `WeeklyVolume`, an SVG with a hover tooltip per week (`.pa-tooltip`) and dots on marked weeks;
- `category_heatmap_html` (245–310) → `HeatMap`, a grid with `heatStep` colours, a tooltip per cell, and row headers as `role="rowheader"`;
- `movers_html` (349–380) → `Movers`, with the mini sparkline from `_mini_spark` 341;
- `themes_html` (400–427) → `ThemeMomentum`.

Every chart gets `<TableView>`: a `<details>` "Show as a table" holding a real `<table>`.

`page.tsx` follows `render_insights` (`dashboard/app.py` 3932–3968): order, headings and captions.

**CSS:** translate the Insights tab styles (1542–1694) into `insights.module.css`.

- [ ] **Step 4: Run the tests and check in the browser**

Run: `cd web && pnpm test && pnpm typecheck`
Expected: all pass.

In `pnpm dev`, put `/gambling/insights` next to Streamlit's Insights. Every tile number, weekly count, heat map cell and mover must match.

- [ ] **Step 5: Commit**

```bash
git add web/app/[sector]/insights web/components/insights web/test/insights-ui.test.tsx
git commit -m "web: Insights tab with tables behind every chart"
```

---

### Task 15: Docker, docs and final check

**Files:**
- Create: `web/Dockerfile`, `web/.dockerignore`, `web/README.md`, `web/.env.example`
- Modify: root `README.md` (add a "Next.js app" section)

- [ ] **Step 1: Write `web/Dockerfile`**, adapted from `~/code/tpa-email-signatures/Dockerfile`

```dockerfile
# syntax=docker/dockerfile:1.7
#
# Sector Signal web: multi-stage Next.js (App Router, standalone output) build,
# following tpa-email-signatures. Build from the repo root so the image can
# carry a snapshot of data/ and config/ for local runs; on stage DATA_BASE_URL
# and CONFIG_BASE_URL point at the live files instead.
ARG NODE_VERSION=20-alpine

FROM registry.pressassociation.io/node:${NODE_VERSION} AS deps
WORKDIR /workspace
RUN corepack enable && corepack prepare pnpm@10.32.0 --activate
COPY web/pnpm-lock.yaml web/package.json ./
RUN pnpm install --frozen-lockfile --ignore-scripts

FROM registry.pressassociation.io/node:${NODE_VERSION} AS builder
WORKDIR /workspace
RUN corepack enable && corepack prepare pnpm@10.32.0 --activate
COPY web/ ./
COPY --from=deps /workspace/node_modules ./node_modules
ENV NEXT_TELEMETRY_DISABLED=1
RUN pnpm build

FROM registry.pressassociation.io/node:${NODE_VERSION} AS runner
RUN addgroup -g 1001 -S nodejs \
  && adduser -u 1001 -S -G nodejs -s /bin/sh nextjs \
  && apk add --no-cache tini
WORKDIR /app
ARG BUILD_TAG=unknown
ENV NODE_ENV=production \
    HOSTNAME=0.0.0.0 \
    PORT=3000 \
    NEXT_TELEMETRY_DISABLED=1 \
    BUILD_TAG=${BUILD_TAG} \
    DATA_DIR=/app/data \
    CONFIG_DIR=/app/config
COPY --from=builder --chown=nextjs:nodejs /workspace/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /workspace/.next/static ./.next/static
COPY --from=builder --chown=nextjs:nodejs /workspace/public ./public
COPY --chown=nextjs:nodejs data ./data
COPY --chown=nextjs:nodejs config ./config
USER 1001
EXPOSE 3000
ENTRYPOINT ["/sbin/tini", "--"]
CMD ["node", "server.js"]
```

If `registry.pressassociation.io` can't be reached locally (it needs the PA VPN), test with `--build-arg` overriding nothing but swapping the `FROM` lines to `node:20-alpine` in a scratch copy. Don't commit that change.

`web/.dockerignore`:
```
node_modules
.next
coverage
test
*.md
.env*
```

- [ ] **Step 2: Write `web/.env.example`**

```bash
# Sign-in (Microsoft Entra). Needed on stage; optional locally.
AUTH_SECRET=                      # openssl rand -base64 32
AUTH_URL=http://localhost:3000
AUTH_MICROSOFT_ENTRA_ID_ID=
AUTH_MICROSOFT_ENTRA_ID_SECRET=
AUTH_MICROSOFT_ENTRA_ID_ISSUER=   # https://login.microsoftonline.com/<tenant id>/v2.0
AUTH_REQUIRED_GROUP_ID=           # staff group; the app registration must emit the groups claim

# Local only: a password sign-in for development. Ignored outside `pnpm dev`.
AUTH_DEV_PASSWORD=local

# Data. Locally the defaults read ../data and ../config.
# DATA_DIR=../data
# CONFIG_DIR=../config
# On stage, or to read the latest from GitHub locally:
# DATA_BASE_URL=https://raw.githubusercontent.com/LAKelly1411/signal-prototype/main/data/
# CONFIG_BASE_URL=https://raw.githubusercontent.com/LAKelly1411/signal-prototype/main/config/

# Source and company logos (optional). Server-side only.
LOGO_DEV_TOKEN=
```

- [ ] **Step 3: Write `web/README.md`** and the root README section

`web/README.md` covers:
- what the app is (link the spec);
- `cp .env.example .env.local`, then `pnpm install`, then `pnpm dev`, then sign in with `AUTH_DEV_PASSWORD`;
- `pnpm test` and `pnpm typecheck`;
- regenerating parity fixtures with `.venv/bin/python scripts/export_parity_fixtures.py`, and why they exist;
- the environment table from `.env.example`;
- the Entra app registration needs: the redirect URI `https://<host>/api/auth/callback/microsoft-entra-id` and the groups claim;
- `docker build -f web/Dockerfile --build-arg BUILD_TAG=local -t sector-signal-web .`, run from the repo root;
- what isn't done yet (the spec's Out of scope).

Root `README.md`: add a "Next.js app (in progress)" section of three lines, pointing to `web/README.md` and saying Streamlit stays live until cutover.

- [ ] **Step 4: Run every check**

```bash
cd web && pnpm test && pnpm typecheck && pnpm build
cd .. && .venv/bin/python -m pytest -q
```

Expected: the Vitest suite passes, there are no type errors, the Next.js build succeeds, and pytest passes as before (452 or more).

- [ ] **Step 5: Final browser check against Streamlit**

Run `pnpm dev` in `web/` (port 3000) and Streamlit (port 8501) side by side, for both sectors, and confirm:
- **Feed:** the default count, and search "commission";
- **Patterns:** the same list and order;
- **Themes:** the same list; one panel opened and closed; "Show summary";
- **Insights:** the tile numbers;
- **Sign-in:** the art moving on the first frame;
- **Phone width (375px):** no sideways scroll, and the pane is a bottom sheet.

Take screenshots of each view. Save them outside the repo and report their paths.

- [ ] **Step 6: Commit**

```bash
git add web/Dockerfile web/.dockerignore web/README.md web/.env.example README.md
git commit -m "web: Dockerfile, environment example and docs"
```
