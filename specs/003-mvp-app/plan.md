# Implementation Plan: MVP App

**Branch**: `003-mvp-app` | **Date**: 2026-07-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/003-mvp-app/spec.md`

## Summary

Ship a minimal, vertical, end-to-end slice of the app: sign-in, add-item-by-photo
(VLM extraction), view closet, get an outfit suggestion — reachable at a public
URL. Backend adds exactly two new endpoints (photo → draft extraction; confirmed
attributes → saved item) plus an additive `pattern`/`fit` migration; everything
else (`/wardrobe/items` CRUD, `/recommend`, JWT verification) is reused as-is.
Frontend is a new Next.js app consuming the backend's OpenAPI types, using
Supabase Auth JS directly (no new backend auth code), styled from `/design`'s
token bundle without pixel-porting its narrower (design-only) taxonomy. Deploy:
backend to Railway, frontend to Vercel — bare public reachability, not full
Feature 005 hardening.

## Technical Context

**Language/Version**: Python 3.12 (backend, unchanged); TypeScript 5.x / Node 20+
(frontend, new)

**Primary Dependencies**: FastAPI, SQLAlchemy, Alembic, PyJWT, LangChain/OpenAI
gateway client (all existing, backend); Next.js 15 (App Router), React 19,
`@supabase/supabase-js`, `openapi-typescript` (dev-only, type generation) — all
new, frontend. `storage.py`'s Supabase Storage REST calls use the **existing**
`requests` dependency (already in `pyproject.toml` for the ingest layer) — no
new `supabase-py` client package is added for this feature.

**Storage**: Postgres via Supabase (existing, additive migration only) +
Supabase Storage (new: one bucket, `wardrobe-photos`, for uploaded item photos)

**Testing**: pytest against the live Supabase DB via the existing rollback
fixture (`tests/conftest.py::db_session`), same pattern as Feature 001/002 —
new unit tests for the deterministic parts of vision extraction (payload
building, `ExtractedAttributes` validation) with the LLM call mocked, plus
integration tests for the two new endpoints. No dedicated frontend test
suite (simplicity — the four flows are validated manually per quickstart.md,
consistent with this feature's minimal-first framing); `tsc --noEmit` and
`next build` are the frontend's correctness gate.

**Target Platform**: Web browser (mobile + desktop viewport), backend on
Railway (Linux container), frontend on Vercel

**Project Type**: Web application (backend + frontend, both present) —
Option 2 structure

**Performance Goals**: None beyond existing (`/recommend` already meets eval
harness latency norms). SC-002's "under 2 minutes" is a human task-time budget,
not a server-side perf target.

**Constraints**: Every endpoint except `/health` stays JWT-gated (unchanged
dependency). Schema stays additive-only (`pattern`, `fit` nullable, mirroring
`fabric`/`source`'s precedent). No parallel formality/category vocab in the
frontend — full 6-value formality enum and full 6 category groups, matching
`docs/design-backend-conflict-report.md`'s taxonomy corrections. Supabase
pooler (port 6543) constraint from Feature 001 unchanged.

**Scale/Scope**: Solo-project/demo scale — single-digit concurrent users for
the milestone demo, not a production load target.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Result |
|---|---|---|
| I. Existing pipeline is authoritative | `/recommend`, retrieval, KB, eval harness untouched — new code is additive (2 endpoints, 2 nullable columns) | PASS |
| II. Deterministic core, LLM at the edges | New VLM call **extracts attributes from a single photo the user already chose** — it does not select among candidate items or assemble an outfit. This is a metadata-labeling task, not the "LLM selects clothing items" case Principle II targets. The pre-existing, already-flagged debt (`/recommend`'s LLM still picks outfit items directly) is untouched by this feature — not worsened, not newly introduced. See SDD-HANDOFF Step 4 item 5 for the existing, tracked trade-off. **Reviewed during `/speckit.analyze` (finding N1, informational)**: this is a genuinely novel LLM use case the principle's text didn't anticipate; the reasoning above was re-checked and holds — flagged here for the next reader's visibility, not as an open question. | PASS (new use is out of scope for the principle; existing debt unchanged) |
| III. Style KB gates wardrobe retrieval | Unchanged — `/recommend` internals not touched | PASS |
| IV. Grounded output only | Unchanged — new items are grounded by construction (user-confirmed attributes saved verbatim, `source='upload'`) | PASS |
| V. Scoring functions are eval metrics | No new scoring in this feature | PASS (N/A) |
| VI. Schema stability | `pattern`/`fit` added as nullable, free-text columns — additive only, same shape as `fabric`/`source` in Feature 001. No rename, no parallel formality/category scale. | PASS |
| VII. Single source of truth for contracts | Frontend generates types from the backend's OpenAPI schema (`openapi-typescript`); no hand-maintained duplicate types | PASS |

No violations — Complexity Tracking table is empty.

## Project Structure

### Documentation (this feature)

```text
specs/003-mvp-app/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md         # Phase 1 output
├── contracts/
│   ├── wardrobe-items-extract.md
│   └── wardrobe-items-upload.md
└── tasks.md              # Phase 2 output (/speckit.tasks, not this command)
```

### Source Code (repository root)

```text
backend/
├── src/whattowear/
│   ├── api.py                # + POST /wardrobe/items/extract, POST /wardrobe/items/upload, CORS middleware
│   ├── schema.py              # + pattern/fit on WardrobeItem & WardrobeItemPatch; + ExtractedAttributes,
│   │                           #   PhotoExtractionResponse, CreateWardrobeItemFromUploadRequest
│   ├── models.py               # + pattern/fit nullable columns on WardrobeItemRow
│   ├── crud.py                  # + create_wardrobe_item_from_upload()
│   ├── vision.py                 # NEW — VLM structured-output extraction from an image
│   ├── storage.py                 # NEW — Supabase Storage upload (caller's own bearer token, no service key)
│   └── eval/
│       └── vision_harness.py       # NEW — lightweight golden-vision-case check (Quality Bar)
├── alembic/versions/
│   └── 0002_add_pattern_fit.py       # NEW — additive migration
├── data/
│   ├── golden_set.yaml               # + vision_cases: section
│   └── fixtures/vision_samples/       # NEW — a handful of sample photos for vision_cases
└── tests/
    ├── unit/test_vision.py            # NEW — extraction payload/parsing, LLM mocked
    └── integration/test_wardrobe_photo_flow.py  # NEW — extract + upload endpoints, live DB

frontend/
├── app/
│   ├── (auth)/sign-in/page.tsx, sign-up/page.tsx   # NEW
│   ├── closet/page.tsx                              # NEW — view closet (US3)
│   ├── closet/add/page.tsx                          # NEW — add-by-photo flow (US2)
│   ├── suggest/page.tsx                             # NEW — free-text suggestion request (US4)
│   └── layout.tsx                                    # NEW — auth guard, shell
├── lib/
│   ├── supabase-client.ts                             # NEW — Supabase Auth JS client
│   ├── api-client.ts                                   # NEW — thin fetch wrapper, attaches JWT
│   └── api-types.ts                                     # NEW — generated from backend OpenAPI (openapi-typescript)
├── openapi.json                                          # NEW — checked-in snapshot backend emits at /openapi.json
├── components/                                            # NEW — minimal, on-theme components (design token reference only)
└── styles/                                                 # NEW — tokens adapted from design/_ds/nocturne-.../styles.css
```

**Structure Decision**: Option 2 (web application). `backend/` (existing,
extended) + `frontend/` (new, first code in this directory) — matches the
constitution's locked repo layout (Principle: "Backend code lives in
`backend/`, frontend in `frontend/`. Do not restructure.").

## Complexity Tracking

*No violations — table intentionally empty.*
