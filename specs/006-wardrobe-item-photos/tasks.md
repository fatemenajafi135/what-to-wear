# Tasks: Wardrobe Item Photos

**Input**: Design documents from `/specs/006-wardrobe-item-photos/`
**Prerequisites**: plan.md, spec.md

**Tests**: One backend test requested explicitly (spec/plan: a deterministic
CRUD round-trip, no LLM calls). No frontend test framework exists in this
repo — frontend verification is typecheck/lint/build + the manual
quickstart.md steps, matching how Features 003/004 verified frontend work.

**Organization**: Single user story (US1) — this feature has no smaller
independently-valuable slice (see spec.md's "Why this priority").

## Phase 1: Setup

- [ ] T001 Confirm the dev environment already has the Feature 003/005
      `wardrobe-photos` Storage bucket + RLS policies (no new setup — this
      phase is a pre-flight check, not new infrastructure). If missing,
      stop and do `specs/003-mvp-app/quickstart.md`'s Prerequisites first;
      out of scope for this feature to (re)create.

## Phase 2: Foundational (blocking prerequisites)

- [ ] T002 Additive Alembic migration `backend/alembic/versions/0004_add_photo_path.py`
      adding a nullable `photo_path` (String) column to `wardrobe_items` —
      same pattern as `0002_add_pattern_fit.py`. Run `uv run alembic upgrade head`
      to apply it locally.
- [ ] T003 Add `photo_path: Mapped[str | None] = mapped_column(String, nullable=True)`
      to `WardrobeItemRow` in `backend/src/whattowear/models.py` (alongside
      the existing `pattern`/`fit` columns).
- [ ] T004 Add `photo_path: Optional[str] = None` to `WardrobeItem` in
      `backend/src/whattowear/schema.py` (do NOT add it to
      `WardrobeItemPatch` — out of scope per plan.md, it's set once at
      creation, never user-edited).

**Checkpoint**: Migration applies cleanly; `WardrobeItem`/`WardrobeItemRow`
have the field; nothing reads or writes it yet, so existing behavior is
unchanged (verify: `uv run pytest tests/ -q` still fully green).

## Phase 3: User Story 1 - See a real photo, or the swatch fallback (Priority: P1)

**Goal**: A photo-uploaded item's closet card shows its real photo; a
catalog item's card is unchanged; any photo-load failure falls back to
today's swatch-only rendering.

**Independent Test**: Add one item by photo and one from the catalog, view
`/closet` — the photo item shows its picture + color/pattern info, the
catalog item shows only its swatch, exactly as before this feature.

### Backend

- [ ] T005 [US1] In `backend/src/whattowear/crud.py`,
      `create_wardrobe_item_from_upload` sets `photo_path=req.photo_path`
      on the new `WardrobeItemRow` (currently received via
      `CreateWardrobeItemFromUploadRequest.photo_path` but discarded —
      just wire it through).
- [ ] T006 [US1] In `backend/src/whattowear/crud.py`, `_to_wardrobe_item`
      (the row → `WardrobeItem` mapper used by every read path, including
      `GET /wardrobe/items`) includes `photo_path=row.photo_path`.
- [ ] T007 [P] [US1] `backend/tests/integration/test_wardrobe_item_photo_path.py`:
      create an item via `create_wardrobe_item_from_upload` with a
      non-null `photo_path`, read it back via `list_wardrobe_items`,
      assert the field round-trips. Create a second item via
      `add_wardrobe_item_from_catalog`, assert its `photo_path` is `None`.
      No LLM calls — pure DB round-trip, uses the `db_session`
      rollback-isolation fixture like other CRUD tests (not the
      non-isolated pattern that caused a real bug during the 005 merge —
      see `docs/005-production-hardening-merge-report.md` if unsure why
      that distinction matters).

### Frontend

- [ ] T008 [US1] Regenerate `frontend/lib/api-types.ts`: start the backend
      locally (`uv run uvicorn whattowear.api:app --reload`), then from
      `frontend/`, `npm run fetch:openapi && npm run gen:types`. Confirm
      `photo_path` now appears on the generated `WardrobeItem` schema.
- [ ] T009 [US1] `frontend/components/ClosetItemCard.tsx`: when
      `item.photo_path` is present, call
      `supabase.storage.from("wardrobe-photos").createSignedUrl(item.photo_path, 3600)`
      (import the existing `supabase` client from `@/lib/supabase-client`)
      in a `useEffect`, and render an `<img>` above the existing
      `closet-item-swatches` div when the signed URL resolves. On any
      error (thrown, or an `error` field in the response) or while
      `photo_path` is absent, render exactly what the component renders
      today — no broken `<img>`, no thrown error. Color swatches, hex
      title, fabric/pattern/fit tags stay unconditional (plan.md's
      Frontend approach / spec.md FR-005).
- [ ] T010 [US1] `npm run typecheck && npm run lint && npm run build` in
      `frontend/` — must be clean (matches how every prior frontend
      change in this repo was verified; no new frontend test framework
      introduced for this one small component).

**Checkpoint**: quickstart.md's four validation steps all pass manually
against a locally running backend + frontend.

## Phase 4: Polish

- [ ] T011 [P] `uv run ruff check . && uv run ruff format .` in `backend/`
      — touched files only need to be clean (this repo has pre-existing,
      unrelated ruff findings in notebooks/`external/trends.py`; don't
      fix those as part of this feature).
- [ ] T012 Per the handoff contract (root `CLAUDE.md` "Session workflow"):
      update `docs/SDD-HANDOFF.md`'s Feature 006 entry and `CLAUDE.md`'s
      "Current state" section, mark this file's tasks `[X]`.

## Dependencies

- Phase 1 (T001) → Phase 2 (T002-T004) → Phase 3 (T005-T010) → Phase 4 (T011-T012).
- T002 → T003 (model needs the column to exist) → T004 (schema mirrors the model) — sequential, same file family, don't parallelize.
- T005/T006 depend on T003/T004 (the field must exist first).
- T007 depends on T005/T006 (tests the behavior they implement).
- T008 depends on T004 (nothing to regenerate until the schema has the field) — must also happen before T009 can compile against the new type.
- T009 depends on T008.
- T010 depends on T009.
- No other user stories exist to sequence against (single-story feature).

## Parallel execution opportunities

- T007 (backend test) can be written in parallel with T008-T009 (frontend) once T005/T006 land — different files, no shared state.
- Everything else is a short, mostly-sequential chain — this is a small feature; don't over-parallelize a few hours of work.

## Implementation strategy

MVP = the whole feature (single user story, P1, no smaller cut makes
sense). Suggested order for whoever implements: T001 → T002 → T003 → T004
→ (verify existing suite still green) → T005 → T006 → T007 → T008 → T009
→ T010 → T011 → T012.
