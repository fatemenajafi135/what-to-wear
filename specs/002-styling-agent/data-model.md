# Phase 1 Data Model: Styling Agent

All entities below are additive to the existing `schema.py` contracts (`Context`,
`WardrobeItem`, `Outfit`, `OutfitResult`, `Rationale`, `CitedSource`). None of the
frozen taxonomy (category groups, formality enum, warmth 0–5, seasons, hex colors —
constitution Principle VI) is touched. New types live in `schema.py` (Pydantic, per
Principle VII — single source of truth for contracts) or `scoring/` (plain
dataclasses for internal-only shapes not exposed over the API).

## New entities

### `DimensionScore` (Pydantic, `schema.py`)

One deterministic scorer's output for one outfit.

| Field | Type | Notes |
|---|---|---|
| `dimension` | `Literal["color_harmony", "formality_coherence", "weather_fitness", "silhouette_balance"]` | which of the four scorers produced this |
| `value` | `float`, `0.0`–`1.0` | higher is better, consistent scale across dimensions |
| `reason` | `str` | short human-readable explanation, e.g. "high contrast (7.1:1) — a bold pairing" |

Produced by `scoring/color_harmony.py` etc. (research.md §3). Immutable; recomputing
the same outfit + context yields an identical `DimensionScore` (SC-005).

### `ScoredOutfit` (Pydantic, `schema.py`)

Extends the existing `Outfit` (items + rationale) with scoring.

| Field | Type | Notes |
|---|---|---|
| `items` | `list[str]` | inherited from `Outfit` — wardrobe item ids only (FR-003) |
| `rationale` | `list[Rationale]` | inherited from `Outfit` |
| `scores` | `list[DimensionScore]`, exactly 4 | one per dimension, always all four (FR-008) |
| `rank_score` | `float` | the single value produced by the active combination strategy (FR-009a); used to order the returned list, not a fifth independent dimension |

`OutfitResult.outfits` becomes `list[ScoredOutfit]` in Phase 3, when the graph's
`explain` node (wrapping `cite.build_result`) starts producing it — not Phase 2,
which only builds the standalone `scoring/` package with nothing wired into
`OutfitResult` yet. This is **not** a backward-compatible additive change:
`/recommend`'s old linear-pipeline path never runs `score_and_rank`, so it can't
populate the required 4 scores against the new type. Rather than support two
result shapes indefinitely, `/recommend` is retired within Phase 3 once
`/suggest` is verified equivalent (tasks.md T037a) — see contracts/suggest.md.

### `ScoreCombinationStrategy` (plain type, `scoring/combine.py`, not a Pydantic
model — internal only, never serialized over the API)

```
Strategy = Callable[[list[DimensionScore]], float]
```

Not an entity with identity — a named, swappable function value. `EQUAL_WEIGHTED_AVERAGE`
is the default `Strategy` implementation shipped this feature (research.md §3,
FR-009a). At least one documented alternative (e.g. a fit-first lexicographic
strategy) ships alongside it, undocumented as *the* production default, for
evaluation experimentation.

### `SuggestRequest` (Pydantic, `schema.py` or `api.py`, mirrors `RecommendRequest`)

| Field | Type | Notes |
|---|---|---|
| `occasion` | `str` | required |
| `mood` | `Optional[str]` | |
| `formality` | `Optional[Formality]` | existing enum, unchanged |
| `location` | `Optional[str]` | |
| `temp_c` | `Optional[float]` | fallback per existing context assembler |
| `strategy` | `str`, default `"advanced"` | retrieval strategy, unchanged from `/recommend` |
| `thread_id` | `Optional[str]` | present when continuing a refinement conversation (US4); absent starts a new thread |

No `user_id` field — identical to the Phase 1 fix on `/recommend`, the requester's
identity always comes from the verified JWT (FR-001).

### `RefinementTurn` (not a new stored table — a checkpointer-managed graph state
snapshot, research.md §5)

| Field | Type | Notes |
|---|---|---|
| `thread_id` | `str` | checkpointer key |
| `original_context` | `Context` | preserved across refinements so "warmer" doesn't require restating the occasion (FR-013) |
| `last_result` | `OutfitResult` | the most recently returned suggestion set, for "give me alternatives" (FR-012) |
| `refinement_deltas` | `list[str]` | ordered log of applied refinements (e.g. `["warmer", "less formal"]`), for traceability in the rationale/explain node |

Lifecycle: created on the first `/suggest` call without a `thread_id`; updated on
each refinement call that supplies the same `thread_id`; no explicit deletion this
feature (checkpointer TTL/cleanup is out of scope — matches the existing
`memory/store.py` pattern of no expiry).

## Unchanged entities (referenced, not modified)

- `WardrobeItem`, `Context`, `Outfit`, `Rationale`, `CitedSource`, `OutfitResult` —
  `schema.py`, frozen taxonomy (Principle VI). `OutfitResult.outfits` element type
  changes from `Outfit` to `ScoredOutfit` (additive).
- `RetrievalResult` — `retrieval/base.py`, unchanged; consumed by `style_retrieval`
  and `wardrobe_retrieval` graph nodes as-is.

## Validation rules

- `DimensionScore.value` MUST be in `[0.0, 1.0]` (Pydantic `Field(ge=0, le=1)`).
- `ScoredOutfit.scores` MUST have exactly 4 entries, one per `dimension` literal,
  no duplicates (validated in the node that assembles it, mirroring FR-008).
- `ScoredOutfit.items` MUST all resolve to ids in the wardrobe used for the request
  (grounding check, reuses `pipeline/cite.owned_only`, extended for the
  no-catalog-substitution scope — see Future Work in spec.md).
