"""Color-harmony dimension scorer.

Reuses `colors.contrast_ratio`/`colors.nearest_names` (WCAG math lives in one
place, colors.py — not reimplemented here). Higher contrast among the core
items' colors reads as a bolder, more deliberate pairing; scored on the
average pairwise contrast ratio, normalized into 0-1.
"""

from __future__ import annotations

from itertools import combinations

from ..categories import is_core
from ..colors import contrast_ratio
from ..schema import Context, DimensionScore, WardrobeItem

# WCAG contrast ratios range 1.0 (identical) to 21.0 (black/white); normalize
# against a ratio that already reads as "high contrast" (colors.contrast_hint's
# own 4.5 threshold) rather than the unreachable theoretical max.
_NORMALIZATION_CEILING = 10.0


def score(items: list[WardrobeItem], ctx: Context) -> DimensionScore:
    core = [it for it in items if is_core(it.category)]
    palette = [c for it in core for c in it.colors]

    if len(palette) < 2:
        return DimensionScore(
            dimension="color_harmony", value=0.5,
            reason="not enough colors to compare — neutral score",
        )

    pairs = list(combinations(palette, 2))
    ratios = [contrast_ratio(a, b) for a, b in pairs]
    avg_ratio = sum(ratios) / len(ratios)
    value = min(1.0, avg_ratio / _NORMALIZATION_CEILING)

    return DimensionScore(
        dimension="color_harmony",
        value=value,
        reason=f"average pairwise contrast {avg_ratio:.1f}:1 across {len(palette)} colors",
    )
