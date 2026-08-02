# Tasks: Outfits gallery + detail

**Input**: Design documents from `/specs/010-outfits/` (plan.md, research.md, data-model.md,
contracts/recommend-outfits.md, quickstart.md)

**Tests**: included. The constitution's Quality Bar requires unit tests for deterministic logic,
and the handoff's Definition of Done requires backend/frontend test counts to not drop
(660 / 263 today) plus a two-user RLS+GRANT proof for every new/altered table — not optional here.

**Organization**: grouped by user story from spec.md, in priority order (P1, P1, P2, P3).

## Phase 1: Setup

- [ ] T001 Create `infra/supabase/migrations/0010_outfits_detail.sql` per data-model.md /
      design-decisions.md §38-39: `alter table outfits add column title text` (backfilled from
      `occasion` for existing rows, then `not null`), `add column rationale_with_citations text
      not null default ''`, `add column citations jsonb not null default '[]'::jsonb`,
      `add column dimension_scores jsonb not null default '[]'::jsonb`,
      `add constraint outfits_id_user_id_key unique (id, user_id)`; new `outfit_wears` table
      (`id`, `outfit_id`, `user_id`, `worn_date date not null default current_date`,
      `created_at`, `unique (outfit_id, worn_date)`,
      `foreign key (outfit_id, user_id) references outfits (id, user_id) on delete cascade`),
      RLS (`for all using (auth.uid() = user_id) with check (...)`), and
      `grant select, insert, update, delete on outfit_wears to authenticated`. Verify with
      `npx supabase db reset` (applies `0001`-`0010` clean from empty).

## Phase 2: Foundational (blocks all user stories)

- [ ] T002 In `backend/src/whattowear/repositories/supabase_outfits.py`, add
      `list(user_id, sort: Literal["date", "favorite", "most_worn"] = "date") -> list[dict]`:
      selects `id, title, match_label, favorite, created_at, item_ids` for the caller
      (`WHERE user_id = :user_id`), ordered per `sort` (`created_at desc` / `favorite desc,
      created_at desc` / a `left join` count against `outfit_wears` ordered `desc` — see
      research.md §4 for why `most_worn` needs the new table, not `item_ids`). Returns raw rows;
      thumbnail/item resolution happens in the route (repository stays DB-shaped, matching
      `list_wardrobe_items`'s own convention of returning plain data, not view models).
- [ ] T003 [P] In `supabase_outfits.py`, add
      `get(user_id, outfit_id) -> dict | None`: full row (`SELECT *`) filtered by
      `WHERE user_id = :user_id AND id = :outfit_id`, `None` if not found/not owned — same
      convention as every other repository method in this file.
- [ ] T004 [P] In `supabase_outfits.py`, add `delete(user_id, outfit_id) -> bool`: single
      `DELETE ... WHERE user_id = :user_id AND id = :outfit_id RETURNING id` (relies on
      `outfit_wears`' `on delete cascade`), `True`/`False` on row-found, mirroring
      `supabase_closet.py::delete_wardrobe_item`'s exact shape.
- [ ] T005 [P] In `supabase_outfits.py`, add `rename(user_id, outfit_id, title) -> str | None`:
      single `UPDATE outfits SET title = :title WHERE user_id = :user_id AND id = :outfit_id
      RETURNING title`, `None` if not found/not owned. Caller (the route) is responsible for
      rejecting an empty/whitespace title before calling this — the repository itself doesn't
      re-validate, matching this file's existing division of concerns (routes validate request
      shape, repositories trust their callers).
- [ ] T006 In `supabase_outfits.py`, add
      `log_worn(user_id, outfit_id, owned_item_ids: list[str]) -> bool` per design-decisions.md
      §39: in one transaction, ownership-precheck `outfit_id` (`SELECT 1 FROM outfits WHERE
      user_id = ... AND id = ...`, return `False` if missing), then
      `INSERT INTO outfit_wears (outfit_id, user_id, worn_date) VALUES (..., ..., CURRENT_DATE)
      ON CONFLICT (outfit_id, worn_date) DO NOTHING`, then for every id in `owned_item_ids`
      (the caller passes only ids the user currently owns — filtering happens in the route via
      the existing `list_wardrobe_items`, mirroring how `save_outfit` already validates
      ownership) the exact `item_wears` upsert `record_wear` already uses. Returns `True`.
- [ ] T007 [P] `backend/tests/unit/test_supabase_outfits_repository.py`: unit-test every method
      added in T002-T006 — `list` ordering for all three `sort` values, `get`/`delete`/`rename`
      returning `None`/`False` for another user's or a nonexistent id, `log_worn` writing exactly
      one `outfit_wears` row and one `item_wears` row per owned item on repeat same-day calls,
      and skipping an id not in `owned_item_ids`.
- [ ] T008 In `backend/src/whattowear/api/v1/routes/recommend.py`, add a small
      `_get_state_for_thread(thread_id) -> dict | None` helper wrapping
      `get_compiled_graph(repository).get_state({"configurable": {"thread_id": thread_id}})`,
      returning `.values` or `None` if the snapshot is empty (LangGraph returns an empty
      `StateSnapshot` for an unknown thread, not an exception) — used by T009.
- [ ] T009 In `recommend.py`, change `SaveOutfitRequest` to add a required `thread_id: str`, and
      change `save_outfit` per design-decisions.md §38: call `_get_state_for_thread(thread_id)`;
      if the state exists and `state.get("user_id") == user_id`, find the `ScoredOutfit` in
      `state.get("last_result").outfits` (if `last_result` is not `None`) whose `.items` list
      equals `body.item_ids` exactly (ordered); if found, build `rationale_with_citations` (the
      `[n]`-marker-injection logic from `git show bdc9ad4` — resurrect verbatim, adapted to
      return the marked-up string instead of mutating a response field) and `citations`
      (`[{number, text}]` from the same `seen`/numbering logic, `text` = the matching
      `SuggestResult.sources` entry's `.source`) and `dimension_scores`
      (`[{"dimension": s.dimension, "value": s.value} for s in outfit.scores]`); on any miss
      (no state, wrong user, no match), use empty defaults for all three. Pass `title` (seeded
      from `body.occasion`, §36) and the three new fields to a widened
      `SupabaseOutfitRepository.create(...)` call.
- [ ] T010 In `supabase_outfits.py`, widen `create(...)` to accept and insert `title,
      rationale_with_citations, citations, dimension_scores` alongside the existing fields
      (`citations`/`dimension_scores` inserted as JSON via SQLAlchemy's `text()` cast, matching
      how this file already passes `item_ids` as a Postgres array param).
- [ ] T011 [P] `backend/tests/unit/test_supabase_outfits_repository.py`: extend for the widened
      `create` — round-trips `title`/`rationale_with_citations`/`citations`/`dimension_scores`
      correctly, including the all-empty-defaults path.
- [ ] T012 [P] `backend/tests/integration/test_recommend_routes.py`: extend `save_outfit` tests
      for the `thread_id` happy path (a real invoked thread with citations → row has non-empty
      `citations`/`dimension_scores`) and every degrade path (missing `thread_id` in state store,
      `thread_id` belonging to another user, `item_ids` that don't match any outfit in
      `last_result` → row has empty defaults, `201` still returned).

**Checkpoint**: repository + save-time capture complete — every user story phase below can now
proceed independently.

---

## Phase 3: User Story 1 - Browse saved outfits (P1)

**Goal**: `/outfits` lists every saved outfit, newest first, with title/match/date/thumbnails.

**Independent Test**: save 2+ outfits, open `/outfits`, confirm all appear correctly ordered.

- [ ] T013 [US1] Add `GET /recommend/outfits` to `recommend.py` per
      contracts/recommend-outfits.md: `OutfitSummary`/`OutfitSummaryListResponse` models; calls
      `outfit_repository.list(user_id, sort)`, resolves each row's first-4 `item_ids` into
      `RecommendItemView` thumbnails (reusing the existing `storage.create_signed_urls` +
      `RecommendItemView.from_wardrobe_item` helpers already in this file), sets `item_count` to
      `len(item_ids)`.
- [ ] T014 [P] [US1] `backend/tests/integration/test_recommend_routes.py`: `GET /recommend/outfits`
      returns the caller's outfits only, newest-first by default, correct `item_count`/thumbnail
      truncation at 4/5 items, empty list for a user with none.
- [ ] T015 [US1] Create `frontend/app/(app)/outfits/OutfitsGrid.tsx` mirroring
      `app/(app)/closet/ClosetGrid.tsx`'s structure: fetches `GET /api/v1/recommend/outfits`,
      renders the vertically-stacked card list per design-system.md § Outfits (gallery) — header
      row (title, match-label pill, spacer, favorite heart, "⋯"), item row (≤4 real thumbnails,
      "+N" chip past 4 in the 4th slot, real thumbnails link to `/closet/:itemId`, chip links to
      `/outfits/:id`), date line. Accepts an optional `selectedOutfitId` prop (mirrors
      `ClosetGrid`'s `selectedItemId`) for the desktop two-pane highlight.
- [ ] T016 [P] [US1] `frontend/app/(app)/outfits/OutfitsGrid.module.css`: card styling
      (`radius-lg`, surface fill, bordered, 14px padding, `gap: 12px` between cards) per
      design-system.md's literal values; loading skeleton (two 100px blocks, 16px radius) and
      the `outfits.empty.first_run.*`/`outfits.error.*` states, reusing the existing pattern from
      `app/(app)/outfits/page.tsx`'s current stub.
- [ ] T017 [US1] Rewrite `frontend/app/(app)/outfits/page.tsx` (replacing the stub): `TopHeader`
      (title "Outfits", subtitle = count), renders `<OutfitsGrid/>` inside a `.twoPane` wrapper
      beside a `.detailPane` placeholder ("Select an outfit to see its details.") — mirrors
      `app/(app)/closet/page.tsx` exactly.
- [ ] T018 [P] [US1] `frontend/app/(app)/outfits/page.module.css`: `.twoPane`/`.gridPane`/
      `.detailPane` media-query classes, copied from `app/(app)/closet/page.module.css`'s exact
      breakpoint values (≥1024px two-pane).
- [ ] T019 [P] [US1] `frontend/app/(app)/outfits/page.test.tsx` (new) and
      `OutfitsGrid.test.tsx` (new): loading/empty/error/loaded-with-items states, "+N" chip
      rendering and its link target, real-thumbnail link targets.

**Checkpoint**: gallery is independently browsable and testable.

---

## Phase 4: User Story 2 - See the full reasoning behind a saved outfit (P1)

**Goal**: `/outfits/:outfitId` shows every item, cited description, rule list, match breakdown —
no number/percentage ever rendered.

**Independent Test**: open a saved outfit's detail; verify items/citations/rules/bars per
quickstart.md scenario 3.

- [ ] T020 [US2] Add `GET /recommend/outfits/{outfit_id}` to `recommend.py` per
      contracts/recommend-outfits.md: `OutfitDetailResponse` model; calls
      `outfit_repository.get(user_id, outfit_id)`, `404` if `None`; re-resolves `items` live from
      `repository.list_wardrobe_items(user_id)` (Constitution IV — silently drops any `item_ids`
      entry no longer owned, never errors); returns `rationale_text`,
      `rationale_with_citations`, `citations`, `dimension_scores`, `match_label`, `favorite`,
      `title`, `occasion`, `created_at` verbatim from the row.
- [ ] T021 [P] [US2] `backend/tests/integration/test_recommend_routes.py`: `GET
      /recommend/outfits/{id}` happy path (all fields present, items re-resolved), `404` for
      another user's/nonexistent id, an outfit whose `item_ids` includes a since-deleted item
      (item silently omitted from `items`, no error).
- [ ] T022 [US2] Create `frontend/app/(app)/outfits/[outfitId]/RationaleWithCitations.tsx`:
      resurrect `renderWithCitations`/`CITATION_TOKEN` from `git show
      c545533:frontend/components/recommend/ChatMessageList.tsx` — parses `[n]` tokens out of
      `rationale_with_citations` and renders each as a `<Badge tone="citation">`, falling back to
      plain `rationale_text` (no parsing) when `rationale_with_citations` is empty.
- [ ] T023 [P] [US2] Create `frontend/app/(app)/outfits/[outfitId]/CitedRuleList.tsx` +
      `CitedRuleList.module.css`: resurrect `git show
      c545533:frontend/components/recommend/CitedRuleList.tsx` (dashed top-border numbered list,
      digit + `textCaption` explanation), adapted to accept `citations: {number, text}[]` and
      render nothing when empty.
- [ ] T024 [P] [US2] Create `frontend/app/(app)/outfits/[outfitId]/MatchBreakdown.tsx`: "Match
      level: {label}" row using the same pill markup as the gallery card, then one bar per
      `dimension_scores` entry (`--color-primary` fill width = `value * 100%`, `--color-
      surface-sunken` track, per § Scores) — bar width is the *only* place `value` is consumed;
      confirm no JSX anywhere in this file interpolates `value` into visible text.
- [ ] T025 [US2] Create `frontend/app/(app)/outfits/[outfitId]/page.tsx`: `TopHeader` (title =
      outfit title, subtitle = date, favorite heart + "⋯" as sibling icon controls per §
      Outfit detail item 1), one surface card containing (a) the item grid (`ItemPhoto`,
      `aspect-ratio:1`, `radius-md`, 2-col mobile/3-col tablet+, no cap/scroll/chip), (b)
      `<RationaleWithCitations/>`, (c) a dashed-border `<CitedRuleList/>`, (d) a second dashed
      divider then `<MatchBreakdown/>`. Loading skeleton (2-col thumbnail grid + one description
      bar, per design-system.md's Outfit detail skeleton spec) and a not-found/error state
      (`outfit_detail.error.*` — new copy pair matching the existing table's voice, per
      data-model.md's per-screen-states note) with a back-to-`/outfits` action. Renders beside
      `<OutfitsGrid selectedOutfitId={outfitId}/>` in the `.gridPane` at desktop width, mirroring
      `app/(app)/closet/[itemId]/page.tsx`'s exact two-pane composition.
- [ ] T026 [P] [US2] `frontend/app/(app)/outfits/[outfitId]/page.module.css`: item grid, card,
      and skeleton styling per design-system.md's literal values (§ Image treatment's Outfit
      detail row: fraction-based `aspect-ratio:1`, 14px radius).
- [ ] T027 [P] [US2] Test files: `RationaleWithCitations.test.tsx` (marker parsing, empty
      fallback), `CitedRuleList.test.tsx` (renders nothing when empty, correct numbering),
      `MatchBreakdown.test.tsx` (bar widths, **asserts no numeric/percentage text node exists
      anywhere in the rendered output** — this is the test that directly guards Constitution II /
      FR-004 / SC-003 for this component), `[outfitId]/page.test.tsx` (loading/error/loaded
      states, item grid column count at each breakpoint via a matchMedia mock).

**Checkpoint**: detail page fully explains a saved outfit; gallery + detail together are a
complete browsing experience (P1s done).

---

## Phase 5: User Story 3 - Manage a saved outfit (P2)

**Goal**: log worn, rename, favorite, delete (with confirmation) all work from gallery card and/or
detail's overflow menu, staying in sync.

**Independent Test**: from detail, log worn twice (one effect), rename, delete with confirm, per
quickstart.md scenarios 4-6.

- [ ] T028 [US3] Add `PATCH /recommend/outfits/{outfit_id}/title` to `recommend.py`: rejects
      empty/whitespace `title` (`422`) before calling `outfit_repository.rename(...)`, `404` if
      `None` returned.
- [ ] T029 [P] [US3] Add `POST /recommend/outfits/{outfit_id}/wear` to `recommend.py`: fetches
      `owned_item_ids` by intersecting the outfit's `item_ids` (from `outfit_repository.get(...)`,
      `404` if missing) with `{item.id for item in repository.list_wardrobe_items(user_id)}`,
      calls `outfit_repository.log_worn(user_id, outfit_id, owned_item_ids)`, `204` on success.
- [ ] T030 [P] [US3] Add `DELETE /recommend/outfits/{outfit_id}` to `recommend.py`: calls
      `outfit_repository.delete(...)`, `404` if `False`, `204` on success.
- [ ] T031 [P] [US3] `backend/tests/integration/test_recommend_routes.py`: rename (happy path,
      `422` on blank, `404` for another user's id), wear (happy path writes both tables, repeat
      same-day call stays at one row each, `404` for another user's id, an owned-item skip when
      the outfit references a removed item), delete (happy path, `404` for another user's id,
      `outfit_wears` rows cascade-deleted).
- [ ] T032 [US3] Create `frontend/app/(app)/outfits/[outfitId]/OutfitOverflowSheet.tsx` mirroring
      `app/(app)/closet/[itemId]/ItemOverflowSheet.tsx`'s exact pattern: rows "Log as worn today"
      (disabled when offline), "Edit title", "Delete" (`tone: "danger"`) — no separate Favorite
      row per design-system.md (the heart is the header's own direct control, not routed through
      this sheet, per § Outfit detail item 3).
- [ ] T033 [P] [US3] Create `frontend/app/(app)/outfits/[outfitId]/DeleteOutfitDialog.tsx` +
      `.module.css` mirroring `app/(app)/closet/[itemId]/DeleteConfirmDialog.tsx` verbatim
      (title `Delete {outfit title}?`, body `This can't be undone.`, outline Cancel + danger
      Delete, focus capture/restore via the same `useModalDialog` hook), parameterized by outfit
      title instead of item name.
- [ ] T034 [US3] Wire `[outfitId]/page.tsx` to the three new sheet actions (log worn → `POST
      .../wear`; edit title → inline rename, see T035; delete → open `DeleteOutfitDialog`, on
      confirm `DELETE ...` then `router.push("/outfits")`) and the header favorite heart (`POST
      .../favorite`, existing route, local state flip on success).
- [ ] T035 [US3] Add inline title rename to `OutfitsGrid.tsx`'s card (tap title → text input +
      "Done" pill, per § Outfits gallery item 2 — on-card, not in a sheet): calls `PATCH
      .../title` on Done, updates local list state on success, reverts input on `422`/failure
      without crashing. Also add the gallery card's own favorite-heart tap handler (`POST
      .../favorite`) and its "⋯" → a lightweight card-level menu offering the same actions as
      T032 (or reuses `OutfitOverflowSheet` if the card can host it — implementer's call, keep
      the favorite state read from/written to the same field either way).
- [ ] T036 [P] [US3] Disable (not hide) wear/rename/favorite/delete controls while offline —
      reuse the existing `useOnlineStatus` hook (`app/(app)/closet/[itemId]/page.tsx`'s own
      pattern) in both `OutfitsGrid.tsx` and `[outfitId]/page.tsx`.
- [ ] T037 [P] [US3] Test files: `OutfitOverflowSheet.test.tsx`, `DeleteOutfitDialog.test.tsx`
      (confirm/cancel behavior, focus restore), extend `page.test.tsx`/`OutfitsGrid.test.tsx` for
      rename (blank-input rejection), favorite sync across card/header/sheet, offline-disabled
      controls, and the full delete-confirm-then-remove flow.

**Checkpoint**: full outfit lifecycle management works from both surfaces.

---

## Phase 6: User Story 4 - Sort saved outfits (P3)

**Goal**: sort by date added (default) / favorited-first / most worn. No filter facets (§41).

**Independent Test**: outfits with varied dates/favorites/worn-counts; each sort reorders
correctly; per quickstart.md scenario in spirit (not separately numbered there since it's the
lowest-priority story).

- [ ] T038 [US4] Create `frontend/app/(app)/outfits/SortSheet.tsx`: a `BottomSheet`-based trigger
      (the "Filter & sort" pill per § Outfits gallery item 1, using Lucide `sliders-horizontal`
      via `IconButton`'s existing `filter` keyword) offering three single-select rows — Date
      added / Favorited first / Most worn — no filter chips, no active-count badge, no "Clear"
      link (§41: nothing is ever in a filtered state this feature).
- [ ] T039 [US4] Wire `SortSheet`'s selection into `OutfitsGrid.tsx`'s fetch (`?sort=...` query
      param) and `page.tsx`'s header (mount the sort trigger beside `TopHeader`).
- [ ] T040 [P] [US4] `SortSheet.test.tsx` + extend `OutfitsGrid.test.tsx`: each sort option
      re-fetches with the right query param and re-renders in the new order.

**Checkpoint**: all four user stories complete.

---

## Phase 7: Polish & Cross-Cutting

- [ ] T041 [P] `backend/tests/integration/test_outfit_wears_rls.py` (new): two-user RLS+GRANT
      proof mirroring `test_wardrobe_rls.py::TestItemWearsRLS` exactly — user B cannot
      `SELECT`/`UPDATE`/`DELETE` user A's `outfit_wears` rows, and
      `test_user_cannot_insert_a_wear_row_against_another_users_outfit` (forged
      `(outfit_id, user_id)` pair → `psycopg.errors.ForeignKeyViolation`, mirroring the item
      version's exact assertion).
- [ ] T042 [P] Extend `backend/tests/integration/test_outfits_rls.py` for the new columns
      (`title`, `rationale_with_citations`, `citations`, `dimension_scores`) — confirm they're
      covered by the existing RLS policy/GRANT with no separate policy needed (same table, same
      policy already proven; this task is the two-user proof that the new columns don't leak
      through some other path, e.g. a view or a default-permissive grant).
- [ ] T043 Run `npm run generate:api-types` against the running backend (handoff trap #6) and
      commit the regenerated `frontend/lib/api/schema.d.ts` — never hand-edited.
- [ ] T044 Verify Constitution I: `git diff rebuild...HEAD -- backend/src/whattowear/pipeline
      backend/src/whattowear/scoring backend/src/whattowear/retrieval` is empty; if it isn't,
      re-run `uv run python -m evals.harness` (or this repo's equivalent entry point) and compare
      against `docs/eval-baselines/`, justifying every movement before merge.
- [ ] T045 Run the full CI-equivalent gate locally: backend `ruff check`, `ruff format --check`,
      `mypy src`, `uv run pytest` (≥660 passing), `lint-imports`; frontend `eslint`,
      `tsc --noEmit`, `npm test` (≥263 passing), `next build`.
- [ ] T046 Execute `quickstart.md` end-to-end against the running local stack (both dev server
      hostnames per the handoff — `localhost:3000` and `127.0.0.1:3000` — both light/dark themes,
      mobile and desktop widths), and directly inspect a saved outfit's row in Postgres per
      quickstart.md scenario 1 to confirm citations/dimension_scores actually reached storage,
      not just a `201`.

## Dependencies & execution order

- **Phase 1 → Phase 2 → all user story phases.** Phase 2 (T002-T012) is a hard prerequisite for
  every story: US1 needs `list`, US2 needs `get` + the save-time capture (T008-T010) to have
  anything to show, US3 needs `delete`/`rename`/`log_worn`, US4 needs `list`'s `sort` param.
- **US1 (Phase 3) and US2 (Phase 4) can proceed in parallel** once Phase 2 is done — they touch
  disjoint route/component sets (list vs. detail) and neither's frontend imports the other's.
- **US3 (Phase 5) depends on US1's `OutfitsGrid.tsx` existing** (T035 edits it) and **US2's
  `[outfitId]/page.tsx` existing** (T034 edits it) — sequence after both, or coordinate carefully
  if parallelized.
- **US4 (Phase 6) depends on US1's `OutfitsGrid.tsx`/`page.tsx` existing** (T039 edits them).
- **Phase 7** runs last, after all stories.
- **MVP scope**: Phase 1 + Phase 2 + Phase 3 (US1) alone delivers a browsable, if unmanageable and
  unexplained, gallery — not a meaningful demo on its own. **Recommended real MVP is Phase 1 +
  Phase 2 + Phase 3 + Phase 4 (both P1 stories)**: browse *and* understand every saved outfit,
  which is the feature's own stated mission in full; US3 (manage) and US4 (sort) are genuinely
  incremental on top.

## Parallel execution examples

- Within Phase 2: T003, T004, T005 (independent repository methods, same file but non-
  overlapping method bodies — coordinate if working literally simultaneously) then T007, T011,
  T012 (independent test files) in parallel with each other.
- Within Phase 3: T014 (backend test) run in parallel with T015-T018 (frontend); T019 last
  (depends on T015-T018 existing).
- Within Phase 4: T021 (backend test) in parallel with T022-T026 (frontend); T027 last.
- Across Phase 3/4: once Phase 2 is merged, one implementer can take US1 (T013-T019) while
  another takes US2 (T020-T027) simultaneously.
