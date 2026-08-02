# Data Model — Feature 010: Outfits gallery + detail

## Entities

### `outfits` (extends migration `0009`)

| Column | Type | Notes |
|---|---|---|
| `id` | `uuid` PK | unchanged (0009) |
| `user_id` | `uuid` | unchanged (0009) |
| `occasion` | `text` | unchanged (0009) |
| `meta_line` | `text` | unchanged (0009) |
| `rationale_text` | `text` | unchanged (0009) — stays plain, never markers (§38) |
| `match_label` | `text` (enum check) | unchanged (0009) |
| `item_ids` | `uuid[]` | unchanged (0009) |
| `favorite` | `boolean` | unchanged (0009) |
| `created_at`/`updated_at` | `timestamptz` | unchanged (0009) |
| `title` | `text not null` | **NEW.** User-editable, shown on gallery card + detail `TopHeader`. Backfilled from `occasion` for every pre-010 row (design-decisions.md §36's own seam), then `not null`. Rejects empty/whitespace-only on rename (FR-006). |
| `rationale_with_citations` | `text not null default ''` | **NEW.** Same content as `rationale_text` but with `[n]` markers appended per cited rationale segment, numbered in first-appearance order (§38). Empty-string default is itself a valid "nothing cited" state — renders as `rationale_text` with no markers. |
| `citations` | `jsonb not null default '[]'` | **NEW.** `[{number: int, text: string}]` — the numbered rule-list rows the markers refer to. `text` is the cited rule's human-readable source label (`CitedSource.source`), not styling guidance itself. |
| `dimension_scores` | `jsonb not null default '[]'` | **NEW.** `[{dimension: ScoreDimension, value: float}]`, at most one entry per `SCORE_DIMENSIONS` value. `value` is never rendered as text — only used to compute a bar's fill width (§ Scores; design-decisions.md §38's explicit transmit-vs-render distinction). |

Constraint added: `unique (id, user_id)` — composite-FK target for `outfit_wears` below (same
pattern `0005` used for `wardrobe_items`/`item_wears`).

### `outfit_wears` (new table)

| Column | Type | Notes |
|---|---|---|
| `id` | `uuid` PK, `gen_random_uuid()` | |
| `outfit_id` | `uuid not null` | |
| `user_id` | `uuid not null` | denormalized, same convention as `item_wears` |
| `worn_date` | `date not null default current_date` | |
| `created_at` | `timestamptz not null default now()` | |

Constraints: `unique (outfit_id, worn_date)` (idempotent logging, matching `item_wears`'
`unique (item_id, worn_date)`); `foreign key (outfit_id, user_id) references outfits (id, user_id)
on delete cascade` (forged-pair rejection at the DB level, matching `item_wears`' FK to
`wardrobe_items`). RLS: `for all using (auth.uid() = user_id) with check (auth.uid() = user_id)`.
GRANT: `select, insert, update, delete ... to authenticated` (the `0002` pattern, non-optional).

No schema change to `item_wears` itself — logging an outfit as worn reuses its existing
`unique (item_id, worn_date)` upsert unchanged, once per item still owned by the caller
(design-decisions.md §39).

## Validation rules

- **Title**: non-empty after `.strip()`; enforced at the route (422 on empty/whitespace) before
  it reaches the repository — matches the existing project convention of validating request
  bodies at the route, not relying on a DB constraint alone for a user-input shape check.
- **`item_ids` ↔ pipeline match** (save route only, §38): the specific `ScoredOutfit` used for
  citations/scores is the one in `last_result.outfits` whose `.items` list equals
  `SaveOutfitRequest.item_ids` **exactly, in order** — not a set comparison. No match → proceed
  with empty citations/scores (degrade, not fail).
- **Ownership**: every read/write filters `WHERE user_id = :user_id` in the repository (existing
  convention, `supabase_outfits.py`/`supabase_closet.py`) — never left to RLS alone, since the
  pooler role has BYPASSRLS. The checkpointer read additionally checks `state["user_id"]` before
  trusting `last_result` (§38) — this table has no RLS of its own to fall back on.
- **Log-worn item skip**: an `item_id` in `outfit.item_ids` not present in the caller's current
  `wardrobe_items` is silently skipped for the `item_wears` insert (not an error) — the outfit's
  own `outfit_wears` row is still written regardless.

## State transitions

- **Favorite**: `false ↔ true` via the existing `toggle_favorite` UPDATE...RETURNING (0009,
  unchanged) — reachable from gallery card heart, detail header heart, and the overflow sheet's
  Favorite/Unfavorite row; all three read/write the same column, so they're inherently in sync
  (no client-side favorite cache needed, matching 009's `StylingOutfit.id` precedent for why none
  is needed here either).
- **Title**: any non-empty string → any other non-empty string, no history kept.
- **Delete**: `outfits` row exists → row and its `outfit_wears` rows (`on delete cascade`) are
  permanently removed. One-way, no soft-delete/undo (design-decisions.md §40) — gated by the
  bespoke confirmation dialog client-side; the DELETE route itself performs the delete
  unconditionally once called (confirmation is a UI gate, not a second server-side step, matching
  005's own delete route shape exactly).
- **Wear log**: absent → present for `(outfit_id, today)`, idempotent thereafter for the rest of
  that calendar day (upsert `DO NOTHING` on conflict, both tables).

## Per-screen states (Constitution VIII: loading/error/empty/offline, all mandatory)

| Screen | Loading | Empty | Error | Offline |
|---|---|---|---|---|
| Outfits gallery | Two 100px skeleton blocks (design-system.md's own Outfits skeleton spec, unchanged) | `outfits.empty.first_run.*` copy verbatim (0 outfits saved, ever) | `outfits.error.*` copy + Retry | Global offline banner; screen-level error suppressed while offline (§6's "offline wins for messaging" rule) |
| Outfit detail | One card: 2-col item-thumbnail skeleton grid + one description-shaped bar (design-system.md's own Outfit detail skeleton spec) | N/A (detail always has exactly one outfit or 404s) | Not-found/removed copy + back-to-Outfits action (mirrors `item_detail.error.*`'s pattern, no exact copy specified for outfits in design-system.md's Auth/Recommend/Closet/Item-detail/Add-item/Outfits/Calendar/Chat-history/Profile table — this feature adds the missing `outfit_detail.error.*` pair, worded to match that table's existing voice/pattern exactly) | Same global-banner suppression rule; wear/rename/favorite/delete actions disabled while offline (FR-014) |

No `empty-filtered` state for the gallery in this feature — filtering doesn't ship (§41), so only
the true "zero outfits ever saved" empty state exists; "Most worn"/"Favorited first"/"Date added"
sorting never produces zero results from a non-empty list, so no filtered-empty case can occur.

## API-facing shapes (see `contracts/recommend-outfits.md` for full request/response bodies)

- `OutfitSummary` (gallery card): `id, title, match_label, item_thumbnails (≤4, +N indicator),
  favorite, created_at`.
- `OutfitDetail`: `id, title, occasion, items (full resolved list), rationale_text,
  rationale_with_citations, citations, dimension_scores, match_label, favorite, created_at`.
- `SaveOutfitRequest` gains `thread_id: str` (required) — see §38.
