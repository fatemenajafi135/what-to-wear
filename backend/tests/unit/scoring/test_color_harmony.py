"""Unit tests for scoring/color_harmony.py.

Feature 002 Phase 2 introduced this scorer using raw WCAG contrast, which
was inverted (rewarded clashes, punished tonal pairings). Feature 009
rewrites it around real color theory — see research.md Decision 1 for the
exact rule table and how each threshold below was verified against the
real palette hexes.
"""

from __future__ import annotations

from whattowear.schema import Context, WardrobeItem
from whattowear.scoring import color_harmony


def _item(id, category="top", *, colors=None, formality="casual", warmth=1) -> WardrobeItem:
    return WardrobeItem(
        id=id,
        category=category,
        colors=colors or ["#000000"],
        formality=formality,
        warmth=warmth,
        season=["summer"],
    )


def _ctx() -> Context:
    return Context(occasion="dinner", formality="casual")


class TestColorHarmonyScore:
    def test_equal_weight_complementary_clash_scores_low(self):
        # tomato red + emerald green: ~113 deg apart, neither analogous nor
        # a genuine complementary pairing — the classic "clashing" case.
        result = color_harmony.score(
            [
                _item("a", colors=["#ff6347"]),
                _item("b", "jeans", colors=["#046307"]),
            ],
            _ctx(),
        )
        assert result.value < 0.45

    def test_neutral_anchored_outfit_scores_high(self):
        result = color_harmony.score(
            [
                _item("a", colors=["#1b2a4a"]),  # navy
                _item("b", "jeans", colors=["#36454f"]),  # charcoal
                _item("c", "shoes", colors=["#ffffff"]),  # white
            ],
            _ctx(),
        )
        assert result.value >= 0.8

    def test_all_neutral_tones_scores_high(self):
        result = color_harmony.score(
            [
                _item("a", colors=["#ded0b6"]),  # oatmeal
                _item("b", "jeans", colors=["#c19a6b"]),  # camel
                _item("c", "shoes", colors=["#fffdd0"]),  # cream
            ],
            _ctx(),
        )
        assert result.value >= 0.8

    def test_complementary_pair_with_clear_accent_scores_higher_than_equal_weight(self):
        # cobalt, not navy: navy is a *named neutral* in FASHION_COLOR_PALETTE
        # (styling convention — "navy is the new black"), so it can never be
        # the chromatic partner in a 2-hue complementary comparison; cobalt is
        # the palette's other deep-blue entry, classified chromatic.
        accented = color_harmony.score(
            [
                _item("a", colors=["#0047ab"]),  # cobalt
                _item("b", "jeans", colors=["#ffdb58"]),  # mustard — accent
            ],
            _ctx(),
        )
        equal_weight = color_harmony.score(
            [
                _item("a", colors=["#0047ab"]),  # cobalt
                # constructed: same saturation/lightness as cobalt, opposite hue
                _item("b", "jeans", colors=["#ab6400"]),
            ],
            _ctx(),
        )
        assert accented.value >= 0.7
        assert equal_weight.value < 0.5
        assert accented.value > equal_weight.value

    def test_analogous_reds_score_high(self):
        result = color_harmony.score(
            [
                _item("a", colors=["#800020"]),  # burgundy
                _item("b", "jeans", colors=["#de5d83"]),  # blush pink
            ],
            _ctx(),
        )
        assert result.value >= 0.7

    def test_four_saturated_clashing_hues_score_lowest(self):
        result = color_harmony.score(
            [
                _item("a", colors=["#ff0000"]),
                _item("b", "jeans", colors=["#00ff00"]),
                _item("c", "shoes", colors=["#0000ff"]),
                _item("d", "jacket", colors=["#ff00ff"]),
            ],
            _ctx(),
        )
        assert result.value < 0.3

    def test_single_dominant_hue_scores_high(self):
        result = color_harmony.score(
            [
                _item("a", colors=["#800020"]),  # burgundy
                _item("b", "jeans", colors=["#800020"]),  # same burgundy
            ],
            _ctx(),
        )
        assert result.value >= 0.8

    def test_reason_is_present(self):
        result = color_harmony.score([_item("a", colors=["#1b2a4a"]), _item("b", "jeans", colors=["#36454f"])], _ctx())
        assert result.reason

    def test_dimension_is_color_harmony(self):
        result = color_harmony.score([_item("a")], _ctx())
        assert result.dimension == "color_harmony"

    def test_not_enough_colors_is_neutral(self):
        result = color_harmony.score([_item("a", colors=["#1b2a4a"])], _ctx())
        assert result.value == 0.5

    def test_deterministic_rescoring_is_identical(self):
        items = [_item("a", colors=["#1b2a4a"]), _item("b", "jeans", colors=["#c8ad7f"])]
        ctx = _ctx()
        first = color_harmony.score(items, ctx)
        second = color_harmony.score(items, ctx)
        assert first == second

    def test_value_within_bounds(self):
        result = color_harmony.score([_item("a", colors=["#ff6347"]), _item("b", "jeans", colors=["#046307"])], _ctx())
        assert 0.0 <= result.value <= 1.0
