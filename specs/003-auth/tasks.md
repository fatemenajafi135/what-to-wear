---

description: "Task list for feature 003 — Auth"
---

# Tasks: Auth

**Input**: Design documents from `/specs/003-auth/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/whoami.md, quickstart.md — all present.

**Tests**: Included. The handoff (`docs/handoffs/003-auth.md` §10) explicitly requires backend
tests for valid/missing/invalid tokens and a full sign-up→sign-in→sign-out→sign-in Playwright
run; this repo's existing convention is a co-located `*.test.tsx` per component (see
`frontend/components/ui/Input/Input.test.tsx`).

**Organization**: Tasks are grouped by user story (spec.md's six stories), after a Foundational
phase that only the genuinely cross-cutting plumbing lives in — see plan.md's Constitution
Check and research.md §1/§4 for why route protection and the Supabase client wrappers can't be
split per-story without duplicating the redirect rule.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1–US6, matching spec.md's priorities (US1/US2/US5/US6 = P1, US3 = P2, US4 = P3)

## Path Conventions

Fixed layout per the constitution: `frontend/app/`, `frontend/components/`, `frontend/lib/`;
`backend/src/whattowear/`, `backend/tests/{unit,integration}`; `infra/supabase/`.

---

## Phase 1: Setup

- [ ] T001 Add `@supabase/supabase-js` and `@supabase/ssr` to `frontend/package.json`
      dependencies; `npm install` in `frontend/`
- [ ] T002 [P] Add `pyjwt>=2.9.0,<3.0.0` to `backend/pyproject.toml` `dependencies`, and
      `pytest-mock>=3.14.0,<4.0.0` to its `dev` group; `uv sync` in `backend/`
- [ ] T003 [P] Create `frontend/.env.example` with `NEXT_PUBLIC_SUPABASE_URL` and
      `NEXT_PUBLIC_SUPABASE_ANON_KEY` placeholders (values come from `npx supabase status`,
      never committed as real values)
- [ ] T004 [P] Add `SUPABASE_URL` and `SUPABASE_JWT_AUD=authenticated` placeholders to
      `backend/.env.example`, matching the existing file's comment style
- [ ] T005 [P] In `infra/supabase/config.toml`, raise `minimum_password_length` from `6` to
      `8` under `[auth]` (design-decisions §1.7 — the server must enforce what the client
      claims)
- [ ] T006 [P] In `infra/supabase/config.toml`, add an `[auth.external.google]` block
      (`enabled = true`, `client_id = "env(SUPABASE_AUTH_EXTERNAL_GOOGLE_CLIENT_ID)"`,
      `secret = "env(SUPABASE_AUTH_EXTERNAL_GOOGLE_SECRET)"`) and add both env var names as
      empty placeholders to `infra/.env.example` (create the file if it doesn't exist) — per
      handoff §2: wire it even with no real credentials, never delete or stub the button

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: No user story work can begin until this phase is complete. Every story below
either establishes a session through the Supabase client or depends on the redirect rule that
protects it — see research.md §1 and §4 for why this can't be split by story without
duplicating the rule six times.

- [ ] T007 [P] Create `frontend/lib/supabase/client.ts` — browser Supabase client,
      `flowType: 'pkce'`, reading `NEXT_PUBLIC_SUPABASE_URL`/`NEXT_PUBLIC_SUPABASE_ANON_KEY`
- [ ] T008 [P] Create `frontend/lib/supabase/server.ts` — Server Component / Route Handler
      Supabase client using `@supabase/ssr`'s `createServerClient`, reading/writing cookies
      via Next's `cookies()`
- [ ] T009 Create `frontend/lib/supabase/middleware.ts` — the session-refresh helper
      (`createServerClient` bound to the middleware `request`/`response` pair, calling
      `getUser()` so the refresh token rotates on every request) — depends on T007/T008's
      established client-construction pattern
- [ ] T010 Create `frontend/middleware.ts` — classifies each request path as auth-stack
      (`/signin`, `/signup`, `/forgot-password`, `/reset-password/*`) or authenticated-app
      (everything else except `/auth/callback`, which passes through), and redirects per
      FR-010/FR-011: signed-out + authenticated-app → `/signin`; signed-in + auth-stack →
      `/recommend`. Matcher excludes `_next/static`, `_next/image`, and files with an
      extension. Depends on T009.
- [ ] T011 [P] Create `frontend/components/auth/AuthShell.tsx` + `.module.css` — the shared
      auth-screen chrome: `role="main"`, full-bleed `max-width: 360px` mobile → centred
      tablet → `--color-surface` panel `max-width: 400px` desktop (design-system §5), slot
      for a promoted `<h1>` wordmark
- [ ] T012 [P] Create `frontend/lib/auth-validation.ts` — shared field validators
      (`field.required`, `field.email.invalid`, `field.password.tooShort` at 8 chars,
      `field.password.mismatch`), fires on blur only, re-validates on change once errored
      (design-decisions §1.7); exports the copy-key → message map
- [ ] T013 Create `frontend/app/(auth)/layout.tsx` using `AuthShell` and the existing
      `FocusOnNavigate` component (`frontend/components/shell/FocusOnNavigate.tsx` — already
      generic over any `main h1`, reused as-is) so focus moves to the wordmark on navigation
      between auth screens. Depends on T011.

**Checkpoint**: Foundation ready — route protection and the shared auth shell exist; user
story implementation can now begin.

---

## Phase 3: User Story 1 - Create an account and land in the app (Priority: P1) 🎯 MVP

**Goal**: A signed-out visitor can sign up with email + password and land signed-in on
`/recommend`.

**Independent Test**: Visit `/signup`, submit a new email + 8-char password, confirm landing
on `/recommend` and that a reload keeps the session.

### Tests for User Story 1

- [ ] T014 [P] [US1] Component test `frontend/components/auth/SignUpForm.test.tsx` —
      renders email/password/confirm fields, blur-fires validation, calls
      `supabase.auth.signUp` on submit, renders a `Banner` (`variant="error"`) on
      `auth.signup.error.body` without clearing entered values

### Implementation for User Story 1

- [ ] T015 [US1] Create `frontend/components/auth/SignUpForm.tsx` + `.module.css` — `Input`
      (email, password with show/hide toggle, confirm-password), `Button` in `stretch` mode,
      `Banner` above the form for form-level errors, field errors beneath their own field
      (design-decisions §1.2/§1.7); depends on T012
- [ ] T016 [US1] Create `frontend/app/(auth)/signup/page.tsx` — mounts `SignUpForm`, promotes
      the wordmark to `<h1>` (handoff §5.1 — no `TopHeader` on this screen); depends on T013,
      T015
- [ ] T017 [US1] On successful `signUp`, redirect client-side to `/recommend` (session cookie
      is already set by the Supabase client; middleware's redirect-away-from-auth-stack rule
      from T010 covers the server-rendered case on the next navigation)

**Checkpoint**: Sign-up works end to end and lands in the app.

---

## Phase 4: User Story 2 - Sign in with an existing account (Priority: P1)

**Goal**: A returning user signs in with email + password and lands on `/recommend`, the same
place every signed-in session lands.

**Independent Test**: Visit `/signin` with a real account's credentials, confirm landing on
`/recommend`.

### Tests for User Story 2

- [ ] T018 [P] [US2] Component test `frontend/components/auth/SignInForm.test.tsx` — renders
      email/password, calls `supabase.auth.signInWithPassword` on submit, renders a single
      `Banner` for `auth.signin.error.body` on a bad credential pair (not a field-level error)

### Implementation for User Story 2

- [ ] T019 [US2] Create `frontend/components/auth/SignInForm.tsx` + `.module.css` — mirrors
      `SignUpForm`'s shape minus the confirm field; depends on T012
- [ ] T020 [P] [US2] Create `frontend/components/auth/GoogleButton.tsx` — visual only, takes
      an `onClick` prop, standard four-colour Google "G" mark (handoff trap #4 — the design
      leaves the exact treatment open; record the choice in `docs/design-decisions.md` if it
      deviates). Shared by Sign in and Sign up.
- [ ] T021 [US2] Create `frontend/app/(auth)/signin/page.tsx` — mounts `SignInForm` +
      `GoogleButton` (onClick wired in US4), wordmark promoted to `<h1>`; also mount
      `GoogleButton` on `frontend/app/(auth)/signup/page.tsx` (T016) alongside `SignUpForm`,
      per FR-004's "both screens" requirement. Depends on T016, T019, T020.

**Checkpoint**: Sign-in works; `/signin` is the default signed-out destination.

---

## Phase 5: User Story 5 - Route protection and sign-out (Priority: P1)

**Goal**: Signed-out visitors never see authenticated content; signed-in visitors never see
auth screens; a signed-in user can sign out from Profile.

**Independent Test**: Request an authenticated route while signed out → redirected to
`/signin`. Sign out from Profile → next authenticated-route request redirects to `/signin`.

> The redirect *mechanism* (T010) is already built in Foundational because US1/US2/US3/US4 all
> depend on it existing to be independently testable. This phase adds the one remaining piece
> — sign-out — and the dedicated tests proving the mechanism holds in both directions.

### Tests for User Story 5

- [ ] T022 [P] [US5] Update `frontend/e2e/root-redirect.spec.ts` — two scenarios: signed-out
      `/` → `/signin`; signed-in `/` → `/recommend` (replaces the old single unconditional
      assertion, which tested feature 001's stub per FR-012)
- [ ] T023 [P] [US5] Create `frontend/e2e/route-protection.spec.ts` — signed-out visiting
      `/recommend` directly → `/signin`; signed-in visiting `/signin` directly → `/recommend`;
      sign out from `/profile` → next `/recommend` request → `/signin`

### Implementation for User Story 5

- [ ] T024 [US5] Update `frontend/app/page.tsx` — replace feature 001's unconditional
      `redirect("/recommend")` stub with a real check via the server Supabase client (T008):
      signed-out → `/signin`, signed-in → `/recommend` (FR-012)
- [ ] T025 [US5] Add a sign-out `Button` to `frontend/app/(app)/profile/page.tsx`, calling
      `supabase.auth.signOut()` then routing to `/signin`

**Checkpoint**: Route protection holds in both directions; sign-out works.

---

## Phase 6: User Story 3 - Reset a forgotten password (Priority: P2)

**Goal**: A user can request a reset email, follow the link, set a new password, and sign in
with it — landing on `/signin`, never auto-signed-in.

**Independent Test**: Request a reset for a known email, open the emailed link, set a new
password, confirm the old password no longer works and the new one does.

### Tests for User Story 3

- [ ] T026 [P] [US3] Component test `frontend/components/auth/ForgotPasswordForm.test.tsx` —
      submitting any email (registered or not) renders the same confirmation state in place,
      no route change
- [ ] T027 [P] [US3] Component test `frontend/components/auth/ResetPasswordForm.test.tsx` —
      covers all three states: form (valid token), error (invalid/expired token — resend link
      returns to `/forgot-password`), success (routes to `/signin`, never establishes a
      session)

### Implementation for User Story 3

- [ ] T028 [US3] Create `frontend/components/auth/ForgotPasswordForm.tsx` + `.module.css` —
      email field, `auth.forgot.sent.body`/`auth.forgot.sent.cta` confirmation state,
      `auth.forgot.error.body` on send failure; depends on T012
- [ ] T029 [US3] Create `frontend/app/(auth)/forgot-password/page.tsx`; depends on T013, T028
- [ ] T030 [US3] Create `frontend/components/auth/ResetPasswordForm.tsx` + `.module.css` —
      new-password + confirm-password fields (`stretch` submit), the error state's
      `auth.reset.error.body`/`.cta`, the success state's `auth.reset.success.body`/`.cta`;
      depends on T012
- [ ] T031 [US3] Create `frontend/app/(auth)/reset-password/[token]/page.tsx` — validates the
      token via the Supabase client, renders `ResetPasswordForm`'s appropriate state, routes
      to `/signin` on success without calling anything that establishes a session (FR-008);
      not linked from any in-app navigation (handoff trap #3). Depends on T030.

**Checkpoint**: Password reset completes end to end without crossing into the app.

---

## Phase 7: User Story 4 - Sign in or up with Google (Priority: P3)

**Goal**: A user can authenticate via Google from either `/signin` or `/signup`, returning
through the app's own `/auth/callback`.

**Independent Test**: Choose Google on `/signin`, complete consent, land on `/recommend` with
a session. (Requires a real Google OAuth client id — see T006. If unavailable, verify the
button reaches the provider and fails cleanly instead.)

### Tests for User Story 4

- [ ] T032 [P] [US4] Component test extension in `SignInForm.test.tsx`/`SignUpForm.test.tsx`
      — clicking `GoogleButton` calls `supabase.auth.signInWithOAuth` with
      `provider: 'google'` and `options.redirectTo` ending in `/auth/callback`

### Implementation for User Story 4

- [ ] T033 [US4] Wire `GoogleButton`'s `onClick` in both `SignInForm` and `SignUpForm` to
      `supabase.auth.signInWithOAuth`; depends on T020
- [ ] T034 [US4] Create `frontend/app/auth/callback/route.ts` — exchanges the auth code for a
      session (`exchangeCodeForSession`), redirects to `/recommend` on success; on failure or
      a cancelled consent, redirects to `/signin` with no session established and no error
      left in a broken authenticated state

**Checkpoint**: Google OAuth is wired and PKCE-correct, tested if a client id is available,
otherwise reported as untested per handoff §10.

---

## Phase 8: User Story 6 - Backend proves who is calling (Priority: P1)

**Goal**: A backend request carrying a valid session credential is verifiable; a missing or
invalid one is rejected identically.

**Independent Test**: Call the protected example endpoint with a valid/missing/tampered
credential and confirm the three outcomes from contracts/whoami.md.

### Tests for User Story 6

- [ ] T035 [P] [US6] `backend/tests/unit/test_auth.py` — mocked `_get_jwk_client`/`jwt.decode`
      covering missing, invalid-signature, expired, and valid-token cases (pattern confirmed
      working in `../app-legacy/backend/tests/unit/test_auth.py` — no live JWKS needed)
- [ ] T036 [P] [US6] `backend/tests/integration/test_whoami.py` — `TestClient` hits
      `GET /api/v1/whoami` with no header (401), a garbage header (401), and a mocked-valid
      token (200, `user_id` echoes the mocked `sub`)

### Implementation for User Story 6

- [ ] T037 [US6] Add `supabase_url: str` and `supabase_jwt_aud: str = "authenticated"` to
      `Settings` in `backend/src/whattowear/core/config.py`
- [ ] T038 [US6] Create `backend/src/whattowear/auth.py` — `get_current_user_id` FastAPI
      dependency, `PyJWKClient` against `{settings.supabase_url}/auth/v1/.well-known/jwks.json`,
      `algorithms=["ES256"]`, `audience=settings.supabase_jwt_aud`; adapted from
      `../app-legacy/backend/src/whattowear/auth.py` onto `get_settings()` rather than raw
      `os.environ`/`load_dotenv` (research.md §2). Depends on T037.
- [ ] T039 [US6] Create `backend/src/whattowear/api/v1/routes/whoami.py` — `WhoamiResponse`
      Pydantic model (`user_id: str`), `GET /api/v1/whoami` depending on
      `get_current_user_id`, per contracts/whoami.md. Depends on T038.
- [ ] T040 [US6] Register the route in `backend/src/whattowear/main.py`
      (`app.include_router(...)`, prefix `/api/v1`)

**Checkpoint**: Backend identity verification works end to end, proven by a real route, not
just the dependency's own unit tests.

---

## Phase 9: Polish & Cross-Cutting Concerns

- [ ] T041 [P] Create `frontend/e2e/auth-flow.spec.ts` — sign up → sign out → sign in → sign
      out, asserting each redirect (handoff §10's core Definition-of-Done scenario)
- [ ] T042 [P] Keyboard-only pass across all four auth screens: confirm `:focus-visible` (not
      bare `:focus`) on every control including the password show/hide `IconButton`, and that
      focus lands on the wordmark `<h1>` after navigation (T013's `FocusOnNavigate` reuse)
- [ ] T043 [P] Visual pass: every specified state (default/error/success/loading where
      applicable) of all four screens, both themes, at 320/768/1024/1440px (SC-007)
- [ ] T044 Update `docs/ios-verification-backlog.md` — confirm or correct the four
      anticipated auth items (5–8) against what was actually built, add anything new (handoff
      §9)
- [ ] T045 If `GoogleButton`'s treatment deviated from the standard four-colour mark, or any
      other genuine spec gap was found, record it in `docs/design-decisions.md` (handoff §11)
- [ ] T046 Run `uv run pytest && uv run ruff check . && uv run mypy src && uv run lint-imports`
      in `backend/`, and `npm run lint && npm run typecheck && npm run build && npm test` in
      `frontend/` — all must be clean
- [ ] T047 Run `quickstart.md`'s steps against a running local Supabase where this
      environment's Docker access allows it; explicitly record which steps could and could
      not be executed here (research.md §5)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies
- **Foundational (Phase 2)**: depends on Setup — BLOCKS every user story
- **US1, US2, US3, US4, US6 (Phases 3, 4, 6, 7, 8)**: depend only on Foundational; independent
  of each other
- **US5 (Phase 5)**: depends on Foundational (its core mechanism, T010, already lives there);
  its own two tasks (T024 sign-out, root redirect) have no dependency on US1–US4's forms, but
  T022/T023's e2e tests are most useful once US1/US2 exist to sign in with — recommended after
  Phase 3/4, not strictly required before
- **Polish (Phase 9)**: depends on all stories being complete

### Recommended Order

Foundational → US1 → US2 → US5 → US3 → US6 → US4 → Polish. US6 (backend) has no frontend
dependency and can run in parallel with any frontend story once Foundational is done.

### Parallel Opportunities

- T001–T006 (Setup) are all `[P]`
- T007/T008/T011/T012 (Foundational) are `[P]`; T009/T010/T013 are sequential on top of them
- Every story's `[P]`-marked test task can run alongside that story's sibling `[P]` tasks
- US6 (backend, Phase 8) can run in parallel with any frontend phase — no shared files

---

## Parallel Example: Foundational Phase

```bash
Task: "Create frontend/lib/supabase/client.ts"
Task: "Create frontend/lib/supabase/server.ts"
Task: "Create frontend/components/auth/AuthShell.tsx + .module.css"
Task: "Create frontend/lib/auth-validation.ts"
```

---

## Implementation Strategy

### MVP First

1. Setup (Phase 1) → Foundational (Phase 2) → US1 (Phase 3, sign-up) → US2 (Phase 4, sign-in)
   → US5 (Phase 5, route protection + sign-out)
2. **STOP and VALIDATE**: sign-up → reload → sign-out → sign-in works, protection holds both
   directions. This alone satisfies the handoff's core Definition-of-Done scenario.

### Incremental Delivery

3. Add US3 (password reset) → validate independently
4. Add US6 (backend identity) → validate independently — no frontend dependency, can slot in
   anywhere after Foundational
5. Add US4 (Google OAuth) → validate if a client id is available, else report wired-but-untested
6. Polish (Phase 9)

---

## Notes

- [P] tasks touch different files with no incomplete dependency
- Commit after each task or small logical group, on `003-auth`
- This environment cannot pull Docker images for `npx supabase start` (research.md §5) — tasks
  requiring a live local Supabase (parts of T041–T044, T047, and the "valid token" case's real
  JWT in T036) are implemented and unit-tested here with mocks, but their live verification is
  a manual follow-up step, reported honestly rather than claimed
