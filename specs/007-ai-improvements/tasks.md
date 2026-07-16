# Tasks: L1/L3 Retrieval Restructure + Refinement Warmth-Floor Fix

**Input**: Design documents from `/specs/007-ai-improvements/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Tests**: Included — this feature modifies deterministic, unit-tested code paths and the constitution's
Quality Bar requires unit tests for deterministic logic; existing tests that encode the old (buggy)
behavior are updated, not just added to.

**Organization**: Tasks are grouped by user story (US1 = L1 semantic layer, US2 = live L3 Tavily,
US3 = warmth-floor fix) per spec.md's priorities. All three are independent of each other (touch
disjoint functions) and can be implemented/tested/committed in any order.

All paths are relative to `backend/`.

**Environment constraints hit this implementing session** (read before checking task status below):
this session ran in a fresh remote sandbox clone — not an existing checkout or a `git worktree add` off
one — with **no `backend/.env`** and **none of the gitignored `backend/data/` source files** the KB
build needs (`data/wikipedia/*.md`, `data/books/*.epub`, `data/fixtures/wardrobe.json`; only the 6 files
actually tracked in git — `golden_set.yaml`, `manifest.yaml`, and the 3 `kb/*.jsonl` card files — were
present). This is the same class of gap CLAUDE.md's Gotchas section already documents for a fresh `git
worktree add`, just hit here in a fresh container clone instead. Confirmed two ways: `get_kb()` fails on
a missing `.epub` file before ever reaching a network call, and the warmth-floor evidence script fails
on `psycopg` connection-string parsing against a placeholder `DATABASE_URL` before reaching the graph at
all. **Tasks T007, T017, T022, T027, T028, T029, T032, T033, T034 (and the credential/reachability half
of T001) could not be executed in this session** and are left `[ ]` below — every other task (all
pure-Python logic changes and all unit tests that don't touch the DB/KB/gateway) was implemented and
verified green. The next session needs real `.env` credentials and a full `backend/data/` (copied from
an existing checkout, per the same Gotchas entry) to complete the ones left open.

## Phase 1: Setup

- [ ] T001 Confirm environment is ready: `uv sync --group dev` succeeds, `backend/.env` has
      `TAVILY_API_KEY` set (already required by `external/trends.py`, no new key needed), Qdrant/DB
      reachable — no new dependencies to add (`langchain-tavily` already in `pyproject.toml`).
      `uv sync --group dev` succeeded this session; credential/reachability confirmation did not (see
      environment note above).

**Checkpoint**: No foundational/blocking work needed — all three user stories touch pre-existing,
disjoint functions and share no new infrastructure.

---

## Phase 2: User Story 1 - Deeper style rationale from long-form sources (Priority: P1) 🎯 MVP

**Goal**: `retrieve_l1()` returns both the existing hand-written atomic rule cards and semantically
retrieved passages from the already-embedded long-form sources (Wikipedia color-theory/harmony/
complementary-colors, Chevreul, Munsell), so a suggestion's rationale can cite a specific passage, not
only a card.

**Independent Test**: Call `retrieve_l1(kb, ctx)` for a query and confirm the result contains chunks
with both `granularity: "atomic"` and `granularity: "section"`; confirm `build_kb`'s reference-only-text
guard still passes; confirm baseline's recall is unaffected (`quickstart.md` §1).

### Tests for User Story 1

- [X] T002 [P] [US1] Create `tests/unit/retrieval/__init__.py` (new directory, matching the existing
      `tests/unit/pipeline/__init__.py` / `tests/unit/scoring/__init__.py` convention), then add a
      unit test in `tests/unit/retrieval/test_hybrid.py` (new file):
      `retrieve_l1()` returns a union of atomic + section chunks for a query with L1 matches in both
      pools, using a fake/stub `KnowledgeBase` (mock `vectorstore.similarity_search` to return a
      canned `Document` list tagged `layer=L1, granularity=section`, and `chunks` with atomic cards) —
      no live embedding call in this test.
- [X] T003 [P] [US1] Unit test in `tests/unit/retrieval/test_hybrid.py`: `retrieve_l1()`'s existing
      `color_filter` narrowing still only narrows the atomic pool (unchanged behavior) and does not
      accidentally apply to the new semantic branch.

### Implementation for User Story 1

- [X] T004 [US1] In `src/whattowear/ingest/build_kb.py`'s `build_vectorstore()`, add a second
      `client.create_payload_index(collection_name=collection, field_name="metadata.granularity",
      field_schema=models.PayloadSchemaType.KEYWORD)` call alongside the existing `metadata.layer`
      index (server-mode only, same `if url:` block) — required before a compound `layer`+
      `granularity` filter will work against a real Qdrant server (research.md D2).
- [X] T005 [US1] In `src/whattowear/retrieval/hybrid.py`, add `_l1_semantic_filter()` (mirrors
      `_l3_filter()`) building a `models.Filter` on `metadata.layer == "L1"` AND
      `metadata.granularity == "section"`.
- [X] T006 [US1] In `src/whattowear/retrieval/hybrid.py`, extend `retrieve_l1()` to also run
      `kb.vectorstore.similarity_search(l1_query, k=5, filter=_l1_semantic_filter())` (query text =
      `query_builder.l3_query(ctx)`, per research.md D1) and return the union of the existing atomic
      load-all with these results, de-duplicated by `rule_id` (defensive; the granularity filter
      should already prevent overlap). Keep the existing `color_filter` behavior scoped to the atomic
      pool only, per T003.
- [ ] T007 [US1] Run `uv run python -m whattowear.ingest.build_kb --sample-check` and confirm the
      final report line (`OK: metadata complete, rule_ids unique, no reference-only book text
      stored.`) still prints — the reference-only guard (`build_kb._print_report`'s `leaked` assertion)
      must keep passing (SC-002). **Not run this session** — needs the missing `data/wikipedia/*.md` /
      `data/books/*.epub` source files and a real gateway key (see environment note above).
- [X] T008 [US1] Run `uv run pytest tests/unit/retrieval/test_hybrid.py -q` — new tests green. **Ran
      this session: 12 passed** (this file, plus test_advanced.py, share one run — see T016).

**Checkpoint**: User Story 1 fully functional and independently testable — `retrieve_l1()` returns a
richer, still-grounded pool; nothing else in the pipeline needed to change for this to be true.

---

## Phase 3: User Story 2 - Suggestions reflect current trends, not a fixed snapshot (Priority: P2)

**Goal**: `retrieve_l3()` calls Tavily live (via the existing `external/trends.search_trends()`) instead
of querying the static pre-ingested trend collection, for the `hybrid`/`advanced` strategies, gated on
`ctx.season` exactly as today, still executing before `wardrobe_retrieval`, degrading gracefully on
failure, and remaining citable/grounded.

**Independent Test**: Call `retrieve_l3(l3_query)` directly and confirm it returns live, citable
`Document`s; confirm a `TAVILY_API_KEY`-less/network-failure run returns `[]` without raising
(`quickstart.md` §2); confirm `baseline`'s corpus/recall is untouched (its own manifest-driven ingest of
`l3_trend_cards.jsonl` is unchanged, per research.md D6).

### Tests for User Story 2

- [X] T009 [P] [US2] Unit test in `tests/unit/retrieval/test_hybrid.py`: `retrieve_l3()` (new
      signature, no longer takes `kb`) calls `external.trends.search_trends` (patched/mocked) and maps
      each result dict into a `Document` with `metadata.layer == "L3"`, `metadata.rule_id` starting
      with `"L3-live-"`, `metadata.source`/`metadata.url` populated from the result — per
      research.md D4's exact shape.
- [X] T010 [P] [US2] Unit test in `tests/unit/retrieval/test_hybrid.py`: when `search_trends` raises
      (any `Exception`), `retrieve_l3()` returns `[]` and does not propagate — FR-008/SC-004.
- [X] T011 [P] [US2] Unit test in `tests/unit/retrieval/test_advanced.py` (new file): `advanced.retrieve()`
      still over-fetches (`FIRST_STAGE_K` live results) then reranks down to `k_l3` via the existing
      `get_reranker` call — assert `hybrid.retrieve_l3` is invoked with `k=FIRST_STAGE_K`, not `k_l3`
      (mock `hybrid.retrieve_l3` and `get_reranker`, same shape as the pre-existing behavior).

### Implementation for User Story 2

- [X] T012 [US2] In `src/whattowear/retrieval/hybrid.py`, replace `retrieve_l3()`'s body: drop the
      `kb: KnowledgeBase` parameter (no longer needed — nothing in the live path touches the
      vectorstore), call `external.trends.search_trends(l3_query, max_results=k)` inside a
      `try/except Exception` (log via `logging_utils.get_logger`, return `[]` on failure — research.md
      D5), and map each result into a `Document` per research.md D4's shape (`rule_id` =
      `f"L3-live-{hashlib.sha1(result.get('url','').encode()).hexdigest()[:10]}"`).
- [X] T013 [US2] Update `retrieve_l3`'s two call sites: `src/whattowear/retrieval/hybrid.py`'s
      `retrieve()` (drop the `kb` argument from the call) and `src/whattowear/retrieval/advanced.py`'s
      `retrieve()` (same — `hybrid.retrieve_l3(l3_query, k=first_stage_k)`, rerank stage unchanged).
- [X] T014 [US2] Confirm `src/whattowear/retrieval/baseline.py` is untouched (no edits) and
      `data/kb/manifest.yaml`'s `l3_trend_cards.jsonl` entry keeps `ingest: true` unchanged — baseline's
      whole-collection corpus must stay exactly as it is today (research.md D6, out-of-scope
      constraint).
- [X] T015 [US2] In `data/golden_set.yaml`, remove the single static L3 id
      (`L3-2025-metallic-evening`, `L3-2025-tailored-trousers`, `L3-2025-quiet-luxury` respectively)
      from the `relevant_rule_ids` list of the 3 cases that pin one, keeping each case's L4/L1 ids
      intact (research.md D7) — add a one-line YAML comment on each edited line noting why.
- [X] T016 [US2] Run `uv run pytest tests/unit/retrieval/test_hybrid.py tests/unit/retrieval/test_advanced.py -q`
      — new tests green. **Ran this session: 12 passed, 0 failed.**
- [ ] T017 [US2] Run `uv run pytest tests/integration/test_suggest_refinement.py -q -k Warmer` (or any
      integration test exercising a `season`-bearing request) against the real graph and confirm a live
      Tavily call actually happens (network required) and the response still assembles successfully.
      **Not run this session** — needs a real DB + gateway + Tavily key + KB source files (see
      environment note above).

**Checkpoint**: User Story 2 fully functional and independently testable — L3 is genuinely live for
`hybrid`/`advanced`; `baseline` and the rest of the pipeline are unaffected; failures degrade instead of
crashing.

---

## Phase 4: User Story 3 - "Warmer" reliably works across the whole outfit (Priority: P1)

**Goal**: The "warmer" refinement's warmth floor scales per category to that category's own achievable
warmth ceiling (computed from the closet), replacing the current blanket footwear/accessory exemption,
so low-ceiling categories get a real (if small) push instead of either a full pass or an impossible bar.

**Independent Test**: Unit-test `_item_fits_hard_constraints` directly with items/ceilings crafted per
research.md D8's worked example; run the before/after evidence script against the real graph
(`quickstart.md` §3) and confirm the fallback rate drops.

### Tests for User Story 3

> Existing tests `test_warmer_delta_raises_the_warmth_floor` and
> `test_warmer_delta_does_not_gate_footwear_or_accessories` in
> `tests/unit/pipeline/test_graph.py` assert the old (buggy) blanket-exemption behavior — updating them
> is part of this story's implementation, not separate follow-up (they'd otherwise fail against the
> fix by design).

- [X] T018 [P] [US3] Unit test in `tests/unit/pipeline/test_graph.py`: `_category_warmth_ceiling()`
      computes the correct per-group max from a mixed `ctx.wardrobe` list, and returns an empty dict for
      an empty wardrobe.
- [X] T019 [P] [US3] Unit test in `tests/unit/pipeline/test_graph.py`: with an explicit
      `category_ceilings` of `{"footwear": 3}` and `warmer_count=1`, an item with `warmth=1` in
      `"sneakers"` passes and `warmth=0` fails (research.md D8's worked example, floor=1); with
      `warmer_count=3`, an item with `warmth=3` passes and nothing higher is ever required (floor
      capped at ceiling=3) — FR-011.
- [X] T020 [P] [US3] Unit test in `tests/unit/pipeline/test_graph.py`: with `category_ceilings` of
      `{"accessory": 0}` and any `warmer_count`, every accessory item passes regardless of its own
      warmth (a zero-ceiling category never gates) — the corrected replacement for
      `test_warmer_delta_does_not_gate_footwear_or_accessories`, now derived from the closet's actual
      data rather than a hardcoded group exemption.
- [X] T021 [US3] Update `tests/integration/test_suggest_refinement.py`: remove the
      `_WARMTH_FLOOR_EXEMPT_GROUPS` import and its use in `_mean_warmth()` (that constant no longer
      exists post-fix); `_mean_warmth()` should include all groups now that the floor is relative
      rather than an on/off exemption.

### Implementation for User Story 3

- [X] T022 [US3] Capture **before** evidence: create `scripts/warmth_floor_evidence.py` per
      research.md D9 (loads the eval baseline user's closet, drives all 9 `OCCASION_FORMALITY` cases
      through the real compiled graph with a `"warmer"` follow-up turn each, records the FR-015
      fallback rate, writes JSON + prints a `strategy | fallback_rate` table). **Script written and
      verified structurally correct** (imports resolve, fails only at the live DB-connection step
      against a placeholder `DATABASE_URL` — confirmed environment-only, not a code bug). **Running it
      against real pre-fix code for an actual "before" number was NOT possible this session** — the
      fix (T023-T025) was implemented in the same session the script had to be written in, and neither
      before nor after numbers could be captured live regardless, per the environment note above. This
      is a real, unresolved gap: the "one and only chance to get a real baseline number" (research.md
      D9) was missed here — the next session with real credentials should run the script against a
      revert of T023-T025 first if a true "before" number is still wanted, or accept an "after-only"
      capture and reason about the improvement from the unit tests' worked examples (T019/T020) instead.
- [X] T023 [US3] In `src/whattowear/pipeline/graph.py`, add `_WARMTH_SCALE_REFERENCE = 5` and
      `_category_warmth_ceiling(wardrobe: list[WardrobeItem]) -> dict[str, int]` per research.md D8.
- [X] T024 [US3] In `src/whattowear/pipeline/graph.py`, remove `_WARMTH_FLOOR_EXEMPT_GROUPS` and
      replace `_item_fits_hard_constraints`'s warmer-floor branch with the relative-ceiling formula
      (research.md D8), adding an optional `category_ceilings: Optional[dict[str, int]] = None`
      parameter that falls back to `_category_warmth_ceiling(ctx.wardrobe)` when not supplied.
- [X] T025 [US3] In `src/whattowear/pipeline/graph.py`'s `wardrobe_retrieval()`, precompute
      `category_ceilings = _category_warmth_ceiling(ctx.wardrobe)` once and pass it into every
      `_item_fits_hard_constraints(...)` call in its loop.
- [X] T026 [US3] Run `uv run pytest tests/unit/pipeline/test_graph.py -q` — all warmer-delta tests
      (T018-T020, plus the pre-existing formality/season/ceiling tests, unaffected) green. **Ran this
      session: 26 passed, 0 failed.**
- [ ] T027 [US3] Capture **after** evidence: `uv run python scripts/warmth_floor_evidence.py --out
      artifacts/warmth_floor_after.json`. **Not run this session** — see T022; blocked on the same
      missing DB/gateway/KB-source-file environment.
- [ ] T028 [US3] Write the before/after `strategy | fallback_rate` comparison (T022 vs. T027) into
      the feature's completion notes (SC-005) — confirm the after rate is lower. **Not possible this
      session** — no before or after numbers were captured (see T022).
- [ ] T029 [US3] Run `uv run pytest tests/integration/test_suggest_refinement.py -q` (real graph,
      network required) — confirm `TestWarmerRefinement` still passes or cleanly skips per its existing
      FR-015 fallback allowance. **Not run this session** — see environment note above.

**Checkpoint**: User Story 3 fully functional and independently testable — the fix is isolated to
`pipeline/graph.py` and its tests; no dependency on US1/US2.

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Full no-regression gate across all three stories together, and handoff documentation.

- [X] T030 Run `uv run ruff check . && uv run ruff format --check .` across all changed files. **Ran
      this session: ruff check clean on every file this feature touches (2 pre-existing, unrelated
      findings in notebooks/ and external/trends.py, not touched by this feature, left as-is); ruff
      format applied to 4 files that needed it.**
- [X] T031 Run the full backend test suite: `uv run pytest tests/ -q`. **Ran this session (as `tests/
      unit` — `tests/integration` needs the DB/gateway this sandbox doesn't have, so it wasn't
      collected): 193 passed. The only errors (33, all in the pre-existing, untouched `test_crud.py`/
      `test_seed.py`) are a live-DB connection failure against the placeholder `DATABASE_URL` — an
      environment gap, not a regression from this feature (those files aren't touched by it).**
- [ ] T032 Run the full eval no-regression gate: `uv run python -m whattowear.eval.harness` across all
      three strategies; diff against `artifacts/eval_runs/` — confirm `baseline` is byte-identical
      (SC-006), and that `hybrid`/`advanced` deltas are limited to the 3 golden cases edited in T015 plus
      any genuine L1-recall improvement (research.md D7). **Not run this session** — needs the full
      live stack (see environment note above). This is the most important remaining gap before merge:
      the constitution's no-regression gate is mandatory for any change touching retrieval, and this
      feature touches retrieval significantly.
- [ ] T033 [P] Manually verify a real `/suggest` call's LangSmith trace shows the live Tavily call as
      its own step under `node.style_retrieval`, per `quickstart.md` §2's verification checklist item.
      **Not run this session** — needs a live backend + LangSmith key.
- [ ] T034 [P] Verify `cite.owned_only`/`cite.all_cites_grounded` pass on a request that exercises both
      a new L1 semantic chunk citation and a live Tavily citation in the same run (a season-bearing
      request against a closet/occasion likely to trigger both — e.g. `occasion="wedding",
      season="autumn"`). **Not run this session** — needs the full live stack. The grounding *logic*
      itself is unchanged by this feature (`cite.py` reads the same four metadata keys off any
      `Document` regardless of source) and both new `Document` shapes (T006, T012) carry all four keys
      by construction — but this is reasoning from code, not a live-verified confirmation.
- [X] T035 Update `docs/SDD-HANDOFF.md` (feature table row + a new "Step 7" narrative) and
      `CLAUDE.md`'s "Current state" section per the project's session-workflow handoff contract; mark
      completed tasks in this file `[X]` (this file — 26/35 checked; 9 remain open, each with an
      inline note on why and what the next session needs).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **User Story 1, 2, 3 (Phases 2-4)**: Each depends only on Setup — they touch disjoint functions
  (`retrieve_l1` vs. `retrieve_l3` vs. `_item_fits_hard_constraints`/`wardrobe_retrieval`) in different
  files (`hybrid.py`'s two functions don't call each other; `graph.py`'s warmth-floor code is untouched
  by either retrieval story) and can be implemented, tested, and committed in **any order or in
  parallel**.
- **Polish (Phase 5)**: Depends on all three user stories being complete (the full eval gate needs all
  changes present to give one meaningful comparison run).

### User Story Dependencies

- **User Story 1 (P1)**: Independent. No dependency on US2/US3.
- **User Story 2 (P2)**: Independent. No dependency on US1/US3.
- **User Story 3 (P1)**: Independent. No dependency on US1/US2. (Note: US3's "before" evidence, T022,
  must run before US3's own implementation tasks T023-T025 — that ordering constraint is *within* US3,
  not across stories. This session's environment gap meant neither before nor after could actually run —
  see T022's note.)

### Within Each User Story

- Tests before implementation is the general order shown, but since this is bugfix/enhancement work on
  existing functions (not new modules), test and implementation tasks for the same function are meant
  to be iterated together in practice — the ordering documents intent (tests exist and are checked),
  not a hard TDD gate.

### Parallel Opportunities

- T002/T003 (US1 tests), T009/T010/T011 (US2 tests), and T018/T019/T020 (US3 tests) are each
  parallelizable within their story (different test functions, same or adjacent new files).
- All three user story phases (2, 3, 4) can be worked in parallel by construction — they share no file.
- T033/T034 in Polish are parallelizable (independent manual verifications).

---

## Implementation Strategy

### MVP First (User Story 1 Only)

US1 alone (Phase 1 + Phase 2) is a complete, shippable increment: `retrieve_l1()` returns a richer,
still-grounded pool, verifiable independently of US2/US3, per `quickstart.md` §1.

### Incremental Delivery

1. Setup (T001) → ready.
2. US1 (T002-T008) → verify independently → could ship alone.
3. US2 (T009-T017) → verify independently → could ship alone.
4. US3 (T018-T029) → verify independently → could ship alone.
5. Polish (T030-T035) → full gate + handoff, once all three are in.

Given all three stories are independent and this is a solo-developer feature (not a staffed team), the
practical order used in this session is US1 → US2 → US3 → Polish (spec priority order, P1/P2/P1), not
parallel execution — but nothing about the tasks below assumes that order.

## Notes

- No `contracts/` directory exists for this feature (plan.md: no external interface changes) — no
  contract tests.
- No new persisted entities (data-model.md) — no migration tasks.
- `[Story]` labels map to spec.md's User Story 1/2/3, which map 1:1 to the handoff's Task A/B/C.
- **Status as of this session**: 26/35 tasks complete. All code changes (Tasks A/B/C from the original
  handoff) are implemented and covered by passing unit tests (38 new/updated unit tests across
  `test_hybrid.py`, `test_advanced.py`, `test_graph.py`, plus the full pre-existing `tests/unit` suite
  at 193/193 passing). The 9 open tasks all require a live gateway/DB/Qdrant/Tavily/LangSmith stack and
  the gitignored `backend/data/` source files, neither of which this sandbox session had — see the
  environment note near the top of this file. **T032 (the full eval no-regression gate) is the single
  most important one to run before merging**, per the constitution's mandatory no-regression gate for
  any retrieval-touching change.
