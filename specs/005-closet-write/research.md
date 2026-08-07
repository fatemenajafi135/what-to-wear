# Research: Closet (write)

All items below were genuinely open (not covered by an existing pattern) or worth confirming
against feature 004/012/013's precedent before writing code.

## 1. Wear history shape and same-day semantics

**Decision**: `item_wears` table, one row per item per calendar day, unique on
`(item_id, worn_date)`. Recorded via upsert (`ON CONFLICT (item_id, worn_date) DO NOTHING`).

Full reasoning and alternatives: `docs/design-decisions.md` §22.1.

## 2. Delete confirmation

**Decision**: a bespoke confirmation dialog (native `<dialog>`/`showModal()`, matching
BottomSheet's own modal-semantics treatment), not a bare single-tap danger row.

Full reasoning and alternatives: `docs/design-decisions.md` §22.2.

## 3. Favourite storage

**Decision**: `favorite boolean not null default false` directly on `wardrobe_items`. Unlike
wear history, favourite is genuinely a single mutable flag with no history/audit requirement
anywhere in the spec or design system — a second table would be the "repository pattern with
one implementation" complexity the constitution's Quality Bar warns against. Toggled via
`PATCH`-shaped write (an UPDATE, not a separate resource).

**Alternatives considered**: an `item_favorites` join table (one row per user per favourited
item) — rejected, since `wardrobe_items` is already owned 1:1 by a single user (unlike a
shared/many-to-many favourites scenario), so a join table adds a join for no isolation or
audit benefit a column doesn't already give.

## 4. Category/Group field mapping in the edit form

Screen anatomy names six edit fields: Name, Category, Group, Fabric, Colour, Notes. But reading
`frontend/app/(app)/closet/[itemId]/page.tsx` (feature 004) shows the existing read view's field
*labels* are the inverse of the taxonomy's own naming: the row labeled "Category" displays
`item.category_group` (the coarse slot: top/bottom/outerwear/footwear/accessory) and the row
labeled "Group" displays `item.category` (the specific garment type, e.g. "blazer"). This
feature's edit form must match that existing read view exactly (design-system.md: "same field
order"), so it inherits the same inversion — not a new decision, just a fact the plan must not
silently normalize away.

Both labels resolve to a single stored column (`wardrobe_items.category`) — there is no separate
`category_group` column (constitution VI: the group is always derived via `categories.group_of`,
never stored, so it can't drift). `categories.py`'s own `CATEGORY_GROUPS` dict already makes
every bare group name a valid `category` value in its own right ("the six GROUP names must also
map to themselves" — the photo-extraction path already stores bare group names this way).

**Decision**: the edit form holds one local `category` string in its draft state.
- The "Category" `Chip` row (five options, the same `ClosetChipFilter` set the closet grid's
  filter chips already use — top/bottom/outerwear/footwear/accessory) sets `category` to the
  chosen group's bare name when tapped.
- The "Group" text `Input` directly below it edits the same `category` state as free text, for
  the specific type (e.g. typing "blazer" over a `category` that was just set to "outerwear" by
  the chip). Whichever the user touches last is what's submitted — no separate field, no
  precedence rule needed, because there is only one field.

This is the smallest change that satisfies "Category is Chips, the rest are text inputs" without
inventing a second stored column the frozen taxonomy (constitution VI) doesn't have room for.

**Alternatives considered**: storing `category_group` as its own column — rejected outright,
constitution VI freezes the taxonomy and explicitly reserves group-membership-in-two-places as
the exact drift the freeze exists to prevent (`categories.py`'s own docstring says so for
`catalog_items`; the same reasoning applies here).

## 5. Route shape

Four new routes on the existing `api/v1/routes/closet.py` router, alongside the two GETs from
004:

- `PATCH /closet/items/{item_id}` — body `WardrobeItemPatch` (already exists in `schema.py`,
  built for exactly this in 004/007's contract but never given a route until now) plus `name`
  handling already present on the model. Returns the updated `ClosetItemView`.
- `POST /closet/items/{item_id}/favorite` — toggles the boolean, returns
  `{ "favorite": bool }`. A toggle (not a body-carrying PATCH) because the client has no
  reliable local copy of the current value to flip client-side and round-trip (Item detail
  never displays it, §2.3) — the server is the only source of truth for what "toggle" means
  here, so it reads-then-flips-then-writes inside one transaction.
- `POST /closet/items/{item_id}/wear` — records today's wear (upsert, see §1), returns 204.
- `DELETE /closet/items/{item_id}` — hard delete, returns 204.

All four resolve a 404 for a missing/foreign item identically to the existing GET
(`get_wardrobe_item` returning `None` / zero rows affected), matching `contracts/closet.md`'s
established "never reveal which" shape from 004.

`ports.ClosetRepository` is untouched — every new method lives only on
`SupabaseClosetRepository`, matching how `get_wardrobe_item` itself was already added
structurally-extra in 004 (see that file's own docstring).

## 6. Frontend composition

- `ItemOverflowSheet` (new, in the `[itemId]` route folder) — owns the `BottomSheet` instance
  004 wired the trigger for but left with an empty `onClick`. Four rows in the design's fixed
  order: Edit, Log as worn today, Favorite, Delete (danger tone). "Log as worn today" is
  `disabled` when `!isOnline` per `useOnlineStatus()` (already imported in the page from 004).
- `ItemEditForm` (new) — replaces `ItemDetailCard` in place when editing; same field order,
  reuses `Chip`, `Input`, `Textarea`, `Button` (`width="full"`, i.e. `fullWidth`) exactly as
  shipped, no new form primitives per the handoff's Trap 5 / design-decisions §1.
- `DeleteConfirmDialog` (new) — the bespoke `<dialog>` from design-decisions §22.2, modeled on
  the calendar permission primer's own bespoke-card precedent (§18) rather than `BottomSheet`.
- No new client-side state library — local `useState` in the page component, matching how
  004 already manages `item`/`loading`/`notFound`/`error`.

## 7. Test strategy

Mirrors 004 exactly:
- `backend/tests/unit/test_supabase_closet_repository.py` — extend with mocked-session unit
  tests for the four new repository methods (mapping/upsert-arg shape only, no real DB).
- `backend/tests/integration/test_closet_routes.py` — extend with real-DB route tests for the
  four new routes: happy path, 404-for-foreign-item, 404-for-missing.
- `backend/tests/integration/test_wardrobe_rls.py` — extend `TestWardrobeItemsRLS` with
  UPDATE/DELETE isolation cases (004's version only proved SELECT), plus a new
  `TestItemWearsRLS` class for the new table, both using the same `authenticator`-role direct
  connection technique (BYPASSRLS makes testing through the app's own pooler connection give a
  false pass — see that file's own header).
- Frontend: component tests for `ItemOverflowSheet`, `ItemEditForm`, `DeleteConfirmDialog`
  (React Testing Library, matching `Chip.test.tsx`'s existing pattern), plus an update to the
  `[itemId]` page's own test coverage for the new interactive states.
