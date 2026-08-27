from datetime import datetime, timedelta, timezone

from src.cluster import (
    PEAK_SCORE_MAX,
    RECENCY_MAX,
    SIGNIFICANT_SCORE,
    assign_clusters,
    compute_heat,
    is_excluded,
)
from src.entities import build_alias_map

NOW = datetime(2026, 8, 27, tzinfo=timezone.utc)


def signal(sid, entities, days_ago=1, source="gambling_commission", score=60):
    return {
        "id": sid,
        "source": source,
        "entities": entities,
        "newsworthiness_score": score,
        "published_at": (NOW - timedelta(days=days_ago)).isoformat(),
    }


class TestExclusions:
    def test_institutions_are_excluded(self):
        for name in [
            "Gambling Commission",
            "BGC",
            "Betting and Gaming Council",
            "Illegal Gambling Taskforce",
            "DCMS",
            "HM Treasury",
            "The Gazette",
        ]:
            assert is_excluded(name), name

    def test_companies_are_not_excluded(self):
        for name in ["Entain", "bet365 Group Limited", "Rank Group"]:
            assert not is_excluded(name), name


class TestAssignClusters:
    def test_shared_entity_forms_a_cluster(self):
        signals = [signal("a", ["Rank Group"]), signal("b", ["Rank Group"])]
        assign_clusters(signals, now=NOW)
        assert signals[0]["cluster_id"] is not None
        assert signals[0]["cluster_id"] == signals[1]["cluster_id"]

    def test_variants_of_one_company_now_join(self):
        # The headline fix: before canonicalisation these two never clustered.
        signals = [
            signal("a", ["Entain"], source="lse_rns"),
            signal("b", ["Entain Holdings (UK) Limited"], source="companies_house"),
        ]
        assign_clusters(signals, now=NOW)
        assert signals[0]["cluster_id"] == signals[1]["cluster_id"]
        assert signals[0]["cluster_id"] is not None

    def test_aliases_join_via_the_watchlist(self):
        alias_map = build_alias_map(
            [{"name": "Entain Holdings (UK) Limited", "aliases": ["bwin"]}]
        )
        signals = [signal("a", ["bwin"]), signal("b", ["Entain Holdings (UK) Limited"])]
        assign_clusters(signals, now=NOW, alias_map=alias_map)
        assert signals[0]["cluster_id"] == signals[1]["cluster_id"]

    def test_institutions_alone_do_not_cluster(self):
        signals = [
            signal("a", ["Gambling Commission"]),
            signal("b", ["Gambling Commission"]),
        ]
        assign_clusters(signals, now=NOW)
        assert signals[0]["cluster_id"] is None
        assert signals[1]["cluster_id"] is None

    def test_prefers_precomputed_canonical_entities(self):
        a = signal("a", ["Something Odd"])
        a["canonical_entities"] = ["Rank"]
        b = signal("b", ["Rank Group"])
        assign_clusters([a, b], now=NOW)
        assert a["cluster_id"] == b["cluster_id"]

    def test_signals_outside_the_window_are_excluded(self):
        signals = [signal("a", ["Rank Group"], days_ago=1),
                   signal("b", ["Rank Group"], days_ago=120)]
        assign_clusters(signals, now=NOW)
        assert signals[0]["cluster_id"] is None
        assert signals[1]["cluster_id"] is None

    def test_window_reaches_90_days(self):
        # Widened from 30: a company's signals rarely arrive within a month of
        # each other, which was the real limit on the pattern layer.
        signals = [signal("a", ["Rank Group"], days_ago=5),
                   signal("b", ["Rank Group"], days_ago=85)]
        assign_clusters(signals, now=NOW)
        assert signals[0]["cluster_id"] == signals[1]["cluster_id"]
        assert signals[0]["cluster_id"] is not None

    def test_window_is_overridable(self):
        signals = [signal("a", ["Rank Group"], days_ago=5),
                   signal("b", ["Rank Group"], days_ago=85)]
        assign_clusters(signals, window_days=30, now=NOW)
        assert all(s["cluster_id"] is None for s in signals)

    def test_unscored_signals_are_excluded(self):
        signals = [signal("a", ["Rank Group"], score=None),
                   signal("b", ["Rank Group"])]
        assign_clusters(signals, now=NOW)
        assert all(s["cluster_id"] is None for s in signals)

    def test_reassignment_clears_stale_cluster_ids(self):
        signals = [signal("a", ["Rank Group"]), signal("b", ["Flutter"])]
        signals[0]["cluster_id"] = "stale"
        assign_clusters(signals, now=NOW)
        assert signals[0]["cluster_id"] is None

    def test_transitive_grouping(self):
        signals = [
            signal("a", ["Entain", "Flutter"]),
            signal("b", ["Flutter", "Rank Group"]),
            signal("c", ["Rank Group"]),
        ]
        assign_clusters(signals, now=NOW)
        ids = {s["cluster_id"] for s in signals}
        assert len(ids) == 1 and None not in ids


class TestComputeHeat:
    def test_source_diversity_outweighs_raw_count(self):
        one_source = [signal(str(i), ["X"], source="a") for i in range(4)]
        two_sources = [
            signal("x", ["X"], source="a"),
            signal("y", ["X"], source="b"),
            signal("z", ["X"], source="c"),
        ]
        assert compute_heat(two_sources, now=NOW) > compute_heat(one_source, now=NOW)

    def test_recency_raises_heat(self):
        recent = [signal("a", ["X"], days_ago=0), signal("b", ["X"], days_ago=0)]
        old = [signal("a", ["X"], days_ago=25), signal("b", ["X"], days_ago=25)]
        assert compute_heat(recent, now=NOW) > compute_heat(old, now=NOW)

    def test_recency_never_goes_negative(self):
        ancient = [signal("a", ["X"], days_ago=400)]
        assert compute_heat(ancient, now=NOW) >= 0

    def test_recency_still_discriminates_beyond_30_days(self):
        # The old fixed 30-day ramp bottomed out a third of the way into the
        # 90-day window, tying every cluster older than a month.
        mid = [signal("a", ["X"], days_ago=40), signal("b", ["X"], days_ago=40)]
        late = [signal("a", ["X"], days_ago=80), signal("b", ["X"], days_ago=80)]
        assert compute_heat(mid, now=NOW) > compute_heat(late, now=NOW)

    def test_recency_contribution_is_capped_at_its_ceiling(self):
        # Widening the window redistributes recency; it must not inflate heat,
        # or the dashboard's tier thresholds would silently need re-tuning.
        freshest = [
            signal("a", ["X"], days_ago=0, score=100),
            signal("b", ["X"], days_ago=0, score=100),
        ]
        base = 2 * 10 + 1 * 20 + PEAK_SCORE_MAX
        assert compute_heat(freshest, now=NOW) == base + RECENCY_MAX

    def test_recency_reaches_zero_at_the_window_edge(self):
        edge = [
            signal("a", ["X"], days_ago=90, score=100),
            signal("b", ["X"], days_ago=90, score=100),
        ]
        assert compute_heat(edge, now=NOW) == 2 * 10 + 1 * 20 + PEAK_SCORE_MAX

    def test_routine_filings_do_not_outrank_a_real_story(self):
        # The reason heat became score-aware: a month of RNS boilerplate used
        # to bury a two-signal cluster containing a record fine.
        boilerplate = [signal(str(i), ["X"], score=20) for i in range(12)]
        enforcement = [
            signal("a", ["Y"], score=88),
            signal("b", ["Y"], score=72),
        ]
        assert compute_heat(enforcement, now=NOW) > compute_heat(boilerplate, now=NOW)

    def test_below_threshold_signals_add_no_volume(self):
        two_real = [signal("a", ["X"], score=60), signal("b", ["X"], score=60)]
        padded = two_real + [signal(f"p{i}", ["X"], score=SIGNIFICANT_SCORE - 1)
                             for i in range(8)]
        assert compute_heat(padded, now=NOW) == compute_heat(two_real, now=NOW)

    def test_peak_score_rewards_the_best_signal(self):
        weak = [signal("a", ["X"], score=40), signal("b", ["X"], score=40)]
        strong = [signal("a", ["X"], score=40), signal("b", ["X"], score=95)]
        assert compute_heat(strong, now=NOW) > compute_heat(weak, now=NOW)

    def test_peak_score_counts_even_when_below_threshold(self):
        # A cluster of sub-threshold signals still scores above zero, so it
        # sinks rather than vanishing.
        quiet = [signal("a", ["X"], score=10), signal("b", ["X"], score=10)]
        assert compute_heat(quiet, now=NOW) > 0

    def test_unscored_members_are_tolerated(self):
        members = [signal("a", ["X"], score=None), signal("b", ["X"], score=70)]
        assert compute_heat(members, now=NOW) > 0

    def test_heat_window_follows_the_cluster_window(self):
        members = [signal("a", ["X"], days_ago=40), signal("b", ["X"], days_ago=40)]
        # Under a 30-day window that cluster is past the edge; under 90 it isn't.
        assert compute_heat(members, now=NOW, window_days=30) < compute_heat(
            members, now=NOW, window_days=90
        )
