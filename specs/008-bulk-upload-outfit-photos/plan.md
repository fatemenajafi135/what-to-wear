# Implementation Plan: Photo Management & Display Expansion

**Branch**: `006-wardrobe-item-photos` (continuing on this branch, not a fresh
one — see spec.md's header) | **Date**: 2026-07-17 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/008-bulk-upload-outfit-photos/spec.md`

## Summary

Four extensions of Feature 006 (wardrobe-item-photos), which already shipped
`photo_path` persistence and signed-URL photo rendering. Mostly frontend;
one small, focused backend addition for US4:

1. **Bulk photo upload (US1, P1)**: a new multi-file add-item flow that calls
   the *existing* single-item `POST /wardrobe/items/extract` and
   `POST /wardrobe/items/upload` endpoints once per photo, sequentially, with
   a per-item review step (reusing the existing `ExtractedItemForm`) and
   per-item success/failure tracking. No new backend endpoint.
2. **Outfit photo display (US2, P2)**: `SuggestionResult.tsx` already receives
   full `WardrobeItem` objects (including `photo_path`) via its `closetById`
   map — it just renders them as plain text today. Swap in the same
   signed-URL photo rendering `ClosetItemCard` already has, laid out
   horizontally within each outfit's existing card container. No backend
   change.
3. **Photo preview during single-item review (US3, P3)**: the add-item review
   step currently shows only the extracted-attributes form, not the photo
   itself. Show it, reusing the same signed-URL mechanism. No backend change.
4. **Edit/remove photo on a saved item (US4, P4)**: the one story that
   touches the backend — `photo_path` becomes patchable (currently
   deliberately excluded from `WardrobeItemPatch`, set once at creation) so a
   photo can be removed via the existing generic `PATCH` endpoint, plus one
   new small endpoint that uploads a replacement photo (reusing
   `storage.upload_wardrobe_photo`, no re-extraction — FR-014) and applies it
   through the same existing patch mechanism.

## Technical Context

**Language/Version**: TypeScript / Next.js 16 (frontend, all four stories);
Python 3.12 / FastAPI (backend, US4 only — the other three stories touch no
backend code).

**Primary Dependencies**: None new. Reuses `@supabase/supabase-js` (already
instantiated in `lib/supabase-client.ts`, already used for signed URLs by
`ClosetItemCard.tsx` since Feature 006), the existing `apiFetch` client
(`lib/api-client.ts`), and on the backend, the existing `storage.py`/`crud.py`
functions US4 composes (no new backend dependency).

**Storage**: Additive-only on the backend: no new column, no migration —
`photo_path` already exists on `wardrobe_items` since Feature 006; US4 only
makes it *patchable* after creation (it was write-once before). Bulk upload
(US1) persists via N sequential calls to the existing single-item creation
path; nothing new is stored there either.

**Testing**: No frontend test framework exists in this repo (unchanged from
Features 003/004/006); verified via `typecheck`/`lint`/`build` +
`quickstart.md`'s manual steps. Backend: one small pytest addition for US4's
new endpoint + the `WardrobeItemPatch` field, following the same
`db_session`-isolated pattern as every other CRUD test in this repo — no LLM
calls in US4's own code path (photo replace explicitly does NOT re-run
extraction, FR-014), so no AI-cost tradeoff to make.

**Target Platform**: Existing deployed stack (Railway backend, Vercel
frontend) — no infra change.

**Project Type**: Web application (existing `backend/` + `frontend/`
structure, unchanged).

**Performance Goals**: N/A for US2/US3 (client-side rendering, same
signed-URL mechanism already in production use). US1's only "goal" is
UX-bounded, not latency-bounded: a 30-photo batch is expected to take
noticeably longer than a single upload (each photo is a real sequential VLM
call) — the requirement is that the user sees per-item progress, not that the
whole batch completes in any specific time. US4's new endpoint is a simple
synchronous upload-then-patch, same latency shape as the existing single-item
upload flow.

**Constraints**: No new backend endpoint for US1-US3 (constitution simplicity
+ none of them add a new persistence or retrieval concern). US4 adds exactly
one new endpoint, justified because reusing the existing extract-and-upload
flow would force an unwanted, costly re-extraction just to change a photo
(FR-014). Batch size capped at 30 (spec.md Assumptions). Sequential (not
concurrent) extraction calls for US1 — see Research for why. Old photo
objects are not deleted from Storage on replace/remove (US4) — see spec.md
Assumptions.

**Scale/Scope**: One new frontend page (bulk add, US1), one rendering change
to an existing component plus a new small shared component (US2), one small
addition to an existing component (US3), one schema field change + one new
thin backend endpoint + a small closet-view addition (US4).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Existing Pipeline Is Authoritative** — N/A. Touches no
  retrieval/ingest/eval code. US2 changes only how already-selected outfit
  items are *displayed*, not which items are selected.
- **II. Deterministic Core, LLM At The Edges** — PASS. US1 calls the existing
  `/wardrobe/items/extract` VLM call once per photo in the batch — same LLM
  usage pattern as today's single-item flow, just repeated; no new LLM call
  site. US4's new endpoint explicitly does NOT call the VLM (FR-014) — a
  photo replacement is not a re-classification. No LLM involved in item
  *selection* anywhere in this feature.
- **III. Style Knowledge Gates Wardrobe Retrieval** — N/A. No retrieval code
  touched.
- **IV. Grounded Output Only** — N/A. Not about outfit suggestions' item
  *selection* — US2 only changes how already-grounded, already-selected
  items are rendered.
- **V. Scoring Functions Are Eval Metrics** — N/A. No scoring code touched.
- **VI. Schema Stability** — PASS. US4 makes an existing, already-frozen-shape
  field (`photo_path`, added additively in Feature 006) patchable — no new
  field, no renamed field, no change to the frozen category groups/formality
  enum/warmth scale/season vocabulary.
- **VII. Single Source Of Truth For Contracts** — PASS, with an explicit step
  for US4 only: `frontend/lib/api-types.ts` MUST be regenerated after the new
  endpoint + `WardrobeItemPatch` field land (US1-US3 need no regeneration —
  first frontend-touching stories in this project that don't, since they add
  no backend contract surface at all).

No violations. Complexity Tracking table intentionally omitted (nothing to
justify — even the one new endpoint is a thin composition of two already-
existing functions, not a new abstraction).

## Project Structure

### Documentation (this feature)

```text
specs/008-bulk-upload-outfit-photos/
├── plan.md              # This file
├── checklists/
│   └── requirements.md  # Already written (spec stage)
└── quickstart.md        # Phase 1 output — manual verification steps

(No research.md beyond the one inline decision below: nothing else here is
genuinely unresolved — all four stories reuse existing, already-shipped
mechanisms end to end. No data-model.md: no new entity, no new field — see
"Data model delta" below for the one behavioral change (photo_path becomes
patchable). No contracts/ directory: the one new endpoint is documented
inline below and in tasks.md; a one-endpoint addition to an already-documented
resource doesn't warrant a separate contracts/ file, consistent with how
Feature 006 handled its own schema addition.)
```

### Source Code (repository root)

```text
backend/
├── src/whattowear/
│   ├── schema.py                        # WardrobeItemPatch gains photo_path
│   ├── crud.py                          # unchanged — update_wardrobe_item's
│   │                                     # existing generic patch loop
│   │                                     # already handles the new field
│   └── api.py                           # NEW: POST /wardrobe/items/{id}/photo
└── tests/
    └── integration/
        └── test_wardrobe_item_photo_edit.py   # NEW — replace + remove

frontend/
├── app/
│   └── closet/
│       ├── add-bulk/
│       │   └── page.tsx                 # NEW (US1) — multi-file select,
│       │                                 # per-item review loop, per-item
│       │                                 # save + retry
│       └── page.tsx                     # +link to bulk-add entry point (US1)
│                                         # +replace/remove photo affordance
│                                         # per card (US4)
├── components/
│   ├── ExtractedItemForm.tsx            # +photo preview (US3)
│   ├── ClosetItemCard.tsx               # useSignedPhotoUrl extracted from
│   │                                     # here (US2); +replace/remove
│   │                                     # controls (US4)
│   ├── SuggestionResult.tsx             # outfit items rendered via the
│   │                                     # photo hook, in a horizontal row
│   │                                     # (US2)
│   └── OutfitItemPhoto.tsx              # NEW (US2) — small shared
│                                         # component: signed photo (via the
│                                         # extracted hook) + swatch/category
│                                         # fallback
└── lib/
    ├── use-signed-photo-url.ts          # NEW (US2) — the useEffect + state
    │                                     # currently inline in
    │                                     # ClosetItemCard, extracted so
    │                                     # SuggestionResult and
    │                                     # ExtractedItemForm can reuse it
    └── api-types.ts                     # regenerated after US4's backend
                                          # change (only story that needs it)
```

**Structure Decision**: Existing `backend/` + `frontend/` layout, unchanged
shape. One new backend endpoint (US4) composing two already-existing
functions, one schema field addition. Three new/extended frontend pieces
(bulk-add page, shared signed-photo hook + component, photo controls on the
closet card) — all built from what Feature 006 already shipped.

## Research: why sequential, not concurrent, extraction calls for US1

Considered and rejected: firing all N extraction calls concurrently
(`Promise.all`) to make a 30-photo batch faster. Rejected because (a) it
multiplies instantaneous load against the same gateway that also serves
live `/suggest` traffic, with no existing rate-limiting/backoff tuned for
that burst shape, and (b) per-item progress ("item 4 of 20 analyzing...") is
an explicit product need (FR-005's per-item success/failure reporting) that
sequential processing gives for free and concurrent processing complicates
(needs its own progress-aggregation logic for no real benefit, since the
user is reviewing/correcting items one at a time anyway per FR-003 — the
batch isn't on any latency-sensitive path a user is blocked staring at).
Decision: sequential `for` loop, one extraction call at a time, matching the
existing single-item flow's call shape exactly.

## Data model delta

No new entity, no new field. One behavioral change: `photo_path` (added
additively in Feature 006, write-once at creation) becomes patchable after
creation via US4 — the existing `wardrobe_items.photo_path` column already
allows `NULL`, so both "replace" (non-null new value) and "remove" (explicit
`null`) fit its existing nullable, unconstrained shape with no migration.

## Backend approach (US4 only)

- `schema.py`: add `photo_path: Optional[str] = None` to `WardrobeItemPatch`.
  This alone enables **removal** through the existing, unchanged
  `PATCH /wardrobe/items/{id}` endpoint and `crud.update_wardrobe_item` — its
  `model_dump(exclude_unset=True)` + generic `setattr` loop already applies
  any field present in the patch, including an explicit `null`; no crud.py
  change needed.
- `api.py`: new `POST /wardrobe/items/{item_id}/photo` (multipart, auth-gated
  via `get_current_user_id`/`get_bearer_token` like every other photo
  endpoint) for **replace**: uploads the new file via the existing
  `storage.upload_wardrobe_photo` (unchanged), then applies the resulting
  path via the existing `crud.update_wardrobe_item(session, user_id,
  item_id, WardrobeItemPatch(photo_path=new_path))` — composing two
  already-existing functions, zero new persistence logic. Ownership
  (FR-013) is enforced the same way `update_wardrobe_item` already enforces
  it for every other field: a mismatched `user_id` returns `None` → 404,
  never a cross-user write.
- Explicitly NOT calling `vision.extract_attributes_from_image` anywhere in
  this endpoint (FR-014) — replacing a photo is not a re-classification.

## Frontend approach

**US1 (bulk upload)**: a new `/closet/add-bulk` page. File input with
`multiple` accepts up to 30 files (FR-006). For each selected file, in
sequence: call `/wardrobe/items/extract` (existing endpoint, unchanged),
collect the result into a per-item state entry (`pending` →
`ready-for-review` or `extraction-failed`, matching today's single-item
`extraction_ok` fallback semantics). Once all N extractions complete, the
user reviews items one at a time (reusing `ExtractedItemForm`, now also
carrying US3's photo preview — see below) — items whose extraction failed
still get reviewed via the same manual-entry path `extraction_ok: false`
already drives today. On confirming each item, call `/wardrobe/items/upload`
(existing endpoint, unchanged) immediately for that item (not batched at the
end) — a save failure on item 7 doesn't jeopardize items 1-6, which already
saved; the UI marks item 7 as failed-to-save with a retry action (FR-005).

**US2 (outfit photos)**: extract `ClosetItemCard`'s inline
`useEffect`/`useState` signed-URL logic into a small reusable hook
(`useSignedPhotoUrl(photoPath)`), used by `ClosetItemCard` (refactor,
behavior-preserving), a new small `OutfitItemPhoto` component used by
`SuggestionResult.tsx`, and `ExtractedItemForm` (US3, see below).
`SuggestionResult`'s existing per-outfit `<ul className="outfit-items">`
becomes a horizontal flex row of `OutfitItemPhoto` instead of plain `<li>`
text — same fallback contract as `ClosetItemCard`: absent `photo_path`,
expired/missing object, or a network error all degrade to today's
text/swatch-only presentation, never a broken `<img>` (spec.md FR-008).

**US3 (single-item preview)**: `ExtractedItemForm` already receives
`photoPath` as a prop (currently used only to build the save payload, never
rendered) — render it via the same `useSignedPhotoUrl` hook from US2. Covers
both the immediate-upload path and the resumed-draft path (session-storage
`Draft` only ever carried `photoPath`, not a local file object, so the
signed-URL fetch is the only option that works for both — no separate
local-blob-URL special case needed).

**US4 (edit/remove photo)**: `ClosetItemCard` gains a small affordance
(shown on hover/tap, not permanently visible clutter) offering "Replace
photo" (file picker → `POST /wardrobe/items/{id}/photo` → re-fetch or
locally update that item's `photo_path` → the existing `useSignedPhotoUrl`
hook picks up the new value) and "Remove photo" (only shown when a photo
exists → `PATCH /wardrobe/items/{id}` with `{"photo_path": null}` → card
falls back to swatch-only, exactly like a catalog item). A catalog item
(never had a photo) instead shows only "Add photo", reusing the same
replace endpoint.

## Complexity Tracking

*(Not applicable — no Constitution Check violations to justify. The one new
endpoint is a thin composition of two pre-existing functions, not a new
abstraction layer.)*
