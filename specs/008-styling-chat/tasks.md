# Tasks: Styling chat

**Input**: Design documents from `/specs/008-styling-chat/` (plan.md, research.md, data-model.md,
contracts/recommend.md, quickstart.md)

**Tests**: included. The constitution's Quality Bar requires unit tests for deterministic logic
and a golden-set/mocked-gateway entry for every LLM-dependent path, and the handoff's Definition
of Done requires backend/frontend test counts to not drop (617 / 182 today) — this is not an
optional TDD preference for this project.

**Organization**: grouped by user story from spec.md, in priority order (P1, P2, P2, P3, P3).

## Phase 1: Setup

- [ ] T001 Add `wtw_wardrobe_min_items` (5), `wtw_wardrobe_sparse_threshold` (15),
      `wtw_styling_request_timeout_seconds` (120) to `Settings` in
      `backend/src/whattowear/core/config.py` (data-model.md "Backend — config additions").
- [ ] T002 [P] Add `newChat` keyword (Lucide `SquarePen`, default label "New chat") to
      `IconKeyword`/`ICONS`/`DEFAULT_LABELS` in
      `frontend/components/ui/IconButton/IconButton.tsx`.

## Phase 2: Foundational (blocks all user stories)

- [ ] T003 Create `backend/src/whattowear/readiness.py`: pure function
      `evaluate_wardrobe_readiness(items: list[WardrobeItem], min_items: int, sparse_threshold: int) -> ReadinessResult`
      implementing the slot-coverage algorithm in data-model.md ("Readiness algorithm"), using
      `categories.group_of`. `ReadinessResult` is a small dataclass/model: `ready: bool`,
      `sparse: bool`, `missing: list[str]`.
- [ ] T004 [P] `backend/tests/unit/test_readiness.py`: boundary cases — 0 items; exactly
      `min_items` with full coverage; `min_items` with missing footwear only; missing top+shoes
      (skeleton A) vs. missing full_body+shoes (skeleton B) with tie-break to A; coverage
      satisfied but count `< min_items` (empty `missing`); count `≥ sparse_threshold` (`sparse`
      false); count between the two thresholds (`sparse` true).
- [ ] T005 Create `backend/src/whattowear/api/v1/routes/recommend.py`: `router = APIRouter()`,
      `_get_repository()` returning `SupabaseClosetRepository()` (mirrors `closet.py`), imports for
      `get_current_user_id`/`get_current_access_token`. Register in
      `backend/src/whattowear/main.py` via `app.include_router(recommend_router, prefix="/api/v1")`
      alongside the other three routers.
- [ ] T006 Implement `GET /recommend/readiness` in `recommend.py`: calls
      `repository.list_wardrobe_items(user_id)`, runs `readiness.evaluate_wardrobe_readiness`
      with settings from `get_settings()`, returns `ReadinessResponse` (data-model.md). No
      pipeline/LLM call.
- [ ] T007 [P] `backend/tests/integration/test_recommend_routes.py::test_readiness_*`: ready
      closet → `{ready: true, sparse: false}`; sparse closet → `{ready: true, sparse: true}`;
      under-floor closet → `{ready: false, missing: [...]}`; unauthenticated → 401 (same pattern
      as `tests/integration/test_closet_routes.py`'s `_client_as` helper).
- [ ] T008 Warm the checkpointer at startup: in `backend/src/whattowear/main.py`'s `lifespan`,
      after `get_engine()`, call `pipeline.graph.get_compiled_graph(SupabaseClosetRepository())`
      once (design-decisions.md §27). Guard with a `try`/`log.exception` so a Qdrant/DB hiccup at
      boot degrades to lazy (first-request) setup rather than crashing app startup — the app's own
      `/health` endpoint already reports DB reachability separately.
- [ ] T009 [P] `frontend/lib/recommend/timeOfDayGreeting.ts`: pure function
      `greetingFor(hour: number): "Good morning" | "Good afternoon" | "Good evening"` per
      design-system.md §9 boundaries (00–11:59 / 12–17:59 / 18–23:59), plus
      `timeOfDayGreeting.test.ts` covering all three boundaries and the two edge minutes (11:59,
      12:00, 17:59, 18:00, 23:59, 00:00).
- [ ] T010 [P] `frontend/components/recommend/useGreeting.ts`: client hook returning
      `` `${greetingFor(new Date().getHours())}, ${name}` `` — reads the signed-in user's display
      name from wherever it's already available in the app shell (check `frontend/lib/auth` /
      existing profile hook before adding a new fetch).

**Checkpoint**: readiness endpoint, checkpointer warm-up, and greeting logic all exist and are
tested. No user-facing chat surface yet — every story phase below builds on this.

## Phase 3: User Story 1 — Ask for an outfit and get a grounded, cited suggestion (P1) 🎯 MVP

**Goal**: hero state → type/compose messages → tap "Start styling" → get one cited outfit built
from the user's own closet, with tappable thumbnails.

**Independent test**: with a ready closet and a populated KB, compose "business casual for a
rainy commute," tap Start styling, confirm the reply contains only owned items, ≥1 real citation,
and every citation traces to something actually retrieved.

### Backend

- [ ] T011 [US1] Add `SendMessageRequest`, `SendMessageResponse`, `StylingOutfit`,
      `StylingReplyItem` (reuse `ClosetItemView` directly, don't redefine it — import from
      `closet.py` or hoist `ClosetItemView` to `schema.py` if importing across route modules is
      awkward; decide at implementation time and note the choice in a code comment), `CitedRule`
      route-local models in `recommend.py` per data-model.md.
- [ ] T012 [US1] Implement `match_label(rank_score: float) -> Literal["great","good","might_work"] | None`
      as a small pure function (co-located in `recommend.py` or `readiness.py`'s sibling) applying
      design-system.md § Scores thresholds (≥0.8 / 0.6–0.79 / 0.4–0.59 / `None` below 0.4 — not
      surfaced).
- [ ] T013 [P] [US1] `backend/tests/unit/test_recommend_match_label.py`: all four threshold bands
      including the exact boundary values (0.8, 0.6, 0.4).
- [ ] T014 [US1] Implement `POST /recommend/messages` in `recommend.py`:
      1. Re-run the readiness check (T003/T006's function) — `403` with
         `{"detail": "Your closet isn't ready for a styling request yet."}` if not ready, pipeline
         never invoked (FR-007, contracts/recommend.md).
      2. Build `SuggestRequest(occasion=body.message, thread_id=body.thread_id)`.
      3. Every existing route in this codebase is a sync `def`, not `async def`
         (confirmed: `closet.py`, `calendar.py`) — FastAPI already runs these off the event loop,
         so there is no event loop to `await` against and `asyncio.wait_for` does not apply. Use
         `concurrent.futures.ThreadPoolExecutor(max_workers=1).submit(compiled_graph.invoke, input,
         config={"configurable": {"thread_id": ...}}).result(timeout=get_settings().
         wtw_styling_request_timeout_seconds)`, catching `concurrent.futures.TimeoutError` → `504`
         `{"detail": "That took too long. Try again."}`. (The invocation isn't truly cancelled on
         timeout — the submitted thread keeps running to completion in the background; this is the
         accepted characteristic of this timeout pattern in Python and is fine for a backstop that
         exists to bound the *response*, not to reclaim compute.)
      4. From `result.outfits`, take `[0]` if non-empty; resolve its item ids via
         `repository.list_wardrobe_items(user_id)` (already fetched for the readiness check —
         reuse, don't re-fetch) + `storage.create_signed_urls` (research.md §1).
      5. Build `citations` from the rendered outfit's `rationale[].cites`, resolved against
         `result.sources`, numbered 1..N in first-appearance order, de-duplicated.
      6. `reply_text` = pipeline's `note` when `result.outfits` is empty (research.md §6);
         otherwise `None`.
      7. Return `SendMessageResponse(thread_id=..., reply_text=..., outfit=..., citations=...)`.
- [ ] T015 [US1] `backend/tests/integration/test_recommend_routes.py::test_send_message_*`:
      happy-path outfit (assert only the caller's own item ids appear, assert `match_label` never
      `None`-but-shown-as-number, assert no float/percentage anywhere in the JSON), zero-outfit →
      `reply_text` set / `outfit` null, blocked-by-readiness → `403` with pipeline never invoked
      (assert via a mock/spy that `get_compiled_graph`/`invoke` was not called), backstop timeout
      → `504`. LLM gateway mocked per `tests/unit/pipeline/test_engine.py:162-171`'s
      `patch.object(engine, "get_chat_model", ...)` pattern — locate the actual generation-node
      module to patch (likely `pipeline.generator` or similar; confirm exact import site before
      writing the patch target).

### Frontend

- [ ] T016 [US1] Run `npm run generate:api-types` against the running backend (after T005–T014
      land) to regenerate `frontend/lib/api/schema.d.ts` — commit the regenerated file (it's
      gitignored per design-decisions §20, so this is a local-verification step, not a commit
      step; re-run again after any later contract change in this feature).
- [ ] T017 [P] [US1] `frontend/components/recommend/HeroState.tsx` + `.module.css`: 60×60 brand
      mark, "What to Wear" wordmark (26px/700), `useGreeting()` line, one static welcome bubble
      (surface-sunken, tail `14px 14px 14px 4px`), 3 `Chip`-based suggestion chips ("Rainy day
      commute", "Dinner date outfit", "Business casual") that populate the composer on tap. Copy
      check (FR-018): the welcome bubble's copy must not imply personalization or memory of past
      feedback — preference memory is inert this slice (handoff §2.2).
- [ ] T018 [P] [US1] `frontend/components/recommend/HeroState.test.tsx`: renders greeting from a
      mocked hour, renders all 3 chips, tapping a chip populates the composer (via a passed
      callback prop).
- [ ] T019 [P] [US1] `frontend/components/recommend/Composer.tsx` + `.module.css`: single-line
      `<input>` (not textarea, design-system.md "Chat input behavior"), pill-shaped, 28px circular
      send button; Enter or send-button click appends to the parent's pending-message list and
      clears the input — no network call (research.md §7); disabled (input + button) when
      `!navigator.onLine` (via existing `useOnlineStatus`) or when a Start-styling request is in
      flight (prop-driven).
- [ ] T020 [P] [US1] `frontend/components/recommend/Composer.test.tsx`: Enter submits and clears
      input, empty/whitespace-only input is a no-op, offline disables both controls, `inFlight`
      prop disables both controls.
- [ ] T021 [US1] `frontend/components/recommend/ChatMessageList.tsx` + `.module.css`: renders
      user bubbles (right-aligned, `--color-primary`, tail `14px 14px 4px 14px`) for every message
      in the transcript (pending or already-styled — visually identical, no separate "unsent"
      styling since none is specified), assistant reply bubbles (left-aligned, surface-sunken,
      tail `14px 14px 14px 4px`) with inline text + numbered `Badge tone="citation"` markers
      parsed from `[n]`-style tokens in `rationale_text`, and a "Thinking…" row while a
      Start-styling request is in flight. Copy check (FR-018): no assistant copy anywhere in this
      list may imply personalization or memory of past feedback (preference memory is inert this
      slice).
- [ ] T022 [US1] `frontend/components/recommend/ItemThumbnailRow.tsx` + `.module.css`: wrapped row
      of 56×56 (`radius-sm`, bordered) thumbnails below an assistant reply with a rendered outfit,
      each an `<a href="/closet/{itemId}">` wrapping the `photo_url` image.
- [ ] T023 [US1] `frontend/components/recommend/CitedRuleList.tsx` + `.module.css`: dashed
      top-border list, one row per `CitedRule` — numbered `--color-primary` digit + secondary
      explanation text — rendered below the thumbnail row when `citations.length > 0`.
- [ ] T024 [P] [US1] `frontend/components/recommend/ChatMessageList.test.tsx` +
      `ItemThumbnailRow.test.tsx` + `CitedRuleList.test.tsx`: bubble alignment/tail classes,
      citation badge count matches `citations`, thumbnail links point at `/closet/:itemId`, rule
      list rows match `citations` 1:1, "Thinking…" row visibility tied to an `inFlight` prop.
- [ ] T025 [US1] `frontend/components/recommend/StartStylingButton.tsx` + `.module.css`:
      full-width primary `Button`, caption "Uses everything you have told me so far" beneath;
      visible once the transcript has ≥1 user message; `disabled` when **any** of: no message is
      pending since the last successful Start-styling call (design-decisions §28), a Start-styling
      request is already in flight (`status === "sending"` — FR-012, no second concurrent send;
      analyze pass finding U1), or the client is offline (`!useOnlineStatus()` — Start styling is
      the only control that actually makes a network call under §28's local-only composer, so it
      must carry its own offline gate rather than relying on `Composer`'s; FR-013/SC-007, finding
      U2).
- [ ] T026 [P] [US1] `frontend/components/recommend/StartStylingButton.test.tsx`: hidden with 0
      messages, visible+enabled with 1 pending message, disabled immediately after a successful
      call with nothing new typed since, disabled while `status === "sending"` even with a pending
      message, disabled while offline even with a pending message.
- [ ] T027 [US1] `frontend/components/recommend/RecommendChat.tsx` + `.module.css`: owns
      `messages`, `pendingSinceLastStyle`, `threadId` (`null` initially), `status`
      (`"idle"|"sending"|"error"`); wires `HeroState` (shown when `messages.length === 0`),
      `Composer`, `StartStylingButton`, `ChatMessageList`; on Start-styling tap, joins pending
      message texts (space-joined, per the prototype's own join convention, research.md §7),
      `POST /recommend/messages` with `{ message, thread_id: threadId }`, appends the assistant
      reply to `messages` on success, sets `threadId` from the response, clears the pending batch;
      on failure/timeout shows `recommend.error.body`/`.cta` inline with retry (re-sends the same
      pending batch).
- [ ] T028 [US1] `frontend/components/recommend/RecommendChat.test.tsx`: full happy path with a
      mocked `apiClient.POST` (hero → compose → Start styling → thinking → reply with citations
      and thumbnails); error path shows retry and retry re-issues the same request; zero-outfit
      reply renders `reply_text` with no thumbnails/citations.
- [ ] T029 [US1] Wire `RecommendChat` into `frontend/app/(app)/recommend/page.tsx`, replacing the
      placeholder `.empty`/`.body` markup; drop the now-unused CSS in `page.module.css`; update
      `frontend/app/(app)/recommend/page.test.tsx` accordingly (it may not exist yet — check
      before assuming an edit vs. a new file).

**Checkpoint**: User Story 1 is independently testable end-to-end (quickstart.md "Validate — happy
path").

## Phase 4: User Story 2 — Refine the outfit through the same conversation (P2)

**Goal**: a second Start-styling tap in the same conversation refines rather than restarts.

**Independent test**: send a first message, Start styling, wait for the reply, compose "something
warmer," Start styling again — confirm the second reply reads as a refinement and the request
carried the first response's `thread_id`.

- [ ] T030 [US2] `backend/tests/integration/test_recommend_routes.py::test_refinement_continues_thread`:
      two sequential `POST /recommend/messages` calls, second with the first response's
      `thread_id`; assert the pipeline was invoked with `configurable.thread_id` matching, and
      that the graph's own refinement path was exercised (assert via whatever observable the
      mocked/real graph run exposes — e.g. the checkpointer actually persisting state between the
      two calls against the local Postgres, not a fully mocked graph for this one test).
- [ ] T031 [US2] Confirm/extend `RecommendChat.tsx` (T027) so `threadId` is included on every
      Start-styling call after the first — this should already fall out of T027's design; this
      task is the explicit verification + any fix needed.
- [ ] T032 [P] [US2] `frontend/components/recommend/RecommendChat.test.tsx` addition: second
      Start-styling call's request body includes the `thread_id` returned by the first call's
      response.

**Checkpoint**: US1 + US2 together support a full multi-turn styling conversation.

## Phase 5: User Story 3 — Blocked when the closet isn't ready yet (P2)

**Goal**: an under-stocked closet blocks the composer with an actionable message, enforced
server-side independent of the client gate.

**Independent test**: with a closet that fails the readiness bar, open Styling and confirm the
gate renders instead of the composer; call `POST /recommend/messages` directly, bypassing the UI,
and confirm `403` with the pipeline never invoked.

- [ ] T033 [US3] `frontend/components/recommend/InsufficientClosetGate.tsx` + `.module.css`:
      renders `recommend.insufficient_closet.body` (design-decisions §11's `{missing}`-interpolated
      copy) + "Add items to your closet" CTA linking to `/closet` (or `/add`, matching whatever the
      Closet empty-state CTA already links to — check `frontend/app/(app)/closet/` for the
      precedent before picking).
- [ ] T034 [P] [US3] `frontend/components/recommend/InsufficientClosetGate.test.tsx`: renders the
      count-only fallback phrase when `missing` is empty, renders the joined `missing` list
      otherwise ("a top and a pair of shoes" — Oxford-comma-free two-item join; confirm/implement a
      simple natural-language join helper for 1/2/3+ items).
- [ ] T035 [US3] `frontend/components/recommend/SparseClosetBanner.tsx` + `.module.css`:
      dismissible `Banner variant="info"` with `recommend.sparse_closet.hint` copy; dismissal
      writes a `sessionStorage` key so it does not reappear until the next browser session
      (design-decisions §11).
- [ ] T036 [P] [US3] `frontend/components/recommend/SparseClosetBanner.test.tsx`: renders when
      `sparse` is true, dismiss hides it and sets the sessionStorage flag, does not render again
      within the same mocked session.
- [ ] T037 [US3] Wire `GET /recommend/readiness` into `RecommendChat.tsx` (fetched once on mount):
      render `InsufficientClosetGate` instead of the hero/chat surface when `!ready`; render
      `SparseClosetBanner` above the hero/chat surface when `sparse`; render the normal composer
      otherwise.
- [ ] T038 [US3] Backend: confirm T014's `403` gate check (already implemented in Phase 3) is
      covered by a bypass-specific test if T015 didn't already assert it explicitly — otherwise
      this task is a no-op verification, not new code.

**Checkpoint**: US3 is independently testable without US1/US2 having been exercised in the same
session (a fresh under-stocked test user).

## Phase 6: User Story 4 — Start a fresh conversation (P3)

**Goal**: "New chat" is visible-but-disabled on an empty thread, and resets to hero state
otherwise.

**Independent test**: send one message, trigger "New chat," confirm the screen returns to hero
state with a fresh (absent) `thread_id` on the next Start-styling call.

- [ ] T039 [US4] Add the "New chat" (`newChat`, T002) and "Chat history" (`history`, already
      exists) 36px `IconButton`s as `TopHeader`'s `rightSlot: {kind:"custom", node: <>...</>}` in
      `frontend/app/(app)/recommend/page.tsx`, `gap: 6px` per design-system.md anatomy item 1.
      "Chat history" wires to `/history` if that route exists yet (check — feature 011 may not
      have shipped it; if the route doesn't exist, wire the control to a no-op/disabled state and
      say so explicitly in the final report rather than link to a 404).
- [ ] T040 [US4] "New chat" `disabled` when `messages.length === 0`; `onClick` resets
      `RecommendChat`'s `messages`, `pendingSinceLastStyle`, and `threadId` to initial state
      (no backend call in this slice — design-decisions §25 explicitly defers archival to 011).
- [ ] T041 [P] [US4] Test coverage (in `RecommendChat.test.tsx` or a dedicated
      `page.test.tsx`): "New chat" disabled with 0 messages, enabled with ≥1, click resets to hero
      state and the next Start-styling call omits `thread_id`.

**Checkpoint**: US4 layers cleanly on US1's `RecommendChat` state shape.

## Phase 7: User Story 5 — Style for a calendar event (P3)

**Goal**: the existing calendar-context line (built by feature 012) is correctly positioned within
the new chat surface; no new calendar logic.

**Independent test**: with no picked event, confirm the invite-to-pick line; with a picked event,
confirm it's named with a "Change" affordance.

- [ ] T042 [US5] Place the existing `RecommendCalendarContext` (unchanged) below the message list
      within `RecommendChat.tsx`/`page.tsx`, per design-system.md anatomy item 4 — verify it still
      renders correctly against the new surrounding markup (it was previously the only real
      content in the placeholder page).
- [ ] T043 [P] [US5] Extend `frontend/app/(app)/recommend/page.test.tsx` (or
      `RecommendChat.test.tsx`) to confirm `RecommendCalendarContext` renders in both the hero and
      chat states — this is a placement regression check, not new calendar logic (012 already owns
      `RecommendCalendarContext`'s own tests).

**Checkpoint**: all 5 user stories complete.

## Phase 8: Polish & cross-cutting concerns

- [ ] T044 Backend quality gates: `uv run ruff check .`, `uv run ruff format --check .`,
      `uv run mypy src`, `uv run pytest -q` (confirm ≥617, report the real new total),
      `uv run lint-imports`.
- [ ] T045 Frontend quality gates: `npm run lint`, `npx tsc --noEmit`, `npm run build` (confirm
      ≥182 tests via `npm test -- --run`, report the real new total).
- [ ] T046 Confirm no diff under `pipeline/`, `scoring/`, or `retrieval/` (`git diff main --
      backend/src/whattowear/pipeline backend/src/whattowear/scoring backend/src/whattowear/retrieval`);
      if genuinely empty, state in the final report that eval baselines were not re-run because
      nothing eval-relevant changed — do not run evals as theater.
- [ ] T047 `npx supabase db reset` from empty, confirm migrations `0001`–`0006` apply cleanly (no
      `0007` was added, design-decisions §27), then run through quickstart.md's happy path once
      against the freshly-reset database to confirm the checkpointer's startup warm-up (T008)
      actually created its tables.
- [ ] T048 Time a real styling request end-to-end (wall clock, `POST /recommend/messages` to
      response) against the populated local KB — record the number for the final report
      (handoff §11 explicitly asks for this over any test count).
- [ ] T049 Manual browser check at `localhost:3000` **and** `127.0.0.1:3000`, both themes, all
      three breakpoints, per quickstart.md's full validation list — if the environment cannot
      drive a real browser, leave this unchecked and say so explicitly rather than skip silently
      (handoff, "What you may not be able to do").
- [ ] T050 Open the PR early (per handoff "Verification" guidance) once Phase 3 (US1/MVP) is
      green, rather than waiting for all 5 stories — let CI run in parallel with Phases 4–8.

## Dependencies

- **Setup (T001-T002)** — no dependencies, both `[P]`.
- **Foundational (T003-T010)** — depends on Setup; blocks every user story phase. T003→T004,
  T005→T006→T007, T008 depends on T005 existing (router file) but not on T006. T009→T010.
- **US1 (T011-T029)** — depends on Foundational. Backend (T011-T015) before frontend wiring
  (T016-T029), but component-only tasks (T017-T026) are largely parallel with each other and with
  backend work once the contract (data-model.md/contracts/recommend.md) is stable — they don't
  need the real backend running, only the generated types (T016) for full type-checking.
- **US2 (T030-T032)** — depends on US1's `RecommendChat.tsx` (T027) and route (T014) existing.
- **US3 (T033-T038)** — depends on Foundational (T006's readiness endpoint) and US1's
  `RecommendChat.tsx` shape (T037 wires into it) but is otherwise independently testable in
  isolation with a mocked readiness response.
- **US4 (T039-T041)** — depends on US1's `RecommendChat.tsx` state shape.
- **US5 (T042-T043)** — depends on US1's `RecommendChat.tsx`/`page.tsx` layout; no new logic.
- **Polish (T044-T050)** — depends on all prior phases; T050 should actually happen as early as
  T029 completes, not literally last — listed last only because it's a repo-owner-facing action,
  not because CI-opening should wait for US2-US5.

## Parallel execution examples

Within Foundational: `T004`, `T007` (once T003/T006 exist), `T009`, `T010` can run in parallel
with each other.

Within US1 once the contract is stable: `T017`+`T018`, `T019`+`T020`, `T022`, `T023`, `T024`,
`T025`+`T026` are independent files and can be built in parallel; `T021`/`T027`/`T029` are the
integration points that depend on the smaller pieces existing first.

## Implementation strategy

**MVP = Phase 1 + 2 + 3 (US1)**. This alone delivers the handoff's core mission ("I ask for an
outfit in plain English and get one back") and is independently demoable/testable. US2-US5 are
additive layers on the same `RecommendChat` state shape and can ship incrementally after MVP is
verified — open the PR at the end of Phase 3 (T050) and let CI run while US2-US5 continue.
