"""Unit tests for pipeline/engine.py — the opt-in deterministic-selection
approach. Covers enumerate_outfits' skeleton counts, full_body handling,
coherence-guard exclusion and outerwear crossing, and engine_write's
selection validation and deterministic fallback.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from whattowear.pipeline import engine
from whattowear.pipeline.generator import GenRationale
from whattowear.schema import Context, DimensionScore, Rationale, ScoredOutfit, WardrobeItem


def _item(id, category, *, formality="casual", warmth=1, season=None) -> WardrobeItem:
    return WardrobeItem(
        id=id,
        category=category,
        colors=["#000000"],
        formality=formality,
        warmth=warmth,
        season=season or [],
    )


def _scored_outfit(item_ids: list[str], rank_score: float) -> ScoredOutfit:
    return ScoredOutfit(
        items=item_ids,
        rationale=[Rationale(text="r", cites=["L1-x"])],
        scores=[
            DimensionScore(dimension="color_harmony", value=0.5, reason="color reason"),
            DimensionScore(dimension="formality_coherence", value=0.5, reason="formality reason"),
            DimensionScore(dimension="weather_fitness", value=0.5, reason="weather reason"),
            DimensionScore(dimension="silhouette_balance", value=0.5, reason="silhouette reason"),
        ],
        rank_score=rank_score,
    )


class TestEnumerateOutfitsSkeletonCounts:
    def test_3x2x2_closet_produces_12_top_bottom_footwear_combos(self):
        candidates = {
            "top": [_item(f"top{i}", "top") for i in range(3)],
            "bottom": [_item(f"bot{i}", "jeans") for i in range(2)],
            "footwear": [_item(f"shoe{i}", "sneakers") for i in range(2)],
        }
        combos = engine.enumerate_outfits(candidates, require_outerwear=False)
        assert len(combos) == 12
        assert all(len(c) == 3 for c in combos)

    def test_full_body_x_footwear_combos_are_included(self):
        candidates = {
            "full_body": [_item(f"dress{i}", "dress") for i in range(2)],
            "footwear": [_item(f"shoe{i}", "heels") for i in range(2)],
        }
        combos = engine.enumerate_outfits(candidates, require_outerwear=False)
        assert len(combos) == 4
        assert all(len(c) == 2 for c in combos)

    def test_top_bottom_footwear_and_full_body_footwear_tracks_are_independent(self):
        candidates = {
            "top": [_item("top0", "top")],
            "bottom": [_item("bot0", "jeans")],
            "full_body": [_item("dress0", "dress")],
            "footwear": [_item("shoe0", "sneakers")],
        }
        combos = engine.enumerate_outfits(candidates, require_outerwear=False)
        # top+bottom+shoe (1) + dress+shoe (1) -- never top+bottom+dress together
        assert {frozenset(c) for c in combos} == {
            frozenset(["top0", "bot0", "shoe0"]),
            frozenset(["dress0", "shoe0"]),
        }

    def test_empty_candidates_yields_no_combos(self):
        assert engine.enumerate_outfits({}, require_outerwear=False) == []


class TestEnumerateOutfitsCoherenceGuardExclusion:
    def test_an_item_mis_filed_under_the_wrong_slot_is_excluded_by_the_real_guard(self):
        # A defensive scenario: "shoe1" is actually footwear by its own
        # .category, but ends up filed under the "top" candidate slot (a
        # caller bug). The reused guards operate on the item's REAL
        # category via wardrobe_by_id, not the dict key it was filed
        # under, so the resulting 2-footwear combo is correctly rejected.
        mislabeled_shoe = _item("shoe1", "sneakers")
        candidates = {
            "top": [mislabeled_shoe],
            "bottom": [_item("bot0", "jeans")],
            "footwear": [_item("shoe0", "sneakers")],
        }
        combos = engine.enumerate_outfits(candidates, require_outerwear=False)
        assert combos == []


class TestEnumerateOutfitsOuterwearCrossing:
    def test_require_outerwear_adds_versions_with_an_outerwear_item(self):
        candidates = {
            "top": [_item("top0", "top")],
            "bottom": [_item("bot0", "jeans")],
            "footwear": [_item("shoe0", "sneakers")],
            "outerwear": [_item("coat0", "coat")],
        }
        combos = engine.enumerate_outfits(candidates, require_outerwear=True)
        item_sets = {frozenset(c) for c in combos}
        assert frozenset(["top0", "bot0", "shoe0"]) in item_sets  # bare skeleton still present
        assert frozenset(["top0", "bot0", "shoe0", "coat0"]) in item_sets  # outerwear-added version

    def test_require_outerwear_with_no_outerwear_candidates_still_returns_base_skeletons(self):
        candidates = {
            "top": [_item("top0", "top")],
            "bottom": [_item("bot0", "jeans")],
            "footwear": [_item("shoe0", "sneakers")],
        }
        combos = engine.enumerate_outfits(candidates, require_outerwear=True)
        assert combos == [["top0", "bot0", "shoe0"]]

    def test_require_outerwear_false_never_crosses_outerwear_even_if_present(self):
        candidates = {
            "top": [_item("top0", "top")],
            "bottom": [_item("bot0", "jeans")],
            "footwear": [_item("shoe0", "sneakers")],
            "outerwear": [_item("coat0", "coat")],
        }
        combos = engine.enumerate_outfits(candidates, require_outerwear=False)
        assert combos == [["top0", "bot0", "shoe0"]]


class TestEnumerateOutfitsSafetyValve:
    def test_projected_combo_count_over_threshold_is_narrowed_to_top_6_per_slot(self):
        # 15x15x15 base x 15 outerwear = 50,625 projected, well over the
        # 20,000 valve -- confirm the result is bounded by what a
        # narrowed-to-6-per-slot enumeration would produce (6^3 base
        # skeletons + 6^3 x 6 outerwear-added versions = 1512), which the
        # un-narrowed 15x15x15x15 (~50k) would blow past.
        candidates = {
            "top": [_item(f"top{i}", "top") for i in range(15)],
            "bottom": [_item(f"bot{i}", "jeans") for i in range(15)],
            "footwear": [_item(f"shoe{i}", "sneakers") for i in range(15)],
            "outerwear": [_item(f"coat{i}", "coat") for i in range(15)],
        }
        combos = engine.enumerate_outfits(candidates, require_outerwear=True)
        assert len(combos) <= 6 * 6 * 6 * 7


class TestEngineWriteFallback:
    def test_invalid_output_falls_back_to_top_3_by_rank_score_with_no_fabricated_citation(self):
        shortlist = [
            _scored_outfit(["a"], 0.9),
            _scored_outfit(["b"], 0.7),
            _scored_outfit(["c"], 0.5),
            _scored_outfit(["d"], 0.3),
        ]
        ctx = Context(occasion="office", formality="business_casual", wardrobe=[])
        bad_output = engine.EngineWriteOutput(
            selections=[
                engine.EngineSelection(index=0, rationale=[GenRationale(text="r", cites=["L1-x"])]),
                engine.EngineSelection(index=0, rationale=[GenRationale(text="r", cites=["L1-x"])]),  # duplicate
                engine.EngineSelection(index=1, rationale=[GenRationale(text="r", cites=["L1-x"])]),
            ]
        )
        fake_llm = MagicMock()
        fake_llm.with_structured_output.return_value.invoke.return_value = bad_output
        retrieval = MagicMock()
        retrieval.all.return_value = []

        with (
            patch.object(engine, "get_chat_model", return_value=fake_llm),
            patch.object(engine, "_format_rules", return_value=""),
        ):
            result = engine.engine_write(shortlist, ctx, retrieval)

        assert [o.items for o in result] == [["a"], ["b"], ["c"]]
        assert all(r.cites == [] for o in result for r in o.rationale)

    def test_out_of_range_index_falls_back(self):
        shortlist = [_scored_outfit(["a"], 0.9), _scored_outfit(["b"], 0.7), _scored_outfit(["c"], 0.5)]
        ctx = Context(occasion="office", formality="business_casual", wardrobe=[])
        bad_output = engine.EngineWriteOutput(
            selections=[
                engine.EngineSelection(index=0, rationale=[]),
                engine.EngineSelection(index=1, rationale=[]),
                engine.EngineSelection(index=99, rationale=[]),  # out of range
            ]
        )
        fake_llm = MagicMock()
        fake_llm.with_structured_output.return_value.invoke.return_value = bad_output
        retrieval = MagicMock()
        retrieval.all.return_value = []

        with (
            patch.object(engine, "get_chat_model", return_value=fake_llm),
            patch.object(engine, "_format_rules", return_value=""),
        ):
            result = engine.engine_write(shortlist, ctx, retrieval)

        assert [o.items for o in result] == [["a"], ["b"], ["c"]]

    def test_llm_call_exception_falls_back(self):
        shortlist = [_scored_outfit(["a"], 0.9), _scored_outfit(["b"], 0.7), _scored_outfit(["c"], 0.5)]
        ctx = Context(occasion="office", formality="business_casual", wardrobe=[])
        fake_llm = MagicMock()
        fake_llm.with_structured_output.return_value.invoke.side_effect = RuntimeError("gateway down")
        retrieval = MagicMock()
        retrieval.all.return_value = []

        with (
            patch.object(engine, "get_chat_model", return_value=fake_llm),
            patch.object(engine, "_format_rules", return_value=""),
        ):
            result = engine.engine_write(shortlist, ctx, retrieval)

        assert [o.items for o in result] == [["a"], ["b"], ["c"]]

    def test_valid_output_maps_selections_and_filters_unresolvable_citations(self):
        shortlist = [_scored_outfit(["a"], 0.9), _scored_outfit(["b"], 0.7), _scored_outfit(["c"], 0.5)]
        ctx = Context(occasion="office", formality="business_casual", wardrobe=[])
        good_output = engine.EngineWriteOutput(
            selections=[
                engine.EngineSelection(
                    index=2,
                    rationale=[GenRationale(text="great fit", cites=["L1-real", "L1-hallucinated"])],
                ),
                engine.EngineSelection(index=0, rationale=[GenRationale(text="classic", cites=["L1-real"])]),
                engine.EngineSelection(index=1, rationale=[GenRationale(text="fine", cites=[])]),
            ]
        )
        fake_llm = MagicMock()
        fake_llm.with_structured_output.return_value.invoke.return_value = good_output

        retrieved_doc = MagicMock()
        retrieved_doc.metadata = {"rule_id": "L1-real"}
        retrieval = MagicMock()
        retrieval.all.return_value = [retrieved_doc]

        with (
            patch.object(engine, "get_chat_model", return_value=fake_llm),
            patch.object(engine, "_format_rules", return_value=""),
        ):
            result = engine.engine_write(shortlist, ctx, retrieval)

        # returned in deterministic rank_score order, NOT the LLM's pick order
        assert [o.items for o in result] == [["a"], ["b"], ["c"]]
        assert result[0].rank_score == 0.9  # highest deterministic score ranked first
        # the hallucinated citation on the "c" pick was dropped wherever it lands
        c_outfit = next(o for o in result if o.items == ["c"])
        assert c_outfit.rationale[0].cites == ["L1-real"]
