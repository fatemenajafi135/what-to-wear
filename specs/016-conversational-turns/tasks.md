# Tasks: Conversational styling turns

**Input**: Design documents from `/specs/016-conversational-turns/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/recommend-turns.md,
quickstart.md — all present.

**Tests**: included. The constitution's Quality Bar requires a unit test for deterministic logic and
a golden-set entry for any LLM-dependent path; this is a new LLM path, so tests are not optional here.

**Organization**: grouped by user story (spec.md priorities). US1/US2 are both P1 and share almost all
foundational work — the real MVP boundary in this feature is "the endpoint exists and composes
correctly," not either story alone, so Phase 2 (Foundational) carries more of the total work than
usual.

## Path Conventions

Backend: `backend/src/whattowear/`, tests in `backend/tests/{unit,integration}`, evals in
`backend/evals/`. Frontend: `frontend/components/recommend/`. Infra:
`infra/supabase/migrations/`.

---

## Phase 1: Setup

- [x] T001 Confirm `backend/.env` has `AI_GATEWAY_API_KEY` set (copy `backend/.env.example`,
      request the value if missing — cannot proceed to any live-call verification without it).
- [x] T002 Confirm `npx supabase start` and `docker compose up -d` (from `infra/`) are running and
      Qdrant is populated, so a later "Start styling" smoke test doesn't look broken for unrelated
      reasons (handoff trap #8).
- [x] T003 Inspect the generated constraint name for `messages.kind` in the local Supabase instance
      (`\d messages` or `information_schema.check_constraints`) to confirm the exact name migration
      `0012` must `DROP CONSTRAINT` before writing it.

## Phase 2: Foundational (blocking prerequisites for both P1 stories)

**Purpose**: the conversational endpoint, slot storage, and composition logic every user story
depends on. No user story is independently testable until this phase is done.

- [x] T004 [P] Write `infra/supabase/migrations/0012_conversational_turns.sql` — drop and recreate
      `messages`'s `kind` check constraint to add `'conversational_turn'` and `'wrap_up'` (exact name
      from T003). No other change. Apply via `npx supabase db reset` and confirm all four kind values
      are accepted, three are still rejected (garbage value).
- [x] T005 [P] Add `wtw_conversation_turn_cap: int = 6` to `Settings` in
      `backend/src/whattowear/core/config.py`, beside `wtw_wardrobe_min_items` (design-decisions.md
      §48).
- [x] T006 [P] Create `backend/src/whattowear/copy.py` with `TURN_CAP_REACHED`, `CALL_FAILED`, and
      `wrap_up_text(occasion: str, formality: str | None) -> str` — every constant carries a comment
      pointing at `docs/handoffs/016-conversational-turns.md` §3 and is flagged DRAFT (data-model.md
      "copy.py (new module)").
- [x] T007 [P] Add `ConversationalTurnResult` to `backend/src/whattowear/schema.py` — `reply_text: str`
      plus optional `occasion`/`formality`/`mood`/`temp_c`/`location`, matching `ExtractedAttributes`'s
      all-fields-independent shape (ok for some to be null while `reply_text` is always present).
- [x] T008 [P] Write `backend/src/whattowear/prompts/conversational_turn_system.md` — versioned
      front-matter (`version: 1`, `model:` the chat default, `role: system`), instructs first-person
      stylist voice, at most one clarifying question, never promising anything the pipeline can't
      deliver, extracting only what's genuinely stated (no guessing a slot), and includes the four
      dynamic-reply lines from handoff §3 as DRAFT-flagged few-shot voice examples (research.md §9).
- [x] T009 Write `backend/src/whattowear/conversation.py`: hand-written nullable-required JSON schema
      (mirrors `vision.py::_EXTRACTION_SCHEMA`), `reply()` function taking the message + already-known
      slots dict, calling `adapters.llm_gateway.get_chat_model()` (no model override) +
      `with_structured_output(_SCHEMA, method="json_schema")`, `@traceable(name="conversation.reply")`,
      loading the system prompt via `prompts.load_prompt("conversational_turn_system")`, validating any
      returned `formality` against the six-value enum (drop to `None` if unrecognized), returning
      `ConversationalTurnResult`. Raises on a genuine call failure — caller maps that to fallback copy,
      never a 5xx (mirrors `vision.py`).
- [x] T010 [US1][US2] Add `count_user_messages(user_id: str, thread_id: str) -> int` to
      `backend/src/whattowear/repositories/supabase_sessions.py` (contracts/recommend-turns.md).
- [x] T011 [US1][US2] Implement `POST /recommend/turns` in
      `backend/src/whattowear/api/v1/routes/recommend.py` per contracts/recommend-turns.md steps 1–9:
      thread_id mint-or-reuse, upsert session, insert `user_message`, turn-cap check via T010, on-cap
      short-circuit to `copy.TURN_CAP_REACHED` (no LLM call), else call `conversation.reply()` (T009)
      with `graph.get_state(config).values` as known slots, catch a call failure into
      `copy.CALL_FAILED`, `graph.update_state(config, ...)` with only the non-null new slots, insert
      `conversational_turn` message, return `SendMessageResponse`-sibling model per the contract.
- [x] T012 [US2] In `send_message` (`recommend.py`), remove the existing
      `session_repository.insert_message(..., "user_message", body.message)` call
      (design-decisions.md §50) — leave a comment noting `POST /recommend/turns` is now the sole
      writer of that kind.
- [x] T013 [US2] In `send_message`, before building the `graph.invoke(...)` input dict: read
      `graph.get_state(config).values`; branch on `original_context is None` exactly as
      contracts/recommend-turns.md describes — compose explicitly from slots (occasion falling back to
      `body.message`) on a first invoke, or build the unmodified 008 `{"occasion": body.message, ...}`
      dict on a refinement invoke. No change to anything from `graph.invoke(...)` onward.
- [x] T014 [US3] In `send_message`, after `graph.invoke(...)` returns and `result`/`note` are resolved:
      build `wrap_up = copy.wrap_up_text(occasion, result.context.formality if result.context else
      None)`, insert a `wrap_up` message, add `wrap_up_text` to the returned response model.
- [x] T015 [P] `backend/tests/unit/test_conversation.py` — `get_chat_model` mocked (pattern:
      `test_vision.py`). Cases: extracts a known slot; leaves unmentioned slots `None`; an
      out-of-enum `formality` string from the model is dropped to `None`, never passed through
      (Principle VI); a call failure raises (caller's job to catch, not this function's).
- [x] T016 [P] `backend/evals/conversational_golden_set.yaml` — hand-authored cases:
      `{id, prior_slots, utterance, expected_slots, voice_check}` (research.md §10). At least one case
      per slot (occasion/formality/mood/temp_c/location), one case with prior_slots already partially
      filled (must not re-ask), one with an utterance that maps to nothing extractable.
- [x] T017 [P] `backend/tests/unit/eval/test_conversational_golden_set.py` — fixture-shape assertions
      only (path resolves, cases load, ids unique, every case has an id/utterance), mirrors
      `test_golden_set.py`. No live call.
- [x] T018 `backend/src/whattowear/eval/conversational_harness.py` — live-gateway runner scoring both
      halves of `conversational_golden_set.yaml` (deterministic `expected_slots` match; `voice_check`
      via an adapted `eval/judge.py`-style rubric). Not imported by any `pytest`-collected test file.

**Checkpoint**: `POST /recommend/turns` and the changed `POST /recommend/messages` are both fully
implemented and unit-tested. US1 and US2 can now be verified independently.

---

## Phase 3: User Story 1 — The stylist actually replies (P1)

**Goal**: every composer send gets a real, in-voice reply before "Start styling."

**Independent Test**: send one message in Recommend; an assistant bubble with a reply appears before
"Start styling" is tapped (quickstart.md Scenario 1).

- [x] T019 [P] [US1] **Built differently than drafted, deliberately**: `Composer.tsx` stays a dumb
      text input — `onSend` keeps its original synchronous signature. `RecommendChat.tsx`'s own
      `handleSend` becomes `async` and calls `apiClient.POST("/api/v1/recommend/turns", ...)` itself,
      exactly mirroring how it already owns the one other real network call (`handleStartStyling`).
      Giving `Composer` its own fetch/`thread_id` awareness would have split "the network call" and
      "the state that changes because of it" across two components for no benefit — `RecommendChat`
      already documents itself as owning the chat surface's one real network trigger.
- [x] T020 [US1] `RecommendChat.tsx`: rename the existing Start-styling-only `"sending"` status to
      `"stylingPending"`; add `"turnPending"` for a conversational call in flight. `handleSend`
      becomes async: append the user bubble, set `turnPending`, await the turns call, append the
      assistant reply bubble (or, on a genuine fetch failure, append nothing — research.md §9), clear
      `turnPending`. `thread_id` is set from the **first** turns response if not already held (a fresh
      thread may now be minted by `/recommend/turns` before "Start styling" is ever tapped).
- [x] T021 [US1] `Composer.tsx` / `StartStylingButton.tsx`: disable on `turnPending || stylingPending`
      (currently only `inFlight`/Start-styling-in-flight) — design-system.md § Chat input behavior
      "Intended (production)": both input and send button disabled, distinct visible in-progress
      affordance, re-enable the instant the reply lands.
- [x] T022 [US1] `ChatMessageList.tsx`: render a `"Thinking…"` bubble while `turnPending` (distinct
      component/copy from the existing `PagerSkeletonCard`'s "Styling your outfit…", which stays for
      `stylingPending` only).
- [x] T023 [P] [US1] Update `Composer.test.tsx` for the async `onSend` contract.
- [x] T024 [P] [US1] Update/create `RecommendChat.test.tsx` cases: a send produces an assistant reply
      bubble; `turnPending` disables composer + Start-styling; a second reply doesn't re-ask about an
      already-known slot (mock the turns response accordingly).
- [x] T025 [US1] `backend/tests/integration/test_recommend_routes.py`: new cases for
      `POST /recommend/turns` — first call mints `thread_id` and returns a reply; a second call on the
      same thread receives the first call's extracted slots as "already known" input to the (mocked)
      LLM; empty message → `422`.

**Checkpoint**: User Story 1 is independently demoable — conversation happens, no reliance on US2/US3.

---

## Phase 4: User Story 2 — What I said earlier is what gets used (P1)

**Goal**: outfits from "Start styling" reflect everything discussed, not just the latest message —
and this is verified against the actual invoke input, not the outfits.

**Independent Test**: state occasion in turn 1, formality in turn 2, tap "Start styling"; confirm both
values are in the `graph.invoke(...)` input (quickstart.md Scenario 2).

- [x] T026 [US2] `backend/tests/integration/test_recommend_routes.py`: the load-bearing test for this
      whole feature — call `/recommend/turns` twice (occasion in turn 1, formality in turn 2, mocked
      LLM), then call `/recommend/messages`; patch `pipeline.graph.get_compiled_graph(...).invoke` (or
      capture its call args via a spy) and assert the captured input dict contains **both** the turn-1
      occasion and the turn-2 formality. This is the test that proves handoff §8's verification
      requirement, not an eyeball check of the response.
- [x] T027 [US2] `backend/tests/integration/test_recommend_routes.py`: a refinement-tap case — after
      one real invoke on a thread, a second `/recommend/messages` call's invoke input is the unmodified
      008 shape (`occasion = body.message`, no slot fields injected), proving design-decisions.md §49's
      handoff to the existing refinement path.
- [x] T028 [US2] `backend/tests/integration/test_recommend_routes.py`: update every existing
      008/009/011 case that asserted a `user_message` row was written by `/recommend/messages` directly
      — either call `/recommend/turns` first (matching the real flow) or assert the row's absence from
      that route, per design-decisions.md §50. Confirm total backend test count has not dropped
      (baseline: 644 + whatever 009 already added).
- [x] T029 [US2] `backend/tests/integration/test_recommend_routes.py`: a case with zero slots ever
      extracted — `/recommend/messages`'s invoke `occasion` falls back to `body.message`, matching
      008's original behavior exactly.
- [x] T029a [US2] `backend/tests/integration/test_recommend_routes.py`: overwrite case (FR-004) —
      two `/recommend/turns` calls on one thread that each extract a *different* value for the
      **same** slot (e.g. formality "casual" then "business_casual"); assert the later value, not
      the earlier one, is what reaches the `/recommend/messages` invoke input. Distinct from T026
      (which proves two *different* slots both arrive) — this is the one test that actually exercises
      the checkpointer's per-key overwrite semantics §47 relies on.

**Checkpoint**: the conversation demonstrably changes pipeline input. Combined with Phase 3, this is
the feature's core value delivered.

---

## Phase 5: User Story 3 — Start styling shows its work (P2)

**Goal**: a wrap-up assistant message renders before the outfits, degrading gracefully when a slot
was never mentioned.

**Independent Test**: short conversation, tap "Start styling," confirm a wrap-up bubble renders before
the outfit pager, and reads sensibly with formality absent (quickstart.md Scenario 2 step 2 +
data-model.md's degrade case).

- [x] T030 [US3] `RecommendChat.tsx` `handleStartStyling`: when the response includes `wrap_up_text`,
      append it as its own assistant `ChatMessage` (plain-reply bubble) **before** appending the
      outfit-bearing message, in the same state update.
- [x] T031 [P] [US3] `backend/tests/unit/test_copy.py` (new, small): `wrap_up_text("wedding",
      "formal")` → `"Styling for wedding, formal."`; `wrap_up_text("wedding", None)` →
      `"Styling for wedding."` (data-model.md's degrade case).
- [x] T032 [US3] `backend/tests/integration/test_recommend_routes.py`: `/recommend/messages`
      response includes `wrap_up_text`, and a `wrap_up`-kind message row exists afterward
      (`GET /recommend/sessions/{id}` shows it in order, alongside the existing `styling_reply`).
      Same test also asserts a `conversational_turn` row from an earlier `/recommend/turns` call in
      the same thread comes back from `GET /recommend/sessions/{id}` with `role="assistant"` — the
      one place the two new `messages.kind` values actually reach an existing (011) read path, which
      nothing else in this phase otherwise exercises.
- [x] T033 [P] [US3] Update `RecommendChat.test.tsx`: wrap-up bubble renders above the outfit pager
      within one `handleStartStyling` response.

**Checkpoint**: the full "converse, tap Start styling, see what was understood, then see outfits" loop
is demoable end-to-end.

---

## Phase 6: User Story 4 — The conversation doesn't stall or run away (P2)

**Goal**: turn cap steers to Start styling; a failed conversational call never blocks Start styling;
offline disables the composer without promising a queued send.

**Independent Test**: quickstart.md Scenario 3 (cap + failure) and Scenario 4 (offline).

- [x] T034 [US4] `backend/tests/integration/test_recommend_routes.py`: send `wtw_conversation_turn_cap
      + 1` messages on one thread (override the setting in the test); confirm the last reply is
      exactly `copy.TURN_CAP_REACHED` and no LLM call happened for it (mock asserts `not called` past
      the cap).
- [x] T035 [US4] `backend/tests/integration/test_recommend_routes.py`: mock `conversation.reply` to
      raise; confirm `/recommend/turns` still returns `200` with `copy.CALL_FAILED` and no slot update
      occurred (`graph.get_state` unchanged before/after).
- [x] T036 [US4] `backend/tests/integration/test_recommend_routes.py`: after a simulated
      `/recommend/turns` failure, `/recommend/messages` on the same thread still succeeds using
      whatever slots were accumulated before the failure (SC-005).
- [x] T037 [P] [US4] `RecommendChat.test.tsx` / `Composer.test.tsx`: a rejected `/recommend/turns`
      fetch leaves the composer re-enabled and adds no assistant bubble, and does not clear
      `pendingTexts`/block a subsequent "Start styling" tap.
- [x] T038 [P] [US4] Confirm (existing `useOnlineStatus` wiring, likely no code change needed —
      verify only) the composer already disables on `navigator.onLine === false` and that no code path
      queues or promises a send while offline; add a `Composer.test.tsx` case if none currently covers
      the turns-call path specifically.

**Checkpoint**: the feature is safe to leave running unattended — bounded cost, no dead ends.

---

## Phase 7: Polish & cross-cutting

- [x] T039 Regenerate `frontend/lib/api/schema.d.ts` (`npm run generate:api-types`, backend running)
      once T011/T014's response shapes are stable; fix any resulting frontend type errors.
- [x] T040 [P] `ruff check`, `ruff format --check`, `mypy src`, `lint-imports` (confirm `conversation.py`
      and `copy.py` don't import `fastapi`/`whattowear.api` — they're not in the frozen AI-only set,
      but keep them dependency-light on principle) — all clean.
- [x] T041 [P] `eslint`, `tsc --noEmit`, `next build` — all clean.
- [x] T042 Run `uv run pytest` — full backend suite green, count not dropped.
- [x] T043 Run the live-gateway `conversational_harness.py` (T018) once, by hand — record whether the
      slot-extraction and voice-check halves pass; this is not a CI gate but is part of the handoff's
      "report back" requirement. **Result**: voice mean 0.86/1.0 over 7 judged cases (solid). Slot
      match 1/7 *exact*, but most "mismatches" are the model harmlessly re-stating an already-known
      prior slot alongside the genuinely new one — the harness's strict-equality comparison checks
      the full extracted set against the delta-only `expected_slots`, not "did the new value land
      without corrupting old ones," which is what the route itself actually needs and what the
      integration tests (T026/T029a) verify precisely. One real, worth-tracking imprecision found:
      case c07 ("more casual than formal" → expected `smart_casual`, got `casual`) — a genuine
      judgment call the model resolved more aggressively than intended, not a wiring bug. Left as a
      named follow-up (harness scoring precision + one prompt-tuning case), not blocking — this is
      exactly the kind of gap the golden set exists to surface over time, not fix on first run.
- [x] T044 Manual browser pass at `localhost:3000` **and** `127.0.0.1:3000`, both light and dark theme
      (quickstart.md all four scenarios) — the handoff's own definition-of-done line.
- [x] T045 Confirm whether final assistant-turn copy has arrived from the design owner; if yes, swap
      it into `copy.py`/`conversational_turn_system.md` (content-only edit, T006/T008's files) and
      remove the DRAFT flags; if no, leave both files flagged and say so plainly in the report.

---

## Dependencies

- **Phase 1 (Setup)** → **Phase 2 (Foundational)**: T003's constraint name feeds T004.
- **Phase 2** blocks every user-story phase — `POST /recommend/turns` and the changed
  `POST /recommend/messages` are shared by every story.
- **US1 (Phase 3)** and **US2 (Phase 4)** are both P1 and can proceed in parallel once Phase 2 is done
  — US1 is frontend-heavy, US2 is backend-integration-test-heavy, and neither's tasks touch the other's
  files.
- **US3 (Phase 5)** depends on US2's `wrap_up_text` field existing in the response (T014) but not on
  US1's frontend wiring being finished — the backend half (T031, T032) can start as soon as Phase 2
  lands.
- **US4 (Phase 6)** depends only on Phase 2 (the cap check and failure handling live entirely in
  T009/T011).
- **Phase 7 (Polish)** last, after every story phase.

## Parallel example (after Phase 2)

```
T019 [P] [US1] Composer.tsx async onSend       T026 [US2] invoke-input integration test
T023 [P] [US1] Composer.test.tsx               T027 [US2] refinement-tap integration test
T031 [P] [US3] copy.py unit test               T034 [US4] turn-cap integration test
```

## Implementation strategy

**MVP = Phase 2 + Phase 3 + Phase 4** (both P1 stories). This is the minimum that delivers the
handoff's actual mission: a real conversation whose content demonstrably reaches the pipeline. Phase 5
(wrap-up) and Phase 6 (cap/failure/offline hardening) are P2 — valuable, required by the handoff's own
DoD, but the feature is not silently broken without them for one extra commit's worth of time; they
should still land before the PR is considered done, not deferred past this slice.
