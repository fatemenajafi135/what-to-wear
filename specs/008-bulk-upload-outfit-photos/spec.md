# Feature Specification: Photo Management & Display Expansion

**Feature Branch**: `008-bulk-upload-outfit-photos` (spec directory only — developed
and committed on the existing `006-wardrobe-item-photos` git branch per explicit
instruction, not a fresh branch)

**Created**: 2026-07-17

**Status**: Draft

**Input**: User description: four related photo capabilities building directly
on the just-shipped wardrobe-item-photos feature, prioritized by the user as
follows — (1) bulk photo upload so a user with a large existing wardrobe isn't
stuck adding items one at a time, (2) showing each item's real photo, grouped
per outfit, in outfit suggestions (currently text-only), (3) previewing the
actual photo during the single-item add/review step (currently only the form
is shown, not the photo), and (4) editing or removing a photo on an
already-saved item (currently no way to do this at all). User explicitly
ranked (1) and (2) above (3) and (4) — implement in that order, but all four
are in scope for this spec.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Add many wardrobe items at once (Priority: P1)

A user with an existing wardrobe of 20+ garments wants to digitize their whole
closet in one sitting, rather than repeating a single-item "take a photo →
confirm details → save" cycle 20 separate times. They select or capture
multiple photos at once, the system analyzes each one, and the user reviews or
corrects each item's details before everything is saved to their closet
together.

**Why this priority**: the single biggest usability gap in the photo-based add
flow today — without it, digitizing a real wardrobe is prohibitively tedious,
which undermines the core "assemble outfits from what you actually own"
premise if most of a user's closet never gets entered.

**Independent Test**: select 5+ photos in one upload action, review/correct
each resulting item in sequence, save the batch, and verify all items appear
in the closet afterward — deliverable and testable without any other story in
this spec.

**Acceptance Scenarios**:

1. **Given** a user on the add-item flow, **When** they select multiple photos
   at once, **Then** each photo is analyzed individually and the user can
   review/correct each item's details before any of it is saved.
2. **Given** a batch of selected photos, **When** the user finishes reviewing
   and confirming all items, **Then** every confirmed item is saved to their
   closet in one action, and the user is returned to the closet view showing
   all newly added items.
3. **Given** a batch where one photo fails analysis (e.g., unreadable image),
   **When** the user proceeds through the review step, **Then** that one item
   falls back to the same manual-entry path as today's single-item flow,
   without blocking review or saving of the other items in the batch.
4. **Given** a batch where saving one item fails (e.g., a transient network
   error) while the rest of the batch saves successfully, **When** saving
   completes, **Then** the user is told exactly which item(s) failed and can
   retry just those, without re-entering or re-uploading items that already
   saved.

---

### User Story 2 - See item photos in outfit suggestions (Priority: P2)

When a user gets an outfit suggestion, each suggested item is currently
described only in text (category and color). The user wants to see each
item's actual photo next to its details, the same way it already appears in
their closet, so they can visually recognize the specific garment being
recommended — with each outfit's items shown together as a set, not as a
scattered list.

**Why this priority**: valuable and cheap to deliver (the underlying
photo-display capability already exists from the wardrobe-item-photos
feature), but it's a comprehension/delight improvement on an already-functional
suggestion flow, not a blocker to using the product — lower priority than
closing the bulk-add gap in User Story 1.

**Independent Test**: request a suggestion for a closet containing at least
one photo-added item, and verify that item's real photo renders alongside its
suggested outfit, grouped with that outfit's other items — independently
verifiable without any other story in this spec.

**Acceptance Scenarios**:

1. **Given** a suggested outfit containing an item that has a photo, **When**
   the suggestion is displayed, **Then** that item's real photo is shown
   alongside its existing text details (category, color, etc.).
2. **Given** a suggested outfit containing an item with no photo (e.g., added
   from the shared catalog), **When** the suggestion is displayed, **Then**
   that item shows today's text/color-only presentation, exactly as before
   this feature — no broken image.
3. **Given** a suggestion containing multiple outfits, **When** the suggestion
   is displayed, **Then** each outfit's items are visually grouped together as
   a set, distinguishing one outfit's items from another's at a glance.

---

### User Story 3 - Preview the photo while reviewing a new item (Priority: P3)

After taking or choosing a photo to add a new item, the user currently only
sees a form of extracted/guessed attributes to confirm or correct — not the
photo itself. They want to see the actual photo they just captured while
reviewing and correcting its details, so they can visually verify the details
match what they're looking at (e.g., confirming an extracted color actually
matches the garment).

**Why this priority**: a real gap, but a comprehension aid on a flow that
already works today (users can already successfully add items without seeing
the photo during review) — lower priority than closing the bulk-add gap (US1)
or the outfit-display gap (US2), which are both bigger, more frequently-hit
gaps.

**Independent Test**: start adding a single item by photo, and verify the
just-captured photo is visible throughout the review/correction step, before
saving — independently testable without any other story in this spec.

**Acceptance Scenarios**:

1. **Given** a user has just captured or selected a photo to add an item,
   **When** they reach the review/correction step, **Then** the photo they
   captured is visible alongside the form.
2. **Given** a user's session expired mid-review and they resume later
   (matches existing resume behavior), **When** they return to the review
   step, **Then** the photo is still visible, not just the form fields.

---

### User Story 4 - Edit or remove a photo on an already-saved item (Priority: P4)

A user who already added an item by photo — or who wants to add/replace a
photo on an item that doesn't have one, or has the wrong one — currently has
no way to do this from their closet. They want to replace an item's photo
with a better one, or remove it entirely (falling back to the swatch-only
display), directly from their closet.

**Why this priority**: the least-requested of the four, and the one most
likely to need a real product judgment call (e.g., what happens to the old
photo) — appropriate to tackle last, once the higher-value gaps are closed.
Note this is also the only story of the four with no existing
foundation to build on: there is no item-editing surface anywhere in the app
today, for any attribute, not just photos.

**Independent Test**: from the closet view, replace an existing item's photo
with a new one and verify it renders instead of the old one; separately,
remove a photo from an item and verify it falls back to swatch-only —
independently testable without any other story in this spec.

**Acceptance Scenarios**:

1. **Given** an item in the closet that has a photo, **When** the user
   chooses to replace it with a new photo, **Then** the new photo is what
   displays for that item afterward (in the closet and anywhere else it's
   shown), not the old one.
2. **Given** an item in the closet that has a photo, **When** the user
   chooses to remove it, **Then** the item displays swatch-only afterward,
   exactly like an item that never had a photo.
3. **Given** an item in the closet that has no photo, **When** the user adds
   one, **Then** it displays going forward, exactly like an item added with a
   photo originally.

---

### Edge Cases

- What happens if a user selects zero photos, or cancels partway through
  reviewing a batch (US1)? Nothing unreviewed is saved.
- What's the practical upper bound on how many photos can be selected in one
  batch (US1)? See Assumptions — defaulted rather than left open, given a
  concrete real-world number (20+) was already given.
- What happens if a user's session expires partway through reviewing or
  saving a large batch (US1)? Matches today's single-item resume-after-sign-in
  behavior, extended to cover a batch.
- What happens if a photo's signed display URL fails to load in the
  outfit-suggestion view (US2, expired/deleted object)? Falls back to
  text-only for that item, matching the closet view's existing fallback
  (FR-008).
- What happens to the old photo file in storage when a user replaces or
  removes it (US4)? See Assumptions — left in place, not actively deleted,
  for now.
- What happens if a user tries to replace/remove a photo on an item they
  don't own (US4)? Rejected, same ownership check as every other per-item
  operation in this app.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Users MUST be able to select multiple photos in a single action
  when adding wardrobe items.
- **FR-002**: The system MUST analyze each selected photo independently and
  produce a reviewable, correctable set of attributes for each resulting item,
  reusing the same review/correction experience as the existing single-item
  flow.
- **FR-003**: Users MUST be able to review and correct each item in the batch
  before any of it is saved.
- **FR-004**: A single photo failing analysis MUST NOT block review or saving
  of the other items in the same batch — that item falls back to the same
  manual-entry path as today's single-item flow.
- **FR-005**: Saving the batch MUST report success/failure per item, not as a
  single all-or-nothing outcome, and MUST let the user retry only the failed
  items.
- **FR-006**: The system MUST cap the number of photos accepted in a single
  batch at 30 (see Assumptions).
- **FR-007**: Outfit suggestions MUST display each item's real photo when one
  exists, using the same display mechanism already used on the closet view.
- **FR-008**: Outfit suggestions MUST fall back to today's text/color-only
  item display when no photo exists for an item, or its photo fails to load —
  never a broken image or an error in place of the suggestion.
- **FR-009**: Outfit suggestions MUST visually group each outfit's items
  together as a distinct set, distinguishable from other outfits shown in the
  same response.
- **FR-010**: Users MUST be able to see the actual photo they just
  captured/selected throughout the review/correction step of the single-item
  add flow, before saving.
- **FR-011**: Users MUST be able to replace an already-saved item's photo
  with a new one from the closet view.
- **FR-012**: Users MUST be able to remove an already-saved item's photo,
  after which the item displays exactly as an item that never had a photo.
- **FR-013**: Replacing or removing a photo MUST be restricted to the item's
  owner, consistent with every other per-item wardrobe operation.
- **FR-014**: Replacing a photo MUST NOT re-analyze or change the item's
  other attributes (category, color, formality, etc.) — only the photo
  changes.

### Key Entities

- **Wardrobe Item** (existing entity): bulk upload and single-item preview
  add no new fields (US1, US3). US4 makes the existing `photo_path` reference
  editable after creation for the first time — previously set once, now also
  replaceable/clearable.
- **Upload Batch** (new, transient, not persisted): the in-progress set of
  photos a user is actively reviewing before saving (US1); exists only for
  the duration of one add-items session, not stored once saved.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can add 20 wardrobe items from photos in a single sitting
  without repeating a full separate flow per item.
- **SC-002**: When one item in a batch of many fails to analyze or save, the
  user loses no progress on the other items in that batch.
- **SC-003**: A user viewing an outfit suggestion for an item they added by
  photo sees that item's real photo, not just text, with no additional
  action required.
- **SC-004**: Outfit suggestions render with no broken images or errors
  regardless of which suggested items have photos.
- **SC-005**: A user reviewing a newly captured item photo can see it without
  leaving the review step.
- **SC-006**: A user can change what photo represents an already-saved item,
  or remove it, without needing to delete and re-add the item.

## Assumptions

- Bulk upload reuses the existing single-item photo analysis and save
  operations, run per item across the batch — not a new or different
  analysis method.
- Each photo in a batch is analyzed independently: batch members don't need
  to be visually or categorically related (a user might mix tops, bottoms,
  and shoes in one batch).
- Batch size is capped at 30 photos per batch — comfortably above the
  20-item real-world case that motivated this feature, while keeping review
  time and per-batch analysis cost (each photo is a real model call) bounded.
  Adjustable later; not worth blocking on.
- The outfit-suggestion photo display reuses the same signed, time-limited
  photo access already used on the closet view — no new photo-storage or
  access model.
- This feature only affects how suggestions are displayed on the client; it
  does not change which outfits are selected or how they're scored (no
  retrieval/generation/scoring code is touched — Constitution Principles I-V
  are N/A, same as the wardrobe-item-photos feature before it).
- Replacing a photo (US4) does not re-run attribute extraction — the item's
  existing attributes are untouched, avoiding an unnecessary model call when
  the user only wants to change the picture, not the item's details (FR-014).
- The old photo file in storage is left in place (not actively deleted) when
  a photo is replaced or removed (US4) — consistent with this codebase not
  having a photo-deletion capability today; acceptable to ship without
  storage cleanup and revisit later if it becomes a real cost/clutter issue.
