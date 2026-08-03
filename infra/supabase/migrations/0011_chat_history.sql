-- Feature 011: Chat history. The first durable persistence for a styling
-- conversation — before this, `RecommendChat` held its transcript and
-- `thread_id` only in component state (design-decisions.md §25), and a page
-- reload lost both even though the pipeline's own checkpointed state for
-- that thread was still sitting in Postgres.
--
-- See docs/design-decisions.md §44 (what a "session" is, and what writes
-- one — written-on-start, keyed on `thread_id` itself, not a second
-- generated id), §45 (outfits link back to their session, nullable,
-- populated only going forward — no backfill, no guess for pre-existing
-- rows), and §46 (what the archived view's citation Badges render from).

-- --------------------------------------------------------------------------
-- sessions — one row per pipeline thread, from its first user message on.
-- --------------------------------------------------------------------------

create table sessions (
  -- IS thread_id, not a second independently-generated uuid (§44) — the
  -- pipeline already mints exactly one id per logical conversation
  -- (parse_request's uuid.uuid4() fallback, §25), and there is no caller
  -- anywhere that ever needs a session id and a thread id to differ.
  -- No `default gen_random_uuid()`: always supplied by the route, which
  -- already has the pipeline's own thread id in scope.
  id uuid primary key,
  -- The verified JWT `sub` claim — matches every other owned table's
  -- convention (no local `users` table).
  user_id uuid not null,
  created_at timestamptz not null default now(),
  -- Bumped on every message written to this thread (not just at creation).
  -- This is both "the date" a Chat-history row shows and the sort key for
  -- "most recently active first" — a continued, older conversation moves
  -- back to the top.
  updated_at timestamptz not null default now()
);

create index sessions_user_id_updated_at_idx on sessions (user_id, updated_at desc);

alter table sessions enable row level security;

create policy "sessions_modify_own" on sessions
  for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

-- Same non-optional table-level GRANT `0002` documents: RLS restricts ROWS,
-- but does nothing without this — the default ACL for a table `postgres`
-- creates gives `authenticated` no SELECT at all. Proven by a two-user
-- isolation test (tests/integration/test_sessions_rls.py). This backend's
-- own pooler role has BYPASSRLS, so the query-level `WHERE user_id = ...`
-- every repository method issues is what actually isolates this app's own
-- traffic; RLS + GRANT here is the documented convention and defense in
-- depth for any other access path, matching 0002's own note.
grant select, insert, update, delete on sessions to authenticated;

-- --------------------------------------------------------------------------
-- messages — one row per turn. Append-only from this feature's own routes.
-- --------------------------------------------------------------------------

create table messages (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references sessions (id) on delete cascade,
  -- Denormalized, matching outfit_wears/item_wears' own convention — RLS
  -- and the query-level ownership filter both read a flat column directly
  -- rather than requiring a join to reach the owning user on every row.
  user_id uuid not null,
  -- The §2 accommodation this feature exists to make ahead of feature 016
  -- (design-decisions.md §37, research.md §4): the column and the concept
  -- exist from day one. Only today's two real values are permitted by this
  -- constraint — 016 widens this exact constraint (a one-line
  -- ALTER TABLE ... DROP CONSTRAINT ... ADD CONSTRAINT ...) to add
  -- 'conversational_turn' and 'wrap_up' when it ships; pre-authorizing
  -- values nothing can yet write would be the speculative build-ahead the
  -- handoff explicitly warns against, not the accommodation it asks for.
  --
  -- `role` (user vs. assistant, needed to align a bubble left/right) is
  -- deliberately NOT a separate column — it is fully determined by `kind`
  -- for every value this feature or 016 names ('user_message' -> user;
  -- every other kind -> assistant), so a second column could only ever
  -- drift from this one, never add information. Derived in the repository
  -- layer instead.
  kind text not null check (kind in ('user_message', 'styling_reply')),
  -- The user's own message verbatim for kind='user_message'. For
  -- kind='styling_reply': the pipeline's reply_text/honesty-fallback copy
  -- when the turn produced zero outfits; '' when it produced one or more
  -- (that turn's content is the linked outfits below, not this column —
  -- no duplicating rationale_with_citations into a second place).
  text text not null default '',
  -- For kind='styling_reply': the ids of outfits this turn produced, in
  -- the same request that created them (design-decisions.md §42's own
  -- in-hand-data reasoning applies again here). Always '{}' for
  -- kind='user_message'. Plain array, no join table — same reasoning §32
  -- already gave for outfits.item_ids: no per-row metadata needed, order
  -- is display order, and nothing in this slice reads or writes more.
  outfit_ids uuid[] not null default '{}',
  created_at timestamptz not null default now()
);

-- The read pattern for Session detail is always "every message for one
-- session, in order."
create index messages_session_id_created_at_idx on messages (session_id, created_at);

alter table messages enable row level security;

create policy "messages_modify_own" on messages
  for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

-- Same GRANT requirement as sessions above. update/delete are granted for
-- parity with every other owned table's grant statement in this codebase
-- (0002's own comment: "for all... shouldn't need a migration just to add
-- these grants"), even though no route in this feature issues either —
-- messages are append-only from this feature's own routes.
grant select, insert, update, delete on messages to authenticated;

-- --------------------------------------------------------------------------
-- outfits — gains an optional link back to the session that produced it.
-- --------------------------------------------------------------------------

-- Nullable, populated only for outfits `send_message` creates from this
-- feature onward (design-decisions.md §45). Every pre-existing row stays
-- null — never backfilled, never guessed; a guessed link would be exactly
-- the "silently defaulted" failure mode the handoff's own trap list names.
-- No RLS change needed: this is a plain column on an already-RLS'd table,
-- same reasoning 0010's migration used for its four new columns on
-- `outfits`.
alter table outfits add column thread_id uuid references sessions (id) on delete set null;
