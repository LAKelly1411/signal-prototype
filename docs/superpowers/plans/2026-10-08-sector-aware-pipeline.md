# Sector-aware Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make "sector" a first-class concept in the Sector Signal pipeline. Gambling becomes `config/sectors/gambling.yaml` and produces identical output, and any further sector runs from its own config file with its own data.

**Architecture:**
- A `Sector` object is loaded and validated from `config/sectors/<slug>.yaml`, plus its `.user.yaml` additions.
- The sector is passed through categories, clustering, scoring and collector construction. Each of those takes `sector=None`, which means gambling, so existing callers such as the dashboard keep working.
- The pipeline runs each sector in isolation, writing to `data/<slug>/`, and maintains an index at `data/sectors.json`.
- After a gambling run it also writes a copy to the old `data/signals.json` paths, for the deployed dashboard.

**Tech Stack:** Python 3.11+, PyYAML, pytest, Anthropic SDK (faked in tests), GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-10-08-sector-aware-pipeline-design.md`

## Global Constraints

- **Byte-identical gambling behaviour.** For `gambling.yaml`, everything must equal what today's code produces:
  - the rendered scoring, cluster and theme prompts;
  - the summary version hashes;
  - the taxonomy and its order;
  - `canonical_category` results;
  - `is_excluded` results;
  - cluster and theme assignment;
  - collector construction.

  The baseline fixture from Task 1 is the arbiter.
- **Signal ids are unchanged:** `make_id(source, stable_key)`. No sector in the id.
- **`sector=None` means gambling everywhere.** It is loaded lazily from `config/sectors/gambling.yaml`.
- **Every sector writes only under `data/<slug>/`.** The one exception is the gambling compatibility copy at `data/signals.json` and `data/run_status.json`.
- **Exit codes:** `python -m src.pipeline` exits `0` when all sectors succeed, `1` if any sector failed and `2` for an unknown `--sector`.
- **Commit trailer:** every commit message ends with:
  ```
  Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_016YJv2T4yhVoixtyDTkv1fZ
  ```
- **Running things:** use the repo virtualenv, `.venv/bin/python -m pytest …`, from the repo root. Paths like `config/…` are relative to the root.

## Review Focus

1. **Watchlist additions can't be lost in the move.** The dashboard's form writes `{"operators": [...]}`. Its file moves to `config/sectors/gambling.user.yaml`, and the loader must merge an `operators` key as well as `companies`. The test is in Task 2.
2. **Company numbers written as unquoted YAML numbers** (e.g. `04241161` becomes the int `4241161`, dropping the leading zero) must be rejected with a clear error, not silently mangled. The test is in Task 2.
3. **One bad sector must not stop the rest.** An invalid config or an exception during a run must still let the other sectors run, record `error` in the index and exit 1. The test is in Task 7.
4. **The migration script is safe to run twice,** and also on a repo that's already been migrated: a no-op that changes no files. The test is in Task 8.
5. **The compatibility copy must stay exactly equal** to `data/gambling/signals.json` and `run_status.json` after a gambling run, because the live dashboard reads it. The test is in Task 7.

---

## File structure

| File | Responsibility |
|---|---|
| `config/sectors/gambling.yaml` (new) | The gambling sector: wording, keywords, companies, tickers, gambling-only categories, excluded bodies and sources. Replaces `config/sources.yaml` and `config/watchlist.yaml`. |
| `src/sectors.py` (new) | `Sector` dataclass, `load_sector`, validation, `.user.yaml` merge, `list_sector_slugs`, the index (`update_index`, `refresh_index`). |
| `src/categories.py` | Core categories and rules, plus a per-sector `Ruleset`; `canonical_category(..., sector=None)`. |
| `src/cluster.py` | Shared excluded institutions plus the sector's bodies; `sector=None` on every function that excludes. |
| `src/score.py` | Prompt templates rendered from `sector.prompt`; version functions; `sector=None` on the scoring and summary functions. |
| `src/collectors/dcms.py` | The department slug becomes a constructor argument. |
| `src/pipeline.py` | `COLLECTORS` registry, `build_collectors(sector)`, `run_sector`, `main()` with `--sector`, the compatibility copy. |
| `scripts/migrate_to_sectors.py` (new) | Moves today's data into `data/gambling/`. |
| `scripts/backfill_canonical_entities.py` | Gains `--sector`. |
| `dashboard/app.py` | The watchlist file path becomes `config/sectors/gambling.user.yaml`. |
| `.github/workflows/pipeline.yml` | Optional `sector` input; a concurrency group. |
| `tests/fixtures/make_gambling_baseline.py`, `tests/fixtures/gambling_baseline.json` (new) | Records today's behaviour. |
| `tests/test_gambling_equivalence.py` (new) | Proves gambling is unchanged. |
| `tests/test_sectors.py`, `tests/test_pipeline_sectors.py`, `tests/test_migrate.py` (new) | New behaviour. |

---

### Task 1: Record today's gambling behaviour (baseline)

Run this **before changing any code**. It records what the current code produces, and every later task is checked against it.

**Files:**
- Create: `tests/fixtures/__init__.py` (empty), `tests/fixtures/make_gambling_baseline.py`, `tests/fixtures/gambling_baseline.json` (generated)
- Create: `tests/test_gambling_equivalence.py`

**Interfaces:**
- Produces: `tests/fixtures/gambling_baseline.json` with these keys: `prompts{system,cluster,theme}`, `versions{cluster,theme}`, `taxonomy`, `category_inputs`, `categories`, `entities`, `excluded`, `now`, `signals`, `alias_operators`, `cluster_ids`, `theme_ids`, `theme_heat`, `collectors`.

- [ ] **Step 1: Write the baseline generator**

`tests/fixtures/make_gambling_baseline.py`:

```python
"""Records what today's (pre-sector) code does for gambling, so the sector
refactor can prove it changed nothing. Run once, before the refactor:

    .venv/bin/python -m tests.fixtures.make_gambling_baseline
"""

import copy
import json
import os
from datetime import timedelta
from pathlib import Path

from src import categories, cluster, score, store
from src.entities import build_alias_map
from src.pipeline import build_collectors, load_sources, load_watchlist

OUT = Path("tests/fixtures/gambling_baseline.json")

# Labels and titles that exercise every rule and the fallbacks, on top of
# whatever the live store holds.
EXTRA_CATEGORY_INPUTS = [
    ["AML/licence enforcement", "", None],
    ["illegal gambling enforcement", "", None],
    ["ASA ruling - irresponsible advertising", "", None],
    ["safer gambling", "", None],
    ["personal licence revocation", "", None],
    ["", "Publication of the Scheme Document", None],
    [None, "Untitled", "regulatory"],
    [None, "Untitled", "insolvency"],
    ["", "", None],
    ["nonsense label", "some title", None],
]


def collector_snapshot(collector) -> dict:
    attrs = {k: v for k, v in vars(collector).items() if k != "api_key"}
    return {
        "class": type(collector).__name__,
        "attrs": json.loads(json.dumps(attrs, default=str, sort_keys=True)),
    }


def main() -> None:
    os.environ.setdefault("COMPANIES_HOUSE_API_KEY", "baseline-test-key")
    signals = [s for s in store.load() if s.get("newsworthiness_score") is not None]
    operators = load_watchlist()
    alias_map = build_alias_map(operators)

    category_inputs = [
        [s.get("category"), s.get("title", ""), s.get("signal_type")] for s in signals
    ] + EXTRA_CATEGORY_INPUTS
    entities = sorted(
        {e for s in signals for e in (s.get("entities") or []) + (s.get("canonical_entities") or [])}
        | set(cluster.EXCLUDED_ENTITIES)
        | {"Entain", "bet365 Group Limited", "Rank Group", "HM Treasury", "The Gazette"}
    )
    now = max(cluster._parse_date(s["published_at"]) for s in signals) + timedelta(days=1)

    working = copy.deepcopy(signals)
    cluster.assign_clusters(working, now=now, alias_map=alias_map)
    cluster.assign_themes(working, now=now, alias_map=alias_map)
    by_theme: dict[str, list[dict]] = {}
    for s in working:
        if s.get("theme_id"):
            by_theme.setdefault(s["theme_id"], []).append(s)

    baseline = {
        "prompts": {
            "system": score.SYSTEM_PROMPT,
            "cluster": score.CLUSTER_SYSTEM_PROMPT,
            "theme": score.THEME_SYSTEM_PROMPT,
        },
        "versions": {
            "cluster": score.CLUSTER_SUMMARY_VERSION,
            "theme": score.THEME_SUMMARY_VERSION,
        },
        "taxonomy": categories.TAXONOMY,
        "category_inputs": category_inputs,
        "categories": [categories.canonical_category(*i) for i in category_inputs],
        "entities": entities,
        "excluded": [cluster.is_excluded(e) for e in entities],
        "now": now.isoformat(),
        "signals": signals,
        "alias_operators": operators,
        "cluster_ids": {s["id"]: s.get("cluster_id") for s in working},
        "theme_ids": {s["id"]: s.get("theme_id") for s in working},
        "theme_heat": {
            t: cluster.compute_theme_heat(m, now=now, alias_map=alias_map)
            for t, m in by_theme.items()
        },
        "collectors": [collector_snapshot(c) for c in build_collectors(load_sources())],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(baseline, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {OUT}: {len(signals)} signals, {len(category_inputs)} category inputs, "
          f"{len(entities)} entities, {len(baseline['collectors'])} collectors")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Generate the baseline**

Run: `touch tests/fixtures/__init__.py && .venv/bin/python -m tests.fixtures.make_gambling_baseline`
Expected: `Wrote tests/fixtures/gambling_baseline.json: 336 signals, … collectors` (9 collectors).

- [ ] **Step 3: Write the equivalence test against today's API**

`tests/test_gambling_equivalence.py`:

```python
"""Gambling must behave exactly as it did before sectors existed. The
baseline was recorded from the pre-sector code (tests/fixtures/
make_gambling_baseline.py); every assertion compares against it."""

import copy
import json
import os
from datetime import datetime
from pathlib import Path

import pytest

from src import categories, cluster, score
from src.entities import build_alias_map

BASE = json.loads(Path("tests/fixtures/gambling_baseline.json").read_text(encoding="utf-8"))
NOW = datetime.fromisoformat(BASE["now"])


def test_prompts_are_identical():
    assert score.SYSTEM_PROMPT == BASE["prompts"]["system"]
    assert score.CLUSTER_SYSTEM_PROMPT == BASE["prompts"]["cluster"]
    assert score.THEME_SYSTEM_PROMPT == BASE["prompts"]["theme"]


def test_summary_versions_are_identical():
    assert score.CLUSTER_SUMMARY_VERSION == BASE["versions"]["cluster"]
    assert score.THEME_SUMMARY_VERSION == BASE["versions"]["theme"]


def test_taxonomy_is_identical():
    assert categories.TAXONOMY == BASE["taxonomy"]


def test_categories_are_identical():
    got = [categories.canonical_category(*i) for i in BASE["category_inputs"]]
    assert got == BASE["categories"]


def test_exclusions_are_identical():
    assert [cluster.is_excluded(e) for e in BASE["entities"]] == BASE["excluded"]


def test_clusters_and_themes_are_identical():
    working = copy.deepcopy(BASE["signals"])
    alias_map = build_alias_map(BASE["alias_operators"])
    cluster.assign_clusters(working, now=NOW, alias_map=alias_map)
    cluster.assign_themes(working, now=NOW, alias_map=alias_map)
    assert {s["id"]: s.get("cluster_id") for s in working} == BASE["cluster_ids"]
    assert {s["id"]: s.get("theme_id") for s in working} == BASE["theme_ids"]


def test_collectors_are_identical(monkeypatch):
    monkeypatch.setenv("COMPANIES_HOUSE_API_KEY", "baseline-test-key")
    from src.pipeline import build_collectors, load_sources
    from tests.fixtures.make_gambling_baseline import collector_snapshot

    got = [collector_snapshot(c) for c in build_collectors(load_sources())]
    assert got == BASE["collectors"]
```

- [ ] **Step 4: Run it. It must pass against the unchanged code**

Run: `.venv/bin/python -m pytest tests/test_gambling_equivalence.py -q`
Expected: `7 passed`.

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures tests/test_gambling_equivalence.py
git commit -m "Record gambling baseline before the sector refactor

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_016YJv2T4yhVoixtyDTkv1fZ"
```

---

### Task 2: Sector config and loader

**Files:**
- Create: `config/sectors/gambling.yaml`
- Create: `src/sectors.py`
- Test: `tests/test_sectors.py`

**Interfaces:**
- Produces:
  - `Sector`, a dataclass with these fields:
    - `slug: str`, `name: str`, `brief: str`, `prompt: dict[str, str]`;
    - `keywords: list[str]`, `companies: list[dict]`, `tickers: dict[str, str]`;
    - `categories: list[dict]`, where each item has the keys `name`, `pattern` and `before`;
    - `signal_type_fallback: dict[str, str]`, `excluded_bodies: list[str]`, `sources: dict[str, dict]`;
    - `created_at: str | None`.
  - `Sector`'s path properties: `data_dir`, `signals_path`, `run_status_path`, `archive_dir`, `archive_ids_path`.
  - `SectorConfigError(ValueError)`.
  - `load_sector(slug: str, config_dir: Path | None = None) -> Sector`.
  - `list_sector_slugs(config_dir: Path | None = None) -> list[str]`.
  - `update_index(slug: str, **fields) -> None` and `refresh_index(slugs: list[str]) -> None`.
  - The module globals `CONFIG_DIR = Path("config/sectors")`, `DATA_DIR = Path("data")`, `INDEX_PATH = DATA_DIR / "sectors.json"`. They are read at call time, so tests can monkeypatch them.
  - `PROMPT_FIELDS`, `KNOWN_SOURCES`.
- Consumes: `src.categories.CORE_RULE_NAMES` (a `set[str]`), which Task 3 creates. Until then, Step 3 defines a temporary local copy (see the note there).

- [ ] **Step 1: Create `config/sectors/gambling.yaml`**

Copy the values verbatim from `config/sources.yaml` and `config/watchlist.yaml`, including their comments. The `pattern` strings are exactly the regexes in today's `src/categories.py` `_RULES`. The `excluded_bodies` are the gambling-specific entries of today's `EXCLUDED_ENTITIES`; the generic UK institutions stay in code (Task 4).

```yaml
# The gambling sector. Hand-curated; dashboard additions go to
# gambling.user.yaml so the app never edits this file.
slug: gambling
name: Gambling & gaming
brief: >-
  A B2B newsroom covering the UK gambling and gaming sector: operators,
  suppliers, affiliates and the regulators around them.

# Sector wording slotted into the Claude prompts (src/score.py). These are
# today's exact phrases: changing any of them changes every score.
prompt:
  newsroom: B2B gambling-industry newsroom
  coverage: the UK gambling and gaming sector
  audience: specialist B2B gambling audience
  materiality: A small operator's confirmation statement can matter here even if it would never make national news.
  key_players: operators, suppliers or affiliates
  entity_hint: operator or company names mentioned
  company_word: operator
  significance_audience: specialist gambling newsroom
  theme_scope: the UK gambling sector

# Default search terms for keyword sources; a source's own `keywords` wins.
keywords: ["gambling", "betting", "bookmaker", "casino", "bingo", "gaming"]

companies:
  - name: "bet365 Group Limited"
    company_number: "04241161"
    aliases: ["bet365", "Hillside"]
    notes: "Clean single group entity. Privately held (Denise Coates)."
  - name: "Entain Holdings (UK) Limited"
    company_number: "11159638"
    aliases: ["Ladbrokes", "Coral", "bwin", "partypoker", "Gala", "Entain"]
    notes: "Entain plc itself is Isle of Man registered and shows at CH only as overseas company FC037925. Track the UK holding co, 11159638, for real filings."
  - name: "Ladbrokes Coral Group Limited"
    company_number: "00566221"
    aliases: ["Ladbrokes", "Coral"]
    notes: "Group entity under Entain. Operating co is Ladbrokes Betting & Gaming Limited, 00775667."
  - name: "William Hill Limited"
    company_number: "04212563"
    aliases: ["William Hill", "888", "Mr Green", "evoke"]
    notes: "Principal group entity. Long-standing operating co is William Hill Organization Limited, 00278208. Parent evoke being acquired by Bally's Intralot (agreed 5 June 2026)."
  - name: "Betfair Limited"
    company_number: "05140986"
    aliases: ["Betfair", "Paddy Power", "Flutter"]
    notes: "Flutter UK entity. Sky Bet files under Bonne Terre Limited and Paddy Power GB retail under Power Leisure Bookmakers Limited, both still to resolve. Flutter plc is Irish-domiciled, NYSE-listed, so no standard UK accounts."

tickers:
  ENT: "Entain"
  FLTR: "Flutter Entertainment"
  EVOK: "evoke"
  RNK: "Rank Group"

# Gambling-only categories, on top of the core set in src/categories.py.
# `before` places each rule ahead of a core rule; listed order is kept, so
# these four sit between Insolvency and Enforcement action, as before.
categories:
  - name: "Illegal gambling"
    pattern: "illegal|black market|unlicensed|untaxed"
    before: "Enforcement action"
  - name: "Advertising ruling"
    pattern: 'advertis|\basa\b|marketing standard|promotion'
    before: "Enforcement action"
  - name: "Player protection"
    pattern: "social responsib|player protect|safer gambling|problem gambling|self.?exclu|affordability|harm"
    before: "Enforcement action"
  - name: "Licence action"
    pattern: "licen[cs]e|licensing"
    before: "Enforcement action"

signal_type_fallback:
  regulatory: "Licence action"

# Gambling bodies that anchor nothing; generic UK institutions are excluded
# for every sector in src/cluster.py.
excluded_bodies:
  - "gambling commission"
  - "ukgc"
  - "dcms"
  - "department for culture, media and sport"
  - "department for culture media and sport"
  - "department for digital, culture, media and sport"
  - "department for digital culture media and sport"
  - "dcms select committee"
  - "betting and gaming council"
  - "bgc"
  - "illegal gambling taskforce"
  - "british horseracing authority"
  - "bha"
  - "horserace betting levy board"
  - "gamble aware"
  - "gambleaware"
  - "gamcare"

# Collectors in pipeline order. Present = enabled.
sources:
  gambling_commission:
    listing_pages:
      - url: "https://www.gamblingcommission.gov.uk/news"
        signal_type: regulatory
      - url: "https://www.gamblingcommission.gov.uk/news/enforcement-action"
        signal_type: enforcement
      - url: "https://www.gamblingcommission.gov.uk/public-register/regulatory-actions/full"
        signal_type: enforcement
  companies_house:
    items_per_page: 25
    sleep_seconds: 0.6   # politeness between watchlist companies, well within the 600 req/5min limit
    # The API returns the most recent N filings whatever their age, so without a
    # date bound the first run back-fills a decade of routine accounts and
    # confirmation statements — each paying for a scoring call and padding out
    # the company's cluster with nothing to report.
    lookback_days: 365
  gazette:
    results_per_term: 20
    sleep_seconds: 1.0
  dcms:
    organisation: "department-for-culture-media-and-sport"
    keywords: ["gambling", "betting"]
    results_per_term: 20
  parliament:
    keywords: ["gambling", "betting"]
    results_per_term: 20
  asa:
    keywords: ["gambling", "betting"]
  bgc:
    pages: 2
  insolvency_service:
    sleep_seconds: 1.0
  lse_rns:
    # Routine corporate-action announcements, matched case-insensitively as
    # substrings of the RNS headline. These accounted for roughly half of all
    # RNS items and scored in the teens and twenties — pure cluster volume with
    # no story in them. Delete a line to start collecting that kind again.
    skip_titles:
      - "holding(s) in company"
      - "notification of major holdings"
      - "director/pdmr shareholding"
      - "transaction in own shares"
      - "total voting rights"
      - "block listing"
```

- [ ] **Step 2: Write the failing tests**

`tests/test_sectors.py`:

```python
from pathlib import Path

import pytest
import yaml

from src import sectors
from src.sectors import SectorConfigError, list_sector_slugs, load_sector

MINIMAL = {
    "slug": "fintech",
    "name": "Fintech",
    "brief": "UK fintech and payments.",
    "prompt": {f: f"{f} text" for f in sectors.PROMPT_FIELDS},
    "sources": {"gazette": {}},
}


def write(dir_: Path, name: str, data) -> None:
    (dir_ / name).write_text(yaml.safe_dump(data), encoding="utf-8")


class TestGambling:
    def test_loads(self):
        s = load_sector("gambling")
        assert s.slug == "gambling"
        assert s.name == "Gambling & gaming"
        assert [c["name"] for c in s.companies][:2] == [
            "bet365 Group Limited", "Entain Holdings (UK) Limited"]
        assert s.tickers["RNK"] == "Rank Group"
        assert list(s.sources) == [
            "gambling_commission", "companies_house", "gazette", "dcms",
            "parliament", "asa", "bgc", "insolvency_service", "lse_rns"]

    def test_paths(self):
        s = load_sector("gambling")
        assert s.signals_path == Path("data/gambling/signals.json")
        assert s.run_status_path == Path("data/gambling/run_status.json")
        assert s.archive_ids_path == Path("data/gambling/archive/ids.json")


class TestValidation:
    def test_minimal_config_loads(self, tmp_path):
        write(tmp_path, "fintech.yaml", MINIMAL)
        s = load_sector("fintech", config_dir=tmp_path)
        assert s.keywords == [] and s.companies == [] and s.categories == []

    @pytest.mark.parametrize("field", ["slug", "name", "brief", "prompt", "sources"])
    def test_required_fields(self, tmp_path, field):
        write(tmp_path, "fintech.yaml", {k: v for k, v in MINIMAL.items() if k != field})
        with pytest.raises(SectorConfigError, match=field):
            load_sector("fintech", config_dir=tmp_path)

    def test_slug_must_match_filename(self, tmp_path):
        write(tmp_path, "fintech.yaml", {**MINIMAL, "slug": "payments"})
        with pytest.raises(SectorConfigError, match="slug"):
            load_sector("fintech", config_dir=tmp_path)

    def test_prompt_needs_every_field(self, tmp_path):
        prompt = dict(MINIMAL["prompt"]); prompt.pop("newsroom")
        write(tmp_path, "fintech.yaml", {**MINIMAL, "prompt": prompt})
        with pytest.raises(SectorConfigError, match="newsroom"):
            load_sector("fintech", config_dir=tmp_path)

    def test_unknown_source_rejected(self, tmp_path):
        write(tmp_path, "fintech.yaml", {**MINIMAL, "sources": {"fca_scraper": {}}})
        with pytest.raises(SectorConfigError, match="fca_scraper"):
            load_sector("fintech", config_dir=tmp_path)

    def test_bad_category_regex_rejected(self, tmp_path):
        cats = [{"name": "Crypto", "pattern": "crypto(", "before": "Enforcement action"}]
        write(tmp_path, "fintech.yaml", {**MINIMAL, "categories": cats})
        with pytest.raises(SectorConfigError, match="categories"):
            load_sector("fintech", config_dir=tmp_path)

    def test_category_before_must_be_core(self, tmp_path):
        cats = [{"name": "Crypto", "pattern": "crypto", "before": "Nonsense"}]
        write(tmp_path, "fintech.yaml", {**MINIMAL, "categories": cats})
        with pytest.raises(SectorConfigError, match="before"):
            load_sector("fintech", config_dir=tmp_path)

    def test_unquoted_company_number_rejected(self, tmp_path):
        # YAML reads 04241161 as the int 4241161, losing the leading zero.
        (tmp_path / "fintech.yaml").write_text(
            yaml.safe_dump({**MINIMAL}) + "companies:\n  - name: X Ltd\n    company_number: 04241161\n",
            encoding="utf-8")
        with pytest.raises(SectorConfigError, match="company_number"):
            load_sector("fintech", config_dir=tmp_path)

    def test_error_names_the_file(self, tmp_path):
        write(tmp_path, "fintech.yaml", {k: v for k, v in MINIMAL.items() if k != "name"})
        with pytest.raises(SectorConfigError, match="fintech.yaml"):
            load_sector("fintech", config_dir=tmp_path)

    def test_missing_file(self, tmp_path):
        with pytest.raises(SectorConfigError, match="not found"):
            load_sector("nope", config_dir=tmp_path)


class TestUserAdditions:
    def test_companies_key_is_merged(self, tmp_path):
        write(tmp_path, "fintech.yaml", MINIMAL)
        write(tmp_path, "fintech.user.yaml", {"companies": [{"name": "Monzo Bank Ltd"}]})
        assert [c["name"] for c in load_sector("fintech", config_dir=tmp_path).companies] == ["Monzo Bank Ltd"]

    def test_dashboard_operators_key_is_merged(self, tmp_path):
        # The dashboard's watchlist form writes {"operators": [...]}.
        write(tmp_path, "fintech.yaml", {**MINIMAL, "companies": [{"name": "A Ltd"}]})
        write(tmp_path, "fintech.user.yaml", {"operators": [{"name": "B Ltd", "company_number": None}]})
        names = [c["name"] for c in load_sector("fintech", config_dir=tmp_path).companies]
        assert names == ["A Ltd", "B Ltd"]


class TestListing:
    def test_lists_slugs_without_user_files(self, tmp_path):
        write(tmp_path, "fintech.yaml", MINIMAL)
        write(tmp_path, "fintech.user.yaml", {"companies": []})
        write(tmp_path, "gambling.yaml", {**MINIMAL, "slug": "gambling"})
        assert list_sector_slugs(config_dir=tmp_path) == ["fintech", "gambling"]


class TestIndex:
    def test_update_index_merges_fields(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sectors, "INDEX_PATH", tmp_path / "sectors.json")
        sectors.update_index("gambling", name="Gambling & gaming", status="ready", signal_count=3)
        sectors.update_index("gambling", status="error", error="boom")
        index = sectors.read_index()
        assert index["gambling"] == {"slug": "gambling", "name": "Gambling & gaming",
                                     "status": "error", "signal_count": 3, "error": "boom"}

    def test_refresh_index_marks_new_sectors_setting_up(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sectors, "INDEX_PATH", tmp_path / "sectors.json")
        monkeypatch.setattr(sectors, "CONFIG_DIR", tmp_path)
        write(tmp_path, "fintech.yaml", MINIMAL)
        sectors.refresh_index(["fintech"])
        entry = sectors.read_index()["fintech"]
        assert entry["status"] == "setting_up" and entry["name"] == "Fintech"
```

- [ ] **Step 3: Run the tests to confirm they fail**

Run: `.venv/bin/python -m pytest tests/test_sectors.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.sectors'`.

- [ ] **Step 4: Implement `src/sectors.py`**

```python
"""Sectors: one config file per sector (config/sectors/<slug>.yaml) defining
what the pipeline collects, how Claude scores it, and what counts as a company.
Dashboard additions live beside it in <slug>.user.yaml, so the app never edits
the hand-curated file. Data for each sector lives under data/<slug>/."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

CONFIG_DIR = Path("config/sectors")
DATA_DIR = Path("data")
INDEX_PATH = DATA_DIR / "sectors.json"

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")

# Sector wording slotted into the Claude prompts; see src/score.py.
PROMPT_FIELDS = (
    "newsroom", "coverage", "audience", "materiality", "key_players",
    "entity_hint", "company_word", "significance_audience", "theme_scope",
)

KNOWN_SOURCES = (
    "gambling_commission", "companies_house", "gazette", "dcms", "parliament",
    "asa", "bgc", "insolvency_service", "lse_rns",
)


class SectorConfigError(ValueError):
    """A sector config that can't be used, naming the file and the field."""

    def __init__(self, path: Path, field_name: str, message: str):
        super().__init__(f"{path}: {field_name}: {message}")
        self.path = path
        self.field_name = field_name


@dataclass
class Sector:
    slug: str
    name: str
    brief: str
    prompt: dict[str, str]
    sources: dict[str, dict]
    keywords: list[str] = field(default_factory=list)
    companies: list[dict] = field(default_factory=list)
    tickers: dict[str, str] = field(default_factory=dict)
    categories: list[dict] = field(default_factory=list)
    signal_type_fallback: dict[str, str] = field(default_factory=dict)
    excluded_bodies: list[str] = field(default_factory=list)
    created_at: str | None = None

    @property
    def data_dir(self) -> Path:
        return DATA_DIR / self.slug

    @property
    def signals_path(self) -> Path:
        return self.data_dir / "signals.json"

    @property
    def run_status_path(self) -> Path:
        return self.data_dir / "run_status.json"

    @property
    def archive_dir(self) -> Path:
        return self.data_dir / "archive"

    @property
    def archive_ids_path(self) -> Path:
        return self.archive_dir / "ids.json"


def _read_yaml(path: Path) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        raise SectorConfigError(path, "yaml", str(exc)) from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise SectorConfigError(path, "yaml", "top level must be a mapping")
    return data


def _companies(path: Path, items, where: str) -> list[dict]:
    if items is None:
        return []
    if not isinstance(items, list):
        raise SectorConfigError(path, where, "must be a list")
    out = []
    for i, company in enumerate(items):
        if not isinstance(company, dict) or not str(company.get("name") or "").strip():
            raise SectorConfigError(path, f"{where}[{i}].name", "each company needs a name")
        number = company.get("company_number")
        if number is not None and not isinstance(number, str):
            raise SectorConfigError(
                path, f"{where}[{i}].company_number",
                "must be a quoted string (YAML drops the leading zeros of a bare number)")
        out.append(company)
    return out


def _build(path: Path, raw: dict, user: dict, user_path: Path) -> Sector:
    from src.categories import CORE_RULE_NAMES, OTHER

    for key in ("slug", "name", "brief", "prompt", "sources"):
        if key not in raw or raw[key] in (None, "", {}, []):
            raise SectorConfigError(path, key, "is required")

    slug = raw["slug"]
    if slug != path.stem or not SLUG_RE.match(str(slug)):
        raise SectorConfigError(path, "slug", f"must match the filename ({path.stem}) and be [a-z0-9-]")

    prompt = raw["prompt"]
    if not isinstance(prompt, dict):
        raise SectorConfigError(path, "prompt", "must be a mapping")
    for key in PROMPT_FIELDS:
        if not isinstance(prompt.get(key), str) or not prompt[key].strip():
            raise SectorConfigError(path, f"prompt.{key}", "is required")

    sources = raw["sources"]
    if not isinstance(sources, dict):
        raise SectorConfigError(path, "sources", "must be a mapping")
    for key, settings in sources.items():
        if key not in KNOWN_SOURCES:
            raise SectorConfigError(path, f"sources.{key}", f"unknown source (known: {', '.join(KNOWN_SOURCES)})")
        if settings is not None and not isinstance(settings, dict):
            raise SectorConfigError(path, f"sources.{key}", "settings must be a mapping")
    sources = {k: (v or {}) for k, v in sources.items()}

    categories = raw.get("categories") or []
    names = set()
    for i, cat in enumerate(categories):
        where = f"categories[{i}]"
        if not isinstance(cat, dict) or not cat.get("name") or not cat.get("pattern"):
            raise SectorConfigError(path, where, "needs name and pattern")
        if cat.get("before") not in CORE_RULE_NAMES:
            raise SectorConfigError(path, f"{where}.before", f"must name a core category rule, got {cat.get('before')!r}")
        try:
            re.compile(cat["pattern"], re.I)
        except re.error as exc:
            raise SectorConfigError(path, f"{where}.pattern", f"invalid regex: {exc}") from exc
        names.add(cat["name"])

    fallback = raw.get("signal_type_fallback") or {}
    allowed = CORE_RULE_NAMES | names | {OTHER}
    for key, value in fallback.items():
        if value not in allowed:
            raise SectorConfigError(path, f"signal_type_fallback.{key}", f"unknown category {value!r}")

    for key, kind in (("keywords", list), ("excluded_bodies", list), ("tickers", dict)):
        if raw.get(key) is not None and not isinstance(raw[key], kind):
            raise SectorConfigError(path, key, f"must be a {kind.__name__}")

    companies = _companies(path, raw.get("companies"), "companies")
    # The dashboard's watchlist form writes "operators"; accept both.
    for key in ("companies", "operators"):
        companies += _companies(user_path, user.get(key), key)

    return Sector(
        slug=slug,
        name=raw["name"],
        brief=str(raw["brief"]).strip(),
        prompt={k: prompt[k] for k in PROMPT_FIELDS},
        sources=sources,
        keywords=list(raw.get("keywords") or []),
        companies=companies,
        tickers=dict(raw.get("tickers") or {}),
        categories=list(categories),
        signal_type_fallback=dict(fallback),
        excluded_bodies=list(raw.get("excluded_bodies") or []),
        created_at=raw.get("created_at"),
    )


def load_sector(slug: str, config_dir: Path | None = None) -> Sector:
    config_dir = config_dir or CONFIG_DIR
    path = config_dir / f"{slug}.yaml"
    if not path.exists():
        raise SectorConfigError(path, "file", "not found")
    user_path = config_dir / f"{slug}.user.yaml"
    user = _read_yaml(user_path) if user_path.exists() else {}
    return _build(path, _read_yaml(path), user, user_path)


def list_sector_slugs(config_dir: Path | None = None) -> list[str]:
    config_dir = config_dir or CONFIG_DIR
    return sorted(
        p.stem for p in config_dir.glob("*.yaml") if not p.name.endswith(".user.yaml")
    )


def read_index() -> dict[str, dict]:
    if not INDEX_PATH.exists():
        return {}
    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        return {e["slug"]: e for e in json.load(f)}


def _write_index(index: dict[str, dict]) -> None:
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump([index[k] for k in sorted(index)], f, indent=2, ensure_ascii=False)


def update_index(slug: str, **fields) -> None:
    """Merge fields into a sector's index entry (data/sectors.json)."""
    index = read_index()
    entry = index.get(slug, {"slug": slug})
    entry.update(fields)
    index[slug] = entry
    _write_index(index)


def refresh_index(slugs: list[str]) -> None:
    """Make sure every configured sector has an entry; new ones start as
    setting_up until their first run lands."""
    index = read_index()
    for slug in slugs:
        if slug in index:
            continue
        try:
            sector = load_sector(slug)
            index[slug] = {"slug": slug, "name": sector.name, "brief": sector.brief,
                           "created_at": sector.created_at, "status": "setting_up"}
        except SectorConfigError as exc:
            index[slug] = {"slug": slug, "status": "error", "error": str(exc)}
    _write_index(index)
```

**Note on `CORE_RULE_NAMES`:** it comes from Task 3. If you run this task's tests before Task 3, temporarily add these lines to `src/categories.py` (Task 3 replaces them):

```python
CORE_RULE_NAMES = {AML, DISQUALIFICATION, INSOLVENCY, ENFORCEMENT, MERGER, SHAREHOLDING,
                   BOARD, TAX, CONSULTATION, RESULTS, CORPORATE_FILING, POLICY}
```

- [ ] **Step 5: Run the tests**

Run: `.venv/bin/python -m pytest tests/test_sectors.py tests/test_gambling_equivalence.py -q`
Expected: all pass (the equivalence test is untouched).

- [ ] **Step 6: Commit**

```bash
git add config/sectors/gambling.yaml src/sectors.py src/categories.py tests/test_sectors.py
git commit -m "Add sector configs and loader, with gambling as the first sector

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_016YJv2T4yhVoixtyDTkv1fZ"
```

---

### Task 3: Per-sector categories

**Files:**
- Modify: `src/categories.py` (rewrite)
- Modify: `tests/test_categories.py`, `tests/test_gambling_equivalence.py`

**Interfaces:**
- Consumes: `load_sector("gambling")` (Task 2).
- Produces:
  - The core name constants (`AML`, `INSOLVENCY`, … `OTHER`), plus the gambling-only name constants `ILLEGAL`, `ADVERTISING`, `PLAYER_PROTECTION`, `LICENCE`, which stay as plain strings for compatibility.
  - `CORE_RULE_NAMES: set[str]`.
  - `Ruleset(taxonomy: list[str], rules: list[tuple[str, re.Pattern]], fallback: dict[str, str])`.
  - `ruleset(sector=None) -> Ruleset`, cached per slug.
  - `taxonomy(sector=None) -> list[str]`.
  - `canonical_category(category, title="", signal_type=None, sector=None) -> str`.
  - `category_of(signal, sector=None) -> str`.
  - `default_sector()`, which returns the cached gambling `Sector`.
  - The module-level `TAXONOMY` constant is **removed**.

- [ ] **Step 1: Update the equivalence test to the new API (it now fails)**

In `tests/test_gambling_equivalence.py`, replace `test_taxonomy_is_identical` and `test_categories_are_identical` with:

```python
def test_taxonomy_is_identical():
    gambling = load_sector("gambling")
    assert categories.taxonomy() == BASE["taxonomy"]
    assert categories.taxonomy(gambling) == BASE["taxonomy"]


def test_categories_are_identical():
    gambling = load_sector("gambling")
    assert [categories.canonical_category(*i) for i in BASE["category_inputs"]] == BASE["categories"]
    assert [categories.canonical_category(*i, sector=gambling) for i in BASE["category_inputs"]] == BASE["categories"]
```

Add `from src.sectors import load_sector` to its imports.

- [ ] **Step 2: Add a fintech-shaped test to `tests/test_categories.py`**

Change `TAXONOMY` uses in that file to `taxonomy()` (import it), then append:

```python
from src.categories import ruleset, taxonomy
from src.sectors import Sector


def _fintech(**overrides):
    base = dict(slug="fintech", name="Fintech", brief="b",
                prompt={}, sources={"gazette": {}},
                categories=[{"name": "Crypto", "pattern": "crypto|stablecoin",
                             "before": "Enforcement action"}])
    base.update(overrides)
    return Sector(**base)


class TestSectorCategories:
    def test_sector_category_matches_before_core(self):
        assert canonical_category("stablecoin enforcement", sector=_fintech()) == "Crypto"

    def test_gambling_only_categories_absent_elsewhere(self):
        t = taxonomy(_fintech())
        assert "Illegal gambling" not in t and "Crypto" in t and t[-1] == OTHER

    def test_core_fallback_for_regulatory_is_other(self):
        assert canonical_category(None, "Untitled", "regulatory", sector=_fintech()) == OTHER

    def test_gambling_overrides_regulatory_fallback(self):
        assert canonical_category(None, "Untitled", "regulatory") == LICENCE

    def test_ruleset_is_cached_per_slug(self):
        assert ruleset(_fintech()) is ruleset(_fintech())
```

- [ ] **Step 3: Run the tests to confirm they fail**

Run: `.venv/bin/python -m pytest tests/test_categories.py tests/test_gambling_equivalence.py -q`
Expected: FAIL (`taxonomy`/`ruleset` not defined).

- [ ] **Step 4: Rewrite `src/categories.py`**

Keep the module docstring as it is, adding one paragraph at the end:

> Categories are per sector. A core set, below, applies everywhere. A sector's config adds its own categories, each slotted in ahead of a named core rule (`before`), so rule priority is under the sector's control. Gambling's additions — Illegal gambling, Advertising ruling, Player protection, Licence action — live in config/sectors/gambling.yaml.

Then replace everything after the docstring with:

```python
import re
from dataclasses import dataclass
from functools import lru_cache

AML = "AML and compliance failures"
BOARD = "Board and director changes"
CONSULTATION = "Consultation"
CORPORATE_FILING = "Corporate filing"
DISQUALIFICATION = "Director disqualification"
ENFORCEMENT = "Enforcement action"
RESULTS = "Financial results"
INSOLVENCY = "Insolvency"
MERGER = "Merger and acquisition"
POLICY = "Policy and legislation"
SHAREHOLDING = "Shareholding disclosure"
TAX = "Tax and levy"
OTHER = "Other"

# Gambling-only names, kept as constants for callers and tests; their rules
# live in config/sectors/gambling.yaml.
ADVERTISING = "Advertising ruling"
ILLEGAL = "Illegal gambling"
LICENCE = "Licence action"
PLAYER_PROTECTION = "Player protection"

# (theme, pattern) in priority order. Patterns run against the legacy category
# label first, and against the title only if the label decides nothing.
_CORE_RULES: list[tuple[str, re.Pattern]] = [
    (AML, re.compile(r"\baml\b|money laundering|anti-money", re.I)),
    (DISQUALIFICATION, re.compile(r"disqualif", re.I)),
    (INSOLVENCY, re.compile(
        r"insolven|winding.?up|wound.?up|liquidat|administrat|receivership|"
        r"creditors|dissolution|struck off", re.I)),
    (ENFORCEMENT, re.compile(
        r"enforcement|penalt|fine|sanction|settlement|regulatory action|"
        r"compliance failure|breach", re.I)),
    (MERGER, re.compile(
        r"acquisit|merger|takeover|scheme document|scheme of arrangement|"
        r"court meeting|divest|disposal|delisting|offer for|restructur", re.I)),
    (SHAREHOLDING, re.compile(
        r"shareholding|shareholder|share buyback|buy.?back|voting rights|"
        r"major holding|\bpdmr\b|\btr.?1\b|director dealing|issuance of shares",
        re.I)),
    (BOARD, re.compile(
        r"director (change|appointment|resignation)|board|directorate|"
        r"officer filing|\bpsc\b|person with significant", re.I)),
    (TAX, re.compile(r"\btax|duty|levy|\bhmrc\b|treasury", re.I)),
    (CONSULTATION, re.compile(r"consultation|call for evidence|white paper", re.I)),
    (RESULTS, re.compile(
        r"results|trading (update|statement)|earnings|interim|annual report|"
        r"\bagm\b|financial performance", re.I)),
    (CORPORATE_FILING, re.compile(
        r"accounts filing|confirmation statement|charge (filing|release)|"
        r"registered office|company filing|mortgage|capital", re.I)),
    (POLICY, re.compile(
        r"policy|legislat|parliament|debate|regulation|reform|speech|"
        r"select committee|statistics|government", re.I)),
]
CORE_RULE_NAMES = {name for name, _ in _CORE_RULES}

# signal_type is a coarse fallback when nothing matches. A sector can
# override entries (gambling maps regulatory to Licence action).
_CORE_FALLBACK = {
    "insolvency": INSOLVENCY,
    "enforcement": ENFORCEMENT,
    "consultation": CONSULTATION,
    "corporate_filing": CORPORATE_FILING,
    "policy": POLICY,
    "regulatory": OTHER,
}


@dataclass(frozen=True)
class Ruleset:
    taxonomy: list[str]
    rules: list[tuple[str, re.Pattern]]
    fallback: dict[str, str]


@lru_cache(maxsize=1)
def default_sector():
    """Gambling, the sector every sector=None call means."""
    from src.sectors import load_sector
    return load_sector("gambling")


_RULESETS: dict[str, Ruleset] = {}


def ruleset(sector=None) -> Ruleset:
    sector = sector or default_sector()
    cached = _RULESETS.get(sector.slug)
    if cached is not None:
        return cached
    rules = list(_CORE_RULES)
    for cat in sector.categories:
        position = next(i for i, (name, _) in enumerate(rules) if name == cat["before"])
        rules.insert(position, (cat["name"], re.compile(cat["pattern"], re.I)))
    names = sorted(CORE_RULE_NAMES | {cat["name"] for cat in sector.categories})
    built = Ruleset(
        taxonomy=names + [OTHER],
        rules=rules,
        fallback={**_CORE_FALLBACK, **sector.signal_type_fallback},
    )
    _RULESETS[sector.slug] = built
    return built


def taxonomy(sector=None) -> list[str]:
    return list(ruleset(sector).taxonomy)


def canonical_category(
    category: str | None,
    title: str = "",
    signal_type: str | None = None,
    sector=None,
) -> str:
    """Map a signal onto its sector's taxonomy. Already-canonical values pass
    straight through, so re-running this is a no-op."""
    rs = ruleset(sector)
    if category:
        lookup = {t.lower(): t for t in rs.taxonomy}
        exact = lookup.get(category.strip().lower())
        if exact:
            return exact

    for text in (category or "", title or ""):
        if not text.strip():
            continue
        for theme, pattern in rs.rules:
            if pattern.search(text):
                return theme

    return rs.fallback.get(signal_type or "", OTHER)


def category_of(signal: dict, sector=None) -> str:
    """Canonical theme for a stored signal, preferring the value the pipeline
    already resolved so the dashboard doesn't recompute it every render."""
    resolved = signal.get("canonical_category")
    if resolved:
        return resolved
    return canonical_category(
        signal.get("category"), signal.get("title", ""), signal.get("signal_type"),
        sector=sector,
    )
```

`src/score.py` imports `TAXONOMY`. Change that import to `from src.categories import canonical_category, taxonomy`, and change `_CATEGORY_LIST` to `"\n".join(f"  - {c}" for c in taxonomy())`. Task 5 reworks this properly.

- [ ] **Step 5: Run the tests**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: all pass, including all 7 equivalence tests.

- [ ] **Step 6: Commit**

```bash
git add src/categories.py src/score.py tests/test_categories.py tests/test_gambling_equivalence.py
git commit -m "Make categories per sector; gambling-only rules move to its config

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_016YJv2T4yhVoixtyDTkv1fZ"
```

---

### Task 4: Per-sector exclusions in clustering

**Files:**
- Modify: `src/cluster.py`
- Modify: `tests/test_cluster.py`, `tests/test_themes.py`, `tests/test_gambling_equivalence.py`

**Interfaces:**
- Consumes: `default_sector()` and `category_of(signal, sector)` (Task 3).
- Produces:
  - `SHARED_EXCLUDED: frozenset[str]` and `excluded_entities(sector=None) -> frozenset[str]`.
  - `is_excluded(name, sector=None)`.
  - `assign_clusters(..., sector=None)`, `assign_themes(..., sector=None)` and `compute_theme_heat(..., sector=None)`.
  - `EXCLUDED_ENTITIES` is **removed**.

- [ ] **Step 1: Extend the equivalence test**

In `tests/test_gambling_equivalence.py`, replace `test_exclusions_are_identical` and `test_clusters_and_themes_are_identical` with:

```python
def test_exclusions_are_identical():
    gambling = load_sector("gambling")
    assert [cluster.is_excluded(e) for e in BASE["entities"]] == BASE["excluded"]
    assert [cluster.is_excluded(e, gambling) for e in BASE["entities"]] == BASE["excluded"]


@pytest.mark.parametrize("explicit", [False, True])
def test_clusters_and_themes_are_identical(explicit):
    sector = load_sector("gambling") if explicit else None
    working = copy.deepcopy(BASE["signals"])
    alias_map = build_alias_map(BASE["alias_operators"])
    cluster.assign_clusters(working, now=NOW, alias_map=alias_map, sector=sector)
    cluster.assign_themes(working, now=NOW, alias_map=alias_map, sector=sector)
    assert {s["id"]: s.get("cluster_id") for s in working} == BASE["cluster_ids"]
    assert {s["id"]: s.get("theme_id") for s in working} == BASE["theme_ids"]
    by_theme = {}
    for s in working:
        if s.get("theme_id"):
            by_theme.setdefault(s["theme_id"], []).append(s)
    assert {t: cluster.compute_theme_heat(m, now=NOW, alias_map=alias_map, sector=sector)
            for t, m in by_theme.items()} == pytest.approx(BASE["theme_heat"])
```

Append to `tests/test_cluster.py`:

```python
from src.sectors import Sector


def _fintech():
    return Sector(slug="fintech", name="Fintech", brief="b", prompt={},
                  sources={"gazette": {}}, excluded_bodies=["financial ombudsman service"])


class TestSectorExclusions:
    def test_shared_institutions_excluded_in_every_sector(self):
        assert is_excluded("HM Treasury", _fintech())
        assert is_excluded("Companies House", _fintech())

    def test_gambling_bodies_not_excluded_elsewhere(self):
        assert not is_excluded("Gambling Commission", _fintech())

    def test_sector_bodies_excluded(self):
        assert is_excluded("Financial Ombudsman Service", _fintech())
        assert not is_excluded("Financial Ombudsman Service")  # gambling default
```

- [ ] **Step 2: Run the tests to confirm they fail**

Run: `.venv/bin/python -m pytest tests/test_cluster.py tests/test_gambling_equivalence.py -q`
Expected: FAIL (`sector` is not a parameter).

- [ ] **Step 3: Implement in `src/cluster.py`**

Change the categories import to `from src.categories import OTHER, category_of, default_sector`.

Replace `EXCLUDED_ENTITIES` and `is_excluded` with the following. Keep the existing explanatory comment above it, generalised to say that sector-specific bodies come from each sector's `excluded_bodies`.

```python
# Generic UK institutions, excluded in every sector. Each sector's config adds
# its own regulators and trade bodies (excluded_bodies). Matched against the
# canonical form, so both the bare and expanded names need listing.
SHARED_EXCLUDED = frozenset({
    "hmrc",
    "hm revenue & customs",
    "hm revenue and customs",
    "hm treasury",
    "treasury",
    "companies house",
    "the gazette",
    "gazette",
    "advertising standards authority",
    "asa",
    "cap",
    "committee of advertising practice",
    "insolvency service",
    "financial conduct authority",
    "fca",
    "parliament",
    "uk parliament",
    "house of commons",
    "house of lords",
    "government",
    "uk government",
    "cabinet office",
    "home office",
})

_EXCLUDED_BY_SECTOR: dict[str, frozenset[str]] = {}


def excluded_entities(sector=None) -> frozenset[str]:
    sector = sector or default_sector()
    cached = _EXCLUDED_BY_SECTOR.get(sector.slug)
    if cached is None:
        cached = SHARED_EXCLUDED | {b.strip().lower() for b in sector.excluded_bodies}
        _EXCLUDED_BY_SECTOR[sector.slug] = cached
    return cached


def is_excluded(name: str, sector=None) -> bool:
    """True for institutions that shouldn't anchor or label a cluster."""
    excluded = excluded_entities(sector)
    return match_key(name) in excluded or name.strip().lower() in excluded
```

Add `sector=None` as the last keyword parameter of `assign_clusters`, `assign_themes` and `compute_theme_heat`. Inside them:
- pass it to every `is_excluded(e)` call, making it `is_excluded(e, sector)` (lines ~180, ~187, ~263, ~285);
- in `assign_themes`, change `category_of(s)` to `category_of(s, sector)`.

- [ ] **Step 4: Fix the baseline generator's import**

`tests/fixtures/make_gambling_baseline.py` references `cluster.EXCLUDED_ENTITIES`. Replace it with `cluster.excluded_entities()`. The generator is historical, and this keeps it importable for `collector_snapshot`.

- [ ] **Step 5: Run all tests**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: all pass. `test_themes.py` needs no change, because its defaults still mean gambling.

- [ ] **Step 6: Commit**

```bash
git add src/cluster.py tests/test_cluster.py tests/test_gambling_equivalence.py tests/fixtures/make_gambling_baseline.py
git commit -m "Exclude institutions per sector in clustering and themes

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_016YJv2T4yhVoixtyDTkv1fZ"
```

---

### Task 5: Prompts rendered from the sector

**Files:**
- Modify: `src/score.py`
- Modify: `tests/test_gambling_equivalence.py`, `tests/test_normalise_and_score.py` (only if it references removed names)

**Interfaces:**
- Consumes: `taxonomy(sector)`, `canonical_category(..., sector=)`, `default_sector()`.
- Produces:
  - `system_prompt(sector=None)`, `cluster_prompt(sector=None)` and `theme_prompt(sector=None)`, each returning `str`.
  - `cluster_summary_version(sector=None)` and `theme_summary_version(sector=None)`, each returning `str`.
  - `score_signal(signal, client=None, alias_map=None, sector=None)`.
  - `summarize_cluster(members, client=None, sector=None)`.
  - `summarize_theme(theme, members, client=None, sector=None)`.
  - The constants `SYSTEM_PROMPT`, `CLUSTER_SYSTEM_PROMPT`, `THEME_SYSTEM_PROMPT`, `CLUSTER_SUMMARY_VERSION` and `THEME_SUMMARY_VERSION` are **removed**.

- [ ] **Step 1: Update the equivalence test**

Replace `test_prompts_are_identical` and `test_summary_versions_are_identical` with:

```python
@pytest.mark.parametrize("explicit", [False, True])
def test_prompts_are_identical(explicit):
    sector = load_sector("gambling") if explicit else None
    assert score.system_prompt(sector) == BASE["prompts"]["system"]
    assert score.cluster_prompt(sector) == BASE["prompts"]["cluster"]
    assert score.theme_prompt(sector) == BASE["prompts"]["theme"]


def test_summary_versions_are_identical():
    assert score.cluster_summary_version() == BASE["versions"]["cluster"]
    assert score.theme_summary_version() == BASE["versions"]["theme"]


def test_other_sectors_get_their_own_wording_and_versions():
    from src.sectors import PROMPT_FIELDS, Sector
    fintech = Sector(slug="fintech", name="Fintech", brief="b", sources={"gazette": {}},
                     prompt={**{f: f"<{f}>" for f in PROMPT_FIELDS},
                             "newsroom": "B2B fintech newsroom"})
    assert "B2B fintech newsroom" in score.system_prompt(fintech)
    assert "gambling" not in score.system_prompt(fintech).lower()
    assert score.cluster_summary_version(fintech) != score.cluster_summary_version()
```

- [ ] **Step 2: Run the tests to confirm they fail**

Run: `.venv/bin/python -m pytest tests/test_gambling_equivalence.py -q`
Expected: FAIL (`system_prompt` not defined).

- [ ] **Step 3: Template the prompts in `src/score.py`**

Replace everything from `_CATEGORY_LIST = …` down to (and including) `THEME_SUMMARY_VERSION = …` with the following. Each `$name` is a `string.Template` placeholder filled from `sector.prompt`. Everything else is today's text, character for character, and the equivalence test will flag any slip.

```python
from string import Template

from src.categories import canonical_category, default_sector, taxonomy

_SYSTEM_TEMPLATE = Template(
    "You are a signal-scoring assistant for a $newsroom. "
    "You are given one item from a public, regulatory or corporate source. "
    "Assess how newsworthy it is to journalists covering $coverage. You do not "
    "write articles. You return structured JSON only.\n\n"
    "Score for a $audience, not a general newsdesk. $materiality "
    "Reward items that name $key_players, involve enforcement or money, or "
    "signal a regulatory or policy shift. Extract entity names carefully; these "
    "drive a downstream pattern-detection layer.\n\n"
    "The category must be exactly one of these, copied verbatim. Free-text "
    "themes fragment the cross-company pattern detection downstream, so pick "
    "the closest match rather than inventing a better label. Use 'Other' only "
    "when genuinely none applies:\n"
    "$category_list\n\n"
    "Return exactly this JSON shape, no prose, no markdown fences:\n"
    "{\n"
    '  "newsworthiness_score": 0-100,\n'
    '  "signal_type": "regulatory|enforcement|consultation|corporate_filing|insolvency|policy",\n'
    '  "entities": ["$entity_hint"],\n'
    '  "category": "one value copied verbatim from the list above",\n'
    '  "why_it_matters": "one sentence, plain English, no more than 30 words"\n'
    "}"
)
```

Before using it, compare it with today's `SYSTEM_PROMPT`. The original's second paragraph reads `"Score for a specialist B2B gambling audience, not a general newsdesk. A small operator's confirmation statement can matter here even if it would never make national news. Reward items that name operators, suppliers or affiliates, involve enforcement or money, or signal a regulatory or policy shift. Extract entity names carefully; these drive a downstream pattern-detection layer."`

Likewise, `_HOUSE_STYLE` becomes `_HOUSE_STYLE_TEMPLATE`, today's text with one change: `"Name the operator, the regulator, the sum of "` becomes `"Name the $company_word, the regulator, the sum of "`.

`_CLUSTER_TEMPLATE` is today's `CLUSTER_SYSTEM_PROMPT`, with `_HOUSE_STYLE` replaced by a `$house_style` placeholder and three phrases replaced:

| Today | Placeholder |
|---|---|
| `"B2B gambling-industry newsroom"` | `$newsroom` |
| `"happen to name the same operator"` | `"happen to name the same $company_word"` |
| `"how much a specialist gambling newsroom should care"` | `"how much a $significance_audience should care"` |

`_THEME_TEMPLATE` is today's `THEME_SYSTEM_PROMPT`, with `_HOUSE_STYLE` replaced by `$house_style` and two phrases replaced:

| Today | Placeholder |
|---|---|
| `"B2B gambling-industry newsroom"` | `$newsroom` |
| `"across the UK gambling sector"` | `"across $theme_scope"` |

Then add:

```python
def _fields(sector) -> dict[str, str]:
    sector = sector or default_sector()
    fields = dict(sector.prompt)
    fields["house_style"] = _HOUSE_STYLE_TEMPLATE.substitute(fields)
    fields["category_list"] = "\n".join(f"  - {c}" for c in taxonomy(sector))
    return fields


def system_prompt(sector=None) -> str:
    return _SYSTEM_TEMPLATE.substitute(_fields(sector))


def cluster_prompt(sector=None) -> str:
    return _CLUSTER_TEMPLATE.substitute(_fields(sector))


def theme_prompt(sector=None) -> str:
    return _THEME_TEMPLATE.substitute(_fields(sector))


def _version(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]


# Tied to the rendered prompt text, so editing a prompt or a sector's wording
# automatically invalidates the summaries cached under the old wording.
def cluster_summary_version(sector=None) -> str:
    return _version(cluster_prompt(sector))


def theme_summary_version(sector=None) -> str:
    return _version(theme_prompt(sector))
```

In `score_signal`, `summarize_cluster` and `summarize_theme`:
- add the parameter `sector=None` (after `alias_map` in `score_signal`, after `client` in the other two);
- use `system=system_prompt(sector)`, `system=cluster_prompt(sector)` and `system=theme_prompt(sector)` respectively;
- in `score_signal`, change the canonical-category call to `canonical_category(signal["category"], signal["title"], signal.get("signal_type"), sector=sector)`.

The template text is `$`-free apart from the placeholders, so `substitute` raises if a field is missing, which is what we want.

- [ ] **Step 4: Point the pipeline at the new names (temporary)**

In `src/pipeline.py`, replace the imports of `CLUSTER_SUMMARY_VERSION` and `THEME_SUMMARY_VERSION` with `cluster_summary_version` and `theme_summary_version`. Use `cluster_summary_version()` and `theme_summary_version()` at the two cache-key sites. Task 7 rewrites this file; this keeps it working meanwhile.

In `tests/fixtures/make_gambling_baseline.py`, nothing needs to change at runtime. Leave it, because it documents what was recorded.

- [ ] **Step 5: Run all tests**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: all pass. `test_source_uses_the_or_form` still passes, because the `os.environ.get("ANTHROPIC_MODEL") or` lines are untouched.

- [ ] **Step 6: Commit**

```bash
git add src/score.py src/pipeline.py tests/test_gambling_equivalence.py
git commit -m "Render Claude prompts from the sector's wording

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_016YJv2T4yhVoixtyDTkv1fZ"
```

---

### Task 6: Collectors built from the sector

**Files:**
- Modify: `src/collectors/dcms.py`, `src/pipeline.py`
- Modify: `tests/test_gambling_equivalence.py`, `tests/test_lse_rns.py`

**Interfaces:**
- Consumes: `Sector.sources`, `.keywords`, `.companies`, `.tickers`.
- Produces:
  - `DCMSCollector(keywords, user_agent, results_per_term=20, organisation="department-for-culture-media-and-sport")`.
  - `COLLECTORS: dict[str, Callable[[Sector, dict], Collector | None]]`, in today's build order.
  - `build_collectors(sector) -> list`.
  - `DEFAULT_USER_AGENT = "Signal-Prototype/0.1"`.

- [ ] **Step 1: Update the collector equivalence test**

Replace `test_collectors_are_identical` with:

```python
def test_collectors_are_identical(monkeypatch):
    monkeypatch.setenv("COMPANIES_HOUSE_API_KEY", "baseline-test-key")
    from src.pipeline import build_collectors
    from tests.fixtures.make_gambling_baseline import collector_snapshot

    got = [collector_snapshot(c) for c in build_collectors(load_sector("gambling"))]
    assert [c["class"] for c in got] == [c["class"] for c in BASE["collectors"]]
    for new, old in zip(got, BASE["collectors"]):
        # Every recorded attribute is unchanged; DCMS gains `organisation`,
        # set to the department it used to hard-code.
        extra = set(new["attrs"]) - set(old["attrs"])
        assert {k: new["attrs"][k] for k in old["attrs"]} == old["attrs"], new["class"]
        assert extra <= {"organisation"}
        if extra:
            assert new["attrs"]["organisation"] == "department-for-culture-media-and-sport"
```

In `tests/test_lse_rns.py`, change the top to read from the sector:

```python
from src.collectors.lse_rns import LSERNSCollector
from src.sectors import load_sector

SKIP_TITLES = load_sector("gambling").sources["lse_rns"]["skip_titles"]
```

Then remove the now-unused `import yaml`.

- [ ] **Step 2: Run the tests to confirm they fail**

Run: `.venv/bin/python -m pytest tests/test_gambling_equivalence.py -q`
Expected: FAIL (`build_collectors` takes the sources dict, not a sector).

- [ ] **Step 3: Parameterise DCMS**

In `src/collectors/dcms.py`, keep `ORGANISATION_SLUG` as the default value and change the constructor and search:

```python
class DCMSCollector(Collector):
    def __init__(
        self,
        keywords: list[str],
        user_agent: str,
        results_per_term: int = 20,
        organisation: str = ORGANISATION_SLUG,
    ):
        self.keywords = keywords
        self.headers = {"User-Agent": user_agent}
        self.results_per_term = results_per_term
        # Which GOV.UK department's publications to search; DCMS for gambling,
        # e.g. hm-treasury for a fintech sector.
        self.organisation = organisation
```

In `_search`, change `"filter_organisations": ORGANISATION_SLUG,` to `"filter_organisations": self.organisation,`.

- [ ] **Step 4: Replace `load_sources`, `load_watchlist` and `build_collectors` in `src/pipeline.py`**

Delete `load_sources`, `_load_operators_file`, `load_watchlist` and the old `build_collectors`, then add:

```python
from src.sectors import Sector

DEFAULT_USER_AGENT = "Signal-Prototype/0.1"


def _ua(settings: dict) -> str:
    return settings.get("user_agent", DEFAULT_USER_AGENT)


def _keywords(sector: Sector, settings: dict) -> list[str]:
    # A source's own keywords win; otherwise the sector's defaults.
    return list(settings.get("keywords", sector.keywords))


def _gambling_commission(sector, s):
    return GamblingCommissionCollector(listing_pages=s["listing_pages"], user_agent=_ua(s))


def _companies_house(sector, s):
    api_key = os.environ.get("COMPANIES_HOUSE_API_KEY")
    if not api_key:
        logger.warning("COMPANIES_HOUSE_API_KEY not set — skipping Companies House collector")
        return None
    return CompaniesHouseCollector(
        api_key=api_key,
        operators=sector.companies,
        items_per_page=s.get("items_per_page", 25),
        sleep_seconds=s.get("sleep_seconds", 0.6),
        lookback_days=s.get("lookback_days", 365),
        categories=s.get("categories"),
    )


def _gazette(sector, s):
    return GazetteCollector(
        search_terms=_keywords(sector, s) + [c["name"] for c in sector.companies],
        user_agent=_ua(s),
        results_per_term=s.get("results_per_term", 20),
        sleep_seconds=s.get("sleep_seconds", 1.0),
    )


def _dcms(sector, s):
    kwargs = {"organisation": s["organisation"]} if "organisation" in s else {}
    return DCMSCollector(
        keywords=_keywords(sector, s), user_agent=_ua(s),
        results_per_term=s.get("results_per_term", 20), **kwargs,
    )


def _parliament(sector, s):
    return ParliamentCollector(
        keywords=_keywords(sector, s), user_agent=_ua(s),
        results_per_term=s.get("results_per_term", 20),
    )


def _asa(sector, s):
    return ASACollector(keywords=_keywords(sector, s), user_agent=_ua(s))


def _bgc(sector, s):
    return BGCCollector(user_agent=_ua(s), pages=s.get("pages", 2))


def _insolvency_service(sector, s):
    return InsolvencyServiceCollector(
        keywords=_keywords(sector, s), user_agent=_ua(s),
        sleep_seconds=s.get("sleep_seconds", 1.0),
    )


def _lse_rns(sector, s):
    return LSERNSCollector(
        tickers=dict(s.get("tickers", sector.tickers)), user_agent=_ua(s),
        skip_titles=s.get("skip_titles"),
    )


# Build order matters: it sets the order raw items, and so new signals, arrive.
COLLECTORS = {
    "gambling_commission": _gambling_commission,
    "companies_house": _companies_house,
    "gazette": _gazette,
    "dcms": _dcms,
    "parliament": _parliament,
    "asa": _asa,
    "bgc": _bgc,
    "insolvency_service": _insolvency_service,
    "lse_rns": _lse_rns,
}


def build_collectors(sector: Sector) -> list:
    collectors = []
    for key, build in COLLECTORS.items():
        if key in sector.sources:
            collector = build(sector, sector.sources[key])
            if collector is not None:
                collectors.append(collector)
    return collectors
```

`src.sectors.KNOWN_SOURCES` and `COLLECTORS` must list the same keys. Add this test to `tests/test_sectors.py`:

```python
def test_known_sources_match_the_registry():
    from src.pipeline import COLLECTORS
    assert tuple(COLLECTORS) == sectors.KNOWN_SOURCES
```

In `run()`, for now, replace `sources = load_sources()` / `build_collectors(sources)` with `sector = load_sector("gambling")` / `collectors = build_collectors(sector)`, and `alias_map = build_alias_map(load_watchlist())` with `alias_map = build_alias_map(sector.companies)`. Task 7 replaces `run()`.

In `scripts/backfill_canonical_entities.py`, replace `from src.pipeline import load_watchlist` and `load_watchlist()` with `from src.sectors import load_sector` and `load_sector("gambling").companies`. Task 8 adds `--sector`.

The baseline generator imports `build_collectors, load_sources, load_watchlist`, which no longer exist. Change its import line to `from src.pipeline import build_collectors` and add a comment at the top: `# Historical: generated the fixture from the pre-sector code (commit before Task 2). Only collector_snapshot is still imported.` Move the `main()` body's imports of removed names inside `main()`, so importing `collector_snapshot` still works.

- [ ] **Step 5: Run all tests**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/collectors/dcms.py src/pipeline.py scripts/backfill_canonical_entities.py tests/
git commit -m "Build collectors from the sector config via a registry

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_016YJv2T4yhVoixtyDTkv1fZ"
```

---

### Task 7: Run per sector, with the index and the compatibility copy

**Files:**
- Modify: `src/pipeline.py`
- Test: `tests/test_pipeline_sectors.py`

**Interfaces:**
- Consumes: everything above; `store.load/merge_new/load_archived_ids/save` with path arguments.
- Produces:
  - `run_sector(sector, client) -> dict`, which returns the run status.
  - `main(argv: list[str] | None = None) -> int`, which returns the exit code.
  - `write_compat_copy(sector) -> None`.
  - The constants `COMPAT_SIGNALS_PATH = Path("data/signals.json")` and `COMPAT_STATUS_PATH = Path("data/run_status.json")`.
  - `run()` is **removed**. The entry point is `sys.exit(main())`.

- [ ] **Step 1: Write the failing tests**

`tests/test_pipeline_sectors.py`:

```python
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from src import pipeline, sectors
from src.collectors.base import RawItem
from src.sectors import PROMPT_FIELDS


def sector_yaml(slug, **extra):
    data = {"slug": slug, "name": slug.title(), "brief": f"The {slug} sector.",
            "prompt": {f: f"{slug} {f}" for f in PROMPT_FIELDS},
            "sources": {"gazette": {}}}
    data.update(extra)
    return data


class FakeCollector:
    def __init__(self, items): self.items = items
    def collect(self): return self.items


def item(n, source="gazette"):
    return RawItem(source=source, source_url=f"https://x/{n}", title=f"Item {n}",
                   raw_summary="s", published_at="2026-10-01T00:00:00+00:00",
                   signal_type="insolvency")


class FakeClient:
    """Answers every Claude call with a fixed, valid payload."""
    def __init__(self):
        self.messages = SimpleNamespace(create=self._create)
        self.systems = []

    def _create(self, model, max_tokens, system, messages):
        self.systems.append(system)
        payload = {"newsworthiness_score": 55, "signal_type": "insolvency",
                   "entities": ["Acme Ltd"], "category": "Insolvency",
                   "why_it_matters": "x", "summary": "y", "pattern_type": "routine",
                   "coherent": True, "significance": 10, "key_points": [], "direction": "steady"}
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=json.dumps(payload))],
                               stop_reason="end_turn", usage=SimpleNamespace(output_tokens=5))


@pytest.fixture
def repo(tmp_path, monkeypatch):
    config = tmp_path / "config" / "sectors"
    config.mkdir(parents=True)
    data = tmp_path / "data"
    monkeypatch.setattr(sectors, "CONFIG_DIR", config)
    monkeypatch.setattr(sectors, "DATA_DIR", data)
    monkeypatch.setattr(sectors, "INDEX_PATH", data / "sectors.json")
    monkeypatch.setattr(pipeline, "COMPAT_SIGNALS_PATH", data / "signals.json")
    monkeypatch.setattr(pipeline, "COMPAT_STATUS_PATH", data / "run_status.json")
    client = FakeClient()
    monkeypatch.setattr(pipeline, "build_client", lambda: client)
    monkeypatch.setattr(pipeline, "load_dotenv", lambda: None)
    feeds = {}
    monkeypatch.setattr(pipeline, "build_collectors",
                        lambda sector: [FakeCollector(feeds.get(sector.slug, []))])
    return SimpleNamespace(config=config, data=data, feeds=feeds, client=client)


def write(repo, slug, **extra):
    (repo.config / f"{slug}.yaml").write_text(yaml.safe_dump(sector_yaml(slug, **extra)), encoding="utf-8")


def test_each_sector_writes_only_its_own_data(repo):
    write(repo, "alpha"); write(repo, "beta")
    repo.feeds["alpha"] = [item(1), item(2)]
    repo.feeds["beta"] = [item(3)]
    assert pipeline.main([]) == 0
    alpha = json.loads((repo.data / "alpha" / "signals.json").read_text())
    beta = json.loads((repo.data / "beta" / "signals.json").read_text())
    assert len(alpha) == 2 and len(beta) == 1
    assert {s["sector"] for s in alpha} == {"alpha"} and {s["sector"] for s in beta} == {"beta"}
    assert json.loads((repo.data / "alpha" / "run_status.json").read_text())["sector"] == "alpha"


def test_prompts_use_each_sectors_wording(repo):
    write(repo, "alpha")
    repo.feeds["alpha"] = [item(1)]
    pipeline.main(["--sector", "alpha"])
    assert any("alpha newsroom" in s for s in repo.client.systems)


def test_sector_flag_runs_only_that_sector(repo):
    write(repo, "alpha"); write(repo, "beta")
    repo.feeds["alpha"] = [item(1)]; repo.feeds["beta"] = [item(2)]
    assert pipeline.main(["--sector", "beta"]) == 0
    assert not (repo.data / "alpha" / "signals.json").exists()
    assert (repo.data / "beta" / "signals.json").exists()


def test_unknown_sector_exits_2_and_runs_nothing(repo, capsys):
    write(repo, "alpha")
    assert pipeline.main(["--sector", "nope"]) == 2
    assert not (repo.data / "alpha").exists()
    assert "alpha" in capsys.readouterr().err


def test_one_bad_sector_does_not_stop_the_rest(repo):
    write(repo, "alpha")
    (repo.config / "broken.yaml").write_text("slug: broken\nname: Broken\n", encoding="utf-8")
    repo.feeds["alpha"] = [item(1)]
    assert pipeline.main([]) == 1
    assert (repo.data / "alpha" / "signals.json").exists()
    index = sectors.read_index()
    assert index["alpha"]["status"] == "ready" and index["alpha"]["signal_count"] == 1
    assert index["broken"]["status"] == "error" and "brief" in index["broken"]["error"]
    assert "error" in json.loads((repo.data / "broken" / "run_status.json").read_text())


def test_a_run_exception_is_isolated(repo, monkeypatch):
    write(repo, "alpha"); write(repo, "beta")
    repo.feeds["beta"] = [item(1)]
    real = pipeline.run_sector
    def flaky(sector, client):
        if sector.slug == "alpha":
            raise RuntimeError("boom")
        return real(sector, client)
    monkeypatch.setattr(pipeline, "run_sector", flaky)
    assert pipeline.main([]) == 1
    assert sectors.read_index()["alpha"]["error"] == "boom"
    assert sectors.read_index()["beta"]["status"] == "ready"


def test_gambling_writes_the_compat_copy(repo):
    write(repo, "gambling")
    repo.feeds["gambling"] = [item(1), item(2)]
    assert pipeline.main(["--sector", "gambling"]) == 0
    assert (repo.data / "signals.json").read_text() == (repo.data / "gambling" / "signals.json").read_text()
    assert (repo.data / "run_status.json").read_text() == (repo.data / "gambling" / "run_status.json").read_text()


def test_other_sectors_do_not_touch_the_compat_copy(repo):
    write(repo, "alpha")
    repo.feeds["alpha"] = [item(1)]
    pipeline.main([])
    assert not (repo.data / "signals.json").exists()


def test_existing_signals_are_kept_and_not_rescored(repo):
    write(repo, "alpha")
    repo.feeds["alpha"] = [item(1)]
    pipeline.main([])
    calls_first = len(repo.client.systems)
    pipeline.main([])
    alpha = json.loads((repo.data / "alpha" / "signals.json").read_text())
    assert len(alpha) == 1
    # Second run: nothing new to score; summaries are cached.
    assert len(repo.client.systems) == calls_first
```

- [ ] **Step 2: Run the tests to confirm they fail**

Run: `.venv/bin/python -m pytest tests/test_pipeline_sectors.py -q`
Expected: FAIL (`pipeline.main` not defined).

- [ ] **Step 3: Implement in `src/pipeline.py`**

Remove `RUN_STATUS_PATH` and `run()`. Add `import argparse`, `import shutil` and `import sys`. Import from `src.sectors`: `Sector, SectorConfigError, list_sector_slugs, load_sector, refresh_index, update_index, DATA_DIR` (as `sectors_data_dir`). Then add:

```python
# The deployed dashboard still reads these; written after every gambling run
# until stage 2 points it at data/gambling/.
COMPAT_SIGNALS_PATH = Path("data/signals.json")
COMPAT_STATUS_PATH = Path("data/run_status.json")


def write_run_status(status: dict, path: Path) -> None:
    """Publish what the run actually did, so a silently broken scraper shows
    up in the dashboard instead of only in an Actions log nobody reads."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(status, f, indent=2, ensure_ascii=False)


def write_compat_copy(sector: Sector) -> None:
    COMPAT_SIGNALS_PATH.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(sector.signals_path, COMPAT_SIGNALS_PATH)
    shutil.copyfile(sector.run_status_path, COMPAT_STATUS_PATH)


def run_sector(sector: Sector, client) -> dict:
    """One sector, end to end: collect, score, cluster, summarise, save.
    Everything it reads and writes lives under data/<slug>/."""
    started_at = datetime.now(timezone.utc)
    collectors = build_collectors(sector)
    alias_map = build_alias_map(sector.companies)

    raw_items = []
    source_status: dict[str, dict] = {}
    for collector in collectors:
        name = type(collector).__name__
        try:
            collected = collector.collect()
        except Exception:
            # One source's unexpected failure shouldn't take every other
            # source down with it — log it and move on.
            logger.exception("[%s] Collector %s failed — skipping, other sources unaffected",
                             sector.slug, name)
            source_status[name] = {"items": 0, "ok": False, "error": True}
            continue
        raw_items.extend(collected)
        # Zero items isn't an exception, but for a scraper it usually means
        # the page layout moved underneath us — flag it as unhealthy.
        source_status[name] = {"items": len(collected), "ok": bool(collected), "error": False}
    logger.info("[%s] Collected %d raw items", sector.slug, len(raw_items))

    new_signals_by_id = {}
    for raw in raw_items:
        signal = to_signal(raw)
        signal["sector"] = sector.slug
        new_signals_by_id[signal["id"]] = signal

    existing = store.load(sector.signals_path)
    merged, added = store.merge_new(
        existing, list(new_signals_by_id.values()),
        store.load_archived_ids(sector.archive_ids_path),
    )
    for s in merged:
        s.setdefault("sector", sector.slug)

    unscored = [s for s in merged if s.get("newsworthiness_score") is None]
    logger.info("[%s] %d new signals, %d unscored total (including retries of prior failures)",
                sector.slug, len(added), len(unscored))
    for signal in unscored:
        score_signal(signal, client=client, alias_map=alias_map, sector=sector)

    cluster.assign_clusters(merged, alias_map=alias_map, sector=sector)
    cluster.assign_themes(merged, alias_map=alias_map, sector=sector)
    by_cluster = defaultdict(list)
    for s in merged:
        if s.get("cluster_id"):
            by_cluster[s["cluster_id"]].append(s)
    themes = {s["theme_id"] for s in merged if s.get("theme_id")}
    logger.info("[%s] %d clusters and %d themes formed", sector.slug, len(by_cluster), len(themes))

    cluster_version = cluster_summary_version(sector)
    for cluster_id, members in by_cluster.items():
        # Cache key covers both cluster membership and prompt wording, so
        # either changing invalidates it and triggers a re-summary.
        cache_key = f"{cluster_id}:{cluster_version}"
        if any(m.get("cluster_summary_for") == cache_key for m in members):
            continue
        verdict = summarize_cluster(members, client=client, sector=sector)
        if verdict:
            for m in members:
                m["cluster_summary"] = verdict["summary"]
                m["cluster_pattern_type"] = verdict["pattern_type"]
                m["cluster_coherent"] = verdict["coherent"]
                m["cluster_significance"] = verdict["significance"]
                m["cluster_summary_for"] = cache_key

    by_theme = defaultdict(list)
    for s in merged:
        if s.get("theme_id"):
            by_theme[s["theme_id"]].append(s)

    theme_version = theme_summary_version(sector)
    for theme, members in by_theme.items():
        # theme_id is stable, but membership isn't, so the cache key covers
        # who is in it as well as the prompt wording.
        members_hash = hashlib.sha256(
            "|".join(sorted(m["id"] for m in members)).encode("utf-8")
        ).hexdigest()[:12]
        cache_key = f"{theme}:{members_hash}:{theme_version}"
        if any(m.get("theme_summary_for") == cache_key for m in members):
            continue
        verdict = summarize_theme(theme, members, client=client, sector=sector)
        if verdict:
            for m in members:
                m["theme_summary"] = verdict["summary"]
                m["theme_key_points"] = verdict["key_points"]
                m["theme_direction"] = verdict["direction"]
                m["theme_summary_for"] = cache_key

    live = store.save(merged, path=sector.signals_path,
                      archive_dir=sector.archive_dir, ids_path=sector.archive_ids_path)
    logger.info("[%s] Store now holds %d live signals (%d archived this run)",
                sector.slug, len(live), len(merged) - len(live))

    status = {
        "sector": sector.slug,
        "started_at": started_at.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "sources": source_status,
        "healthy_sources": sum(1 for s in source_status.values() if s["ok"]),
        "total_sources": len(source_status),
        "raw_items": len(raw_items),
        "new_signals": len(added),
        "unscored": sum(1 for s in live if s.get("newsworthiness_score") is None),
        "live_signals": len(live),
        "clusters": len(by_cluster),
    }
    write_run_status(status, sector.run_status_path)
    return status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Collect, score and cluster signals per sector.")
    parser.add_argument("--sector", help="run just this sector (default: every sector)")
    args = parser.parse_args(argv)

    load_dotenv()
    available = list_sector_slugs()
    if args.sector and args.sector not in available:
        print(f"No sector config named {args.sector!r} (available: {', '.join(available)})",
              file=sys.stderr)
        return 2
    slugs = [args.sector] if args.sector else available
    refresh_index(available)

    client = build_client()
    failed = False
    for slug in slugs:
        try:
            sector = load_sector(slug)
            status = run_sector(sector, client)
            update_index(slug, name=sector.name, brief=sector.brief, created_at=sector.created_at,
                         status="ready", last_run_at=status["finished_at"],
                         signal_count=status["live_signals"], error=None)
            if slug == "gambling":
                write_compat_copy(sector)
        except Exception as exc:  # isolate: one sector's failure never stops the rest
            failed = True
            logger.exception("[%s] Sector run failed", slug)
            now = datetime.now(timezone.utc).isoformat()
            write_run_status({"sector": slug, "finished_at": now, "error": str(exc)},
                             sectors_data_dir / slug / "run_status.json")
            update_index(slug, status="error", error=str(exc), last_run_at=now)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
```

**Data dir in tests:** `sectors_data_dir` must be read at call time so the test fixture's monkeypatch applies. Replace `sectors_data_dir / slug` with `sectors.DATA_DIR / slug`, using `from src import sectors` at the top of the module. In `test_one_bad_sector…`, `load_sector("broken")` raises `SectorConfigError` naming `brief`, which is the first missing field after `slug`/`name`. The `update_index` call records it.

- [ ] **Step 4: Run all tests**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/pipeline.py tests/test_pipeline_sectors.py
git commit -m "Run the pipeline per sector, isolated, with an index and a compat copy

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_016YJv2T4yhVoixtyDTkv1fZ"
```

---

### Task 8: Migrate today's data into `data/gambling/`, and backfill per sector

**Files:**
- Create: `scripts/migrate_to_sectors.py`
- Modify: `scripts/backfill_canonical_entities.py`
- Test: `tests/test_migrate.py`

**Interfaces:**
- Produces: `migrate(data_dir: Path = Path("data"), dry_run: bool = False) -> dict`, which returns a report with the keys `status` (`"migrated" | "already migrated" | "nothing to migrate"`), `signals`, `archived` and `files`.

- [ ] **Step 1: Write the failing tests**

`tests/test_migrate.py`:

```python
import json
from pathlib import Path

from scripts.migrate_to_sectors import migrate


def seed(data: Path):
    (data / "archive").mkdir(parents=True)
    live = [{"id": "a", "published_at": "2026-09-01T00:00:00+00:00", "newsworthiness_score": 50},
            {"id": "b", "published_at": "2026-09-02T00:00:00+00:00", "newsworthiness_score": 20}]
    (data / "signals.json").write_text(json.dumps(live))
    (data / "run_status.json").write_text(json.dumps({"live_signals": 2}))
    (data / "archive" / "signals-2025.json").write_text(json.dumps([{"id": "z", "published_at": "2025-01-01"}]))
    (data / "archive" / "ids.json").write_text(json.dumps(["z"]))
    return live


def test_moves_everything_and_tags_sector(tmp_path):
    live = seed(tmp_path)
    report = migrate(tmp_path)
    assert report["status"] == "migrated" and report["signals"] == 2 and report["archived"] == 1
    moved = json.loads((tmp_path / "gambling" / "signals.json").read_text())
    assert [s["id"] for s in moved] == ["a", "b"]
    assert all(s["sector"] == "gambling" for s in moved)
    assert moved[0]["newsworthiness_score"] == live[0]["newsworthiness_score"]  # not re-scored
    arch = json.loads((tmp_path / "gambling" / "archive" / "signals-2025.json").read_text())
    assert arch[0]["sector"] == "gambling"
    assert json.loads((tmp_path / "gambling" / "archive" / "ids.json").read_text()) == ["z"]
    assert json.loads((tmp_path / "gambling" / "run_status.json").read_text())["sector"] == "gambling"
    # The old top-level files stay: they are the dashboard's compat copy.
    assert (tmp_path / "signals.json").exists()
    assert not (tmp_path / "archive").exists()


def test_writes_the_index(tmp_path, monkeypatch):
    from src import sectors
    monkeypatch.setattr(sectors, "INDEX_PATH", tmp_path / "sectors.json")
    seed(tmp_path)
    migrate(tmp_path)
    assert sectors.read_index()["gambling"]["status"] == "ready"


def test_second_run_is_a_no_op(tmp_path):
    seed(tmp_path)
    migrate(tmp_path)
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    assert migrate(tmp_path)["status"] == "already migrated"
    after = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    assert before == after


def test_dry_run_writes_nothing(tmp_path):
    seed(tmp_path)
    before = sorted(p for p in tmp_path.rglob("*"))
    assert migrate(tmp_path, dry_run=True)["status"] == "migrated"
    assert sorted(p for p in tmp_path.rglob("*")) == before


def test_nothing_to_migrate(tmp_path):
    assert migrate(tmp_path)["status"] == "nothing to migrate"
```

- [ ] **Step 2: Run the tests to confirm they fail**

Run: `.venv/bin/python -m pytest tests/test_migrate.py -q`
Expected: FAIL (`No module named 'scripts.migrate_to_sectors'`).

- [ ] **Step 3: Implement `scripts/migrate_to_sectors.py`**

```python
"""One-off: move today's single-sector data into data/gambling/, tagging
every signal with its sector. No re-scoring, no API calls. Safe to re-run:
a migrated repo is left untouched.

    python -m scripts.migrate_to_sectors --dry-run
    python -m scripts.migrate_to_sectors
"""

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

SLUG = "gambling"


def _read(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def _tag(signals: list[dict]) -> list[dict]:
    for s in signals:
        s["sector"] = SLUG
    return signals


def migrate(data_dir: Path = Path("data"), dry_run: bool = False) -> dict:
    target = data_dir / SLUG
    if (target / "signals.json").exists():
        return {"status": "already migrated", "signals": 0, "archived": 0, "files": []}
    old_signals = data_dir / "signals.json"
    if not old_signals.exists():
        return {"status": "nothing to migrate", "signals": 0, "archived": 0, "files": []}

    signals = _tag(_read(old_signals))
    files = [target / "signals.json"]
    archived = 0
    old_archive = data_dir / "archive"
    year_files = sorted(old_archive.glob("signals-*.json")) if old_archive.exists() else []

    if not dry_run:
        _write(target / "signals.json", signals)
    for year_file in year_files:
        batch = _tag(_read(year_file))
        archived += len(batch)
        files.append(target / "archive" / year_file.name)
        if not dry_run:
            _write(target / "archive" / year_file.name, batch)
    if (old_archive / "ids.json").exists():
        files.append(target / "archive" / "ids.json")
        if not dry_run:
            shutil.copyfile(old_archive / "ids.json", target / "archive" / "ids.json")
    old_status = data_dir / "run_status.json"
    if old_status.exists():
        files.append(target / "run_status.json")
        if not dry_run:
            _write(target / "run_status.json", {**_read(old_status), "sector": SLUG})

    if not dry_run:
        # The top-level signals.json/run_status.json stay as the dashboard's
        # compatibility copy; the old archive now lives under data/gambling/.
        if old_archive.exists():
            shutil.rmtree(old_archive)
        from src import sectors
        sectors.update_index(SLUG, name="Gambling & gaming", status="ready",
                             signal_count=len(signals),
                             last_run_at=datetime.now(timezone.utc).isoformat(), error=None)

    return {"status": "migrated", "signals": len(signals), "archived": archived,
            "files": [str(f) for f in files]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    report = migrate(dry_run=args.dry_run)
    print(json.dumps(report, indent=2))
    if args.dry_run:
        print("Dry run — nothing written.")


if __name__ == "__main__":
    main()
```

In `test_moves_everything_and_tags_sector`, the index is written to the real `data/sectors.json`, because `sectors.INDEX_PATH` isn't patched. Prevent that by adding this autouse fixture at the top of `tests/test_migrate.py`:

```python
import pytest

@pytest.fixture(autouse=True)
def _isolated_index(tmp_path, monkeypatch):
    from src import sectors
    monkeypatch.setattr(sectors, "INDEX_PATH", tmp_path / "sectors.json")
```

Then drop the now-redundant `monkeypatch` line from `test_writes_the_index`. Also, `test_dry_run_writes_nothing` must ignore `sectors.json`. The dry run doesn't write it, so the assertion already holds.

- [ ] **Step 4: Give the backfill script `--sector`**

In `scripts/backfill_canonical_entities.py`:
- add `parser.add_argument("--sector", default="gambling")`;
- load `sector = load_sector(args.sector)` and use `alias_map = build_alias_map(sector.companies)`;
- read with `signals = store.load(sector.signals_path)`;
- pass `sector=sector` to `canonical_category(...)`, `cluster.assign_clusters/assign_themes/compute_theme_heat` and `cluster.is_excluded(e, sector)`;
- write with `store.save(signals, path=sector.signals_path, retention_days=None)` and `print(f"Written to {sector.signals_path}.")`.

Update the usage lines in the docstring to show `--sector gambling`.

- [ ] **Step 5: Run all tests**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add scripts/migrate_to_sectors.py scripts/backfill_canonical_entities.py tests/test_migrate.py
git commit -m "Add the data migration into data/gambling/ and a per-sector backfill

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_016YJv2T4yhVoixtyDTkv1fZ"
```

---

### Task 9: Cut over — retire the old config, run the migration, update the workflow and docs

**Files:**
- Delete: `config/sources.yaml`, `config/watchlist.yaml`, and `config/user_watchlist.yaml` if present. If it exists, move its `operators` into `config/sectors/gambling.user.yaml` first.
- Modify: `dashboard/app.py` (the watchlist path), `.github/workflows/pipeline.yml`, `README.md`
- Data: run the migration (this changes `data/`)

- [ ] **Step 1: Move any user watchlist entries, then delete the old config files**

Run:

```bash
if [ -f config/user_watchlist.yaml ]; then git mv config/user_watchlist.yaml config/sectors/gambling.user.yaml; fi
git rm config/sources.yaml config/watchlist.yaml
grep -rn "sources.yaml\|watchlist.yaml\|load_watchlist\|load_sources" src scripts tests dashboard | grep -v "gambling.user.yaml"
```

Expected: the grep prints nothing. If it finds a reference, fix it to use `load_sector`.

- [ ] **Step 2: Point the dashboard's watchlist form at the sector's user file**

In `dashboard/app.py`, change:

```python
USER_WATCHLIST_PATH = "config/user_watchlist.yaml"
```

to:

```python
# The pipeline reads dashboard additions from the gambling sector's user file
# (src/sectors.py merges its "operators" key).
USER_WATCHLIST_PATH = "config/sectors/gambling.user.yaml"
```

- [ ] **Step 3: Workflow input and concurrency**

In `.github/workflows/pipeline.yml`, change the trigger and run step and add concurrency:

```yaml
on:
  workflow_dispatch:  # fired by the n8n schedule instead of GitHub's own cron
    inputs:
      sector:
        description: "Run just this sector (slug); empty runs every sector"
        required: false
        default: ""

# Runs commit to the repo; queue them rather than letting two race.
concurrency:
  group: pipeline
  cancel-in-progress: false
```

```yaml
      - name: Run pipeline
        env:
          # … existing env block unchanged …
          SECTOR: ${{ inputs.sector }}
        run: |
          if [ -n "$SECTOR" ]; then python -m src.pipeline --sector "$SECTOR"; else python -m src.pipeline; fi
```

In the commit step, change the message line to:

```bash
          git diff --staged --quiet || git commit -m "Update signals${SECTOR:+ ($SECTOR)} [skip ci]"
```

Add `SECTOR: ${{ inputs.sector }}` to that step's `env` as well.

- [ ] **Step 4: README**

In `README.md`:
- Replace the "Setup" run line with:
  ```
  python -m scripts.migrate_to_sectors   # once, after pulling this change
  python -m src.pipeline                 # every sector
  python -m src.pipeline --sector gambling
  ```
- Replace the "Data files" section's paths with the per-sector layout: `data/<slug>/signals.json`, `run_status.json`, `archive/`, plus the index `data/sectors.json`. Add a note that `data/signals.json` and `data/run_status.json` are a gambling compatibility copy kept for the deployed dashboard until stage 2.
- Add a "Sectors" section: one file per sector in `config/sectors/<slug>.yaml` (point to `gambling.yaml` as the worked example), dashboard additions in `<slug>.user.yaml`, and each sector's run costs its own Claude calls.

- [ ] **Step 5: Run the migration on the real data**

Run: `.venv/bin/python -m scripts.migrate_to_sectors --dry-run`
Expected: `"status": "migrated"`, `"signals": 336` (or the current count) and the archive count.

Run: `.venv/bin/python -m scripts.migrate_to_sectors`

Then verify:

```bash
.venv/bin/python -c "
import json; a=json.load(open('data/signals.json')); b=json.load(open('data/gambling/signals.json'))
print(len(a), len(b), {s['id'] for s in a}=={s['id'] for s in b}, {s.get('sector') for s in b})"
```

Expected: equal counts, `True` and `{'gambling'}`.

- [ ] **Step 6: Full test suite and dashboard smoke test**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: all pass.

Run the dashboard app test (`streamlit.testing.v1.AppTest` on `streamlit_app.py`, log in with the local password). It must render all three tabs with no exception, because the dashboard still reads the compatibility copy.

- [ ] **Step 7: Commit**

```bash
git add -A config dashboard/app.py .github/workflows/pipeline.yml README.md data
git commit -m "Cut over to sector configs: migrate data, retire old config, workflow input

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_016YJv2T4yhVoixtyDTkv1fZ"
```

---

### Task 10: Real run and verification

This needs the real `ANTHROPIC_API_KEY` and `COMPANIES_HOUSE_API_KEY` in `.env`. It makes paid API calls.

- [ ] **Step 1: Check the keys are present without printing them**

Run: `.venv/bin/python -c "import os; from dotenv import load_dotenv; load_dotenv(); print({k: bool(os.environ.get(k)) for k in ['ANTHROPIC_API_KEY','COMPANIES_HOUSE_API_KEY']})"`
Expected: both `True`. If not, stop and ask the author to add them; don't skip to Step 3.

- [ ] **Step 2: Run gambling for real**

Run: `.venv/bin/python -m src.pipeline --sector gambling; echo "exit=$?"`
Expected: `exit=0`. The log lines are prefixed `[gambling]`.

- [ ] **Step 3: Compare against the last production run**

Run:

```bash
.venv/bin/python -c "
import json
new=json.load(open('data/gambling/run_status.json')); print({k:new[k] for k in ['healthy_sources','total_sources','live_signals','clusters','unscored']})
idx=json.load(open('data/sectors.json')); print(idx)
a=open('data/signals.json').read()==open('data/gambling/signals.json').read(); print('compat copy equal:', a)"
git diff --stat HEAD -- data | tail -3
```

Expected:
- `total_sources` is 9;
- `live_signals` is within a few of the previous run (new items only);
- the compatibility copy is equal;
- the index shows gambling `ready`.

Also compare `clusters` with the previous `run_status.json` in git (`git show HEAD:data/run_status.json`). Any large swing needs explaining before you proceed.

- [ ] **Step 4: Confirm the dashboard reads the compatibility copy**

Restart the local Streamlit app and load http://localhost:8501. The Feed, Patterns and Themes must show data, and the freshness strip must reflect the new run.

- [ ] **Step 5: Commit the run's data (optional, at the author's discretion)**

Only if the author wants the refreshed data on the branch:

```bash
git add data && git commit -m "Refresh gambling data from the first sector-aware run

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_016YJv2T4yhVoixtyDTkv1fZ"
```

Do **not** push. The repo owner reviews the branch before anything merges.
