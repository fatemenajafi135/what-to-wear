-- Feature 005: closet (write). Adds the storage the four overflow-menu
-- actions need: a favourite flag on the item, and per-day wear history.
--
-- Follows 0002's RLS + GRANT pattern exactly (see that file's own header
-- for why both are needed — RLS restricts rows, GRANT is what lets the
-- `authenticated` role touch the table at all).
--
-- Wear-model decision (one row per item per calendar day, not per tap, not
-- a bare counter) is recorded in docs/design-decisions.md §22.1 and
-- specs/005-closet-write/data-model.md — not repeated here.

-- --------------------------------------------------------------------------
-- wardrobe_items.favorite — a single mutable flag, no history needed.
-- --------------------------------------------------------------------------

alter table wardrobe_items add column favorite boolean not null default false;

-- No RLS/GRANT change needed: 0002's `wardrobe_items_modify_own` policy is
-- `for all` and the table-level GRANT already includes update — both cover
-- this new column for free.

-- A composite candidate key so item_wears' foreign key below can bind
-- item_id AND user_id together in one constraint (see that FK's own
-- comment for why: RLS's `with check (auth.uid() = user_id)` on its own
-- only proves a wear row's user_id is the caller's, not that the item it
-- points at is also theirs).
alter table wardrobe_items add constraint wardrobe_items_id_user_id_key unique (id, user_id);

-- --------------------------------------------------------------------------
-- item_wears — one row per item per calendar day it was worn.
-- --------------------------------------------------------------------------

create table item_wears (
  id uuid primary key default gen_random_uuid(),
  item_id uuid not null,
  -- Denormalized from the item at write time, matching wardrobe_items.user_id's
  -- own "verified JWT sub claim, no local users table" convention — RLS and
  -- the query-level filter both need it directly on this table, not via a
  -- join to wardrobe_items, for the same reason 0002's tables never join for
  -- ownership.
  user_id uuid not null,
  worn_date date not null default current_date,
  created_at timestamptz not null default now(),
  -- The mechanism that makes "log as worn today" idempotent per day: a
  -- second tap the same day is an ON CONFLICT DO NOTHING no-op against this
  -- constraint, never a second row.
  unique (item_id, worn_date),
  -- Composite FK against wardrobe_items' new (id, user_id) unique key,
  -- not a plain `item_id references wardrobe_items(id)`: RLS's own
  -- `with check` only verifies THIS row's `user_id` matches the caller —
  -- it can't see whether `item_id` belongs to that same user. This
  -- constraint makes that pairing impossible at the schema level: no row
  -- can exist where `item_id` and `user_id` don't both come from the same
  -- wardrobe_items row, closing the gap RLS alone leaves open (a caller
  -- could otherwise log a "wear" against someone else's item under their
  -- own user_id and have it pass RLS). `on delete cascade` still applies
  -- via this same constraint.
  foreign key (item_id, user_id) references wardrobe_items (id, user_id) on delete cascade
);

create index item_wears_item_id_idx on item_wears (item_id);

alter table item_wears enable row level security;

create policy "item_wears_modify_own" on item_wears
  for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

-- update/delete granted for convention-consistency with 0002's tables even
-- though this feature's own routes only ever insert (data-model.md) — a
-- table with insert-only privileges would be the first exception to that
-- pattern, worth avoiding for no benefit.
grant select, insert, update, delete on item_wears to authenticated;
