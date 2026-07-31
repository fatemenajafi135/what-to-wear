# Data model: Closet (write)

## `wardrobe_items` (extended, migration `0005`)

Adds one column to the table `0002` created:

| Column | Type | Notes |
|---|---|---|
| `favorite` | `boolean not null default false` | Toggled by the Favorite overflow row. Never read back by this feature's own UI (design-system §2.3 excludes a favourite indicator from Item detail) — consumed by future features (Outfits, later favourites views). |

No RLS change needed: `0002`'s `wardrobe_items_modify_own` policy is `for all`, so it already
covers `UPDATE`/`DELETE` on this and every other column, and the table-level `GRANT` already
includes `update`/`delete`.

## `item_wears` (new, migration `0005`)

One row per item per calendar day it was worn — see `docs/design-decisions.md` §22.1 for why
this shape and not `worn_count` or one-row-per-tap.

| Column | Type | Notes |
|---|---|---|
| `id` | `uuid primary key default gen_random_uuid()` | |
| `item_id` | `uuid not null references wardrobe_items(id) on delete cascade` | Deleting an item deletes its wear history — no orphaned rows, and nothing in this feature or the spec needs wear history to outlive its item. |
| `user_id` | `uuid not null` | Denormalized from the item at write time (matches `wardrobe_items.user_id`'s own "verified JWT `sub` claim, no local users table" convention) — RLS and the query-level filter both need it directly on this table, not via a join, for the same reason `0002`'s tables never join for ownership. |
| `worn_date` | `date not null default current_date` | The calendar day, in the semantics the upsert relies on. |
| `created_at` | `timestamptz not null default now()` | Ordering/audit only; not user-editable. |

Constraint: `unique (item_id, worn_date)` — the mechanism that makes "log as worn today"
idempotent per day (§22.1). No `updated_at`/trigger — rows are immutable once written (a
no-op repeat tap touches nothing, per the `ON CONFLICT ... DO NOTHING` upsert).

Index: `item_wears_item_id_idx on item_wears (item_id)` — matches `wardrobe_items_user_id_idx`'s
precedent of indexing the column every query filters by.

RLS: same pattern as `wardrobe_items` — `for all using (auth.uid() = user_id) with check
(auth.uid() = user_id)`, plus `grant select, insert, update, delete on item_wears to
authenticated`. `update`/`delete` are granted for convention-consistency with `0002`
even though this feature's own routes only ever insert; a table with insert-only granted
privileges would be the first exception to that pattern, worth avoiding for no benefit.

## API-facing shapes (no new Pydantic types beyond what's listed)

- `WardrobeItemPatch` (`schema.py`, already exists) — the `PATCH` body. No changes needed; every
  field the edit form touches (`category`, `fabric`, `name`, `notes` — `colors` is out of scope
  for this feature's form, see quickstart) is already optional on it.
- `ClosetItemView` (`routes/closet.py`, already exists) — the `PATCH` response reuses it
  unchanged; `favorite` is added as a new field sourced from the extended `WardrobeItem`
  model (see below), not a new response type.
- `WardrobeItem` (`schema.py`) gains `favorite: bool = False` — additive, matches the existing
  pattern for `name`/`notes` (feature 004) and keeps this the single contract type for both the
  AI pipeline's read path and this feature's write path (constitution VII).
- New route-local response models in `routes/closet.py`: `FavoriteToggleResponse { favorite:
  bool }`. Wear-log and delete return `204 No Content` — no body, matching the calendar
  `disconnect`-style routes' own no-body-on-success precedent.
- New route-local request model `ClosetItemEditRequest { name, category, fabric, colors_text,
  notes: str | None }` — deliberately not `WardrobeItemPatch` itself. The edit form's Colour
  field (design-system: a single text input, not a multi-swatch picker) collects a
  comma-separated list of color **names** (pre-filled from `color_names`, matching what the
  user reads), but `WardrobeItemPatch.colors` is validated hex-only — `colors.py` already draws
  that hex-is-truth line and this feature has no reason to blur it. The route converts
  `colors_text` ("navy, white") to hex via `colors.name_to_hex` per comma-separated token
  (falling back to `colors.is_hex`/`normalize_hex` if the token is already hex) before building
  the `WardrobeItemPatch` it passes to the repository — keeping the AI-pipeline-facing contract
  (`WardrobeItemPatch`) exactly as `WardrobeItem`'s reference the same way `ClosetItemView`
  already layers route-local, display-facing fields on top of it without changing it. An
  unrecognized name (not in `FASHION_COLOR_PALETTE`, not valid hex) is a 422 naming the bad
  token, not a silent drop. Pattern and fit are not part of this form at all — the field list
  is exactly Name/Category/Group/Fabric/Colour/Notes per design-system Screen anatomy, so
  neither reaches `WardrobeItemPatch` from this route.

## State transitions

- Edit: `wardrobe_items` row, partial column update. No status/lifecycle field involved.
- Favorite: `favorite` boolean flips. No intermediate state.
- Log as worn: `item_wears` gains a row for `(item_id, today)` on the first tap of the day;
  every subsequent tap that day is a no-op against the same row.
- Delete: `wardrobe_items` row removed; cascades to any `item_wears` rows for it.
