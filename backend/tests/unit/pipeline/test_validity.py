"""Unit tests for pipeline/validity.py — never had one before this port
(moved verbatim out of graph.py in the legacy code; test_graph.py's
TestIsValidCombination already covers is_valid_combination against the
module attribute it re-exports, but is_slot_complete never had coverage
at all)."""

from __future__ import annotations

from whattowear.pipeline.validity import is_slot_complete, is_valid_combination
from whattowear.schema import WardrobeItem


def _item(id: str, category: str) -> WardrobeItem:
    return WardrobeItem(id=id, category=category, colors=["#000000"], formality="casual", warmth=1, season=[])


def _wb(*items: WardrobeItem) -> dict[str, WardrobeItem]:
    return {it.id: it for it in items}


class TestIsSlotComplete:
    def test_top_bottom_footwear_is_complete(self) -> None:
        items = [_item("t", "top"), _item("j", "jeans"), _item("s", "sneakers")]
        assert is_slot_complete([i.id for i in items], _wb(*items)) is True

    def test_full_body_covers_top_and_bottom_halves(self) -> None:
        items = [_item("d", "dress"), _item("s", "sneakers")]
        assert is_slot_complete([i.id for i in items], _wb(*items)) is True

    def test_missing_footwear_is_incomplete(self) -> None:
        items = [_item("t", "top"), _item("j", "jeans")]
        assert is_slot_complete([i.id for i in items], _wb(*items)) is False

    def test_missing_bottom_half_is_incomplete(self) -> None:
        items = [_item("t", "top"), _item("s", "sneakers")]
        assert is_slot_complete([i.id for i in items], _wb(*items)) is False

    def test_unknown_item_id_is_ignored_not_erroring(self) -> None:
        items = [_item("t", "top"), _item("j", "jeans"), _item("s", "sneakers")]
        assert is_slot_complete([*[i.id for i in items], "ghost"], _wb(*items)) is True

    def test_empty_items_is_incomplete(self) -> None:
        assert is_slot_complete([], {}) is False


class TestIsValidCombination:
    def test_normal_outfit_is_valid(self) -> None:
        items = [_item("t", "top"), _item("j", "jeans"), _item("s", "sneakers")]
        assert is_valid_combination([i.id for i in items], _wb(*items)) is True

    def test_two_footwear_rejected(self) -> None:
        items = [_item("t", "top"), _item("s1", "sneakers"), _item("s2", "shoes")]
        assert is_valid_combination([i.id for i in items], _wb(*items)) is False

    def test_full_body_plus_separate_bottom_rejected(self) -> None:
        items = [_item("d", "dress"), _item("p", "trousers")]
        assert is_valid_combination([i.id for i in items], _wb(*items)) is False

    def test_layered_tops_allowed(self) -> None:
        items = [_item("tee", "t-shirt"), _item("card", "cardigan"), _item("j", "jeans")]
        assert is_valid_combination([i.id for i in items], _wb(*items)) is True
