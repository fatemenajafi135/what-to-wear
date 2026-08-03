# Contracts — Feature 011: Chat history

Extends `specs/010-outfits/contracts/recommend-outfits.md` (not duplicated here where unchanged).
All routes below live on the existing `recommend.py` router (handoff §4.1: extend, don't add a
second router).

## `POST /api/v1/recommend/messages` (changed — persistence, no request/response shape change)

Request/response bodies are unchanged (`SendMessageRequest` in, `SendMessageResponse` out).
What changes is what happens server-side, all inside the same request/transaction that already
persists each surfaced outfit (§42):

1. Before invoking the pipeline: upsert a `sessions` row for `thread_id` —
   `INSERT INTO sessions (id, user_id) VALUES (:thread_id, :user_id) ON CONFLICT (id) DO UPDATE
   SET updated_at = now()`. Runs on every call, not only the first — first call creates it,
   every later call bumps `updated_at` (data-model.md).
2. Insert a `messages` row, `kind='user_message'`, `text=body.message`.
3. After the pipeline returns and outfits are resolved/persisted (unchanged §42 logic), each
   created `outfits.id` gets `thread_id` set to this request's `thread_id` (data-model.md,
   §45) — one extra column value on the same `INSERT` `SupabaseOutfitRepository.create` already
   issues, not a second write.
4. Insert one `messages` row, `kind='styling_reply'`: `outfit_ids` = the ids from step 3 (empty
   array if none), `text` = `reply_text` when step 3 produced no outfits, else `''`
   (data-model.md).

No change to the response the client sees, no change to `thread_id` minting (§25), no change to
pipeline/scoring/retrieval invocation.

## `GET /api/v1/recommend/sessions` (new)

List the caller's sessions — Chat history's own list, most recently active first.

- `200` → `SessionSummaryListResponse`:

```jsonc
{
  "sessions": [
    {
      "id": "…",                  // == thread_id
      "preview": "…",              // first user message, truncated
      "message_count": 4,          // total turns, both roles
      "outfit_count": 2,           // 0 when no outfits, per §45 — see below
      "updated_at": "2026-08-03T12:00:00Z"
    }
  ]
}
```

- `outfit_count` is present and `>= 0` always; the frontend renders the third preview line only
  when it is `> 0` (design-system.md § Chat history row anatomy — "only if the session produced
  outfits").
- No pagination (research.md §7). No filter/sort query param — always most-recently-active-first.
- Empty list (no sessions yet) is a normal `200`, `sessions: []` — matches every other list
  route's own empty-is-still-200 convention (`recommend-outfits.md`'s own `GET /recommend/
  outfits`).

## `GET /api/v1/recommend/sessions/{sessionId}` (new)

Session detail — the full read-only transcript plus enough to render "Continue conversation" /
"View in Outfits."

- `404` if `sessionId` doesn't parse as a uuid, or doesn't belong to the caller (same
  indistinguishable-404 convention `get_outfit`/`_parse_outfit_id` already use).
- `200` → `SessionDetailResponse`:

```jsonc
{
  "id": "…",                     // == thread_id, what "Continue conversation" resumes with
  "updated_at": "2026-08-03T12:00:00Z",
  "outfit_count": 2,
  "messages": [
    {
      "id": "…",
      "kind": "user_message",
      "role": "user",             // derived server-side from kind (research.md §4); frontend never re-derives it
      "text": "Something for a rainy client dinner",
      "outfits": []
    },
    {
      "id": "…",
      "kind": "styling_reply",
      "role": "assistant",
      "text": "",
      "outfits": [
        {
          "id": "…",
          "title": "…",
          "rationale_with_citations": "A cohesive, weather-ready look. [1]",
          "citations": [ { "number": 1, "text": "…" } ]
          // deliberately no `items`/thumbnails and no rule-list-only fields here beyond
          // `citations` itself — §46: archived view renders citation badges from this text,
          // never the item-thumbnail grid or a separate rule list.
        }
      ]
    }
  ]
}
```

- A `styling_reply` message with `outfits: []` (the turn produced nothing surfaceable) means the
  frontend renders `text` as a plain assistant bubble, no citation badge (§46).
- `outfit_count` here is the same live-computed value as the list route's own field, so Session
  detail never has to re-derive or contradict what the list row already showed.

## Frontend "Continue conversation"

No new endpoint. Session detail already has `id` (== `thread_id`); "Continue conversation"
navigates to `/recommend?thread_id={id}`, and `RecommendChat` (extended to accept an initial
`thread_id` + hydrated `messages` from the session-detail fetch) sends its next
`POST /recommend/messages` with that same `thread_id` in the request body — verified by
inspecting the outgoing request, per the handoff's own verification instruction, not by reading
the reply.
