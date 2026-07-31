---

description: "Task list for feature 004: Closet (read)"

---

# Tasks: Closet (read)

**Input**: Design documents from `/specs/004-closet-read/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/closet.md, quickstart.md

**Tests**: Included — the handoff requires the RLS isolation proof as an automated test and
requires the existing 459 backend tests to keep passing, so test tasks are not optional here.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US5)

## Path Conventions

- **Frontend**: `frontend/app/(app)/closet/`, `frontend/components/`, `frontend/lib/api/`
- **Backend**: `backend/src/whattowear/`, tests in `backend/tests/{unit,integration}`
- **Infra**: `infra/supabase/migrations/`

---

## Phase 1: Setup

- [ ] T001 Add `NEXT_PUBLIC_API_URL=http://localhost:8000` to `frontend/.env.example` and
      `frontend/.env.local`
- [ ] T002 [P] Add `openapi-typescript` and `openapi-fetch` to `frontend/package.json`
      devDependencies/dependencies; add a `generate:api-types` npm script
      (`openapi-typescript http://localhost:8000/openapi.json -o lib/api/schema.d.ts`)
- [ ] T003 [P] Add `WTW_CLOSET_PAGE_SIZE: int = 20` to `Settings` in
      `backend/src/whattowear/core/config.py`

**Checkpoint**: tooling in place; no product code yet.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The migration, the frozen-contract extension, the repository, and the routes —
every user story needs real data flowing before its screen behavior can be verified.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T004 Write `infra/supabase/migrations/0002_wardrobe_and_catalog_items.sql` per
      `data-model.md`: `catalog_items` and `wardrobe_items` tables, `warmth`/`season` CHECK
      constraints, `wardrobe_items_user_id_idx`, both tables' `updated_at` triggers
      (`public.set_updated_at()`), RLS enabled on both, `wardrobe_items_modify_own` policy
      (`for all using (auth.uid() = user_id) with check (auth.uid() = user_id)`),
      `catalog_items_select_shared` policy (`for select using (true) to authenticated`)
- [ ] T005 Run `cd infra && npx supabase db reset` and confirm it replays cleanly from empty
      (§8 checklist item 1)
- [ ] T006 [P] Add `name: str | None = None` and `notes: str | None = None` to
      `WardrobeItem` and `WardrobeItemPatch` in `backend/src/whattowear/schema.py`
      (research.md §4)
- [ ] T007 [P] Extend `backend/tests/unit/test_schema.py` to cover the new optional
      `name`/`notes` fields (default `None`, accepted when provided)
- [ ] T008 Run `uv run pytest backend/tests -q` and confirm the existing suite is still
      green after T006 (no regression from the additive schema change) before continuing
- [ ] T009 Create `backend/src/whattowear/repositories/__init__.py` (new package)
- [ ] T010 Implement `SupabaseClosetRepository` in
      `backend/src/whattowear/repositories/supabase_closet.py`: `list_wardrobe_items`,
      `list_catalog_items`, `get_derivation_inputs` (returns `([], {})` — feature 010's
      territory, documented in the class docstring per the handoff's instruction to state
      this explicitly), plus the extra `get_wardrobe_item(user_id, item_id)` method
      (research.md §6) — all via parameterized `sqlalchemy.text()` over
      `core.db.get_session`, each query preceded by
      `SELECT set_config('request.jwt.claim.sub', :user_id, true)` in the same transaction
      (research.md §1's forward-compatible, currently-inert-but-correct context call) and
      filtered by `WHERE user_id = :user_id` regardless (the actual guarantee today)
- [ ] T011 [P] `backend/tests/unit/test_supabase_closet_repository.py` — unit-level tests
      against a mocked session for row→`WardrobeItem` mapping, including `name`/`notes`
      passthrough and the derivation-inputs empty-return contract
- [ ] T012 [P] Confirm `adapters.closet_fixture.FixtureClosetRepository` and
      `backend/tests/unit/test_closet_fixture.py` are untouched (no edit — verification
      task only, per the handoff's explicit "keep the fixture" instruction)
- [ ] T013 Implement `GET /api/v1/closet/items` and `GET /api/v1/closet/items/{item_id}` in
      `backend/src/whattowear/api/v1/routes/closet.py` per `contracts/closet.md`:
      `ClosetItemView(WardrobeItem)` with computed `category_group`
      (`categories.group_of(category)`) and `color_names` (`colors.nearest_names(colors)`),
      `ClosetItemsResponse` (route-local), category→group filtering (Bottoms includes
      `full_body`), offset pagination at `WTW_CLOSET_PAGE_SIZE`, 404 with identical shape for
      missing-vs-not-owned, both behind `Depends(get_current_user_id)` — found missing during
      `/speckit-analyze` (C2): without the computed fields, the frontend would have to
      duplicate `categories.py`/`colors.py`'s mapping logic in TypeScript
- [ ] T014 Register the closet router in `backend/src/whattowear/main.py`
      (`app.include_router(closet_router, prefix="/api/v1")`, matching `whoami_router`'s
      existing pattern)
- [ ] T015 [P] `backend/tests/integration/test_closet_routes.py` — real local Supabase:
      seed two users' rows directly, assert 200/401/404 per contract, assert category
      filtering and pagination, assert user A never receives user B's rows through the route
- [ ] T016 [P] `backend/tests/integration/test_wardrobe_rls.py` — the isolation proof
      (research.md §2): connect to port 54322 directly as `authenticator`, `SET ROLE
      authenticated`, `set_config('request.jwt.claim.sub', ...)` per seeded user, assert a
      raw unfiltered `SELECT * FROM wardrobe_items` returns only that user's rows; assert
      `catalog_items` is readable by both without a claim set to anything user-specific
- [ ] T017 Run `uv run pytest backend/tests -q`, `uv run ruff check backend`,
      `uv run ruff format --check backend`, `uv run mypy backend/src`,
      `uv run lint-imports` (from `backend/`) and confirm all clean before starting frontend
      work
- [ ] T018 With the backend running (`uv run uvicorn whattowear.main:app --reload`), run
      `npm run generate:api-types` in `frontend/` to produce `frontend/lib/api/schema.d.ts`;
      commit the generated file
- [ ] T019 Implement `frontend/lib/api/client.ts` — thin `openapi-fetch` wrapper typed
      against the generated `paths`, attaching the current Supabase session's access token as
      `Authorization: Bearer`
- [ ] T020 [P] Implement `useOnlineStatus()` hook in `frontend/lib/useOnlineStatus.ts`
      (`navigator.onLine` + `online`/`offline` window events, research.md §9)
- [ ] T021 [P] Implement `frontend/components/shell/OfflineBanner.tsx` (mounts
      `Banner variant="offline"` from `offline.banner.body` copy, using `useOnlineStatus`)
      and mount it once in `frontend/app/(app)/layout.tsx`

**Checkpoint**: real data flows end-to-end (migration → repository → route → generated
types); every user story below only adds screen behavior on top of this.

---

## Phase 3: User Story 1 - Browse my closet (Priority: P1) 🎯 MVP

**Goal**: `/closet` renders the signed-in user's own items in a responsive grid, with the
desktop two-pane layout.

**Independent Test**: Sign in as a user with seeded items, load `/closet`, confirm the grid
and item count; confirm a second user sees none of the first user's items.

### Implementation for User Story 1

- [ ] T022 [US1] Replace the feature-001 stub at `frontend/app/(app)/closet/page.tsx` with a
      client component fetching `GET /api/v1/closet/items` via `lib/api/client.ts`,
      rendering `TopHeader` (title "Closet", subtitle = item count) and the 2/3/4-column grid
      of placeholder tiles (diagonal-stripe treatment, `design-system.md` § Image treatment)
- [ ] T023 [P] [US1] `frontend/app/(app)/closet/page.module.css` — grid at 2/3/4 columns per
      breakpoint, 120px tile height, 14px radius, tokens only (no raw hex/px outside the
      documented literal-pixel exceptions)
- [ ] T024 [US1] Implement `frontend/app/(app)/closet/[itemId]/page.tsx` — `TopHeader` with
      back navigation and a `dots` right-slot trigger (wired, sheet left empty — feature
      005's), photo placeholder block, details card (Name/Category/Group/Fabric/Colour/Notes
      label-value pairs) — Category reads the response's `category_group`, Group reads
      `category`, Colour reads `color_names.join(", ")`; both computed fields come from the
      API response (T013's `ClosetItemView`), never re-derived on the frontend
- [ ] T025 [P] [US1] `frontend/app/(app)/closet/[itemId]/page.module.css`
- [ ] T026 [US1] Implement the desktop two-pane composition (≥1024px): grid as the wide list
      pane beside an item-detail pane; placeholder copy "Select an item from your closet to
      see its details." when nothing selected; narrower breakpoints push-navigate instead
- [ ] T027 [P] [US1] `frontend/e2e/closet-two-pane.spec.ts` — playwright, confirms the
      two-pane layout at 1024/1440px and single-column push-nav at 320/768px
- [ ] T027a [US1] Add the manual "Load more" text button below the grid in
      `frontend/app/(app)/closet/page.tsx` when `has_more` is true: fetches the next
      `offset`, appends items, shows a "Loading more items…" caption while fetching — not
      infinite scroll (FR-009; found missing from the task list during `/speckit-analyze`,
      C1)
- [ ] T028 [P] [US1] `frontend/components/…` vitest coverage for the grid's item-count
      subtitle and per-item navigation (matching existing component test patterns, e.g.
      `Chip.test.tsx`)

**Checkpoint**: US1 is independently functional — a populated closet renders correctly and
per-user isolation is visible end-to-end, not just at the API layer.

---

## Phase 4: User Story 3 - Open an item's detail (Priority: P1)

**Goal**: `/closet/:itemId` and the desktop detail pane both resolve correctly, including the
not-found case for a missing or not-owned id.

**Independent Test**: Open an owned item from the grid and confirm its fields; request a
random/foreign id directly and confirm the not-found error state.

### Implementation for User Story 3

- [ ] T029 [US3] Add the `item_detail.error` state (`item_detail.error.body`/`.cta` = "Back
      to Closet") to `frontend/app/(app)/closet/[itemId]/page.tsx` for the 404 response
- [ ] T030 [P] [US3] `frontend/e2e/closet-item-detail.spec.ts` — playwright: open an owned
      item end to end; request a foreign item id directly and confirm the not-found state,
      never the foreign item's data

**Checkpoint**: US3 complete — item detail is correct standalone and from the desktop pane.

---

## Phase 5: User Story 2 - Filter by category (Priority: P2)

**Goal**: The category chip row filters the grid client-request-side, including the
`full_body`→Bottoms mapping and the distinct empty-filtered state.

**Independent Test**: Select each chip against a seeded multi-category closet (including one
`full_body` item) and confirm correct membership per chip, plus the empty-filtered state for
a chip with no matches.

### Implementation for User Story 2

- [ ] T031 [US2] Add the single-select `Chip` row (All/Tops/Bottoms/Outerwear/Shoes/
      Accessories) to `frontend/app/(app)/closet/page.tsx`, driving the `category` query
      param; discard in-flight stale requests on filter change (edge case in spec.md)
- [ ] T032 [US2] Render `closet.empty.filtered.body`/`.cta` ("Clear filter") when
      `total === 0` and a filter is active, distinct component/branch from the first-run
      empty state (never both conditions reachable simultaneously)
- [ ] T033 [P] [US2] `frontend/e2e/closet-filter.spec.ts` — playwright: seed items across
      groups including `full_body`, confirm the Bottoms chip includes it, confirm
      empty-filtered copy/action differ from first-run empty

**Checkpoint**: US2 complete — filtering works and the two empty states never collide.

---

## Phase 6: User Story 4 - See my closet is empty and know what to do (Priority: P2)

**Goal**: A zero-item closet shows the first-run empty state, never the filtered one.

**Independent Test**: Brand-new user, zero items, no filter — confirm first-run copy/action.

### Implementation for User Story 4

- [ ] T034 [US4] Render `closet.empty.first_run.body`/`.cta` ("Add your first item" →
      `/add`) in `frontend/app/(app)/closet/page.tsx` when `total === 0` and no filter is
      active
- [ ] T035 [P] [US4] `frontend/components/ui/…` or page-level vitest asserting first-run and
      empty-filtered never render simultaneously and use distinct copy

**Checkpoint**: US4 complete.

---

## Phase 7: User Story 5 - Recover from a failed or offline load (Priority: P3)

**Goal**: Screen-level error state with Retry when online; suppressed in favor of the global
banner when offline.

**Independent Test**: Force a request failure while online → error state with working Retry.
Go offline → global banner shows, screen's own error is suppressed.

### Implementation for User Story 5

- [ ] T036 [US5] Add the loading skeleton (2×2 grid of 120px blocks, 14px radius, per
      `design-system.md` § Per-screen skeleton layouts) to `frontend/app/(app)/closet/page.tsx`
- [ ] T037 [US5] Add `closet.error.body`/`.cta` ("Retry") for a failed fetch, and suppress it
      when `useOnlineStatus()` reports offline (design-system §6 precedence rule) in both
      `frontend/app/(app)/closet/page.tsx` and `frontend/app/(app)/closet/[itemId]/page.tsx`
- [ ] T038 [P] [US5] `frontend/e2e/closet-error-offline.spec.ts` — playwright: mock a 500,
      confirm error+Retry; go offline, confirm the global banner appears and the screen's own
      error copy does not

**Checkpoint**: All five user stories independently functional.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T039 [P] Both-theme visual pass at 320/768/1024/1440px for `/closet` and
      `/closet/:itemId`, every state (§8 checklist item 4) — manual, via `npm run dev`
- [ ] T040 [P] Accessibility pass: 44px hit targets, `:focus-visible` on the chip row and
      grid tiles, one `<h1>` per screen (already `TopHeader`'s), focus moved on navigation
      (existing `FocusOnNavigate`), reduced-motion honored by the skeleton's pulse
- [ ] T041 Run the full quickstart.md validation end to end, including the two-user manual
      isolation check
- [ ] T042 Final gate run: `uv run pytest`, `uv run ruff check .`, `uv run ruff format
      --check .`, `uv run mypy src`, `uv run lint-imports` (backend); `npm run lint`, `npm run
      typecheck`, `npm test`, `npm run build` (frontend) — confirm the §8 checklist's gate row

---

## Dependencies & Execution Order

- **Setup (Phase 1)** → **Foundational (Phase 2)**: strictly sequential, blocks every story.
- **US1 (P1)** and **US3 (P1)**: both depend only on Foundational; US3 reuses US1's grid to
  navigate into detail but its own not-found/error branch is independent — build US1 first
  since US3's "open from the grid" independent test needs a rendered grid to click into.
- **US2 (P2)** depends on US1's grid existing (filters it) but not on US3.
- **US4 (P2)** depends on US1's page shell (adds a branch to the same component) but not on
  US2 or US3.
- **US5 (P3)** depends on US1's page shell (adds loading/error branches) and on the global
  `OfflineBanner` from Foundational; independent of US2/US3/US4.
- **Polish (Phase 8)** depends on all five stories being complete.

## Parallel Opportunities

- T001–T003 (Setup) run in parallel.
- T006/T007 (schema.py) parallel with T004/T005 (migration) — different files — but T008's
  full-suite check should run after both land.
- T011, T012, T015, T016 (backend tests) parallel with each other once T010/T013 exist.
- T020/T021 (offline hook/banner) parallel with T018/T019 (typegen/client) — independent
  concerns.
- Within each user-story phase, the `[P]`-marked test task runs alongside its sibling
  implementation task's review, though the implementation task itself should land first.

## Implementation Strategy

**MVP** = Phase 1 + Phase 2 + Phase 3 (US1). A populated, per-user-isolated closet grid at
every breakpoint is demonstrable and independently valuable before item detail, filtering, or
the empty/error states exist.

**Incremental delivery** thereafter: US3 (detail) → US2 (filter) → US4 (first-run empty) →
US5 (error/offline) → Polish. Each checkpoint leaves the screen in a shippable, honestly
partial state — e.g. after US1+US3 alone, a user with items has a fully working closet; only
users with zero items or a failed request see an unfinished screen, until US4/US5 land.
