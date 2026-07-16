"""Weather-fitness dimension scorer.

Reuses `categories.group_of` for the outerwear check and
`eval.properties.weather_appropriate` for the hard requires-outer/max-warmth
check — the same predicate the golden-set eval already encodes, imported
here rather than forked into a second implementation. Blends that hard check
with a continuous "how close is average core warmth to the temp band's
target" signal, so two outfits that both pass the hard check can still be
ranked against each other.
"""

from __future__ import annotations

from ..categories import is_core
from ..eval.properties import weather_appropriate
from ..schema import Context, DimensionScore, TempBand, WardrobeItem

# 0 (airy) .. 5 (heaviest) — mirrors WardrobeItem.warmth's own scale.
_TARGET_WARMTH: dict[TempBand, int] = {
    "freezing": 5, "cold": 4, "cool": 3, "mild": 2, "warm": 1, "hot": 0,
}


def _expected_for_band(temp_band: TempBand) -> dict:
    """Same shape as golden_set.yaml's `expected` — requires_outer for
    cold/freezing, max_warmth for warm/hot — the hard constraints
    weather_appropriate() checks."""
    if temp_band in ("freezing", "cold"):
        return {"requires_outer": True}
    if temp_band in ("warm", "hot"):
        return {"max_warmth": 2 if temp_band == "warm" else 1}
    return {}


def score(items: list[WardrobeItem], ctx: Context) -> DimensionScore:
    core = [it for it in items if is_core(it.category)]

    if not core:
        return DimensionScore(
            dimension="weather_fitness", value=0.5,
            reason="no core items to evaluate — neutral score",
        )
    if ctx.temp_band is None:
        return DimensionScore(
            dimension="weather_fitness", value=0.5,
            reason="no weather context available — neutral score",
        )

    target = _TARGET_WARMTH[ctx.temp_band]
    avg_warmth = sum(it.warmth for it in core) / len(core)
    closeness = 1.0 - min(1.0, abs(avg_warmth - target) / 5)

    ids = [it.id for it in core]
    wardrobe = {it.id: it for it in core}
    hard_ok = weather_appropriate(ids, wardrobe, _expected_for_band(ctx.temp_band))

    value = closeness if hard_ok else closeness * 0.3
    reason = f"average core warmth {avg_warmth:.1f} vs {ctx.temp_band} target {target}"
    if not hard_ok:
        reason += " — misses a hard weather requirement (e.g. outerwear/max warmth)"

    return DimensionScore(dimension="weather_fitness", value=round(value, 4), reason=reason)
