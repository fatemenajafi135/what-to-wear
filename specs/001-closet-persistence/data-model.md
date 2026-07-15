# Data Model: Closet Persistence

**Terminology**: the code, API, and database use **wardrobe** throughout, to
align with the existing frozen Pydantic `WardrobeItem` contract (constitution
Principles VI/VII). **Closet** is the user-facing product/UI word only — the
frontend may show "your closet," but there is no `closet_*` identifier in
code. See research.md → "Terminology".

## WardrobeItem (persisted)

An item a specific user owns. Persisted in the `wardrobe_items` table via the
`WardrobeItemRow` ORM model (models.py). One row per owned garment/accessory
instance — adding the same catalog item twice creates two rows (spec
Assumptions).

The ORM class is named `WardrobeItemRow`, not `WardrobeItem`, deliberately: the
frozen Pydantic `WardrobeItem` in `schema.py` already owns that name and is the
API/pipeline contract. The `Row` suffix keeps the persistence row distinct from
the contract it maps to, so the two never shadow each other in `crud.py`.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID, PK | server-generated |
| `user_id` | UUID, not null, indexed, **no FK constraint** | from verified JWT `sub` claim — there is no local `users` table to reference (research.md). Treat as a bare opaque UUID everywhere it appears in this or any future table; do not declare a foreign key to a `users` table that doesn't exist. |
| `category` | VARCHAR, not null | free-form; slot/bucket is derived on read via existing `categories.group_of()`, never stored (Clarifications) |
| `colors` | JSONB, not null | list of hex strings, validated at the Pydantic boundary (`colors.normalize_hex`) |
| `fabric` | VARCHAR, nullable | new field; nullable because the catalog seed has no fabric data yet (research.md) |
| `warmth` | INTEGER, not null, `CHECK (warmth BETWEEN 0 AND 5)` | matches existing `WardrobeItem.warmth` |
| `formality` | VARCHAR, not null | one of the six-value enum (`casual` … `black_tie`), validated at the Pydantic boundary |
| `season` | JSONB, not null | list of season values; field kept named `season` to match the existing frozen schema (research.md) |
| `source` | VARCHAR, not null, default `'catalog'` | `catalog` \| `upload`. Every row in this feature is `catalog` (photo upload is out of scope, FR-003). Added now, unused beyond its default, so Feature 003 doesn't need a migration to introduce photo-uploaded items — see research.md for why this isn't actually needed by Feature 002. |
| `catalog_item_id` | UUID, nullable, FK → `catalog_items.id` | provenance only — the row is an independent copy (FR-011), this is not a live reference |
| `created_at` | TIMESTAMPTZ, not null, default now() | |
| `updated_at` | TIMESTAMPTZ, not null, default now(), updated on correction | |

**Validation rules** (enforced at the Pydantic boundary, matching existing
`schema.py` conventions, not as DB constraints beyond `warmth`'s CHECK):
- `colors` entries must be valid hex (`colors.normalize_hex`)
- `formality` must be one of the six controlled values
- `season` entries must be one of the four controlled values
- `warmth` must be within 0-5
- `category` accepts any string (open-ended, per existing `categories.py`
  design) — an unrecognized value simply derives to the `accessory` bucket

**Lifecycle**: created via catalog selection (US2) → optionally corrected, any
field (US3) → optionally removed, hard delete (US4). No soft-delete, no
status/state field — a row's existence *is* its state.

## CatalogItem (persisted)

A shared, pre-built item definition, same attribute shape as a wardrobe item
minus ownership. Persisted in the `catalog_items` table via the
`CatalogItemRow` ORM model. Read-only through this feature's API; written only
by the one-time seed step from `data/fixtures/wardrobe.json`.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID, PK | server-generated |
| `category` | VARCHAR, not null | same rules as the wardrobe `category` |
| `colors` | JSONB, not null | |
| `fabric` | VARCHAR, nullable | null for all 40 seeded items today (research.md) |
| `warmth` | INTEGER, not null, `CHECK (warmth BETWEEN 0 AND 5)` | |
| `formality` | VARCHAR, not null | |
| `season` | JSONB, not null | |
| `created_at` | TIMESTAMPTZ, not null, default now() | |

No `user_id` — this table has exactly one shared set of rows, visible to
every authenticated user.

## Explicitly not modeled in this feature

- **`users` table** — not created; see research.md. `user_id` values are
  opaque UUIDs from the JWT, unenforced by a local FK. This applies to every
  future table that carries a `user_id` (e.g. Feature 004's `feedback`,
  `preference_profiles`): bare indexed column, never a foreign key, since
  there is no local row to reference.
- **Catalog embeddings / vector similarity** — not added. Feature 002's
  similar-item substitution ("you don't own this, but it'd work") is planned
  to reuse the same deterministic attribute-distance scoring the styling
  engine already needs (formality distance, warmth distance, season overlap,
  color harmony) applied to `catalog_items` candidates, not a nearest-neighbor
  embedding search. See research.md. If that turns out to be too coarse,
  adding embeddings to `catalog_items` later is an additive, isolated change —
  `wardrobe_items` never needs them, since owned items are always explicitly
  available rather than "found by similarity."
- **Soft delete / deleted-item retention** — out of scope (spec Assumptions);
  removal is a hard `DELETE`.

## Relationship to `schema.py` (Pydantic)

`WardrobeItem` (existing Pydantic contract in `schema.py`) gains two new
optional fields:

```python
fabric: Optional[str] = None
source: Optional[Literal["catalog", "upload"]] = None
```

There is no separate "ClosetItem" API type. `GET /wardrobe/items` and
`GET /catalog/items` both return the same `WardrobeItem` shape (catalog
entries simply carry no `user_id`/`source`), per constitution Principle VII
(one Pydantic contract, not a parallel API type that could drift from the
pipeline-internal one). The generator/pipeline code ignores fields it doesn't
read (`source`, timestamps); the API layer surfaces them from the ORM row.

No other field changes. `context_assembler.load_wardrobe(user_id)` maps
`WardrobeItemRow` ORM rows → `WardrobeItem` Pydantic instances; everything
downstream of that function is unmodified.
