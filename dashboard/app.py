import requests
import streamlit as st

st.set_page_config(page_title="PA Sector Signal — SBC Media", layout="wide")


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


def render_feed(signals: list[dict]) -> None:
    st.title("PA Sector Signal — SBC Media")
    st.caption("Gambling & gaming sector signals, scored for newsworthiness.")

    scored = [s for s in signals if s.get("newsworthiness_score") is not None]
    scored.sort(key=lambda s: s["published_at"], reverse=True)

    if not scored:
        st.info("No scored signals yet — check back after the next pipeline run.")
        return

    for signal in scored:
        with st.container(border=True):
            st.markdown(f"**{signal['title']}**")
            st.caption(
                f"{signal['source']} · {signal['published_at'][:10]} · "
                f"score {signal['newsworthiness_score']}"
            )
            if signal.get("why_it_matters"):
                st.write(signal["why_it_matters"])
            st.markdown(f"[Source]({signal['source_url']})")


def main() -> None:
    if not check_password():
        return
    signals = load_signals()
    render_feed(signals)


main()
