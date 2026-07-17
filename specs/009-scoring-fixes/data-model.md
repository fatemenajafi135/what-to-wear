# Phase 1 Data Model: Scoring & Retrieval Correctness Fixes

No new entities and no changes to existing ones. This feature only changes
*how* existing values are computed, sorted, or ranked — not the shape of any
Pydantic model. Documented here for completeness against the plan template.

## Existing entities touched (read-only, unchanged shape)

- **`WardrobeItem`** (`schema.py`) — `colors: list[str]` (hex) is read by the
  rewritten color-harmony scorer; `formality`, `warmth` are read by the new
  `wardrobe_retrieval` sort key. No field added, removed, or retyped.
- **`Context`** (`schema.py`) — `formality`, `temp_band` are read by the new
  sort key (via the existing `FORMALITY_ORDER` scale and a new but purely
  internal warmth-ideal-by-band mapping local to `wardrobe_retrieval`, not a
  persisted or schema-level concept).
- **`DimensionScore`** (`schema.py`) — `dimension: "color_harmony"`,
  `value: float [0,1]`, `reason: str`. Output shape unchanged; only the
  *value* the color_harmony scorer computes changes, plus the `reason` text
  now names one of the new `L1-color-*` rule ids.
- **`ScoredOutfit`** (`schema.py`) — `rank_score: float`, computed by
  whichever `combine.Strategy` is passed to `rank_outfits`; unchanged shape,
  the *default* strategy used to compute it changes.

## New non-persisted internal values

- **HSL triple** `(h: float [0,360), s: float [0,1], l: float [0,1])` —
  returned by the new `colors.hex_to_hsl`. Pure function output, not stored,
  not part of any API response.
- **Per-slot sort key** `(formality_notch_distance: int, warmth_distance: int)`
  — computed transiently inside `wardrobe_retrieval` per candidate item, used
  only to order a list before slicing; discarded immediately after.

## Validation rules

- `hex_to_hsl` must accept the same hex formats `_hex_to_rgb`/`normalize_hex`
  already accept (existing validation, not new).
- `DimensionScore.value` stays constrained to `[0,1]` (existing
  `Field(ge=0.0, le=1.0)` on the model — the new scorer's clamp step is
  belt-and-suspenders, not a schema change).
