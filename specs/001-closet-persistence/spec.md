# Feature Specification: Closet Persistence

**Feature Branch**: `001-closet-persistence`

**Created**: 2026-07-15

**Status**: Draft

**Input**: User description: "A user's closet is persistent, private to them, and editable. A user can view their closet, add an item by picking from a shared pre-built catalog, correct any attribute of an item, and remove an item. Accessories are first-class items alongside clothing. Every item carries a slot, a category within that slot, colors with hex values, a fabric, a warmth rating, a formality rating, and applicable seasons. Existing wardrobe retrieval must read from this persistent closet instead of the fixture file, with no change to retrieval behaviour or eval scores. Photo upload is out of scope. Catalog selection is the only way to add items."

## Clarifications

### Session 2026-07-15

- Q: Should "slot" (the broad bucket: top, bottom, full_body, outerwear,
  footwear, accessory) be its own stored, independently-correctable field, or
  stay derived from `category` on read, matching the existing code? → A:
  Stays derived from `category`. There is no separate stored/correctable slot
  field — correcting `category` is what changes which bucket an item falls
  into.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - View my closet (Priority: P1)

A user opens their closet and sees every item they currently own, with all of its
attributes, so they know what they have to work with before asking for an outfit.

**Why this priority**: Without a reliable view of what's actually owned, nothing
else in the system (styling suggestions, corrections, removals) has anything to
act on. This is also the flow that existing wardrobe retrieval depends on.

**Independent Test**: Seed a closet with a known set of items and confirm every
item and every one of its attributes (category — whose slot/bucket is derived
automatically, colors, fabric, warmth, formality, seasons) is visible, with no
items from any other user's closet appearing.

**Acceptance Scenarios**:

1. **Given** a user with 12 items in their closet, **When** they view their
   closet, **Then** all 12 items appear with their full attribute set.
2. **Given** a user with an empty closet, **When** they view their closet,
   **Then** they see an empty closet, not an error.
3. **Given** two users each with their own items, **When** either user views
   their closet, **Then** they see only their own items.

---

### User Story 2 - Add an item from the shared catalog (Priority: P1)

A user browses a shared, pre-built catalog and adds an item to their own
closet, so their closet reflects what they actually own without uploading a
photo.

**Why this priority**: This is the only way to populate a closet in this
feature, so it is as foundational as viewing — a closet with no way to add
items is a dead end.

**Independent Test**: From a populated catalog, select one item and confirm it
now appears in the user's own closet view with the same attributes, and that
it does not appear in any other user's closet.

**Acceptance Scenarios**:

1. **Given** a shared catalog with items available, **When** a user selects
   one, **Then** that item appears in their closet with all of its attributes
   intact.
2. **Given** a user has added an item from the catalog, **When** the catalog
   item is later changed, **Then** the copy already in the user's closet is
   unaffected (the closet holds its own copy, not a live reference).

---

### User Story 3 - Correct an item's attributes (Priority: P2)

A user notices an item in their closet has a wrong attribute (e.g. the wrong
color or formality) and corrects it, so their closet stays accurate.

**Why this priority**: Catalog data can be wrong or a user's judgment of their
own item can differ from the catalog default; this keeps the closet trustworthy
without requiring removal and re-adding.

**Independent Test**: Take an item already in a closet, change one attribute,
and confirm the new value is what's shown and used afterward, while every
other attribute of that item is unchanged.

**Acceptance Scenarios**:

1. **Given** an item in a user's closet, **When** the user corrects its
   formality rating, **Then** the closet view reflects the new value and no
   other attribute changes.
2. **Given** an item in a user's closet, **When** the user attempts to set
   any constrained attribute to an invalid value — formality or a season
   outside the controlled vocabulary, a warmth outside 0-5, or a malformed
   hex color — **Then** the correction is rejected with a clean validation
   error and the item keeps its prior value.
3. **Given** an item in a user's closet, **When** the user corrects its
   category to a value the system doesn't recognize, **Then** the correction
   is accepted (categories are open-ended) and the item's slot/bucket falls
   back to "accessory" until a recognized category is set.

---

### User Story 4 - Remove an item (Priority: P3)

A user removes an item they no longer own from their closet.

**Why this priority**: Lower priority than the above three — a closet that can
only grow is usable for a demo, but removal is needed for the closet to stay
accurate over time.

**Independent Test**: Remove one item from a closet containing several, and
confirm it no longer appears in that user's closet view while the remaining
items are untouched.

**Acceptance Scenarios**:

1. **Given** a user's closet with several items, **When** they remove one,
   **Then** it no longer appears in their closet and every other item is
   unaffected.

---

### Edge Cases

- What happens when a user tries to view, correct, or remove an item that
  belongs to a different user? The system MUST treat it as not found for them.
- What happens when the catalog has zero items available (not yet seeded)?
  Add-from-catalog MUST show an empty catalog, not an error.
- What happens when a correction is attempted on an item mid-removal or a
  removal is attempted twice? The second operation on an already-removed item
  MUST be treated as already-removed, not a crash.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST let a user view every item currently in their own
  closet, and MUST NOT show items belonging to any other user.
- **FR-002**: System MUST let a user add an item to their own closet by
  selecting it from a shared, pre-built catalog.
- **FR-003**: System MUST NOT support photo upload as a way to add an item in
  this feature; catalog selection is the only path.
- **FR-004**: Every closet item MUST carry: a category (a free-form value;
  its slot/bucket — top, bottom, full_body, outerwear, footwear, or accessory
  — is derived automatically from category and is not a separately stored or
  corrected field), one or more colors expressed as hex values, a fabric, a
  warmth rating, a formality rating, and one or more applicable seasons.
- **FR-005**: Accessories MUST be stored and treated as first-class closet
  items alongside clothing — not a separate or lesser-featured category.
- **FR-006**: System MUST let a user correct any attribute of an item already
  in their own closet.
- **FR-007**: System MUST reject a correction that sets any constrained
  attribute to an invalid value, returning a clean validation error and
  leaving the item's prior value intact: `formality` or `season` outside its
  controlled vocabulary, `warmth` outside 0-5, or a `colors` entry that is
  not a valid hex value. Category corrections MUST accept any value,
  consistent with categories being open-ended; an unrecognized category MUST
  safely fall back to the "accessory" slot/bucket rather than being rejected.
- **FR-008**: System MUST let a user remove an item from their own closet.
- **FR-009**: A closet's contents MUST persist across sessions — closing and
  reopening, or logging out and back in, MUST NOT lose or alter closet data.
- **FR-010**: The shared catalog MUST be readable by every user; catalog
  contents are not user-editable through this feature.
- **FR-011**: When an item is added from the catalog, the closet MUST store
  its own independent copy of that item's attributes, not a live reference to
  the catalog entry.
- **FR-012**: Existing wardrobe retrieval behavior MUST be unchanged by this
  feature: given equivalent closet contents, retrieval results and evaluation
  scores MUST match current fixture-based behavior.

### Key Entities

- **Closet Item**: A single garment or accessory a specific user owns. Carries
  category (its slot/bucket derived automatically from category), colors,
  fabric, warmth, formality, seasons, and belongs to exactly one user.
- **Catalog Item**: A shared, pre-built item definition, in the same shape as
  a Closet Item but with no owning user, available for any user to add from.
- **User**: The person who owns a closet; a closet's contents are visible and
  editable only by its owning user.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can view their complete closet contents in a single
  interaction, regardless of closet size, up to at least 200 items.
- **SC-002**: An item added from the catalog appears in the user's closet
  view immediately, with no manual refresh step beyond the add action.
- **SC-003**: 100% of items in any closet display all six required attributes
  (category, colors, fabric, warmth, formality, seasons), each with its
  slot/bucket correctly derived, with none missing.
- **SC-004**: A user can correct a wrongly-set attribute or remove an unwanted
  item in a single action each, with the change visible immediately.
- **SC-005**: For the existing golden evaluation set, style-suggestion
  retrieval results and scores are identical before and after switching from
  the fixture file to persistent closet storage.

## Assumptions

- **Terminology**: this spec uses "closet" as the user-facing product word.
  In code, the API, and the database the same concept is called "wardrobe"
  (`wardrobe_items`, `/wardrobe/items`, the frozen `WardrobeItem` contract) —
  see plan.md / research.md → "Terminology". They are the same thing; "closet"
  is display copy, "wardrobe" is the code identifier.
- The item taxonomy follows the project constitution's frozen schema
  (`schema.py` / `categories.py`): category groups are `top`, `bottom`,
  `full_body`, `outerwear`, `footwear`, `accessory`; formality is the
  six-value enum (`casual` → `black_tie`); warmth is 0-5. This spec uses that
  taxonomy rather than the earlier draft wording of `one-piece`/`outer` slots
  or a 1-5 numeric formality scale.
- `fabric` is a new attribute not present in the current schema. Adding it is
  an additive schema change, not a rename or removal of an existing frozen
  field, and will need an explicit migration at planning time.
- Standard per-account access control enforces "private to them"; the specific
  authentication technology is a planning-phase decision, not a spec concern.
- Item removal is a hard delete for this feature. No other feature yet
  references closet item ids after deletion, so retention rules for deleted
  items are out of scope here.
- How the shared catalog is seeded (source data, process) is a planning-phase
  concern, not specified here.
- Selecting the same catalog item more than once creates multiple independent
  closet items (e.g. two identical white t-shirts are two closet items, not
  one deduplicated entry) — consistent with how a real closet can hold
  duplicates.
