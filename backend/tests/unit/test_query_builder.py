"""Unit tests for pipeline/query_builder.py (Feature 002 Phase 1 backfill).

The router and the two query synthesizers are pure functions of Context. The
router rules (handoff §3) are load-bearing: L1+L4 always, L3 only when season
is known, L2 never.
"""

from __future__ import annotations

from whattowear.pipeline import query_builder
from whattowear.schema import Context


def _ctx(**overrides) -> Context:
    defaults = dict(occasion="dinner party", formality="smart_casual")
    defaults.update(overrides)
    return Context(**defaults)


class TestRoute:
    def test_l1_and_l4_always_selected(self):
        layers = query_builder.route(_ctx(season=None))
        assert "L1" in layers
        assert "L4" in layers

    def test_l3_selected_only_when_season_known(self):
        assert "L3" not in query_builder.route(_ctx(season=None))
        assert "L3" in query_builder.route(_ctx(season="winter"))

    def test_l2_never_selected(self):
        assert "L2" not in query_builder.route(_ctx(season="summer"))


class TestNaiveQuery:
    def test_includes_occasion_and_formality_with_underscores_spaced(self):
        q = query_builder.naive_query(_ctx(occasion="job interview", formality="business_casual"))
        assert "job interview" in q
        assert "business casual" in q
        assert "business_casual" not in q

    def test_optional_bits_included_when_present(self):
        q = query_builder.naive_query(_ctx(mood="relaxed", temp_band="cold", season="winter"))
        assert "relaxed mood" in q
        assert "cold weather" in q
        assert "winter" in q

    def test_optional_bits_omitted_when_absent(self):
        q = query_builder.naive_query(_ctx(mood=None, temp_band=None, season=None))
        assert "mood" not in q
        assert "weather" not in q


class TestL3Query:
    def test_assembles_present_parts_only(self):
        q = query_builder.l3_query(
            _ctx(occasion="brunch", formality="casual", mood="playful", temp_band="warm", season="spring")
        )
        assert q == "spring brunch outfit casual playful tone warm weather"

    def test_omits_absent_parts_and_has_no_stray_whitespace(self):
        q = query_builder.l3_query(_ctx(occasion="gala", formality="black_tie", mood=None, temp_band=None, season=None))
        assert q == "gala outfit black tie"
