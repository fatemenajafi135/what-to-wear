"""Integration test for pipeline/graph.py's `verify_grounding` node (Feature
005 US2/FR-003-005).

Hits the real Postgres catalog table (`crud.list_catalog_items`, read-only —
no fixture/rollback needed) the same way `verify_grounding` does in
production; no mocking of the DB call itself. This is the spec's own
Independent Test for US2: inject an outfit referencing a nonexistent item id
and confirm it's withheld while valid outfits still come through.
"""

from __future__ import annotations

from whattowear.pipeline import graph
from whattowear.schema import Context, DimensionScore, Rationale, ScoredOutfit, WardrobeItem


def _item(id: str) -> WardrobeItem:
    return WardrobeItem(id=id, category="t-shirt", colors=["#000000"], formality="casual", warmth=1, season=[])


def _scored_outfit(item_ids: list[str]) -> ScoredOutfit:
    return ScoredOutfit(
        items=item_ids,
        rationale=[Rationale(text="r", cites=["L1-x"])],
        scores=[
            DimensionScore(dimension="color_harmony", value=0.8, reason="r"),
            DimensionScore(dimension="formality_coherence", value=0.7, reason="r"),
            DimensionScore(dimension="weather_fitness", value=0.6, reason="r"),
            DimensionScore(dimension="silhouette_balance", value=0.5, reason="r"),
        ],
        rank_score=0.5,
    )


def test_outfit_with_unowned_item_is_dropped_valid_ones_remain():
    owned_a, owned_b = _item("owned-a"), _item("owned-b")
    ctx = Context(occasion="dinner", formality="casual", wardrobe=[owned_a, owned_b])

    good_outfit = _scored_outfit(["owned-a", "owned-b"])
    bad_outfit = _scored_outfit(["owned-a", "definitely-not-a-real-item-id-005"])
    state = {"ctx": ctx, "scored_outfits": [good_outfit, bad_outfit]}

    result = graph.verify_grounding(state)

    assert result["scored_outfits"] == [good_outfit]


def test_all_outfits_bad_yields_empty_list():
    owned_a = _item("owned-a")
    ctx = Context(occasion="dinner", formality="casual", wardrobe=[owned_a])
    bad_outfit = _scored_outfit(["definitely-not-a-real-item-id-005"])
    state = {"ctx": ctx, "scored_outfits": [bad_outfit]}

    result = graph.verify_grounding(state)

    assert result["scored_outfits"] == []


def test_all_outfits_good_are_unaffected():
    owned_a, owned_b = _item("owned-a"), _item("owned-b")
    ctx = Context(occasion="dinner", formality="casual", wardrobe=[owned_a, owned_b])
    outfits = [_scored_outfit(["owned-a"]), _scored_outfit(["owned-b"])]
    state = {"ctx": ctx, "scored_outfits": outfits}

    result = graph.verify_grounding(state)

    assert result["scored_outfits"] == outfits
