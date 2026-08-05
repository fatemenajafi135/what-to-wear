# Phase 0 Research: Conversational styling turns

Every decision below either restates something already settled by `docs/design-decisions.md` §37
(amending §28) or is recorded fresh at §47–§50 of that same file, with rejected alternatives. This
file indexes those decisions for the plan; it does not re-argue them.

## 1. New conversational endpoint

**Decision**: `POST /recommend/turns` — new route in the existing `recommend.py` router (matching the
codebase's own convention: every Recommend-surface route lives in one file, not split by feature).
Request `{ message: str, thread_id: str | None }` (thread_id null on the very first turn, minted
the same `uuid.uuid4()` way `send_message` already does). Response
`{ thread_id, reply_text, occasion?, formality?, mood?, temp_c?, location? }` — the exact shape §37
specifies, plus `thread_id` so a fresh thread's minted id reaches the client the same way
`SendMessageResponse.thread_id` already does.

**Rationale**: matches the handoff's contract exactly; keeping it in `recommend.py` rather than a new
module mirrors how `/recommend/readiness`, `/recommend/messages`, `/recommend/sessions*` and
`/recommend/outfits*` already coexist in one file, each documented in that file's own module
docstring.

**No readiness gate**: unlike `/recommend/messages`, this route does not call
`evaluate_wardrobe_readiness` — a conversational reply never touches wardrobe size or contents (the
handoff's own "no wardrobe load" constraint), and the screen that hosts the composer already refuses
to render it when `readiness.ready` is false (`RecommendChat.tsx`), so there is no reachable path where
this endpoint is called against an unready closet.

## 2. New LLM call site

**Decision**: a new top-level module `backend/src/whattowear/conversation.py`, sibling to `vision.py`
(not inside `pipeline/`, which stays untouched per Principle I). Follows `vision.py`'s exact pattern:
`adapters.llm_gateway.get_chat_model(...).with_structured_output(_SCHEMA, method="json_schema")`, a
hand-written nullable-required JSON schema (same reason `vision.py::_EXTRACTION_SCHEMA` gives — the
gateway rejects a Pydantic-derived schema for an all-optional model), `@traceable`, and a system prompt
loaded via `prompts.load_prompt("conversational_turn_system")` — never an inline string.

**Rationale**: "not a second way to call an LLM" (handoff §4.1) — reusing the exact factory function and
structured-output idiom `vision.py`/`pipeline/generator.py` already use is what makes that true, rather
than merely true in spirit.

**Model**: `get_chat_model()` with no `model=` override — the existing `wtw_chat_model` default
(`openai/gpt-5.4-mini`), i.e. "the small chat model" the handoff names, is already the right one; no new
model setting is needed. (`vision.py` overrides to `vision_model` because it needs vision capability;
this call needs neither vision nor the heavier generation-model tier.)

## 3. Slot storage

**Decision**: `docs/design-decisions.md` §47 — the pipeline's own LangGraph checkpointer, read via
`CompiledStateGraph.get_state(config)` and written via `.update_state(config, values)`, never via
`.invoke(...)`. No migration. Full reasoning and three rejected alternatives (a new `sessions.slots`
column, `memory/store.py`'s in-process `InMemoryStore`, on-demand reconstruction from `messages`) are
recorded there.

## 4. Turn cap

**Decision**: §48 — `Settings.wtw_conversation_turn_cap: int = 6`, counted from existing
`kind='user_message'` rows per thread (no new counter), lifetime per thread rather than reset per
"Start styling" tap. Once a call's turn number exceeds the cap, the endpoint skips the LLM entirely and
returns the fixed "turn cap reached" copy (§ below).

## 5. Slot lifecycle across a "Start styling" tap

**Decision**: §49 — slot composition (§47) supplies the invoke input only for a thread's **first** real
pipeline invoke (`graph.get_state(config).values.get("original_context") is None`, checked in
`send_message` before building the invoke dict). Every later invoke on that thread uses the pre-existing,
unmodified 008 raw-text refinement path (`occasion = body.message`) — the exact signal
`pipeline.graph.parse_request` already uses to distinguish a fresh thread from a continuing one, read
once more, one call earlier, in the route.

## 6. `POST /recommend/messages` no longer inserts `user_message`

**Decision**: §50 — removed outright (not made conditional). Every composer send now reaches
`POST /recommend/turns` first, which is the sole writer of `user_message` rows going forward. 008/009's
existing integration tests that relied on `send_message` writing that row are updated (not deleted) to
reflect the new architecture, keeping the handoff's "test count has not dropped" bar intact.

## 7. Composing the Start-styling invoke input explicitly

**Decision**: even though checkpointer merge semantics would let omitted keys flow through
automatically (§47), `send_message` builds the full `graph.invoke(...)` input dict by hand from
`graph.get_state(config).values` on a first invoke — occasion/mood/formality/location/temp_c each
read out and set individually, `occasion` falling back to `body.message` when no `occasion` slot was
ever extracted (the handoff's own fallback rule). This is what makes "what was actually passed to the
graph" answerable by reading one dict literal at the call site, satisfying the handoff's explicit
verification instruction (§8: "by inspecting the invoke input, not by looking at the outfits").

## 8. The wrap-up message

**Decision**: Python-templated, not a second LLM call — "the model extracts; Python composes" (§37)
applies to the wrap-up the same way it applies to the invoke input. Built from `result.context`
(the same `Context` `_meta_line` already reads for the pager's meta line) **after** `graph.invoke`
returns, using the draft template `"Styling for {occasion}, {formality}."` — degrading to just
`"Styling for {occasion}."` when `formality` was never resolved to anything worth stating beyond the
pipeline's own default inference (context_assembler.assemble_context always fills `formality` via
`infer_formality` when absent, so in practice this is rarely empty; the degrade path exists for
honesty, not because the field can be null in `Context`).

Persisted as a **new** `messages` row, `kind='wrap_up'`, inserted alongside the existing
`kind='styling_reply'` row `send_message` already writes — two rows per Start-styling call now, not
one, matching the handoff's "adds `conversational_turn` and `wrap_up`" framing (both are genuinely new
kinds, not one kind doing two jobs). Returned to the client as a new `SendMessageResponse.wrap_up_text`
field, rendered by the frontend as its own assistant bubble immediately above the outfit pager within
the same response — "before the outfit group loads beneath it" (handoff §4.3) is a rendering-order
guarantee within one response, not a second round trip, since the whole `/recommend/messages` call is
already synchronous end-to-end.

Rendered on **every** Start-styling tap (first and refinement), not only the first — `result.context`
is populated identically on both paths, so no extra branching is needed to support this, and the
handoff's DoD line ("Start styling shows the wrap-up... then the outfits") is not qualified to "first
tap only."

## 9. Copy — draft vs. final

**Decision**: the deterministic, Python-owned strings (turn-cap-reached copy, call-failed copy, the
wrap-up template) live in **one new module**, `backend/src/whattowear/copy.py`, each constant carrying
a comment pointing at `docs/handoffs/016-conversational-turns.md` §3 and flagged as DRAFT — per the
handoff's explicit instruction ("keep every string in one module with a comment pointing at §3").
`prompts/conversational_turn_system.md` additionally embeds the four dynamic-reply example lines from
the same draft table as voice-calibration few-shot text, under its own DRAFT-flagged heading, since a
system prompt guiding free-form generation is the correct place for style exemplars — the model is not
meant to reproduce them verbatim (this is genuine back-and-forth conversation, not four canned
strings), only to match their register.

**No frontend copy module is needed.** The one place client-side copy might have been needed — a
fallback when the network call to `/recommend/turns` itself fails (not an LLM failure, which the
backend already catches and turns into the "call failed" `reply_text`, a normal 200) — is handled
without inventing text: the composer simply re-enables and no assistant bubble is added for that failed
send, matching FR-010/SC-005 ("leaves the conversation in a usable state") without a client-authored
string standing in for design copy that was never supplied for that surface either.

**Status at plan time**: final copy has not arrived. Every string in `copy.py` and
`conversational_turn_system.md` stays visibly marked DRAFT; swapping in final copy when it arrives is a
content-only edit to those two files, touching no route or component logic.

## 10. Golden set — two halves, evaluated separately

**Decision**: `backend/evals/conversational_golden_set.yaml` — new file (constitution Principle X's
eval-dataset carve-out), each case shaped as
`{id, prior_slots, utterance, expected_slots, voice_check}`:

- `expected_slots` is checked deterministically (dict equality against what extraction returns) — the
  handoff's "checkable" half.
- `voice_check` (a short prose description, e.g. "acknowledges the occasion, asks about formality, one
  question only") is scored by the existing `eval/judge.py` LLM-judge pattern, adapted with a
  conversation-specific rubric — the handoff's "judge or loose check" half. No case asserts exact
  `reply_text`.

Both halves run only in `eval/conversational_harness.py` (new, mirrors `eval/harness.py`), a live-gateway
script excluded from `pytest`/CI, matching how `eval/harness.py` itself is never invoked by the test
suite. `pytest`-visible coverage is a new `backend/tests/unit/test_conversation.py`
(`get_chat_model` mocked, exactly `test_vision.py`'s pattern) plus
`backend/tests/unit/eval/test_conversational_golden_set.py` (fixture-shape assertions only, no call) —
this is what satisfies "CI makes no live LLM calls" for the new path.

## 11. Migration

**Decision**: one new file, `infra/supabase/migrations/0012_conversational_turns.sql` —
`ALTER TABLE messages DROP CONSTRAINT messages_kind_check, ADD CONSTRAINT messages_kind_check CHECK
(kind IN ('user_message', 'styling_reply', 'conversational_turn', 'wrap_up'))` (exact constraint name
confirmed against `0011`'s generated name before writing the migration). No table reshape, no backfill
— exactly what `0011`'s own comment already promised this feature would need.

## 12. Frontend architecture

**Decision**: `Composer`'s `onSend` becomes async and itself calls `POST /recommend/turns` (today it is
purely local — `RecommendChat.handleSend` appends to `messages`/`pendingTexts` and nothing else).
`RecommendChat` gains a `sending` status distinct from today's Start-styling-only `"sending"` — renamed
so the two are unambiguous: `"turnPending"` (conversational call in flight — shows "Thinking…") vs.
`"stylingPending"` (Start-styling call in flight — shows the pager's existing "Styling your outfit…"
skeleton, unchanged). Both disable the composer input and send button and the Start-styling button;
`useOnlineStatus` continues to gate both independently, unchanged.

`pendingTexts` (the raw-text accumulator feeding `/recommend/messages.message`) is **kept**,
unmodified in spirit — it still needs to exist for §49's refinement-tap path and the first-tap fallback
— but is no longer the only thing a send does; a send now also fires the conversational call whose
reply becomes a new assistant `ChatMessage`.

`ChatMessageList`/`ChatMessage` gains a `kind: "reply"` variant rendered as a plain assistant bubble
(today's shape already covers this — the existing `replyText`-only branch, previously reached only for
a zero-outfit Start-styling response, is reused for ordinary conversational replies too) and the
wrap-up is appended as its own `ChatMessage` immediately before the outfit-bearing one in the same
`handleStartStyling` state update.

## 13. Frontend API types

**Decision**: `frontend/lib/api/schema.d.ts` is regenerated (`npm run generate:api-types`, backend
running) once the new route and `SendMessageResponse.wrap_up_text` field land — per the handoff's own
trap #7. No hand-maintained duplicate type is introduced (Principle VII).
