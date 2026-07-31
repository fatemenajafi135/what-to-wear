# Implementation Plan: Closet (write)

**Branch**: `005-closet-write` | **Date**: 2026-07-31 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/005-closet-write/spec.md`

## Summary

A signed-in user edits, favourites, logs a wear on, and deletes an item they already own, all
from the Item detail overflow menu 004 wired the trigger for but left empty. Backend: migration
`0005` (a `favorite` column plus a new `item_wears` table), four new routes on the existing
`closet.py` router, four new methods on `SupabaseClosetRepository` (no `ports.py` change).
Frontend: an `ItemOverflowSheet` filling in `BottomSheet`, an in-place `ItemEditForm` replacing
the read-only card, and a bespoke `DeleteConfirmDialog`. Two product gaps the handoff asked to
be decided rather than assumed — same-day wear semantics and delete confirmation — are resolved
in `docs/design-decisions.md` §22 and carried through this plan.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript/Next.js App Router (frontend) — both
already fixed by the constitution; no new language/runtime introduced.

**Primary Dependencies**: FastAPI, SQLAlchemy + psycopg3 (backend, both existing); React 19,
`openapi-fetch` (frontend, both existing). No new dependency added by this feature.

**Storage**: Postgres via Supabase (existing). One migration (`0005`): `wardrobe_items.favorite`
column, new `item_wears` table.

**Testing**: `pytest` (backend unit + integration against a real local Supabase stack), Vitest +
React Testing Library (frontend), both existing harnesses — no new test tooling.

**Target Platform**: Same as every other screen — responsive web, installed PWA, identical
routes (constitution IX). No new platform surface.

**Project Type**: Web application (fixed Next.js + FastAPI layout, constitution "Technology
Constraints").

**Performance Goals**: No feature-specific target beyond the project's general standard web/API
latency expectations — none of the four actions is a bulk or high-frequency operation.

**Constraints**: Offline must disable "Log as worn" and "Save changes" (`navigator.onLine`,
FR-008) with nothing queued. Ownership enforced at query level and RLS (FR-007). No visible
worn-count/favourite indicator on Item detail (FR-006).

**Scale/Scope**: Four write actions on one existing screen (`/closet/:itemId`); one migration;
no new route/screen (the overflow sheet and edit mode are states of the existing route, not new
destinations, so constitution IX's screen-graph parity is unaffected).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Answer each gate explicitly. Mark N/A where a principle genuinely does not apply to this
feature, and say why in one line. Any gate that cannot be satisfied goes into Complexity
Tracking with a justification, or the plan does not proceed to `/speckit-tasks`.

- [x] **I — Salvaged AI code is authoritative.** N/A — this feature touches no
      retrieval/chunking/ingest/KB/scoring/pipeline/eval code at all; it's closet CRUD.
- [x] **II — Deterministic scoring.** N/A — no outfit scoring involved.
- [x] **III — Style gates wardrobe.** N/A — no style/wardrobe retrieval involved.
- [x] **IV — Grounded output.** N/A in the citation sense (no rationale generated), but the
      underlying spirit — every item acted on is provably the requester's own — is FR-007,
      enforced at both the repository query (`WHERE user_id = ...`) and RLS layers, matching
      004/012/013's established pattern.
- [x] **V — Scorers are eval metrics.** N/A — no quality judgement introduced.
- [x] **VI — Schema stability.** Conforms. `favorite` and `item_wears` are additive; no
      taxonomy value, category group, or formality scale is touched. The edit form's
      Category/Group mapping (research.md §4) writes only the existing `category` column,
      through the existing frozen vocabulary — no parallel classification introduced.
- [x] **VII — Contracts.** `WardrobeItemPatch` (existing), `ClosetItemView` (existing, gains
      `favorite`), and two new route-local models (`ClosetItemEditRequest`,
      `FavoriteToggleResponse`) are the only contracts; frontend consumes all of them via
      regenerated `schema.d.ts`, no hand-maintained type.
- [x] **VIII — Visual truth.** Every new visual element (`ItemOverflowSheet`,
      `ItemEditForm`, `DeleteConfirmDialog`) is composed from existing tokened components
      (`BottomSheet`, `Chip`, `Input`, `Textarea`, `Button`) or, for the confirmation dialog,
      the already-established bespoke-`<dialog>` escape hatch (design-system §3, precedented
      by `CalendarPrimer`) — no new component invented, no raw hex/pixel value. Offline state
      (FR-008) and the loading/error/not-found states already on `[itemId]/page.tsx` are
      preserved; Edit adds no new top-level state, it's a mode of the existing card. WCAG:
      dialog focus-trap/restore follows `CalendarPrimer`'s exact precedent (native `showModal`
      + explicit trigger-refocus on close); Chip/Input/Textarea/Button already carry
      `:focus-visible` and 44px hit areas per their own components.
- [x] **IX — One codebase.** No new route. The overflow sheet and edit mode are states of the
      existing `/closet/:itemId`, identical at every form factor per 004's own two-pane
      composition — this feature adds no chrome-specific branching.
- [x] **X — Documents are data.** N/A — no document/corpus involved.

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

<!--
  The repository layout is FIXED by the constitution ("Technology Constraints":
  frontend/, backend/, infra/, design/, docs/ — do not restructure). There is no
  layout choice to make. List only the concrete paths this feature touches.

  There is deliberately no mobile-app option. Principle IX: one Next.js codebase
  serves the desktop web experience and the installed mobile PWA. Creating ios/,
  android/, or any second frontend is a constitutional violation, not an option.
-->

```text
frontend/                     # Next.js App Router + TypeScript. Web AND installed PWA.
├── app/                      # routes — identical at every form factor
├── components/
├── styles/                   # token layers: system → semantic → theme blocks
└── public/                   # icons/ and logo.svg already exist; do not regenerate

backend/
├── pyproject.toml
├── src/whattowear/           # src layout, single package
│   ├── main.py  api/v1/routes/  core/  schemas/  models/
│   ├── repositories/         # ALL database access
│   ├── services/             # use cases: repositories + AI
│   ├── pipeline/ retrieval/ scoring/ memory/ ingest/   # framework-free
│   ├── prompts/              # prompt FILES, loaded by name — never inline strings
│   ├── adapters/  ports.py   # Protocols; AI reaches the DB only through these
│   └── evals/
└── tests/{unit,integration,evals}

infra/
├── corpus.yaml               # the tracked corpus manifest
└── supabase/migrations/      # the ONLY migration system — Alembic is not used
```

**Structure Decision**:

```text
infra/supabase/migrations/0005_closet_write.sql      # new

backend/src/whattowear/
├── schema.py                                          # WardrobeItem gains `favorite`
├── api/v1/routes/closet.py                             # +4 routes, +3 route-local models
├── repositories/supabase_closet.py                     # +4 methods
└── colors.py                                            # read-only; name_to_hex reused, unchanged

backend/tests/
├── unit/test_supabase_closet_repository.py              # +tests for the 4 new methods
├── integration/test_closet_routes.py                     # +tests for the 4 new routes
└── integration/test_wardrobe_rls.py                       # +UPDATE/DELETE cases, +item_wears RLS class

frontend/
├── lib/api/schema.d.ts                                   # regenerated, not hand-edited
└── app/(app)/closet/[itemId]/
    ├── page.tsx                                           # wire the sheet, edit mode, delete dialog
    ├── ItemOverflowSheet.tsx  (+.test.tsx)                # new
    ├── ItemEditForm.tsx  (+.module.css, +.test.tsx)        # new
    └── DeleteConfirmDialog.tsx  (+.module.css, +.test.tsx) # new
```

No path outside the fixed layout is needed.

## Complexity Tracking

No Constitution Check violations — this table is empty. Every gate above is either satisfied
directly or genuinely N/A for a feature with no AI-pipeline surface.
