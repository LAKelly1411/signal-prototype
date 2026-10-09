"""The Insights tab: the sector at a glance.

Four rows, most useful first: headline numbers, signals per week, a category ×
week heat map, then company movers beside theme momentum. Everything here is
plain HTML/SVG built from the stored signals, with no Streamlit, so it is unit
tested; dashboard/app.py calls these and renders the strings.

Colour follows the job: one series is cobalt, magnitude is a single-hue cobalt
ramp (validated light→dark with the dataviz skill's checker), and text stays in
ink or grey. Direction (building, steady, easing) is said in words beside an
arrow, never by colour alone. Every chart has a hover read-out and a table.
"""

from __future__ import annotations

import html
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable

WEEKS = 18
HIGH_SCORE = 70  # SCORE_TIERS' "High"

# Heat map: cobalt light→dark (passes monotone lightness, visible steps and a
# light end that clears white), with empty cells a neutral grey.
HEAT_RAMP = ("#93afff", "#668eff", "#3b6bff", "#124ced", "#0033ad")
HEAT_EMPTY = "#efede6"

_NICE = (2, 4, 6, 8, 10, 12, 16, 20, 30, 40, 50, 60, 80, 100, 120, 160, 200)


def _dt(signal: dict) -> datetime:
    dt = datetime.fromisoformat(signal["published_at"])
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def week_starts(now: datetime, weeks: int = WEEKS) -> list[datetime]:
    """Monday 00:00 UTC of each of the last `weeks` calendar weeks, oldest
    first; the last is the current (part) week."""
    today = now.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    this_monday = today - timedelta(days=today.weekday())
    return [this_monday - timedelta(weeks=weeks - 1 - i) for i in range(weeks)]


def week_index(signal: dict, starts: list[datetime]) -> int | None:
    dt = _dt(signal)
    if dt < starts[0] or dt >= starts[-1] + timedelta(weeks=1):
        return None
    return min(int((dt - starts[0]).days // 7), len(starts) - 1)


def _week_label(start: datetime) -> str:
    end = start + timedelta(days=6)
    if start.month == end.month:
        return f"{start.day}–{end.day} {end:%b}"
    return f"{start.day} {start:%b} – {end.day} {end:%b}"


def nice_top(peak: int) -> int:
    return next((n for n in _NICE if n >= peak), -(-peak // 50) * 50)


# ── Headline numbers ────────────────────────────────────────────────────────

@dataclass
class Tile:
    label: str
    value: str
    note: str = ""  # the comparison, in words


def _change(now_n: int, then_n: float, period: str) -> str:
    diff = round(now_n - then_n)
    if diff == 0:
        return f"Level with {period}"
    return f"{'+' if diff > 0 else '−'}{abs(diff)} vs {period}"


def headline_tiles(signals: list[dict], now: datetime, active_patterns: int,
                   themes_building: int, healthy: int | None, total_sources: int | None) -> list[Tile]:
    week_ago, month_ago, two_months = (now - timedelta(days=d) for d in (7, 30, 60))
    this_week = sum(1 for s in signals if _dt(s) > week_ago)
    prior_4w = sum(1 for s in signals if week_ago - timedelta(days=28) < _dt(s) <= week_ago)
    high = [s for s in signals if (s.get("newsworthiness_score") or 0) >= HIGH_SCORE]
    high_now = sum(1 for s in high if _dt(s) > month_ago)
    high_then = sum(1 for s in high if two_months < _dt(s) <= month_ago)
    tiles = [
        Tile("Signals this week", f"{this_week:,}", _change(this_week, prior_4w / 4, "4-week average")),
        Tile("High relevance, last 30 days", f"{high_now:,}", _change(high_now, high_then, "previous 30 days")),
        Tile("Active patterns", f"{active_patterns:,}", "Companies with a run of related signals"),
        Tile("Themes building", f"{themes_building:,}", "Sector-wide stories gaining pace"),
    ]
    if healthy is not None and total_sources:
        tiles.append(Tile("Sources healthy", f"{healthy}/{total_sources}", "At the last update"))
    return tiles


def tiles_html(tiles: list[Tile]) -> str:
    """One hero number (the first tile), then the rest as smaller tiles."""
    cells = []
    for i, t in enumerate(tiles):
        cells.append(
            f'<div class="ov-tile{" ov-hero" if i == 0 else ""}">'
            f'<div class="ov-tile-label">{html.escape(t.label)}</div>'
            f'<div class="ov-tile-value">{html.escape(t.value)}</div>'
            + (f'<div class="ov-tile-note">{html.escape(t.note)}</div>' if t.note else "")
            + "</div>"
        )
    return f'<div class="ov-tiles">{"".join(cells)}</div>'


# ── Signals per week ────────────────────────────────────────────────────────

def weekly_volume_html(signals: list[dict], now: datetime) -> str:
    """Signals per calendar week as a line with a light area, a hover column
    per week (guide, dot and a read-out with the week's top story), and a dot
    on every week with a high-relevance signal."""
    starts = week_starts(now)
    counts = [0] * WEEKS
    top: dict[int, dict] = {}
    for s in signals:
        i = week_index(s, starts)
        if i is None:
            continue
        counts[i] += 1
        if (s.get("newsworthiness_score") or 0) > (top.get(i, {}).get("newsworthiness_score") or -1):
            top[i] = s
    scale = nice_top(max(counts) or 1)
    height = 100

    def y(c: int) -> float:
        return height - c / scale * (height - 4)

    step = 100 / (WEEKS - 1)
    pts = [(i * step, y(c)) for i, c in enumerate(counts)]
    line = "M" + " L".join(f"{x:.2f},{yy:.2f}" for x, yy in pts)
    area = f"{line} L100,{height} L0,{height} Z"

    grid = "".join(
        f'<line class="ov-grid" x1="0" x2="100" y1="{y(v):.2f}" y2="{y(v):.2f}"/>'
        for v in (scale // 2, scale)
    )
    ticks = "".join(
        f'<span class="ov-ytick" style="bottom:{(height - y(v)) / height * 100:.1f}%">{v}</span>'
        for v in (0, scale // 2, scale)
    )
    cols, marks = [], []
    for i, ((x, yy), c, ws) in enumerate(zip(pts, counts, starts)):
        x0, x1 = max(0.0, x - step / 2), min(100.0, x + step / 2)
        at = (x - x0) / (x1 - x0) * 100
        bottom = (height - yy) / height * 100
        edge = " ov-tip-start" if i < 2 else " ov-tip-end" if i > WEEKS - 3 else ""
        story = top.get(i)
        story_html = (f'<span class="ov-tip-story">Top: {html.escape(story["title"])}</span>'
                      if story else "")
        label = "This week" if i == WEEKS - 1 else _week_label(ws)
        cols.append(
            f'<div class="ov-col" style="left:{x0:.2f}%;width:{x1 - x0:.2f}%">'
            f'<span class="ov-guide" style="left:{at:.1f}%"></span>'
            f'<span class="ov-hdot" style="left:{at:.1f}%;bottom:{bottom:.1f}%"></span>'
            f'<span class="ov-tip{edge}" style="left:{at:.1f}%;bottom:calc({bottom:.1f}% + 14px)">'
            f"<span>{html.escape(label)}</span><b>{c} signal{'s' if c != 1 else ''}</b>{story_html}"
            "</span></div>"
        )
        if story and (story.get("newsworthiness_score") or 0) >= HIGH_SCORE:
            marks.append(f'<span class="ov-mark" style="left:{x:.2f}%;bottom:{bottom:.1f}%"></span>')

    # Month labels along the bottom, at the first week starting in each month.
    months, seen = [], set()
    for i, ws in enumerate(starts):
        if ws.month not in seen and (i > 0 or ws.day <= 7):
            seen.add(ws.month)
            months.append(f'<span style="left:{i * step:.2f}%">{ws:%b}</span>')

    rows = "".join(
        f"<tr><td>{html.escape(_week_label(ws))}</td><td>{c}</td>"
        f"<td>{html.escape(top[i]['title']) if i in top else ''}</td></tr>"
        for i, (ws, c) in enumerate(zip(starts, counts))
    )
    total = sum(counts)
    return (
        '<div class="ov-card">'
        '<div class="ov-card-head"><div class="ov-card-title">Signals per week</div>'
        f'<div class="ov-card-sub">{total:,} signals over {WEEKS} weeks · '
        '<span class="ov-key-mark"></span> week with a high-relevance signal</div></div>'
        f'<div class="ov-chart" role="img" aria-label="{html.escape(_volume_label(counts, starts), quote=True)}">'
        f'<div class="ov-yaxis">{ticks}</div>'
        '<div class="ov-plot">'
        f'<svg class="ov-svg" viewBox="0 0 100 {height}" preserveAspectRatio="none" aria-hidden="true">'
        f'{grid}<line class="ov-base" x1="0" x2="100" y1="{height}" y2="{height}"/>'
        f'<path class="ov-area" d="{area}"/><path class="ov-line" d="{line}"/></svg>'
        f'{"".join(marks)}<div class="ov-cols">{"".join(cols)}</div>'
        f'<div class="ov-xaxis">{"".join(months)}</div>'
        "</div></div>"
        '<details class="ov-table"><summary>Show as a table</summary>'
        "<table><thead><tr><th>Week</th><th>Signals</th><th>Top story</th></tr></thead>"
        f"<tbody>{rows}</tbody></table></details>"
        "</div>"
    )


def _volume_label(counts: list[int], starts: list[datetime]) -> str:
    peak = max(range(len(counts)), key=counts.__getitem__)
    return (f"Signals per week over the last {len(counts)} weeks, {sum(counts)} in all. "
            f"Busiest: {counts[peak]} in the week of {starts[peak].day} {starts[peak]:%b}; "
            f"{counts[-1]} so far this week.")


# ── Category × week ─────────────────────────────────────────────────────────

def heat_step(count: int, thresholds: tuple[int, ...]) -> str:
    """The ramp colour for a cell: empty grey, then the lightest step whose
    upper bound the count is within."""
    if count <= 0:
        return HEAT_EMPTY
    for colour, upper in zip(HEAT_RAMP, thresholds):
        if count <= upper:
            return colour
    return HEAT_RAMP[-1]


def heat_thresholds(counts: list[int]) -> tuple[int, ...]:
    """Upper bounds for the five ramp steps, from the spread of non-empty
    cells, so a quiet sector still uses the whole ramp."""
    nonzero = sorted(c for c in counts if c > 0)
    if not nonzero:
        return (1, 2, 3, 4, 5)
    peak = nonzero[-1]
    if peak <= 5:
        return tuple(range(1, 6))
    qs = [nonzero[min(len(nonzero) - 1, int(len(nonzero) * q))] for q in (0.3, 0.55, 0.75, 0.9)]
    # Each bound strictly above the last and below the peak, so the busiest
    # cell is always in the darkest step.
    bounds, last = [], 0
    for i, q in enumerate(qs):
        last = min(max(last + 1, q), peak - (len(qs) - i))
        bounds.append(last)
    return (*bounds, peak)


def category_heatmap_html(signals: list[dict], now: datetime,
                          icon_for: Callable[[str], str]) -> str:
    """Categories (busiest first) by calendar week; cell shade is the count.
    Bursts that a weekly total hides show up as dark runs in one row."""
    starts = week_starts(now)
    grid: dict[str, list[int]] = defaultdict(lambda: [0] * WEEKS)
    for s in signals:
        i = week_index(s, starts)
        if i is None:
            continue
        grid[s.get("canonical_category") or "Other"][i] += 1
    rows = sorted(grid.items(), key=lambda kv: (-sum(kv[1]), kv[0]))
    thresholds = heat_thresholds([c for _, cs in rows for c in cs])

    body = []
    for name, cs in rows:
        cells = "".join(
            f'<span class="ov-cell" style="background:{heat_step(c, thresholds)}" tabindex="0" '
            f'aria-label="{html.escape(name, quote=True)}, {_week_label(ws)}: {c} signal{"s" if c != 1 else ""}">'
            f'<span class="ov-cell-tip{" ov-tip-end" if i > WEEKS - 4 else ""}">'
            f"<span>{html.escape(name)} · {html.escape(_week_label(ws))}</span>"
            f"<b>{c} signal{'s' if c != 1 else ''}</b></span></span>"
            for i, (c, ws) in enumerate(zip(cs, starts))
        )
        body.append(
            '<div class="ov-hrow">'
            f'<span class="ov-hname"><span class="ov-hicon">{icon_for(name)}</span>'
            f'<span class="ov-hlabel">{html.escape(name)}</span></span>'
            f'{cells}<span class="ov-htotal">{sum(cs)}</span></div>'
        )

    lows = [1] + [t + 1 for t in thresholds[:-1]]
    legend = "".join(
        f'<span class="ov-legend-item"><span class="ov-legend-swatch" style="background:{colour}"></span>'
        f'{lo if lo == hi else f"{lo}–{hi}"}</span>'
        for colour, lo, hi in zip(HEAT_RAMP, lows, thresholds)
    )
    legend = (f'<span class="ov-legend-item"><span class="ov-legend-swatch" style="background:{HEAT_EMPTY}">'
              f"</span>0</span>{legend}")
    # A full row of cells (name column, one per week, total column) so the
    # month labels can't knock the first category out of its row.
    months = "<span></span>" + "".join(
        f"<span>{ws:%b}</span>" if i == 0 or ws.month != starts[i - 1].month else "<span></span>"
        for i, ws in enumerate(starts)
    ) + "<span></span>"
    table_rows = "".join(
        f"<tr><th scope=\"row\">{html.escape(n)}</th>{''.join(f'<td>{c}</td>' for c in cs)}<td>{sum(cs)}</td></tr>"
        for n, cs in rows
    )
    table_head = "".join(f"<th>{ws.day} {ws:%b}</th>" for ws in starts)
    return (
        '<div class="ov-card">'
        '<div class="ov-card-head"><div class="ov-card-title">What kind of news, week by week</div>'
        '<div class="ov-card-sub">Signals per category each week. Darker means more.</div></div>'
        f'<div class="ov-heat" style="--weeks:{WEEKS}">'
        f'<div class="ov-hmonths">{months}</div>{"".join(body)}</div>'
        f'<div class="ov-legend">{legend}</div>'
        '<details class="ov-table"><summary>Show as a table</summary>'
        f'<div class="ov-table-scroll"><table><thead><tr><th>Category</th>{table_head}<th>Total</th></tr></thead>'
        f"<tbody>{table_rows}</tbody></table></div></details>"
        "</div>"
    )


# ── Company movers ──────────────────────────────────────────────────────────

def company_movers(signals: list[dict], now: datetime, entities_of: Callable[[dict], list[str]],
                   excluded: Callable[[str], bool], limit: int = 8) -> list[dict]:
    """Companies named most in the last 30 days (regulators and government
    left out, as on Patterns), with the change against the 30 days before
    and their weekly counts for a sparkline."""
    starts = week_starts(now)
    month_ago, two_months = now - timedelta(days=30), now - timedelta(days=60)
    recent, before = Counter(), Counter()
    weekly: dict[str, list[int]] = defaultdict(lambda: [0] * WEEKS)
    for s in signals:
        names = {e for e in entities_of(s) if not excluded(e)}
        dt = _dt(s)
        i = week_index(s, starts)
        for n in names:
            if dt > month_ago:
                recent[n] += 1
            elif dt > two_months:
                before[n] += 1
            if i is not None:
                weekly[n][i] += 1
    return [
        {"name": n, "count": c, "change": c - before[n], "weekly": weekly[n]}
        for n, c in sorted(recent.items(), key=lambda kv: (-kv[1], kv[0]))[:limit]
    ]


def _mini_spark(counts: list[int]) -> str:
    peak = max(counts) or 1
    step = 100 / (len(counts) - 1)
    pts = " ".join(f"{i * step:.1f},{24 - c / peak * 20:.1f}" for i, c in enumerate(counts))
    return (f'<svg class="ov-spark" viewBox="0 0 100 26" preserveAspectRatio="none" aria-hidden="true">'
            f'<polyline points="{pts}"/></svg>')


def movers_html(movers: list[dict], logo_for: Callable[[str], str]) -> str:
    if not movers:
        body = '<div class="ov-empty">No companies named in the last 30 days.</div>'
    else:
        rows = []
        for m in movers:
            ch = m["change"]
            arrow, word = ("▲", f"+{ch}") if ch > 0 else ("▼", f"−{abs(ch)}") if ch < 0 else ("", "0")
            arrow_html = f'<span aria-hidden="true">{arrow}</span> ' if arrow else ""
            rows.append(
                '<div class="ov-mrow">'
                f'<span class="ov-mname">{logo_for(m["name"])}<span>{html.escape(m["name"])}</span></span>'
                f"{_mini_spark(m['weekly'])}"
                f'<span class="ov-mcount">{m["count"]}</span>'
                f'<span class="ov-mchange" title="Change vs the previous 30 days">{arrow_html}{word}</span>'
                "</div>"
            )
        body = ('<div class="ov-mhead"><span>Company</span><span>18 weeks</span>'
                '<span>30 days</span><span>Change</span></div>' + "".join(rows))
    return (
        '<div class="ov-card">'
        '<div class="ov-card-head"><div class="ov-card-title">Companies in the news</div>'
        '<div class="ov-card-sub">Most-named companies in the last 30 days, against the 30 before.'
        " Regulators and government bodies are left out.</div></div>"
        f"{body}</div>"
    )


# ── Theme momentum ──────────────────────────────────────────────────────────

DIRECTION_WORDS = {"building": ("Building", "↗"), "steady": ("Steady", "→"), "easing": ("Easing", "↘")}


def themes_html(themes: list[dict]) -> str:
    """Themes as bars of heat (the Themes tab's measure), busiest first, each
    with its direction in words."""
    if not themes:
        body = '<div class="ov-empty">No sector-wide themes yet.</div>'
    else:
        peak = max(t["heat"] for t in themes) or 1
        rows = []
        for t in themes:
            word, arrow = DIRECTION_WORDS.get(t.get("direction") or "", ("", ""))
            direction = f'<span aria-hidden="true">{arrow}</span> {word}' if word else "—"
            rows.append(
                '<div class="ov-trow">'
                f'<span class="ov-tname">{html.escape(t["name"])}</span>'
                f'<span class="ov-tbar"><span style="width:{max(2.0, t["heat"] / peak * 100):.1f}%"></span></span>'
                f'<span class="ov-tdir">{direction}</span>'
                "</div>"
            )
        body = "".join(rows)
    return (
        '<div class="ov-card">'
        '<div class="ov-card-head"><div class="ov-card-title">Theme momentum</div>'
        '<div class="ov-card-sub">How hot each sector-wide theme is, and which way it is heading.</div></div>'
        f"{body}</div>"
    )
