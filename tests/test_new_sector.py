from dashboard.new_sector import apply_review, merge_pending
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
