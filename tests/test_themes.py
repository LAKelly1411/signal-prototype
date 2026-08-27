from datetime import datetime, timedelta, timezone

from src.categories import ENFORCEMENT, INSOLVENCY, OTHER
from src.cluster import (
    MAX_BRIDGING_ENTITIES,
    THEME_SIGNIFICANT_SCORE,
    assign_clusters,
    assign_themes,
    compute_theme_heat,
)

NOW = datetime(2026, 8, 27, tzinfo=timezone.utc)


def signal(sid, entities, category=INSOLVENCY, days_ago=1, score=30, source="gazette"):
    return {
        "id": sid,
        "source": source,
        "entities": entities,
        "canonical_entities": entities,
        "canonical_category": category,
        "newsworthiness_score": score,
        "published_at": (NOW - timedelta(days=days_ago)).isoformat(),
    }


class TestAssignThemes:
    def test_a_wave_across_companies_becomes_one_theme(self):
        # The motivating case: individually unremarkable insolvencies at
        # different companies, which entity clustering can never connect.
        signals = [signal(str(i), [f"Operator {i}"]) for i in range(5)]
        assign_themes(signals, now=NOW)
        assert {s["theme_id"] for s in signals} == {INSOLVENCY}

    def test_one_companys_run_of_filings_is_not_a_theme(self):
        signals = [signal(str(i), ["Rank"]) for i in range(6)]
        assign_themes(signals, now=NOW)
        assert all(s["theme_id"] is None for s in signals)

    def test_needs_min_companies(self):
        signals = [signal("a", ["A"]), signal("b", ["B"])]
        assign_themes(signals, now=NOW, min_companies=3)
        assert all(s["theme_id"] is None for s in signals)
        assign_themes(signals, now=NOW, min_companies=2)
        assert all(s["theme_id"] == INSOLVENCY for s in signals)

    def test_low_scoring_relevant_signals_still_count(self):
        # A wave is made of individually unremarkable events — judging
        # membership at the company-cluster bar would discard the pattern.
        signals = [
            signal(str(i), [f"Operator {i}"], score=THEME_SIGNIFICANT_SCORE)
            for i in range(4)
        ]
        assign_themes(signals, now=NOW)
        assert all(s["theme_id"] == INSOLVENCY for s in signals)

    def test_irrelevant_signals_are_still_excluded(self):
        # The Gazette matches non-gambling firms on keyword; Claude scores
        # those in single figures, which is what keeps them out.
        signals = [
            signal(str(i), [f"Restaurant {i}"], score=THEME_SIGNIFICANT_SCORE - 1)
            for i in range(5)
        ]
        assign_themes(signals, now=NOW)
        assert all(s["theme_id"] is None for s in signals)

    def test_other_is_never_a_theme(self):
        signals = [signal(str(i), [f"Op {i}"], category=OTHER) for i in range(5)]
        assign_themes(signals, now=NOW)
        assert all(s["theme_id"] is None for s in signals)

    def test_window_is_respected(self):
        signals = [signal(str(i), [f"Op {i}"], days_ago=200) for i in range(5)]
        assign_themes(signals, now=NOW)
        assert all(s["theme_id"] is None for s in signals)

    def test_themes_are_recomputed_not_accumulated(self):
        stale = signal("a", ["A"], days_ago=200)
        stale["theme_id"] = INSOLVENCY
        assign_themes([stale], now=NOW)
        assert stale["theme_id"] is None

    def test_theme_id_is_stable_across_runs(self):
        # Unlike cluster_id, which rehashes whenever membership changes.
        signals = [signal(str(i), [f"Op {i}"]) for i in range(4)]
        assign_themes(signals, now=NOW)
        first = signals[0]["theme_id"]
        assign_themes(signals + [signal("new", ["Op new"])], now=NOW)
        assert signals[0]["theme_id"] == first


class TestThemeHeat:
    def test_breadth_across_companies_beats_raw_volume(self):
        broad = [signal(str(i), [f"Op {i}"]) for i in range(5)]
        narrow = [signal(str(i), ["Op A", "Op B"]) for i in range(7)]
        assert compute_theme_heat(broad, now=NOW) > compute_theme_heat(narrow, now=NOW)

    def test_recency_raises_theme_heat(self):
        fresh = [signal(str(i), [f"Op {i}"], days_ago=0) for i in range(4)]
        stale = [signal(str(i), [f"Op {i}"], days_ago=80) for i in range(4)]
        assert compute_theme_heat(fresh, now=NOW) > compute_theme_heat(stale, now=NOW)

    def test_peak_score_lifts_a_theme(self):
        weak = [signal(str(i), [f"Op {i}"], score=30) for i in range(4)]
        strong = [signal(str(i), [f"Op {i}"], score=30) for i in range(3)]
        strong.append(signal("big", ["Op big"], score=95))
        assert compute_theme_heat(strong, now=NOW) > compute_theme_heat(weak, now=NOW)


class TestSuperclusterGuard:
    def test_a_roundup_does_not_weld_companies_together(self):
        roundup = signal(
            "roundup",
            [f"Operator {i}" for i in range(MAX_BRIDGING_ENTITIES + 3)],
            category=ENFORCEMENT,
            score=60,
        )
        a = signal("a", ["Operator 0"], category=ENFORCEMENT, score=60)
        b = signal("b", ["Operator 5"], category=ENFORCEMENT, score=60)
        signals = [roundup, a, b]
        assign_clusters(signals, now=NOW)
        # a and b are unrelated companies; only the roundup names both.
        assert a["cluster_id"] is None or a["cluster_id"] != b["cluster_id"]

    def test_normal_signals_still_bridge(self):
        a = signal("a", ["Rank"], score=60)
        b = signal("b", ["Rank"], score=60)
        assign_clusters([a, b], now=NOW)
        assert a["cluster_id"] == b["cluster_id"] is not None

    def test_a_hub_entity_does_not_group_everything(self):
        # An entity naming most of the window behaves like an institution: a
        # law firm acting on every case, a regulator's spokesperson. Genuine
        # pairs must still cluster, just not be welded to each other.
        signals = []
        for pair in range(6):
            for copy in range(2):
                signals.append(
                    signal(
                        f"{pair}-{copy}",
                        ["Ubiquitous Advisers LLP", f"Operator {pair}"],
                        score=60,
                    )
                )
        assign_clusters(signals, now=NOW)

        ids = {s["cluster_id"] for s in signals}
        assert None not in ids, "genuine pairs should still cluster"
        assert len(ids) == 6, f"expected one cluster per operator, got {len(ids)}"

    def test_without_a_hub_the_pairs_are_unaffected(self):
        signals = []
        for pair in range(6):
            for copy in range(2):
                signals.append(signal(f"{pair}-{copy}", [f"Operator {pair}"], score=60))
        assign_clusters(signals, now=NOW)
        assert len({s["cluster_id"] for s in signals}) == 6
