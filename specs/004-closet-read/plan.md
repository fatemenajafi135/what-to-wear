# Implementation Plan: Closet (read)

**Branch**: `004-closet-read` | **Date**: 2026-07-31 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/004-closet-read/spec.md`

## Summary

Add the first product table (`wardrobe_items` + shared `catalog_items`) and the RLS
convention every later table copies; implement `ports.ClosetRepository` against real
Postgres without touching the Protocol or the fixture-backed implementation the eval harness
depends on; expose authenticated read routes for a user's own items; render `/closet` and
`/closet/:itemId` with every specified state, including the two-pane desktop layout, using
newly-generated OpenAPI types on the frontend (this feature's first consumer of that
pipeline). RLS is proven independent of the backend's own bypass-privileged database role
(research.md §1–2) — a discovery this plan treats as load-bearing, not incidental.

## Technical Context

**Language/Version**: Python 3.12 (backend, `uv`), TypeScript 5.9 / Next.js 16 App Router
(frontend) — both already fixed by the constitution.

**Primary Dependencies**: FastAPI, SQLAlchemy Core (`text()`, no ORM layer — research.md §7),
psycopg3, existing `whattowear.auth.get_current_user_id`. Frontend: `openapi-typescript` +
`openapi-fetch` (new — research.md §8), existing `components/ui/*`.

**Storage**: Postgres via the local Supabase stack, migration `0002` (two new tables:
`wardrobe_items`, `catalog_items`).

**Testing**: `pytest` (unit — repository logic, mocked/fixture; integration — real local
Supabase, including a dedicated RLS-isolation test connecting outside the app's own role);
`vitest` (component state matrices); `playwright` (breakpoint/theme coverage, following
existing `frontend/e2e/*` patterns).

**Target Platform**: Linux server (Railway, backend), Vercel (frontend) — web + installed PWA,
one codebase (Principle IX). Local-only for this feature (no cloud Supabase project).

**Project Type**: Web application (Next.js frontend + FastAPI backend), per the constitution's
fixed layout.

**Performance Goals**: No stated target beyond "usable" — a personal wardrobe's scale (tens to
low hundreds of items per user) makes the route-level in-memory pagination in research.md §5
adequate without a dedicated goal.

**Constraints**: RLS must be provably correct independent of the backend's own bypass-role
connection (research.md §1–2); the `ClosetRepository` Protocol (`ports.py`) must not change;
`adapters.closet_fixture.FixtureClosetRepository` must keep working unmodified — 459 existing
tests depend on it.

**Scale/Scope**: Two new tables, one new repository implementation, two new HTTP routes, two
new screens (`/closet`, `/closet/:itemId`) each with 5 states, plus the desktop two-pane
variant and the global offline banner this feature's own offline requirement depends on
(research.md §9).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **I — Salvaged AI code is authoritative.** N/A. This feature touches no retrieval,
      chunking, ingest, KB, scoring, pipeline, or eval-harness code — it adds a new
      `ClosetRepository` implementation the pipeline consumes through the unchanged Protocol.
- [x] **II — Deterministic scoring.** N/A. No outfit scoring anywhere in this feature; it's
      read-only closet data.
- [x] **III — Style gates wardrobe.** N/A. No style/wardrobe retrieval ordering exists in a
      read-only closet-listing feature.
- [x] **IV — Grounded output.** N/A directly (no suggestion output here), but the same
      grounding discipline is honored at the data layer: every route enforces the caller can
      only ever see their own `wardrobe_items` rows, at both the query and the RLS level
      (FR-002, contracts/closet.md).
- [x] **V — Scorers are eval metrics.** N/A. No quality judgment introduced.
- [x] **VI — Schema stability.** Conforms. Both new tables use `0001_init.sql`'s existing
      `category_group`-derivation path (`categories.group_of()`, never a stored column) and
      `formality_level` enum unchanged. `name`/`notes` are additive fields, not a taxonomy
      change (research.md §4). No parallel formality scale, no renamed group.
- [x] **VII — Contracts.** Satisfied, and this is the feature that makes it real for the first
      time: Pydantic (`WardrobeItem`, route-local response models) is the contract; the
      frontend consumes only `openapi-typescript`-generated types (research.md §8). No
      hand-written duplicate.
- [x] **VIII — Visual truth.** Every token read from design-system.md/design-decisions.md
      (no invented value); `design/prototype/` read for intent only, never copied; all five
      states (loading/empty-first-run/empty-filtered/error/offline) implemented for both
      screens (FR-005–FR-009); WCAG AA carried forward from existing components
      (`TopHeader`, `Chip`, `IconButton`, `Banner` already meet §8 — this feature composes
      them, introduces no new interactive primitive needing its own audit).
- [x] **IX — One codebase.** `/closet` and `/closet/:itemId` are the same Next.js routes at
      every breakpoint; only the two-pane layout at ≥1024px changes composition, not the
      route tree (FR-010). No mobile-specific branch.
- [x] **X — Documents are data.** N/A. No document, corpus entry, or ingestion path in this
      feature.

No unresolved gate. No Complexity Tracking entry required.

## Project Structure

### Documentation (this feature)

```text
specs/004-closet-read/
├── plan.md              # this file
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/closet.md
└── tasks.md             # /speckit-tasks output, not this command's
```

### Source Code (repository root)

```text
frontend/
├── app/(app)/closet/
│   ├── page.tsx                    # /closet — replaces feature 001's stub
│   ├── page.module.css
│   ├── [itemId]/page.tsx           # /closet/:itemId
│   ├── [itemId]/page.module.css
│   └── ClosetGrid.tsx / ClosetGrid states, category chips, two-pane composition
├── app/(app)/layout.tsx            # + global offline Banner (research.md §9)
├── components/shell/OfflineBanner.tsx + useOnlineStatus hook (new)
├── components/ui/…                 # existing: TopHeader, Chip, Banner, IconButton — reused, not modified
└── lib/api/
    ├── schema.d.ts                 # generated (openapi-typescript), committed
    └── client.ts                   # thin openapi-fetch wrapper, new

backend/
└── src/whattowear/
    ├── schema.py                   # + name/notes fields on WardrobeItem, WardrobeItemPatch
    ├── repositories/
    │   ├── __init__.py
    │   └── supabase_closet.py      # SupabaseClosetRepository — new
    └── api/v1/routes/
        └── closet.py               # GET /closet/items, GET /closet/items/{id} — new

infra/supabase/migrations/
└── 0002_wardrobe_and_catalog_items.sql   # new

backend/tests/
├── unit/test_supabase_closet_repository.py
├── unit/test_schema.py             # extended: name/notes fields
└── integration/
    ├── test_closet_routes.py
    └── test_wardrobe_rls.py        # the isolation proof, research.md §2
```

**Structure Decision**: `repositories/` is new (first feature to need it — the handoff's own
instruction). No `models/`/`schemas/` package added: response types live beside their route
(matching `whoami.py`'s existing precedent) and `WardrobeItem` stays in the existing
single-file `schema.py` rather than forking a second contract file (research.md §7 explains
why no ORM/models layer is introduced either). Nothing added outside the constitution's fixed
five top-level directories.

## Complexity Tracking

No violations. Table not filled.
