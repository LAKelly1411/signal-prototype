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
    at.button(key="sectoropt-off-fintech").click().run()
    assert not at.exception
    assert at.session_state["sector"] == "fintech"
    assert "f_min_score" not in at.session_state or at.session_state["f_min_score"] != 70
    assert "wl_name" not in at.session_state or at.session_state["wl_name"] == ""


def test_new_sector_row_is_enabled_below_the_cap(monkeypatch):
    serve(monkeypatch, sector_routes())
    at = app().run()
    assert not at.button(key="sector-new").disabled


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


def _expander_labels(at):
    return [e.proto.label for e in at.get("expander")]


def test_missing_run_status_reserves_the_strip(monkeypatch):
    # No run_status.json for any sector: the header column still gets the
    # strip's (hidden) boxes, so switching sectors doesn't move the page.
    serve(monkeypatch, sector_routes())
    at = app({"sector": "energy"}).run()
    assert not at.exception
    assert "Which sources returned nothing?" in _expander_labels(at)


def test_legacy_without_run_status_reserves_nothing(monkeypatch):
    serve(monkeypatch, {LEGACY_SIGNALS: Resp(payload=GAMBLING)})
    at = app(base=None).run()
    assert not at.exception
    assert "Which sources returned nothing?" not in _expander_labels(at)


def test_sector_row_keys_put_the_state_before_the_slug(monkeypatch):
    # A slug may contain "-off"; the tick CSS keys off the state segment.
    index = INDEX + [{"slug": "offshore-off", "name": "Offshore", "status": "setting_up"}]
    serve(monkeypatch, sector_routes(index))
    at = app().run()
    assert not at.exception
    assert at.button(key="sectoropt-on-gambling")
    assert at.button(key="sectoropt-off-offshore-off")


def _body(at):
    return html.unescape(" ".join(m.value for m in at.markdown))


def test_errored_run_status_shows_failed_not_healthy(monkeypatch):
    index = [dict(INDEX[0], status="error")] + INDEX[1:]
    routes = sector_routes(index)
    routes[BASE + "gambling/run_status.json"] = Resp(payload={
        "sector": "gambling", "finished_at": "2099-01-01T00:00:00+00:00", "error": "boom"})
    serve(monkeypatch, routes)
    at = app().run()
    assert not at.exception
    body = _body(at)
    assert "Last update failed" in body
    assert "all sources healthy" not in body
    assert "The last update didn't finish." in body


NOT_AVAILABLE = "We couldn't load Fintech & payments yet. We'll try again on the next scheduled update."


def test_signals_500_shows_not_available(monkeypatch):
    routes = sector_routes()
    routes[BASE + "fintech/signals.json"] = Resp(500)
    serve(monkeypatch, routes)
    at = app({"sector": "fintech"}).run()
    assert not at.exception
    body = _body(at)
    assert "Not available yet" in body and NOT_AVAILABLE in body


def test_error_status_without_signals_shows_not_available(monkeypatch):
    index = [INDEX[0], dict(INDEX[1], status="error")] + INDEX[2:]
    routes = sector_routes(index)
    del routes[BASE + "fintech/signals.json"]
    serve(monkeypatch, routes)
    at = app({"sector": "fintech"}).run()
    assert not at.exception
    body = _body(at)
    assert "Not available yet" in body and NOT_AVAILABLE in body


def test_markdown_in_a_sector_name_renders_literally(monkeypatch):
    index = INDEX + [{"slug": "odd", "name": "*Odd* [x](javascript:alert(1))", "status": "ready"}]
    serve(monkeypatch, sector_routes(index))
    at = app().run()
    assert not at.exception
    labels = [b.proto.label for b in at.button if b.key and "sectoropt" in b.key]
    odd = [label for label in labels if "Odd" in label]
    assert odd and r"\*Odd\*" in odd[0] and "*Odd*" not in odd[0].replace(r"\*Odd\*", "")


def test_ready_sector_with_empty_file_shows_no_signals_yet(monkeypatch):
    routes = sector_routes()
    routes[BASE + "fintech/signals.json"] = Resp(payload=[])
    serve(monkeypatch, routes)
    at = app({"sector": "fintech"}).run()
    assert not at.exception
    body = " ".join(html.unescape(m.value) for m in at.markdown)
    assert "Fintech & payments is set up, but nothing has come through yet." in body


def test_index_server_error_falls_back_for_this_run(monkeypatch):
    routes = sector_routes()
    routes[BASE + "sectors.json"] = Resp(500)
    routes[LEGACY_SIGNALS] = Resp(payload=GAMBLING)
    serve(monkeypatch, routes)
    at = app().run()
    assert not at.exception and at.tabs


from src import drafting as drafting_mod  # noqa: E402
from dashboard import github as github_mod  # noqa: E402

DRAFT = drafting_mod.Draft(
    slug="energy-retail",
    config={"slug": "energy-retail", "name": "Energy retail", "brief": "UK energy.",
            "created_at": "2026-10-08T12:00:00+00:00",
            "prompt": {f: "x" for f in __import__("src.sectors", fromlist=["PROMPT_FIELDS"]).PROMPT_FIELDS},
            "keywords": ["energy"], "companies": [
                {"name": "Octopus Energy Limited", "company_number": "09263424", "aliases": []},
                {"name": "OVO Energy Ltd", "company_number": None, "aliases": []},
                {"name": "E.ON UK plc", "company_number": None, "aliases": []}],
            "tickers": {}, "categories": [], "signal_type_fallback": {}, "excluded_bodies": [],
            "sources": {"gazette": {"results_per_term": 20, "sleep_seconds": 1.0}}},
    companies=[{"name": "Octopus Energy Limited", "company_number": "09263424", "aliases": [], "verified": True},
               {"name": "OVO Energy Ltd", "company_number": None, "aliases": [], "verified": False},
               {"name": "E.ON UK plc", "company_number": None, "aliases": [], "verified": False}],
)


def creation_app(monkeypatch, *, anthropic=True, token=True, save=None, draft=None):
    serve(monkeypatch, sector_routes())
    monkeypatch.setattr(drafting_mod, "draft_sector", draft or (lambda *a, **k: DRAFT))
    saved = []

    def fake_save(gh, config, entry, today):
        saved.append((dict(config), entry))
        if callable(save):
            return save(len(saved))
        return save or github_mod.SaveResult(True, True, True, "")
    monkeypatch.setattr(github_mod, "save_sector", fake_save)
    at = app()
    if anthropic:
        at.secrets["ANTHROPIC_API_KEY"] = "k"
    if token:
        at.secrets["GITHUB_TOKEN"] = "t"
    return at, saved


def _to_review(at):
    at.run()
    at.button(key="sector-new").click().run()
    at.button(key="ns-unlock").click().run()
    at.text_area(key="ns_description").input("UK energy suppliers and their regulators").run()
    at.button(key="ns-draft").click().run()


def test_full_creation_flow(monkeypatch):
    at, saved = creation_app(monkeypatch)
    at.run()
    at.button(key="sector-new").click().run()
    assert any("Track any industry" in m.value for m in at.markdown)
    at.button(key="ns-unlock").click().run()
    at.text_area(key="ns_description").input("UK energy suppliers and their regulators").run()
    at.button(key="ns-draft").click().run()
    assert not at.exception
    assert at.text_input(key="ns_name").value == "Energy retail"
    at.button(key="ns-create").click().run()
    assert not at.exception
    assert saved and saved[0][1]["status"] == "setting_up"
    assert saved[0][0]["companies"][0]["company_number"] is None  # no CH key: re-verify clears it
    body = " ".join(html.unescape(m.value) for m in at.markdown)
    assert "Energy retail is being set up. We're gathering the first signals; " \
        "this usually takes under an hour." in body
    at.button(key="ns-done").click().run()
    assert not at.exception
    assert at.session_state["sector"] == "energy-retail"
    assert "We're gathering the first signals for Energy retail." in " ".join(
        html.unescape(m.value) for m in at.markdown)
    assert not any(b.key == "ns-done" for b in at.button)  # the dialog closed


def test_done_reruns_the_whole_app(monkeypatch):
    # Done sits inside the dialog, and a widget in a dialog reruns only the
    # dialog (it's a fragment): without a full rerun the dialog redraws at the
    # upsell and the page stays on the old sector. AppTest always reruns the
    # whole script, so check that Done asks for an app-scope rerun.
    at, _ = creation_app(monkeypatch)
    _to_review(at)
    at.button(key="ns-create").click().run()
    scopes, real = [], st.rerun

    def spy(*args, **kwargs):
        scopes.append(kwargs.get("scope", "app"))
        return real(*args, **kwargs)
    monkeypatch.setattr(st, "rerun", spy)
    at.button(key="ns-done").click().run()
    assert not at.exception
    assert scopes == ["app"]


def test_unlock_is_per_session(monkeypatch):
    at, _ = creation_app(monkeypatch)
    at.run()
    at.button(key="sector-new").click().run()
    at.button(key="ns-unlock").click().run()
    assert at.session_state["premium_unlocked"] is True
    fresh, _ = creation_app(monkeypatch)
    fresh.run()
    assert "premium_unlocked" not in fresh.session_state or not fresh.session_state["premium_unlocked"]


def test_no_anthropic_key_disables_drafting(monkeypatch):
    at, _ = creation_app(monkeypatch, anthropic=False)
    at.run()
    at.button(key="sector-new").click().run()
    at.button(key="ns-unlock").click().run()
    assert at.button(key="ns-draft").disabled
    assert any("Drafting isn't switched on here yet." in i.value for i in at.info)


def test_draft_limit(monkeypatch):
    at, _ = creation_app(monkeypatch)
    at.session_state["ns_drafts_used"] = 5
    at.session_state["premium_unlocked"] = True
    at.run()
    at.button(key="sector-new").click().run()
    assert at.button(key="ns-draft").disabled
    assert any("You've reached the demo's draft limit." in c.value for c in at.caption)


def test_sector_cap_disables_the_row(monkeypatch):
    index = [{"slug": f"s{i}", "name": f"S{i}", "status": "ready"} for i in range(9)] + INDEX[:1]
    serve(monkeypatch, sector_routes(index))
    at = app().run()
    btn = at.button(key="sector-new")
    assert btn.disabled and "Sector limit reached" in btn.proto.label


def test_save_failure_keeps_the_review(monkeypatch):
    at, _ = creation_app(monkeypatch, save=github_mod.SaveResult(False, False, False,
                                                                 "We couldn't save the sector. Please try again."))
    _to_review(at)
    at.button(key="ns-create").click().run()
    assert any("We couldn't save the sector. Please try again." in e.value for e in at.error)
    assert at.session_state["ns_step"] == "review"


def test_partial_save_message_is_shown_on_done(monkeypatch):
    msg = "Saved. It will appear in the menu after the next update."
    at, _ = creation_app(monkeypatch, save=github_mod.SaveResult(True, False, False, msg))
    _to_review(at)
    at.button(key="ns-create").click().run()
    assert not at.exception
    assert msg in _body(at)


@pytest.mark.parametrize("exc", [drafting_mod.DraftError("bad"), RuntimeError("api down"),
                                 requests.ConnectionError("no network")])
def test_draft_failure_shows_the_message(monkeypatch, exc):
    def boom(*a, **k):
        raise exc
    at, _ = creation_app(monkeypatch, draft=boom)
    _to_review(at)
    assert not at.exception
    assert any("We couldn't draft that one. Try describing it differently." in e.value for e in at.error)
    assert at.session_state["ns_step"] == "describe"


def test_short_description_shows_the_length_message(monkeypatch):
    def too_short(*a, **k):
        raise ValueError("description must be 10-300 characters")
    at, _ = creation_app(monkeypatch, draft=too_short)
    _to_review(at)
    assert any("Please describe the industry in 10 to 300 characters." in e.value for e in at.error)


def test_no_github_token_disables_create(monkeypatch):
    at, _ = creation_app(monkeypatch, token=False)
    _to_review(at)
    assert at.button(key="ns-create").disabled
    assert any("Saving isn't switched on here yet." in i.value for i in at.info)


def test_client_construction_error_shows_draft_failed(monkeypatch):
    import anthropic

    def broken(*a, **k):
        raise RuntimeError("bad client")
    monkeypatch.setattr(anthropic, "Anthropic", broken)
    at, _ = creation_app(monkeypatch)
    _to_review(at)
    assert not at.exception
    assert any("We couldn't draft that one. Try describing it differently." in e.value for e in at.error)


def test_one_draft_counts_once_on_a_cold_cache(monkeypatch):
    at, _ = creation_app(monkeypatch)
    _to_review(at)
    assert at.session_state["ns_drafts_used"] == 1


def test_review_table_ticks_only_verified_numbers(monkeypatch):
    def table(at):
        return at.get("dataframe")[0].value.to_dict("records")

    at, _ = creation_app(monkeypatch)
    _to_review(at)
    assert [r["Verified"] for r in table(at)] == ["✓", "–", "–"]
    # An edit folded into the canonical rows (what the editor's on_change
    # does; AppTest can't drive the editor itself) clears the tick.
    rows = [dict(r) for r in at.session_state["ns_company_rows"]]
    rows[0]["company_number"] = "12345678"
    at.session_state["ns_company_rows"] = rows
    at.run()
    assert not at.exception
    assert table(at)[0] == {"Name": "Octopus Energy Limited",
                            "Companies House number": "12345678", "Verified": "–"}


def _at_review(at, **state):
    """Straight to the review step, as if a draft had just come back."""
    at.session_state["premium_unlocked"] = True
    at.session_state["ns_open"] = True
    at.session_state["ns_step"] = "review"
    at.session_state["ns_draft"] = DRAFT
    at.session_state["ns_company_rows"] = [dict(c) for c in DRAFT.config["companies"]]
    for key, value in state.items():
        at.session_state[key] = value
    return at.run()


def _checkout_slugs():
    from src.sectors import list_sector_slugs
    return list_sector_slugs()


def _pending(n):
    return [{"slug": f"p{i}", "name": f"P{i}", "status": "setting_up"} for i in range(n)]


def test_create_refuses_at_the_cap_even_when_the_index_fails(monkeypatch):
    at, saved = creation_app(monkeypatch)
    serve(monkeypatch, {BASE + "sectors.json": Resp(500), LEGACY_SIGNALS: Resp(payload=GAMBLING)})
    # The checkout's configs plus enough created this session to reach ten.
    _at_review(at, pending_sectors=_pending(10 - len(_checkout_slugs())))
    assert at.button(key="sector-new").disabled  # the menu counts the same union
    at.button(key="ns-create").click().run()
    assert not at.exception
    assert any("Contact us to add more sectors." in e.value for e in at.error)
    assert saved == []


def test_create_below_the_cap_with_a_failed_index_still_saves(monkeypatch):
    at, saved = creation_app(monkeypatch)
    serve(monkeypatch, {BASE + "sectors.json": Resp(500), LEGACY_SIGNALS: Resp(payload=GAMBLING)})
    _at_review(at, pending_sectors=_pending(9 - len(_checkout_slugs())))
    assert not at.button(key="sector-new").disabled
    at.button(key="ns-create").click().run()
    assert len(saved) == 1


@pytest.mark.parametrize("state,message", [
    ({"ns_keywords": []}, "Add at least one keyword."),
    ({"ns_company_rows": DRAFT.config["companies"][:2]}, "Keep between 3 and 12 companies."),
    ({f"ns_src_{s}": False for s in drafting_mod.GENERIC_SOURCES}, "Choose at least one source."),
])
def test_incomplete_review_is_not_saved(monkeypatch, state, message):
    at, saved = creation_app(monkeypatch)
    _to_review(at)
    for key, value in state.items():
        at.session_state[key] = value
    at.run()
    at.button(key="ns-create").click().run()
    assert any(message in e.value for e in at.error)
    assert saved == [] and at.session_state["ns_step"] == "review"


def test_slug_taken_mid_review_retries_with_the_next_slug(monkeypatch):
    def save(attempt):
        if attempt == 1:
            return github_mod.SaveResult(False, False, False, github_mod.MSG_NOT_SAVED, exists=True)
        return github_mod.SaveResult(True, True, True, "")
    at, saved = creation_app(monkeypatch, save=save)
    _to_review(at)
    at.button(key="ns-create").click().run()
    assert not at.exception
    assert [c["slug"] for c, _ in saved] == ["energy-retail", "energy-retail-2"]
    assert saved[1][1]["slug"] == "energy-retail-2"
    assert at.session_state["ns_step"] == "done"
    assert at.session_state["ns_result"]["slug"] == "energy-retail-2"


def test_slug_taken_twice_asks_to_try_again(monkeypatch):
    taken = github_mod.SaveResult(False, False, False, github_mod.MSG_NOT_SAVED, exists=True)
    at, saved = creation_app(monkeypatch, save=lambda attempt: taken)
    _to_review(at)
    at.button(key="ns-create").click().run()
    assert len(saved) == 2
    assert any("That name was just taken. Please try again." in e.value for e in at.error)
    assert at.session_state["ns_step"] == "review"


def test_other_save_failures_are_not_retried(monkeypatch):
    at, saved = creation_app(monkeypatch, save=github_mod.SaveResult(False, False, False,
                                                                     github_mod.MSG_NOT_SAVED))
    _to_review(at)
    at.button(key="ns-create").click().run()
    assert len(saved) == 1
    assert any(github_mod.MSG_NOT_SAVED in e.value for e in at.error)


@pytest.mark.parametrize("name,slug", [("Wind power", "wind-power"), ("Gambling", "gambling-2"),
                                       ("Energy retail", "energy-retail")])
def test_renamed_in_review_gets_a_fresh_unique_slug(monkeypatch, name, slug):
    at, saved = creation_app(monkeypatch)  # the index already has gambling
    _to_review(at)
    at.text_input(key="ns_name").input(name).run()
    at.button(key="ns-create").click().run()
    assert not at.exception
    assert saved[0][0]["slug"] == slug and saved[0][1]["slug"] == slug


def test_saved_sector_is_selected_before_done(monkeypatch):
    at, _ = creation_app(monkeypatch)
    _to_review(at)
    at.button(key="ns-create").click().run()
    assert at.query_params["sector"] == ["energy-retail"]
    # Dismissed with X or Escape rather than Done: the page is already on it.
    at.session_state["ns_open"] = False
    at.run()
    assert not at.exception
    assert at.session_state["sector"] == "energy-retail"


def test_bedrock_profile_drafts_without_an_api_key(monkeypatch):
    import anthropic
    calls, drafts = [], []
    monkeypatch.setattr(anthropic, "AnthropicBedrock", lambda **kw: calls.append(kw) or object())
    monkeypatch.setattr(anthropic, "Anthropic", lambda **kw: pytest.fail("direct API used"))
    at, _ = creation_app(monkeypatch, anthropic=False,
                         draft=lambda *a, **k: drafts.append(k.get("model")) or DRAFT)
    at.secrets["BEDROCK_AWS_PROFILE"] = "aie-dev"
    _to_review(at)
    assert not at.exception
    assert calls == [{"aws_profile": "aie-dev", "aws_region": "eu-west-1",
                      "max_retries": 1, "timeout": 60}]
    assert drafts == ["eu.anthropic.claude-sonnet-5-5"]
    assert at.text_input(key="ns_name").value == "Energy retail"


def test_bedrock_model_and_region_can_be_overridden(monkeypatch):
    import anthropic
    calls, drafts = [], []
    monkeypatch.setattr(anthropic, "AnthropicBedrock", lambda **kw: calls.append(kw) or object())
    at, _ = creation_app(monkeypatch, draft=lambda *a, **k: drafts.append(k.get("model")) or DRAFT)
    at.secrets["BEDROCK_AWS_PROFILE"] = "aie-stage"
    at.secrets["BEDROCK_AWS_REGION"] = "eu-central-1"
    at.secrets["BEDROCK_MODEL"] = "eu.anthropic.claude-opus-5-5"
    _to_review(at)
    assert calls[0]["aws_profile"] == "aie-stage" and calls[0]["aws_region"] == "eu-central-1"
    assert drafts == ["eu.anthropic.claude-opus-5-5"]


def test_anthropic_client_retries_once_with_a_timeout(monkeypatch):
    import anthropic
    calls = []
    monkeypatch.setattr(anthropic, "Anthropic", lambda **kw: calls.append(kw) or object())
    at, _ = creation_app(monkeypatch)
    _to_review(at)
    assert calls == [{"api_key": "k", "max_retries": 1, "timeout": 60}]


def test_draft_failure_is_logged(monkeypatch, caplog):
    def boom(*a, **k):
        raise RuntimeError("api down")
    at, _ = creation_app(monkeypatch, draft=boom)
    with caplog.at_level("ERROR"):
        _to_review(at)
    records = [r for r in caplog.records if r.levelname == "ERROR" and r.exc_info]
    assert records and "api down" in caplog.text


def test_create_failure_is_logged(monkeypatch, caplog):
    at, saved = creation_app(monkeypatch)
    _to_review(at)

    def broken(*a, **k):
        raise RuntimeError("bad config")
    monkeypatch.setattr(drafting_mod, "verify_companies", broken)
    with caplog.at_level("ERROR"):
        at.button(key="ns-create").click().run()
    assert saved == []
    assert any(r.exc_info and "bad config" in str(r.exc_info[1]) for r in caplog.records)
