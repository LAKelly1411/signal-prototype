import re

from src.categories import canonical_category, taxonomy
from src.cluster import is_excluded
from src.sectors import PROMPT_FIELDS, load_sector

FINTECH = load_sector("fintech")


def test_loads_with_its_name():
    assert FINTECH.slug == "fintech" and FINTECH.name == "Fintech & payments"


def test_every_prompt_field_is_fintech_wording():
    assert set(FINTECH.prompt) == set(PROMPT_FIELDS)
    assert not any("gambl" in v.lower() or "operator" in v.lower() for v in FINTECH.prompt.values())


def test_company_numbers_are_quoted_eight_character_ids():
    assert 6 <= len(FINTECH.companies) <= 8
    for company in FINTECH.companies:
        assert isinstance(company["company_number"], str)
        assert re.fullmatch(r"[0-9A-Z]{8}", company["company_number"]), company["name"]


def test_only_generic_sources():
    assert "gambling_commission" not in FINTECH.sources and "bgc" not in FINTECH.sources
    assert FINTECH.sources["dcms"]["organisation"] == "hm-treasury"


def test_fintech_categories_route_before_enforcement():
    assert canonical_category("APP fraud reimbursement", sector=FINTECH) == "Fraud and APP scams"
    assert canonical_category("Consumer Duty review", sector=FINTECH) == "Consumer Duty and redress"
    assert canonical_category("Variation of permission", sector=FINTECH) == "Authorisation and permissions"
    t = taxonomy(FINTECH)
    assert "Licence action" not in t and t[-1] == "Other"


def test_fintech_regulators_are_excluded_but_not_in_gambling():
    for body in ("Payment Systems Regulator", "Financial Ombudsman Service", "Bank of England"):
        assert is_excluded(body, FINTECH)
        assert not is_excluded(body)  # gambling default unchanged
