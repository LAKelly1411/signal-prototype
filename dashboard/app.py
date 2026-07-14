import base64
import html
from datetime import datetime

import requests
import streamlit as st
import yaml

st.set_page_config(page_title="PA Sector Signal", layout="wide")

GITHUB_OWNER = "LAKelly1411"
GITHUB_REPO = "signal-prototype"
USER_WATCHLIST_PATH = "config/user_watchlist.yaml"

# Score is a magnitude bucketed into tiers, so it gets an ordinal ramp: one hue
# (PA purple), monotone lightness, light->dark mapping low->high newsworthiness.
SCORE_TIERS = [
    (70, "High", "#3d3677", "#ffffff"),
    (40, "Medium", "#6352b9", "#ffffff"),
    (0, "Low", "#d6dcff", "#000000"),
]


def score_tier(score: int) -> tuple[str, str, str]:
    for threshold, label, bg, fg in SCORE_TIERS:
        if score >= threshold:
            return label, bg, fg
    return SCORE_TIERS[-1][1:]


def inject_css() -> None:
    st.markdown(
        """
        <style>
        html, body, [class*="css"] {
            font-family: 'Greycliff CF', Helvetica, Arial, sans-serif;
        }
        .pa-header-rule {
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
        </style>
        """,
        unsafe_allow_html=True,
    )


def check_password() -> bool:
    if st.session_state.get("authenticated"):
        return True

    st.title("PA Sector Signal")
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


def render_card(signal: dict) -> None:
    label, bg, fg = score_tier(signal["newsworthiness_score"])
    why_it_matters = html.escape(signal.get("why_it_matters") or "")

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
            {html.escape(signal['source'])} &middot; {signal['published_at'][:10]}
          </div>
          <div class="signal-why">{why_it_matters}</div>
          <a class="signal-link" href="{signal['source_url']}" target="_blank">Source &rarr;</a>
        </div>
        """,
        unsafe_allow_html=True,
    )


def apply_filters(scored: list[dict]) -> list[dict]:
    st.sidebar.header("Filters")

    sources = sorted({s["source"] for s in scored})
    selected_sources = st.sidebar.multiselect("Source", sources, default=sources)

    signal_types = sorted({s["signal_type"] for s in scored if s.get("signal_type")})
    selected_types = st.sidebar.multiselect(
        "Signal type", signal_types, default=signal_types
    )

    min_score = st.sidebar.slider("Minimum score", 0, 100, 0)

    published_dates = [
        datetime.fromisoformat(s["published_at"]).date() for s in scored
    ]
    min_date, max_date = min(published_dates), max(published_dates)
    date_range = st.sidebar.date_input(
        "Date range", value=(min_date, max_date), min_value=min_date, max_value=max_date
    )
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date, end_date = min_date, max_date

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
        filtered.append(signal)
    return filtered


def render_feed(signals: list[dict]) -> None:
    st.title("PA Sector Signal")
    st.markdown('<div class="pa-header-rule"></div>', unsafe_allow_html=True)
    st.caption("Gambling & gaming sector signals, scored for newsworthiness.")

    scored = [s for s in signals if s.get("newsworthiness_score") is not None]
    scored.sort(key=lambda s: s["published_at"], reverse=True)

    if not scored:
        st.info("No scored signals yet — check back after the next pipeline run.")
        return

    filtered = apply_filters(scored)
    st.caption(f"Showing {len(filtered)} of {len(scored)} scored signals.")

    if not filtered:
        st.info("No signals match the current filters.")
        return

    for signal in filtered:
        render_card(signal)


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
                            "Couldn't save that addition — please flag it to the PA team."
                        )


def main() -> None:
    inject_css()
    if not check_password():
        return
    render_watchlist_form()
    signals = load_signals()
    render_feed(signals)


main()
