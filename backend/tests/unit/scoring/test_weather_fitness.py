"""Unit tests for scoring/weather_fitness.py (Feature 002 Phase 2)."""

from __future__ import annotations

from whattowear.schema import Context, WardrobeItem
from whattowear.scoring import weather_fitness


def _item(id, category="top", *, warmth=1) -> WardrobeItem:
    return WardrobeItem(
        id=id,
        category=category,
        colors=["#000000"],
        formality="casual",
        warmth=warmth,
        season=["winter"],
    )


def _ctx(temp_band=None) -> Context:
    return Context(occasion="dinner", formality="casual", temp_band=temp_band)


class TestWeatherFitnessScore:
    def test_cold_context_no_outerwear_scores_lower_than_with_outerwear(self):
        no_outer = weather_fitness.score([_item("t", "top", warmth=1), _item("j", "jeans", warmth=1)], _ctx("cold"))
        with_outer = weather_fitness.score(
            [_item("t", "top", warmth=1), _item("j", "jeans", warmth=1), _item("c", "coat", warmth=4)],
            _ctx("cold"),
        )
        assert with_outer.value > no_outer.value

    def test_deterministic_rescoring_is_identical(self):
        items = [_item("t", "top", warmth=2), _item("j", "jeans", warmth=2)]
        ctx = _ctx("mild")
        assert weather_fitness.score(items, ctx) == weather_fitness.score(items, ctx)

    def test_no_temp_band_is_neutral(self):
        result = weather_fitness.score([_item("t", "top")], _ctx(None))
        assert result.value == 0.5

    def test_reason_is_present(self):
        result = weather_fitness.score([_item("t", "top")], _ctx("mild"))
        assert result.reason
