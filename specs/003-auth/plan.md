# Implementation Plan: Auth

**Branch**: `003-auth` | **Date**: 2026-07-29 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/003-auth/spec.md`

## Summary

Ship real authentication end to end: four routes (`/signin`, `/signup`, `/forgot-password`,
`/reset-password/:token`) backed by local Supabase Auth (email+password primary, Google
OAuth secondary, PKCE flow), a persisted session, Next.js middleware-based route protection,
an app-owned `/auth/callback`, sign-out from Profile, and a FastAPI dependency that verifies
the Supabase-issued JWT locally against the project's JWKS endpoint, plus one protected
example route proving it end to end. Frontend uses `@supabase/ssr` + `@supabase/supabase-js`
so the same cookie-based session is readable in middleware, server components, and the
browser. Backend adds `pyjwt` and follows the existing `Settings`/`get_settings()` pattern
rather than the legacy reference's raw `os.environ` + `load_dotenv` style.

## Technical Context

**Language/Version**: TypeScript 5.9 (Next.js 16 App Router, React 19) · Python 3.12

**Primary Dependencies**: `@supabase/supabase-js`, `@supabase/ssr` (frontend) ·
`pyjwt` (backend, joins existing `fastapi`, `pydantic-settings`)

**Storage**: Supabase Auth (local, via `infra/supabase`) — no new database tables. No
`users` table lookup on the backend; the verified JWT `sub` claim is the user id.

**Testing**: Vitest + Testing Library (unit/component), Playwright (e2e) · pytest (backend)

**Target Platform**: Browser (desktop web) and installed Android PWA (WebAPK, shares Chrome
storage — no special handling needed) and installed iOS PWA (built blind, verified later per
`docs/ios-verification-backlog.md`)

**Project Type**: web application — existing `frontend/` (Next.js) + `backend/` (FastAPI),
fixed layout per the constitution

**Performance Goals**: No feature-specific target beyond the existing app's standard web
responsiveness; auth screens are static/lightweight — no perceptible additional latency
budget beyond the Supabase Auth round trip itself.

**Constraints**: Local Supabase project only (no cloud project). Google OAuth client
credentials may be unavailable in a given environment — that path must still be fully wired
and typed. Input font size 16px at every breakpoint (iOS Safari zoom bug, design-decisions
§1.2). Password reset must never auto-sign-in (design-decisions §12).

**Scale/Scope**: 4 routes, ~6 new frontend components/modules (Supabase client, middleware,
4 screen forms, callback route), 1 backend dependency module + 1 example protected route.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **I — Salvaged AI code is authoritative.** N/A. This feature touches no retrieval,
      chunking, ingest, knowledge base, scoring, pipeline, or eval-harness code — it is
      auth, which principle I does not cover. `../app-legacy/backend/src/whattowear/auth.py`
      is read as a reference implementation to adapt (per the feature handoff), not salvaged
      AI code being regenerated.
- [x] **II — Deterministic scoring.** N/A. No outfit scoring is touched by this feature.
- [x] **III — Style gates wardrobe.** N/A. No retrieval of any kind is touched.
- [x] **IV — Grounded output.** N/A. No LLM-authored output exists in this feature.
- [x] **V — Scorers are eval metrics.** N/A. No quality judgement is introduced.
- [x] **VI — Schema stability.** N/A. No item-taxonomy field is touched; Account/Session are
      Supabase Auth's own model, not the wardrobe taxonomy.
- [x] **VII — Contracts.** Satisfied. The one new backend surface (the protected example
      route) returns a Pydantic response model; the frontend does not hand-write a duplicate
      type for it. The Supabase JWT itself is a third-party contract (Supabase's), not one
      this project defines — verified, not hand-modeled.
- [x] **VIII — Visual truth.** Satisfied by design. All four screens' tokens, copy, and
      states come from `design/design-system.md` §4/§5/§6/§8 and
      `docs/design-decisions.md` §1 and §12, read through existing components
      (`Input`/`Textarea`/`Select`/`Button`/`Banner`) — no new form primitive is built (per
      the handoff's explicit trap #1). Every screen's loading/error/empty/success states are
      enumerated in the spec and design system. Accessibility items (44px targets, real
      `:focus-visible`, one `<h1>` — promoted wordmark on Sign in/Sign up per handoff §5.1,
      focus moved on navigation) are carried as explicit tasks, not assumed.
- [x] **IX — One codebase.** Satisfied. All four auth routes and `/auth/callback` are
      ordinary Next.js App Router routes, identical at every form factor; only chrome
      differs, and auth screens have no persistent chrome at all (per design-system's auth
      stack). No user-agent branching decides reachability. Android needs no special
      handling (WebAPK shares Chrome storage); iOS-specific behavior is unverifiable here
      and tracked in the iOS backlog rather than assumed to work.
- [x] **X — Documents are data.** N/A. No document/corpus content is introduced.

No violations. Complexity Tracking is not needed.

## Project Structure

### Documentation (this feature)

```text
specs/003-auth/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
frontend/
├── app/
│   ├── (auth)/                       # NEW — auth shell, no persistent chrome
│   │   ├── layout.tsx                # role="main", no TabBar
│   │   ├── signin/page.tsx
│   │   ├── signup/page.tsx
│   │   ├── forgot-password/page.tsx
│   │   └── reset-password/[token]/page.tsx
│   ├── auth/callback/route.ts        # NEW — app-owned OAuth return route
│   ├── page.tsx                      # CHANGED — real signed-in/out redirect, not stub
│   └── (app)/layout.tsx              # CHANGED — Profile gets a sign-out control
├── components/
│   ├── auth/                         # NEW — AuthShell, SignInForm, SignUpForm, etc.
│   └── ui/                           # UNCHANGED — Input/Textarea/Select/Button/Banner reused as-is
├── lib/
│   └── supabase/                     # NEW — browser client, server client, middleware helper
├── middleware.ts                     # NEW — route protection
└── e2e/                              # sign-up → sign-in → sign-out → sign-in Playwright spec

backend/
├── src/whattowear/
│   ├── core/config.py                # CHANGED — add supabase_url, supabase_jwt_aud
│   ├── auth.py                       # NEW — get_current_user_id() FastAPI dependency
│   └── api/v1/routes/                # NEW dir — the protected example route
└── tests/
    ├── unit/test_auth.py             # NEW — valid/missing/invalid/expired token cases
    └── integration/test_protected_route.py  # NEW

infra/supabase/
└── config.toml                       # CHANGED — minimum_password_length=8, [auth.external.google] wired

docs/
├── design-decisions.md               # Only touched if a genuine gap is found (§11 of handoff)
└── ios-verification-backlog.md       # CHANGED — confirm/correct items 5-8, add any new ones
```

**Structure Decision**: `backend/src/whattowear/api/` does not exist yet (feature 002 shipped
only `/health` directly in `main.py`). This feature introduces the first versioned route
under `api/v1/routes/`, matching the layout the constitution's Technology Constraints already
name (`api/v1/routes/`) — not a new choice, just the first feature to need it. Everything
else is additive within the existing fixed layout.

## Complexity Tracking

No Constitution Check violations — this table is intentionally empty.
