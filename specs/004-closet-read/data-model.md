# Data Model: Closet (read)

## `catalog_items`

Shared, read-only, not owned by any user. Migration `0002`.

| Column | Type | Notes |
|---|---|---|
| `id` | `uuid` | PK, `default gen_random_uuid()` |
| `category` | `text not null` | Specific category (e.g. `"blazer"`); group is derived via `categories.group_of()`, never stored |
| `colors` | `text[] not null default '{}'` | Hex strings, validated at the Pydantic layer (`WardrobeItem`) |
| `formality` | `formality_level not null` | Reuses `0001_init.sql`'s enum |
| `warmth` | `smallint not null check (warmth between 0 and 5)` | |
| `season` | `text[] not null default '{}'` | `check (season <@ array['spring','summer','autumn','winter']::text[])` |
| `fabric` | `text` | nullable |
| `pattern` | `text` | nullable |
| `fit` | `text` | nullable |
| `name` | `text` | nullable — resolved in `/speckit-clarify` |
| `notes` | `text` | nullable — resolved in `/speckit-clarify` |
| `photo_path` | `text` | nullable — no real photos exist until feature 006 |
| `created_at` | `timestamptz not null default now()` | |
| `updated_at` | `timestamptz not null default now()` | trigger: `public.set_updated_at()` |

**RLS**: enabled. One policy, `catalog_items_select_shared`: `for select using (true) to
authenticated`. No insert/update/delete policy in this feature (§3 research.md).

**No seed data ships in this migration** — an empty `catalog_items` table is valid; population
is a later feature's concern (out of scope here, per the handoff).

## `wardrobe_items`

Owned, private, one row per item per user. Migration `0002`.

| Column | Type | Notes |
|---|---|---|
| `id` | `uuid` | PK, `default gen_random_uuid()` |
| `user_id` | `uuid not null` | The verified JWT `sub` claim; no local `users` table (matches `0001_init.sql`'s documented convention) |
| `category` | `text not null` | Same shape as `catalog_items.category` |
| `colors` | `text[] not null default '{}'` | |
| `formality` | `formality_level not null` | |
| `warmth` | `smallint not null check (warmth between 0 and 5)` | |
| `season` | `text[] not null default '{}'` | Same check as `catalog_items.season` |
| `fabric` | `text` | nullable |
| `pattern` | `text` | nullable |
| `fit` | `text` | nullable |
| `name` | `text` | nullable |
| `notes` | `text` | nullable |
| `source` | `text not null check (source in ('catalog','upload'))` | Matches `WardrobeItem.source: Literal["catalog","upload"]` |
| `catalog_item_id` | `uuid` | nullable FK → `catalog_items(id) on delete set null` |
| `photo_path` | `text` | nullable |
| `created_at` | `timestamptz not null default now()` | |
| `updated_at` | `timestamptz not null default now()` | trigger: `public.set_updated_at()` |

Index: `wardrobe_items_user_id_idx on wardrobe_items(user_id)` — every query in this feature
filters by `user_id`.

**RLS**: enabled. One policy, `wardrobe_items_modify_own`: `for all using (auth.uid() =
user_id) with check (auth.uid() = user_id)` — this feature only exercises the `select` branch,
but the policy is written in full now so feature 005 (write) doesn't need to touch it.

## Category-group derivation and the closet filter chips

`category_group` (the `top`/`bottom`/`full_body`/`outerwear`/`footwear`/`accessory` enum) is
**never stored** on either table — it's derived on read from `category` via the existing
`categories.group_of()`. The Closet screen's five filter chips map to the six groups as:

| Chip | Group(s) |
|---|---|
| Tops | `top` |
| Bottoms | `bottom`, `full_body` (resolved in `/speckit-clarify`) |
| Outerwear | `outerwear` |
| Shoes | `footwear` |
| Accessories | `accessory` |

## `WardrobeItem` (schema.py) — additive change

```python
class WardrobeItem(BaseModel):
    ...
    name: str | None = None
    notes: str | None = None
```

Mirrored onto `WardrobeItemPatch` for the same two fields. No other field changes. Both are
`None` for every existing fixture item (`evals/fixtures/wardrobe.json` has neither key) —
valid, since both are optional.

## API response shapes (defined in `api/v1/routes/closet.py`, not `schema.py`)

Route-local, not part of the AI-pipeline contract — matches `whoami.py`'s existing pattern of
defining its own response model beside the route.

```python
class ClosetItemsResponse(BaseModel):
    items: list[WardrobeItem]
    total: int          # count matching the current filter, before pagination
    has_more: bool
```

`GET /api/v1/closet/items/{item_id}` returns a bare `WardrobeItem` (200) or a `404` with
FastAPI's standard `{"detail": ...}` shape — no dedicated wrapper needed for a single object.

## Relationships

```
users (Supabase auth, not a local table)
  └─< wardrobe_items (user_id)  ──> catalog_items (catalog_item_id, nullable, optional provenance)
catalog_items (no owner)
```
