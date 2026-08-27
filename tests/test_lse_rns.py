import yaml

from src.collectors.lse_rns import LSERNSCollector

SKIP_TITLES = yaml.safe_load(open("config/sources.yaml", encoding="utf-8"))["lse_rns"][
    "skip_titles"
]


def collector(skip_titles=SKIP_TITLES):
    return LSERNSCollector(
        tickers={"ENT": "Entain"}, user_agent="test", skip_titles=skip_titles
    )


class TestRoutineFiltering:
    def test_filters_the_shipped_denylist(self):
        c = collector()
        for title in [
            "Holding(s) in Company",
            "Total Voting Rights",
            "Transaction in Own Shares",
            "Director/PDMR Shareholding",
            "TR-1: Notification of major holdings",
            "TR1: Notification of Major Holdings",
            "Block listing Interim Review",
        ]:
            assert c._is_routine(title), title

    def test_substring_match_catches_compound_headlines(self):
        # "Issuance of Shares & Total Voting Rights" is the same boilerplate
        # wearing a longer headline.
        assert collector()._is_routine("Issuance of Shares & Total Voting Rights")

    def test_keeps_the_stories(self):
        c = collector()
        for title in [
            "Interim Results",
            "Publication of the Scheme Document",
            "Results of Court Meeting and General Meeting",
            "Phased exit of Entain CEE - 20% divestment agreed",
            "Flutter completes LSE delisting",
            "Directorate Changes",
            "Trading Statement",
        ]:
            assert not c._is_routine(title), title

    def test_matching_is_case_insensitive(self):
        assert collector()._is_routine("TOTAL VOTING RIGHTS")
        assert collector(["Total Voting Rights"])._is_routine("total voting rights")

    def test_no_denylist_keeps_everything(self):
        assert not collector(None)._is_routine("Total Voting Rights")
        assert not collector([])._is_routine("Total Voting Rights")
