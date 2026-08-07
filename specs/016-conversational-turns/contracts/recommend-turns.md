# Contracts — Feature 016: Conversational styling turns

Both routes below live on the existing `recommend.py` router (same convention 011's own contracts
file names: extend, don't add a second router). See `research.md` and `docs/design-decisions.md`
§47–§50 for the reasoning behind every "why" in this file.

## `POST /api/v1/recommend/turns` (new)

Request:

```jsonc
{ "message": "something for a wedding, mid-October", "thread_id": null }
```

`thread_id` is `null` on the first turn of a new conversation, otherwise the id the previous call
(to this route or, on a continuing thread, `/recommend/messages`) returned.

Behavior:

1. `thread_id = body.thread_id or str(uuid.uuid4())` (same minting as `send_message`).
2. `session_repository.upsert_session(user_id, thread_id)` — written-on-start (§44), unchanged
   idempotent upsert.
3. `session_repository.insert_message(user_id, thread_id, "user_message", body.message)` — this
   route is now the **only** writer of `user_message` rows (§50).
4. `turn_number = session_repository.count_user_messages(user_id, thread_id)` (includes the row
   just inserted).
5. If `turn_number > settings.wtw_conversation_turn_cap`: skip the LLM entirely.
   `reply_text = copy.TURN_CAP_REACHED`; no slot updates.
6. Else: read `graph.get_state(config).values` for already-known slots, call
   `conversation.reply(message=body.message, known_slots=...)` (new `conversation.py`, §47/
   research.md §2). On a genuine LLM-call failure, catch it and fall back to
   `reply_text = copy.CALL_FAILED` with no slot updates — never a 5xx for this (mirrors
   `vision.py`'s `extraction_ok=False` philosophy).
7. `graph.update_state(config, {k: v for k, v in extracted.items() if v is not None})` — merge
   new slots (§47), skipped when step 5 short-circuited.
8. `session_repository.insert_message(user_id, thread_id, "conversational_turn", reply_text)`.
9. Return.

Response:

```jsonc
{
  "thread_id": "…",
  "reply_text": "Got it — mid-October, so probably cool. Is it a smart place, or more relaxed?",
  "occasion": "wedding",
  "formality": null,
  "mood": null,
  "temp_c": null,
  "location": null
}
```

`occasion`/`formality`/`mood`/`temp_c`/`location` are **this turn's own extraction**, not the
accumulated set (data-model.md) — `null` for every field the model didn't newly extract this call,
which is the normal case for most turns after the first.

Errors: `422` if `message` is empty/whitespace-only (mirrors `send_message`'s own check). No
readiness gate (research.md §1) — this route never loads wardrobe.

## `POST /api/v1/recommend/messages` (changed)

Request/response shape is **additive only** — `SendMessageRequest` unchanged;
`SendMessageResponse` gains `wrap_up_text: string`.

What changes server-side:

1. **No longer inserts a `user_message` row** (§50) — that insert is deleted from this handler.
2. Before building the `graph.invoke(...)` input: read
   `graph.get_state(config).values.get("original_context")`.
   - `None` (first real invoke on this thread): compose the invoke input from accumulated slots
     (§47/§49) — `occasion` = the `occasion` slot or `body.message` as fallback; `mood`/
     `formality`/`location`/`temp_c` included only when the corresponding slot is non-`None`.
   - not `None` (a refinement invoke): invoke input is exactly what 008 always sent —
     `{"occasion": body.message, "thread_id", "user_id", "approach": "grounded"}`. No slots
     consulted.
3. Everything from `graph.invoke(...)` onward — outfit resolution, persistence, `styling_reply`
   insert — **is unchanged** (pipeline/scoring/retrieval untouched, per the constitution).
4. One new insert, always, right after the existing `styling_reply` insert:
   `session_repository.insert_message(user_id, thread_id, "wrap_up", copy.wrap_up_text(result.context.occasion, result.context.formality))`.
5. Response gains `wrap_up_text` = the same string just inserted.

No change to `thread_id` minting, no change to pipeline/scoring/retrieval invocation, no change to
how outfits are resolved or persisted.

## `SupabaseSessionRepository` — one new method

```python
def count_user_messages(self, user_id: str, thread_id: str) -> int: ...
```

`SELECT COUNT(*) FROM messages WHERE session_id = :thread_id AND user_id = :user_id AND kind =
'user_message'` — used by both the turn-cap check (route 1, step 4) and nowhere else. No change to
any existing method.
