"""Unit tests for pipeline/graph.py's `wardrobe_retrieval` node (Feature 002
Phase 3, T035): hard-constraint pruning + the k=8-per-slot cap (FR-014).
"""

from __future__ import annotations

from whattowear.pipeline import graph
from whattowear.schema import Context, WardrobeItem


def _item(id, category, *, formality="casual", warmth=1, season=None) -> WardrobeItem:
    return WardrobeItem(
        id=id, category=category, colors=["#000000"],
        formality=formality, warmth=warmth, season=season or [],
    )


class TestWardrobeRetrievalPruning:
    def test_excludes_items_two_notches_below_the_formality_floor(self):
        ctx = Context(
            occasion="gala", formality="black_tie",
            wardrobe=[_item("gown", "gown", formality="black_tie"), _item("tee", "top", formality="casual")],
        )
        result = graph.wardrobe_retrieval({"ctx": ctx})
        kept_ids = {it.id for items in result["candidates"].values() for it in items}
        assert "gown" in kept_ids
        assert "tee" not in kept_ids

    def test_excludes_items_over_the_per_band_warmth_ceiling(self):
        ctx = Context(
            occasion="beach", formality="casual", temp_band="hot",
            wardrobe=[
                _item("tank", "top", warmth=1),
                _item("parka", "coat", warmth=5),
            ],
        )
        result = graph.wardrobe_retrieval({"ctx": ctx})
        kept_ids = {it.id for items in result["candidates"].values() for it in items}
        assert "tank" in kept_ids
        assert "parka" not in kept_ids

    def test_excludes_items_outside_the_requested_season(self):
        ctx = Context(
            occasion="office", formality="business_casual", season="summer",
            wardrobe=[
                _item("linen_shirt", "top", formality="business_casual", season=["summer"]),
                _item("wool_sweater", "sweater", formality="business_casual", season=["winter"]),
            ],
        )
        result = graph.wardrobe_retrieval({"ctx": ctx})
        kept_ids = {it.id for items in result["candidates"].values() for it in items}
        assert "linen_shirt" in kept_ids
        assert "wool_sweater" not in kept_ids

    def test_candidate_count_never_exceeds_k8_per_slot(self):
        wardrobe = [_item(f"top{i}", "top", formality="casual") for i in range(50)]
        ctx = Context(occasion="dinner", formality="casual", wardrobe=wardrobe)
        result = graph.wardrobe_retrieval({"ctx": ctx})
        assert len(result["candidates"]["top"]) == 8

    def test_slots_are_grouped_by_category_group(self):
        ctx = Context(
            occasion="dinner", formality="casual",
            wardrobe=[_item("t", "top"), _item("j", "jeans"), _item("s", "sneakers")],
        )
        result = graph.wardrobe_retrieval({"ctx": ctx})
        assert set(result["candidates"].keys()) == {"top", "bottom", "footwear"}
