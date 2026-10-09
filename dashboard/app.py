import html
import logging
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from urllib.parse import urlparse

import streamlit as st
import yaml

from dashboard.brand import (
    COMPANY_DOMAINS,
    ENTITY_ICON,
    LINK_ICON,
    PEOPLE,
    PERSON_ICON,
    PA_LOGO_SVG,
    SOURCE_DOMAINS,
    SOURCE_LOGOS,
    SOURCE_NAMES,
    category_icon,
    icon,
)
from dashboard import data, github, new_sector
from src import drafting, sectors
from src.entities import match_key
from src.cluster import (
    CLUSTER_WINDOW_DAYS,
    MIN_THEME_COMPANIES,
    compute_heat,
    compute_theme_heat,
    is_excluded,
    signal_entities,
)

st.set_page_config(page_title="Sector Signal", layout="wide")

logger = logging.getLogger(__name__)


# Score is a magnitude bucketed into tiers, so it gets an ordinal ramp in PA ink:
# outline -> sunken grey -> solid ink, light->dark mapping low->high newsworthiness.
# Cobalt is kept off the ramp because in the PA system it means "clickable".
SCORE_TIERS = [
    (70, "High", "#000000", "#ffffff"),
    (40, "Medium", "#dedad9", "#000000"),
    (0, "Low", "#ffffff", "#000000"),
]

# Same ramp for cluster heat. Shown only as words (ACTIVITY_LABELS).
# Calibrated against the observed spread once heat stopped counting routine
# filings: there's a clear break at 60 between the busy half of the clusters
# and the quiet half, and 90 isolates the handful worth interrupting someone
# for. Re-check these if the heat formula changes again.
HEAT_TIERS = [
    (90, "High", "#000000", "#ffffff"),
    (60, "Medium", "#dedad9", "#000000"),
    (0, "Low", "#ffffff", "#000000"),
]

# Theme heat is on its own scale — it rewards breadth across companies rather
# than source diversity, so a sector-wide wave scores far above any single
# company's cluster. Calibrated separately for that reason.
THEME_HEAT_TIERS = [
    (200, "High", "#000000", "#ffffff"),
    (130, "Medium", "#dedad9", "#000000"),
    (0, "Low", "#ffffff", "#000000"),
]

def _tier(value: float, tiers: list[tuple[float, str, str, str]]) -> tuple[str, str, str]:
    for threshold, label, bg, fg in tiers:
        if value >= threshold:
            return label, bg, fg
    return tiers[-1][1:]


def score_tier(score: int) -> tuple[str, str, str]:
    return _tier(score, SCORE_TIERS)


def heat_tier(heat: float) -> tuple[str, str, str]:
    return _tier(heat, HEAT_TIERS)


def theme_heat_tier(heat: float) -> tuple[str, str, str]:
    return _tier(heat, THEME_HEAT_TIERS)


def inject_css() -> None:
    # PA brand: tokens from the PA Media Briefings site (pa-tokens.css), layout
    # from the Sector Signal Figma design (Ren's Playground, frame 2363:521).
    # Square corners, cobalt only on things you can click, signal cards as white
    # panels with a soft shadow. Press Sans throughout; the condensed face is
    # kept for the masthead lockup. The Google Fonts below are the stand-ins
    # pa-tokens.css itself lists, used wherever the PA CDN won't serve the real
    # faces.
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Archivo:wght@400;700;800&family=Oswald:wght@700&display=swap');

        :root {
            --pa-ink: #000000;
            --pa-paper: #ffffff;
            --pa-muted: #464646;
            --pa-cobalt: #004FFF;
            --pa-cobalt-hover: #0040cc;
            --pa-surface: #e8e5e4;
            --pa-sunken: #dedad9;
            --pa-newsprint: #e5e3d3;
            --pa-border: rgba(0, 0, 0, 0.2);
            --pa-hairline: rgba(0, 0, 0, 0.1);
            --pa-font-heading: 'Press Sans Condensed', Oswald, 'Arial Narrow', sans-serif;
            --pa-font-body: var(--pa-font-data);
            --pa-font-data: 'Press Sans', Archivo, Arial, Helvetica, sans-serif;
        }

        /* ── Masthead ─────────────────────────────────────────────── */
        .pa-masthead { margin: 0; }
        /* Chrome won't fetch a fallback webface by itself once the face ahead of
           it in the stack fails, so the UI stand-in is requested explicitly. */
        .pa-font-warm {
            position: absolute;
            opacity: 0;
            pointer-events: none;
            font-family: Archivo;
            font-weight: 400;
        }
        .pa-font-warm b { font-weight: 700; }
        .pa-lockup {
            --lockup-size: 46px;
            --lockup-cap: 0.74;
            --lockup-pad: 0.2;
            display: flex;
            align-items: center;
            gap: 7px;
            color: var(--pa-ink);
            margin-bottom: 1.25rem;
        }
        .pa-logo {
            width: var(--lockup-size);
            height: var(--lockup-size);
            flex-shrink: 0;
        }
        .pa-wordmark { display: flex; flex-direction: column; align-items: flex-start; }
        .pa-wordmark span {
            display: block;
            width: fit-content;
            background: var(--pa-ink);
            color: var(--pa-paper);
            font-family: var(--pa-font-heading);
            font-weight: 700;
            text-transform: uppercase;
            line-height: var(--lockup-cap);
            font-size: calc(var(--lockup-size) / 2 / (var(--lockup-cap) + 2 * var(--lockup-pad)));
            padding: calc(var(--lockup-pad) * 1em);
        }
        .pa-kicker {
            display: inline-block;
            background: var(--pa-cobalt);
            color: var(--pa-paper);
            font-family: var(--pa-font-heading);
            font-weight: 700;
            font-size: 1rem;
            line-height: 1.2;
            text-transform: uppercase;
            padding: 4px 8px;
        }
        .pa-kicker.ink { background: var(--pa-ink); }
        .pa-title {
            font-family: var(--pa-font-heading);
            font-weight: 700;
            font-size: 3rem;
            line-height: 1.0833;
            letter-spacing: 0.005em;
            color: var(--pa-ink);
            margin: 0.75rem 0 0.5rem 0;
        }
        /* The sector switcher: the popover's trigger set as the page title. */
        .st-key-pop-sector [data-testid="stPopoverButton"] {
            border: none;
            background: transparent;
            padding: 0;
            /* One title line (3rem x 1.0833), fixed so switching never moves the page. */
            height: 3.25rem;
            min-height: 3.25rem;
            margin: 0.75rem 0 0.5rem 0;
            justify-content: flex-start;
            max-width: 100%;
        }
        /* A name too long for the column is cut with an ellipsis rather than
           wrapping (which would move the page) or running into the health strip. */
        .st-key-pop-sector [data-testid="stPopoverButton"] > div > div,
        .st-key-pop-sector [data-testid="stPopoverButton"] [data-testid="stMarkdownContainer"] { min-width: 0; }
        /* Streamlit pulls this row 5px right (margin-right: -5px), which made
           the button 5px narrower than its label; undone so the row fits. */
        .st-key-pop-sector [data-testid="stPopoverButton"] > div { min-width: 0; margin-right: 0; max-width: 100%; }
        .st-key-pop-sector [data-testid="stPopoverButton"] p {
            overflow: hidden;
            text-overflow: ellipsis;
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
        [data-testid="stPopoverBody"]:has([class*="st-key-sectoropt-"]) hr { margin: 4px 0; }
        /* The label fills the row, so the muted note can sit at its right edge. */
        [class*="st-key-sectoropt-"] button > div,
        [class*="st-key-sectoropt-"] button > div > span { width: 100%; }
        [class*="st-key-sectoropt-"] [data-testid="stMarkdownContainer"] { flex: 1; }
        [class*="st-key-sectoropt-"] button p span { float: right; margin-left: 1.5rem; }
        /* Matched at the start of a class token, so no slug can collide. */
        :is([class^="st-key-sectoropt-off-"], [class*=" st-key-sectoropt-off-"]) [data-testid="stIconMaterial"] { visibility: hidden; }
        /* At the sector limit the row is visibly not clickable. Scoped to the
           popover so it outranks the menu's own row styles further down. */
        [data-testid="stPopoverBody"] .st-key-sector-new button:disabled p,
        [data-testid="stPopoverBody"] .st-key-sector-new button:disabled [data-testid="stIconMaterial"] { color: rgba(0, 0, 0, 0.45); }
        [data-testid="stPopoverBody"] .st-key-sector-new button:disabled:hover { background: transparent; }
        /* Clear of the standfirst, which ends in markdown's -16px margin. */
        .st-key-sector-state, .st-key-sector-notice { margin-top: 1.5rem; }
        /* Streamlit's element wrappers set visibility themselves, so every
           descendant is hidden, not just the container. */
        .st-key-health-reserve, .st-key-health-reserve * { visibility: hidden !important; }
        .sector-notice {
            font-family: var(--pa-font-data);
            font-size: 0.875rem;
            color: #5c5c5c;
            border-left: 4px solid var(--pa-ink);
            padding: 4px 12px;
            margin: 0 0 8px 0;
        }
        .pa-standfirst {
            font-family: var(--pa-font-body);
            font-size: 1.125rem;
            line-height: 1.6;
            color: var(--pa-muted);
            margin: 0;
        }

        /* ── Section heading (Figma 2363:543): Press Sans Bold 24, sentence case */
        .section-label {
            font-family: var(--pa-font-data);
            font-weight: 700;
            font-size: 1.5rem;
            line-height: 1.2;
            color: var(--pa-ink);
            margin: 2.5rem 0 1.75rem 0;
        }

        /* Empty states: a grey block with friendly copy, the width of a card. */
        .empty-block {
            display: flex;
            align-items: flex-start;
            gap: 12px;
            padding: 20px 24px;
            margin: 0 0 24px 0;
            background: #f3f3f3;
            font-family: var(--pa-font-data);
            color: var(--pa-ink);
        }
        .empty-icon {
            font-family: "Material Symbols Rounded";
            font-size: 24px;
            line-height: 1;
            color: var(--pa-muted);
        }
        .empty-title { font-weight: 700; font-size: 1rem; line-height: 1.4; }
        .empty-body { font-size: 0.9375rem; line-height: 1.5; color: var(--pa-muted); margin-top: 2px; }

        /* ── Signal card (Figma 2363:505) ─────────────────────────── */
        .signal-card {
            background: var(--pa-paper);
            box-shadow: 0 4px 24px rgba(0, 0, 0, 0.1);
            padding: 16px 24px 23px 24px;
            margin: 0 0 24px 0;
            font-family: var(--pa-font-data);
            color: var(--pa-ink);
        }
        .sc-head {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 12px;
            flex-wrap: wrap;
            min-height: 36px;
        }
        .sc-source {
            display: flex;
            align-items: center;
            gap: 7px;
            font-size: 1rem;
            min-width: 0;
        }
        .sc-logo {
            width: 24px;
            height: 24px;
            flex-shrink: 0;
            margin-right: 1px;
            object-fit: cover;
        }
        .sc-logo-initials {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            background: #1f1f1f;
            color: var(--pa-paper);
            font-weight: 700;
            font-size: 0.625rem;
            letter-spacing: 0.02em;
        }
        .sc-logo-sm { font-size: 0.5rem; }
        .sc-logo-person svg { width: 18px; height: 18px; }
        .sc-source-name { font-weight: 700; white-space: nowrap; }
        .sc-sep { opacity: 0.2; }
        .sc-time { position: relative; white-space: nowrap; cursor: default; }
        /* Exact date on hover/focus, in the sparkline tooltip's dark grey. */
        .sc-time-tip {
            position: absolute;
            left: 50%;
            bottom: calc(100% + 8px);
            z-index: 5;
            padding: 8px 12px;
            background: #1f1f1f;
            color: var(--pa-paper);
            font-family: var(--pa-font-data);
            font-size: 0.8125rem;
            font-weight: 400;
            line-height: 1.25;
            white-space: nowrap;
            opacity: 0;
            pointer-events: none;
            transform: translate(-50%, 4px);
            transition: opacity var(--dur-fast) var(--ease), transform var(--dur-fast) var(--ease);
        }
        .sc-time:hover .sc-time-tip,
        .sc-time:focus-visible .sc-time-tip { opacity: 1; transform: translate(-50%, 0); }
        .sc-time:focus-visible { outline: 2px solid var(--pa-cobalt); outline-offset: 2px; }
        .sc-relevance {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            background: rgba(0, 79, 255, 0.05);
            padding: 8px 12px;
            font-size: 1rem;
            white-space: nowrap;
        }
        .sc-ring { flex-shrink: 0; }
        .sc-title {
            font-weight: 700;
            font-size: 1.5rem;
            line-height: 1.2;
            margin-top: 12px;
        }
        .sc-body {
            font-size: 1rem;
            line-height: 24px;
            max-width: 724px;
            margin-top: 8px;
        }
        .sc-foot {
            display: flex;
            justify-content: space-between;
            align-items: flex-end;
            gap: 12px;
            margin-top: 18px;
        }
        .sc-tags {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
        }
        .sc-tag {
            display: inline-flex;
            align-items: center;
            gap: 5px;
            height: 20px;
            padding-right: 5px;
            font-weight: 700;
            font-size: 0.875rem;
            line-height: 1;
            color: #1f1f1f;
            white-space: nowrap;
        }
        .sc-tag-icon {
            display: inline-flex;
            width: 20px;
            height: 20px;
            color: var(--pa-paper);
        }
        .sc-tag-entity { background: rgba(31, 31, 31, 0.1); }
        .sc-tag-entity .sc-tag-icon { background: #1f1f1f; }
        .sc-tag-category { background: rgba(253, 134, 33, 0.1); }
        /* Figma's gavel is ink on orange, not white. */
        .sc-tag-category .sc-tag-icon { background: #fd8621; color: var(--pa-ink); }
        .sc-tag-more { background: rgba(31, 31, 31, 0.1); padding-left: 5px; }
        .sc-link {
            display: inline-flex;
            align-items: center;
            gap: 4px;
            font-weight: 700;
            font-size: 0.875rem;
            color: #1f1f1f !important;
            text-decoration: none !important;
            white-space: nowrap;
        }
        .sc-link:hover { color: var(--pa-cobalt) !important; }
        .pattern-badge {
            margin-top: 12px;
            font-family: var(--pa-font-data);
            font-size: 0.875rem;
            color: var(--pa-muted);
        }
        .sc-tag-plain { padding-left: 6px; padding-right: 6px; }

        /* ── Pattern / theme cards: the signal card's anatomy ────── */
        [class*="st-key-pcard-"], [class*="st-key-tcard-"] {
            background: var(--pa-paper);
            box-shadow: 0 4px 24px rgba(0, 0, 0, 0.1);
            /* The selected card's cobalt edge (Figma 2363:687): every card has
               the 4px border, transparent until selected, and 4px less left
               padding, so selecting one never shifts its content. */
            border-left: 4px solid transparent;
            padding: 16px 24px 24px 20px;
            margin-bottom: 16px;
            gap: 0;
        }
        .gc-title {
            font-family: var(--pa-font-data);
            font-weight: 700;
            font-size: 1.5rem;
            line-height: 1.2;
        }
        .gc-theme-tile {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            background: #fd8621;
            color: var(--pa-ink);
        }
        .gc-theme-tile svg { width: 18px; height: 18px; }
        .group-card .sc-body { margin-top: 12px; }
        .gc-meta {
            margin-top: 12px;
            font-family: var(--pa-font-data);
            font-size: 0.875rem;
            color: var(--pa-muted);
        }
        .gc-tags { margin-top: 16px; }
        /* Streamlit's -16px margin on markdown text ate the card's bottom
           padding, leaving the tags 4px from the edge. */
        [class*="st-key-pcard-"] [data-testid="stMarkdownContainer"],
        [class*="st-key-tcard-"] [data-testid="stMarkdownContainer"] { margin-bottom: 0; }
        /* Sparkline (dataviz mark specs): 2px line, round join/cap; 10% wash;
           >=8px end-dot with a 2px surface ring; hairline baseline. */
        .tl { margin-top: 16px; }
        .tl-grid {
            stroke: rgba(0, 0, 0, 0.08);
            stroke-width: 1px;
            vector-effect: non-scaling-stroke;
        }
        .tl-track {
            position: relative;
            height: 56px;
            border-bottom: 1px solid var(--pa-border);
        }
        .tl-svg { display: block; width: 100%; height: 100%; overflow: visible; }
        .tl-line {
            fill: none;
            stroke: var(--pa-cobalt);
            stroke-width: 2px;
            stroke-linejoin: round;
            stroke-linecap: round;
            vector-effect: non-scaling-stroke;
        }
        .tl-area { fill: var(--pa-cobalt); fill-opacity: 0.1; stroke: none; }
        /* Quiet stretches (no signals either side) in grey: the palest grey
           that still clears 3:1 against white for a graphical mark. */
        .tl-line.tl-line-quiet { stroke: #8a8a8a; }
        .tl-dot.tl-quiet, .tl-hdot.tl-quiet { background: #8a8a8a; }
        /* Hover layer: a column per week, above the card's click overlay so
           list cards get tooltips too (the page script forwards clicks). */
        .tl-cols { position: absolute; inset: -8px 0 0 0; z-index: 3; }
        .tl-col { position: absolute; top: 0; bottom: 0; cursor: crosshair; }
        .tl-guide, .tl-hdot, .tl-tip { position: absolute; opacity: 0; pointer-events: none; }
        .tl-guide {
            top: 8px;
            bottom: 0;
            width: 1px;
            background: rgba(0, 79, 255, 0.25);
            transform: translateX(-0.5px);
        }
        .tl-hdot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: var(--pa-cobalt);
            box-shadow: 0 0 0 2px var(--pa-paper);
            transform: translate(-50%, 50%);
        }
        .tl-tip {
            z-index: 4;
            display: flex;
            flex-direction: column;
            gap: 2px;
            padding: 8px 12px;
            background: #1f1f1f;
            color: var(--pa-paper);
            font-family: var(--pa-font-data);
            font-size: 0.8125rem;
            line-height: 1.25;
            white-space: nowrap;
            transform: translate(-50%, 4px);
        }
        .tl-tip b { font-size: 0.9375rem; font-weight: 700; }
        .tl-tip.tl-tip-start { transform: translate(-12px, 4px); }
        .tl-tip.tl-tip-end { transform: translate(calc(-100% + 12px), 4px); }
        .tl-col:is(:hover, .tl-on) .tl-guide,
        .tl-col:is(:hover, .tl-on) .tl-hdot { opacity: 1; }
        .tl-col:is(:hover, .tl-on) .tl-tip { opacity: 1; transform: translate(-50%, 0); }
        .tl-col:is(:hover, .tl-on) .tl-tip.tl-tip-start { transform: translate(-12px, 0); }
        .tl-col:is(:hover, .tl-on) .tl-tip.tl-tip-end { transform: translate(calc(-100% + 12px), 0); }
        .tl-guide, .tl-hdot, .tl-tip {
            transition: opacity var(--dur-fast) var(--ease), transform var(--dur-fast) var(--ease);
        }
        .tl-dot {
            position: absolute;
            right: 0;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--pa-cobalt);
            box-shadow: 0 0 0 2px var(--pa-paper);
            transform: translate(50%, 50%);
        }
        .tl-axis {
            display: flex;
            justify-content: space-between;
            margin-top: 4px;
            font-family: var(--pa-font-data);
            font-size: 0.75rem;
            color: var(--pa-muted);
        }
        /* The whole card is the click target: its button is stretched over
           the card and made invisible. Focus shows as the card's outline. */
        [class*="st-key-pcard-"], [class*="st-key-tcard-"] {
            position: relative;
            cursor: pointer;
        }
        [class*="st-key-pcard-"]:has(button:disabled),
        [class*="st-key-tcard-"]:has(button:disabled) { cursor: default; }
        [class*="st-key-pcard-"] [data-testid="stElementContainer"]:has([data-testid="stButton"]),
        [class*="st-key-tcard-"] [data-testid="stElementContainer"]:has([data-testid="stButton"]) {
            position: absolute;
            inset: 0;
            z-index: 2;
            margin: 0;
        }
        [class*="st-key-pcard-"] [data-testid="stButton"],
        [class*="st-key-tcard-"] [data-testid="stButton"],
        [class*="st-key-pcard-"] [data-testid="stButton"] > *,
        [class*="st-key-tcard-"] [data-testid="stButton"] > * { width: 100%; height: 100%; }
        [class*="st-key-pcard-"] [data-testid="stButton"] button,
        [class*="st-key-tcard-"] [data-testid="stButton"] button {
            width: 100%;
            height: 100%;
            opacity: 0;
            cursor: inherit;
        }
        [class*="st-key-pcard-"]:has(button:focus-visible),
        [class*="st-key-tcard-"]:has(button:focus-visible) { outline-color: var(--pa-cobalt); }

        /* ── Preview pane ──────────────────────────────────────────
           Fixed to the window's right edge at full height, apart from the
           title and the list, which move over for it. White, lifted off the
           page with the cards' drop shadow; its left edge is the
           drag-to-resize handle, and a × in the corner closes it. */
        :root { --preview-width: min(34rem, 38vw); }
        [data-testid="stLayoutWrapper"]:has(> [class*="st-key-signals-panel-"]) {
            position: fixed;
            top: 0;
            right: 0;
            bottom: 0;
            width: var(--preview-width);
            z-index: 999990;
        }
        /* Only when the pane is in the visible tab: as fragments, Patterns and
           Themes stay mounted (hidden) while Feed shows, and matching any
           pane squeezed the Feed for a pane nobody could see. */
        [data-testid="stMain"]:has([role="tabpanel"] [class*="st-key-signals-panel-"]) {
            padding-right: var(--preview-width);
        }
        [class*="st-key-signals-panel-"] {
            position: relative;
            height: 100%;
            overflow-y: auto;
            background: var(--pa-paper);
            box-shadow: 0 4px 24px rgba(0, 0, 0, 0.1);
            padding: 2rem 1.75rem 3rem 1.75rem;
            gap: 0;
        }
        /* The pane's head (summary and sparkline) sticks to the top while the
           timeline scrolls under it. The pane's own 2rem top padding is pulled
           back so the head sits flush, with a hairline shadow once stuck. */
        /* Sticky goes on Streamlit's wrapper around the container: the
           container itself is only as tall as its wrapper, so it has nowhere
           to stick within it. */
        [data-testid="stLayoutWrapper"]:has(> [class*="st-key-sp-head-"]) {
            position: sticky;
            top: -2rem;
            z-index: 4;
            margin: -2rem -1.75rem 0 -1.75rem;
            /* Full bleed: the wrapper is width:100% by default, so the
               negative side margins alone wouldn't widen it. */
            width: calc(100% + 3.5rem) !important;
            max-width: none;
        }
        [class*="st-key-sp-head-"] {
            position: relative;
            background: var(--pa-paper);
            /* Markdown's -16px bottom margin would otherwise let the last tag
               row hang below the head's white background. */
            padding: 2rem 1.75rem 2rem 1.75rem;
            box-shadow: 0 6px 12px -8px rgba(0, 0, 0, 0.18);
            gap: 0;
        }
        /* Room on the right of the title row for the close button. */
        [class*="st-key-sp-head-"] .group-card-full .sc-head { padding-right: 2.5rem; }
        /* The close button, in the head's top-right corner. */
        [class*="st-key-sp-close-"] {
            position: absolute;
            top: 1.25rem;
            right: 1rem;
            width: auto;
            z-index: 2;
        }
        /* The pane's signals: a quiet list on off-white under the white,
           pinned head. A date column, then a light rail with a small grey
           dot per signal (cobalt on hover, when its week lights up on the
           sparkline), and hairlines between rows. */
        [class*="st-key-signals-panel-"] {
            background: color-mix(in srgb, var(--pa-newsprint) 30%, var(--pa-paper));
        }
        .sp-list { margin: 0; padding: 0; font-family: var(--pa-font-data); }
        /* Each signal is a tile: invisible until hovered (white on the
           off-white list) or opened. The side padding is pulled back with a
           negative margin so the content doesn't move. */
        .sp-item {
            position: relative;
            margin: 0 -0.75rem;
            padding: 0.875rem 0.75rem;
            transition: background var(--dur-fast, 120ms) var(--ease, ease);
        }
        .sp-item + .sp-item { border-top: 1px solid #e3e1d8; }
        .sp-item:hover, .sp-item[open] { background: var(--pa-paper); }
        /* The rail: one segment per signal, each reaching 1px up over the
           hairline above, so it runs unbroken. It starts at the first dot and
           stops at the last; a lone signal has none. Centred on the dots. */
        .sp-item::before {
            content: "";
            position: absolute;
            left: calc(0.75rem + 3.75rem - 1px);
            top: -1px;
            bottom: 0;
            width: 1px;
            background: #d8d6cc;
        }
        .sp-item:first-child::before { top: 23px; }
        .sp-item:last-child::before { bottom: auto; height: 24px; }
        .sp-item:first-child:last-child::before { display: none; }
        .sp-row {
            display: grid;
            grid-template-columns: 3.75rem 1fr;
            cursor: pointer;
            list-style: none;
        }
        .sp-row::-webkit-details-marker { display: none; }
        .sp-row::marker { content: ""; }
        .sp-row:focus-visible { outline: 2px solid var(--pa-cobalt); outline-offset: 2px; }
        .sp-date {
            padding-top: 2px;
            font-size: 0.8125rem;
            color: #6b6b6b;
            white-space: nowrap;
        }
        .sp-main {
            position: relative;
            display: block;
            min-width: 0;
            padding-left: 1.25rem;
        }
        .sp-main::before {
            content: "";
            position: absolute;
            left: -4px;
            top: 6px;
            width: 7px;
            height: 7px;
            border-radius: 50%;
            background: #b9b7ad;
            z-index: 1;
            transition: background var(--dur-fast, 120ms) var(--ease, ease);
        }
        .sp-item:hover .sp-main::before, .sp-item[open] .sp-main::before { background: var(--pa-cobalt); }
        .sp-title {
            display: block;
            font-weight: 700;
            font-size: 0.9375rem;
            line-height: 1.35;
            color: var(--pa-ink);
        }
        .sp-body {
            display: -webkit-box;
            margin-top: 4px;
            font-size: 0.8125rem;
            line-height: 1.45;
            color: var(--pa-muted);
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }
        .sp-item[open] .sp-body { display: block; -webkit-line-clamp: unset; }
        /* The opened part: companies named, the exact date, the source link,
           lined up under the content column. */
        .sp-more {
            margin: 10px 0 0 calc(3.75rem + 1.25rem);
            font-size: 0.75rem;
            color: #6b6b6b;
        }
        /* Everything in the opened part matches the grey meta line above it:
           12px text, 16px icons (as the source logo), regular weight. */
        .sp-tags { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 8px; }
        .sp-tags .sc-tag {
            height: 16px;
            gap: 5px;
            padding-right: 5px;
            font-weight: 400;
            font-size: 0.75rem;
            color: #464646;
        }
        .sp-tags .sc-tag-icon { width: 16px; height: 16px; }
        .sp-tags .sc-tag-icon svg, .sp-tags .sc-tag-icon img { width: 12px; height: 12px; margin: auto; }
        .sp-when { margin-bottom: 8px; }
        [class*="st-key-signals-panel-"] a.sp-open {
            display: inline-flex;
            align-items: center;
            gap: 4px;
            font-family: var(--pa-font-data);
            font-weight: 400;
            font-size: 0.75rem;
            color: var(--pa-cobalt);
            text-decoration: none;
        }
        [class*="st-key-signals-panel-"] a.sp-open svg { width: 12px; height: 12px; }
        [class*="st-key-signals-panel-"] a.sp-open:hover { text-decoration: underline; }
        .sp-meta {
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            gap: 4px;
            margin-top: 6px;
            font-size: 0.75rem;
            color: #6b6b6b;
        }
        .sp-dot { color: #b9b7ad; }
        .sp-src, .sp-rel { display: inline-flex; align-items: center; gap: 5px; }
        .sp-src .sc-logo { width: 16px; height: 16px; font-size: 0.4375rem; margin: 0; }
        .sp-rel .sc-ring { width: 14px; height: 14px; }
        [class*="st-key-sp-close-"] button {
            min-height: 32px;
            height: 32px;
            width: 32px;
            padding: 0;
            justify-content: center;
            color: var(--pa-ink);
        }
        [class*="st-key-sp-close-"] button:hover { background: #f3f3f3; color: var(--pa-ink); }
        .sp-resize {
            position: fixed;
            top: 0;
            bottom: 0;
            right: calc(var(--preview-width) - 4px);
            width: 8px;
            cursor: col-resize;
            z-index: 999991;
        }
        .sp-resize:hover, .sp-resize:focus-visible, body.sp-resizing .sp-resize {
            background: linear-gradient(to right, transparent 3px, var(--pa-cobalt) 3px, var(--pa-cobalt) 5px, transparent 5px);
            outline: none;
        }
        body.sp-resizing { cursor: col-resize; user-select: none; }
        .group-card-full .gc-tags { margin-top: 16px; }
        .gc-points { list-style: none; margin: 12px 0 0 0; padding: 0; }
        .gc-points li {
            position: relative;
            padding-left: 1.25rem;
            margin-bottom: 0.5rem;
            font-family: var(--pa-font-data);
            font-size: 0.9375rem;
            line-height: 1.5;
        }
        .gc-points li::before {
            content: "";
            position: absolute;
            left: 0;
            top: 0.55em;
            width: 8px;
            height: 8px;
            background: var(--pa-cobalt);
        }
        /* "Signals (7)": a small label over the list; the pinned head's
           shadow already separates the two. */
        .sp-section {
            margin: 1.5rem 0 1rem 0;
            font-family: var(--pa-font-data);
            font-weight: 700;
            font-size: 0.8125rem;
            letter-spacing: 0.04em;
            text-transform: uppercase;
            color: #6b6b6b;
        }
        /* Source signals: white cards on a white pane, so a grey border
           separates them instead of the list's shadow. They're narrower than
           the feed's, so they tighten up. */
        [class*="st-key-signals-panel-"] .signal-card {
            box-shadow: none;
            border: 1px solid #cccccc;
            padding: 12px 16px 16px 16px;
            margin-bottom: 12px;
        }
        [class*="st-key-signals-panel-"] .sc-title { font-size: 1.0625rem; }
        [class*="st-key-signals-panel-"] .sc-body { font-size: 0.875rem; line-height: 1.5; }
        [class*="st-key-signals-panel-"] .sc-source,
        [class*="st-key-signals-panel-"] .sc-relevance { font-size: 0.8125rem; }
        [class*="st-key-signals-panel-"] .sc-relevance { padding: 4px 8px; }
        [class*="st-key-signals-panel-"] .sc-foot { flex-wrap: wrap; }
        /* The resize script's st.html block shouldn't add a gap. */
        [data-testid="stElementContainer"]:has([data-testid="stHtml"] script) { display: none; }
        @media (max-width: 767px) {
            /* Phones: a sheet along the bottom of the screen. */
            [data-testid="stLayoutWrapper"]:has(> [class*="st-key-signals-panel-"]) {
                top: auto;
                left: 0;
                width: 100%;
                height: 55vh;
            }
            [data-testid="stMain"]:has([role="tabpanel"] [class*="st-key-signals-panel-"]) {
                padding-right: 0;
                padding-bottom: 55vh;
            }
            [class*="st-key-signals-panel-"] {
                border-left: none;
                border-top: 1px solid #cccccc;
                padding: 1.25rem 1rem 2rem 1rem;
                box-shadow: 0 -8px 24px rgba(0, 0, 0, 0.08);
            }
            .sp-resize { display: none; }
            /* The selected card is in view above the sheet, so the sheet
               leads with its signals rather than repeating the card. */
            [class*="st-key-signals-panel-"] .group-card-full { display: none; }
            [class*="st-key-signals-panel-"] .sp-section { margin-top: 0; padding-top: 0; border-top: none; }
        }

        /* ── Freshness strip: PA status badge ─────────────────────── */
        .health-strip {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            font-family: var(--pa-font-data);
            font-weight: 700;
            font-size: 0.8125rem;
            padding: 0.4em 0.8em;
            margin: 1.25rem 0 0.5rem 0;
            border-left: 4px solid currentColor;
        }
        .health-ok { background: #ecfdf3; color: #15803d; }
        .health-warn { background: #fffaeb; color: #b54708; }
        .health-bad { background: #fef3f2; color: #b3261e; }

        /* ── Streamlit chrome, pulled into the PA idiom ───────────── */
        [data-testid="stMainBlockContainer"] {
            max-width: 90rem;
            padding: 2rem clamp(1rem, 3vw, 2.5rem) 4rem;
        }
        [data-testid="stHeader"] { background: transparent; }
        [data-testid="stCaptionContainer"] p {
            font-family: var(--pa-font-data);
            color: var(--pa-muted);
        }
        /* Tabs (Figma 2363:635): underline style, bold when active. Streamlit
           draws the cobalt underline itself from primaryColor. */
        [data-testid="stTabs"] { margin-top: 1.5rem; }
        [data-testid="stTab"] {
            min-width: 117px;
            justify-content: center;
            padding: 10px;
        }
        [data-testid="stTab"] p {
            font-family: var(--pa-font-data);
            font-weight: 400;
            font-size: 1rem;
            color: var(--pa-ink);
        }
        [data-testid="stTab"][aria-selected="true"] p { font-weight: 700; }
        /* A grey rule under the whole tab bar, as in the frame; the active
           tab's cobalt underline sits on it. Hover tints the tab. */
        [data-testid="stTabs"] [role="tablist"] { border-bottom: 1px solid #cccccc; }
        [data-testid="stTabs"] [data-baseweb="tab-border"] { display: none; }
        [data-testid="stTab"] { transition: background-color var(--dur-fast) var(--ease); }
        [data-testid="stTab"]:hover { background: #f3f3f3; }
        [data-testid="stTab"][aria-selected="true"]:hover { background: #f3f3f3; }
        /* Sort, lifted onto the right end of the tab row: the slot sits just
           above the tabs at zero height, and the control is placed over the
           row's right edge, centred on it. */
        .st-key-tabs-sort {
            position: relative;
            height: 0;
            overflow: visible;
            z-index: 10;
        }
        .st-key-tabs-sort [data-testid="stLayoutWrapper"]:has(> .st-key-pop-sort),
        .st-key-tabs-sort > [data-testid="stElementContainer"],
        .st-key-tabs-sort .st-key-pop-sort {
            position: absolute;
            right: 0;
            top: var(--sort-top, 40px);
        }
        /* Same 40px as a tab, so the boxes match as well as the labels. */
        .st-key-tabs-sort [data-testid="stPopoverButton"] {
            height: 40px;
            min-height: 40px;
            padding-top: 0;
            padding-bottom: 0;
        }
        /* The menu takes the button's width (set by the page script when
           the button is clicked), so it lines up under it exactly. */
        [data-testid="stPopoverBody"]:has([class*="st-key-sortopt-"]) {
            min-width: 0;
            width: var(--sort-menu-w, auto);
        }
        /* PA fields: white with an ink hairline, never the grey card fill. */
        [data-testid="stTextInputRootElement"],
        [data-testid="stTextAreaRootElement"] {
            background: var(--pa-paper);
            border-color: var(--pa-ink);
        }
        /* Pattern and theme rows take the signal card's panel treatment. */
        [data-testid="stMain"] [data-testid="stExpander"] details {
            border: none;
            background: var(--pa-paper);
            box-shadow: 0 4px 24px rgba(0, 0, 0, 0.1);
            margin-bottom: 8px;
        }
        [data-testid="stExpander"] details summary:hover { background: rgba(0, 79, 255, 0.05); }
        [data-testid="stExpander"] summary p {
            font-family: var(--pa-font-data);
            font-weight: 700;
        }
        /* White sidebar with a hairline edge; the feed's filters live here. */
        [data-testid="stSidebar"] { border-right: 1px solid #e7e7e7; }
        /* ── Sidebar filters (Ren's Playground, frame 2374:1266) ─────
           Collapsible sections with a bold 16px heading and the arrow on the
           right; cobalt square checkboxes; a slider with its value in bold
           above the thumb; Company / entity as a search field with the chosen
           companies listed underneath. One left edge throughout. */
        .st-key-sb-filters { gap: 4px; }
        /* The title sits in the sidebar's top strip, level with the collapse
           button (which is on the right), with Clear all beside it. Fixed
           height, and Clear all is always there (hidden when there's nothing
           to clear), so setting a filter never shifts the sidebar. */
        .st-key-sb-filters-head {
            justify-content: flex-start;
            gap: 16px;
            height: 32px;
            margin-top: calc(var(--sb-head-top, 14px) - var(--sb-content-top, 76px));
            margin-bottom: 16px;
            position: relative;
            z-index: 1000000;
        }
        .st-key-sb-filters-head,
        .st-key-sb-filters-head > * { max-height: 32px; }
        .st-key-sb-filters-head button { padding: 0; min-height: 0; height: 32px; }
        .st-key-sb-filters-head button:disabled { visibility: hidden; }
        .st-key-sb-filters-head [data-testid="stMarkdownContainer"],
        .st-key-sb-filters-head [data-testid="stMarkdown"] { margin: 0; }
        .st-key-sb-filters-head [data-testid="stElementContainer"] { align-self: center; }
        [data-testid="stSidebarHeader"] { pointer-events: none; }
        [data-testid="stSidebarHeader"] button { pointer-events: auto; }
        [data-testid="stSidebar"] .st-key-sb-filters [data-testid="stTextInput"] { padding: 0 0 8px 0; }

        /* Sections */
        .st-key-sb-filters [class*="st-key-sec-"] details {
            border: none;
            background: transparent;
        }
        .st-key-sb-filters [class*="st-key-sec-"] summary {
            padding: 8px 0 4px 0;
            background: transparent;
        }
        .st-key-sb-filters [class*="st-key-sec-"] summary:hover { background: transparent; }
        .st-key-sb-filters [class*="st-key-sec-"] summary > span {
            flex-direction: row-reverse;
            justify-content: space-between;
        }
        .st-key-sb-filters [class*="st-key-sec-"] summary p {
            font-family: var(--pa-font-data);
            font-weight: 700;
            font-size: 1rem;
            color: var(--pa-ink);
        }
        .st-key-sb-filters [class*="st-key-sec-"] summary [data-testid="stIconMaterial"] {
            font-size: 24px;
            color: var(--pa-ink);
        }
        .st-key-sb-filters [data-testid="stExpanderDetails"] { padding: 4px 0 12px 0; }
        .st-key-sb-filters [data-testid="stExpanderDetails"] [data-testid="stVerticalBlock"] { gap: 4px; }

        /* Checkboxes: square, outlined grey when off, cobalt when on. */
        .st-key-sb-filters [data-testid="stCheckbox"] label {
            align-items: center;
            gap: 8px;
            min-height: 28px;
        }
        .st-key-sb-filters [data-testid="stCheckbox"] label > div:first-of-type {
            width: 18px;
            height: 18px;
            margin: 3px;
            flex-shrink: 0;
            border-radius: 0;
        }
        .st-key-sb-filters [data-testid="stCheckbox"] p,
        .st-key-sb-filters [data-testid="stRadio"] p {
            font-family: var(--pa-font-data);
            font-size: 1rem;
            line-height: 1.35;
            color: var(--pa-ink);
        }

        /* Slider: value in bold ink above a 16px cobalt thumb, 0 and 100 at
           the ends in bold at half opacity. */
        .st-key-sb-filters [data-testid="stSlider"] [role="slider"] {
            width: 16px;
            height: 16px;
        }
        .st-key-sb-filters [data-testid="stSliderThumbValue"] p {
            font-family: var(--pa-font-data);
            font-weight: 700;
            font-size: 1rem;
            color: var(--pa-ink);
        }
        .st-key-sb-filters [data-testid="stSliderTickBar"] p {
            font-family: var(--pa-font-data);
            font-weight: 700;
            font-size: 1rem;
            color: var(--pa-ink);
            opacity: 0.5;
        }

        /* Company / entity: a search field (the multiselect, its chips hidden)
           and the chosen companies as logo rows with a remove button. */
        .st-key-sb-filters [data-testid="stMultiSelect"] [data-testid="stMultiSelectTagsContainer"] > span {
            display: none;
        }
        .st-key-sb-filters [data-testid="stMultiSelectTagsContainer"]::before {
            content: "search";
            font-family: "Material Symbols Rounded";
            font-size: 22px;
            line-height: 1;
            color: rgba(0, 0, 0, 0.45);
            margin-right: 6px;
        }
        .st-key-sb-filters [data-testid="stMultiSelect"] input {
            font-family: var(--pa-font-data);
            font-size: 1rem;
        }
        [class*="st-key-co-row-"] {
            justify-content: space-between;
            gap: 8px;
            padding: 6px 0 2px 0;
        }
        .co-row {
            display: flex;
            align-items: center;
            gap: 8px;
            min-width: 0;
            font-family: var(--pa-font-data);
            font-size: 1rem;
            color: var(--pa-ink);
        }
        .co-row .sc-logo { width: 20px; height: 20px; font-size: 0.5rem; }
        .co-row .sc-logo-person svg { width: 15px; height: 15px; }
        .co-name { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        [class*="st-key-co-row-"] button { padding: 0; min-height: 0; }
        [class*="st-key-co-row-"] button,
        [class*="st-key-co-row-"] [data-testid="stIconMaterial"] { color: rgba(0, 0, 0, 0.6) !important; font-size: 20px; }
        [class*="st-key-co-row-"] button:hover,
        [class*="st-key-co-row-"] button:hover [data-testid="stIconMaterial"] { color: var(--pa-ink) !important; }

        /* ── Matching the frame's details ───────────────────────── */
        /* Labels regular, not the sidebar's bold widget-label style. */
        [data-testid="stSidebar"] .st-key-sb-filters [data-testid="stCheckbox"] label p,
        [data-testid="stSidebar"] .st-key-sb-filters [data-testid="stRadio"] label p {
            font-weight: 400;
            font-size: 1rem;
        }
        /* No rule under a section heading. */
        .st-key-sb-filters [class*="st-key-sec-"] summary,
        .st-key-sb-filters [class*="st-key-sec-"] details[open] summary { border: none; box-shadow: none; }
        .st-key-sb-filters [class*="st-key-sec-"] [data-testid="stExpanderDetails"] { border: none; }
        /* A filled drop-down arrow, as in the frame, turned right when closed. */
        .st-key-sb-filters [class*="st-key-sec-"] summary [data-testid="stIconMaterial"] { display: none; }
        .st-key-sb-filters [class*="st-key-sec-"] summary > span::before {
            content: "arrow_drop_down";
            font-family: "Material Symbols Rounded";
            font-size: 24px;
            line-height: 1;
            color: var(--pa-ink);
            transition: transform var(--dur-fast) var(--ease);
        }
        .st-key-sb-filters [class*="st-key-sec-"] details:not([open]) summary > span::before { transform: rotate(-90deg); }
        /* Radio rows share the checkbox rhythm. */
        .st-key-sb-filters [data-testid="stRadio"] [role="radiogroup"] { gap: 4px; }
        .st-key-sb-filters [data-testid="stRadio"] label { min-height: 28px; align-items: center; gap: 8px; }
        /* Slider: full-width track, 0 and 100 always shown. */
        [data-testid="stSidebar"] .st-key-sb-filters [data-testid="stSlider"] { padding-left: 0; padding-right: 0; }
        .st-key-sb-filters [data-testid="stSliderTickBar"] { opacity: 1 !important; visibility: visible !important; }
        /* Company field: icon inline, no drop-down arrow, 32px like the frame. */
        .st-key-sb-filters [data-testid="stMultiSelectTagsContainer"] {
            flex-wrap: nowrap;
            align-items: center;
            justify-content: flex-start;
            min-height: 0;
        }
        .st-key-sb-filters [data-testid="stMultiSelect"] [role="group"] > button { display: none; }
        /* Streamlit drops the placeholder once something is chosen; the
           chosen companies are listed below instead, so keep the prompt. */
        .st-key-sb-filters [data-testid="stMultiSelectTagsContainer"]:has(> span):not(:focus-within)::after {
            content: "Search by company";
            font-family: var(--pa-font-data);
            font-size: 1rem;
            color: rgba(0, 0, 0, 0.45);
            pointer-events: none;
        }
        .st-key-sb-filters [data-testid="stMultiSelectTagsContainer"]:has(> span):not(:focus-within) input {
            width: 0;
            min-width: 0;
            padding: 0;
        }
        .st-key-sb-filters [data-testid="stMultiSelect"] [role="group"] { min-height: 32px; }
        /* Search icons in grey, as in the frame. */
        .st-key-sb-filters [data-testid="stTextInputRootElement"] [data-testid="stIconMaterial"] { color: rgba(0, 0, 0, 0.45); }

        /* The dropdown list (rendered at page level): the menu style. */
        [data-baseweb="popover"] [role="listbox"] {
            border-radius: 0;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
        }
        [data-baseweb="popover"] [role="option"] {
            padding: 8px 12px;
            font-family: var(--pa-font-data);
            font-size: 1rem;
        }

        /* ── Feed filter bar (Ren's Playground, frame 2371:835) ──────
           Controls are plain (icon + "Label: **Value**") until opened, then
           #e7e7e7. Menus are white with a 0 4px 12px shadow; rows are 8x12px,
           16px Press Sans; chosen options carry a cobalt tick. */
        .st-key-feed-filters { gap: 4px; margin: 0.5rem 0 0.25rem 0; }
        :is(.st-key-feed-filters, .st-key-tabs-sort) [data-testid="stPopover"],
        :is(.st-key-feed-filters, .st-key-tabs-sort) [data-testid="stPopover"] > div,
        :is(.st-key-feed-filters, .st-key-tabs-sort) [data-testid="stPopoverButton"],
        :is(.st-key-feed-filters, .st-key-tabs-sort) [data-testid="stPopoverButton"] > div,
        :is(.st-key-feed-filters, .st-key-tabs-sort) [data-testid="stPopoverButton"] > div > div { flex-shrink: 0; }
        :is(.st-key-feed-filters, .st-key-tabs-sort) [data-testid="stPopoverButton"] {
            min-height: 40px;
            padding: 8px 12px;
            border: none;
            border-radius: 0;
            background: transparent;
            box-shadow: none;
            color: var(--pa-ink);
        }
        :is(.st-key-feed-filters, .st-key-tabs-sort) [data-testid="stPopoverButton"]:hover,
        :is(.st-key-feed-filters, .st-key-tabs-sort) [data-testid="stPopoverButton"][aria-expanded="true"] { background: #e7e7e7; }
        :is(.st-key-feed-filters, .st-key-tabs-sort) [data-testid="stPopoverButton"]:focus-visible { outline: 2px solid var(--pa-cobalt); }
        :is(.st-key-feed-filters, .st-key-tabs-sort) [data-testid="stPopoverButton"] [data-testid="stIconMaterial"] { font-size: 20px; }
        :is(.st-key-feed-filters, .st-key-tabs-sort) [data-testid="stPopoverButton"] p {
            font-family: var(--pa-font-data);
            font-size: 1rem;
            font-weight: 400;
            white-space: nowrap;
        }
        :is(.st-key-feed-filters, .st-key-tabs-sort) [data-testid="stPopoverButton"] p strong { font-weight: 700; }
        /* Streamlit pulls the button's content wrapper 5px right (margin-right
           -5px, to tuck in the chevron we hide), which clipped labels and made
           the right padding 5px narrower than the left. */
        :is(.st-key-feed-filters, .st-key-tabs-sort) [data-testid="stPopoverButton"] > div { margin-right: 0; }
        /* No chevron: the open state's grey says it's a menu. */
        :is(.st-key-feed-filters, .st-key-tabs-sort) [data-testid="stPopoverButton"] > div > div:last-child:not(:first-child):has([data-testid="stIconMaterial"]) { display: none; }

        /* Search fields: 1px #ccc outline, no fill. */
        .st-key-feed-filters [data-testid="stTextInputRootElement"],
        :is([data-testid="stPopoverBody"], [data-testid="stSidebar"]) [data-testid="stTextInputRootElement"] {
            min-height: 40px;
            border: 1px solid #cccccc;
            border-radius: 0;
            background: var(--pa-paper);
        }
        .st-key-feed-filters [data-testid="stTextInputRootElement"]:focus-within,
        :is([data-testid="stPopoverBody"], [data-testid="stSidebar"]) [data-testid="stTextInputRootElement"]:focus-within {
            border-color: var(--pa-cobalt);
        }
        .st-key-feed-filters input, :is([data-testid="stPopoverBody"], [data-testid="stSidebar"]) input {
            font-family: var(--pa-font-data);
            font-size: 1rem;
        }
        .st-key-pop-sort { margin-left: auto; }
        .st-key-clear-filters button p {
            font-family: var(--pa-font-data);
            font-weight: 700;
            font-size: 0.875rem;
            color: var(--pa-cobalt);
        }

        [data-testid="stPopoverBody"] {
            min-width: 264px;
            /* Streamlit fixes the height when the menu opens; the company
               list changes as you type, so let it grow (within its cap). */
            height: auto !important;
            margin-top: 8px;
            padding: 0;
            border: none;
            border-radius: 0;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
        }
        :is([data-testid="stPopoverBody"], [data-testid="stSidebar"]) [data-testid="stVerticalBlock"] { gap: 0; }
        :is([data-testid="stPopoverBody"], [data-testid="stSidebar"]) [data-testid="stTextInput"] { padding: 8px; }
        :is([data-testid="stPopoverBody"], [data-testid="stSidebar"]) [data-testid="stSlider"],
        :is([data-testid="stPopoverBody"], [data-testid="stSidebar"]) [data-testid="stDateInput"] { padding: 12px; }
        :is([data-testid="stPopoverBody"], [data-testid="stSidebar"]) [data-testid="stCaptionContainer"] { padding: 4px 12px 8px; }

        /* Menu rows: ticked lists (sort, source, type) and plain actions. */
        :is([data-testid="stPopoverBody"], [data-testid="stSidebar"]) button[kind="tertiary"] {
            justify-content: flex-start;
            min-height: 0;
            padding: 8px 12px;
            border-radius: 0;
        }
        :is([data-testid="stPopoverBody"], [data-testid="stSidebar"]) button[kind="tertiary"] > div,
        :is([data-testid="stPopoverBody"], [data-testid="stSidebar"]) button[kind="tertiary"] > div > span { justify-content: flex-start; gap: 8px; }
        :is([data-testid="stPopoverBody"], [data-testid="stSidebar"]) button[kind="tertiary"]:hover { background: var(--pa-surface); }
        :is([data-testid="stPopoverBody"], [data-testid="stSidebar"]) button[kind="tertiary"] p {
            font-family: var(--pa-font-data);
            font-size: 1rem;
            color: var(--pa-ink);
            text-align: left;
        }
        :is([data-testid="stPopoverBody"], [data-testid="stSidebar"]) button[kind="tertiary"] p strong { font-weight: 700; }
        :is([data-testid="stPopoverBody"], [data-testid="stSidebar"]) [data-testid="stIconMaterial"] { color: var(--pa-cobalt); font-size: 20px; }
        [class*="st-key-sortopt-"][class*="-off"] [data-testid="stIconMaterial"],
        [class*="st-key-src-"][class*="-off"] [data-testid="stIconMaterial"],
        [class*="st-key-typ-"][class*="-off"] [data-testid="stIconMaterial"],
        [class*="st-key-scr-"][class*="-off"] [data-testid="stIconMaterial"],
        [class*="st-key-dts-"][class*="-off"] [data-testid="stIconMaterial"] { visibility: hidden; }

        /* Filter sections, divided by hairlines. */
        .fp-head {
            padding: 12px 12px 4px 12px;
            border-top: 1px solid #e7e7e7;
            font-family: var(--pa-font-data);
            font-size: 0.8125rem;
            font-weight: 700;
            color: var(--pa-muted);
        }
        .fp-head.fp-first { border-top: none; padding-top: 4px; }

        .sb-title {
            font-family: var(--pa-font-data);
            font-weight: 700;
            font-size: 1.25rem;
            line-height: 32px;
            color: var(--pa-ink);
        }
        .st-key-sb-filters-head button p {
            font-family: var(--pa-font-data);
            font-weight: 700;
            font-size: 0.875rem;
            color: var(--pa-cobalt) !important;
        }
        .st-key-feed-filters [data-testid="stCaptionContainer"] { margin: 0; }
        [data-testid="stSidebar"] label p {
            font-family: var(--pa-font-data);
            font-weight: 700;
            font-size: 0.8125rem;
        }
        [data-testid="stSidebar"] h2 {
            font-family: var(--pa-font-heading);
            text-transform: uppercase;
            font-size: 1.25rem;
        }
        [data-baseweb="tag"] { border-radius: 0 !important; }

        /* ── Header action: Add to watchlist ─────────────────────────
           PA outline button (Media Briefings Button.astro "outline"): 2px ink
           border, square, Press Sans bold; fills ink on hover. */
        .st-key-header-actions { margin-bottom: 12px; }
        /* One action-button size everywhere: 44px tall, 20px side padding,
           Press Sans bold 16px. Primary is cobalt (theme); the header's
           secondary is the PA outline. Links share the label style. */
        .st-key-open-watchlist button,
        [data-testid="stDialog"] [data-testid^="stBaseButton-primary"],
        [data-testid="stDialog"] [data-testid^="stBaseButton-secondary"] {
            min-height: 44px;
            padding: 0 20px;
            border-radius: 0;
        }
        .st-key-open-watchlist button {
            border: 2px solid var(--pa-ink);
            background: transparent;
            color: var(--pa-ink);
        }
        .st-key-open-watchlist button p,
        [data-testid="stDialog"] [data-testid^="stBaseButton-"] p,
        [data-testid="stDialog"] [data-testid^="stBaseLinkButton-"] p {
            font-family: var(--pa-font-data);
            font-weight: 700;
            font-size: 1rem;
            line-height: 1.25;
        }
        .st-key-open-watchlist [data-testid="stIconMaterial"],
        [data-testid="stDialog"] [data-testid^="stBaseButton-"] [data-testid="stIconMaterial"] { font-size: 20px; }
        [data-testid="stDialog"] :is([data-testid^="stBaseButton-tertiary"],
                                     [data-testid^="stBaseLinkButton-tertiary"]) { padding: 0; min-height: 0; }
        /* Field text at the same 16px as the rest of the app. */
        [data-testid="stDialog"] input,
        [data-testid="stDialog"] textarea {
            font-family: var(--pa-font-data);
            font-size: 1rem;
        }
        .st-key-open-watchlist button:hover { background: var(--pa-ink); color: var(--pa-paper); }
        .st-key-open-watchlist button:hover p,
        .st-key-open-watchlist button:hover [data-testid="stIconMaterial"] { color: var(--pa-paper); }
        .st-key-open-watchlist button:focus-visible { outline: 2px solid var(--pa-cobalt); outline-offset: 2px; }

        /* The watchlist dialog: square, Press Sans, white fields with a #ccc
           outline, a cobalt primary button. */
        [data-testid="stDialog"] [role="dialog"] { border-radius: 0; }
        [data-testid="stDialog"] [role="dialog"] h2 {
            font-family: var(--pa-font-data);
            font-weight: 700;
            font-size: 1.375rem;
        }
        [data-testid="stDialog"] label p {
            font-family: var(--pa-font-data);
            font-weight: 700;
            font-size: 0.875rem;
        }
        [data-testid="stDialog"] [data-testid="stTextInputRootElement"],
        [data-testid="stDialog"] [data-testid="stTextAreaRootElement"] {
            border: 1px solid #cccccc;
            border-radius: 0;
            background: var(--pa-paper);
        }
        [data-testid="stDialog"] [data-testid="stTextInputRootElement"]:focus-within,
        [data-testid="stDialog"] [data-testid="stTextAreaRootElement"]:focus-within { border-color: var(--pa-cobalt); }
        /* Watchlist intro: illustration, headline, copy, primary action. */
        .wl-illustration svg { display: block; }
        .wl-illustration { margin: 0 0 20px 0; }
        .wl-headline {
            font-family: var(--pa-font-data);
            font-weight: 700;
            font-size: 1.5rem;
            line-height: 1.2;
            color: var(--pa-ink);
            margin-bottom: 8px;
        }
        .wl-copy {
            font-family: var(--pa-font-data);
            font-size: 1rem;
            line-height: 1.5;
            color: var(--pa-ink);
            margin: 0 0 12px 0;
        }
        .wl-copy.wl-muted { color: var(--pa-muted); font-size: 0.9375rem; }
        /* New-sector review: group labels styled as field labels, the
           keywords field outlined like the text fields, and source
           checkboxes in regular weight under their bold group label. */
        .ns-label {
            font-family: var(--pa-font-data);
            font-weight: 700;
            font-size: 0.875rem;
            color: var(--pa-ink);
            margin: 0;
        }
        [data-testid="stDialog"] .st-key-ns_keywords [role="group"] {
            border: 1px solid #cccccc;
            border-radius: 0;
            background: var(--pa-paper);
        }
        [data-testid="stDialog"] .st-key-ns_keywords [role="group"]:focus-within { border-color: var(--pa-cobalt); }
        [data-testid="stDialog"] [data-testid="stCheckbox"] label p {
            font-weight: 400;
            font-size: 0.9375rem;
        }
        /* The new-sector dialog opens from the switcher menu; the menu's
           layer sits above the dialog's, so hide it while a dialog is open. */
        body:has([data-testid="stDialog"] [role="dialog"]) [data-testid="stPopoverBody"] {
            display: none;
        }
        /* ── Motion ─────────────────────────────────────────────────
           PA's easing and durations (pa-tokens.css motion: 150/250/400ms,
           cubic-bezier(0.2, 0, 0, 1)). Movement is small, a lift of a couple
           of pixels, so it reads as polish rather than animation. */
        :root {
            --ease: cubic-bezier(0.2, 0, 0, 1);
            --dur-fast: 150ms;
            --dur: 250ms;
            --dur-slow: 400ms;
        }
        .signal-card,
        [class*="st-key-pcard-"],
        [class*="st-key-tcard-"] {
            transition:
                transform var(--dur) var(--ease),
                box-shadow var(--dur) var(--ease),
                border-color var(--dur) var(--ease),
                border-left-color var(--dur) var(--ease),
                outline-color var(--dur) var(--ease);
            outline: 2px solid transparent;
        }
        .signal-card:hover,
        [class*="st-key-pcard-"]:hover,
        [class*="st-key-tcard-"]:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 32px rgba(0, 0, 0, 0.14);
        }
        [class*="st-key-pcard-"]:active,
        [class*="st-key-tcard-"]:active {
            transform: translateY(0) scale(0.995);
            transition-duration: var(--dur-fast);
        }
        [class*="st-key-pcard-"]:has(button:disabled),
        [class*="st-key-tcard-"]:has(button:disabled) { border-left-color: var(--pa-cobalt); }
        /* Signals inside the pane are bordered, not shadowed: they darken
           their border instead of lifting. */
        [class*="st-key-signals-panel-"] .signal-card:hover {
            transform: none;
            box-shadow: none;
            border-color: #8a8a8a;
        }
        .sc-link, .sc-link svg,
        [data-testid="stTab"] p,
        [data-testid="stButton"] button p,
        [data-testid="stExpander"] summary {
            transition: color var(--dur-fast) var(--ease), background-color var(--dur-fast) var(--ease);
        }

        /* The pane slides in when the tab opens. Switching selection updates
           it in place, instantly: nothing waits on an animation. Fill mode is
           "backwards", not "both": a transform left on the pane after the
           animation would capture its fixed resize handle. */
        @keyframes pa-pane-in {
            from { opacity: 0; transform: translateX(24px); }
            to { opacity: 1; transform: translateX(0); }
        }
        [class*="st-key-signals-panel-"] {
            animation: pa-pane-in var(--dur-slow) var(--ease) backwards;
        }
        /* List sparklines draw in when the tab opens. The pane's doesn't
           animate: it changes with every selection, which should be instant. */
        /* A left-to-right reveal rather than a stroke-dash draw: dashes are
           measured in screen space under non-scaling-stroke, so a pathLength
           dash leaves gaps in the line. */
        @keyframes pa-reveal {
            from { clip-path: inset(0 100% 0 0); }
            to { clip-path: inset(0 0 0 0); }
        }
        @keyframes pa-fade-in { from { opacity: 0; } to { opacity: 1; } }
        .group-card:not(.group-card-full) .tl-svg {
            animation: pa-reveal 600ms var(--ease) backwards;
        }
        .group-card:not(.group-card-full) .tl-dot {
            animation: pa-fade-in var(--dur) var(--ease) 500ms backwards;
        }

        @media (prefers-reduced-motion: reduce) {
            *, *::before, *::after {
                animation: none !important;
                transition: none !important;
            }
            .signal-card:hover,
            [class*="st-key-pcard-"]:hover,
            [class*="st-key-tcard-"]:hover { transform: none; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_masthead(entries: list[dict] | None = None, current: dict | None = None,
                    at_cap: bool = False) -> None:
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
    # No gap between these three: the CSS margins space them as the single
    # masthead block did before the switcher (kicker, 12px, title, 8px, standfirst).
    with st.container(key="pa-intro", gap=None):
        st.markdown('<span class="pa-kicker">Sector</span>', unsafe_allow_html=True)
        _sector_switcher(entries, current, at_cap)
        st.markdown('<p class="pa-standfirst">Sector signals, scored for newsworthiness.</p>',
                    unsafe_allow_html=True)


def _sector_switcher(entries: list[dict], current: dict, at_cap: bool) -> None:
    """The sector name, set as the page title, opening a menu of sectors.
    at_cap comes from every known slug (see _slug_union), not just the menu's
    entries, which are the single legacy sector when the index is missing."""
    with st.popover(data.display_name(current), key="pop-sector"):
        for entry in entries:
            note = data.sector_note(entry)
            label = data.display_name(entry) + (f"  :gray[{note}]" if note else "")
            _check_row(f"sectoropt-{entry['slug']}", label, entry["slug"] == current["slug"],
                       _select_sector, (entry["slug"],), state_first=True)
        st.divider()
        st.button("Sector limit reached" if at_cap else "New sector  :blue-background[PREMIUM]",
                  key="sector-new", icon=":material/add:", type="tertiary", width="stretch",
                  disabled=at_cap,
                  help="Contact us to add more sectors." if at_cap else None,
                  on_click=_open_new_sector)
        if st.session_state.get("ns_open"):
            _new_sector_dialog()


def check_password() -> bool:
    if st.session_state.get("authenticated"):
        return True

    render_masthead()
    password = st.text_input("Password", type="password")
    if password:
        if password == st.secrets["DASHBOARD_PASSWORD"]:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    return False


def _secret(name: str) -> str | None:
    try:
        return st.secrets.get(name)
    except Exception:
        return None


@st.cache_data(ttl=600, show_spinner=False)
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


@st.cache_data(ttl=600, show_spinner=False)
def _cached_rules(slug: str):
    return data.load_sector_or_none(slug)


def sector_rules(slug: str):
    """The sector's config, refreshed every ten minutes so a newly created
    sector's rules are picked up. A missing config falls back to gambling's
    rules without caching that fallback."""
    return _cached_rules(slug) or data.sector_rules(data.GAMBLING)


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


def _current_sector_name() -> str:
    return st.session_state.get("sector_name", "this sector")


def safe_url(url: str) -> str:
    """Source URLs come from scraped hrefs on third-party pages and land
    inside an href="..." rendered with unsafe_allow_html, so both the scheme
    and the quoting need checking before they get there."""
    try:
        scheme = urlparse(url).scheme.lower()
    except ValueError:
        return "#"
    if scheme not in ("http", "https"):
        return "#"
    return html.escape(url, quote=True)


# How the newsworthiness tier reads on the card's relevance pill.
RELEVANCE_LABELS = {"High": "Highly relevant", "Medium": "Relevant", "Low": "Low relevance"}

# Cards show this many company tags before collapsing the rest into "+N more".
MAX_ENTITY_TAGS = 4


def _relative_time(published_at: str, now: datetime) -> str:
    """'2 hours ago' when the source gave a time, otherwise a day-level phrase.
    Many collectors only know the date, stored as midnight UTC — reading that
    as "14 hours ago" would invent a precision the data doesn't have."""
    dt = datetime.fromisoformat(published_at)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    if (dt.hour, dt.minute, dt.second) != (0, 0, 0):
        age = (now - dt).total_seconds()
        if 0 <= age < 24 * 3600:
            return _humanise_age(age)
    days = (now.date() - dt.date()).days
    if days <= 0:
        return "Today"
    if days == 1:
        return "Yesterday"
    if days < 7:
        return f"{days} days ago"
    return f"{dt.day} {dt:%b %Y}"


def _logo_dev_token() -> str | None:
    """Publishable logo.dev key, if configured. Only pk_ keys: the token ends up
    in every page's image URLs, so a secret sk_ key must never be used here."""
    try:
        token = st.secrets.get("LOGO_DEV_TOKEN")
    except Exception:
        return None
    return token if token and token.startswith("pk_") else None


try:
    _UK = ZoneInfo("Europe/London")
except Exception:  # no tz database available: fall back to UTC
    _UK = timezone.utc


def _full_date(published_at: str) -> str:
    """The exact date for the relative-time tooltip, with the UK time when
    the source gave one (date-only signals are stored as midnight UTC)."""
    dt = datetime.fromisoformat(published_at)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    if (dt.hour, dt.minute, dt.second) == (0, 0, 0):
        return f"{dt:%A} {dt.day} {dt:%B %Y}"
    local = dt.astimezone(_UK)
    return f"{local:%A} {local.day} {local:%B %Y}, {local:%H:%M}"


def _source_logo(source: str) -> str:
    token = _logo_dev_token()
    domain = SOURCE_DOMAINS.get(source)
    if token and domain:
        return _logo_dev_img(domain, token)
    logo = SOURCE_LOGOS.get(source)
    if logo:
        return f'<img class="sc-logo" src="{logo}" alt="">'
    initials = SOURCE_NAMES.get(source, (source, source[:3].upper()))[1]
    size = "sc-logo-sm" if len(initials) > 2 else ""
    return f'<span class="sc-logo sc-logo-initials {size}">{html.escape(initials)}</span>'


_COMPANY_DOMAINS = {match_key(name): domain for name, domain in COMPANY_DOMAINS.items()}
_PEOPLE = {match_key(name) for name in PEOPLE}


def _is_person(name: str) -> bool:
    return match_key(name) in _PEOPLE


def _entity_icon(name: str) -> str:
    """Person or organisation icon for an entity tag."""
    return PERSON_ICON if _is_person(name) else ENTITY_ICON


def _logo_dev_img(domain: str, token: str) -> str:
    src = html.escape(
        f"https://img.logo.dev/{domain}?token={token}&size=48&format=png&retina=true",
        quote=True,
    )
    return f'<img class="sc-logo" src="{src}" alt="" loading="lazy">'


def _company_logo(name: str) -> str:
    """A company's logo from logo.dev when its website is known (see
    COMPANY_DOMAINS), a person icon for a named person, otherwise an initials
    tile."""
    if _is_person(name):
        return f'<span class="sc-logo sc-logo-initials sc-logo-person">{PERSON_ICON}</span>'
    token = _logo_dev_token()
    domain = _COMPANY_DOMAINS.get(match_key(name))
    if token and domain:
        return _logo_dev_img(domain, token)
    return f'<span class="sc-logo sc-logo-initials">{html.escape(_initials(name))}</span>'


def _relevance_ring(score: int) -> str:
    """Donut showing the score as a share of 100, as in the Figma relevance pill:
    a 20% cobalt track with the cobalt arc running clockwise from 12 o'clock."""
    radius = 7.5
    circumference = 2 * 3.141592653589793 * radius
    arc = circumference * max(0, min(score, 100)) / 100
    return (
        '<svg class="sc-ring" width="20" height="20" viewBox="0 0 20 20" aria-hidden="true">'
        f'<circle cx="10" cy="10" r="{radius}" fill="none" stroke="#004FFF" '
        'stroke-opacity="0.2" stroke-width="5"/>'
        f'<circle cx="10" cy="10" r="{radius}" fill="none" stroke="#004FFF" stroke-width="5" '
        f'stroke-dasharray="{arc:.2f} {circumference:.2f}" transform="rotate(-90 10 10)"/>'
        "</svg>"
    )


def render_card(signal: dict, cluster_info: dict[str, tuple[float, int]] | None = None) -> None:
    score = signal["newsworthiness_score"]
    label = score_tier(score)[0]
    now = datetime.now(timezone.utc)

    source = signal["source"]
    source_name = SOURCE_NAMES.get(source, (source.replace("_", " ").title(), ""))[0]
    when = _relative_time(signal["published_at"], now)
    exact = _full_date(signal["published_at"])
    if signal.get("published_at_estimated"):
        # The source gave no usable date, so this is the ingest time standing
        # in — say so rather than presenting a guess as fact.
        when += " (date estimated)"
        exact += " · estimated from when we collected it"

    # Canonical names, so a company appears once however the source spelled it.
    entities = signal_entities(signal)
    tags = [
        f'<span class="sc-tag sc-tag-entity"><span class="sc-tag-icon">{_entity_icon(e)}</span>'
        f"{html.escape(e)}</span>"
        for e in entities[:MAX_ENTITY_TAGS]
    ]
    if len(entities) > MAX_ENTITY_TAGS:
        tags.append(
            f'<span class="sc-tag sc-tag-more">+{len(entities) - MAX_ENTITY_TAGS} more</span>'
        )
    category = signal.get("canonical_category") or signal.get("category")
    if category:
        tags.append(
            f'<span class="sc-tag sc-tag-category"><span class="sc-tag-icon">'
            f"{category_icon(category)}</span>{html.escape(category)}</span>"
        )

    pattern_html = ""
    cluster_id = signal.get("cluster_id")
    if cluster_info and cluster_id in cluster_info:
        heat, count = cluster_info[cluster_id]
        pattern_html = (
            '<div class="pattern-badge">'
            f"Part of a pattern &middot; {count} signals &middot; "
            f"{ACTIVITY_LABELS[heat_tier(heat)[0]]} — see Patterns tab</div>"
        )

    # One line of HTML: indented, blank-line-separated markup risks being read
    # as a Markdown code block.
    st.markdown(
        '<div class="signal-card">'
        '<div class="sc-head">'
        f'<div class="sc-source">{_source_logo(source)}'
        f'<span class="sc-source-name">{html.escape(source_name)}</span>'
        '<span class="sc-sep" aria-hidden="true">|</span>'
        f'<span class="sc-time" tabindex="0">{html.escape(when)}'
        f'<span class="sc-time-tip" role="tooltip">{html.escape(exact)}</span></span></div>'
        f'<div class="sc-relevance">{_relevance_ring(score)}'
        f"<span><b>{RELEVANCE_LABELS[label]}</b> ({score}%)</span></div>"
        "</div>"
        f'<div class="sc-title">{html.escape(signal["title"])}</div>'
        f'<div class="sc-body">{html.escape(signal.get("why_it_matters") or "")}</div>'
        f"{pattern_html}"
        '<div class="sc-foot">'
        f'<div class="sc-tags">{"".join(tags)}</div>'
        f'<a class="sc-link" href="{safe_url(signal["source_url"])}" '
        f'target="_blank" rel="noopener noreferrer">Source {LINK_ICON}</a>'
        "</div></div>",
        unsafe_allow_html=True,
    )


SORT_RECENT = "Most recent"
SORT_SCORE = "Highest score"
DEFAULT_MIN_SCORE = 40
DATE_PRESETS = {"All time": None, "Last 30 days": 30, "Last 7 days": 7}

# Filter state. Sources and categories are one checkbox each, keyed by name
# (default on), so a source or category that appears later starts ticked.
F_SEARCH, F_SORT, F_COMPANIES = "f_search", "f_sort", "f_companies"
F_SCORE, F_PUBLISHED = "f_min_score", "f_published"


def _src_key(source: str) -> str:
    return f"f_src_{source}"


def _cat_key(category: str) -> str:
    return f"f_cat_{category}"


def _set_sort(option: str) -> None:
    # The page script closes the menu once a choice is made: setting the
    # popover's state from Python doesn't close it.
    st.session_state[F_SORT] = option


def _remove_company(name: str) -> None:
    st.session_state[F_COMPANIES] = [c for c in st.session_state.get(F_COMPANIES, []) if c != name]


def _clear_filters(sources: list[str], categories: list[str]) -> None:
    # Every widget is set back to its default value: removing a widget's key
    # leaves its old value showing.
    state = st.session_state
    state[F_SEARCH] = ""
    state[F_COMPANIES] = []
    state[F_SCORE] = DEFAULT_MIN_SCORE
    state[F_PUBLISHED] = "All time"
    for s in sources:
        state[_src_key(s)] = True
    for c in categories:
        state[_cat_key(c)] = True


def _check_row(key: str, label: str, on: bool, on_click, args: tuple,
               *, state_first: bool = False) -> None:
    """A menu row with a cobalt tick when on (styled in inject_css). The key
    gets the state appended (<key>-on), or with state_first inserted after the
    first segment (sectoropt-on-<slug>), for keys ending in free text such as
    a slug that might itself contain "-off"."""
    state = "on" if on else "off"
    if state_first:
        prefix, _, rest = key.partition("-")
        full_key = f"{prefix}-{state}-{rest}"
    else:
        full_key = f"{key}-{state}"
    st.button(
        label,
        key=full_key,
        icon=":material/check:",
        type="tertiary",
        width="stretch",
        on_click=on_click,
        args=args,
    )


def _filter_options(scored: list[dict]) -> dict:
    """What the filters can choose from, derived from the scored signals."""
    # Canonical names, so one option covers every spelling of a company —
    # picking "Entain Holdings (UK) Limited" also matches signals that named
    # it "Entain".
    entity_counts = Counter(e for s in scored for e in signal_entities(s))
    category_counts = Counter(s.get("canonical_category") or "Other" for s in scored)
    return {
        "sources": sorted({s["source"] for s in scored}, key=lambda s: _source_name(s).lower()),
        # Busiest categories first, as on the cards.
        "categories": [c for c, _ in category_counts.most_common()],
        "entity_counts": entity_counts,
        "entities": sorted(entity_counts, key=lambda e: (-entity_counts[e], e.lower())),
        "dates": [datetime.fromisoformat(s["published_at"]).date() for s in scored],
    }


def _criteria(opts: dict) -> dict:
    """The current filter choices, read from session state."""
    state = st.session_state
    return {
        "sources_off": {s for s in opts["sources"] if not state.get(_src_key(s), True)},
        "categories_off": {c for c in opts["categories"] if not state.get(_cat_key(c), True)},
        "companies": [c for c in state.get(F_COMPANIES, []) if c in opts["entity_counts"]],
        "min_score": state.get(F_SCORE, DEFAULT_MIN_SCORE),
        "days": DATE_PRESETS.get(state.get(F_PUBLISHED, "All time")),
        "search": (state.get(F_SEARCH) or "").strip().lower(),
    }


def _filter_signals(scored: list[dict], dates: list, crit: dict) -> list[dict]:
    """Signals matching the criteria, in their incoming (newest-first) order."""
    today = datetime.now(timezone.utc).date()
    start_date = today - timedelta(days=crit["days"]) if crit["days"] is not None else None
    companies = set(crit["companies"])
    out = []
    for signal, pub_date in zip(scored, dates):
        if signal["source"] in crit["sources_off"]:
            continue
        if (signal.get("canonical_category") or "Other") in crit["categories_off"]:
            continue
        if signal["newsworthiness_score"] < crit["min_score"]:
            continue
        if start_date and pub_date < start_date:
            continue
        if companies and not set(signal_entities(signal)) & companies:
            continue
        if crit["search"]:
            # Search both spellings so "Entain" finds signals stored under
            # the full legal name and vice versa.
            haystack = " ".join(
                [
                    signal.get("title", ""),
                    signal.get("why_it_matters") or "",
                    signal.get("category") or "",
                    " ".join(signal.get("entities", [])),
                    " ".join(signal_entities(signal)),
                ]
            ).lower()
            if crit["search"] not in haystack:
                continue
        out.append(signal)
    return out


def _source_name(s: str) -> str:
    return SOURCE_NAMES.get(s, (s.replace("_", " ").title(), ""))[0]


def apply_filters(scored: list[dict]) -> tuple[list[dict], str]:
    """Feed filters in the sidebar, after Ren's Playground frame 2374:1266:
    collapsible sections (bold heading, drop-down arrow) of cobalt
    checkboxes for Sources and Categories, a Minimum score slider, and a
    Company / entity search whose chosen companies list underneath with
    their logos and a ✕. Native widgets throughout, so every control is
    reliable and keyboard-accessible. Only rendered beside the Feed."""
    opts = _filter_options(scored)
    state = st.session_state
    # Defaults go into state before the widgets render, so each widget has
    # one source of truth (its key) and Clear all can reset it.
    state.setdefault(F_SCORE, DEFAULT_MIN_SCORE)
    state.setdefault(F_PUBLISHED, "All time")
    for s in opts["sources"]:
        state.setdefault(_src_key(s), True)
    for c in opts["categories"]:
        state.setdefault(_cat_key(c), True)
    # A chosen company that has left the data would break the widget.
    if F_COMPANIES in state:
        state[F_COMPANIES] = [c for c in state[F_COMPANIES] if c in opts["entity_counts"]]
    crit = _criteria(opts)
    active = bool(
        crit["search"] or crit["companies"] or crit["sources_off"] or crit["categories_off"]
        or crit["min_score"] != DEFAULT_MIN_SCORE or crit["days"] is not None
    )

    def section(title: str, key: str):
        return st.expander(title, expanded=True, key=key)

    with st.sidebar:
        with st.container(key="sb-filters-head", horizontal=True, vertical_alignment="center"):
            st.markdown('<div class="sb-title">Filters</div>', unsafe_allow_html=True)
            # Always rendered, hidden while nothing is set: appearing would
            # otherwise change the row and shift everything below it.
            st.button("Clear all", key="clear-filters", type="tertiary", disabled=not active,
                      on_click=_clear_filters, args=(opts["sources"], opts["categories"]))
        with st.container(key="sb-filters"):
            st.text_input(
                "Search", placeholder="Search signals", label_visibility="collapsed",
                icon=":material/search:", key=F_SEARCH,
            )
            with section("Sources", "sec-sources"):
                for s in opts["sources"]:
                    st.checkbox(_source_name(s), key=_src_key(s))
            with section("Categories", "sec-categories"):
                for c in opts["categories"]:
                    st.checkbox(c, key=_cat_key(c))
            with section("Minimum score", "sec-score"):
                st.slider("Minimum score", 0, 100, key=F_SCORE, label_visibility="collapsed")
            with section("Company / entity", "sec-company"):
                # Native multiselect for live type-ahead and "Select N
                # matches"; its chips are hidden and the choices are listed
                # underneath with logos instead, as in the design.
                st.multiselect(
                    "Company / entity", opts["entities"], key=F_COMPANIES,
                    placeholder="Search by company", label_visibility="collapsed",
                )
                for i, name in enumerate(crit["companies"]):
                    with st.container(key=f"co-row-{i}", horizontal=True,
                                      vertical_alignment="center"):
                        st.markdown(
                            f'<div class="co-row">{_company_logo(name)}'
                            f'<span class="co-name">{html.escape(name)}</span></div>',
                            unsafe_allow_html=True,
                        )
                        st.button("", key=f"co-rm-{i}", icon=":material/close:", type="tertiary",
                                  help=f"Remove {name}", on_click=_remove_company, args=(name,))
            with section("Published", "sec-published"):
                st.radio("Published", list(DATE_PRESETS), key=F_PUBLISHED,
                         label_visibility="collapsed")

    sort_order = state.get(F_SORT, SORT_RECENT)
    filtered = _filter_signals(scored, opts["dates"], crit)
    if sort_order == SORT_SCORE:
        filtered.sort(key=lambda s: s["newsworthiness_score"], reverse=True)
    return filtered, sort_order


def _feed_toolbar(shown: int, total: int, sort_order: str) -> None:
    """The count above the feed. (Sort sits in the tab row; see main.)"""
    with st.container(key="feed-filters", horizontal=True, vertical_alignment="center"):
        st.caption(f"Showing {shown} of {total} scored signals.")


def _sort_control() -> None:
    """Sort for the feed, placed at the right of the tab row."""
    sort_order = st.session_state.get(F_SORT, SORT_RECENT)
    with st.popover(f"Sort by: **{sort_order}**", icon=":material/swap_vert:", key="pop-sort"):
        for option in (SORT_RECENT, SORT_SCORE):
            _check_row(f"sortopt-{option.split()[0].lower()}", option,
                       option == sort_order, _set_sort, (option,))


def group_by_cluster(scored: list[dict]) -> dict[str, list[dict]]:
    grouped = defaultdict(list)
    for s in scored:
        if s.get("cluster_id"):
            grouped[s["cluster_id"]].append(s)
    return grouped


def _build_cluster_info(scored: list[dict]) -> dict[str, tuple[float, int]]:
    return {
        cid: (compute_heat(members), len(members))
        for cid, members in group_by_cluster(scored).items()
    }


def _date_bucket(pub_date, today) -> str:
    delta = (today - pub_date).days
    if delta <= 0:
        return "Today"
    if delta == 1:
        return "Yesterday"
    if delta <= 7:
        return "This week"
    return "Earlier"


def render_feed(signals: list[dict]) -> None:
    scored = [s for s in signals if s.get("newsworthiness_score") is not None]
    scored.sort(key=lambda s: s["published_at"], reverse=True)

    if not scored:
        st.info("No scored signals yet — check back after the next pipeline run.")
        return

    cluster_info = _build_cluster_info(scored)

    filtered, sort_order = apply_filters(scored)
    _feed_toolbar(len(filtered), len(scored), sort_order)

    if not filtered:
        _empty_block(
            "No signals match your filters.",
            "Try widening them, or use Clear all in the sidebar to start again.",
        )
        return

    if sort_order != SORT_RECENT:
        for signal in filtered:
            render_card(signal, cluster_info)
        return

    # Date-bucketed only for the newest-first view — bucketing would
    # scramble a highest-score-first ordering by scattering same-score
    # items across date sections.
    today = datetime.now(timezone.utc).date()
    buckets: dict[str, list[dict]] = defaultdict(list)
    for signal in filtered:
        pub_date = datetime.fromisoformat(signal["published_at"]).date()
        buckets[_date_bucket(pub_date, today)].append(signal)

    for bucket in ["Today", "Yesterday", "This week", "Earlier"]:
        # Today always shows, so a quiet morning reads as "nothing yet", not
        # as a feed that starts at yesterday for no clear reason.
        if not buckets[bucket] and bucket != "Today":
            continue
        st.markdown(f'<div class="section-label">{bucket}</div>', unsafe_allow_html=True)
        if not buckets[bucket]:
            today_unfiltered = any(
                datetime.fromisoformat(s["published_at"]).date() >= today for s in scored
            )
            if today_unfiltered:
                _empty_block(
                    "Nothing from today matches your filters.",
                    "Try widening them, or catch up on earlier signals below.",
                )
            else:
                _empty_block(
                    "Nothing new yet today.",
                    "We check our sources throughout the day, so new signals will "
                    "appear here as they come in.",
                )
        for signal in buckets[bucket]:
            render_card(signal, cluster_info)


def _empty_block(title: str, body: str) -> None:
    """A friendly grey message block for an empty section or feed."""
    st.markdown(
        f'<div class="empty-block"><span class="empty-icon" aria-hidden="true">inbox</span>'
        f'<div><div class="empty-title">{html.escape(title)}</div>'
        f'<div class="empty-body">{html.escape(body)}</div></div></div>',
        unsafe_allow_html=True,
    )


def _sector_state_block(title: str, body: str) -> None:
    """The block shown instead of the tabs when a sector has nothing to show."""
    with st.container(key="sector-state"):
        _empty_block(title, body)


def _cluster_verdict(members: list[dict]) -> dict:
    """Claude's read of the cluster, carried on every member."""
    return {
        "summary": next(
            (m.get("cluster_summary") for m in members if m.get("cluster_summary")),
            None,
        ),
        "pattern_type": next(
            (m.get("cluster_pattern_type") for m in members
             if m.get("cluster_pattern_type")),
            None,
        ),
        "significance": next(
            (m.get("cluster_significance") for m in members
             if m.get("cluster_significance") is not None),
            None,
        ),
        # Only treat a cluster as rejected if the model actually said so;
        # clusters summarised before this judgement existed have no opinion.
        "coherent": not any(m.get("cluster_coherent") is False for m in members),
    }


# Heat is an unbounded score that means nothing on its own, so readers only ever
# see its tier, as a word. The ring repeats the tier in steps, never quite
# closed, since a full ring reads as an empty circle.
ACTIVITY_LABELS = {"High": "Very active", "Medium": "Active", "Low": "Quiet"}
_ACTIVITY_RING = {"High": 90, "Medium": 60, "Low": 30}

# Only the unusual pattern types earn a tag; "developing story" is the default
# for most clusters, so labelling it tells the reader nothing.
NOTABLE_PATTERN_TYPES = {"escalation": "Escalating", "wave": "Sector-wide"}

# How many co-named companies a pattern or theme card lists before "+N more".
MAX_COMPANY_TAGS = 3


def _activity_pill(tier: str) -> str:
    return (
        f'<div class="sc-relevance">{_relevance_ring(_ACTIVITY_RING[tier])}'
        f"<span><b>{ACTIVITY_LABELS[tier]}</b></span></div>"
    )


def _date_span(members: list[dict]) -> str:
    dates = sorted(datetime.fromisoformat(m["published_at"]).date() for m in members)
    first, last = dates[0], dates[-1]
    if first == last:
        return f"{last.day} {last:%b}"
    return f"{first.day} {first:%b} – {last.day} {last:%b}"


SPARK_WEEKS = 13  # weekly buckets across the ~90-day clustering window
SPARK_HEIGHT = 56  # px; the line's peak sits a little under the top

# Shared y-axis tops: even, so the midline label is a whole number too.
_NICE_SCALES = (2, 4, 6, 8, 10, 12, 16, 20, 30, 40, 50, 60, 80, 100)


def _nice_scale(peak: int) -> int:
    """The smallest clean axis top at or above a tab's busiest week."""
    return next((n for n in _NICE_SCALES if n >= peak), -(-peak // 20) * 20)


def _weekly_counts(members: list[dict], now: datetime) -> list[int]:
    """Signals per week, oldest first; the last bucket is the past 7 days."""
    counts = [0] * SPARK_WEEKS
    for m in members:
        dt = datetime.fromisoformat(m["published_at"])
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        weeks_ago = int((now - dt).total_seconds() // (7 * 86400))
        if 0 <= weeks_ago < SPARK_WEEKS:
            counts[SPARK_WEEKS - 1 - weeks_ago] += 1
    return counts


def _week_index(signal: dict, now: datetime) -> int | None:
    """The signal's column on a sparkline (oldest week 0), or None if it's
    older than the sparkline reaches. Same bucketing as _weekly_counts."""
    dt = datetime.fromisoformat(signal["published_at"])
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    weeks_ago = int((now - dt).total_seconds() // (7 * 86400))
    return SPARK_WEEKS - 1 - weeks_ago if 0 <= weeks_ago < SPARK_WEEKS else None


def _signal_rows_html(members: list[dict], now: datetime, group_id: str = "") -> str:
    """The preview pane's signals as a quiet list, newest first: the date on
    the left, then the title, a two-line summary and one grey line of source,
    category and relevance. Hovering a row lifts it as a white tile and lights
    its week on the sparkline (see _RESIZE_SCRIPT). Clicking it opens it in
    place, with the full summary, the companies and people named, the exact
    date and the source link; opening another closes it (<details name=…>),
    all in the browser with no rerun."""
    rows = []
    group = html.escape(f"sp-{group_id}", quote=True)
    for m in sorted(members, key=lambda m: m["published_at"], reverse=True):
        dt = datetime.fromisoformat(m["published_at"])
        date = f"{dt.day} {dt:%b}" + (f" {dt:%Y}" if dt.year != now.year else "")
        exact = _full_date(m["published_at"])
        if m.get("published_at_estimated"):
            date, exact = f"~{date}", exact + " · estimated from when we collected it"
        week = _week_index(m, now)
        week_attr = f' data-week="{week}"' if week is not None else ""
        meta = [f'<span class="sp-src">{_source_logo(m["source"])}'
                f'{html.escape(_source_name(m["source"]))}</span>']
        category = m.get("canonical_category") or m.get("category")
        if category:
            meta.append(html.escape(category))
        score = m.get("newsworthiness_score")
        if score is not None:
            meta.append(f'<span class="sp-rel" title="{score}% relevant">'
                        f'{_relevance_ring(score)}{score}%</span>')
        entities = signal_entities(m)
        tags = "".join(
            f'<span class="sc-tag sc-tag-entity"><span class="sc-tag-icon">{_entity_icon(e)}</span>'
            f"{html.escape(e)}</span>"
            for e in entities
        )
        more = (
            '<div class="sp-more">'
            + (f'<div class="sp-tags">{tags}</div>' if tags else "")
            + f'<div class="sp-when">{html.escape(exact)}</div>'
            f'<a class="sp-open" href="{safe_url(m["source_url"])}" target="_blank" '
            f'rel="noopener noreferrer">Open source {LINK_ICON}</a>'
            "</div>"
        )
        rows.append(
            f'<details class="sp-item" name="{group}"{week_attr}>'
            '<summary class="sp-row">'
            f'<time class="sp-date" title="{html.escape(exact, quote=True)}">{html.escape(date)}</time>'
            '<span class="sp-main">'
            f'<span class="sp-title">{html.escape(m["title"])}</span>'
            + (f'<span class="sp-body">{html.escape(m["why_it_matters"])}</span>'
               if m.get("why_it_matters") else "")
            + f'<span class="sp-meta">{'<span class="sp-dot">·</span>'.join(meta)}</span>'
            "</span></summary>"
            f"{more}</details>"
        )
    # Plain elements with list roles, not <ol>/<li>: Streamlit's Markdown
    # styles give list items margins and an indent that broke the rail.
    return f'<div class="sp-list" role="list">{"".join(rows)}</div>'


def _week_range(start: datetime) -> str:
    """'18–24 Aug 2026', or '28 Jul – 3 Aug 2026' across a month boundary."""
    end = start + timedelta(days=6)
    if start.month == end.month:
        return f"{start.day}–{end.day} {end:%b %Y}"
    if start.year == end.year:
        return f"{start.day} {start:%b} – {end.day} {end:%b %Y}"
    return f"{start.day} {start:%b %Y} – {end.day} {end:%b %Y}"


def _timeline(members: list[dict], now: datetime, scale: int) -> str:
    """Sparkline of signals per week across the clustering window, today at the
    right: a 2px line over a 10% wash, an end-dot on this week. Shows at a
    glance whether a pattern is a burst this week or a slow build over months.

    Every card on a tab shares one y-axis (`scale`, the tab's busiest week,
    marked by a faint gridline), so heights compare across cards. The axis is
    square-root: counts are heavily skewed (on Themes one wave peaks at 36 a
    week while most peak at 2-3), and on a linear axis a week of 2 drew at 5%
    height, indistinguishable from the baseline. Square root keeps the order
    and the outlier tallest while small counts stay readable. No axis numbers:
    the hover tooltip gives exact counts.

    Two colours, no blend: segments grey where both weeks are empty, cobalt
    wherever a week has signals.

    Hovering snaps to the nearest week: a dot on the line, a faint guide and a
    tooltip with the week and its count. Pure CSS, so it's instant."""
    counts = _weekly_counts(members, now)
    top = 4  # headroom so the line's cap and the end-dot aren't clipped
    step = 100 / (SPARK_WEEKS - 1)

    def y(c: float) -> float:
        return SPARK_HEIGHT - (min(c, scale) / scale) ** 0.5 * (SPARK_HEIGHT - top)

    points = [(i * step, y(c)) for i, c in enumerate(counts)]

    def path(pts: list[tuple[float, float]]) -> str:
        return "M" + " L".join(f"{x:.2f},{yy:.2f}" for x, yy in pts)

    # Runs of consecutive segments sharing a state, each drawn as one path.
    runs: list[tuple[bool, list[tuple[float, float]]]] = []
    for i in range(SPARK_WEEKS - 1):
        active = counts[i] > 0 or counts[i + 1] > 0
        if runs and runs[-1][0] == active:
            runs[-1][1].append(points[i + 1])
        else:
            runs.append((active, [points[i], points[i + 1]]))
    # Grey first so cobalt sits on top where the two meet.
    lines = "".join(
        f'<path class="{"tl-line" if active else "tl-line tl-line-quiet"}" d="{path(pts)}"/>'
        for active, pts in sorted(runs, key=lambda r: r[0])
    )
    area = f"{path(points)} L100,{SPARK_HEIGHT} L0,{SPARK_HEIGHT} Z"

    def dot_class(c: int) -> str:
        return "" if c > 0 else " tl-quiet"

    week_starts = [now - timedelta(days=7 * (SPARK_WEEKS - i)) for i in range(SPARK_WEEKS)]
    columns = []
    for i, ((x, yy), ws, c) in enumerate(zip(points, week_starts, counts)):
        # Each week owns the band halfway to its neighbours; the dot, guide and
        # tooltip sit at the week's point within that band.
        x0, x1 = max(0.0, x - step / 2), min(100.0, x + step / 2)
        at = (x - x0) / (x1 - x0) * 100
        bottom = (SPARK_HEIGHT - yy) / SPARK_HEIGHT * 100
        edge = " tl-tip-start" if i < 2 else " tl-tip-end" if i > SPARK_WEEKS - 3 else ""
        columns.append(
            f'<div class="tl-col" data-week="{i}" style="left:{x0:.2f}%;width:{x1 - x0:.2f}%">'
            f'<span class="tl-guide" style="left:{at:.1f}%"></span>'
            f'<span class="tl-hdot{dot_class(c)}" style="left:{at:.1f}%;bottom:{bottom:.1f}%"></span>'
            f'<span class="tl-tip{edge}" style="left:{at:.1f}%;bottom:calc({bottom:.1f}% + 14px)">'
            f"<span>{_week_range(ws)}</span>"
            f"<b>{c} signal{'s' if c != 1 else ''}</b></span>"
            "</div>"
        )

    peak_week = week_starts[counts.index(max(counts))]
    label = (
        f"Signals per week over the last {SPARK_WEEKS} weeks: "
        f"{', '.join(map(str, counts))}. Peak {max(counts)} in the week of "
        f"{peak_week.day} {peak_week:%b}; {counts[-1]} this week."
    )
    end_bottom = (SPARK_HEIGHT - points[-1][1]) / SPARK_HEIGHT * 100
    start = week_starts[0]
    return (
        f'<div class="tl" role="img" aria-label="{html.escape(label, quote=True)}">'
        '<div class="tl-track">'
        f'<svg class="tl-svg" viewBox="0 0 100 {SPARK_HEIGHT}" preserveAspectRatio="none" '
        'aria-hidden="true">'
        f'<line class="tl-grid" x1="0" x2="100" y1="{y(scale):.2f}" y2="{y(scale):.2f}"/>'
        f'<path class="tl-area" d="{area}"/>'
        f"{lines}"
        "</svg>"
        f'<span class="tl-dot{dot_class(counts[-1])}" style="bottom:{end_bottom:.1f}%"></span>'
        f'<div class="tl-cols">{"".join(columns)}</div>'
        "</div>"
        f'<div class="tl-axis"><span>{start.day} {start:%b}</span><span>This week</span></div>'
        "</div>"
    )


def _company_tags(companies: list[str], limit: int | None = MAX_COMPANY_TAGS) -> list[str]:
    shown = companies if limit is None else companies[:limit]
    tags = [
        f'<span class="sc-tag sc-tag-entity"><span class="sc-tag-icon">{_entity_icon(c)}</span>'
        f"{html.escape(c)}</span>"
        for c in shown
    ]
    if len(companies) > len(shown):
        tags.append(f'<span class="sc-tag sc-tag-more">+{len(companies) - len(shown)} more</span>')
    return tags


def _flag_tag(text: str, icon_name: str | None, accent: bool) -> str:
    style = "sc-tag-category" if accent else "sc-tag-entity"
    icon_html = f'<span class="sc-tag-icon">{icon(icon_name)}</span>' if icon_name else ""
    pad = "" if icon_name else " sc-tag-plain"
    return f'<span class="sc-tag {style}{pad}">{icon_html}{html.escape(text)}</span>'


def _initials(name: str) -> str:
    words = [w for w in name.replace("(", " ").split() if w[:1].isalnum()]
    return "".join(w[0] for w in words[:2]).upper() or "?"


@dataclass
class Group:
    """A pattern or a theme, as both the list card and the preview pane show it."""

    id: str
    key: str
    tile_html: str
    title: str
    tier: str
    summary: str | None
    meta: str
    members: list[dict]
    flags: list[str]
    companies: list[str]
    key_points: list[str] = field(default_factory=list)
    scale: int = 2  # the tab's shared sparkline y-axis top; set in _render_groups


def _group_html(group: Group, now: datetime, full: bool) -> str:
    """The card body. The list card trims the company tags; the preview pane
    shows everything, including a theme's key points."""
    points = ""
    if full and group.key_points:
        items = "".join(f"<li>{html.escape(str(p))}</li>" for p in group.key_points)
        points = f'<ul class="gc-points">{items}</ul>'
    tags = group.flags + _company_tags(group.companies, None if full else MAX_COMPANY_TAGS)
    return (
        f'<div class="group-card{" group-card-full" if full else ""}">'
        '<div class="sc-head">'
        f'<div class="sc-source">{group.tile_html}'
        f'<span class="gc-title">{html.escape(group.title)}</span></div>'
        f"{_activity_pill(group.tier)}"
        "</div>"
        + (f'<div class="sc-body">{html.escape(group.summary)}</div>' if group.summary else "")
        + points
        + f'<div class="gc-meta">{html.escape(group.meta)}</div>'
        f"{_timeline(group.members, now, group.scale)}"
        + (f'<div class="sc-tags gc-tags">{"".join(tags)}</div>' if tags else "")
        + "</div>"
    )


def _group_card(group: Group, now: datetime, selected: bool, state_key: str) -> None:
    """A pattern or theme in the list. Clicking it fills the preview pane."""
    # The key never changes, so selecting a card updates its button in place
    # instead of remounting the card. CSS styles the selected card from the
    # button's disabled state.
    with st.container(key=group.key):
        st.markdown(_group_html(group, now, full=False), unsafe_allow_html=True)
        # Stretched invisibly over the whole card (see inject_css), so a click
        # anywhere on it selects it. The label is for screen readers.
        st.button(
            f"{group.title}, showing in preview" if selected else f"Preview {group.title}",
            key=f"view-{group.key}",
            type="tertiary",
            disabled=selected,
            # Stretch, not the default "content": a content-width button only
            # covered a label-length strip at the card's left edge, so clicks
            # on the rest of the card did nothing.
            width="stretch",
            on_click=st.session_state.__setitem__,
            args=(state_key, group.id),
        )


# Lets the reader drag the preview pane's left edge, forwards clicks on a list
# card's sparkline to the card, sizes the Sort menu to its button and closes
# it once an option is chosen. Injected once per page
# with st.html (scripts allowed) and installs delegated listeners, so it
# survives Streamlit re-rendering the pane. Sets --preview-width, which sizes
# both the pane and the room the main column leaves for it, and remembers the
# width in localStorage. Re-running replaces the previous run's handlers rather
# than stacking them.
_RESIZE_SCRIPT = """
<script>
(() => {
  const win = window;
  const doc = document;
  const root = doc.documentElement;
  const KEY = "sector-signal-preview-width";
  const clamp = (px) => Math.max(320, Math.min(px, win.innerWidth * 0.7));
  const apply = (px) => root.style.setProperty("--preview-width", clamp(px) + "px");
  const current = () => doc.querySelector('[class*="st-key-signals-panel-"]')
    .getBoundingClientRect().width;
  const save = () => { try { win.localStorage.setItem(KEY, current()); } catch (e) {} };
  try { const saved = parseFloat(win.localStorage.getItem(KEY)); if (saved) apply(saved); } catch (e) {}

  let dragging = false;
  const handlers = {
    pointerdown: (e) => {
      if (!e.target.closest || !e.target.closest(".sp-resize")) return;
      dragging = true;
      doc.body.classList.add("sp-resizing");
      e.preventDefault();
    },
    pointermove: (e) => { if (dragging) apply(win.innerWidth - e.clientX); },
    pointerup: () => {
      if (!dragging) return;
      dragging = false;
      doc.body.classList.remove("sp-resizing");
      save();
    },
    click: (e) => {
      // Size the Sort menu to its button.
      const sortBtn = e.target.closest && e.target.closest('.st-key-pop-sort [data-testid="stPopoverButton"]');
      if (sortBtn) root.style.setProperty("--sort-menu-w", sortBtn.getBoundingClientRect().width + "px");
      // Close the Sort menu once an option is chosen.
      if (e.target.closest && e.target.closest('[class*="st-key-sortopt-"] button')) {
        setTimeout(() => {
          const btn = doc.querySelector('.st-key-pop-sort [data-testid="stPopoverButton"]');
          if (btn && btn.getAttribute("aria-expanded") === "true") btn.click();
        }, 0);
      }
      // Close the sector menu once a sector is chosen.
      if (e.target.closest && e.target.closest('[class*="st-key-sectoropt-"] button')) {
        setTimeout(() => {
          const btn = doc.querySelector('.st-key-pop-sector [data-testid="stPopoverButton"]');
          if (btn && btn.getAttribute("aria-expanded") === "true") btn.click();
        }, 0);
      }
      // The sparkline's hover layer sits above a card's click overlay; a click
      // on it still means "select this card".
      const col = e.target.closest && e.target.closest(".tl-col");
      const card = col && col.closest('[class*="st-key-pcard-"], [class*="st-key-tcard-"]');
      const btn = card && card.querySelector("button");
      if (btn && !btn.disabled) btn.click();
    },
    // Hovering a signal in the preview pane lights up its week on the pane's
    // sparkline: the same dot, guide and tooltip as hovering the line itself.
    mouseover: (e) => {
      const card = e.target.closest && e.target.closest('[class*="st-key-signals-panel-"] .sp-item[data-week]');
      const pane = card && card.closest('[class*="st-key-signals-panel-"]');
      doc.querySelectorAll(".tl-col.tl-on").forEach((c) => c.classList.remove("tl-on"));
      if (!pane) return;
      const col = pane.querySelector(`.tl-col[data-week="${card.dataset.week}"]`);
      if (col) col.classList.add("tl-on");
    },
    keydown: (e) => {
      if (!e.target.closest || !e.target.closest(".sp-resize")) return;
      const step = { ArrowLeft: 32, ArrowRight: -32 }[e.key];
      if (!step) return;
      apply(current() + step);
      save();
      e.preventDefault();
    },
  };
  for (const [type, fn] of Object.entries(win.__paPreviewResize || {})) {
    doc.removeEventListener(type, fn);
  }
  for (const [type, fn] of Object.entries(handlers)) doc.addEventListener(type, fn);
  win.__paPreviewResize = handlers;
})();
</script>
"""


def _preview_pane(key: str, group: Group, now: datetime, state_key: str) -> None:
    """The selected pattern or theme in full, then its source signals, in a
    pane fixed to the window's right edge (see inject_css), apart from the
    title and the list. Only the active tab is in the DOM, so the pane appears
    on Patterns and Themes and nowhere else. On phones it's a sheet along the
    bottom of the screen."""
    # Same key and same place in the page for every selection, so switching
    # cards updates the pane's contents in place rather than rebuilding it.
    with st.container(key=key):
        st.markdown(
            '<div class="sp-resize" role="separator" aria-orientation="vertical" '
            'aria-label="Resize preview" tabindex="0"></div>',
            unsafe_allow_html=True,
        )
        # The summary and sparkline stay pinned while the signals scroll under
        # them, with the close button in their corner.
        with st.container(key=f"sp-head-{state_key}"):
            st.button("", key=f"sp-close-{state_key}", icon=":material/close:", type="tertiary",
                      help="Close preview", on_click=st.session_state.pop, args=(state_key, None))
            st.markdown(_group_html(group, now, full=True), unsafe_allow_html=True)
        st.markdown(
            f'<div class="sp-section">Signals ({len(group.members)})</div>'
            f"{_signal_rows_html(group.members, now, group.id)}",
            unsafe_allow_html=True,
        )


def _render_groups(groups: list[Group], state_key: str, pane_key: str) -> None:
    """The list of cards, plus the preview of the selected one. Nothing is
    selected when the tab opens, so the pane only appears once a card is
    clicked; it closes again with its × or when the choice drops out of view."""
    now = datetime.now(timezone.utc)
    # One y-axis for every sparkline on the tab, so heights compare across cards.
    scale = _nice_scale(max(max(_weekly_counts(g.members, now)) for g in groups))
    for group in groups:
        group.scale = scale
    selected = st.session_state.get(state_key)
    current = next((g for g in groups if g.id == selected), None)
    if current is not None:
        _preview_pane(pane_key, current, now, state_key)
    for group in groups:
        _group_card(group, now, current is not None and group.id == selected, state_key)


def render_patterns(signals: list[dict], sector) -> None:
    scored = [s for s in signals if s.get("newsworthiness_score") is not None]
    grouped = group_by_cluster(scored)

    if not grouped:
        st.info(
            "No emerging patterns yet — a pattern needs two or more signals "
            "naming the same company within the last 90 days."
        )
        return

    # Clusters are formed on a shared company name, so some are coincidence.
    # Claude is asked to say which; those are dropped outright — a cluster the
    # model has called unrelated is noise the reader shouldn't have to sift.
    coherent = [m for m in grouped.values() if _cluster_verdict(m)["coherent"]]
    clusters = sorted(
        ((compute_heat(members), members) for members in coherent),
        key=lambda pair: pair[0],
        reverse=True,
    )

    show_quiet = st.toggle(
        "Show quieter patterns",
        help="Includes quiet patterns and routine runs of filings.",
    )
    if not show_quiet:
        clusters = [
            (heat, members)
            for heat, members in clusters
            if heat_tier(heat)[0] != "Low"
            and _cluster_verdict(members)["pattern_type"] != "routine"
        ]
    st.caption(
        f"All {len(clusters)} patterns."
        if show_quiet
        else f"{len(clusters)} active patterns of {len(coherent)}."
    )

    if not clusters:
        st.info("No active patterns right now — switch on quieter patterns to see the rest.")
        return

    groups = []
    for heat, members in clusters:
        verdict = _cluster_verdict(members)
        cluster_id = members[0]["cluster_id"]

        # Most-mentioned company rather than alphabetically-first, so a
        # multi-company cluster is named after whoever it's actually about.
        # The rest become tags instead of a "+3 more" that hides them.
        counts = Counter(e for m in members for e in signal_entities(m))
        companies = [n for n, _ in counts.most_common() if not is_excluded(n, sector)]
        primary = companies[0] if companies else "Unnamed pattern"

        sources = {m["source"] for m in members}
        flags = []
        pattern_type = verdict["pattern_type"]
        if pattern_type in NOTABLE_PATTERN_TYPES:
            flags.append(_flag_tag(NOTABLE_PATTERN_TYPES[pattern_type], "trending_up", True))
        elif pattern_type == "routine":
            flags.append(_flag_tag("Routine filings", None, False))

        groups.append(
            Group(
                id=cluster_id,
                key=f"pcard-{cluster_id}",
                tile_html=_company_logo(primary),
                title=primary,
                tier=heat_tier(heat)[0],
                summary=verdict["summary"],
                meta=(
                    f"{len(members)} signals · {len(sources)} "
                    f"{'source' if len(sources) == 1 else 'sources'} · {_date_span(members)}"
                ),
                members=members,
                flags=flags,
                companies=companies[1:],
            )
        )
    _render_groups(groups, "pattern_selected", "signals-panel-patterns")


_DIRECTION_TAGS = {
    "building": ("Building", "trending_up", True),
    "steady": ("Steady", "trending_flat", False),
    "easing": ("Easing", "trending_down", False),
}


def render_themes(signals: list[dict], sector) -> None:
    """Patterns across companies rather than about one. A run of small
    operators being wound up is a sector story that company clustering can
    never see, because every signal names someone different."""
    grouped = defaultdict(list)
    for s in signals:
        if s.get("theme_id"):
            grouped[s["theme_id"]].append(s)

    if not grouped:
        st.info(
            "No sector-wide themes yet — a theme needs signals of the same "
            f"kind naming at least {MIN_THEME_COMPANIES} different companies "
            "within the last 90 days."
        )
        return

    st.caption(
        "Themes group signals by what happened rather than who it happened "
        "to, so a run of similar events across different companies reads as "
        "one pattern."
    )

    themes = sorted(
        ((compute_theme_heat(members, sector=sector), theme, members)
         for theme, members in grouped.items()),
        reverse=True,
        key=lambda t: t[0],
    )

    groups = []
    for heat, theme, members in themes:
        counts = Counter(e for m in members for e in signal_entities(m) if not is_excluded(e, sector))
        companies = [n for n, _ in counts.most_common()]
        company_word = "company" if len(companies) == 1 else "companies"

        def first(field_name: str, default=None):
            return next((m.get(field_name) for m in members if m.get(field_name)), default)

        # Whether the wave is building or fading is the story, so it leads the
        # tags; the timeline shows the same thing as shape.
        direction = first("theme_direction")
        flags = [_flag_tag(*_DIRECTION_TAGS[direction])] if direction in _DIRECTION_TAGS else []

        groups.append(
            Group(
                id=theme,
                key=f"tcard-{theme}",
                tile_html=f'<span class="sc-logo gc-theme-tile">{category_icon(theme)}</span>',
                title=theme,
                tier=theme_heat_tier(heat)[0],
                summary=first("theme_summary"),
                meta=(
                    f"{len(members)} signals · {len(companies)} {company_word} · "
                    f"{_date_span(members)}"
                ),
                members=members,
                flags=flags,
                companies=companies,
                key_points=first("theme_key_points", []),
            )
        )
    _render_groups(groups, "theme_selected", "signals-panel-themes")


def _humanise_age(delta_seconds: float) -> str:
    minutes = int(delta_seconds // 60)
    if minutes < 60:
        return f"{max(minutes, 0)} min ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    days = hours // 24
    return f"{days} day{'s' if days != 1 else ''} ago"


def render_health_strip(status: dict | None, reserve: bool = False) -> None:
    """Freshness and source health at a glance. Without this a scraper whose
    page layout moved just goes quiet, and the feed looks like a slow news
    week rather than a broken collector.

    With reserve, a missing or unreadable status still takes the strip's
    room (see _reserve_health_strip), so switching sectors doesn't move the
    page."""
    finished = None
    if status:
        try:
            finished = datetime.fromisoformat(status["finished_at"])
        except (KeyError, ValueError, TypeError):
            pass
    if finished is None:
        if reserve:
            _reserve_health_strip()
        return

    age = (datetime.now(timezone.utc) - finished).total_seconds()
    healthy = status.get("healthy_sources", 0)
    total = status.get("total_sources", 0)

    if "error" in status:
        # A failed run writes no source counts; don't read that as healthy.
        st.markdown(
            f'<div class="health-strip health-bad">Last update failed · '
            f"{_humanise_age(age)}</div>",
            unsafe_allow_html=True,
        )
        return

    if age > 12 * 3600:
        css, detail = "health-bad", "pipeline may have stopped running"
    elif healthy < total:
        css, detail = "health-warn", f"{total - healthy} source(s) returned nothing"
    else:
        css, detail = "health-ok", "all sources healthy"

    unscored = status.get("unscored", 0)
    if unscored:
        detail += f" · {unscored} awaiting scoring"

    st.markdown(
        f'<div class="health-strip {css}">Updated {_humanise_age(age)} · '
        f"{healthy}/{total} sources · {html.escape(detail)}</div>",
        unsafe_allow_html=True,
    )

    failing = [
        name
        for name, info in (status.get("sources") or {}).items()
        if not info.get("ok")
    ]
    if failing:
        with st.expander("Which sources returned nothing?"):
            st.write(", ".join(sorted(failing)))


def _reserve_health_strip() -> None:
    """An invisible strip (two lines, as a strip with a detail usually wraps
    to) and expander: the same boxes as a real status, so the bottom-aligned
    header sits where it does for a sector that has one."""
    with st.container(key="health-reserve"):
        st.markdown('<div class="health-strip"><span>&nbsp;<br>&nbsp;</span></div>',
                    unsafe_allow_html=True)
        st.expander("Which sources returned nothing?")


def _fetch_user_watchlist() -> tuple[dict, str | None]:
    gh = github.GitHub(st.secrets["GITHUB_TOKEN"])
    found = gh.get_file(data.user_watchlist_path(_current_slug()))
    if found is None:
        return {"operators": []}, None
    content, sha = found
    watchlist = yaml.safe_load(content) or {"operators": []}
    return watchlist, sha


def add_operator_to_watchlist(
    name: str, company_number: str, aliases: str, notes: str
) -> None:
    watchlist, sha = _fetch_user_watchlist()
    watchlist.setdefault("operators", []).append(
        {
            "name": name,
            "company_number": company_number or None,
            "aliases": [a.strip() for a in aliases.split(",") if a.strip()],
            "notes": notes,
        }
    )
    new_content = yaml.safe_dump(watchlist, sort_keys=False, allow_unicode=True)
    gh = github.GitHub(st.secrets["GITHUB_TOKEN"])
    gh.put_file(
        data.user_watchlist_path(_current_slug()),
        new_content,
        f"Add {name} to watchlist via dashboard",
        sha=sha,
    )


def _watchlist_configured() -> bool:
    try:
        return bool(st.secrets.get("GITHUB_TOKEN"))
    except Exception:
        return False


# Watchlist dialog steps: an illustrated intro, the form, then confirmation.
WL_STEP = "wl_step"

# On-brand illustration for the intro: flat and square in the PA language
# (no shadows, cobalt and ink, newsprint and light-blue accents). A watchlist
# card with company rows, the new row marked with the selected-card cobalt
# edge, a "+" badge and a sparkline.
_WATCHLIST_ILLUSTRATION = """
<svg viewBox="0 0 360 176" width="100%" role="img" aria-label="A watchlist with a new company being added" xmlns="http://www.w3.org/2000/svg">
  <rect x="0" y="0" width="360" height="176" fill="#e5e3d3"/>
  <rect x="24" y="118" width="54" height="34" fill="#8DDBFF"/>
  <rect x="300" y="24" width="36" height="36" fill="#000"/>
  <path d="M308 50 L314 42 L320 46 L328 34" fill="none" stroke="#fff" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/>
  <rect x="88" y="22" width="192" height="134" fill="#fff"/>
  <rect x="88" y="22" width="192" height="24" fill="#000"/>
  <rect x="100" y="31" width="52" height="6" fill="#fff"/>
  <rect x="100" y="58" width="18" height="18" fill="#000"/>
  <rect x="126" y="60" width="78" height="6" fill="#000"/>
  <rect x="126" y="70" width="52" height="4" fill="#dedad9"/>
  <polyline points="224,72 236,64 246,68 258,60 268,62" fill="none" stroke="#004FFF" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>
  <rect x="100" y="86" width="18" height="18" fill="#8DDBFF"/>
  <rect x="126" y="88" width="64" height="6" fill="#000"/>
  <rect x="126" y="98" width="88" height="4" fill="#dedad9"/>
  <polyline points="224,100 236,98 246,96 258,99 268,92" fill="none" stroke="#8a8a8a" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>
  <rect x="88" y="114" width="192" height="32" fill="#f2f6ff"/>
  <rect x="88" y="114" width="4" height="32" fill="#004FFF"/>
  <rect x="100" y="121" width="18" height="18" fill="#004FFF"/>
  <rect x="126" y="123" width="72" height="6" fill="#004FFF"/>
  <rect x="126" y="133" width="44" height="4" fill="#8DDBFF"/>
  <rect x="256" y="104" width="36" height="36" fill="#004FFF"/>
  <rect x="272" y="112" width="4" height="20" fill="#fff"/>
  <rect x="264" y="120" width="20" height="4" fill="#fff"/>
</svg>
"""


def _wl_go(step: str) -> None:
    st.session_state[WL_STEP] = step


def _open_watchlist() -> None:
    st.session_state[WL_STEP] = "intro"
    st.session_state.pop("wl_error", None)


_WL_FIELDS = ("wl_name", "wl_number", "wl_aliases", "wl_notes")


def _submit_watchlist() -> None:
    """Form submit callback: validate, save, then move to the confirmation
    (or keep the form with an error). Steps change in callbacks, so the
    dialog never needs an explicit rerun."""
    state = st.session_state
    name = (state.get("wl_name") or "").strip()
    if not name:
        state["wl_error"] = "Please add the company's name."
        return
    try:
        add_operator_to_watchlist(
            name,
            (state.get("wl_number") or "").strip(),
            state.get("wl_aliases") or "",
            (state.get("wl_notes") or "").strip(),
        )
    except Exception:
        state["wl_error"] = "Something went wrong and we couldn't add it. Please try again, or let the team know."
        return
    state["wl_added"] = name
    state.pop("wl_error", None)
    for key in _WL_FIELDS:
        state[key] = ""
    state[WL_STEP] = "done"


@st.dialog("Add a company to the watchlist", width="medium")
def _watchlist_dialog() -> None:
    """Three steps: an illustrated intro, the form, then confirmation. The
    form adds the company to the current sector's user file
    (config/sectors/<slug>.user.yaml) via GitHub; the pipeline picks it up on
    its next run."""
    step = st.session_state.get(WL_STEP, "intro")

    if step == "intro":
        st.markdown(
            f'<div class="wl-illustration">{_WATCHLIST_ILLUSTRATION}</div>'
            '<div class="wl-headline">Keep an eye on a company</div>'
            '<p class="wl-copy">Add a company you care about and we\'ll keep watch for news '
            "about it. New signals will show up in your feed as they happen.</p>"
            f'<p class="wl-copy wl-muted">It\'s added to {html.escape(_current_sector_name())}. '
            "All you need is its name. If you know its Companies House number, add that "
            "too for fuller coverage.</p>",
            unsafe_allow_html=True,
        )
        st.button("Get started", key="wl-start", type="primary", width="stretch",
                  on_click=_wl_go, args=("form",))
        return

    if step == "done":
        added = st.session_state.get("wl_added", "the company")
        st.markdown(
            '<div class="wl-headline">You\'re all set</div>'
            f'<p class="wl-copy">We\'ll start watching <b>{html.escape(added)}</b> shortly. '
            "New signals will appear in your feed as they come in.</p>",
            unsafe_allow_html=True,
        )
        if st.button("Done", key="watchlist-done", type="primary", width="stretch"):
            st.rerun()  # a full rerun closes the dialog
        st.button("Add another company", key="wl-another", type="tertiary", width="stretch",
                  on_click=_wl_go, args=("form",))
        return

    st.button("Back", key="wl-back", icon=":material/arrow_back:", type="tertiary",
              on_click=_wl_go, args=("intro",))
    configured = _watchlist_configured()
    if not configured:
        # Technical detail for whoever sets it up: needs a GITHUB_TOKEN with
        # write access to the repo in Streamlit's secrets.
        st.info("Adding companies isn't switched on here yet. Ask the team to connect it.")
    with st.form("add_operator_form", border=False):
        st.text_input("Company name", key="wl_name", placeholder="e.g. Example Gaming Ltd")
        st.text_input(
            "Companies House number (optional)",
            key="wl_number",
            help="Optional. It helps us pick up official filings too.",
        )
        st.text_input("Other names it goes by (optional)", key="wl_aliases",
                      placeholder="Separate names with commas")
        st.text_area("Notes (optional)", key="wl_notes",
                     placeholder="Anything that helps the team, e.g. why it matters")
        st.form_submit_button(
            "Add to watchlist", type="primary", disabled=not configured,
            width="stretch", on_click=_submit_watchlist,
        )
    if st.session_state.get("wl_error"):
        st.error(st.session_state["wl_error"])


# The new-sector dialog: a premium upsell, a demo unlock, a description that
# Claude drafts into a sector config, a review form, then the save. The unlock
# lives in session state only, so a reload locks creation again.
MAX_SECTORS, MAX_DRAFTS = 10, 5

# Same flat PA language as the watchlist illustration: a sector switcher card
# with three sector rows, the new one cobalt-edged with a "+" badge and a
# PREMIUM tag block.
_NEW_SECTOR_ILLUSTRATION = """
<svg viewBox="0 0 360 176" width="100%" role="img" aria-label="A sector menu with a new premium sector being added" xmlns="http://www.w3.org/2000/svg">
  <rect x="0" y="0" width="360" height="176" fill="#e5e3d3"/>
  <rect x="24" y="24" width="44" height="44" fill="#8DDBFF"/>
  <rect x="296" y="128" width="40" height="28" fill="#000"/>
  <rect x="88" y="22" width="192" height="134" fill="#fff"/>
  <rect x="88" y="22" width="192" height="24" fill="#000"/>
  <rect x="100" y="31" width="44" height="6" fill="#fff"/>
  <rect x="100" y="58" width="12" height="12" fill="#000"/>
  <rect x="120" y="60" width="88" height="7" fill="#000"/>
  <rect x="100" y="84" width="12" height="12" fill="none" stroke="#000" stroke-width="2"/>
  <rect x="120" y="86" width="70" height="7" fill="#000"/>
  <rect x="100" y="106" width="168" height="2" fill="#dedad9"/>
  <rect x="88" y="114" width="192" height="32" fill="#f2f6ff"/>
  <rect x="88" y="114" width="4" height="32" fill="#004FFF"/>
  <rect x="100" y="126" width="64" height="7" fill="#004FFF"/>
  <rect x="172" y="122" width="52" height="15" fill="#8DDBFF"/>
  <rect x="179" y="128" width="38" height="4" fill="#004FFF"/>
  <rect x="256" y="104" width="36" height="36" fill="#004FFF"/>
  <rect x="272" y="112" width="4" height="20" fill="#fff"/>
  <rect x="264" y="120" width="20" height="4" fill="#fff"/>
</svg>
"""

_NS_DESCRIPTION_LENGTH = "Please describe the industry in 10 to 300 characters."
_NS_DRAFT_FAILED = "We couldn't draft that one. Try describing it differently."
_NS_NO_ANTHROPIC = "Drafting isn't switched on here yet."
_NS_NO_GITHUB = "Saving isn't switched on here yet."
_NS_DRAFT_LIMIT = "You've reached the demo's draft limit."


def _open_new_sector() -> None:
    st.session_state["ns_open"] = True
    st.session_state["ns_step"] = "upsell" if not st.session_state.get("premium_unlocked") else "describe"
    st.session_state.pop("ns_error", None)


def _close_new_sector() -> None:
    """Dismissed with the X or Escape: stop re-opening it on every rerun."""
    st.session_state.pop("ns_open", None)


def _ns_go(step: str) -> None:
    st.session_state["ns_step"] = step
    st.session_state.pop("ns_error", None)


def _unlock() -> None:
    st.session_state["premium_unlocked"] = True
    _ns_go("describe")


BEDROCK_DEFAULT_MODEL = "eu.anthropic.claude-sonnet-5-5"


def _drafting_on() -> bool:
    return bool(_secret("BEDROCK_AWS_PROFILE") or _secret("ANTHROPIC_API_KEY"))


def _anthropic_client():
    """(client, model) for drafting, or (None, None) when it isn't set up.
    Bedrock wins when BEDROCK_AWS_PROFILE is set: it signs requests with that
    AWS CLI profile (run `aws sso login --profile <name>` first), so no
    Anthropic key is needed. Otherwise ANTHROPIC_API_KEY talks to the API
    directly with the default model."""
    import anthropic
    profile = _secret("BEDROCK_AWS_PROFILE")
    if profile:
        client = anthropic.AnthropicBedrock(
            aws_profile=profile, aws_region=_secret("BEDROCK_AWS_REGION") or "eu-west-1",
            max_retries=1, timeout=60)
        return client, _secret("BEDROCK_MODEL") or BEDROCK_DEFAULT_MODEL
    key = _secret("ANTHROPIC_API_KEY")
    if not key:
        return None, None
    return anthropic.Anthropic(api_key=key, max_retries=1, timeout=60), None


def _companies_house():
    key = _secret("COMPANIES_HOUSE_API_KEY")
    return drafting.CompaniesHouse(key) if key else None


def _slug_union(index: list[dict] | None) -> set[str]:
    """Every known sector: the remote index (None if it couldn't be loaded),
    the configs in this checkout, and sectors created earlier this session.
    Both the menu's cap and the save's cap count this, so they agree."""
    pending = [p["slug"] for p in st.session_state.get("pending_sectors", [])]
    slugs = {e.get("slug") for e in index or [] if isinstance(e, dict)}
    return {s for s in slugs if isinstance(s, str)} | set(sectors.list_sector_slugs()) | set(pending)


def _existing_slugs() -> set[str]:
    """Every slug a new sector must not take (and the sectors the cap counts)."""
    try:
        index = load_index()
    except Exception:
        index = None
    return _slug_union(index)


_NS_REVIEW_KEYS = ("ns_name", "ns_brief", "ns_keywords", "ns_companies")


def _run_draft() -> None:
    """Draft from the description. Any failure (bad draft, API or network
    error) becomes the friendly copy; the user stays on the describe step."""
    state = st.session_state
    if not _drafting_on():
        state["ns_error"] = _NS_NO_ANTHROPIC
        return
    if state.get("ns_drafts_used", 0) >= MAX_DRAFTS:
        state["ns_error"] = _NS_DRAFT_LIMIT
        return
    # Everything that could pause (cached index load, client setup) happens
    # before the draft is counted, so one click is never counted twice.
    try:
        existing, ch = _existing_slugs(), _companies_house()
        client, model = _anthropic_client()
    except Exception:
        logger.exception("setting up the sector draft failed")
        state["ns_error"] = _NS_DRAFT_FAILED
        return
    state["ns_drafts_used"] = state.get("ns_drafts_used", 0) + 1
    try:
        draft = drafting.draft_sector(state.get("ns_description", ""), existing, client, ch,
                                      model=model)
    except ValueError:
        logger.exception("the sector description was rejected")
        state["ns_error"] = _NS_DESCRIPTION_LENGTH
        return
    except Exception:
        logger.exception("drafting the sector failed")
        state["ns_error"] = _NS_DRAFT_FAILED
        return
    state["ns_draft"] = draft
    # A fresh draft starts a fresh form: drop the previous one's widget values.
    for key in [*_NS_REVIEW_KEYS, *(f"ns_src_{s}" for s in drafting.GENERIC_SOURCES)]:
        state.pop(key, None)
    state["ns_company_rows"] = [{k: v for k, v in c.items() if k != "verified"}
                                for c in draft.companies]
    _ns_go("review")


_NS_SECTOR_LIMIT = "Contact us to add more sectors."
_NS_NAME_TAKEN = "That name was just taken. Please try again."


def _run_create() -> None:
    """Apply the review edits, check the cap and the form, re-verify company
    numbers, validate, save. If another session takes the slug meanwhile,
    re-slug and retry once."""
    state = st.session_state
    draft = state["ns_draft"]
    config = new_sector.apply_review(
        draft.config,
        name=state.get("ns_name", draft.config["name"]),
        brief=state.get("ns_brief", draft.config["brief"]),
        keywords=state.get("ns_keywords", draft.config["keywords"]),
        companies=state.get("ns_company_rows", draft.companies),
        sources=[s for s in drafting.GENERIC_SOURCES
                 if state.get(f"ns_src_{s}", s in draft.config["sources"])],
    )
    problem = new_sector.review_problem(config)
    if problem:
        state["ns_error"] = problem
        return
    try:
        existing = _existing_slugs()
        # The menu's row is only a hint; this is the cap that holds.
        if len(existing) >= MAX_SECTORS:
            state["ns_error"] = _NS_SECTOR_LIMIT
            return
        if config["name"] != draft.config["name"]:
            config["slug"] = drafting.unique_slug(config["name"], existing)
        # Re-verify: an edited number must be confirmed again before it's saved.
        rows = drafting.verify_companies(config["companies"], _companies_house())
        config["companies"] = [{k: v for k, v in r.items() if k != "verified"} for r in rows]
        sectors.parse_sector(config, config["slug"])
    except Exception:
        logger.exception("preparing the new sector for saving failed")
        state["ns_error"] = github.MSG_NOT_SAVED
        return
    now = datetime.now(timezone.utc)
    gh = github.GitHub(_secret("GITHUB_TOKEN"))

    def save() -> tuple[dict, github.SaveResult]:
        entry = {"slug": config["slug"], "name": config["name"], "brief": config["brief"],
                 "created_at": config["created_at"], "status": "setting_up"}
        return entry, github.save_sector(gh, config, entry, f"{now.day} {now:%B %Y}")

    entry, result = save()
    if not result.saved and result.exists:
        # Another session took the slug while this one was in review.
        config["slug"] = drafting.unique_slug(config["name"], existing | {config["slug"]})
        entry, result = save()
        if not result.saved and result.exists:
            state["ns_error"] = _NS_NAME_TAKEN
            return
    if not result.saved:
        logger.error("saving the %s sector failed: %s", config["slug"], result.message)
        state["ns_error"] = result.message
        return
    state.setdefault("pending_sectors", []).append(entry)
    state["ns_result"] = {"name": config["name"], "slug": config["slug"], "message": result.message}
    load_index.clear()
    # Show it now, so dismissing the Created step with X or Escape lands on it too.
    _select_sector(config["slug"])
    _ns_go("done")


def _apply_company_edits() -> None:
    """Data editor callback: fold its change set into ns_company_rows, then
    drop the editor's own state. The table's data changes with the fold, so
    it redraws from the new rows, Verified ticks recomputed."""
    state = st.session_state
    state["ns_company_rows"] = new_sector.apply_editor_changes(
        state.get("ns_company_rows", []), state.get("ns_companies"))
    state.pop("ns_companies", None)


def _finish_new_sector() -> None:
    """Done: show the new sector and close the dialog. The draft counter
    survives, so closing and reopening doesn't reset the demo's limit."""
    result = st.session_state.get("ns_result") or {}
    if result.get("slug"):
        _select_sector(result["slug"])
    for key in [k for k in st.session_state if str(k).startswith("ns_") and k != "ns_drafts_used"]:
        del st.session_state[key]


@st.dialog("New sector", width="medium", on_dismiss=_close_new_sector)
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
            + (f'<p class="wl-copy wl-muted">{html.escape(result["message"])}</p>'
               if result.get("message") else ""),
            unsafe_allow_html=True,
        )
        # A widget in a dialog reruns only the dialog, so Done asks for a
        # full rerun: that closes the dialog and shows the new sector.
        if st.button("Done", key="ns-done", type="primary", width="stretch"):
            _finish_new_sector()
            st.rerun()
        return

    if step == "describe":
        drafting_on = _drafting_on()
        if not drafting_on:
            st.info(_NS_NO_ANTHROPIC)
        used = state.get("ns_drafts_used", 0)
        st.text_area("Which industry should we track?", key="ns_description", max_chars=300,
                     placeholder="e.g. UK energy suppliers and the regulators around them")
        # Drafted in the script body, not a callback, so the spinner shows
        # while Claude works (a callback runs before anything renders).
        if st.button("Draft it", key="ns-draft", type="primary", width="stretch",
                     disabled=used >= MAX_DRAFTS or not drafting_on):
            with st.spinner("Drafting your sector…", show_time=True):
                _run_draft()
            st.rerun()  # the dialog reopens (ns_open) at the new step
        if used >= MAX_DRAFTS:
            st.caption(_NS_DRAFT_LIMIT)
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
    st.markdown('<p class="ns-label">Companies</p>', unsafe_allow_html=True)
    # The table is drawn from ns_company_rows; each edit is folded back into
    # it (see _apply_company_edits) so the Verified column can follow edits.
    st.data_editor(new_sector.editor_rows(state.get("ns_company_rows", []), draft.companies),
                   key="ns_companies", num_rows="dynamic", width="stretch",
                   disabled=[new_sector.VERIFIED_COL], hide_index=True,
                   on_change=_apply_company_edits)
    st.markdown('<p class="ns-label">Sources</p>', unsafe_allow_html=True)
    for s in drafting.GENERIC_SOURCES:
        st.checkbox(_source_name(s), value=s in cfg["sources"], key=f"ns_src_{s}")
    with st.expander("Advanced", key="ns-advanced"):
        st.caption("How Claude will score this sector. Shown for reference.")
        st.json({"prompt": cfg["prompt"], "categories": cfg["categories"],
                 "excluded_bodies": cfg["excluded_bodies"], "tickers": cfg["tickers"]}, expanded=False)
    can_save = bool(_secret("GITHUB_TOKEN"))
    if not can_save:
        st.info(_NS_NO_GITHUB)
    if st.button("Create sector", key="ns-create", type="primary", width="stretch",
                 disabled=not can_save):
        with st.spinner("Creating your sector…"):
            _run_create()
        st.rerun()
    st.button("Start over", key="ns-restart", type="tertiary", width="stretch",
              on_click=_ns_go, args=("describe",))
    if state.get("ns_error"):
        st.error(state["ns_error"])


def _watchlist_button() -> None:
    """Header action: opens the watchlist dialog at its intro. Secondary
    (outlined), so it doesn't compete with the feed."""
    if st.button("Add to watchlist", key="open-watchlist", icon=":material/add:",
                 on_click=_open_watchlist):
        _watchlist_dialog()


# Fragments: a card click or the quiet toggle reruns only its own tab, not
# the whole app. Without them every click rebuilt all three tabs (~930 KB,
# 212 signal cards) to change one selection.
@st.fragment
def _patterns_fragment(signals: list[dict], sector) -> None:
    render_patterns(signals, sector)


@st.fragment
def _themes_fragment(signals: list[dict], sector) -> None:
    render_themes(signals, sector)


def main() -> None:
    inject_css()
    st.html(_RESIZE_SCRIPT, unsafe_allow_javascript=True)
    if not check_password():
        return
    try:
        index = load_index()
    except data.IndexUnavailable:
        index = None  # this run only: the failure isn't cached
    index = new_sector.merge_pending(index, st.session_state.get("pending_sectors", []))
    at_cap = len(_slug_union(index)) >= MAX_SECTORS
    legacy = index is None
    entries = data.order_index(data.LEGACY_INDEX if legacy else index)
    if not entries:
        entries = data.LEGACY_INDEX
        legacy = True
    slug = data.pick_sector(entries, st.query_params.get("sector"))
    current = next(e for e in entries if e["slug"] == slug)
    st.session_state[SECTOR] = slug
    st.session_state["sector_name"] = data.plain_name(current)  # HTML contexts escape it
    sector = sector_rules(slug)

    # Title on the left and pipeline health on the right, rather than
    # stacked, so the feed starts higher up the page.
    title_col, status_col = st.columns([3, 2], vertical_alignment="bottom")
    with title_col:
        render_masthead(entries, current, at_cap)
    with status_col:
        with st.container(key="header-actions", horizontal=True, horizontal_alignment="right"):
            _watchlist_button()
        render_health_strip(load_run_status(slug, legacy), reserve=not legacy)

    name = data.plain_name(current)  # html.escape'd blocks
    try:
        signals = load_signals(slug, legacy)
    except data.DataError:
        _sector_state_block("Not available yet",
                            f"We couldn't load {name} yet. We'll try again on the next scheduled update.")
        return

    state = data.view_state(current, signals)
    if state == "setting_up":
        _sector_state_block("Setting up", f"We're gathering the first signals for {name}. "
                            "This usually takes under an hour.")
        return
    if state == "empty":
        _sector_state_block("No signals yet", f"{name} is set up, but nothing has come "
                            "through yet. New signals will appear here as they're found.")
        return
    if state == "error_empty":
        _sector_state_block("Not available yet",
                            f"We couldn't load {name} yet. We'll try again on the next scheduled update.")
        return
    if state == "error_with_data":
        with st.container(key="sector-notice"):
            st.markdown('<p class="sector-notice">The last update didn\'t finish. '
                        "Showing the latest data we have.</p>", unsafe_allow_html=True)
    # Only the open tab renders (on_change="rerun" gives each tab .open), so
    # the sidebar's feed filters appear only beside the Feed, and hidden tabs
    # cost nothing.
    # A slot just above the tabs, positioned onto the right of the tab row
    # (see inject_css); filled only on the Feed, the one tab Sort applies to.
    sort_slot = st.container(key="tabs-sort")
    feed_tab, patterns_tab, themes_tab = st.tabs(
        ["Feed", "Patterns", "Themes"], key="tab", on_change="rerun"
    )
    if feed_tab.open:
        with sort_slot:
            _sort_control()
        with feed_tab:
            # Not a fragment: its filters are in the sidebar, which fragments
            # can't write to.
            render_feed(signals)
    if patterns_tab.open:
        with patterns_tab:
            _patterns_fragment(signals, sector)
    if themes_tab.open:
        with themes_tab:
            _themes_fragment(signals, sector)


main()
