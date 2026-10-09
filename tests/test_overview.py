import re
from datetime import datetime, timedelta, timezone

from dashboard import overview

NOW = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)  # a Thursday


def sig(days_ago: float, score: int = 40, category: str = "Insolvency", entities=(), title="t"):
    dt = NOW - timedelta(days=days_ago)
    return {"published_at": dt.isoformat(), "newsworthiness_score": score,
            "canonical_category": category, "entities": list(entities), "title": title}


class TestWeeks:
    def test_week_starts_are_mondays_ending_this_week(self):
        starts = overview.week_starts(NOW)
        assert len(starts) == overview.WEEKS
        assert all(s.weekday() == 0 and s.hour == 0 for s in starts)
        assert starts[-1] == datetime(2026, 10, 5, tzinfo=timezone.utc)

    def test_week_index(self):
        starts = overview.week_starts(NOW)
        assert overview.week_index(sig(0), starts) == overview.WEEKS - 1
        assert overview.week_index(sig(7), starts) == overview.WEEKS - 2
        assert overview.week_index(sig(400), starts) is None

    def test_nice_top(self):
        assert overview.nice_top(1) == 2 and overview.nice_top(44) == 50 and overview.nice_top(250) == 250


class TestTiles:
    def test_counts_and_comparisons(self):
        signals = [sig(1), sig(2), sig(3, score=75)] + [sig(10 + i) for i in range(8)]
        tiles = overview.headline_tiles(signals, NOW, active_patterns=4, themes_building=2,
                                        healthy=8, total_sources=9)
        by = {t.label: t for t in tiles}
        assert by["Signals this week"].value == "3"
        assert by["Signals this week"].note == "+1 vs 4-week average"  # 8 over 4 weeks = 2/week
        assert by["High relevance, last 30 days"].value == "1"
        assert by["Active patterns"].value == "4" and by["Themes building"].value == "2"
        assert by["Sources healthy"].value == "8/9"

    def test_no_status_drops_the_sources_tile(self):
        tiles = overview.headline_tiles([], NOW, 0, 0, None, None)
        assert [t.label for t in tiles][-1] == "Themes building"
        assert tiles[0].note == "Level with 4-week average"

    def test_first_tile_is_the_hero(self):
        out = overview.tiles_html([overview.Tile("A", "1"), overview.Tile("B", "2")])
        assert out.count("ov-hero") == 1


class TestVolume:
    def test_marks_high_relevance_weeks_and_escapes_titles(self):
        signals = [sig(0, score=80, title="<b>Big</b>"), sig(14), sig(15)]
        out = overview.weekly_volume_html(signals, NOW)
        assert out.count('class="ov-mark"') == 1
        assert "&lt;b&gt;Big&lt;/b&gt;" in out and "<b>Big</b>" not in out
        assert "Show as a table" in out and "3 signals over 18 weeks" in out

    def test_empty(self):
        assert "0 signals over 18 weeks" in overview.weekly_volume_html([], NOW)


class TestHeatmap:
    def test_rows_busiest_first_with_totals(self):
        signals = [sig(0, category="Policy and legislation")] * 3 + [sig(0, category="Insolvency")]
        out = overview.category_heatmap_html(signals, NOW, lambda name: "")
        assert out.index("Policy and legislation") < out.index("Insolvency")
        assert re.search(r'ov-htotal">3<', out) and re.search(r'ov-htotal">1<', out)

    def test_steps(self):
        th = overview.heat_thresholds([1, 1, 2, 3, 5, 8, 13, 0, 0])
        assert list(th) == sorted(th) and len(th) == 5 and th[-1] >= 13
        assert overview.heat_step(0, th) == overview.HEAT_EMPTY
        assert overview.heat_step(1, th) == overview.HEAT_RAMP[0]
        assert overview.heat_step(13, th) == overview.HEAT_RAMP[-1]

    def test_small_counts_use_one_step_each(self):
        assert overview.heat_thresholds([1, 2, 3]) == (1, 2, 3, 4, 5)


class TestMovers:
    def test_ranks_recent_and_excludes_regulators(self):
        signals = ([sig(1, entities=["Entain", "Gambling Commission"])] * 3
                   + [sig(40, entities=["Entain"])] * 5 + [sig(2, entities=["Rank"])])
        movers = overview.company_movers(
            signals, NOW, lambda s: s["entities"], lambda e: e == "Gambling Commission")
        assert [m["name"] for m in movers] == ["Entain", "Rank"]
        assert movers[0]["count"] == 3 and movers[0]["change"] == -2
        out = overview.movers_html(movers, lambda n: "")
        assert "−2" in out and "+1" in out

    def test_empty(self):
        assert "No companies named" in overview.movers_html([], lambda n: "")


class TestThemes:
    def test_bars_scale_to_the_hottest_and_say_direction_in_words(self):
        out = overview.themes_html([{"name": "Insolvency", "heat": 200, "direction": "building"},
                                    {"name": "Tax", "heat": 50, "direction": None}])
        assert "width:100.0%" in out and "width:25.0%" in out
        assert "Building" in out and "—" in out
