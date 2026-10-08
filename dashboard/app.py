import base64
import html
from collections import Counter, defaultdict
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests
import streamlit as st
import yaml

from src.cluster import (
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

# The Press Association mark (PRESS / ASSOC / IATION), lifted from the PA Media
# Briefings site's PressAssociationLogo.astro. Inline so it follows currentColor.
# It is a wordmark, not an icon: below ~32px the three lines stop resolving.
PA_LOGO_SVG = (
    '<svg class="pa-logo" viewBox="0 0 346 346" fill="currentColor" '
    'xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
    '<path d="M35.6978 18.292H26.3412V49.6632H35.9377C40.6879 49.6632 42.3673 48.1188 42.5113 42.4237V25.242C42.3673 19.8365 40.448 18.2438 35.6978 18.2438M42.7512 65.8797H26.3412V107.193H3.26172V2.02734H42.7512C59.8329 2.02734 65.4948 8.06026 65.4948 23.2149V43.9199C65.4948 58.8815 59.4011 65.8797 42.7512 65.8797Z"/>'
    '<path d="M116.164 25.242C116.164 19.9813 114.245 18.292 109.639 18.292H98.9383V46.2848H109.639C114.245 46.2848 116.164 44.7404 116.164 39.3349V25.2902V25.242ZM123.746 54.4896V55.2618C133.342 56.5649 137.181 61.2464 137.852 71.1404C138.332 78.0903 139.004 93.1485 139.244 96.7683C139.628 102.029 140.923 104.973 142.555 106.517V107.193H119.331C117.556 106.179 116.788 103.332 116.5 99.2297C116.021 91.7489 115.925 81.2757 115.589 73.5536C115.349 67.762 113.909 62.8391 108.151 62.8391H98.8423V107.193H75.7148V2.02734H118.132C134.686 2.02734 139.052 8.54289 139.052 23.3114V36.6804C139.052 47.4914 134.782 53.0899 123.698 54.4896"/>'
    '<path d="M205.028 2.02734V19.933H174.031V45.8022H200.325V62.5013H174.031V89.2874H205.267V107.193H151.047V2.02734H205.028Z"/>'
    '<path d="M249.316 147.155C249.316 139.578 247.829 135.234 241.303 135.234C234.778 135.234 233.29 139.578 233.29 147.155V198.411C233.29 205.988 234.778 210.332 241.303 210.332C247.829 210.332 249.316 205.988 249.316 198.411V147.155ZM273.739 194.357C273.739 218.392 261.456 227.513 241.303 227.513C221.151 227.513 208.867 218.392 208.867 194.357V151.306C208.867 127.27 221.151 118.149 241.303 118.149C261.456 118.149 273.739 127.27 273.739 151.306V194.357Z"/>'
    '<path d="M249.316 265.641C249.316 258.064 247.829 253.72 241.303 253.72C234.778 253.72 233.29 258.064 233.29 265.641V316.897C233.29 324.474 234.778 328.818 241.303 328.818C247.829 328.818 249.316 324.474 249.316 316.897V265.641ZM273.739 312.795C273.739 336.83 261.456 345.952 241.303 345.952C221.151 345.952 208.867 336.83 208.867 312.795V269.744C208.867 245.709 221.151 236.587 241.303 236.587C261.456 236.587 273.739 245.709 273.739 269.744V312.795Z"/>'
    '<path d="M25.4301 238.469H3.07031V343.973H25.4301V238.469Z"/>'
    '<path d="M99.8516 238.469H166.403V256.375H144.715V343.973H121.636V256.375H99.8516V238.469Z"/>'
    '<path d="M197.688 344.021L174.609 343.973V238.469H197.688V344.021Z"/>'
    '<path d="M282.328 238.469H306.799L323.593 295.517H324.073V238.469H343.122V343.973H321.626L301.905 278.383H301.281V343.973H282.328V238.469Z"/>'
    '<path d="M211.172 70.7058H232.429V83.6887C232.429 90.4455 236.027 92.3761 242.409 92.3761C248.791 92.3761 251.718 90.1077 251.766 82.5786C251.766 76.2078 249.51 72.7811 243.752 68.9683C236.459 64.1903 231.373 60.8601 223.264 54.7789C217.554 50.4835 211.604 43.1474 211.604 28.041C211.604 12.9346 220.673 0 241.833 0C262.993 0 272.542 5.35723 272.542 23.1181V34.267H251.67V25.8692C251.67 19.7397 247.735 17.23 242.361 17.23C236.987 17.23 232.716 19.5949 232.716 25.6761C232.716 31.7573 237.035 35.0392 243.369 39.2381C250.806 44.1127 254.884 46.188 263.137 53.0414C269.231 58.1091 274.749 66.2173 274.749 79.6345C274.749 100.098 261.65 109.654 242.409 109.654C223.168 109.654 211.22 101.063 211.22 84.4126V70.8023L211.172 70.7058Z"/>'
    '<path d="M281.512 70.7058H302.768V83.6887C302.768 90.4455 306.367 92.3761 312.748 92.3761C319.13 92.3761 322.057 90.1077 322.105 82.5786C322.105 76.2078 319.85 72.7811 314.092 68.9683C306.798 64.1903 301.712 60.8601 293.603 54.7789C287.941 50.4835 281.944 43.1474 281.944 28.041C281.944 12.9346 290.964 0 312.172 0C333.381 0 342.881 5.35723 342.881 23.1181V34.267H322.009V25.8692C322.009 19.7397 318.074 17.23 312.7 17.23C307.326 17.23 303.056 19.5949 303.056 25.6761C303.056 31.7573 307.374 35.0392 313.708 39.2381C321.145 44.1127 325.224 46.188 333.477 53.0414C339.57 58.1091 345.088 66.2173 345.088 79.6345C345.088 100.098 331.989 109.654 312.748 109.654C293.507 109.654 281.56 101.063 281.56 84.4126V70.8023L281.512 70.7058Z"/>'
    '<path d="M45.9191 225.583H69.9583L51.1492 120.031H18.7131L0 225.583H20.5365L23.4634 204.733H42.9442L45.9191 225.583ZM25.7186 188.951L32.1962 143.197H34.2114L40.737 188.951H25.7665H25.7186Z"/>'
    '<path d="M81.9075 343.973H105.946L87.1375 238.469H54.7014L35.9883 343.973H56.5248L59.4517 323.171H78.9325L81.9075 343.973ZM61.6589 307.438L68.1365 261.684H70.1518L76.6774 307.438H61.6589Z"/>'
    '<path d="M344.512 182.966V194.357C344.512 218.392 334.627 227.513 314.475 227.513C294.322 227.513 282.039 218.392 282.039 194.357V151.306C282.039 127.27 294.322 118.149 314.475 118.149C334.627 118.149 344.512 127.27 344.512 151.306V161.055H322.44C322.44 161.055 322.44 154.732 322.44 147.203C322.44 139.674 320.952 135.282 314.427 135.282C307.901 135.282 306.414 139.626 306.414 147.203V198.459C306.414 206.036 307.901 210.38 314.427 210.38C320.952 210.38 323.159 206.036 323.159 198.459C323.159 190.882 323.303 187.455 323.159 182.966H344.464H344.512Z"/>'
    '<path d="M139.582 188.372H160.838V201.355C160.838 208.112 163.717 210.042 170.05 210.042C176.384 210.042 178.639 207.774 178.639 200.245C178.639 193.874 177.104 189.675 171.346 185.91C164.053 181.132 158.966 177.802 150.857 171.721C145.196 167.426 139.917 160.814 139.917 145.755C139.917 130.697 148.266 117.714 169.475 117.714C190.683 117.714 199.464 123.072 199.464 140.833V151.981H178.591V143.584C178.591 137.454 175.424 134.944 170.002 134.944C164.58 134.944 161.078 137.309 161.078 143.39C161.078 149.472 165.396 152.754 171.73 156.952C179.167 161.827 183.246 163.902 191.499 170.756C197.592 175.823 201.623 183.932 201.623 197.349C201.623 217.813 189.243 227.369 170.002 227.369C150.761 227.369 139.582 218.778 139.582 202.127V188.517V188.372Z"/>'
    '<path d="M71.6367 188.372H92.8929V201.355C92.8929 208.112 95.7718 210.042 102.106 210.042C108.439 210.042 110.694 207.774 110.694 200.245C110.694 193.874 109.159 189.675 103.401 185.91C96.1077 181.132 91.0216 177.802 82.9126 171.721C77.2506 167.426 71.9726 160.814 71.9726 145.755C71.9726 130.697 80.3215 117.714 101.53 117.714C122.738 117.714 131.519 123.072 131.519 140.833V151.981H110.646V143.584C110.646 137.454 107.48 134.944 102.058 134.944C96.6355 134.944 93.1328 137.309 93.1328 143.39C93.1328 149.472 97.4512 152.754 103.785 156.952C111.222 161.827 115.301 163.902 123.554 170.756C129.647 175.823 133.678 183.932 133.678 197.349C133.678 217.813 121.298 227.369 102.058 227.369C82.8166 227.369 71.6367 218.778 71.6367 202.127V188.517V188.372Z"/>'
    "</svg>"
)

# Score is a magnitude bucketed into tiers, so it gets an ordinal ramp in PA ink:
# outline -> sunken grey -> solid ink, light->dark mapping low->high newsworthiness.
# Cobalt is kept off the ramp because in the PA system it means "clickable".
SCORE_TIERS = [
    (70, "High", "#000000", "#ffffff"),
    (40, "Medium", "#dedad9", "#000000"),
    (0, "Low", "#ffffff", "#000000"),
]

# Same ramp, scaled to the heat slider's range rather than a 0-100 score.
# Calibrated against the observed spread once heat stopped counting routine
# filings: there's a clear break at 60 between the busy half of the clusters
# and the quiet half, and 90 isolates the handful worth interrupting someone
# for. Re-check these if the heat formula changes again.
HEAT_TIERS = [
    (90, "High", "#000000", "#ffffff"),
    (60, "Medium", "#dedad9", "#000000"),
    (0, "Low", "#ffffff", "#000000"),
]

# Heat is unbounded in principle, but sits well under this in practice; a
# higher ceiling would leave most of the slider's travel unusable. It filters
# on a minimum, so anything above the ceiling still shows.
HEAT_SLIDER_MAX = 120

# Theme heat is on its own scale — it rewards breadth across companies rather
# than source diversity, so a sector-wide wave scores far above any single
# company's cluster. Calibrated separately for that reason.
THEME_HEAT_TIERS = [
    (200, "High", "#000000", "#ffffff"),
    (130, "Medium", "#dedad9", "#000000"),
    (0, "Low", "#ffffff", "#000000"),
]

# How Claude's own read of a cluster is shown. Anything not listed falls back
# to a plain chip.
PATTERN_TYPE_LABELS = {
    "escalation": "Escalating",
    "wave": "Sector-wide",
    "developing_story": "Developing",
    "routine": "Routine",
    "unrelated": "Unrelated",
}


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
    # PA brand, after the PA Media Briefings site (pa-tokens.css + brand-bridge.css):
    # square corners, no shadows, separation by fill and hairlines, cobalt only on
    # things you can click. Three faces with fixed jobs — condensed caps for
    # headings and labels, Frame Text serif for reading copy, Press Sans for UI
    # and data. The Google Fonts below are the stand-ins pa-tokens.css itself
    # lists, used wherever the PA CDN won't serve the real faces.
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Archivo:wght@400;700;800&family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,700;1,6..72,400&family=Oswald:wght@700&display=swap');

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
            --pa-font-body: 'Frame Text', Newsreader, Georgia, 'Times New Roman', serif;
            --pa-font-data: 'Press Sans', Archivo, Arial, Helvetica, sans-serif;
        }

        /* ── Masthead ─────────────────────────────────────────────── */
        .pa-masthead { margin: 0 0 1.5rem 0; }
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
            margin-bottom: 2rem;
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

        /* ── Section label: 32x4 cobalt bar over condensed caps ────── */
        .section-label {
            font-family: var(--pa-font-heading);
            font-weight: 700;
            font-size: 1.25rem;
            line-height: 1;
            text-transform: uppercase;
            letter-spacing: 0.01em;
            color: var(--pa-ink);
            margin: 2rem 0 0.25rem 0;
            padding: 0;
        }
        .section-label::before {
            content: "";
            display: block;
            width: 32px;
            height: 4px;
            background: var(--pa-cobalt);
            margin-bottom: 0.625rem;
        }

        /* ── Signal card: ItemCard — no box, hairlines between ─────── */
        .signal-card {
            padding: 1.25rem 0;
            border-top: 1px solid var(--pa-border);
        }
        .signal-card-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 1rem;
        }
        .signal-title {
            font-family: var(--pa-font-heading);
            font-weight: 700;
            font-size: 1.25rem;
            line-height: 1.25;
            color: var(--pa-ink);
        }
        .score-badge {
            font-family: var(--pa-font-data);
            font-weight: 700;
            font-size: 0.75rem;
            line-height: 1.4;
            padding: 0.2em 0.6em;
            border: 1px solid var(--pa-ink);
            white-space: nowrap;
            flex-shrink: 0;
        }
        .signal-meta {
            font-family: var(--pa-font-data);
            font-weight: 700;
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            color: var(--pa-muted);
            margin: 0.5rem 0 0 0;
        }
        .signal-why {
            font-family: var(--pa-font-body);
            font-size: 1.0625rem;
            line-height: 1.6;
            color: var(--pa-ink);
            margin-top: 0.625rem;
        }
        .signal-tags {
            margin-top: 0.625rem;
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
        }
        /* Tags are deliberately never cobalt: they aren't clickable. */
        .tag-chip {
            display: inline-block;
            background: var(--pa-surface);
            color: var(--pa-ink);
            font-family: var(--pa-font-heading);
            font-weight: 700;
            font-size: 0.8rem;
            line-height: 1.3;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            padding: 3px 8px;
        }
        .tag-chip.category { background: var(--pa-newsprint); }
        .tag-chip.pattern { background: var(--pa-ink); color: var(--pa-paper); }
        .pattern-badge {
            margin-top: 0.625rem;
            font-family: var(--pa-font-data);
            font-size: 0.8125rem;
            font-weight: 700;
            color: var(--pa-muted);
        }
        .signal-link {
            display: inline-block;
            margin-top: 0.75rem;
            font-family: var(--pa-font-data);
            font-weight: 700;
            font-size: 0.8125rem;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            color: var(--pa-cobalt) !important;
            text-decoration: none !important;
        }
        .signal-link:hover { text-decoration: underline !important; color: var(--pa-cobalt-hover) !important; }
        .estimated-date { font-style: italic; text-transform: none; }

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

        /* ── Pattern / theme read-outs: newsprint panel, ink kicker ── */
        .cluster-summary {
            background: var(--pa-newsprint);
            padding: 1.25rem 1.5rem;
            margin: 0.5rem 0 1rem 0;
            font-family: var(--pa-font-body);
            font-size: 1.0625rem;
            line-height: 1.6;
            color: var(--pa-ink);
        }
        .cluster-summary-label {
            display: table;
            background: var(--pa-ink);
            color: var(--pa-paper);
            font-family: var(--pa-font-heading);
            font-weight: 700;
            font-size: 0.875rem;
            line-height: 1.2;
            text-transform: uppercase;
            padding: 3px 7px;
            margin-bottom: 0.75rem;
        }
        .theme-points { list-style: none; margin: 0.875rem 0 0 0; padding: 0; }
        .theme-points li {
            position: relative;
            padding-left: 1.25rem;
            margin-bottom: 0.5rem;
        }
        .theme-points li::before {
            content: "";
            position: absolute;
            left: 0;
            top: 0.6em;
            width: 8px;
            height: 8px;
            background: var(--pa-cobalt);
        }
        .direction-chip {
            display: inline-block;
            font-family: var(--pa-font-data);
            font-size: 0.75rem;
            font-weight: 700;
            padding: 0.2em 0.6em;
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }
        .direction-building { background: #fffaeb; color: #b54708; }
        .direction-steady   { background: var(--pa-surface); color: var(--pa-ink); }
        .direction-easing   { background: #ecfdf3; color: #15803d; }

        /* ── Streamlit chrome, pulled into the PA idiom ───────────── */
        [data-testid="stMainBlockContainer"] { max-width: 65rem; padding-top: 3rem; }
        [data-testid="stHeader"] { background: transparent; }
        [data-testid="stCaptionContainer"] p {
            font-family: var(--pa-font-data);
            color: var(--pa-muted);
        }
        [data-testid="stTabs"] [role="tablist"] { gap: 0.25rem; }
        [data-testid="stTab"] {
            padding: 0.5rem 0.875rem;
        }
        [data-testid="stTab"]:hover { background: var(--pa-surface); }
        [data-testid="stTab"] p {
            font-family: var(--pa-font-heading);
            font-weight: 700;
            font-size: 1rem;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            color: var(--pa-ink);
        }
        /* Active tab as an ink block, like the masthead wordmark. */
        [data-testid="stTab"][aria-selected="true"],
        [data-testid="stTab"][aria-selected="true"]:hover { background: var(--pa-ink); }
        [data-testid="stTab"][aria-selected="true"] p { color: var(--pa-paper); }
        /* PA fields: white with an ink hairline, never the grey card fill. */
        [data-testid="stTextInputRootElement"],
        [data-testid="stTextAreaRootElement"] {
            background: var(--pa-paper);
            border-color: var(--pa-ink);
        }
        [data-testid="stExpander"] details {
            border: none;
            background: var(--pa-surface);
        }
        [data-testid="stExpander"] details summary:hover { background: var(--pa-sunken); }
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


def render_card(signal: dict, cluster_info: dict[str, tuple[float, int]] | None = None) -> None:
    label, bg, fg = score_tier(signal["newsworthiness_score"])
    why_it_matters = html.escape(signal.get("why_it_matters") or "")

    category = signal.get("category")
    entities = signal.get("entities") or []
    tags_html = ""
    if category or entities:
        chips = []
        if category:
            chips.append(f'<span class="tag-chip category">{html.escape(category)}</span>')
        chips.extend(f'<span class="tag-chip">{html.escape(e)}</span>' for e in entities)
        tags_html = f'<div class="signal-tags">{"".join(chips)}</div>'

    date_html = signal["published_at"][:10]
    if signal.get("published_at_estimated"):
        # The source gave no usable date, so this is the ingest time standing
        # in — say so rather than presenting a guess as fact.
        date_html = f'<span class="estimated-date">{date_html} (date estimated)</span>'

    pattern_html = ""
    cluster_id = signal.get("cluster_id")
    if cluster_info and cluster_id in cluster_info:
        heat, count = cluster_info[cluster_id]
        heat_label = heat_tier(heat)[0]
        pattern_html = (
            '<div class="pattern-badge">'
            f"Part of a pattern &middot; {count} signals &middot; "
            f"heat {heat:.0f} ({heat_label}) — see Patterns tab</div>"
        )

    st.markdown(
        f"""
        <div class="signal-card">
          <div class="signal-card-header">
            <span class="signal-title">{html.escape(signal['title'])}</span>
            <span class="score-badge" style="background:{bg};color:{fg};">
              {signal['newsworthiness_score']} &middot; {label}
            </span>
          </div>
          <div class="signal-meta">
            {html.escape(signal['source'])} &middot; {date_html}
          </div>
          {tags_html}
          <div class="signal-why">{why_it_matters}</div>
          {pattern_html}
          <a class="signal-link" href="{safe_url(signal['source_url'])}"
             target="_blank" rel="noopener noreferrer">Source &rarr;</a>
        </div>
        """,
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


def cluster_label(members: list[dict]) -> str:
    """Name a cluster after the company it's actually about. Institutions are
    skipped: a cluster titled "Gambling Commission" says nothing, since the
    regulator is named in most of the feed."""
    counts = Counter(e for m in members for e in signal_entities(m))
    companies = [(name, n) for name, n in counts.most_common() if not is_excluded(name)]
    if not companies:
        return "Unnamed cluster"
    primary = companies[0][0]
    others = len(companies) - 1
    return f"{primary} +{others} more" if others else primary


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


def render_patterns(signals: list[dict]) -> None:
    scored = [s for s in signals if s.get("newsworthiness_score") is not None]
    grouped = group_by_cluster(scored)

    if not grouped:
        st.info(
            "No emerging patterns yet — a pattern needs two or more signals "
            "naming the same company within the last 90 days."
        )
        return

    heat_threshold = st.slider("Minimum heat score", 0, HEAT_SLIDER_MAX, 50)

    # Clusters are formed on a shared company name, so some are coincidence.
    # Claude is asked to say which; those are dropped outright — a cluster the
    # model has called unrelated is noise the reader shouldn't have to sift.
    coherent = [m for m in grouped.values() if _cluster_verdict(m)["coherent"]]

    clusters = [(compute_heat(members), members) for members in coherent]
    clusters = [c for c in clusters if c[0] >= heat_threshold]
    clusters.sort(key=lambda pair: pair[0], reverse=True)

    st.caption(f"{len(clusters)} of {len(coherent)} clusters meet the heat threshold.")

    if not clusters:
        st.info("No clusters meet the current heat threshold.")
        return

    for heat, members in clusters:
        cluster_id = members[0]["cluster_id"]
        members_sorted = sorted(members, key=lambda m: m["published_at"], reverse=True)
        sources = sorted({m["source"] for m in members})
        source_word = "source" if len(sources) == 1 else "sources"

        # Heat counts only signals above the significance bar, so the header
        # says the same thing — otherwise a cluster padded with routine
        # filings reads as far busier than its heat implies.
        significant = sum(
            1
            for m in members
            if (m.get("newsworthiness_score") or 0) >= SIGNIFICANT_SCORE
        )
        signal_text = (
            f"{significant} of {len(members)} signals"
            if significant != len(members)
            else f"{len(members)} signals"
        )

        # Most-mentioned company rather than alphabetically-first, so a
        # multi-company cluster is labelled by whoever it's actually about.
        label = cluster_label(members)

        pub_dates = sorted(
            datetime.fromisoformat(m["published_at"]).date() for m in members
        )
        span_days = (pub_dates[-1] - pub_dates[0]).days
        span_text = "in a single day" if span_days == 0 else f"over {span_days} days"

        heat_label = heat_tier(heat)[0]
        verdict = _cluster_verdict(members)
        summary = verdict["summary"]

        # Pattern type lives inside rather than in the header: nearly every
        # cluster is a developing story, so leading with it pushed the company
        # name rightwards and told the reader nothing that distinguishes one
        # row from the next.
        header = (
            f"{label} — heat {heat:.0f} ({heat_label}) · {signal_text} · "
            f"{len(sources)} {source_word} · {span_text}"
        )

        with st.expander(header):
            chips = []
            pattern_type = PATTERN_TYPE_LABELS.get(
                verdict["pattern_type"], verdict["pattern_type"]
            )
            if pattern_type:
                chips.append(
                    f'<span class="tag-chip pattern">{html.escape(pattern_type)}</span>'
                )
            if verdict["significance"] is not None:
                chips.append(
                    '<span class="tag-chip">Significance '
                    f'{verdict["significance"]}</span>'
                )
            if chips:
                st.markdown(
                    f'<div class="signal-tags">{"".join(chips)}</div>',
                    unsafe_allow_html=True,
                )

            if summary:
                st.markdown(
                    f"""
                    <div class="cluster-summary">
                      <span class="cluster-summary-label">Signal</span>
                      {html.escape(summary)}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            show_all = st.checkbox(
                f"Show all {len(members)} signals",
                key=f"show_signals_{cluster_id}",
            )
            if show_all:
                for m in members_sorted:
                    render_card(m)


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

    for heat, theme, members in themes:
        companies = sorted(
            {e for m in members for e in signal_entities(m) if not is_excluded(e)},
            key=str.lower,
        )
        members_sorted = sorted(members, key=lambda m: m["published_at"], reverse=True)
        heat_label = theme_heat_tier(heat)[0]

        pub_dates = sorted(
            datetime.fromisoformat(m["published_at"]).date() for m in members
        )
        span_days = (pub_dates[-1] - pub_dates[0]).days
        company_word = "company" if len(companies) == 1 else "companies"

        summary = next(
            (m.get("theme_summary") for m in members if m.get("theme_summary")), None
        )
        key_points = next(
            (m.get("theme_key_points") for m in members if m.get("theme_key_points")),
            [],
        )
        direction = next(
            (m.get("theme_direction") for m in members if m.get("theme_direction")),
            None,
        )

        with st.expander(
            f"{theme} — heat {heat:.0f} ({heat_label}) · {len(members)} signals · "
            f"{len(companies)} {company_word} · over {span_days} days"
        ):
            if summary:
                points_html = ""
                if key_points:
                    items = "".join(
                        f"<li>{html.escape(str(p))}</li>" for p in key_points
                    )
                    points_html = f'<ul class="theme-points">{items}</ul>'
                st.markdown(
                    f"""
                    <div class="cluster-summary">
                      <span class="cluster-summary-label">What's happening</span>
                      {html.escape(summary)}
                      {points_html}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            # Monthly counts are the point of a theme: whether the wave is
            # building or fading is the story, not any single signal.
            per_month = Counter(m["published_at"][:7] for m in members)
            trend = " · ".join(
                f"{month}: {count}" for month, count in sorted(per_month.items())
            )
            direction_html = ""
            if direction in ("building", "steady", "easing"):
                direction_html = (
                    f' &nbsp;<span class="direction-chip direction-{direction}">'
                    f"{html.escape(direction)}</span>"
                )
            st.markdown(f"**By month** — {trend}{direction_html}", unsafe_allow_html=True)

            shown = ", ".join(companies[:12])
            if len(companies) > 12:
                shown += f", and {len(companies) - 12} more"
            st.markdown(f"**Companies** — {shown}")

            if st.checkbox(
                f"Show all {len(members)} signals", key=f"show_theme_{theme}"
            ):
                for m in members_sorted:
                    render_card(m)


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

    render_masthead()

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
