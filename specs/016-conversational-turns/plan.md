# Implementation Plan: Conversational styling turns

**Branch**: `feat/016-conversational-turns` | **Date**: 2026-08-04 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/016-conversational-turns/spec.md`

## Summary

Every Recommend composer send now gets a real, in-voice reply from a new, cheap, retrieval-free LLM
call (`POST /recommend/turns`), which also extracts structured slots (occasion/mood/formality/
location/temp_c) that accumulate in the pipeline's own per-thread checkpoint. "Start styling"
(`POST /recommend/messages`) remains the sole trigger for the real pipeline, unchanged internally —
it now composes its request explicitly from those accumulated slots on a thread's first invoke only
(later, refinement invokes keep 008's unmodified raw-text behavior), and now also produces a visible
"wrap-up" message before the outfits. See `docs/design-decisions.md` §37 (the reversal of §28 that
authorizes this) and §47–§50 (the four decisions this plan makes concrete) for full reasoning.

## Technical Context

**Language/Version**: Python 3.12 (backend, `uv`), TypeScript / Next.js App Router (frontend) —
unchanged, no new language.

**Primary Dependencies**: `langchain_litellm`/`adapters.llm_gateway` (existing, reused — no new LLM
client), `langgraph` (existing — `CompiledStateGraph.get_state`/`update_state`, not previously called
outside `.invoke` anywhere in this codebase, but part of the same already-a-dependency package).

**Storage**: Postgres via Supabase (existing `messages`/`sessions` tables, one migration widening a
check constraint) + the pipeline's own LangGraph checkpointer (existing, PostgresSaver-backed when
configured — see research.md §3) for accumulated slots. No new table.

**Testing**: `pytest` (backend, unit + integration, LLM call mocked per `test_vision.py`'s pattern) +
a live-gateway-only eval harness excluded from CI (matches `eval/harness.py`'s own existing exclusion);
frontend component tests (existing `*.test.tsx` convention).

**Target Platform**: unchanged — Railway (backend), Vercel (frontend), one Next.js app serving web +
installed PWA (Principle IX, untouched by this feature).

**Project Type**: web application (existing `frontend/` + `backend/` split, unchanged).

**Performance Goals**: a conversational turn is "a fraction of one styling request" (§37) — no
retrieval, no wardrobe load, one small-model structured-output call. No new numeric SLA beyond the
existing `wtw_styling_request_timeout_seconds` backstop, which does not apply to this route (it has no
comparable long-running step to bound).

**Constraints**: turn cap configurable (`wtw_conversation_turn_cap`, default 6, §48); CI makes no live
LLM calls (Quality Bar); no pipeline/scoring/retrieval change (Principle I, handoff traps #1/#6); no
inline prompt strings (Technology Constraints); copy stays DRAFT-flagged until the design owner
supplies final text (Principle VIII, handoff §3).

**Scale/Scope**: one new route, one new module (`conversation.py`), one new prompt file, one new copy
module, one new migration (constraint widen only), frontend changes confined to the existing Recommend
chat surface (`Composer`, `ChatMessageList`, `RecommendChat`; `StartStylingButton` unchanged).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **I — Salvaged AI code is authoritative.** No regeneration of retrieval/chunking/ingest/KB/
      scoring/pipeline/eval harness. `pipeline/graph.py` is touched **only** by calling the existing,
      public `CompiledStateGraph.get_state`/`update_state`/`invoke` methods from `recommend.py` — no
      node, edge, or prompt inside `pipeline/` is edited. §49 explicitly reuses
      `_parse_refinement_intent` unmodified rather than building a second refinement mechanism. No
      eval-baseline-affecting refactor is proposed, so no eval-baseline re-run is required.
- [x] **II — Deterministic scoring.** Unaffected — no scoring code touched, no new scoring code
      added. The new LLM call never scores, ranks, or selects an outfit; it only extracts slots and
      writes conversational prose, both of which are inputs to the unchanged deterministic pipeline,
      never a replacement for any of its checkpoints.
- [x] **III — Style gates wardrobe.** Unaffected — this feature adds no retrieval call of any kind
      (explicit non-goal, research.md §1); the existing style-then-wardrobe ordering inside the
      pipeline is untouched.
- [x] **IV — Grounded output.** Unaffected — outfit grounding/citation logic is not touched. The new
      conversational reply is not a grounded claim about wardrobe items (it's conversation, not an
      outfit rationale) and cites nothing, matching the copy constraint "never promise anything the
      pipeline cannot deliver" (handoff §3).
- [x] **V — Scorers are eval metrics.** N/A — this feature introduces no quality judgment about
      outfits. Its own two eval halves (slot-extraction accuracy, voice) are new, separate metrics for
      a new capability, not a scoring function this principle governs.
- [x] **VI — Schema stability.** `formality` extracted by the new LLM call is validated against the
      existing six-value `Formality` enum before ever being written to checkpoint state or passed to
      the pipeline; an unrecognized value is dropped to `None`, never introduced as a parallel scale
      (data-model.md).
- [x] **VII — Contracts.** `frontend/lib/api/schema.d.ts` is regenerated from the backend's OpenAPI
      output after the new route and `wrap_up_text` field land (research.md §13); no hand-maintained
      duplicate type.
- [x] **VIII — Visual truth.** The one new user-visible surface this feature cannot yet fully satisfy:
      ordinary conversational reply copy has no `design-system.md` entry (handoff §3, itself the
      reason this gate is flagged rather than silently marked pass). Handled per Principle VIII's own
      instruction for exactly this situation — not invented in code, drafted in one clearly-marked
      module (`copy.py`) and one clearly-marked prompt section, both swappable without touching logic,
      status reported explicitly rather than shipped silently (research.md §9). Every other visual
      value this feature touches (bubble states, disabled/in-progress composer, "Thinking…" vs.
      "Styling your outfit…") already exists in `design-system.md` § Chat input behavior and is built
      to its "Intended (production)" text, not the observed prototype behavior, per the handoff's own
      instruction. Loading/empty/error/offline states: sending-in-flight (disabled composer +
      "Thinking…"), call-failure (graceful degrade, no dead end), offline (composer disabled, no
      queuing promised) are all named in FR-008/FR-010/FR-011 and covered in tasks. No code is copied
      from `design/prototype/`.
- [x] **IX — One codebase.** No new route/screen, no platform branching — this feature only changes
      behavior inside the existing Recommend chat surface, identical at every form factor already.
- [x] **X — Documents are data.** No new document/corpus content. `evals/conversational_golden_set.yaml`
      is a new file under the same tracked-eval-dataset carve-out `evals/golden_set.yaml` already uses
      — not a corpus, no `infra/corpus.yaml` entry needed.

No unresolved gate. Complexity Tracking is not needed.

## Project Structure

### Documentation (this feature)

```text
specs/016-conversational-turns/
├── plan.md              # this file
├── research.md          # Phase 0 — done
├── data-model.md        # Phase 1 — done
├── quickstart.md        # Phase 1 — done
├── contracts/
│   └── recommend-turns.md
└── tasks.md             # Phase 2 (/speckit-tasks) — not yet generated
```

### Source Code (repository root)

```text
backend/
├── infra/supabase/migrations/
│   └── 0012_conversational_turns.sql        # NEW — widen messages.kind constraint only
├── src/whattowear/
│   ├── conversation.py                       # NEW — the LLM call site (sibling to vision.py)
│   ├── copy.py                                # NEW — DRAFT-flagged deterministic strings (§9)
│   ├── schema.py                              # CHANGED — add ConversationalTurnResult model
│   ├── core/config.py                         # CHANGED — wtw_conversation_turn_cap
│   ├── prompts/
│   │   └── conversational_turn_system.md      # NEW — versioned system prompt
│   ├── api/v1/routes/recommend.py             # CHANGED — new POST /recommend/turns;
│   │                                           #   send_message: drop user_message insert,
│   │                                           #   compose from slots on first invoke,
│   │                                           #   insert + return wrap_up_text
│   ├── repositories/supabase_sessions.py      # CHANGED — add count_user_messages
│   └── eval/
│       └── conversational_harness.py          # NEW — live-gateway golden-set runner (not in CI)
├── evals/
│   └── conversational_golden_set.yaml         # NEW
└── tests/
    ├── unit/
    │   ├── test_conversation.py               # NEW
    │   └── eval/test_conversational_golden_set.py  # NEW
    └── integration/
        └── test_recommend_routes.py           # CHANGED — new + updated cases

frontend/
├── lib/api/schema.d.ts                        # REGENERATED (generated, gitignored)
└── components/recommend/
    ├── Composer.tsx                           # CHANGED — onSend becomes async, calls
    │                                           #   POST /recommend/turns
    ├── RecommendChat.tsx                       # CHANGED — turnPending/stylingPending states,
    │                                           #   wrap-up message insertion
    ├── ChatMessageList.tsx                     # CHANGED — plain-reply bubble reused for
    │                                           #   conversational replies; "Thinking…" bubble
    ├── Composer.test.tsx                       # CHANGED
    ├── RecommendChat.test.tsx                  # CHANGED
    └── ChatMessageList.test.tsx                # CHANGED (or new, if it doesn't exist yet)
```

**Structure Decision**: every file above sits inside the fixed layout (`frontend/`, `backend/`,
`infra/`). No new top-level directory. `pipeline/`, `scoring/`, `retrieval/`, and every file already
under `prompts/` for the pipeline are untouched — the only files this plan adds under `backend/src/
whattowear/` sit beside `vision.py`, not inside `pipeline/`.

## Complexity Tracking

*No entries — no Constitution Check gate required a justified exception.*
