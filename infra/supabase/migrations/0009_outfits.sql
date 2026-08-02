-- Feature 009: outfit suggestion pager. The project's first persisted
-- outfit — nothing before this migration ever survives past one HTTP
-- response (docs/handoffs/009-suggestion-pager.md §3). Minimal schema:
-- exactly what it costs to save and re-read a pager card, not what the
-- Outfits gallery (feature 010) might eventually want.
--
-- See docs/design-decisions.md §32 for the full reasoning, including why
-- `item_ids` is a plain array rather than a join table (no per-item
-- metadata is read or written anywhere in this slice) and why un-saving
-- flips `favorite` rather than deleting the row (Delete is a separate,
-- later action the Outfits gallery's own overflow menu owns).

create table outfits (
  id uuid primary key default gen_random_uuid(),
  -- The verified JWT `sub` claim — matches every other owned table's
  -- convention (no local `users` table).
  user_id uuid not null,
  -- Frozen at save time from the pipeline's own `Context`, never
  -- re-derived later — `Context` itself is not persisted anywhere else,
  -- so these two fields are the only way a saved outfit can ever show the
  -- same meta line again (design-decisions.md §32/§34).
  occasion text not null,
  meta_line text not null,
  -- Plain text, never citation markers — matches the pager card's own
  -- rendering (design-decisions.md §33/§35).
  rationale_text text not null,
  -- The label only, never the underlying float (Constitution II/VI: no
  -- parallel numeric scale, not even at rest).
  match_label text not null check (match_label in ('great', 'good', 'might_work')),
  -- Wardrobe item ids, in display order. No array-level FK — Postgres has
  -- none — ownership is validated by the route before insert, not by a DB
  -- constraint.
  item_ids uuid[] not null,
  -- Existence + true = "saved" (the only state the heart's first tap can
  -- produce). The second tap flips this exactly like
  -- `wardrobe_items.favorite` already toggles; it never deletes the row.
  favorite boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index outfits_user_id_idx on outfits (user_id);

create trigger trg_outfits_updated_at
  before update on outfits
  for each row execute function public.set_updated_at();

alter table outfits enable row level security;

create policy "outfits_modify_own" on outfits
  for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

-- Same non-optional table-level GRANT `0002` documents: RLS restricts
-- ROWS, but does nothing without this — the default ACL for a table
-- created by `postgres` gives `authenticated` no SELECT at all. Proven by
-- a two-user isolation test (tests/integration/test_outfits_isolation.py).
grant select, insert, update, delete on outfits to authenticated;
