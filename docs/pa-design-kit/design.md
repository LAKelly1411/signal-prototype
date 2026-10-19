# PA design kit

Use this kit to put an internal tool or prototype on the Press Association
brand. It comes from the decisions made building Sector Signal, PA's sector
news-monitoring prototype. Values are exact, and where a rule isn't obvious it
says why.

## What's in the kit

| File | What it is |
|---|---|
| `design.md` | This guide: the rules, tokens and patterns, and how to reskin an app |
| `pa-brand.css` | Fonts, tokens, base styles and the core components as `pa-*` classes |
| `pa-logo.svg` | The PA mark. Inline it so it takes `currentColor` |
| `example.html` | A reference page using only the two files above. Open it to see the target |

## How to use it

- **Reskinning an existing app:** follow [Part 3](#part-3-reskinning-an-app)
  step by step. Apply Part 1 everywhere, and Part 2 only where a pattern fits.
- **Starting a new app:** link `pa-brand.css`, build with the `pa-*` classes,
  and reach for Part 2 when you need a list, detail view or chart.
- **Handing it to an agent:** "Reskin this app to the PA brand using
  `design.md` and the files next to it. Follow Part 3 and finish with its
  checklist."

The values come from PA's own `pa-tokens.css` (the PA Media Briefings site,
`pam-media-briefing-marketing-website`). If this kit and that file ever
disagree, `pa-tokens.css` wins.

---

# Part 1: Core brand

Apply all of this to every app.

## 1.1 Principles

1. **Cobalt means "you can click this".** Use it for links, buttons, toggles,
   the selected state, focus rings and data marks. Never use it for
   decoration, headings or a magnitude scale.
2. **Flat and square.** No rounded corners anywhere: cards, tags, buttons,
   inputs, tooltips or dialogs.
3. **Shadows, not borders.** Separate a panel from the page with a soft
   shadow. Borders are only for inputs (1px ink) and outline buttons
   (2px ink).
4. **Words before colour.** Never show a state by colour alone. Pair it with
   a label ("Very active", "Building", "1 source returned nothing").
5. **One size per row.** Labels in the same line share a font size. Don't mix
   14px tags with 12px metadata in one row.
6. **Plain, finished pages.** No entrance or wipe-in animations: a page
   looks complete on its first frame. Hover, press and ambient motion are
   fine.

## 1.2 Colour

| Token | Value | Use |
|---|---|---|
| `--pa-ink` | `#000000` | Text, wordmark, outline buttons, input borders |
| `--pa-ink-soft` | `#1f1f1f` | Tag icon blocks, tooltips |
| `--pa-paper` | `#ffffff` | Page, cards, panels |
| `--pa-muted` | `#464646` | Secondary text |
| `--pa-meta` | `#6b6b6b` | Dates, meta lines, captions, section labels |
| `--pa-cobalt` | `#004FFF` | Interactive only |
| `--pa-cobalt-hover` | `#0040cc` | Hover on cobalt buttons |
| `--pa-cobalt-tint` | `rgba(0,79,255,0.05)` | Pill backgrounds, hover on expanders |
| `--pa-surface` | `#e8e5e4` | Neutral fills |
| `--pa-sunken` | `#dedad9` | The middle step of ink ramps |
| `--pa-newsprint` | `#e5e3d3` | The brand's off-white |
| `--pa-newsprint-30` | newsprint at 30% over white | List surfaces, so white tiles can lift from them |
| `--pa-border` | `rgba(0,0,0,0.2)` | Light borders |
| `--pa-hairline` | `rgba(0,0,0,0.1)` | Dividers |
| `--pa-hover` | `#f3f3f3` | Hover on tabs and tertiary buttons |
| `--pa-orange` | `#fd8621` | Category tiles and accent tags (tags at 10%) |
| `--pa-warn-bg` / `--pa-warn` | `#fffaeb` / `#b54708` | Partial or stale data |
| `--pa-error-bg` / `--pa-error` | `#fef3f2` / `#b3261e` | Failures, wrong input |

**Magnitude uses ink, not cobalt.** A three-step scale runs white → `#dedad9`
→ black for Low → Medium → High.

## 1.3 Type

| Role | Stack |
|---|---|
| Headings, wordmark, kickers | `'Press Sans Condensed', Oswald, 'Arial Narrow', sans-serif`, 700 |
| Everything else | `'Press Sans', Archivo, Arial, Helvetica, sans-serif`, 400 / 700 / 800 |

**Fonts:**
- Press Sans is a licensed webfont on PA's font CDN. `pa-brand.css` loads it.
- **Never commit the font files.**
- The CDN only serves allowlisted origins. localhost works, but a new
  deployed domain won't until it's added, so ask before launch.
- Until then people see the open stand-ins, Archivo and Oswald. Always load
  them; `pa-brand.css` does.
- Chrome won't fetch a fallback web font by itself once the face before it
  fails. If the stand-ins don't appear, add a hidden element set in Archivo
  400 and 700 to warm them.

| Size | Weight | Use |
|---|---|---|
| 3rem condensed | 700 | Page title (`.pa-title`) |
| 1.5rem | 700 | Card and panel titles |
| 1rem | 400 | Body, buttons (700), pills (700) |
| 0.875rem | 700 | Tags, toggle links, status strips |
| 0.8125rem uppercase, 0.04em tracking | 700 | Section labels (`.pa-label`) |
| 0.75rem | 400 | Meta lines, captions, tooltips. Tags in dense lists, kept bold |

Sentence case everywhere except kickers, the wordmark and section labels.

## 1.4 Elevation, motion, spacing

| Level | Value | Use |
|---|---|---|
| `--pa-shadow` | `0 4px 24px rgba(0,0,0,0.1)` | Cards, panels, tiles |
| `--pa-shadow-hover` | `0 10px 32px rgba(0,0,0,0.14)` plus `translateY(-2px)` | Clickable cards on hover |
| `--pa-shadow-pinned` | `0 6px 12px -8px rgba(0,0,0,0.18)` | Under a sticky header |
| `--pa-shadow-popover` | `0 4px 12px rgba(0,0,0,0.2)` | Menus, dropdowns |

**Motion:**
- Easing `cubic-bezier(0.2, 0, 0, 1)`.
- 150ms for presses and list hovers, 250ms for card lifts and selection,
  400ms for slower moves.
- A press is `scale(0.995)`.
- Honour `prefers-reduced-motion`: stop loops and drop lifts.

**Spacing:**
- Cards `16px 24px 24px 20px`, 16–24px apart.
- Tag gap 10px.
- Panels `2rem 1.75rem`.
- Buttons 44px tall with 20px side padding.
- Phone side gutter 16px.

## 1.5 Core components

Each one is a class in `pa-brand.css` and appears in `example.html`.

| Component | Class | Rules |
|---|---|---|
| Lockup | `.pa-lockup` + `.pa-wordmark` | The PA mark next to the product name, stacked in black blocks (e.g. "SECTOR" / "SIGNAL"). Size it with `--lockup-size` (46px). Top left of every app. The mark is a wordmark: don't use it below about 32px. |
| Kicker | `.pa-kicker` | A small uppercase label above a title. Cobalt by default, `.ink` for secondary. |
| Page title | `.pa-title` | Condensed, 3rem. |
| Primary button | `.pa-btn .pa-btn-primary` | Cobalt fill, white bold text. One per view. |
| Outline button | `.pa-btn .pa-btn-outline` | 2px ink border; fills ink on hover. For header actions. |
| Tertiary button | `.pa-btn .pa-btn-tertiary` | Icon or text only, `#f3f3f3` on hover. For close (×). |
| Link | `a` | Cobalt, bold, underlined on hover. |
| Input | `input`, `textarea` | White, 1px ink border, square. |
| Card | `.pa-card` | White with a shadow. `.is-clickable` lifts on hover; `.is-selected` shows a cobalt 4px left edge. Every card reserves that edge, so selecting one never shifts content. |
| Tag | `.pa-tag` + `.pa-tag-icon` | 20px tall, bold, with a square icon block. Ink tint for entities, `.pa-tag-accent` (orange) for categories and trends, `.pa-tag-plain` for "+N more". `.pa-tags.is-compact` makes them 12px. |
| Pill | `.pa-pill` | A status label on a cobalt tint, with a ring or icon. |
| Status strip | `.pa-status.is-warn` / `.is-error` | A 4px left border in the text colour on a matching tint. Say what happened in plain words. |
| Tabs | `.pa-tabs` / `.pa-tab` | Text tabs. The selected one is bold with a 2px cobalt underline. Hover `#f3f3f3`. |
| Tooltip | `.pa-tooltip` | `#1f1f1f`, white 12px text, `8px 10px` padding. Add an arrow when it points at a mark. |
| Toggle | `.pa-toggle` (a `<details>`) | A bold cobalt link with a chevron. The label swaps "Show summary" ↔ "Show less" via `.when-closed` / `.when-open`. |
| Section label | `.pa-label` | "SIGNALS (62)". |
| Meta line | `.pa-meta` | "62 signals · 20 companies · 13 Jul – 6 Oct". |

Focus on every interactive element: a 2px cobalt outline, 2px offset.

## 1.6 Copy and voice

- **Plain words:** "Sign in", "Show summary", "Show less", "Show as a table",
  "+15 more".
- **Say what happened, then what to do:** "That password isn't right. Try
  again." / "Drafting isn't switched on here yet."
- **Meta lines:** numbers separated by a middle dot (·).
- **Dates:** "6 Oct" and "13 Jul – 6 Oct", with no year for the current year.
  Weeks are "Week of 21 Aug".
- **Direction:** in words ("Building", "Easing", "+1 vs 4-week average"),
  never an arrow alone.
- **Naming:** name things by what they contain ("Signals"), not by how
  they're drawn ("Timeline").
- **Footer** on prototypes: "A Press Association prototype".

## 1.7 Accessibility

- Every state has text as well as colour.
- Focus rings are always visible.
- Icon-only buttons have an `aria-label`.
- Card-wide click targets have a descriptive label ("Preview Policy and
  legislation").
- Decorative SVGs get `aria-hidden="true"`. Meaningful art gets
  `role="img"` and an `aria-label`.
- Every chart has a table view.
- `prefers-reduced-motion` is honoured.

---

# Part 2: Product patterns

Sector Signal used these. Use one when the new app has the same problem;
don't add them just because they exist.

## 2.1 List + preview pane

**When:** the user picks an item from a list and needs its detail without
losing the list.

- **Opening and closing:** clicking a card opens a pane fixed to the right
  edge, with a resting shadow. Nothing is open when the view loads, and the
  pane closes with its × in the top-right corner.
- **The × is vertically centred on the title row.** Measure it; don't
  eyeball it.
- **Switching:** the pane keeps its position and identity across selections,
  so switching updates it in place instead of rebuilding it.
- **Pinned header, the essentials only:**
  - title, status pill and ×;
  - meta line;
  - a small chart;
  - the first 5 tags plus "+N more".
- **Content first:** the pane's main list should start within the first
  screen.
  - Longer context (summary, key points, every tag) sits behind a
    "Show summary" toggle inside the header.
  - Open, the header grows and stops being pinned, because it may now be
    taller than the pane. Closing it pins it again.
- **No scroll inside a scroll.** Never give the expanded header its own
  scroll bar.
- **Phones (below 768px):** the pane becomes a bottom sheet at 55vh, with the
  header hidden because the selected card is visible above it.

## 2.2 Quiet chronological list

**When:** a dated list inside a panel (events, activity, history).

- **Surface:** `--pa-newsprint-30`. Rows are a grid: a 3.75rem date column
  (`--pa-meta`, 0.8125rem), then the content. Hairlines between rows are
  `#e3e1d8`.
- **Rail:** a 1px `#d8d6cc` line through a small grey dot per row.
  - Each row draws its own segment, overlapping the hairline above by 1px,
    so the line never breaks.
  - The rail runs from the first dot to the last. A single row has none.
- **Hover:** the row becomes a white tile without moving its content
  (`margin: 0 -0.75rem; padding: …0.75rem`). Its dot turns cobalt, and so
  does the matching point on the pane's chart.
- **Expand in place:** use `<details name="group">` so opening one row
  closes the others. The opened part uses the meta line's 12px, with bold
  tags.
- **Each row:**
  - bold title;
  - body clamped to two lines;
  - meta: source logo · category · score.

## 2.3 Score as a ring

**When:** a 0–100 score or an activity level.

- **Ring:** a 20px donut with a 5px stroke. The track is cobalt at 20%; the
  arc is cobalt, clockwise from 12 o'clock, in proportion to the score.
- **On cards:** put it in a `.pa-pill` with a word ("Very active" for 90,
  "Active" for 60, "Quiet" for 30).
- **In dense rows:** put it next to a percentage.

## 2.4 Data visualisation

- **Sequential (counts, heat maps):** a cobalt ramp from light to dark,
  `#93afff, #668eff, #3b6bff, #124ced, #0033ad`, with empty cells in
  `#efede6`. The highest value must land on the darkest step.
- **Lines:**
  - a 2px cobalt line over a 10% cobalt fill;
  - a dot on the latest point;
  - axis captions only at the ends ("10 Jul" … "This week").
- **Axes:** one y-axis per view; never two scales on one chart. Small charts
  on the same screen share a scale so they compare.
- **Highlights:** mark only what matters (e.g. weeks with a signal scoring
  75% or more), and say so in the caption.
- **Hover:** every chart gets a tooltip (`.pa-tooltip`), e.g. "Week of 21 Aug
  / 33 signals".
- **Table view:** every chart gets a "Show as a table" link under it.
- **Small numbers aren't trends.** Only call something "Building" or "Easing"
  when it moved at least 25% **and** at least 2 items.
- **Dashboard order:**
  1. KPI tiles, the first one larger, each with a comparison note.
  2. Volume over time.
  3. Breakdown heat map, busiest rows first.
  4. Ranked list.
  5. Momentum in words.
- **Check categorical palettes for colour-blind safety with a script, not by
  eye.**

## 2.5 Sign-in page

**When:** an app behind a shared password or sign-in.

- **Layout:** two columns (1.15 : 1), full bleed, no app header, 100vh.
- **Left: a full-height cobalt hero** with a kicker (product name), a
  condensed headline of at most 13ch (e.g. "Spot the story before it
  breaks.") and a one-line lede.
- **Right:** the form, centred vertically:
  - lockup;
  - "Sign in" and one line of instruction;
  - field;
  - a full-width primary button;
  - footer.
- **Hero art (optional): a calm, data-like loop in the bottom 46vh, flush to
  the edges.**
  - A white line scrolls left continuously (about 40s per width). Draw it
    twice so the loop is seamless.
  - Behind it, a grid of **exact squares** (`aspect-ratio: 1`, sized with
    container query units) scrolls with it, at white opacities that breathe
    slowly. The occasional tile flashes `#8DDBFF`.
  - The squares have their own pattern; they don't trace the line.
  - A few peaks get a pulsing dot and a tooltip as they pass.
  - Generate values from a seeded hash, so it looks organic but renders the
    same every time.
  - **Already moving on the first frame:** use negative animation delays and
    no wipe-in.
  - Hide it on phones. Stop it under reduced motion.

---

# Part 3: Reskinning an app

## 3.1 Steps

1. **Take stock.** Screenshot every screen and state of the current app
   (empty, loading, error, selected, hover) so you can compare later.
2. **Load the kit.** Link `pa-brand.css`, or copy its tokens into the app's
   theme system if it has one (e.g. Tailwind config, MUI theme, Streamlit
   `config.toml`). Make the app's own theme variables point at the tokens
   rather than duplicating values.
3. **Fonts.** Set body and UI to the Press Sans stack and headings to the
   condensed stack. Remove other web fonts.
4. **Colour.** Replace every brand or accent colour.
   - Interactive → `--pa-cobalt`.
   - Text → `--pa-ink` / `--pa-muted` / `--pa-meta`.
   - Backgrounds → paper, with newsprint for list surfaces.
   - Magnitude scales → the ink ramp, or the cobalt ramp for charts.
   - Anything decorative in cobalt loses it.
   - Search the codebase for hex, `rgb(`, `hsl(` and named colours, and
     account for every hit.
5. **Shape.** Set every radius to 0. Turn panel borders into shadows. Keep
   1px ink borders on inputs.
6. **Components.** Map each one onto the Part 1 table: buttons, inputs,
   cards, tags, tabs, pills, tooltips, status messages. Exactly one primary
   button per view.
7. **Masthead.** Put the lockup top left, with the product name in the
   wordmark. Add a kicker where a section or category name helps.
8. **Copy.** Sentence case, plain words, the date formats above, and errors
   that say what to do next.
9. **States.** Add hover, focus (2px cobalt ring), selected (cobalt left
   edge) and disabled states. Show status with words as well as colour.
10. **Patterns, only where they fit (Part 2).** For example, use the list +
    preview pane if the app has a master–detail view, or the data rules if it
    has charts.
11. **Motion.** Remove entrance animations. Add the card lift and press, and
    honour reduced motion.
12. **Phones.** Check at 375px: 16px gutters, no horizontal scroll, panes
    become sheets.

## 3.2 Done checklist

- [ ] No rounded corners anywhere, including inputs, dialogs and tooltips.
- [ ] Cobalt appears only on clickable things, the selection, focus and
      data marks.
- [ ] No colours outside the token table (search the code for hex values).
- [ ] Press Sans (or Archivo) everywhere; condensed only for titles,
      kickers and the wordmark.
- [ ] No two font sizes in the same row of labels.
- [ ] Panels use shadows, not borders.
- [ ] Lockup top left with the right product name.
- [ ] Every status and level has a word, not just a colour.
- [ ] Every interactive element shows a cobalt focus ring on Tab.
- [ ] Every chart has a tooltip and a table view.
- [ ] The page looks finished on its first frame (no wipe-ins).
- [ ] Works at 375px with no horizontal scroll.
- [ ] Reduced motion stops loops and lifts.
- [ ] Side by side with `example.html`, the components match.
- [ ] Font files aren't committed; the deployed domain is on the font
      CDN's allowlist, or you know the stand-ins will show.

---

# Appendix: Streamlit notes

Only for Streamlit apps.

- Put the theme in `.streamlit/config.toml`:
  - `primaryColor = "#004FFF"`, `baseRadius = "none"` and
    `buttonRadius = "none"`;
  - the two font stacks, with `[[theme.fontFaces]]` entries pointing at the
    CDN URLs in `pa-brand.css`.

  Inject the rest of the CSS with `st.markdown("<style>…</style>",
  unsafe_allow_html=True)`.
- `st.container(key="x")` renders the class `.st-key-x`. Scope page-level
  rules with `:has()`, e.g.
  `[data-testid="stMainBlockContainer"]:has(.st-key-login)`.
- **Sticky elements:** make Streamlit's **wrapper** sticky
  (`[data-testid="stLayoutWrapper"]:has(> .st-key-…)`), not the container,
  which has no room to stick in.
- **Selector strength:** scope selectors (`.hero h1.headline`), or Streamlit's
  own `h1` and `p` styles win.
- **Instant interactions:** use `<details>` and CSS for things that need no
  server round trip (show more, expand a row), not `st.button`, which reruns
  the script.
- **Class names:** give each component its own prefix. Two components
  sharing a class silently inherit each other's spacing.
- **Hot reload:** modules other than the entry script don't hot-reload, so
  restart the server after editing them. Injected styles can go stale until
  a full page reload.
