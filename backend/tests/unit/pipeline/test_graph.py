"""Unit tests for pipeline/graph.py.

Feature 002 Phase 3, T035: `wardrobe_retrieval`'s hard-constraint pruning +
the k=8-per-slot cap (FR-014).
Feature 002 Phase 4, T044: refinement-intent parsing and the delta-shifted
pruning bounds it feeds (FR-013), the "alternatives" exclusion (FR-012), and
the unsatisfiable-refinement fallback (FR-015).
"""

from __future__ import annotations

from whattowear.pipeline import graph
from whattowear.schema import Context, DimensionScore, Rationale, ScoredOutfit, WardrobeItem


def _item(id, category, *, formality="casual", warmth=1, season=None) -> WardrobeItem:
    return WardrobeItem(
        id=id, category=category, colors=["#000000"],
        formality=formality, warmth=warmth, season=season or [],
    )


def _scored_outfit_multi(item_ids: list[str]) -> ScoredOutfit:
    return ScoredOutfit(
        items=item_ids,
        rationale=[Rationale(text="r", cites=["L1-x"])],
        scores=[
            DimensionScore(dimension="color_harmony", value=0.5, reason="r"),
            DimensionScore(dimension="formality_coherence", value=0.5, reason="r"),
            DimensionScore(dimension="weather_fitness", value=0.5, reason="r"),
            DimensionScore(dimension="silhouette_balance", value=0.5, reason="r"),
        ],
        rank_score=0.5,
    )


def _scored_outfit(item_id: str) -> ScoredOutfit:
    return _scored_outfit_multi([item_id])


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


class TestParseRefinementIntent:
    def test_warmer_utterance_parses_to_warmer_delta(self):
        assert graph._parse_refinement_intent("warmer please") == ["warmer"]

    def test_less_formal_utterance_parses_to_less_formal_delta(self):
        assert graph._parse_refinement_intent("something less formal") == ["less_formal"]

    def test_alternatives_utterance_parses_to_alternatives_delta(self):
        assert graph._parse_refinement_intent("give me a different option") == ["alternatives"]

    def test_unrelated_utterance_parses_to_no_deltas(self):
        assert graph._parse_refinement_intent("banana") == []

    def test_multiple_intents_in_one_utterance_all_parse(self):
        assert graph._parse_refinement_intent("warmer and less formal") == ["warmer", "less_formal"]


class TestParseRequestRefinementDetection:
    def test_no_original_context_is_a_fresh_request(self):
        result = graph.parse_request({"occasion": "office", "thread_id": "t1"})
        assert result["refinement_deltas"] == []

    def test_original_context_present_parses_the_new_utterance(self):
        ctx = Context(occasion="office", formality="business_casual")
        result = graph.parse_request(
            {"occasion": "warmer", "thread_id": "t1", "original_context": ctx, "refinement_deltas": []}
        )
        assert result["refinement_deltas"] == ["warmer"]

    def test_deltas_accumulate_across_turns(self):
        ctx = Context(occasion="office", formality="business_casual")
        result = graph.parse_request(
            {
                "occasion": "less formal", "thread_id": "t1",
                "original_context": ctx, "refinement_deltas": ["warmer"],
            }
        )
        assert result["refinement_deltas"] == ["warmer", "less_formal"]


class TestItemFitsHardConstraintsRefinementDeltas:
    def test_warmer_delta_raises_the_warmth_floor(self):
        ctx = Context(occasion="office", formality="business_casual")
        cold_item = _item("a", "top", formality="business_casual", warmth=1)
        warm_item = _item("b", "top", formality="business_casual", warmth=4)
        assert graph._item_fits_hard_constraints(cold_item, ctx, ["warmer"]) is False
        assert graph._item_fits_hard_constraints(warm_item, ctx, ["warmer"]) is True

    def test_no_warmer_delta_does_not_apply_a_floor(self):
        ctx = Context(occasion="office", formality="business_casual")
        cold_item = _item("a", "top", formality="business_casual", warmth=0)
        assert graph._item_fits_hard_constraints(cold_item, ctx, []) is True

    def test_warmer_delta_does_not_gate_footwear_or_accessories(self):
        # footwear/accessories rarely carry high warmth values in practice
        # (a fixture-data reality) -- gating them the same way core layers
        # are gated starves those slots and forces the FR-015 fallback far
        # more than "warmer" should.
        ctx = Context(occasion="office", formality="business_casual")
        cold_shoe = _item("a", "sneakers", formality="business_casual", warmth=0)
        cold_belt = _item("b", "belt", formality="business_casual", warmth=0)
        assert graph._item_fits_hard_constraints(cold_shoe, ctx, ["warmer"]) is True
        assert graph._item_fits_hard_constraints(cold_belt, ctx, ["warmer"]) is True

    def test_less_formal_delta_lowers_the_acceptable_band(self):
        ctx = Context(occasion="office", formality="business_casual")  # notch 2
        original_level = _item("a", "top", formality="business_casual")  # notch 2
        one_below = _item("b", "top", formality="smart_casual")  # notch 1
        assert graph._item_fits_hard_constraints(original_level, ctx, ["less_formal"]) is False
        assert graph._item_fits_hard_constraints(one_below, ctx, ["less_formal"]) is True

    def test_multiple_less_formal_deltas_shift_further_down(self):
        ctx = Context(occasion="office", formality="business_casual")  # notch 2
        one_below = _item("a", "top", formality="smart_casual")  # notch 1
        two_below = _item("b", "top", formality="casual")  # notch 0
        assert graph._item_fits_hard_constraints(one_below, ctx, ["less_formal", "less_formal"]) is False
        assert graph._item_fits_hard_constraints(two_below, ctx, ["less_formal", "less_formal"]) is True


class TestGenerateOutfitsAlternativesExclusion:
    """Outfits must be slot-complete (top+bottom+footwear) to survive
    generate_outfits at all (FR-011) — every outfit built here covers all
    three so the alternatives-exclusion logic is what's actually exercised,
    not the completeness filter."""

    def _complete_outfit_items(self, ids: tuple[str, str, str]) -> tuple:
        top_id, bottom_id, shoe_id = ids
        return (
            _item(top_id, "top"),
            _item(bottom_id, "jeans"),
            _item(shoe_id, "sneakers"),
        )

    def test_alternatives_delta_excludes_previously_shown_item_sets(self, mocker):
        from whattowear.pipeline.generator import GenOutfit, GenOutput, GenRationale

        shown_top, shown_bottom, shown_shoe = self._complete_outfit_items(("st", "sb", "ss"))
        new_top, new_bottom, new_shoe = self._complete_outfit_items(("nt", "nb", "ns"))
        repeated = GenOutfit(
            items=["st", "sb", "ss"], rationale=[GenRationale(text="r", cites=["L1-x"])]
        )
        fresh = GenOutfit(items=["nt", "nb", "ns"], rationale=[GenRationale(text="r", cites=["L1-x"])])
        mocker.patch.object(graph, "generate", return_value=GenOutput(outfits=[repeated, fresh]))

        wardrobe = [shown_top, shown_bottom, shown_shoe, new_top, new_bottom, new_shoe]
        ctx = Context(occasion="office", formality="business_casual", wardrobe=wardrobe)
        state = {
            "ctx": ctx,
            "candidates": {"top": [shown_top, new_top], "bottom": [shown_bottom, new_bottom],
                            "footwear": [shown_shoe, new_shoe]},
            "retrieval": mocker.Mock(),
            "refinement_deltas": ["alternatives"],
            "last_result": mocker.Mock(outfits=[_scored_outfit_multi(["st", "sb", "ss"])]),
        }

        result = graph.generate_outfits(state)

        kept_item_sets = [frozenset(o.items) for o in result["generated"].outfits]
        assert frozenset(["st", "sb", "ss"]) not in kept_item_sets
        assert frozenset(["nt", "nb", "ns"]) in kept_item_sets

    def test_no_alternatives_delta_keeps_all_generated_outfits(self, mocker):
        from whattowear.pipeline.generator import GenOutfit, GenOutput, GenRationale

        top, bottom, shoe = self._complete_outfit_items(("a", "b", "c"))
        outfit = GenOutfit(items=["a", "b", "c"], rationale=[GenRationale(text="r", cites=["L1-x"])])
        mocker.patch.object(graph, "generate", return_value=GenOutput(outfits=[outfit]))

        ctx = Context(occasion="office", formality="business_casual", wardrobe=[top, bottom, shoe])
        state = {
            "ctx": ctx,
            "candidates": {"top": [top], "bottom": [bottom], "footwear": [shoe]},
            "retrieval": mocker.Mock(),
            "refinement_deltas": [], "last_result": None,
        }

        result = graph.generate_outfits(state)

        assert len(result["generated"].outfits) == 1


class TestExplainUnsatisfiableRefinementFallback:
    def test_empty_scored_outfits_during_refinement_falls_back_to_last_result(self, mocker):
        from whattowear.pipeline.generator import GenOutput
        from whattowear.retrieval.base import RetrievalResult

        ctx = Context(occasion="office", formality="business_casual")
        previous = graph.SuggestResult(outfits=[_scored_outfit("a")], sources=[], context=ctx)
        state = {
            "ctx": ctx,
            "scored_outfits": [],
            "generated": GenOutput(outfits=[]),
            "retrieval": RetrievalResult(),
            "thread_id": "t1",
            "refinement_deltas": ["warmer"],
            "last_result": previous,
        }

        result = graph.explain(state)

        assert result["result"] == previous
        assert result["note"] is not None
        assert result["last_result"] == previous

    def test_empty_scored_outfits_without_refinement_gets_the_plain_empty_note(self, mocker):
        from whattowear.pipeline.generator import GenOutput
        from whattowear.retrieval.base import RetrievalResult

        ctx = Context(occasion="office", formality="business_casual")
        state = {
            "ctx": ctx,
            "scored_outfits": [],
            "generated": GenOutput(outfits=[]),
            "retrieval": RetrievalResult(),
            "thread_id": "t1",
            "refinement_deltas": [],
            "last_result": None,
        }

        result = graph.explain(state)

        assert result["result"].outfits == []
        assert "enough items" in result["note"]
