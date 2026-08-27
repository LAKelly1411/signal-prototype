# signal-prototype

Gambling/gaming sector signal monitoring prototype.

## Setup

```
pip install -r requirements.txt
cp .env.example .env
python -m src.pipeline
```

Dashboard: `dashboard/app.py` (Streamlit).

## Tests

```
pip install -r requirements-dev.txt
python -m pytest tests/ -q
```

## Data files

The pipeline writes three things under `data/`, all committed:

- `signals.json` — the live store, holding the last `RETENTION_DAYS` (120) of
  signals. This is what the dashboard downloads.
- `archive/signals-YYYY.json` — signals past the retention window, split by
  published year. Append-only.
- `archive/ids.json` — ids of everything archived, so a source that still
  lists an old item can't cause it to be re-ingested and re-scored.
- `run_status.json` — what the last run did, per collector. Drives the
  dashboard's freshness strip.

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
