# Implementation Plan: Wardrobe Item Photos

**Branch**: `006-wardrobe-item-photos` | **Date**: 2026-07-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/006-wardrobe-item-photos/spec.md`

## Summary

Persist the photo path that's already captured (and currently silently
discarded) when an item is created via the photo-upload flow, return it on
`GET /wardrobe/items`, and render the real photo on the closet card when
present — falling back to today's color-swatch-only display otherwise.
Catalog-sourced items are unaffected (never had a photo, still don't). No
new API endpoint: the frontend already has an authenticated Supabase
client that can generate a signed URL against the private
`wardrobe-photos` bucket directly, using the per-user RLS policies already
in place from Feature 003/005.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript / Next.js 16 (frontend) — both already the project's locked stack, unchanged.

**Primary Dependencies**: FastAPI, SQLAlchemy, Alembic (backend); `@supabase/supabase-js` (frontend, already a dependency, already instantiated in `lib/supabase-client.ts`).

**Storage**: Supabase Postgres (additive column on the existing `wardrobe_items` table) + Supabase Storage (the existing `wardrobe-photos` bucket — no bucket/policy changes, this feature only *reads* what Feature 003/005 already write and secure).

**Testing**: pytest (backend, one deterministic CRUD test — no LLM calls anywhere in this feature's own code path). No frontend test framework exists in this repo today; verified via `npm run typecheck`/`lint`/`build` and a manual check against a running backend, matching how Features 003/004 verified frontend work.

**Target Platform**: Existing deployed stack (Railway backend, Vercel frontend) — no infra change.

**Project Type**: Web application (existing `backend/` + `frontend/` structure, unchanged).

**Performance Goals**: N/A — no new hot path; one signed-URL call per photo-bearing card, client-side, not on any request-latency-sensitive path (not `/suggest`).

**Constraints**: Minimal effort, explicitly requested — no new endpoint, no new table, no data-model.md/contracts beyond this plan (a one-field addition to an existing entity doesn't warrant separate files). Minimize AI-related test cost — moot here, since nothing in this feature's own logic calls an LLM, so there's no tradeoff to make.

**Scale/Scope**: One nullable column, one schema field, one CRUD assignment, one frontend component change. The smallest feature this project has shipped.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Existing Pipeline Is Authoritative** — N/A. Touches no retrieval/ingest/eval code.
- **II. Deterministic Core, LLM At The Edges** — N/A. No generation or scoring code touched; the LLM's role in the (separate, existing) photo-*extraction* flow is unchanged.
- **III. Style Knowledge Gates Wardrobe Retrieval** — N/A. No retrieval code touched.
- **IV. Grounded Output Only** — N/A. Not about outfit suggestions; a photo is descriptive metadata on an owned item, not something a suggestion cites.
- **V. Scoring Functions Are Eval Metrics** — N/A. No scoring code touched.
- **VI. Schema Stability** — PASS. `photo_path` is a new, nullable, additive field — same pattern as `fabric`/`pattern`/`fit` before it (Features 001/003). Does not rename or restructure any of the frozen category groups, formality enum, warmth scale, or season vocabulary.
- **VII. Single Source Of Truth For Contracts** — PASS, with an explicit step: `frontend/lib/api-types.ts` MUST be regenerated from the running backend's OpenAPI schema (`npm run fetch:openapi && npm run gen:types`) after the schema change, per the project's established convention — not hand-added.

No violations. Complexity Tracking table intentionally omitted (nothing to justify).

## Project Structure

### Documentation (this feature)

```text
specs/006-wardrobe-item-photos/
├── plan.md              # This file
├── checklists/
│   └── requirements.md  # Already written (spec stage)
└── quickstart.md        # Phase 1 output — manual verification steps

(No research.md: nothing was actually unresolved going into this plan —
every technical decision was settled during the spec conversation by
reading the existing code first, not guessed. No data-model.md: one new
nullable field on an existing, already-documented entity doesn't warrant
a separate file — see "Data model delta" below. No contracts/: no new API
surface — GET /wardrobe/items's existing contract just gains one optional
field on its existing response type, and Feature 006 needs no other
endpoint.)
```

### Source Code (repository root)

```text
backend/
├── alembic/versions/
│   └── 0004_add_photo_path.py          # NEW — additive migration
├── src/whattowear/
│   ├── models.py                        # WardrobeItemRow gains photo_path column
│   ├── schema.py                        # WardrobeItem gains photo_path field
│   └── crud.py                          # create_wardrobe_item_from_upload sets it;
│                                         # _to_wardrobe_item returns it
└── tests/
    └── integration/
        └── test_wardrobe_item_photo_path.py   # NEW — round-trip test

frontend/
├── components/
│   └── ClosetItemCard.tsx               # renders <img> when photo_path present
├── lib/
│   ├── types.ts                         # export photo_path-bearing WardrobeItem (auto via api-types)
│   └── api-types.ts                     # regenerated, not hand-edited
```

**Structure Decision**: Existing `backend/` + `frontend/` layout, unchanged. No new top-level directories, no new package.

## Data model delta

`WardrobeItem` (and its backing `wardrobe_items` table / `WardrobeItemRow`)
gains one field:

- `photo_path: str | None` — the Supabase Storage object path of the
  item's photo (e.g. `{user_id}/{uuid}-{filename}`, the exact shape
  `storage.upload_wardrobe_photo` already produces). `None` for every
  catalog-sourced item, and for any photo-uploaded item created before
  this migration (the original path was never captured for those — see
  spec.md's Edge Cases; not backfilled).

No new entity, no relationship change, no state transition. Set exactly
once, at creation, by `create_wardrobe_item_from_upload`; never touched by
`WardrobeItemPatch` (out of scope — a user correcting an item's attributes
isn't re-uploading its photo).

## Frontend approach

`ClosetItemCard.tsx` gets a small client-side effect: when `item.photo_path`
is truthy, call
`supabase.storage.from("wardrobe-photos").createSignedUrl(item.photo_path, 3600)`
(the already-exported `supabase` client from `lib/supabase-client.ts`,
already authenticated as the signed-in user — the same one used for
sign-in/sign-up). On success, render an `<img>` above the existing
color-swatch row; on any failure (network error, `error` field on the
response, expired/missing object) leave the card exactly as it renders
today — swatch-only, no broken image, no thrown error, no visible retry
UI (matches spec.md FR-006 and the project's established
degrade-gracefully pattern from `pipeline/cache.py`/`storage.py`). Color
swatches, hex, fabric, and pattern tags are unconditional and unchanged
either way (spec.md FR-005).

## Complexity Tracking

*(Not applicable — no Constitution Check violations to justify.)*
