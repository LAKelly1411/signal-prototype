# Dashboard sector switcher (stage 2 of multi-sector Sector Signal)

**Date:** 2026-10-08
**Status:** Draft for review
**Author:** Renars Fazlutdinovs (with Claude)
**Branch:** `sector-switcher` (from `pa-reskin`, which includes stage 1)
**Builds on:** `docs/superpowers/specs/2026-10-08-sector-aware-pipeline-design.md`

## Context and intent

Stage 1 made "sector" first-class in the pipeline:
- each sector has a config at `config/sectors/<slug>.yaml`;
- each sector's data lives in `data/<slug>/`;
- `data/sectors.json` is the index of sectors.

The dashboard still reads one file, the gambling compatibility copy at `data/signals.json`.

Stage 2 makes the dashboard multi-sector:

- The header's "Gambling & gaming" kicker and "Sector Signal" title become one **sector switcher**.
- The dashboard loads the selected sector's data.
- Everything sector-specific follows the selected sector: filters, exclusions, theme heat and the watchlist file.
- A second real sector, **Fintech & payments**, is added by hand so the switcher is proven end to end before stage 3 automates sector creation.

Success means:
- you can switch sectors without layout shift;
- gambling looks and behaves exactly as today;
- a sector that is setting up, or whose last run failed, shows a friendly state, not an error;
- a link with `?sector=<slug>` opens that sector.

## Scope

**In:**
- the switcher;
- per-sector data loading over GitHub raw, with a temporary fallback;
- sector-aware dashboard internals;
- states for "setting up" and "last run failed";
- `config/sectors/fintech.yaml`;
- fintech logos;
- tests.

**Deferred to a follow-up:** removing the pipeline's compatibility copy, the old top-level data files and the fallback (see §6).

**Out (stage 3):**
- creating sectors;
- the premium upsell and demo unlock;
- Claude drafting;
- triggering runs from the dashboard.

The switcher shows a disabled "+ New sector · Premium" row as the place stage 3 plugs into.

## Design

### 1. Header switcher

The kicker becomes a fixed product label, "SECTOR SIGNAL". The title becomes the trigger: the sector's name in the existing condensed title style, followed by a small chevron. The trigger is a `st.popover` whose menu lists:
- every sector in `data/sectors.json`, in index order (sorted by slug, with gambling first if present);
- for each sector, its name plus a muted right-aligned note: the live signal count, "Setting up…" or "Update failed";
- a tick against the selected sector;
- a divider;
- the disabled "+ New sector" row with a "Premium" tag.

```
 SECTOR SIGNAL
 Gambling & gaming  ⌄
        ┌──────────────────────────────────┐
        │ ✓ Gambling & gaming         336  │
        │   Fintech & payments  Setting up…│
        │ ──────────────────────────────── │
        │ + New sector             PREMIUM │
        └──────────────────────────────────┘
```

Behaviour:
- **Styling.** The trigger and menu reuse the Sort popover's approach. Page JS sets the menu's width and closes the menu after a choice. The trigger's height doesn't change between sectors, so nothing below it moves.
- **Choosing a sector:**
  - sets `st.query_params["sector"]`;
  - clears the per-sector filter state;
  - reruns.
- **`?sector=` on load.** An unknown or missing value falls back to gambling if it is present, otherwise the first sector.
- **Browser title.** The page title stays "Sector Signal".

### 2. Data loading

- **The secret.** One new secret, `DATA_BASE_URL`, holds the GitHub raw prefix for the repo's `data/` folder, for example `https://raw.githubusercontent.com/<owner>/<repo>/main/data/`.
- **Loader functions.** Each is `st.cache_data(ttl=600)`:
  - `load_index() -> list[dict]` reads `sectors.json`;
  - `load_signals(slug) -> list[dict]` reads `<slug>/signals.json`;
  - `load_run_status(slug) -> dict | None` reads `<slug>/run_status.json`.

  Only the selected sector's files are fetched.
- **Fallback, for one release.** If `DATA_BASE_URL` is unset, or `sectors.json` returns 404, the dashboard behaves as today:
  - it shows a single implied gambling sector read from `DATA_RAW_URL` / `RUN_STATUS_RAW_URL`;
  - the switcher lists just gambling.

  This keeps the deployed app working from merge until main has run the pipeline once.
- **Failures.** A network failure or bad JSON for the index or the signals shows the existing error treatment for that view. It doesn't crash the page.
- **The data is read-only.** Data loading lives in a small module, `dashboard/data.py`, so it can be unit tested without Streamlit rendering.

### 3. Sector-aware internals

- **Loading the sector.** `load_sector(slug)` reads the repo's own `config/sectors/<slug>.yaml`, which is deployed with the app. Its result is passed to:
  - `is_excluded(name, sector)`;
  - `compute_theme_heat(members, sector=sector)`;
  - every `signal_entities` / alias-map use that has a sector form.

  If the config is missing (a sector in the index with no config in this deploy), the dashboard falls back to gambling's rules for exclusions and shows the data.
- **Filter state.** Filter widget keys are prefixed with the slug (`f_<slug>_src_<source>`, and so on), so each sector keeps its own filter state and switching never shows a stale filter. "Clear all" clears only the current sector's keys.
- **Watchlist.** The dialog writes to `config/sectors/<slug>.user.yaml`, using the `operators` key as today, and the copy names the selected sector.
- **Logos and icons.** The curated `COMPANY_DOMAINS` in `dashboard/brand.py` gains the fintech companies. Unknown categories already fall back to the generic tag icon.

### 4. States

These replace the tab area. The header and switcher stay.

| Index status / data | Shown |
|---|---|
| `setting_up`, no signals file | The grey empty block: "We're gathering the first signals for <Name>. This usually takes under an hour." |
| `error`, signals exist | A thin notice above the tabs: "The last update didn't finish. Showing the latest data we have." Then the normal tabs. |
| `error`, no signals | The grey empty block: "We couldn't load <Name> yet. We'll try again on the next scheduled update." |
| `ready` | Normal tabs. |

### 5. Fintech & payments sector (`config/sectors/fintech.yaml`)

It's hand-written and reviewed like gambling's, and validated by `load_sector`.

- **Prompt wording.** All nine fields, written for a B2B fintech and payments newsroom (for example `company_word: firm`, and `coverage: the UK fintech and payments sector`).
- **Keywords.** fintech, payments, e-money, open banking, buy now pay later, neobank.
- **Companies.** Six to eight UK entities, each with a company number that is quoted and verified against Companies House, never guessed: Monzo Bank, Revolut Ltd, Starling Bank, Wise Payments, Klarna's UK entity, Checkout Ltd, ClearBank and similar.
- **Tickers.** Only clearly fintech LSE listings (for example WISE, PAY).
- **Categories.**
  - **Authorisation and permissions:** FCA authorisation, variation of permission, registration.
  - **Consumer Duty and redress:** Consumer Duty, redress, FOS complaints.
  - **Fraud and APP scams:** APP fraud, reimbursement, scams.

  Each sits `before` a named core rule. They must not change gambling: the stage 1 equivalence tests still pass.
- **Excluded bodies.** prudential regulation authority, pra, payment systems regulator, psr, financial ombudsman service, bank of england, uk finance. The FCA is already shared.
- **Sources.** `companies_house`, `gazette`, `dcms` with `organisation: hm-treasury`, `parliament`, `asa`, `insolvency_service`, `lse_rns`. Not `gambling_commission` or `bgc`.
- **First run.** A `sector=fintech` dispatch of the GitHub workflow, which makes paid API calls. It's triggered only with the author's go-ahead, after the branch is pushed.

### 6. The compatibility copy stays (removal is a follow-up)

The pipeline keeps writing `data/signals.json` and `data/run_status.json` after each gambling run during this stage. If it stopped, the deployed app, which reads those files until `DATA_BASE_URL` is set, would freeze between merge and the secret change.

**Order on deploy (documented in the README):**
1. Merge.
2. Let the pipeline run once on main. This creates `data/gambling/` and `data/sectors.json` through stage 1's automatic migration.
3. Set `DATA_BASE_URL` in Streamlit Cloud. The switcher goes live.

**Follow-up, once that's confirmed:** remove `write_compat_copy`, the old top-level data files, the old secrets and the fallback in §2.

## Testing

- **`dashboard/data.py` unit tests,** with mocked `requests`:
  - the index loads;
  - a sector's signals and status load;
  - the fallback triggers when `DATA_BASE_URL` is unset or the index returns 404;
  - bad JSON is handled.
- **Fintech config:** `load_sector("fintech")` validates. Every company number is a quoted string matching `^[0-9A-Z]{8}$`. The stage 1 equivalence tests stay green.
- **AppTest,** with HTTP patched to serve fixture data for two sectors:
  - it renders gambling by default;
  - `?sector=fintech` renders fintech;
  - a `setting_up` sector shows the setting-up block;
  - an unknown slug falls back to gambling;
  - with the fallback (no index), it renders as today.
- **Manual browser check** against the mockup:
  - no layout shift when switching;
  - the menu width matches the trigger, as Sort does;
  - the menu closes after a choice.

## Risks

- **Deploy ordering.** Without `DATA_BASE_URL`, the app stays on the fallback, which is safe. With it set but before main's first sector-aware run, the index returns 404, so it also falls back. Both orders are safe.
- **Stale configs.** Fintech prompt wording and categories are new and untested against real data. The first run should be reviewed (counts, clusters, themes) before anyone relies on them.
- **Claude cost.** Claude cost grows per sector. Fintech roughly doubles daily scoring calls at first, then levels off to new items only.
- **Company numbers.** These must be verified. A wrong number silently collects another company's filings.
