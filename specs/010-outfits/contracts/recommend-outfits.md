# Contracts — Feature 010: Outfits gallery + detail

Extends `specs/009-suggestion-pager/contracts/recommend.md` (not duplicated here where unchanged).
All routes below live on the existing `recommend.py` router.

## `POST /api/v1/recommend/outfits` (changed)

Request (`SaveOutfitRequest`) gains a required field:

```jsonc
{
  "occasion": "…",
  "meta_line": "…",
  "rationale_text": "…",
  "match_label": "great",
  "item_ids": ["…"],
  "thread_id": "…"        // NEW, required — see data-model.md / design-decisions.md §38
}
```

- Behavior unchanged otherwise (owned-items check, `201` → `SavedOutfitResponse`).
- Internally, the route now also: reads `get_compiled_graph(repo).get_state(...)` for
  `thread_id`, verifies `state["user_id"] == user_id`, finds the `ScoredOutfit` in
  `last_result.outfits` whose `.items` exactly equals `item_ids`, and — if found — derives
  `title` (seeded from `occasion`, §36), `rationale_with_citations`, `citations`, and
  `dimension_scores` from it before insert. No match (or no state) → those four columns get
  their empty/seeded defaults; the save still succeeds (`201`).

## `GET /api/v1/recommend/outfits` (new)

List the caller's saved outfits — the gallery.

Query params: `sort` = `date` (default) | `favorite` | `most_worn`.

- `200` → `OutfitSummaryListResponse`:

```jsonc
{
  "outfits": [
    {
      "id": "…",
      "title": "…",
      "match_label": "great",
      "favorite": true,
      "created_at": "2026-08-01T12:00:00Z",
      "item_thumbnails": [ /* up to 4 RecommendItemView-shaped entries */ ],
      "item_count": 5              // lets the client render "+2" in the 4th slot when > 4
    }
  ]
}
```

- Always `200`, `outfits: []` for the true empty case (no separate empty response shape — the
  frontend distinguishes "empty" from "loaded" by list length, matching 009's `outfits[]`
  convention for the pager).
- `401` if unauthenticated.

## `GET /api/v1/recommend/outfits/{outfit_id}` (new)

One saved outfit's full detail.

- `200` → `OutfitDetailResponse`:

```jsonc
{
  "id": "…",
  "title": "…",
  "occasion": "…",
  "items": [ /* full RecommendItemView list, re-resolved live from wardrobe_items */ ],
  "rationale_text": "…",
  "rationale_with_citations": "…",      // "" if none captured (§38 degrade path)
  "citations": [ {"number": 1, "text": "…"} ],   // [] if none
  "dimension_scores": [ {"dimension": "color_harmony", "value": 0.82} ],  // [] if none
  "match_label": "great",
  "favorite": true,
  "created_at": "2026-08-01T12:00:00Z"
}
```

- `404` if `outfit_id` doesn't exist or doesn't belong to the caller (never distinguished —
  existing convention).
- `401` if unauthenticated.
- An item id in `item_ids` no longer present in the caller's `wardrobe_items` is simply omitted
  from `items` (Constitution IV — never a stale/broken reference).

## `PATCH /api/v1/recommend/outfits/{outfit_id}/title` (new)

Rename. Request: `{"title": "…"}`.

- `200` → `SavedOutfitResponse`-shaped `{"id": "…", "title": "…"}` (the new title, echoed).
- `422` if `title` is empty or whitespace-only after `.strip()`.
- `404` if not found/not owned.
- `401` if unauthenticated.

## `POST /api/v1/recommend/outfits/{outfit_id}/wear` (new)

Log the outfit — and every item still owned by the caller — as worn today (design-decisions.md
§39).

- `204` on success (no body — matches `POST /closet/items/{item_id}/wear`'s existing convention).
- Idempotent: a second call the same calendar day is a no-op success, not an error.
- `404` if not found/not owned.
- `401` if unauthenticated.

## `DELETE /api/v1/recommend/outfits/{outfit_id}` (new)

Permanently delete a saved outfit (and its `outfit_wears` rows, via `on delete cascade`).
Confirmation is a client-side UI gate (design-decisions.md §40) — this route performs the delete
unconditionally once called, matching `DELETE /closet/items/{item_id}`'s own shape exactly.

- `204` on success.
- `404` if not found/not owned.
- `401` if unauthenticated.

## `POST /api/v1/recommend/outfits/{outfit_id}/favorite` (unchanged)

Behavior unchanged from 009 — listed here only because Outfit detail and its overflow sheet are
new callers of this existing route (data-model.md's Favorite state-transition section).

## Frontend consumption

`schema.d.ts` is regenerated (`npm run generate:api-types`, backend running) once these routes
land — there is currently no list/detail/rename/wear/delete shape in the generated schema at all
for outfits. `SuggestionPager.tsx`'s save call additionally needs `threadId` threaded down from
`RecommendChat.tsx` → `ChatMessageList.tsx` → `SuggestionPager.tsx` (a new prop at each layer,
no new state — `RecommendChat` already holds `threadId`).
