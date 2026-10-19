# Signals ingest API: contract (draft v0)

**Status:** first draft, written for Renars, Steven and Lesley-Anne to refine.
Anything marked **[open]** is a question rather than a decision.

## What it's for

Every source sends what it finds to one service, in one shape.
- **n8n workflows** (newsroom alerts, 60+) keep doing the fetching, parsing
  and per-item Claude summary. Teams posting carries on unchanged.
- **The Python Sector Signal pipeline** (gambling, fintech) is treated the
  same way.

The service stores everything, adds embeddings, entities, patterns and
themes, and the Next.js frontend reads from it.

```
n8n workflow ──┐
               ├──▶  POST /v1/ingest  ──▶  Signals service  ──▶  Next.js frontend
Python pipeline┘     POST /v1/runs         (Steven: storage, embeddings, search,
                                            patterns and themes)
```

There are two calls:

| Call | When | Why |
|---|---|---|
| `POST /v1/ingest` | for each item found (single item or batch) | store the item; re-sending updates it |
| `POST /v1/runs` | once at the end of **every** run, even when nothing is new | so a source that quietly stops working gets noticed |

---

## Authentication

- Send `Authorization: Bearer <key>` on every request.
- There's one key per caller: `n8n` and `signals-pipeline`. Each is stored as
  a credential in n8n or a secret in the pipeline, and can be revoked on its
  own.
- The key says **who is calling**. The `source` field says **which source**
  the item is from. A caller may only post for sources the catalogue assigns
  to it.
- **[open]** One key per caller, or one per source? Per source is stricter but
  means 60+ keys to manage.

---

## `POST /v1/ingest`

### Request

The body is either one item, or a batch of up to 100:

```json
{ "items": [ { …item… }, { …item… } ] }
```

### Item fields

| Field | Type | Required | Rules |
|---|---|---|---|
| `source` | string | **yes** | The source's catalogue slug, lowercase with hyphens, e.g. `cqc`, `nmc`, `pfd`, `link-bank-closures`, `signals-bgc`. Unknown slugs are rejected. |
| `item_key` | string | **yes** | Stable and unique **within the source**. The same thing found again must give the same key. Max 200 characters. Re-sending a key **updates** the item; it never creates a duplicate. |
| `title` | string | **yes** | Plain text, max 500 characters. |
| `url` | string | **yes** | Link to the original, as `https://…`. |
| `published_at` | string | **yes** | ISO 8601. If there's no time zone, the service assumes Europe/London. |
| `published_precision` | `"datetime"` \| `"date"` \| `"month"` | no | Defaults to `datetime`. Use `month` when only the month is known (e.g. NMC's monthly tables). |
| `summary` | string | no | The AI summary the workflow already makes. Plain text. |
| `key_facts` | string[] | no | Short factual bullet points. |
| `caveats` | string[] | no | E.g. "Model reply was not valid JSON", or "Not for publication: always check source". |
| `score` | integer 0–100 | no | **Internal only.** Used for ranking and alert thresholds; never shown to users. Send it even when it's below the Teams threshold. |
| `streams` | string[] | no | Desks or topics the item belongs to, e.g. `["health", "social-care"]`. For the Python pipeline, the sector, e.g. `["gambling"]`. |
| `entities` | (string \| `{name, type}`)[] | no | Organisations and people named. `type` is one of `org`, `person`, `place`. Plain strings are allowed. The service normalises them. |
| `category` | string | no | The source's own category, if it has one. |
| `data` | object | no | **The workflow's whole item, as-is.** Nothing in it is required. Up to 256 KB. Send PDF links, not PDF contents. |
| `run_id` | string | no | The n8n execution ID or pipeline run ID, which links the item to its run report. |

**Rules:**
- **Send every item, not just the newsworthy ones.** Post before any score
  threshold, so the service can show trends. The threshold only decides what
  goes to Teams.
- **Updates replace.** A re-sent item replaces the stored fields. The service
  keeps `first_seen_at` and sets `last_seen_at`.
- **Unknown fields are ignored**, apart from `data`, which is kept whole.
  Adding a field never breaks a workflow.
- **[open]** Should a re-send with an *older* `published_at` be ignored, in
  case it's a stale replay?

### Response

`200 OK` returns a result for each item, in the same order:

```json
{
  "results": [
    { "item_key": "cqc-1-1234567890-2026-10-13", "status": "created" },
    { "item_key": "cqc-1-0987654321-2026-10-13", "status": "unchanged" },
    { "item_key": "", "status": "rejected", "errors": ["item_key is required"] }
  ]
}
```

- **`status`** is one of `created`, `updated`, `unchanged` or `rejected`.
- **A batch is never all-or-nothing.** Good items are stored even when others
  are rejected.
- **Other responses:**

| Code | Meaning |
|---|---|
| `401` | Bad key |
| `403` | The key can't post for that source |
| `413` | Body over 1 MB |
| `429` | Too many requests. Retry after `Retry-After` seconds |
| `5xx` | Retry with back-off. Safe to retry, because `item_key` makes it idempotent |

---

## `POST /v1/runs`

Send this at the end of every run, success or failure. Use n8n's error
workflow for runs that crash.

```json
{
  "source": "cqc",
  "run_id": "n8n-exec-48213",
  "started_at": "2026-10-19T14:00:00Z",
  "finished_at": "2026-10-19T14:00:41Z",
  "status": "ok",
  "items_found": 37,
  "items_sent": 3,
  "error": null
}
```

| Field | Rules |
|---|---|
| `status` | `ok` (ran, may have found nothing new), `empty` (the source returned nothing, which often means a layout change), or `error` (the run failed) |
| `items_found` | What the source listed this run, before removing ones already seen |
| `items_sent` | How many were posted to `/v1/ingest` |
| `error` | Short message when `status` is `error` |

The service compares runs with the catalogue's expected schedule. A source
that misses its runs, or keeps reporting `empty` or `error`, gets flagged.
**[open]** Flagged where: Teams, the dashboard, or both?

---

## Examples

### CQC (n8n)

The workflow's "Assess Ratings" node already builds `item_key`, `stream(s)`,
`title`, `link` and `published`, and "Score Item" adds the summary and facts.

```json
{
  "source": "cqc",
  "item_key": "cqc-1-1234567890-2026-10-13",
  "title": "Bedford Road",
  "url": "https://www.cqc.org.uk/location/1-1234567890",
  "published_at": "2026-10-13T00:01:00",
  "summary": "Haringey care home run by Certitude rated Requires improvement in its first rating.",
  "key_facts": ["6 beds", "Provider: Certitude", "First rating: Requires improvement"],
  "score": 41,
  "streams": ["social-care"],
  "entities": [{ "name": "Certitude", "type": "org" }, { "name": "Haringey", "type": "place" }],
  "category": "Care home",
  "data": {
    "locationId": "1-1234567890",
    "providerId": "1-0000000000",
    "care_home": true,
    "watchlist_label": "",
    "org_type": "Location",
    "rating": "Requires improvement",
    "previous_rating": null
  },
  "run_id": "n8n-exec-48213"
}
```

**Mapping:**

| Workflow field | Contract field |
|---|---|
| `item_key` | `item_key` |
| `name` / `title` | `title` |
| `link` | `url` |
| `published` | `published_at` |
| `streams` | `streams` |
| `summary` | `summary` |
| `key_facts` | `key_facts` |
| `caveats` | `caveats` |
| `score` | `score` |
| everything else | `data` |

### NMC (n8n)

Only the month is known from the listing, so `published_precision` is
`month`. The Claude reply is richer than CQC's, so the extra fields go in
`data`. Post **before** "IF — Newsworthy threshold met".

```json
{
  "source": "nmc",
  "item_key": "nmc-<case_id>",
  "title": "Fitness to practise outcome: <registrant name>",
  "url": "https://www.nmc.org.uk/…/<outcome>.pdf",
  "published_at": "2026-10-01",
  "published_precision": "month",
  "summary": "…",
  "score": 64,
  "streams": ["health"],
  "entities": [{ "name": "<setting from Claude>", "type": "org" }],
  "category": "<allegation_type>",
  "data": {
    "case_id": "<case_id>",
    "register_part": "…",
    "venue": "…",
    "county": "…",
    "committee": "…",
    "allegation_type": "…",
    "pdf_url": "https://…",
    "score_note": "…",
    "setting": "…",
    "orgs_mentioned": ["…"]
  }
}
```

Named people: NMC, PFD and SSSC items carry personal data. Internally that's
fine; see **[open]** below for the external product.

### PFD (n8n)

Claude returns `score` (or `newsworthiness_score`), `priority`, `summary`,
`confidence`, `key_facts`, `caveats` and `category_tags`.

| Workflow field | Contract field |
|---|---|
| `url` | `url` |
| `url` | `item_key` (e.g. `pfd-` plus the report slug) |
| `title` | `title` |
| `summary` | `summary` |
| `key_facts` | `key_facts` |
| `caveats` | `caveats` |
| `score` | `score` |
| `category_tags` | `streams` (or keep them in `data`; **[open]**) |
| `priority`, `confidence`, `deceased_name`, … | `data` |

### LINK bank closures (n8n, no AI step)

No `summary` or `score`. That's fine, since both are optional.

```json
{
  "source": "link-bank-closures",
  "item_key": "link-<site id or postcode>-<closure date>",
  "title": "Cash machine closure: <site>, <town>",
  "url": "https://www.link.co.uk/…",
  "published_at": "2026-10-19",
  "published_precision": "date",
  "streams": ["business", "money"],
  "data": { "…the spreadsheet row…": "…" }
}
```

### Sector Signal (Python pipeline)

Each Python source becomes its own catalogue entry (`signals-bgc`,
`signals-companies-house`, …). The signal's `id` is already a stable hash.
Claude's per-item fields map across. The pattern and theme fields **aren't
sent**: the service works those out across all sources.

```json
{
  "source": "signals-bgc",
  "item_key": "e0620e0a515362777c95eb7eab221b30a7236ca12d3183770626bb2d40395ad5",
  "title": "BGC welcomes Lisa Nandy's reappointment and looks forward to working with Chancellor John Healey",
  "url": "https://bettingandgamingcouncil.com/news/bgc-welcomes-lisa-nandys-reappointment-and-looks-forward-to-working-with-chancellor-john-healey",
  "published_at": "2026-07-21T00:00:00+00:00",
  "published_precision": "date",
  "summary": "Signals which ministers the gambling industry's trade body will engage with on future policy and regulation.",
  "score": 22,
  "streams": ["gambling"],
  "entities": ["BGC", "Lisa Nandy", "John Healey"],
  "category": "Policy and legislation",
  "data": {
    "signal_type": "policy",
    "raw_category": "political reaction/lobbying",
    "raw_summary": "",
    "ingested_at": "2026-07-21T10:21:41.411373+00:00"
  }
}
```

| Signal field | Contract field |
|---|---|
| `id` | `item_key` |
| `source` | `source` (prefixed `signals-`) |
| `source_url` | `url` |
| `title` | `title` |
| `published_at` | `published_at` |
| `published_at_estimated` | `published_precision: "date"` |
| `why_it_matters` | `summary` |
| `newsworthiness_score` | `score` |
| `sector` | `streams` |
| `canonical_entities` | `entities` |
| `canonical_category` | `category` |
| `signal_type`, `category`, `raw_summary` | `data` |
| `cluster_*`, `theme_*` | not sent (the service works these out) |

The one-off import of existing data (about 3 MB, archive included) uses
exactly this mapping, so IDs and stored scores carry over and nothing is
re-scored.

---

## Open questions

1. **Keys:** one per caller, or one per source? (See Authentication.)
2. **Source naming:** the `signals-` prefix for Python sources, or should a
   source's slug ignore which system collects it, so it survives being moved
   into n8n later?
3. **Patterns and themes:** should the Python pipeline also send its current
   pattern and theme results until the service can work them out (as `data`,
   or a separate call)? Or does the newsroom dashboard wait for Steven's
   version?
4. **The score outside PA:** it stays internal, but Sector Signal shows a
   relevance % today. Do customers see a score, a band ("Very active"), or
   nothing?
5. **Personal data:** for the external marketplace, which sources may carry
   named individuals to customers, and do we redact names or drop those
   sources?
6. **PDFs and attachments:** send links only (as above), or should the
   service fetch and keep a copy, since source sites remove documents?
7. **Batching from n8n:** one call per item (simplest in a loop), or a batch
   at the end of the run (fewer calls, but one failure delays all of them)?
8. **Failure alerts:** where do flags for sources that have gone quiet show
   up?
