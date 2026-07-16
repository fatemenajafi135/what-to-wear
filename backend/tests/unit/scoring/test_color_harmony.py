"""Unit tests for scoring/color_harmony.py (Feature 002 Phase 2)."""

from __future__ import annotations

from whattowear.schema import Context, WardrobeItem
from whattowear.scoring import color_harmony


def _item(id, category="top", *, colors=None, formality="casual", warmth=1) -> WardrobeItem:
    return WardrobeItem(
        id=id, category=category, colors=colors or ["#000000"],
        formality=formality, warmth=warmth, season=["summer"],
    )


def _ctx() -> Context:
    return Context(occasion="dinner", formality="casual")


class TestColorHarmonyScore:
    def test_high_contrast_pair_scores_higher_than_low_contrast_pair(self):
        high = color_harmony.score(
            [_item("a", colors=["#000000"]), _item("b", "jeans", colors=["#ffffff"])], _ctx()
        )
        low = color_harmony.score(
            [_item("a", colors=["#808080"]), _item("b", "jeans", colors=["#808080"])], _ctx()
        )
        assert high.value > low.value

    def test_reason_is_present(self):
        result = color_harmony.score(
            [_item("a", colors=["#000000"]), _item("b", "jeans", colors=["#ffffff"])], _ctx()
        )
        assert result.reason

    def test_dimension_is_color_harmony(self):
        result = color_harmony.score([_item("a")], _ctx())
        assert result.dimension == "color_harmony"

    def test_deterministic_rescoring_is_identical(self):
        items = [_item("a", colors=["#1b2a4a"]), _item("b", "jeans", colors=["#c8ad7f"])]
        ctx = _ctx()
        first = color_harmony.score(items, ctx)
        second = color_harmony.score(items, ctx)
        assert first == second

    def test_value_within_bounds(self):
        result = color_harmony.score(
            [_item("a", colors=["#000000"]), _item("b", "jeans", colors=["#ffffff"])], _ctx()
        )
        assert 0.0 <= result.value <= 1.0
