-- Feature 004: closet (read). The first product tables, and the row-level-
-- security convention every later table copies.
--
-- Two tables, not one nullable-owner table (specs/004-closet-read/research.md
-- §3): `catalog_items` is shared and has no owner; `wardrobe_items` is owned
-- and private. Their RLS policies genuinely differ, which is the whole reason
-- to split them rather than branch on a nullable `user_id`.
--
-- IMPORTANT — RLS is enabled and correct here, but it is NOT the guarantee
-- for this backend's own traffic: the pooler role this app connects as
-- (`postgres`, via the local `pooler-dev` tenant) has BYPASSRLS, so Postgres
-- skips policy evaluation entirely for every query this app issues,
-- regardless of the JWT context set alongside it. The query-level
-- `WHERE user_id = ...` every repository method issues is what actually
-- isolates data today. RLS ships anyway as the documented convention and as
-- defense-in-depth for any access path that does NOT use this app's
-- bypass-privileged connection (Supabase Studio, PostgREST, a future edge
-- function). See specs/004-closet-read/research.md §1-2 for the full finding
-- and for how the isolation test proves the policy independent of this
-- app's own connection.

-- --------------------------------------------------------------------------
-- catalog_items — shared, read-only, no owner.
-- --------------------------------------------------------------------------

create table catalog_items (
  id uuid primary key default gen_random_uuid(),
  -- Specific category (e.g. "blazer"). The category GROUP (top/bottom/
  -- full_body/outerwear/footwear/accessory) is derived on read via the
  -- existing categories.group_of() — never stored (constitution VI: the
  -- taxonomy is frozen, and group membership living in two places is
  -- exactly the kind of drift that freeze exists to prevent).
  category text not null,
  colors text[] not null default '{}',
  formality formality_level not null,
  warmth smallint not null check (warmth between 0 and 5),
  season text[] not null default '{}'
    check (season <@ array['spring', 'summer', 'autumn', 'winter']::text[]),
  fabric text,
  pattern text,
  fit text,
  -- Added in /speckit-clarify (2026-07-31): the design system's Item detail
  -- and Add-item screens both require Name/Notes fields the frozen
  -- WardrobeItem contract didn't have. Additive only — see schema.py.
  name text,
  notes text,
  -- No real photo exists until feature 006; the frontend renders the
  -- design system's diagonal-stripe placeholder regardless of this value.
  photo_path text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create trigger trg_catalog_items_updated_at
  before update on catalog_items
  for each row execute function public.set_updated_at();

alter table catalog_items enable row level security;

-- Every signed-in user reads the whole catalog; nobody owns a row. No
-- insert/update/delete policy exists in this feature — catalog population
-- is out of scope here (specs/004-closet-read/research.md §3) and can only
-- happen through a bypass-privileged connection (a seed script or a future
-- migration) until a feature explicitly owns catalog management.
create policy "catalog_items_select_shared" on catalog_items
  for select
  to authenticated
  using (true);

-- RLS restricts ROWS; it does nothing without the table-level GRANT that
-- lets `authenticated` touch the table at all. This table was created by
-- `postgres`, and the local stack's default ACL for objects `postgres`
-- creates in `public` gives `authenticated` only DELETE/REFERENCES/
-- TRIGGER/MAINTAIN — no SELECT (confirmed against `pg_default_acl`; this
-- is not a supabase-cli quirk, it's plain Postgres default-privilege
-- behavior). Without this line the policy above is silently unreachable:
-- every query fails with "permission denied for table catalog_items"
-- before RLS is ever evaluated. Caught by writing the isolation test
-- against this exact role instead of assuming the policy alone was enough
-- (specs/004-closet-read/research.md §2).
grant select on catalog_items to authenticated;

-- --------------------------------------------------------------------------
-- wardrobe_items — owned, private. One row per item per user.
-- --------------------------------------------------------------------------

create table wardrobe_items (
  id uuid primary key default gen_random_uuid(),
  -- The verified JWT `sub` claim. No local `users` table — matches
  -- 0001_init.sql's documented convention.
  user_id uuid not null,
  category text not null,
  colors text[] not null default '{}',
  formality formality_level not null,
  warmth smallint not null check (warmth between 0 and 5),
  season text[] not null default '{}'
    check (season <@ array['spring', 'summer', 'autumn', 'winter']::text[]),
  fabric text,
  pattern text,
  fit text,
  name text,
  notes text,
  -- Matches WardrobeItem.source: Literal["catalog", "upload"].
  source text not null check (source in ('catalog', 'upload')),
  -- Optional provenance: which catalog item this was added from, if any.
  -- Losing the link on catalog cleanup doesn't corrupt the item itself —
  -- its own attributes were copied in at creation time, not derived on read.
  catalog_item_id uuid references catalog_items (id) on delete set null,
  photo_path text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index wardrobe_items_user_id_idx on wardrobe_items (user_id);

create trigger trg_wardrobe_items_updated_at
  before update on wardrobe_items
  for each row execute function public.set_updated_at();

alter table wardrobe_items enable row level security;

-- for all (not just select): this feature only exercises the select branch,
-- but writing the full policy now means feature 005 (closet write) doesn't
-- need to touch this migration's policy at all.
create policy "wardrobe_items_modify_own" on wardrobe_items
  for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

-- Same table-level GRANT requirement as catalog_items above — "for all" to
-- match the RLS policy's own scope, since feature 005 (closet write) will
-- need insert/update/delete and shouldn't need a migration just to add
-- these grants.
grant select, insert, update, delete on wardrobe_items to authenticated;
