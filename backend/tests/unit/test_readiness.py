"""Unit tests for readiness.py (feature 008): the three-band closet gate
docs/design-decisions.md §11 specifies — count floor AND slot coverage, not
either alone."""

from __future__ import annotations

import pytest

from whattowear.readiness import evaluate_wardrobe_readiness
from whattowear.schema import WardrobeItem

MIN_ITEMS = 5
SPARSE_THRESHOLD = 15


def _item(category: str, item_id: str | None = None) -> WardrobeItem:
    return WardrobeItem(
        id=item_id or category,
        category=category,
        formality="casual",
        warmth=2,
        season=["spring"],
    )


def _evaluate(items: list[WardrobeItem]):
    return evaluate_wardrobe_readiness(items, min_items=MIN_ITEMS, sparse_threshold=SPARSE_THRESHOLD)


class TestReadyBand:
    def test_full_skeleton_a_at_the_floor_is_ready(self):
        items = [_item("top", "1"), _item("bottom", "2"), _item("footwear", "3"), _item("top", "4"), _item("top", "5")]
        result = _evaluate(items)
        assert result.ready is True
        assert result.missing == []

    def test_full_skeleton_b_at_the_floor_is_ready(self):
        items = [
            _item("full_body", "1"),
            _item("footwear", "2"),
            _item("accessory", "3"),
            _item("accessory", "4"),
            _item("accessory", "5"),
        ]
        result = _evaluate(items)
        assert result.ready is True
        assert result.missing == []


class TestBlockedOnCoverage:
    def test_missing_footwear_only(self):
        items = [_item("top", "1"), _item("bottom", "2"), _item("top", "3"), _item("bottom", "4"), _item("top", "5")]
        result = _evaluate(items)
        assert result.ready is False
        assert result.missing == ["a pair of shoes"]

    def test_missing_top_and_shoes_prefers_the_closer_skeleton(self):
        # bottom + 4 accessories: skeleton A is missing top+shoes (2 gaps),
        # skeleton B is missing full_body+shoes (2 gaps) — tie favors A.
        items = [
            _item("bottom", "1"),
            _item("accessory", "2"),
            _item("accessory", "3"),
            _item("accessory", "4"),
            _item("accessory", "5"),
        ]
        result = _evaluate(items)
        assert result.ready is False
        assert result.missing == ["a top", "a pair of shoes"]

    def test_bottom_and_footwear_only_prefers_skeleton_a_gap(self):
        # bottom+footwear present: skeleton A missing only "a top" (1 gap),
        # skeleton B missing full_body (1 gap, footwear already present) — tie
        # favors A, and either way this exercises the closer-skeleton pick.
        items = [
            _item("bottom", "1"),
            _item("footwear", "2"),
            _item("accessory", "3"),
            _item("accessory", "4"),
            _item("accessory", "5"),
        ]
        result = _evaluate(items)
        assert result.ready is False
        assert result.missing == ["a top"]


class TestBlockedOnCountFloor:
    def test_coverage_satisfied_but_under_floor_has_no_missing_list(self):
        items = [_item("top", "1"), _item("bottom", "2"), _item("footwear", "3")]
        result = _evaluate(items)
        assert result.ready is False
        assert result.missing == []

    def test_empty_closet_is_blocked(self):
        # Coverage also fails on zero items (not just the count floor) —
        # skeleton B (2 gaps: full_body + shoes) beats skeleton A (3 gaps:
        # top + bottom + shoes), so `missing` is populated here, unlike the
        # "coverage satisfied, only the floor is short" case above.
        result = _evaluate([])
        assert result.ready is False
        assert result.missing == ["a full-body piece like a dress or jumpsuit", "a pair of shoes"]


class TestSparseBand:
    def test_just_under_sparse_threshold_is_sparse(self):
        items = [_item("top", str(i)) for i in range(12)] + [_item("bottom", "b"), _item("footwear", "f")]
        result = _evaluate(items)
        assert result.ready is True
        assert result.sparse is True

    def test_at_sparse_threshold_is_not_sparse(self):
        items = [_item("top", str(i)) for i in range(13)] + [_item("bottom", "b"), _item("footwear", "f")]
        assert len(items) == SPARSE_THRESHOLD
        result = _evaluate(items)
        assert result.ready is True
        assert result.sparse is False

    def test_well_above_sparse_threshold_is_not_sparse(self):
        items = [_item("top", str(i)) for i in range(20)] + [_item("bottom", "b"), _item("footwear", "f")]
        result = _evaluate(items)
        assert result.ready is True
        assert result.sparse is False


@pytest.mark.parametrize("min_items,sparse_threshold", [(5, 15), (1, 3), (0, 1)])
def test_thresholds_are_parameters_not_hardcoded(min_items, sparse_threshold):
    """design-decisions.md §11: both thresholds must be real config values,
    not literals baked into the function — this pins that contract."""
    items = [_item("top", "1"), _item("bottom", "2"), _item("footwear", "3")]
    result = evaluate_wardrobe_readiness(items, min_items=min_items, sparse_threshold=sparse_threshold)
    assert result.ready == (len(items) >= min_items)
