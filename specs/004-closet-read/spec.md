# Feature Specification: Closet (read)

**Feature Branch**: `004-closet-read`

**Created**: 2026-07-31

**Status**: Draft

**Input**: User description: "Closet (read). Users can see their closet: items exist in the
database, private per user, and render in the grid (/closet) and detail (/closet/:itemId)
screens with every specified state (loading, empty-first-run, empty-filtered, error,
offline). Read only — adding/editing/deleting items is feature 005, photo upload is feature
006. This slice also adds the first product table (wardrobe items + shared catalog) and
establishes the RLS convention (per-user row isolation, proven by a two-user test) that every
later table copies. Full brief at docs/handoffs/004-closet-read.md — read it first, it is
authoritative for scope."

## Clarifications

### Session 2026-07-31

- Q: Should Name and Notes be added as new optional fields on the frozen WardrobeItem model
  (schema.py), or handled another way? → A: Extend WardrobeItem — add `name: str | None` and
  `notes: str | None` as new optional fields, plus matching migration columns; the
  database-backed repository and API response carry them through like every other field.
- Q: The Closet screen's filter chips are All, Tops, Bottoms, Outerwear, Shoes, Accessories —
  five specific chips — but the frozen taxonomy has six category groups, including
  `full_body` (dresses, suits, jumpsuits, rompers), which has no chip of its own. Which chip
  should `full_body` items appear under? → A: Bottoms — `full_body` items filter under the
  Bottoms chip, matching the existing scoring-code precedent that treats `full_body` as a
  bottom-equivalent slot.
- Q: How many items should one page of the closet grid load before the manual "Load more"
  button appears? → A: 20, treated as a named config constant, not a literal.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Browse my closet (Priority: P1)

A signed-in user with items in their closet opens the Closet screen and sees their own items
laid out in a grid, nothing belonging to anyone else.

**Why this priority**: This is the entire feature's reason to exist — everything else
(filtering, detail, empty states) is secondary to "I can see what I own."

**Independent Test**: Sign in as a user with wardrobe items, open `/closet`, and confirm the
grid shows exactly that user's items and item count, at 2/3/4 columns across
mobile/tablet/desktop.

**Acceptance Scenarios**:

1. **Given** a signed-in user with wardrobe items, **When** they open `/closet`, **Then** the
   grid renders their items with a header subtitle stating the item count.
2. **Given** two different signed-in users each with their own items, **When** either opens
   `/closet`, **Then** they see only their own items — never the other user's.
3. **Given** a user on a viewport ≥1024px, **When** they open `/closet`, **Then** the grid
   renders as the wide list pane beside an empty item-detail pane showing placeholder copy.

---

### User Story 2 - Filter by category (Priority: P2)

A user narrows the closet grid to one category at a time using the chip row.

**Why this priority**: Useful once a closet has more than a handful of items, but the screen
is fully usable without it — it refines User Story 1 rather than replacing it.

**Independent Test**: Open `/closet` with items spanning multiple categories, select a
category chip, and confirm the grid shows only matching items; select a category with no
matching items and confirm the distinct empty-filtered state appears.

**Acceptance Scenarios**:

1. **Given** a closet with items in multiple category groups, **When** the user selects a
   category chip (single-select), **Then** the grid shows only items in that group and the
   header subtitle updates to the filtered count.
2. **Given** a category filter selected, **When** no owned item matches it, **Then** the
   screen shows the empty-filtered state ("No items match this filter" + a Clear-filter
   action) — never the first-run empty state.
3. **Given** a category filter is active, **When** the user chooses "All" or the
   Clear-filter action, **Then** the full closet reappears.

---

### User Story 3 - Open an item's detail (Priority: P1)

A user taps an item in the grid and sees its full details on its own screen.

**Why this priority**: Equally foundational to browsing — a grid of untitled placeholder
tiles is not usable on its own; the detail screen is where the item's identity is confirmed.

**Independent Test**: From `/closet`, open an item and confirm `/closet/:itemId` shows its
name, category, group, fabric, colour and notes; request a non-existent or someone else's
item id directly and confirm the error state.

**Acceptance Scenarios**:

1. **Given** a user's own item, **When** they open it from the grid, **Then**
   `/closet/:itemId` shows a photo placeholder block and a details card listing Name,
   Category, Group, Fabric, Colour and Notes as label/value pairs.
2. **Given** an item id that does not exist or does not belong to the requesting user,
   **When** the user requests `/closet/:itemId` directly, **Then** the screen shows the
   item-not-found error state with a way back to Closet — never another user's item data.
3. **Given** a viewport ≥1024px, **When** the user selects an item from the closet grid's
   wide list pane, **Then** its detail renders in the adjacent detail pane rather than
   navigating away from the grid.

---

### User Story 4 - See my closet is empty and know what to do (Priority: P2)

A brand-new user with no items yet opens Closet and understands why it's empty and what to do
next, distinctly from a user whose filter just happens to match nothing.

**Why this priority**: Correctness of the two empty states is explicitly called out as the
most common way this screen ships wrong; it matters for first-run experience but doesn't
block a user who already has items.

**Independent Test**: Sign in as a brand-new user with zero wardrobe items, open `/closet`,
and confirm the first-run empty state (not empty-filtered) appears with its own copy and
recovery action.

**Acceptance Scenarios**:

1. **Given** a user with zero wardrobe items and no filter active, **When** they open
   `/closet`, **Then** the screen shows "Your closet is empty. Add a few pieces and I'll
   start suggesting outfits." with an "Add your first item" action.
2. **Given** a user with zero wardrobe items, **When** the empty state renders, **Then** it
   is visually and textually distinct from the empty-filtered state (different copy,
   different action).

---

### User Story 5 - Recover from a failed or offline load (Priority: P3)

A user whose closet fails to load, or who is offline, gets a clear, correctly-scoped signal
rather than a blank or double-messaged screen.

**Why this priority**: Necessary for a production-quality screen, but the least frequently
hit path — most sessions load successfully.

**Independent Test**: Force a closet request to fail while online and confirm the screen-level
error state with Retry; then simulate offline and confirm the screen suppresses its own error
in favor of the global offline banner.

**Acceptance Scenarios**:

1. **Given** the closet request fails for a server-side reason while the client is online,
   **When** `/closet` attempts to load, **Then** the screen shows "Couldn't load your closet."
   with a Retry action.
2. **Given** the client has no network connection, **When** `/closet` would otherwise show
   its own error state, **Then** the screen suppresses that error and relies solely on the
   global offline banner — it does not show both.

---

### Edge Cases

- What happens when a user's closet has more items than one page? A manual "Load more" text
  button appears below the grid — not infinite scroll — with a loading caption while the next
  page fetches.
- What happens when a user switches category filters while a page is still loading? The
  in-flight request's result is discarded in favor of the new filter's request (no stale data
  flash).
- What happens when a signed-in user requests another user's item id directly (URL
  tampering)? Treated identically to a non-existent id — the not-found error state, no data
  leak, enforced at both the query and the database level.
- What happens to the catalog (shared, not owned by anyone)? It is read-only and visible to
  every signed-in user; this feature exposes it through the repository layer for the AI
  pipeline's consumption but does not add a catalog-browsing screen (no such screen exists in
  the design system's screen graph for this feature).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST persist wardrobe items in the database, each owned by exactly one
  user, using the frozen category-group and formality-level taxonomy (Constitution Principle
  VI) — no parallel scale, no renamed group — plus a `name` and a `notes` field, both
  optional, added additively to the shared `WardrobeItem` contract (not part of the frozen
  taxonomy itself).
- **FR-002**: System MUST let a signed-in user list only their own wardrobe items, never
  another user's, enforced independently at both the database row-security level and the
  query level.
- **FR-003**: System MUST render `/closet` with a sticky header (title, item-count subtitle),
  a single-select category filter row (All, Tops, Bottoms, Outerwear, Shoes, Accessories —
  where Bottoms includes both the `bottom` and `full_body` taxonomy groups), and a responsive
  grid (2 columns mobile / 3 tablet / 4 desktop) of item tiles using the design system's photo
  placeholder treatment.
- **FR-004**: System MUST render `/closet/:itemId` with a sticky header (back navigation, an
  overflow-menu trigger), a photo placeholder block, and a details card listing Name,
  Category (the derived category group), Group (the specific category, e.g. "Blazers"),
  Fabric, Colour and Notes.
- **FR-005**: System MUST distinguish the first-run empty state (zero items, no filter) from
  the empty-filtered state (items exist, current filter matches none) with different copy and
  a different recovery action, and MUST never show one where the other applies.
- **FR-006**: System MUST show a loading skeleton matching the design system's closet
  skeleton shape while items are being fetched.
- **FR-007**: System MUST show a screen-level error state with a retry action when a closet or
  item-detail request fails for a server-side reason while online.
- **FR-008**: System MUST suppress the screen-level error state while the client is offline
  and rely on the global offline banner instead, never showing both for the same failure.
- **FR-009**: System MUST show a manual "Load more" action (not infinite scroll) when
  additional items exist beyond the current page, using a page size of 20 items (a named
  config constant, not a literal).
- **FR-010**: System MUST render `/closet` as a two-pane master-detail layout at ≥1024px
  viewports (grid as the wide list pane, item detail in the adjacent pane, placeholder copy
  when nothing is selected), and as a single grid with push-navigation to item detail at
  narrower viewports.
- **FR-011**: System MUST expose an overflow-menu trigger on item detail's header; the menu's
  contents (Edit/Log as worn/Favorite/Delete) are out of scope for this feature and are wired
  as feature 005's responsibility.
- **FR-012**: System MUST provide a read-only, database-backed repository implementation
  satisfying the existing `ClosetRepository` protocol (`ports.py`) — listing a user's wardrobe
  items, listing the shared catalog, and returning preference-derivation inputs (empty in
  this feature; feature 010's territory) — without altering the protocol or removing the
  existing fixture-backed implementation the eval harness depends on.
- **FR-013**: System MUST expose authenticated read routes for a user's own wardrobe items and
  a single item's detail, backed by generated OpenAPI types on the frontend with no
  hand-written duplicate type.
- **FR-014**: System MUST render every specified closet and item-detail state in both light
  and dark themes.

### Key Entities

- **Wardrobe item**: A single garment owned by exactly one user — category (with a derived
  category group), colors, fabric, warmth, season, formality, pattern, fit, an optional name,
  optional notes, and an optional photo reference (no real photo exists yet in this feature; a
  placeholder renders in its place). Private to its owner.
- **Catalog item**: A garment in the shared catalog, structurally identical to a wardrobe item
  but not owned by any single user — readable by every signed-in user, not user-editable.
- **User**: The opaque identity established by feature 003's verified session; no local
  `users` table exists — ownership is expressed by an item's `user_id` matching the verified
  caller.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A signed-in user with existing items sees their own closet grid rendered within
  a single request cycle, with zero instances of another user's item appearing, across
  repeated verification with two distinct accounts.
- **SC-002**: 100% of direct requests for an item id that is missing or not owned by the
  caller resolve to the not-found error state, never to another user's item data.
- **SC-003**: Every one of the closet and item-detail screens' specified states (loading,
  empty-first-run, empty-filtered, error, offline) is visually verifiable in both themes at
  320/768/1024/1440px, with no missing or visually broken state.
- **SC-004**: Row-level isolation is demonstrated by an automated test in which two distinct
  users each read only their own rows, with no manual/visual-only verification standing in
  for it.

## Assumptions

- Photo upload, storage and vision extraction do not exist yet (feature 006); every item tile
  and detail photo block renders the design system's diagonal-stripe placeholder regardless
  of whether a `photo_path` is present.
- Adding, editing and deleting items (feature 005) are out of scope; this feature ships a
  read-only repository and read-only routes. The item-detail overflow menu's trigger is wired
  but its sheet contents are feature 005's responsibility.
- Preference/feedback derivation data (feature 010) does not exist yet; the repository's
  `get_derivation_inputs` returns an empty result in this feature, matching the existing
  fixture-backed implementation's documented behavior.
- This feature runs against the local Supabase project only; no cloud project is provisioned
  or targeted.
- The two-pane desktop layout and responsive breakpoints follow `design/design-system.md` §5
  exactly; this spec does not restate those values, only the behavior they must satisfy.
- Frontend-to-backend HTTP calls for closet data are new to the project (feature 003 only
  exercised a proof-of-concept endpoint); this feature is the first to establish the
  OpenAPI-generated-types consumption pattern Constitution Principle VII requires.
