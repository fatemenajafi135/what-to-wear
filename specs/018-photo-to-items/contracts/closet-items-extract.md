# Contract: `POST /api/v1/closet/items/extract` (revised)

**Supersedes** the response shape documented in
`specs/006-photo-upload-vision/contracts/wardrobe-items-extract.md` — amended forward, that file
is left as written for its own history. Everything in that contract not called out below
(auth, request shape, upload-size/type validation, the genuine-Storage-failure 5xx) is unchanged
and not repeated here.

Same route, same method, same auth. This is an extension of the existing contract (spec.md's own
framing), not a new endpoint.

## Auth

Unchanged: `get_current_user_id` + `get_current_access_token`.

## Request

Unchanged: `multipart/form-data`, one `photo` field, same size/type validation, same `422`s.

## Response — `200 OK` (changed)

```json
{
  "drafts": [
    {
      "photo_path": "3f9c.../a1b2-flatlay.jpg",
      "region": { "x": 0.02, "y": 0.05, "width": 0.44, "height": 0.60 },
      "extracted": {
        "category": "t-shirt",
        "colors": ["#1b2a4a"],
        "fabric": "cotton",
        "warmth": 1,
        "formality": "casual",
        "season": ["spring", "summer"],
        "pattern": "solid",
        "fit": "regular",
        "background_color": "#f2f0ec"
      },
      "extraction_ok": true,
      "color_names": ["navy"],
      "isolated_photo_path": "3f9c.../c7e1-isolated-flatlay.jpg",
      "isolated_photo_url": "https://.../object/sign/wardrobe-photos/3f9c.../c7e1-isolated-flatlay.jpg?token=..."
    }
  ],
  "truncated": false
}
```

Always a list, even for a photo containing exactly one garment — that case returns
`drafts` with exactly one element, identical in every field to what the single-object response
used to return, so a caller reading `drafts[0]` sees today's exact shape (FR-004).

- `region` — fractions (0–1) of the *original* photo's width/height, `{0,0,1,1}` for the
  whole-photo fallback cases below. Lets the frontend crop the original locally before an
  isolated image exists (data-model.md §5).
- `isolated_photo_path`/`isolated_photo_url` — both `null` when isolation hasn't produced a
  usable image for this detection yet or ever (FR-013). Never absent from the object; always
  present, possibly null, so clients don't need an `in` check.
- `truncated` — `true` when more garments were detected than `wtw_max_detections_per_photo`
  (default 8) kept. The 8 kept are the most confidently/prominently detected (FR-002).

### Fallback cases (unchanged in spirit from before this feature, FR-003)

| Condition | `drafts` |
|---|---|
| Detection call raises (network/gateway error) | one element, `extraction_ok: false`, all `extracted` fields null, `region: {0,0,1,1}`, `isolated_photo_path: null` |
| Detection call succeeds, zero garments confidently found | one element, `extraction_ok: true`, all `extracted` fields null, `region: {0,0,1,1}` |
| Detection call succeeds, 1–8 garments found | one element per garment |
| Detection call succeeds, >8 garments found | 8 elements (highest-confidence), `truncated: true` |

Never zero elements for a photo that uploaded successfully — the photo upload itself (and its
distinct 5xx-on-genuine-failure case) is unaffected by any of the above; it always runs first
and is orthogonal to what detection finds.

## Response — `4xx`/`5xx`

Unchanged from the 006 contract: `401` missing/invalid bearer token; `422` missing/unsupported/
oversized photo; `5xx` only a genuine Storage upload failure.
