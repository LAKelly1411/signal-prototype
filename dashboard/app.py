import base64
import html
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import requests
import streamlit as st
import streamlit.components.v1 as components
import yaml

from dashboard.brand import (
    ENTITY_ICON,
    LINK_ICON,
    PA_LOGO_SVG,
    SOURCE_DOMAINS,
    SOURCE_LOGOS,
    SOURCE_NAMES,
    category_icon,
    icon,
)
from src.cluster import (
    CLUSTER_WINDOW_DAYS,
    MIN_THEME_COMPANIES,
    SIGNIFICANT_SCORE,
    compute_heat,
    compute_theme_heat,
    is_excluded,
    signal_entities,
)

st.set_page_config(page_title="Sector Signal", layout="wide")

GITHUB_OWNER = "LAKelly1411"
GITHUB_REPO = "signal-prototype"
USER_WATCHLIST_PATH = "config/user_watchlist.yaml"

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
        .sc-source-name { font-weight: 700; white-space: nowrap; }
        .sc-sep { opacity: 0.2; }
        .sc-time { white-space: nowrap; }
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
            padding: 16px 24px 20px 24px;
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
        /* Timeline: one tick per signal over the 90-day window. */
        .tl { margin-top: 12px; }
        .tl-track {
            position: relative;
            height: 32px;
            border-bottom: 1px solid var(--pa-border);
        }
        /* Cobalt in the relevance ring's two tones: solid for signals that
           count toward heat, the ring's 20% track for the ones that don't. */
        .tl-tick {
            position: absolute;
            bottom: 0;
            width: 6px;
            margin-left: -3px;
            background: var(--pa-cobalt);
        }
        .tl-tick.tl-quiet { background: rgba(0, 79, 255, 0.2); }
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
        [class*="st-key-pcard-"][class*="-sel"], [class*="st-key-tcard-"][class*="-sel"] { cursor: default; }
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
        [class*="st-key-tcard-"]:has(button:focus-visible) { outline-color: var(--pa-cobalt-hover); }

        /* ── Preview pane ──────────────────────────────────────────
           Fixed to the window's right edge at full height, apart from the
           title and the list, which move over for it. White, with a grey rule
           on its left edge that doubles as the drag-to-resize handle. */
        :root { --preview-width: min(34rem, 38vw); }
        [data-testid="stLayoutWrapper"]:has(> [class*="st-key-signals-panel-"]) {
            position: fixed;
            top: 0;
            right: 0;
            bottom: 0;
            width: var(--preview-width);
            z-index: 999990;
        }
        [data-testid="stMain"]:has([class*="st-key-signals-panel-"]) {
            padding-right: var(--preview-width);
        }
        [class*="st-key-signals-panel-"] {
            position: relative;
            height: 100%;
            overflow-y: auto;
            background: var(--pa-paper);
            border-left: 1px solid #cccccc;
            padding: 2rem 1.75rem 3rem 1.75rem;
            gap: 0;
        }
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
        .sp-section {
            margin: 2rem 0 1rem 0;
            padding-top: 1.5rem;
            border-top: 1px solid #cccccc;
            font-family: var(--pa-font-data);
            font-weight: 700;
            font-size: 1.125rem;
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
        /* The resize script's zero-height component shouldn't add a gap. */
        [data-testid="stElementContainer"]:has(> iframe[srcdoc*="paPreviewResize"]) {
            position: absolute;
            height: 0;
            overflow: hidden;
        }
        @media (max-width: 767px) {
            [data-testid="stLayoutWrapper"]:has(> [class*="st-key-signals-panel-"]) {
                position: static;
                width: 100%;
            }
            [data-testid="stMain"]:has([class*="st-key-signals-panel-"]) { padding-right: 0; }
            [class*="st-key-signals-panel-"] { height: auto; border-left: none; border-top: 1px solid #cccccc; }
            .sp-resize { display: none; }
            /* Inline under its card on phones, so the card's details would
               repeat directly above; just the signals show. */
            [class*="st-key-signals-panel-"] .group-card-full { display: none; }
            [class*="st-key-signals-panel-"] .sp-section { margin-top: 0; }
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
        [data-testid="stSidebar"] { border-right: none; }
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
        [class*="st-key-pcard-"][class*="-sel"],
        [class*="st-key-tcard-"][class*="-sel"] { outline-color: var(--pa-cobalt); }
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

        /* The pane slides in when it opens and again when the selection
           changes (it's keyed by selection, so it remounts). Fill mode is
           "backwards", not "both": a transform left on the pane after the
           animation would capture its fixed resize handle, and one left on
           the cards would block their hover lift. */
        @keyframes pa-pane-in {
            from { opacity: 0; transform: translateX(24px); }
            to { opacity: 1; transform: translateX(0); }
        }
        @keyframes pa-rise {
            from { opacity: 0; transform: translateY(8px); }
            to { opacity: 1; transform: translateY(0); }
        }
        [class*="st-key-signals-panel-"] {
            animation: pa-pane-in var(--dur-slow) var(--ease) backwards;
        }
        [class*="st-key-signals-panel-"] .signal-card {
            animation: pa-rise var(--dur-slow) var(--ease) backwards;
            animation-delay: 120ms;
        }
        /* Timeline ticks grow from the baseline, staggered left to right. */
        @keyframes pa-tick-grow {
            from { transform: scaleY(0); }
            to { transform: scaleY(1); }
        }
        .tl-tick {
            transform-origin: bottom;
            animation: pa-tick-grow var(--dur-slow) var(--ease) backwards;
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


def render_masthead(show_intro: bool = True) -> None:
    """PA lockup — the mark beside the product name set as two ink blocks, as on
    the Media Briefings header — then kicker, title and standfirst."""
    intro = ""
    if show_intro:
        intro = (
            '<span class="pa-kicker">Gambling &amp; gaming</span>'
            '<div class="pa-title">Sector Signal</div>'
            '<p class="pa-standfirst">Sector signals, scored for newsworthiness.</p>'
        )
    st.markdown(
        '<div class="pa-masthead"><div class="pa-lockup">'
        f"{PA_LOGO_SVG}"
        '<span class="pa-wordmark"><span>Sector</span><span>Signal</span></span>'
        f'</div>{intro}<span class="pa-font-warm" aria-hidden="true">a<b>a</b></span></div>',
        unsafe_allow_html=True,
    )


def check_password() -> bool:
    if st.session_state.get("authenticated"):
        return True

    render_masthead(show_intro=False)
    password = st.text_input("Password", type="password")
    if password:
        if password == st.secrets["DASHBOARD_PASSWORD"]:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    return False


@st.cache_data(ttl=600)
def load_signals() -> list[dict]:
    resp = requests.get(st.secrets["DATA_RAW_URL"], timeout=20)
    resp.raise_for_status()
    return resp.json()


@st.cache_data(ttl=600)
def load_run_status() -> dict | None:
    """Pipeline health, published next to the signals file. Absent on older
    data or if the URL isn't configured — the strip just hides itself."""
    url = st.secrets.get("RUN_STATUS_RAW_URL")
    if not url:
        return None
    try:
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


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


def _source_logo(source: str) -> str:
    token = _logo_dev_token()
    domain = SOURCE_DOMAINS.get(source)
    if token and domain:
        src = html.escape(
            f"https://img.logo.dev/{domain}?token={token}&size=48&format=png&retina=true",
            quote=True,
        )
        return f'<img class="sc-logo" src="{src}" alt="" loading="lazy">'
    logo = SOURCE_LOGOS.get(source)
    if logo:
        return f'<img class="sc-logo" src="{logo}" alt="">'
    initials = SOURCE_NAMES.get(source, (source, source[:3].upper()))[1]
    size = "sc-logo-sm" if len(initials) > 2 else ""
    return f'<span class="sc-logo sc-logo-initials {size}">{html.escape(initials)}</span>'


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
    if signal.get("published_at_estimated"):
        # The source gave no usable date, so this is the ingest time standing
        # in — say so rather than presenting a guess as fact.
        when += " (date estimated)"

    # Canonical names, so a company appears once however the source spelled it.
    entities = signal_entities(signal)
    tags = [
        f'<span class="sc-tag sc-tag-entity"><span class="sc-tag-icon">{ENTITY_ICON}</span>'
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
        f'<span class="sc-time">{html.escape(when)}</span></div>'
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


def apply_filters(scored: list[dict]) -> tuple[list[dict], str]:
    st.sidebar.header("Filters")

    search_query = st.sidebar.text_input(
        "Search", placeholder="Search title, summary, entities…"
    ).strip().lower()

    # Keyed on the current option set so the widget resets to "all selected"
    # whenever a new source or signal type shows up — otherwise Streamlit
    # keeps a session's original default forever, silently hiding anything
    # added after the browser tab was first opened.
    sources = sorted({s["source"] for s in scored})
    selected_sources = st.sidebar.multiselect(
        "Source", sources, default=sources, key=f"sources_{','.join(sources)}"
    )

    signal_types = sorted({s["signal_type"] for s in scored if s.get("signal_type")})
    selected_types = st.sidebar.multiselect(
        "Signal type",
        signal_types,
        default=signal_types,
        key=f"types_{','.join(signal_types)}",
    )

    # Canonical names, so one option covers every spelling of a company —
    # picking "Entain Holdings (UK) Limited" also matches signals that named
    # it "Entain".
    all_entities = sorted(
        {e for s in scored for e in signal_entities(s)}, key=str.lower
    )
    selected_entities = st.sidebar.multiselect(
        "Company / entity",
        all_entities,
        help="Leave empty to include all companies.",
    )

    # Defaults to 40 (Medium+) rather than 0 so a busy day doesn't bury
    # higher-value signals under Low-tier noise; still adjustable down to 0.
    min_score = st.sidebar.slider("Minimum score", 0, 100, 40)

    published_dates = [
        datetime.fromisoformat(s["published_at"]).date() for s in scored
    ]
    min_date, max_date = min(published_dates), max(published_dates)
    date_range = st.sidebar.date_input(
        "Date range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
        # Keyed on the current bounds so the widget resets to the full
        # range whenever new data extends it — otherwise Streamlit keeps
        # whatever range was selected when the browser session started,
        # which quietly falls behind as the store picks up new signals.
        key=f"date_range_{min_date}_{max_date}",
    )
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date, end_date = min_date, max_date

    sort_order = st.sidebar.radio(
        "Sort by", ["Newest first", "Highest score first"], horizontal=True
    )

    filtered = []
    for signal, pub_date in zip(scored, published_dates):
        if signal["source"] not in selected_sources:
            continue
        if signal.get("signal_type") not in selected_types:
            continue
        if signal["newsworthiness_score"] < min_score:
            continue
        if not (start_date <= pub_date <= end_date):
            continue
        if selected_entities and not set(signal_entities(signal)) & set(
            selected_entities
        ):
            continue
        if search_query:
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
            if search_query not in haystack:
                continue
        filtered.append(signal)

    if sort_order == "Highest score first":
        filtered.sort(key=lambda s: s["newsworthiness_score"], reverse=True)

    return filtered, sort_order


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
    st.caption(f"Showing {len(filtered)} of {len(scored)} scored signals.")

    if not filtered:
        st.info("No signals match the current filters.")
        return

    if sort_order != "Newest first":
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
        if not buckets[bucket]:
            continue
        st.markdown(f'<div class="section-label">{bucket}</div>', unsafe_allow_html=True)
        for signal in buckets[bucket]:
            render_card(signal, cluster_info)


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


def _timeline(members: list[dict], now: datetime) -> str:
    """One tick per signal across the clustering window, today at the right.
    Height follows the signal's score; ticks below the significance bar are
    pale, as heat ignores them. Shows at a glance whether a pattern is a burst
    this week or a slow build over months."""
    start = now - timedelta(days=CLUSTER_WINDOW_DAYS)
    span = CLUSTER_WINDOW_DAYS * 86400
    ticks = []
    for m in sorted(members, key=lambda m: m["published_at"]):
        dt = datetime.fromisoformat(m["published_at"])
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        x = max(0.0, min(100.0, (dt - start).total_seconds() / span * 100))
        score = m.get("newsworthiness_score") or 0
        height = 6 + round(score / 100 * 26)
        quiet = " tl-quiet" if score < SIGNIFICANT_SCORE else ""
        delay = min(len(ticks) * 20, 400)
        ticks.append(
            f'<span class="tl-tick{quiet}" '
            f'style="left:{x:.2f}%;height:{height}px;animation-delay:{delay}ms"></span>'
        )
    label = (
        f"{len(members)} signals over the last {CLUSTER_WINDOW_DAYS} days, "
        f"latest {_date_span(members[-1:])}"
    )
    return (
        f'<div class="tl" role="img" aria-label="{html.escape(label, quote=True)}">'
        f'<div class="tl-track">{"".join(ticks)}</div>'
        f'<div class="tl-axis"><span>{start.day} {start:%b}</span><span>Today</span></div>'
        "</div>"
    )


def _company_tags(companies: list[str], limit: int | None = MAX_COMPANY_TAGS) -> list[str]:
    shown = companies if limit is None else companies[:limit]
    tags = [
        f'<span class="sc-tag sc-tag-entity"><span class="sc-tag-icon">{ENTITY_ICON}</span>'
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
        f"{_timeline(group.members, now)}"
        + (f'<div class="sc-tags gc-tags">{"".join(tags)}</div>' if tags else "")
        + "</div>"
    )


def _group_card(group: Group, now: datetime, selected: bool, state_key: str) -> None:
    """A pattern or theme in the list. Clicking it fills the preview pane."""
    with st.container(key=f"{group.key}{'-sel' if selected else ''}"):
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


# Lets the reader drag the preview pane's left edge. Streamlit can't run
# scripts from Markdown, so this rides in a zero-height component, whose iframe
# is same-origin with the app and can reach the page. It sets --preview-width,
# which sizes both the pane and the room the main column leaves for it, and
# remembers the width in localStorage. Streamlit replaces the iframe on
# re-render, and handlers owned by a discarded iframe stop firing, so each new
# iframe removes its predecessor's handlers and installs its own.
_RESIZE_SCRIPT = """
<script>
(() => {
  const win = window.parent;
  const doc = win.document;
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


def _preview_pane(key: str, group: Group, now: datetime) -> None:
    """The selected pattern or theme in full, then its source signals, in a
    pane fixed to the window's right edge (see inject_css), apart from the
    title and the list. Only the active tab is in the DOM, so the pane appears
    on Patterns and Themes and nowhere else."""
    # Keyed by selection, so choosing another card remounts the pane and its
    # entrance animation plays again.
    with st.container(key=f"{key}-{group.key}"):
        st.markdown(
            '<div class="sp-resize" role="separator" aria-orientation="vertical" '
            'aria-label="Resize preview" tabindex="0"></div>'
            f"{_group_html(group, now, full=True)}"
            f'<div class="sp-section">Signals ({len(group.members)})</div>',
            unsafe_allow_html=True,
        )
        for m in sorted(group.members, key=lambda m: m["published_at"], reverse=True):
            render_card(m)
    components.html(_RESIZE_SCRIPT, height=0)


def _render_groups(groups: list[Group], state_key: str, pane_key: str) -> None:
    """The list of cards plus the preview of the selected one, falling back
    to the first when nothing is chosen yet or the choice dropped out of view."""
    now = datetime.now(timezone.utc)
    ids = [g.id for g in groups]
    selected = st.session_state.get(state_key)
    if selected not in ids:
        selected = ids[0]
    for group in groups:
        _group_card(group, now, group.id == selected, state_key)
        if group.id == selected:
            _preview_pane(pane_key, group, now)


def render_patterns(signals: list[dict]) -> None:
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
        companies = [n for n, _ in counts.most_common() if not is_excluded(n)]
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
                tile_html=(
                    '<span class="sc-logo sc-logo-initials">'
                    f"{html.escape(_initials(primary))}</span>"
                ),
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


def render_themes(signals: list[dict]) -> None:
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
        ((compute_theme_heat(members), theme, members)
         for theme, members in grouped.items()),
        reverse=True,
        key=lambda t: t[0],
    )

    groups = []
    for heat, theme, members in themes:
        counts = Counter(e for m in members for e in signal_entities(m) if not is_excluded(e))
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


def render_health_strip(status: dict | None) -> None:
    """Freshness and source health at a glance. Without this a scraper whose
    page layout moved just goes quiet, and the feed looks like a slow news
    week rather than a broken collector."""
    if not status:
        return

    try:
        finished = datetime.fromisoformat(status["finished_at"])
    except (KeyError, ValueError):
        return

    age = (datetime.now(timezone.utc) - finished).total_seconds()
    healthy = status.get("healthy_sources", 0)
    total = status.get("total_sources", 0)

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


def _github_headers() -> dict:
    return {
        "Authorization": f"token {st.secrets['GITHUB_TOKEN']}",
        "Accept": "application/vnd.github+json",
    }


def _fetch_user_watchlist() -> tuple[dict, str | None]:
    url = (
        f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}"
        f"/contents/{USER_WATCHLIST_PATH}"
    )
    resp = requests.get(url, headers=_github_headers(), timeout=20)
    if resp.status_code == 404:
        return {"operators": []}, None
    resp.raise_for_status()
    payload = resp.json()
    content = base64.b64decode(payload["content"]).decode("utf-8")
    data = yaml.safe_load(content) or {"operators": []}
    return data, payload["sha"]


def add_operator_to_watchlist(
    name: str, company_number: str, aliases: str, notes: str
) -> None:
    data, sha = _fetch_user_watchlist()
    data.setdefault("operators", []).append(
        {
            "name": name,
            "company_number": company_number or None,
            "aliases": [a.strip() for a in aliases.split(",") if a.strip()],
            "notes": notes,
        }
    )
    new_content = yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
    encoded = base64.b64encode(new_content.encode("utf-8")).decode("utf-8")

    url = (
        f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}"
        f"/contents/{USER_WATCHLIST_PATH}"
    )
    body = {
        "message": f"Add {name} to watchlist via dashboard",
        "content": encoded,
        "branch": "main",
    }
    if sha:
        body["sha"] = sha
    resp = requests.put(url, headers=_github_headers(), json=body, timeout=20)
    resp.raise_for_status()


def render_watchlist_form() -> None:
    with st.sidebar.expander("Add a company to the watchlist"):
        with st.form("add_operator_form", clear_on_submit=True):
            name = st.text_input("Company name")
            company_number = st.text_input(
                "Companies House number (optional)",
                help="If you don't have this, we'll still monitor the name "
                "for Gazette insolvency notices, but not Companies House filings.",
            )
            aliases = st.text_input("Aliases / trading names (comma-separated, optional)")
            notes = st.text_area("Notes (optional)")
            submitted = st.form_submit_button("Add to watchlist")

            if submitted:
                if not name.strip():
                    st.error("Company name is required.")
                else:
                    try:
                        add_operator_to_watchlist(
                            name.strip(), company_number.strip(), aliases, notes.strip()
                        )
                        st.success(
                            f"Added {name} — it'll be picked up on the next pipeline run."
                        )
                    except Exception:
                        st.error(
                            "Couldn't save that addition — please flag it to the team."
                        )


def main() -> None:
    inject_css()
    if not check_password():
        return
    render_watchlist_form()

    # Title on the left and pipeline health on the right, rather than
    # stacked, so the feed starts higher up the page.
    title_col, status_col = st.columns([3, 2], vertical_alignment="bottom")
    with title_col:
        render_masthead()
    with status_col:
        render_health_strip(load_run_status())

    signals = load_signals()
    feed_tab, patterns_tab, themes_tab = st.tabs(["Feed", "Patterns", "Themes"])
    with feed_tab:
        render_feed(signals)
    with patterns_tab:
        render_patterns(signals)
    with themes_tab:
        render_themes(signals)


main()
