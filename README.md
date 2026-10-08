# signal-prototype

Gambling/gaming sector signal monitoring prototype.

## Setup

```
pip install -r requirements.txt
cp .env.example .env
python -m src.pipeline                 # every sector
python -m src.pipeline --sector gambling
```

The move from the old single-sector layout (`data/signals.json`,
`data/archive/`) into `data/gambling/` happens automatically: the first
pipeline run that includes gambling after this change is merged migrates the
data it finds, then runs as normal. To migrate a local checkout by hand,
`python -m scripts.migrate_to_sectors` (add `--dry-run` to preview) does the
same move; it is safe to re-run, and warns rather than changes anything if
`data/gambling/` is older than `data/signals.json`.

Dashboard: `dashboard/app.py` (Streamlit).

## Tests

```
pip install -r requirements-dev.txt
python -m pytest tests/ -q
```

## Data files

Each sector writes under `data/<slug>/`, all committed:

- `data/<slug>/signals.json` — the live store, holding the last
  `RETENTION_DAYS` (120) of signals.
- `data/<slug>/archive/signals-YYYY.json` — signals past the retention window,
  split by published year. Append-only.
- `data/<slug>/archive/ids.json` — ids of everything archived, so a source that
  still lists an old item can't cause it to be re-ingested and re-scored.
- `data/<slug>/run_status.json` — what the last run did, per collector.
  Drives the dashboard's freshness strip.
- `data/sectors.json` — the index of sectors.

`data/signals.json` and `data/run_status.json` are a gambling compatibility
copy, kept for the deployed dashboard until stage 2.

## Sectors

One file per sector in `config/sectors/<slug>.yaml`;
`config/sectors/gambling.yaml` is the worked example. Additions live beside a
sector's config in `config/sectors/<slug>.user.yaml`; the dashboard's
watchlist form writes to the file of the sector it is showing. Each sector's
run makes its own Claude calls, so every sector adds to the cost of a run.

Current sectors:

- **Gambling & gaming** (`gambling`).
- **Fintech & payments** (`fintech`). Run it with
  `python -m src.pipeline --sector fintech`, or dispatch the Pipeline workflow
  with `sector` set to `fintech`. Its first run scores everything it collects,
  so it makes paid Claude calls.

The dashboard lists the sectors in `data/sectors.json` in a switcher on the
page title; `?sector=<slug>` opens one directly.

The Pipeline workflow takes an optional `sector` input; empty runs every
sector. GitHub keeps at most one pending run per concurrency group, so a newer
queued dispatch replaces an older queued one, and the all-sectors run covers
every sector anyway.

To add `canonical_entities` to signals scored before canonicalisation existed
(no API calls, no re-scoring):

```
python -m scripts.backfill_canonical_entities --dry-run   # report only
python -m scripts.backfill_canonical_entities
```

## Configuration

GitHub Actions **secrets**: `ANTHROPIC_API_KEY`, `COMPANIES_HOUSE_API_KEY`,
and optionally `ALERT_WEBHOOK_URL` (Slack or Teams incoming webhook — the
pipeline posts there on failure; without it the alert step is skipped).

GitHub Actions **variable**: `ANTHROPIC_MODEL` (not a secret, so the model in
use is visible without opening settings).

Streamlit secrets: `DASHBOARD_PASSWORD`, `GITHUB_TOKEN` and `DATA_BASE_URL`
— the raw prefix of the repo's `data/` folder, ending in `/`, for example
`https://raw.githubusercontent.com/LAKelly1411/signal-prototype/main/data/`.
The dashboard reads `sectors.json` and each sector's `<slug>/signals.json` and
`<slug>/run_status.json` from there.

`DATA_RAW_URL` and `RUN_STATUS_RAW_URL` (the raw URLs of `data/signals.json`
and `data/run_status.json`) are now only the fallback: the dashboard uses them,
as a single gambling sector, while `DATA_BASE_URL` is unset or
`data/sectors.json` doesn't exist on main yet. Without `RUN_STATUS_RAW_URL` the
fallback simply hides the freshness strip.

### Deploying the sector switcher

1. Merge.
2. Let the pipeline run once on main. This creates `data/gambling/` and
   `data/sectors.json`.
3. Set `DATA_BASE_URL` in Streamlit Cloud.

Follow-up, once that's live: remove the compatibility copy
(`data/signals.json`, `data/run_status.json`), the old `DATA_RAW_URL` /
`RUN_STATUS_RAW_URL` secrets and the dashboard's fallback to them.
