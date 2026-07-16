---

description: "Task list for Feature 004: preference-memory"
---

# Tasks: Preference Memory

**Input**: Design documents from `/specs/004-preference-memory/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/preferences.md, quickstart.md

**Tests**: Included — matches this project's established convention (Feature
001/002/003 all ship integration tests against the live DB plus unit tests
for deterministic logic; the constitution's Quality Bar requires unit tests
for deterministic logic, which `derive_signals()` is).

**Organization**: Grouped by user story (spec.md priorities) so each story is
independently implementable, testable, and deliverable.

## Path Conventions

Existing web app split: `backend/src/whattowear/`, `backend/tests/`,
`frontend/`. No new top-level directories (plan.md's Structure Decision).

---

## Phase 1: Setup

- [ ] T001 Confirm the Alembic revision chain's current head is `0002` (`cd backend && uv run alembic heads`) before authoring a new migration — this branch's worktree is developed in parallel with the `002-styling-agent` worktree (see root CLAUDE.md's "Working in parallel" note); verify no head has been added by the other branch getting merged into this one unexpectedly.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Persistence and contract shapes every user story depends on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T002 [P] Additive Alembic migration adding `suggestion_feedback` and `preference_signal_dismissal` tables (columns, check/unique constraints per data-model.md) in `backend/alembic/versions/0003_add_suggestion_feedback.py`
- [ ] T003 [P] Add `SuggestionFeedbackRow` and `PreferenceSignalDismissalRow` SQLAlchemy models (per data-model.md's exact column/constraint spec) in `backend/src/whattowear/models.py`
- [ ] T004 [P] Add `Verdict`, `SubmitFeedbackRequest`, `SuggestionFeedback`, `PreferenceSignal`, `PreferenceProfile` Pydantic models in `backend/src/whattowear/schema.py`
- [ ] T005 Apply the migration (`cd backend && uv run alembic upgrade head`) and confirm both tables exist (`\d suggestion_feedback`, `\d preference_signal_dismissal` via `psql`, or a quick SQLAlchemy `inspect()` check)

**Checkpoint**: Schema and contracts exist — user story implementation can begin.

---

## Phase 3: User Story 1 - React to a suggestion (Priority: P1) 🎯 MVP

**Goal**: A signed-in user can mark a received outfit suggestion as liked or
rejected, optionally with a reason, and that reaction is durably recorded
against the right user and the right outfit.

**Independent Test**: Get a suggestion from `/recommend`. React to it as
liked. Get a different suggestion, react as rejected with a reason and
separately without one. Confirm each reaction is recorded, attributed to the
correct suggestion (item set) and user, and that reacting twice to the same
item set replaces rather than accumulates (spec.md Edge Cases).

### Implementation for User Story 1

- [ ] T006 [US1] `record_feedback(session, user_id, item_ids, verdict, reason)` in `backend/src/whattowear/crud.py`: resolve `item_ids` against the caller's own `wardrobe_items` (raise a new `UnknownWardrobeItemIds` exception, mirroring `UnknownCatalogItemIds`, if any id is missing or belongs to another user); build `item_snapshot` from the resolved rows' current `category`/`colors`/`formality`; compute the sorted `item_ids_key`; upsert on `(user_id, item_ids_key)` (update `verdict`/`reason`/`item_snapshot`/`created_at` if a row exists, else insert)
- [ ] T007 [US1] `POST /preferences/feedback` endpoint in `backend/src/whattowear/api.py` — `get_current_user_id` + `get_session` dependencies (same pattern as `/wardrobe/items`), calls T006, maps `UnknownWardrobeItemIds` to `404`, returns `SuggestionFeedback` with `201`
- [ ] T008 [P] [US1] Integration tests in `backend/tests/integration/test_preferences_api.py`: liked reaction recorded; rejected reaction with and without reason recorded; reacting twice to the same item set replaces (row count doesn't grow, latest verdict wins); unknown/foreign `item_id` → `404`; missing bearer token → `401`; empty `item_ids` → `422`
- [ ] T009 [US1] Reaction affordance (like/reject buttons + optional reason field on reject) on each outfit card, calling `POST /preferences/feedback` with that outfit's `items`, in `frontend/components/SuggestionResult.tsx`
- [ ] T010 [US1] Regenerate OpenAPI-derived types (`cd frontend && npm run fetch:openapi && npm run gen:types`) against a locally running backend and typecheck (`npm run typecheck`)

**Checkpoint**: User Story 1 fully functional and independently testable — reactions persist, survive a backend restart (Postgres-backed from T002 on), and are correctly scoped per user.

---

## Phase 4: User Story 2 - Future suggestions reflect what I've taught it (Priority: P1)

**Goal**: Without the user restating anything, later `/recommend` suggestions
measurably avoid repeatedly-rejected colors/categories and trend toward the
formality level implied by the user's rejection pattern — while an explicit
request in that suggestion always wins over the learned drift, a single
feedback event never swings anything, and a user with no feedback sees no
change at all.

**Independent Test**: Reject several suggestions sharing a common color,
request a new suggestion, and confirm that color appears measurably less
often than for a user with no rejection history (spec.md US2 Independent
Test / SC-002).

### Implementation for User Story 2

- [ ] T011 [P] [US2] `derive_signals(feedback, dismissals)` pure function in `backend/src/whattowear/memory/preferences.py`: net-count threshold (`MIN_SIGNAL_COUNT = 3`) for rejected colors and avoided categories (`rejections - likes >= threshold`), formality-drift direction from `avg(rejected formality) - avg(liked formality)` (requires ≥3 of each side), dismissal-timestamp filtering per `signal_key` — exactly the algorithm in research.md §2 (no DB access in this module)
- [ ] T012 [P] [US2] Unit tests for `derive_signals()` in `backend/tests/unit/test_preferences.py`: below-threshold produces no signal; contradicting feedback (reject blue ×4, like blue ×1) still nets to a signal reduced but present; formality drift both directions and the below-threshold no-signal case; a dismissed signal is excluded until enough post-dismissal feedback re-establishes it; empty feedback list produces an empty profile
- [ ] T013 [US2] Swap `set_preference`/`get_profile` in `backend/src/whattowear/memory/store.py` to Postgres-backed: open a short-lived session via `db.SessionLocal()` (no session parameter — `profile_note(user_id)`'s call site in `pipeline/run.py` passes none), query `SuggestionFeedbackRow`/`PreferenceSignalDismissalRow` for that user, call `derive_signals()` from T011, project to the existing `dict[str, str]` shape `get_profile()` already returns. `profile_note(user_id)`'s signature, return type, and `None`-when-nothing-learned behavior stay byte-for-byte unchanged; `remember_interaction`/`recent_interactions` are untouched
- [ ] T014 [P] [US2] Wiring test in `backend/tests/integration/test_recommend_profile_note.py` (new file, mocked-pipeline pattern from `test_recommend_auth.py` — mock `generate()`, assert on its call args, no real LLM call): (1) `profile_note()` returns `None` for a user with no feedback rows, and a joined `"key: value; key: value"` string once a signal crosses threshold — confirms `profile_note(user_id)`'s contract is unchanged end-to-end and `pipeline/run.py`/`pipeline/generator.py` needed zero source changes; (2) when a user has a learned profile, the resulting `profile_note` text reaches the mocked `generate()` call (closes analyze finding C1 — the "does the learned signal reach generation" branch was previously dead code, since nothing ever called `set_preference` before this feature); (3) in that same call, the explicit `Context` fields (occasion/formality/etc.) passed to `generate()` are unchanged by the presence of a profile note — confirms the wiring can't let a learned preference clobber an explicit request (closes analyze finding C2 / FR-005's "never overrides" guarantee, at the wiring level — not a claim about whether the LLM itself obeys it, which stays a manual/quickstart concern per root CLAUDE.md's eval-harness gotcha)
- [ ] T015 [US2] Re-run the eval no-regression gate (`cd backend && uv run python -m whattowear.eval.harness`) and confirm the baseline eval user's scores are unchanged (that user has no feedback rows, so `profile_note()` still returns `None` for it — constitution Principle I)

**Checkpoint**: User Stories 1 AND 2 both work — feedback is recorded and it measurably, softly shapes future suggestions for that user only.

---

## Phase 5: User Story 3 - See what the system has learned about me (Priority: P2)

**Goal**: A user can view a plain-language summary of their derived
preferences, or a clear "nothing learned yet" state if they have none.

**Independent Test**: After a user has given enough feedback to produce a
derived signal, open the preferences view and confirm that signal appears in
plain language, not raw counts or ids (spec.md US3 Independent Test).

### Implementation for User Story 3

- [ ] T016 [US3] `GET /preferences` endpoint in `backend/src/whattowear/api.py`: calls `derive_signals()` (T011) directly against the caller's own feedback/dismissal rows, projects each `DerivedSignal` to a `PreferenceSignal` with a plain-language `summary` (e.g. `"color:#1b2a4a"` → `"You tend to reject navy items."`, using `colors.nearest_names()` for the color name — reuses existing code, no new color-naming logic), sets `has_feedback` by checking whether the user has any `suggestion_feedback` rows at all (distinct from "has feedback but no signal has crossed threshold yet")
- [ ] T017 [P] [US3] Integration tests in `backend/tests/integration/test_preferences_api.py`: brand-new user → `{"has_feedback": false, "signals": []}`; user with feedback below every threshold → `{"has_feedback": true, "signals": []}`; user with a crossed threshold → plain-language `summary` present with no raw hex/internal id leaking through; cross-user isolation (user B never sees user A's signals)
- [ ] T018 [US3] `PreferencesView` component + `/preferences` route rendering `PreferenceProfile` (plain-language list, or the "nothing learned yet" empty state) in `frontend/components/PreferencesView.tsx` and `frontend/app/preferences/page.tsx`
- [ ] T019 [US3] Regenerate OpenAPI-derived types again (new endpoint) and typecheck — `cd frontend && npm run fetch:openapi && npm run gen:types && npm run typecheck`

**Checkpoint**: Users can see what's been learned, in plain language, including the "nothing yet" state.

---

## Phase 6: User Story 4 - Clear or correct a learned preference (Priority: P2)

**Goal**: A user can remove one specific derived signal without affecting the
rest of their profile, or clear the entire profile in one action — and a
cleared signal can be learned again later from new feedback.

**Independent Test**: With a user who has a multi-part derived profile,
remove one signal and confirm the rest is untouched; separately, clear the
entire profile and confirm subsequent suggestions behave as if there were no
feedback history (spec.md US4 Independent Test).

### Implementation for User Story 4

- [ ] T020 [US4] `dismiss_signal(session, user_id, signal_key)` in `backend/src/whattowear/crud.py`: upsert a `PreferenceSignalDismissalRow` on `(user_id, signal_key)` with `dismissed_at = now()`
- [ ] T021 [US4] `DELETE /preferences/signals/{signal_key}` endpoint in `backend/src/whattowear/api.py` — calls T020, returns `204`, idempotent (dismissing an absent signal is a no-op, not a `404`)
- [ ] T022 [US4] `DELETE /preferences` endpoint in `backend/src/whattowear/api.py` — computes the caller's current signals via `derive_signals()` (T011), calls T020 for each present `signal_key`, returns `204` (no-op `204` if the profile was already empty)
- [ ] T023 [P] [US4] Integration tests in `backend/tests/integration/test_preferences_api.py`: removing one signal leaves the others in a multi-signal profile; clearing the whole profile makes `GET /preferences` return the no-feedback-equivalent state and a subsequent `/recommend` call behaves as it would for a brand-new user; dismissing an already-absent signal returns `204` not `404`; new feedback recorded after a dismissal re-establishes the same signal once threshold is crossed again (spec.md Edge Cases / US4 AC3)
- [ ] T024 [US4] Remove-one-signal and clear-all actions in `frontend/components/PreferencesView.tsx`
- [ ] T025 [US4] Regenerate OpenAPI-derived types again (two new endpoints) and typecheck — `cd frontend && npm run fetch:openapi && npm run gen:types && npm run typecheck`

**Checkpoint**: All four user stories independently functional — the full feature is deliverable.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T026 [P] Run `specs/004-preference-memory/quickstart.md` end-to-end against a locally running backend + frontend (all 9 steps)
- [ ] T027 [P] `cd backend && uv run ruff check . && uv run ruff format --check .`
- [ ] T028 [P] `cd frontend && npm run lint && npm run build`
- [ ] T029 Full backend test suite (`cd backend && uv run pytest tests/ -q`) — confirm no regression in the pre-existing 149+11 tests alongside the new preference-memory tests

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies.
- **Foundational (Phase 2)**: depends on Setup — blocks every user story.
- **User Story 1 (Phase 3)**: depends on Foundational only.
- **User Story 2 (Phase 4)**: depends on Foundational only. Reads the same `suggestion_feedback` table US1 writes to, but is independently testable by inserting feedback directly (e.g. via US1's own endpoint, or crud-level in a test) — does not require US1's frontend piece.
- **User Story 3 (Phase 5)**: depends on Foundational + T011 (`derive_signals`, built in US2's phase but a pure function with no US2-specific state — importable standalone). If built before US2, T011 must be pulled forward; as ordered here, US3 reuses it from Phase 4.
- **User Story 4 (Phase 6)**: depends on Foundational + T011 (same reuse as US3) + the `preference_signal_dismissal` table from Foundational.
- **Polish (Phase 7)**: depends on all four user stories.

### Within Each User Story

Models/schemas (Foundational) → crud functions → endpoint → tests → frontend → regenerate types. Each story's checkpoint is independently demoable.

### Parallel Opportunities

- T002, T003, T004 (Foundational) touch different files — parallelizable.
- T008 (US1 tests) can run alongside T009/T010 (US1 frontend) once T007 lands.
- T011 and T012 (US2 derivation + its unit tests) are parallelizable with each other but both block T013.
- T017 (US3 tests), T023 (US4 tests) are parallelizable within their own phase.
- T026–T028 (Polish) are parallelizable with each other.

---

## Parallel Example: Foundational Phase

```bash
# T002, T003, T004 touch different files, no shared state yet:
Task: "Additive Alembic migration in backend/alembic/versions/0003_add_suggestion_feedback.py"
Task: "SuggestionFeedbackRow + PreferenceSignalDismissalRow models in backend/src/whattowear/models.py"
Task: "SubmitFeedbackRequest/SuggestionFeedback/PreferenceProfile schemas in backend/src/whattowear/schema.py"
```

## Parallel Example: User Story 2

```bash
# T011 and T012 are independent (implementation vs. its own test file):
Task: "derive_signals() in backend/src/whattowear/memory/preferences.py"
Task: "Unit tests for derive_signals() in backend/tests/unit/test_preferences.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1 (Setup) → Phase 2 (Foundational) → Phase 3 (US1).
2. **STOP and VALIDATE**: reactions are recorded, persist across a backend
   restart, replace-not-accumulate on the same outfit, and are user-isolated.
3. This alone closes FR-001/002/010(persistence)/011/012's write side, but
   delivers no visible behavior change to suggestions yet — US2 is what
   makes the feedback matter (spec.md: "collecting feedback that never
   influences anything would be pointless"). Treat US1+US2 together as the
   real MVP if a demo needs to show impact, not just recording.

### Incremental Delivery

1. Setup + Foundational → foundation ready.
2. US1 → feedback recording works, independently verifiable.
3. US2 → learned preferences visibly shape future suggestions (the feature's core value).
4. US3 → trust/transparency (view what's learned).
5. US4 → correction (remove/clear).
6. Polish → quickstart validation, lint, full test suite.

Each story adds value without breaking the previous ones; US3/US4 both build
on US2's `derive_signals()` (T011) rather than duplicating derivation logic.

---

## Notes

- [P] tasks touch different files with no dependency on an incomplete task.
- [Story] labels map every user-story-phase task to spec.md's US1–US4.
- Commit after each task or logical group (per root CLAUDE.md's git guidance) — do not push or merge without being asked.
- `derive_signals()` (T011) is the single reuse point for US2 (feeds `profile_note`), US3 (feeds `GET /preferences`), and US4 (`DELETE` endpoints compute current signals before dismissing them) — implement it once, correctly, per research.md §2.
