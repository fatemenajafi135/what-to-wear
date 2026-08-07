-- Feature 012: calendar. Google Calendar connection state, an ephemeral PKCE
-- handoff table, and the single picked-event snapshot that surfaces on
-- Recommend. Follows 0002_wardrobe_and_catalog_items.sql's RLS convention
-- exactly (see that migration's own header comment for the reasoning this
-- doesn't repeat): `user_id uuid` is the verified JWT `sub` claim, no local
-- `users` table, RLS enabled on every table with a `for all using
-- (auth.uid() = user_id) with check (auth.uid() = user_id)` policy, plus the
-- table-level GRANT every earlier migration found necessary (Postgres's
-- default-privilege behavior otherwise leaves `authenticated` unable to
-- touch a table `postgres` created, regardless of the RLS policy).
--
-- OAuth tokens are credentials, not ordinary user data — access_token and
-- refresh_token are stored *encrypted*, not plaintext, because this
-- project's own prior finding (specs/004-closet-read/research.md §1) is
-- that RLS is a no-op for this backend's own pooler connection (BYPASSRLS).
-- See specs/012-calendar/research.md §2 for the full decision and
-- docs/design-decisions.md §16 for the cross-reference. The encryption
-- itself happens in Python (adapters/token_encryption.py); this migration
-- only declares the columns as `text`, wide enough to hold ciphertext.

-- --------------------------------------------------------------------------
-- calendar_connections — owned, private. Zero or one row per user.
-- --------------------------------------------------------------------------

create table calendar_connections (
  user_id uuid primary key,
  access_token_encrypted text not null,
  refresh_token_encrypted text not null,
  token_expires_at timestamptz not null,
  connected_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create trigger trg_calendar_connections_updated_at
  before update on calendar_connections
  for each row execute function public.set_updated_at();

alter table calendar_connections enable row level security;

create policy "calendar_connections_modify_own" on calendar_connections
  for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

grant select, insert, update, delete on calendar_connections to authenticated;

-- --------------------------------------------------------------------------
-- calendar_oauth_attempts — owned, private, ephemeral. One row per in-flight
-- connect attempt; deleted the moment it's used. Never exposed through any
-- API response (specs/012-calendar/research.md §3) — internal PKCE state
-- only. No expiry sweep in this slice: an abandoned row is useless without
-- its matching short-lived Google authorization code, so it carries no real
-- risk, only unbounded (if slow) table growth — accepted as a known,
-- documented gap, not an oversight.
-- --------------------------------------------------------------------------

create table calendar_oauth_attempts (
  state uuid primary key default gen_random_uuid(),
  user_id uuid not null,
  code_verifier text not null,
  created_at timestamptz not null default now()
);

alter table calendar_oauth_attempts enable row level security;

create policy "calendar_oauth_attempts_modify_own" on calendar_oauth_attempts
  for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

grant select, insert, update, delete on calendar_oauth_attempts to authenticated;

-- --------------------------------------------------------------------------
-- picked_events — owned, private. Zero or one row per user: a snapshot, not
-- a history. Cleared whenever calendar_connections is disconnected for that
-- user (spec.md FR-013); overwritten (upsert) whenever a new event is
-- picked. google_event_id is a reference to Google's own event id, not a
-- foreign key — no local events table exists (events are fetched live,
-- never persisted, per research.md §5).
-- --------------------------------------------------------------------------

create table picked_events (
  user_id uuid primary key,
  google_event_id text not null,
  title text not null,
  start_time timestamptz not null,
  location text,
  picked_at timestamptz not null default now()
);

alter table picked_events enable row level security;

create policy "picked_events_modify_own" on picked_events
  for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

grant select, insert, update, delete on picked_events to authenticated;
