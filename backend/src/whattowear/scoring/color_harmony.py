"""Color-harmony dimension scorer.

Real color-theory classification of core items' colors (neutral-anchored,
analogous, complementary, triadic) — not raw WCAG contrast. Contrast only
measures lightness distance, never hue relationship, so it rewarded bold
clashes (e.g. tomato red + emerald green) over elegant tonal pairings (e.g.
navy + charcoal). See `docs/eval-baselines/pre-009/NOTES.md` and
`specs/009-scoring-fixes/research.md` Decision 1 for the verified bug and
the exact rule table this implements. The value-contrast bonus step below
uses HSL lightness (a simpler, different axis than WCAG contrast) — the old
`contrast_ratio` helper in `colors.py` is untouched and still public, just
no longer consumed here; the WCAG math itself wasn't wrong, using it as the
*entire* harmony signal was.
"""

from __future__ import annotations

from itertools import combinations

from ..categories import is_core
from ..colors import FASHION_COLOR_PALETTE, hex_to_hsl, normalize_hex
from ..schema import Context, DimensionScore, WardrobeItem

# Colors this project already treats as neutral by name (the "# neutrals"
# section of FASHION_COLOR_PALETTE) always count as neutral regardless of
# their computed HSL — several (oatmeal, camel, cream) don't clear the
# numeric thresholds below on their own; the named list is load-bearing, not
# a redundant belt-and-suspenders check (verified directly, see research.md).
_NAMED_NEUTRAL_NAMES = frozenset(
    {
        "black",
        "white",
        "grey",
        "charcoal",
        "navy",
        "beige",
        "cream",
        "ivory",
        "tan",
        "khaki",
        "camel",
        "oatmeal",
        "taupe",
        "brown",
    }
)
_NAMED_NEUTRAL_HEXES = frozenset(FASHION_COLOR_PALETTE[name] for name in _NAMED_NEUTRAL_NAMES)

_NEUTRAL_SATURATION_MAX = 0.18
_NEUTRAL_LIGHTNESS_MIN = 0.10
_NEUTRAL_LIGHTNESS_MAX = 0.92

_ANALOGOUS_HUE_MAX = 40.0
_COMPLEMENTARY_HUE_MIN = 150.0
_DOMINANCE_SATURATION_DELTA = 0.25
_DOMINANCE_LIGHTNESS_DELTA = 0.20
_TRIADIC_HUE_RANGE = (90.0, 150.0)

_LIGHTNESS_BONUS_RANGE = (0.25, 0.75)
_LIGHTNESS_BONUS = 0.1

# 40-150 deg (equivalently 210-320 deg uncircularized) is neither analogous
# nor a genuine ~180 deg complementary pairing — no organizing hue
# relationship at all. Originally proposed at 0.4; revised to 0.3 during
# implementation after the spec's own required test case (tomato red +
# emerald green, <0.45) failed arithmetic at 0.4 once run against the real
# palette hexes (0.4 base + 0.1 lightness-contrast bonus = 0.5). See
# research.md Decision 1 addendum for the full verification.
_SCORE_NEUTRAL_ANCHOR = 0.9
_SCORE_ANALOGOUS = 0.85
_SCORE_COMPLEMENTARY_ACCENTED = 0.75
_SCORE_COMPLEMENTARY_CLASH = 0.35
_SCORE_MIDBAND = 0.3
_SCORE_TRIADIC = 0.7
_SCORE_THREE_CHROMATIC_CLASH = 0.35
_SCORE_FOUR_PLUS_CHROMATIC = 0.25


def _is_neutral(hex_color: str) -> bool:
    if normalize_hex(hex_color) in _NAMED_NEUTRAL_HEXES:
        return True
    _, saturation, lightness = hex_to_hsl(hex_color)
    return (
        saturation < _NEUTRAL_SATURATION_MAX or lightness < _NEUTRAL_LIGHTNESS_MIN or lightness > _NEUTRAL_LIGHTNESS_MAX
    )


def _hue_delta(h1: float, h2: float) -> float:
    """Circular hue distance in degrees, always in [0, 180]."""
    d = abs(h1 - h2) % 360
    return min(d, 360 - d)


def _two_chromatic_score(chromatics: list[str]) -> tuple[float, str]:
    (h1, s1, l1), (h2, s2, l2) = (hex_to_hsl(c) for c in chromatics)
    delta = _hue_delta(h1, h2)

    if delta <= _ANALOGOUS_HUE_MAX:
        return _SCORE_ANALOGOUS, "an analogous pairing (L1-color-analogous, hues close together)"

    if delta >= _COMPLEMENTARY_HUE_MIN:
        dominant = abs(s1 - s2) >= _DOMINANCE_SATURATION_DELTA or abs(l1 - l2) >= _DOMINANCE_LIGHTNESS_DELTA
        if dominant:
            return (
                _SCORE_COMPLEMENTARY_ACCENTED,
                "a complementary pairing (L1-color-complementary) with one color clearly a minor accent",
            )
        return (
            _SCORE_COMPLEMENTARY_CLASH,
            "an equal-weight complementary pairing (L1-color-complementary) — a classic Chevreul clash",
        )

    return (
        _SCORE_MIDBAND,
        "a hue pairing that is neither analogous nor genuinely complementary — no organizing relationship",
    )


def _three_chromatic_score(chromatics: list[str]) -> tuple[float, str]:
    hues = [hex_to_hsl(c)[0] for c in chromatics]
    deltas = [_hue_delta(a, b) for a, b in combinations(hues, 2)]
    triadic_lo, triadic_hi = _TRIADIC_HUE_RANGE
    if all(triadic_lo <= d <= triadic_hi for d in deltas):
        return _SCORE_TRIADIC, "a roughly triadic three-color combination"
    return _SCORE_THREE_CHROMATIC_CLASH, "three chromatic colors with no triadic or analogous structure"


def score(items: list[WardrobeItem], ctx: Context) -> DimensionScore:
    core = [it for it in items if is_core(it.category)]
    palette = [c for it in core for c in it.colors]

    if len(palette) < 2:
        return DimensionScore(
            dimension="color_harmony",
            value=0.5,
            reason="not enough colors to compare — neutral score",
        )

    chromatics = sorted({normalize_hex(c) for c in palette if not _is_neutral(c)})

    if len(chromatics) <= 1:
        base, rule = _SCORE_NEUTRAL_ANCHOR, "neutral-anchored (L1-color-neutral-anchor)"
    elif len(chromatics) == 2:
        base, rule = _two_chromatic_score(chromatics)
    elif len(chromatics) == 3:
        base, rule = _three_chromatic_score(chromatics)
    else:
        base, rule = _SCORE_FOUR_PLUS_CHROMATIC, "four or more clashing saturated hues (L1-color-three-max)"

    lightnesses = [hex_to_hsl(c)[2] for c in palette]
    lightness_gap = max(lightnesses) - min(lightnesses)
    lo, hi = _LIGHTNESS_BONUS_RANGE
    bonus = _LIGHTNESS_BONUS if lo <= lightness_gap <= hi else 0.0

    value = max(0.0, min(1.0, base + bonus))
    bonus_note = " with some (not extreme) value contrast" if bonus else ""

    return DimensionScore(
        dimension="color_harmony",
        value=value,
        reason=f"{rule}{bonus_note}",
    )
