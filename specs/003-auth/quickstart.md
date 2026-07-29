# Quickstart: Auth

Full environment setup (Docker, `uv`, Node, Supabase CLI) is already covered by
`docs/handoffs/003-auth.md` §2 — this file only adds the auth-specific validation steps once
that baseline is running. If you're picking this up fresh, do §2 of the handoff first.

## Prerequisites

```bash
cd infra && npx supabase start   # Postgres + Auth + Storage in Docker; leave running
```

`npx supabase status` prints the values `backend/.env` and `frontend/.env.local` need:
`API URL`, `anon key`, and the project's JWKS is served at `<API URL>/auth/v1/.well-known/jwks.json`.

## Backend — verify without a running Supabase (fast, no network)

```bash
cd backend
uv sync
uv run pytest tests/unit/test_auth.py -v   # missing / invalid / expired / valid-token cases, all mocked
uv run ruff check . && uv run mypy src && uv run lint-imports
```

Expected: all pass with zero network access — `_get_jwk_client` and `jwt.decode` are mocked,
matching `../app-legacy/backend/tests/unit/test_auth.py`'s own pattern.

## Backend — verify against a running local Supabase (needs §Prerequisites)

```bash
uv run uvicorn whattowear.main:app --reload
```

```bash
# 401 — no token
curl -s -o /dev/null -w "%{http_code}\n" localhost:8000/api/v1/whoami   # expect 401

# 401 — garbage token
curl -s -o /dev/null -w "%{http_code}\n" -H "Authorization: Bearer garbage" localhost:8000/api/v1/whoami   # expect 401

# 200 — real token, obtained by signing in through the frontend (below) and
# copying the access token out of devtools' Application > Cookies, or via:
#   curl -s -X POST "$SUPABASE_URL/auth/v1/token?grant_type=password" \
#     -H "apikey: $SUPABASE_ANON_KEY" -H "Content-Type: application/json" \
#     -d '{"email":"you@example.com","password":"yourpassword123"}' | jq -r .access_token
curl -s -H "Authorization: Bearer $TOKEN" localhost:8000/api/v1/whoami   # expect 200 {"user_id":"..."}
```

## Frontend — manual flow validation (needs §Prerequisites)

```bash
cd frontend && npm ci && npm run dev
```

1. **Sign up**: visit `/signin`, confirm redirect to `/signin` (signed out). Go to `/signup`,
   submit a new email + an 8+ character password. Confirm landing on `/recommend` and that
   reloading the page keeps you signed in (FR-009).
2. **Route protection**: while signed in, visit `/signin` directly — confirm redirect to
   `/recommend` (FR-011). Sign out from Profile, then visit `/recommend` directly — confirm
   redirect to `/signin` (FR-010).
3. **Sign in error**: on `/signin`, submit a wrong password for a real account — confirm a
   single `Banner` error above the form, not a field-level error (FR-018).
4. **Password reset**: from `/signin`, go to `/forgot-password`, submit a real account's
   email — confirm the confirmation state renders in place (no route change). Open
   `http://127.0.0.1:54324` (Inbucket/Mailpit, local email capture) to find the reset email,
   open its link, set a new password on `/reset-password/:token`, confirm it lands on
   `/signin` (never auto-signed-in — FR-008), then sign in with the new password and confirm
   the old one now fails.
5. **Expired/invalid reset link**: open a previously-used or hand-edited-garbage
   `/reset-password/:token` URL — confirm the error state renders (FR-007).
6. **Google OAuth**: if a Google Cloud OAuth client ID/secret is configured in
   `infra/supabase/config.toml` (`[auth.external.google]`), click the Google button on
   `/signin`, complete consent, confirm return via `/auth/callback` and landing on
   `/recommend`. If no client ID is available, confirm the button is present and wired
   (network tab shows an attempt to reach the provider) and record it as untested — do not
   delete or hide it (handoff §2, §10).
7. **Keyboard pass**: Tab through `/signin` and `/signup` — confirm a visible focus ring only
   on keyboard focus (not mouse click), that the wordmark is the page's `<h1>` and receives
   focus on navigation, and that every control (including the password show/hide toggle) is
   reachable and operable via keyboard alone.
8. **Themes and breakpoints**: repeat a pass over all four routes' states at 320 / 768 / 1024
   / 1440px, in both light and dark (`prefers-color-scheme`), per SC-007.

## Automated e2e (needs §Prerequisites)

```bash
cd frontend && npm run e2e -- auth
```

Expected scenario: sign up → sign out → sign in → sign out, asserting the redirects in step 2
above at each transition.

## What this quickstart cannot validate in a sandboxed CI-like environment

Steps under "needs §Prerequisites" require a real Docker daemon that can pull Supabase's
images from Docker Hub. See `research.md` §5 if that pull is blocked by network policy —
in that case, run these steps on a machine with normal Docker Hub access instead, and report
which ones were actually run versus only wired (handoff §12's reporting requirement).

### What was actually run, building this feature

The session that built this feature had a Docker daemon but no Docker Hub access
(`research.md` §5), so `npx supabase start` never completed. What was verified instead:

- **Backend — fully run, fast section**: `uv run pytest`, `ruff check`, `ruff format --check`,
  `mypy`, `lint-imports` — all clean, including the mocked JWT unit and integration tests.
- **Frontend — fully run**: `npm run lint`, `npm run typecheck`, `npm run build`, `npm test`
  (Vitest — 65 tests, including every auth component's blur-validation, submit, and error
  paths, all mocked). `next build` emits all four auth routes plus `/auth/callback` at their
  expected static/dynamic shapes.
- **Frontend — manually run against `next dev`, no live Supabase**: confirmed `/signin`,
  `/signup`, `/forgot-password` render 200 (not 500), the wordmark renders as a focusable
  `<h1>`, keyboard tab order reaches every control on `/signin` in the expected sequence, the
  password show/hide toggle and Sign in button both take real keyboard focus, and the desktop
  (1024px+) panel picks up its `--color-surface` background per design-decisions §13.
  `/reset-password/some-bad-token` correctly falls through to the error state when `verifyOtp`
  fails against an unreachable Supabase.
- **Not run at all**: every scenario requiring a live Supabase response — real sign-up/sign-in,
  the password-reset email round trip, Google OAuth against a real provider, and all four
  Playwright specs that depend on any of those (`auth-flow.spec.ts`, `root-redirect.spec.ts`'s
  signed-in case, `route-protection.spec.ts`, `password-reset.spec.ts`). These are believed
  correct by code review and by the manual checks above, but **unverified** — run them for real
  on a machine with Docker Hub access before calling this feature done.
