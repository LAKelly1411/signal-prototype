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

# Score is a magnitude bucketed into tiers, so it gets an ordinal ramp: one hue
# (brand purple), monotone lightness, light->dark mapping low->high newsworthiness.
SCORE_TIERS = [
    (70, "High", "#3d3677", "#ffffff"),
    (40, "Medium", "#6352b9", "#ffffff"),
    (0, "Low", "#d6dcff", "#000000"),
]

# Same ramp, scaled to the heat slider's range rather than a 0-100 score.
# Calibrated against the observed spread once heat stopped counting routine
# filings: there's a clear break at 60 between the busy half of the clusters
# and the quiet half, and 90 isolates the handful worth interrupting someone
# for. Re-check these if the heat formula changes again.
HEAT_TIERS = [
    (90, "High", "#3d3677", "#ffffff"),
    (60, "Medium", "#6352b9", "#ffffff"),
    (0, "Low", "#d6dcff", "#000000"),
]

# Heat is unbounded in principle, but sits well under this in practice; a
# higher ceiling would leave most of the slider's travel unusable. It filters
# on a minimum, so anything above the ceiling still shows.
HEAT_SLIDER_MAX = 120

# Theme heat is on its own scale — it rewards breadth across companies rather
# than source diversity, so a sector-wide wave scores far above any single
# company's cluster. Calibrated separately for that reason.
THEME_HEAT_TIERS = [
    (200, "High", "#3d3677", "#ffffff"),
    (130, "Medium", "#6352b9", "#ffffff"),
    (0, "Low", "#d6dcff", "#000000"),
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
    st.markdown(
        """
        <style>
        html, body, [class*="css"] {
            font-family: 'Greycliff CF', Helvetica, Arial, sans-serif;
        }
        .header-rule {
            height: 4px;
            background: linear-gradient(90deg, #ffcb47, #6352b9);
            border-radius: 2px;
            margin-bottom: 1.25rem;
        }
        .signal-card {
            background-color: #d6dcff26;
            border: 1px solid #d6dcff;
            border-radius: 10px;
            padding: 16px 20px;
            margin-bottom: 14px;
        }
        .signal-card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 12px;
            flex-wrap: wrap;
        }
        .signal-title {
            font-weight: 700;
            font-size: 1.05rem;
            color: #000000;
        }
        .score-badge {
            font-weight: 700;
            font-size: 0.8rem;
            padding: 3px 12px;
            border-radius: 999px;
            white-space: nowrap;
        }
        .signal-meta {
            color: #3d3677;
            font-size: 0.85rem;
            margin-top: 4px;
        }
        .signal-why {
            margin-top: 8px;
            color: #000000;
        }
        .signal-link {
            display: inline-block;
            margin-top: 10px;
            color: #6352b9;
            font-weight: 600;
            text-decoration: none;
        }
        .signal-link:hover {
            text-decoration: underline;
        }
        .signal-tags {
            margin-top: 8px;
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
        }
        .tag-chip {
            display: inline-block;
            background-color: #d6dcff;
            color: #3d3677;
            font-size: 0.75rem;
            font-weight: 600;
            padding: 2px 10px;
            border-radius: 999px;
        }
        .tag-chip.category {
            background-color: #ffe9b3;
            color: #7a5c00;
        }
        .tag-chip.pattern {
            background-color: #3d3677;
            color: #ffffff;
        }
        .theme-points {
            margin: 10px 0 0 0;
            padding-left: 20px;
        }
        .theme-points li {
            margin-bottom: 6px;
            color: #000000;
        }
        .direction-chip {
            display: inline-block;
            font-size: 0.75rem;
            font-weight: 700;
            padding: 2px 10px;
            border-radius: 999px;
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }
        .direction-building { background-color: #fdeaea; color: #8a1c1c; }
        .direction-steady   { background-color: #eceaf7; color: #3d3677; }
        .direction-easing   { background-color: #e6f4ea; color: #1c5c2e; }
        .pattern-badge {
            margin-top: 8px;
            font-size: 0.8rem;
            color: #3d3677;
            font-weight: 600;
        }
        .estimated-date {
            font-style: italic;
            opacity: 0.75;
        }
        .health-strip {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 0.85rem;
            padding: 6px 14px;
            border-radius: 999px;
            margin-bottom: 1rem;
            width: fit-content;
        }
        .health-ok { background-color: #e6f4ea; color: #1c5c2e; }
        .health-warn { background-color: #fff6df; color: #8a6a00; }
        .health-bad { background-color: #fdeaea; color: #8a1c1c; }
        .cluster-summary {
            background-color: #fff6df;
            border-left: 4px solid #ffcb47;
            border-radius: 6px;
            padding: 12px 18px;
            margin-bottom: 16px;
            color: #000000;
        }
        .cluster-summary-label {
            display: block;
            font-weight: 700;
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: #8a6a00;
            margin-bottom: 4px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def check_password() -> bool:
    if st.session_state.get("authenticated"):
        return True

    st.title("Sector Signal")
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
        st.subheader(bucket)
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
    # Claude is asked to say which; those are set aside rather than deleted,
    # since a wrong call should be visible, not silently hidden.
    incoherent = [m for m in grouped.values() if not _cluster_verdict(m)["coherent"]]
    if incoherent:
        show_rejected = st.checkbox(
            f"Include {len(incoherent)} cluster(s) Claude flagged as unrelated",
            value=False,
        )
    else:
        show_rejected = True

    clusters = [
        (compute_heat(members), members)
        for members in grouped.values()
        if show_rejected or _cluster_verdict(members)["coherent"]
    ]
    clusters = [c for c in clusters if c[0] >= heat_threshold]
    clusters.sort(key=lambda pair: pair[0], reverse=True)

    st.caption(f"{len(clusters)} of {len(grouped)} clusters meet the heat threshold.")

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
        if not verdict["coherent"]:
            header = f"⚠ {header}"

        with st.expander(header):
            if not verdict["coherent"]:
                st.warning(
                    "Claude judged these signals unrelated — they share a "
                    "company name rather than a story."
                )

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

    st.title("Sector Signal")
    st.markdown('<div class="header-rule"></div>', unsafe_allow_html=True)
    st.caption("Gambling & gaming sector signals, scored for newsworthiness.")

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
