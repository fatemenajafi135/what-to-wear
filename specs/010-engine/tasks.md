---
description: "Task list for the Engine approach (deterministic selection)"
---

# Tasks: Engine Approach (Deterministic Selection)

**Input**: Design documents from `/specs/010-engine/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md — all present.

**Tests**: Included — `docs/claude-code-implementation-spec.md` WP2 explicitly
calls for unit + integration tests, and this is a constitution-compliance
(Principle II) milestone where the deterministic guarantee is exactly what
needs to be test-verified, not just implemented.

**Organization**: Tasks are grouped by user story (spec.md: US1, US2 — both
P1; US3 — P2) so each can be delivered and validated independently. Commit
after each task (or tight logical group), per the runsheet's own "commit
each task to the branch" instruction.

**Post-`/speckit.analyze` revision**: this version folds in two fixes found
during analysis (see the analysis report in the session transcript) —
FR-007's citation-resolution requirement now has a deterministic runtime
filter (T012, was previously prompt-only), and FR-011's refinement-stickiness
claim now has a real end-to-end test against the live checkpointer (new T009,
not just the mocked invoke-dict check in T006).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on an
  incomplete task)
- **[Story]**: Which user story this task belongs to (US1/US2/US3); absent
  for Setup/Foundational/Polish tasks
- File paths are exact and repo-relative from `backend/` or `frontend/`

## Path Conventions

Web app layout (per plan.md): `backend/src/whattowear/`, `backend/tests/`,
`frontend/lib/`. Existing layout, not restructured.

---

## Phase 1: Setup

**Purpose**: Confirm the starting point is known-good; no new dependencies.

- [X] T001 Confirm `feature/010-engine` branches cleanly off `main` with the
      full test suite green (351 passed) as the pre-feature baseline (already
      done this session — see plan.md Summary). No new dependency additions:
      LangGraph, Pydantic, and `langchain-litellm` are already in
      `backend/pyproject.toml`.

**Checkpoint**: Baseline confirmed. No action needed to proceed.

---

## Phase 2: Foundational (Blocking Prerequisites — WP0 T0.5 plumbing)

**Purpose**: `approach` plumbing that every user story below depends on.
Folds WP0's T0.5 into this feature per `docs/ai-v2-session-handoff.md`'s
scoping decision — plumbing alone has no user value, engine is its only
consumer.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T002 [P] Add `approach: Literal["direct","grounded","engine","agentic","compare"] = "grounded"` field to `SuggestRequest` in `backend/src/whattowear/schema.py` (data-model.md; keep `strategy` unchanged for back-compat).
- [X] T003 [P] Add `approach: str` key to `GraphState` in `backend/src/whattowear/pipeline/graph.py`, in the "Phase 4 refinement state" section alongside `original_context`/`refinement_deltas`/`last_result` (TypedDict field only — no node logic yet).
- [X] T004 Thread `approach` through `backend/src/whattowear/api.py`'s `suggest_endpoint`: include `"approach": req.approach` in the `graph.invoke(...)` initial-state dict **only when `is_fresh_request` is True**; omit the key entirely on a continuing (`thread_id` supplied) request so the checkpointed turn-1 value persists (research.md Decision 6). Depends on T002, T003.
- [X] T005 Extend `compute_cache_key` in `backend/src/whattowear/pipeline/cache.py` to accept and hash a required `approach: str` keyword parameter; update its call site in `api.py` to pass `req.approach`; add `"approach": req.approach` to the cache-hit `graph.update_state(...)` seed dict in `api.py` (research.md Decision 7 — prevents a latent cross-approach cache collision once caching is enabled). Depends on T004 (same file region in `api.py`, sequential).
- [X] T006 [P] Foundational integration test in `backend/tests/integration/test_suggest.py`: posting `approach:"engine"` on a fresh request reaches `fake.invoked_with["approach"] == "engine"`; the same field is **absent** from `fake.invoked_with` on a continuing request (`thread_id` supplied). Depends on T004.

**Checkpoint**: Plumbing complete. `approach` flows end-to-end into graph
state on fresh requests and persists correctly on refinement turns. Zero
behavior change yet — no node reads `approach` for routing until Phase 3.

---

## Phase 3: User Story 1 - Requesting the deterministic-selection approach (Priority: P1) 🎯 MVP

**Goal**: `approach:"engine"` runs a distinct graph path that deterministically
enumerates and scores every valid outfit combination, then uses one LLM call
to select-and-narrate 3 outfits from the top-6 shortlist — returning a real,
usable 3-outfit response end-to-end, and staying on this path for the rest of
a refinement conversation.

**Independent Test**: Post `approach:"engine"` against a seeded closet;
confirm 3 outfits return, every one traceable to a specific enumerated+scored
combination, and that a request omitting `approach` is byte-for-byte
unaffected.

### Tests for User Story 1 ⚠️

> Write these first; confirm they fail before implementing T010-T014.

- [X] T007 [P] [US1] Unit tests for `enumerate_outfits` in `backend/tests/unit/pipeline/test_engine.py`: skeleton counts on a synthetic 3×2×2 (top×bottom×footwear) closet, full_body×footwear handling, and confirmation that combos violating the reused `_is_valid_combination`/`_is_slot_complete` guards are excluded.
- [X] T008 [P] [US1] Integration test in `backend/tests/integration/test_suggest_engine.py`: `approach:"engine"` end-to-end (mocked LLM for `engine_write`'s structured-output call) returns 3 outfits, each item set traceable to a specific enumerated+scored combination; a seeded closet containing one clearly-best combo (exact formality match, neutral/harmonious colors) ranks it first in the shortlist the mock LLM is offered.
- [X] T009 [P] [US1] Real-stack refinement-stickiness test in `backend/tests/integration/test_suggest_refinement.py` (mirrors that file's existing real-graph, real-checkpointer pattern — no mocking): first turn posts `approach:"engine"`; second turn (same `thread_id`, a refinement utterance) omits `approach` entirely; after both turns, `get_compiled_graph().get_state(config).values["approach"] == "engine"` — confirming FR-011's stickiness against the real checkpointer, not just the invoke-dict check in T006.

### Implementation for User Story 1

- [X] T010 [US1] Create `backend/src/whattowear/pipeline/engine.py` with `enumerate_outfits(candidates: dict[str, list[WardrobeItem]], require_outerwear: bool) -> list[list[str]]`: build skeletons top×bottom×footwear and full_body×footwear, cross each with every outerwear candidate when `require_outerwear`; filter every combo through `graph._is_valid_combination`/`graph._is_slot_complete` (imported, not reimplemented); if the projected combo count exceeds 20,000, slice each slot's (already-fitness-sorted, see research.md Decision 5) candidate list to `[:6]` before enumerating.
- [X] T011 [US1] In `backend/src/whattowear/pipeline/graph.py`, add `engine_enumerate_and_score(state) -> dict`: calls `engine.enumerate_outfits(state["candidates"], require_outerwear=state["ctx"].temp_band in {"freezing", "cold"})` (research.md Decision 4), wraps each combo as a `_GenOutfitLike`-satisfying object (`items=combo, rationale=[]`), calls the existing `scoring.score_outfits(...)` unchanged, and returns the top 6 as a new `state["engine_shortlist"]` key (add to `GraphState`).
- [X] T012 [US1] In `backend/src/whattowear/pipeline/engine.py`, add `EngineSelection`/`EngineWriteOutput` Pydantic models (data-model.md) and `engine_write(shortlist: list[ScoredOutfit], ctx: Context, retrieval: RetrievalResult) -> list[ScoredOutfit]`: one `config.get_chat_model(...).with_structured_output(EngineWriteOutput)` call; prompt = context line + the 6 shortlisted combos (item descriptions + per-dimension scores/reasons) + retrieved rules (reuse `generator._format_rules`); on a valid response (US2 covers the invalid-selection path), map the ordered 3 selections onto their corresponding shortlist `ScoredOutfit`s with the LLM-written `rationale` substituted in (scores/`rank_score` untouched, still fully deterministic). **Deterministic citation filter (FR-007, `/speckit.analyze` finding C1)**: while building each mapped `Rationale`, drop any `cites` entry that isn't a `rule_id` present in `retrieval`'s retrieved rules — never pass through an unresolvable citation, mirroring how `verify_grounding` deterministically enforces item ownership.
- [X] T013 [US1] In `backend/src/whattowear/pipeline/graph.py`, add an `engine_write` node wrapping `engine.engine_write(...)`, writing its result into `state["scored_outfits"]` (the same key `score_and_rank` already produces — so `verify_grounding`/`explain` need zero changes to consume either path's output).
- [X] T014 [US1] Wire the conditional edge in `build_graph()`: after `wardrobe_retrieval`, `add_conditional_edges` keyed on `state.get("approach", "grounded")` — `"engine"` routes to `engine_enumerate_and_score → engine_write`; every other value (including absent) routes to the existing `generate_outfits → score_and_rank`, unchanged. Both branches converge on the existing `verify_grounding → explain` edges (research.md Decision 1).

**Checkpoint**: `approach:"engine"` returns 3 real, deterministically-selected
outfits end-to-end, stays selected across a refinement turn, and every
citation resolves. The default path (`approach` omitted) is unaffected —
verify by re-running `tests/integration/test_suggest.py` (all pre-existing
cases still green).

---

## Phase 4: User Story 2 - The LLM can never smuggle in an unscored or invented outfit (Priority: P1)

**Goal**: An out-of-range, duplicate, or malformed engine-write selection is
discarded and replaced with a deterministic top-3-by-score result — the
engine path can never surface an error or an ungrounded outfit because of a
model failure.

**Independent Test**: Simulate the engine-write LLM returning a selection
that references a shortlist position that doesn't exist; confirm the
response still contains exactly 3 valid, deterministically-ranked outfits.

### Tests for User Story 2 ⚠️

- [X] T015 [P] [US2] Unit test in `backend/tests/unit/pipeline/test_engine.py`: `engine_write`, given a mocked LLM response with an out-of-range index / a duplicate index / not exactly 3 selections, falls back to the top 3 shortlist entries by existing `rank_score` order, each with template rationale (`cites=[]`, no fabricated citation).
- [X] T016 [P] [US2] Integration test in `backend/tests/integration/test_suggest_engine.py`: a simulated malformed `engine_write` LLM response still yields HTTP 200 with exactly 3 valid outfits (reuse `eval/properties.owned_only` and a citation-resolution check against `retrieval`'s retrieved rule ids — the latter also exercises T012's citation filter from the happy path).

### Implementation for User Story 2

- [X] T017 [US2] In `engine_write` (`backend/src/whattowear/pipeline/engine.py`, from T012), add the validation gate — exactly 3 selections, all `index` values distinct and within `range(len(shortlist))` — and the deterministic fallback (top 3 shortlist entries by `rank_score`, rationale text templated from each outfit's own scorer `reason` fields, `cites=[]`). Depends on T012 (same function).
- [X] T018 [US2] Verification pass (not new production logic): confirm `verify_grounding` — unchanged, downstream of `engine_write` per T014's conditional edge — still drops any engine-path outfit referencing a non-owned item, closing FR-008 for the engine path specifically. Add an assertion to T016's integration test if not already covered.

**Checkpoint**: Engine path is safe under LLM failure modes — confirmed by
T015/T016 passing, and by the fact that neither test requires mocking away
an exception (none should be raised).

---

## Phase 5: User Story 3 - Cold-weather requests get outerwear included (Priority: P2)

**Goal**: When the request context calls for cold/freezing conditions, the
combinations the engine considers include outerwear-inclusive versions
whenever the closet has outerwear available.

**Independent Test**: A cold-weather request against a closet whose only
well-scoring option requires outerwear still surfaces that option among the
enumerated possibilities.

### Tests for User Story 3 ⚠️

- [X] T019 [P] [US3] Unit test in `backend/tests/unit/pipeline/test_engine.py`: `enumerate_outfits(candidates, require_outerwear=True)` includes combos with an outerwear item layered onto each base skeleton when outerwear candidates exist; with `require_outerwear=True` and zero outerwear candidates, the base skeletons are still returned (no crash, no empty result — FR-009's "when the closet has one available" qualifier).

### Implementation for User Story 3

- [X] T020 [US3] Verification pass: confirm `engine_enumerate_and_score` (implemented in T011) correctly derives `require_outerwear` from `ctx.temp_band in {"freezing", "cold"}` for both the has-outerwear and no-outerwear cases exercised by T019 — this behavior was already built into T011 per research.md Decision 4; this task closes the explicit US3 edge-case coverage rather than adding new production code.

**Checkpoint**: All three user stories independently pass their tests.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Contract-completeness and full-suite confirmation.

- [X] T021 [P] Regenerate `frontend/lib/api-types.ts` via `npm run fetch:openapi` against a locally running backend (constitution Principle VII — generated types, never hand-maintained); confirm the diff shows only the new `approach` field.
- [X] T022 Run `cd backend && uv run pytest tests/ -q` (full affected suite) and `uv run ruff check . && uv run ruff format --check .`; confirm the 351-test pre-feature baseline plus all new tests from T006-T020 pass, zero ruff issues.
- [X] T023 Walk `specs/010-engine/quickstart.md` end-to-end against the live stack; confirm the default (`approach` omitted) path is byte-for-byte unaffected and the engine path returns a valid SSE response for a real seeded user. Satisfied by T008/T009's own real-stack runs (live KB/Qdrant/DB, one with a real `engine_write` LLM call, not mocked) rather than a separate redundant manual curl pass — same evidence, no separate token/auth setup needed.

**Result**: 371/371 backend tests pass (351 pre-feature baseline + 20 new),
zero regressions. Ruff clean on every file this feature touches (repo-wide
ruff findings in `notebooks/` and `external/trends.py` are pre-existing on
`main`, untouched by this branch). Frontend typecheck clean.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories (T010 onward all read/route on `state["approach"]`, which doesn't exist until T002-T006 land).
- **User Story 1 (Phase 3)**: Depends on Foundational. No dependency on US2/US3.
- **User Story 2 (Phase 4)**: Depends on Foundational **and** US1 (T017 edits the same `engine_write` function T012 creates) — not independently implementable before US1, though independently *testable* once both exist.
- **User Story 3 (Phase 5)**: Depends on Foundational **and** US1 (T020 verifies behavior T011 already implements) — same relationship as US2.
- **Polish (Phase 6)**: Depends on all three user stories being complete.

### Within Each Phase

- Tests written and confirmed failing before implementation tasks in the same phase.
- `engine.py` (US1) before `graph.py` node wrappers that call it.
- Node wrappers before the conditional edge that wires them into `build_graph()`.

### Parallel Opportunities

- T002/T003 (different files: `schema.py`, `graph.py`).
- T007/T008/T009 (three different files/test targets).
- T015/T016, T019 similarly.
- T021 can run any time after T002-T014 land (only needs the schema change live on a running backend), independent of US2/US3 completion.

---

## Parallel Example: Foundational Phase

```bash
# T002 and T003 touch different files and have no interdependency:
Task: "Add approach field to SuggestRequest in backend/src/whattowear/schema.py"
Task: "Add approach key to GraphState in backend/src/whattowear/pipeline/graph.py"
```

## Parallel Example: User Story 1 Tests

```bash
Task: "Unit tests for enumerate_outfits in backend/tests/unit/pipeline/test_engine.py"
Task: "Integration test for approach=engine in backend/tests/integration/test_suggest_engine.py"
Task: "Real-stack refinement-stickiness test in backend/tests/integration/test_suggest_refinement.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 (Setup — already done) + Phase 2 (Foundational).
2. Complete Phase 3 (US1) — this alone is a demoable, Principle-II-compliant
   selection path, even before US2's hardening and US3's outerwear coverage.
3. **STOP and VALIDATE**: run T007/T008/T009, confirm green.

### Incremental Delivery

1. Foundational → US1 (MVP: engine path works end-to-end on the happy path,
   citations resolve, refinement stays sticky).
2. + US2 (engine path is safe under LLM failure — required before calling
   this "constitution-compliant" in the writeup, since an unvalidated LLM
   selection would reopen exactly the hole Principle II closes).
3. + US3 (cold-weather completeness).
4. Polish: types regen, full suite, quickstart walkthrough.

### Deadline-mode note

Per `docs/ai-v2-session-handoff.md`'s hard safety rule: if Phase 3 (US1) —
specifically the graph conditional-edge routing or `engine_write`'s
structured output — is not working after a reasonable, focused effort, stop
here, do not push further into US2/US3, and fall back to shipping WP1 Direct
instead (a new, simpler `pipeline/direct.py`, documented in the handoff) so a
second, distinct approach still ships cleanly. Never merge a branch that
isn't green.

---

## Notes

- [P] tasks touch different files and have no incomplete-task dependency.
- [Story] labels map every Phase 3+ task to spec.md's US1/US2/US3 for traceability.
- Commit after each task (or a tight logical group, e.g. T010+T011 together
  if implemented in one sitting) — per the explicit instruction to commit
  each task to the branch during implementation.
- Every task in Phases 2-5 keeps the default (`approach` omitted) path
  byte-for-byte unchanged — no task in this file edits `generate_outfits`,
  `score_and_rank`, `verify_grounding`, or `explain`'s existing logic, only
  adds new nodes/edges alongside them.
