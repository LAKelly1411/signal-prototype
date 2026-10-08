# Sector-aware pipeline (stage 1 of multi-sector Sector Signal)

**Date:** 2026-10-08
**Status:** Draft for review
**Author:** Renars Fazlutdinovs (with Claude)
**Branch:** `sectors` (from `pa-reskin`)

## Context and intent

Sector Signal today covers one sector, UK gambling. The goal is to make it a
multi-sector product.

- The dashboard header becomes a sector switcher.
- Each sector is a **real** sector: its own sources, keywords, companies,
  categories and Claude scoring. It is not a filtered view of the gambling data.
- Creating a sector is self-service but premium. It will be a paid add-on, and
  the purchase is simulated for now.
- Claude drafts a new sector's configuration from a name and a one-line
  description, and the user reviews it before saving.
- Saving a new sector triggers a pipeline run straight away.

The work is staged. Each stage has its own spec, plan and implementation.

1. **This spec: a sector-aware pipeline.** "Sector" becomes a first-class concept
   in the pipeline. Gambling is migrated to a sector config and its output does
   not change.
2. **Dashboard sector switcher.** The header's kicker and title become one
   sector control, and the dashboard loads each sector's data.
3. **Premium sector creation.** An upsell dialog with a demo unlock, a
   Claude-drafted config the user reviews, saving via GitHub, triggering a run,
   and a "setting up" state.

This stage changes the repo owner's (`lakelly1411`) pipeline substantially. The
owner should review before anything merges. Nothing is pushed without the
author's go-ahead.

### Success criteria

- `gambling.yaml` drives the pipeline to **identical** outputs to today's code
  for the same inputs. That covers the prompts sent to Claude, the categories,
  the exclusions, the clusters and the themes. It is proven by an equivalence
  test recorded before the refactor.
- A second sector can be added by dropping in a config file. It runs alongside
  gambling with no pipeline code changes, and its data stays separate.
- The deployed dashboard keeps working unchanged throughout. It reads the old
  paths through a compatibility copy until stage 2.

### Out of scope

- Dashboard changes, apart from keeping one import working (stage 2).
- Sector creation, the premium flow and Claude drafting (stage 3).
- New hand-built scrapers for other sectors' regulators.
- Per-sector heat thresholds. They stay shared, and the one value tuned on
  gambling data is noted.
- Removing the compatibility copy at the old data paths. That is a follow-up
  once stage 2 ships.

## 1. Sector config

There is one file per sector: `config/sectors/<slug>.yaml`. User additions live
in a sibling file, `config/sectors/<slug>.user.yaml`. The dashboard's watchlist
form will write to it in stage 2, so the app never edits the hand-curated file.

```yaml
slug: gambling                      # [a-z0-9-]+, must match the filename
name: Gambling & gaming
brief: >                            # the newsroom context in every Claude prompt
  A B2B newsroom covering the UK gambling and gaming sector: operators,
  suppliers, affiliates and the regulators around them.
keywords: [gambling, betting, bookmaker, casino, bingo, gaming]
companies:                          # was config/watchlist.yaml "operators"
  - name: bet365 Group Limited
    company_number: "04241161"
    aliases: [bet365, Hillside]
    notes: "…"
tickers: {ENT: Entain, FLTR: Flutter Entertainment, EVOK: evoke, RNK: Rank Group}
categories:                         # sector-specific additions to the core set
  - name: Illegal gambling
    patterns: ["illegal", "black market", "unlicensed", "untaxed"]
  - name: Player protection
    patterns: ["safer gambling", "problem gambling", "self.?exclu", "affordability", "harm"]
  # … the remaining gambling categories and rules from src/categories.py
signal_type_fallback:               # optional overrides of the core fallback
  regulatory: Licence action
excluded_bodies: [Gambling Commission, UKGC, BGC, Betting and Gaming Council,
                  DCMS, Illegal Gambling Taskforce, ASA, CAP, BHA, …]
sources:                            # which collectors run, with their settings
  gambling_commission: {listing_pages: [ … from sources.yaml … ]}
  bgc: {pages: 2}
  gazette: {}                       # search terms = keywords + company names
  parliament: {}
  insolvency_service: {}
  lse_rns: {skip_titles: [ … ]}
  companies_house: {lookback_days: …, categories: [ … ]}
  dcms: {organisation: department-for-culture-media-and-sport}
  asa: {}
```

### Rules

- **Shared defaults stay in code** and apply to every sector:
  - Generic UK institutions are always excluded: HMRC, HM Treasury, Companies
    House, the Gazette, the Insolvency Service, Parliament, Government, the Home
    Office, the Cabinet Office and similar. A sector's `excluded_bodies` adds to
    this list.
  - The **core categories**, with their matching rules, stay in code:
    Insolvency, Enforcement action, Corporate filing, Consultation, Policy and
    legislation, Shareholding disclosure, Board and director changes, Financial
    results, Merger and acquisition, Director disqualification, AML and
    compliance failures, Tax and levy, and Other. The generic sources and the
    signal-type fallback rely on them. A sector's `categories` adds to them.
  - The **gambling-only categories**, with their rules, move to
    `gambling.yaml`: Illegal gambling, Player protection, Licence action and
    Advertising ruling. They depend on gambling-specific concepts or bodies,
    such as the ASA.
  - Rule priority is preserved: sector rules are inserted at the same
    positions their gambling rules hold in today's `_RULES` list. The
    equivalence test checks this.
  - The core signal-type fallback: insolvency → Insolvency, enforcement →
    Enforcement action, consultation → Consultation, corporate_filing →
    Corporate filing, policy → Policy and legislation, regulatory → Other.
    Gambling overrides `regulatory` to Licence action.
  - `user_agent` and the other collector plumbing defaults.
- Unknown keys under `sources:` are an error. A collector listed under
  `sources:` is enabled, and an absent one is off.
- The hand-built collectors (`gambling_commission`, `bgc`) are only meaningful
  for gambling. Nothing stops them being listed in another sector, but stage 3's
  drafting will only offer the generic ones.
- **Validation runs on load.** It checks:
  - the slug matches the filename;
  - the required fields are present (`slug`, `name`, `brief`, `sources`);
  - category patterns compile;
  - no source keys are unknown;
  - company numbers are strings.

  A validation failure is a per-sector error with a message naming the file and
  the field.

## 2. Running and data

- `python -m src.pipeline` runs **every** sector in `config/sectors/`, in slug
  order.
- `python -m src.pipeline --sector <slug>` runs one sector.
- An unknown slug exits non-zero with "No sector config named '<slug>'
  (available: …)".
- **Each sector run is self-contained.** Each one has its own:
  - config and collectors;
  - collected items;
  - scoring with its brief and categories;
  - clustering with its excluded bodies;
  - themes and summaries;
  - store, archive and run status.
- **Isolation:** one sector's failure (bad config, an exception) is caught and
  recorded in that sector's run status and the index. The remaining sectors
  still run. The process exits non-zero at the end if any sector failed, so the
  workflow's existing failure alert fires.

### Data layout

```
data/<slug>/signals.json
data/<slug>/run_status.json
data/<slug>/archive/signals-YYYY.json
data/<slug>/archive/ids.json
data/sectors.json
```

`data/sectors.json` is the sector index. Each entry has `slug`, `name`,
`brief`, `created_at`, `last_run_at` and `status` (`setting_up` | `ready` |
`error`), plus `error` when failed and the `signal_count`. It is written after
each sector's run. A sector config with no data yet appears as `setting_up`.

### Signal changes

- Signals gain `sector: <slug>`.
- Ids stay `sha256(source:stable_key)`. Stores are per-sector, so the same item
  appearing in two sectors is intentional and harmless.
- Theme ids (the category name) only need to be unique within a sector.

### Compatibility copy

After the gambling run, the pipeline also writes `data/signals.json` and
`data/run_status.json` exactly as today. The deployed dashboard reads those over
GitHub raw. The copy is removed in a follow-up once stage 2 reads
`data/gambling/`.

### Workflow (.github/workflows/pipeline.yml)

- `workflow_dispatch` gains an optional input, `sector` (default: empty, meaning
  all sectors).
- n8n keeps dispatching with no input.
- Stage 3 dispatches with `sector=<new-slug>`.
- A `concurrency` group serialises runs so two never commit at once. Runs queue;
  they don't cancel.
- The commit step still stages `data/`. The commit message names the sector or
  sectors run.

### Cost

Every sector run makes its own Claude calls: scoring per new signal, plus
cluster and theme summaries. Adding sectors adds cost roughly in proportion to
their signal volume.

## 3. Code changes

| Module | Change |
|---|---|
| `src/sectors.py` (new) | `Sector` dataclass, `load_sector(slug)`, `list_sectors()`, validation, merging the `.user.yaml` additions, `write_index()`. Holds the shared institution list and core categories. |
| `src/score.py` | `SYSTEM_PROMPT`, `CLUSTER_SYSTEM_PROMPT` and `THEME_SYSTEM_PROMPT` become templates taking `sector.brief` and the sector's category list. Gambling's brief is chosen so the rendered gambling prompts are **byte-identical** to today's. Summary cache versions keep hashing the rendered prompt text, so they come out per-sector naturally. Model selection stays in score.py, unchanged. |
| `src/categories.py` | `canonical_category(category, title, signal_type, sector)` matches against core plus sector categories and rules, in the same priority order as today. `category_of(signal, sector)`. The gambling categories and rules move to `gambling.yaml`. Module-level names stay for the core categories. |
| `src/cluster.py` | `is_excluded(name, sector=None)` checks the shared list plus the sector's bodies. `assign_clusters` and `assign_themes` take the sector. `sector=None` keeps today's gambling list for callers that haven't migrated (the dashboard, in stage 1 only). |
| `src/pipeline.py` | A `COLLECTORS` registry (source key → builder taking the sector and that source's settings) replaces the if-chain. Adds `run_sector(sector)`, `run_all()` and a `--sector` argument parser. Watchlist loading moves to `Sector.companies`. Writes the compatibility copy after gambling. |
| `src/store.py` | No logic change. Callers pass per-sector paths. |
| `src/collectors/dcms.py` | The department slug comes from settings (`organisation`). |
| Collector docstrings | Gambling wording is generalised. No behaviour change. |
| `scripts/backfill_canonical_entities.py` | Gains `--sector` (default `gambling`) and uses the sector's paths. |
| `scripts/migrate_to_sectors.py` (new) | Moves `data/signals.json`, the archive and the run status into `data/gambling/` and adds `sector: gambling`, without re-scoring. It is idempotent, has `--dry-run` and writes the index. |
| `config/sources.yaml`, `config/watchlist.yaml`, `config/user_watchlist.yaml` | Folded into `config/sectors/gambling.yaml` and `gambling.user.yaml`. The old files are deleted in the same change. |
| `dashboard/app.py` | No change in stage 1. Its `is_excluded` calls rely on the `sector=None` gambling default. |

## 4. Error handling

| Situation | Behaviour |
|---|---|
| Invalid sector config | That sector is skipped. The error (file, field) goes to its `run_status.json` and the index (`status: error`). The other sectors run, and the process exits non-zero. |
| A collector raises | Same as today: recorded per source in run status, and the sector continues. |
| A sector returns no items | `ready` with zero signals. Not an error. |
| Unknown `--sector` | Exits non-zero with the available slugs. No sectors run. |
| Migration script run twice | No-op: it detects `data/gambling/` and an existing `sector` field. |

## 5. Testing

- **Equivalence test, written first against today's code.** On a fixed set of
  raw items and signals, with Claude faked by a deterministic stub that records
  its inputs, it captures:
  - the exact prompt text sent for scoring and for cluster and theme summaries;
  - `canonical_category` for every signal;
  - `is_excluded` for every entity;
  - cluster and theme assignments;
  - the run-status shape.

  The refactored pipeline, run with `gambling.yaml`, must reproduce all of it
  exactly.
- **Existing tests:**
  - `test_categories`, `test_cluster`, `test_themes` and `test_lse_rns` are
    updated to load the gambling sector, not module constants. Their
    assertions are kept.
  - `test_normalise_and_score` keeps its id test unchanged, because ids don't
    change.
- **New tests:**
  - config validation: a missing field, a slug/filename mismatch, a bad regex,
    an unknown source key;
  - core categories are always present;
  - `.user.yaml` additions are merged;
  - two sectors in one run write separate stores and don't touch each other's
    data;
  - one sector failing still runs the rest and exits non-zero;
  - `--sector` selects one sector, and an unknown slug fails;
  - the index contents and statuses;
  - the compatibility copy matches `data/gambling/`;
  - the migration on a copy of today's data preserves counts, ids and scores,
    adds `sector`, and is idempotent.
- **Manual check:** one real run (with real Claude and Companies House keys)
  of `--sector gambling` on a branch. Compare signal counts, clusters and
  themes with the latest production run. Confirm the deployed dashboard is
  unaffected.

## Risks

- **Prompt drift:** any change to the gambling prompt text changes scores. This
  is mitigated by the byte-identical equivalence test.
- **Owner's codebase:** this is a broad refactor of `lakelly1411`'s pipeline.
  Agree it with them before merging.
- **The compatibility copy must be removed later.** The follow-up is tracked in
  stage 2's spec.
- **Cost growth** with each new sector (see section 2).
