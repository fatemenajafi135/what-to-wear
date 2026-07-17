# Phase 1 Data Model: Engine Approach (Deterministic Selection)

No changes to persisted storage (no migration) and no changes to the frozen
item taxonomy (constitution Principle VI). This feature adds request/graph-
state fields and two new in-memory (non-persisted) Pydantic models for one
LLM call's structured output.

## Modified: `SuggestRequest` (`schema.py`)

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `approach` | `Literal["direct","grounded","engine","agentic","compare"]` | `"grounded"` | NEW. `"grounded"` names today's existing default pipeline (`generate_outfits`→`score_and_rank`) so its meaning is explicit rather than implicit-via-absence. Only `"grounded"` (implicit) and `"engine"` are implemented by this feature; `"direct"`/`"agentic"`/`"compare"` are accepted values (so the Literal matches the full roadmap per `docs/claude-code-implementation-spec.md` T0.5) but not yet routed anywhere new — they fall through to the `grounded` branch of the conditional edge exactly like today, i.e. no behavior change for them either. |
| `strategy` | `str` | `"advanced"` | UNCHANGED — kept for back-compat per the existing field and the T0.5 instruction. |

## New: `GraphState.approach` (`pipeline/graph.py`)

| Field | Type | Notes |
|-------|------|-------|
| `approach` | `str` (not `Optional` — always resolved to at least `"grounded"` before the routing conditional edge reads it) | Lives in the "Phase 4 refinement state" section of `GraphState`, alongside `original_context`/`refinement_deltas`/`last_result`. Set from the request only on a fresh (non-continuing) invoke; a continuing invoke omits the key from its input dict so the checkpointed turn-1 value persists automatically (see research.md Decision 6). |

## New: `EngineSelection` / `EngineWriteOutput` (`pipeline/engine.py`)

In-memory only — the structured-output schema for the engine path's one LLM
call. Never persisted, never returned to the API caller directly (mapped
into the existing `ScoredOutfit`/`Rationale` response shapes before
`explain` builds the response).

```python
class EngineSelection(BaseModel):
    index: int              # 0-based position into the 6-item shortlist offered to the LLM
    rationale: list[GenRationale]  # reused from generator.py: {text: str, cites: list[str]}

class EngineWriteOutput(BaseModel):
    selections: list[EngineSelection]  # must be exactly 3 valid, distinct, in-range indices to be trusted
```

**Validation rule** (enforced in `pipeline/engine.py`, not by Pydantic field
constraints alone — the constraint is relative to the shortlist length,
which Pydantic can't express): `len(selections) == 3` and all `index` values
are distinct and within `range(len(shortlist))`. Violation → the entire
`EngineWriteOutput` is discarded; see research.md Decision 3 for the
deterministic fallback.

## Modified: `GraphState.candidates` consumers — no change

`engine_enumerate_and_score` reads `state["candidates"]` (the existing
per-slot, capped, sorted dict `wardrobe_retrieval` already produces) exactly
as `generate_outfits` does today. No new state shape here — this feature is
a new *consumer* of an existing state key, not a new producer.

## Unchanged: `ScoredOutfit`, `DimensionScore`, `SuggestResult`, `Rationale`

The engine path's final output is mapped into these exact existing types
(`schema.py`) before `verify_grounding`/`explain` run — no new response-level
type reaches the API caller. `ScoredOutfit.scores` keeps its existing
"exactly one entry per `SCORE_DIMENSIONS`" validator; engine-path outfits
satisfy it the same way grounded-path outfits do, since both are produced by
the same `scoring.score_outfits` call.

## Modified: `compute_cache_key` (`pipeline/cache.py`)

Adds `approach: str` as a required keyword parameter, included in the hashed
key material (research.md Decision 7). Not a schema change — an internal
cache-key input, invisible to callers.

## Entity relationship summary

```text
SuggestRequest.approach ──(api.py, fresh turns only)──> GraphState.approach
                                                             │
                                                             ▼
                                          conditional edge after wardrobe_retrieval
                                             │                              │
                                    (approach=="engine")            (otherwise, unchanged)
                                             ▼                              ▼
                                  engine_enumerate_and_score          generate_outfits
                                  (engine.py::enumerate_outfits            │
                                   + scoring.score_outfits)                ▼
                                             │                       score_and_rank
                                             ▼                              │
                                      engine_write                         │
                                  (EngineWriteOutput, validated             │
                                   + deterministic fallback)                │
                                             │                              │
                                             └──────────► ScoredOutfit list ◄┘
                                                             │
                                                             ▼
                                              verify_grounding → explain
                                                    (unchanged, both paths)
```
