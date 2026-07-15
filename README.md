# signal-prototype

Sector Signal prototype (gambling/gaming).

Gambling Commission, Companies House, Gazette insolvency, and DCMS collectors → Claude scoring → `data/signals.json` → password-gated Streamlit dashboard.

## Local setup

```
pip install -r requirements.txt
cp .env.example .env   # fill in ANTHROPIC_API_KEY
python -m src.pipeline
```

## Dashboard

Deployed on Streamlit Community Cloud from `dashboard/app.py`. Secrets (`DASHBOARD_PASSWORD`, `DATA_RAW_URL`) are set in the app's Settings → Secrets, not in this repo.

## Scheduling

`.github/workflows/pipeline.yml` runs the pipeline on a schedule and commits `data/signals.json` back to the repo.
