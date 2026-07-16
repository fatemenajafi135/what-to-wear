# Quickstart: Photo Management & Display Expansion

## Prerequisites

- Everything Feature 006's quickstart already required (Storage
  bucket/RLS, `backend/.env`, `frontend/.env.local`) — no new env vars, no
  new bucket/policy.
- `uv run alembic upgrade head` — not actually needed (no migration in this
  feature), listed only so it's clear there isn't one to forget.
- A signed-in user with at least one photo-uploaded item already in their
  closet, for US2/US4's validation.

## Validation: US1 — bulk photo upload (SC-001, SC-002)

1. Open the new bulk-add entry point (linked from `/closet`). Select 5+
   photos at once.
2. Confirm each photo is analyzed one at a time (visible per-item progress),
   and that once analysis finishes you can review/correct each item in
   sequence before anything saves — reusing the same review form as the
   single-item flow.
3. Confirm and save all items. Verify the closet view afterward shows every
   newly added item.
4. **Partial extraction failure** (FR-004): include one deliberately bad
   photo (e.g., a blank/corrupt image) in the batch. Confirm that item falls
   back to manual entry during review, without blocking review of the other
   items.
5. **Partial save failure** (FR-005): not easily reproducible without
   simulating a network drop mid-batch — acceptable to verify by code
   inspection (each item's save is independent, one failure doesn't touch
   already-saved items) rather than live-triggering it.
6. Select more than 30 photos at once — confirm the batch is capped (FR-006)
   with a clear message, not a silent truncation or a crash.

## Validation: US2 — outfit photo display (SC-003, SC-004)

1. Request a suggestion (`/suggest`) for a closet containing at least one
   photo-uploaded item and at least one item with no photo (catalog-sourced).
2. Confirm any outfit containing the photo-uploaded item shows its real
   photo alongside its existing text details.
3. Confirm the no-photo item in the same or another outfit still renders
   text/color-only, exactly as before this feature — no broken image.
4. Confirm each outfit's items are visually grouped together as a row,
   distinguishable outfit from outfit.
5. **Graceful degradation** (same pattern as Feature 006's own quickstart):
   simulate a signed-URL failure for one item's photo and confirm that one
   item falls back to text-only without affecting the rest of the outfit or
   throwing a visible error.

## Validation: US3 — photo preview during single-item review (SC-005)

1. Add a single item by photo (existing flow). At the review/correction
   step, confirm the actual captured photo is visible alongside the form,
   not just the attribute fields.
2. Trigger the existing resume-after-sign-in path (let the session expire
   mid-review, per Feature 003's original edge case) and confirm the photo
   is still visible after resuming, not just the form.

## Validation: US4 — edit/remove photo on a saved item (SC-006)

1. On a closet item that has a photo, use the replace control to upload a
   different photo. Confirm the new photo displays for that item afterward
   (closet view, and in an outfit suggestion if it appears in one) — not the
   old one.
2. Confirm replacing a photo does NOT change the item's other attributes
   (category, color, formality, fabric, pattern, fit) — only the photo
   changes (FR-014).
3. On a closet item that has a photo, use the remove control. Confirm it
   falls back to swatch-only display, exactly like a catalog item.
4. On a catalog-sourced item (never had a photo), use the add/replace
   control. Confirm a photo now displays for it going forward.
5. **Ownership check** (FR-013): attempt to replace/remove a photo on an
   item belonging to a different user (e.g., via a direct API call with a
   mismatched id) — confirm it's rejected the same way any other cross-user
   wardrobe-item operation is rejected in this app today (404, not a
   silent write).

## What's NOT covered here

No eval-harness run — this feature touches no retrieval/generation/scoring
code (constitution Principles I-V gate is N/A per plan.md's Constitution
Check). No new migration to verify. US1-US3 need no new contract
verification — every endpoint they call is unchanged and already tested; only
US4's one new endpoint plus the `WardrobeItemPatch` field addition are new
backend surface, covered by `test_wardrobe_item_photo_edit.py`.
