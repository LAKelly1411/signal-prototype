# Premium sector creation (stage 3 of multi-sector Sector Signal)

**Date:** 2026-10-08
**Status:** Draft for review
**Author:** Renars Fazlutdinovs (with Claude)
**Branch:** `sector-creation` (from `pa-reskin`, which includes stages 1 and 2)
**Builds on:**
- `docs/superpowers/specs/2026-10-08-sector-aware-pipeline-design.md` (stage 1)
- `docs/superpowers/specs/2026-10-08-sector-switcher-design.md` (stage 2)

## Context and intent

Stages 1 and 2 made sectors real. Each sector:
- has its own config at `config/sectors/<slug>.yaml`;
- keeps its data in `data/<slug>/`;
- is listed in `data/sectors.json`;
- appears in the header switcher.

Today, adding a sector means hand-writing its YAML.

Stage 3 lets a dashboard user create a sector themselves. It is presented as a **premium add-on**, simulated for now with a demo unlock:

1. The switcher's "+ New sector · PREMIUM" row opens an **upsell dialog**. "Unlock for demo" unlocks creation for the current browser session.
2. The user describes the industry in a sentence. **Claude drafts the whole sector config.**
3. The user **reviews the draft in a friendly form**, with companies checked against Companies House, and creates it.
4. The config is committed through GitHub, the sector appears in the switcher as **"Setting up…"**, and **a pipeline run starts at once**.

Success means:
- the demo can be run end to end, from upsell to sector setting up, in under two minutes;
- every saved config passes the same validation as a hand-written one;
- no unverified company number is ever saved;
- nothing is left half-saved when a step fails.

## Scope

**In:**
- The stage 2 deferred prerequisites (§1).
- The upsell and unlock.
- Drafting with Claude.
- Company verification.
- The review form.
- Saving through GitHub.
- Run triggering.
- Limits.
- Tests and a browser check.

**Out:**
- Real billing or entitlement (the unlock is a demo).
- Editing or deleting sectors from the dashboard.
- New hand-built scrapers.
- Per-user accounts.

## Design

### 1. Prerequisites carried over from stage 2

These must land first. User-created sectors depend on them.

- **Display names are safe.**
  - `dashboard/data.py` gains `display_name(entry) -> str`. It coerces the name to `str`, falls back to the slug, and escapes Streamlit markdown: backslash-escape `` \ * _ ` [ ] ( ) : # ~ | > ``.
  - The switcher popover label, menu rows, state blocks and watchlist copy all use it.
  - HTML contexts still go through `html.escape`.
- **Empty versus missing signals.**
  - `load_signals` returns `None` on a 404 and `[]` for an empty file.
  - `view_state` gains `"empty"`, meaning ready with no signals. It shows the grey block: title "No signals yet", body "<Name> is set up, but nothing has come through yet. New signals will appear here as they're found."
  - Still `"setting_up"` when the file is missing.
- **Index failures aren't cached.**
  - `load_index` distinguishes a 404 (the legacy fallback, cacheable) from other failures. Other failures raise inside the cached function, so they aren't cached.
  - The app then falls back for that run only.
- **Sector rules are fresh.**
  - `sector_rules` is cached with a TTL of 600 seconds (`st.cache_data`, returning a copy), not `cache_resource` forever.
  - The gambling fallback for a missing config is not cached.

### 2. Unlock and upsell

- **Session flag.** `st.session_state["premium_unlocked"]` is false by default and is never persisted. A reload locks creation again.
- **The row.** "+ New sector · PREMIUM" becomes enabled and opens the `_new_sector_dialog` (`st.dialog`, width "medium").
- **Upsell step (locked):**
  - An on-brand SVG illustration in the watchlist dialog's visual language.
  - Headline: "Track any industry".
  - Copy: "Add a sector of your own, with its own sources, companies and scoring. New sectors are part of the premium add-on."
  - Primary button: "Unlock for demo".
  - Tertiary link: "Talk to us", a `mailto:` using the `SALES_EMAIL` secret, hidden if unset.
- **Sector cap.** When the index already lists `MAX_SECTORS = 10` sectors, the row is disabled. Its label is "Sector limit reached" and its tooltip is "Contact us to add more sectors."

### 3. Describe → draft

**Describe step.**
- One `st.text_area`, labelled "Which industry should we track?", with placeholder "e.g. UK energy suppliers and the regulators around them".
- 10 to 300 characters.
- Primary button: "Draft it".
- The dialog allows at most **5 drafts per session**. After that the button is disabled with "You've reached the demo's draft limit."

**Drafting** happens in a new Streamlit-free module, `src/drafting.py`:

`draft_sector(description: str, existing_slugs: set[str], client, ch_client=None) -> Draft`

- **One Claude call.** It uses `anthropic` tool use with a single tool, `propose_sector`, whose JSON schema mirrors the sector config:
  - name, brief, the nine `prompt` fields, keywords;
  - companies (name, company_number or null, aliases);
  - tickers;
  - categories (name, pattern, before);
  - signal_type_fallback, excluded_bodies;
  - sources (chosen from the generic set);
  - an optional `dcms.organisation` GOV.UK slug.

  The model is `os.environ.get("ANTHROPIC_MODEL") or "claude-sonnet-5"`, matching `src/score.py`.
- **The system prompt explains:**
  - the house style;
  - that gambling's config is the worked example (`config/sectors/gambling.yaml` is included verbatim);
  - that company numbers must be ones it is confident of, or null;
  - the generic sources allowed: `companies_house`, `gazette`, `dcms`, `parliament`, `asa`, `insolvency_service`, `lse_rns`;
  - the core category names available for `before`.
- **Normalising the draft:**
  - The slug comes from the name: lowercase, non-alphanumerics become `-`, collapsed, trimmed, at most 40 characters. It is made unique against `existing_slugs` with `-2`, `-3` and so on, and must pass `SLUG_RE`.
  - `created_at` is set to now (UTC ISO).
  - Sources are limited to the generic set; `gambling_commission` and `bgc` are dropped. Settings for each source are filled from safe defaults (the fintech values).
  - Each category pattern must be at most 200 characters and must compile. `before` must name a core rule. A category that fails any of these is dropped.
  - Companies: 3 to 12, deduplicated by name.
- **Company verification.** Each company number is checked with `GET https://api.company-information.service.gov.uk/company/<number>` (basic auth, key from `COMPANIES_HOUSE_API_KEY`).
  - It is kept only if `company_status == "active"` and the registered name matches the drafted name. A match means `src.entities.match_key` of both are equal, or one contains the other.
  - Otherwise the number is set to `null`, and the company keeps being tracked by name, for example through the Gazette.
  - Without a key, every number is set to `null`.
  - `Draft.companies` records `verified: bool` for each row.
- **Validation.** The normalised dict is validated by the same code as hand-written configs. `src/sectors.py` gains `parse_sector(raw: dict, slug: str) -> Sector`, which validates a dict without a file. `load_sector` calls it.
  - If validation fails, the draft is retried **once**, with the error message added to the user turn.
  - If it fails again, `DraftError` is raised. The dialog shows: "We couldn't draft that one. Try describing it differently."

### 4. Review form

- **Fields:**
  - Name (text).
  - One-line description (text). It becomes the `brief`.
  - Keywords (`st.multiselect` with `accept_new_options=True`).
  - Companies (`st.data_editor`): columns Name, Companies House number and Verified (read-only ✓/–). Editing a number clears its Verified tick, and it is re-checked on save.
  - Sources (checkboxes), from the generic set, defaulting to the draft's choice.
- **Advanced** (an expander, read-only): the prompt wording, categories with their patterns, excluded bodies and tickers.
- **Buttons:**
  - "Create sector" (primary, full width).
  - "Start over" (tertiary), which goes back to Describe and counts towards the draft limit only when a new draft is made.
- **On create:**
  1. Edits are applied to the draft.
  2. Any edited numbers are re-verified.
  3. The result is re-validated with `parse_sector`.
  4. Then save (§5).

### 5. Saving and triggering a run

A new module, `dashboard/github.py`, holds the existing GitHub helpers (moved out of `app.py`) plus the new ones:

- `put_file(path, text, message)`
- `get_file(path) -> (text, sha) | None`
- `dispatch_workflow(inputs)`

**Order** (each step only runs if the previous one succeeded):

1. **Commit** `config/sectors/<slug>.yaml`, dumped with `yaml.safe_dump(sort_keys=False, allow_unicode=True)` and a header comment saying "Drafted with Claude from the dashboard on <date>; reviewed by a user". The commit message is "Add the <Name> sector via dashboard". It fails if the file already exists, which guards against a race.
2. **Add the index entry** to `data/sectors.json`: read it, add `{"slug", "name", "brief", "created_at", "status": "setting_up"}`, and write it with the sha, so a concurrent write fails rather than clobbers. If the file doesn't exist yet (legacy deploy), skip this step; the pipeline's `refresh_index` adds the sector on its run.
3. **Start a run.** `POST /repos/{owner}/{repo}/actions/workflows/pipeline.yml/dispatches` with `{"ref": "main", "inputs": {"sector": ""}}`.
   - This is an **all-sectors run**, not a single-sector one. One concurrency group keeps at most one pending run, and a newer pending dispatch replaces an older one. If creation dispatched only its own sector, that could replace a queued scheduled run, and gambling would miss a cycle. An all-sectors run makes either replacement harmless. Already-scored signals aren't re-scored, so the extra cost is collection time, not Claude calls.

**After saving:**
- `load_index` is cleared.
- **The new entry is merged in locally.** GitHub raw serves cached files for up to about five minutes, so a fresh fetch of `sectors.json` may not include the new sector yet. The entry from step 2 is kept in `st.session_state["pending_sectors"]` and merged into the loaded index (by slug, without duplicates) until the remote index includes it. Otherwise `pick_sector` would fall back to gambling right after creation.
- The query param is set to the new slug.
- The Created step reads "<Name> is being set up. We're gathering the first signals; this usually takes under an hour."
- "Done" closes the dialog, and the page shows the new sector's "Setting up" block.

**Failures:**

| What fails | What happens |
|---|---|
| Step 1 | Nothing is saved. Message: "We couldn't save the sector. Please try again." |
| Step 2 | The config exists. Message: "Saved. It will appear in the menu after the next update." |
| Step 3 | The config and index entry exist. Message: "Saved. Its first update will run with the next scheduled one." |

**Secrets:**
- `ANTHROPIC_API_KEY` is required for drafting. Without it, Describe shows "Drafting isn't switched on here yet."
- `GITHUB_TOKEN` needs contents read/write and actions write. Without it, Review's create button is disabled, with "Saving isn't switched on here yet."
- `COMPANIES_HOUSE_API_KEY` is optional.
- `SALES_EMAIL` is optional.

## Testing

- **`src/drafting.py`**, with a fake Anthropic client returning canned `propose_sector` tool calls and a fake Companies House client:
  - normalisation;
  - slug generation and uniqueness;
  - gambling-only sources stripped;
  - long or invalid patterns dropped;
  - a wrong, inactive or name-mismatched number cleared;
  - no key means all numbers cleared;
  - one retry on a validation failure, then `DraftError`;
  - the output passes `parse_sector`.
- **`src/sectors.parse_sector`.** The stage 1 `load_sector` tests still pass, and dict-only validation has its own tests.
- **`dashboard/github.py`**, with `requests` faked:
  - the three-step order;
  - a step 1 failure stops steps 2 and 3;
  - a step 2 failure still dispatches;
  - an existing file fails step 1;
  - a sha conflict on the index is reported.
- **`dashboard/data.py`:** `display_name` escaping, `None` versus `[]` signals, the `"empty"` state, and index failures not being cached.
- **AppTest:**
  - locked upsell → unlock → describe → (faked) draft → review → create → setting-up;
  - the sector cap disables the row;
  - no Anthropic key shows the message;
  - the draft limit;
  - markdown in a sector name is rendered literally.
- **Browser check:** all four dialog steps and the setting-up result, against mock services, with screenshots.

## Risks

- **Draft quality.** Claude's prompt wording and categories shape every score for the new sector. The review form keeps them read-only for safety, so poor wording needs a hand edit of the YAML. That is acceptable for a demo; editing from the dashboard is out of scope.
- **Cost growth.** Each new sector adds about a day's worth of first-run scoring, then only new items. The 10-sector cap and the 5-drafts-per-session limit bound it.
- **Shared password.** Anyone with the dashboard password can unlock the demo and create a sector, and creation commits to the repo. Entitlement is simulated; real gating is out of scope and needed before a real launch.
- **Concurrent writes.** Two people creating sectors at once: the sha check on `sectors.json` makes the second index write fail. Its config is still saved, and the next run adds it to the index.
