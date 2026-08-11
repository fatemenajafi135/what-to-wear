# Contract: `POST /api/v1/recommend/turns` — picked-event seed (defect 3)

**No request/response shape change.** `SendTurnRequest`/`SendTurnResponse` are byte-identical
to today — this documents an added server-side behavior on an unchanged contract, not a new
contract.

## Added behavior

When `body.thread_id` is absent (this call is creating a brand-new thread) AND the
authenticated caller has a picked event on record (`SupabaseCalendarRepository.get_picked_event`
returns non-`None`) AND that event has a non-null `location`:

- Before `known_slots = graph.get_state(config).values` is read and before
  `conversation.reply(...)` is called, the route calls
  `graph.update_state(config, {"location": event.location})`.
- This is a **plain field copy**, not an LLM call and not an inference — the same trust level
  the route already gives a `location` value it has itself extracted from a prior user
  message.

No other field (`occasion`, `formality`, `mood`, `temp_c`) is written from the picked event by
this route. `occasion`/`formality` are never derived from `event.title` anywhere in the
backend — see `docs/design-decisions.md` §61.

## Observable consequences (no new fields, only different values in existing ones)

- `SendTurnResponse.location` on this first turn's response may now be non-null even if the
  user's own first message said nothing about location — because
  `conversation.reply`'s extraction reads `known_slots` (which now includes the seeded value)
  and the model's own structured output may echo it back, exactly as it already would for any
  other already-known slot mentioned to it.
- `SendTurnResponse.reply_text` — no contract guarantee on exact wording, but per FR-006 the
  first turn's reply must not ask the user to state a location the picked event already
  supplied. This is verified by asserting the conversational prompt's "already known" line
  (`conversation._known_slots_line`) contains `location` before the LLM call is made — a
  deterministic, code-level guarantee — rather than by asserting anything about the model's
  free-text output.
- A later `POST /recommend/messages` first invoke on the same thread already reads
  `known_state.get("location")` (existing code, unchanged) — so this seed is sufficient for
  FR-007 (Start Styling uses the location) with zero change to `recommend.py`'s
  `send_message` function.

## Non-goals

- No new endpoint, no new query/body parameter for "which event to seed from" — the picked
  event is always read from the caller's own single-row `picked_events` record, the same
  source `GET /calendar/picked-event` already reads.
- No change to `context_assembler.assemble_context`'s signature — it already accepts
  `location` and already calls `get_weather` when one is present (verified in
  `research.md`/the issue itself); this contract only ensures a value reaches it via the
  existing `state.get("location")` path.
