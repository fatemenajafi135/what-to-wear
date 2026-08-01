# Tasks: Photo upload + vision

**Input**: `spec.md`, `plan.md`, `research.md`, `data-model.md`,
`contracts/wardrobe-items-extract.md`, `contracts/wardrobe-items-create-from-upload.md`,
`quickstart.md` — all in this directory.

Tests are included (constitution Quality Bar: unit tests for deterministic logic, CI gates
including `pytest`/Vitest). No test makes a live VLM or live Storage call — every VLM call is
mocked at `vision._image_content_block`/`get_chat_model`; every Storage HTTP call in unit tests
is mocked at the `requests` boundary.

## Phase 1: Setup

- [ ] T001 Declare the bucket in `infra/supabase/config.toml`:
  `[storage.buckets.wardrobe-photos]` with `public = false`, `file_size_limit = "10MiB"`,
  `allowed_mime_types = ["image/jpeg", "image/png", "image/webp"]` (`data-model.md` §1).
- [ ] T002 Write migration `infra/supabase/migrations/0006_wardrobe_photos.sql`:
  `storage.objects` RLS policy `wardrobe_photos_owner_rw` (`for all`,
  `bucket_id = 'wardrobe-photos' and (storage.foldername(name))[1] = auth.uid()::text` on both
  `using` and `with check`) plus `grant select, insert, update, delete on storage.objects to
  authenticated` — follow `0002`'s comment style exactly (`data-model.md` §2).
- [ ] T003 Apply it: `cd infra && npx supabase db reset` and confirm `0001`-`0006` apply clean
  from empty, and the `wardrobe-photos` bucket exists afterward with no manual step (§9 DoD
  item 1). **Environment note**: this sandbox cannot pull the Docker images `supabase start`
  needs (egress-policy 403s, `research.md` §12) — run this on a machine/CI with Docker access.

## Phase 2: Foundational (blocking prerequisites for all user stories)

- [ ] T004 [P] Add `wtw_max_upload_bytes: int = 10_485_760` and
  `wtw_photo_signed_url_ttl_seconds: int = 3600` to `Settings` in
  `backend/src/whattowear/core/config.py` (`data-model.md` §4).
- [ ] T005 [P] Add `get_current_access_token` to `backend/src/whattowear/auth.py`: same
  JWKS/ES256 verification as `get_current_user_id`, returns the raw token string instead of the
  `sub` claim (`research.md` §1). Unit tests in `backend/tests/unit/test_auth.py`: valid token
  returns the raw string; missing/invalid token raises 401, mirroring the existing
  `get_current_user_id` test cases.
- [ ] T006 [P] Port `backend/src/whattowear/adapters/storage.py` from
  `../app-legacy/backend/src/whattowear/storage.py` (read it, adapt — don't copy verbatim):
  `upload_photo(access_token: str, user_id: str, file_bytes: bytes, filename: str, content_type:
  str) -> str` (uploads to `{user_id}/{uuid4}-{filename}` in the `wardrobe-photos` bucket via
  `requests.post` against `{SUPABASE_URL}/storage/v1/object/...`, caller's bearer token, raises
  on a genuine HTTP failure) and `create_signed_url(access_token: str, photo_path: str,
  expires_in: int | None = None) -> str` (`POST .../storage/v1/object/sign/wardrobe-photos/
  {photo_path}`, `expires_in` defaults to `get_settings().wtw_photo_signed_url_ttl_seconds`).
  Both read config via `get_settings()` inside the function body — **no `os.environ` or
  `load_dotenv()` at module scope** (handoff trap 2; `test_import_safety.py` catches this).
  Add `"whattowear.adapters.storage"` to `REGRESSION_SURFACE_MODULES` in
  `backend/tests/unit/test_import_safety.py`.
- [ ] T007 [P] Unit tests in `backend/tests/unit/test_storage_adapter.py`: `upload_photo` posts
  to the right URL with the right path shape and headers (mocked `requests.post`, no network);
  `create_signed_url` posts to the sign endpoint and returns the signed URL from the mocked
  response; both raise on a mocked non-2xx response.
- [ ] T008 Relax `CreateWardrobeItemFromUploadRequest` in `backend/src/whattowear/schema.py` per
  `data-model.md` §3: `formality`, `warmth`, `season`, `fabric`, `pattern`, `fit` become
  `| None = None` (keep the existing `ge=0, le=5` constraint on `warmth`); `photo_path`,
  `category`, `colors` (`min_length=1`) stay required. Keep the existing `_colors_must_be_hex`
  validator unchanged.
- [ ] T009 [P] Add `photo_url: str | None = None` to `ClosetItemView` in
  `backend/src/whattowear/api/v1/routes/closet.py` (`data-model.md` §5). Update
  `list_closet_items` and `get_closet_item` to accept the new `get_current_access_token`
  dependency and pass each item's `photo_path` (when not `None`) through
  `storage.create_signed_url` to populate it — `None` stays `None` when there's no photo.
- [ ] T010 [P] Integration test `backend/tests/integration/test_storage_rls.py`: user A uploads
  an object under their own prefix (via `adapters.storage.upload_photo` with a real local-stack
  access token, mirroring `test_wardrobe_rls.py`'s existing two-real-user technique); user B's
  own access token attempts to read that exact object path (`GET
  {SUPABASE_URL}/storage/v1/object/wardrobe-photos/{userA}/...`) and to overwrite it (`POST` to
  the same path) — both must fail. §9 DoD "Storage isolation proven" item. **Cannot run in this
  sandbox** (no local Supabase, `research.md` §12) — written to the same standard
  `test_wardrobe_rls.py` already meets, ready to run wherever Docker egress is available.

**Checkpoint**: bucket + RLS exist; the read routes can mint signed URLs; the upload-request
contract accepts a partial scan. Nothing new is callable by users yet — that's Phase 3.

## Phase 3: User Story 1 — Photograph one garment and save it (P1)

**Goal**: upload → scan → six-field review card → save → item appears in Closet with its real
photo, survives reload. Empty/error states distinct. Offline disables upload. Camera primer
gates the first capture.

**Independent test**: `quickstart.md` steps 2–6, 8–9 (primer, scan, save, no-garment-found,
offline, color validation).

- [ ] T011 [P] [US1] Unit tests for the extract route's request-validation edges in
  `backend/tests/unit/test_closet_routes_extract.py`: no `photo` field → 422; wrong content
  type → 422; file larger than `wtw_max_upload_bytes` → 422 — all before any Storage/VLM call
  (mock both, assert neither was invoked on a 422).
- [ ] T012 [US1] `POST /closet/items/extract` in `backend/src/whattowear/api/v1/routes/closet.py`
  (`contracts/wardrobe-items-extract.md`): validates the upload (422s per T011), calls
  `adapters.storage.upload_photo` with the caller's access token (`get_current_access_token`),
  calls `vision.extract_attributes_from_image`, catches a genuine extraction-call failure as
  `extraction_ok=False` with all-`null` `extracted` fields (never a 5xx for that — a real
  Storage failure is the only path that legitimately 5xxs), returns `PhotoExtractionResponse`.
  Depends on T005, T006.
- [ ] T013 [P] [US1] Add `create_wardrobe_item_from_upload(self, user_id: str, request:
  CreateWardrobeItemFromUploadRequest) -> WardrobeItem` to
  `backend/src/whattowear/repositories/supabase_closet.py`: applies the three documented
  defaults (`formality="casual"`, `warmth=3`, `season=["spring","summer","autumn","winter"]`)
  when the request field is `None` (`research.md` §4), inserts with `source='upload'`, returns
  the created row via the existing `_row_to_wardrobe_item` mapping. Not added to
  `ports.ClosetRepository` (handoff trap 5). Unit test in
  `backend/tests/unit/test_supabase_closet_repository.py`: a request with all five optional
  attributes omitted inserts with the three documented defaults and `NULL` fabric/pattern/fit.
- [ ] T014 [US1] `POST /closet/items/from-upload` in `closet.py`
  (`contracts/wardrobe-items-create-from-upload.md`): body is
  `CreateWardrobeItemFromUploadRequest`, calls T013's repository method, returns
  `ClosetItemView.from_wardrobe_item(...)` with `photo_url` populated (reuse the T009 signing
  helper). Depends on T008, T009, T013.
- [ ] T015 [P] [US1] Integration tests in `backend/tests/integration/test_closet_routes.py`:
  extract with a mocked-success VLM returns `extraction_ok: true` and populated `extracted`;
  extract with a mocked extraction failure returns `200`, `extraction_ok: false`, all-`null`
  fields; from-upload with only the six review-card fields set creates an item with the three
  documented defaults applied; from-upload's created item is retrievable via
  `GET /closet/items/{id}` with a non-null `photo_url`. Depends on T012, T014.
- [ ] T016 [P] [US1] `frontend/lib/camera/primed.ts`: `isCameraPrimed`/`setCameraPrimed` against
  `wtw_camera_primed` in `localStorage`, mirroring `lib/calendar/primed.ts` exactly (SSR-safe).
- [ ] T017 [P] [US1] `frontend/components/camera/CameraPrimer.tsx` + `.module.css` +
  `.test.tsx`, modeled directly on `components/calendar/CalendarPrimer.tsx` (same
  `showModal`/trigger-refocus-on-close `<dialog>` pattern): title "Before you scan", body copy
  and button labels "Continue"/"Not now" per `design-decisions.md` §23.6. Test mirrors
  `CalendarPrimer.test.tsx`'s assertions.
- [ ] T018 [P] [US1] `frontend/lib/colors/validateColorName.ts` + `.test.ts`: a small
  client-side mirror of `FASHION_COLOR_PALETTE`'s keys (case-insensitive/trimmed match) used to
  validate the Color field before submit, returning either a resolved name or `null`
  (`data-model.md` §7's `field.color.notRecognized` message shown when `null`). Keeping this as
  a name-only check (not hex resolution — the backend still does the authoritative
  `name_to_hex` conversion) avoids duplicating `colors.py`'s hex values in two languages.
- [ ] T019 [US1] `frontend/app/(app)/add/Dropzone.tsx` + `.module.css` + `.test.tsx`: full-width
  `height: 220px`, `16px` radius dropzone per design-system §"Image treatment", disabled (via
  `useOnlineStatus`) with no retry-promise copy when offline (FR-014), gates the
  `<input type="file" accept="image/*" capture="environment">` behind `CameraPrimer` (T017) the
  first time (`isCameraPrimed()` false) using `add_item.upload.placeholder` copy.
- [ ] T020 [US1] `frontend/app/(app)/add/ReviewCard.tsx` + `.module.css` + `.test.tsx`: the
  six-field card (Name `Input`, Category `Chip` group, Group `Input`, Fabric `Input`, Color
  `Input` validated via T018 on submit, Notes `Textarea`) at `150px` review-card photo height,
  `16px` radius, matching `ItemEditForm.tsx`'s Category/Group dual-write pattern; submit calls
  `POST /closet/items/from-upload` (T014) after resolving Color to hex via `name_to_hex`
  server-side (client sends the resolved name, server does the hex lookup — the client only
  gates *whether* to submit, per `research.md` §5's "backend still does the authoritative
  conversion").
- [ ] T021 [US1] `frontend/app/(app)/add/AddItemFlow.tsx` + `.module.css` + `.test.tsx`: the
  state machine `dropzone → scanning → review → saved`, calling `POST /closet/items/extract`
  (T012) on file selection, rendering the "no garment found" empty state
  (`add_item.empty.body`/`add_item.empty.retake_cta`) when `extraction_ok: false` with an
  "Enter manually" action that advances to T020's `ReviewCard` blank (`research.md` §8, FR-016)
  instead of a distinct form, and a genuine-failure error state
  (`add_item.error.body`/`add_item.error.cta`) distinct from the empty state when the extract
  call itself fails (network/5xx). On save, closes the overlay via the existing
  `CloseAddOverlay`.
- [ ] T022 [US1] Replace `frontend/app/(app)/add/page.tsx`'s stub body with `AddItemFlow`
  (single-item path; T024 adds the bulk branch's entry choice on top of this same page).
  Depends on T021.

**Checkpoint**: User Story 1 fully functional and independently testable/shippable — the
feature's core mission works end to end (mocked VLM in tests; real VLM needs a live gateway key,
`research.md` §12).

## Phase 4: User Story 2 — Add several garments in one pass (P2)

**Goal**: several photos queue as one-item-per-photo review cards; "Save & next" advances with
an announced position indicator; a single card's failure is isolated; finishing the queue closes
the overlay with everything saved.

**Independent test**: `quickstart.md` step 7.

- [ ] T023 [P] [US2] `frontend/app/(app)/add/BulkChoiceSheet.tsx` + `.module.css` +
  `.test.tsx`: the bespoke "Add to Closet" sheet (icon+title+description rows, design-system §3's
  named bespoke-variant exception — not `BottomSheet` itself) with copy keys
  `add_item.bulk.title`/`.subtitle`/`.option_title`/`.option_subtitle`, offering "Add bulk
  items" alongside the existing single-photo entry.
- [ ] T024 [US2] Wire `BulkChoiceSheet` as `/add`'s entry point in `page.tsx`/`AddItemFlow.tsx`:
  choosing bulk supplies multiple files and transitions into `BulkQueue` (T025) instead of a
  single `AddItemFlow` run; choosing single-photo (or the default, unchanged path) keeps T022's
  existing behavior. Depends on T022, T023.
- [ ] T025 [US2] `frontend/app/(app)/add/BulkQueue.tsx` + `.test.tsx`: holds one queue entry per
  supplied photo (`{ file, photoPath, extracted, fields, status }`, `data-model.md` §8), renders
  T020's `ReviewCard` for the current entry with a live-announcing `<h2 aria-live="polite">`
  reading `add_item.review.position` (design-system §7/FR-006) and animates its progress
  indicator per `research.md` §8's motion-token pairing (reduced-motion gated). "Save & next"
  saves the current card and advances; on the last card, the same action's label/behavior
  finishes the queue and closes the overlay (spec.md Acceptance Scenario 3).
- [ ] T026 [US2] Per-card failure isolation in `BulkQueue.tsx`: a failed save
  (`POST /closet/items/from-upload` fails) sets that entry's `status` to `'error'`, rendering its
  Save action in `Button`'s Error treatment ("Try again") in place — does not advance, does not
  drop the entry, does not affect already-`'saved'` entries (`research.md` §6, FR-008). Test:
  a mocked failure on the 2nd of 3 cards leaves card 1 saved, card 2 retryable, card 3
  unreached; retrying card 2 successfully then allows normal advance.
- [ ] T027 [P] [US2] Integration test in `backend/tests/integration/test_closet_routes.py`:
  three sequential `from-upload` calls with distinct `photo_path`s each create their own item
  (no accidental id/photo collision across "one item per photo").

**Checkpoint**: User Stories 1 and 2 both independently functional.

## Phase 5: User Story 3 — Real photos replace the placeholder (P3)

**Goal**: closet grid tile and item-detail hero render the real photo via `photo_url`; the
diagonal-stripe placeholder is gone for any item that has one; a defined (non-placeholder)
treatment exists for items with no photo; unauthorized requests for a photo are refused (backend
half already covered by T010).

**Independent test**: `quickstart.md` steps 4–5, 11.

- [ ] T028 [US3] `frontend/app/(app)/closet/ClosetGrid.tsx` + `.module.css`: grid tile renders
  `<img src={item.photo_url} alt="" />` filling the existing `120px` tile box when `photo_url`
  is set; renders the no-photo treatment (`research.md` §11 — static `--color-surface-sunken`
  fill + centered Lucide icon, `aria-hidden`) when it's `null`; **delete** the diagonal-stripe
  `background-image` rule and `.placeholderLabel` span/usage for the has-photo case (keep the
  `--color-surface-sunken` fill, now shared with the no-photo treatment, per
  `ClosetGrid.module.css`).
- [ ] T029 [US3] `frontend/app/(app)/closet/[itemId]/page.tsx` + `.module.css`: `ItemDetailCard`'s
  `.photo` block renders the real photo (full-width, `220px`, `16px` radius per design-system,
  40%-width at tablet+ per the existing two-pane rule) when `item.photo_url` is set, the same
  no-photo treatment otherwise; delete the placeholder `<span>`/debug-label usage for the
  has-photo case.
- [ ] T030 [P] [US3] Frontend tests: `ClosetGrid` renders an `<img>` for an item with
  `photo_url` and the no-photo treatment (not the old placeholder markup) for one without;
  same pair of assertions for the item-detail page's photo block.

**Checkpoint**: All three user stories independently functional — full feature complete.

## Phase 6: Polish & cross-cutting

- [ ] T031 Source/generate the two vision golden-set fixture images at
  `backend/evals/fixtures/vision_samples/navy_top_placeholder.png` and
  `beige_trousers_placeholder.png` (`research.md` §9 — synthetic, programmatically generated;
  documented limitation, not a real photograph). Confirm
  `uv run python -m whattowear.eval.vision_harness` no longer fails on a missing file.
  **Running it to a pass/fail verdict needs a live `AI_GATEWAY_API_KEY`**, explicitly not
  configured in this sandbox (`research.md` §12) — report as skipped, not faked.
- [ ] T032 Regenerate `frontend/lib/api/schema.d.ts`: `cd backend && uv run uvicorn
  whattowear.main:app &` then `cd frontend && npm run generate:api-types`.
- [ ] T033 [P] Backend quality gate: `uv run ruff check .`, `uv run ruff format --check .`,
  `uv run mypy .`, `uv run pytest`, `uv run lint-imports` — all clean; test count not below
  577 (§9 DoD). Integration tests requiring a live Supabase stack (T003, T010, and the extended
  cases in T015/T027) cannot execute in this sandbox — reported explicitly, not skipped
  silently or faked green.
- [ ] T034 [P] Frontend quality gate: `npm run lint`, `npm run typecheck`, `npm test`, `npm run
  build` — all clean; test count not below 143 (§9 DoD).
- [ ] T035 Manual browser verification per `quickstart.md`'s full walkthrough, at both
  `localhost:3000` and `127.0.0.1:3000`, both themes, all three breakpoints (§9 DoD, trap 8 —
  don't narrow CORS while doing this). **Needs a running frontend+backend+Supabase stack this
  sandbox cannot provide** — reported as skipped per the handoff's explicit allowance for this
  exact check.
- [ ] T036 Confirm no secret and no personal/`data/`-sourced photo in the diff (`git diff`
  review) before reporting done.

## Dependencies & execution order

- Phase 1 (T001-T003) blocks everything Storage-related — the bucket and RLS must exist before
  any upload path is meaningful, though the route code itself (Phase 3) can be written and unit
  (mocked) tested without a live bucket.
- Phase 2 (T004-T010) blocks all three user-story phases — the signing/upload adapter, the
  relaxed contract, and `photo_url` must exist before any route or screen depends on them.
- User Story phases (3, 4, 5) are meant to be built in priority order — US2 (bulk) reuses US1's
  `ReviewCard`/extract-route work directly, and US3 (real photos) reuses Phase 2's `photo_url`
  wiring — so unlike 005's three independent stories, **US2 and US3 both depend on US1's
  components existing first**, not just on Phase 2. Sequential within one working session, per
  the handoff's own "run this alone" instruction.
- Within a phase, `[P]`-marked tasks touch disjoint files and can be done in any order relative
  to each other; non-`[P]` tasks in a phase are ordered as listed.
- Phase 6 runs last, after all three story phases.

## Parallel example (Phase 2, Foundational)

T004 (settings), T005 (auth dependency), T006+T007 (storage adapter + its tests), and T009
(ClosetItemView field, once T006 exists) touch disjoint files and can proceed in parallel; T008
(schema relaxation) is independent of all of them.

## MVP scope

User Story 1 alone, after Phases 1+2, is the feature's complete demoable mission: photograph a
garment, review it, save it, see it in the closet with its real photo. User Stories 2 (bulk) and
3 (placeholder removal everywhere) are each independently shippable additions on top.
