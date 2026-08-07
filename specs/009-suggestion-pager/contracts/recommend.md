# Contracts — Feature 009: Outfit suggestion pager

Extends `specs/008-styling-chat/contracts` (not duplicated here where unchanged).

## `POST /api/v1/recommend/messages` (changed)

Request: unchanged (`SendMessageRequest` — `message`, optional `thread_id`).

Response (`SendMessageResponse`, changed — see data-model.md):

```jsonc
{
  "thread_id": "…",
  "reply_text": null,           // set only when outfits is empty
  "outfits": [                   // was `outfit: {...} | null` — now always a list, never null
    {
      "id": null,                 // null until saved this session
      "rationale_text": "…",      // plain text, no [n] markers
      "items": [ /* StylingReplyItem, unchanged shape */ ],
      "match_label": "great",
      "meta_line": "Rainy day commute · Business casual"
    }
  ]
  // "citations" field removed — no remaining renderer (research.md §2/§4)
}
```

- `outfits` is filtered to entries scoring ≥ 0.4 — never includes a below-floor outfit.
- `outfits: []` + `reply_text` set is the Empty case; the frontend renders the pager's Empty
  group-state, not an empty track.
- `403`/`422`/`504` behavior unchanged from 008.

## `POST /api/v1/recommend/outfits` (new)

Save a suggestion. Request (`SaveOutfitRequest`, see data-model.md): `occasion`, `meta_line`,
`rationale_text`, `match_label`, `item_ids` (non-empty).

- `201` → `SavedOutfitResponse` (`{"id": "...", "favorite": true}`) on success.
- `422` if any `item_id` does not belong to the caller's own wardrobe (validated against
  `repository.list_wardrobe_items(user_id)` before insert — Constitution IV).
- `401` if unauthenticated (existing `get_current_user_id` dependency, unchanged).

## `POST /api/v1/recommend/outfits/{outfit_id}/favorite` (new)

Toggle the saved/favorited state of one of the caller's own saved outfits (the heart's second
tap onward).

- `200` → `SavedOutfitResponse` (`{"id": "...", "favorite": false}` or `true` — the state
  *after* the toggle, same convention as `POST /closet/items/{item_id}/favorite`).
- `404` if `outfit_id` doesn't exist or doesn't belong to the caller (never distinguishes the two
  — same convention as the closet item favorite route, to avoid leaking existence of another
  user's row).
- `401` if unauthenticated.

## Frontend consumption

`apiClient` (existing `openapi-fetch` wrapper) gains no new setup — the two new routes and the
changed response shape are picked up automatically once `schema.d.ts` is regenerated
(`npm run generate:api-types`, backend running — handoff trap #6).
