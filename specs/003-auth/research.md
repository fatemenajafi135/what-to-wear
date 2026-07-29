# Research: Auth

## 1. Frontend Supabase integration approach

**Decision**: `@supabase/supabase-js` + `@supabase/ssr`, with three thin wrappers under
`frontend/lib/supabase/`: a browser client (`client.ts`), a server client for Server
Components/Route Handlers (`server.ts`), and a middleware helper (`middleware.ts`) that
refreshes the session cookie on every request. Session storage is cookie-based (not
`localStorage`), configured with `flowType: 'pkce'`.

**Rationale**: Route protection (spec FR-010/011/012) has to happen before a page renders,
which in the App Router means `middleware.ts` — and middleware can only read a session from
cookies, not from `localStorage`. `@supabase/ssr` is Supabase's own package for exactly this
split (browser/server/middleware clients sharing one cookie-based session), and is what makes
PKCE work correctly across the redirect to `/auth/callback` (the code verifier must survive
the round trip through a real HTTP redirect, not an in-memory client).

**Alternatives considered**:
- Plain `@supabase/supabase-js` with `localStorage` session storage — rejected: unreadable
  by middleware, so route protection would have to happen client-side after a flash of
  wrong content, which SC-002/SC-003 (protected/auth routes must never render first) rules
  out.
- Rolling a custom cookie session manager — rejected: reimplements what `@supabase/ssr`
  already does correctly, including PKCE verifier handling and refresh-token rotation
  (`enable_refresh_token_rotation = true` is already set in `infra/supabase/config.toml`).

## 2. Backend JWT verification approach

**Decision**: Port `../app-legacy/backend/src/whattowear/auth.py`'s approach —
`PyJWKClient` fetching `{SUPABASE_URL}/auth/v1/.well-known/jwks.json`, verifying signature
with algorithm `ES256`, audience `authenticated` — but rehomed onto this project's own
`Settings`/`get_settings()` pattern (`backend/src/whattowear/core/config.py`) instead of the
reference's raw `os.environ` + `load_dotenv()`, and without depending on a `users` table
(the verified `sub` claim is the identity).

**Rationale**: Supabase CLI 2.x (this project pins `2.110.0` in `infra/package.json`)
defaults new local projects to asymmetric JWT signing keys (ES256), the same scheme the
legacy reference confirmed for its own — separate — Supabase project. JWKS-based
verification means the backend holds only a public key and can never mint a token itself,
which is a strictly better security posture than a shared HS256 secret and costs nothing
extra to implement.

**Alternatives considered**:
- HS256 with a shared `SUPABASE_JWT_SECRET` (the older Supabase pattern, and what the
  handoff's phrase "the JWT secret comes from `npx supabase status`" evokes) — not chosen
  as primary: newer local Supabase projects issue ES256 signing keys by default, so a
  hardcoded HS256 path would silently fail against this project's actual local stack. Not
  empirically confirmed in this environment (§5 below) — flagged as a manual verification
  step in tasks.md rather than assumed blind.

## 3. Backend test strategy without a live Supabase instance

**Decision**: Follow the legacy reference's own test pattern exactly — mock `_get_jwk_client`
and `jwt.decode` with `pytest-mock`, so `tests/unit/test_auth.py` covers missing / invalid /
expired / valid-token cases with zero network dependency. Add `pytest-mock` to
`backend/pyproject.toml`'s dev dependency group (not currently present).

**Rationale**: `../app-legacy/backend/tests/unit/test_auth.py` already proves this pattern
works and needs no live JWKS endpoint — confirmed by reading it directly. This matters more
than usual here: this session's sandboxed network cannot reach Docker's registry to run
`supabase start` at all (see §5), so a test suite that required a live instance would be
unrunnable here, not just slower.

**Alternatives considered**:
- An integration test against a real local Supabase JWKS endpoint — valuable, and still
  called for in `quickstart.md` as a manual verification step, but not the unit-test suite's
  job; it needs a machine that can actually run `supabase start`.

## 4. Route protection mechanism

**Decision**: A single `frontend/middleware.ts` using the `@supabase/ssr` middleware client,
with a matcher excluding static assets. It classifies each request's path as auth-stack or
authenticated-app (per design-system §4's two stacks) and redirects per spec FR-010/011/012.
`/` and `/auth/callback` are handled as special cases (redirect-by-auth-state, and
pass-through respectively).

**Rationale**: Centralizing the redirect rule in one file is the only way to guarantee
SC-002/SC-003 ("no wrong content ever renders first") — a per-page check in Server Components
would still let the auth-stack layout mount before redirecting.

**Alternatives considered**:
- Per-page `redirect()` calls in each Server Component — rejected: duplicated across 6
  routes, and easy to miss one (exactly the kind of drift Principle IX warns about at the
  route level).

## 5. Environment limitation — local Supabase cannot be started in this session

**Finding**: `npx supabase start` pulls its images from Docker Hub via
`production.cloudfront.docker.com`. This sandboxed session's outbound network policy returns
`403` (policy denial, confirmed via `$HTTPS_PROXY/__agentproxy/status`) for that host, so the
pull cannot complete here regardless of retries. Docker's daemon itself runs fine in this
container (started manually — it is not running by default); only the image pull is
blocked.

**Consequence**: Everything that needs a *running* local Supabase — real sign-up/sign-in
against Auth, the `/auth/v1/.well-known/jwks.json` endpoint actually responding, `npx
supabase status` printing real values, live Playwright runs of the full auth flow — cannot
be executed or verified in this session. This is a session/environment constraint, not a
property of the code, and does not change what gets built: it changes what can be verified
*here* versus what must be verified by whoever next runs this on a machine with normal
Docker Hub access (the handoff's own "fresh machine" setup path in §2 already assumes that).

**Handling**: `tasks.md` separates "build and unit-test" tasks (fully doable here) from
"verify against a running stack" tasks (recorded as manual follow-up, per the handoff's own
Definition of Done in §10, which already anticipates this distinction by asking for what was
"actually tested" versus "only wired").
