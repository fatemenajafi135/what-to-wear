---

description: "Task list for Feature 005: production-hardening"
---

# Tasks: Production Hardening

**Input**: Design documents from `/specs/005-production-hardening/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/suggest.md, quickstart.md

**Tests**: Included — matches this project's established convention (every
prior feature ships unit tests for deterministic logic per the constitution's
Quality Bar, plus integration tests against real backing services). Both new
modules this feature adds (`pipeline/grounding.py`, `pipeline/cache.py`) are
pure/deterministic-enough logic per that bar.

**Organization**: Grouped by user story (spec.md priorities) so each story is
independently implementable, testable, and deliverable. The four stories are
architecturally independent slices touching disjoint files (plan.md
Summary) — there is no cross-story blocking beyond shared Setup.

## Path Conventions

Existing web app split: `backend/src/whattowear/`, `backend/tests/`. No
frontend code changes this feature (deploy config only). No new top-level
directories (plan.md's Structure Decision).

---

## Phase 1: Setup

- [X] T001 Copy gitignored `backend/data/` and `backend/artifacts/eval_runs/`
  from the main worktree (`/home/fateme/Projects/w2w/what-to-wear/backend/`)
  into this worktree via `rsync -a` — the known "fresh worktree doesn't carry
  gitignored data" gotcha (CLAUDE.md); confirmed missing here already.
  Required before T004 and before the eval harness can run at all.
- [X] T002 Add `litellm`, `langchain-litellm`, `redis` to `backend/pyproject.toml`
  dependencies (research.md §5); run `uv sync --group dev`.
- [X] T003 [P] Add `REDIS_URL` to `backend/.env.example` (Railway Redis addon
  connection string placeholder, plus a comment showing the local dev
  fallback `redis://localhost:6379/0` and `docker run -d -p 6379:6379
  redis:7-alpine`).
- [X] T004 Establish the pre-change baseline: run `uv run pytest tests/ -q`
  and `uv run python -m whattowear.eval.harness`, confirm both green and note
  the `retrieval_recall` figures against `backend/artifacts/eval_runs/` —
  this is what T024's post-change gate re-run diffs against (constitution
  Principle I). **249/249 tests pass.**

---

## Phase 2: Foundational (Blocking Prerequisites)

**None beyond Setup.** The four user stories touch disjoint files
(`config.py` for US4; `pipeline/grounding.py` + `pipeline/graph.py` for US2;
`pipeline/cache.py` + `api.py` for US3; deploy configuration only for US1) —
introducing a shared abstraction layer across them would violate the
constitution's simplicity clause without a concrete need. Proceed directly
to user story phases once Setup is complete.

---

## Phase 3: User Story 1 - Reach the app from anywhere (Priority: P1) 🎯 MVP

**Goal**: The app is actually publicly reachable — live backend URL, live
frontend URL, durable per-user photo storage — closing the three steps
Feature 003 left undone.

**Independent Test**: From a machine that has never run any part of this
project locally, visit the public frontend URL, sign up, sign in, add one
item by photo, and receive a suggestion — no terminal, no local backend.

### Implementation for User Story 1

- [ ] T005 [US1] **Manual, owner-only**: confirm with the project owner
  whether the Supabase Storage `wardrobe-photos` bucket + per-user RLS
  policy already exists (Feature 003, never confirmed done); if not, create
  it per `specs/003-mvp-app/quickstart.md`'s Prerequisites — no repo file,
  tracked here so it isn't silently skipped.
- [ ] T006 [P] [US1] **Manual, owner-only**: confirm with the project owner
  whether a Railway project for the backend already exists; if not,
  configure one — start command `uv run uvicorn whattowear.api:app --host
  0.0.0.0 --port $PORT`, env vars from `backend/.env` including the new
  `REDIS_URL` (from Railway's own Redis addon — add the addon if it doesn't
  exist yet) and `WTW_CORS_ORIGINS` set to the Vercel origin from T007.
- [ ] T007 [P] [US1] **Manual, owner-only**: confirm with the project owner
  whether a Vercel project for the frontend already exists; if not,
  configure one — env vars `NEXT_PUBLIC_SUPABASE_URL`,
  `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `NEXT_PUBLIC_API_BASE_URL` (pointed at the
  Railway URL from T006).
- [ ] T008 [US1] Run `quickstart.md`'s "Validation: US1" end-to-end from a
  browser that has never touched local dev, against the live URLs (depends
  on T005, T006, T007).
- [ ] T008a [P] [US1] Enhance `GET /health` in
  `backend/src/whattowear/api.py` (FR-012, research.md §3a) to check
  Postgres reachability (reuse `memory.store._reachable`'s short-timeout
  connect pattern) and Qdrant reachability (`kb.get_kb()`'s client), 
  returning `503` naming which dependency failed if either is unreachable,
  `200 {"status": "ok"}` otherwise.

**Checkpoint**: App is publicly reachable and passes its own quickstart
validation end-to-end.

---

## Phase 4: User Story 2 - Never see a fabricated outfit (Priority: P2)

**Goal**: An explicit, deterministic post-generation check drops any outfit
referencing an item id that doesn't genuinely exist in the requester's
wardrobe, as a safety net on top of the existing selection guarantee.

**Independent Test**: Deliberately make one outfit's item list reference a
nonexistent item id before it reaches the user; confirm the system withholds
that specific outfit while still showing any other valid ones, and confirm
the existing "couldn't put together a suggestion" fallback fires if every
outfit fails.

### Tests for User Story 2

- [X] T009 [P] [US2] Unit tests for `verify_outfit_grounding()` — all-owned
  outfit passes, one unknown id fails, empty item list, an item id that's
  catalog-only (not in the wardrobe) still passes — in
  `backend/tests/unit/pipeline/test_grounding.py`.

### Implementation for User Story 2

- [X] T010 [US2] Implement `verify_outfit_grounding(item_ids, wardrobe_by_id,
  catalog_ids) -> bool` in new `backend/src/whattowear/pipeline/grounding.py`
  per research.md §3 — every item id must be in the wardrobe or the shared
  catalog (Principle IV, checked literally; no outfit can contain a
  catalog-only item today, but the check costs one cheap query and removes
  any ambiguity about matching the constitution's stated grounding
  definition).
- [X] T011 [US2] Add a `verify_grounding` node to
  `backend/src/whattowear/pipeline/graph.py`: fetches catalog ids via
  `crud.list_catalog_items` (own short-lived `SessionLocal()` session, same
  pattern as `memory.store.get_profile`), filters `scored_outfits` via
  T010's predicate, wired between `score_and_rank` and `explain` in
  `build_graph()`'s edges (depends on T010).
- [X] T012 [US2] Integration test: monkeypatch/construct a `GraphState` so
  one candidate outfit contains an id absent from `ctx.wardrobe`, invoke the
  compiled graph, confirm that outfit is absent from `result.outfits` while
  any other valid outfits remain, and confirm the existing zero-outfit
  `note` fires when every outfit is bad — in
  `backend/tests/integration/test_grounding_graph.py` (depends on T011).
- [X] T013 [US2] Re-run `uv run python -m whattowear.eval.harness` against
  the golden set and confirm no legitimate outfit is ever dropped
  (`retrieval_recall` unchanged from T004's baseline) — proves the new node
  only removes genuinely-bad outfits, never good ones (depends on T011).
  **Verified**: per-case `retrieval_recall` byte-identical to the archived
  baseline for every shared golden-set case, all 3 strategies (one extra
  case in the current golden set vs. the archived comparison file explains
  the mean-level difference, not a per-case regression); `owned_only` stays
  1.0 in both. One unrelated single-case `owned_only` flip on `hybrid`
  (False->True) is on `final_state["generated"]`, a field `verify_grounding`
  doesn't even touch — LLM-sampling variance, the documented flakiness
  pattern, not caused by this feature.

**Checkpoint**: The grounding guardrail is live for both the `/suggest`
endpoint and `eval/harness.py`'s direct graph invocation (same compiled
graph, no forked path).

---

## Phase 5: User Story 3 - Repeated requests come back faster and cheaper (Priority: P3)

**Goal**: An equivalent repeated styling request, for the same user with an
unchanged closet, is served from a per-user Redis cache — no retrieval, no
generation, no new AI-provider call — in well under a second.

**Independent Test**: Issue the same styling request twice in a row; confirm
the second response returns in well under a second with no new
LangSmith-traced provider call. Edit the closet and repeat; confirm the
system reprocesses fully rather than serving the now-stale cached result.

### Tests for User Story 3

- [X] T014 [P] [US3] Unit tests for the cache-key derivation function —
  normalization collapses equivalent occasion/mood casing and whitespace,
  two different users never produce the same key even with identical other
  inputs, and the wardrobe fingerprint changes when an item is added,
  edited, or removed — in `backend/tests/unit/pipeline/test_cache.py`.
  **Caught a real bug**: `OCCASION_FORMALITY.get(occasion, ...)` used the
  raw (non-normalized) occasion, so differently-cased occasions resolved to
  different default formalities — fixed to use `occasion_norm`.

### Implementation for User Story 3

- [X] T015 [US3] Implement `backend/src/whattowear/pipeline/cache.py` per
  data-model.md: a pure `compute_cache_key(user_id, ctx_fields, wardrobe) ->
  str` (sha256 over user id + normalized occasion/mood/formality/temp_band/
  season + a **full-content** wardrobe fingerprint — see research.md §2's
  implementation-time correction, not `(id, updated_at)` pairs as
  originally planned), plus `get_cached_result(key) -> (SuggestResult,
  note) | None` and `set_cached_result(key, result, note, ttl_seconds=3600)
  -> None` using `redis.Redis.from_url(os.environ["REDIS_URL"])` directly
  (no abstraction layer — one concrete backend). Both get/set catch
  connection errors and degrade to a no-op miss (spec Edge Cases: cache
  store unavailable -> process fresh, never fail the request).
- [X] T016 [US3] Wire the cache into `suggest_endpoint` in
  `backend/src/whattowear/api.py`: load the wardrobe once via
  `context_assembler.load_wardrobe`, compute the cache key (skip the cache
  entirely when `req.thread_id` continues an existing conversation — a
  refinement turn always runs the graph, per research.md §2), check
  `get_cached_result` before `graph.invoke`; on hit, build the SSE response
  directly from the cached `SuggestResult` (no graph invocation); on miss,
  pass the already-loaded wardrobe into `graph.invoke(..., wardrobe=...)`
  (using `GraphState.wardrobe`'s existing DB-load-bypass override, so the
  wardrobe isn't fetched twice) and `set_cached_result` the fresh result
  after a successful run (depends on T015). **Real bug found and fixed**:
  a cache hit's `thread_id` was never passed to `graph.invoke`, so the
  checkpointer had no state for it — a refinement continuing that
  `thread_id` was silently treated as a brand-new conversation (reproduced
  via a seeded cache entry + `test_suggest_refinement.py`'s existing
  alternatives test). Fixed by seeding the checkpointer on every cache hit
  via `graph.update_state(config, {...})` (research.md §2).
- [X] T017 [P] [US3] Integration test against a real (test) Redis instance:
  first request misses and populates the cache, an immediate repeat hits and
  matches the first response's `result` exactly, then editing the test
  user's wardrobe (add/patch/delete one item) causes the next identical
  request to miss again — in `backend/tests/integration/test_suggest_cache.py`
  (depends on T016). Also added: a refinement `thread_id` is never served
  from cache. Needed an autouse Redis-flush fixture for test isolation
  (all cases share one occasion/user) and a spy on `graph.invoke` itself,
  not `get_compiled_graph()` (which a hit legitimately still calls once,
  for the `update_state` seeding above) — both found via a first failing
  run, not assumed upfront.
- [X] T018 [US3] Integration test: point `REDIS_URL` at an unreachable host
  and confirm `/suggest` still returns a normal successful result (processed
  fresh, not an error) — in `backend/tests/integration/test_suggest_cache.py`
  alongside T017 (depends on T015, T016).

**Checkpoint**: A repeated request is measurably faster with zero new
provider usage; a closet edit correctly busts the cache; a down cache store
degrades gracefully.

---

## Phase 6: User Story 4 - One place to see and control AI spend and failures (Priority: P4)

**Goal**: Every AI-provider call goes through one routing layer (LiteLLM),
giving automatic retry on transient failures and LangSmith-visible
cost/usage, with zero change to any existing call site's code.

**Independent Test**: Simulate a transient provider failure and confirm the
request still succeeds via automatic retry with no visible error to the
caller; confirm the LangSmith project shows cost/usage on traced calls
afterward.

### Implementation for User Story 4

- [X] T019 [US4] Swap the internals of `get_chat_model()` and
  `get_judge_model()` in `backend/src/whattowear/config.py` to construct
  `langchain_litellm.ChatLiteLLM` (`max_retries=3`, litellm's own
  transient-failure retry) pointed at the existing `GATEWAY_BASE_URL`/gateway
  key; `get_embeddings()` is left on `langchain_openai.OpenAIEmbeddings`,
  unchanged (research.md §1 — no reported problem to fix there, and forcing
  it through litellm too would be scope creep).
- [X] T020 [US4] Smoke-test all four call sites against the real gateway.
  `pipeline/generator.py`, `eval/judge.py`, `external/trends.py` needed
  **zero changes** — confirmed by direct real calls. `vision.py`'s
  `ExtractedAttributes` (all-`Optional` fields) hit a real gateway
  incompatibility (not the originally-guessed `json_mode` fallback — that
  and `json_schema, strict=False` were both tried and rejected by the
  gateway too). Fixed with a hand-written nullable-required JSON schema —
  see research.md §1's "what actually happened" for the full story
  (depends on T019).
- [X] T021 [P] [US4] Integration test: patch `litellm.completion` (the
  actual transport `ChatLiteLLM.client` calls) to raise one transient
  `APIConnectionError` then fall through to the real call; confirm the
  chat model's `.invoke()` still returns a normal result — in
  `backend/tests/integration/test_llm_retry.py` (depends on T019).
- [ ] T022 [US4] **Manual, owner-only**: after a handful of real `/suggest`
  calls (already happened via this session's own testing), check the
  LangSmith project dashboard shows cost/usage populated on the traced LLM
  calls — confirms FR-010/SC-005 per this session's clarification (existing
  tracing suffices, no new dashboard built). This session has no LangSmith
  dashboard access to confirm visually; the traced calls themselves were
  confirmed happening (LangSmith tracing is already mandatory,
  `config._require_langsmith()` fails fast without it, and every real call
  in this session's testing succeeded under that requirement) (depends on
  T019).

**Checkpoint**: Every chat-completion call in the codebase goes through
LiteLLM; a transient failure is invisible to callers; cost/usage is visible
in the existing LangSmith project.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T023 [P] Update `backend/README.md`'s "single gateway layer" /
  `config.py` description to mention the LiteLLM swap and the new Redis
  cache briefly, matching how prior features kept this doc in sync.
- [ ] T024 Full gate re-run before merge: `uv run ruff check . && uv run
  ruff format .`, `uv run pytest tests/ -q`, `uv run python -m
  whattowear.eval.harness` — confirm `retrieval_recall` is byte-identical to
  T004's captured baseline (constitution Principle I no-regression gate;
  depends on all of Phases 4-6 being complete).
- [ ] T025 Run every scenario in `quickstart.md` end-to-end (US1-US4) as
  final sign-off (depends on T008, T008a, T013, T017, T018, T021, T022, T024).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: None beyond Setup (see note above) — user
  story phases can start as soon as Setup completes.
- **User Stories (Phase 3-6)**: Each depends only on Setup, not on each
  other. They may proceed in parallel or in priority order (P1 → P2 → P3 →
  P4); priority order is recommended since US1 unblocks demoing everything
  else, but nothing technically requires it.
- **Polish (Phase 7)**: Depends on whichever of Phases 3-6 are in scope for
  this delivery being complete (T024/T025 specifically need Phases 4-6 done
  to have something meaningful to gate/validate).

### User Story Dependencies

- **User Story 1 (P1)**: Independent — deploy configuration only, no code
  dependency on US2/US3/US4.
- **User Story 2 (P2)**: Independent — touches `pipeline/graph.py` +new
  `pipeline/grounding.py` only.
- **User Story 3 (P3)**: Independent implementation-wise, but its cached
  `SuggestResult` naturally reflects whatever US2's grounding node has
  already filtered by the time `api.py` sees `final_state["result"]` — no
  explicit coordination task needed, just note the two compose correctly by
  construction if both are built.
- **User Story 4 (P4)**: Independent — touches `config.py` only.

### Within Each User Story

- Tests before the implementation they cover, where both exist.
- A story's own checkpoint (re-running the eval harness, or the
  quickstart.md scenario) closes out that phase.

### Parallel Opportunities

- T003 (Setup) can run alongside T001/T002.
- T006 and T007 (US1, different dashboards) run in parallel; both depend on
  T005 only insofar as bucket existence is checked first for clarity, not a
  hard technical dependency.
- T009 (US2 unit test) can be written in parallel with T014 (US3 unit test)
  — different files, different stories.
- T021 (US4 integration test) can run in parallel with T017/T018 (US3
  integration tests) — different files.
- T023 (Polish, README) can run any time after T019.

---

## Parallel Example: User Story 2 and User Story 3 together

```bash
# Different developers/sessions could take these in parallel — disjoint files:
Task: "Unit tests for verify_outfit_grounding() in backend/tests/unit/pipeline/test_grounding.py"
Task: "Unit tests for cache-key derivation in backend/tests/unit/pipeline/test_cache.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup.
2. Complete Phase 3: User Story 1 (deploy) — this is the one story every
   other story's real-world demonstration depends on, per spec.md's own
   "Why this priority" for US1.
3. **STOP and VALIDATE**: quickstart.md's US1 scenario against the live URLs.

### Incremental Delivery

1. Setup → Foundational (none) → ready.
2. US1 (deploy) → validate → the app is now demoable publicly.
3. US2 (grounding guardrail) → validate → trust/safety property added, no
   user-visible change on the happy path.
4. US3 (cache) → validate → repeated requests get faster/cheaper.
5. US4 (LiteLLM routing) → validate → operational visibility + resilience.
6. Polish → final gate re-run + full quickstart.md sign-off.

### Notes

- [P] tasks = different files, no dependencies.
- [Story] label maps each task to its user story for traceability.
- Manual/owner-only tasks (T005-T007) have no repo file to check off against
  — they're tracked here specifically so they aren't silently skipped, per
  Feature 003's own precedent for the same three steps.
- Commit after each task or logical group; re-run the eval no-regression
  gate (T024) before considering Phases 4/6 done, since both touch the LLM
  call path or the generation-adjacent pipeline (constitution Principle I).
