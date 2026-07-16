# Phase 1 Data Model: MVP App

No new top-level entity beyond what `specs/003-mvp-app/spec.md`'s Key Entities
section already names (Account, Closet Item, Outfit Suggestion) — Account maps
to Supabase Auth (no local table, unchanged from Feature 001), Outfit
Suggestion stays the ephemeral `OutfitResult` `/recommend` already returns
(unchanged). What's new is two additive fields on the existing Closet Item and
three new Pydantic contract shapes for the photo flow.

## Closet Item (`WardrobeItem` / `WardrobeItemRow`) — additive change

| Field | Type | Constraint | Change |
|---|---|---|---|
| `id` | str/UUID | pk | unchanged |
| `category` | str | one of 6 frozen groups | unchanged |
| `colors` | list[str] | hex, validated | unchanged |
| `formality` | Formality enum | 6-value frozen enum | unchanged |
| `warmth` | int | 0–5 | unchanged |
| `season` | list[Season] | frozen 4-value enum | unchanged |
| `fabric` | Optional[str] | free-text | unchanged |
| `source` | Optional["catalog"\|"upload"] | | unchanged |
| **`pattern`** | **Optional[str]** | **free-text, matches `fabric`'s shape** | **NEW** |
| **`fit`** | **Optional[str]** | **free-text, matches `fabric`'s shape** | **NEW** |

Applies to `schema.WardrobeItem`, `schema.WardrobeItemPatch` (both new fields
optional in the patch, PATCH semantics unchanged), and `models.WardrobeItemRow`
(two new nullable `String` columns). **Not** added to `CatalogItemRow` —
catalog items predate these fields; a catalog-sourced wardrobe row simply has
`pattern=None, fit=None`, same as it already has no issue with `fabric=None`
today.

Migration `0002_add_pattern_fit.py`: `ALTER TABLE wardrobe_items ADD COLUMN
pattern VARCHAR NULL, ADD COLUMN fit VARCHAR NULL` (additive, no backfill, no
default — mirrors exactly how `fabric`/`source` were added in
`0001_initial_wardrobe_schema.py`'s precedent pattern, just as a follow-on
migration instead of inline in the initial one).

## New: `ExtractedAttributes`

Draft output of one VLM extraction call. Every field optional — extraction
failure on any/all fields must not block the flow (FR-006).

| Field | Type |
|---|---|
| `category` | Optional[str] |
| `colors` | Optional[list[str]] (hex) |
| `fabric` | Optional[str] |
| `warmth` | Optional[int] (0–5) |
| `formality` | Optional[Formality] |
| `season` | Optional[list[Season]] |
| `pattern` | Optional[str] |
| `fit` | Optional[str] |

## New: `PhotoExtractionResponse`

What `POST /wardrobe/items/extract` returns — an unsaved draft, never a
persisted row.

| Field | Type | Notes |
|---|---|---|
| `photo_path` | str | Storage object path — passed back on save so the photo isn't re-uploaded |
| `extracted` | ExtractedAttributes | may be entirely empty fields if extraction failed |
| `extraction_ok` | bool | `false` when the VLM call failed or returned nothing usable — frontend shows the "couldn't process, retry or fill in manually" state (FR-006, Acceptance Scenario 3) |

## New: `CreateWardrobeItemFromUploadRequest`

Body of `POST /wardrobe/items/upload` — the user-confirmed (possibly
corrected) attributes, required at save time since every saved item must have
every attribute populated (SC-003).

| Field | Type | Constraint |
|---|---|---|
| `photo_path` | str | from the prior `/extract` response |
| `category` | str | one of 6 frozen groups |
| `colors` | list[str] | hex, ≥1 |
| `formality` | Formality | required |
| `warmth` | int | 0–5, required |
| `season` | list[Season] | ≥1, required |
| `fabric` | str | **required** — SC-003 needs 100% of saved items populated, none blank |
| `pattern` | str | **required** — SC-003 needs 100% of saved items populated, none blank |
| `fit` | str | **required** — SC-003 needs 100% of saved items populated, none blank |

`fabric`/`pattern`/`fit` are required **only on this creation path** — SC-003's
"100% populated, none blank" applies to items saved through the photo flow,
where the user has just reviewed every field and confirmed a value for each
(FR-005/FR-006). The persisted `wardrobe_items.fabric/pattern/fit` columns
stay nullable (catalog-sourced rows predate `pattern`/`fit` and already allow
`fabric=None`), and `WardrobeItemPatch` (the correction path) keeps all three
optional — this constraint is specific to `CreateWardrobeItemFromUploadRequest`,
not a schema-wide tightening.

Maps 1:1 to a new `WardrobeItemRow` with `source="upload"`,
`catalog_item_id=None` — parallel to, not replacing, the existing
catalog-based creation path.

## State transitions (US2's flow)

```
photo captured/chosen
   → POST /wardrobe/items/extract  (upload to Storage, one VLM call)
   → PhotoExtractionResponse (unsaved draft)
   → user reviews, edits any field
   → POST /wardrobe/items/upload   (user-confirmed attributes)
   → WardrobeItem (persisted, source="upload")
```

Correcting an already-saved item re-enters the existing, unchanged
`PATCH /wardrobe/items/{id}` flow — no new transition there.
