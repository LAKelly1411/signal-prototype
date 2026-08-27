from src.entities import build_alias_map, canonical, canonicalise, match_key

WATCHLIST = [
    {
        "name": "Entain Holdings (UK) Limited",
        "aliases": ["Ladbrokes", "Coral", "bwin", "Entain"],
    },
    {"name": "Ladbrokes Coral Group Limited", "aliases": ["Ladbrokes", "Coral"]},
    {"name": "William Hill Limited", "aliases": ["William Hill", "888", "evoke"]},
]


class TestSuffixStripping:
    def test_collapses_legal_suffixes(self):
        assert match_key("William Hill Organization Ltd") == "william hill"
        assert match_key("William Hill Limited") == "william hill"
        assert match_key("William Hill Group") == "william hill"
        assert match_key("William Hill") == "william hill"

    def test_collapses_jurisdiction_parentheticals(self):
        assert match_key("Petfre (Gibraltar) Ltd") == "petfre"
        assert match_key("Petfre (Gibraltar) Limited") == "petfre"

    def test_strips_leading_the(self):
        assert match_key("The Rank Group") == "rank"
        assert match_key("Rank Group plc") == "rank"

    def test_keeps_meaningful_qualifiers(self):
        # Betfair Casino is a different entity from Betfair itself — "Casino"
        # is part of the name, not legal-entity noise.
        assert match_key("Betfair Limited") != match_key("Betfair Casino Limited")

    def test_never_strips_a_name_to_nothing(self):
        assert match_key("Limited") == "limited"
        assert canonical("Group") == "Group"

    def test_case_and_whitespace_insensitive(self):
        assert match_key("bet365  Group   Limited") == match_key("BET365")


class TestAliasMap:
    def test_maps_aliases_to_canonical_name(self):
        alias_map = build_alias_map(WATCHLIST)
        assert canonical("bwin", alias_map) == "Entain Holdings (UK) Limited"
        assert canonical("Entain", alias_map) == "Entain Holdings (UK) Limited"

    def test_operator_name_beats_another_operators_alias(self):
        # "Coral" is an alias of Entain, but here it's also an operator in its
        # own right — its own name must win, whatever the file order.
        alias_map = build_alias_map(
            [
                {"name": "Entain Holdings (UK) Limited", "aliases": ["Coral"]},
                {"name": "Coral Limited"},
            ]
        )
        assert canonical("Coral", alias_map) == "Coral Limited"
        assert canonical("Entain", alias_map) == "Entain Holdings (UK) Limited"

    def test_contested_alias_resolves_to_the_first_claimant(self):
        # "Ladbrokes" is listed as an alias of two operators and matches
        # neither's own name, so the seed file's order decides. Deterministic
        # is what matters here — not which parent wins.
        alias_map = build_alias_map(WATCHLIST)
        assert canonical("Ladbrokes", alias_map) == "Entain Holdings (UK) Limited"
        assert build_alias_map(WATCHLIST) == alias_map

    def test_full_legal_name_keeps_its_own_identity(self):
        # Stripping leaves "ladbrokes coral", distinct from bare "ladbrokes",
        # so the group entity doesn't get absorbed into Entain.
        alias_map = build_alias_map(WATCHLIST)
        assert (
            canonical("Ladbrokes Coral Group Limited", alias_map)
            == "Ladbrokes Coral Group Limited"
        )

    def test_off_watchlist_names_still_collapse(self):
        alias_map = build_alias_map(WATCHLIST)
        assert canonical("Gaming Realms plc", alias_map) == "Gaming Realms"

    def test_tolerates_missing_and_blank_fields(self):
        alias_map = build_alias_map(
            [{"name": "Acme Ltd"}, {"name": ""}, {"name": "Foo", "aliases": [None, ""]}]
        )
        assert alias_map["acme"] == "Acme Ltd"


class TestCanonicalise:
    def test_dedupes_variants_of_one_company(self):
        alias_map = build_alias_map(WATCHLIST)
        result = canonicalise(
            ["Entain", "Entain Holdings (UK) Limited", "bwin"], alias_map
        )
        assert result == ["Entain Holdings (UK) Limited"]

    def test_preserves_order_and_drops_blanks(self):
        assert canonicalise(["Zeta plc", "", "Alpha Ltd"]) == ["Zeta", "Alpha"]

    def test_handles_empty_input(self):
        assert canonicalise([]) == []
        assert canonicalise(None) == []
