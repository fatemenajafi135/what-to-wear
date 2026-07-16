# Feature Specification: Bulk Photo Upload & Outfit Photo Display

**Feature Branch**: `007-bulk-upload-outfit-photos` (spec directory only — developed
and committed on the existing `006-wardrobe-item-photos` git branch per explicit
instruction, not a fresh branch)

**Created**: 2026-07-17

**Status**: Draft

**Input**: User description: two related photo capabilities building directly on
the just-shipped wardrobe-item-photos feature — (1) bulk photo upload so a user
with a large existing wardrobe isn't stuck adding items one at a time, and (2)
showing each item's real photo, grouped per outfit, in outfit suggestions
(currently text-only). User flagged both as higher priority than two other
photo ideas (photo preview during the single-item review step; editing/removing
a photo on an already-saved item), which are explicitly deferred to a later spec.

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
in the closet afterward — deliverable and testable without User Story 2
existing.

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
verifiable without User Story 1 existing.

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

### Edge Cases

- What happens if a user selects zero photos, or cancels partway through
  reviewing a batch? Nothing unreviewed is saved.
- What's the practical upper bound on how many photos can be selected in one
  batch? See Assumptions — defaulted rather than left open, given a concrete
  real-world number (20+) was already given.
- What happens if a user's session expires partway through reviewing or
  saving a large batch? Matches today's single-item resume-after-sign-in
  behavior, extended to cover a batch.
- What happens if a photo's signed display URL fails to load in the
  outfit-suggestion view (expired, deleted)? Falls back to text-only for that
  item, matching the closet view's existing fallback (FR-008).

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

### Key Entities

- **Wardrobe Item** (existing entity, unchanged): this feature adds no new
  fields — bulk upload creates multiple wardrobe items via the existing
  single-item creation path, and outfit display reads the existing photo
  reference already stored per item.
- **Upload Batch** (new, transient, not persisted): the in-progress set of
  photos a user is actively reviewing before saving; exists only for the
  duration of one add-items session, not stored once saved.

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
- Previewing a photo during the single-item (non-batch) review step, and
  editing/removing a photo on an already-saved item, are explicitly out of
  scope for this feature — planned as a separate, later feature per the
  user's own stated sequencing.
