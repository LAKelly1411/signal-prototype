import html

import requests
import streamlit as st

st.set_page_config(page_title="PA Sector Signal", layout="wide")

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


def render_feed(signals: list[dict]) -> None:
    st.title("PA Sector Signal")
    st.markdown('<div class="pa-header-rule"></div>', unsafe_allow_html=True)
    st.caption("Gambling & gaming sector signals, scored for newsworthiness.")

    scored = [s for s in signals if s.get("newsworthiness_score") is not None]
    scored.sort(key=lambda s: s["published_at"], reverse=True)

    if not scored:
        st.info("No scored signals yet — check back after the next pipeline run.")
        return

    for signal in scored:
        render_card(signal)


def main() -> None:
    inject_css()
    if not check_password():
        return
    signals = load_signals()
    render_feed(signals)


main()
