"""Unit tests for pipeline/grounding.py (Feature 005 US2/FR-003-005)."""

from __future__ import annotations

from whattowear.pipeline.grounding import verify_outfit_grounding
from whattowear.schema import WardrobeItem


def _item(id: str) -> WardrobeItem:
    return WardrobeItem(id=id, category="t-shirt", colors=["#000000"], formality="casual", warmth=1, season=[])


class TestVerifyOutfitGrounding:
    def test_all_items_owned_passes(self):
        wardrobe_by_id = {"a": _item("a"), "b": _item("b")}
        assert verify_outfit_grounding(["a", "b"], wardrobe_by_id, catalog_ids=set()) is True

    def test_unknown_item_id_fails(self):
        wardrobe_by_id = {"a": _item("a")}
        assert verify_outfit_grounding(["a", "nonexistent"], wardrobe_by_id, catalog_ids=set()) is False

    def test_empty_item_list_passes_vacuously(self):
        assert verify_outfit_grounding([], wardrobe_by_id={}, catalog_ids=set()) is True

    def test_catalog_only_item_still_passes(self):
        """Principle IV: closet OR catalog. No outfit draws from the catalog
        today (Feature 002 Phase 3), but the predicate itself must accept a
        catalog id, not just a wardrobe id."""
        wardrobe_by_id = {"a": _item("a")}
        assert verify_outfit_grounding(["a", "catalog-item-1"], wardrobe_by_id, catalog_ids={"catalog-item-1"}) is True

    def test_item_in_neither_wardrobe_nor_catalog_fails(self):
        wardrobe_by_id = {"a": _item("a")}
        assert verify_outfit_grounding(["a", "ghost"], wardrobe_by_id, catalog_ids={"catalog-item-1"}) is False
