# Contract: Styling chat routes

Both routes are auth'd via feature 003's dependencies (`get_current_user_id`,
`get_current_access_token`), same pattern as `closet.py`/`calendar.py`. `thread_id` and
`message` are never trusted to carry identity — `user_id` always comes from the verified JWT.

## `GET /api/v1/recommend/readiness`

### Request

```
GET /api/v1/recommend/readiness
Authorization: Bearer <supabase-access-token>
```

### Responses

**200**

```json
{ "ready": false, "sparse": false, "missing": ["a pair of shoes"] }
```

```json
{ "ready": true, "sparse": true, "missing": [] }
```

Algorithm: `data-model.md` "Readiness algorithm". No pipeline/LLM call — pure computation over
`repository.list_wardrobe_items(user_id)`.

**401** — missing/invalid/expired token, same shape as `whoami.md`'s contract.

## `POST /api/v1/recommend/messages`

### Request

```
POST /api/v1/recommend/messages
Authorization: Bearer <supabase-access-token>
Content-Type: application/json

{ "message": "business casual for a rainy commute", "thread_id": null }
```

A refinement in the same conversation:

```json
{ "message": "something warmer", "thread_id": "3fa6...e21" }
```

### Responses

**200 — outfit produced**

```json
{
  "thread_id": "3fa6...e21",
  "reply_text": null,
  "outfit": {
    "rationale_text": "A tailored blazer over a crisp shirt keeps this business casual [1], while the water-resistant trench and low block heel handle the rain without sacrificing polish [2].",
    "items": [
      { "id": "...", "name": "Navy blazer", "category": "blazer", "category_group": "outerwear",
        "colors": ["#1b2a4a"], "color_names": ["Navy"], "photo_url": "https://...", "...": "ClosetItemView fields" }
    ],
    "match_label": "great"
  },
  "citations": [
    { "number": 1, "text": "Structured outerwear signals business casual without full formalwear." },
    { "number": 2, "text": "Water-resistant outerwear and low, stable heels are the two rain-commute adjustments that don't read as casual." }
  ]
}
```

**200 — no viable outfit** (pipeline's own honesty path, research.md §6)

```json
{
  "thread_id": "3fa6...e21",
  "reply_text": "Your closet doesn't have enough items to assemble an outfit for this request.",
  "outfit": null,
  "citations": []
}
```

**403 — closet not ready** (server-side gate, independent of the client's own `GET /recommend/readiness` check)

```json
{ "detail": "Your closet isn't ready for a styling request yet." }
```

Returned instead of invoking the pipeline at all whenever the readiness algorithm's `ready` is
`false` for the caller, even if the request never consulted `GET /recommend/readiness` first —
FR-007.

**422** — empty/missing `message`.

**504 — backstop timeout** (research.md §3)

```json
{ "detail": "That took too long. Try again." }
```

Raised when the graph invocation exceeds `wtw_styling_request_timeout_seconds` (120s default).
Maps to `recommend.error.body`/`recommend.error.cta` client-side, same as any other failure —
the client does not distinguish a timeout from any other 5xx.

**401** — missing/invalid/expired token.

**5xx** — any other unhandled pipeline failure maps to the generic `recommend.error.*` state
client-side; nothing pipeline-internal (stack traces, node names) is ever surfaced to the user.
