"""Formality-coherence dimension scorer.

Reuses `schema.FORMALITY_ORDER` (the single formality scale — constitution
Principle VI, no parallel numeric scale). An outfit whose core items all sit
at the same formality notch reads as coherent; the more the notches spread,
the lower the score.
"""

from __future__ import annotations

from ..categories import is_core
from ..schema import FORMALITY_ORDER, Context, DimensionScore, WardrobeItem

# FORMALITY_ORDER spans 0-5, so the widest possible spread among core items is 5.
_MAX_SPREAD = max(FORMALITY_ORDER.values()) - min(FORMALITY_ORDER.values())


def score(items: list[WardrobeItem], ctx: Context) -> DimensionScore:
    core = [it for it in items if is_core(it.category)]

    if not core:
        return DimensionScore(
            dimension="formality_coherence",
            value=0.5,
            reason="no core items to compare — neutral score",
        )

    notches = [FORMALITY_ORDER[it.formality] for it in core]
    spread = max(notches) - min(notches)
    value = 1.0 - (spread / _MAX_SPREAD)

    return DimensionScore(
        dimension="formality_coherence",
        value=value,
        reason=f"formality spread of {spread} notch(es) across {len(core)} core items",
    )
