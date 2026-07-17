# Phase 0 Research: Scoring & Retrieval Correctness Fixes

No `NEEDS CLARIFICATION` markers were left in the Technical Context — this is
a bug-fix feature against existing, already-understood code, not new
technology. This document records the concrete decisions carried in from the
verified debug analysis (`docs/claude-code-implementation-spec.md` §WP0), so
`/speckit.tasks` has one unambiguous source instead of re-deriving thresholds.

## Decision 1: Color-harmony algorithm

**Decision**: Replace mean-pairwise-WCAG-contrast with an HSL-based
neutral/analogous/complementary/triadic classifier over core-item colors,
producing a base score by chromatic-color count plus a small value-contrast
bonus. Exact rule table:

| Chromatics | Condition | Score | Rule id |
|---|---|---|---|
| 0-1 | — | 0.9 | `L1-color-neutral-anchor` |
| 2 | hue Δ ≤ 40° | 0.85 | `L1-color-analogous` |
| 2 | hue Δ 150-210°, dominance asymmetry (\|s₁-s₂\|≥0.25 or \|l₁-l₂\|≥0.20) | 0.75 | `L1-color-complementary` (accented) |
| 2 | hue Δ 150-210°, no asymmetry | 0.35 | `L1-color-complementary` (clash) |
| 2 | hue Δ 40-150° or 210-320° | 0.3 (see addendum below) | — |
| 3 | all pairwise Δ ∈ [90°,150°] (triadic) | 0.7 | — |
| 3 | otherwise | 0.35 | — |
| ≥4 | — | 0.25 | `L1-color-three-max` |

Then: `+0.1` if the max pairwise lightness gap across the whole core palette
∈ [0.25, 0.75], clamp to [0,1].

Neutral partition: `s < 0.18 or l < 0.10 or l > 0.92`, OR the color is one of
the named-neutral entries in `FASHION_COLOR_PALETTE` (black…brown) regardless
of computed HSL — this second clause matters because some named "neutral"
hexes (e.g. a warm brown) can compute slightly outside the numeric neutral
band depending on exact RGB values; treating the palette's own neutral names
as authoritative avoids an inconsistency between what the app calls a color
and how the scorer classifies it.

**Rationale**: This is real color theory (analogous/complementary/triadic hue
relationships, Munsell-style value contrast), not an arbitrary heuristic —
matches how the spec's acceptance scenarios were derived (tomato-red +
emerald-green ≈ 150° apart, roughly equal saturation → clash; navy + charcoal
are both near-neutral → high; oatmeal/camel/cream are all low-saturation
neutrals → high).

**Addendum (found and fixed during `/speckit.implement`, not assumed
upfront)**: the source technical spec's own required test case — "tomato
red + emerald green → score < 0.45" — was computed against the *exact*
palette hexes (`#ff6347`, `#046307`) to verify the algorithm before writing
any code. Actual HSL: tomato red h≈9.1°, s=1.0, l=0.639; emerald green
h≈121.9°, s=0.922, l=0.202 — hue delta ≈112.8°, squarely in the "40-150°"
middle band, with a lightness gap of 0.437 (inside the bonus range). At the
source spec's originally-proposed base of 0.4, this scores 0.4+0.1=**0.5**,
failing the spec's own `<0.45` requirement — a real inconsistency between
the algorithm as literally specified and its own test fixture, not
discovered until the exact numbers were run. Resolved by revising this
band's base score to **0.3** (0.3+0.1=0.4, passing), re-verified against
all 6 of the spec's required color-harmony test cases before committing to
it (tomato/emerald 0.4<0.45 ✓; navy+charcoal+white 0.9≥0.8 ✓ via the
named-neutral override — neither navy (s=0.465,l=0.198) nor charcoal
(s=0.188,l=0.261) clears the *numeric* neutral thresholds on its own, only
the named-palette override does, confirming that override is load-bearing,
not redundant; oatmeal+camel+cream 0.9≥0.8 ✓, same reasoning — none of the
three clears the numeric thresholds either; burgundy+blush-pink (Δ≈2.7°)
0.95≥0.7 ✓; cobalt+constructed-equal-weight-partner (Δ=180°, matched s/l by
construction) 0.35<0.5 ✓; cobalt+palette-mustard (Δ≈168°, real dominance
asymmetry: Δl=0.337) 0.85≥0.7 ✓; 4 saturated hues at matched
lightness (avoids an unwanted bonus) 0.25<0.3 ✓.

**A second issue found during this same verification pass**: the spec's
original illustrative choice of "navy" as the chromatic partner in the
accent/equal-weight complementary test doesn't work at all — navy is one of
this project's own *named neutrals* (`FASHION_COLOR_PALETTE`'s "# neutrals"
section, a pre-existing, intentional classification — "navy is the new
black" is a standard styling claim, not a bug), so the named-neutral
override always absorbs it out of the chromatic set before any 2-hue
comparison runs, regardless of its partner (this is exactly what made the
navy+charcoal+white and oatmeal+camel+cream cases resolve via the override
rather than the numeric thresholds above). Substituted the palette's other
deep-blue entry, `cobalt` (`#0047ab`, classified chromatic), for both the
accent and equal-weight test cases in `test_color_harmony.py`.

This also confirms this
band is defensible on color-theory grounds independent of the arithmetic
fix: a hue pair that is neither analogous nor a genuine (~180°)
complementary pairing has no organizing relationship at all — arguably the
least harmonious two-hue case, more so than a true complementary clash
(which at least has the "bold, intentional" reading captured by the
accented-complementary band).

**Alternatives considered**:
- *Keep WCAG contrast but invert the direction* (rewarding low contrast) —
  rejected: contrast ratio has no relationship to hue harmony at all; a
  black+white outfit (contrast 21:1, "low harmony" under this naive inversion)
  is actually a classic, harmonious neutral pairing. Contrast measures
  lightness distance only, never hue relationship — the wrong axis entirely.
- *A learned/LLM-scored color harmony* — rejected outright by constitution
  Principle V (scoring functions must be deterministic code, reused unchanged
  in the eval harness).

## Decision 2: `hex_to_hsl` placement

**Decision**: New function in `colors.py`, next to `_hex_to_rgb` (reused
internally — HSL is derived from the same RGB triple), following the file's
existing private-helper-plus-public-function pattern. Only the new
public entrypoint `hex_to_hsl` needs a full docstring; internal math can stay
terse like the existing `_relative_luminance`.

**Rationale**: `colors.py` is already the single place hex-color math lives
(constitution Principle I — extend, don't duplicate elsewhere). `contrast_ratio`
stays untouched and public — it's simply not called by the rewritten scorer
anymore (corrected during implementation: the spec's own "value-contrast
bonus" step operates on HSL lightness, a different and simpler axis than
WCAG's gamma-corrected relative luminance; an earlier draft of this
decision assumed `contrast_ratio` would be reused for that step, which
doesn't match the algorithm as actually specified). The WCAG math wasn't
wrong, it was wrong to use as the *entire* harmony signal — `contrast_ratio`/
`contrast_hint` remain valid, tested, public utilities in `colors.py`, just
not consumed by `color_harmony.py` after this fix.

## Decision 3: Default ranking strategy swap

**Decision**: `combine.rank_outfits`'s default parameter changes from
`EQUAL_WEIGHTED_AVERAGE` to the module's existing `fit_first_lexicographic`
(already implemented, already has a passing test proving it differs
meaningfully from the average — `TestFitFirstLexicographic` in
`test_combine.py`). No new ranking logic is written.

**Rationale**: The function already exists and is tested; this is a
one-line default-parameter change plus updating the one test
(`test_default_strategy_is_equal_weighted_average`) that currently *locks in*
the old default — per this project's rule to replace tests that encode
now-wrong behavior rather than weaken them.

## Decision 4: Per-slot sort key before the retention cap

**Decision**: Sort key = `(abs(FORMALITY_ORDER[item.formality] -
FORMALITY_ORDER[ctx.formality]), warmth_distance)`, ascending (best first),
applied immediately before the existing `items[:_CANDIDATES_PER_SLOT]` slice
in `wardrobe_retrieval`. **No inference fallback is needed here**: confirmed
by direct inspection of `context_assembler.assemble_context()` (line 107,
`formality = formality or infer_formality(occasion)`) that `ctx.formality`
is *already* resolved before `Context` is ever constructed, on every path
that reaches `wardrobe_retrieval` (fresh request and the refinement
rebuild-from-`original_context` branch both go through
`assemble_context`). A second "or inferred" fallback inside
`wardrobe_retrieval` itself would be unreachable dead code — `/speckit.analyze`
caught this before implementation (an earlier draft of this decision assumed
`ctx.formality` could be unset here; it can't). `warmth_distance` =
`abs(item.warmth - ideal_warmth_for_band)` using a new mapping
`freezing→4, cold→3, cool→2, mild→2, warm→1, hot→0` (name it
`_IDEAL_WARMTH_BY_BAND`, placed near the existing `_MAX_WARMTH_BY_BAND` for
discoverability — the two are deliberately distinct: `_MAX_WARMTH_BY_BAND` is
a hard-constraint *ceiling* for warm/hot only, this is an *ideal target*
across all six bands, used only to rank, never to exclude), `0` if
`ctx.temp_band` is unset.

**Rationale**: The formality half mirrors the *existing* formality-notch-distance
idiom already used in `_item_fits_hard_constraints` (same file) and in
`scoring/formality_coherence.py` — no new formality math, just applying the
established idiom as a sort key instead of (only) a hard-constraint gate.
Sorting is a pure, stable, cheap operation over ≤ a few dozen items per slot
— no perf concern.

**Alternatives considered**: Reusing `scoring/weather_fitness.py`'s own
internal scoring function directly as the sort key — rejected as needless
coupling; that scorer operates on whole assembled outfits (post-generation),
not single candidate items pre-generation, and pulling it in here would blur
the pipeline stage boundary the graph's node design (`research.md` for
Feature 002) deliberately keeps separate.

## Decision 5: Palette additions

**Decision**: Add the 8 named colors verbatim as specified (`red #c0392b`,
`orange #e67e22`, `coral #ff7f50`, `pink #f8a1c4`, `teal #008080`,
`turquoise #40e0d0`, `forest green #228b22`, `mint #98d8aa`) to
`FASHION_COLOR_PALETTE`, in the section matching each color's family
(matching the file's existing grouped-by-comment convention).

**Rationale**: `nearest_name`/`nearest_names` already do Euclidean-RGB
nearest-neighbor lookup against this table — the "teal reads as sage"
symptom is purely a missing-entry problem, not a lookup-algorithm bug.

## Decision 6: Test locations

**Decision**: Confirmed by direct inspection — `backend/tests/unit/test_colors.py`
(existing, for the new `hex_to_hsl`/`nearest_names` tests),
`backend/tests/unit/scoring/test_color_harmony.py` (rewrite),
`backend/tests/unit/scoring/test_combine.py` (default-strategy assertion
update), `backend/tests/unit/pipeline/test_graph.py` (existing file, add the
sort-before-cap test for `wardrobe_retrieval`). No new test files needed.

## Decision 7: No `contracts/` API surface, but an internal signature contract is still documented

**Decision**: This feature adds no external API/endpoint. `contracts/` holds
one file, `scoring-interfaces.md`, documenting the *internal* function
signatures other modules depend on (the graph, the eval harness) — these are
the de facto contract even though nothing crosses the network boundary, and
keeping them written down guards against a future WP (e.g. WP2 Engine, which
directly imports `score_outfits`/`DIMENSION_SCORERS`) accidentally assuming a
different shape.
