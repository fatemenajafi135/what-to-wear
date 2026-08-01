# Contract: Closet write routes

Extends `specs/004-closet-read/contracts/closet.md`'s two GETs with four new routes on the same
router (`api/v1/routes/closet.py`, mounted under `/api/v1`). All four require a valid bearer
token (`get_current_user_id`, 401 if missing/invalid) and act only on the caller's own items —
a foreign or nonexistent `item_id` gets the identical 404 shape as the existing GET
(`{"detail": "Item not found"}`), never revealing which case it was.

## `PATCH /closet/items/{item_id}`

Request body — `ClosetItemEditRequest` (route-local, see `data-model.md`):

```json
{
  "name": "Navy blazer",
  "category": "outerwear",
  "fabric": "wool",
  "colors_text": "navy, charcoal",
  "notes": "Dry clean only"
}
```

Every field optional; omitted fields are unchanged (PATCH semantics, matching
`WardrobeItemPatch`'s own doc comment). `colors_text` is a comma-separated list of color
names (`colors.FASHION_COLOR_PALETTE`) or hex codes.

- `200` — the updated `ClosetItemView` (identical shape to the GET response).
- `404` — item not found or not owned by caller.
- `422` — a `colors_text` token isn't a known name or valid hex; standard FastAPI/Pydantic
  validation-error shape, naming the offending field.

## `POST /closet/items/{item_id}/favorite`

No request body. Reads the item's current `favorite` value and writes its negation in one
transaction (the client has no reliable local copy to flip and round-trip — Item detail never
displays this field, design-system §2.3).

- `200` — `{"favorite": true}` or `{"favorite": false}`, the value **after** the toggle.
- `404` — item not found or not owned by caller.

## `POST /closet/items/{item_id}/wear`

No request body. Idempotent per calendar day (`docs/design-decisions.md` §22.1) — a second call
the same day for the same item succeeds identically to the first, without creating a second
`item_wears` row.

- `204` — no body, whether this was the first log today or a repeat.
- `404` — item not found or not owned by caller.

## `DELETE /closet/items/{item_id}`

Hard delete. Cascades to the item's `item_wears` rows.

- `204` — no body.
- `404` — item not found or not owned by caller (already deleted, never existed, or belongs to
  someone else — same shape either way).

## Unchanged

`GET /closet/items` and `GET /closet/items/{item_id}` (feature 004) are untouched by this
feature except that `ClosetItemView`/`WardrobeItem` gain the additive `favorite: bool` field,
so every existing response now also includes it (defaulting `false` for pre-existing rows via
the migration's `default false`).
