"""The swappable score-combination strategy.

A `Strategy` is a plain function, not a class/ABC — Python functions are
already first-class, and there's exactly one seam here: comparing
strategies is ongoing evaluation work, not a decision to finalize.
`fit_first_lexicographic` ships as the production default — weather/
formality fit decides ranking before color/silhouette cosmetic tiebreaks;
`EQUAL_WEIGHTED_AVERAGE` let a beautiful but weather-inappropriate outfit
outrank a merely-adequate, correctly-weighted one. `rank_outfits` is the
one call site `score_and_rank` uses, so swapping strategies during
evaluation is a one-argument change, never a code change inside the graph
node.
"""

from __future__ import annotations

from collections.abc import Callable

from ..schema import DimensionScore, ScoredOutfit

Strategy = Callable[[list[DimensionScore]], float]


def equal_weighted_average(scores: list[DimensionScore]) -> float:
    return sum(s.value for s in scores) / len(scores)


def fit_first_lexicographic(scores: list[DimensionScore]) -> float:
    """Weather + formality decide the outfit's basic fitness for the
    request; color + silhouette only break ties within that. Encoded as one
    float (the `Strategy` signature) by weighting the primary pair heavily
    enough that it dominates ordering whenever it differs at all, with the
    secondary pair only nudging within a tie."""
    by_dim = {s.dimension: s.value for s in scores}
    primary = (by_dim["weather_fitness"] + by_dim["formality_coherence"]) / 2
    secondary = (by_dim["color_harmony"] + by_dim["silhouette_balance"]) / 2
    return primary * 1000 + secondary


EQUAL_WEIGHTED_AVERAGE: Strategy = equal_weighted_average


def rank_outfits(outfits: list[ScoredOutfit], strategy: Strategy = fit_first_lexicographic) -> list[ScoredOutfit]:
    """Compute `rank_score` for each outfit via `strategy` and return them
    ordered descending by that score. Deterministic: identical input yields
    an identical, identically-ordered output."""
    ranked = [o.model_copy(update={"rank_score": strategy(o.scores)}) for o in outfits]
    ranked.sort(key=lambda o: o.rank_score, reverse=True)
    return ranked
