# Tasks: Closet (write)

**Input**: `spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/closet-write.md`,
`quickstart.md` — all in this directory.

Tests are included (this project's constitution Quality Bar requires unit tests for
deterministic logic and CI gates including `pytest`/Vitest).

## Phase 1: Setup

- [ ] T001 Write migration `infra/supabase/migrations/0005_closet_write.sql`: `alter table
  wardrobe_items add column favorite boolean not null default false`; `create table item_wears
  (...)` per `data-model.md` (unique `(item_id, worn_date)`, FK `on delete cascade`, index on
  `item_id`); enable RLS + `for all using/with check (auth.uid() = user_id)` policy +
  `grant select, insert, update, delete on item_wears to authenticated` — follow `0002`'s
  comment style and RLS/GRANT pattern exactly.
- [ ] T002 Apply it: `cd infra && npx supabase db reset` and confirm `0001`-`0005` apply clean
  from empty (§9 DoD item 1).

## Phase 2: Foundational (blocking prerequisites)

- [ ] T003 Add `favorite: bool = False` to `WardrobeItem` in `backend/src/whattowear/schema.py`
  (additive, matches the `name`/`notes` precedent already in that file).
- [ ] T004 Update `_ITEM_COLUMNS` and `_row_to_wardrobe_item` in
  `backend/src/whattowear/repositories/supabase_closet.py` to read/map the new `favorite`
  column (and update `list_catalog_items`'s column projection, which forces `source` the same
  way — `catalog_items` has no `favorite` column, so project a literal `false AS favorite`
  there, matching the existing `'catalog' AS source` pattern).
- [ ] T005 Confirm `backend/tests/unit/test_supabase_closet_repository.py`'s `_ROW` fixture and
  existing assertions still pass with the new column (update the fixture dict to include
  `"favorite": False`).

**Checkpoint**: `GET /closet/items` and `GET /closet/items/{id}` still work and now include
`favorite` in every response. Existing tests green before any new-route work starts.

## Phase 3: User Story 1 — Edit an item's details (P1)

**Goal**: Owner can PATCH Name/Category/Group(category)/Fabric/Colour/Notes; persists across
reload; rejected for a non-owned item; offline disables the submit control.

**Independent test**: `quickstart.md` steps 3 and 7 (Edit + offline-disables-Save).

- [ ] T006 [P] [US1] Unit tests for a new `update_wardrobe_item` repository method in
  `backend/tests/unit/test_supabase_closet_repository.py`: builds the right `UPDATE` SQL/args
  from a `WardrobeItemPatch` with only some fields set, commits, returns the updated row; a
  patch with zero fields set is a no-op (no SQL executed) rather than an empty `UPDATE ... SET`.
- [ ] T007 [US1] Implement `update_wardrobe_item(self, user_id: str, item_id: str, patch:
  WardrobeItemPatch) -> WardrobeItem | None` in
  `backend/src/whattowear/repositories/supabase_closet.py` — `_set_jwt_claim`, dynamic `SET`
  clause from `patch.model_dump(exclude_unset=True)`, `WHERE user_id = :user_id AND id =
  :item_id`, `session.commit()`, re-fetch via the existing `get_wardrobe_item` and return it (or
  `None` if no row matched). Depends on T003/T004.
- [ ] T008 [P] [US1] Add `colors.name_to_hex`/`is_hex` based color-text parsing: a small
  private helper `_parse_colors_text(text: str) -> list[str]` colocated in
  `backend/src/whattowear/api/v1/routes/closet.py` (comma-split, trim, resolve each token via
  `colors.name_to_hex` or `colors.normalize_hex` if already hex, raise `ValueError` naming the
  bad token otherwise) plus a unit test for it (valid names, valid hex, mixed, unknown-token
  error) in a new `backend/tests/unit/test_closet_routes_colors_parsing.py` or alongside
  existing route tests.
- [ ] T009 [US1] Add `ClosetItemEditRequest` (route-local Pydantic model per
  `data-model.md`: `name`, `category`, `fabric`, `colors_text`, `notes`, all `str | None`) and
  `PATCH /closet/items/{item_id}` in `backend/src/whattowear/api/v1/routes/closet.py`: validate
  `item_id` as UUID (404 on malformed, matching the existing GET's pattern), build a
  `WardrobeItemPatch` from the request (converting `colors_text` via T008's helper; a
  `ValueError` from parsing becomes a `422` via `HTTPException`), call
  `update_wardrobe_item`, 404 if `None`, else return `ClosetItemView.from_wardrobe_item(...)`.
  Depends on T007, T008.
- [ ] T010 [P] [US1] Integration tests in `backend/tests/integration/test_closet_routes.py`:
  partial update changes only the sent fields and persists (re-GET confirms); unknown
  `colors_text` token → 422; PATCH on another user's item → 404, item unchanged; PATCH on a
  nonexistent/malformed id → 404. Depends on T009.
- [ ] T011 [P] [US1] Add an UPDATE-isolation case to
  `backend/tests/integration/test_wardrobe_rls.py`'s `TestWardrobeItemsRLS`: user B's
  `authenticator`-role connection issues an unfiltered `UPDATE wardrobe_items SET name = ...
  WHERE id = <user A's item>` and asserts zero rows affected (RLS blocks it, not just the
  query-level filter — the same "prove the policy itself" methodology as the file's existing
  SELECT tests). §9 DoD "RLS proven" item. Depends on T001/T002.
- [ ] T012 [P] [US1] `frontend/app/(app)/closet/[itemId]/ItemEditForm.tsx` +
  `ItemEditForm.module.css`: form matching read-view field order (Name, Category as `Chip`
  group of the five `ClosetChipFilter` values, Group as `Input` free-text feeding the same
  `category` draft state per `research.md` §4, Fabric as `Input`, Colour as `Input`
  pre-filled from `color_names.join(", ")`, Notes as `Textarea`), ending in a full-width
  `Button` "Save changes" that's `disabled` when `!isOnline` (FR-008) or a save request is in
  flight. On submit, calls `apiClient.PATCH("/api/v1/closet/items/{item_id}", ...)` with only
  changed fields, and on success calls a passed-in `onSaved(updatedItem)` callback.
- [ ] T013 [P] [US1] `frontend/app/(app)/closet/[itemId]/ItemEditForm.test.tsx`: renders
  pre-filled from a fixture item; changing a field and submitting calls the PATCH endpoint
  with only the changed field(s); Save is disabled when an `isOnline={false}` prop is passed.
- [ ] T014 [US1] Wire `ItemEditForm` into `frontend/app/(app)/closet/[itemId]/page.tsx`: an
  `editing` boolean state; when true, render `ItemEditForm` instead of `ItemDetailCard`;
  `onSaved` sets the updated item and flips `editing` back to `false`. Depends on T012.

**Checkpoint**: User Story 1 fully functional and independently testable/shippable.

## Phase 4: User Story 2 — Favourite and log wear (P2)

**Goal**: Toggle favourite; idempotent-per-day wear logging; neither visible on Item detail;
both owner-only; "Log as worn" disabled offline.

**Independent test**: `quickstart.md` steps 4, 5, 7 (favourite, worn-today ×2, offline).

- [ ] T015 [P] [US2] Unit tests for `toggle_favorite` and `record_wear` in
  `backend/tests/unit/test_supabase_closet_repository.py` against a mocked session (toggle
  reads-then-writes the negation; record_wear issues an `ON CONFLICT DO NOTHING` upsert with
  today's date).
- [ ] T016 [US2] Implement `toggle_favorite(self, user_id: str, item_id: str) -> bool | None` in
  `supabase_closet.py`: single transaction, `UPDATE wardrobe_items SET favorite = NOT favorite
  WHERE user_id = :user_id AND id = :item_id RETURNING favorite`, commit, return the new value
  or `None` if no row matched. Depends on T003/T004.
- [ ] T017 [US2] Implement `record_wear(self, user_id: str, item_id: str) -> bool` in
  `supabase_closet.py`: first confirms the item belongs to `user_id` (reuse
  `get_wardrobe_item`, return `False` if `None`), then `INSERT INTO item_wears (item_id,
  user_id, worn_date) VALUES (:item_id, :user_id, CURRENT_DATE) ON CONFLICT (item_id,
  worn_date) DO NOTHING`, commit, return `True`. Depends on T001/T002.
- [ ] T018 [US2] `POST /closet/items/{item_id}/favorite` → `FavoriteToggleResponse{favorite:
  bool}`, 404 if `toggle_favorite` returns `None`; `POST /closet/items/{item_id}/wear` → `204`,
  404 if `record_wear` returns `False`. Both in `backend/src/whattowear/api/v1/routes/closet.py`,
  same malformed-id-is-404 handling as the existing GET. Depends on T016, T017.
- [ ] T019 [P] [US2] Integration tests in `test_closet_routes.py`: favorite toggles true→false
  →true across two calls; wear logs 204 on first and second same-day call; both 404 for a
  foreign item id. Depends on T018.
- [ ] T020 [P] [US2] Integration test proving `item_wears`'s `unique(item_id, worn_date)`
  actually enforces idempotency at the DB level: two direct inserts for the same
  `(item_id, worn_date)` via the app's own `record_wear` (or a raw upsert) leave exactly one
  row (query `item_wears` directly and assert `count == 1`). Depends on T001/T002, T017.
- [ ] T021 [P] [US2] New `TestItemWearsRLS` class in
  `backend/tests/integration/test_wardrobe_rls.py`, same `authenticator`-role direct-connection
  technique as `TestWardrobeItemsRLS`: user A's unfiltered `SELECT`/`INSERT` sees/affects only
  their own `item_wears` rows; user B cannot insert a wear row against user A's `item_id` (the
  policy's `with check (auth.uid() = user_id)` blocks it even though `item_id` itself doesn't
  belong to B — confirms the row's own `user_id`, not `item_id`'s owner, is what RLS checks).
  §9 DoD "RLS proven" item. Depends on T001/T002.
- [ ] T022 [P] [US2] Add a DELETE-isolation case to `TestWardrobeItemsRLS` in
  `test_wardrobe_rls.py`: user B's connection issues an unfiltered `DELETE FROM wardrobe_items
  WHERE id = <user A's item>` and asserts zero rows affected, then a follow-up `SELECT` as user
  A confirms the row still exists. Depends on T001/T002.
- [ ] T023 [P] [US2] `frontend/app/(app)/closet/[itemId]/ItemOverflowSheet.tsx` +
  `.test.tsx`: wraps `BottomSheet`, four rows in fixed order (Edit, "Log as worn today",
  Favorite, Delete — Delete `tone="danger"`), "Log as worn today" `disabled` when `!isOnline`.
  `onSelect` handlers call the passed-in callbacks (`onEdit`, `onLogWorn`, `onToggleFavorite`,
  `onDelete`) and close the sheet. Test asserts row order/labels/tones and that "Log as worn
  today" is disabled when an `isOnline={false}` prop is passed.
- [ ] T024 [US2] Wire `ItemOverflowSheet` into `page.tsx`: `sheetOpen` state, the existing
  `TopHeader`'s `dots` `onClick` opens it (closing gap 004 left — the trigger existed, the sheet
  didn't); `onEdit` sets `editing=true`; `onToggleFavorite` calls the favorite endpoint;
  `onLogWorn` calls the wear endpoint (both fire-and-forget from the UI's perspective — no
  visible state changes per FR-006, so no local state update needed beyond closing the sheet).
  Depends on T014, T023.

**Checkpoint**: User Stories 1 AND 2 both independently functional.

## Phase 5: User Story 3 — Delete an item (P3)

**Goal**: Hard delete behind a confirmation step (design-decisions §22.2); owner-only; removed
item 404s at its own detail URL and disappears from the grid.

**Independent test**: `quickstart.md` step 6.

- [ ] T025 [P] [US3] Unit test for `delete_wardrobe_item` in
  `test_supabase_closet_repository.py` (mocked session: issues `DELETE ... WHERE user_id =
  ... AND id = ...`, commits, returns whether a row was affected).
- [ ] T026 [US3] Implement `delete_wardrobe_item(self, user_id: str, item_id: str) -> bool` in
  `supabase_closet.py`. Depends on T003/T004.
- [ ] T027 [US3] `DELETE /closet/items/{item_id}` in `closet.py`: 204 on success, 404 if
  `delete_wardrobe_item` returns `False` (covers both "never existed" and "not owned").
  Depends on T026.
- [ ] T028 [P] [US3] Integration tests in `test_closet_routes.py`: delete removes the item (a
  follow-up GET 404s); deleting a foreign item 404s and leaves it intact (owner's GET still
  200s); deleting an already-deleted id 404s (not 500). Depends on T027.
- [ ] T029 [P] [US3] Integration test: deleting an item with `item_wears` rows cascades (insert
  a wear via T017's path, delete the item, confirm `item_wears` has zero rows for that
  `item_id`) — proves the migration's `on delete cascade`. Depends on T001/T002, T017, T027.
- [ ] T030 [P] [US3] `frontend/app/(app)/closet/[itemId]/DeleteConfirmDialog.tsx` +
  `.module.css` + `.test.tsx`, modeled directly on
  `frontend/components/calendar/CalendarPrimer.tsx`'s bespoke-`<dialog>` pattern (same
  `showModal`/trigger-refocus-on-close approach, same reduced-motion-gated CSS shape): title
  "Delete {item name}?", body "This can't be undone.", secondary "Cancel", danger-styled
  "Delete" button. Props `open`, `itemName`, `onConfirm`, `onCancel`. Test: renders both
  actions, `onConfirm`/`onCancel` fire on click, `showModal` called when `open` flips true
  (mirrors `CalendarPrimer.test.tsx`'s four assertions).
- [ ] T031 [US3] Wire into `page.tsx`: `deleteDialogOpen` state; overflow sheet's `onDelete`
  opens it instead of deleting immediately; `onConfirm` calls `DELETE
  /api/v1/closet/items/{item_id}` and on success `router.push("/closet")`; `onCancel` just
  closes the dialog. Depends on T024, T030.

**Checkpoint**: All three user stories independently functional — full feature complete.

## Phase 6: Polish & cross-cutting

- [ ] T032 Regenerate `frontend/lib/api/schema.d.ts`: `cd backend && uv run uvicorn
  whattowear.main:app &` then `cd frontend && npm run generate:api-types` (§ handoff warning —
  this file is not committed; regenerate before typecheck/build).
- [ ] T033 [P] Run backend quality gate: `uv run ruff check .`, `uv run ruff format --check .`,
  `uv run mypy .`, `uv run pytest`, `uv run lint-imports` — all clean, backend test count ≥ 549
  (§9 DoD).
- [ ] T034 [P] Run frontend quality gate: `npm run lint`, `npm run typecheck`, `npm test`, `npm
  run build` — all clean, frontend test count ≥ 127 (§9 DoD).
- [ ] T035 Manual browser verification per `quickstart.md`'s 8-step walkthrough, at both
  `localhost:3000` and `127.0.0.1:3000` (§9 DoD, Trap 6 — don't narrow CORS while doing this).
- [ ] T036 Confirm no secret in the diff (`git diff` review) before reporting done.

## Dependencies & execution order

- Phase 1 (T001-T002) blocks everything — the migration must exist and be applied.
- Phase 2 (T003-T005) blocks all three user-story phases — `favorite` must be readable/mappable
  before any route that returns it.
- User Story phases (3, 4, 5) are independent of each other once Phase 2 is done — US2 and US3
  do not depend on US1's edit form, and vice versa. Suggested order follows priority (P1→P2→P3)
  but P2/P3 backend work (T015-T022, T025-T029) could run in parallel with P1's frontend work
  (T012-T014) if split across two contributors — this handoff, however, says run it alone
  (single collision-prone file set, §"How to run this"), so treat phases as sequential within
  one working session.
- Within a phase, `[P]`-marked tasks touch disjoint files and can be done in any order relative
  to each other, but all non-`[P]` tasks in a phase are ordered as listed (later ones depend on
  earlier ones in the same phase).
- Phase 6 runs last, after all three story phases.

## Parallel example (Phase 4, User Story 2)

Once T016-T018 (backend routes) land, T019/T020/T021/T022 (four independent test files/classes)
and T023 (frontend sheet component, unrelated files) can all proceed in parallel — none shares
a file with any other.

## MVP scope

User Story 1 (Edit) alone, after Phase 1+2, is a complete, independently demoable slice: a user
can correct a miscategorized or mistyped item. User Stories 2 and 3 add the two lightweight
toggles and the (confirmed) destructive action on top, each independently shippable.
