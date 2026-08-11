# Tasks: Calendar Pick Reaches Recommend

**Input**: Design documents from `/specs/020-calendar-pick-to-recommend/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md,
contracts/{picked-event-store,calendar-pick-flow,recommend-turns-seed}.md, quickstart.md — all
present. `docs/design-decisions.md` §61 (defect 3's design decision) already committed.

**Tests**: Included. The repo's convention co-locates a `.test.ts(x)`/`test_*.py` with every
module/route this feature touches, and the baseline counts (backend 780, frontend 363, PWA
e2e 11) must not drop.

**Organization**: Tasks are grouped by user story (spec.md) — all three are P1, since the
issue's own acceptance criteria treat them as one connected bug, but each remains
independently testable per its own Independent Test.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1 (pick navigates), US2 (Recommend stays current), US3 (conversation knows
  the calendar)
- Every task names its exact file path

## Path Conventions

Frontend: `frontend/`. Backend: `backend/src/whattowear/`, `backend/tests/`. No `infra/` or
`design/` path is touched (docs already committed in the plan phase).

---

## Phase 1: Setup

**Purpose**: Stand up the write-through store's read side (contracts/picked-event-store.md)
before any component or write path depends on it — both US1 and US2 need this to exist first.

- [X] T001 Create `frontend/lib/calendar/pickedEventStore.ts` with the `PickedEventState` type
      (`status: "unknown" | "loaded"`, `event: CalendarEventView | null`), where
      `CalendarEventView` is `components["schemas"]["CalendarEventView"]` via
      `import type { components } from "@/lib/api/schema"` — the established convention for
      consuming a generated type in this codebase (`components/recommend/OutfitCard.tsx`'s
      `type StylingOutfit = components["schemas"]["StylingOutfit"]`), not a redefinition
      (Constitution VII). A
      module-scoped snapshot variable initialized to `{ status: "unknown", event: null }`, a
      `listeners: Set<() => void>` set, and `getState()`/`getServerSnapshot()`/`subscribe(listener)`
      — mirroring `frontend/lib/recommend/recommendChatStore.ts`'s existing shape for these
      three. No `hydrate`/`set` yet.

**Checkpoint**: The store's read side compiles and exports a stable `"unknown"` snapshot.
Nothing writes to it yet.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The store's two mutators — both US1 (writes via `set`) and US2 (reads, and
triggers `hydrate` when needed) depend on these existing and being correct first.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T002 In `frontend/lib/calendar/pickedEventStore.ts`, implement `set(event:
      CalendarEventView | null): void` — synchronously writes `{ status: "loaded", event }` and
      notifies listeners, no network call (contracts/picked-event-store.md point 3).
      (depends on T001)
- [X] T003 In `frontend/lib/calendar/pickedEventStore.ts`, implement `hydrate(): void` — a
      no-op if `status !== "unknown"` or a hydration request is already in flight; otherwise
      calls `apiClient.GET("/api/v1/calendar/picked-event")` exactly once and writes the
      result via the same path `set()` uses (`status: "loaded"`, `event: data.event ?? null`
      when `data.picked`, else `null`) — contracts/picked-event-store.md points 2 and 4.
      (depends on T002)
- [X] T004 [P] Create `frontend/lib/calendar/pickedEventStore.test.ts` covering: initial
      `getState()`/`getServerSnapshot()` both return `{status: "unknown", event: null}`;
      `hydrate()` issues exactly one GET and updates state on resolution; a second `hydrate()`
      call while the first is still in flight does not issue a second GET; `hydrate()` is a
      no-op once `status === "loaded"`; `set(event)` updates state and notifies subscribers
      synchronously with no network call; `set(null)` is a valid clear. (depends on T003)

**Checkpoint**: The store is fully implemented and unit-tested standalone, independent of any
component.

---

## Phase 3: User Story 1 - Picking an event takes you to Recommend (Priority: P1) 🎯

**Goal**: `handlePick` checks its `PUT` result, writes the confirmed pick through to
`pickedEventStore`, and navigates to `/recommend` only on confirmed success — never before,
never on a failure.

**Independent Test**: Tap an event on Calendar with the save succeeding — land on `/recommend`
with no manual navigation. Repeat with the save failing — stay on Calendar, rows re-enable, an
error shows.

- [X] T005 [US1] Rewrite `handlePick` in `frontend/app/(app)/calendar/page.tsx` per
      contracts/calendar-pick-flow.md: add `savingEventId: string | null` and
      `pickError: CalendarEventView | null` (the event to retry) state; on tap, set
      `savingEventId` to the tapped event's id (rows disable via the existing
      `disabled={pickedEventId !== null || savingEventId !== null}` condition — reusing
      §609's existing dimming, not a new visual state) and clear any previous `pickError`;
      `await` the `PUT`; on success (`data` present, `error` absent) call
      `pickedEventStore.set(data.event)`, set `pickedEventId` from `data.event.google_event_id`,
      and `router.push("/recommend")` (`useRouter` from `next/navigation`); on failure, clear
      `savingEventId`, leave `pickedEventId` untouched (still `null` if this was the first
      attempt), and set `pickError` to the attempted event so a retry can re-use it. Remove the
      old pre-await `setPickedEventId` call and the discarded PUT result — this is the literal
      bug (issue #41 defect 1), not something to preserve alongside the fix.
- [X] T006 [US1] In `frontend/app/(app)/calendar/page.tsx`, render a `Banner` (import from
      `@/components/ui/Banner/Banner`, `variant="error"`) above the event list when `pickError`
      is set: body copy "Couldn't save that pick." (voice-matched to the existing
      "Couldn't sync your calendar." on the same screen), `action={{ label: "Try again",
      onClick: () => handlePick(pickError) }}`.
- [X] T007 [P] [US1] Add cases to `frontend/app/(app)/calendar/page.test.tsx`: tapping an
      event with `apiClient.PUT` resolving `{data: {picked: true, event: {...}}, error:
      undefined}` navigates to `/recommend` (mock `next/navigation`'s `useRouter`, assert
      `push` called with `"/recommend"`) and calls the (mocked) `pickedEventStore.set` with
      the response's event; tapping an event with `PUT` resolving `{data: undefined, error:
      {...}}` does NOT navigate, re-enables every row (not left `disabled`), and renders a
      "Couldn't save that pick." `Banner` with a "Try again" action; tapping "Try again"
      re-invokes the `PUT` for the same event. (depends on T005, T006)
- [ ] T008 [US1] Manual validation: drive quickstart.md Scenario A (success navigates;
      simulated failure re-enables rows and shows the Banner) against the local dev stack.
      (depends on T005, T006, T007)

**Checkpoint**: User Story 1 is fully functional and independently testable — picking an
event no longer dead-ends, and a failed save is never indistinguishable from a successful one.

---

## Phase 4: User Story 2 - The Recommend screen always shows the current pick (Priority: P1)

**Goal**: `RecommendCalendarContext` renders from `pickedEventStore` instead of its own
mount-scoped fetch, so it reflects the true current pick immediately — including the instant
after a Story 1 navigation, and across any later in-app navigation.

**Independent Test**: Pick an event, land on Recommend — the label is already correct on
first paint. Navigate to another tab and back — still correct, no re-fetch flash.

- [X] T009 [US2] Rewrite `frontend/components/calendar/RecommendCalendarContext.tsx`: replace
      the local `useState` + `useEffect` fetch with
      `useSyncExternalStore(pickedEventStore.subscribe, pickedEventStore.getState,
      pickedEventStore.getServerSnapshot)`; call `pickedEventStore.hydrate()` once, in a
      `useEffect` that only fires when `status === "unknown"` on mount (a no-op per T003 if
      already `"loaded"`); render "Style for an event from calendar" when `event === null`,
      "Styling for {event.title} · Change" when set — copy and markup unchanged, only the data
      source changes. (depends on T002, T003)
- [X] T010 [P] [US2] Rewrite `frontend/components/calendar/RecommendCalendarContext.test.tsx`
      to mock `@/lib/calendar/pickedEventStore` instead of `apiClient` directly: renders the
      unpicked prompt when the store's `event` is `null`; renders "Styling for {title} ·
      Change" when the store already holds a `"loaded"` event **synchronously on first
      render** (no `waitFor` needed — proving there's no fetch-then-flash for the common
      "just navigated from a successful pick" case, the actual regression this feature fixes);
      calls `hydrate()` once when the store starts `"unknown"`; does not call `hydrate()` again
      if the store is already `"loaded"` when a second instance mounts. (depends on T009)
- [ ] T011 [US2] Manual validation: drive quickstart.md Scenario B (label correct immediately
      after a Story-1 navigation; stays correct across a tab-away-and-back; updates again after
      picking a different event) against the local dev stack. (depends on T005, T009, T010)

**Checkpoint**: User Stories 1 and 2 both work, together and independently — the pick reaches
Recommend, instantly and correctly, every time.

---

## Phase 5: User Story 3 - The stylist already knows what the calendar knows (Priority: P1)

**Goal**: A fresh conversation with a picked event silently carries its `location` into the
conversation's slot state (never its occasion/formality — docs/design-decisions.md §61), and
offers the event's title/time back as editable, unsent Composer text.

**Independent Test**: With an event picked and a fresh conversation, the Composer is
pre-filled; sending it (or "what should I wear") gets a reply that doesn't ask for the
location; Start Styling carries that location into context assembly regardless.

### Backend (location seed)

- [X] T012 [US3] In `backend/src/whattowear/api/v1/routes/recommend.py`, add
      `_get_calendar_repository() -> SupabaseCalendarRepository` (mirrors the existing
      `_get_repository`/`_get_session_repository` pattern) and import
      `SupabaseCalendarRepository` from `whattowear.repositories.supabase_calendar`. In
      `send_turn`, add a `calendar_repository: SupabaseCalendarRepository =
      Depends(_get_calendar_repository)` parameter. When `body.thread_id is None` (a
      brand-new thread — the existing signal already used to generate `thread_id` via
      `str(uuid.uuid4())`), look up `calendar_repository.get_picked_event(user_id)` and, if it
      returns an event with a non-null `location`, call
      `graph.update_state(config, {"location": event.location})` — placed after `thread_id`/
      `graph`/`config` are established and **before** `known_slots = graph.get_state(config).values`
      is read, per contracts/recommend-turns-seed.md. No other field is written from the
      picked event.
- [X] T013 [P] [US3] Create `backend/tests/unit/test_recommend_turns_calendar_seed.py` (or
      the equivalent existing test module for `recommend.py`'s `/recommend/turns` route if one
      already exists — extend it instead of creating a duplicate) covering: a brand-new
      thread with a picked event that has a `location` results in
      `graph.get_state(config).values["location"]` equal to that location after the call,
      and the conversational LLM call (mocked, per the constitution's "no live LLM calls in
      CI") receives a prompt whose "already known" line includes `location` (i.e.
      `conversation._known_slots_line` is exercised with `location` present — verifying
      FR-006 at the deterministic, code level rather than asserting on model free text); a
      brand-new thread with no picked event leaves `location` unset; a brand-new thread with a
      picked event that has `location: None` leaves `location` unset (no crash); a
      **continuing** thread (`body.thread_id` provided) never re-reads or re-seeds the picked
      event, even if one exists, so an in-progress conversation's own stated location is never
      clobbered (spec.md FR-011). **Also** (closing the FR-007/SC-004 gap identified in
      `/speckit-analyze`, so this is verified automatically and not only by T018's manual
      pass): after seeding, call `send_message` (mocking `graph.invoke` the same way this
      route's existing tests already do) for the first turn on that same thread and assert the
      `invoke_input` dict `graph.invoke` was called with contains `"location"` equal to the
      seeded value — proving the existing, unmodified `known_state.get("location")` read in
      `send_message` actually picks up what `send_turn` seeded, end to end across both routes.
      (depends on T012)

### Frontend (composer pre-fill)

- [X] T014 [P] [US3] Add an optional `initialValue?: string` prop to
      `frontend/components/recommend/Composer.tsx`; seed `useState(initialValue ?? "")` from
      it — a plain initial-value read, not a `useEffect` sync, so a later change to
      `initialValue` (e.g. the picked event changing after the user has already started
      typing) never overwrites what the user has typed.
- [X] T015 [P] [US3] Add cases to `frontend/components/recommend/Composer.test.tsx`: with
      `initialValue="Dinner with Ana, Fri 8:00 PM"`, the input renders that text on mount and
      it is editable; typing over it and calling `onSend` sends the edited text, not the
      original; re-rendering with a different `initialValue` prop after the user has typed
      does not replace what they typed. (depends on T014)
- [X] T016 [US3] In `frontend/components/recommend/RecommendChat.tsx`, compute the Composer
      pre-fill: when `!hasUserMessage` (the same condition already gating `HeroState`) and
      `pickedEventStore.getState().event` is non-null, build
      `` `${event.title}, ${formatEventTime(event.start)}` `` (import `formatEventTime` from
      `@/lib/calendar/formatEventTime`, the same formatter `EventRow` already uses) and pass
      it as `<Composer initialValue={...} .../>`; otherwise pass no `initialValue`. Read the
      store via the same `useSyncExternalStore` subscription pattern already used for
      `recommendChatStore` in this file. (depends on T009, T014)
- [X] T017 [P] [US3] Add cases to `frontend/components/recommend/RecommendChat.test.tsx`: a
      fresh conversation (`!hasUserMessage`) with a picked event in the (mocked)
      `pickedEventStore` renders the Composer with the expected pre-filled text; a fresh
      conversation with no picked event renders the Composer with no pre-fill (unchanged
      behavior); a conversation that already has a user message renders no pre-fill even if a
      picked event exists (spec.md FR-011/Acceptance Scenario 5 — an in-progress conversation
      is left alone). (depends on T016)
- [ ] T018 [US3] Manual validation: drive quickstart.md Scenario C in full, including the
      contradiction check (step 6) — pre-filled Composer text on arrival; the first reply
      doesn't ask for a location the event supplied; Start Styling carries the location
      through; a user-edited/contradicting location overrides the seeded one on a later turn.
      (depends on T012, T013, T016, T017)

**Checkpoint**: All three user stories work, together and independently. The pick now reaches
the conversation, without ever asserting a title-derived occasion/formality as fact.

---

## Phase 6: Polish & Cross-Cutting Verification

**Purpose**: Confirm the full verification suite is green and nothing regressed, per the task
brief's baselines (backend 780, frontend 363, PWA e2e 11) — counts must not drop.

- [X] T019 [P] Confirm no OpenAPI contract drift: with the backend running locally, run
      `npm run generate:api-types` in `frontend/` and diff `frontend/lib/api/schema.d.ts`
      against its committed version — expect **no diff** (research.md's "Confirmed: no
      OpenAPI contract change" finding); if a diff appears, investigate before proceeding
      rather than committing an unexplained schema change.
- [ ] T020 Run the backend verification suite from `backend/`: `uv run pytest`,
      `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src`,
      `uv run lint-imports` — all must pass; `pytest` count must be ≥ 780 (781+ once T013's
      new cases are counted).
- [ ] T021 Run the frontend verification suite from `frontend/`: `npm run lint`,
      `npm run typecheck`, `npm test`, `npm run build` — all must pass; `npm test` count must
      be ≥ 363 (367+ once T004/T007/T010/T015/T017's new cases are counted).
- [ ] T022 Run `npm run e2e:pwa` from `frontend/` against a production build — count must be
      ≥ 11, no regression.
- [ ] T023 Full manual pass in a real browser (see final report): pick an event → land on
      Recommend immediately → context current → ask "what should I wear" → confirm the
      stylist doesn't ask for what the event already gave it. Document what was verified
      against a mock vs. a real Google Calendar connection, per spec.md's Assumptions.

---

## Dependencies & Execution Order

- **Phase 1 → Phase 2**: sequential (T001 → T002 → T003 → T004), all touch the same new file.
- **Phase 2 is a hard prerequisite for Phase 3 and Phase 4** — both need `pickedEventStore`'s
  `set`/`hydrate` to exist.
- **Phase 3 (US1) and Phase 4 (US2) touch different files** (`calendar/page.tsx` vs.
  `RecommendCalendarContext.tsx`) and could proceed in parallel once Phase 2 is done — but
  T011's manual validation depends on both being complete (a real "pick → land on Recommend
  with a correct label" pass needs both halves working together), so Phase 4 is sequenced
  after Phase 3 here for a single implementer's linear execution; a team could split them.
- **Phase 5 (US3) backend (T012–T013) and frontend (T014–T017) sub-tracks are independent of
  each other** and of Phases 3–4's files, but T016 depends on `pickedEventStore` (Phase 2) and
  T018's manual validation depends on the backend seed (T012) actually running.
- **Phase 6 depends on all of Phases 1–5.**

## Parallel Execution Examples

- Within Phase 2: T004 can start as soon as T003 lands (different file — the test file vs.
  the store module).
- Within Phase 5: T012/T013 (backend) and T014/T015 (frontend `Composer`) touch entirely
  different files and languages — fully parallelizable by two implementers or two agent
  sessions.
- T019 (schema drift check) can run any time after Phase 5's backend half (T012) — it doesn't
  depend on frontend work.

## Implementation Strategy

**MVP = User Story 1 alone** (Phases 1–3) already fixes the literal dead-end and the
discarded-PUT-result bug — the most user-visible half of issue #41. User Story 2 (Phase 4)
then removes the staleness a user would hit immediately after. User Story 3 (Phase 5) is the
"desired" outcome the issue names but is the one most tolerant of landing last, since Stories
1–2 alone already leave the app in a strictly better, non-broken state (today's status quo:
pick has no effect on styling — Story 3 changes that, but its absence isn't a regression).
Recommended order for a single implementer: Phases 1 → 2 → 3 → 4 → 5 → 6, exactly as listed.
