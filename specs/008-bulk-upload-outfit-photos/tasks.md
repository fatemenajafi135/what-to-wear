# Tasks: Photo Management & Display Expansion

**Input**: Design documents from `/specs/008-bulk-upload-outfit-photos/`

**Prerequisites**: plan.md, spec.md

**Tests**: One backend test task (US4 only — the only story touching backend
code): a deterministic CRUD/endpoint round-trip, no LLM calls (US4's new
endpoint explicitly never calls the VLM, per FR-014). US1-US3 are
frontend-only; no frontend test framework exists in this repo — verified via
typecheck/lint/build + quickstart.md's manual steps, matching every prior
frontend change here.

**Organization**: Four user stories, in the priority order the user
explicitly requested (US1, US2 first; US3, US4 after).

## Phase 1: Setup

- [ ] T001 Confirm the dev environment already has everything this feature
      needs (Feature 003/005/006's Storage bucket + RLS, `backend/.env`,
      `frontend/.env.local`) — no new env vars, no new migration, no new
      bucket/policy in this feature. Pre-flight check only, nothing to
      create.

## Phase 2: Foundational

No blocking, cross-story prerequisites this time — unlike Feature 006, no
migration or shared schema change is needed before *any* story can start.
US1 needs nothing beyond what already exists. The one piece of shared
infrastructure (`useSignedPhotoUrl`, needed by US2/US3/US4) is introduced
inside US2 below (the first story in priority order that needs it) rather
than forced into this phase, since US1 doesn't depend on it — see
Dependencies.

## Phase 3: User Story 1 - Add many wardrobe items at once (Priority: P1)

**Goal**: A user can select 5-30 photos at once, review/correct each
resulting item, and save them all to their closet — without a single
photo's failure blocking the rest of the batch.

**Independent Test**: select 5+ photos in one action, review/correct each,
save, and verify all appear in the closet afterward.

- [ ] T002 [US1] New page `frontend/app/closet/add-bulk/page.tsx`: file input
      with `multiple`, client-side cap at 30 files (FR-006) with a clear
      message when exceeded, not a silent truncation.
- [ ] T003 [US1] In the same page: sequential (not concurrent — see plan.md
      Research) `for` loop calling the existing `POST /wardrobe/items/extract`
      once per selected file, building a per-item state array
      (`pending` → `ready-for-review` | `extraction-failed`) with visible
      per-item progress (FR-002).
- [ ] T004 [US1] Per-item review step: loop through the batch one item at a
      time reusing `ExtractedItemForm` (`frontend/components/ExtractedItemForm.tsx`,
      unmodified by this task — US3 adds photo preview to it later, which
      this flow inherits for free) — items with `extraction-failed` still
      enter review via the same manual-entry fallback the single-item flow
      already uses (`extraction_ok: false`) (FR-003, FR-004).
- [ ] T005 [US1] On confirming each item in review, call the existing
      `POST /wardrobe/items/upload` immediately for that item (not batched
      at the end); track per-item save success/failure and offer a retry
      action for failed items only — items that already saved are
      untouched by a later item's failure (FR-005).
- [ ] T006 [US1] Add a link to `/closet/add-bulk` from
      `frontend/app/closet/page.tsx` (near the existing single-item add
      entry point).
- [ ] T007 [US1] `npm run typecheck && npm run lint && npm run build` in
      `frontend/` — clean.

**Checkpoint**: quickstart.md's US1 validation steps all pass manually.

## Phase 4: User Story 2 - See item photos in outfit suggestions (Priority: P2)

**Goal**: Outfit suggestions show each item's real photo (when one exists),
grouped per outfit, instead of today's plain text.

**Independent Test**: request a suggestion for a closet with at least one
photo-added item; verify its real photo renders, grouped with its outfit.

- [ ] T008 [P] [US2] Extract the signed-URL fetch/state logic currently
      inline in `frontend/components/ClosetItemCard.tsx` (the `useEffect` +
      `useState` added in Feature 006) into a new reusable hook
      `frontend/lib/use-signed-photo-url.ts` — same fallback contract
      (absent path / expired object / network error → `null`, never throws).
- [ ] T009 [US2] Refactor `ClosetItemCard.tsx` to call the extracted hook
      instead of its own inline effect — behavior-preserving, verify the
      closet view still renders identically.
- [ ] T010 [P] [US2] New `frontend/components/OutfitItemPhoto.tsx`: takes a
      `WardrobeItem`, uses `useSignedPhotoUrl`, renders the photo when
      resolved, falling back to today's compact text/color presentation
      otherwise — never a broken `<img>` (FR-008).
- [ ] T011 [US2] `frontend/components/SuggestionResult.tsx`: replace the
      `<ul className="outfit-items">` text list with a horizontal row of
      `OutfitItemPhoto`, one per item, within each outfit's existing card
      (FR-007, FR-009).
- [ ] T012 [US2] Add CSS for the horizontal outfit-item photo row in
      `frontend/app/globals.css` (new class, e.g. `.outfit-item-photos`).
- [ ] T013 [US2] `npm run typecheck && npm run lint && npm run build` in
      `frontend/` — clean.

**Checkpoint**: quickstart.md's US2 validation steps all pass manually.

## Phase 5: User Story 3 - Preview the photo while reviewing a new item (Priority: P3)

**Goal**: The single-item (and, for free, bulk) add/review step shows the
actual captured photo, not just the attribute form.

**Independent Test**: add a single item by photo; verify the captured photo
is visible throughout the review step, before saving.

- [ ] T014 [US3] `frontend/components/ExtractedItemForm.tsx`: render the
      photo via `useSignedPhotoUrl(photoPath)` (from US2/T008) above or
      alongside the form fields — `photoPath` is already a prop, currently
      only used to build the save payload (FR-010).
- [ ] T015 [US3] Verify the resumed-draft path (`app/closet/add/page.tsx`'s
      session-storage `Draft`, which only ever carries `photoPath` as a
      string, never a local file object) also renders the photo via the
      same hook — no separate local-blob-URL case needed, confirm by code
      read plus quickstart.md's manual resume check.
- [ ] T016 [US3] `npm run typecheck && npm run lint && npm run build` in
      `frontend/` — clean.

**Checkpoint**: quickstart.md's US3 validation steps all pass manually.

## Phase 6: User Story 4 - Edit or remove a photo on an already-saved item (Priority: P4)

**Goal**: A user can replace or remove an already-saved item's photo from
the closet view.

**Independent Test**: replace an item's photo and verify the new one
displays; separately, remove a photo and verify swatch-only fallback.

### Backend

- [ ] T017 [US4] In `backend/src/whattowear/schema.py`, add
      `photo_path: Optional[str] = None` to `WardrobeItemPatch` — this alone
      enables **remove** via the existing, unchanged
      `PATCH /wardrobe/items/{id}` endpoint: `crud.update_wardrobe_item`'s
      generic `model_dump(exclude_unset=True)` + `setattr` loop already
      applies any present field, including an explicit `null`. No
      `crud.py` change needed for this part.
- [ ] T018 [US4] In `backend/src/whattowear/api.py`, add
      `POST /wardrobe/items/{item_id}/photo` (multipart `photo: UploadFile`,
      auth-gated via the existing `get_current_user_id`/`get_bearer_token`
      dependencies, same pattern as `extract_wardrobe_item`): upload the
      file via the existing `storage.upload_wardrobe_photo` (unchanged, no
      VLM call — FR-014), then apply the resulting path via
      `crud.update_wardrobe_item(session, user_id, item_id,
      WardrobeItemPatch(photo_path=new_path))`. Ownership (FR-013) is
      enforced the same way `update_wardrobe_item` already enforces it for
      every other field — a mismatched `user_id` or unknown `item_id`
      returns `None` → the route raises 404, never a cross-user write.
- [ ] T019 [P] [US4]
      `backend/tests/integration/test_wardrobe_item_photo_edit.py`: (a)
      replace — call the new endpoint on a seeded item, assert
      `photo_path` changed to the new value and no other field changed
      (FR-014); (b) remove — `PATCH` with `{"photo_path": null}`, assert it
      clears; (c) cross-user — attempt replace/remove as a different user,
      assert 404. Uses the `db_session` rollback-isolation fixture like
      other CRUD/endpoint tests in this repo; no LLM calls (mock or bypass
      `storage.upload_wardrobe_photo` the same way
      `test_wardrobe_photo_flow.py` mocks it today).

### Frontend

- [ ] T020 [US4] `frontend/components/ClosetItemCard.tsx`: add a
      replace/remove (or "add photo", for a catalog item with none)
      affordance, revealed on hover/tap rather than permanently visible.
      Replace calls the new `POST /wardrobe/items/{id}/photo`; remove calls
      the existing `PATCH /wardrobe/items/{id}` with `{"photo_path": null}`.
      Either way, the card's existing `useSignedPhotoUrl` hook picks up the
      new/cleared value once the item's `photo_path` updates locally.
- [ ] T021 [US4] Regenerate `frontend/lib/api-types.ts`: start the backend
      locally (`uv run uvicorn whattowear.api:app --reload`), then from
      `frontend/`, `npm run fetch:openapi && npm run gen:types`. Confirm
      the new endpoint and `WardrobeItemPatch.photo_path` appear — the only
      story in this feature that needs this regeneration.
- [ ] T022 [US4] `npm run typecheck && npm run lint && npm run build` in
      `frontend/` — clean.

**Checkpoint**: quickstart.md's US4 validation steps all pass manually.

## Phase 7: Polish

- [ ] T023 [P] `uv run ruff check . && uv run ruff format .` in `backend/`
      — touched files only need to be clean (this repo has pre-existing,
      unrelated ruff findings elsewhere; don't fix those as part of this
      feature).
- [ ] T024 `uv run pytest tests/ -q` in `backend/` — full suite green,
      confirming US4's backend change didn't regress anything.
- [ ] T025 Per the handoff contract (root `CLAUDE.md` "Session workflow"):
      update `docs/SDD-HANDOFF.md` and `CLAUDE.md`'s "Current state" for
      this feature, mark this file's tasks `[X]`.

## Dependencies

- Phase 1 (T001) → all user story phases (trivial pre-flight, not a real
  blocker).
- **US1 (T002-T007) has no dependency on any other story** — it reuses only
  already-existing endpoints and the not-yet-modified `ExtractedItemForm`.
  Can be implemented and shipped alone.
- **US2 (T008-T013) has no dependency on US1.** T008 (hook extraction) is a
  prerequisite for US3 and US4 below, but not for anything within US1.
- **US3 (T014-T016) depends on US2's T008** (the extracted
  `useSignedPhotoUrl` hook) — sequence US2 before US3, matching their P2/P3
  priority order anyway.
- **US4 (T017-T022)'s backend tasks (T017-T019) have no frontend
  dependency** and could be built any time. Its frontend task (T020)
  depends on **both** US2's T008 (same hook, already-updated
  `ClosetItemCard`) **and** T018 (the new backend endpoint it calls) —
  sequence US2 before US4, and T018 before T020, within this story.
- T021 (regenerate `api-types.ts`) depends on T017+T018 (nothing to
  regenerate until the backend change exists).
- Phase 7 (T023-T025) depends on all four stories being complete.

## Parallel execution opportunities

- T008 and T010 (US2) touch different new/existing files with no shared
  state — can be written in parallel.
- T019 (US4's backend test) can be written in parallel with T020 (US4's
  frontend) once T017/T018 land.
- T023 (ruff) can run in parallel with any frontend polish.
- Across stories: US1 (T002-T007) can be built entirely in parallel with
  US2's early tasks (T008, T010) by a second contributor, since neither
  touches the other's files — not relevant for a single-session
  implementation, but noted since this is a 4-story feature.

## Implementation strategy

Priority order as explicitly requested: **US1 and US2 first** (P1, P2 — the
two the user called most important), **then US3 and US4** (P3, P4).
Suggested sequence: T001 → T002-T007 (US1) → T008-T013 (US2) → T014-T016
(US3) → T017-T022 (US4) → T023-T025 (Polish). Each user story phase ends at
an independently shippable checkpoint per its quickstart.md section, so
stopping after US1+US2 (matching the user's own stated priority) is a valid
place to pause if US3/US4 end up deprioritized later.
