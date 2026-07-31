# Contract: Closet read routes

## `GET /api/v1/closet/items`

### Request

```
GET /api/v1/closet/items?category=top&offset=0
Authorization: Bearer <supabase-access-token>
```

Query parameters (both optional):
- `category` — one of `top`, `bottom`, `outerwear`, `footwear`, `accessory` (the taxonomy's
  `category_group` values; `bottom` includes `full_body` items per
  `research.md` §3/spec clarification). Omitted or absent → no filter (`All`).
- `offset` — pagination offset, default `0`. Page size is fixed at `WTW_CLOSET_PAGE_SIZE`
  (20), not client-controlled.

### Responses

**200**

```json
{
  "items": [ { "id": "...", "category": "top", "colors": ["#1b2a4a"], "formality": "casual",
               "warmth": 1, "season": ["spring"], "fabric": null, "source": "upload",
               "pattern": null, "fit": null, "photo_path": null,
               "name": "Navy tee", "notes": null,
               "category_group": "top", "color_names": ["Navy"] } ],
  "total": 37,
  "has_more": true
}
```

`category_group` and `color_names` are computed at response time (`ClosetItemView` in
`data-model.md`) — never stored, never re-derived on the frontend.

`items` is exactly the caller's own `wardrobe_items` rows (never another user's, never
`catalog_items`), category-filtered then sliced to one page. `total` is the count matching
the current filter before slicing — the header subtitle's "N items" text and the
empty-vs-empty-filtered distinction both read from it (`total == 0` with no filter →
first-run empty; `total == 0` with a filter active → empty-filtered).

**401** — missing/invalid/expired token, same shape as `whoami.md`'s contract.

## `GET /api/v1/closet/items/{item_id}`

### Request

```
GET /api/v1/closet/items/f7b3.../
Authorization: Bearer <supabase-access-token>
```

### Responses

**200** — a bare `WardrobeItem`, only when `item_id` belongs to the caller.

**404** — `item_id` does not exist, or exists but belongs to a different user. Both cases
return the identical `{"detail": "Item not found"}` — the route never reveals whether an id
merely belongs to someone else, matching the same non-disclosure shape `auth.py` already
uses for missing vs. invalid tokens.

**401** — missing/invalid/expired token.

## Behavioral guarantees

- Both routes depend on `get_current_user_id` (feature 003); `user_id` never comes from a
  request body or query parameter.
- Ownership is enforced twice, independently: the SQL `WHERE user_id = :caller_id` (query
  level, the actual guarantee for this backend's own traffic — see `research.md` §1) and the
  RLS policy on `wardrobe_items` (the convention every later table copies, proven independent
  of this backend's connection — see `research.md` §2).
- Neither route touches `catalog_items` — `list_catalog_items()` exists on the repository for
  the AI pipeline's consumption (per `ports.ClosetRepository`), not for these HTTP routes;
  this feature adds no catalog-browsing screen (design system has none for this feature).
- Response models are Pydantic (`WardrobeItem`, plus a route-local `ClosetItemsResponse`
  wrapper); the frontend consumes both only through `openapi-typescript`-generated types
  (`frontend/lib/api/schema.d.ts`), per Constitution VII — no hand-written duplicate.
