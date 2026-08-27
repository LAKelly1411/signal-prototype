from src.collectors.base import RawItem
from src.normalise import make_id, to_signal
from src.score import _strip_fences

ITEM = RawItem(
    source="gambling_commission",
    source_url="https://example.gov.uk/news/thing",
    title="Operator fined",
    raw_summary="A summary",
    published_at="2026-08-01T00:00:00+00:00",
    signal_type="enforcement",
)


class TestToSignal:
    def test_id_is_stable_across_runs(self):
        assert to_signal(ITEM)["id"] == to_signal(ITEM)["id"]

    def test_source_id_wins_over_url_as_the_stable_key(self):
        with_id = RawItem(**{**ITEM.__dict__, "source_id": "abc"})
        assert with_id and to_signal(with_id)["id"] == make_id(
            "gambling_commission", "abc"
        )

    def test_url_changes_produce_a_different_id(self):
        moved = RawItem(**{**ITEM.__dict__, "source_url": "https://example.gov.uk/x"})
        assert to_signal(moved)["id"] != to_signal(ITEM)["id"]

    def test_starts_unscored_and_uncanonicalised(self):
        signal = to_signal(ITEM)
        assert signal["newsworthiness_score"] is None
        assert signal["entities"] == []
        assert signal["canonical_entities"] == []
        assert signal["status"] == "new"

    def test_estimated_date_flag_is_carried_through(self):
        assert to_signal(ITEM)["published_at_estimated"] is False
        guessed = RawItem(**{**ITEM.__dict__, "published_at_estimated": True})
        assert to_signal(guessed)["published_at_estimated"] is True


class TestStripFences:
    def test_plain_json_is_untouched(self):
        assert _strip_fences('{"a": 1}') == '{"a": 1}'

    def test_removes_json_fences(self):
        assert _strip_fences('```json\n{"a": 1}\n```') == '{"a": 1}'

    def test_removes_bare_fences(self):
        assert _strip_fences('```\n{"a": 1}\n```') == '{"a": 1}'

    def test_tolerates_surrounding_whitespace(self):
        assert _strip_fences('  \n```json\n{"a": 1}\n```  ') == '{"a": 1}'
