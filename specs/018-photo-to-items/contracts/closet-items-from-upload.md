# Contract: `POST /api/v1/closet/items/from-upload` (revised)

**Supersedes** the field list in
`specs/006-photo-upload-vision/contracts/wardrobe-items-create-from-upload.md` — amended forward,
that file is left as written for its own history. Auth, response shape (`201` → `ClosetItemView`),
and every `4xx` condition not called out below are unchanged.

## Request (changed — one field added)

`application/json` — `CreateWardrobeItemFromUploadRequest` (data-model.md §2):

```json
{
  "photo_path": "3f9c.../a1b2-flatlay.jpg",
  "isolated_photo_path": "3f9c.../c7e1-isolated-flatlay.jpg",
  "category": "t-shirt",
  "colors": ["#1b2a4a"],
  "formality": "casual",
  "warmth": 1,
  "season": ["spring", "summer"],
  "fabric": "cotton",
  "pattern": "solid",
  "fit": "regular",
  "name": null,
  "notes": null,
  "photo_background_color": "#f2f0ec"
}
```

`isolated_photo_path` is optional and nullable — `null` when the draft being saved never got a
usable isolated image (isolation failed, timed out, or the strategy simply produced nothing
usable for this detection). The extract response's own `drafts[i].isolated_photo_path` is passed
straight through unmodified; this route does not re-attempt isolation, re-validate the path
against Storage, or otherwise touch it beyond persisting it — same trust level `photo_path`
already gets (spec.md FR-013: isolation failure never blocks or is retried at save time).

## Response — `201 Created` (changed — one field added to the existing shape)

`ClosetItemView`, now including `isolated_photo_url` (signed, `null` when the item has no
isolated image) alongside the existing `photo_url` (data-model.md §2).

## Response — `4xx`

Unchanged: `401` missing/invalid bearer token; `422` missing/empty `category`/`colors`, or an
unresolvable color.

**New `422` condition**: when `isolated_photo_path` is present (non-null), it MUST also start
with `{user_id}/` — the same ownership-prefix check the route already applies to `photo_path`
(006 contract), extended to cover this second path rather than left as a one-off exception. A
Storage object path is access-control-relevant (unlike `photo_background_color`, a cosmetic hex
value with no path/ownership implication, which stays validated only for hex shape); accepting
an unvalidated path here would be the same class of gap `photo_path`'s existing check exists to
close, just on the newer field.
