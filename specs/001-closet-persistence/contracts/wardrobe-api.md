# API Contract: Wardrobe & Catalog

Per constitution Principle VII, Pydantic models in `schema.py` /
`api.py` are the single source of truth for these contracts — FastAPI
generates the real OpenAPI document from that code at runtime. This file
describes intended shape and behavior for planning; it is not a
hand-maintained duplicate spec to keep in sync by hand.

All endpoints below require a valid Supabase JWT (`Authorization: Bearer
<token>`), verified by the `auth.py` dependency. There is no anonymous
access.

## `GET /wardrobe/items`

Returns every wardrobe item belonging to the requesting user (derived from the
JWT), newest first. Empty wardrobe → `200` with an empty list, not an error
(spec US1 acceptance scenario 2).

**Response**: list of `WardrobeItem` (id, category, colors, fabric, warmth,
formality, season, source, catalog_item_id, created_at, updated_at)

## `POST /wardrobe/items`

Adds an item to the requesting user's wardrobe by referencing a catalog item.

**Request**: `{ "catalog_item_id": "<uuid>" }`

**Response**: `201` with the newly created `WardrobeItem` — a full independent
copy of the catalog item's attributes (FR-011), not a reference. `source` is
always `"catalog"` in this feature (photo upload is out of scope, FR-003).

**Errors**: `404` if `catalog_item_id` doesn't exist in the catalog.

## `PATCH /wardrobe/items/{id}`

Corrects one or more attributes of an item already in the requesting user's
wardrobe.

**Request**: partial `WardrobeItem` body — only fields to change.

**Response**: `200` with the updated `WardrobeItem`.

**Validation** (FR-007): an invalid value for any constrained field →
`422`, with the item's prior value left unchanged — `formality`/`season`
outside the controlled vocabulary, `warmth` outside 0-5, or a malformed hex
`colors` entry. `category` accepts any value (open-ended) — its slot/bucket
is re-derived automatically, never itself an input field.

**Errors**: `404` if `id` doesn't belong to the requesting user (not found,
not forbidden — spec Edge Cases).

## `DELETE /wardrobe/items/{id}`

Removes an item from the requesting user's wardrobe. Hard delete.

**Response**: `204`.

**Errors**: `404` if `id` doesn't belong to the requesting user, or was
already removed (idempotent from the caller's point of view — spec Edge
Cases: a second delete is "already gone," not a crash).

## `GET /catalog/items`

Returns the shared catalog. Same `WardrobeItem` shape, with `user_id`,
`source`, and `catalog_item_id` absent (catalog entries have no owner).

**Response**: list of `WardrobeItem` (catalog entries). Empty catalog → `200`
with an empty list (spec Edge Cases).

No `POST`/`PATCH`/`DELETE` on `/catalog/items` in this feature — the catalog
is seeded once from `data/fixtures/wardrobe.json` and is not user-editable
(FR-010).
