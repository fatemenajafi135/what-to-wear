# Data Model — Feature 011: Chat history

Full reasoning for every choice below: `docs/design-decisions.md` §44 (sessions), §45 (outfit
link), §46 (citation rendering). This is the shape, not the rationale.

## `sessions`

One row per pipeline thread, from its first user message onward.

| Column | Type | Notes |
|---|---|---|
| `id` | `uuid primary key` | **Is** `thread_id` — not a second generated id (§44). No `default gen_random_uuid()`: always supplied by the route, which already has the pipeline's own thread id. |
| `user_id` | `uuid not null` | JWT `sub`, matching every owned table's convention. |
| `created_at` | `timestamptz not null default now()` | Set once, on first insert. |
| `updated_at` | `timestamptz not null default now()` | Bumped on every subsequent message in this thread — this is "the date" a Chat-history row shows and the sort key for "most recently active first." |

RLS: `for all using (auth.uid() = user_id) with check (auth.uid() = user_id)`, `grant select,
insert, update, delete on sessions to authenticated` (0002 pattern).

## `messages`

One row per turn. Append-only from this feature's own routes (no update/delete route exists).

| Column | Type | Notes |
|---|---|---|
| `id` | `uuid primary key default gen_random_uuid()` | |
| `session_id` | `uuid not null references sessions(id) on delete cascade` | |
| `user_id` | `uuid not null` | Denormalized, matching `outfit_wears`/`item_wears` — RLS/ownership reads a flat column, no join needed. |
| `kind` | `text not null check (kind in ('user_message', 'styling_reply'))` | The §2 accommodation. 016 widens this exact constraint to add `conversational_turn`/`wrap_up` — no new column, no new table (research.md §4). `role` (user/assistant) is derived from `kind` in code, not stored — fully determined by it for every kind this feature or 016 names. |
| `text` | `text not null default ''` | The user's own message verbatim for `kind='user_message'`. For `kind='styling_reply'`: the pipeline's `reply_text`/honesty-fallback copy when the turn produced zero outfits; `''` when it produced one or more (that turn's content is the linked outfits below, not this column — no duplication of `rationale_with_citations` into a second place). |
| `outfit_ids` | `uuid[] not null default '{}'` | For `kind='styling_reply'`: the ids of outfits this turn produced (via `outfit_repository.create`, same request). Always `'{}'` for `kind='user_message'`. Plain array, no join table — same reasoning §32 already gave for `outfits.item_ids`: no per-row metadata needed, order is display order. |
| `created_at` | `timestamptz not null default now()` | Ordering key for the transcript. |

RLS: same shape as `sessions`. `grant select, insert, update, delete on messages to
authenticated` — `update`/`delete` granted for parity with every other owned table's grant
statement in this codebase (0002's own comment: "for all... feature 005 will need
insert/update/delete and shouldn't need a migration just to add these grants"), even though no
route in this feature issues either.

Index: `messages_session_id_created_at_idx on messages (session_id, created_at)` — the read
pattern for Session detail is always "every message for one session, in order."

## `outfits` (extended)

| Column | Type | Notes |
|---|---|---|
| `thread_id` | `uuid references sessions(id) on delete set null` | New, nullable. Set only for outfits created by this feature's updated `send_message` onward (§45). Every pre-existing row stays `null` — never backfilled, never guessed. |

No RLS change needed — `thread_id` is a plain column on an already-RLS'd table (same reasoning
`0010`'s own migration used for its four new columns on `outfits`).

## Derived values (never stored)

- **Session preview text** (Chat-history row, top line): the first `kind='user_message'` row's
  `text` for that session, truncated per the existing card-title truncation rule
  (design-system.md § Card title truncation).
- **Message count** (Chat-history row, second line): `COUNT(*) FROM messages WHERE session_id =
  :id` — total turns, both roles (spec.md Assumptions).
- **Outfit count** (Chat-history row's optional third line; Session detail's "View in Outfits"
  button): `COUNT(*) FROM outfits WHERE thread_id = :id` — always live, never cached (§45).

## Relationships

```text
sessions (1) ──< messages (many)         session_id, cascade delete
sessions (1) ──< outfits  (many, optional) thread_id, set null on session delete
```

No session-delete route exists in this feature (out of scope, spec.md Assumptions) — the cascade/
set-null behavior above is specified for schema correctness, not because anything in this slice
triggers it.

## State / lifecycle

A session has no explicit status field. Its only "state" is implicit in whether it has any
`messages` rows yet:

1. **Does not exist** — no thread, or a thread whose only interaction so far is the unsent
   greeting. Nothing in `sessions` or `messages`.
2. **Active/archived** (no distinction — §44) — at least one `user_message` row exists. Visible
   in Chat history from this point on, continuously, whether or not the user has tapped "New
   chat."

There is no third state and no separate "archived" flag — see §44's full reasoning for why one
is unnecessary.
