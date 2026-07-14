# signal-prototype

PA Sector Signal prototype (gambling/gaming). See `SBC_Signal_Prototype_BUILD_SPEC.md` for the full build spec.

Phase 0: Gambling Commission collector → Claude scoring → `data/signals.json` → password-gated Streamlit dashboard.

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
