# Implementation Plan: Photo upload + vision

**Branch**: `006-photo-upload-vision` | **Date**: 2026-08-01 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/006-photo-upload-vision/spec.md`

## Summary

A signed-in user photographs a garment and it lands in their closet with attributes pre-filled.
Backend: migration `0006` (Storage bucket + `storage.objects` RLS, no new table), two new routes
on the existing `closet.py` router (`POST /closet/items/extract`, `POST
/closet/items/from-upload`) wired to feature 007's already-ported, previously-uncalled
`vision.py`, a new `adapters/storage.py` ported from the legacy prototype, and a relaxed
`CreateWardrobeItemFromUploadRequest`. Frontend: the `/add` overlay's real body (dropzone → scan
→ review card(s) → saved), a bulk-upload queue, a `CameraPrimer` following 012's established
bespoke-dialog pattern, and removal of the diagonal-stripe placeholder from the closet grid tile
and item-detail hero now that real photos exist. Six named gaps and two `known-gaps.md` items
are resolved in `research.md` and mirrored into `docs/design-decisions.md` §23.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript/Next.js App Router (frontend) — both
already fixed by the constitution; no new language/runtime introduced.

**Primary Dependencies**: FastAPI, SQLAlchemy + psycopg3, `requests` (Storage HTTP calls,
already a dependency via the ingest layer), `langsmith`/LangChain (existing, `vision.py` already
uses them) — backend, all existing. React 19, `openapi-fetch` — frontend, both existing. **One
new backend dependency, found during implementation**: `python-multipart`, which FastAPI's
`File(...)`/`UploadFile` parameters require at import time and which nothing before this feature
ever used (every prior route was pure-JSON) — `test_import_safety.py` caught its absence
immediately (`RuntimeError: Form data requires "python-multipart" to be installed`).

**Storage**: Postgres via Supabase (existing, unchanged tables) plus Supabase Storage (new
usage — first feature to use it). One migration (`0006`): `wardrobe-photos` bucket declaration
in `config.toml` + `storage.objects` RLS policy and grant. No new Postgres table.

**Testing**: `pytest` (backend unit + integration against a real local Supabase stack, existing
harness), Vitest + React Testing Library (frontend, existing). No new test tooling. Every VLM
call is mocked at `vision._image_content_block`/`get_chat_model` (matching `test_vision.py`'s
existing pattern) — no test makes a live call (constitution Quality Bar).

**Target Platform**: Same as every other screen — responsive web, installed PWA, identical
routes (constitution IX). The camera primer's file input is the first real native-capability
surface in the product (`capture="environment"`), still served by the same single route.

**Project Type**: Web application (fixed Next.js + FastAPI layout).

**Performance Goals**: No hard numeric target beyond general web/API latency expectations. One
practical constraint the handoff names explicitly: the extract route must not let an unbounded
upload reach the VLM (research.md §3's 10 MiB ceiling exists for exactly this).

**Constraints**: Extraction failure is always `200`, never `5xx` (FR-003/FR-004). Offline
disables the upload trigger with no queuing promise (FR-014). Storage isolation must hold
under a real two-user test (FR-011). `ports.ClosetRepository` must not change (handoff trap 5).

**Scale/Scope**: One migration, two new backend routes, one new adapter module, one relaxed
request contract, one response field addition (`photo_url`), the `/add` route's real
implementation plus a bulk-upload queue and one new bespoke primer component. No new screen/route
is added — `/add` already exists as a stub (004's launcher); constitution IX's screen-graph
parity is unaffected.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **I — Salvaged AI code is authoritative.** `vision.py` (feature 007's port) is wired up
      exactly as it exists — this feature adds callers, it does not modify extraction logic,
      the prompt, or `_EXTRACTION_SCHEMA`. No retrieval/chunking/ingest/KB/scoring/pipeline/eval
      code is touched. `eval/vision_harness.py` gains fixture images only (§5.6), not logic
      changes.
- [x] **II — Deterministic scoring.** N/A — this feature performs attribute *labelling* from a
      user-chosen photo, which `vision.py`'s own docstring and constitution II's rationale both
      already classify as metadata labelling, not outfit item selection (research.md/
      design-decisions §7 "Vision and Principle II", carried forward unchanged from the
      handoff's own §7 table — not relitigated here). No outfit scoring is involved.
- [x] **III — Style gates wardrobe.** N/A — no style/wardrobe retrieval involved.
- [x] **IV — Grounded output.** N/A in the citation sense (no rationale generated), but the
      underlying spirit holds: every photo/item this feature acts on is provably the requester's
      own, enforced at the repository query, RLS *and* (new for this feature) Storage RLS layers
      (FR-011).
- [x] **V — Scorers are eval metrics.** N/A — no quality judgement introduced. The vision golden
      set (§5.6) is an existing mechanism this feature unblocks, not a new metric.
- [x] **VI — Schema stability.** Conforms. No category-group or formality-scale change.
      `CreateWardrobeItemFromUploadRequest`'s relaxation (research.md §4) only widens which
      fields are *required at request time*; the frozen enum values themselves, and every
      column's type, are untouched. The three DB-`NOT NULL` columns keep their constraint —
      the route supplies a documented default rather than the schema being loosened.
- [x] **VII — Contracts.** `ExtractedAttributes`/`PhotoExtractionResponse` (existing, unchanged),
      `CreateWardrobeItemFromUploadRequest` (relaxed), `ClosetItemView` (gains `photo_url`) are
      the only contracts touched; frontend consumes all of them via regenerated `schema.d.ts`.
      The one documented exception (research.md §10): the extract route's multipart *request*
      body is sent as raw `FormData`, since `openapi-typescript` cannot usefully type a
      multipart body — the *response* type is still fully generated, and no hand-maintained
      duplicate type is introduced anywhere.
- [x] **VIII — Visual truth.** Every new visual element (`AddItemFlow`, `Dropzone`,
      `ReviewCard`, `CameraPrimer`, `BulkQueue`) is composed from existing tokened components
      (`Input`, `Textarea`, `Chip`, `Button`, plus the bespoke-`<dialog>` escape hatch
      design-system §3 already names and 012/005 already precedent for `CameraPrimer` and the
      no-photo/error treatments) — no new component invented, no raw hex/pixel value. Every new
      state (upload, empty/no-garment, error, offline, bulk-queue-partial-failure) is one of the
      design system's own named states or a handoff-directed decision recorded in research.md,
      never invented ad hoc. WCAG: `CameraPrimer` follows `CalendarPrimer`'s exact focus-trap/
      restore precedent; the review counter is a live-announcing `<h2>` (FR-006, design-system
      §7); every control reused already carries `:focus-visible` and 44px hit areas.
- [x] **IX — One codebase.** No new route — `/add` already exists (004's stub) and is filled in
      identically at every form factor per its existing centered/stacked responsive spec (§5).
      No chrome-specific branching is added.
- [x] **X — Documents are data.** N/A for the product's own document corpus. The two vision
      golden-set fixture images (research.md §9) fall under the same tracked-fixtures carve-out
      `evals/fixtures/wardrobe.json` already uses — small, committed, non-personal, not sourced
      from `data/`.

## Project Structure

### Documentation (this feature)

```text
specs/006-photo-upload-vision/
├── plan.md              # This file
├── research.md           # Phase 0 — all decisions + alternatives
├── data-model.md         # Phase 1 — Storage bucket/RLS, schema changes
├── quickstart.md         # Phase 1 — end-to-end validation guide
├── contracts/
│   ├── wardrobe-items-extract.md
│   └── wardrobe-items-create-from-upload.md
└── tasks.md              # Phase 2 (/speckit-tasks) — not created by this command
```

### Source Code (repository root)

```text
frontend/                     # Next.js App Router + TypeScript. Web AND installed PWA.
├── app/                      # routes — identical at every form factor
├── components/
├── styles/                   # token layers: system → semantic → theme blocks
└── public/                   # icons/ and logo.svg already exist; do not regenerate

backend/
├── pyproject.toml
├── src/whattowear/           # src layout, single package
│   ├── main.py  api/v1/routes/  core/  schemas/
│   ├── repositories/         # ALL database access
│   ├── adapters/  ports.py   # Protocols; AI reaches the DB only through these
│   └── vision.py  colors.py  categories.py  schema.py
└── tests/{unit,integration,evals}

infra/
└── supabase/migrations/      # the ONLY migration system — Alembic is not used
```

**Structure Decision**:

```text
infra/supabase/config.toml                            # +[storage.buckets.wardrobe-photos]
infra/supabase/migrations/0006_wardrobe_photos.sql     # new — storage.objects RLS + grant

backend/src/whattowear/
├── auth.py                                             # +get_current_access_token
├── schema.py                                            # CreateWardrobeItemFromUploadRequest relaxed
├── core/config.py                                       # +wtw_max_upload_bytes, +wtw_photo_signed_url_ttl_seconds
├── adapters/storage.py                                  # new — ported from ../app-legacy
├── api/v1/routes/closet.py                              # +2 routes, ClosetItemView +photo_url
└── repositories/supabase_closet.py                      # +create_wardrobe_item_from_upload method

backend/.env.example                                     # +documented (blank) new settings, if any need a key

backend/tests/
├── unit/test_storage_adapter.py                          # new — upload/sign payload building, mocked HTTP
├── unit/test_auth.py                                      # +get_current_access_token cases
├── integration/test_closet_routes.py                      # +extract, +from-upload route tests
└── integration/test_storage_rls.py                        # new — two-user Storage isolation

backend/evals/fixtures/vision_samples/
├── navy_top_placeholder.png                              # new — synthetic fixture, research.md §9
└── beige_trousers_placeholder.png                        # new — synthetic fixture, research.md §9

frontend/
├── lib/api/schema.d.ts                                    # regenerated, not hand-edited
├── lib/camera/primed.ts                                    # new — wtw_camera_primed, mirrors lib/calendar/primed.ts
├── lib/colors/validateColorName.ts (+.test.ts)              # new — client-side FASHION_COLOR_PALETTE mirror check
├── components/camera/CameraPrimer.tsx (+.module.css, +.test.tsx)  # new — mirrors CalendarPrimer
└── app/(app)/add/
    ├── page.tsx                                            # replaced — real AddItemFlow body
    ├── AddItemFlow.tsx (+.module.css, +.test.tsx)            # new — dropzone → scan → review → saved state machine
    ├── Dropzone.tsx (+.module.css, +.test.tsx)                # new
    ├── ReviewCard.tsx (+.module.css, +.test.tsx)              # new — the 6-field card, single AND bulk
    ├── BulkChoiceSheet.tsx (+.module.css, +.test.tsx)         # new — "Add to Closet" bespoke sheet (§5.3)
    └── BulkQueue.tsx (+.test.tsx)                             # new — queue state, position indicator

frontend/app/(app)/closet/
├── ClosetGrid.tsx  ClosetGrid.module.css                   # tile renders photo_url or no-photo treatment
└── [itemId]/page.tsx  page.module.css                       # hero renders photo_url or no-photo treatment
```

No path outside the fixed layout is needed.

## Complexity Tracking

No Constitution Check violations — this table is empty. The one documented, non-violating
exception (multipart request bodies not typing through `openapi-typescript`, research.md §10)
is a Principle VII gate note, not a Complexity Tracking entry — it doesn't require justification
against a simpler alternative, it's an upstream tooling limitation with no hand-maintained
duplicate type introduced as a workaround.
