"""Unit tests for pipeline/graph.py.

Covers `wardrobe_retrieval`'s hard-constraint pruning + the k=8-per-slot
cap, refinement-intent parsing and the delta-shifted pruning bounds it
feeds, the "alternatives" exclusion, and the unsatisfiable-refinement
fallback.

`generate_outfits`/`gather_context`/`verify_grounding` now take an
injected `repo: ClosetRepository` (specs/007-ai-port/research.md §1) — a
`MagicMock()` stand-in is enough here since none of these test cases set
`ctx.user_id`, so `memory.profile_note` short-circuits before ever
touching it.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from whattowear.pipeline import graph
from whattowear.pipeline.generator import GenOutfit, GenOutput, GenRationale
from whattowear.retrieval.base import RetrievalResult
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
            occasion="gala",
            formality="black_tie",
            wardrobe=[_item("gown", "gown", formality="black_tie"), _item("tee", "top", formality="casual")],
        )
        result = graph.wardrobe_retrieval({"ctx": ctx})
        kept_ids = {it.id for items in result["candidates"].values() for it in items}
        assert "gown" in kept_ids
        assert "tee" not in kept_ids

    def test_excludes_items_over_the_per_band_warmth_ceiling(self):
        ctx = Context(
            occasion="beach",
            formality="casual",
            temp_band="hot",
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
            occasion="office",
            formality="business_casual",
            season="summer",
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
            occasion="dinner",
            formality="casual",
            wardrobe=[_item("t", "top"), _item("j", "jeans"), _item("s", "sneakers")],
        )
        result = graph.wardrobe_retrieval({"ctx": ctx})
        assert set(result["candidates"].keys()) == {"top", "bottom", "footwear"}

    def test_best_fitting_item_survives_the_cap_even_when_placed_after_it(self):
        # The cap must not take a naive positional prefix (items[:8]) with
        # no sort — an exact formality match placed 9th in closet order
        # must not be silently dropped even though it's the best fit. All
        # 10 items pass the hard-constraint floor (>= one notch below
        # "formal") so none are excluded before the cap; only the item at
        # index 8 (the 9th item) is an *exact* formality match.
        near_matches_before = [_item(f"near{i}", "top", formality="black_tie") for i in range(8)]
        exact_match = _item("exact", "top", formality="formal")
        near_match_after = _item("near8", "top", formality="black_tie")
        wardrobe = near_matches_before + [exact_match] + [near_match_after]

        ctx = Context(occasion="gala", formality="formal", wardrobe=wardrobe)
        result = graph.wardrobe_retrieval({"ctx": ctx})

        kept_ids = {it.id for it in result["candidates"]["top"]}
        assert "exact" in kept_ids
        assert len(result["candidates"]["top"]) == 8


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
                "occasion": "less formal",
                "thread_id": "t1",
                "original_context": ctx,
                "refinement_deltas": ["warmer"],
            }
        )
        assert result["refinement_deltas"] == ["warmer", "less_formal"]


class TestCategoryWarmthCeiling:
    def test_computes_max_warmth_per_group_from_the_wardrobe(self):
        wardrobe = [
            _item("a", "sneakers", warmth=3),
            _item("b", "boots", warmth=1),
            _item("c", "coat", warmth=5),
        ]
        ceilings = graph._category_warmth_ceiling(wardrobe)
        assert ceilings == {"footwear": 3, "outerwear": 5}

    def test_empty_wardrobe_yields_an_empty_ceiling_map(self):
        assert graph._category_warmth_ceiling([]) == {}


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

    def test_warmer_floor_scales_to_a_low_ceiling_category_instead_of_exempting_it(self):
        # footwear/accessories rarely carry high warmth values in practice
        # (a fixture-data reality) -- the floor scales to what THIS
        # category can actually offer (its own max warmth in the closet),
        # not a flat absolute number and not a full pass-through.
        ctx = Context(occasion="office", formality="business_casual")
        ceilings = {"footwear": 3}
        cold_shoe = _item("a", "sneakers", formality="business_casual", warmth=0)
        warm_enough_shoe = _item("b", "sneakers", formality="business_casual", warmth=1)
        assert graph._item_fits_hard_constraints(cold_shoe, ctx, ["warmer"], ceilings) is False
        assert graph._item_fits_hard_constraints(warm_enough_shoe, ctx, ["warmer"], ceilings) is True

    def test_warmer_floor_never_exceeds_the_category_s_own_ceiling(self):
        # repeated "warmer" requests keep climbing elsewhere but never
        # demand more than a low-ceiling category can actually supply --
        # its own warmest item always still passes.
        ctx = Context(occasion="office", formality="business_casual")
        ceilings = {"footwear": 3}
        warmest_available_shoe = _item("a", "sneakers", formality="business_casual", warmth=3)
        assert graph._item_fits_hard_constraints(warmest_available_shoe, ctx, ["warmer"] * 3, ceilings) is True

    def test_zero_ceiling_category_is_never_gated(self):
        # a category with genuinely no warmth range (e.g. accessories in a
        # closet with none rated above 0) computes a floor of 0 and never
        # excludes anything -- the correct degenerate case of the same
        # formula, not a hardcoded exemption list.
        ctx = Context(occasion="office", formality="business_casual")
        ceilings = {"accessory": 0}
        cold_belt = _item("a", "belt", formality="business_casual", warmth=0)
        assert graph._item_fits_hard_constraints(cold_belt, ctx, ["warmer"], ceilings) is True

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
    generate_outfits at all -- every outfit built here covers all three so
    the alternatives-exclusion logic is what's actually exercised, not the
    completeness filter."""

    def _complete_outfit_items(self, ids: tuple[str, str, str]) -> tuple:
        top_id, bottom_id, shoe_id = ids
        return (
            _item(top_id, "top"),
            _item(bottom_id, "jeans"),
            _item(shoe_id, "sneakers"),
        )

    def test_alternatives_delta_excludes_previously_shown_item_sets(self):
        shown_top, shown_bottom, shown_shoe = self._complete_outfit_items(("st", "sb", "ss"))
        new_top, new_bottom, new_shoe = self._complete_outfit_items(("nt", "nb", "ns"))
        repeated = GenOutfit(items=["st", "sb", "ss"], rationale=[GenRationale(text="r", cites=["L1-x"])])
        fresh = GenOutfit(items=["nt", "nb", "ns"], rationale=[GenRationale(text="r", cites=["L1-x"])])

        wardrobe = [shown_top, shown_bottom, shown_shoe, new_top, new_bottom, new_shoe]
        ctx = Context(occasion="office", formality="business_casual", wardrobe=wardrobe)
        state = {
            "ctx": ctx,
            "candidates": {
                "top": [shown_top, new_top],
                "bottom": [shown_bottom, new_bottom],
                "footwear": [shown_shoe, new_shoe],
            },
            "retrieval": MagicMock(),
            "refinement_deltas": ["alternatives"],
            "last_result": MagicMock(outfits=[_scored_outfit_multi(["st", "sb", "ss"])]),
        }

        with patch.object(graph, "generate", return_value=GenOutput(outfits=[repeated, fresh])):
            result = graph.generate_outfits(state, MagicMock())

        kept_item_sets = [frozenset(o.items) for o in result["generated"].outfits]
        assert frozenset(["st", "sb", "ss"]) not in kept_item_sets
        assert frozenset(["nt", "nb", "ns"]) in kept_item_sets

    def test_no_alternatives_delta_keeps_all_generated_outfits(self):
        top, bottom, shoe = self._complete_outfit_items(("a", "b", "c"))
        outfit = GenOutfit(items=["a", "b", "c"], rationale=[GenRationale(text="r", cites=["L1-x"])])

        ctx = Context(occasion="office", formality="business_casual", wardrobe=[top, bottom, shoe])
        state = {
            "ctx": ctx,
            "candidates": {"top": [top], "bottom": [bottom], "footwear": [shoe]},
            "retrieval": MagicMock(),
            "refinement_deltas": [],
            "last_result": None,
        }

        with patch.object(graph, "generate", return_value=GenOutput(outfits=[outfit])):
            result = graph.generate_outfits(state, MagicMock())

        assert len(result["generated"].outfits) == 1


class TestExplainUnsatisfiableRefinementFallback:
    def test_empty_scored_outfits_during_refinement_falls_back_to_last_result(self):
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

    def test_empty_scored_outfits_without_refinement_gets_the_plain_empty_note(self):
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


class TestIsValidCombination:
    """The deterministic coherence guard. Split into the incoherent combos
    it MUST reject (the reported funny outfits) and the legitimately
    plural looks it MUST still allow (guarding against over-strictness
    re-creating the 'returns nothing' failure)."""

    def _wb(self, *items):
        return {it.id: it for it in items}

    def _valid(self, *items):
        return graph._is_valid_combination([it.id for it in items], self._wb(*items))

    # --- must reject ---
    def test_a_normal_outfit_is_valid(self):
        assert self._valid(_item("t", "top"), _item("j", "jeans"), _item("s", "sneakers")) is True

    def test_two_footwear_is_rejected(self):
        # the reported shoes + sneakers bug
        assert (
            self._valid(_item("t", "top"), _item("j", "jeans"), _item("sh", "shoes"), _item("sn", "sneakers")) is False
        )

    def test_full_body_with_a_separate_bottom_is_rejected(self):
        # the reported dress + pants bug
        assert self._valid(_item("d", "dress"), _item("p", "trousers"), _item("h", "heels")) is False

    def test_two_full_body_pieces_are_rejected(self):
        assert self._valid(_item("d1", "dress"), _item("d2", "gown"), _item("h", "heels")) is False

    def test_two_separate_bottoms_are_rejected(self):
        assert (
            self._valid(_item("t", "top"), _item("j", "jeans"), _item("c", "chinos"), _item("s", "sneakers")) is False
        )

    # --- must still allow (leniency: real, common layered looks) ---
    def test_layered_tops_are_allowed(self):
        # t-shirt + cardigan are both the 'top' group -- layering, not a conflict
        assert (
            self._valid(_item("tee", "t-shirt"), _item("card", "cardigan"), _item("j", "jeans"), _item("s", "sneakers"))
            is True
        )

    def test_a_cardigan_over_a_dress_is_allowed(self):
        # cardigan is the 'top' group; a top layered over a full_body piece is fine
        assert self._valid(_item("d", "dress"), _item("card", "cardigan"), _item("h", "heels")) is True

    def test_outerwear_over_a_dress_is_allowed(self):
        assert self._valid(_item("d", "dress"), _item("b", "blazer"), _item("h", "heels")) is True

    def test_layered_outerwear_is_allowed(self):
        assert (
            self._valid(
                _item("t", "top"),
                _item("j", "jeans"),
                _item("bl", "blazer"),
                _item("co", "coat"),
                _item("s", "sneakers"),
            )
            is True
        )


class TestGenerateOutfitsValidityFilter:
    def test_an_incoherent_generated_outfit_is_dropped(self):
        # LLM returns one clean outfit and one with two pairs of footwear
        clean = GenOutfit(items=["t", "j", "s1"], rationale=[GenRationale(text="r", cites=["L1-x"])])
        two_shoes = GenOutfit(items=["t", "j", "s1", "s2"], rationale=[GenRationale(text="r", cites=["L1-x"])])

        wardrobe = [_item("t", "top"), _item("j", "jeans"), _item("s1", "sneakers"), _item("s2", "shoes")]
        ctx = Context(occasion="office", formality="business_casual", wardrobe=wardrobe)
        state = {
            "ctx": ctx,
            "candidates": {"top": [wardrobe[0]], "bottom": [wardrobe[1]], "footwear": [wardrobe[2], wardrobe[3]]},
            "retrieval": MagicMock(),
            "refinement_deltas": [],
            "last_result": None,
        }

        with patch.object(graph, "generate", return_value=GenOutput(outfits=[clean, two_shoes])):
            result = graph.generate_outfits(state, MagicMock())

        kept = [frozenset(o.items) for o in result["generated"].outfits]
        assert frozenset(["t", "j", "s1"]) in kept
        assert frozenset(["t", "j", "s1", "s2"]) not in kept


class TestVerifyGroundingUsesInjectedRepo:
    def test_catalog_ids_come_from_the_repo_not_a_db_session(self):
        item = _item("a", "top")
        ctx = Context(occasion="office", formality="business_casual", wardrobe=[item])
        outfit = _scored_outfit("a")
        state = {"ctx": ctx, "scored_outfits": [outfit]}
        repo = MagicMock()
        repo.list_catalog_items.return_value = []

        result = graph.verify_grounding(state, repo)

        repo.list_catalog_items.assert_called_once_with()
        assert len(result["scored_outfits"]) == 1

    def test_outfit_grounded_only_via_catalog_is_kept(self):
        ctx = Context(occasion="office", formality="business_casual", wardrobe=[])
        outfit = _scored_outfit("catalog-item")
        state = {"ctx": ctx, "scored_outfits": [outfit]}
        repo = MagicMock()
        repo.list_catalog_items.return_value = [_item("catalog-item", "top")]

        result = graph.verify_grounding(state, repo)

        assert len(result["scored_outfits"]) == 1

    def test_ungrounded_outfit_is_dropped(self):
        ctx = Context(occasion="office", formality="business_casual", wardrobe=[])
        outfit = _scored_outfit("ghost-item")
        state = {"ctx": ctx, "scored_outfits": [outfit]}
        repo = MagicMock()
        repo.list_catalog_items.return_value = []

        result = graph.verify_grounding(state, repo)

        assert result["scored_outfits"] == []


class TestBuildGraphWiring:
    def test_build_graph_compiles_without_error(self):
        repo = MagicMock()
        graph_obj = graph.build_graph(repo)
        assert graph_obj is not None

    def test_route_by_approach_defaults_to_grounded(self):
        assert graph._route_by_approach({}) == "grounded"
        assert graph._route_by_approach({"approach": "something-else"}) == "grounded"

    def test_route_by_approach_engine(self):
        assert graph._route_by_approach({"approach": "engine"}) == "engine"
