# Quickstart: validating Photo to items end-to-end

## Prerequisites

- `backend/.env` populated (copy `backend/.env.example`; needs `AI_GATEWAY_API_KEY` — a live vision
  call is required for real scenarios below). `WTW_SEGMENTATION_API_URL`/`_API_KEY` also needed for
  the segmentation/hybrid strategies (research.md §5) — the generative strategy needs only the
  existing gateway key.
- `npx supabase db reset` (applies `infra/supabase/migrations/`, including this slice's `0013`).
- `cd backend && uv sync && uv run uvicorn whattowear.main:app --reload`
- `cd frontend && npm ci && npm run generate:api-types && npm run dev`
- A closet meeting `wtw_wardrobe_min_items` is not required for this surface (Add-item works on an
  empty closet).

## Scenario 1 — one photo, several garments (User Story 1)

1. Open `http://localhost:3000/add` (or the bulk-upload entry point) and upload a flat-lay photo
   containing 3–4 visibly different garments.
2. **Expect**: the review queue shows one card per garment (not one card for the whole photo), each
   pre-filled with different attributes. The "Reviewing item X of Y" indicator's Y matches the
   detection count, not 1.
3. Upload a photo with more garments than `wtw_max_detections_per_photo` (default 8) — e.g. a large
   pile.
4. **Expect**: exactly 8 cards, plus a visible notice that some garments in the photo weren't
   captured (FR-002) — no error, no dropped upload.

## Scenario 2 — single-garment photo is unchanged (User Story 2, the load-bearing check)

1. Upload a photo of exactly one garment on a hanger, the way the app has always supported.
2. **Expect**: exactly one review card, same fields, comparable wait to before this feature —
   confirm by comparing against a pre-018 recording/screenshot if one exists, or simply that
   nothing about the single-item path *feels* different.
3. Temporarily point the detection call at an invalid model name (or otherwise force the VLM call
   to raise), restart the backend, upload any photo.
4. **Expect**: still exactly one review card, blank, `extraction_ok: false` — never a 5xx, never
   zero cards. Restore the real config afterward.

## Scenario 3 — isolated images render, and fall back cleanly (User Story 4)

1. Upload a photo of a garment worn by a person, or sitting among several other garments.
2. **Expect**: the review card shows that garment alone, background removed — not the full scene.
3. Set `WTW_ISOLATION_STRATEGY=segmentation` and temporarily break `WTW_SEGMENTATION_API_URL`
   (point it at an unreachable host), restart the backend, repeat step 1.
4. **Expect**: the card still renders (that garment's own region of the original photo, per
   research.md §4's client-side crop), still saveable, no error surfaced to the user. Restore the
   real URL afterward.
5. Save the item. Open its Item detail page.
6. **Expect**: the isolated image renders by default; a toggle lets you switch to the original
   photo (FR-020). Confirm the original is the unmodified upload, not the cutout.

## Scenario 4 — extraction accuracy, demonstrated not asserted (User Story 3, #46)

1. Ensure `evals/fixtures/vision_samples/` holds the expanded (10+) real-photo corpus and
   `evals/golden_set.yaml`'s `vision_cases:` reflect it, including `expected_count` for the
   multi-garment fixtures.
2. `git stash` the prompt change (revert `prompts/vision_system.md` to v2 temporarily), run
   `uv run python -m whattowear.eval.vision_harness`, record the pass count.
3. Restore the v3 prompt, re-run the same command.
4. **Expect**: the v3 pass count is measurably higher, or the specific failures the issue names
   (wrong category, missed attributes, vague names) are visibly reduced in the printed per-case
   output — not merely "the prompt reads better." Record both runs (spec.md SC-003).

## Scenario 5 — isolation strategy comparison (#48)

1. Run `uv run python -m whattowear.eval.vision_harness --isolation-report` (research.md §9).
2. **Expect**: a per-strategy table (segmentation / generative / hybrid) with success rate,
   p50 latency, and cost per image against the fixture corpus.
3. Confirm the configured default (`wtw_isolation_strategy`) matches whichever strategy the table
   shows as cheapest/fastest at acceptable success — or, if it doesn't, that the mismatch is
   recorded as a decision (`docs/design-decisions.md` §61) with the reason, not silently ignored
   (FR-016).

## Scenario 6 — bulk upload scales by detections, not files

1. Bulk-upload 2 photos: one single-garment, one with 4 detected garments.
2. **Expect**: the queue shows 5 cards total, "Reviewing item 1 of 5" through "5 of 5" — never "1
   of 2" (spec.md edge case: the position indicator reflects the true total across all photos).
