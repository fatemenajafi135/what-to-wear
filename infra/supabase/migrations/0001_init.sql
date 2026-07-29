-- Feature 002: backend and database foundation.
--
-- Scope: foundation objects only — extensions, the frozen item taxonomy
-- (Constitution Principle VI) as enforced Postgres enums, a reusable
-- `updated_at` trigger function, and the row-level-security convention every
-- table added from feature 004 onward follows. No product table (wardrobe
-- items, outfits, users) is created here — see
-- specs/002-backend-foundation/data-model.md and research.md §6-7 for the
-- reasoning behind each object below.

-- --------------------------------------------------------------------------
-- Extensions
-- --------------------------------------------------------------------------

-- gen_random_uuid() for every future table's primary-key default.
create extension if not exists pgcrypto;

-- --------------------------------------------------------------------------
-- Frozen taxonomy (Constitution Principle VI) — Postgres enums.
-- Features MUST conform to these values. They MUST NOT introduce a parallel
-- formality scale or rename a category group. Any change to either enum is a
-- breaking, explicit migration of its own — never an edit to this one.
-- --------------------------------------------------------------------------

create type category_group as enum (
  'top',
  'bottom',
  'full_body',
  'outerwear',
  'footwear',
  'accessory'
);

create type formality_level as enum (
  'casual',
  'smart_casual',
  'business_casual',
  'semi_formal',
  'formal',
  'black_tie'
);

-- --------------------------------------------------------------------------
-- updated_at trigger convention
--
-- No table uses this yet. Every future table with an `updated_at` column
-- attaches it via:
--
--   create trigger trg_<table>_updated_at
--     before update on <table>
--     for each row execute function public.set_updated_at();
-- --------------------------------------------------------------------------

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

-- --------------------------------------------------------------------------
-- Row-level-security convention (documented, not yet applied)
--
-- Written here as guidance, not executable SQL — there is no table to attach
-- a policy to in this migration. Every per-user table from feature 004
-- onward carries a `user_id uuid` column (no local `users` table; `user_id`
-- is the opaque `sub` claim from the verified Supabase JWT, per the legacy
-- prototype's precedent) and follows this exact shape:
--
--   alter table <table> enable row level security;
--
--   create policy "<table>_select_own" on <table>
--     for select using (auth.uid() = user_id);
--
--   create policy "<table>_modify_own" on <table>
--     for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
--
-- auth.uid() is populated by Supabase's request-scoped JWT context when a
-- request goes through Supabase's own Data API. A backend that queries
-- Postgres directly (as this project's FastAPI service does, via
-- core/db.py) must establish that same context itself per request for these
-- policies to evaluate correctly — that mechanism is feature 003's (Auth)
-- responsibility to wire, not this migration's.
-- --------------------------------------------------------------------------
