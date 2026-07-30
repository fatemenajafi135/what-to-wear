# Feature Specification: Auth

**Feature Branch**: `003-auth`

**Created**: 2026-07-29

**Status**: Draft

**Input**: User description: "003-auth: Ship the four auth screens (/signin, /signup, /forgot-password, /reset-password/:token), real Supabase authentication (email+password primary, Google OAuth secondary, PKCE flow), session persistence across reloads, route protection (unauthenticated -> /signin, authenticated visiting an auth route -> /recommend, / redirects per auth state replacing feature 001's unconditional redirect), an app-owned /auth/callback route, sign-out from Profile, and backend verification of the Supabase JWT (ported/adapted from ../app-legacy/backend/src/whattowear/auth.py) exposed as a FastAPI dependency plus one protected example route with tests for valid/missing/invalid tokens. Full scope, decisions already made, and traps are recorded in docs/handoffs/003-auth.md — use it as the primary source. Out of scope: closet/outfit/styling/calendar screens, profile/settings content beyond sign-out, password change/account deletion/data export, magic links/email OTP, service worker/offline, any cloud Supabase project."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Create an account and land in the app (Priority: P1)

A new visitor arrives signed out, creates an account with an email and password, and lands
in the authenticated app without any extra steps.

**Why this priority**: Nothing downstream of this feature exists without a way to become a
user. This is the floor the whole product depends on.

**Independent Test**: Visit `/signup` on a signed-out session, submit a valid email and an
8+ character password, and confirm the session lands on `/recommend` and survives a page
reload.

**Acceptance Scenarios**:

1. **Given** a signed-out visitor on `/signup`, **When** they submit a new email and a valid
   password, **Then** an account is created, a session is established, and they land on
   `/recommend`.
2. **Given** a signed-out visitor on `/signup`, **When** they submit details that fail
   sign-up (e.g. an email already in use), **Then** a form-level error banner explains the
   problem and no session is created.
3. **Given** a signed-up user with an active session, **When** they reload the page or
   restart the app, **Then** they remain signed in without re-entering credentials.

---

### User Story 2 - Sign in with an existing account (Priority: P1)

A returning user with an existing account signs in with email and password and reaches the
same place a signed-in user always lands.

**Why this priority**: Equally foundational to sign-up — most sessions after the first visit
are sign-ins, not sign-ups.

**Independent Test**: Visit `/signin` with a previously-registered account's credentials and
confirm the session lands on `/recommend`.

**Acceptance Scenarios**:

1. **Given** a signed-out visitor on `/signin`, **When** they submit the correct email and
   password for an existing account, **Then** a session is established and they land on
   `/recommend`.
2. **Given** a signed-out visitor on `/signin`, **When** they submit an email/password
   combination that does not match an account, **Then** a single form-level error explains
   the mismatch without revealing whether the email exists.
3. **Given** a signed-in user, **When** they navigate to `/signin` or `/signup` directly,
   **Then** they are redirected to `/recommend` instead of seeing the auth form.

---

### User Story 3 - Reset a forgotten password (Priority: P2)

A user who cannot remember their password requests a reset link by email, follows it, sets a
new password, and signs in with it — without ever landing inside the app mid-flow.

**Why this priority**: Password recovery is required for the product to be usable long-term,
but a fresh install can launch and be demoed without it.

**Independent Test**: From `/signin`, request a password reset for a known email, open the
emailed link, set a new password on `/reset-password/:token`, and confirm sign-in with the
new password succeeds while the old password no longer works.

**Acceptance Scenarios**:

1. **Given** a visitor on `/forgot-password`, **When** they submit an email, **Then** the
   screen shows a confirmation state (not a route change) that neither confirms nor denies
   the email is registered, and an email is sent if the account exists.
2. **Given** a user who opens a valid, unexpired reset link, **When** they land on
   `/reset-password/:token`, **Then** they see a form to set a new password and confirm it.
3. **Given** a user who submits a valid new password on `/reset-password/:token`, **When**
   the update succeeds, **Then** they are routed to `/signin` — never signed in
   automatically and never routed into the authenticated app.
4. **Given** a user who opens an expired or already-used reset link, **When**
   `/reset-password/:token` loads, **Then** they see an error state with a way back to
   `/forgot-password` to request a new link.
5. **Given** any signed-in or signed-out user, **When** they look for a way to reach
   `/reset-password/:token` from in-app navigation, **Then** no such link exists — it is only
   reachable from the emailed link.

---

### User Story 4 - Sign in or up with Google (Priority: P3)

A user chooses to authenticate with their Google account instead of typing a password.

**Why this priority**: Specified as the secondary flow — valuable, but the product is fully
usable without it, and it depends on an external credential the team may not have yet (see
Assumptions).

**Independent Test**: From `/signin` or `/signup`, choose the Google option, complete the
provider's consent flow, return to the app via `/auth/callback`, and land on `/recommend`
with a session established.

**Acceptance Scenarios**:

1. **Given** a signed-out visitor on `/signin` or `/signup`, **When** they choose the Google
   option and complete consent, **Then** they return to the app through `/auth/callback` and
   land on `/recommend` with a session established.
2. **Given** the OAuth exchange fails or is cancelled partway, **When** the visitor returns
   to the app, **Then** they see a clear error and remain signed out rather than landing in a
   broken authenticated state.

---

### User Story 5 - Route protection and sign-out (Priority: P1)

The app never shows authenticated content to a signed-out visitor, never shows the auth
screens to a signed-in user, and lets a signed-in user sign out on demand.

**Why this priority**: Without this, every other feature that assumes "who is this?" has an
answer is unsafe to build on.

**Independent Test**: As a signed-out session, request any authenticated route directly and
confirm a redirect to `/signin`; as a signed-in session, sign out from Profile and confirm
the next request for an authenticated route redirects to `/signin`.

**Acceptance Scenarios**:

1. **Given** a signed-out visitor, **When** they request any route that requires a session
   (including `/`), **Then** they are redirected to `/signin`.
2. **Given** a signed-in user, **When** they request `/`, **Then** they land on `/recommend`.
3. **Given** a signed-in user on Profile, **When** they choose sign out, **Then** their
   session ends and the next request for an authenticated route redirects to `/signin`.

---

### User Story 6 - Backend proves who is calling (Priority: P1)

A backend request carrying a session's credentials is verifiable server-side, so downstream
features can trust the caller's identity without re-implementing verification themselves.

**Why this priority**: Feature 004 and everything after it depends on this existing; without
it no backend feature can be built safely.

**Independent Test**: Call the protected example endpoint with a valid session's credentials
and confirm it succeeds and identifies the caller; call it with no credentials and with
tampered credentials and confirm both are rejected.

**Acceptance Scenarios**:

1. **Given** a request carrying a valid, unexpired session credential, **When** it reaches a
   protected endpoint, **Then** the request is accepted and the caller's identity is
   available to the endpoint.
2. **Given** a request with no credential, **When** it reaches a protected endpoint, **Then**
   it is rejected without revealing whether a resource exists.
3. **Given** a request with an invalid, malformed, or expired credential, **When** it reaches
   a protected endpoint, **Then** it is rejected the same way as a missing credential.

---

### Edge Cases

- What happens when a user submits the sign-up or sign-in form with a password shorter than
  the minimum? Field-level validation blocks submission before any request is sent.
- What happens when a user requests a password reset for an email with no account? The
  confirmation state shows regardless, so an attacker cannot enumerate registered emails.
- What happens when a user opens a reset link twice, or opens it after already resetting
  their password once? The second attempt shows the expired/invalid error state.
- What happens when a signed-in user's session expires while they are active in the app? The
  next request that depends on a valid session redirects them to `/signin` rather than
  silently failing.
- What happens when Google OAuth is not configured (no client credentials available in a
  given environment)? The Google option remains visible and wired; choosing it fails at the
  provider-consent step with a clear error rather than being hidden or removed.
- What happens when a user closes the OAuth consent flow without completing it? They return
  to the auth screen they started from, still signed out, with no error persisted.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide four auth routes — `/signin`, `/signup`,
  `/forgot-password`, `/reset-password/:token` — matching the design system's auth stack,
  identical in structure across mobile, tablet and desktop.
- **FR-002**: System MUST let a visitor create an account with an email and a password of at
  least 8 characters, both client-validated and server-enforced.
- **FR-003**: System MUST let a visitor with an existing account sign in with email and
  password.
- **FR-004**: System MUST offer Google as a secondary sign-in/sign-up method on `/signin` and
  `/signup`, returning through an app-owned `/auth/callback` route rather than a
  provider-hosted or auth-service-hosted page.
- **FR-005**: System MUST NOT offer or send a magic link, or any other passwordless
  email-link sign-in, anywhere in the product.
- **FR-006**: System MUST let a visitor request a password-reset email from
  `/forgot-password`, showing a confirmation state in place (not a route change) that gives
  the same response whether or not the email is registered.
- **FR-007**: System MUST let a user reach `/reset-password/:token` only via the emailed
  link (no in-app navigation entry point), and MUST render exactly one of three states there:
  a form to set and confirm a new password, an error state for an invalid/expired token, or a
  success state.
- **FR-008**: System MUST route a user who completes a password reset to `/signin`, and MUST
  NOT establish a session automatically as part of that flow.
- **FR-009**: System MUST persist an established session across page reloads and app
  restarts without requiring the user to re-authenticate.
- **FR-010**: System MUST redirect a signed-out visitor away from any authenticated route
  (including `/`) to `/signin`.
- **FR-011**: System MUST redirect a signed-in user away from any auth route to `/recommend`.
- **FR-012**: System MUST redirect `/` to `/signin` when signed out and to `/recommend` when
  signed in.
- **FR-013**: System MUST let a signed-in user sign out from Profile, ending their session
  such that the next authenticated-route request redirects to `/signin`.
- **FR-014**: System MUST verify a caller's session credential on the backend independently
  (signature verification, not a trust-the-client shortcut) and expose the verified caller
  identity to backend request handlers.
- **FR-015**: System MUST reject backend requests to protected endpoints that carry a
  missing, malformed, invalid-signature, or expired credential, all as an equivalent
  unauthorized failure.
- **FR-016**: System MUST include at least one protected backend endpoint, beyond the
  verification mechanism itself, that demonstrates the mechanism rejecting a missing token,
  rejecting an invalid token, and accepting a valid one.
- **FR-017**: System MUST render every specified state of all four auth screens (including
  error and success states) in both light and dark themes.
- **FR-018**: System MUST show form-level errors (e.g. "email and password don't match") in a
  single banner-style element above the form, distinct from field-level validation errors
  shown beneath their own field.
- **FR-019**: System MUST validate each field on blur, not on every keystroke, and
  re-validate on change once a field has already errored.
- **FR-020**: Auth screens without a page header (`/signin`, `/signup`) MUST expose the
  product wordmark as the page's single top-level heading.
- **FR-021**: All interactive controls on auth screens MUST be reachable and operable by
  keyboard alone, with a visible focus indicator on keyboard navigation that does not appear
  on mouse-driven focus.

### Key Entities

- **Account**: A registered user identity — an email address and a credential (password
  and/or a linked Google identity). Owns exactly one session at a time from the app's
  perspective; the app does not display or manage multiple concurrent sessions.
- **Session**: The proof that a request or a browser tab currently represents a specific
  signed-in Account. Has a lifetime, can expire, and can be ended deliberately (sign-out).
- **Password reset request**: A one-time, time-limited link tied to an Account's email,
  usable exactly once to set a new credential, after which it is invalid.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A new visitor can go from `/signup` to a usable, signed-in `/recommend` screen
  in under 60 seconds of form interaction.
- **SC-002**: 100% of direct requests to an authenticated route while signed out result in
  landing on `/signin`, with no authenticated content ever rendered first.
- **SC-003**: 100% of direct requests to an auth route while signed in result in landing on
  `/recommend`, with no auth form ever rendered first.
- **SC-004**: A signed-in session survives an arbitrary page reload or app restart with no
  observable re-authentication prompt, for as long as the underlying session has not expired
  or been signed out.
- **SC-005**: A user who completes the password-reset flow can sign in with the new password
  and cannot sign in with the old one, 100% of the time.
- **SC-006**: A backend request to a protected endpoint with a tampered or missing credential
  is rejected 100% of the time; a request with a valid credential is accepted and correctly
  identifies the caller 100% of the time.
- **SC-007**: Every one of the four auth screens' specified states is visually verifiable in
  both themes at 320/768/1024/1440px, with no missing or visually broken state.

## Assumptions

- Email/password is the primary flow and Google OAuth is secondary, per
  `docs/design-decisions.md` §12 — this is a recorded decision, not an open question.
- Magic-link and email-OTP sign-in are permanently out of scope, per the same decision;
  nothing in this spec introduces either.
- A Google Cloud OAuth client ID/secret may not be available in every environment this
  feature is built and verified in. Where it is not, the Google option is still fully built,
  wired, and left visible — it is reported as untested rather than removed or stubbed. This
  is an explicit exception to "all acceptance scenarios verified": User Story 4 may ship
  verified only against a local Supabase project's default (non-functional) OAuth
  configuration in some environments.
- "Local only" — this feature targets a local Supabase project. No cloud Supabase project is
  provisioned or targeted as part of this work.
- Installed-iOS-specific behavior (e.g. the storage-container isolation that rules out magic
  links) cannot be verified without a physical device in this environment; those items are
  built to spec and recorded in `docs/ios-verification-backlog.md` rather than tested here,
  per `docs/design-decisions.md` §12 and the feature handoff.
- The four auth screens' visual content (layout, copy, tokens) is fully specified in
  `design/design-system.md` and `docs/design-decisions.md` §1 and §12; this spec does not
  restate that content, only the behavior it must satisfy.
- Profile and Settings screens beyond a sign-out control are out of scope, per
  `design/known-gaps.md` §0.6 — sign-out is included here only as the minimal control needed
  to satisfy User Story 5.
