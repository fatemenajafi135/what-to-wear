"""Unit tests for scoring/combine.py (Feature 002 Phase 2, FR-009a, SC-005)."""

from __future__ import annotations

from whattowear.schema import DimensionScore, Rationale, ScoredOutfit
from whattowear.scoring import combine


def _scores(color=0.5, formality=0.5, weather=0.5, silhouette=0.5) -> list[DimensionScore]:
    return [
        DimensionScore(dimension="color_harmony", value=color, reason="r"),
        DimensionScore(dimension="formality_coherence", value=formality, reason="r"),
        DimensionScore(dimension="weather_fitness", value=weather, reason="r"),
        DimensionScore(dimension="silhouette_balance", value=silhouette, reason="r"),
    ]


def _outfit(id, **score_kwargs) -> ScoredOutfit:
    return ScoredOutfit(
        items=[id], rationale=[Rationale(text="because", cites=["r1"])],
        scores=_scores(**score_kwargs), rank_score=0.0,
    )


class TestEqualWeightedAverage:
    def test_is_a_true_average(self):
        assert combine.equal_weighted_average(_scores(0.2, 0.4, 0.6, 0.8)) == 0.5


class TestFitFirstLexicographic:
    def test_genuinely_different_from_equal_weighted_average_on_a_constructed_example(self):
        # equal-weighted average scores these two identically (0.5 each): one
        # is all color/silhouette, the other all weather/formality. Fit-first
        # must break that tie by favoring the weather/formality-strong one.
        fit_poor_look_good = _scores(color=1.0, formality=0.0, weather=0.0, silhouette=1.0)
        fit_good_look_poor = _scores(color=0.0, formality=1.0, weather=1.0, silhouette=0.0)

        assert combine.equal_weighted_average(fit_poor_look_good) == combine.equal_weighted_average(
            fit_good_look_poor
        )
        assert combine.fit_first_lexicographic(fit_good_look_poor) > combine.fit_first_lexicographic(
            fit_poor_look_good
        )


class TestRankOutfits:
    def test_orders_descending_by_combined_score(self):
        low = _outfit("low", color=0.1, formality=0.1, weather=0.1, silhouette=0.1)
        high = _outfit("high", color=0.9, formality=0.9, weather=0.9, silhouette=0.9)
        ranked = combine.rank_outfits([low, high])
        assert [o.items[0] for o in ranked] == ["high", "low"]
        assert ranked[0].rank_score > ranked[1].rank_score

    def test_default_strategy_is_equal_weighted_average(self):
        outfit = _outfit("a", color=0.2, formality=0.4, weather=0.6, silhouette=0.8)
        [ranked] = combine.rank_outfits([outfit])
        assert ranked.rank_score == 0.5

    def test_rerunning_same_input_is_byte_identical(self):
        outfits = [
            _outfit("a", color=0.3, formality=0.5, weather=0.7, silhouette=0.9),
            _outfit("b", color=0.9, formality=0.1, weather=0.2, silhouette=0.4),
        ]
        first = combine.rank_outfits(outfits)
        second = combine.rank_outfits(outfits)
        assert [o.model_dump_json() for o in first] == [o.model_dump_json() for o in second]
