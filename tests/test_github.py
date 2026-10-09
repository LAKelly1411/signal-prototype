import base64
import json
from types import SimpleNamespace

import pytest
import yaml

from dashboard import github
from src.sectors import parse_sector


def resp(status=200, payload=None):
    return SimpleNamespace(status_code=status, json=lambda: payload or {},
                           text=json.dumps(payload or {}))


class FakeHTTP:
    def __init__(self, routes):
        self.routes = routes   # (method, url-suffix) -> resp or callable
        self.calls = []

    def _hit(self, method, url, **kw):
        self.calls.append((method, url, kw))
        for (m, suffix), r in self.routes.items():
            if m == method and url.endswith(suffix):
                return r(kw) if callable(r) else r
        return resp(404)

    def get(self, url, **kw):
        return self._hit("GET", url, **kw)

    def put(self, url, **kw):
        return self._hit("PUT", url, **kw)

    def post(self, url, **kw):
        return self._hit("POST", url, **kw)


def b64(text):
    return base64.b64encode(text.encode()).decode()


CONFIG = {
    "slug": "energy-retail", "name": "Energy retail", "brief": "UK energy.",
    "created_at": "2026-10-08T12:00:00+00:00",
    "prompt": {f: "x" for f in __import__("src.sectors", fromlist=["PROMPT_FIELDS"]).PROMPT_FIELDS},
    "keywords": ["energy"], "companies": [{"name": "Octopus Energy Limited", "company_number": "09263424", "aliases": []}],
    "tickers": {}, "categories": [], "signal_type_fallback": {}, "excluded_bodies": [],
    "sources": {"gazette": {"results_per_term": 20, "sleep_seconds": 1.0}},
}
ENTRY = {"slug": "energy-retail", "name": "Energy retail", "brief": "UK energy.",
         "created_at": "2026-10-08T12:00:00+00:00", "status": "setting_up"}
INDEX = [{"slug": "gambling", "name": "Gambling & gaming", "status": "ready"}]

CFG_PATH = "/contents/config/sectors/energy-retail.yaml"
IDX_PATH = "/contents/data/sectors.json"
DISPATCH = "/actions/workflows/pipeline.yml/dispatches"


def test_sector_yaml_round_trips_and_validates():
    text = github.sector_yaml(CONFIG, "8 October 2026")
    assert text.startswith("# Drafted with Claude from the dashboard on 8 October 2026; reviewed by a user")
    parse_sector(yaml.safe_load(text), "energy-retail")


def test_happy_path_order_and_payloads():
    http = FakeHTTP({
        ("PUT", CFG_PATH): resp(201),
        ("GET", IDX_PATH): resp(200, {"content": b64(json.dumps(INDEX)), "sha": "abc"}),
        ("PUT", IDX_PATH): resp(200),
        ("POST", DISPATCH): resp(204),
    })
    result = github.save_sector(github.GitHub("t", http=http), CONFIG, ENTRY, "8 October 2026")
    assert (result.saved, result.indexed, result.dispatched) == (True, True, True)
    methods = [(m, u.split("/repos/LAKelly1411/signal-prototype")[1]) for m, u, _ in http.calls]
    assert methods == [("GET", CFG_PATH), ("PUT", CFG_PATH), ("GET", IDX_PATH), ("PUT", IDX_PATH), ("POST", DISPATCH)]
    idx_put = http.calls[3][2]["json"]
    assert idx_put["sha"] == "abc" and idx_put["branch"] == "main"
    written = json.loads(base64.b64decode(idx_put["content"]))
    assert [e["slug"] for e in written] == ["energy-retail", "gambling"]
    assert http.calls[4][2]["json"] == {"ref": "main", "inputs": {"sector": ""}}


def test_existing_config_stops_everything():
    http = FakeHTTP({("GET", CFG_PATH): resp(200, {"content": b64("x"), "sha": "s"})})
    result = github.save_sector(github.GitHub("t", http=http), CONFIG, ENTRY, "d")
    assert not result.saved and not result.indexed and not result.dispatched
    assert result.message == "We couldn't save the sector. Please try again."
    assert result.exists
    assert [m for m, _, _ in http.calls] == ["GET"]


def test_config_put_failure_stops_index_and_dispatch():
    http = FakeHTTP({("PUT", CFG_PATH): resp(500)})
    result = github.save_sector(github.GitHub("t", http=http), CONFIG, ENTRY, "d")
    assert not result.saved and not result.indexed and not result.dispatched
    assert result.message == "We couldn't save the sector. Please try again."
    assert not result.exists
    assert [m for m, _, _ in http.calls] == ["GET", "PUT"]


def test_config_put_422_race_stops_everything():
    http = FakeHTTP({("PUT", CFG_PATH): resp(422)})
    result = github.save_sector(github.GitHub("t", http=http), CONFIG, ENTRY, "d")
    assert not result.saved and not result.indexed and not result.dispatched
    assert result.message == "We couldn't save the sector. Please try again."
    assert result.exists  # created between the check and the PUT
    assert [m for m, _, _ in http.calls] == ["GET", "PUT"]


def test_index_get_failure_reports_not_indexed():
    http = FakeHTTP({("PUT", CFG_PATH): resp(201), ("GET", IDX_PATH): resp(500),
                     ("POST", DISPATCH): resp(204)})
    result = github.save_sector(github.GitHub("t", http=http), CONFIG, ENTRY, "d")
    assert result.saved and not result.indexed and result.dispatched
    assert result.message == "Saved. It will appear in the menu after the next update."


def test_non_list_index_is_not_overwritten():
    http = FakeHTTP({
        ("PUT", CFG_PATH): resp(201),
        ("GET", IDX_PATH): resp(200, {"content": b64(json.dumps({"a": 1})), "sha": "abc"}),
        ("POST", DISPATCH): resp(204),
    })
    result = github.save_sector(github.GitHub("t", http=http), CONFIG, ENTRY, "d")
    assert result.saved and not result.indexed and result.dispatched
    assert result.message == "Saved. It will appear in the menu after the next update."
    assert not any(m == "PUT" and u.endswith(IDX_PATH) for m, u, _ in http.calls)


def test_index_conflict_still_dispatches():
    http = FakeHTTP({
        ("PUT", CFG_PATH): resp(201),
        ("GET", IDX_PATH): resp(200, {"content": b64(json.dumps(INDEX)), "sha": "abc"}),
        ("PUT", IDX_PATH): resp(409),
        ("POST", DISPATCH): resp(204),
    })
    result = github.save_sector(github.GitHub("t", http=http), CONFIG, ENTRY, "d")
    assert result.saved and not result.indexed and result.dispatched
    assert result.message == "Saved. It will appear in the menu after the next update."


def test_no_index_file_skips_index_but_dispatches():
    http = FakeHTTP({("PUT", CFG_PATH): resp(201), ("POST", DISPATCH): resp(204)})
    result = github.save_sector(github.GitHub("t", http=http), CONFIG, ENTRY, "d")
    assert result.saved and not result.indexed and result.dispatched


def test_dispatch_failure_message():
    http = FakeHTTP({
        ("PUT", CFG_PATH): resp(201),
        ("GET", IDX_PATH): resp(200, {"content": b64(json.dumps(INDEX)), "sha": "abc"}),
        ("PUT", IDX_PATH): resp(200),
        ("POST", DISPATCH): resp(403),
    })
    result = github.save_sector(github.GitHub("t", http=http), CONFIG, ENTRY, "d")
    assert result.saved and result.indexed and not result.dispatched
    assert result.message == "Saved. Its first update will run with the next scheduled one."


def test_index_entry_not_duplicated():
    existing = INDEX + [ENTRY]
    http = FakeHTTP({
        ("PUT", CFG_PATH): resp(201),
        ("GET", IDX_PATH): resp(200, {"content": b64(json.dumps(existing)), "sha": "abc"}),
        ("PUT", IDX_PATH): resp(200),
        ("POST", DISPATCH): resp(204),
    })
    github.save_sector(github.GitHub("t", http=http), CONFIG, ENTRY, "d")
    written = json.loads(base64.b64decode(http.calls[3][2]["json"]["content"]))
    assert [e["slug"] for e in written].count("energy-retail") == 1


@pytest.mark.parametrize("slug", ["../evil", "Bad Slug", "x\n", "", None])
def test_invalid_slug_never_touches_github(slug):
    http = FakeHTTP({})
    result = github.save_sector(github.GitHub("t", http=http), {**CONFIG, "slug": slug}, ENTRY, "d")
    assert not result.saved and result.message == "We couldn't save the sector. Please try again."
    assert http.calls == []


def test_swallowed_failures_are_logged_without_the_token(caplog):
    http = FakeHTTP({
        ("PUT", CFG_PATH): resp(201),
        ("GET", IDX_PATH): resp(500),
        ("POST", DISPATCH): resp(403),
    })
    with caplog.at_level("ERROR", logger="dashboard.github"):
        github.save_sector(github.GitHub("secret-token", http=http), CONFIG, ENTRY, "d")
    errors = [r for r in caplog.records if r.levelname == "ERROR"]
    assert len(errors) == 2 and all(r.exc_info for r in errors)
    assert "secret-token" not in caplog.text


def test_config_failure_is_logged(caplog):
    http = FakeHTTP({("PUT", CFG_PATH): resp(500)})
    with caplog.at_level("ERROR", logger="dashboard.github"):
        github.save_sector(github.GitHub("secret-token", http=http), CONFIG, ENTRY, "d")
    assert [r.exc_info is not None for r in caplog.records if r.levelname == "ERROR"] == [True]
    assert "secret-token" not in caplog.text
