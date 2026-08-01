# Contract: `POST /api/v1/closet/items/extract`

New endpoint on the existing `closet.py` router. Draft extraction only — nothing is persisted
to `wardrobe_items` by this call. Adapted from the legacy contract at
`../app-legacy/specs/003-mvp-app/contracts/wardrobe-items-extract.md` (handoff §5.2: "read it,
and treat its status table as a starting point rather than a spec to copy") — the status table
below is unchanged from it; the size limit and Storage-shape details are new to this port.

## Auth

Required. `get_current_user_id` (for ownership) **and** `get_current_access_token` (research.md
§1 — Storage calls use the caller's own bearer token, never a service-role key). 401 without a
valid bearer token.

## Request

`multipart/form-data`

| Field | Type | Required |
|---|---|---|
| `photo` | file (`image/jpeg`, `image/png`, `image/webp`) | yes |

Rejected before upload or extraction is attempted:
- No `photo` field, or a file whose content type isn't one of the three above → `422`.
- File larger than `Settings.wtw_max_upload_bytes` (10 MiB default, research.md §3) → `422`.

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

On extraction failure (blurry photo, no garment visible, VLM error): still `200 OK`,
`extraction_ok: false`, `extracted` fields mostly/entirely `null` — **never** a 5xx for a
bad-but-successfully-uploaded photo (spec.md FR-003/FR-004). The photo is still uploaded to
Storage and `photo_path` is still returned, so the user can proceed to manual entry (spec.md
FR-016, the same review card, blank) without re-uploading.

A category the VLM returns outside the frozen taxonomy (handoff trap 7) is not corrected or
widened here — it's returned as-is in `extracted.category`; the review card shows it as free
text the user can fix like any other scanned value, and `categories.group_of` already defaults
an unrecognized category to `"accessory"` on any later read.

## Response — `4xx`/`5xx`

| Status | Condition |
|---|---|
| 401 | missing/invalid bearer token |
| 422 | missing `photo` field, unsupported image type, or file exceeds the size limit |
| 5xx | genuine Storage upload failure (Storage unreachable) — the one case that legitimately errors, distinct from an extraction failure, which is always a 200 |
