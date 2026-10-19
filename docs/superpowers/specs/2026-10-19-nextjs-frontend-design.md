# Next.js frontend: design

**Date:** 2026-10-19
**Author:** Renars (frontend), with Claude
**Status:** awaiting review

## Purpose

Replace the Streamlit dashboard with a Next.js app. This is the frontend part
of the agreed Signals platform:

```
n8n workflows ──▶ ingest API (Steven: storage, embeddings, search,
Python pipeline ─┘                 patterns and themes) ──▶ Next.js frontend (Renars)
```

Steven's API doesn't exist yet, so v1 reads the JSON files the Python pipeline
already writes. The Streamlit app, the pipeline and the n8n workflows keep
running unchanged until cutover.

**Done means:** `pnpm dev` in `web/` shows gambling and fintech in Feed,
Patterns, Themes and Insights after signing in locally. Its numbers match
Streamlit's, and every test passes: the new Vitest suite and the untouched
Python suite.

## Decisions already made

| Decision | Choice |
|---|---|
| Where data comes from in v1 | The existing JSON files, through one data module that can be swapped for Steven's API later |
| v1 scope | The core views only (below). No marketplace, no "New sector", no "Add to watchlist" |
| Sign-in | Microsoft Entra via Auth.js, plus a dev-only password provider until the Entra app registration exists |
| Repo layout | A new `web/` folder alongside the Python code. Nothing existing moves |
| Stack | Matches PA's other Next.js apps (`tpa-email-signatures`, `aie-ai-gateway`): Next.js 16 App Router, React 19.2, TypeScript, pnpm, Node 20, `next-auth` 5 (beta), Vitest 4, `output: 'standalone'` |

## 1. Structure

```
web/
├── app/
│   ├── layout.tsx                 fonts, pa-brand.css, metadata
│   ├── page.tsx                   redirects to the first sector's feed
│   ├── login/page.tsx             sign-in page (cobalt hero + timeline art)
│   ├── [sector]/
│   │   ├── layout.tsx             header: lockup, sector menu, status strip, tabs
│   │   ├── feed/page.tsx
│   │   ├── patterns/page.tsx
│   │   ├── themes/page.tsx
│   │   └── insights/page.tsx
│   └── api/
│       ├── health/route.ts        { ok, tag } – tag is the build tag
│       ├── ready/route.ts         200 once the data source answers
│       └── auth/[...nextauth]/route.ts
├── auth.ts                        Auth.js config (Entra + dev provider)
├── middleware.ts                  protects everything except /login, /api/health, /api/ready, /api/auth
├── components/                    see §3
├── lib/
│   ├── data/
│   │   ├── source.ts              the DataSource interface
│   │   ├── files.ts               FileDataSource: local folder or base URL
│   │   └── types.ts               Signal, SectorEntry, RunStatus, SectorRules
│   └── signals/                   logic ported from Python (see §2)
├── styles/
│   ├── pa-brand.css               copied from docs/pa-design-kit/
│   └── *.module.css
├── public/pa-logo.svg
├── test/                          Vitest; parity fixtures generated from Python
├── Dockerfile                     copied from tpa-email-signatures, adjusted
├── next.config.ts                 output: 'standalone'
├── package.json, pnpm-lock.yaml, tsconfig.json, vitest.config.ts, .nvmrc (20)
└── README.md                      how to run, environment variables
```

The repo root is untouched apart from:
- `web/` itself;
- `.gitignore` entries for `web/node_modules` and `web/.next`;
- `scripts/export_parity_fixtures.py` (§5);
- a short "Next.js app" section in the root `README.md`.

## 2. Data

### The DataSource interface

The only code that knows where data lives. Pages and components never read
files or URLs themselves.

```ts
interface DataSource {
  listSectors(): Promise<SectorEntry[]>;          // data/sectors.json
  getSignals(slug: string): Promise<Signal[]>;    // data/<slug>/signals.json
  getRunStatus(slug: string): Promise<RunStatus | null>; // data/<slug>/run_status.json
  getSectorRules(slug: string): Promise<SectorRules>;    // config/sectors/<slug>.yaml (+ .user.yaml)
}
```

**`FileDataSource`** implements it in one of two modes, chosen by environment:

| Variable | Mode | Use |
|---|---|---|
| `DATA_DIR` (default `../data`) and `CONFIG_DIR` (default `../config`) | reads from disk | local development |
| `DATA_BASE_URL` and `CONFIG_BASE_URL` | fetches over HTTP, like Streamlit does today | stage, until Steven's API exists |

- **Caching:** responses are cached for 5 minutes (Next.js `revalidate: 300`).
  The pipeline runs about three times a day.
- **Errors:** a missing or invalid file throws a typed `DataError`. A page
  turns it into the same calm empty states Streamlit shows today ("No signals
  yet", "This sector is being set up").
- **Slugs** are validated against `^[a-z0-9-]+$` before any path or URL is
  built, as in `dashboard/data.py`.
- **Steven's API later:** a second implementation, `ApiDataSource`, replaces
  `FileDataSource`. Pages don't change. Its shape is Steven's to define; this
  interface is only what the frontend needs from it.

### Types

Typed from the real JSON, not guessed:

- **`Signal`:**
  - item fields: `id`, `source`, `source_url`, `title`, `published_at`, …;
  - per-item AI fields: `newsworthiness_score`, `why_it_matters`,
    `canonical_category`, `canonical_entities`, …;
  - group fields (all optional): `cluster_*`, `theme_*`.
- **`SectorEntry`:** `sectors.json`.
- **`RunStatus`:** `run_status.json`.
- **`SectorRules`:** the YAML fields the dashboard uses (categories,
  companies, regulators and excluded bodies, used for filters and entity
  icons).

Parsing goes through `zod` schemas, so a format change in the pipeline fails
loudly in one place.

### Logic ported from Python (`lib/signals/`)

Ported function for function, with the same names in camelCase, so the two
can be compared.

| TypeScript module | From | What |
|---|---|---|
| `tiers.ts` | `app.py`: `SCORE_TIERS`, `HEAT_TIERS`, `THEME_HEAT_TIERS`, `score_tier`, `heat_tier`, `theme_heat_tier`, `ACTIVITY_LABELS` | score and activity tiers |
| `groups.ts` | `app.py`: `group_by_cluster`, `_build_cluster_info`, `_cluster_verdict`, `Group` building in `render_patterns` / `render_themes`, `_date_span` | patterns and themes as cards |
| `filters.ts` | `app.py`: `_filter_options`, `_criteria`, `_filter_signals`, `apply_filters`, sort | feed filtering and sorting |
| `time.ts` | `app.py`: `_weekly_counts`, `_week_index`, `_week_range`, `_nice_scale`, `_relative_time`, `_full_date`, `_date_bucket`, `_humanise_age` | weeks, scales, dates |
| `entities.ts` | `app.py`: `_is_person`, `_entity_icon`, `_source_name`, `_initials`; `data.py`: `plain_name`, `display_name` | names and icons |
| `insights.ts` | `overview.py` (all of it) | KPI tiles, weekly volume, heat map, companies, theme momentum |

Python stays the reference until cutover. If the two disagree, Python is right
and the port gets fixed.

## 3. Pages and components

The same views and behaviour as the Streamlit app on `login-page`, in the PA
design kit (`docs/pa-design-kit/`). Pages are server components. Only the
parts that respond to the user are client components.

| Page | Contents |
|---|---|
| **Header** (all pages) | lockup, sector menu (`<details>` menu linking to `/<slug>/<tab>`), status strip ("Updated 2 hours ago · 8/9 sources", with "Which sources returned nothing?"), tabs as links |
| **Feed** | signal cards (source logo, title, why it matters, tags, relevance ring, source link) grouped by date bucket; sidebar filters (search, sources, categories, companies) and sort. Filters live in the URL query, so a filtered view can be shared |
| **Patterns / Themes** | card list (selected card has the cobalt edge) and the preview panel. The selection lives in the URL (`?pattern=<id>` / `?theme=<id>`), so a panel can be linked and survives reload |
| **Preview panel** | pinned header (title, pill, ×, meta, sparkline, first 5 tags), "Show summary" toggle that expands the header and unpins it; dated signals list with the rail, hover tile and expand in place (`<details name>`); bottom sheet below 768px |
| **Insights** | KPI tiles, weekly volume, category × week heat map, companies by relevance, theme momentum; every chart has hover values and "Show as a table" |
| **Sign-in** | the cobalt hero with the scrolling timeline and heat map art, already moving on the first frame; "Sign in with Microsoft" (plus the dev password form in development only) |

**Components** (`components/`):
- `SignalCard`, `GroupCard`, `PreviewPane`, `SignalList`, `Tag`, `RelevanceRing`, `ActivityPill`;
- `Sparkline`, `WeeklyVolume`, `HeatMap`, `Movers`, `ThemeMomentum`, `StatTile`;
- `SectorMenu`, `StatusStrip`, `Masthead`, `LoginArt`.

Charts stay hand-written SVG as in Python. No chart library.

**Behaviour carried over exactly:**
- the hover dot on the rail lights up the matching week on the sparkline;
- the × is centred on the title row;
- open, the panel header stops being pinned;
- reduced motion stops loops;
- the score is shown as Streamlit shows it today (a decision for the external
  version, not this one).

**Source logos:** the `logo.dev` token moves server-side. Logos are fetched
through a small `/api/logo/[domain]` route that caches them, so the token
never reaches the browser. If no token is set, initials are shown, as today.

**Fonts:** load from the PA font CDN with the Archivo and Oswald stand-ins, as
in `pa-brand.css`. localhost is allowlisted, so local runs show Press Sans.

## 4. Sign-in

- **Auth.js** (`next-auth` 5) with the Microsoft Entra ID provider, set up as in
  `aie-ai-gateway`:
  - `AUTH_MICROSOFT_ENTRA_ID_ID`, `AUTH_MICROSOFT_ENTRA_ID_SECRET`,
    `AUTH_MICROSOFT_ENTRA_ID_ISSUER`, `AUTH_SECRET`, `AUTH_URL`;
  - `AUTH_REQUIRED_GROUP_ID` limits access to a staff group.
- **Fails closed:** if Entra isn't configured, nobody gets in except through
  the dev provider below, and a production build never does.
- **Dev provider:** a username-free password form, enabled only when both
  `NODE_ENV === "development"` and `AUTH_DEV_PASSWORD` are set. It's never
  added to the provider list otherwise, and a test checks that.
- **`middleware.ts`** redirects anyone not signed in to `/login`, keeping the
  page they asked for.
- Session in a JWT cookie (Auth.js default). There's no database.

**Needed from IT before stage:** an Entra app registration with the redirect
URI `https://<stage host>/api/auth/callback/microsoft-entra-id`, plus the staff
group ID. Local development doesn't need it.

## 5. Testing

- **Parity with Python.** `scripts/export_parity_fixtures.py` runs the Python
  logic on the committed JSON and writes the expected results to
  `web/test/fixtures/parity/*.json`. Vitest checks the TypeScript port gives
  the same results. It covers:
  - tiers for a range of scores and heats;
  - pattern and theme groups for both sectors;
  - feed filter results for a few criteria;
  - weekly counts and scales;
  - every Insights number.

  Fixtures are regenerated with one command when the Python logic changes.
- **Unit tests:** data source (disk mode and URL mode with a mocked `fetch`,
  slug validation, error handling), schemas, and the auth provider list (the
  dev provider is absent outside development).
- **Component tests** (Vitest + Testing Library):
  - the panel opens from a card and closes with ×;
  - "Show summary" toggles;
  - filters narrow the feed;
  - the selected card has the selected state.
- **Visual check** in the browser, side by side with Streamlit, before calling
  it done.
- **The Python suite** (`pytest`) must stay green. Nothing in `src/` or
  `dashboard/` changes.

## 6. Ready to deploy, not deployed

- **`web/Dockerfile`:** copied from `tpa-email-signatures`. It has three
  stages and a non-root user 1001, uses tini, and takes `BUILD_TAG` as a
  build arg, which `/api/health` reports.
- **`/api/ready`:** returns 200 once `listSectors()` succeeds.
- **Environment variables** are documented in `web/README.md`.

Not in this spec: the Argo chart, GitHub Actions workflows and secrets. They
wait until the repo's home (org repo or this one) is settled. That's a
separate, small spec copying `tpa-email-signatures`.

## Out of scope

- Marketplace of verified sources (waits for the source list).
- "New sector", Claude drafting, "Add to watchlist" (need Steven's backend to save).
- `ApiDataSource` (needs Steven's read API).
- Argo, CI, secrets, stage deployment.
- Removing Streamlit (one commit at cutover).
- Any change to the Python pipeline or the n8n workflows.

## Risks

| Risk | Mitigation |
|---|---|
| The port drifts from Streamlit's behaviour | Python-generated fixtures are the oracle; the side-by-side visual check |
| `next-auth` 5 is still beta | Same version range as `aie-ai-gateway` and `hydrogen-os`, which run it in production |
| Local `data/` is stale (it's whatever branch is checked out) | `DATA_BASE_URL` can point at `main` on GitHub in development too; the README says how |
| The repo is public | Unchanged by this work; flagged separately (make it private) |
