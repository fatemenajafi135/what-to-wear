# Tasks: Photo to items

**Input**: Design documents from `/specs/018-photo-to-items/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md — all present.

**Tests**: included. The constitution's Quality Bar requires a unit test for deterministic logic and
a golden-set entry for any LLM-dependent path; this feature rewrites the one existing LLM-vision path
and adds a second (isolation), so tests are not optional here.

**Organization**: grouped by user story (spec.md priorities). Isolation (US4, P2, issue #48) is
deliberately its **own** phase rather than folded into Foundational — detection+extraction (US1/US2,
P1) is fully shippable and independently demoable with every card falling back to a region-cropped
original (FR-013's already-valid degraded state), so isolation is added as a later, separable
increment rather than a blocking prerequisite for the MVP.

## Path Conventions

Backend: `backend/src/whattowear/`, tests in `backend/tests/{unit,integration}`, evals in
`backend/evals/`. Frontend: `frontend/app/(app)/add/`, `frontend/app/(app)/closet/`. Infra:
`infra/supabase/migrations/`.

---

## Phase 1: Setup

- [ ] T001 Confirm `backend/.env` has `AI_GATEWAY_API_KEY` set (copy `backend/.env.example` if
      missing) — required from Phase 2 onward for any live verification.
- [ ] T002 Confirm `npx supabase start` is running locally, for T004's migration.
- [ ] T003 [P] Identify the source of 10+ real closet photos for the expanded fixture corpus
      (T027) — a real closet, phone camera roll, or equivalent; confirm they can be committed
      under the tracked `evals/fixtures/` carve-out (Constitution Principle X) before Phase 5.
      **10, not 8** (corrected in `/speckit-analyze`, finding F2): spec.md's Assumptions require
      "at least ten **real** closet photos" — the corpus doesn't reach that bar by keeping the 2
      existing synthetic placeholders and adding 8; those 2 are retired in T027, not counted.

---

## Phase 2: Foundational — detection & extraction (blocking prerequisites for US1/US2)

**Purpose**: the multi-garment detect+extract call, its response shape, and the route that
serves it. No user story is independently testable until this phase is done. Isolation is
deliberately **not** part of this phase (see Organization above) — every field this phase adds
for it (`isolated_photo_path`/`_url`) exists but stays `null` until Phase 6.

- [ ] T004 [P] Write `infra/supabase/migrations/0013_isolated_photo.sql` (data-model.md §1) —
      `wardrobe_items.isolated_photo_path text`, nullable, no default. Apply via
      `npx supabase db reset`; confirm the column exists and no existing row is affected.
- [ ] T005 [P] Add `wtw_max_detections_per_photo: int = 8` to `Settings` in
      `backend/src/whattowear/core/config.py` (data-model.md §3; isolation-specific settings are
      added later, in T041).
- [ ] T006 Extend `backend/src/whattowear/schema.py` (data-model.md §2): add `BoundingBox`; add
      `DetectedGarment` (`region: BoundingBox`, `attributes: ExtractedAttributes`); extend
      `PhotoExtractionResponse` with `region: BoundingBox` and `isolated_photo_path: str | None
      = None`; add `PhotoExtractionListResponse` (`drafts: list[PhotoExtractionView]`,
      `truncated: bool`); add `isolated_photo_path: str | None = None` to both `WardrobeItem` and
      `CreateWardrobeItemFromUploadRequest`. (`ExtractedAttributes` itself is unchanged — FR-005.)
- [ ] T007 Rewrite `backend/src/whattowear/vision.py`: replace `extract_attributes_from_image`
      with `detect_garments_from_image(image_bytes, mime_type) -> tuple[list[DetectedGarment],
      bool]` (the `bool` is `truncated`). Extend `_EXTRACTION_SCHEMA` into a `detections` array
      schema, each entry gaining `region` (research.md §1); enforce
      `wtw_max_detections_per_photo` in Python (truncate to first N, set `truncated`), never in
      the JSON schema itself (research.md §3). An empty `detections` array is a valid, successful
      return (`[], False`) — the caller (T009), not this function, decides what an empty result
      or a raised exception means for the response shape (research.md §2).
- [ ] T008 Rewrite `backend/src/whattowear/prompts/vision_system.md`: `version: 2` → `version: 3`.
      Instruct the model to enumerate **every** distinguishable garment in the photo (not only
      the most prominent one), order detections by confidence/prominence, and emit a `region`
      per detection. Keep every existing attribute instruction unchanged (FR-005) while
      tightening the three failure modes issue #46 names: prefer specific category over bare
      group (already in v2 — keep, reinforce per-detection), avoid vague/generic naming, and
      explicitly check each region individually for fabric/pattern/fit rather than describing the
      photo once. Wording here is a first pass — T034 iterates it against real harness results.
- [ ] T009 Rewrite `POST /closet/items/extract` in
      `backend/src/whattowear/api/v1/routes/closet.py`: call `vision.detect_garments_from_image`
      after the existing upload step (unchanged). On a raised exception: one draft,
      `extraction_ok=False`, all-null attributes, `region={0,0,1,1}` (today's exact fallback,
      contracts/closet-items-extract.md). On an empty, successful result: one draft,
      `extraction_ok=True`, all-null attributes, `region={0,0,1,1}` (today's "nothing found"
      semantics). On 1–8 detections: one draft per detection, each `extraction_ok=True`,
      `isolated_photo_path`/`isolated_photo_url` both `null` (Phase 6 populates them). Returns
      `PhotoExtractionListResponse`.
- [ ] T010 Update `POST /closet/items/from-upload` (`closet.py`) and
      `create_wardrobe_item_from_upload` (`backend/src/whattowear/repositories/supabase_closet.
      py`): accept and persist `isolated_photo_path` (contracts/closet-items-from-upload.md); add
      the same `{user_id}/` ownership-prefix `422` check `photo_path` already gets. Extend
      `ClosetItemView` and every read path that signs `photo_url` (`GET /closet/items`,
      `GET /closet/items/{item_id}`, this route's own `201` response) to also sign
      `isolated_photo_url` from `isolated_photo_path` when present, batched alongside the
      existing `photo_paths` batch-sign call.
- [ ] T011 [P] Regenerate `frontend/lib/api/schema.d.ts` (`npm run generate:api-types`, backend
      running) once T006/T009/T010's shapes are stable.
- [ ] T012 [P] `backend/tests/unit/test_vision.py`: mocked `get_chat_model`. Cases: N detections
      parsed with their own `region`+attributes; >8 raw detections → 8 kept, `truncated=True`;
      exactly 8 → `truncated=False`; empty list is returned as `([], False)`, not raised.
- [ ] T013 [P] `backend/tests/integration/test_closet_routes.py`: extract route — N-detection
      mocked response → `drafts` list of length N, each field traceable to its own detection;
      `truncated` passed through; every draft's `isolated_photo_path`/`_url` is `null` (not
      absent) at this phase.

**Checkpoint**: detection + extraction fully implemented and unit/integration-tested. Frontend
untouched — Phase 3 begins the user-observable slice.

---

## Phase 3: User Story 1 — One photo, several garments (Priority: P1) 🎯 MVP

**Goal**: a photo with several garments produces one review card per garment.

**Independent Test**: quickstart.md Scenario 1.

- [ ] T014 [US1] Restructure `frontend/app/(app)/add/BulkQueue.tsx`'s `QueueEntry` to one-per-
      draft (research.md §10): `scanEntry` expands `data.drafts` into N entries sharing the same
      `photoUrl`(blob)/`file`, each carrying its own `region`/`isolatedPhotoUrl`/`isolatedPhotoPath`/
      `extracted`/`extraction_ok`/`photoPath`/`status`. `isolatedPhotoPath` (the raw Storage path,
      distinct from the signed `isolatedPhotoUrl` used only for display) is what T017a's save call
      needs — do not drop it while flattening. **Preserve the existing upload-error branch as a
      one-entry special case**: an upload failure (`!photoPath`) has no `drafts` array to flatten at
      all, and must still produce exactly one `"upload-error"` entry for that file, unchanged from
      today (FR-026) — this is evaluated before `data.drafts` is ever read.
- [ ] T015 [US1] Same flattening in `frontend/app/(app)/add/AddItemFlow.tsx`'s `FlowState`
      (`drafts: Draft[]` + `currentIndex`, replacing the single-draft fields, each draft carrying
      `isolatedPhotoPath` alongside `isolatedPhotoUrl` per T014) — a photo yielding >1 detection
      reviews the same way a small bulk batch does (FR-025). The existing `"error"` state (genuine
      upload/scan failure, distinct from `"empty"`) is unchanged (FR-026).
- [ ] T016 [US1] `frontend/app/(app)/add/OrientationAwarePhoto.tsx`: add an optional `region`
      prop — when present and no `isolatedSrc` is given, renders the full blob scaled/positioned
      to the region's fraction inside the existing letterbox frame (research.md §4). No change to
      the natural/portrait letterbox decision itself.
- [ ] T017 [US1] `frontend/app/(app)/add/ReviewCard.tsx`: accept and pass through
      `isolatedPhotoUrl`/`region` to `OrientationAwarePhoto` — isolated image when present
      (always null until Phase 6, so this path is a no-op until then), else the region crop.
- [ ] T017a [US1] Thread `isolatedPhotoPath` through to the actual save request — found missing in
      `/speckit-analyze` (finding C1): `frontend/app/(app)/add/fromUploadBody.ts`'s
      `buildFromUploadBody()` gains an `isolatedPhotoPath: string | null | undefined` parameter,
      sent as `isolated_photo_path` (mirrors how `photoBackgroundColor` is already threaded);
      `BulkQueue.tsx`'s and `AddItemFlow.tsx`'s `handleSave` call sites both pass the current
      draft's `isolatedPhotoPath` (T014/T015) through to it. Without this, T004/T006/T010's backend
      support for `isolated_photo_path` is never exercised by a real save — the column stays `null`
      forever regardless of how well isolation itself works.
- [ ] T018 [US1] Add the "some garments in this photo weren't captured" notice to `BulkQueue.tsx`/
      `AddItemFlow.tsx`, shown when a photo's `truncated: true` (FR-002), using
      `frontend/lib/add-item-copy.ts`'s existing copy-module convention.
- [ ] T019 [US1] Confirm `BulkQueuePosition`'s "Reviewing item X of Y" already counts flattened
      drafts post-T014/T015 (no separate change expected — this task is verification + a
      regression test, not new code).
- [ ] T020 [P] [US1] `frontend/app/(app)/add/BulkQueue.test.tsx`: a batch of photos with mixed
      detection counts produces the right total card count and "X of Y" sequence (quickstart.md
      Scenario 6).
- [ ] T021 [P] [US1] `frontend/app/(app)/add/AddItemFlow.test.tsx`: one photo yielding 3
      detections reviews as 3 sequential cards, each save advancing correctly, `truncated` notice
      shown when applicable.
- [ ] T022 [P] [US1] `frontend/app/(app)/add/OrientationAwarePhoto.test.tsx`: region-cropped
      rendering across landscape/portrait × region-subset combinations.
- [ ] T023 [US1] Manual/live verification: quickstart.md Scenario 1 (flat-lay upload, and the
      >8-garments overflow case).

**Checkpoint**: multi-garment photos produce multiple, individually-saveable review cards
end-to-end. This is a demoable MVP slice on its own.

---

## Phase 4: User Story 2 — A single-garment photo still feels exactly like today (Priority: P1)

**Goal**: zero observable regression for the existing single-item flow.

**Independent Test**: quickstart.md Scenario 2.

- [ ] T024 [US2] `backend/tests/integration/test_closet_routes.py`: the literal regression-proof
      test — a single confident detection's draft has field-for-field identical values to what
      the pre-018 single-object response would have returned (diff against a fixed expected
      dict), plus the two fallback cases (T009's exception/empty-list paths) each produce exactly
      one draft, never zero.
- [ ] T025 [US2] `frontend/app/(app)/add/AddItemFlow.test.tsx`: a one-detection response renders
      exactly one `ReviewCard` and shows no "X of Y" position indicator, matching today's
      single-item silence (extends T021's file).
- [ ] T026 [US2] Manual/live verification: quickstart.md Scenario 2 — single hanger photo (compare
      wait time and fields against pre-018 behavior), then a forced detection-call failure.

**Checkpoint**: US1 + US2 together are the feature's MVP — multi-garment detection works, and
existing single-item users see no regression.

---

## Phase 5: User Story 3 — Each card describes its garment accurately (Priority: P2, issue #46)

**Goal**: demonstrate, not assert, that the v3 prompt measurably improves on wrong category,
missed attributes, and vague naming.

**Independent Test**: quickstart.md Scenario 4.

- [ ] T027 [US3] Retire `evals/fixtures/vision_samples/navy_top_placeholder.png` and
      `beige_trousers_placeholder.png` (synthetic, not real — don't count toward spec.md's "at
      least ten real closet photos"); add the 10+ real photos identified in T003 to
      `backend/evals/fixtures/vision_samples/`, covering: ≥1 single garment on a hanger, ≥2
      flat-lay/multi-garment photos, ≥1 garment worn by a person, ≥1 partially occluded garment
      (spec.md Assumptions' minimum corpus — 10+ fixtures, all real).
- [ ] T028 [US3] Extend `backend/evals/golden_set.yaml`'s `vision_cases:` — remove `v01`/`v02`
      (the retired placeholders' cases); one new case per real fixture; multi-garment fixtures
      gain `expected_count`; each case's comment names which named failure mode (#46) it targets.
- [ ] T029 [US3] Extend `backend/src/whattowear/eval/vision_harness.py`'s `_check()`: call
      `detect_garments_from_image`; when `expected_count` is present, compare it to the returned
      detection count; apply the existing per-field loose checks per detection (matched to the
      closest `expected` sub-case by category group) instead of to one whole-photo result. Stays
      structurally separate from `eval/harness.py` (unchanged import boundary, Principle I).
- [ ] T030 [P] [US3] `backend/tests/unit/eval/test_vision_harness.py` (new or extended):
      fixture-shape assertions only (cases load, ids unique, `expected_count` present where
      declared) — no live call, mirrors `test_golden_set.py`'s existing pattern.
- [ ] T031 [US3] Run `uv run python -m whattowear.eval.vision_harness` against v2 (temporarily
      restore the prior prompt file), record the pass count and failures.
- [ ] T032 [US3] Restore v3 (T008), re-run the same command, record the pass count and failures.
- [ ] T033 [US3] Record both runs — prompt version, model, pass counts, and the specific
      before/after cases for wrong-category/missed-attribute/vague-naming — in a new
      `docs/design-decisions.md` §61 entry (FR-009, Constitution Principle X's carve-out).
- [ ] T034 [US3] Based on T033's remaining failures (if any), iterate `prompts/vision_system.md`
      wording (still v3, content-only) targeting them specifically; re-run T031/T032's comparison
      until the harness shows measurable improvement, or record the remaining gap as a known
      limitation in the same §61 entry rather than silently dropping it.

**Checkpoint**: SC-003 is satisfied with recorded evidence, not a claim.

---

## Phase 6: User Story 4 — Each item's photo shows just the garment (Priority: P2, issue #48)

**Goal**: wire real isolation into the extract flow; measure and lock in the default strategy.

**Independent Test**: quickstart.md Scenario 3 + Scenario 5.

- [ ] T035 [P] Add `IsolationClient` Protocol to `backend/src/whattowear/ports.py` (data-model.md
      §4) and `IsolationOutcome` to `schema.py` (`image_bytes`/`mime_type`/`mask_area_fraction`/
      `cost_usd` all `Optional`, `latency_seconds` always set).
- [ ] T036 [P] Add isolation settings to `core/config.py` (data-model.md §3):
      `wtw_isolation_strategy`, `wtw_isolation_timeout_seconds`, `wtw_isolation_hybrid_min_area`,
      `wtw_isolation_hybrid_max_area`, `wtw_segmentation_api_url`, `wtw_segmentation_api_key`,
      `wtw_generative_isolation_model` (+ a `generative_isolation_model` property mirroring
      `vision_model`'s existing fallback-to-chat-model pattern). All optional-until-used, same
      posture as `cohere_api_key`/`tavily_api_key`.
- [ ] T037 [P] Write `backend/src/whattowear/adapters/isolation_segmentation.py`: plain
      `requests`-based hosted call (no SDK, mirrors `adapters/storage.py`'s idiom), bounded by
      `wtw_isolation_timeout_seconds`. **Never raises** on a call/timeout failure — returns
      `IsolationOutcome(image_bytes=None, ...)` instead (mirrors `storage.py::create_signed_url`'s
      fail-soft pattern), so every call site handles success/failure uniformly without try/except
      boilerplate.
- [ ] T038 [P] Add `get_image_model()` to `backend/src/whattowear/adapters/llm_gateway.py`
      (mirrors `get_chat_model()`) and write
      `backend/src/whattowear/adapters/isolation_generative.py` using it — same fail-soft
      contract as T037.
- [ ] T039 Write `backend/src/whattowear/adapters/isolation_hybrid.py`: calls the segmentation
      adapter (T037) first; escalates to the generative adapter (T038) when
      `mask_area_fraction < wtw_isolation_hybrid_min_area`, `> wtw_isolation_hybrid_max_area`, or
      the segmentation call itself failed (research.md §6). Depends on T037/T038.
- [ ] T040 Write `backend/src/whattowear/adapters/isolation.py` — `get_isolation_client()` factory
      selecting T037/T038/T039 by `wtw_isolation_strategy`, mirroring `kb.py`'s `wtw_kb_mode`
      selection pattern. Depends on T037–T039.
- [ ] T041 Wire isolation into the extract route (`closet.py`, extends T009): for each accepted
      detection, dispatch `get_isolation_client().isolate(...)` concurrently across detections
      (`concurrent.futures.ThreadPoolExecutor`, research.md §5 — the route stays a plain `def`,
      no `async def` conversion); on success, upload via `storage.upload_photo` with an
      `-isolated-` filename (research.md §7) and populate `isolated_photo_path`/sign
      `isolated_photo_url`; on failure/timeout, leave both `null` (FR-013 — the draft stays fully
      saveable via T009's existing region-crop fallback).
- [ ] T042 [P] `backend/tests/unit/test_isolation.py`: each adapter's success/failure/timeout path
      (mocked HTTP/gateway calls, never raises); hybrid escalation at both area boundaries and on
      segmentation failure; factory selects the right adapter per `wtw_isolation_strategy`.
- [ ] T043 `backend/tests/integration/test_closet_routes.py` (extends T013's file): isolation
      success populates both new fields; isolation failure leaves them `null` and the draft
      remains fully present; 8 mocked detections' isolation calls complete in roughly one call's
      wall-clock time, not eight (proves T041's concurrency).
- [ ] T044 Extend `eval/vision_harness.py` with an `isolation_report()` function (research.md §9):
      for each strategy, run every fixture-corpus image through `get_isolation_client(strategy)`,
      record latency/success/cost, print a per-strategy summary table. Add a
      `--isolation-report` CLI flag.
- [ ] T045 Run `uv run python -m whattowear.eval.vision_harness --isolation-report` against the
      real fixture corpus (T027) for all three strategies; record the table in
      `docs/design-decisions.md` §62; set `wtw_isolation_strategy`'s real default and
      `wtw_isolation_hybrid_min_area`/`_max_area`'s real values from the measured numbers (FR-016)
      — replacing T036's placeholder defaults. Two checks added in `/speckit-analyze` (findings
      E3/E4), both recorded in the same §62 entry: (a) **SC-008** — compute the full per-photo
      cost at the chosen default (one detection/extraction call's own cost + up to 8 isolation
      calls at that strategy), not isolation cost alone, and confirm it's ≤ $0.05, or record why
      not; (b) **SC-005** — confirm the chosen default's success rate on worn/flat-lay/occluded
      fixtures clears 50%, or record why not.
- [ ] T046 [US4] Frontend: `frontend/app/(app)/closet/ClosetGrid.tsx` and
      `.../closet/[itemId]/page.tsx`'s `ItemDetailCard` — pass
      `src={item.isolated_photo_url ?? item.photo_url}` and
      `backgroundColor={item.isolated_photo_url ? null : item.photo_background_color}` to
      `ItemPhoto` (research.md §8). Zero changes inside `components/ui/ItemPhoto/ItemPhoto.tsx`.
- [ ] T047 [P] [US4] Tests confirming the prop wiring from T046 (ClosetGrid/ItemDetailCard test
      files) — isolated image renders with the neutral-surface fallback, original renders with
      its own `backgroundColor` as before.
- [ ] T048 [US4] Manual/live verification: quickstart.md Scenario 3 (worn/multi-item photo → clean
      isolated card; forced `WTW_SEGMENTATION_API_URL` failure → graceful region-crop fallback,
      still saveable) and Scenario 5 (per-strategy report sanity check). Two checks added in
      `/speckit-analyze` (findings E2/E5): (a) **SC-007** — time a real (not mocked) upload of an
      8-detection photo end-to-end and confirm it lands within 30s, recording the actual figure;
      (b) **SC-004** — upload a plain-background/hanger photo (today's best case) and confirm the
      isolated image looks at least as clean as the app's existing (non-isolated) treatment of the
      same kind of photo.

**Checkpoint**: review cards and closet tiles show clean, isolated images by default, with the
strategy chosen from real measurements rather than assumption.

---

## Phase 7: User Story 5 — Original photos are never lost (Priority: P3)

**Goal**: the item detail page can flip back to the original photo; graceful behavior when no
isolated image exists.

**Independent Test**: quickstart.md Scenario 3 steps 5–6.

- [ ] T049 [US5] New `frontend/app/(app)/closet/[itemId]/ItemDetailToggle.tsx` — renders only when
      `item.isolated_photo_url` is present; flips which `src`/`backgroundColor` pair
      `ItemDetailCard` passes to `ItemPhoto`, defaulting to the isolated image (FR-020). Built
      from the existing segmented-control/tab primitive under `components/ui/` if one exists;
      otherwise a minimal two-option `Button`-state group, explicitly flagged in this task's
      commit as a Principle VIII gap (no design-system token for this control yet) rather than
      inventing a new visual language silently.
- [ ] T050 [US5] Wire the toggle into `.../closet/[itemId]/page.tsx`'s `ItemDetailCard`.
- [ ] T051 [P] [US5] `ItemDetailToggle.test.tsx`: absent when no isolated image; present and
      functional when one exists; defaults to isolated.
- [ ] T052 [US5] `backend/tests/integration/test_closet_routes.py`: both `GET /closet/items` and
      `GET /closet/items/{item_id}` return `isolated_photo_url: null` (present, not omitted) for
      every item saved before this feature — SC-006's "100% of saved items" claim, including the
      pre-existing ones.
- [ ] T053 [US5] Manual/live verification: save an item from a multi-garment photo; confirm its
      detail-page toggle's "original" state shows the literal, unmodified upload (the whole
      multi-garment photo it was detected from), not a cropped or regenerated variant.

**Checkpoint**: all five user stories independently demoable; spec.md is fully satisfied.

---

## Phase 8: Polish & cross-cutting

- [ ] T054 [P] `ruff check`, `ruff format --check`, `mypy src`, `lint-imports` — confirm
      `adapters/isolation_*.py` and `vision.py` still import neither `fastapi` nor
      `whattowear.api` (Technology Constraints' framework-free AI modules rule).
- [ ] T055 [P] `eslint`, `tsc --noEmit`, `next build` — all clean.
- [ ] T056 Run `uv run pytest` — full backend suite green, count not dropped from the pre-018
      baseline.
- [ ] T057 Run `npm test` (frontend) — full suite green.
- [ ] T058 Add a `docs/deferred-work.md` row for the real segmentation-provider account/API key
      still needing procurement before production use (research.md §5's "open item" — CI and
      local dev are unaffected, mocked/unconfigured throughout).
- [ ] T059 Manual browser pass at `localhost:3000` and `127.0.0.1:3000`, light and dark theme, all
      six quickstart.md scenarios.
- [ ] T060 Confirm `docs/design-decisions.md` §61 (T033) and §62 (T045) are both complete and
      cross-referenced from spec.md's Assumptions section.

---

## Dependencies

- **Phase 1 (Setup)** has no dependencies.
- **Phase 2 (Foundational)** blocks every user-story phase — the detect+extract call and its
  response shape are shared by all of them.
- **US1 (Phase 3)** and **US2 (Phase 4)** are both P1 and share almost all their groundwork
  (Phase 2); Phase 4's tests can start as soon as Phase 2 lands, in parallel with Phase 3's
  frontend work.
- **US3 (Phase 5)** depends only on Phase 2 (the v3 prompt and `detect_garments_from_image`
  already exist there) — independent of US1/US2's frontend work.
- **US4 (Phase 6)** depends only on Phase 2 — independent of US1/US2/US3, though T046's frontend
  wiring reads the same `ClosetItemView` shape T010 already extended.
- **US5 (Phase 7)** depends on US4 (Phase 6) — there is nothing to toggle to until an isolated
  image can exist.
- **Phase 8 (Polish)** last, after every story phase intended for this slice.

## Parallel example (after Phase 2)

```
T014 [US1] BulkQueue.tsx flattening        T024 [US2] regression-proof integration test
T020 [P][US1] BulkQueue.test.tsx           T027 [US3] source real fixture photos
T035 [P] ports.py IsolationClient          T036 [P] core/config.py isolation settings
T037 [P] isolation_segmentation.py         T038 [P] isolation_generative.py
```

## Implementation strategy

**MVP = Phase 2 + Phase 3 + Phase 4** (both P1 stories) — multi-garment detection and extraction,
fully demoable, zero regression for single-item photos, every card saveable even though no card
yet shows an isolated image (region-cropped original instead, an already-valid FR-013 state).

**Incremental after MVP**: Phase 5 (US3, accuracy proof) and Phase 6 (US4, isolation) can proceed
in either order or in parallel — neither depends on the other. Phase 7 (US5, the original-photo
toggle) is the natural last story, since it has nothing to show until Phase 6 exists. Phase 8
closes out the branch.
