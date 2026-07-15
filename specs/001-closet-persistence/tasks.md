---

description: "Task list for Closet Persistence (001)"
---

# Tasks: Closet Persistence

**Input**: Design documents from `/specs/001-closet-persistence/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/wardrobe-api.md](./contracts/wardrobe-api.md), [quickstart.md](./quickstart.md)

**Tests**: Included. Not requested by the spec itself, but the project
constitution's Quality Bar mandates unit tests for deterministic logic, and
every task in this feature is deterministic CRUD/auth logic.

**Organization**: Tasks are grouped by user story (spec.md priorities:
US1/US2 = P1, US3 = P2, US4 = P3) so each story can be implemented and
verified independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Maps the task to US1/US2/US3/US4
- File paths are relative to the repo root

---

## Phase 1: Setup

**Purpose**: Add the new dependencies and migration scaffolding this feature needs.

- [X] T001 Add `sqlalchemy`, `alembic`, `psycopg[binary]`, `pyjwt[crypto]` (the `crypto` extra is needed for ES256/JWKS verification) to `backend/pyproject.toml`; run `uv sync`
- [X] T002 Initialize Alembic scaffolding in `backend/alembic/` (`alembic.ini`, `alembic/env.py`) wired to read `DATABASE_URL` (Supabase transaction pooler, port 6543) the same way `config.py` reads other env vars; support an optional `DATABASE_URL_DIRECT` (port 5432) for running migrations off the pooler if needed — see research.md → "Supabase transaction pooler" for the prepared-statement gotcha this avoids

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core persistence, models, auth, and seed data — every user story needs these.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T003 [P] Create SQLAlchemy engine/session factory in `backend/src/whattowear/db.py`
- [X] T004 [P] Create ORM models `WardrobeItemRow` and `CatalogItemRow` in `backend/src/whattowear/models.py` per [data-model.md](./data-model.md) — suffixed `Row` to avoid shadowing the frozen Pydantic `WardrobeItem` in `schema.py` (`category`, `colors` JSONB, `fabric` nullable, `warmth` with `CHECK BETWEEN 0 AND 5`, `formality`, `season` JSONB, `created_at`, `updated_at`; `WardrobeItemRow` additionally: `user_id` UUID indexed **no FK**, `source` default `'catalog'`, `catalog_item_id` nullable FK to `catalog_items.id`)
- [X] T005 Generate and review Alembic migration `0001_initial_wardrobe_schema` in `backend/alembic/versions/` from the models in T004 (depends on T002, T003, T004)
- [X] T006 [P] Add `fabric: Optional[str] = None` and `source: Optional[Literal["catalog", "upload"]] = None` to `WardrobeItem` in `backend/src/whattowear/schema.py`
- [X] T007 Create the FastAPI JWT-verification dependency `get_current_user_id` in `backend/src/whattowear/auth.py` — verifies the Supabase JWT signature with `pyjwt`'s `PyJWKClient` against the project's JWKS endpoint (ES256, `audience="authenticated"`), returns the `sub` claim as `user_id`; no local `users` table lookup. See research.md → "JWT verification" for the ES256-vs-HS256 decision and the fallback if the project still issues HS256 tokens (depends on T001)
- [X] T008 Implement `seed_catalog()` in `backend/src/whattowear/crud.py` — loads `data/fixtures/wardrobe.json` into `catalog_items` (`fabric` left `NULL`, no `source` column on this table) (depends on T004, T005)
- [X] T009 Implement `seed_eval_baseline_user()` in `backend/src/whattowear/crud.py` — seeds a fixed, well-known `EVAL_BASELINE_USER_ID`'s `wardrobe_items` with the same 40 items from `data/fixtures/wardrobe.json` (same ids/attributes, `source='catalog'`). **Seed closet items only — no memory preferences** for this user, so `memory.profile_note()` stays `None` and generation behavior matches today's fixture-based runs exactly (see T014 for why this matters to the eval gate) (depends on T004, T005)
- [X] T010 [P] Unit tests for `auth.get_current_user_id` (valid token → user_id, invalid/expired token → rejected) in `backend/tests/unit/test_auth.py`
- [X] T011 [P] Unit tests for `seed_catalog()` and `seed_eval_baseline_user()` (all 40 catalog items present with `fabric` NULL; eval user's 40 closet items match the fixture ids/attributes; eval user has no seeded preferences) in `backend/tests/unit/test_seed.py`

**Checkpoint**: Foundation ready — user story implementation can now begin.

---

## Phase 3: User Story 1 - View my closet (Priority: P1) 🎯 MVP

**Goal**: A user can see every item in their own closet, with all attributes, and never sees another user's items.

**Independent Test**: Seed closet rows directly for two users; `GET /wardrobe/items` for each returns only that user's items with full attributes; a user with no rows gets an empty list, not an error.

- [X] T012 [P] [US1] `list_wardrobe_items(user_id)` in `backend/src/whattowear/crud.py`, mapping ORM rows → `WardrobeItem`
- [X] T013 [US1] `GET /wardrobe/items` endpoint in `backend/src/whattowear/api.py`, using T007's auth dependency (depends on T007, T012)
- [X] T014 [US1] Switch wardrobe retrieval to Postgres **and rewire the eval harness** (depends on T009, T012):
  - Update `load_wardrobe()` in `backend/src/whattowear/pipeline/context_assembler.py` to take a `user_id` and call `crud.list_wardrobe_items(user_id)` instead of reading `data/fixtures/wardrobe.json`
  - Thread `user_id` through the `assemble_context()` call site so the pipeline passes it down
  - Update `eval/harness.py::run_case()` to pass `EVAL_BASELINE_USER_ID` to `run_pipeline()` — currently it passes neither `wardrobe` nor `user_id`, which after this change would read an empty closet and silently break the no-regression gate. This is the wiring that makes T017 meaningful.
- [X] T015 [P] [US1] Unit tests for `list_wardrobe_items` (empty closet, multi-item closet, cross-user isolation, **an accessory-category item is returned identically to a garment** — FR-005) in `backend/tests/unit/test_crud.py`
- [X] T016 [US1] Integration test for `GET /wardrobe/items` (two users, isolation, empty state, **a ~200-item closet returns fully in one call** — SC-001) in `backend/tests/integration/test_wardrobe_view.py` (depends on T013)
- [X] T017 [US1] Re-run the existing eval harness (`backend/evals`) against the Postgres-seeded eval baseline user and diff against `backend/artifacts/eval_runs/` — spec FR-012 / SC-005, constitution Principle I gate. Scores must match exactly (depends on T014)

**Checkpoint**: US1 is fully functional and independently testable; retrieval behavior is confirmed unregressed.

---

## Phase 4: User Story 2 - Add an item from the shared catalog (Priority: P1) 🎯 MVP

**Goal**: A user can browse the shared catalog and add an item to their own closet as an independent copy.

**Independent Test**: From a seeded catalog, `POST` one item as user A; it appears in A's closet with full attributes and does not appear for user B.

- [X] T018 [P] [US2] `list_catalog_items()` in `backend/src/whattowear/crud.py`
- [X] T019 [US2] `GET /catalog/items` endpoint in `backend/src/whattowear/api.py` (depends on T007, T018)
- [X] T020 [P] [US2] `add_wardrobe_item_from_catalog(user_id, catalog_item_id)` in `backend/src/whattowear/crud.py` — copies the catalog row's attributes into a new `wardrobe_items` row, `source='catalog'`, `catalog_item_id` set for provenance only (FR-011) (depends on T004)
- [X] T020a [P] [US2] `add_wardrobe_items_from_catalog(user_id, catalog_item_ids)` bulk variant in `backend/src/whattowear/crud.py` — added post-implementation (user feedback: bulk-populate a test closet in one call, plus a real "add several at once" product need); all-or-nothing (validates every id exists before inserting any), duplicates in the list allowed (depends on T004)
- [X] T021 [US2] `POST /wardrobe/items` endpoint in `backend/src/whattowear/api.py`, 404 on unknown `catalog_item_id` (depends on T007, T020)
- [X] T021a [US2] `POST /wardrobe/items/bulk` endpoint in `backend/src/whattowear/api.py` — see contracts/wardrobe-api.md; 404 naming the offending id(s) if any is unknown (depends on T007, T020a)
- [X] T022 [P] [US2] Unit tests for `add_wardrobe_item_from_catalog` (copy semantics, unknown id, adding the same catalog item twice creates two independent rows, **adding an accessory-category catalog item works identically** — FR-005) in `backend/tests/unit/test_crud.py`
- [X] T022a [P] [US2] Unit tests for `add_wardrobe_items_from_catalog` (bulk insert, duplicate ids in one batch, any-unknown-id rejects the whole batch and inserts nothing) in `backend/tests/unit/test_crud.py`
- [X] T023 [US2] Integration test for `POST /wardrobe/items` + `GET /catalog/items` (empty catalog, add flow, cross-user isolation) in `backend/tests/integration/test_wardrobe_add.py` (depends on T019, T021)
- [X] T023a [US2] Integration test for `POST /wardrobe/items/bulk` (all-succeed, any-unknown-id rejects the batch atomically) in `backend/tests/integration/test_wardrobe_add.py` (depends on T021a)

**Checkpoint**: US1 + US2 both work independently — a closet can now be viewed and meaningfully populated. This is the MVP.

---

## Phase 5: User Story 3 - Correct an item's attributes (Priority: P2)

**Goal**: A user can correct any attribute of an owned item; every validated field (`formality`, `season`, `warmth`, `colors`) is checked and rejected cleanly when invalid, while `category` stays open-ended.

**Independent Test**: Correct an owned item's formality and confirm it persists; attempt an invalid formality, season, warmth (out of 0-5), or malformed hex color and confirm each is rejected with a clean validation error and the prior value retained; correct category to an unrecognized value and confirm it's accepted (buckets to `accessory`).

- [ ] T024 [P] [US3] `update_wardrobe_item(user_id, item_id, patch)` in `backend/src/whattowear/crud.py` — 404 if not found or not owned by `user_id`; validates **all** constrained fields at the Pydantic boundary before persisting so an invalid value never reaches (and 500s against) the DB `CHECK`: out-of-vocabulary `formality`/`season`, `warmth` outside 0-5, and malformed hex `colors` are all rejected; `category` accepts any value (FR-007, data-model.md validation rules) (depends on T004)
- [ ] T025 [US3] `PATCH /wardrobe/items/{id}` endpoint in `backend/src/whattowear/api.py`, returns `422` on any invalid `formality`/`season`/`warmth`/`colors` value (depends on T007, T024)
- [ ] T026 [P] [US3] Unit tests for `update_wardrobe_item` (valid correction; invalid formality, invalid season, out-of-range warmth, and malformed hex color each rejected with prior value retained; unrecognized category accepted and buckets to accessory; correcting an accessory-category item works — FR-005; cross-user correction is 404) in `backend/tests/unit/test_crud.py`
- [ ] T027 [US3] Integration test for `PATCH /wardrobe/items/{id}` — valid correction plus a 422 for each invalid field class — in `backend/tests/integration/test_wardrobe_correct.py` (depends on T025)

**Checkpoint**: US1-US3 all work independently.

---

## Phase 6: User Story 4 - Remove an item (Priority: P3)

**Goal**: A user can remove an owned item; a repeated or cross-user delete is handled safely, not as a crash.

**Independent Test**: Remove one of several items and confirm only it disappears; delete it again and confirm idempotent handling; attempt to delete another user's item and confirm 404.

- [ ] T028 [P] [US4] `delete_wardrobe_item(user_id, item_id)` in `backend/src/whattowear/crud.py` — hard delete, safe on an already-deleted or not-owned id (depends on T004)
- [ ] T029 [US4] `DELETE /wardrobe/items/{id}` endpoint in `backend/src/whattowear/api.py` (depends on T007, T028)
- [ ] T030 [P] [US4] Unit tests for `delete_wardrobe_item` (normal delete, repeated delete, cross-user delete, deleting an accessory-category item — FR-005) in `backend/tests/unit/test_crud.py`
- [ ] T031 [US4] Integration test for `DELETE /wardrobe/items/{id}` in `backend/tests/integration/test_wardrobe_remove.py` (depends on T029)

**Checkpoint**: All four user stories independently functional.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T032 [P] `uv run ruff check` / format all new and modified files in `backend/`
- [ ] T033 Walk through `quickstart.md` end-to-end by hand (seed, view, add, correct, remove, two-user isolation)
- [ ] T034 Final re-run of the full eval harness after all stories are implemented; confirm scores still match `backend/artifacts/eval_runs/` (depends on all prior tasks)
- [ ] T035 [P] Update `docs/SDD-HANDOFF.md`'s "Not built yet" list — items 1 (Database) and 2 (Closet CRUD and auth) are now done

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies
- **Foundational (Phase 2)**: depends on Setup — blocks all user stories
- **User Stories (Phase 3-6)**: all depend on Foundational; independent of each other, can proceed in parallel or in priority order (US1 → US2 → US3 → US4)
- **Polish (Phase 7)**: depends on all desired user stories being complete

### Within Each Story

- CRUD function before its endpoint
- Endpoint before its integration test
- Unit tests for a story's CRUD functions can run in parallel with the endpoint task ([P] tasks share no files)

### Critical wiring note (C1)

The no-regression eval gate (T017, reconfirmed at T034) depends on **three**
pieces landing together: the eval baseline user's closet seeded in Postgres
(T009), `load_wardrobe()` reading Postgres (T014), and `eval/harness.py`
passing that user_id (T014). Miss any one and the gate reads an empty closet
and reports a false regression — or worse, passes vacuously.

## Parallel Example: User Story 1

```bash
Task: "list_wardrobe_items(user_id) in backend/src/whattowear/crud.py"
Task: "Unit tests for list_wardrobe_items in backend/tests/unit/test_crud.py"
```
(Endpoint task T013 and the retrieval-swap task T014 depend on T012 completing first.)

## Implementation Strategy

### MVP First (User Stories 1 + 2 — both P1)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (blocks everything)
3. Complete Phase 3: User Story 1 (view) — including the eval-harness rewiring
4. Complete Phase 4: User Story 2 (add from catalog)
5. **STOP and VALIDATE**: a closet that can be viewed and populated is the
   MVP — a view-only closet with no way to add items is a dead end (spec
   US2 rationale)
6. Run the no-regression eval gate (T017) before going further

### Incremental Delivery

1. Setup + Foundational → foundation ready
2. US1 + US2 → MVP: closet exists, can be viewed and populated
3. US3 → closet stays accurate (corrections)
4. US4 → closet stays accurate over time (removal)
5. Polish → confirm no regression, update docs

---

## Notes

- [P] tasks touch different files and have no incomplete dependencies
- Every CRUD function scopes its query by `user_id` — there is no cross-user
  access path to test around, only to confirm is absent
- The no-regression eval gate (T017, reconfirmed at T034) is not optional:
  constitution Principle I and spec FR-012/SC-005 both require it before this
  feature can be considered done
