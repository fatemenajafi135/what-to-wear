"""Unit tests for pipeline/query_builder.py — never had one before this port."""

from __future__ import annotations

from whattowear.pipeline import query_builder
from whattowear.schema import Context


class TestRoute:
    def test_always_includes_l4_and_l1(self) -> None:
        ctx = Context(occasion="office", formality="business_casual")
        assert set(query_builder.route(ctx)) >= {"L4", "L1"}

    def test_includes_l3_only_when_season_known(self) -> None:
        with_season = Context(occasion="office", formality="business_casual", season="autumn")
        without_season = Context(occasion="office", formality="business_casual")
        assert "L3" in query_builder.route(with_season)
        assert "L3" not in query_builder.route(without_season)

    def test_l2_is_never_selected(self) -> None:
        ctx = Context(occasion="office", formality="business_casual", season="autumn")
        assert "L2" not in query_builder.route(ctx)


class TestNaiveQuery:
    def test_includes_occasion_and_formality(self) -> None:
        ctx = Context(occasion="wedding", formality="formal")
        q = query_builder.naive_query(ctx)
        assert "wedding" in q
        assert "formal" in q

    def test_omits_unset_optional_fields(self) -> None:
        ctx = Context(occasion="office", formality="business_casual")
        q = query_builder.naive_query(ctx)
        assert "mood" not in q

    def test_includes_mood_temp_band_and_season_when_present(self) -> None:
        ctx = Context(occasion="dinner", formality="smart_casual", mood="playful", temp_band="cool", season="autumn")
        q = query_builder.naive_query(ctx)
        assert "playful mood" in q
        assert "cool weather" in q
        assert "autumn" in q


class TestL3Query:
    def test_includes_all_known_parts(self) -> None:
        ctx = Context(
            occasion="office", formality="business_casual", mood="confident", temp_band="mild", season="spring"
        )
        q = query_builder.l3_query(ctx)
        assert "office" in q
        assert "outfit" in q
        assert "business casual" in q
        assert "confident tone" in q
        assert "mild weather" in q
        assert "spring" in q

    def test_omits_unset_parts_without_stray_whitespace(self) -> None:
        ctx = Context(occasion="office", formality="business_casual")
        q = query_builder.l3_query(ctx)
        assert "  " not in q
        assert q == q.strip()
