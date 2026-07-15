# Contract: `POST /wardrobe/items/extract`

New endpoint. Draft extraction only — nothing is persisted to `wardrobe_items`
by this call.

## Auth

Required. Same `get_current_user_id` JWT dependency as every other
`/wardrobe/*` endpoint. 401 without a valid bearer token.

## Request

`multipart/form-data`

| Field | Type | Required |
|---|---|---|
| `photo` | file (image/jpeg, image/png, image/webp) | yes |

## Response — `200 OK`

```json
{
  "photo_path": "3f9c.../a1b2-shirt.jpg",
  "extracted": {
    "category": "top",
    "colors": ["#1b2a4a"],
    "fabric": "cotton",
    "warmth": 2,
    "formality": "smart_casual",
    "season": ["spring", "autumn"],
    "pattern": "solid",
    "fit": "regular"
  },
  "extraction_ok": true
}
```

On extraction failure (blurry photo, no garment visible, VLM error): still
`200 OK`, `extraction_ok: false`, `extracted` fields mostly/entirely `null` —
**never** a 5xx for a bad-but-successfully-uploaded photo (FR-006, spec Edge
Cases). The photo is still uploaded to Storage and `photo_path` is still
returned, so the user can proceed to manual entry without re-uploading.

## Response — `4xx`

| Status | Condition |
|---|---|
| 401 | missing/invalid bearer token |
| 422 | missing `photo` field, or file isn't a supported image type |

A genuine upload failure (Storage unreachable) is the one case that legitimately
5xx's — distinct from an extraction failure, which is always a 200.
