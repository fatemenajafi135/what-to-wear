# Data Model: Conversational styling turns

No new table. One migration widening an existing constraint, one new column's worth of response
shape, and one durable-but-unmigrated state location (the pipeline's own checkpointer). See
`research.md` §1–13 and `docs/design-decisions.md` §47–§50 for the reasoning behind each choice below.

## `messages.kind` — two new values

`infra/supabase/migrations/0012_conversational_turns.sql` widens the check constraint 011 already
anticipated:

| `kind` | Written by | `role` (derived, §44) | `text` | `outfit_ids` |
|---|---|---|---|---|
| `user_message` (existing) | `POST /recommend/turns` only, from this slice on (§50 — `POST /recommend/messages` no longer writes it) | user | the user's verbatim message | `{}` |
| `styling_reply` (existing) | `POST /recommend/messages`, unchanged | assistant | pipeline reply/honesty-fallback text, or `''` when outfits were produced | linked outfit ids |
| `conversational_turn` (new) | `POST /recommend/turns` | assistant | the reply text (LLM-generated, or the fixed turn-cap/call-failed copy from `copy.py`) | `{}` |
| `wrap_up` (new) | `POST /recommend/messages`, one new insert alongside the existing `styling_reply` insert | assistant | the Python-templated wrap-up sentence (`copy.py`) | `{}` |

No other column changes on `messages`; no change to `sessions` or `outfits`.

## Accumulated slots — not a table row

Lives in the pipeline's own LangGraph checkpoint for the thread's `thread_id` (`docs/design-decisions.md`
§47), under the exact `GraphState` field names:

| Key | Type | Written by |
|---|---|---|
| `occasion` | `str \| None` | `POST /recommend/turns`, via `update_state` |
| `mood` | `str \| None` | same |
| `formality` | `Formality \| None` (validated against the six-value enum; an unrecognized string from the LLM is dropped to `None`, never passed through) | same |
| `location` | `str \| None` | same |
| `temp_c` | `float \| None` | same |

Read by:
- `POST /recommend/turns` itself, at the top of every call, to give the extraction prompt what's
  already known (so it doesn't re-ask).
- `POST /recommend/messages`, once, on a thread's first real invoke only (§49) — never read again on
  that thread afterward.

Never migrated, never backfilled — a thread created before this slice ships simply has an empty
checkpoint for these keys, which composes exactly like "nothing was ever said," the documented fallback
behavior.

## `SendMessageResponse` — one new field

```
{
  thread_id: string
  reply_text: string | null   # unchanged
  wrap_up_text: string        # NEW — always present when outfits or a reply exist; the templated
                               #   "Styling for {occasion}, {formality}." sentence (copy.py)
  outfits: StylingOutfit[]    # unchanged
}
```

## New response: `POST /recommend/turns`

```
{
  thread_id: string            # echoes the request, or the newly minted id on a fresh thread
  reply_text: string           # always present — the in-voice reply, or the fixed
                                #   turn-cap/call-failed copy
  occasion: string | null
  formality: string | null     # one of the six Formality values, or null
  mood: string | null
  temp_c: number | null
  location: string | null
}
```

`occasion`/`formality`/`mood`/`temp_c`/`location` here are this **turn's own extraction only** (what
changed this call), not the full accumulated set — the accumulated set lives server-side in the
checkpoint (above) and is never round-tripped to the client, since nothing in this slice's UI needs to
display "everything gathered so far" as its own affordance (the wrap-up, shown once at Start-styling
time, is that surface).

## `Settings`

One new field, `backend/src/whattowear/core/config.py`, beside `wtw_wardrobe_min_items`:

```python
wtw_conversation_turn_cap: int = 6
```

## `copy.py` (new module)

```python
# Every string here is DRAFT (docs/handoffs/016-conversational-turns.md §3) — the design owner has
# not yet supplied final copy. Swap in place when it arrives; nothing else in this slice changes.

TURN_CAP_REACHED = "Let's put this to work — tap Start styling and I'll pull some looks together."
CALL_FAILED = "I didn't catch that — try again, or tap Start styling with what we have."

def wrap_up_text(occasion: str, formality: str | None) -> str:
    if formality:
        return f"Styling for {occasion}, {formality}."
    return f"Styling for {occasion}."
```

(Final field names/signatures are implementation detail, not re-litigated here — this shows the shape
`tasks.md` builds against.)
