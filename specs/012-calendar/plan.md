# Implementation Plan: Calendar

**Branch**: `feat/012-calendar` | **Date**: 2026-07-31 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/012-calendar/spec.md`

## Summary

Ship `/calendar` (disconnected / connected-with-events / connected-empty / error, plus
loading and offline), a Google Calendar connection backed by a second, app-orchestrated PKCE
OAuth flow independent of feature 003's sign-in (research.md §1), a picked-event snapshot that
surfaces on `/recommend`'s stub, a one-time permission primer, and one shared connect/disconnect
state reachable from `/calendar` and (once feature 013 merges) Settings → Connected accounts.
Tokens are encrypted at rest (research.md §2). Migration `0004` adds three tables, all RLS-
protected and proven isolated by a direct-Postgres test mirroring feature 004's
`test_wardrobe_rls.py`.

## Technical Context

**Language/Version**: TypeScript 5.9 (Next.js 16 App Router, React 19) · Python 3.12

**Primary Dependencies**: `cryptography` (backend, new — token encryption at rest,
research.md §2) · `requests` (backend, existing — Google's REST endpoints directly, no Google
API client library needed for three plain HTTP calls) · no new frontend dependency (native
`fetch`, existing `openapi-fetch`/generated types, existing `Button`/`Badge` components)

**Storage**: Supabase-managed Postgres (local), three new tables in migration `0004` —
`calendar_connections`, `calendar_oauth_attempts`, `picked_events` (data-model.md). No
calendar-event data is persisted; events are fetched live from Google on each request
(research.md §5).

**Testing**: pytest (backend: unit against a mocked session/HTTP client, integration against a
real Postgres for RLS + routes) · Vitest + Testing Library (frontend unit/component)

**Target Platform**: Browser (desktop web) and installed Android/iOS PWA — identical routes,
per Constitution IX; iOS-specific OAuth-redirect behavior is unverifiable without a physical
device and tracked in `docs/ios-verification-backlog.md` rather than assumed to work, matching
feature 003's precedent.

**Project Type**: web application — existing `frontend/` (Next.js) + `backend/` (FastAPI),
fixed layout per the constitution.

**Performance Goals**: No feature-specific target beyond the app's standard responsiveness;
`GET /events` makes one live call to Google per request (no local cache to warm), bounded by
the 7-day/20-event window (research.md §4) to keep that call and its response small.

**Constraints**: Local Supabase project only. A Google Cloud OAuth client may be unavailable
or only partially usable in a given environment — the connect flow must still be fully wired
and typed regardless (spec Assumptions, FR-017). OAuth tokens are credentials: never in a
tracked file, log line, or client-facing error (FR-005). This session's sandboxed network
cannot reach Docker Hub/GHCR to run `npx supabase start` — research.md §8 documents the
bare-Postgres harness used instead and exactly what it does and doesn't substitute for.

**Scale/Scope**: 1 new route (`/calendar`) + 1 new route handler (`/calendar/callback`) + a
shared client module (connect/disconnect/picked-event state) + a minimal addition to the
`/recommend` stub · 1 backend router (7 endpoints) + 1 repository + migration `0004`.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **I — Salvaged AI code is authoritative.** N/A. This feature touches no retrieval,
      chunking, ingest, knowledge base, scoring, pipeline, or eval-harness code.
- [x] **II — Deterministic scoring.** N/A. No outfit scoring is touched.
- [x] **III — Style gates wardrobe.** N/A. No retrieval of any kind is touched.
- [x] **IV — Grounded output.** N/A. No LLM-authored output exists in this feature; the
      picked-event snapshot is a plain data echo of what Google Calendar returned, not a
      generated claim.
- [x] **V — Scorers are eval metrics.** N/A. No quality judgement is introduced.
- [x] **VI — Schema stability.** N/A. No item-taxonomy field is touched; the three new tables
      are calendar/OAuth state, not wardrobe items.
- [x] **VII — Contracts.** Satisfied. Every new backend route returns a Pydantic response
      model (`contracts/calendar.md`); the frontend consumes only `openapi-typescript`-
      generated types — no hand-written duplicate of any response shape.
- [x] **VIII — Visual truth.** Satisfied by design, with two gaps `design-system.md` left
      silent on now resolved in `docs/design-decisions.md` §16-18 (token storage isn't a
      visual matter and lives in `research.md` §2 instead; the disconnect-affordance gap and
      the primer copy gap are genuinely visual/copy gaps and are resolved there, not invented
      silently). All four `/calendar` states plus loading/offline are built. No component is
      copied from `design/prototype/`. Accessibility: one `<h1>` (`TopHeader`'s title),
      44px hit areas via existing `Button`/`IconButton`, real `:focus-visible` (existing
      component behavior, reused not reinvented), focus moved to the primer's heading on open
      (native `<dialog>` semantics, same mechanism `BottomSheet` already uses),
      `prefers-reduced-motion` honored (reusing `BottomSheet.module.css`'s existing gated
      motion rules for the bespoke primer, per design-decisions §18).
- [x] **IX — One codebase.** Satisfied. `/calendar` and `/calendar/callback` are ordinary
      Next.js App Router routes, identical at every form factor; only chrome differs (existing
      `TopHeader`/nav shell, untouched by this feature). No user-agent branching decides
      reachability. The manifest's `scope: "/"` (already set by feature 001) covers the new
      `/calendar/callback` redirect target with no manifest change needed, matching
      design-decisions §12's precedent for `/auth/callback`.
- [x] **X — Documents are data.** N/A. No document/corpus content is introduced.

No violations. Complexity Tracking is not needed.

## Project Structure

### Documentation (this feature)

```text
specs/012-calendar/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/calendar.md
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
frontend/
├── app/
│   ├── (app)/calendar/
│   │   ├── page.tsx                  # NEW — the four states + loading/offline
│   │   └── page.module.css
│   ├── calendar/callback/route.ts    # NEW — app-owned OAuth return route (distinct from
│   │                                 #   /auth/callback — see research.md §1)
│   └── (app)/recommend/page.tsx      # CHANGED — minimal: the calendar-context line only
├── components/
│   └── calendar/
│       ├── CalendarPrimer.tsx        # NEW — bespoke primer card (design-decisions §18)
│       ├── EventRow.tsx              # NEW
│       └── *.module.css
├── lib/
│   └── calendar/
│       ├── useCalendarConnection.ts  # NEW — shared connect/disconnect state, consumed by
│       │                             #   /calendar now and Settings' row once 013 merges
│       ├── formatEventTime.ts        # NEW — relative-day/time computation (research.md §7)
│       └── primed.ts                 # NEW — wtw_calendar_primed persisted-flag helper
└── lib/api/schema.d.ts               # CHANGED — regenerated (openapi-typescript) after the
                                       #   backend contract exists

backend/
├── src/whattowear/
│   ├── core/config.py                # CHANGED — add WTW_TOKEN_ENCRYPTION_KEY,
│   │                                  #   GOOGLE_OAUTH_CLIENT_ID/SECRET,
│   │                                  #   GOOGLE_OAUTH_REDIRECT_URI
│   ├── adapters/
│   │   └── token_encryption.py       # NEW — Fernet encrypt/decrypt helpers
│   ├── adapters/google_calendar.py   # NEW — thin HTTP client for Google's OAuth + Calendar
│   │                                  #   endpoints (research.md §1/§5)
│   ├── repositories/
│   │   └── supabase_calendar.py      # NEW — calendar_connections/oauth_attempts/picked_events
│   └── api/v1/routes/
│       └── calendar.py               # NEW — the 7 routes (contracts/calendar.md)
└── tests/
    ├── unit/test_supabase_calendar_repository.py   # NEW
    ├── unit/test_token_encryption.py               # NEW
    ├── unit/test_google_calendar_adapter.py        # NEW
    └── integration/
        ├── test_calendar_rls.py       # NEW — mirrors test_wardrobe_rls.py
        └── test_calendar_routes.py    # NEW

infra/
├── supabase/migrations/0004_calendar.sql   # NEW
└── .env.example                            # CHANGED — a note only: calendar OAuth is
                                             #   app-orchestrated (research.md §1), its
                                             #   credentials live in backend/.env, not here

backend/.env.example                        # CHANGED — WTW_TOKEN_ENCRYPTION_KEY,
                                             #   GOOGLE_OAUTH_CLIENT_ID/SECRET,
                                             #   GOOGLE_OAUTH_REDIRECT_URI (blank)

docs/
├── design-decisions.md               # CHANGED — §16-18 (this feature's genuine gaps)
└── ios-verification-backlog.md       # CHANGED — add the calendar-redirect item, matching
                                       #   §12/003's existing iOS-callback entries
```

**Structure Decision**: Fully within the existing fixed layout. `adapters/` already exists
(feature 007) for framework-adjacent external integrations; `google_calendar.py` and
`token_encryption.py` join it rather than inventing a new top-level module, since neither is
AI-pipeline code and both are exactly what `adapters/` is for (external-system boundary code).
`repositories/` and `api/v1/routes/` already exist as directories once feature 004 merges (or
are created here first if this feature lands before it — both are additive, no conflict either
order).

## Complexity Tracking

No Constitution Check violations — this table is intentionally empty.
