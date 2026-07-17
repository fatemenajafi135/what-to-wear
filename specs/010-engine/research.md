# Phase 0 Research: Engine Approach (Deterministic Selection)

No `NEEDS CLARIFICATION` markers exist in the Technical Context — this
project's architecture (LangGraph pipeline, deterministic scoring package,
existing coherence guards) already fully determines the approach. This
document records the design decisions made while translating the spec's
functional requirements into a concrete graph/module design, each with
rejected alternatives, rather than open unknowns.

## Decision 1: Graph routing via a conditional edge, not a parallel graph

**Decision**: After `wardrobe_retrieval`, add one `add_conditional_edges` call
keyed on `state.get("approach", "grounded")`. `"engine"` routes to
`engine_enumerate_and_score → engine_write`; every other value (including
absent) routes to the existing `generate_outfits → score_and_rank`. Both
branches converge back into the existing, unchanged `verify_grounding →
explain` tail.

**Rationale**: The graph is currently pure linear edges (`build_graph`'s
`add_edge` calls). A conditional edge is the smallest change that lets two
selection strategies share the same pre-processing (`gather_context` through
`wardrobe_retrieval`) and the same post-processing safety net
(`verify_grounding`, `explain`) — neither of which this feature has any
reason to fork. `verify_grounding` in particular must stay a single
implementation (constitution Principle IV) regardless of how an outfit was
selected.

**Alternatives considered**:
- *A fully separate second graph* — rejected: would duplicate
  `verify_grounding`/`explain`, directly against Principle I ("extend, don't
  fork").
- *An `if/else` inside `generate_outfits` itself* — rejected: conflates two
  structurally different flows (LLM-assembles-combos vs.
  enumerate-then-LLM-picks) into one function's control flow, harder to test
  in isolation than two small nodes.

## Decision 2: Reuse `score_outfits` by wrapping enumerated combos, not reimplementing scoring

**Decision**: `engine_enumerate_and_score` wraps each enumerated
`list[str]` combo in a lightweight object satisfying the existing
`_GenOutfitLike` protocol (`items: list[str]`, `rationale: list` — empty at
this stage) and calls the existing `scoring.score_outfits(...)` unchanged.
The returned `ScoredOutfit`s (already carrying all four dimension scores and
`rank_score`, already sorted) are sliced to the top 6 as the shortlist.

**Rationale**: `score_outfits`/`DIMENSION_SCORERS` never read `rationale` —
only `items` and `ctx` — so an empty rationale list at scoring time is a
valid input needing no change to the scoring package (constitution
Principle V forbids a second, divergent scoring implementation).

**Alternatives considered**: A bespoke scoring call inside `engine.py`
reusing `DIMENSION_SCORERS` directly — rejected as needless duplication of
wiring `score_outfits` already provides; no behavioral difference, only
extra surface area.

## Decision 3: `engine_write`'s structured output, validation, and fallback

**Decision**: New Pydantic models in `pipeline/engine.py`:
```python
class EngineSelection(BaseModel):
    index: int  # position into the 6-item shortlist, 0-based
    rationale: list[GenRationale]  # reused from generator.py — same {text, cites} shape

class EngineWriteOutput(BaseModel):
    selections: list[EngineSelection]
```
`engine_write` calls the LLM once with the shortlist (item descriptions +
per-dimension scores/reasons) and the retrieved rules, requesting an ordered
pick of 3 indices with rationale. Validation: the output is accepted only if
it has exactly 3 selections, all indices are in range and distinct. Any
violation (out-of-range index, duplicate index, wrong count, or a structured-
output/call failure) discards the entire LLM output and falls back to the
top 3 shortlist entries in rank order, each given a deterministic rationale
(`text="Selected by deterministic ranking (top {dimension})."`, `cites=[]`)
built from the scorer's own `reason` fields — never a fabricated rule
citation.

**Rationale**: Matches spec FR-006 exactly ("the caller always receives a
valid, deterministically-grounded result") and mirrors the existing pattern
elsewhere in this codebase of never trusting unvalidated LLM structured
output outright (`verify_grounding` plays the same "safety net, not the only
guarantee" role for item grounding).

**Addendum (`/speckit.analyze` finding C1)**: selection-index validation
alone doesn't close FR-007 ("every rationale MUST cite only rules that were
actually retrieved") — the LLM could return a structurally valid selection
(3 distinct, in-range indices) whose rationale still cites a hallucinated
`rule_id`. `engine_write` therefore also filters each accepted rationale's
`cites` list against the actual retrieved rule_id set (from `retrieval`,
already a required parameter) before returning, dropping any unresolvable
entry rather than the whole outfit. This runs on the happy path only — the
deterministic fallback's `cites=[]` already trivially satisfies FR-007.

**Alternatives considered**: Surfacing an error/500 to the caller on invalid
selection — rejected: violates FR-006 and the project's own "the demo must
never break" operating principle (`docs/ai-v2-session-handoff.md`'s hard
safety rule for this exact feature).

## Decision 4: Outerwear-crossing threshold reuses the existing weather band split, not a new one

**Decision**: `require_outerwear` is computed as
`ctx.temp_band in {"freezing", "cold"}` — the identical band set
`pipeline/graph.py` already uses for its own hard-constraint warmth ceiling
(`_MAX_WARMTH_BY_BAND` covers the *hot/warm* side of the same threshold
family). No new constant is introduced.

**Rationale**: Principle I — a second, slightly-different temperature
threshold living in a different module would be exactly the kind of
"invented a new one instead of reusing what exists" drift the constitution
warns against.

**Alternatives considered**: Also considering `ctx.condition` (e.g. "rain")
as an outerwear trigger — explicitly out of scope per the spec (temp-band
only, matching `docs/claude-code-implementation-spec.md` WP2's own wording).

## Decision 5: Safety valve slices the already-sorted candidate lists, no new sort

**Decision**: Before materializing the full combination list,
`enumerate_outfits` computes the projected count
(`len(top)*len(bottom)*len(footwear)`, `+ len(full_body)*len(footwear)`,
each `× len(outerwear)` when crossing is active). If the projection exceeds
20,000, each slot's candidate list is tightened to its own top 6 by simple
slicing (`items[:6]`) — **no new sort is needed** because
`wardrobe_retrieval` (`pipeline/graph.py`) already sorts every slot's
candidates by ascending-badness fitness (`_slot_fitness_key`, Feature 009)
*before* capping each slot at 8. `enumerate_outfits` only ever receives
already-best-first-ordered lists, so narrowing further is a slice, not a
second sort.

**Rationale**: Reuses the ordering `wardrobe_retrieval` already produced
instead of recomputing it — cheaper and avoids a second, potentially
divergent notion of "best fit" (`_slot_fitness_key` needs `ctx`, which
`enumerate_outfits` deliberately doesn't take as a parameter — see its
signature in `docs/claude-code-implementation-spec.md` WP2 — so recomputing
it here isn't even the simplest option available; slicing the existing order
is).

**Alternatives considered**: A hard combination-count cutoff applied *after*
generating the full Python list — rejected: defeats the purpose of a safety
valve (the expensive step already happened) and was explicitly called out in
`docs/ai-v2-session-handoff.md` as the wrong approach ("tighten to top-6/slot
... before ever enumerating"). Re-sorting inside `enumerate_outfits` — 
rejected once the already-sorted-input property above was noticed: strictly
redundant work.

## Decision 6: `approach` persistence across refinement turns

**Decision**: `GraphState` gains a plain `approach: str` key (default
`"grounded"` when absent), living alongside the existing "Phase 4 refinement
state" fields (`original_context`, `refinement_deltas`, `last_result`) —
*not* nested inside the `Context` model. `api.py`'s `suggest_endpoint`
includes `"approach": req.approach` in the dict passed to `graph.invoke(...)`
**only when `is_fresh_request` is true** (mirroring the existing
`is_fresh_request` gate already used for the cache lookup); on a continuing
thread (`thread_id` supplied), the key is omitted from the invoke input
entirely, so LangGraph's checkpoint-merge behavior (only keys present in a
given invoke's input dict are overwritten; absent keys retain their last
checkpointed value) leaves turn 1's `approach` untouched regardless of
whatever value a later refinement request's body happens to carry.

**Rationale**: This achieves exactly the "sticky across a conversation"
behavior `original_context` already has for `occasion`/`mood`/`formality`,
using the same underlying LangGraph mechanism, with zero new fields on the
`Context` model (simpler — `approach` is about *how* a suggestion is
produced, not part of the normalized request context `Context` represents).
`strategy`'s existing (unprotected, always-re-passed) behavior is
deliberately left untouched — changing it is out of this feature's scope.

**Alternatives considered**: Adding `approach` as a field on `Context` itself
(persisted automatically by `gather_context`'s existing
original-vs-continuing branch) — workable, but rejected as a slightly larger
footprint (touches `schema.py`'s `Context` model and
`context_assembler.assemble_context`'s signature) for no behavioral gain
over the invoke-input-gating approach, which needs only an `api.py` edit.

## Decision 7: Cache-key/seed extension for `approach` (small, in-scope correctness fix)

**Decision**: `pipeline/cache.py::compute_cache_key` gains `approach: str` as
an explicit keyword parameter, included in the hashed material. The cache-hit
branch in `api.py` (which seeds the checkpointer via `graph.update_state`)
adds `"approach": req.approach` to the seeded state dict alongside the
fields it already seeds.

**Rationale**: The suggestion cache (`WTW_SUGGEST_CACHE_ENABLED`, currently
default off — see `CLAUDE.md`) is still an existing component this feature
must integrate with correctly (Principle I). Without this, an `engine`
request and a `grounded` request with otherwise-identical context would
collide on the same cache key once caching is enabled later, silently
serving one approach's result for the other — a latent correctness bug this
feature would otherwise introduce into dormant code. The fix is two
additive lines, not a cache redesign.

**Alternatives considered**: Leaving `cache.py` untouched since the cache is
off by default today — rejected: cheap to fix now, expensive (a confusing
bug report) to diagnose later once someone flips the flag.
