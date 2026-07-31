"""Deterministic outfit-scoring package.

Four independent dimension scorers (`color_harmony`, `formality_coherence`,
`weather_fitness`, `silhouette_balance`), each `score(items, ctx) ->
DimensionScore`, plus `combine.rank_outfits` to turn four scores into one
ordering. These are the literal functions both the graph's `score_and_rank`
node and the eval harness import (constitution Principle V) — never
reimplemented in either caller.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Protocol

from ..schema import Context, Rationale, ScoredOutfit, WardrobeItem
from . import color_harmony, formality_coherence, silhouette_balance, weather_fitness
from .combine import rank_outfits

DIMENSION_SCORERS = (color_harmony, formality_coherence, weather_fitness, silhouette_balance)


class _RationaleLike(Protocol):
    # @property, not a plain attribute: score_outfits only ever reads these
    # fields, and a plain Protocol attribute is checked invariantly by
    # mypy — pipeline/generator.py's GenRationale (cites: list[str]) would
    # then fail to structurally satisfy a Sequence[str]-typed attribute
    # even though list[str] is perfectly readable as one. A property makes
    # the member covariant, matching the actual (read-only) usage here.
    @property
    def text(self) -> str: ...
    @property
    def cites(self) -> Sequence[str]: ...


class _GenOutfitLike(Protocol):
    @property
    def items(self) -> Sequence[str]: ...
    @property
    def rationale(self) -> Sequence[_RationaleLike]: ...


def score_outfits(
    gen_outfits: Iterable[_GenOutfitLike], wardrobe_by_id: dict[str, WardrobeItem], ctx: Context
) -> list[ScoredOutfit]:
    """Score every candidate outfit on all four dimensions and rank them.
    The one place `DIMENSION_SCORERS` + `combine.rank_outfits` are called
    from — reused unchanged by both `pipeline/graph.py`'s `score_and_rank`
    node and `eval/harness.py` (constitution Principle V)."""
    candidates = [
        ScoredOutfit(
            items=list(o.items),
            rationale=[Rationale(text=r.text, cites=list(r.cites)) for r in o.rationale],
            scores=[
                s.score([wardrobe_by_id[i] for i in o.items if i in wardrobe_by_id], ctx) for s in DIMENSION_SCORERS
            ],
            rank_score=0.0,
        )
        for o in gen_outfits
    ]
    return rank_outfits(candidates)
