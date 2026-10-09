# Dashboard Sector Switcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The dashboard header becomes a sector switcher. The dashboard loads the selected sector's data from `data/<slug>/`, sector-specific behaviour follows the selected sector, and a second real sector (Fintech & payments) exists.

**Architecture:**
- A new Streamlit-free module, `dashboard/data.py`, holds all data loading and selection logic, so it can be unit tested:
  - reads the `data/sectors.json` index and the per-sector files over GitHub raw;
  - falls back to the legacy single-file URLs;
  - picks the sector;
  - decides the view state;
  - maps a slug to its rules and its watchlist path.
- `dashboard/app.py` keeps rendering. It gains:
  - the switcher (a `st.popover` in the masthead);
  - sector-scoped state reset;
  - the "setting up" and "error" states;
  - passing the `Sector` into exclusions and theme heat.
- `config/sectors/fintech.yaml` is hand-written and validated by stage 1's loader.

**Tech Stack:** Python 3.11+, Streamlit 1.62 (`st.popover`, `st.query_params`, `streamlit.testing.v1.AppTest`), requests, PyYAML, pytest.

**Spec:** `docs/superpowers/specs/2026-10-08-sector-switcher-design.md`. Stage 1, which this builds on: `docs/superpowers/specs/2026-10-08-sector-aware-pipeline-design.md`.

## Global Constraints

- **Gambling unchanged.** Gambling looks and behaves exactly as today, and stage 1's `tests/test_gambling_equivalence.py` stays green.
- **The pipeline keeps writing the compatibility copy** (`data/signals.json`, `data/run_status.json`) in this stage. Removal is a follow-up.
- **New secret.** `DATA_BASE_URL` is the GitHub raw prefix of the repo's `data/` folder and ends in `/`. The legacy secrets `DATA_RAW_URL` / `RUN_STATUS_RAW_URL` still work as the fallback.
- **Fallback.** If `DATA_BASE_URL` is unset or `sectors.json` can't be loaded, the dashboard behaves as today, as a single gambling sector read from the legacy URLs.
- **Default sector.** An unknown or missing `?sector=` falls back to gambling if present, otherwise the first sector.
- **Data loading.** Only the selected sector's files are fetched, each with `st.cache_data(ttl=600)`.
- **Switching sectors** clears every session-state key that starts with `f_` (filters, sort) or `wl_` (watchlist dialog). No filter carries across sectors.
- **No layout shift.** Switching never moves the content below the header: the trigger keeps one fixed height.
- **State copy, verbatim:**
  - Setting up: title "Setting up", body "We're gathering the first signals for <Name>. This usually takes under an hour."
  - Error with data: notice "The last update didn't finish. Showing the latest data we have."
  - Error, no data: title "Not available yet", body "We couldn't load <Name> yet. We'll try again on the next scheduled update."
- **Company numbers** in `fintech.yaml` are quoted strings, verified against Companies House, never guessed.
- **Commit trailer.** Every commit message ends with:
  ```
  Co-Authored-By: <the model that wrote the commit> <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_016YJv2T4yhVoixtyDTkv1fZ
  ```
- **Running things.** Run from the repo root with `.venv/bin/python -m pytest …`. Never push. Never start, stop or restart the Streamlit server already running on port 8501.

## Review Focus

1. **Filters set in one sector, then switching.** The new sector shows no stale filter, sort or watchlist-form state. The AppTest is in Task 4.
2. **A crafted `?sector=` value** (`../x`, `GAMBLING`, empty) must never reach a URL or file path. Only slugs from the index are used. The test is in Task 1 (`pick_sector`), plus Task 4's AppTest.
3. **A sector in the index with no config in this deploy.** Exclusions fall back to gambling's rules and the page renders. The test is in Task 1 (`sector_rules`).
4. **The index says `ready` but the sector's `signals.json` is a 404** (a mid-commit race). The setting-up block shows, with no crash. The test is in Task 1 (`load_signals` and `view_state`).
5. **"Add to watchlist" while viewing fintech** writes `config/sectors/fintech.user.yaml`, never gambling's file, and never a path built from an unvalidated slug. The test is in Task 1 (`user_watchlist_path`), and the dialog is in Task 3.

---

## File structure

| File | Responsibility |
|---|---|
| `dashboard/data.py` (new) | Loading the index, signals and status (with fallback); `order_index`, `pick_sector`, `sector_note`, `view_state`, `sector_rules`, `user_watchlist_path`. No Streamlit import. |
| `dashboard/app.py` | Masthead switcher, sector selection and reset, state blocks, the sector passed to `is_excluded` / `compute_theme_heat`, watchlist path per sector, cached wrappers over `dashboard/data.py`. |
| `dashboard/brand.py` | Logo domains for the fintech companies. |
| `config/sectors/fintech.yaml` (new) | The Fintech & payments sector. |
| `tests/test_dashboard_data.py` (new) | Unit tests for `dashboard/data.py`. |
| `tests/test_fintech_sector.py` (new) | Validation of the fintech config. |
| `tests/test_dashboard_app.py` (new) | AppTest: default sector, switching, states, fallback, filter reset. |
| `README.md` | `DATA_BASE_URL`, deploy order, the fintech sector. |

---

### Task 1: `dashboard/data.py`, the data and selection module

**Files:**
- Create: `dashboard/data.py`
- Test: `tests/test_dashboard_data.py`

**Interfaces:**
- Consumes:
  - `src.sectors`: `load_sector(slug) -> Sector`, `SectorConfigError`, `SLUG_RE`.
  - `Sector` has `.slug` and `.name`.
- Produces:
  - `GAMBLING = "gambling"`.
  - `LEGACY_INDEX: list[dict]`, which is `[{"slug": "gambling", "name": "Gambling & gaming", "status": "ready"}]`.
  - `class DataError(Exception)`.
  - Loaders:
    - `load_index(base_url: str | None) -> list[dict] | None` returns `None` when unset or on any failure.
    - `load_signals(base_url: str, slug: str) -> list[dict]` returns `[]` on a 404 and raises `DataError` on other failures.
    - `load_run_status(base_url: str, slug: str) -> dict | None` returns `None` on any failure.
    - `load_legacy_signals(url: str) -> list[dict]` raises `DataError` on failure.
    - `load_legacy_status(url: str | None) -> dict | None`.
  - Selection and state:
    - `order_index(entries: list[dict]) -> list[dict]`: gambling first, then by slug, and drops entries whose slug fails `SLUG_RE`.
    - `pick_sector(entries: list[dict], requested: str | None) -> str`: always a slug present in `entries`.
    - `sector_note(entry: dict) -> str`.
    - `view_state(entry: dict, signals: list[dict]) -> str`, one of `"ready"`, `"setting_up"`, `"error_with_data"`, `"error_empty"`.
  - Rules and paths:
    - `sector_rules(slug: str) -> Sector`: the sector's config, or gambling's when the config is missing or invalid.
    - `user_watchlist_path(slug: str) -> str` raises `ValueError` for a slug failing `SLUG_RE`.
  - Every HTTP call goes through `requests.get(url, timeout=20)`, looked up at call time, so tests can monkeypatch `requests.get`.

- [ ] **Step 1: Write the failing tests**

`tests/test_dashboard_data.py`:

```python
import json
from types import SimpleNamespace

import pytest
import requests

from dashboard import data

BASE = "https://raw.example/data/"


class Resp:
    def __init__(self, status=200, payload=None, text=None):
        self.status_code = status
        self._payload = payload
        self._text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")

    def json(self):
        if self._text is not None:
            return json.loads(self._text)
        return self._payload


@pytest.fixture
def web(monkeypatch):
    routes: dict[str, Resp] = {}
    calls: list[str] = []

    def fake_get(url, timeout=None, **kw):
        calls.append(url)
        if url in routes:
            return routes[url]
        return Resp(404)

    monkeypatch.setattr(requests, "get", fake_get)
    return SimpleNamespace(routes=routes, calls=calls)


INDEX = [
    {"slug": "fintech", "name": "Fintech & payments", "status": "setting_up"},
    {"slug": "gambling", "name": "Gambling & gaming", "status": "ready", "signal_count": 336},
]


class TestLoadIndex:
    def test_reads_the_index(self, web):
        web.routes[BASE + "sectors.json"] = Resp(payload=INDEX)
        assert data.load_index(BASE) == INDEX

    def test_unset_base_means_no_index(self, web):
        assert data.load_index(None) is None and data.load_index("") is None
        assert web.calls == []

    def test_missing_index_means_fallback(self, web):
        assert data.load_index(BASE) is None

    def test_bad_json_means_fallback(self, web):
        web.routes[BASE + "sectors.json"] = Resp(text="{not json")
        assert data.load_index(BASE) is None

    def test_wrong_shape_means_fallback(self, web):
        web.routes[BASE + "sectors.json"] = Resp(payload={"slug": "gambling"})
        assert data.load_index(BASE) is None


class TestLoadSignals:
    def test_reads_the_sector_file(self, web):
        web.routes[BASE + "fintech/signals.json"] = Resp(payload=[{"id": "a"}])
        assert data.load_signals(BASE, "fintech") == [{"id": "a"}]

    def test_404_is_empty_not_an_error(self, web):
        assert data.load_signals(BASE, "fintech") == []

    def test_other_failures_raise_data_error(self, web):
        web.routes[BASE + "fintech/signals.json"] = Resp(500)
        with pytest.raises(data.DataError):
            data.load_signals(BASE, "fintech")

    def test_bad_json_raises_data_error(self, web):
        web.routes[BASE + "fintech/signals.json"] = Resp(text="nope")
        with pytest.raises(data.DataError):
            data.load_signals(BASE, "fintech")

    def test_run_status_failure_is_none(self, web):
        assert data.load_run_status(BASE, "fintech") is None
        web.routes[BASE + "fintech/run_status.json"] = Resp(payload={"live_signals": 3})
        assert data.load_run_status(BASE, "fintech") == {"live_signals": 3}


class TestLegacy:
    def test_legacy_signals(self, web):
        web.routes["https://raw.example/data/signals.json"] = Resp(payload=[{"id": "x"}])
        assert data.load_legacy_signals("https://raw.example/data/signals.json") == [{"id": "x"}]

    def test_legacy_signals_failure_raises(self, web):
        with pytest.raises(data.DataError):
            data.load_legacy_signals("https://raw.example/data/signals.json")

    def test_legacy_status_optional(self, web):
        assert data.load_legacy_status(None) is None
        assert data.load_legacy_status("https://raw.example/data/run_status.json") is None


class TestSelection:
    def test_order_puts_gambling_first_then_slug(self):
        entries = [{"slug": "zeta"}, {"slug": "fintech"}, {"slug": "gambling"}]
        assert [e["slug"] for e in data.order_index(entries)] == ["gambling", "fintech", "zeta"]

    def test_order_drops_invalid_slugs(self):
        entries = [{"slug": "gambling"}, {"slug": "../x"}, {"slug": "Bad"}, {"name": "no slug"}]
        assert [e["slug"] for e in data.order_index(entries)] == ["gambling"]

    @pytest.mark.parametrize("requested", [None, "", "nope", "../x", "GAMBLING", "fintech/"])
    def test_unknown_request_falls_back_to_gambling(self, requested):
        assert data.pick_sector(data.order_index(INDEX), requested) == "gambling"

    def test_known_request_wins(self):
        assert data.pick_sector(data.order_index(INDEX), "fintech") == "fintech"

    def test_falls_back_to_first_without_gambling(self):
        entries = [{"slug": "fintech"}, {"slug": "energy"}]
        assert data.pick_sector(data.order_index(entries), "nope") == "energy"

    def test_notes(self):
        assert data.sector_note({"status": "ready", "signal_count": 336}) == "336"
        assert data.sector_note({"status": "setting_up"}) == "Setting up…"
        assert data.sector_note({"status": "error"}) == "Update failed"
        assert data.sector_note({"status": "ready"}) == ""


class TestViewState:
    @pytest.mark.parametrize("entry,signals,expected", [
        ({"status": "ready"}, [{"id": "a"}], "ready"),
        ({"status": "ready"}, [], "setting_up"),          # index says ready, file not there yet
        ({"status": "setting_up"}, [], "setting_up"),
        ({"status": "setting_up"}, [{"id": "a"}], "ready"),
        ({"status": "error"}, [{"id": "a"}], "error_with_data"),
        ({"status": "error"}, [], "error_empty"),
        ({}, [{"id": "a"}], "ready"),
    ])
    def test_states(self, entry, signals, expected):
        assert data.view_state(entry, signals) == expected


class TestRulesAndPaths:
    def test_rules_for_a_configured_sector(self):
        assert data.sector_rules("gambling").slug == "gambling"

    def test_rules_fall_back_to_gambling_without_a_config(self):
        assert data.sector_rules("no-such-sector").slug == "gambling"

    def test_watchlist_path(self):
        assert data.user_watchlist_path("fintech") == "config/sectors/fintech.user.yaml"

    @pytest.mark.parametrize("slug", ["../gambling", "Fintech", "", "a/b"])
    def test_watchlist_path_rejects_bad_slugs(self, slug):
        with pytest.raises(ValueError):
            data.user_watchlist_path(slug)
```

- [ ] **Step 2: Run the tests to confirm they fail**

Run: `.venv/bin/python -m pytest tests/test_dashboard_data.py -q`
Expected: FAIL with `ImportError: cannot import name 'data' from 'dashboard'` (or "No module named dashboard.data").

If `dashboard` isn't importable as a package (no `dashboard/__init__.py`), check how `dashboard/app.py` imports `dashboard.brand`. It works as a namespace package from the repo root. Do not add an `__init__.py` unless the import genuinely fails.

- [ ] **Step 3: Implement `dashboard/data.py`**

```python
"""Where the dashboard's data comes from, and which sector it shows.

Each sector's data sits in the repo at data/<slug>/ and is read over GitHub
raw from DATA_BASE_URL; data/sectors.json lists the sectors. Until main has
that index (the first pipeline run after the stage 1 merge creates it), the
dashboard falls back to the single gambling file it has always read.

No Streamlit here, so all of this is unit tested; dashboard/app.py wraps the
loaders in st.cache_data.
"""

from __future__ import annotations

import logging

import requests

from src.sectors import SLUG_RE, SectorConfigError, load_sector

logger = logging.getLogger(__name__)

GAMBLING = "gambling"
LEGACY_INDEX = [{"slug": GAMBLING, "name": "Gambling & gaming", "status": "ready"}]


class DataError(Exception):
    """A sector's signals couldn't be loaded (other than not existing yet)."""


def _get_json(url: str):
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()
    return resp.json()


def load_index(base_url: str | None) -> list[dict] | None:
    """The sector index, or None to mean "use the legacy single file"."""
    if not base_url:
        return None
    try:
        index = _get_json(base_url + "sectors.json")
    except Exception:
        logger.info("No sector index at %s — using the legacy data file", base_url)
        return None
    if not isinstance(index, list):
        logger.warning("Sector index is not a list — using the legacy data file")
        return None
    return index


def load_signals(base_url: str, slug: str) -> list[dict]:
    """A sector's live signals. Not there yet (404) is an empty list: the
    sector is still setting up."""
    url = f"{base_url}{slug}/signals.json"
    try:
        resp = requests.get(url, timeout=20)
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        raise DataError(f"Couldn't load {url}: {exc}") from exc


def load_run_status(base_url: str, slug: str) -> dict | None:
    try:
        return _get_json(f"{base_url}{slug}/run_status.json")
    except Exception:
        return None


def load_legacy_signals(url: str) -> list[dict]:
    try:
        return _get_json(url)
    except Exception as exc:
        raise DataError(f"Couldn't load {url}: {exc}") from exc


def load_legacy_status(url: str | None) -> dict | None:
    if not url:
        return None
    try:
        return _get_json(url)
    except Exception:
        return None


def order_index(entries: list[dict]) -> list[dict]:
    """Gambling first (the original sector), then alphabetical by slug. Entries
    without a valid slug are dropped: a slug ends up in URLs and file paths."""
    valid = [e for e in entries if isinstance(e.get("slug"), str) and SLUG_RE.match(e["slug"])]
    return sorted(valid, key=lambda e: (e["slug"] != GAMBLING, e["slug"]))


def pick_sector(entries: list[dict], requested: str | None) -> str:
    """The sector to show: the requested one if it's listed, else gambling,
    else the first. Only ever returns a slug from the index."""
    slugs = [e["slug"] for e in entries]
    if requested in slugs:
        return requested
    if GAMBLING in slugs:
        return GAMBLING
    return slugs[0]


def sector_note(entry: dict) -> str:
    """The muted note beside a sector in the switcher."""
    status = entry.get("status")
    if status == "setting_up":
        return "Setting up…"
    if status == "error":
        return "Update failed"
    count = entry.get("signal_count")
    return str(count) if count is not None else ""


def view_state(entry: dict, signals: list[dict]) -> str:
    """What the page shows under the header for this sector."""
    if entry.get("status") == "error":
        return "error_with_data" if signals else "error_empty"
    return "ready" if signals else "setting_up"


def sector_rules(slug: str):
    """The sector's config, for exclusions and theme heat. A sector listed in
    the index but without a config in this deploy falls back to gambling's
    rules rather than breaking the page."""
    try:
        return load_sector(slug)
    except SectorConfigError:
        logger.warning("No usable config for sector %r — using gambling's rules", slug)
        return load_sector(GAMBLING)


def user_watchlist_path(slug: str) -> str:
    """Where the dashboard's "Add to watchlist" writes for this sector."""
    if not SLUG_RE.match(slug or ""):
        raise ValueError(f"Not a sector slug: {slug!r}")
    return f"config/sectors/{slug}.user.yaml"
```

Notes:
- `SLUG_RE` is `^[a-z0-9][a-z0-9-]*$` (`src/sectors.py`). A `SLUG_RE.match` on `"fintech/"` fails because of the `$` anchor. Check this. If `SLUG_RE` uses `match` without full anchoring, use `SLUG_RE.fullmatch` throughout this module.
- `load_sector("no-such-sector")` raises `SectorConfigError` (file not found), as stage 1 tests show.

- [ ] **Step 4: Run the tests**

Run: `.venv/bin/python -m pytest tests/test_dashboard_data.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add dashboard/data.py tests/test_dashboard_data.py
git commit -m "Add the dashboard's sector data loader and selection logic

Co-Authored-By: <model> <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_016YJv2T4yhVoixtyDTkv1fZ"
```

---

### Task 2: The Fintech & payments sector config

**Files:**
- Create: `config/sectors/fintech.yaml`
- Modify: `dashboard/brand.py` (`COMPANY_DOMAINS`)
- Test: `tests/test_fintech_sector.py`

**Interfaces:**
- Consumes:
  - `src.sectors.load_sector`;
  - `src.categories.taxonomy` and `canonical_category`;
  - `src.cluster.is_excluded`.
- Produces: `load_sector("fintech")`, with `name == "Fintech & payments"`.

- [ ] **Step 1: Verify the company numbers on Companies House**

For each candidate, fetch the public search page (no key needed) and read the exact registered name, the 8-character number and the status. Keep only **active** companies:

```bash
for q in "Monzo Bank" "Revolut Ltd" "Starling Bank" "Wise Payments" "Klarna Financial Services UK" "Checkout Ltd" "ClearBank" "GoCardless"; do
  echo "== $q"
  curl -s "https://find-and-update.company-information.service.gov.uk/search/companies?q=$(printf %s "$q" | sed 's/ /+/g')" \
    | grep -oE '/company/[0-9A-Z]{8}"[^<]*<[^>]*>[^<]+' | head -3
done
```

Record each chosen entity's search URL and the line you matched in the task report. If the grep pattern doesn't match the page's HTML, adjust it. If a company can't be confirmed, leave it out: a wrong number silently collects another company's filings.

- [ ] **Step 2: Write the failing tests**

`tests/test_fintech_sector.py`:

```python
import re

from src.categories import canonical_category, taxonomy
from src.cluster import is_excluded
from src.sectors import PROMPT_FIELDS, load_sector

FINTECH = load_sector("fintech")


def test_loads_with_its_name():
    assert FINTECH.slug == "fintech" and FINTECH.name == "Fintech & payments"


def test_every_prompt_field_is_fintech_wording():
    assert set(FINTECH.prompt) == set(PROMPT_FIELDS)
    assert not any("gambl" in v.lower() or "operator" in v.lower() for v in FINTECH.prompt.values())


def test_company_numbers_are_quoted_eight_character_ids():
    assert 6 <= len(FINTECH.companies) <= 8
    for company in FINTECH.companies:
        assert isinstance(company["company_number"], str)
        assert re.fullmatch(r"[0-9A-Z]{8}", company["company_number"]), company["name"]


def test_only_generic_sources():
    assert "gambling_commission" not in FINTECH.sources and "bgc" not in FINTECH.sources
    assert FINTECH.sources["dcms"]["organisation"] == "hm-treasury"


def test_fintech_categories_route_before_enforcement():
    assert canonical_category("APP fraud reimbursement", sector=FINTECH) == "Fraud and APP scams"
    assert canonical_category("Consumer Duty review", sector=FINTECH) == "Consumer Duty and redress"
    assert canonical_category("Variation of permission", sector=FINTECH) == "Authorisation and permissions"
    t = taxonomy(FINTECH)
    assert "Licence action" not in t and t[-1] == "Other"


def test_fintech_regulators_are_excluded_but_not_in_gambling():
    for body in ("Payment Systems Regulator", "Financial Ombudsman Service", "Bank of England"):
        assert is_excluded(body, FINTECH)
        assert not is_excluded(body)  # gambling default unchanged
```

- [ ] **Step 3: Run the tests to confirm they fail**

Run: `.venv/bin/python -m pytest tests/test_fintech_sector.py -q`
Expected: FAIL with `SectorConfigError: config/sectors/fintech.yaml: file: not found`.

- [ ] **Step 4: Write `config/sectors/fintech.yaml`**

Fill `companies` with the entities verified in Step 1 (6 to 8 of them). The values below are the shape; the names and numbers are the verified ones.

```yaml
# The fintech and payments sector. Hand-curated; dashboard additions go to
# fintech.user.yaml so the app never edits this file.
slug: fintech
name: Fintech & payments
brief: >-
  A B2B newsroom covering UK fintech and payments: banks and e-money firms,
  payment processors, lenders and the regulators around them.

prompt:
  newsroom: B2B fintech and payments newsroom
  coverage: the UK fintech and payments sector
  audience: specialist B2B fintech audience
  materiality: A small payments firm's change of permissions can matter here even if it would never make national news.
  key_players: banks, payment firms, lenders or platforms
  entity_hint: firm or company names mentioned
  company_word: firm
  significance_audience: specialist fintech newsroom
  theme_scope: the UK fintech and payments sector

keywords: ["fintech", "payments", "e-money", "open banking", "buy now pay later", "neobank"]

companies:
  - name: "Monzo Bank Limited"
    company_number: "<verified>"
    aliases: ["Monzo"]
  - name: "Revolut Ltd"
    company_number: "<verified>"
    aliases: ["Revolut"]
  - name: "Starling Bank Limited"
    company_number: "<verified>"
    aliases: ["Starling"]
  - name: "Wise Payments Limited"
    company_number: "<verified>"
    aliases: ["Wise", "TransferWise"]
  # … up to eight, each verified in Step 1

tickers:
  WISE: "Wise"
  PAY: "PayPoint"

# Fintech-only categories, on top of the core set. Listed order is kept,
# all ahead of Enforcement action.
categories:
  - name: "Fraud and APP scams"
    pattern: 'app fraud|authorised push payment|\bscams?\b|fraud|reimburse'
    before: "Enforcement action"
  - name: "Consumer Duty and redress"
    pattern: 'consumer duty|redress|ombudsman|\bfos\b|complaint|remediation'
    before: "Enforcement action"
  - name: "Authorisation and permissions"
    pattern: 'authoris|variation of permission|\bvop\b|e-money licen|registration|permission'
    before: "Enforcement action"

signal_type_fallback:
  regulatory: "Authorisation and permissions"

excluded_bodies:
  - "prudential regulation authority"
  - "pra"
  - "payment systems regulator"
  - "psr"
  - "financial ombudsman service"
  - "bank of england"
  - "uk finance"

sources:
  companies_house:
    items_per_page: 25
    sleep_seconds: 0.6
    lookback_days: 365
  gazette:
    results_per_term: 20
    sleep_seconds: 1.0
  dcms:
    # The collector searches any GOV.UK department's publications; HM Treasury
    # owns payments and fintech policy.
    organisation: "hm-treasury"
    keywords: ["fintech", "payments", "open banking", "buy now pay later"]
    results_per_term: 20
  parliament:
    keywords: ["fintech", "buy now pay later", "open banking", "payment services"]
    results_per_term: 20
  asa:
    keywords: ["buy now pay later", "payments", "fintech"]
  insolvency_service:
    sleep_seconds: 1.0
  lse_rns:
    skip_titles:
      - "holding(s) in company"
      - "notification of major holdings"
      - "director/pdmr shareholding"
      - "transaction in own shares"
      - "total voting rights"
      - "block listing"
```

Before committing, check that `PAY` on LSE RNS is PayPoint, and that each ticker belongs to the listed name. If you can't confirm a ticker, drop it.

- [ ] **Step 5: Add logo domains**

In `dashboard/brand.py`, add one entry per verified company to `COMPANY_DOMAINS`, keeping its alphabetical order. Include both the short and the registered name, as the gambling entries do. For example:

```python
    "Monzo": "monzo.com",
    "Monzo Bank": "monzo.com",
    "Revolut": "revolut.com",
    "Starling": "starlingbank.com",
    "Starling Bank": "starlingbank.com",
    "Wise": "wise.com",
    "Wise Payments": "wise.com",
```

- [ ] **Step 6: Run the tests**

Run: `.venv/bin/python -m pytest tests/test_fintech_sector.py tests/test_gambling_equivalence.py tests/test_sectors.py -q`
Expected: all pass. The gambling equivalence is unchanged.

Then run `.venv/bin/python -m pytest -q`. Expected: the whole suite passes.

- [ ] **Step 7: Commit**

```bash
git add config/sectors/fintech.yaml dashboard/brand.py tests/test_fintech_sector.py
git commit -m "Add the Fintech & payments sector

Co-Authored-By: <model> <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_016YJv2T4yhVoixtyDTkv1fZ"
```

---

### Task 3: Sector-aware dashboard: loading, switcher, states, rules, watchlist

**Files:**
- Modify: `dashboard/app.py`

**Interfaces:**
- Consumes: all of `dashboard/data.py` (Task 1).
- Produces, used by Task 4's AppTest:
  - session-state key `"sector"`, the selected slug, set every run;
  - popover key `"pop-sector"`;
  - menu buttons keyed `sectoropt-<slug>-on` / `sectoropt-<slug>-off` (via `_check_row`);
  - the disabled button key `"sector-new"`;
  - state blocks rendered with `_empty_block(...)`, using the verbatim copy in Global Constraints;
  - the notice in a `st.container(key="sector-notice")`.

- [ ] **Step 1: Cached loaders**

Replace `load_signals` and `load_run_status` (around `dashboard/app.py:1277-1298`) with cached wrappers over `dashboard/data.py`:

```python
from dashboard import data


def _secret(name: str) -> str | None:
    try:
        return st.secrets.get(name)
    except Exception:
        return None


@st.cache_data(ttl=600)
def load_index() -> list[dict] | None:
    return data.load_index(_secret("DATA_BASE_URL"))


@st.cache_data(ttl=600)
def load_signals(slug: str, legacy: bool) -> list[dict]:
    if legacy:
        return data.load_legacy_signals(st.secrets["DATA_RAW_URL"])
    return data.load_signals(_secret("DATA_BASE_URL"), slug)


@st.cache_data(ttl=600)
def load_run_status(slug: str, legacy: bool) -> dict | None:
    """Pipeline health, published next to the signals file. Absent on older
    data or if the URL isn't configured — the strip just hides itself."""
    if legacy:
        return data.load_legacy_status(_secret("RUN_STATUS_RAW_URL"))
    return data.load_run_status(_secret("DATA_BASE_URL"), slug)


@st.cache_resource
def sector_rules(slug: str):
    return data.sector_rules(slug)
```

- [ ] **Step 2: Selecting a sector**

Add the selection helpers next to them:

```python
SECTOR = "sector"  # session-state key: the slug being shown


def _select_sector(slug: str) -> None:
    """Switcher callback: show another sector, starting from clean filters.
    Filter, sort and watchlist-form state is all keyed f_* / wl_*, and none of
    it means anything in another sector (different sources, categories and
    companies)."""
    st.query_params["sector"] = slug
    for key in [k for k in st.session_state if str(k).startswith(("f_", "wl_"))]:
        del st.session_state[key]


def _current_slug() -> str:
    return st.session_state.get(SECTOR, data.GAMBLING)
```

- [ ] **Step 3: The switcher in the masthead**

Split `render_masthead` so that the lockup stays markdown, and the intro becomes the switcher. Replace the `intro` markup and the function with:

```python
def render_masthead(entries: list[dict] | None = None, current: dict | None = None) -> None:
    """PA lockup — the mark beside the product name set as two ink blocks, as on
    the Media Briefings header — then the sector switcher and standfirst. The
    login page passes nothing and gets the lockup alone."""
    st.markdown(
        '<div class="pa-masthead"><div class="pa-lockup">'
        f"{PA_LOGO_SVG}"
        '<span class="pa-wordmark"><span>Sector</span><span>Signal</span></span>'
        '</div><span class="pa-font-warm" aria-hidden="true">a<b>a</b></span></div>',
        unsafe_allow_html=True,
    )
    if entries is None or current is None:
        return
    st.markdown('<span class="pa-kicker">Sector</span>', unsafe_allow_html=True)
    _sector_switcher(entries, current)
    st.markdown('<p class="pa-standfirst">Sector signals, scored for newsworthiness.</p>',
                unsafe_allow_html=True)


def _sector_switcher(entries: list[dict], current: dict) -> None:
    """The sector name, set as the page title, opening a menu of sectors."""
    with st.popover(current.get("name", current["slug"]), key="pop-sector"):
        for entry in entries:
            note = data.sector_note(entry)
            label = entry.get("name", entry["slug"]) + (f"  :gray[{note}]" if note else "")
            _check_row(f"sectoropt-{entry['slug']}", label,
                       entry["slug"] == current["slug"], _select_sector, (entry["slug"],))
        st.divider()
        st.button("New sector  :blue-background[PREMIUM]", key="sector-new",
                  icon=":material/add:", type="tertiary", width="stretch", disabled=True,
                  help="Creating sectors arrives with the premium add-on.")
```

`check_password()` currently calls `render_masthead(show_intro=False)`. Change it to `render_masthead()`.

**Kicker wording, a ruling against the spec's mockup.** The spec's mockup shows the kicker as "SECTOR SIGNAL". The lockup beside it already reads "Sector Signal", and that repetition is the redundancy this stage removes. So the kicker labels the control: "Sector". Record this in the task report.

- [ ] **Step 4: Switcher styling and menu behaviour**

In `inject_css()`, next to the `.pa-title` rules, add the following. It makes the popover trigger look like the title (borderless, condensed, 3rem), keeps one fixed height so nothing below moves, and gives the menu a minimum width:

```css
        /* The sector switcher: the popover's trigger set as the page title. */
        .st-key-pop-sector [data-testid="stPopoverButton"] {
            border: none;
            background: transparent;
            padding: 0;
            height: 3.6rem;
            min-height: 3.6rem;
            margin: 0.75rem 0 0.5rem 0;
            justify-content: flex-start;
        }
        .st-key-pop-sector [data-testid="stPopoverButton"] p {
            font-family: var(--pa-font-heading);
            font-weight: 700;
            font-size: 3rem;
            line-height: 1.0833;
            letter-spacing: 0.005em;
            color: var(--pa-ink);
            white-space: nowrap;
        }
        .st-key-pop-sector [data-testid="stPopoverButton"]:hover p { color: var(--pa-cobalt); }
        [data-testid="stPopoverBody"]:has([class*="st-key-sectoropt-"]) { min-width: 320px; }
        [class*="st-key-sectoropt-"] button p span { float: right; margin-left: 1.5rem; }
```

In `_RESIZE_SCRIPT`'s `click` handler, next to the Sort close, add:

```javascript
      // Close the sector menu once a sector is chosen.
      if (e.target.closest && e.target.closest('[class*="st-key-sectoropt-"] button')) {
        setTimeout(() => {
          const btn = doc.querySelector('.st-key-pop-sector [data-testid="stPopoverButton"]');
          if (btn && btn.getAttribute("aria-expanded") === "true") btn.click();
        }, 0);
      }
```

If the trigger's chevron sits far from the label, or the note doesn't float right, adjust these selectors during the Task 5 browser check. Don't guess now.

- [ ] **Step 5: Exclusions and theme heat use the sector**

Thread the selected sector's rules through the two places that use them:
- `render_patterns(signals)` → `render_patterns(signals, sector)`. Change `is_excluded(n)` to `is_excluded(n, sector)` (around line 2242).
- `render_themes(signals)` → `render_themes(signals, sector)`. Change `compute_theme_heat(members)` to `compute_theme_heat(members, sector=sector)`, and `is_excluded(e)` to `is_excluded(e, sector)` (around lines 2304 and 2312).
- `_patterns_fragment` and `_themes_fragment` take and pass `sector` too.

Then grep: `grep -n "is_excluded(\|compute_theme_heat(" dashboard/app.py`. Every call must pass the sector.

- [ ] **Step 6: Watchlist writes the sector's file**

- Delete the `USER_WATCHLIST_PATH` constant and its comment.
- In `_fetch_user_watchlist` and `add_operator_to_watchlist`, build the path with `data.user_watchlist_path(_current_slug())`.
- In `_watchlist_dialog`, update the docstring, and make the intro copy's second paragraph name the sector:

```python
            f'<p class="wl-copy wl-muted">It\'s added to {html.escape(_current_sector_name())}. '
            "All you need is its name. If you know its Companies House number, add that "
            "too for fuller coverage.</p>",
```

with:

```python
def _current_sector_name() -> str:
    return st.session_state.get("sector_name", "this sector")
```

`main()` sets `st.session_state["sector_name"]` every run (Step 7).

- [ ] **Step 7: `main()` wires it together**

Replace the body of `main()` after `check_password()` with:

```python
    index = load_index()
    legacy = index is None
    entries = data.order_index(data.LEGACY_INDEX if legacy else index)
    if not entries:
        entries = data.LEGACY_INDEX
        legacy = True
    slug = data.pick_sector(entries, st.query_params.get("sector"))
    current = next(e for e in entries if e["slug"] == slug)
    st.session_state[SECTOR] = slug
    st.session_state["sector_name"] = current.get("name", slug)
    sector = sector_rules(slug)

    # Title on the left and pipeline health on the right, rather than
    # stacked, so the feed starts higher up the page.
    title_col, status_col = st.columns([3, 2], vertical_alignment="bottom")
    with title_col:
        render_masthead(entries, current)
    with status_col:
        with st.container(key="header-actions", horizontal=True, horizontal_alignment="right"):
            _watchlist_button()
        render_health_strip(load_run_status(slug, legacy))

    try:
        signals = load_signals(slug, legacy)
    except data.DataError:
        _empty_block("Not available yet",
                     f"We couldn't load {current.get('name', slug)} yet. "
                     "We'll try again on the next scheduled update.")
        return

    state = data.view_state(current, signals)
    name = current.get("name", slug)
    if state == "setting_up":
        _empty_block("Setting up", f"We're gathering the first signals for {name}. "
                     "This usually takes under an hour.")
        return
    if state == "error_empty":
        _empty_block("Not available yet",
                     f"We couldn't load {name} yet. We'll try again on the next scheduled update.")
        return
    if state == "error_with_data":
        with st.container(key="sector-notice"):
            st.markdown('<p class="sector-notice">The last update didn\'t finish. '
                        "Showing the latest data we have.</p>", unsafe_allow_html=True)
```

After that comes the existing tab code (`sort_slot = …`, `st.tabs(...)`, and so on), with `sector` passed to the two fragments:

```python
    if patterns_tab.open:
        with patterns_tab:
            _patterns_fragment(signals, sector)
    if themes_tab.open:
        with themes_tab:
            _themes_fragment(signals, sector)
```

Add CSS for the notice in `inject_css()`:

```css
        .sector-notice {
            font-family: var(--pa-font-data);
            font-size: 0.875rem;
            color: #5c5c5c;
            border-left: 4px solid var(--pa-ink);
            padding: 4px 12px;
            margin: 0 0 8px 0;
        }
```

Data loading notes:
- `load_index()` is cached for 10 minutes, so a sector created in stage 3 appears within 10 minutes. That is fine for stage 2.
- In legacy mode, the cached wrappers call `st.secrets["DATA_RAW_URL"]` exactly as today.

- [ ] **Step 8: Manual import check**

Run: `.venv/bin/python -c "import ast,sys; ast.parse(open('dashboard/app.py').read()); print('ok')"`, then `.venv/bin/python -m pytest -q`.
Expected: `ok`, and the whole suite passes. Task 4 adds the AppTest.

- [ ] **Step 9: Commit**

```bash
git add dashboard/app.py
git commit -m "Make the dashboard sector-aware, with a switcher in the header

Co-Authored-By: <model> <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_016YJv2T4yhVoixtyDTkv1fZ"
```

---

### Task 4: AppTest coverage for the switcher

**Files:**
- Create: `tests/test_dashboard_app.py`, and `tests/fixtures/dashboard/` (small JSON fixtures)

**Interfaces:**
- Consumes: Task 3's keys (`"sector"`, `"pop-sector"`, `sectoropt-<slug>-on/off`, `"sector-new"`, `"sector-notice"`) and its state copy.

- [ ] **Step 1: Fixtures**

Create `tests/fixtures/dashboard/` with:
- `gambling_signals.json`: the first 30 signals of `data/signals.json`. Generate it once with `.venv/bin/python -c "import json; json.dump(json.load(open('data/signals.json'))[:30], open('tests/fixtures/dashboard/gambling_signals.json','w'), indent=1)"`.
- `fintech_signals.json`: three hand-written scored signals. Each has `id`, `source`, `source_url`, `title`, `published_at`, `newsworthiness_score`, `canonical_category`, `entities`, `why_it_matters` and `signal_type`, plus every other key `render_feed` reads. Copy one gambling signal's keys and change the values.

- [ ] **Step 2: Write the tests**

`tests/test_dashboard_app.py`:

```python
import json
from pathlib import Path

import pytest
import requests
import streamlit as st
from streamlit.testing.v1 import AppTest

FIX = Path("tests/fixtures/dashboard")
BASE = "https://raw.example/data/"
LEGACY_SIGNALS = "https://raw.example/legacy/signals.json"

GAMBLING = json.loads((FIX / "gambling_signals.json").read_text())
FINTECH = json.loads((FIX / "fintech_signals.json").read_text())

INDEX = [
    {"slug": "gambling", "name": "Gambling & gaming", "status": "ready", "signal_count": len(GAMBLING)},
    {"slug": "fintech", "name": "Fintech & payments", "status": "ready", "signal_count": len(FINTECH)},
    {"slug": "energy", "name": "Energy retail", "status": "setting_up"},
]


class Resp:
    def __init__(self, status=200, payload=None):
        self.status_code, self._payload = status, payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))

    def json(self):
        return self._payload


def serve(monkeypatch, routes):
    def fake_get(url, timeout=None, **kw):
        return routes.get(url, Resp(404))
    monkeypatch.setattr(requests, "get", fake_get)


@pytest.fixture(autouse=True)
def _fresh_caches():
    st.cache_data.clear()
    st.cache_resource.clear()
    yield


def app(query=None, base=BASE):
    at = AppTest.from_file("streamlit_app.py", default_timeout=30)
    at.secrets["DASHBOARD_PASSWORD"] = "x"
    at.secrets["DATA_RAW_URL"] = LEGACY_SIGNALS
    if base:
        at.secrets["DATA_BASE_URL"] = base
    at.session_state["authenticated"] = True
    if query:
        at.query_params.update(query)
    return at


def sector_routes(index=INDEX):
    return {
        BASE + "sectors.json": Resp(payload=index),
        BASE + "gambling/signals.json": Resp(payload=GAMBLING),
        BASE + "fintech/signals.json": Resp(payload=FINTECH),
    }


def popover_label(at):
    return at.get("popover")[0].proto.label


def test_defaults_to_gambling(monkeypatch):
    serve(monkeypatch, sector_routes())
    at = app().run()
    assert not at.exception
    assert at.session_state["sector"] == "gambling"
    assert popover_label(at) == "Gambling & gaming"


def test_query_param_selects_fintech(monkeypatch):
    serve(monkeypatch, sector_routes())
    at = app({"sector": "fintech"}).run()
    assert not at.exception
    assert at.session_state["sector"] == "fintech"


@pytest.mark.parametrize("bad", ["nope", "../gambling", "FINTECH"])
def test_unknown_or_crafted_slug_falls_back(monkeypatch, bad):
    serve(monkeypatch, sector_routes())
    at = app({"sector": bad}).run()
    assert not at.exception and at.session_state["sector"] == "gambling"


def test_setting_up_sector_shows_the_block(monkeypatch):
    serve(monkeypatch, sector_routes())
    at = app({"sector": "energy"}).run()
    assert not at.exception
    body = " ".join(m.value for m in at.markdown)
    assert "We're gathering the first signals for Energy retail." in body
    assert not at.tabs  # tabs replaced by the state block


def test_error_with_data_shows_the_notice(monkeypatch):
    index = [dict(INDEX[0], status="error")] + INDEX[1:]
    serve(monkeypatch, sector_routes(index))
    at = app().run()
    assert not at.exception
    assert any("The last update didn't finish." in m.value for m in at.markdown)
    assert at.tabs


def test_switching_clears_filters(monkeypatch):
    serve(monkeypatch, sector_routes())
    at = app().run()
    at.session_state["f_min_score"] = 70
    at.session_state["wl_name"] = "Half-typed Ltd"
    at.button(key="sectoropt-fintech-off").click().run()
    assert not at.exception
    assert at.session_state["sector"] == "fintech"
    assert "f_min_score" not in at.session_state or at.session_state["f_min_score"] != 70
    assert "wl_name" not in at.session_state or at.session_state["wl_name"] == ""


def test_new_sector_row_is_disabled(monkeypatch):
    serve(monkeypatch, sector_routes())
    at = app().run()
    assert at.button(key="sector-new").disabled


def test_falls_back_to_legacy_without_index(monkeypatch):
    serve(monkeypatch, {LEGACY_SIGNALS: Resp(payload=GAMBLING)})
    at = app().run()
    assert not at.exception
    assert at.session_state["sector"] == "gambling"
    assert at.tabs


def test_legacy_when_base_unset(monkeypatch):
    serve(monkeypatch, {LEGACY_SIGNALS: Resp(payload=GAMBLING)})
    at = app(base=None).run()
    assert not at.exception and at.tabs
```

API adaptation notes:
- These tests use the AppTest API as of Streamlit 1.62. Check each call against the installed version: `at.query_params`, `at.get("popover")`, `at.button(key=...)`, `at.tabs` and `.disabled`. Where one doesn't exist, use the closest equivalent; for example, read the popover label from the element tree, or pass the query params through `AppTest.from_file(...)`. Keep each test's assertion the same.
- `streamlit_app.py` runs `dashboard/app.py` with `runpy`. If AppTest can't follow that, point `from_file` at `dashboard/app.py` directly.
- Record every adaptation in the report.

- [ ] **Step 3: Run the tests**

Run: `.venv/bin/python -m pytest tests/test_dashboard_app.py -q`
Expected: all pass. Then run `.venv/bin/python -m pytest -q`; the whole suite passes. Finally run `git status`: it shows no changes under `data/`.

If a test exposes a Task 3 bug, fix it in `dashboard/app.py` in this task and say so in the report.

- [ ] **Step 4: Commit**

```bash
git add tests/test_dashboard_app.py tests/fixtures/dashboard dashboard/app.py
git commit -m "Cover the sector switcher with AppTests

Co-Authored-By: <model> <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_016YJv2T4yhVoixtyDTkv1fZ"
```

---

### Task 5: README, local secrets and the browser check

**Files:**
- Modify: `README.md`
- Local only (gitignored, never committed): `.streamlit/secrets.toml`

- [ ] **Step 1: README**

In `README.md`:

- **Dashboard secrets.** Document `DATA_BASE_URL`, for example `https://raw.githubusercontent.com/LAKelly1411/signal-prototype/main/data/`, which must end in `/`. State that `DATA_RAW_URL` and `RUN_STATUS_RAW_URL` are now only the fallback, used until `data/sectors.json` exists on main.
- **Deploy order.** Add the spec's three steps:
  1. Merge.
  2. Let the pipeline run once on main. This creates `data/gambling/` and `data/sectors.json`.
  3. Set `DATA_BASE_URL` in Streamlit Cloud.

  Note the follow-up: remove the compatibility copy, the old secrets and the fallback.
- **Sectors section.** Add Fintech & payments and how to run it: `python -m src.pipeline --sector fintech`, or the workflow's `sector` input. Its first run makes paid Claude calls.

- [ ] **Step 2: Local secrets**

Add `DATA_BASE_URL` to the local, gitignored `.streamlit/secrets.toml`. Point it at the same raw `main/data/` prefix the existing `DATA_RAW_URL` uses (keep the owner and repo from that URL). Main has no `sectors.json` yet, so the local app will run in fallback mode. That is expected, and it's the first deploy state.

- [ ] **Step 3: Browser check (both modes)**

The Streamlit server on port 8501 belongs to another session. Run a second one for this check, and stop it afterwards:

```bash
.venv/bin/streamlit run streamlit_app.py --server.headless true --server.port 8502
```

**Fallback mode.** Open http://localhost:8502 and log in with the local password. Then check:
- The header reads PA lockup, then the "Sector" kicker, then the "Gambling & gaming ⌄" title, then the standfirst.
- The menu lists one sector plus the disabled "New sector · PREMIUM" row.
- Choosing a sector closes the menu.
- Nothing below the header moves.

**Sector mode.** Serve fixture data locally:
1. Make a temp dir containing `sectors.json` (INDEX from Task 4), `gambling/signals.json` and `fintech/signals.json`.
2. Run `python -m http.server 8765` in it.
3. Temporarily set `DATA_BASE_URL = "http://localhost:8765/"` in the local secrets.

Then switch between Gambling, Fintech and Energy, and check:
- the setting-up block shows for Energy;
- notes are muted and right-aligned in the menu;
- the menu closes on choice;
- there is no layout shift;
- the title doesn't wrap at 1280px width.

Fix any CSS issues found, in `dashboard/app.py`. Restore the local secret to the raw `main/data/` URL and stop both servers when done.

Take screenshots of the header closed, the menu open and the setting-up state. Save them to `$CLAUDE_JOB_DIR/tmp/` (or `/tmp` if that variable is unset) and list their paths in the report.

- [ ] **Step 4: Full suite and commit**

Run: `.venv/bin/python -m pytest -q`. Expected: the whole suite passes.

```bash
git add README.md dashboard/app.py
git commit -m "Document the sector switcher's data source and deploy order

Co-Authored-By: <model> <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_016YJv2T4yhVoixtyDTkv1fZ"
```

The fintech sector's first real run (`sector=fintech` workflow dispatch, with paid calls) is **not** part of this plan. It needs the branch pushed and the author's go-ahead.
