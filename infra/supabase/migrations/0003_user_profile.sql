-- Feature 013: Profile and Settings.
--
-- One product table: `user_profile`, holding declared style/body/size preferences and the
-- notifications toggle. Explicitly does NOT hold the account email (that's Supabase Auth's
-- own field, edited via `supabase.auth.updateUser` — see
-- specs/013-profile-settings/research.md §3) and does NOT extend
-- backend/src/whattowear/memory/preferences.py (that module holds *derived* signals learned
-- from outfit feedback; this table holds only what the user explicitly declared — see the
-- feature's handoff §6).
--
-- Follows the RLS convention `0001_init.sql` documented in writing (Postgres enums/extensions/
-- trigger function, no table yet). See specs/013-profile-settings/research.md §1: this
-- backend's own connection uses the Postgres superuser role via Supavisor and does not
-- populate `auth.uid()`, so this policy is defense-in-depth for a future direct-PostgREST/
-- anon-key path, not what protects data through this app today — the repository layer's own
-- `user_id` scoping is what does that. The policy itself is proven by a dedicated test that
-- opens its own restricted-role connection (tests/integration/test_user_profile_rls.py),
-- independent of the app's session, per that same research note.

create table user_profile (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null unique references auth.users (id) on delete cascade,

  style_tags text[] not null default '{}',
  colour_tags text[] not null default '{}',
  brands_to_avoid text[] not null default '{}',

  body_shape text,
  gender text,
  birth_date date,
  height text,
  top_size text,
  bottom_size text,
  shoe_size text,

  notifications_enabled boolean not null default true,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create trigger trg_user_profile_updated_at
  before update on user_profile
  for each row execute function public.set_updated_at();

alter table user_profile enable row level security;

create policy "user_profile_select_own" on user_profile
  for select using (auth.uid() = user_id);

create policy "user_profile_modify_own" on user_profile
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
