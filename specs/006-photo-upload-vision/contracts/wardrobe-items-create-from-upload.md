# Contract: `POST /api/v1/closet/items/from-upload`

New endpoint on the existing `closet.py` router. Creates a `wardrobe_items` row from a
previously-extracted (and possibly user-corrected) draft. Requires the extract route to have
run first — this route never uploads a photo itself, only `photo_path` is passed through.

## Auth

Required. `get_current_user_id` only (no Storage call on this route).

## Request

`application/json` — `CreateWardrobeItemFromUploadRequest` (data-model.md §3, relaxed per
research.md §4):

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
  "fit": "regular",
  "name": "Navy tee",
  "notes": null
}
```

`formality`, `warmth`, `season`, `fabric`, `pattern`, `fit` are all optional. When
`formality`/`warmth`/`season` are omitted, the route applies the documented defaults
(`"casual"` / `3` / all four seasons — research.md §4) before persisting, since those three
columns are `NOT NULL` at the database layer; `fabric`/`pattern`/`fit` are stored `NULL` when
omitted. `name`/`notes` reuse `WardrobeItem`'s existing optional fields.

`colors` — the review card's Color field is free text; the frontend resolves it against
`FASHION_COLOR_PALETTE` before this request is sent (research.md §5), so this route still
receives hex, matching every other write path (`_colors_must_be_hex`). A value the frontend
couldn't resolve never reaches this route — it's a `field.color.notRecognized` client-side
validation error shown on the review card instead (data-model.md §7).

## Response — `201 Created`

`ClosetItemView` (existing shape, data-model.md §5) — the same response shape
`GET /closet/items/{item_id}` returns, including the freshly-minted `photo_url`.

## Response — `4xx`

| Status | Condition |
|---|---|
| 401 | missing/invalid bearer token |
| 422 | `category` or `colors` missing/empty, an unresolvable color already caught client-side but re-validated here defensively, or `photo_path` doesn't look like a path this user's own extract call would have produced |

`ports.ClosetRepository` is unchanged — this route calls a new method on
`SupabaseClosetRepository` directly (`create_wardrobe_item_from_upload`), the same pattern
005's four write methods already established for repository methods that exist without a
matching `ports.py` Protocol entry (handoff trap 5 / data-model precedent from
`specs/005-closet-write/research.md` §5).
