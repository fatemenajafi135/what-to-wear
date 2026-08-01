# Quickstart: Photo upload + vision

## Prerequisites

```bash
cd infra && npx supabase start          # local Postgres/Auth/Storage
cd ../backend && uv sync
cd ../frontend && npm ci
```

`backend/.env` needs `AI_GATEWAY_API_KEY` (and optionally `WTW_VISION_MODEL`) for any real
scan — see `.env.example`. Without it, the extract route's Storage upload still works but the
scan call itself fails; that failure is exactly the "genuine upload/scan failure" error state
this feature also has to show correctly (contracts/wardrobe-items-extract.md's 5xx row) so it's
still a useful thing to exercise even with no key configured, just not the *success* path.

## Apply the migration

```bash
cd infra && npx supabase db reset       # applies 0001-0006 from empty
```

Confirms `wardrobe-photos` exists as a bucket afterward with no manual Studio step (§9's
definition-of-done item 1), and that `storage.objects` carries the new RLS policy and grant.

## Run the backend

```bash
cd backend && uv run uvicorn whattowear.main:app --reload
```

## Regenerate frontend API types

```bash
cd frontend && npm run generate:api-types   # backend must be running (previous step)
```

## Validate end to end

1. Sign in, tap the Create action (FAB/rail button/pill depending on viewport) to open `/add`.
2. First time only: the camera primer appears. Tap "Continue" — confirm the file input opens
   with `capture="environment"` on a mobile browser/device, or a normal file picker on desktop.
   Reload the page and reopen `/add`; confirm the primer does **not** appear again
   (`wtw_camera_primed` persisted).
3. Supply a garment photo. Confirm a review card appears with Name/Category/Group/Fabric/
   Color/Notes pre-filled wherever the scan found a value (or, with no VLM key configured,
   confirm the distinct error state appears instead — not the "no garment found" empty state).
4. Edit a field, tap Save. Confirm the overlay closes, `/closet` shows the new item with its
   real photo (not the diagonal-stripe placeholder), and the photo survives a reload.
5. Open the new item's detail page; confirm the hero photo area also shows the real photo.
6. **No garment found**: upload a photo of something that isn't clothing (or a blank image).
   Confirm the empty state (`add_item.empty.body`) appears, not an error, with a "Retake photo"
   action and an "Enter manually" path into the same blank review card (spec.md FR-016).
7. **Bulk**: from `/add`'s initial choice, pick "Add bulk items", supply 2–3 photos. Confirm
   each becomes its own queued review card; "Save & next" advances the announced
   "Reviewing item X of Y" heading; the final card's action finishes the queue back to `/closet`
   with all items present.
8. **Offline**: DevTools → Network → Offline. Confirm the upload trigger is disabled and no
   copy promises a retry.
9. **Color validation**: on a review card, type a color name not in `FASHION_COLOR_PALETTE`
   (e.g. "mauve") and attempt to save. Confirm `field.color.notRecognized` appears and nothing
   saves; correct it to a recognized name (e.g. "plum") and confirm save succeeds.
10. **Ownership**: as a second user (or via `curl` with a different bearer token), attempt to
    read or overwrite the first user's `photo_path` object directly against the Storage API;
    confirm both are refused.
11. **Legacy no-photo item**: open an item seeded before this feature (`photo_path IS NULL`);
    confirm it shows the defined no-photo treatment (research.md §11), not the removed
    diagonal-stripe pattern.

## Vision golden set

```bash
cd backend && uv run python -m whattowear.eval.vision_harness
```

Requires a live `AI_GATEWAY_API_KEY` (no test file makes this call — this is the one command in
the repo that legitimately does). See `research.md` §9 for the fixture images' provenance and
its stated limitation.

## Tests

```bash
cd backend && uv run pytest && uv run ruff check . && uv run ruff format --check . \
  && uv run mypy . && uv run lint-imports
cd frontend && npm test && npm run lint && npm run typecheck && npm run build
```

See `data-model.md` for the Storage bucket/RLS and schema changes, and
`contracts/wardrobe-items-extract.md` / `contracts/wardrobe-items-create-from-upload.md` for the
two new routes' exact request/response shapes.
