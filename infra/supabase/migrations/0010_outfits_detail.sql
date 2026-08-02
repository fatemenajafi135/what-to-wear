-- Feature 010: Outfits gallery + detail. Widens `outfits` (0009) with what
-- Outfit detail needs that a pager card never showed — a user-editable
-- title, citations, and per-dimension scores — plus a new `outfit_wears`
-- table for "Log as worn today" and the gallery's "Most worn" sort.
--
-- See docs/design-decisions.md §38 (citations/scores, captured server-side
-- from the pipeline's checkpointed thread state at save time, never trusted
-- from the client and never re-generated), §39 (outfit-level wear logging
-- also logs every item still owned by the caller, via the unchanged
-- `item_wears` table from 0005), and §41 (why there is no new filter-facet
-- column here — filtering is deliberately deferred, only sorting ships).

alter table outfits
  -- User-editable, shown on the gallery card and Outfit detail's TopHeader.
  -- Backfilled from `occasion` below for every pre-010 row (design-decisions.md
  -- §36's own seam), then locked to not null.
  add column title text,
  -- Same content as `rationale_text`, but with `[n]` markers appended after
  -- each cited rationale segment, numbered in first-appearance order —
  -- resurrects the exact marker convention `bdc9ad4` built for 008 and 009
  -- removed once every outfit reply moved to the citation-free pager.
  -- `rationale_text` itself is untouched: it stays plain, matching 0009's
  -- own "never citation markers" comment, for any consumer that still
  -- trusts that invariant.
  add column rationale_with_citations text not null default '',
  -- [{number, text}] — the numbered rule-list rows the markers point at.
  -- `text` is the cited rule's human-readable source label, not styling
  -- guidance itself (§ Badge: "a footnote-style reference to a styling
  -- rule"). Empty array is the honest "nothing cited, or no longer provable"
  -- state (design-decisions.md §38's degrade path), not an error.
  add column citations jsonb not null default '[]'::jsonb,
  -- [{dimension, value}] — one entry per SCORE_DIMENSIONS value when
  -- present. `value` is transmitted (needed for a bar's fill width) but
  -- never rendered as visible text anywhere (§ Scores) — storing/sending a
  -- float is not the violation the design system forbids; rendering one as
  -- a number is. `DimensionScore.reason` is deliberately not persisted: no
  -- surface in design-system.md ever renders it.
  add column dimension_scores jsonb not null default '[]'::jsonb;

update outfits set title = occasion where title is null;
alter table outfits alter column title set not null;

-- Composite-FK target for outfit_wears below, same pattern 0005 used for
-- wardrobe_items/item_wears.
alter table outfits add constraint outfits_id_user_id_key unique (id, user_id);

create table outfit_wears (
  id uuid primary key default gen_random_uuid(),
  outfit_id uuid not null,
  -- Denormalized, same convention as item_wears.
  user_id uuid not null,
  worn_date date not null default current_date,
  created_at timestamptz not null default now(),
  -- One row per outfit per calendar day, not per tap — same idempotent
  -- shape 0005 chose for item_wears and for the identical reason: no
  -- confirmation or on-page feedback exists for this action either, so a
  -- second same-day tap must be a harmless no-op, not a second row.
  unique (outfit_id, worn_date),
  -- Rejects a forged (outfit_id, user_id) pair at the database level, same
  -- as item_wears' FK to wardrobe_items.
  foreign key (outfit_id, user_id) references outfits (id, user_id) on delete cascade
);

create index outfit_wears_user_id_idx on outfit_wears (user_id);

alter table outfit_wears enable row level security;

create policy "outfit_wears_modify_own" on outfit_wears
  for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

-- Same non-optional table-level GRANT `0002` documents: RLS restricts ROWS,
-- but does nothing without this. Proven by a two-user isolation test
-- (tests/integration/test_outfit_wears_rls.py).
grant select, insert, update, delete on outfit_wears to authenticated;
