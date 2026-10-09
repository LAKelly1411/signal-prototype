# Premium Sector Creation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A dashboard user unlocks a demo of the premium add-on, describes an industry, reviews a Claude-drafted sector config (with company numbers verified), and creates it. The config is committed through GitHub, an all-sectors pipeline run starts, and the switcher shows the new sector as "Setting up…".

**Architecture:**
- New Streamlit-free modules carry the logic, each unit tested:
  - `src/drafting.py`: Claude tool-use draft, normalisation and Companies House verification;
  - `src/sectors.parse_sector`: dict validation;
  - `dashboard/github.py`: the GitHub Contents and Actions APIs, and the three-step save.
- `dashboard/app.py` gains one multi-step `st.dialog`, wired from the switcher's "New sector" row.
- Stage 2's deferred prerequisites land first in `dashboard/data.py`.

**Tech Stack:** Python 3.11+, Streamlit 1.62 (`st.dialog`, `st.data_editor`, `st.multiselect(accept_new_options=True)`, AppTest), `anthropic==1.1.0` (tool use), requests, PyYAML, pytest.

**Spec:** `docs/superpowers/specs/2026-10-08-sector-creation-design.md`. Stages 1 and 2: `docs/superpowers/specs/2026-10-08-sector-aware-pipeline-design.md`, `docs/superpowers/specs/2026-10-08-sector-switcher-design.md`.

## Global Constraints

- **Gambling and fintech unchanged.** Every existing test stays green, including `tests/test_gambling_equivalence.py`.
- **Unlock.** `st.session_state["premium_unlocked"]` is False by default and never persisted. A reload locks creation again.
- **Limits:**
  - `MAX_SECTORS = 10`: at the cap, the row label is "Sector limit reached" and its tooltip is "Contact us to add more sectors."
  - `MAX_DRAFTS = 5` per session: at the limit, the copy is "You've reached the demo's draft limit."
  - The description is 10 to 300 characters.
- **Generic sources only:** `companies_house`, `gazette`, `dcms`, `parliament`, `asa`, `insolvency_service`, `lse_rns`. Never `gambling_commission` or `bgc`.
- **Category limits.** Each category pattern is at most 200 characters and must compile. `before` must be a core rule name. Invalid categories are dropped.
- **Companies.** 3 to 12, deduplicated by name.
- **Company numbers.** A number is kept only if Companies House says `company_status == "active"` and `match_key(registered name)` equals, contains or is contained by `match_key(drafted name)`. Otherwise it is `None`. With no `COMPANIES_HOUSE_API_KEY`, every number is `None`.
- **Slugs.** Lowercase; non-alphanumerics become `-`, collapsed and trimmed; at most 40 characters. Unique against existing slugs with `-2`, `-3` and so on. Must `SLUG_RE.fullmatch`.
- **Model.** `os.environ.get("ANTHROPIC_MODEL") or "claude-sonnet-5"`.
- **Save order:**
  1. Commit `config/sectors/<slug>.yaml`; fail if it already exists.
  2. Add the index entry to `data/sectors.json` with its sha; skip if the file doesn't exist.
  3. Dispatch `pipeline.yml` on `main` with `{"sector": ""}`, an all-sectors run.

  Each step runs only if the previous one succeeded.
- **Copy, verbatim:**
  - Upsell headline: "Track any industry"
  - Upsell body: "Add a sector of your own, with its own sources, companies and scoring. New sectors are part of the premium add-on."
  - Unlock button: "Unlock for demo"
  - Sales link: "Talk to us"
  - Describe label: "Which industry should we track?"
  - Describe placeholder: "e.g. UK energy suppliers and the regulators around them"
  - Draft button: "Draft it"
  - Draft failed: "We couldn't draft that one. Try describing it differently."
  - No Anthropic key: "Drafting isn't switched on here yet."
  - No GitHub token: "Saving isn't switched on here yet."
  - Created: "<Name> is being set up. We're gathering the first signals; this usually takes under an hour."
  - Save failed (step 1): "We couldn't save the sector. Please try again."
  - Saved, step 2 failed: "Saved. It will appear in the menu after the next update."
  - Saved, step 3 failed: "Saved. Its first update will run with the next scheduled one."
  - Empty state: title "No signals yet", body "<Name> is set up, but nothing has come through yet. New signals will appear here as they're found."
- **Commit trailer.** Every commit message ends with:
  ```
  Co-Authored-By: <the model that wrote the commit> <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_016YJv2T4yhVoixtyDTkv1fZ
  ```
- **Running things.** Run from the repo root with `.venv/bin/python -m pytest …`. Never push. Never start, stop or restart the Streamlit server on port 8501. Tests never touch the network.

## Review Focus

1. **Claude returns a malformed tool call** (no `tool_use` block, missing fields, wrong types, `companies` as a string). It must be treated as a validation failure: retry once, then `DraftError`. Never a crash. The tests are in Task 3.
2. **A drafted name that slugifies to empty or collides** ("!!!", "Gambling & gaming" when gambling exists). The slug becomes `sector` / `gambling-gaming-2` style and stays unique. The test is in Task 3.
3. **The user edits a company number in the review form to garbage** ("abc", "4241161", with spaces). It is re-verified on create and cleared if not confirmed, and it never reaches the YAML as a non-string. The test is in Task 5 (`apply_review`).
4. **Double-clicking "Create sector", or two users creating the same slug.** Step 1 fails on the existing file. No second index entry or dispatch happens, and the user sees the step 1 message. The test is in Task 4.
5. **A sector name containing markdown or HTML** (`*Energy* [x](javascript:alert(1))`). It renders literally in the switcher, the state blocks and the Created copy. The test is in Task 1 (`display_name`) and Task 5's AppTest.

---

## File structure

| File | Responsibility |
|---|---|
| `dashboard/data.py` | Prerequisites: `display_name`, `load_signals` returning `None` for missing, `view_state` gaining `"empty"`, `load_index` raising on non-404 failures. |
| `src/sectors.py` | `parse_sector(raw, slug)`, dict validation shared with `load_sector`. |
| `src/drafting.py` (new) | `slugify`, `unique_slug`, `normalise_draft`, `verify_companies`, `draft_sector`, `Draft`, `DraftError`, `CompaniesHouse`. |
| `dashboard/github.py` (new) | `GitHub` client (`get_file`, `put_file`, `dispatch_workflow`), `save_sector`, `SaveResult`; the watchlist helpers move here. |
| `dashboard/app.py` | The prerequisites wired in, the new-sector dialog, pending-sector merge, cap and limits. |
| `tests/test_dashboard_data.py`, `tests/test_sectors.py` | Updated and extended. |
| `tests/test_drafting.py`, `tests/test_github.py` (new) | New. |
| `tests/test_dashboard_app.py` | Extended: creation flow, cap, missing keys, name escaping. |
| `README.md` | Secrets and the creation flow. |

---

### Task 1: Stage 2 prerequisites in `dashboard/data.py` and the app

**Files:**
- Modify: `dashboard/data.py`, `dashboard/app.py`
- Test: `tests/test_dashboard_data.py`, `tests/test_dashboard_app.py`

**Interfaces:**
- Produces:
  - `data.display_name(entry: dict) -> str`: the markdown-escaped name, falling back to the slug.
  - `data.load_signals(base_url, slug) -> list[dict] | None`: `None` means the file is missing (404).
  - `data.view_state(entry, signals: list | None) -> str`, adding `"empty"`.
  - `data.IndexUnavailable(Exception)`.
  - `data.load_index(base_url) -> list[dict] | None`: `None` for unset or 404; raises `IndexUnavailable` for other failures.
  - `data.MD_SPECIAL`.

- [ ] **Step 1: Update and add unit tests**

In `tests/test_dashboard_data.py`:
- change `test_404_is_empty_not_an_error` to assert `data.load_signals(BASE, "fintech") is None`;
- change `test_missing_index_means_fallback` to keep `is None` for a 404;
- change `test_bad_json_means_fallback` and `test_wrong_shape_means_fallback` to expect `pytest.raises(data.IndexUnavailable)`.

Then add:

```python
class TestIndexFailures:
    def test_server_error_raises_not_none(self, web):
        web.routes[BASE + "sectors.json"] = Resp(500)
        with pytest.raises(data.IndexUnavailable):
            data.load_index(BASE)


class TestDisplayName:
    @pytest.mark.parametrize("entry,expected", [
        ({"slug": "fintech", "name": "Fintech & payments"}, "Fintech & payments"),
        ({"slug": "energy"}, "energy"),
        ({"slug": "energy", "name": ""}, "energy"),
        ({"slug": "energy", "name": 42}, "42"),
        ({"slug": "x", "name": "*Energy* [x](javascript:alert(1))"},
         r"\*Energy\* \[x\]\(javascript\:alert\(1\)\)"),
        ({"slug": "x", "name": "a_b `c` #d ~e |f >g :h"},
         r"a\_b \`c\` \#d \~e \|f \>g \:h"),
    ])
    def test_escapes_markdown(self, entry, expected):
        assert data.display_name(entry) == expected


class TestEmptyState:
    @pytest.mark.parametrize("entry,signals,expected", [
        ({"status": "ready"}, [], "empty"),
        ({"status": "ready"}, None, "setting_up"),
        ({"status": "setting_up"}, None, "setting_up"),
        ({"status": "setting_up"}, [], "empty"),
        ({"status": "error"}, None, "error_empty"),
        ({"status": "error"}, [], "error_empty"),
        ({"status": "ready"}, [{"id": "a"}], "ready"),
    ])
    def test_states(self, entry, signals, expected):
        assert data.view_state(entry, signals) == expected
```

Update `TestViewState`'s existing parametrize: `({"status": "ready"}, [], "setting_up")` becomes `({"status": "ready"}, None, "setting_up")`. Also add `({"status": "ready"}, [], "empty")`.

- [ ] **Step 2: Run the tests to confirm they fail**

Run: `.venv/bin/python -m pytest tests/test_dashboard_data.py -q`
Expected: failures for `display_name`, `IndexUnavailable` and the `None`/`"empty"` cases.

- [ ] **Step 3: Implement in `dashboard/data.py`**

```python
# Characters Streamlit renders as markdown (or directives) in labels.
MD_SPECIAL = set("\\*_`[]():#~|>")


class IndexUnavailable(Exception):
    """The sector index exists but couldn't be read (network, server or bad
    JSON). Raised so the cached loader doesn't cache the failure."""


def display_name(entry: dict) -> str:
    """A sector's name, safe to put in a Streamlit label: coerced to text,
    falling back to the slug, with markdown characters escaped."""
    name = entry.get("name")
    text = str(name) if name not in (None, "") else str(entry.get("slug", ""))
    return "".join("\\" + ch if ch in MD_SPECIAL else ch for ch in text)
```

Replace `load_index`:

```python
def load_index(base_url: str | None) -> list[dict] | None:
    """The sector index; None means "use the legacy single file" (unset, or
    no index on main yet). Any other failure raises IndexUnavailable, so the
    app falls back for that run only rather than caching it for ten minutes."""
    base_url = _base(base_url)
    if not base_url:
        return None
    url = base_url + "sectors.json"
    try:
        resp = requests.get(url, timeout=20)
    except Exception as exc:
        raise IndexUnavailable(f"Couldn't reach {url}: {exc}") from exc
    if resp.status_code == 404:
        logger.info("No sector index at %s — using the legacy data file", base_url)
        return None
    try:
        resp.raise_for_status()
        index = resp.json()
    except Exception as exc:
        raise IndexUnavailable(f"Couldn't read {url}: {exc}") from exc
    if not isinstance(index, list):
        raise IndexUnavailable(f"{url} is not a list")
    return index
```

In `load_signals`, change the 404 branch to `return None`, and update the docstring: `None` means the file isn't there yet, and `[]` means the sector ran and found nothing.

Replace `view_state`:

```python
def view_state(entry: dict, signals: list[dict] | None) -> str:
    """What the page shows under the header for this sector. signals is None
    when the sector's file doesn't exist yet."""
    if entry.get("status") == "error":
        return "error_with_data" if signals else "error_empty"
    if signals is None:
        return "setting_up"
    return "ready" if signals else "empty"
```

- [ ] **Step 4: Wire into `dashboard/app.py`**

- **Index failures.** In `main()`, replace `index = load_index()` with:

  ```python
  try:
      index = load_index()
  except data.IndexUnavailable:
      index = None  # this run only: the failure isn't cached
  ```
- **Sector rules.** Replace `@st.cache_resource def sector_rules(slug)` with a TTL cache. A gambling fallback is still returned, but not cached for a sector whose config may arrive soon:

  ```python
  @st.cache_data(ttl=600, show_spinner=False)
  def _cached_rules(slug: str):
      return data.load_sector_or_none(slug)


  def sector_rules(slug: str):
      """The sector's config, refreshed every ten minutes so a newly created
      sector's rules are picked up. A missing config falls back to gambling's
      rules without caching that fallback."""
      return _cached_rules(slug) or data.sector_rules(data.GAMBLING)
  ```

  Add to `dashboard/data.py`:

  ```python
  def load_sector_or_none(slug: str):
      if not _is_slug(slug):
          return None
      try:
          return load_sector(slug)
      except SectorConfigError:
          return None
  ```

  `st.cache_data` pickles the return value. `Sector` is a plain dataclass, so this is fine. Check it with the AppTest.
- **Display names.** Use `data.display_name(...)` everywhere a sector name reaches a Streamlit label or copy:
  - in `_sector_switcher`, the popover label is `data.display_name(current)` and each row's label is `data.display_name(entry) + note`;
  - in `main()`, `name = data.display_name(current)`;
  - `st.session_state["sector_name"] = data.display_name(current)`.

  The HTML contexts (`_sector_state_block`, the watchlist copy) already `html.escape`. Escaping the markdown first then shows backslashes in HTML. So for HTML contexts, use the raw text: add `data.plain_name(entry) -> str` (the same coercion without escaping), and pass `plain_name` to `html.escape` users. Store both:

  ```python
  st.session_state["sector_name"] = data.plain_name(current)  # HTML contexts escape it
  name_md = data.display_name(current)                        # Streamlit labels
  name = data.plain_name(current)                              # html.escape'd blocks
  ```

  ```python
  def plain_name(entry: dict) -> str:
      name = entry.get("name")
      return str(name) if name not in (None, "") else str(entry.get("slug", ""))
  ```

  `display_name` then becomes `"".join(... for ch in plain_name(entry))`. Add a unit test that `plain_name({"slug": "x", "name": 42}) == "42"`.
- **The empty state.** In `main()`, after the existing `setting_up` branch, add:

  ```python
  if state == "empty":
      _sector_state_block("No signals yet", f"{name} is set up, but nothing has come "
                          "through yet. New signals will appear here as they're found.")
      return
  ```

  The legacy path's `load_legacy_signals` returns a list, so legacy is unaffected.

- [ ] **Step 5: AppTests**

Append to `tests/test_dashboard_app.py`, using its existing `serve`, `app`, `sector_routes`, `Resp`, `BASE` and `INDEX`:

```python
def test_markdown_in_a_sector_name_renders_literally(monkeypatch):
    index = INDEX + [{"slug": "odd", "name": "*Odd* [x](javascript:alert(1))", "status": "ready"}]
    serve(monkeypatch, sector_routes(index))
    at = app().run()
    assert not at.exception
    labels = [b.proto.label for b in at.button if b.key and "sectoropt" in b.key]
    assert r"\*Odd\* \[x\]\(javascript\:alert\(1\)\)" in labels[-1] or any(
        r"\*Odd\*" in label for label in labels)


def test_ready_sector_with_empty_file_shows_no_signals_yet(monkeypatch):
    routes = sector_routes()
    routes[BASE + "fintech/signals.json"] = Resp(payload=[])
    serve(monkeypatch, routes)
    at = app({"sector": "fintech"}).run()
    assert not at.exception
    body = " ".join(html.unescape(m.value) for m in at.markdown)
    assert "Fintech & payments is set up, but nothing has come through yet." in body


def test_index_server_error_falls_back_for_this_run(monkeypatch):
    routes = sector_routes()
    routes[BASE + "sectors.json"] = Resp(500)
    routes[LEGACY_SIGNALS] = Resp(payload=GAMBLING)
    serve(monkeypatch, routes)
    at = app().run()
    assert not at.exception and at.tabs
```

Add `import html` at the top if it's missing. If the button label lookup differs in this AppTest version (the file's existing tests read the popover label via `proto.popover.label`), adapt the lookup and keep the assertion: the escaped form is present, and the raw `*Odd*` is not.

- [ ] **Step 6: Run everything**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add dashboard/data.py dashboard/app.py tests/test_dashboard_data.py tests/test_dashboard_app.py
git commit -m "Escape sector names, tell empty from missing data, don't cache index failures

Co-Authored-By: <model> <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_016YJv2T4yhVoixtyDTkv1fZ"
```

---

### Task 2: `parse_sector`, validating a dict without a file

**Files:**
- Modify: `src/sectors.py`
- Test: `tests/test_sectors.py`

**Interfaces:**
- Produces: `parse_sector(raw: dict, slug: str) -> Sector`. It raises `SectorConfigError`, whose path is `config/sectors/<slug>.yaml` (in memory). There are no user additions.
- `load_sector` keeps its behaviour and is now built on the same `_build`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_sectors.py`:

```python
class TestParseSector:
    def test_valid_dict(self):
        s = sectors.parse_sector(dict(MINIMAL), "fintech")
        assert s.slug == "fintech" and s.companies == []

    def test_slug_mismatch(self):
        with pytest.raises(SectorConfigError, match="slug"):
            sectors.parse_sector({**MINIMAL, "slug": "other"}, "fintech")

    def test_same_errors_as_load_sector(self):
        bad = {**MINIMAL, "sources": {"fca_scraper": {}}}
        with pytest.raises(SectorConfigError, match="fca_scraper"):
            sectors.parse_sector(bad, "fintech")

    def test_unquoted_number_rejected(self):
        bad = {**MINIMAL, "companies": [{"name": "X Ltd", "company_number": 4241161}]}
        with pytest.raises(SectorConfigError, match="company_number"):
            sectors.parse_sector(bad, "fintech")

    def test_error_names_the_virtual_file(self):
        with pytest.raises(SectorConfigError, match="fintech.yaml"):
            sectors.parse_sector({k: v for k, v in MINIMAL.items() if k != "brief"}, "fintech")
```

- [ ] **Step 2: Run the tests to confirm they fail**

Run: `.venv/bin/python -m pytest tests/test_sectors.py -q -k ParseSector`
Expected: FAIL (`parse_sector` is not defined).

- [ ] **Step 3: Implement**

In `src/sectors.py`, after `_build`:

```python
def parse_sector(raw: dict, slug: str) -> Sector:
    """Validate a sector config held in memory (e.g. a Claude draft) with the
    same rules as a file on disk. Errors name the file it would be saved as."""
    if not isinstance(raw, dict):
        raise SectorConfigError(CONFIG_DIR / f"{slug}.yaml", "yaml", "top level must be a mapping")
    path = CONFIG_DIR / f"{slug}.yaml"
    return _build(path, raw, {}, CONFIG_DIR / f"{slug}.user.yaml")
```

`_build` checks `slug != path.stem`, which handles the mismatch case.

- [ ] **Step 4: Run the tests**

Run: `.venv/bin/python -m pytest tests/test_sectors.py tests/test_gambling_equivalence.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/sectors.py tests/test_sectors.py
git commit -m "Validate a sector config held in memory with parse_sector

Co-Authored-By: <model> <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_016YJv2T4yhVoixtyDTkv1fZ"
```

---

### Task 3: `src/drafting.py`, Claude's draft, normalised and verified

**Files:**
- Create: `src/drafting.py`
- Test: `tests/test_drafting.py`

**Interfaces:**
- Consumes:
  - `src.sectors`: `parse_sector`, `PROMPT_FIELDS`, `KNOWN_SOURCES`, `SLUG_RE`, `SectorConfigError`, `CONFIG_DIR`;
  - `src.categories.CORE_RULE_NAMES`;
  - `src.entities.match_key`.
- Produces:
  - `GENERIC_SOURCES: tuple[str, ...]`;
  - `DEFAULT_SOURCE_SETTINGS: dict[str, dict]`;
  - `MAX_PATTERN = 200`;
  - `slugify(name) -> str`;
  - `unique_slug(name, existing: set[str]) -> str`;
  - `class CompaniesHouse` with `__init__(api_key, get=requests.get)` and `lookup(number) -> dict | None`;
  - `verify_companies(companies: list[dict], ch: CompaniesHouse | None) -> list[dict]`. Each row gets `verified: bool`, and `company_number` is `None` unless verified;
  - `normalise_draft(raw: dict, existing: set[str], now: datetime | None = None) -> dict`, the config dict without the `verified` keys;
  - `@dataclass Draft`: `slug: str`, `config: dict`, `companies: list[dict]` (with `verified`);
  - `class DraftError(Exception)`;
  - `draft_sector(description: str, existing_slugs: set[str], client, ch: CompaniesHouse | None = None, now=None) -> Draft`;
  - `PROPOSE_SECTOR_TOOL: dict`.

- [ ] **Step 1: Write the failing tests**

`tests/test_drafting.py`:

```python
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from src import drafting
from src.sectors import PROMPT_FIELDS, parse_sector

NOW = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)


def proposal(**over):
    base = {
        "name": "Energy retail",
        "brief": "UK energy suppliers and the regulators around them.",
        "prompt": {f: f"energy {f}" for f in PROMPT_FIELDS},
        "keywords": ["energy supplier", "price cap"],
        "companies": [
            {"name": "Octopus Energy Limited", "company_number": "09263424", "aliases": ["Octopus"]},
            {"name": "OVO Energy Ltd", "company_number": "06890795", "aliases": []},
            {"name": "E.ON UK plc", "company_number": None, "aliases": ["E.ON"]},
        ],
        "tickers": {"CNA": "Centrica"},
        "categories": [
            {"name": "Price cap and tariffs", "pattern": "price cap|tariff", "before": "Enforcement action"},
        ],
        "signal_type_fallback": {},
        "excluded_bodies": ["ofgem"],
        "sources": ["companies_house", "gazette", "dcms", "gambling_commission", "bgc"],
        "dcms_organisation": "department-for-energy-security-and-net-zero",
    }
    base.update(over)
    return base


class FakeCH:
    def __init__(self, records):
        self.records = records
        self.calls = []

    def lookup(self, number):
        self.calls.append(number)
        return self.records.get(number)


class FakeClient:
    """Returns queued tool inputs (or raw content blocks) one call at a time."""
    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kw):
        self.requests.append(kw)
        item = self.responses.pop(0)
        if isinstance(item, list):
            content = item
        else:
            content = [SimpleNamespace(type="tool_use", name="propose_sector", input=item)]
        return SimpleNamespace(content=content, stop_reason="tool_use")


class TestSlugs:
    @pytest.mark.parametrize("name,expected", [
        ("Energy retail", "energy-retail"),
        ("Gambling & gaming", "gambling-gaming"),
        ("  UK  Water -- Utilities ", "uk-water-utilities"),
        ("!!!", "sector"),
        ("Ä" * 3, "sector"),
        ("x" * 80, "x" * 40),
    ])
    def test_slugify(self, name, expected):
        assert drafting.slugify(name) == expected

    def test_unique(self):
        assert drafting.unique_slug("Gambling & gaming", {"gambling-gaming"}) == "gambling-gaming-2"
        assert drafting.unique_slug("Gambling & gaming", {"gambling-gaming", "gambling-gaming-2"}) == "gambling-gaming-3"


class TestNormalise:
    def test_strips_gambling_only_sources_and_fills_settings(self):
        cfg = drafting.normalise_draft(proposal(), set(), now=NOW)
        assert set(cfg["sources"]) == {"companies_house", "gazette", "dcms"}
        assert cfg["sources"]["dcms"]["organisation"] == "department-for-energy-security-and-net-zero"
        assert cfg["sources"]["companies_house"] == drafting.DEFAULT_SOURCE_SETTINGS["companies_house"]

    def test_drops_bad_categories(self):
        cats = [
            {"name": "Ok", "pattern": "ok", "before": "Enforcement action"},
            {"name": "Long", "pattern": "a" * 201, "before": "Enforcement action"},
            {"name": "Broken", "pattern": "x(", "before": "Enforcement action"},
            {"name": "Nowhere", "pattern": "y", "before": "Not a rule"},
        ]
        cfg = drafting.normalise_draft(proposal(categories=cats), set(), now=NOW)
        assert [c["name"] for c in cfg["categories"]] == ["Ok"]

    def test_fallback_to_a_dropped_category_is_removed(self):
        cats = [{"name": "Broken", "pattern": "x(", "before": "Enforcement action"}]
        cfg = drafting.normalise_draft(proposal(categories=cats,
                                                signal_type_fallback={"regulatory": "Broken"}),
                                       set(), now=NOW)
        assert cfg["signal_type_fallback"] == {}

    def test_companies_deduplicated_and_capped(self):
        companies = [{"name": f"Co {i} Ltd", "company_number": None, "aliases": []} for i in range(20)]
        companies.append({"name": "Co 1 Ltd", "company_number": None, "aliases": []})
        cfg = drafting.normalise_draft(proposal(companies=companies), set(), now=NOW)
        assert len(cfg["companies"]) == 12 and len({c["name"] for c in cfg["companies"]}) == 12

    def test_slug_and_created_at(self):
        cfg = drafting.normalise_draft(proposal(name="Gambling & gaming"), {"gambling-gaming"}, now=NOW)
        assert cfg["slug"] == "gambling-gaming-2"
        assert cfg["created_at"] == "2026-10-08T12:00:00+00:00"

    def test_output_validates(self):
        cfg = drafting.normalise_draft(proposal(), set(), now=NOW)
        parse_sector(cfg, cfg["slug"])

    @pytest.mark.parametrize("bad", [
        {"companies": "Octopus"},
        {"keywords": "energy"},
        {"prompt": "nope"},
        {"name": ""},
        {"sources": "gazette"},
    ])
    def test_wrong_shapes_raise_value_error(self, bad):
        with pytest.raises(ValueError):
            drafting.normalise_draft(proposal(**bad), set(), now=NOW)


class TestVerify:
    def test_keeps_only_active_matching_numbers(self):
        ch = FakeCH({
            "09263424": {"company_name": "OCTOPUS ENERGY LIMITED", "company_status": "active"},
            "06890795": {"company_name": "SOMETHING ELSE LTD", "company_status": "active"},
        })
        rows = drafting.verify_companies(proposal()["companies"], ch)
        assert [(r["company_number"], r["verified"]) for r in rows] == [
            ("09263424", True), (None, False), (None, False)]

    def test_dissolved_is_cleared(self):
        ch = FakeCH({"09263424": {"company_name": "OCTOPUS ENERGY LIMITED", "company_status": "dissolved"}})
        rows = drafting.verify_companies(proposal()["companies"][:1], ch)
        assert rows[0]["company_number"] is None

    def test_no_key_clears_everything_without_lookups(self):
        rows = drafting.verify_companies(proposal()["companies"], None)
        assert all(r["company_number"] is None and r["verified"] is False for r in rows)

    @pytest.mark.parametrize("number", ["abc", "4241161", " 09263424 ", 9263424])
    def test_malformed_numbers_cleared_or_trimmed(self, number):
        ch = FakeCH({"09263424": {"company_name": "OCTOPUS ENERGY LIMITED", "company_status": "active"}})
        row = drafting.verify_companies([{"name": "Octopus Energy Limited", "company_number": number}], ch)[0]
        if number == " 09263424 ":
            assert row["company_number"] == "09263424" and row["verified"]
        else:
            assert row["company_number"] is None and not row["verified"]


class TestDraftSector:
    def test_happy_path(self):
        ch = FakeCH({"09263424": {"company_name": "OCTOPUS ENERGY LIMITED", "company_status": "active"}})
        client = FakeClient(proposal())
        d = drafting.draft_sector("UK energy suppliers", {"gambling", "fintech"}, client, ch, now=NOW)
        assert d.slug == "energy-retail"
        assert d.config["companies"][0]["company_number"] == "09263424"
        assert "verified" not in d.config["companies"][0]
        assert d.companies[0]["verified"] is True
        req = client.requests[0]
        assert req["tool_choice"] == {"type": "tool", "name": "propose_sector"}
        assert "UK energy suppliers" in req["messages"][0]["content"]

    def test_retries_once_then_succeeds(self):
        client = FakeClient(proposal(companies="nope"), proposal())
        d = drafting.draft_sector("UK energy suppliers", set(), client, None, now=NOW)
        assert d.slug == "energy-retail" and len(client.requests) == 2
        assert "companies" in client.requests[1]["messages"][-1]["content"]

    def test_two_failures_raise_draft_error(self):
        client = FakeClient(proposal(companies="nope"), proposal(prompt="nope"))
        with pytest.raises(drafting.DraftError):
            drafting.draft_sector("UK energy suppliers", set(), client, None, now=NOW)

    def test_no_tool_call_counts_as_failure(self):
        text_only = [SimpleNamespace(type="text", text="Sure! Here's a sector…")]
        client = FakeClient(text_only, proposal())
        d = drafting.draft_sector("UK energy suppliers", set(), client, None, now=NOW)
        assert d.slug == "energy-retail"

    def test_too_few_companies_is_a_failure(self):
        client = FakeClient(proposal(companies=[{"name": "Only Ltd"}]),
                            proposal(companies=[{"name": "Only Ltd"}]))
        with pytest.raises(drafting.DraftError):
            drafting.draft_sector("x" * 20, set(), client, None, now=NOW)

    @pytest.mark.parametrize("desc", ["short", "x" * 301, "   "])
    def test_description_length(self, desc):
        with pytest.raises(ValueError):
            drafting.draft_sector(desc, set(), FakeClient(), None, now=NOW)


class TestCompaniesHouseClient:
    def test_lookup_uses_basic_auth_and_returns_none_on_404(self):
        calls = []

        def fake_get(url, auth=None, timeout=None):
            calls.append((url, auth))
            if url.endswith("/09263424"):
                return SimpleNamespace(status_code=200, json=lambda: {"company_name": "X", "company_status": "active"},
                                       raise_for_status=lambda: None)
            return SimpleNamespace(status_code=404, json=lambda: {}, raise_for_status=lambda: None)

        ch = drafting.CompaniesHouse("key", get=fake_get)
        assert ch.lookup("09263424")["company_status"] == "active"
        assert ch.lookup("00000000") is None
        assert calls[0] == ("https://api.company-information.service.gov.uk/company/09263424", ("key", ""))

    def test_network_error_is_none(self):
        def boom(*a, **k):
            raise OSError("down")
        assert drafting.CompaniesHouse("key", get=boom).lookup("09263424") is None
```

- [ ] **Step 2: Run the tests to confirm they fail**

Run: `.venv/bin/python -m pytest tests/test_drafting.py -q`
Expected: FAIL (`No module named 'src.drafting'`).

- [ ] **Step 3: Implement `src/drafting.py`**

```python
"""Drafting a new sector with Claude, for the dashboard's premium "New sector"
flow. Claude proposes the whole config through one tool call; we normalise it
(slug, generic sources only, safe category patterns), check every company
number against Companies House, and validate the result with the same rules
as a hand-written config before anyone sees it.

No Streamlit here: dashboard/app.py calls draft_sector and shows the result.
"""

from __future__ import annotations

import os
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import requests

from src.categories import CORE_RULE_NAMES
from src.entities import match_key
from src.sectors import PROMPT_FIELDS, SLUG_RE, SectorConfigError, parse_sector

GENERIC_SOURCES = ("companies_house", "gazette", "dcms", "parliament", "asa",
                   "insolvency_service", "lse_rns")
MAX_PATTERN = 200
MIN_COMPANIES, MAX_COMPANIES = 3, 12
MIN_DESCRIPTION, MAX_DESCRIPTION = 10, 300
NUMBER_RE = re.compile(r"[0-9A-Z]{8}")

# Settings each source gets in a drafted sector (the fintech values).
DEFAULT_SOURCE_SETTINGS = {
    "companies_house": {"items_per_page": 25, "sleep_seconds": 0.6, "lookback_days": 365},
    "gazette": {"results_per_term": 20, "sleep_seconds": 1.0},
    "dcms": {"results_per_term": 20},
    "parliament": {"results_per_term": 20},
    "asa": {},
    "insolvency_service": {"sleep_seconds": 1.0},
    "lse_rns": {"skip_titles": [
        "holding(s) in company", "notification of major holdings",
        "director/pdmr shareholding", "transaction in own shares",
        "total voting rights", "block listing",
    ]},
}


class DraftError(Exception):
    """Claude's draft couldn't be turned into a valid sector, even on retry."""


@dataclass
class Draft:
    slug: str
    config: dict
    companies: list[dict] = field(default_factory=list)  # with "verified"


def slugify(name: str) -> str:
    text = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40].strip("-")
    return slug if slug and SLUG_RE.fullmatch(slug) else "sector"


def unique_slug(name: str, existing: set[str]) -> str:
    base = slugify(name)
    slug, n = base, 2
    while slug in existing:
        suffix = f"-{n}"
        slug = base[: 40 - len(suffix)] + suffix
        n += 1
    return slug


class CompaniesHouse:
    URL = "https://api.company-information.service.gov.uk/company/{}"

    def __init__(self, api_key: str, get=requests.get):
        self.api_key = api_key
        self._get = get

    def lookup(self, number: str) -> dict | None:
        try:
            resp = self._get(self.URL.format(number), auth=(self.api_key, ""), timeout=10)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return None


def _names_match(a: str, b: str) -> bool:
    ka, kb = match_key(a), match_key(b)
    return bool(ka and kb) and (ka == kb or ka in kb or kb in ka)


def verify_companies(companies: list[dict], ch: CompaniesHouse | None) -> list[dict]:
    """Each company with its number kept only if Companies House confirms it
    (active, matching name). Everything else is tracked by name alone."""
    out = []
    for company in companies:
        row = dict(company)
        raw = row.get("company_number")
        number = raw.strip().upper() if isinstance(raw, str) else None
        verified = False
        if ch is not None and number and NUMBER_RE.fullmatch(number):
            record = ch.lookup(number)
            verified = bool(record) and record.get("company_status") == "active" and \
                _names_match(record.get("company_name", ""), row.get("name", ""))
        row["company_number"] = number if verified else None
        row["verified"] = verified
        out.append(row)
    return out


def _require(cond: bool, message: str) -> None:
    if not cond:
        raise ValueError(message)


def normalise_draft(raw: dict, existing: set[str], now: datetime | None = None) -> dict:
    """Claude's proposal → a sector config dict. Raises ValueError for shapes
    that can't be repaired; drops parts that are merely unsafe."""
    _require(isinstance(raw, dict), "proposal must be an object")
    name = raw.get("name")
    _require(isinstance(name, str) and name.strip(), "name is required")
    _require(isinstance(raw.get("brief"), str) and raw["brief"].strip(), "brief is required")
    prompt = raw.get("prompt")
    _require(isinstance(prompt, dict), "prompt must be an object")
    for key in ("keywords", "companies", "excluded_bodies", "categories", "sources"):
        _require(isinstance(raw.get(key, []), list), f"{key} must be a list")
    _require(isinstance(raw.get("tickers", {}), dict), "tickers must be an object")
    _require(isinstance(raw.get("signal_type_fallback", {}), dict), "signal_type_fallback must be an object")

    companies, seen = [], set()
    for c in raw.get("companies", []):
        _require(isinstance(c, dict) and isinstance(c.get("name"), str), "each company needs a name")
        key = match_key(c["name"])
        if not key or key in seen:
            continue
        seen.add(key)
        aliases = c.get("aliases") or []
        companies.append({
            "name": c["name"].strip(),
            "company_number": c.get("company_number"),
            "aliases": [a for a in aliases if isinstance(a, str)] if isinstance(aliases, list) else [],
        })
    companies = companies[:MAX_COMPANIES]
    _require(len(companies) >= MIN_COMPANIES, f"need at least {MIN_COMPANIES} companies")

    categories = []
    for cat in raw.get("categories", []):
        if not (isinstance(cat, dict) and isinstance(cat.get("name"), str)
                and isinstance(cat.get("pattern"), str) and len(cat["pattern"]) <= MAX_PATTERN
                and cat.get("before") in CORE_RULE_NAMES):
            continue
        try:
            re.compile(cat["pattern"], re.I)
        except re.error:
            continue
        categories.append({"name": cat["name"], "pattern": cat["pattern"], "before": cat["before"]})
    allowed = CORE_RULE_NAMES | {c["name"] for c in categories} | {"Other"}
    fallback = {k: v for k, v in raw.get("signal_type_fallback", {}).items() if v in allowed}

    sources = {}
    for key in raw.get("sources", []):
        if key in GENERIC_SOURCES and key not in sources:
            sources[key] = dict(DEFAULT_SOURCE_SETTINGS[key])
    _require(bool(sources), "at least one generic source is required")
    org = raw.get("dcms_organisation")
    if "dcms" in sources and isinstance(org, str) and re.fullmatch(r"[a-z0-9-]{3,80}", org):
        sources["dcms"]["organisation"] = org

    now = now or datetime.now(timezone.utc)
    return {
        "slug": unique_slug(name, existing),
        "name": name.strip(),
        "brief": raw["brief"].strip(),
        "created_at": now.isoformat(),
        "prompt": {k: prompt.get(k) for k in PROMPT_FIELDS},
        "keywords": [k for k in raw.get("keywords", []) if isinstance(k, str) and k.strip()],
        "companies": companies,
        "tickers": {str(k): str(v) for k, v in raw.get("tickers", {}).items()},
        "categories": categories,
        "signal_type_fallback": fallback,
        "excluded_bodies": [b.lower() for b in raw.get("excluded_bodies", []) if isinstance(b, str)],
        "sources": sources,
    }


_EXAMPLE = Path("config/sectors/gambling.yaml")

PROPOSE_SECTOR_TOOL = {
    "name": "propose_sector",
    "description": "Propose a complete Sector Signal sector config.",
    "input_schema": {
        "type": "object",
        "required": ["name", "brief", "prompt", "keywords", "companies", "sources"],
        "properties": {
            "name": {"type": "string", "description": "Short display name, e.g. 'Energy retail'"},
            "brief": {"type": "string", "description": "One sentence on what the newsroom covers"},
            "prompt": {"type": "object", "required": list(PROMPT_FIELDS),
                       "properties": {f: {"type": "string"} for f in PROMPT_FIELDS}},
            "keywords": {"type": "array", "items": {"type": "string"}},
            "companies": {"type": "array", "items": {"type": "object", "required": ["name"], "properties": {
                "name": {"type": "string", "description": "Registered UK company name"},
                "company_number": {"type": ["string", "null"],
                                   "description": "8-character Companies House number, only if certain; else null"},
                "aliases": {"type": "array", "items": {"type": "string"}}}}},
            "tickers": {"type": "object", "additionalProperties": {"type": "string"},
                        "description": "LSE ticker -> company name, only certain ones"},
            "categories": {"type": "array", "items": {"type": "object", "required": ["name", "pattern", "before"],
                           "properties": {"name": {"type": "string"}, "pattern": {"type": "string"},
                                          "before": {"type": "string", "enum": sorted(CORE_RULE_NAMES)}}}},
            "signal_type_fallback": {"type": "object", "additionalProperties": {"type": "string"}},
            "excluded_bodies": {"type": "array", "items": {"type": "string"}},
            "sources": {"type": "array", "items": {"type": "string", "enum": list(GENERIC_SOURCES)}},
            "dcms_organisation": {"type": "string",
                                  "description": "GOV.UK organisation slug whose publications to search, "
                                                 "e.g. department-for-energy-security-and-net-zero"},
        },
    },
}


def _system_prompt() -> str:
    example = _EXAMPLE.read_text(encoding="utf-8") if _EXAMPLE.exists() else ""
    return (
        "You design sector configs for Sector Signal, a B2B newsroom tool that collects UK "
        "regulatory, corporate and parliamentary items about one industry and scores them for "
        "newsworthiness. Propose a config for the industry the user describes by calling "
        "propose_sector exactly once.\n\n"
        "Rules:\n"
        f"- prompt needs all of: {', '.join(PROMPT_FIELDS)}. Match the tone and length of the example.\n"
        f"- companies: {MIN_COMPANIES}-{MAX_COMPANIES} of the most important UK companies, using registered "
        "names. Give company_number only if you are certain of it; otherwise null.\n"
        f"- sources: choose from {', '.join(GENERIC_SOURCES)} only.\n"
        f"- categories: 2-4 industry-specific ones; each pattern a short case-insensitive regex "
        f"(at most {MAX_PATTERN} characters) that won't match routine corporate filings; before must be one "
        f"of: {', '.join(sorted(CORE_RULE_NAMES))}.\n"
        "- excluded_bodies: the industry's regulators and trade bodies, lower case.\n"
        "- tickers: only LSE tickers you are certain of.\n\n"
        "This is the existing gambling sector, as a worked example of the format and tone:\n\n" + example
    )


def _tool_input(response) -> dict:
    for block in getattr(response, "content", []) or []:
        if getattr(block, "type", None) == "tool_use" and getattr(block, "name", None) == "propose_sector":
            return block.input
    raise ValueError("no propose_sector tool call in the response")


def draft_sector(description: str, existing_slugs: set[str], client,
                 ch: CompaniesHouse | None = None, now: datetime | None = None) -> Draft:
    """Draft, normalise, verify and validate a sector. One retry with the
    validation error fed back; then DraftError."""
    description = (description or "").strip()
    if not (MIN_DESCRIPTION <= len(description) <= MAX_DESCRIPTION):
        raise ValueError(f"description must be {MIN_DESCRIPTION}-{MAX_DESCRIPTION} characters")
    model = os.environ.get("ANTHROPIC_MODEL") or "claude-sonnet-5"
    messages = [{"role": "user", "content": f"Industry to track: {description}"}]
    last_error = None
    for _ in range(2):
        response = client.messages.create(
            model=model, max_tokens=4000, system=_system_prompt(), messages=messages,
            tools=[PROPOSE_SECTOR_TOOL], tool_choice={"type": "tool", "name": "propose_sector"},
        )
        try:
            config = normalise_draft(_tool_input(response), existing_slugs, now=now)
            rows = verify_companies(config["companies"], ch)
            config["companies"] = [{k: v for k, v in r.items() if k != "verified"} for r in rows]
            parse_sector(config, config["slug"])
            return Draft(slug=config["slug"], config=config, companies=rows)
        except (ValueError, SectorConfigError) as exc:
            last_error = exc
            messages = messages + [{"role": "user", "content":
                                    f"That proposal was invalid: {exc}. Call propose_sector again, fixing it."}]
    raise DraftError(str(last_error))
```

Notes:
- If `match_key` is not exported from `src/entities.py` under that name, use what `src/cluster.py` imports. It does use `match_key`.
- In the retry message, the second `messages` list ends with a user turn and contains no assistant turn. That is acceptable to the API as consecutive user content only if it is merged: if the SDK rejects two consecutive user messages, put both texts in one user message. Make the test `test_retries_once_then_succeeds` assert on the final message's content, as written.

- [ ] **Step 4: Run the tests**

Run: `.venv/bin/python -m pytest tests/test_drafting.py -q`, then `.venv/bin/python -m pytest -q`.
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/drafting.py tests/test_drafting.py
git commit -m "Draft a sector config with Claude, verified and validated

Co-Authored-By: <model> <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_016YJv2T4yhVoixtyDTkv1fZ"
```

---

### Task 4: `dashboard/github.py`, saving and starting the run

**Files:**
- Create: `dashboard/github.py`
- Modify: `dashboard/app.py` (the watchlist helpers use the new client)
- Test: `tests/test_github.py`

**Interfaces:**
- Produces:
  - `OWNER = "LAKelly1411"`, `REPO = "signal-prototype"`, `BRANCH = "main"`, `WORKFLOW = "pipeline.yml"`.
  - `class GitHubError(Exception)`, `class FileExists(GitHubError)`.
  - `class GitHub`:
    - `__init__(token: str, http=requests)`;
    - `get_file(path) -> tuple[str, str] | None` returns (text, sha);
    - `put_file(path, text, message, sha=None, create_only=False)` raises `FileExists` if `create_only` and the file exists, and `GitHubError` on other failures;
    - `dispatch_workflow(inputs: dict)`.
  - `@dataclass SaveResult`: `saved: bool`, `indexed: bool`, `dispatched: bool`, `message: str`.
  - `save_sector(gh: GitHub, config: dict, index_entry: dict, today: str) -> SaveResult`, using the verbatim messages from Global Constraints.
  - `sector_yaml(config: dict, today: str) -> str`.

- [ ] **Step 1: Write the failing tests**

`tests/test_github.py`:

```python
import base64
import json
from types import SimpleNamespace

import pytest
import yaml

from dashboard import github
from src.sectors import parse_sector


def resp(status=200, payload=None):
    return SimpleNamespace(status_code=status, json=lambda: payload or {},
                           text=json.dumps(payload or {}))


class FakeHTTP:
    def __init__(self, routes):
        self.routes = routes   # (method, url-suffix) -> resp or callable
        self.calls = []

    def _hit(self, method, url, **kw):
        self.calls.append((method, url, kw))
        for (m, suffix), r in self.routes.items():
            if m == method and url.endswith(suffix):
                return r(kw) if callable(r) else r
        return resp(404)

    def get(self, url, **kw):
        return self._hit("GET", url, **kw)

    def put(self, url, **kw):
        return self._hit("PUT", url, **kw)

    def post(self, url, **kw):
        return self._hit("POST", url, **kw)


def b64(text):
    return base64.b64encode(text.encode()).decode()


CONFIG = {
    "slug": "energy-retail", "name": "Energy retail", "brief": "UK energy.",
    "created_at": "2026-10-08T12:00:00+00:00",
    "prompt": {f: "x" for f in __import__("src.sectors", fromlist=["PROMPT_FIELDS"]).PROMPT_FIELDS},
    "keywords": ["energy"], "companies": [{"name": "Octopus Energy Limited", "company_number": "09263424", "aliases": []}],
    "tickers": {}, "categories": [], "signal_type_fallback": {}, "excluded_bodies": [],
    "sources": {"gazette": {"results_per_term": 20, "sleep_seconds": 1.0}},
}
ENTRY = {"slug": "energy-retail", "name": "Energy retail", "brief": "UK energy.",
         "created_at": "2026-10-08T12:00:00+00:00", "status": "setting_up"}
INDEX = [{"slug": "gambling", "name": "Gambling & gaming", "status": "ready"}]

CFG_PATH = "/contents/config/sectors/energy-retail.yaml"
IDX_PATH = "/contents/data/sectors.json"
DISPATCH = "/actions/workflows/pipeline.yml/dispatches"


def test_sector_yaml_round_trips_and_validates():
    text = github.sector_yaml(CONFIG, "8 October 2026")
    assert text.startswith("# Drafted with Claude from the dashboard on 8 October 2026; reviewed by a user")
    parse_sector(yaml.safe_load(text), "energy-retail")


def test_happy_path_order_and_payloads():
    http = FakeHTTP({
        ("PUT", CFG_PATH): resp(201),
        ("GET", IDX_PATH): resp(200, {"content": b64(json.dumps(INDEX)), "sha": "abc"}),
        ("PUT", IDX_PATH): resp(200),
        ("POST", DISPATCH): resp(204),
    })
    result = github.save_sector(github.GitHub("t", http=http), CONFIG, ENTRY, "8 October 2026")
    assert (result.saved, result.indexed, result.dispatched) == (True, True, True)
    methods = [(m, u.split("/repos/LAKelly1411/signal-prototype")[1]) for m, u, _ in http.calls]
    assert methods == [("GET", CFG_PATH), ("PUT", CFG_PATH), ("GET", IDX_PATH), ("PUT", IDX_PATH), ("POST", DISPATCH)]
    idx_put = http.calls[3][2]["json"]
    assert idx_put["sha"] == "abc" and idx_put["branch"] == "main"
    written = json.loads(base64.b64decode(idx_put["content"]))
    assert [e["slug"] for e in written] == ["energy-retail", "gambling"]
    assert http.calls[4][2]["json"] == {"ref": "main", "inputs": {"sector": ""}}


def test_existing_config_stops_everything():
    http = FakeHTTP({("GET", CFG_PATH): resp(200, {"content": b64("x"), "sha": "s"})})
    result = github.save_sector(github.GitHub("t", http=http), CONFIG, ENTRY, "d")
    assert not result.saved and not result.indexed and not result.dispatched
    assert result.message == "We couldn't save the sector. Please try again."
    assert [m for m, _, _ in http.calls] == ["GET"]


def test_config_put_failure_stops_index_and_dispatch():
    http = FakeHTTP({("PUT", CFG_PATH): resp(500)})
    result = github.save_sector(github.GitHub("t", http=http), CONFIG, ENTRY, "d")
    assert not result.saved and not result.dispatched
    assert all(not u.endswith(IDX_PATH) for _, u, _ in http.calls if _ == "PUT")


def test_index_conflict_still_dispatches():
    http = FakeHTTP({
        ("PUT", CFG_PATH): resp(201),
        ("GET", IDX_PATH): resp(200, {"content": b64(json.dumps(INDEX)), "sha": "abc"}),
        ("PUT", IDX_PATH): resp(409),
        ("POST", DISPATCH): resp(204),
    })
    result = github.save_sector(github.GitHub("t", http=http), CONFIG, ENTRY, "d")
    assert result.saved and not result.indexed and result.dispatched
    assert result.message == "Saved. It will appear in the menu after the next update."


def test_no_index_file_skips_index_but_dispatches():
    http = FakeHTTP({("PUT", CFG_PATH): resp(201), ("POST", DISPATCH): resp(204)})
    result = github.save_sector(github.GitHub("t", http=http), CONFIG, ENTRY, "d")
    assert result.saved and not result.indexed and result.dispatched


def test_dispatch_failure_message():
    http = FakeHTTP({
        ("PUT", CFG_PATH): resp(201),
        ("GET", IDX_PATH): resp(200, {"content": b64(json.dumps(INDEX)), "sha": "abc"}),
        ("PUT", IDX_PATH): resp(200),
        ("POST", DISPATCH): resp(403),
    })
    result = github.save_sector(github.GitHub("t", http=http), CONFIG, ENTRY, "d")
    assert result.saved and result.indexed and not result.dispatched
    assert result.message == "Saved. Its first update will run with the next scheduled one."


def test_index_entry_not_duplicated():
    existing = INDEX + [ENTRY]
    http = FakeHTTP({
        ("PUT", CFG_PATH): resp(201),
        ("GET", IDX_PATH): resp(200, {"content": b64(json.dumps(existing)), "sha": "abc"}),
        ("PUT", IDX_PATH): resp(200),
        ("POST", DISPATCH): resp(204),
    })
    github.save_sector(github.GitHub("t", http=http), CONFIG, ENTRY, "d")
    written = json.loads(base64.b64decode(http.calls[3][2]["json"]["content"]))
    assert [e["slug"] for e in written].count("energy-retail") == 1
```

- [ ] **Step 2: Run the tests to confirm they fail**

Run: `.venv/bin/python -m pytest tests/test_github.py -q`
Expected: FAIL (`cannot import name 'github'`).

- [ ] **Step 3: Implement `dashboard/github.py`**

```python
"""The dashboard's writes to the repo, over the GitHub API: watchlist
additions, new sector configs, the sector index, and starting a pipeline run.
No Streamlit here; dashboard/app.py builds a GitHub from its secrets."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass

import requests
import yaml

OWNER = "LAKelly1411"
REPO = "signal-prototype"
BRANCH = "main"
WORKFLOW = "pipeline.yml"
API = f"https://api.github.com/repos/{OWNER}/{REPO}"

MSG_NOT_SAVED = "We couldn't save the sector. Please try again."
MSG_NOT_INDEXED = "Saved. It will appear in the menu after the next update."
MSG_NOT_DISPATCHED = "Saved. Its first update will run with the next scheduled one."


class GitHubError(Exception):
    pass


class FileExists(GitHubError):
    pass


class GitHub:
    def __init__(self, token: str, http=requests):
        self.http = http
        self.headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github+json"}

    def get_file(self, path: str) -> tuple[str, str] | None:
        resp = self.http.get(f"{API}/contents/{path}", headers=self.headers,
                             params={"ref": BRANCH}, timeout=20)
        if resp.status_code == 404:
            return None
        if resp.status_code >= 400:
            raise GitHubError(f"GET {path}: {resp.status_code}")
        payload = resp.json()
        return base64.b64decode(payload["content"]).decode("utf-8"), payload["sha"]

    def put_file(self, path: str, text: str, message: str, sha: str | None = None,
                 create_only: bool = False) -> None:
        if create_only and self.get_file(path) is not None:
            raise FileExists(path)
        body = {"message": message, "branch": BRANCH,
                "content": base64.b64encode(text.encode("utf-8")).decode("ascii")}
        if sha:
            body["sha"] = sha
        resp = self.http.put(f"{API}/contents/{path}", headers=self.headers, json=body, timeout=20)
        if resp.status_code >= 400:
            raise GitHubError(f"PUT {path}: {resp.status_code}")

    def dispatch_workflow(self, inputs: dict) -> None:
        resp = self.http.post(f"{API}/actions/workflows/{WORKFLOW}/dispatches", headers=self.headers,
                              json={"ref": BRANCH, "inputs": inputs}, timeout=20)
        if resp.status_code >= 400:
            raise GitHubError(f"dispatch: {resp.status_code}")


@dataclass
class SaveResult:
    saved: bool
    indexed: bool
    dispatched: bool
    message: str


def sector_yaml(config: dict, today: str) -> str:
    header = f"# Drafted with Claude from the dashboard on {today}; reviewed by a user.\n"
    return header + yaml.safe_dump(config, sort_keys=False, allow_unicode=True)


def save_sector(gh: GitHub, config: dict, index_entry: dict, today: str) -> SaveResult:
    """Config first, then the index entry, then an all-sectors run. A later
    step only runs if the earlier one worked; nothing is left half-saved.

    The run covers every sector, not just the new one: GitHub keeps one pending
    run per concurrency group, so a single-sector dispatch could replace a
    queued scheduled run and gambling would miss an update."""
    slug = config["slug"]
    try:
        gh.put_file(f"config/sectors/{slug}.yaml", sector_yaml(config, today),
                    f"Add the {config['name']} sector via dashboard", create_only=True)
    except Exception:
        return SaveResult(False, False, False, MSG_NOT_SAVED)

    indexed = False
    try:
        current = gh.get_file("data/sectors.json")
        if current is not None:
            text, sha = current
            index = [e for e in json.loads(text) if isinstance(e, dict) and e.get("slug") != slug]
            index.append(index_entry)
            index.sort(key=lambda e: e.get("slug", ""))
            gh.put_file("data/sectors.json", json.dumps(index, indent=2, ensure_ascii=False),
                        f"List the {config['name']} sector", sha=sha)
            indexed = True
    except Exception:
        indexed = False

    try:
        gh.dispatch_workflow({"sector": ""})
        dispatched = True
    except Exception:
        dispatched = False

    if not dispatched:
        message = MSG_NOT_DISPATCHED
    elif not indexed and current is not None:
        message = MSG_NOT_INDEXED
    else:
        message = ""
    return SaveResult(True, indexed, dispatched, message)
```

`current` must be defined before the `try`; set `current = None` just above it. In `test_no_index_file_skips_index_but_dispatches`, the message is `""`, because a missing index on a legacy deploy is expected, not a failure.

- [ ] **Step 4: Move the watchlist onto the client**

In `dashboard/app.py`:
- Delete `GITHUB_OWNER`, `GITHUB_REPO` and `_github_headers`.
- Rewrite `_fetch_user_watchlist` and `add_operator_to_watchlist` to use `github.GitHub(st.secrets["GITHUB_TOKEN"])`, with `get_file` and `put_file(path, text, message, sha=sha)`.
- Keep their behaviour and messages identical.
- Add `from dashboard import github`.

- [ ] **Step 5: Run the tests**

Run: `.venv/bin/python -m pytest tests/test_github.py -q`, then `.venv/bin/python -m pytest -q`.
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add dashboard/github.py dashboard/app.py tests/test_github.py
git commit -m "Save sectors and start runs through a small GitHub client

Co-Authored-By: <model> <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_016YJv2T4yhVoixtyDTkv1fZ"
```

---

### Task 5: The new-sector dialog

**Files:**
- Modify: `dashboard/app.py`
- Test: `tests/test_dashboard_app.py`, `tests/test_new_sector.py` (new; pure helpers)

**Interfaces:**
- Consumes:
  - `drafting.draft_sector`, `drafting.CompaniesHouse`, `drafting.verify_companies`, `drafting.GENERIC_SOURCES`, `drafting.DraftError`;
  - `github.GitHub`, `github.save_sector`;
  - `sectors.parse_sector`;
  - `data.display_name`, `data.plain_name`.
- Produces:
  - Constants: `MAX_SECTORS = 10`, `MAX_DRAFTS = 5`.
  - Session keys:
    - `premium_unlocked`;
    - `ns_step`, one of `"upsell"`, `"describe"`, `"review"` or `"done"`;
    - `ns_draft` (a `drafting.Draft`), `ns_drafts_used`, `ns_error`, `ns_result`;
    - `pending_sectors` (a list of index entries).
  - Button keys: `sector-new`, `ns-unlock`, `ns-draft`, `ns-create`, `ns-restart`, `ns-done`.
  - Widget keys: `ns_description`, `ns_name`, `ns_brief`, `ns_keywords`, `ns_companies`, `ns_src_<source>`.
  - `apply_review(draft_config, *, name, brief, keywords, companies, sources) -> dict`, in a new pure module `dashboard/new_sector.py` so it can be unit tested.
  - `merge_pending(index, pending) -> list[dict]`, also in `dashboard/new_sector.py`.

- [ ] **Step 1: Pure helpers, with tests first**

`tests/test_new_sector.py`:

```python
from dashboard.new_sector import apply_review, merge_pending
from src.sectors import PROMPT_FIELDS, parse_sector

CONFIG = {
    "slug": "energy-retail", "name": "Energy retail", "brief": "UK energy.", "created_at": "2026-10-08T12:00:00+00:00",
    "prompt": {f: "x" for f in PROMPT_FIELDS}, "keywords": ["energy"],
    "companies": [{"name": "Octopus Energy Limited", "company_number": "09263424", "aliases": []}],
    "tickers": {}, "categories": [], "signal_type_fallback": {}, "excluded_bodies": [],
    "sources": {"gazette": {"results_per_term": 20, "sleep_seconds": 1.0},
                "companies_house": {"items_per_page": 25}},
}


def test_apply_review_edits_and_keeps_slug():
    out = apply_review(CONFIG, name="Energy suppliers", brief="UK energy suppliers.",
                       keywords=["energy", "tariff"],
                       companies=[{"name": "Octopus Energy Limited", "company_number": "09263424"},
                                  {"name": "OVO Energy Ltd", "company_number": ""}],
                       sources=["gazette"])
    assert out["slug"] == "energy-retail"            # slug is fixed at draft time
    assert out["name"] == "Energy suppliers"
    assert out["companies"][1]["company_number"] is None
    assert list(out["sources"]) == ["gazette"]
    parse_sector(out, out["slug"])


def test_apply_review_drops_blank_company_rows_and_coerces_numbers():
    out = apply_review(CONFIG, name="E", brief="b", keywords=[],
                       companies=[{"name": "  ", "company_number": "x"},
                                  {"name": "A Ltd", "company_number": 4241161},
                                  {"name": "B Ltd", "company_number": " abc "}],
                       sources=["gazette"])
    assert [c["name"] for c in out["companies"]] == ["A Ltd", "B Ltd"]
    assert all(c["company_number"] is None or isinstance(c["company_number"], str) for c in out["companies"])


def test_merge_pending_adds_until_remote_has_it():
    index = [{"slug": "gambling"}]
    pending = [{"slug": "energy-retail", "status": "setting_up"}]
    assert [e["slug"] for e in merge_pending(index, pending)] == ["gambling", "energy-retail"]
    assert merge_pending(index + [{"slug": "energy-retail", "status": "ready"}], pending)[-1]["status"] == "ready"
    assert merge_pending(None, pending) is None
```

`dashboard/new_sector.py`:

```python
"""Pure helpers for the dashboard's new-sector dialog."""

from __future__ import annotations

from src.drafting import GENERIC_SOURCES, DEFAULT_SOURCE_SETTINGS


def apply_review(config: dict, *, name: str, brief: str, keywords: list[str],
                 companies: list[dict], sources: list[str]) -> dict:
    """The draft with the review form's edits applied. Company numbers come
    back as text or None (verification happens separately, on create)."""
    out = dict(config)
    out["name"] = name.strip() or config["name"]
    out["brief"] = brief.strip() or config["brief"]
    out["keywords"] = [k.strip() for k in keywords if isinstance(k, str) and k.strip()]
    rows = []
    for c in companies:
        cname = str(c.get("name") or "").strip()
        if not cname:
            continue
        number = c.get("company_number")
        number = str(number).strip() if number not in (None, "") else None
        rows.append({"name": cname, "company_number": number or None,
                     "aliases": list(c.get("aliases") or [])})
    out["companies"] = rows
    out["sources"] = {s: dict(config["sources"].get(s, DEFAULT_SOURCE_SETTINGS[s]))
                      for s in sources if s in GENERIC_SOURCES}
    return out


def merge_pending(index: list[dict] | None, pending: list[dict]) -> list[dict] | None:
    """Sectors created this session but not yet in the (cached, CDN-delayed)
    remote index, appended to it. The remote entry wins once it appears."""
    if index is None:
        return None
    have = {e.get("slug") for e in index if isinstance(e, dict)}
    return list(index) + [p for p in pending if p["slug"] not in have]
```

Run `.venv/bin/python -m pytest tests/test_new_sector.py -q`, red then green.

- [ ] **Step 2: The dialog in `dashboard/app.py`**

Add the imports `from dashboard import new_sector` and `from src import drafting`, and the constants `MAX_SECTORS, MAX_DRAFTS = 10, 5`.

**Enable the row.** In `_sector_switcher`, replace the disabled `sector-new` button with:

```python
        at_cap = len(entries) >= MAX_SECTORS
        st.button("Sector limit reached" if at_cap else "New sector  :blue-background[PREMIUM]",
                  key="sector-new", icon=":material/add:", type="tertiary", width="stretch",
                  disabled=at_cap,
                  help="Contact us to add more sectors." if at_cap else None,
                  on_click=_open_new_sector)
        if st.session_state.get("ns_open"):
            _new_sector_dialog()
```

`st.dialog` can't open from inside a popover in every Streamlit version. If the AppTest or the browser shows the dialog not opening, set `ns_open` in the callback, and call `_new_sector_dialog()` from `main()` after the masthead renders, when `ns_open` is set. Clear `ns_open` on "Done" or when the dialog closes. Do it the way that works, and record it.

**Helpers:**

```python
def _open_new_sector() -> None:
    st.session_state["ns_open"] = True
    st.session_state["ns_step"] = "upsell" if not st.session_state.get("premium_unlocked") else "describe"
    st.session_state.pop("ns_error", None)


def _ns_go(step: str) -> None:
    st.session_state["ns_step"] = step
    st.session_state.pop("ns_error", None)


def _unlock() -> None:
    st.session_state["premium_unlocked"] = True
    _ns_go("describe")


def _anthropic_client():
    key = _secret("ANTHROPIC_API_KEY")
    if not key:
        return None
    import anthropic
    return anthropic.Anthropic(api_key=key, max_retries=2)


def _companies_house():
    key = _secret("COMPANIES_HOUSE_API_KEY")
    return drafting.CompaniesHouse(key) if key else None


def _existing_slugs() -> set[str]:
    try:
        index = load_index() or []
    except data.IndexUnavailable:
        index = []
    from src.sectors import list_sector_slugs
    pending = [p["slug"] for p in st.session_state.get("pending_sectors", [])]
    return {e.get("slug") for e in index if isinstance(e, dict)} | set(list_sector_slugs()) | set(pending)


def _run_draft() -> None:
    state = st.session_state
    client = _anthropic_client()
    if client is None:
        state["ns_error"] = "Drafting isn't switched on here yet."
        return
    if state.get("ns_drafts_used", 0) >= MAX_DRAFTS:
        state["ns_error"] = "You've reached the demo's draft limit."
        return
    state["ns_drafts_used"] = state.get("ns_drafts_used", 0) + 1
    try:
        draft = drafting.draft_sector(state.get("ns_description", ""), _existing_slugs(),
                                      client, _companies_house())
    except ValueError:
        state["ns_error"] = "Please describe the industry in 10 to 300 characters."
        return
    except Exception:
        state["ns_error"] = "We couldn't draft that one. Try describing it differently."
        return
    state["ns_draft"] = draft
    for key in ("ns_name", "ns_brief", "ns_keywords", "ns_companies"):
        state.pop(key, None)
    _ns_go("review")


def _run_create() -> None:
    state = st.session_state
    draft = state["ns_draft"]
    edited = state.get("ns_companies_value") or draft.companies
    config = new_sector.apply_review(
        draft.config,
        name=state.get("ns_name", draft.config["name"]),
        brief=state.get("ns_brief", draft.config["brief"]),
        keywords=state.get("ns_keywords", draft.config["keywords"]),
        companies=edited,
        sources=[s for s in drafting.GENERIC_SOURCES if state.get(f"ns_src_{s}", s in draft.config["sources"])],
    )
    # Re-verify: an edited number must be confirmed again before it's saved.
    rows = drafting.verify_companies(config["companies"], _companies_house())
    config["companies"] = [{k: v for k, v in r.items() if k != "verified"} for r in rows]
    try:
        from src.sectors import parse_sector
        parse_sector(config, config["slug"])
    except Exception:
        state["ns_error"] = "We couldn't save the sector. Please try again."
        return
    token = _secret("GITHUB_TOKEN")
    entry = {"slug": config["slug"], "name": config["name"], "brief": config["brief"],
             "created_at": config["created_at"], "status": "setting_up"}
    result = github.save_sector(github.GitHub(token), config, entry,
                                datetime.now(timezone.utc).strftime("%-d %B %Y"))
    if not result.saved:
        state["ns_error"] = result.message
        return
    state.setdefault("pending_sectors", []).append(entry)
    state["ns_result"] = {"name": config["name"], "slug": config["slug"], "message": result.message}
    load_index.clear()
    _ns_go("done")


def _finish_new_sector() -> None:
    result = st.session_state.get("ns_result") or {}
    if result.get("slug"):
        _select_sector(result["slug"])
    for key in [k for k in st.session_state if str(k).startswith("ns_")]:
        del st.session_state[key]
```

`_select_sector` deletes `f_*` and `wl_*` keys. The `ns_*` keys are deleted afterwards, in the same callback.

**The dialog:**

```python
@st.dialog("New sector", width="medium")
def _new_sector_dialog() -> None:
    state = st.session_state
    step = state.get("ns_step", "upsell")

    if step == "upsell":
        st.markdown(
            f'<div class="wl-illustration">{_NEW_SECTOR_ILLUSTRATION}</div>'
            '<div class="wl-headline">Track any industry</div>'
            '<p class="wl-copy">Add a sector of your own, with its own sources, companies and '
            "scoring. New sectors are part of the premium add-on.</p>",
            unsafe_allow_html=True,
        )
        st.button("Unlock for demo", key="ns-unlock", type="primary", width="stretch", on_click=_unlock)
        sales = _secret("SALES_EMAIL")
        if sales:
            st.link_button("Talk to us", f"mailto:{sales}?subject=Sector%20Signal%20premium%20sectors",
                           type="tertiary", width="stretch")
        return

    if step == "done":
        result = state.get("ns_result", {})
        name = html.escape(result.get("name", "Your sector"))
        st.markdown(
            '<div class="wl-headline">Sector created</div>'
            f'<p class="wl-copy">{name} is being set up. We\'re gathering the first signals; '
            "this usually takes under an hour.</p>"
            + (f'<p class="wl-copy wl-muted">{html.escape(result["message"])}</p>' if result.get("message") else ""),
            unsafe_allow_html=True,
        )
        st.button("Done", key="ns-done", type="primary", width="stretch", on_click=_finish_new_sector)
        return

    if step == "describe":
        if not _secret("ANTHROPIC_API_KEY"):
            st.info("Drafting isn't switched on here yet.")
        used = state.get("ns_drafts_used", 0)
        st.text_area("Which industry should we track?", key="ns_description", max_chars=300,
                     placeholder="e.g. UK energy suppliers and the regulators around them")
        with st.spinner("Drafting your sector…", show_time=True):
            st.button("Draft it", key="ns-draft", type="primary", width="stretch",
                      disabled=used >= MAX_DRAFTS or not _secret("ANTHROPIC_API_KEY"),
                      on_click=_run_draft)
        if used >= MAX_DRAFTS:
            st.caption("You've reached the demo's draft limit.")
        if state.get("ns_error"):
            st.error(state["ns_error"])
        return

    # Review
    draft = state["ns_draft"]
    cfg = draft.config
    st.text_input("Name", value=cfg["name"], key="ns_name")
    st.text_input("One-line description", value=cfg["brief"], key="ns_brief")
    st.multiselect("Keywords", options=cfg["keywords"], default=cfg["keywords"],
                   accept_new_options=True, key="ns_keywords")
    rows = [{"Name": c["name"], "Companies House number": c.get("company_number") or "",
             "Verified": "✓" if c.get("verified") else "–"} for c in draft.companies]
    edited = st.data_editor(rows, key="ns_companies", num_rows="dynamic", width="stretch",
                            disabled=["Verified"], hide_index=True)
    state["ns_companies_value"] = [
        {"name": r.get("Name"), "company_number": r.get("Companies House number"),
         "aliases": next((c.get("aliases", []) for c in draft.companies if c["name"] == r.get("Name")), [])}
        for r in (edited.to_dict("records") if hasattr(edited, "to_dict") else edited)
    ]
    st.markdown("**Sources**")
    for s in drafting.GENERIC_SOURCES:
        st.checkbox(_source_name(s), value=s in cfg["sources"], key=f"ns_src_{s}")
    with st.expander("Advanced", key="ns-advanced"):
        st.caption("How Claude will score this sector. Shown for reference.")
        st.json({"prompt": cfg["prompt"], "categories": cfg["categories"],
                 "excluded_bodies": cfg["excluded_bodies"], "tickers": cfg["tickers"]}, expanded=False)
    can_save = bool(_secret("GITHUB_TOKEN"))
    if not can_save:
        st.info("Saving isn't switched on here yet.")
    st.button("Create sector", key="ns-create", type="primary", width="stretch",
              disabled=not can_save, on_click=_run_create)
    st.button("Start over", key="ns-restart", type="tertiary", width="stretch",
              on_click=_ns_go, args=("describe",))
    if state.get("ns_error"):
        st.error(state["ns_error"])
```

**Illustration.** Add `_NEW_SECTOR_ILLUSTRATION`, an on-brand SVG next to `_WATCHLIST_ILLUSTRATION`. Use the same palette (`#e5e3d3` newsprint background, `#000` ink, `#004FFF` cobalt, `#8DDBFF` light blue, white card). It shows a switcher card with three sector rows, the last one cobalt-edged with a "+" badge and a "PREMIUM" tag block.

**Pending sectors.** In `main()`, after the index is loaded, add:

```python
    index = new_sector.merge_pending(index, st.session_state.get("pending_sectors", []))
```

In legacy mode `merge_pending` returns `None`, so the switcher shows gambling only. That is correct, because a legacy deploy has no `sectors.json`, and the new sector appears after the next pipeline run.

`_source_name` already exists in `app.py` and maps source keys to display names; reuse it.

- [ ] **Step 3: AppTests**

Append to `tests/test_dashboard_app.py`. The drafting client and GitHub calls are faked by monkeypatching `src.drafting.draft_sector` (as the app imports it) and `dashboard.github.save_sector`:

```python
from src import drafting as drafting_mod
from dashboard import github as github_mod

DRAFT = drafting_mod.Draft(
    slug="energy-retail",
    config={"slug": "energy-retail", "name": "Energy retail", "brief": "UK energy.",
            "created_at": "2026-10-08T12:00:00+00:00",
            "prompt": {f: "x" for f in __import__("src.sectors", fromlist=["PROMPT_FIELDS"]).PROMPT_FIELDS},
            "keywords": ["energy"], "companies": [
                {"name": "Octopus Energy Limited", "company_number": "09263424", "aliases": []},
                {"name": "OVO Energy Ltd", "company_number": None, "aliases": []},
                {"name": "E.ON UK plc", "company_number": None, "aliases": []}],
            "tickers": {}, "categories": [], "signal_type_fallback": {}, "excluded_bodies": [],
            "sources": {"gazette": {"results_per_term": 20, "sleep_seconds": 1.0}}},
    companies=[{"name": "Octopus Energy Limited", "company_number": "09263424", "aliases": [], "verified": True},
               {"name": "OVO Energy Ltd", "company_number": None, "aliases": [], "verified": False},
               {"name": "E.ON UK plc", "company_number": None, "aliases": [], "verified": False}],
)


def creation_app(monkeypatch, *, anthropic=True, token=True, save=None):
    serve(monkeypatch, sector_routes())
    monkeypatch.setattr(drafting_mod, "draft_sector", lambda *a, **k: DRAFT)
    saved = []
    def fake_save(gh, config, entry, today):
        saved.append((config, entry))
        return save or github_mod.SaveResult(True, True, True, "")
    monkeypatch.setattr(github_mod, "save_sector", fake_save)
    at = app()
    if anthropic:
        at.secrets["ANTHROPIC_API_KEY"] = "k"
    if token:
        at.secrets["GITHUB_TOKEN"] = "t"
    return at, saved


def test_full_creation_flow(monkeypatch):
    at, saved = creation_app(monkeypatch)
    at.run()
    at.button(key="sector-new").click().run()
    assert any("Track any industry" in m.value for m in at.markdown)
    at.button(key="ns-unlock").click().run()
    at.text_area(key="ns_description").input("UK energy suppliers and their regulators").run()
    at.button(key="ns-draft").click().run()
    assert not at.exception
    assert at.text_input(key="ns_name").value == "Energy retail"
    at.button(key="ns-create").click().run()
    assert not at.exception
    assert saved and saved[0][1]["status"] == "setting_up"
    assert saved[0][0]["companies"][0]["company_number"] is None  # no CH key: re-verify clears it
    body = " ".join(html.unescape(m.value) for m in at.markdown)
    assert "Energy retail is being set up." in body
    at.button(key="ns-done").click().run()
    assert at.session_state["sector"] == "energy-retail"
    assert "We're gathering the first signals for Energy retail." in " ".join(
        html.unescape(m.value) for m in at.markdown)


def test_unlock_is_per_session(monkeypatch):
    at, _ = creation_app(monkeypatch)
    at.run()
    at.button(key="sector-new").click().run()
    at.button(key="ns-unlock").click().run()
    assert at.session_state["premium_unlocked"] is True
    fresh, _ = creation_app(monkeypatch)
    fresh.run()
    assert "premium_unlocked" not in fresh.session_state or not fresh.session_state["premium_unlocked"]


def test_no_anthropic_key_disables_drafting(monkeypatch):
    at, _ = creation_app(monkeypatch, anthropic=False)
    at.run()
    at.button(key="sector-new").click().run()
    at.button(key="ns-unlock").click().run()
    assert at.button(key="ns-draft").disabled
    assert any("Drafting isn't switched on here yet." in i.value for i in at.info)


def test_draft_limit(monkeypatch):
    at, _ = creation_app(monkeypatch)
    at.session_state["ns_drafts_used"] = 5
    at.session_state["premium_unlocked"] = True
    at.run()
    at.button(key="sector-new").click().run()
    assert at.button(key="ns-draft").disabled


def test_sector_cap_disables_the_row(monkeypatch):
    index = [{"slug": f"s{i}", "name": f"S{i}", "status": "ready"} for i in range(9)] + INDEX[:1]
    serve(monkeypatch, sector_routes(index))
    at = app().run()
    btn = at.button(key="sector-new")
    assert btn.disabled and "Sector limit reached" in btn.proto.label


def test_save_failure_keeps_the_review(monkeypatch):
    at, _ = creation_app(monkeypatch, save=github_mod.SaveResult(False, False, False,
                                                                 "We couldn't save the sector. Please try again."))
    at.run()
    at.button(key="sector-new").click().run()
    at.button(key="ns-unlock").click().run()
    at.text_area(key="ns_description").input("UK energy suppliers and their regulators").run()
    at.button(key="ns-draft").click().run()
    at.button(key="ns-create").click().run()
    assert any("We couldn't save the sector. Please try again." in e.value for e in at.error)
    assert at.session_state["ns_step"] == "review"
```

AppTest notes:
- AppTest can't drive `st.data_editor` edits. The flow test uses the draft's rows unchanged; `apply_review`'s unit tests cover edits.
- If dialogs don't render inside AppTest's element tree in 1.62, assert through session state and the `markdown` text, as above. If a widget inside the dialog can't be reached by key, set its value through `at.session_state[...]` before clicking. Record each adaptation.
- The app imports `draft_sector` through the module (`drafting.draft_sector(...)`), so monkeypatching the module attribute works. Keep it that way: no `from src.drafting import draft_sector` in `app.py`. The same applies to `github.save_sector`.

- [ ] **Step 4: Run everything**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass. Then `git status` is clean.

- [ ] **Step 5: Commit**

```bash
git add dashboard/app.py dashboard/new_sector.py tests/test_new_sector.py tests/test_dashboard_app.py
git commit -m "Let users create a sector: upsell, demo unlock, Claude draft, review, save

Co-Authored-By: <model> <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_016YJv2T4yhVoixtyDTkv1fZ"
```

---

### Task 6: README and the browser check

**Files:**
- Modify: `README.md`, and `dashboard/app.py` for any CSS fixes found

- [ ] **Step 1: README**

Add a "Creating a sector (premium demo)" section covering:
- the flow, from upsell to setting up;
- that the unlock lasts only for the browser session;
- the secrets: `ANTHROPIC_API_KEY` (required for drafting), `GITHUB_TOKEN` (needs contents read/write **and** actions write), `COMPANIES_HOUSE_API_KEY` (optional; without it, no company number is saved), `SALES_EMAIL` (optional);
- the limits: 10 sectors, 5 drafts per session;
- that creation commits to `main` and starts an all-sectors run, and why;
- that anyone with the dashboard password can create sectors in the demo.

- [ ] **Step 2: Browser check**

Run your own Streamlit on port 8502 with a private secrets file (`--secrets.files <tmp>/secrets.toml`), never the shared `.streamlit/secrets.toml`. Give it:
- `DATA_BASE_URL` pointing at a local fixture server (the tests' INDEX and fixtures) on port 8765;
- `ANTHROPIC_API_KEY = "fake"`;
- `GITHUB_TOKEN = "fake"`.

So no real calls are made, start the app through a tiny wrapper script in `$CLAUDE_JOB_DIR/tmp/` (or `/tmp`). The script monkeypatches `src.drafting.draft_sector` to return the test `DRAFT` after 2 seconds, and `dashboard.github.save_sector` to return success, then runs `dashboard/app.py` with `runpy`.

Use the Claude-in-Chrome tools if they're connected, in your own new tab, closed at the end. Otherwise use headless Chrome over DevTools at 1280px. Check:
- **Upsell:** the illustration is on brand, and the copy is verbatim.
- **Unlock → Describe:** the label, placeholder, and the spinner while drafting.
- **Review:** the fields are laid out cleanly, the Verified column reads ✓ / –, Advanced is collapsed, and the buttons are full width with consistent sizes (same as the watchlist dialog).
- **Created:** the copy is right, and "Done" lands on the new sector's "Setting up" block, with the switcher listing it.
- **Sector cap:** the row text and tooltip.

Fix CSS issues in `dashboard/app.py`. Save screenshots of each step to `$CLAUDE_JOB_DIR/tmp/` (or `/tmp`), and list them in the report. Stop every server you started.

- [ ] **Step 3: Full suite and commit**

Run: `.venv/bin/python -m pytest -q`. Expected: all pass.

```bash
git add README.md dashboard/app.py
git commit -m "Document premium sector creation; polish the dialog

Co-Authored-By: <model> <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_016YJv2T4yhVoixtyDTkv1fZ"
```

Real drafting against the Claude API, and a real save to the repo, are **not** part of this plan. They need real keys and the author's go-ahead, because a save commits to `main` and starts a paid run.
