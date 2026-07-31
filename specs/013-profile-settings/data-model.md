# Data Model: Profile and Settings

## `user_profile`

One row per user, created lazily on first save (no row = every field at its default — FR-015).
Owned exclusively by feature 013. Nothing under `backend/src/whattowear/memory/` is touched or
extended by this table (see research.md and the handoff's §6 boundary).

| Column | Type | Constraint / default | Notes |
|---|---|---|---|
| `id` | `uuid` | PK, default `gen_random_uuid()` | |
| `user_id` | `uuid` | not null, unique, `references auth.users(id) on delete cascade` | One row per user — `unique` is what makes the upsert-on-first-save pattern (`insert ... on conflict (user_id) do update`) correct. |
| `style_tags` | `text[]` | not null, default `'{}'` | Subset of `{Classic, Minimal, Bold, Casual, Edgy}`. Validated in the Pydantic schema, not a Postgres `check` — matches this table's role as declared free-form-ish taste data, and keeps the enum change cost at the application layer (no migration needed to add a 6th tag later). |
| `colour_tags` | `text[]` | not null, default `'{}'` | Subset of `{Neutral tones, Jewel tones, Pastels, Monochrome, Earth tones}`. Same validation posture as `style_tags`. |
| `brands_to_avoid` | `text[]` | not null, default `'{}'` | Free text, no fixed vocabulary (spec.md Assumptions). Trimmed, de-duplicated at the API boundary before storage. |
| `body_shape` | `text` | nullable | One of `{hourglass, pear, rectangle, apple, inverted_triangle}` or `null` (unset). Single-select. |
| `gender` | `text` | nullable | One of `{woman, man, non_binary, prefer_not_to_say}` or `null`. Single-select. |
| `birth_date` | `date` | nullable | Must not be in the future (application-layer validation, FR — Body & size edge case). |
| `height` | `text` | nullable | Free-form `Select` value (e.g. `"5 ft 6 in"`) — design-system §4 lists Height as "text/select"; stored as the selected option's string, not decomposed into inches/cm (no computation over height exists anywhere in scope). |
| `top_size` | `text` | nullable | One of `XXS,XS,S,M,L,XL,XXL,XXXL`. |
| `bottom_size` | `text` | nullable | One of `00,0,2,4,...,20` (even sizes, design-system's stated `00–20` range). |
| `shoe_size` | `text` | nullable | Select value; exact option list decided in the `Select` options array in code (no numeric computation over it exists in scope). |
| `notifications_enabled` | `boolean` | not null, default `true` | Push notifications, defaults on (FR-009). The only field with no Edit/Done — commits immediately. |
| `created_at` | `timestamptz` | not null, default `now()` | |
| `updated_at` | `timestamptz` | not null, default `now()` | Maintained by `public.set_updated_at()` (0001_init.sql), per that migration's stated convention — no new trigger function written. |

### Row-level security

```sql
alter table user_profile enable row level security;

create policy "user_profile_select_own" on user_profile
  for select using (auth.uid() = user_id);

create policy "user_profile_modify_own" on user_profile
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
```

Per research.md §1: real from any path using the `authenticated` Postgres role with
`auth.uid()` populated (proven by a dedicated test); inert from the backend's own superuser
connection today (flagged gap, not this feature's fix). The repository layer independently
scopes every query by the JWT-verified `user_id` — the enforcement that actually protects data
through the app as currently wired.

### Validation rules (Pydantic, not Postgres `check` constraints)

- `style_tags`, `colour_tags`: each element must be in its fixed vocabulary; duplicates
  collapsed to a set.
- `brands_to_avoid`: each element trimmed of surrounding whitespace; duplicates (post-trim,
  case-sensitive exact match) dropped; empty strings rejected.
- `body_shape`, `gender`: must be in their fixed vocabulary or `null`.
- `birth_date`: must be `<= today` (server-side `date.today()` at request time) or `null`.
- `top_size`, `bottom_size`: must be in their fixed option list or `null`.
- All four PATCH payloads are **whole-section replaces** (the Edit/Done draft-commit model —
  there is no partial-field PATCH within a section; the frontend always sends every field the
  section owns).

### Why no separate entities for style/colour tags or sizes

Style tags, colour tags, and sizes are all closed, small, spec-fixed vocabularies — normalizing
them into lookup tables would be schema for values that are enumerated once in
`design-system.md` and change, if ever, via a code deploy, not a runtime admin action. Postgres
array-of-text plus application-layer vocabulary validation is proportionate; a lookup-table
join for a 5-item chip list would be the "speculative abstraction" the constitution's Quality
Bar prohibits (mirrors research.md §7's reasoning in `002-backend-foundation` against a
placeholder table).
