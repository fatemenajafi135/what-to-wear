---
description: "Task list for Feature 003 (mvp-app)"
---

# Tasks: MVP App

**Input**: Design documents from `/specs/003-mvp-app/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included for backend (matches plan.md's Testing section and this
repo's existing pytest convention). No dedicated frontend test suite — `tsc
--noEmit`/`next build` plus manual `quickstart.md` validation is the frontend
gate (simplicity — matches this feature's minimal-first framing).

**Organization**: Tasks are grouped by user story (US1–US4 from spec.md, all
P1). Feature 003 is developed **vertically** (backend + frontend together per
capability slice), per SDD-HANDOFF Step 4 — so most story phases mix backend
and frontend tasks in build order, not backend-then-frontend.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1 (sign in), US2 (add by photo), US3 (view closet), US4 (get suggestion)

---

## Phase 1: Setup

**Purpose**: Project initialization — first code ever written to `frontend/`.

- [ ] T001 Scaffold Next.js 15 (App Router, TypeScript) app in `frontend/` (`package.json`, `tsconfig.json`, `next.config.ts`, `app/` root)
- [ ] T002 [P] Configure frontend lint/format (ESLint + Prettier configs) in `frontend/`
- [ ] T003 [P] Install frontend runtime deps (`@supabase/supabase-js`) and dev dep (`openapi-typescript`) in `frontend/package.json`
- [ ] T004 [P] Add `frontend/lib/api-types.ts` generation in `frontend/package.json`: a `fetch:openapi` script (`curl $API_BASE_URL/openapi.json -o openapi.json`, checked-in snapshot) plus a `gen:types` script (`openapi-typescript ./openapi.json -o lib/api-types.ts`) — `gen:types` depends on `fetch:openapi` having been run at least once

**Checkpoint**: `npm run dev` in `frontend/` serves an empty Next.js shell.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared infrastructure every user story needs — auth plumbing (all
four stories require a signed-in session), the CORS bridge (no story works
cross-origin without it), and the additive schema change (US2 writes
`pattern`/`fit`, US3 displays them).

**⚠️ CRITICAL**: No user story work starts until this phase is complete.

- [X T005 Add `CORSMiddleware` to `backend/src/whattowear/api.py`, origins from new `WTW_CORS_ORIGINS` env var (comma-separated, default `*`); document in `backend/.env.example`
- [X T006 [P] Create Alembic migration `backend/alembic/versions/0002_add_pattern_fit.py` — additive nullable `pattern`, `fit` columns on `wardrobe_items` only (mirrors `0001`'s `fabric`/`source` precedent)
- [X T007 [P] Add `pattern: Optional[str]`, `fit: Optional[str]` to `WardrobeItem` and `WardrobeItemPatch` in `backend/src/whattowear/schema.py`
- [X T008 Add `pattern`, `fit` nullable `String` columns to `WardrobeItemRow` in `backend/src/whattowear/models.py` (depends on T006)
- [X T009 Update `crud._to_wardrobe_item()` to map `pattern`/`fit` in `backend/src/whattowear/crud.py` (depends on T007, T008)
- [ ] T010 Manual one-time Supabase setup: create Storage bucket `wardrobe-photos` with a per-`{user_id}`-folder RLS policy (see `quickstart.md` Prerequisites) — no repo file, tracked here so it isn't skipped
- [ ] T011 [P] Create `frontend/lib/supabase-client.ts` — Supabase Auth JS client (env: `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`)
- [ ] T012 Create `frontend/lib/api-client.ts` — thin `apiFetch<T>()` wrapper attaching the Supabase session's JWT as `Authorization: Bearer`, typed via `lib/api-types.ts`; on a `401` response, redirect to `/sign-in` **without discarding caller-held in-progress state** (the caller — e.g. T029's draft form — is responsible for holding its own unsaved data until resubmit, this wrapper only redirects) (depends on T004, T011)
- [ ] T013 Create app shell + auth guard in `frontend/app/layout.tsx` — redirects to `/sign-in` when no Supabase session exists (depends on T011)

**Checkpoint**: Backend runs with CORS + migrated schema; frontend has a
typed API client and an auth-gated shell. User story work can begin.

---

## Phase 3: User Story 1 - Sign in to a private account (Priority: P1) 🎯 MVP

**Goal**: A person can create an account, sign in, stay signed in across
reloads, and is blocked from every other screen while signed out.

**Independent Test**: Create an account, reach a signed-in screen; reload the
browser and remain signed in; sign out/in again and land on the same account;
confirm closet/add/suggest routes redirect to sign-in while signed out.

No backend tasks — `/wardrobe/*` and `/recommend` are already JWT-gated
(Feature 001/002 Phase 1, unchanged); this story is 100% frontend, wiring the
already-verified Supabase JWT the auth guard (T013) expects.

### Implementation for User Story 1

- [ ] T014 [P] [US1] Build sign-up page (`supabase.auth.signUp`) in `frontend/app/(auth)/sign-up/page.tsx`
- [ ] T015 [P] [US1] Build sign-in page (`supabase.auth.signInWithPassword`) in `frontend/app/(auth)/sign-in/page.tsx`
- [ ] T016 [US1] Add sign-out control + signed-in identity display to the app shell in `frontend/app/layout.tsx` (depends on T013)

**Checkpoint**: US1 is fully functional and testable independently — sign up,
reload-persists, sign out/in, anonymous redirect all work.

---

## Phase 4: User Story 2 - Add an item to my closet from a photo (Priority: P1)

**Goal**: A signed-in user submits a photo, gets pre-filled attributes back
as an editable draft, corrects any field, and saves — the corrected values
persist, not the raw extraction. A bad photo never blocks manual entry.

**Independent Test**: From an empty closet, submit one photo, confirm a
pre-filled draft with all 8 attributes, change one, save, confirm the closet
shows the corrected value. Submit a blurry/no-garment photo, confirm a clear
"couldn't process" state that still allows manual fill-in and save.

### Tests for User Story 2

- [X T017 [US2] Unit tests for extraction payload building + `ExtractedAttributes` validation (LLM call mocked) in `backend/tests/unit/test_vision.py` — written against `vision.py`'s intended interface; expected to fail (or be written alongside) until T020 lands, not a true parallel/independent task
- [X T018 [US2] Integration tests for `POST /wardrobe/items/extract` and `POST /wardrobe/items/upload` (incl. `extraction_ok: false` path, a 422 when `fabric`/`pattern`/`fit` is blank on upload, and a cross-user isolation assertion — a second user's token must never see or overwrite the first user's uploaded item, matching the precedent in `tests/integration/test_recommend_auth.py`) in `backend/tests/integration/test_wardrobe_photo_flow.py` (depends on T023, T024)

### Backend Implementation for User Story 2

- [X T019 [P] [US2] Add `ExtractedAttributes` model to `backend/src/whattowear/schema.py`
- [X T020 [P] [US2] Create `backend/src/whattowear/vision.py` — `extract_attributes_from_image()` using `config.get_chat_model().with_structured_output(ExtractedAttributes)` with a multimodal (base64 image) human message (depends on T019)
- [X T021 [P] [US2] Create `backend/src/whattowear/storage.py` — `upload_wardrobe_photo(user_id, file_bytes, filename, access_token)` uploading to the `wardrobe-photos` bucket under `{user_id}/{uuid4}-{filename}` using the caller's own bearer token (depends on T010)
- [X T022 [US2] Add `PhotoExtractionResponse`, `CreateWardrobeItemFromUploadRequest` models to `backend/src/whattowear/schema.py` — `fabric`/`pattern`/`fit` are **required** (non-optional `str`) on `CreateWardrobeItemFromUploadRequest` specifically, so a 422 rejects a blank submission (SC-003); `WardrobeItem`/`WardrobeItemPatch` keep all three optional, unchanged (depends on T019, T007)
- [X T023 [US2] Add `POST /wardrobe/items/extract` endpoint to `backend/src/whattowear/api.py` per `contracts/wardrobe-items-extract.md` (depends on T020, T021, T022)
- [X T024 [US2] Add `crud.create_wardrobe_item_from_upload()` in `backend/src/whattowear/crud.py`, then `POST /wardrobe/items/upload` endpoint in `backend/src/whattowear/api.py` per `contracts/wardrobe-items-upload.md` (depends on T009, T022)
- [X T025 [P] [US2] Add `vision_cases:` section to `backend/data/golden_set.yaml` + sample photos in `backend/data/fixtures/vision_samples/`
- [X T026 [US2] Create `backend/src/whattowear/eval/vision_harness.py` — checks extraction output against `vision_cases:` (depends on T020, T025)

### Frontend Implementation for User Story 2

- [ ] T027 [US2] Build add-item page (camera capture / gallery file picker → `POST /wardrobe/items/extract`) in `frontend/app/closet/add/page.tsx` (depends on T012, T023)
- [ ] T028 [US2] Build editable extracted-attributes form (all 8 fields, category/formality/season as pickers matching the full frozen taxonomy, pattern/fit/fabric as free text) in `frontend/components/ExtractedItemForm.tsx` — disable the save action client-side until `fabric`/`pattern`/`fit` are all non-blank (SC-003; the backend 422 in T022/T024 is the enforced fallback, this is the UX-level guard)
- [ ] T029 [US2] Wire save action (`POST /wardrobe/items/upload`) and the `extraction_ok: false` fallback (manual-entry state, no crash) in `frontend/app/closet/add/page.tsx`; hold the draft in component state so a `401` mid-flow (session expiry, see T012) redirects to sign-in without discarding what the user already entered (depends on T024, T027, T028)

**Checkpoint**: US1 + US2 both work independently — a signed-in user can add
a real item by photo, corrected values save.

---

## Phase 5: User Story 3 - View my closet (Priority: P1)

**Goal**: A signed-in user sees every item they own, with an empty state
(not an error) when the closet is empty, and never another user's items.

**Independent Test**: With a closet containing photo-added and catalog items,
open the closet view and confirm every item and its attributes appear; with
an empty closet, confirm an empty state.

No backend tasks — `GET /wardrobe/items` already exists and is already
user-scoped (Feature 001).

### Implementation for User Story 3

- [ ] T030 [US3] Build closet grid/list view calling `GET /wardrobe/items` in `frontend/app/closet/page.tsx` (depends on T012)
- [ ] T031 [P] [US3] Build item display component (category, colors, formality, warmth, season, fabric, pattern, fit) in `frontend/components/ClosetItemCard.tsx`
- [ ] T032 [US3] Add empty-state UI (zero items, not an error) in `frontend/app/closet/page.tsx` (depends on T030)

**Checkpoint**: US1 + US2 + US3 all independently functional.

---

## Phase 6: User Story 4 - Get an outfit suggestion (Priority: P1)

**Goal**: A signed-in user types a free-text request and gets an outfit
assembled only from their own closet, with a written rationale — or, if the
closet can't dress the occasion, a clear explanation instead of an error.

**Independent Test**: With a well-stocked closet, submit a plain-English
request and confirm an outfit + rationale built only from owned items. With
a too-sparse closet, confirm a clear "not enough" explanation.

No backend tasks — `POST /recommend` already exists, is already JWT-gated
(Feature 002 Phase 1), and is used exactly as-is.

### Implementation for User Story 4

- [ ] T033 [US4] Build suggestion request page (free-text field → `POST /recommend`) in `frontend/app/suggest/page.tsx` (depends on T012)
- [ ] T034 [P] [US4] Build outfit + rationale result display in `frontend/components/SuggestionResult.tsx`
- [ ] T035 [US4] Handle the "closet can't fulfill this request" explanation state (no error, no fabricated outfit) in `frontend/app/suggest/page.tsx` (depends on T033)

**Checkpoint**: All four P1 user stories independently functional — this is
the full MVP.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Responsive layout (SC-004) and public deployment (SC-005/FR-012),
which no single story owns.

- [ ] T036 [P] Responsive styling pass (phone-width and laptop-width viewports) across `frontend/app/**` and `frontend/components/**`, adapting design tokens from `design/_ds/nocturne-6d6fcdf7-6dc8-4d75-b4ec-a4605bf9306c/styles.css` (not a pixel-perfect port — full 6-value formality/6 category groups, no occasion-picker buttons)
- [ ] T037 [P] Configure Railway deploy for backend: start command `uv run uvicorn whattowear.api:app --host 0.0.0.0 --port $PORT`; set env vars (incl. `WTW_CORS_ORIGINS`) in the Railway dashboard
- [ ] T038 [P] Configure Vercel deploy for frontend: set env vars (`NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `NEXT_PUBLIC_API_BASE_URL`) in the Vercel dashboard
- [ ] T039 Run full `quickstart.md` validation locally, then again against the deployed Railway/Vercel URLs from a browser that never touched local dev (depends on T036, T037, T038)

**Checkpoint**: App is publicly reachable and passes every quickstart.md
validation at both viewport sizes.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies
- **Foundational (Phase 2)**: depends on Setup — BLOCKS all user stories
- **US1 (Phase 3)**: depends on Foundational only — the true MVP floor (nothing else is reachable without it)
- **US2 (Phase 4)**: depends on Foundational; independently testable once US1's auth guard exists to reach the screen, but its own logic has no US1 dependency
- **US3 (Phase 5)**: depends on Foundational; same relationship to US1 as US2
- **US4 (Phase 6)**: depends on Foundational; same relationship to US1 as US2
- **Polish (Phase 7)**: depends on US1–US4 all being complete

### Recommended build order (vertical slice, per SDD-HANDOFF Step 4)

Sequential: Setup → Foundational → US1 → US2 → US3 → US4 → Polish. Each story
is demoable on completion; US1 first since every other screen sits behind its
auth guard in practice, even though US2–US4's own code has no hard dependency
on US1 beyond that guard.

### Parallel Opportunities

- T002, T003 (Setup) in parallel
- T006, T007, T011 (Foundational) in parallel; T008 after T006, T009 after T007+T008
- T014, T015 (US1) in parallel
- T019, T021, T025 (US2) in parallel; T017 written alongside/just after T020 starts (not truly independent — see T017's note); T022 after T019+T007; T023 after T020+T021+T022; T024 after T009+T022
- T031 (US3) in parallel with T030
- T034 (US4) in parallel with T033
- T036, T037, T038 (Polish) in parallel

---

## Parallel Example: User Story 2 backend

```bash
Task: "Add ExtractedAttributes model to backend/src/whattowear/schema.py"
Task: "Create backend/src/whattowear/storage.py upload wrapper"
Task: "Add vision_cases: section to backend/data/golden_set.yaml"
# test_vision.py (T017) is written alongside vision.py (T020), not run
# fully in parallel with it — see T017's note.
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 (Setup) + Phase 2 (Foundational)
2. Complete Phase 3 (US1 — sign in)
3. **STOP and VALIDATE**: a person can sign up, stay signed in, and every
   other route redirects them away while signed out
4. This alone isn't demoable as "the app" yet — it's the floor everything
   else stands on, not a usable increment by itself (unlike a typical
   feature's US1). Continue to US2 before calling anything demo-ready.

### Incremental Delivery

1. Setup + Foundational → foundation ready
2. US1 → auth works end-to-end
3. US2 → a user can build a real closet from their own photos (the feature's
   central promise — nothing to suggest an outfit from without it)
4. US3 → the confirmation loop that makes US2 trustworthy
5. US4 → the actual point of the app; demoable end-to-end for the first time
6. Polish → responsive pass + public deploy → milestone-ready

---

## Notes

- [P] tasks touch different files and have no incomplete dependencies
- This feature reuses `/recommend`, `GET /wardrobe/items`,
  `PATCH /wardrobe/items/{id}`, and the JWT dependency entirely unchanged —
  no task above should modify any of them
- The known, accepted trade-off that `/recommend`'s LLM still picks outfit
  items directly (Principle II debt) is unchanged by this feature — no task
  here touches it; it stays Feature 002 Phases 2–3's fix
- `pattern`/`fit` are free-text, matching `fabric`'s existing shape — no task
  above should introduce a closed enum for either
