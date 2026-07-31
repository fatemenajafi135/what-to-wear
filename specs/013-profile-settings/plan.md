# Implementation Plan: Profile and Settings

**Branch**: `feat/013-profile-settings` | **Date**: 2026-07-31 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/013-profile-settings/spec.md`

## Summary

A signed-in user can view a `/profile` summary (three read-only cards) and manage five
settings sections at `/profile/settings` (in-page switcher, not sub-routes): Style
preferences, Body & size, Account, Connected accounts, Notifications. Four of the five
sections persist to a new `user_profile` table (one row per user); Account's email edits go
through Supabase Auth's own `updateUser` path (existing feature-003 plumbing, not a new
field); Connected accounts renders Google Calendar inert (feature 012's job) and Weather
services as "Coming soon". Every section but Notifications has an Edit/Done draft-commit
toggle.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript 5 / Next.js 16 App Router (frontend)
— both already established, no new language.

**Primary Dependencies**: FastAPI + SQLAlchemy + Pydantic (backend, existing); Next.js/React 19
(frontend, existing). **New**: `openapi-typescript` (frontend devDependency) to generate
types from the backend's `/openapi.json` — first feature whose frontend actually calls the
FastAPI backend for product data (see research.md §2).

**Storage**: PostgreSQL via Supabase (existing). New table: `user_profile`.

**Testing**: `pytest` (backend unit + integration, incl. a dedicated RLS-isolation test — see
research.md §1); Vitest + Testing Library (frontend unit); existing Playwright e2e harness
extended only if a p1 flow needs it.

**Target Platform**: Same Next.js codebase serves desktop web + installed PWA (Principle IX).
Backend: Linux server (existing).

**Project Type**: Web app + web service (existing monorepo layout, unchanged).

**Performance Goals**: None beyond the app's existing conventions — this is CRUD-shaped
settings data, not a latency-sensitive path.

**Constraints**: 16px input font at every breakpoint (iOS zoom guard, design-decisions §1.2);
offline banner + per-action disabling (design-system §6); WCAG AA (Constitution VIII).

**Scale/Scope**: One new table, one row per user. Two routes. Five in-page sections. ~4 new
backend endpoints (GET profile, PATCH style-preferences, PATCH body-size, PATCH
notifications). No new endpoint for Account (Supabase Auth) or Connected accounts (static).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **I — Salvaged AI code is authoritative.** N/A. Touches no retrieval/chunking/ingest/
      knowledge-base/scoring/pipeline/eval code.
- [x] **II — Deterministic scoring.** N/A. No outfit scoring involved.
- [x] **III — Style gates wardrobe.** N/A. No wardrobe/style retrieval involved.
- [x] **IV — Grounded output.** N/A. No AI-surfaced items or citations.
- [x] **V — Scorers are eval metrics.** N/A. No new quality judgement.
- [x] **VI — Schema stability.** N/A. Does not touch `category_group`/`formality_level`.
- [x] **VII — Contracts.** Applies. Frontend will consume `openapi-typescript`-generated
      types from the backend's OpenAPI schema — no hand-written duplicate request/response
      shapes (research.md §2).
- [x] **VIII — Visual truth.** Applies. Every value sourced from design-system tokens /
      design-decisions.md; nothing copied from `design/prototype/`; loading/error/offline
      states on both screens; WCAG AA (44px targets, `:focus-visible`, one `<h1>` per screen,
      focus-on-navigate, focus trap+restore where BottomSheet/overlay patterns are reused,
      reduced motion honoured via existing token/animation conventions). Two design-system
      "Open questions" resolved here rather than silently invented — see research.md §4-5.
- [x] **IX — One codebase.** Applies. `/profile` and `/profile/settings` are ordinary
      App Router routes, identical at every form factor; only chrome (nav rail/sidebar/bottom
      bar, two-pane at desktop per §5) differs. No separate mobile build, no UA branching.
- [x] **X — Documents are data.** N/A. No corpus/document involved.

**Flagged, not a gate failure**: an architecture gap outside this feature's clean boundary —
the backend's own Postgres connection uses the `postgres` superuser role (bypasses RLS
entirely) and nothing populates `auth.uid()` for it; `0001_init.sql` deferred that wiring to
feature 003, which never did it. Resolution and scoping: research.md §1.

## Project Structure

### Documentation (this feature)

```text
specs/013-profile-settings/
├── plan.md              # this file
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── profile-settings-api.md
└── tasks.md             # /speckit-tasks output (not yet generated)
```

### Source Code (repository root)

```text
frontend/
├── app/(app)/profile/page.tsx                    # replace stub — 3 read-only cards
├── app/(app)/profile/page.module.css             # replace stub
├── app/(app)/profile/settings/page.tsx           # replace stub — 5-section switcher
├── app/(app)/profile/settings/page.module.css    # replace stub
├── app/(app)/profile/settings/sections/          # new — one file per section
│   ├── StylePreferencesSection.tsx
│   ├── BodySizeSection.tsx
│   ├── AccountSection.tsx
│   ├── ConnectedAccountsSection.tsx
│   └── NotificationsSection.tsx
├── components/ui/BodyShapePicker/                # new — the one net-new UI piece (§1.3
│   │                                                design-decisions doesn't cover it);
│   │                                                everything else reuses Chip/Select/
│   │                                                DatePicker/TagInput/Switch/Input as-is.
│   └── BodyShapePicker.tsx
├── lib/api/
│   ├── schema.d.ts                               # generated by openapi-typescript, gitignored
│   ├── client.ts                                 # thin typed fetch wrapper (new)
│   └── profile.ts                                # profile-specific calls (new)
└── package.json                                   # + openapi-typescript devDep + gen script

backend/
├── src/whattowear/
│   ├── api/v1/routes/profile.py                  # new — GET/PATCH endpoints
│   ├── schemas/profile.py                        # new — Pydantic request/response models
│   ├── models/user_profile.py                    # new — SQLAlchemy model
│   ├── repositories/profile_repository.py        # new — all DB access for this table
│   └── main.py                                   # + include profile router
└── tests/
    ├── unit/test_profile_schemas.py              # new
    ├── integration/test_profile_routes.py        # new
    └── integration/test_user_profile_rls.py      # new — separate-connection RLS proof

infra/
└── supabase/migrations/0003_user_profile.sql     # new
```

**Structure Decision**: fits entirely within the fixed layout; no new top-level directory. The
only genuinely new frontend component is `BodyShapePicker` (a 5-option illustrated
single-select with no existing equivalent among Chip/Select/etc. — everything else in scope
reuses an already-shipped control per docs/design-decisions.md §1 and the handoff's Trap 1).

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|---------------------------------------|
| New `BodyShapePicker` component | Design-decisions §1 lists 6 form controls; none is an illustrated single-select. Building a 6th is unavoidable — the alternative is misusing `Chip` for a control that needs an image+label per option and a 5-item horizontal scroll track. | Reusing `Chip` for body shape would drop the illustration entirely, contradicting FR-005 ("5 illustrated options") and the handoff's explicit requirement. |
| `openapi-typescript` added as a new devDependency | Principle VII requires generated types; no prior feature needed the frontend to call a FastAPI product endpoint (003's Supabase Auth calls don't cross this boundary), so the generation step doesn't exist yet. | Hand-written TypeScript interfaces mirroring the Pydantic models would be the exact "hand-maintained duplicate" Principle VII prohibits. |
