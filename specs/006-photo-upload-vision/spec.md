# Feature Specification: Photo upload + vision

**Feature Branch**: `006-photo-upload-vision`

**Created**: 2026-08-01

**Status**: Draft

**Input**: User description: "I photograph a garment and it lands in my closet with its
attributes already filled in. Supabase Storage bucket+RLS for wardrobe photos (migration
0006), two new routes on the existing closet router (extract: multipart image ->
PhotoExtractionResponse, persists nothing to wardrobe_items; create-from-upload:
CreateWardrobeItemFromUploadRequest -> saved item), the /add overlay flow (dropzone -> scan ->
review card(s) -> saved) replacing the current stub body, bulk upload (one item per photo,
queued review cards), the camera permission primer gating a file input capture=environment
behind a persisted wtw_camera_primed flag, deleting the diagonal-stripe placeholder from the
closet grid tile and item-detail hero once real photos exist, and closing the vision harness
gap left open by feature 007. Six named gaps recorded as decisions in design-decisions.md
starting at section 23: review-card field mismatch vs. required upload attributes, the Color
text field writing into a hex column, bucket privacy, max upload file size, partial bulk-save
failure, camera primer copy. Two more from known-gaps.md: review progress bar animation, and
whether 'Enter manually' opens the same review form blank or a distinct flow."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Photograph one garment and save it (Priority: P1)

A user taps the Create action, is (if this is their first time) shown a one-time camera
permission primer, then photographs or uploads a photo of a single garment. The photo is
scanned; a review card appears with Name, Category, Group, Fabric, Color and Notes already
filled in from the scan. The user checks the fields, corrects anything wrong, and saves. The
item now appears in their closet grid with its real photo, and survives a reload.

**Why this priority**: This is the feature's whole mission statement — every other scenario
(bulk, primer, placeholder removal) is a variation or a precondition of this one flow actually
working end to end.

**Independent Test**: Photograph a real garment, confirm the review card pre-fills plausible
values, save without changing anything, and confirm the item appears in Closet with its photo
intact after a page reload.

**Acceptance Scenarios**:

1. **Given** the Add-item overlay is open and the user has a photo ready, **When** they submit
   it, **Then** the photo uploads, a scan runs, and a review card appears with Name, Category,
   Group, Fabric, Color and Notes pre-filled from the scan wherever the scan produced a value.
2. **Given** a filled-in review card, **When** the user edits one or more of the six fields and
   taps Save, **Then** the item is created with the edited values, the overlay closes back to
   the screen the user opened it from, and the new item appears in the closet grid with its own
   photo (not the placeholder).
3. **Given** a photo with no identifiable garment in it, **When** the scan completes, **Then**
   the flow shows an explanatory empty state (not an error) offering to retake the photo or
   enter the item manually, and the photo itself is not lost — proceeding manually reuses the
   same uploaded photo and review card, left blank, rather than restarting the upload.
4. **Given** the scan identified some but not all attributes (e.g. it found a color but not a
   fabric), **When** the review card appears, **Then** every field the scan found is pre-filled
   and every field it missed is left blank and editable — a partial scan never blocks the save.
5. **Given** the user is offline, **When** they try to start the upload, **Then** the upload
   trigger is disabled and no copy promises the photo will be queued or retried automatically.
6. **Given** a genuine upload failure (not a "no garment found" result), **When** it happens,
   **Then** the user sees an error state with a way to try again, distinct from the "no garment
   found" empty state.

---

### User Story 2 - Add several garments in one pass (Priority: P2)

A user with a pile of clothes to catalog chooses the bulk option, supplies several photos, and
reviews them one at a time as a queue — one item per photo. They can save the current card and
move to the next, or save the whole remaining queue at once when they reach the last card.

**Why this priority**: The single-item flow is the minimum viable version of the mission;
bulk is the same mechanism repeated, valuable for anyone stocking their closet for the first
time, but not required for the feature's core promise to hold.

**Independent Test**: Start the bulk option with three photos, save the first card and confirm
it advances to the second with an updated, announced position indicator, then use the final
action to finish the queue and confirm all three items exist in the closet.

**Acceptance Scenarios**:

1. **Given** the user chooses to add bulk items, **When** they supply several photos, **Then**
   each photo becomes its own queued review card, one item per photo, in the order supplied.
2. **Given** a queue of review cards, **When** the user saves the current card, **Then** the
   item is created, the position indicator ("Reviewing item X of Y") updates and is announced
   to assistive technology, and the next card in the queue appears.
3. **Given** the user is on the last card of the queue, **When** they save it, **Then** the
   overlay closes back to the screen it was opened from and all queued items now exist in the
   closet.
4. **Given** one card in the middle of the queue fails to save (a genuine server/network
   failure, not a validation problem), **When** the failure happens, **Then** that card alone
   shows a retryable error in place, the cards already saved before it stay saved, and the
   queue does not silently skip or lose the failed card.
5. **Given** a queue is in progress, **When** the user closes the overlay before finishing,
   **Then** only the cards already saved persist — nothing is auto-saved on close.

---

### User Story 3 - Real photos replace the placeholder (Priority: P3)

Once a garment has been photographed and saved, its real photo appears everywhere the app shows
that item — the closet grid tile and the item's own detail page — instead of the diagonal-stripe
placeholder used throughout development.

**Why this priority**: This is the visible payoff of the other two stories rather than a
separate capability; it depends on items with real photos existing, which requires Story 1
first, but it is a small, mechanical change once that's true.

**Independent Test**: Save a new item with a photo, open Closet and confirm the grid tile for
that item shows the real photo, then open the item and confirm its detail page also shows the
real photo, both without any diagonal-stripe pattern visible anywhere for that item.

**Acceptance Scenarios**:

1. **Given** an item created through this feature, **When** it appears in the closet grid,
   **Then** its tile shows the item's real photo, not the diagonal-stripe placeholder.
2. **Given** the same item, **When** its detail page is opened, **Then** the hero photo area
   shows the real photo, not the diagonal-stripe placeholder.
3. **Given** an item that predates this feature and has no photo at all, **When** it is shown
   in the grid or on its detail page, **Then** it renders a defined no-photo treatment — not
   the removed diagonal-stripe pattern repurposed as a stand-in.
4. **Given** any item's photo, **When** it is requested by someone who is not that item's
   owner, **Then** the request is refused.

---

### Edge Cases

- A photo upload that succeeds but whose scan call itself fails outright (not "no garment
  found," a real service failure) must not be indistinguishable from the "no garment found"
  empty state — it is the distinct error state instead.
- A file that is not an image, or has no file at all, is rejected before any upload attempt.
- A file larger than the enforced maximum is rejected with a clear reason before it reaches the
  scan step.
- A user backing out of the Add-item overlay mid-review (single-item flow) discards the
  in-progress review without creating anything, matching the overlay's existing close behavior.
- Two users cannot see or overwrite each other's uploaded photos under any circumstance,
  including by guessing or reusing another user's object path.
- A user editing the Color field to a value the app cannot resolve to a stored color is told so
  and is not silently saved with an unrelated or fabricated color.
- Going offline mid-flow (not just at the start) disables the upload trigger immediately.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST let a signed-in user upload a photo of a single garment and receive
  back scanned attributes for Name, Category, Group, Fabric, Color and Notes, pre-filling a
  review card the user can edit before saving.
- **FR-002**: System MUST persist nothing to the user's closet as a result of the scan alone —
  only an explicit save creates the item.
- **FR-003**: System MUST treat "no garment found in this photo" as a normal, successful
  outcome (not an error): the photo is still uploaded, and the user sees an explanatory empty
  state offering to retake the photo or continue to the same review card with blank fields.
- **FR-004**: System MUST treat a genuine upload or scan-service failure as a distinct error
  state, separate from "no garment found," with its own retry action.
- **FR-005**: System MUST NOT require the five attributes outside the review card (Formality,
  Warmth, Season, Pattern, Fit) to block a save when the scan could not determine them; the item
  saves with whatever was found (or a documented, non-arbitrary default where a value is
  mandatory to store the item at all), and every attribute remains correctable afterward through
  the existing item-edit flow.
- **FR-006**: System MUST let the user add several garments in one pass, one item per supplied
  photo, reviewed one at a time as a queue with a position indicator that updates and is
  announced to assistive technology as the user advances.
- **FR-007**: System MUST let the user save the current card in a queue and advance to the next,
  and MUST let the user finish and close the queue once the last card is saved.
- **FR-008**: System MUST isolate a single failed save within a bulk queue to that card alone —
  cards already saved before the failure MUST remain saved, and the failed card MUST show a
  retryable error in place rather than being silently skipped or losing the user's edits.
- **FR-009**: System MUST require a one-time camera permission primer, gated behind a persisted
  choice, before the first real camera capture in this flow; the choice MUST persist across a
  reload so the primer is not shown again once accepted.
- **FR-010**: System MUST reject an upload that is missing, not an image, or larger than a
  defined maximum size, before it reaches the scan step, with a clear reason in each case.
- **FR-011**: System MUST store each uploaded photo so that only its owner can read or overwrite
  it — no other signed-in user, under any request shape, can access another user's photo.
- **FR-012**: System MUST render each item's real photo, once it has one, in the closet grid
  tile and on the item's detail page, and MUST NOT show the diagonal-stripe placeholder for any
  item that has a real photo.
- **FR-013**: System MUST define and use a distinct treatment for an item that has no photo at
  all (e.g. seeded before this feature shipped) that is not the removed placeholder pattern.
- **FR-014**: System MUST disable the upload trigger while the client is offline, and MUST NOT
  present any copy implying the upload will be queued or retried automatically once
  reconnected.
- **FR-015**: System MUST validate a user-edited Color value against the app's known color
  vocabulary before saving, and MUST tell the user clearly when a typed value cannot be
  resolved rather than saving an unrelated or guessed color.
- **FR-016**: System MUST let a user reach a blank version of the same review form directly
  from the "no garment found" state ("Enter manually"), without a second, separately-built
  entry form.

### Key Entities

- **Wardrobe item photo**: The image behind one wardrobe item, owned by the same user as the
  item. Exists independently of whether the item itself has been saved yet (a scan can upload
  a photo without creating an item). Readable and overwritable only by its owner.
- **Extracted attributes (draft)**: The unsaved, scan-derived guess at a garment's Name,
  Category, Group, Fabric, Color, Notes and the five additional attributes the closet schema
  requires. Never persisted on its own; becomes part of a wardrobe item only when the user
  saves the review card.
- **Review queue item**: One entry in a bulk-upload session — a photo plus its (possibly still
  unsaved) reviewed attributes and a save outcome (not yet attempted / saved / failed).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can go from photographing a garment to seeing it, with its real photo, in
  their closet grid in one continuous flow with no more than one review step.
- **SC-002**: A photo with no recognizable garment never produces an error-looking failure — it
  always resolves to the defined empty state with a clear next step.
- **SC-003**: A user adding several garments in one session saves all of them without having to
  restart the whole batch because one photo in the middle failed.
- **SC-004**: No user can ever view or overwrite another user's uploaded garment photo.
- **SC-005**: After this feature ships, no screen in the product shows the diagonal-stripe
  placeholder for an item that has a real photo.
- **SC-006**: A user who denies or defers the camera primer can still complete the flow by
  uploading a file instead, and is not shown the primer again once they have made a choice.

## Assumptions

- **Review-card / required-attribute mismatch (design-decisions.md §23.1).** The five
  attributes not on the review card (Formality, Warmth, Season, Pattern, Fit) are relaxed from
  strictly-required to best-effort: saved as scanned when present, defaulted to a documented,
  conservative value only where the database itself cannot store a missing value (Formality,
  Warmth, Season), and left null where the database already allows it (Fabric shown on-card
  regardless; Pattern, Fit). Nothing blocks a save. Full alternatives considered are recorded in
  `docs/design-decisions.md`.
- **Color text field vs. stored hex (§23.2).** The review card's Color field is pre-filled with
  the derived name of the scanned hex. On save, the (possibly edited) text is matched
  case-insensitively against the app's curated color vocabulary; an unmatched value is rejected
  with a clear message rather than silently approximated or guessed.
- **Bucket privacy (§23.3).** The photo bucket is private; the backend issues short-lived signed
  URLs when the closet is read, rather than serving photos from a public bucket.
- **Maximum upload size (§23.4).** A concrete file-size ceiling is enforced before a photo
  reaches the scan step; exceeding it is rejected with a clear reason, not silently truncated
  or passed through.
- **Partial bulk-save failure (§23.5).** A failed card in a bulk queue is isolated: it shows a
  retryable error in place, already-saved cards are unaffected, and the queue does not advance
  past the failed card until it succeeds or the user abandons the whole overlay.
- **Camera primer copy (§23.6)** is newly written in the stylist's first-person voice,
  following the shape feature 012's calendar primer already established, and is recorded in
  `docs/design-decisions.md` rather than invented ad hoc in code.
- **Review progress bar animates** between steps rather than jumping instantly, consistent with
  the rest of the system's motion tokens, gated by `prefers-reduced-motion`.
- **"Enter manually" reuses the same review form**, left blank, rather than a second bespoke
  manual-entry UI — consistent with the constraint that every form control already exists and
  none should be duplicated.
- Bulk upload's "several photos" has no fixed maximum named by the design; a reasonable
  practical ceiling is assumed and enforced to protect the scan/upload path, not a design
  requirement.
- Extraction/scan runs synchronously from the user's point of view (submit photo, wait, see
  result) — no background/async job UI exists in the design for this flow.
- The Storage/RLS isolation guarantee, and the query-level ownership filter pattern, follow the
  same convention established by every earlier data-owning feature (004/005).
