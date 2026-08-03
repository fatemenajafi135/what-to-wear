---

description: "Task list for feature 011: Chat history"

---

# Tasks: Chat history

**Input**: Design documents from `/specs/011-chat-history/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/recommend.md, quickstart.md

**Tests**: Included — this project's own quality bar (Constitution "Quality Bar") requires unit
tests for deterministic logic and RLS proven by a two-user test; the handoff's DoD requires
backend/frontend test counts not to drop (692/291 on `rebuild` at hand-off).

**Organization**: Tasks are grouped by user story (spec.md priorities) after one Foundational
phase both stories need (schema + repository).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US5)

## Path Conventions

- **Backend**: `backend/src/whattowear/`, tests in `backend/tests/{unit,integration}`
- **Frontend**: `frontend/app/`, `frontend/components/`
- **Infra**: `infra/supabase/migrations/`

---

## Phase 1: Setup

No new dependencies or tooling — this feature reuses the existing FastAPI/Supabase/Next.js
stack and test runners already configured on `rebuild`.

- [ ] T001 Confirm local stack is current: `cd infra && npx supabase start`, `docker compose up
      -d` (Qdrant), `cd ../backend && uv sync`, `cd ../frontend && npm ci`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The schema and repository every user story writes through or reads from.

**⚠️ CRITICAL**: No user story task can begin until this phase is complete.

- [ ] T002 Write migration `infra/supabase/migrations/0011_chat_history.sql`: `sessions` table
      (`id uuid primary key` = `thread_id`, `user_id`, `created_at`, `updated_at`), `messages`
      table (`id`, `session_id references sessions(id) on delete cascade`, `user_id`, `kind text
      not null check (kind in ('user_message','styling_reply'))`, `text`, `outfit_ids uuid[]`,
      `created_at`, plus `messages_session_id_created_at_idx`), `alter table outfits add column
      thread_id uuid references sessions(id) on delete set null` — RLS (`for all using
      (auth.uid() = user_id) with check (...)`) and `grant select, insert, update, delete ... to
      authenticated` on both new tables, per `data-model.md` and the `0002`/`0009` pattern
- [ ] T003 `npx supabase db reset` (from `infra/`) and confirm migrations `0001`–`0011` apply
      clean
- [ ] T004 [P] Create `backend/src/whattowear/repositories/supabase_sessions.py`:
      `SupabaseSessionRepository` with `upsert_session(user_id, thread_id) -> None`,
      `insert_message(user_id, session_id, kind, text, outfit_ids) -> str`,
      `list_sessions(user_id) -> list[Row]` (joins `outfits` for a live `outfit_count`, orders by
      `updated_at desc`), `get_session(user_id, session_id) -> Row | None`,
      `list_messages(user_id, session_id) -> list[Row]` — mirrors `supabase_outfits.py`'s
      `_session_scope`/`_set_jwt_claim` pattern exactly; role is derived from `kind`
      (`research.md` §4), not stored
- [ ] T005 [P] `backend/tests/unit/test_supabase_sessions_repository.py` — mocked-session unit
      tests for every method in T004, matching `test_supabase_outfits_repository.py`'s
      `_fake_session`/`patch_session_scope` fixtures

**Checkpoint**: Schema exists, repository is unit-tested. User story work can begin.

---

## Phase 3: User Story 1 - A conversation survives a reload (Priority: P1) 🎯 MVP

**Goal**: The first user message in a thread durably creates a session; every message in that
thread is durably recorded; the list is queryable.

**Independent Test**: Send one message via `POST /recommend/messages`, then `GET
/recommend/sessions` and confirm the thread appears — no frontend needed to prove this story.

### Tests for User Story 1

- [ ] T006 [P] [US1] Integration test `backend/tests/integration/test_sessions_rls.py` — two-user,
      direct-port (`54322`), `SET ROLE authenticated` isolation proof for `sessions` and
      `messages` (own rows visible, other user's rows invisible, forged-`user_id` insert
      rejected), same shape as `test_outfits_rls.py`
- [ ] T007 [P] [US1] Extend `backend/tests/unit/test_recommend_routes.py` (or wherever
      `send_message` is currently tested): assert `POST /recommend/messages` (a) creates exactly
      one `sessions` row on a thread's first call and reuses it on the second, (b) writes a
      `user_message` row per call, (c) writes one `styling_reply` row per call with
      `outfit_ids` matching the outfits actually persisted that request, (d) each persisted
      `outfits` row gets `thread_id` set to the request's `thread_id`

### Implementation for User Story 1

- [ ] T008 [US1] Wire persistence into `send_message` in
      `backend/src/whattowear/api/v1/routes/recommend.py`: call
      `session_repository.upsert_session` + `insert_message(kind='user_message', ...)` before
      invoking the pipeline; after outfits are resolved/persisted (existing §42 loop), pass
      `thread_id` into `outfit_repository.create(...)` and call
      `insert_message(kind='styling_reply', outfit_ids=[...], text=...)` — depends on T004
- [ ] T009 [US1] Add `outfit_repository.create`'s `thread_id` parameter in
      `backend/src/whattowear/repositories/supabase_outfits.py` (nullable, included in the
      existing `INSERT` column list) — depends on T002
- [ ] T010 [US1] Add `GET /api/v1/recommend/sessions` to `recommend.py`:
      `SessionSummaryListResponse`/`SessionSummary` Pydantic models per `contracts/recommend.md`,
      backed by `session_repository.list_sessions` — depends on T004, T008
- [ ] T011 [US1] `backend/tests/unit/test_recommend_routes.py` (or a new
      `test_recommend_sessions_routes.py`): unit-test `GET /recommend/sessions` shape, ordering,
      the `outfit_count = 0` / no-third-line case for a session with none, **and** — FR-009/
      SC-004 — a session whose only associated `outfits` row has `thread_id IS NULL` (an
      old-style, pre-migration row that happens to share the session's `user_id`/`occasion`)
      shows `outfit_count = 0`, never a guessed/backfilled count

**Checkpoint**: A conversation is durable and listable via the API. Verifiable with `curl`/pytest
alone — no frontend required yet (spec.md's own Independent Test for this story).

---

## Phase 4: User Story 2 - Browse and reopen a past conversation (Priority: P1)

**Goal**: `/history` lists sessions with the specified row anatomy; `/history/:sessionId` shows
the full read-only transcript with citation badges and no thumbnails/rule list.

**Independent Test**: With ≥2 sessions (one with outfits, one without), open `/history` and
confirm both rows render correctly per design-system.md; open the one with outfits and confirm
citation badges render with no thumbnail grid or rule list.

### Tests for User Story 2

- [ ] T012 [P] [US2] `backend/tests/unit/test_recommend_sessions_routes.py`: unit-test `GET
      /recommend/sessions/{sessionId}` — 404 for foreign/missing/malformed id, message ordering,
      `styling_reply` messages carrying resolved outfit citation data, `user_message` messages
      carrying plain text
- [ ] T013 [P] [US2] `frontend/app/(app)/history/HistoryList.test.tsx`: loading skeleton, empty
      state (`chat_history.empty.body`), error state + retry (`chat_history.error.body`/`.cta`),
      **offline state suppresses the screen's own error** (mock `useOnlineStatus` to `false`,
      matching `OutfitsGrid.test.tsx`'s own convention — FR-012), row rendering (preview/date/
      message-count/optional outfit-count line), mocking `apiClient.GET`
- [ ] T014 [P] [US2] `frontend/app/(app)/history/[sessionId]/SessionDetail.test.tsx`: renders
      user/assistant bubbles in order, renders citation badges for a `styling_reply` message with
      outfits, asserts no item-thumbnail row and no rule list render anywhere on the screen,
      renders plain text for a zero-outfit `styling_reply`, **offline state suppresses the
      screen's own error** (FR-012)

### Implementation for User Story 2

- [ ] T015 [US2] Add `GET /api/v1/recommend/sessions/{sessionId}` to `recommend.py`:
      `SessionDetailResponse`/`SessionMessageView`/`SessionMessageOutfitView` per
      `contracts/recommend.md`, resolving each `styling_reply` message's `outfit_ids` against
      `outfit_repository.get` for `rationale_with_citations`/`citations`/`title` — depends on
      T004, T010
- [ ] T016 [US2] Regenerate `frontend/lib/api/schema.d.ts`
      (`npm run generate:api-types`, backend running) — depends on T010, T015
- [ ] T017 [P] [US2] `frontend/app/(app)/history/page.module.css` — two-pane CSS-only breakpoint,
      mirrors `frontend/app/(app)/outfits/page.module.css` exactly, with the 640px content-width
      cap design-system.md §5 specifies for Chat history specifically (not the 1.6fr grid's own
      wider cap)
- [ ] T018 [US2] `frontend/app/(app)/history/HistoryList.tsx`: fetch/loading/empty/error/offline
      states — `useOnlineStatus()` gates the screen's own error exactly like `OutfitsGrid.tsx`
      (`showError = error && isOnline`) — row list per design-system.md § Chat history row
      anatomy — depends on T016
- [ ] T019 [US2] `frontend/app/(app)/history/page.tsx`: `TopHeader` (title "Chat history", back
      arrow, right slot = `pill` "New chat"), two-pane shell wrapping `HistoryList` +
      `"Select a conversation to view it."` placeholder pane (desktop only) — depends on T017,
      T018
- [ ] T020 [US2] `frontend/components/history/RationaleWithCitations.tsx` (or lift/share the
      existing helper): factor `frontend/app/(app)/outfits/[outfitId]/RationaleWithCitations.tsx`'s
      `CITATION_TOKEN` splitting logic into a location both Outfit detail and Session detail can
      import, so Session detail doesn't duplicate the citation-badge-rendering regex
- [ ] T021 [US2] `frontend/app/(app)/history/[sessionId]/page.tsx`: `TopHeader` (title
      "Conversation", subtitle = session date, back arrow, no right slot), read-only bubble list
      (user text bubbles; `styling_reply` bubbles render each linked outfit's citation-badged
      `rationale_with_citations` via T020, explicitly no thumbnail grid / rule list; zero-outfit
      replies render plain `text`), loading/error/offline states matching `[outfitId]/page.tsx`'s
      own `useOnlineStatus()`-gated pattern (FR-012) — depends on T016, T020
- [ ] T022 [US2] Wire the Recommend header's `history` `IconButton` in
      `frontend/app/(app)/recommend/page.tsx` to link to `/history` (currently hardcoded
      `disabled`/inert) — depends on T019

**Checkpoint**: Chat history is fully browsable and read-only-reopenable in the browser.

---

## Phase 5: User Story 3 - Continue a past conversation (Priority: P1)

**Goal**: "Continue conversation" resumes Recommend on the same thread; the next message carries
the original `thread_id`.

**Independent Test**: Open a session, tap "Continue conversation," send a message, inspect the
network request body for `thread_id`.

### Tests for User Story 3

- [ ] T023 [P] [US3] `frontend/components/recommend/RecommendChat.test.tsx` (extend existing):
      given an initial `thread_id` + hydrated `messages` prop, the next `POST
      /recommend/messages` call's request body carries that same `thread_id` — assert on the
      mocked `apiClient.POST` call args, not on rendered reply text (handoff's own verification
      instruction)

### Implementation for User Story 3

- [ ] T024 [US3] Extend `RecommendChatHandle`/props in
      `frontend/components/recommend/RecommendChat.tsx` to accept an optional initial `thread_id`
      + `messages` (hydrating `useState` instead of starting empty) — depends on T004
- [ ] T025 [US3] `frontend/app/(app)/recommend/page.tsx`: read a `thread_id` query/search param
      on mount; when present, fetch that session via `GET /recommend/sessions/{id}` (T015) and
      pass its `id` + reconstructed `messages` into `RecommendChat` — depends on T015, T024
- [ ] T026 [US3] Add the "Continue conversation" full-width primary `Button` to
      `frontend/app/(app)/history/[sessionId]/page.tsx`, linking to
      `/recommend?thread_id={session.id}` — depends on T021, T025

**Checkpoint**: A past conversation can be genuinely resumed, verified at the request level.

---

## Phase 6: User Story 4 - Start a new conversation without losing the old one (Priority: P2)

**Goal**: Confirm "New chat" needs no behavior change (§44) and its guard still holds now that
sessions are real.

**Independent Test**: Send a message, tap "New chat," reload `/history`, confirm the prior
conversation is present exactly as before.

### Tests for User Story 4

- [ ] T027 [US4] Update `frontend/app/(app)/recommend/page.test.tsx`'s existing "Chat history is
      present but inert" test — the `history` icon is no longer inert (T022 wired it); replace
      with an assertion that it links to `/history`, and that `newChat` remains disabled with no
      user turns / enabled with ≥1

### Implementation for User Story 4

- [ ] T028 [US4] No production code change expected (§44: `newChat()`'s existing local-reset
      implementation in `RecommendChat.tsx` already satisfies this story once T008 makes
      persistence real) — run `quickstart.md` Scenario 4 manually and record the result; only
      touch code here if the manual run reveals the guard doesn't actually hold

**Checkpoint**: "New chat" behavior is confirmed correct under real persistence, not just
assumed.

---

## Phase 7: User Story 5 - Jump from a session to the outfits it produced (Priority: P3)

**Goal**: Session detail's "View in Outfits" button appears only when the session produced
outfits, with the correct count, and navigates to `/outfits`.

**Independent Test**: Open a session with outfits, confirm the button's count and destination;
open one without, confirm no button.

### Tests for User Story 5

- [ ] T029 [P] [US5] Extend `SessionDetail.test.tsx` (T014): asserts the "{count} → View in
      Outfits" button renders with the right count when `outfit_count > 0` and is absent when
      `outfit_count === 0`

### Implementation for User Story 5

- [ ] T030 [US5] Add the full-width secondary "{outfit count} → View in Outfits" `Button` to
      `frontend/app/(app)/history/[sessionId]/page.tsx`, linking to `/outfits`, conditional on
      `session.outfit_count > 0` — depends on T021

**Checkpoint**: All five user stories independently functional.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T031 Run `quickstart.md` Scenarios 1–7 end-to-end in a browser, both `localhost:3000` and
      `127.0.0.1:3000`, both themes, mobile and desktop widths — record what was seen per the
      handoff §9 report format
- [ ] T032 `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy src
      && uv run pytest && uv run lint-imports` — confirm backend test count ≥ 692
- [ ] T033 `cd frontend && npm run lint && npm run typecheck && npm run build && npm test` —
      confirm frontend test count ≥ 291
- [ ] T034 Confirm no file under `pipeline/`, `scoring/`, or `retrieval/` appears in `git diff
      rebuild...HEAD` — if one does, re-run evals and justify in this feature's own
      design-decisions.md addendum before proceeding (expected: no such diff exists)
- [ ] T035 Open the PR early against `rebuild` (`feat/011-chat-history`) and record the CI run
      URL/result for the handoff §9 report

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)** → **Foundational (Phase 2)**: schema + repository, blocks everything else
- **US1 (Phase 3)**: needs Phase 2 only — independently verifiable via API/pytest alone
- **US2 (Phase 4)**: needs US1's `GET /recommend/sessions` (T010) plus its own new
  `GET /recommend/sessions/{id}` (T015)
- **US3 (Phase 5)**: needs US2's `GET /recommend/sessions/{id}` (T015) and Session detail page
  shell (T021) to place its button in
- **US4 (Phase 6)**: needs US1's persistence (T008) to be real and US2's history-icon wiring
  (T022) to exist to update the test it changes
- **US5 (Phase 7)**: needs US2's Session detail page shell (T021)
- **Polish (Phase 8)**: needs all stories complete

### Parallel Opportunities

- T004/T005 (Phase 2) in parallel once T002/T003 land
- T006/T007 (US1 tests) in parallel with each other, and can be written before T008–T011
  (write-first, matching this codebase's existing test-alongside-implementation style)
- T012/T013/T014 (US2 tests) in parallel with each other
- T017 (CSS module) in parallel with T015/T016 (backend route + type regen) — different files
- T023 (US3 test) in parallel with US2 tasks once US2's contract (T015) is stable

---

## Implementation Strategy

### MVP First

Phases 1–3 (Setup, Foundational, US1) prove the actual mission-critical gap — durable persistence
— entirely at the API layer, before any UI exists. Phases 4–5 (US2, US3) are what make that
persistence reachable and resumable by a real user; both are P1 in spec.md, so "MVP" for this
feature realistically means Phases 1–5 together, not US1 alone left half-facing.

### Incremental Delivery

1. Phases 1–3 → persistence real, provable via `pytest`/`curl`
2. Phase 4 → `/history` browsable in a browser
3. Phase 5 → "Continue conversation" closes the mission's own stated loop
4. Phase 6 → confirms nothing regressed on the existing "New chat" guard
5. Phase 7 → the one P3 convenience link
6. Phase 8 → full verification + PR
