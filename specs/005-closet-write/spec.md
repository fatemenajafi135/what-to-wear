# Feature Specification: Closet (write)

**Feature Branch**: `005-closet-write`

**Created**: 2026-07-31

**Status**: Draft

**Input**: User description: "Closet write: a signed-in user can manage items already in their
closet. From Item detail (/closet/:itemId), the overflow (dots) menu opens a BottomSheet with
four rows in this order: Edit, Log as worn today, Favorite, Delete. Edit swaps the read-only
card for an editable form ending in a full-width 'Save changes' button that persists a partial
update. Favorite/unfavorite toggles a boolean flag. Log as worn today records a timestamped wear
event; nothing on Item detail displays a worn count or favorite indicator as a result. Delete
hard-deletes the item using the BottomSheet's danger row tone. No add-item flow of any kind is
in scope. All four actions are owner-only, enforced at RLS and query level. Offline disables
'Log as worn' and the save-changes submit; nothing is queued. Two decisions are open: same-day
double-tap semantics for 'Log as worn today', and whether Delete needs a confirmation step."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Edit an item's details (Priority: P1)

A user viewing one of their closet items opens the overflow menu, chooses Edit, and the
read-only card is replaced by a form pre-filled with the item's current values in the same
field order (Name, Category, Group, Fabric, Colour, Notes). They change one or more fields and
tap "Save changes"; the page returns to its read-only state showing the new values, and the
change survives a page reload.

**Why this priority**: Correcting a misclassified or mistyped item is the most common reason a
user returns to an item they already own, and every other action in this feature (favourite,
worn, delete) is a single-tap toggle with no form — Edit is the one piece of real UI work.

**Independent Test**: Open an existing item, edit its Name and Notes, save, reload the page, and
confirm both new values persist and every other field is unchanged.

**Acceptance Scenarios**:

1. **Given** an item's read-only detail view, **When** the user selects "Edit" from the overflow
   menu, **Then** the same card area shows an editable form with identical field order and the
   item's current values pre-filled.
2. **Given** the edit form is open, **When** the user changes a subset of fields and taps "Save
   changes", **Then** only the changed fields are updated, the form closes back to the read-only
   view showing the new values, and unrelated fields (photo, favourite state, wear history) are
   untouched.
3. **Given** the edit form is open, **When** the user is offline, **Then** the "Save changes"
   button is disabled and no request is attempted.
4. **Given** another user's item, **When** this user attempts to edit it directly (e.g. via a
   replayed or forged request), **Then** the request is rejected and no data changes.

---

### User Story 2 - Favourite and log wear (Priority: P2)

From the same overflow menu, a user can mark an item as a favourite (and unmark it later), and
can log that they wore it today. Neither action changes what is visible on the Item detail page
itself — both are recorded for use elsewhere in the product.

**Why this priority**: These are the two lightweight, high-frequency actions a user takes
repeatedly on items they already like or wear often; they're simpler than Edit but only useful
once items exist to act on, so they follow Edit in priority.

**Independent Test**: Tap "Favorite" on an unfavourited item, confirm the flag flips (verifiable
via the API/database, not the page — the design shows no on-page indicator), tap it again and
confirm it flips back. Separately, tap "Log as worn today" and confirm a wear record is created
for that item for today's date.

**Acceptance Scenarios**:

1. **Given** an item that is not favourited, **When** the user selects "Favorite" from the
   overflow menu, **Then** the item's favourite flag becomes true and no visual change appears
   on Item detail.
2. **Given** an item that is favourited, **When** the user selects the same row again, **Then**
   the flag becomes false.
3. **Given** an item with no wear record for today, **When** the user selects "Log as worn
   today", **Then** exactly one wear record exists for that item for today's date, and Item
   detail continues to show no worn-count or favourite indicator.
4. **Given** an item that was already logged as worn today, **When** the user selects "Log as
   worn today" again the same day, **Then** the wear record for today is not duplicated (see
   Assumptions for the exact same-day semantics decided for this feature).
5. **Given** the user is offline, **When** they view the overflow menu, **Then** "Log as worn
   today" is disabled and no request is attempted.

---

### User Story 3 - Delete an item (Priority: P3)

A user who no longer owns or wants to track a garment removes it from their closet permanently
via the overflow menu's Delete row.

**Why this priority**: Least frequent of the four actions, and irreversible — it's ordered last
both because it's rarer and because its safety behaviour (confirmation) depends on the other
three actions' patterns being established first.

**Independent Test**: Open an item, choose Delete, confirm the deletion when prompted, and
verify the item no longer appears in the closet grid or at its detail URL.

**Acceptance Scenarios**:

1. **Given** an item's overflow menu, **When** the user selects "Delete", **Then** they are asked
   to confirm the permanent, unrecoverable removal before anything is deleted (see Assumptions
   for why a confirmation step was added).
2. **Given** the confirmation is accepted, **When** the deletion completes, **Then** the item is
   permanently removed, no longer appears in the closet grid, and its detail URL shows the
   existing "item not found" error state.
3. **Given** the confirmation is shown, **When** the user cancels it, **Then** nothing is deleted
   and the overflow menu closes (or returns to the prior state) unchanged.
4. **Given** another user's item ID, **When** a delete request is issued for it by this user,
   **Then** the request is rejected and the item is not removed.

---

### Edge Cases

- Editing a field to an empty/blank value where the underlying column allows it (e.g. clearing
  Notes) must persist as empty, not be silently ignored.
- Rapid double-submission of "Save changes" (e.g. double-tap) must not create inconsistent state
  or duplicate side effects — the second submission either no-ops or overwrites with the same
  values.
- A user with the app open in two tabs deletes the item in one tab; the other tab's now-stale
  overflow actions must fail gracefully (owner/existence check) rather than silently succeeding
  or crashing.
- Toggling "Favorite" or tapping "Log as worn today" while a save from Edit is still in flight
  must not corrupt either update — each action addresses only its own field(s).
- Going offline mid-session (not just on load) must disable "Log as worn" and "Save changes"
  immediately, matching `navigator.onLine` transitions, not just the initial page state.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST let the owning user edit an existing item's Name, Category, Group,
  Fabric, Colour, and Notes via a partial update; fields not included in the update MUST remain
  unchanged.
- **FR-002**: The edit form MUST present the same field order as the read-only view, with
  Category rendered as selectable Chips and all other fields as text inputs.
- **FR-003**: System MUST let the owning user toggle a favourite flag on an item on and off.
- **FR-004**: System MUST let the owning user record that they wore an item today, and MUST
  prevent a second tap on the same day from creating more than one wear record for that
  item/day pair.
- **FR-005**: System MUST let the owning user permanently delete an item, after an explicit
  confirmation step, with no way to recover it afterward.
- **FR-006**: System MUST NOT display a worn count or a favourite indicator anywhere on Item
  detail, regardless of the item's actual favourite state or wear history.
- **FR-007**: System MUST reject edit, favourite, worn-logging, and delete requests for an item
  the requesting user does not own, at both the data-access layer and the database layer.
- **FR-008**: System MUST disable "Log as worn today" and the edit form's "Save changes" control
  whenever the client is offline, and MUST NOT queue either action for later retry or claim that
  it will retry.
- **FR-009**: System MUST NOT provide any means to add a new item to the closet (no catalog
  browse or catalog-add flow); this feature only modifies items that already exist.
- **FR-010**: The overflow menu MUST present exactly four rows in this order: Edit, Log as worn
  today, Favorite, Delete, with Delete using the destructive/danger visual tone.

### Key Entities

- **Wardrobe item**: A garment the user owns. Gains a favourite flag in this feature. Editable
  fields: name, category, group, fabric, colour, notes. Not editable here: photo, source,
  ownership.
- **Wear record**: A timestamped fact that a specific item was worn on a specific day, owned by
  the same user as the item. Written by "Log as worn today"; never read back by this feature's
  own UI (consumed by later features — outfit "most worn" sorting and the styling pipeline).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can change an item's details and see the update reflected immediately and
  after a page reload, with no unrelated field affected.
- **SC-002**: A user can toggle favourite state and log a wear on an item in a single tap each,
  with no additional confirmation step for either (only Delete requires confirmation).
- **SC-003**: No user can view, infer from timing/error differences, modify, or delete another
  user's closet item through any of this feature's actions.
- **SC-004**: A user cannot lose a garment record from a single accidental tap — deletion always
  requires a distinct, deliberate second action.
- **SC-005**: A user offline sees "Log as worn today" and "Save changes" as visibly inert
  (disabled) rather than appearing to work and silently failing or queuing.

## Assumptions

- **Same-day wear semantics — idempotent per day, not per tap.** "Log as worn today" records at
  most one wear per item per calendar day; tapping it again the same day is a no-op against an
  existing record rather than inserting a second row. Chosen because the action reads as a
  same-day boolean claim ("I wore this today"), not an event counter, and because the design
  provides no confirmation and no on-page feedback for this action — an accidental repeat tap
  must not be able to silently inflate future "most worn" rankings with no way for the user to
  notice. The alternative (one row per tap) was rejected for that reason; full reasoning and
  schema consequence recorded in `docs/design-decisions.md`.
- **Delete requires a confirmation step**, even though the design system specifies none for the
  overflow menu's danger row. Chosen because the action is an unrecoverable hard delete of a
  garment the user photographed, reachable by a single tap in a four-row menu; the cost of one
  extra confirmation tap is low next to permanent, unrecoverable data loss. Full reasoning and
  alternatives recorded in `docs/design-decisions.md`.
- Ownership enforcement follows the pattern feature 004 already established: an explicit
  `user_id` filter at the query level (the actual isolation guarantee, since this backend's
  pooler connection bypasses RLS) plus RLS policies and table GRANTs as the documented
  convention and defense-in-depth for any other access path.
- "Add item" (photo upload) is feature 006 and entirely out of scope; no UI or route for
  creating a wardrobe item is added here.
- The four overflow-menu actions are the complete scope of this feature; outfit-related uses of
  favourite/wear data are out of scope (feature 010).
