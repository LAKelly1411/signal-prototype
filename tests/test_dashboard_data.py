import json
from types import SimpleNamespace

import pytest
import requests

from dashboard import data

BASE = "https://raw.example/data/"


class Resp:
    def __init__(self, status=200, payload=None, text=None):
        self.status_code = status
        self._payload = payload
        self._text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")

    def json(self):
        if self._text is not None:
            return json.loads(self._text)
        return self._payload


@pytest.fixture
def web(monkeypatch):
    routes: dict[str, Resp] = {}
    calls: list[str] = []

    def fake_get(url, timeout=None, **kw):
        calls.append(url)
        if url in routes:
            return routes[url]
        return Resp(404)

    monkeypatch.setattr(requests, "get", fake_get)
    return SimpleNamespace(routes=routes, calls=calls)


INDEX = [
    {"slug": "fintech", "name": "Fintech & payments", "status": "setting_up"},
    {"slug": "gambling", "name": "Gambling & gaming", "status": "ready", "signal_count": 336},
]


class TestLoadIndex:
    def test_reads_the_index(self, web):
        web.routes[BASE + "sectors.json"] = Resp(payload=INDEX)
        assert data.load_index(BASE) == INDEX

    def test_unset_base_means_no_index(self, web):
        assert data.load_index(None) is None and data.load_index("") is None
        assert web.calls == []

    def test_missing_index_means_fallback(self, web):
        assert data.load_index(BASE) is None

    def test_bad_json_means_fallback(self, web):
        web.routes[BASE + "sectors.json"] = Resp(text="{not json")
        assert data.load_index(BASE) is None

    def test_wrong_shape_means_fallback(self, web):
        web.routes[BASE + "sectors.json"] = Resp(payload={"slug": "gambling"})
        assert data.load_index(BASE) is None


class TestLoadSignals:
    def test_reads_the_sector_file(self, web):
        web.routes[BASE + "fintech/signals.json"] = Resp(payload=[{"id": "a"}])
        assert data.load_signals(BASE, "fintech") == [{"id": "a"}]

    def test_404_is_empty_not_an_error(self, web):
        assert data.load_signals(BASE, "fintech") == []

    def test_other_failures_raise_data_error(self, web):
        web.routes[BASE + "fintech/signals.json"] = Resp(500)
        with pytest.raises(data.DataError):
            data.load_signals(BASE, "fintech")

    def test_bad_json_raises_data_error(self, web):
        web.routes[BASE + "fintech/signals.json"] = Resp(text="nope")
        with pytest.raises(data.DataError):
            data.load_signals(BASE, "fintech")

    def test_run_status_failure_is_none(self, web):
        assert data.load_run_status(BASE, "fintech") is None
        web.routes[BASE + "fintech/run_status.json"] = Resp(payload={"live_signals": 3})
        assert data.load_run_status(BASE, "fintech") == {"live_signals": 3}


class TestLegacy:
    def test_legacy_signals(self, web):
        web.routes["https://raw.example/data/signals.json"] = Resp(payload=[{"id": "x"}])
        assert data.load_legacy_signals("https://raw.example/data/signals.json") == [{"id": "x"}]

    def test_legacy_signals_failure_raises(self, web):
        with pytest.raises(data.DataError):
            data.load_legacy_signals("https://raw.example/data/signals.json")

    def test_legacy_status_optional(self, web):
        assert data.load_legacy_status(None) is None
        assert data.load_legacy_status("https://raw.example/data/run_status.json") is None


class TestSelection:
    def test_order_puts_gambling_first_then_slug(self):
        entries = [{"slug": "zeta"}, {"slug": "fintech"}, {"slug": "gambling"}]
        assert [e["slug"] for e in data.order_index(entries)] == ["gambling", "fintech", "zeta"]

    def test_order_drops_invalid_slugs(self):
        entries = [{"slug": "gambling"}, {"slug": "../x"}, {"slug": "Bad"}, {"name": "no slug"}]
        assert [e["slug"] for e in data.order_index(entries)] == ["gambling"]

    def test_order_drops_non_dict_entries(self):
        entries = ["gambling", None, 3, {"slug": "fintech"}]
        assert [e["slug"] for e in data.order_index(entries)] == ["fintech"]

    def test_all_invalid_index_orders_to_empty(self):
        assert data.order_index(["gambling", None]) == []
        assert data.order_index([{"slug": "../x"}, {"slug": "Bad"}]) == []

    def test_pick_sector_on_empty_raises_value_error(self):
        with pytest.raises(ValueError):
            data.pick_sector([], "gambling")

    @pytest.mark.parametrize("requested", [None, "", "nope", "../x", "GAMBLING", "fintech/", "gambling\n"])
    def test_unknown_request_falls_back_to_gambling(self, requested):
        assert data.pick_sector(data.order_index(INDEX), requested) == "gambling"

    def test_known_request_wins(self):
        assert data.pick_sector(data.order_index(INDEX), "fintech") == "fintech"

    def test_falls_back_to_first_without_gambling(self):
        entries = [{"slug": "fintech"}, {"slug": "energy"}]
        assert data.pick_sector(data.order_index(entries), "nope") == "energy"

    def test_notes(self):
        assert data.sector_note({"status": "ready", "signal_count": 336}) == "336"
        assert data.sector_note({"status": "setting_up"}) == "Setting up…"
        assert data.sector_note({"status": "error"}) == "Update failed"
        assert data.sector_note({"status": "ready"}) == ""


class TestViewState:
    @pytest.mark.parametrize("entry,signals,expected", [
        ({"status": "ready"}, [{"id": "a"}], "ready"),
        ({"status": "ready"}, [], "setting_up"),          # index says ready, file not there yet
        ({"status": "setting_up"}, [], "setting_up"),
        ({"status": "setting_up"}, [{"id": "a"}], "ready"),
        ({"status": "error"}, [{"id": "a"}], "error_with_data"),
        ({"status": "error"}, [], "error_empty"),
        ({}, [{"id": "a"}], "ready"),
    ])
    def test_states(self, entry, signals, expected):
        assert data.view_state(entry, signals) == expected


class TestRulesAndPaths:
    def test_rules_for_a_configured_sector(self):
        assert data.sector_rules("gambling").slug == "gambling"

    def test_rules_fall_back_to_gambling_without_a_config(self):
        assert data.sector_rules("no-such-sector").slug == "gambling"

    def test_watchlist_path(self):
        assert data.user_watchlist_path("fintech") == "config/sectors/fintech.user.yaml"

    @pytest.mark.parametrize("slug", ["../gambling", "Fintech", "", "a/b", "gambling\n"])
    def test_watchlist_path_rejects_bad_slugs(self, slug):
        with pytest.raises(ValueError):
            data.user_watchlist_path(slug)

    def test_sector_rules_guards_an_invalid_slug(self):
        assert data.sector_rules("../gambling").slug == "gambling"
        assert data.sector_rules("gambling\n").slug == "gambling"


class TestSinkGuards:
    def test_load_signals_rejects_invalid_slug_without_fetching(self, web):
        with pytest.raises(data.DataError):
            data.load_signals(BASE, "../gambling")
        assert web.calls == []

    def test_load_run_status_rejects_invalid_slug_without_fetching(self, web):
        web.routes[BASE + "../gambling/run_status.json"] = Resp(payload={"live_signals": 1})
        assert data.load_run_status(BASE, "../gambling") is None
        assert web.calls == []


class TestBaseNormalisation:
    @pytest.mark.parametrize("base", [BASE, BASE.rstrip("/")])
    def test_index_signals_and_status_work_with_or_without_slash(self, web, base):
        web.routes[BASE + "sectors.json"] = Resp(payload=INDEX)
        web.routes[BASE + "fintech/signals.json"] = Resp(payload=[{"id": "a"}])
        web.routes[BASE + "fintech/run_status.json"] = Resp(payload={"ok": 1})
        assert data.load_index(base) == INDEX
        assert data.load_signals(base, "fintech") == [{"id": "a"}]
        assert data.load_run_status(base, "fintech") == {"ok": 1}

    def test_blank_base_is_unset(self, web):
        assert data.load_index("  ") is None
