from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from src import drafting
from src.sectors import PROMPT_FIELDS, parse_sector

NOW = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)


def proposal(**over):
    base = {
        "name": "Energy retail",
        "brief": "UK energy suppliers and the regulators around them.",
        "prompt": {f: f"energy {f}" for f in PROMPT_FIELDS},
        "keywords": ["energy supplier", "price cap"],
        "companies": [
            {"name": "Octopus Energy Limited", "company_number": "09263424", "aliases": ["Octopus"]},
            {"name": "OVO Energy Ltd", "company_number": "06890795", "aliases": []},
            {"name": "E.ON UK plc", "company_number": None, "aliases": ["E.ON"]},
        ],
        "tickers": {"CNA": "Centrica"},
        "categories": [
            {"name": "Price cap and tariffs", "pattern": "price cap|tariff", "before": "Enforcement action"},
        ],
        "signal_type_fallback": {},
        "excluded_bodies": ["ofgem"],
        "sources": ["companies_house", "gazette", "dcms", "gambling_commission", "bgc"],
        "dcms_organisation": "department-for-energy-security-and-net-zero",
    }
    base.update(over)
    return base


class FakeCH:
    def __init__(self, records):
        self.records = records
        self.calls = []

    def lookup(self, number):
        self.calls.append(number)
        return self.records.get(number)


class FakeClient:
    """Returns queued tool inputs (or raw content blocks) one call at a time."""
    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kw):
        self.requests.append(kw)
        item = self.responses.pop(0)
        if isinstance(item, list):
            content = item
        else:
            content = [SimpleNamespace(type="tool_use", name="propose_sector", input=item)]
        return SimpleNamespace(content=content, stop_reason="tool_use")


class TestSlugs:
    @pytest.mark.parametrize("name,expected", [
        ("Energy retail", "energy-retail"),
        ("Gambling & gaming", "gambling-gaming"),
        ("  UK  Water -- Utilities ", "uk-water-utilities"),
        ("!!!", "sector"),
        ("Ä" * 3, "sector"),
        ("x" * 80, "x" * 40),
    ])
    def test_slugify(self, name, expected):
        assert drafting.slugify(name) == expected

    def test_unique(self):
        assert drafting.unique_slug("Gambling & gaming", {"gambling-gaming"}) == "gambling-gaming-2"
        assert drafting.unique_slug("Gambling & gaming", {"gambling-gaming", "gambling-gaming-2"}) == "gambling-gaming-3"


class TestNormalise:
    def test_strips_gambling_only_sources_and_fills_settings(self):
        cfg = drafting.normalise_draft(proposal(), set(), now=NOW)
        assert set(cfg["sources"]) == {"companies_house", "gazette", "dcms"}
        assert cfg["sources"]["dcms"]["organisation"] == "department-for-energy-security-and-net-zero"
        assert cfg["sources"]["companies_house"] == drafting.DEFAULT_SOURCE_SETTINGS["companies_house"]

    def test_drops_bad_categories(self):
        cats = [
            {"name": "Ok", "pattern": "ok", "before": "Enforcement action"},
            {"name": "Long", "pattern": "a" * 201, "before": "Enforcement action"},
            {"name": "Broken", "pattern": "x(", "before": "Enforcement action"},
            {"name": "Nowhere", "pattern": "y", "before": "Not a rule"},
        ]
        cfg = drafting.normalise_draft(proposal(categories=cats), set(), now=NOW)
        assert [c["name"] for c in cfg["categories"]] == ["Ok"]

    def test_fallback_to_a_dropped_category_is_removed(self):
        cats = [{"name": "Broken", "pattern": "x(", "before": "Enforcement action"}]
        cfg = drafting.normalise_draft(proposal(categories=cats,
                                                signal_type_fallback={"regulatory": "Broken"}),
                                       set(), now=NOW)
        assert cfg["signal_type_fallback"] == {}

    def test_companies_deduplicated_and_capped(self):
        companies = [{"name": f"Co {i} Ltd", "company_number": None, "aliases": []} for i in range(20)]
        companies.append({"name": "Co 1 Ltd", "company_number": None, "aliases": []})
        cfg = drafting.normalise_draft(proposal(companies=companies), set(), now=NOW)
        assert len(cfg["companies"]) == 12 and len({c["name"] for c in cfg["companies"]}) == 12

    def test_slug_and_created_at(self):
        cfg = drafting.normalise_draft(proposal(name="Gambling & gaming"), {"gambling-gaming"}, now=NOW)
        assert cfg["slug"] == "gambling-gaming-2"
        assert cfg["created_at"] == "2026-10-08T12:00:00+00:00"

    def test_output_validates(self):
        cfg = drafting.normalise_draft(proposal(), set(), now=NOW)
        parse_sector(cfg, cfg["slug"])

    @pytest.mark.parametrize("bad", [
        {"companies": "Octopus"},
        {"keywords": "energy"},
        {"prompt": "nope"},
        {"name": ""},
        {"sources": "gazette"},
    ])
    def test_wrong_shapes_raise_value_error(self, bad):
        with pytest.raises(ValueError):
            drafting.normalise_draft(proposal(**bad), set(), now=NOW)


class TestVerify:
    def test_keeps_only_active_matching_numbers(self):
        ch = FakeCH({
            "09263424": {"company_name": "OCTOPUS ENERGY LIMITED", "company_status": "active"},
            "06890795": {"company_name": "SOMETHING ELSE LTD", "company_status": "active"},
        })
        rows = drafting.verify_companies(proposal()["companies"], ch)
        assert [(r["company_number"], r["verified"]) for r in rows] == [
            ("09263424", True), (None, False), (None, False)]

    def test_dissolved_is_cleared(self):
        ch = FakeCH({"09263424": {"company_name": "OCTOPUS ENERGY LIMITED", "company_status": "dissolved"}})
        rows = drafting.verify_companies(proposal()["companies"][:1], ch)
        assert rows[0]["company_number"] is None

    def test_no_key_clears_everything_without_lookups(self):
        rows = drafting.verify_companies(proposal()["companies"], None)
        assert all(r["company_number"] is None and r["verified"] is False for r in rows)

    @pytest.mark.parametrize("number", ["abc", "4241161", " 09263424 ", 9263424])
    def test_malformed_numbers_cleared_or_trimmed(self, number):
        ch = FakeCH({"09263424": {"company_name": "OCTOPUS ENERGY LIMITED", "company_status": "active"}})
        row = drafting.verify_companies([{"name": "Octopus Energy Limited", "company_number": number}], ch)[0]
        if number == " 09263424 ":
            assert row["company_number"] == "09263424" and row["verified"]
        else:
            assert row["company_number"] is None and not row["verified"]


class TestDraftSector:
    def test_happy_path(self):
        ch = FakeCH({"09263424": {"company_name": "OCTOPUS ENERGY LIMITED", "company_status": "active"}})
        client = FakeClient(proposal())
        d = drafting.draft_sector("UK energy suppliers", {"gambling", "fintech"}, client, ch, now=NOW)
        assert d.slug == "energy-retail"
        assert d.config["companies"][0]["company_number"] == "09263424"
        assert "verified" not in d.config["companies"][0]
        assert d.companies[0]["verified"] is True
        req = client.requests[0]
        assert req["tool_choice"] == {"type": "tool", "name": "propose_sector"}
        assert "UK energy suppliers" in req["messages"][0]["content"]

    def test_retries_once_then_succeeds(self):
        client = FakeClient(proposal(companies="nope"), proposal())
        d = drafting.draft_sector("UK energy suppliers", set(), client, None, now=NOW)
        assert d.slug == "energy-retail" and len(client.requests) == 2
        assert "companies" in client.requests[1]["messages"][-1]["content"]

    def test_two_failures_raise_draft_error(self):
        client = FakeClient(proposal(companies="nope"), proposal(prompt="nope"))
        with pytest.raises(drafting.DraftError):
            drafting.draft_sector("UK energy suppliers", set(), client, None, now=NOW)

    def test_no_tool_call_counts_as_failure(self):
        text_only = [SimpleNamespace(type="text", text="Sure! Here's a sector…")]
        client = FakeClient(text_only, proposal())
        d = drafting.draft_sector("UK energy suppliers", set(), client, None, now=NOW)
        assert d.slug == "energy-retail"

    def test_too_few_companies_is_a_failure(self):
        client = FakeClient(proposal(companies=[{"name": "Only Ltd"}]),
                            proposal(companies=[{"name": "Only Ltd"}]))
        with pytest.raises(drafting.DraftError):
            drafting.draft_sector("x" * 20, set(), client, None, now=NOW)

    @pytest.mark.parametrize("desc", ["short", "x" * 301, "   "])
    def test_description_length(self, desc):
        with pytest.raises(ValueError):
            drafting.draft_sector(desc, set(), FakeClient(), None, now=NOW)


class TestCompaniesHouseClient:
    def test_lookup_uses_basic_auth_and_returns_none_on_404(self):
        calls = []

        def fake_get(url, auth=None, timeout=None):
            calls.append((url, auth))
            if url.endswith("/09263424"):
                return SimpleNamespace(status_code=200, json=lambda: {"company_name": "X", "company_status": "active"},
                                       raise_for_status=lambda: None)
            return SimpleNamespace(status_code=404, json=lambda: {}, raise_for_status=lambda: None)

        ch = drafting.CompaniesHouse("key", get=fake_get)
        assert ch.lookup("09263424")["company_status"] == "active"
        assert ch.lookup("00000000") is None
        assert calls[0] == ("https://api.company-information.service.gov.uk/company/09263424", ("key", ""))

    def test_network_error_is_none(self):
        def boom(*a, **k):
            raise OSError("down")
        assert drafting.CompaniesHouse("key", get=boom).lookup("09263424") is None


class TestMalformedShapes:
    @pytest.mark.parametrize("bad", [
        {"companies": [{"name": f"Co {i} Ltd", "aliases": "Octopus"} for i in range(3)],
         "signal_type_fallback": {"regulatory": ["x"]}},
        {"companies": [{"name": f"Co {i} Ltd", "company_number": 9263424} for i in range(3)],
         "prompt": {f: 5 for f in PROMPT_FIELDS}},
        {"sources": [["gazette"]]},
        {"categories": ["not-an-object"], "tickers": ["CNA"]},
        {"prompt": {f: ["list"] for f in PROMPT_FIELDS}},
    ])
    def test_never_escapes_draft_sector(self, bad):
        client = FakeClient(proposal(**bad), proposal(**bad))
        try:
            d = drafting.draft_sector("UK energy suppliers", set(), client, None, now=NOW)
        except drafting.DraftError:
            return
        # Repaired shapes must still validate.
        parse_sector(d.config, d.slug)

    def test_non_string_prompt_values_retry(self):
        client = FakeClient(proposal(prompt={f: 5 for f in PROMPT_FIELDS}), proposal())
        d = drafting.draft_sector("UK energy suppliers", set(), client, None, now=NOW)
        assert d.slug == "energy-retail"

    def test_unhashable_fallback_value_retries(self):
        client = FakeClient(proposal(signal_type_fallback={"regulatory": ["x"]}), proposal())
        d = drafting.draft_sector("UK energy suppliers", set(), client, None, now=NOW)
        assert d.slug == "energy-retail"


class TestRetryConversation:
    def test_retry_is_one_user_turn(self):
        client = FakeClient(proposal(companies="nope"), proposal())
        drafting.draft_sector("UK energy suppliers", set(), client, None, now=NOW)
        msgs = client.requests[1]["messages"]
        assert [m["role"] for m in msgs] == ["user"]
        assert "UK energy suppliers" in msgs[0]["content"]
        assert "That proposal was invalid" in msgs[0]["content"]


def test_slugify_never_returns_invalid_slug():
    from src.sectors import SLUG_RE
    for name in ["a" * 39 + "-b", "a" * 39 + " b", "x-" * 30, "\n", "ab\n"]:
        assert SLUG_RE.fullmatch(drafting.slugify(name))
