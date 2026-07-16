# Contract: `POST /wardrobe/items/upload`

New endpoint. Persists a wardrobe item from user-confirmed (possibly
corrected) attributes. Parallel to, not replacing, the existing catalog-based
`POST /wardrobe/items` (which takes a `catalog_item_id`, not raw attributes).

## Auth

Required. Same `get_current_user_id` JWT dependency as every other
`/wardrobe/*` endpoint. 401 without a valid bearer token.

## Request — `application/json`

```json
{
  "photo_path": "3f9c.../a1b2-shirt.jpg",
  "category": "top",
  "colors": ["#1b2a4a"],
  "formality": "smart_casual",
  "warmth": 2,
  "season": ["spring", "autumn"],
  "fabric": "cotton",
  "pattern": "solid",
  "fit": "regular"
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `photo_path` | str | yes | from the prior `/extract` response |
| `category` | str | yes | one of the 6 frozen category groups |
| `colors` | list[str] | yes | hex, at least one |
| `formality` | Formality | yes | 6-value frozen enum |
| `warmth` | int | yes | 0–5 |
| `season` | list[Season] | yes | at least one |
| `fabric` | str | **yes** | free-text — required on this endpoint (SC-003) |
| `pattern` | str | **yes** | free-text — required on this endpoint (SC-003) |
| `fit` | str | **yes** | free-text — required on this endpoint (SC-003) |

422 if any required field is missing/invalid (same validators as
`WardrobeItem`/`WardrobeItemPatch`) — matches SC-003 ("100% of saved items
have every required attribute populated"). `fabric`/`pattern`/`fit` are
required **here only**: the frontend's review form (FR-005/FR-006) must have
the user fill any field extraction left blank before this call is made,
since the endpoint itself now rejects a blank value with a 422. Correcting
an already-saved item still goes through `PATCH /wardrobe/items/{id}`, where
all three stay optional (partial-update semantics, unchanged).

## Response — `201 Created`

Returns the saved `WardrobeItem` (same shape `GET /wardrobe/items` already
returns), with `source: "upload"`.

```json
{
  "id": "9f1e2d3c-...",
  "category": "top",
  "colors": ["#1b2a4a"],
  "formality": "smart_casual",
  "warmth": 2,
  "season": ["spring", "autumn"],
  "fabric": "cotton",
  "source": "upload",
  "pattern": "solid",
  "fit": "regular"
}
```

## Response — `4xx`

| Status | Condition |
|---|---|
| 401 | missing/invalid bearer token |
| 422 | validation failure on a required field |

Correcting a saved item afterward uses the existing, unchanged
`PATCH /wardrobe/items/{id}` — not this endpoint.
