# Tasks: Recommend Chat Persists Across In-App Navigation

**Input**: Design documents from `/specs/019-recommend-chat-persistence/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/recommend-chat-store.md, quickstart.md — all present

**Tests**: Included. The repo's own convention co-locates a `.test.ts(x)` with every module/component (see `RecommendChat.test.tsx`, `page.test.tsx`, `lib/calendar/useCalendarConnection.test.ts`), and the task brief requires the frontend baseline (347) not to drop — a feature-sized refactor with no new or updated tests would itself be a regression risk against that bar.

**Organization**: Tasks are grouped by user story (spec.md) to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US4)
- Every task names its exact file path

## Path Conventions

Frontend only, per plan.md's Project Structure — no backend, `infra/`, or `design/` path is touched.

---

## Phase 1: Setup

**Purpose**: Stand up the new store module's shape before wiring any behavior into it.

- [X] T001 Create `frontend/lib/recommend/recommendChatStore.ts` with the `RecommendChatState` type (per contracts/recommend-chat-store.md), the initial/default state, a module-scoped mutable snapshot variable, a `listeners: Set<() => void>` set, and `getState()`/`subscribe(listener)` — no action functions yet. `getState()` returns the current snapshot; `subscribe` adds/removes a listener and returns the unsubscribe function.

**Checkpoint**: The store's read side compiles and exports a stable empty snapshot. Nothing consumes it yet.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The store's actions — every user story depends on these existing and being correct before any component is wired to them.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T002 In `frontend/lib/recommend/recommendChatStore.ts`, implement `reset()` (returns every field to its empty/idle default and notifies listeners) and `hydrate(threadId, messages)` (replaces `messages`/`threadId` wholesale, resets `pendingTexts`/`turnPending`/`startStyling` to defaults, notifies listeners) — per data-model.md's state-transitions table. (depends on T001)
- [X] T003 In `frontend/lib/recommend/recommendChatStore.ts`, implement `sendTurn(text: string): Promise<void>` by porting the body of `RecommendChat.tsx`'s current `handleSend` (`POST /recommend/turns` via `apiClient`) to mutate the singleton and notify listeners directly instead of calling React setters — including the existing "no bubble invented on error" behavior. (depends on T002)
- [X] T004 In `frontend/lib/recommend/recommendChatStore.ts`, implement `startStyling(): Promise<void>` by porting the body of `RecommendChat.tsx`'s current `handleStartStyling` (`POST /recommend/messages` via `apiClient`) the same way, including the wrap-up + outfit-bearing message pair on success and the `"error"` status on failure. (depends on T002)
- [X] T005 Create `frontend/lib/recommend/recommendChatStore.test.ts` covering: `sendTurn` success appends a user message + assistant reply and sets `threadId` from the response; `sendTurn` failure leaves `messages`/`pendingTexts` unchanged and adds no bubble; `startStyling` success appends the wrap-up + outfit message and clears `pendingTexts`; `startStyling` failure sets `startStyling: "error"`; `hydrate` replaces `messages`/`threadId` and resets the rest; `reset` clears every field; a listener registered *after* an async action starts still observes the action's eventual result when it calls `getState()` following notification (the FR-007 guarantee — simulate "no component mounted" by not subscribing until after invoking the action). (depends on T002, T003, T004)

**Checkpoint**: The store is fully implemented and unit-tested standalone, independent of any component.

---

## Phase 3: User Story 1 - Conversation survives a trip to another tab (Priority: P1) 🎯 MVP

**Goal**: `RecommendChat` renders from the shared store instead of local state, so unmounting and remounting it (what in-app navigation does) no longer loses the conversation.

**Independent Test**: Render `RecommendChat`, send a message and let it reply, unmount it, render a fresh instance with no props — the same messages are shown immediately, no hero state, no new network call for the conversation itself.

- [X] T006 [US1] Refactor `frontend/components/recommend/RecommendChat.tsx`: replace the five `useState` calls for `messages`/`pendingTexts`/`threadId`/`turnPending`/`startStyling` with `useSyncExternalStore(recommendChatStore.subscribe, recommendChatStore.getState)`; have `handleSend`/`handleStartStyling` call `recommendChatStore.sendTurn`/`recommendChatStore.startStyling` instead of holding their own request logic; remove the `forwardRef`, `useImperativeHandle`, and the exported `RecommendChatHandle` type (page.tsx will call the store directly instead); remove the `onHasUserMessageChange` prop (page.tsx will read `hasUserMessage` from the store directly). Readiness (`GET /recommend/readiness`) stays untouched, local `useState`, refetched on mount (FR-009). (depends on T001–T005)
- [X] T007 [US1] Update `frontend/app/(app)/recommend/page.tsx`: drop `chatRef`/`RecommendChatHandle`/`onHasUserMessageChange`; read `hasUserMessage` via `useSyncExternalStore(recommendChatStore.subscribe, recommendChatStore.getState)` (`.messages.some(m => m.role === "user")`); wire the "New chat" `IconButton`'s `onClick` to `recommendChatStore.reset()` directly; render `<RecommendChat />` with no ref and no `onHasUserMessageChange` prop. (depends on T006)
- [X] T008 [US1] Update `frontend/components/recommend/RecommendChat.test.tsx`: add `beforeEach(() => recommendChatStore.reset())`; add a test that renders, sends a message, unmounts, renders a fresh `<RecommendChat />` with no props, and asserts the prior message and reply are still shown with no hero state and no new `POST /recommend/turns` call. Existing tests continue to pass unmodified apart from the added `beforeEach` (they already interact only through props/DOM, not the removed ref). Also add: (a) a component-level in-flight test — render, send a message but don't let the mocked `POST /recommend/turns` resolve yet, unmount, render a fresh instance, *then* resolve the mock — assert the reply lands in the new instance exactly once, with no stuck "Thinking…" and no duplicate bubble (`/speckit-analyze` finding E1, closing the gap between T005's store-level coverage and FR-007/SC-003's component-level guarantee); (b) an unmount/remount test with a *changed* `GET /recommend/readiness` mock between the two renders, asserting the second render reflects the new readiness response — proves readiness stayed decoupled from the store refactor (`/speckit-analyze` finding E2, FR-009/Acceptance Scenario 6). (depends on T006)
- [X] T009 [P] [US1] Update `frontend/app/(app)/recommend/page.test.tsx`: add `beforeEach(() => recommendChatStore.reset())`. (depends on T007)
- [ ] T010 [US1] Manual validation: drive quickstart.md steps 1–4 (send a message, Start styling, navigate to Closet and back three-plus times, confirm no drift and no flash) in a real browser against a running dev stack. (depends on T006, T007, T008, T009)

**Checkpoint**: User Story 1 is fully functional and independently testable — the core bug from issue #47 is fixed.

---

## Phase 4: User Story 2 - "New chat" still starts fresh (Priority: P2)

**Goal**: Confirm the one deliberate reset path keeps working, and that the reset itself survives a subsequent trip to another tab and back (it doesn't get silently undone by the persistence mechanism).

**Independent Test**: With an active conversation, tap "New chat" → hero state. Navigate away and back → still hero state.

- [X] T011 [US2] Add tests in `frontend/app/(app)/recommend/page.test.tsx`: tapping "New chat" returns to hero state and disables the button again (extends the existing "New chat becomes enabled… and resets the thread on click" test if present, or adds alongside it); after tapping "New chat," unmounting and remounting `RecommendPage` (simulating navigate-away-and-back) still shows the hero state, not the pre-reset conversation. (depends on T007, T009)
- [ ] T012 [US2] Manual validation: drive quickstart.md step 6 (New chat, then navigate away and back, confirm hero state holds) in a real browser. (depends on T011)

**Checkpoint**: User Stories 1 and 2 both work, together and independently.

---

## Phase 5: User Story 3 - A real reload starts fresh (Priority: P3)

**Goal**: Confirm the module-singleton design doesn't accidentally survive a real reload — no code path writes the conversation anywhere that outlives the JS context (`localStorage`, `sessionStorage`, IndexedDB, a cookie, etc.).

**Independent Test**: With an active conversation, hard-reload the tab (or fully close/relaunch the installed PWA) — hero state.

- [X] T013 [US3] Add a test in `frontend/lib/recommend/recommendChatStore.test.ts` that spies on `window.localStorage.setItem`, `window.sessionStorage.setItem`, and `document.cookie` (setter) across a full `sendTurn` → `startStyling` sequence and asserts none of them were called — the store's persistence boundary is provably "JS memory only." (depends on T005)
- [ ] T014 [US3] Manual validation: drive quickstart.md step 7 (hard-reload the tab, or close and relaunch the installed PWA, with an active conversation) and confirm the hero state, not the prior conversation. (depends on T006, T007, T008, T009)

**Checkpoint**: All three of the persist/reset boundaries from the issue (in-app nav persists; New chat resets; real reload resets) are covered.

---

## Phase 6: User Story 4 - Resuming a specific past thread via link still works (Priority: P4 in delivery order; P3 in spec.md)

**Goal**: The existing `?thread_id=` "Continue conversation" resume path (feature 011) keeps working, and gains the same navigate-away-and-back durability as an ordinary conversation, without regressing to a re-fetch on every return.

**Independent Test**: From Session detail, tap "Continue conversation" for a past session — its prior turns load. Navigate away and back — still there, no second fetch.

- [X] T015 [US4] Update `frontend/app/(app)/recommend/page.tsx`'s resume `useEffect`: before calling `GET /recommend/sessions/{session_id}`, compare `resumeThreadId` against `recommendChatStore.getState().threadId`; if equal, skip the fetch entirely and treat the screen as immediately ready; if different (including the store being empty), fetch as today and call `recommendChatStore.hydrate(resumeThreadId, messages)` with the mapped messages instead of local `setResumedMessages` state; remove the now-unnecessary `resumedMessages` local state. (depends on T007)
- [X] T016 [US4] Update `frontend/app/(app)/recommend/page.test.tsx`: a test that a `?thread_id=` link for a thread not currently held triggers the fetch and renders its turns; a test that a `?thread_id=` link matching the store's current `threadId` does **not** trigger a `GET /recommend/sessions/{id}` call; a test that after resuming, unmounting and remounting `RecommendPage` (now with no query param, matching plain in-app nav to `/recommend`) still shows the resumed conversation. (depends on T015)
- [ ] T017 [US4] Manual validation: drive quickstart.md step 8 (open a session from History via "Continue conversation," then navigate away and back to plain `/recommend`) in a real browser. (depends on T015, T016)

**Checkpoint**: All four user stories are independently functional and interoperate correctly.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Full verification suite, per the task brief's hard bar (counts must not drop) and its explicit requirement for a real, human-driven browser pass.

- [X] T018 [P] Run `npm run lint && npm run typecheck` in `frontend/` and fix any findings introduced by this feature's changes. (depends on T006–T017)
- [X] T019 [P] Run `npm test` in `frontend/` and confirm the total passing count is at or above the 347 baseline recorded in the task brief. (depends on T006–T017)
- [X] T020 Run `npm run build` in `frontend/`. (depends on T018, T019)
- [ ] T021 Run `npm run e2e:pwa` in `frontend/` and confirm the total passing count is at or above the 11 baseline. (depends on T020)
- [ ] T022 Full manual walkthrough of `quickstart.md`'s 8-step sequence, end to end in one sitting, in a real browser — not just the per-story slices already run in T010/T012/T014/T017 — to catch any interaction between the four stories. (depends on T021)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies — starts immediately.
- **Foundational (Phase 2)**: depends on Setup. **Blocks every user story** — the store's actions must exist and be correct before any component can be wired to them.
- **User Story 1 (Phase 3)**: depends on Foundational. No dependency on any other story.
- **User Story 2 (Phase 4)**: depends on Foundational **and** on US1's `page.tsx`/`RecommendChat.tsx` refactor (T006/T007) already existing, since it tests the reset path through those same files. Cannot usefully start before US1 lands.
- **User Story 3 (Phase 5)**: T013 depends only on Foundational (pure store-level test) and could run in parallel with US1. T014 (manual validation) depends on US1's refactor being live, same as US2.
- **User Story 4 (Phase 6)**: depends on Foundational and on US1's `page.tsx` refactor (T007), since it modifies the same resume effect.
- **Polish (Phase 7)**: depends on all four user stories being complete.

### Within Each User Story

- Store/foundational work before component wiring.
- Component wiring before its own tests.
- Automated tests before the manual validation task for that story.

### Parallel Opportunities

- T009 (`page.test.tsx` beforeEach) can run in parallel with T008 (`RecommendChat.test.tsx` beforeEach) — different files, both depend only on T006/T007 respectively.
- T013 (US3's store-level test) can run in parallel with all of Phase 3 (US1) — it only depends on Foundational.
- T018 and T019 in Polish can run in parallel — independent commands, no shared file edits.

---

## Parallel Example: Phase 2 boundary

```text
# T013 (US3) has no dependency on US1's component refactor and can be picked up
# as soon as Foundational (T001-T005) is done, alongside T006 (US1):
Task: "Add localStorage/sessionStorage/cookie spy test in frontend/lib/recommend/recommendChatStore.test.ts"
Task: "Refactor frontend/components/recommend/RecommendChat.tsx to consume the store"
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1 (Setup) → Phase 2 (Foundational) → Phase 3 (US1).
2. **STOP and VALIDATE**: run T010's manual walkthrough. This alone closes GitHub issue #47's
   reported symptom.
3. Everything from Phase 4 onward hardens the two boundary cases (New chat, real reload) and the
   pre-existing resume path against regressing — all real requirements from spec.md, not optional
   polish, but US1 is the slice that fixes the bug.

### Incremental Delivery

1. Setup + Foundational → store ready, no user-visible change yet.
2. US1 → the bug is fixed. Commit, verify.
3. US2 → New chat's reset is proven to survive navigation too. Commit, verify.
4. US3 → real reload is proven to still reset (a regression guard, not new behavior). Commit, verify.
5. US4 → the `?thread_id=` resume path is proven not to regress and to gain the same durability. Commit, verify.
6. Polish → full suite + full manual pass.

---

## Notes

- [P] tasks touch different files with no unresolved dependency between them.
- Every user-story phase ends in a manual-validation task — per the task brief, this is "the part
  no test suite proves," not a formality.
- Per the repo's hard commit-cadence requirement: commit after each task or tight group (e.g.
  T002–T004 as one commit, since they're the same file built incrementally; T006+T007 as one
  commit, since `page.tsx` doesn't compile against the refactored `RecommendChat.tsx` until both
  land) — never let a working session's changes pile up uncommitted.
