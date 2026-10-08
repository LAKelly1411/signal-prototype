from dashboard.new_sector import apply_editor_changes, apply_review, editor_rows, merge_pending
from src.sectors import PROMPT_FIELDS, parse_sector

CONFIG = {
    "slug": "energy-retail", "name": "Energy retail", "brief": "UK energy.", "created_at": "2026-10-08T12:00:00+00:00",
    "prompt": {f: "x" for f in PROMPT_FIELDS}, "keywords": ["energy"],
    "companies": [{"name": "Octopus Energy Limited", "company_number": "09263424", "aliases": []}],
    "tickers": {}, "categories": [], "signal_type_fallback": {}, "excluded_bodies": [],
    "sources": {"gazette": {"results_per_term": 20, "sleep_seconds": 1.0},
                "companies_house": {"items_per_page": 25}},
}


def test_apply_review_edits_and_keeps_slug():
    out = apply_review(CONFIG, name="Energy suppliers", brief="UK energy suppliers.",
                       keywords=["energy", "tariff"],
                       companies=[{"name": "Octopus Energy Limited", "company_number": "09263424"},
                                  {"name": "OVO Energy Ltd", "company_number": ""}],
                       sources=["gazette"])
    assert out["slug"] == "energy-retail"            # slug is fixed at draft time
    assert out["name"] == "Energy suppliers"
    assert out["companies"][1]["company_number"] is None
    assert list(out["sources"]) == ["gazette"]
    parse_sector(out, out["slug"])


def test_apply_review_drops_blank_company_rows_and_coerces_numbers():
    out = apply_review(CONFIG, name="E", brief="b", keywords=[],
                       companies=[{"name": "  ", "company_number": "x"},
                                  {"name": "A Ltd", "company_number": 4241161},
                                  {"name": "B Ltd", "company_number": " abc "}],
                       sources=["gazette"])
    assert [c["name"] for c in out["companies"]] == ["A Ltd", "B Ltd"]
    assert all(c["company_number"] is None or isinstance(c["company_number"], str) for c in out["companies"])


def test_merge_pending_adds_until_remote_has_it():
    index = [{"slug": "gambling"}]
    pending = [{"slug": "energy-retail", "status": "setting_up"}]
    assert [e["slug"] for e in merge_pending(index, pending)] == ["gambling", "energy-retail"]
    assert merge_pending(index + [{"slug": "energy-retail", "status": "ready"}], pending)[-1]["status"] == "ready"
    assert merge_pending(None, pending) is None


def test_apply_review_dedupes_by_match_key_keeping_the_first():
    out = apply_review(CONFIG, name="E", brief="b", keywords=[],
                       companies=[{"name": "Octopus Energy Limited", "company_number": "09263424"},
                                  {"name": "Octopus Energy Ltd", "company_number": "X"},
                                  {"name": "OVO Energy", "company_number": None}],
                       sources=["gazette"])
    assert [c["name"] for c in out["companies"]] == ["Octopus Energy Limited", "OVO Energy"]
    assert out["companies"][0]["company_number"] == "09263424"


def test_apply_review_caps_companies_at_twelve():
    many = [{"name": f"Company {i} Ltd", "company_number": None} for i in range(15)]
    out = apply_review(CONFIG, name="E", brief="b", keywords=[], companies=many, sources=["gazette"])
    assert [c["name"] for c in out["companies"]] == [f"Company {i} Ltd" for i in range(12)]


DRAFTED = [{"name": "Octopus Energy Limited", "company_number": "09263424", "aliases": [], "verified": True},
           {"name": "OVO Energy Ltd", "company_number": None, "aliases": [], "verified": False}]


def test_editor_rows_tick_only_unedited_verified_numbers():
    rows = [{"name": "Octopus Energy Limited", "company_number": "09263424", "aliases": []},
            {"name": "OVO Energy Ltd", "company_number": None, "aliases": []}]
    assert [r["Verified"] for r in editor_rows(rows, DRAFTED)] == ["✓", "–"]
    rows[0]["company_number"] = "09263425"                       # edited: no longer verified
    assert editor_rows(rows, DRAFTED)[0]["Verified"] == "–"
    assert editor_rows(rows, DRAFTED)[0]["Companies House number"] == "09263425"
    rows[0]["company_number"] = " 09263424 "                     # same number, stray spaces
    assert editor_rows(rows, DRAFTED)[0]["Verified"] == "✓"
    rows[0]["name"] = "Something Else Ltd"                       # number now belongs to another name
    assert editor_rows(rows, DRAFTED)[0]["Verified"] == "–"


def test_apply_editor_changes_edits_deletes_and_adds():
    rows = [{"name": "A Ltd", "company_number": "1", "aliases": ["A"]},
            {"name": "B Ltd", "company_number": None, "aliases": []},
            {"name": "C Ltd", "company_number": None, "aliases": []}]
    changes = {"edited_rows": {0: {"Companies House number": "2"}, 2: {"Name": "C2 Ltd"}},
               "deleted_rows": [1],
               "added_rows": [{"Name": "D Ltd"}, {}]}
    out = apply_editor_changes(rows, changes)
    assert out == [{"name": "A Ltd", "company_number": "2", "aliases": ["A"]},
                   {"name": "C2 Ltd", "company_number": None, "aliases": []},
                   {"name": "D Ltd", "company_number": None, "aliases": []},
                   {"name": "", "company_number": None, "aliases": []}]
    assert rows[0]["company_number"] == "1"                      # input untouched
    assert apply_editor_changes(rows, None) == rows


def test_apply_editor_changes_accepts_string_row_indexes():
    rows = [{"name": "A Ltd", "company_number": None, "aliases": []}]
    out = apply_editor_changes(rows, {"edited_rows": {"0": {"Name": "Z Ltd"}}})
    assert out[0]["name"] == "Z Ltd"
