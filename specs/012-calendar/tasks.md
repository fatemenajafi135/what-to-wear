---

description: "Task list for feature 012: Calendar"

---

# Tasks: Calendar

**Input**: Design documents from `/specs/012-calendar/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/calendar.md,
quickstart.md

**Tests**: Included — the handoff requires the RLS isolation proof as an automated test
(mirroring feature 004's `test_wardrobe_rls.py`) and requires the existing 459 backend tests
to keep passing, so test tasks are not optional here.

**Environment note**: This session's sandboxed network cannot reach Docker Hub/GHCR (blocked
by egress policy, confirmed even for `hello-world` — see research.md §8), so `npx supabase
start` cannot run here. A bare-Postgres harness (real PostgreSQL 16, Supabase's `auth.uid()`
and role convention reproduced by hand, listening on the canonical port 54322) stands in for
it in this session, making the integration/RLS tasks below genuinely runnable — see the
feature report for exactly what that harness does and does not substitute for (no real GoTrue,
no real Google OAuth token exchange without live credentials).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US4)

## Path Conventions

- **Frontend**: `frontend/app/(app)/calendar/`, `frontend/app/calendar/callback/`,
  `frontend/components/calendar/`, `frontend/lib/calendar/`, `frontend/lib/api/`
- **Backend**: `backend/src/whattowear/`, tests in `backend/tests/{unit,integration}`
- **Infra**: `infra/supabase/migrations/`

---

## Phase 1: Setup

- [ ] T001 [P] Add `cryptography` to `backend/pyproject.toml` dependencies; `uv sync`
- [ ] T002 [P] Add `WTW_TOKEN_ENCRYPTION_KEY`, `GOOGLE_OAUTH_CLIENT_ID`,
      `GOOGLE_OAUTH_CLIENT_SECRET`, `GOOGLE_OAUTH_REDIRECT_URI` (blank) to
      `backend/.env.example`, with a comment on how to generate the encryption key
      (`Fernet.generate_key()`) and that the redirect URI is an app route, never
      provider-hosted (design-decisions §12)
- [ ] T003 [P] Add `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET` (blank) to
      `infra/.env.example`, documenting they're shared with feature 003's sign-in client
      (docs/handoffs/012-calendar.md §2)
- [ ] T004 Add `token_encryption_key`, `google_oauth_client_id`,
      `google_oauth_client_secret`, `google_oauth_redirect_uri` fields to `Settings` in
      `backend/src/whattowear/core/config.py`, all optional (`str | None = None`) so
      `get_settings()` doesn't fail for callers that don't need them (matching the existing
      AI-layer-key pattern)

**Checkpoint**: tooling and config in place; no product code yet.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Migration, token encryption, the Google adapter, the repository, and the routes
— every user story needs real connect/disconnect/event-fetch plumbing before its screen
behavior can be verified.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T005 Write `infra/supabase/migrations/0004_calendar.sql` per `data-model.md`:
      `calendar_connections`, `calendar_oauth_attempts`, `picked_events` tables, each with
      RLS enabled and a `for all using (auth.uid() = user_id) with check (auth.uid() =
      user_id)` policy, `updated_at` trigger on `calendar_connections`, and the
      `grant select, insert, update, delete ... to authenticated` on all three (0002's
      documented convention — silently unreachable without it)
- [ ] T006 Apply migration `0004` against the local Postgres harness and confirm it
      reproduces cleanly from the existing schema (§10 checklist item 1's spirit; full
      `npx supabase db reset` replay is deferred to whoever next runs this with working
      Docker — see feature report)
- [ ] T007 [P] Implement `backend/src/whattowear/adapters/token_encryption.py`:
      `encrypt(plaintext: str) -> str` / `decrypt(ciphertext: str) -> str` wrapping `Fernet`,
      raising a clear error if `WTW_TOKEN_ENCRYPTION_KEY` is unset (research.md §2)
- [ ] T008 [P] `backend/tests/unit/test_token_encryption.py` — round-trip encrypt/decrypt,
      and the clear-error-when-unset case
- [ ] T009 [P] Implement `backend/src/whattowear/adapters/google_calendar.py`: pure HTTP
      functions (via `requests`) for (a) building the authorization URL with PKCE challenge,
      (b) exchanging `code`+`code_verifier` for tokens, (c) refreshing an access token from a
      refresh token, (d) listing primary-calendar events in a date range — no route/DB code,
      matching the AI-independence contract's spirit of framework-free adapters (research.md
      §1/§4/§5)
- [ ] T010 [P] `backend/tests/unit/test_google_calendar_adapter.py` — each function against
      a mocked `requests` call: correct PKCE params on the authorize URL, correct token
      exchange/refresh request shape, correct event-list query params (primary calendar,
      7-day window, `maxResults=20`), and that no function ever logs a token/code value
- [ ] T011 Implement `backend/src/whattowear/repositories/supabase_calendar.py`:
      `SupabaseCalendarRepository` with `get_connection`, `start_oauth_attempt`,
      `finish_oauth_attempt` (looks up + deletes the `calendar_oauth_attempts` row,
      encrypts and upserts into `calendar_connections`), `disconnect` (deletes both
      `calendar_connections` and `picked_events` rows), `get_valid_access_token` (decrypts,
      refreshes-and-re-encrypts-if-expired via the adapter, deletes the connection row and
      returns `None` on refresh failure per research.md §6), `get_picked_event`,
      `set_picked_event` (upsert) — every method sets `request.jwt.claim.sub` first, matching
      `supabase_closet.py`'s `_set_jwt_claim` convention
- [ ] T012 [P] `backend/tests/unit/test_supabase_calendar_repository.py` — mocked-session
      tests per method: connect upserts, disconnect deletes both tables, refresh failure
      clears the connection and returns `None`, picked-event upsert
- [ ] T013 Implement `backend/src/whattowear/api/v1/routes/calendar.py`: the 7 routes from
      `contracts/calendar.md` (`GET /connection`, `POST /connect/start`,
      `POST /connect/finish`, `POST /disconnect`, `GET /events`, `GET /picked-event`,
      `PUT /picked-event`), all behind `get_current_user_id`, response models per the
      contract, `409` when `/events` is called disconnected, `502` on a live Google-call
      failure, generic `400` detail on `/connect/finish` failure (never echoes Google's error
      body or the code/verifier), `503` on `/connect/start` when
      `GOOGLE_OAUTH_CLIENT_ID`/`SECRET` are unset (FR-017) — never a raw 500
- [ ] T014 Register `calendar_router` in `backend/src/whattowear/main.py` alongside the
      existing `closet_router`/`whoami_router` (or just `whoami_router` if 004 hasn't merged
      yet — additive either way)
- [ ] T015 [P] `backend/tests/integration/test_calendar_routes.py` — 401 with no token; 200
      shapes for connection/events/picked-event against a real Postgres; 409 on `/events`
      when disconnected; idempotent `/disconnect`; 503 on `/connect/start` with
      `GOOGLE_OAUTH_CLIENT_ID` unset (FR-017)
- [ ] T016 `backend/tests/integration/test_calendar_rls.py` — mirrors
      `test_wardrobe_rls.py` exactly (direct port, `authenticator` role, `SET ROLE
      authenticated`, session-scoped `request.jwt.claim.sub`): two seeded users each see only
      their own `calendar_connections` row, only their own `picked_events` row, and a
      connection with no claim set sees nothing (research.md §9)
- [ ] T017 Run `uv run pytest backend/tests -q` and confirm the existing 459+ tests are still
      green plus the new tests above, before continuing (§10 checklist "backend test count
      has not dropped")
- [ ] T018 [P] Add `NEXT_PUBLIC_API_URL` usage confirmation / regenerate
      `frontend/lib/api/schema.d.ts` via `npm run generate:api-types` against the running
      backend (Constitution VII — no hand-written duplicate of any `contracts/calendar.md`
      shape)
- [ ] T019 [P] Implement `frontend/lib/calendar/primed.ts`: `isCalendarPrimed()` /
      `setCalendarPrimed()` reading/writing `wtw_calendar_primed` in `localStorage`
      (known-gaps.md §-2)
- [ ] T020 [P] Implement `frontend/lib/calendar/formatEventTime.ts`: pure function computing
      the Today/Tomorrow/weekday/short-date label plus a locale-aware time string from an ISO
      timestamp (research.md §7, design-system "Date & time formats")
- [ ] T021 [P] `frontend/lib/calendar/formatEventTime.test.ts` — Today, Tomorrow, a weekday
      within 6 days, and a short date beyond that, using a fixed mocked "now"
- [ ] T022 Implement `frontend/lib/calendar/useCalendarConnection.ts`: a hook exposing
      `{ connected, connectedAt, isLoading, connect(), disconnect() }` — `connect()` calls
      `POST /connect/start`, redirects via `window.location.assign`; `disconnect()` calls
      `POST /disconnect` and refetches connection state. This is the shared module both
      `/calendar` and (once feature 013 merges) Settings' Connected-accounts row consume, per
      the handoff's "two entry points, one state" requirement
- [ ] T023 [P] `frontend/lib/calendar/useCalendarConnection.test.ts` — connect/disconnect
      call the right endpoints and update state; a failed disconnect leaves state unchanged

**Checkpoint**: Backend fully wired and tested; shared frontend connection state ready to
consume. User story work can now begin.

---

## Phase 3: User Story 1 - Connect Google Calendar (P1)

**Goal**: A user with no calendar connection sees the disconnected card, connects through the
primer + PKCE flow, and the connection persists.

**Independent Test**: Visit `/calendar` signed in as a fresh user, confirm the disconnected
card, trigger connect, confirm the primer appears once then not again, and confirm a completed
connection is reflected back on `/calendar`.

- [ ] T024 [US1] Implement `frontend/components/calendar/CalendarPrimer.tsx`: bespoke
      `<dialog>`-based card (real modal semantics via `showModal()`, matching
      `BottomSheet.tsx`'s pattern) with the title/body/actions from design-decisions §18,
      "Continue to Google" (primary) and "Not now" (secondary/dismiss)
- [ ] T025 [P] [US1] `frontend/components/calendar/CalendarPrimer.test.tsx` — renders title/
      body/both actions, "Continue to Google" and "Not now" each fire their callback, focus
      moves to the dialog on open
- [ ] T026 [US1] Implement `frontend/app/(app)/calendar/page.tsx` disconnected state: icon
      tile, `calendar.disconnected.title`/`.body`/`.cta` from design-system §6, wired to
      `useCalendarConnection().connect` gated behind the primer (skip the primer if
      `isCalendarPrimed()` is already true, per FR-002)
- [ ] T027 [US1] Implement `frontend/app/calendar/callback/route.ts`: extracts `code`/`state`
      from the query string, calls `POST /connect/finish`, redirects to `/calendar`
      regardless of outcome (success shows connected; failure leaves the disconnected card,
      per spec's Story 1 acceptance scenario 5 — no partial/broken connection persisted)
- [ ] T028 [P] [US1] `frontend/app/(app)/calendar/page.test.tsx` (disconnected-state cases):
      renders the disconnected card copy, connect button triggers the primer on first use,
      skips the primer on a subsequent use
- [ ] T029 [US1] Manual/local verification against a real Google Cloud OAuth client if one is
      available in this environment (docs/handoffs/012-calendar.md §2) — record in the
      feature report whether this ran or was only wired

**Checkpoint**: User Story 1 independently functional and testable (fixture/mocked
`useCalendarConnection` for the UI; real backend routes underneath).

---

## Phase 4: User Story 2 - See events and pick one to style for (P1)

**Goal**: A connected user with upcoming events sees them, picks one, all rows disable, and
the pick surfaces on `/recommend`.

**Independent Test**: As a connected user with fixture/live events, open `/calendar`, confirm
computed date/time labels render, pick a row, confirm all rows disable, and confirm
`/recommend` shows "Styling for {event} · Change".

- [ ] T030 [US2] Implement `frontend/components/calendar/EventRow.tsx`: title line + `{time}
      · {location}` meta line (using `formatEventTime`), `disabled` prop applying `opacity:
      0.5; cursor: not-allowed` per design-system §6 (no "selected" visual state)
- [ ] T031 [P] [US2] `frontend/components/calendar/EventRow.test.tsx` — renders computed
      label (not a hardcoded string), omits the `· {location}` segment cleanly when location
      is absent, disabled prop applies the specified styles
- [ ] T032 [US2] Extend `frontend/app/(app)/calendar/page.tsx` with the connected-with-events
      state: `calendar.list.hint` caption + stacked `EventRow`s fetched from `GET /events`;
      picking a row calls `PUT /picked-event` then re-renders every row disabled
- [ ] T033 [US2] Add the calendar-context line to the `/recommend` stub
      (`frontend/app/(app)/recommend/page.tsx`): "Style for an event from calendar" link when
      `GET /picked-event` returns `picked: false`, "Styling for {event} · Change" (with the
      calendar glyph) when `picked: true` — the only change to this file; the rest of the stub
      (chat/hero content) stays feature 008's territory
- [ ] T034 [P] [US2] `frontend/app/(app)/recommend/page.test.tsx` — both context-line states
      render correctly given a mocked `GET /picked-event` response
- [ ] T035 [US2] "Change" on `/recommend` navigates back to `/calendar`

**Checkpoint**: User Stories 1-2 together deliver the feature's core payoff end to end.

---

## Phase 5: User Story 3 - Empty and error calendars (P2)

**Goal**: A connected user with no upcoming events, or a real sync failure, sees the correct
state — never a blank or ambiguous screen, and never a double-messaged offline+error.

**Independent Test**: Force `GET /events` to return `events: []` and confirm the empty state
and its bypass button; force a `502`/network failure and confirm the error state and retry;
force `navigator.onLine === false` and confirm the screen suppresses its own error in favor of
the global offline banner.

- [ ] T036 [US3] Extend `frontend/app/(app)/calendar/page.tsx` with the connected-empty state
      (`calendar.empty.body`/`.cta` → `/recommend` directly, bypassing the event list) and
      the error state (`calendar.error.body`/`.cta` → retry), plus the Calendar skeleton
      (two 56px blocks, 14px radius) for loading
- [ ] T037 [US3] Wire the screen's error-vs-offline precedence: suppress the screen-level
      error and rely on the existing global offline `Banner` when `navigator.onLine` is
      `false`, matching feature 004's established pattern for `/closet`
- [ ] T038 [P] [US3] `frontend/app/(app)/calendar/page.test.tsx` (empty/error/offline cases):
      each state renders its specified copy and action; offline suppresses the error state

**Checkpoint**: All four `/calendar` states plus loading/offline are complete and tested.

---

## Phase 6: User Story 4 - Disconnect from either entry point (P2)

**Goal**: Disconnecting from Settings → Connected accounts (or `/calendar`'s own shared state)
is reflected everywhere, and clears any picked event.

**Independent Test**: As a connected user with a picked event, call `disconnect()` through
`useCalendarConnection`, confirm `GET /connection` now returns `connected: false`, confirm
`GET /picked-event` now returns `picked: false`, and confirm `/recommend`'s context line
reverts.

- [ ] T039 [US4] Confirm (already true by construction from T011/T013) that
      `POST /disconnect` deletes both `calendar_connections` and `picked_events` server-side
      in one call — add an integration-test case to `test_calendar_routes.py` asserting
      `GET /picked-event` returns `picked: false` immediately after disconnect
- [ ] T040 [US4] Document, in the feature report, exactly what `ConnectedAccountsSection.tsx`
      (feature 013's branch, not yet merged into `rebuild`) needs once merged: a "Connected"
      `Badge` + "Disconnect" text action (design-decisions §17) both wired to
      `useCalendarConnection()` — this feature does not touch that file since it doesn't
      exist on this branch (handoff §2/013 handoff §7)
- [ ] T041 [P] [US4] `frontend/lib/calendar/useCalendarConnection.test.ts` (extend T023):
      after `disconnect()`, `connected` is `false` and a subsequent `/recommend` context-line
      read reflects the unpicked prompt

**Checkpoint**: Both entry points' shared state is proven to actually stay in sync — not just
built to look like it does.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T042 [P] Add `docs/design-decisions.md` §16-18 references into this feature's report
      (already written during planning — confirm nothing drifted during implementation)
- [ ] T043 [P] Add the calendar-redirect iOS item to `docs/ios-verification-backlog.md`,
      matching the existing `/auth/callback` entries' shape (design-decisions §12 precedent)
- [ ] T044 Run the full backend gate: `uv run pytest && uv run ruff check . && uv run ruff
      format --check . && uv run mypy src && uv run lint-imports`
- [ ] T045 Run the full frontend gate: `npm run lint && npm run typecheck && npm run build &&
      npm test`
- [ ] T046 Manual pass of all four `/calendar` states in both themes at
      320/768/1024/1440px (§10 checklist item 3) — record exactly how each was driven
      (fixture vs. live) in the feature report
- [ ] T047 Keyboard-only pass of `/calendar` and the primer: tab order, focus-visible ring
      present on keyboard nav and absent on mouse click, focus trapped in the primer while
      open and restored to the invoking control on close (§10 checklist item 9)
- [ ] T048 Confirm exactly one `<h1>` on `/calendar` (`TopHeader`'s title) and that the
      `/recommend` change didn't introduce a second one
- [ ] T049 Grep the diff for `access_token`/`refresh_token`/`code_verifier` outside
      `token_encryption.py`/`google_calendar.py`/tests to confirm no token ever reaches a log
      line, tracked file, or API response body (§10 checklist item 8, FR-005)
- [ ] T050 Write the feature completion report per handoff §12: what was built, whether OAuth
      was tested or only wired, token storage rationale, exact `/recommend` diff, unmet
      Constitution Check gates (if any), §10 checklist results, and everything recorded in
      `design-decisions.md`

---

## Dependencies & Execution Order

- **Phase 1 (Setup)** → **Phase 2 (Foundational)**: strictly sequential, blocks everything.
- **Phase 3 (US1)** can start once Phase 2 is done. **Phase 4 (US2)** depends on US1's
  `useCalendarConnection`/connected-state plumbing existing, but its own event-list/picked-
  event code is independent of US1's primer/callback code — buildable in parallel by a second
  contributor once Phase 2 is merged.
- **Phase 5 (US3)** and **Phase 6 (US4)** both extend the same `page.tsx` US1/US2 create —
  sequential after US2 in practice, though their acceptance criteria are independent of each
  other.
- **Phase 7 (Polish)** last, after all user stories.

## Parallel Execution Examples

- Within Phase 2: T007-T010 (encryption + Google adapter, both new files with no shared
  state) run in parallel; T012/T015/T016 (three independent test files) run in parallel once
  T011/T013 land.
- Within Phase 3: T024-T025 (primer component + its test) in parallel with T027 (callback
  route) — different files, no shared dependency until T026 wires them together.

## Implementation Strategy

**MVP = User Story 1 + User Story 2** (P1 both): a user can connect, see events, pick one, and
have it surface on Recommend — the feature's stated Mission end to end. User Stories 3-4 (P2)
harden the edges (empty/error states, disconnect sync) and can ship as a fast-follow if time is
short, but per the handoff's Definition of Done they are expected in the same PR, not deferred.
