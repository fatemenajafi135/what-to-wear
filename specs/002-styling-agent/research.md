# Phase 0 Research: Styling Agent

All unknowns below are resolved from the existing, locked stack (constitution
"Technology Constraints") and the code already in `backend/src/whattowear/`. No
external research agents were dispatched — the open questions are internal design
decisions, not technology surveys.

## 1. Graph node order and library

**Decision**: LangGraph `StateGraph` with nodes `parse_request → gather_context →
style_retrieval → build_query → wardrobe_retrieval → generate_outfits →
score_and_rank → explain`, linear edges (no branching) for the MVP.

**Rationale**: `langgraph>=1.0.0,<2.0.0` is already a pyproject dependency (used
today only for `memory/store.py`'s checkpointer/store, not yet for a graph). This
node order is a direct translation of the existing linear pipeline
(`pipeline/run.py`'s stages 1–5) plus the new `score_and_rank` stage — it does not
introduce a new architecture, it makes the existing stage boundaries explicit graph
nodes so LangSmith tracing, checkpointing, and future conditional edges (e.g.
refinement re-entry) have somewhere to attach. `style_retrieval` before
`wardrobe_retrieval` preserves constitution Principle III verbatim.

**Alternatives considered**: A single monolithic node wrapping `run_pipeline()`
unchanged — rejected because it would give the checkpointer nothing meaningful to
checkpoint between, and would make `score_and_rank` (Phase 2's new stage) an
afterthought bolted onto `generate_outfits` rather than an independent, testable
node.

## 2. Reusing existing modules as graph nodes

**Decision**: `parse_request` and `gather_context` wrap
`pipeline/context_assembler.assemble_context`; `style_retrieval` +
`build_query` wrap `pipeline/query_builder.route/naive_query/l3_query` plus the
existing `_retrieve` KB call; `wardrobe_retrieval` is the wardrobe half of context
assembly (already inside `assemble_context` via `load_wardrobe`); `generate_outfits`
wraps `pipeline/generator.generate`; `explain` wraps `pipeline/cite.build_result`.
None of `query_builder.py`, `context_assembler.py`, `generator.py`, `cite.py`,
`colors.py`, `categories.py` are rewritten — each becomes a thin node function that
calls the existing pure function and maps `GraphState` fields in/out.

**Rationale**: Constitution Principle I ("Existing pipeline is authoritative")
requires explicit justification to rewrite any of these; there is none here — they
already do exactly what each node needs. This also means Phase 1's new unit tests
for `cite.py`/`categories.py`/`query_builder.py`/`colors.py`/`eval/properties.py`
remain valid unchanged; the graph nodes get thin wrapper tests, not replacement
tests.

**Alternatives considered**: Rewriting `context_assembler`/`query_builder` directly
as LangGraph nodes (merging the module into the graph file) — rejected as an
unjustified rewrite under Principle I, and it would break the modules' existing
standalone unit tests and reuse by the eval harness.

## 3. Deterministic scoring package shape

**Decision**: New `backend/src/whattowear/scoring/` package:
- `scoring/color_harmony.py`, `formality_coherence.py`, `weather_fitness.py`,
  `silhouette_balance.py` — each exposes one pure function
  `score(outfit_items: list[WardrobeItem], ctx: Context) -> DimensionScore`
  returning a `(value: float 0-1, reason: str)` pair (see data-model.md).
- `scoring/combine.py` — the FR-009a swappable combination strategy. A `Strategy`
  is a plain function `list[DimensionScore] -> float`; `EQUAL_WEIGHTED_AVERAGE` is
  the shipped default; `rank_outfits(outfits, strategy=EQUAL_WEIGHTED_AVERAGE)` is
  the one call site `score_and_rank` uses, so switching strategies during
  evaluation is a one-argument change, not a code change inside the graph node.

**Rationale**: Constitution Principle V requires these functions to be usable
unchanged inside the eval harness — a plain function per dimension, no class
hierarchy, is the simplest form that satisfies "no repository patterns / service
layers / ABCs unless two concrete implementations exist today" (Quality Bar). Two
concrete combination strategies *do* exist today by design (per the spec's
clarification: ship the default, document at least one alternative) — that is
exactly the "two concrete implementations" bar the constitution sets for allowing
a seam, so `combine.py` uses a strategy **function** (not a class/ABC): a
`Callable[[list[DimensionScore]], float]` typedef, no interface class needed since
Python functions are already first-class.

**Alternatives considered**: A `Scorer` ABC with subclasses — rejected, no second
concrete scorer implementation exists per dimension (only a second *combination*
strategy exists, which the plain-function seam already covers) — a class hierarchy
here would be exactly the premature abstraction the constitution warns against.

## 4. Candidate pruning and combination cap

**Decision**: Hard-constraint pruning (warmth band, formality band, season) runs
**before** combination, using the item-level filtering already expressed in
`eval/properties.py`'s `weather_appropriate`/`occasion_fit` predicates (reused, not
reimplemented). After pruning, candidates are capped at **k=8 per slot** before the
combinatorial step in `generate_outfits`/`score_and_rank`, matching the plan
directive and keeping worst-case combinations bounded (5 slots × 8 = 8^5 = 32,768
raw combinations before scoring — combined with hard per-outfit slot-count limits
in practice far fewer).

**Rationale**: Directly specified in the plan input; matches constitution Principle
II ("deterministic pruning, combination, and scoring") and keeps `score_and_rank` a
bounded, testable computation rather than brute-forcing an arbitrarily large
closet (closets are capped at 200 items per Feature 001's SC-001, but 200 items
across slots without pruning would be combinatorially unusable).

**Alternatives considered**: No cap (score every combination) — rejected as
unbounded for large closets; a configurable cap read from settings — deferred
(YAGNI per Quality Bar; k=8 is a constant until evidence says otherwise).

## 5. Conversational refinement state

**Decision**: Use the LangGraph checkpointer already present in
`memory/store.py` (`checkpointer = InMemorySaver()`), keyed by `thread_id`, for
Phase 4. Swap `InMemorySaver` for `PostgresSaver`
(`langgraph-checkpoint-postgres`, a new dependency to add in Phase 4) so refinement
threads survive process restarts, matching the plan directive of "Postgres
checkpointer keyed by thread_id."

**Rationale**: `memory/store.py`'s own docstring already names this exact swap as
its "extension seam" — this feature is that seam being used, not a new mechanism.
Deferred to Phase 4 specifically (not Phase 3) because refinement is US4, scoped to
Phase 4 in the spec's Delivery Phases.

**Alternatives considered**: A hand-rolled thread-state table in the existing
Postgres schema — rejected, duplicates what `langgraph-checkpoint-postgres`
already does and would be a second, hand-maintained persistence mechanism for the
same concern (checkpointer state), contra Quality Bar simplicity.

## 6. `/suggest` streaming transport

**Decision**: FastAPI `StreamingResponse` emitting `text/event-stream`
(server-sent events), following the existing plan directive. No new dependency is
required — `text/event-stream` framing (`data: ...\n\n`) is written directly by the
endpoint; `sse-starlette` is *not* added since FastAPI's `StreamingResponse` covers
the full requirement without an extra dependency.

**Rationale**: Keeps to "no new dependency unless justified"; `StreamingResponse`
is already available via the existing `fastapi` dependency. Event payloads are
JSON-encoded `OutfitResult`-shaped chunks (see contracts/suggest.md) plus a final
`done` event.

**Alternatives considered**: WebSockets — rejected, SSE is unidirectional
(server→client) which matches "stream suggestions as they're scored", is simpler to
proxy/cache, and was explicitly named in the plan directive.

## 7. Body shape and catalog substitution

**Decision**: No design work in this feature. Per the spec's Clarifications and
Future Work, `Context`/`WardrobeItem` gain no new fields for body shape, and
`generate_outfits`/`score_and_rank` never reach into the shared catalog — an outfit
missing a required slot is dropped from the candidate set, not completed from the
catalog.

**Rationale**: Directly resolved by the spec clarification session; re-stated here
so a later research pass doesn't accidentally reintroduce it mid-implementation.
