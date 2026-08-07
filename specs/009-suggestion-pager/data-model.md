# Data model — Feature 009: Outfit suggestion pager

## Database — `outfits` table (migration `0009`)

Full schema and rationale: `docs/design-decisions.md` §32.

| Column | Type | Notes |
|---|---|---|
| `id` | `uuid primary key default gen_random_uuid()` | |
| `user_id` | `uuid not null` | Verified JWT `sub`, same convention as `wardrobe_items`. |
| `occasion` | `text not null` | `Context.occasion` at save time — frozen, not re-derived on read. |
| `meta_line` | `text not null` | Precomputed `"{occasion} · {formality|weather}"` string (data-model §2 below) — frozen at save time so a later read never needs `Context` again. |
| `rationale_text` | `text not null` | Plain text, no citation markers (never had any — §33/§35). |
| `match_label` | `text not null check (match_label in ('great', 'good', 'might_work'))` | The label only — never the float (Constitution II/VI: no parallel numeric scale). |
| `item_ids` | `uuid[] not null` | Wardrobe item ids, order = display order. No array-level FK (Postgres has none); ownership is validated at insert time by the route, not by a DB constraint. |
| `favorite` | `boolean not null default true` | Existence + `true` = "saved and favorited" (the only state the heart's first tap can produce). Second tap flips this the same way `wardrobe_items.favorite` already toggles — never deletes the row. |
| `created_at` / `updated_at` | `timestamptz not null default now()` | Same `set_updated_at` trigger convention as every other table. |

RLS: `for all using (auth.uid() = user_id) with check (auth.uid() = user_id)`, plus `grant
select, insert, update, delete on outfits to authenticated` (the `0002`-documented non-optional
GRANT). Proven by a two-user isolation test.

No `thread_id` — out of scope (research.md §1); no `photo_url`/resolved-item snapshot — items are
re-resolved from `wardrobe_items` by id at read time, same convention as `_resolve_outfit` today.

## Backend — route-local models (`api/v1/routes/recommend.py`)

### `StylingOutfit` (nested in `SendMessageResponse`, changed)

| Field | Type | Notes |
|---|---|---|
| `id` | `str \| None` | **New.** The saved-outfit id once saved this session, else `None`. Drives the heart's filled/outline state — no separate "is this favorited" fetch exists, since the frontend already knows (it made the save call itself, or hasn't). |
| `rationale_text` | `str` | **Changed**: no more embedded `[n]` markers — plain text, always (§33/§35). |
| `items` | `list[StylingReplyItem]` | Unchanged shape, resolved per outfit (now N times per response instead of once). |
| `match_label` | `Literal["great", "good", "might_work"]` | Unchanged derivation (`match_label()`), now applied per outfit instead of only to `outfits[0]` — an outfit below the floor is dropped from the list entirely rather than included with `match_label = None`. |
| `meta_line` | `str` | **New.** `"{occasion} · {formality|weather}"`, computed once per response from `SuggestResult.context` and repeated identically on every card in that response's list (research.md §3). |

### `SendMessageResponse` (changed)

| Field | Type | Notes |
|---|---|---|
| `thread_id` | `str` | Unchanged. |
| `reply_text` | `str \| None` | Unchanged — still the pipeline's `note`/generic fallback, still only set when `outfits` is empty. |
| `outfits` | `list[StylingOutfit]` | **Replaces** `outfit: StylingOutfit \| None`. Empty list = the Empty group-state (research.md §4); never `None`. |
| ~~`citations`~~ | — | **Removed.** No remaining renderer (research.md §2/§4). |

### `SaveOutfitRequest` (new, `POST /recommend/outfits`)

| Field | Type | Notes |
|---|---|---|
| `occasion` | `str` | Copied from the `StylingOutfit`/response the client already has in hand — no re-fetch. |
| `meta_line` | `str` | Same. |
| `rationale_text` | `str` | Same. |
| `match_label` | `Literal["great", "good", "might_work"]` | Same. |
| `item_ids` | `list[str]`, min length 1 | Validated server-side: every id MUST appear in `repository.list_wardrobe_items(user_id)` for the caller, or the request is rejected (`422`) — a save can never record an item the caller doesn't own (Constitution IV), independent of whatever the client sent. |

### `SavedOutfitResponse` (new, shared by both outfit routes)

| Field | Type | Notes |
|---|---|---|
| `id` | `str` | |
| `favorite` | `bool` | Current state after this call. |

### `POST /recommend/outfits/{outfit_id}/favorite` (new)

No body. Toggles `favorite` on the caller's own row (`404` if the id doesn't belong to the
caller — same ownership-scoped `UPDATE ... WHERE user_id = ... RETURNING` pattern as
`toggle_closet_item_favorite`). Returns `SavedOutfitResponse`.

## Backend — repository (`repositories/supabase_outfits.py`, new)

`SupabaseOutfitRepository`, mirroring `SupabaseClosetRepository`'s session/RLS-claim pattern:

- `create(user_id, ...) -> str` — inserts one row, returns its id. Caller (the route) has already
  validated item ownership before calling this.
- `toggle_favorite(user_id, outfit_id) -> bool | None` — same `RETURNING`-flip shape as
  `supabase_closet.py::toggle_favorite`; `None` when the row doesn't belong to `user_id`.

No `list`/`get` method in this feature — nothing in scope reads outfits back (010's job).

## Frontend — pager state (client-side only, component-local)

| Field | Type | Notes |
|---|---|---|
| `outfits` | `StylingOutfit[]` | From the response, as-is — order is display order. |
| `index` | `number` | Current visible card, `0`-based. Reset to `0` whenever a new `outfits` array arrives (a new reply). |
| `savedIds` | `Record<number, string>` (keyed by array index) | Populated as the user saves cards this session — not fetched, not persisted; matches `StylingOutfit.id` starting `null`. |
| `feedback` | `Record<number, "up" \| "down" \| null>` | Per-card, component-local, never sent anywhere but the two feedback-toggle handlers (FR-011/FR-012). |

`SuggestionPager` owns `index`; `OutfitCard` is presentational, receiving its own outfit, saved
id, and feedback state plus callbacks — no card owns pager-group state itself.
