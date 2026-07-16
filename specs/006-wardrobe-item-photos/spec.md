# Feature Specification: Wardrobe Item Photos

**Feature Branch**: `006-wardrobe-item-photos`

**Created**: 2026-07-16

**Status**: Draft

**Input**: User description: "We have a card for each cloth item, showing
the item's name, fabric, color, etc. It would be helpful to also show their
pictures. If the picture exists in storage, use it; otherwise, just show
the color — a small change in the wardrobe item is needed for this. If the
image exists, we also still want the color/hex and pattern shown."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See a real photo of an owned item, not just its color (Priority: P1)

A user viewing their closet sees, for each item that was added by photo,
the actual photo of that garment on its card — not just a color swatch.
Items added from the shared catalog (which were never photographed)
continue to show only their color swatches, exactly as today. Whether or
not a photo is shown, the item's color, hex value, and pattern are still
shown alongside it — the photo is additive, not a replacement for that
information.

**Why this priority**: This is the entire feature — there's no smaller
independently valuable slice to split it into.

**Independent Test**: Add one item by photo and one item from the catalog.
View the closet. The photo-added item shows its real photo plus its
color/pattern info; the catalog item shows only its color swatch, as
before.

**Acceptance Scenarios**:

1. **Given** an item that was added via the photo-upload flow, **When**
   its card is displayed, **Then** the item's actual photo is shown,
   alongside its color swatch(es)/hex and pattern (unchanged from today).
2. **Given** an item that was added from the shared catalog, **When** its
   card is displayed, **Then** only the color swatch(es) are shown,
   exactly as today — no broken image, no placeholder implying a photo
   should exist.
3. **Given** an item that was added via photo upload but whose photo can't
   currently be loaded (e.g. a transient network/storage issue), **When**
   its card is displayed, **Then** it falls back to showing just the color
   swatch(es), the same as an item with no photo — never a broken-image
   icon or an error.

---

### Edge Cases

- What happens when the underlying photo file is later removed at the
  storage level, outside the app? Falls back to swatch-only display (same
  as Acceptance Scenario 3).
- What happens for an item that was added by photo *before* this feature
  existed? Its photo location was never captured at upload time, so it
  displays swatch-only — same as a catalog item. Not retroactively
  backfillable: the original upload's photo path was already discarded
  and never stored anywhere, so there's nothing to recover it from.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST persist the storage location of an item's
  photo when the item is created via the photo-upload flow.
- **FR-002**: The system MUST include that photo location in the item data
  returned to the closet view, when one exists.
- **FR-003**: The closet view MUST display an item's real photo when a
  photo location exists for that item.
- **FR-004**: The closet view MUST display only the item's color
  swatch(es) — the current behavior — when no photo location exists for
  that item (catalog-sourced items, and any photo-uploaded items created
  before this feature).
- **FR-005**: The closet view MUST continue to display an item's color
  swatch(es)/hex and pattern regardless of whether a photo is also shown.
- **FR-006**: If a photo location exists but the photo itself cannot
  currently be retrieved, the closet view MUST fall back to the
  swatch-only display rather than showing a broken image or an error.
- **FR-007**: A photo MUST remain visible only to the user who owns that
  item — no change to the existing per-user access restriction on stored
  photos.

### Key Entities *(include if feature involves data)*

- **Wardrobe item**: gains one new optional attribute, its photo's storage
  location — present only for items added via the photo-upload flow,
  absent for catalog-sourced items.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user who has added at least one item by photo sees that
  item's real photo on their closet view, with no additional action
  required.
- **SC-002**: No existing closet item's display (a catalog item, or an
  item added by photo before this feature shipped) changes in any way
  beyond what's explicitly in scope here.
- **SC-003**: A photo that's temporarily unavailable never produces a
  broken image or an error state in the closet view.

## Assumptions

- Only items added through the photo-upload flow can have a photo;
  catalog items are out of scope for photos entirely — the shared catalog
  has no per-user photo concept, and adding one would be a much larger
  feature than what's asked for here.
- Items already in the database before this feature ships won't
  retroactively gain a photo — the original upload's photo path was never
  captured, so there's nothing to backfill from; re-uploading is out of
  scope.
- "Cannot currently be retrieved" (FR-006) covers both a genuinely
  missing/removed file and a transient failure fetching it — the
  user-visible behavior is identical either way (fall back), so this
  isn't split into two separate requirements.
- Access to a stored photo continues to be governed by the existing
  per-user Storage access restriction already set up for the upload flow
  (Feature 003) — this feature adds no new access rule, it only makes use
  of a photo that's already restricted to its owner.
