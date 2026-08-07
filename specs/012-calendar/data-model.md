# Data Model: Calendar

Migration `0004`. Three tables — see `research.md` §1-3 for why each exists.

## `calendar_connections`

Owned, private. Exactly zero or one row per user (`user_id` is the primary key, not a
separate `id` — an upsert target, not a log of connection attempts).

| Column | Type | Notes |
|---|---|---|
| `user_id` | `uuid primary key` | The verified JWT `sub` claim; no local `users` table, matching `0001_init.sql`'s convention |
| `access_token_encrypted` | `text not null` | `Fernet`-encrypted (research.md §2); never returned by any API response |
| `refresh_token_encrypted` | `text not null` | Same encryption; used to mint a new access token on expiry |
| `token_expires_at` | `timestamptz not null` | The *access* token's expiry — refresh tokens are long-lived and not separately tracked |
| `connected_at` | `timestamptz not null default now()` | Set once, at first successful connect |
| `updated_at` | `timestamptz not null default now()` | trigger: `public.set_updated_at()`, bumped on every token refresh |

**RLS**: enabled. `calendar_connections_modify_own`: `for all using (auth.uid() = user_id)
with check (auth.uid() = user_id)` — same shape as `wardrobe_items_modify_own` (`0002`).

## `calendar_oauth_attempts`

Owned, private, ephemeral. Zero-to-many short-lived rows per user (one per in-flight connect
attempt; deleted on completion). Not exposed through any route response — internal to the
connect flow only (research.md §3).

| Column | Type | Notes |
|---|---|---|
| `state` | `uuid primary key default gen_random_uuid()` | Returned to the client as the OAuth `state` param; looked up (not filtered by user) at finish time, then ownership-checked |
| `user_id` | `uuid not null` | Who started this attempt |
| `code_verifier` | `text not null` | The PKCE verifier, plaintext — useless without the matching short-lived Google authorization code (research.md §3) |
| `created_at` | `timestamptz not null default now()` | No expiry sweep in this slice (research.md §3, accepted gap) |

**RLS**: enabled. `calendar_oauth_attempts_modify_own`: `for all using (auth.uid() = user_id)
with check (auth.uid() = user_id)`.

## `picked_events`

Owned, private. Exactly zero or one row per user (`user_id` primary key — a snapshot, not a
history).

| Column | Type | Notes |
|---|---|---|
| `user_id` | `uuid primary key` | |
| `google_event_id` | `text not null` | Google's own event id — reference only, not a FK (no local events table) |
| `title` | `text not null` | Snapshotted at pick time; not re-fetched live |
| `start_time` | `timestamptz not null` | Snapshotted |
| `location` | `text` | nullable — Google Calendar events may have no location |
| `picked_at` | `timestamptz not null default now()` | |

**RLS**: enabled. `picked_events_modify_own`: `for all using (auth.uid() = user_id) with
check (auth.uid() = user_id)`.

**Cleared** (row deleted) whenever `calendar_connections` is disconnected for that user — per
spec FR-013 — and overwritten (upsert) whenever a new event is picked.

## Grants

All three tables need the same table-level `grant select, insert, update, delete ... to
authenticated` that `0002` documents as required — RLS restricts rows, the grant is what lets
the `authenticated` role touch the table at all (silently unreachable otherwise; see `0002`'s
own comment on this exact failure mode).

## Non-persisted: calendar event (read model)

Not a table — fetched live from Google on each `GET /api/v1/calendar/events` call
(research.md §5) and returned directly as a response model:

| Field | Type | Notes |
|---|---|---|
| `google_event_id` | `str` | Google's event id |
| `title` | `str` | |
| `start` | `datetime` (ISO 8601, UTC) | Relative-day/time label is computed client-side (research.md §7) |
| `location` | `str \| None` | |

## Token lifecycle (not a table — a behavior)

1. **Connect**: `calendar_connections` row is inserted (upsert) with the initial access +
   refresh token pair and `token_expires_at`.
2. **Read** (any call needing a live Google API request): if `token_expires_at` has passed,
   the stored refresh token is exchanged for a new access token first; the row is updated
   in place (`access_token_encrypted`, `token_expires_at`, `updated_at`).
3. **Refresh failure**: the row (and the user's `picked_events` row) is deleted; the caller
   sees the same shape as "never connected" (research.md §6).
4. **Disconnect**: the row (and the user's `picked_events` row) is deleted directly — no
   token revocation call to Google is made in this slice (out of scope; Google's own token
   expiry/rotation is the backstop, and revocation is a reasonable follow-up, not a
   correctness requirement of this feature).
