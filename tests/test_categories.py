from src.categories import (
    AML,
    BOARD,
    CONSULTATION,
    CORPORATE_FILING,
    DISQUALIFICATION,
    ENFORCEMENT,
    ILLEGAL,
    INSOLVENCY,
    LICENCE,
    MERGER,
    OTHER,
    SHAREHOLDING,
    canonical_category,
    category_of,
    ruleset,
    taxonomy,
)
from src.sectors import Sector


class TestLegacyMapping:
    def test_the_insolvency_wave_collapses_to_one_theme(self):
        # 15 spellings of the same thing were what made the wave invisible.
        for raw in [
            "insolvency filing",
            "insolvency/liquidation",
            "winding-up petition",
            "winding up petition",
            "company winding-up",
            "insolvency notice",
            "winding-up order",
            "creditors meeting",
            "insolvency/winding-up",
        ]:
            assert canonical_category(raw) == INSOLVENCY, raw

    def test_aml_beats_the_licence_framing(self):
        # "AML/licence enforcement" is an AML story; rule order decides.
        assert canonical_category("AML/licence enforcement") == AML
        assert canonical_category("AML/social responsibility enforcement") == AML

    def test_maps_the_common_legacy_labels(self):
        cases = {
            "personal licence revocation": LICENCE,
            "licence suspension": LICENCE,
            "financial penalty": ENFORCEMENT,
            "regulatory settlement": ENFORCEMENT,
            "shareholder disclosure": SHAREHOLDING,
            "share buyback": SHAREHOLDING,
            "director appointment": BOARD,
            "accounts filing": CORPORATE_FILING,
            "illegal gambling enforcement": ILLEGAL,
            "M&A / takeover": MERGER,
            "corporate restructuring/scheme": MERGER,
        }
        for raw, expected in cases.items():
            assert canonical_category(raw) == expected, raw

    def test_disqualification_is_not_swallowed_by_board_changes(self):
        assert canonical_category("director disqualification") == DISQUALIFICATION


class TestFallbacks:
    def test_falls_back_to_the_title(self):
        assert canonical_category(None, "Publication of the Scheme Document") == MERGER

    def test_falls_back_to_signal_type_last(self):
        assert canonical_category(None, "Untitled", "insolvency") == INSOLVENCY
        assert canonical_category(None, "Untitled", "consultation") == CONSULTATION

    def test_unmappable_becomes_other(self):
        assert canonical_category("", "", None) == OTHER

    def test_every_result_is_in_the_taxonomy(self):
        for raw in ["insolvency filing", "nonsense label", "", "AML"]:
            assert canonical_category(raw, "some title") in taxonomy()


class TestIdempotence:
    def test_canonical_values_pass_through_unchanged(self):
        for theme in taxonomy():
            assert canonical_category(theme) == theme

    def test_matching_is_case_insensitive(self):
        assert canonical_category("INSOLVENCY FILING") == INSOLVENCY
        assert canonical_category(INSOLVENCY.upper()) == INSOLVENCY


class TestCategoryOf:
    def test_prefers_the_stored_value(self):
        signal = {"canonical_category": AML, "category": "insolvency filing"}
        assert category_of(signal) == AML

    def test_derives_when_absent(self):
        signal = {"category": "winding-up petition", "title": "X LTD"}
        assert category_of(signal) == INSOLVENCY


def _fintech(**overrides):
    base = dict(slug="fintech", name="Fintech", brief="b",
                prompt={}, sources={"gazette": {}},
                categories=[{"name": "Crypto", "pattern": "crypto|stablecoin",
                             "before": "Enforcement action"}])
    base.update(overrides)
    return Sector(**base)


class TestSectorCategories:
    def test_sector_category_matches_before_core(self):
        assert canonical_category("stablecoin enforcement", sector=_fintech()) == "Crypto"

    def test_gambling_only_categories_absent_elsewhere(self):
        t = taxonomy(_fintech())
        assert "Illegal gambling" not in t and "Crypto" in t and t[-1] == OTHER

    def test_core_fallback_for_regulatory_is_other(self):
        assert canonical_category(None, "Untitled", "regulatory", sector=_fintech()) == OTHER

    def test_gambling_overrides_regulatory_fallback(self):
        assert canonical_category(None, "Untitled", "regulatory") == LICENCE

    def test_ruleset_is_cached_per_slug(self):
        assert ruleset(_fintech()) is ruleset(_fintech())
