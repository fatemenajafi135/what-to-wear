# Research: Calendar

## 1. OAuth architecture — a second, app-orchestrated flow, not Supabase's `signInWithOAuth`

**Decision**: Calendar connection is a separate OAuth 2.0 Authorization Code + PKCE exchange
that this app's own backend performs directly against Google's endpoints
(`accounts.google.com/o/oauth2/v2/auth` → `oauth2.googleapis.com/token`) — not
`supabase.auth.signInWithOAuth()`. The redirect lands on a new app route, `/calendar/callback`
(a Next.js Route Handler), distinct from feature 003's `/auth/callback`.

**Rationale**: Feature 003's Google OAuth establishes a Supabase *session* — proving identity.
This feature needs a Google Calendar *access token* usable by the backend on the user's behalf,
persisted well beyond the moment of sign-in, refreshable independently, and never conflated
with the user's own session credential. Supabase's `signInWithOAuth()` can request extra scopes
and briefly exposes `session.provider_token`/`provider_refresh_token` right after the redirect,
but Supabase does not persist or refresh these for later reuse — the app would still have to
capture and store them itself, while also fighting the fact that a second `signInWithOAuth()`
call for an *already-signed-in* user re-triggers identity sign-in semantics (linked-identity
edge cases, a second session cookie write) for a completely different purpose: granting
calendar access, not proving who the user is. Doing our own PKCE exchange, scoped to exactly
what this feature needs, avoids both problems and keeps identity (003's concern) and
third-party API access (this feature's concern) as two clearly separate mechanisms.

**Alternatives considered**:
- **`supabase.auth.signInWithOAuth({ scopes: 'calendar.events.readonly' })` on the
  already-signed-in user, reading `session.provider_token` afterward.** Rejected: Supabase
  does not refresh `provider_token` after the initial grant — this feature explicitly needs a
  working refresh path (spec's Edge Cases: "the next request that needs it attempts a silent
  refresh"), so the app would have to capture, store, and refresh the token itself regardless.
  At that point the only thing Supabase's flow is buying is the initial code exchange, at the
  cost of re-entering the sign-in code path for a non-sign-in purpose.
- **A Supabase Edge Function as the token-exchange endpoint instead of the FastAPI backend.**
  Rejected: this project's data/auth layer is Supabase, but its API layer is the FastAPI
  backend (constitution's Technology Constraints) — introducing a second serverless runtime
  for one feature's OAuth exchange duplicates the `Settings`/`get_settings()` pattern, secret
  handling, and error conventions the FastAPI backend already has, for no benefit.

## 2. OAuth token storage — encrypted at rest, not plaintext, not RLS-alone

**Decision**: `access_token` and `refresh_token` are encrypted at the application layer with
`cryptography`'s `Fernet` (AES-128-CBC + HMAC, authenticated symmetric encryption) before being
written to `calendar_connections`, using a key read from a new required setting,
`WTW_TOKEN_ENCRYPTION_KEY` (added blank to `.env.example`, generated locally with
`Fernet.generate_key()`, never committed). Decryption happens only inside the repository layer,
immediately before a live Google API call; the plaintext token is never returned from any
repository method beyond that call site, never serialized into a Pydantic response model, and
never logged.

**Rationale**: `specs/004-closet-read/research.md` §1 (read per this feature's handoff)
establishes that RLS is *not* the real isolation guarantee for this backend's own traffic — the
pooler role it connects as has `BYPASSRLS`, so Postgres skips policy evaluation for every query
this app issues. For an ordinary wardrobe item, the query-level `WHERE user_id = ...` filter is
an acceptable sole guarantee. A third-party OAuth token is a materially different kind of data:
it's a credential usable outside this application entirely (directly against Google's API), and
the same finding that makes RLS a no-op for this app's connection also means RLS alone would do
nothing to protect it from anyone with that same bypass-privileged connection (Supabase Studio
using the service key, a database backup, a misconfigured future access path). Application-layer
encryption is a second, independent barrier that specifically survives all of those — reading
the raw column without the encryption key yields ciphertext, not a usable Google credential.

**Alternatives considered**:
- **Plaintext in Postgres, RLS as the only guard.** Rejected per the rationale above — this is
  the first feature holding a third-party token, and the handoff explicitly asks for that fact
  to be taken seriously rather than defaulted into the existing wardrobe-item pattern, which was
  never evaluated against holding a credential.
- **A managed secret store (e.g. a cloud KMS or Supabase Vault).** Rejected for this slice:
  `infra/supabase/config.toml` already shows `[db.vault]` commented out and unconfigured, this
  project targets local Supabase only (no cloud project, per every feature's scoping so far),
  and standing up a KMS dependency for one feature's two token columns is disproportionate.
  Vault is worth revisiting if a second feature ever needs the same capability.
- **Storing only the refresh token (re-deriving an access token on every request).** Rejected:
  adds a network round-trip to Google on every event fetch instead of only when the cached
  access token has actually expired, for no security benefit — the refresh token is exactly as
  sensitive as the access token and gets the same encryption regardless.

## 3. PKCE `code_verifier` handoff across the redirect

**Decision**: A short-lived `calendar_oauth_attempts` table (`state` primary key, `user_id`,
`code_verifier`, `created_at`) holds the PKCE verifier between "start" and "finish". The backend
generates `state` and `code_verifier` in `POST /api/v1/calendar/connect/start`, stores the row,
and returns Google's authorization URL (with `code_challenge`/`code_challenge_method=S256`,
`access_type=offline`, `prompt=consent` — the latter two so Google actually issues a refresh
token, which it only does on the first consent or when explicitly re-prompted). The frontend
redirects the browser there directly. `/calendar/callback` forwards `code`+`state` to
`POST /api/v1/calendar/connect/finish`, which looks up and deletes the matching row, verifies it
belongs to the calling user, and completes the token exchange.

**Rationale**: The verifier must survive a full browser round-trip to Google and back — it
cannot live in server memory (this is a stateless API process) or a client-side variable (lost
on Google's redirect). A DB row is the same category of solution feature 004 already uses for
per-user state, needs no new infrastructure, and — unlike embedding the verifier in a signed
`state` parameter — needs no new signing secret.

**Alternatives considered**:
- **Sign the verifier into the `state` parameter itself (HMAC or JWT), avoiding a table
  entirely.** Rejected: introduces a second cryptographic secret (`WTW_OAUTH_STATE_SECRET`) for
  a problem the existing "small per-user table + RLS" convention already solves plainly, and
  makes `state` itself a bearer credential worth protecting rather than an opaque lookup key.
- **An httpOnly cookie carrying the verifier, read directly by `/calendar/callback`.** Rejected:
  works for a same-origin round trip but `/calendar/callback`'s Route Handler would then have to
  forward the verifier to the FastAPI backend anyway (the backend, not Next.js, holds Google's
  client secret and performs the token exchange) — no simpler than the table, and couples the
  flow to cookie behavior across the OAuth redirect, which is exactly the kind of storage-
  isolation hazard `docs/design-decisions.md` §12 flags for cross-container auth flows.

No expiry sweep exists yet for abandoned `calendar_oauth_attempts` rows (a user who starts but
never finishes leaves an orphan row). Accepted as a known, minor gap for this slice — an orphan
row is useless without its matching short-lived Google authorization code, so it carries no
real risk, only unbounded (if slow) table growth. Worth a cleanup task if this pattern is reused
by a future feature; not blocking here.

## 4. Scope and event window — from `/speckit-clarify`

**Decision**: `https://www.googleapis.com/auth/calendar.events.readonly` (least-privilege,
events-only, no calendar-list/settings access), primary calendar only, events in the next 7
days capped at 20, ordered by start time. Both settled during clarification — see spec.md's
Clarifications log for the full reasoning.

## 5. Event fetch — live on every visit, nothing cached

**Decision**: `GET /api/v1/calendar/events` calls the Google Calendar API
(`GET https://www.googleapis.com/calendar/v3/calendars/primary/events`) fresh on every request,
refreshing the access token first if it has expired. No event data is persisted beyond the
single picked-event snapshot.

**Rationale**: The spec's Key Entities section already settles this (an explicit Assumption)
and the design system's screen anatomy describes a plain list with no cache/staleness affordance
— syncing and storing a mirror of the user's calendar would be a real feature of its own (staleness
windows, webhook-based push updates, deletion handling) that nothing in scope asks for.

## 6. Silent refresh failure → treated as disconnected

**Decision**: When a stored refresh token itself fails (Google returns `invalid_grant` or
similar), the repository deletes the user's `calendar_connections` row (and, per FR-013, their
`picked_events` row) and the route surfaces the same response shape as "never connected" rather
than a distinct error. The frontend cannot tell "never connected" from "connection expired and
was cleared" apart — both render the disconnected state, matching the spec's Edge Cases section.

**Rationale**: A half-alive connection that can never successfully fetch events is
indistinguishable from no connection at all from the user's perspective, and keeping a dead row
around only invites a future bug where some other code path assumes "a `calendar_connections`
row exists" means "events are fetchable."

**Alternatives considered**: A distinct `expired` state surfaced to the frontend — rejected, no
such state exists in design-system.md's four specified Calendar states (disconnected /
connected-with-events / connected-empty / error), and inventing one would be a Principle VIII
violation for a case the user experience doesn't actually need to distinguish (the recovery
action is identical either way: reconnect).

## 7. Relative-day/time label computation — client-side

**Decision**: The backend returns each event's `start` as an ISO 8601 UTC timestamp; the
frontend computes the Today/Tomorrow/weekday/short-date label and the locale-aware time string
at render time, in a small pure function (`frontend/lib/calendar/formatEventTime.ts`).

**Rationale**: Matches the one precedent design-system.md already documents as correct —
Settings' birth date uses `toLocaleDateString` client-side specifically because "locale-aware"
is a client concern (the browser knows the user's locale and timezone; the backend does not,
and formatting server-side would either hardcode a locale or require threading one through every
request). "Date & time formats" in design-system.md specifies this exact Today/Tomorrow/weekday/
short-date convention for Calendar rows, generalizing the pattern this project already used for
Settings.

**Alternatives considered**: Server-computed labels — rejected, the backend has no reliable
signal for the user's locale/timezone (no such field exists in the frozen schema or the request),
and baking in a fixed locale/timezone would produce wrong labels for any user outside it.

## 8. Environment limitation — local Supabase's Docker stack, and how this session worked around it

**Finding**: Consistent with `specs/003-auth/research.md` §5's prior finding, this session's
sandboxed network policy denies every Docker Hub/GHCR blob-storage CDN host (confirmed via the
agent proxy's `recentRelayFailures` — `production.cloudfront.docker.com`,
`pkg-containers.githubusercontent.com` — both `403`, policy denial, not a transient failure).
`npx supabase start` cannot pull any image in this session, including `hello-world`, regardless
of retries.

**This session's handling goes further than 003's did.** Rather than treating everything that
needs a database as unverifiable, this session stood up a bare `apt`-installed PostgreSQL 16
(no Docker) on the canonical local direct-connection port (`54322`, matching what
`npx supabase status` would report), and manually created the subset of Supabase's local stack
that the RLS convention and the app's own connection actually depend on: the `auth` schema's
`uid()` function (reading `request.jwt.claim.sub`/`request.jwt.claims`, matching Supabase's own
definition read from `pg_proc` per `specs/004-closet-read/research.md` §2), and the
`anon`/`authenticated`/`service_role`/`authenticator` roles with the same login/`BYPASSRLS`
attributes and role memberships the real stack ships. This makes it possible to actually run
`0004`'s migration, the RLS isolation test (§9 below), and the backend's full test suite against
a real Postgres — not just unit-test the repository against a mock.

**What this does not substitute for**: GoTrue (no real Supabase-issued JWT/JWKS endpoint —
irrelevant to this feature specifically, since it authenticates via feature 003's existing
`get_current_user_id` dependency, already covered by that feature's own test strategy),
PostgREST/Studio, and — separately — the live Google OAuth round-trip itself, which depends on
a real Google Cloud OAuth client's credentials being supplied, not on Supabase at all. See the
feature report for exactly what was and was not exercised.

## 9. RLS isolation test — same mechanism as `test_wardrobe_rls.py`

**Decision**: `tests/integration/test_calendar_rls.py` connects directly to Postgres on the
direct port as the `authenticator` role (not the app's own bypass-privileged pooler connection),
`SET ROLE authenticated`, sets `request.jwt.claim.sub` via `set_config(..., false)` (session-
scoped, since the test connection runs `autocommit=True`), and runs raw unfiltered
`SELECT * FROM calendar_connections` / `picked_events` for two seeded users — proving the policy
itself, independent of this backend's own query-level filtering, exactly as
`specs/004-closet-read/research.md` §1-2 established and as this feature's handoff explicitly
requires ("a policy written but never exercised is a policy that does not work").
