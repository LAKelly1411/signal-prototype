import html
import json
from pathlib import Path

import pytest
import requests
import streamlit as st
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "tests" / "fixtures" / "dashboard"
BASE = "https://raw.example/data/"
LEGACY_SIGNALS = "https://raw.example/legacy/signals.json"

GAMBLING = json.loads((FIX / "gambling_signals.json").read_text())
FINTECH = json.loads((FIX / "fintech_signals.json").read_text())

INDEX = [
    {"slug": "gambling", "name": "Gambling & gaming", "status": "ready", "signal_count": len(GAMBLING)},
    {"slug": "fintech", "name": "Fintech & payments", "status": "ready", "signal_count": len(FINTECH)},
    {"slug": "energy", "name": "Energy retail", "status": "setting_up"},
]


class Resp:
    def __init__(self, status=200, payload=None):
        self.status_code, self._payload = status, payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))

    def json(self):
        return self._payload


def serve(monkeypatch, routes):
    def fake_get(url, timeout=None, **kw):
        return routes.get(url, Resp(404))
    monkeypatch.setattr(requests, "get", fake_get)


@pytest.fixture(autouse=True)
def _fresh_caches(monkeypatch):
    # The app imports `dashboard` and `src` as top-level packages; AppTest runs
    # it in this process, so the repo root has to be importable.
    monkeypatch.syspath_prepend(str(ROOT))
    st.cache_data.clear()
    st.cache_resource.clear()
    yield


def app(query=None, base=BASE):
    at = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=30)
    at.secrets["DASHBOARD_PASSWORD"] = "x"
    at.secrets["DATA_RAW_URL"] = LEGACY_SIGNALS
    if base:
        at.secrets["DATA_BASE_URL"] = base
    at.session_state["authenticated"] = True
    if query:
        at.query_params.update(query)
    return at


def sector_routes(index=INDEX):
    return {
        BASE + "sectors.json": Resp(payload=index),
        BASE + "gambling/signals.json": Resp(payload=GAMBLING),
        BASE + "fintech/signals.json": Resp(payload=FINTECH),
    }


def popover_label(at):
    return at.get("popover")[0].proto.popover.label


def test_defaults_to_gambling(monkeypatch):
    serve(monkeypatch, sector_routes())
    at = app().run()
    assert not at.exception
    assert at.session_state["sector"] == "gambling"
    assert popover_label(at) == "Gambling & gaming"


def test_query_param_selects_fintech(monkeypatch):
    serve(monkeypatch, sector_routes())
    at = app({"sector": "fintech"}).run()
    assert not at.exception
    assert at.session_state["sector"] == "fintech"


@pytest.mark.parametrize("bad", ["nope", "../gambling", "FINTECH"])
def test_unknown_or_crafted_slug_falls_back(monkeypatch, bad):
    serve(monkeypatch, sector_routes())
    at = app({"sector": bad}).run()
    assert not at.exception and at.session_state["sector"] == "gambling"


def test_setting_up_sector_shows_the_block(monkeypatch):
    serve(monkeypatch, sector_routes())
    at = app({"sector": "energy"}).run()
    assert not at.exception
    body = html.unescape(" ".join(m.value for m in at.markdown))
    assert "We're gathering the first signals for Energy retail." in body
    assert not at.tabs  # tabs replaced by the state block


def test_error_with_data_shows_the_notice(monkeypatch):
    index = [dict(INDEX[0], status="error")] + INDEX[1:]
    serve(monkeypatch, sector_routes(index))
    at = app().run()
    assert not at.exception
    assert any("The last update didn't finish." in html.unescape(m.value) for m in at.markdown)
    assert at.tabs


def test_switching_clears_filters(monkeypatch):
    serve(monkeypatch, sector_routes())
    at = app().run()
    at.session_state["f_min_score"] = 70
    at.session_state["wl_name"] = "Half-typed Ltd"
    at.button(key="sectoropt-fintech-off").click().run()
    assert not at.exception
    assert at.session_state["sector"] == "fintech"
    assert "f_min_score" not in at.session_state or at.session_state["f_min_score"] != 70
    assert "wl_name" not in at.session_state or at.session_state["wl_name"] == ""


def test_new_sector_row_is_disabled(monkeypatch):
    serve(monkeypatch, sector_routes())
    at = app().run()
    assert at.button(key="sector-new").disabled


def test_falls_back_to_legacy_without_index(monkeypatch):
    serve(monkeypatch, {LEGACY_SIGNALS: Resp(payload=GAMBLING)})
    at = app().run()
    assert not at.exception
    assert at.session_state["sector"] == "gambling"
    assert at.tabs


def test_legacy_when_base_unset(monkeypatch):
    serve(monkeypatch, {LEGACY_SIGNALS: Resp(payload=GAMBLING)})
    at = app(base=None).run()
    assert not at.exception and at.tabs
