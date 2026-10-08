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
sector's config in `config/sectors/<slug>.user.yaml`; for now the dashboard's
watchlist form writes `config/sectors/gambling.user.yaml` only (other sectors
arrive in stage 2). Each sector's run makes its own Claude calls, so every
sector adds to the cost of a run.

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

Streamlit secrets: `DASHBOARD_PASSWORD`, `DATA_RAW_URL`, `GITHUB_TOKEN`, and
`RUN_STATUS_RAW_URL` — the raw URL of `data/run_status.json`. If it isn't set
the dashboard simply hides the freshness strip.
