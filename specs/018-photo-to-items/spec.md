# Feature Specification: Photo to items

**Feature Branch**: `feat/018-photo-to-items`

**Created**: 2026-08-10

**Status**: Draft

**Input**: User description: "One photo in, N clean garment items out. Closes GitHub issues #45 (detection —
`POST /closet/items/extract` must return one review draft per garment in a photo, not one per photo),
#46 (extraction accuracy — `prompts/vision_system.md` rewritten for multi-garment detection, targeting
named failure modes: wrong category, missed attributes, vague names) and #48 (isolation — each detected
garment gets its own clean, background-removed image, via a segmentation strategy, a generative
reconstruction strategy, and a hybrid, chosen by configuration). Bundled into one slice because all three
share one prompt file and one fixture corpus. Storage retains the original photo unconditionally and adds
one derived-image column to `wardrobe_items` via migration. Out of scope: #50 (accessory attributes), #51
(outfit-on-body generation), #53 (background styling queue)."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - One photo, several garments (Priority: P1)

A user photographs several garments at once — a flat-lay of the day's laundry, a folded stack on a
shelf, a few hangers on a rail — the way they'd naturally photograph a batch of clothes rather than
one item at a time. Today that single photo produces one review card for the whole scene, with
attributes describing whichever garment happened to dominate the frame. Instead, it must produce one
review card per garment actually in the photo, each with its own attributes.

**Why this priority**: This is the entire feature. Without detection splitting one photo into several
candidates, extraction accuracy and image isolation have nothing distinct to work on.

**Independent Test**: Upload one photo containing three visibly different garments and confirm three
review cards appear, each describing a different garment rather than three copies of the same one.

**Acceptance Scenarios**:

1. **Given** a flat-lay photo of four different garments, **When** it is uploaded, **Then** exactly
   four review cards are produced, each with attributes describing a different garment.
2. **Given** a photo of a folded stack of garments, **When** it is uploaded, **Then** each
   distinguishable garment in the stack produces its own card, up to the system's detection limit.
3. **Given** a photo with more garments in it than the detection limit allows, **When** it is
   uploaded, **Then** the system produces cards for the most confidently identified garments up to
   the limit and tells the user some garments in the photo were not captured, rather than silently
   dropping them or erroring the whole upload.

---

### User Story 2 - A single-garment photo still feels exactly like today (Priority: P1)

A user photographs one garment by itself, the way the app has always supported. This must keep
working exactly as it does today: one photo in, one review card out, same wait, same fields.

**Why this priority**: This is the existing, load-bearing behavior every current user already relies
on. Extending the contract to support N garments must not be observable as a regression when N is 1 —
this is what makes the change an extension rather than a new, riskier route.

**Independent Test**: Upload a photo of one garment and confirm exactly one review card appears, with
the same fields, in about the same time, as before this feature shipped.

**Acceptance Scenarios**:

1. **Given** a photo containing exactly one garment, **When** it is uploaded, **Then** exactly one
   review card is produced — never zero, never more than one.
2. **Given** the garment-detection step itself fails to run (rather than legitimately finding nothing),
   **When** the photo is processed, **Then** the system falls back to today's original behavior:
   one review card covering the whole photo.
3. **Given** a blurry or empty photo where no garment can be confidently identified, **When** it is
   processed, **Then** the system still produces exactly one blank-ish review card the user can fill
   in by hand, the same way an unrecognized single-item photo behaves today — never zero cards.

---

### User Story 3 - Each card describes its garment accurately (Priority: P2)

For every detected garment, the category, colors, fabric, warmth, formality, season, pattern and fit
that pre-fill the review card are specific and correct often enough to be worth keeping rather than
retyping — matching the standard the single-item flow already sets, now applied per garment in a
crowded photo.

**Why this priority**: A detection step that finds the right number of garments but describes them
vaguely or wrongly saves the user no time over typing everything by hand; this is the accuracy work
that makes the split worth having.

**Independent Test**: Run the fixture-corpus photos through the extraction step before and after the
prompt change and confirm a measurable improvement — not just an asserted one — on wrong category,
missed attributes, and vague naming, the specific failures the issue names.

**Acceptance Scenarios**:

1. **Given** a garment with a specific, recognizable type (e.g. a denim jacket, not just "a top"),
   **When** it is extracted, **Then** the category reflects the specific type rather than only the
   bare category group, matching today's single-item standard.
2. **Given** a photo with several garments close together, **When** each is extracted, **Then**
   each card's attributes describe that card's own garment, not a neighboring one.
3. **Given** a garment the model genuinely cannot determine an attribute for, **When** it is
   extracted, **Then** that field is left blank rather than guessed — never a confident-looking wrong
   value.

---

### User Story 4 - Each item's photo shows just the garment (Priority: P2)

Once a garment is detected, its review card — and later its closet tile and item detail page — show
a clean image of that garment on its own, not the whole flat-lay or the person wearing it. The result
looks like a product photo of that one piece, the way today's single-item photos already do when the
user photographs one thing against a plain background.

**Why this priority**: This is what makes a photo of several garments actually produce several usable
item photos, rather than several cards that all show the same busy scene.

**Independent Test**: Upload a photo of a garment worn by a person or lying among other garments and
confirm the review card shows that garment isolated from its surroundings, not the full original
scene.

**Acceptance Scenarios**:

1. **Given** a garment detected in a busy or multi-item photo, **When** its review card renders,
   **Then** it shows an image scoped to that garment alone.
2. **Given** isolating a particular garment's image fails, **When** its review card renders, **Then**
   it falls back to that garment's own region of the original photo rather than failing the card or
   blocking the save — the card remains fully saveable either way.
3. **Given** a garment photographed on a hanger against a plain background (today's typical
   single-item case), **When** it is processed, **Then** the isolated image looks at least as clean
   as what the app already produces for that case today.

---

### User Story 5 - Original photos are never lost (Priority: P3)

Whatever a garment's isolated image ends up looking like, the actual photo the user took is always
kept and can still be viewed later — the product's promise is that these are the user's actual
clothes, not a stylized rendering of them.

**Why this priority**: Trust, not core function — the feature works without this being visible day to
day, but retaining and exposing the original is what keeps a generated or cut-out image from silently
replacing the evidence it was derived from.

**Independent Test**: Save an item whose image was isolated, open its item detail page, and confirm
the original uploaded photo is still viewable from there.

**Acceptance Scenarios**:

1. **Given** an item saved from a photo that had several garments in it, **When** its detail page is
   opened, **Then** the user can view the original photo the item came from, not only the isolated
   cutout.
2. **Given** an item whose isolation failed at save time, **When** its detail page is opened,
   **Then** it behaves exactly as an item without an isolated image does today — no broken image, no
   dead control.

---

### Edge Cases

- A photo has more distinguishable garments than the detection limit allows — handled by User Story
  1's acceptance scenario 3 (top-confidence subset, explicit "not everything was captured" signal).
- A photo has zero confidently-identifiable garments — handled by User Story 2's acceptance scenario
  3 (one blank-ish card, never zero cards).
- A garment is worn by a person rather than laid out — detection and isolation both apply to it the
  same as a laid-out garment; the person is not itself a "detection."
- A garment is partially occluded by another garment or by a fold — extraction may leave more fields
  blank than an unoccluded item would, which is expected and handled by the existing null-field
  convention, not a new failure mode.
- Two detections in the same photo are close enough that a naive read might treat them as one garment
  or double-count one garment as two — accuracy against this is part of what the fixture corpus (which
  deliberately includes a flat-lay and an occluded case) and the eval harness must demonstrate.
- The photo upload itself fails (a genuine Storage error, not an extraction or isolation outcome) —
  unchanged from today: the existing bulk-upload error state and per-photo retry apply, before
  detection is ever attempted.
- A user bulk-uploads several photos, each producing a different number of detections — the review
  queue and its position indicator must reflect the true total across all photos, not the file count.

## Requirements *(mandatory)*

### Functional Requirements

**Detection (#45)**

- **FR-001**: The photo-extraction endpoint MUST return a list of review drafts for every photo, never
  a single draft object — including when exactly one garment is found, so callers handle one shape
  consistently regardless of how many garments a photo contains.
- **FR-002**: The system MUST accept up to 8 detections from a single photo. Above that limit, it MUST
  keep the 8 most confidently identified garments and MUST indicate to the caller that additional,
  uncaptured garments were present in the photo, rather than silently dropping them or rejecting the
  whole upload.
- **FR-003**: If the detection step itself fails to run, or completes but confidently identifies no
  garments, the system MUST fall back to today's single-draft behavior: exactly one review draft
  covering the whole photo. The system MUST NOT return zero drafts for a successfully uploaded photo.
- **FR-004**: A photo containing exactly one garment MUST produce exactly one review draft, with the
  same fields and the same practical wait as today's single-item flow.

**Extraction accuracy (#46)**

- **FR-005**: The extraction prompt MUST describe and label multiple garments within one photo without
  adding, removing, or changing which attributes are extracted per garment — the same attribute set
  (category, colors, fabric, warmth, formality, season, pattern, fit, background color) applies
  unchanged, one instance per detection.
- **FR-006**: Each garment's extracted category MUST prefer the most specific matching type over a
  bare category group, matching the standard already applied to single-item photos.
- **FR-007**: Attributes for one detection MUST describe only that detection's garment, not a
  neighboring garment in the same photo.
- **FR-008**: An attribute the system cannot confidently determine MUST be left blank rather than
  guessed, per detection, matching the existing single-item convention.
- **FR-009**: Every accuracy claim about the rewritten prompt MUST be demonstrated by running the
  fixture corpus through the evaluation harness before and after the change and recording the result,
  not asserted from reading the prompt. Every evaluation row MUST record which prompt version and
  which model produced it.

**Isolation (#48)**

- **FR-010**: For every detection, the system MUST attempt to produce a clean image of that garment
  alone, with its surroundings removed, using one of several interchangeable isolation strategies
  selected by configuration rather than hardcoded per call site.
- **FR-011**: One of the strategies MUST work by segmenting the garment out of its surroundings; one
  MUST work by generatively reconstructing a clean product-style image of the garment; one MUST be a
  hybrid that segments first and only falls through to generative reconstruction when the segmentation
  result is inadequate.
- **FR-012**: The hybrid strategy's decision to fall through to generative reconstruction MUST be
  based on a measurable property of the segmentation result (e.g. the isolated area covering an
  implausibly small or implausibly large fraction of the frame, or the segmentation call itself
  failing or timing out) — never on an unspecified, unmeasurable judgment of whether the result "looks
  bad."
- **FR-013**: If isolating a given detection fails or exceeds its time budget, that detection's review
  card MUST fall back to showing that garment's own region of the original photo, and the card MUST
  remain fully saveable — an isolation failure MUST NOT fail extraction, MUST NOT block the save, and
  MUST NOT be surfaced as an error to the user.
- **FR-014**: The system MUST run isolation as part of producing each review card (not deferred to
  after save), bounded by a per-detection time budget, so the review queue's existing all-scanned-
  upfront behavior is preserved rather than gaining a second, separate waiting state.
- **FR-015**: Isolation strategies MUST NOT depend on installing heavyweight in-process machine-learning
  runtimes or model weights into the backend service — every strategy MUST be reachable as a
  hosted/external call, preserving the deployment's existing image size and cold-start characteristics.
- **FR-016**: The default isolation strategy used in production MUST be the one measured to be cheapest
  and fastest of the three, unless the measured data justifies a different default — the choice MUST be
  recorded as a decision, not left implicit in configuration.

**Storage and schema**

- **FR-017**: The original uploaded photo MUST always be retained in Storage unmodified, regardless of
  how many garments were detected in it or whether isolation succeeded for any of them.
- **FR-018**: Each item's isolated image, when isolation succeeds and the item is saved, MUST be
  stored as its own Storage object under that user's existing Storage prefix, and `wardrobe_items` MUST
  gain one new column pointing to it, added by migration. This is an additive schema change to where an
  image lives, not a change to the item taxonomy, and does not require the taxonomy's breaking-change
  process.
- **FR-019**: The closet grid tile and the review card MUST render a detection's isolated image when
  one exists, falling back to the original (or, on the review card, that garment's own region of the
  original) when it does not.
- **FR-020**: The item detail page MUST render the isolated image by default when one exists, and MUST
  let the user switch to viewing the original photo. The closet grid and the review card MUST NOT
  offer this switch — only the detail page is the surface where a user deliberately checks provenance.
- **FR-021**: Once a detection's image has been isolated, its background is removed, so the extracted
  `background_color` value no longer describes what that image is padded with; a removed background
  MUST be padded using the app's standard neutral surface treatment instead. `background_color`
  continues to mean what it means today for any image still showing its original, unremoved
  background (the fallback cases in FR-013 and FR-019).
- **FR-022**: The existing orientation-aware photo treatment MUST apply to isolated images exactly as
  it does to any other photo the app renders — no separate treatment for cut-outs.

**Frontend**

- **FR-023**: The bulk-upload review queue MUST be keyed to individual detections, not to uploaded
  files — a batch of photos producing a mixed number of detections per photo MUST still produce one
  card per detection in the queue.
- **FR-024**: The "Reviewing item X of Y" indicator MUST count detections across the whole batch, not
  files uploaded.
- **FR-025**: The single-photo add-item entry point MUST remain the entry point for adding items one
  photo at a time; when that photo yields more than one detection, the user reviews them the same way
  a bulk upload's multiple cards are reviewed today.
- **FR-026**: A genuine photo upload failure (Storage rejects or cannot accept the file) MUST continue
  to use the existing upload-error state and per-photo retry, unaffected by how many garments the
  photo might contain — this failure precedes detection and is unrelated to it.
- **FR-027**: A card whose extraction did not succeed MUST continue to be a normal 200 response with
  `extraction_ok: false`, per detection — never a server error, matching today's single-item behavior.

### Key Entities

- **Detection**: One garment identified within an uploaded photo. Carries the region of the photo it
  occupies, its own extracted attributes, its own `extraction_ok` outcome, and — when isolation
  succeeded — its own isolated image. A single-garment photo yields exactly one detection.
- **Original photo**: The one file the user uploaded. Immutable evidence, always retained, independent
  of how many detections or isolated images are derived from it.
- **Isolated image**: The clean, background-removed image produced for a detection by whichever
  isolation strategy is configured. Optional per detection — its absence is a normal, saveable outcome,
  not an error state.
- **Extraction draft**: The reviewable unit shown to the user (today: one per photo; from this feature
  on: one per detection) — the same shape as today's draft, now addressed by detection rather than by
  photo.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A photo containing exactly one garment produces exactly one review card, with a wait
  time indistinguishable from today's single-item flow.
- **SC-002**: A photo containing several garments produces one review card per garment, up to 8, with
  no photo ever producing zero cards.
- **SC-003**: On the expanded fixture corpus, extraction accuracy on category correctness, attribute
  completeness, and name specificity measurably improves over the prior prompt version, as recorded by
  the evaluation harness — not merely asserted.
- **SC-004**: On photos where a garment is laid out against a plain background or on a hanger (today's
  best case), the isolated image is at least as clean as what the app already produces for that
  scenario today.
- **SC-005**: On photos where a garment is worn, part of a flat-lay, or partially occluded, a majority
  of detections on the fixture corpus produce a usable isolated image rather than falling back to the
  original.
- **SC-006**: The original photo remains viewable from an item's detail page for 100% of saved items,
  regardless of isolation outcome.
- **SC-007**: Processing a photo with the maximum 8 detections (detection, extraction, and isolation
  for all of them) completes within 30 seconds at the 50th percentile.
- **SC-008**: Processing one photo end to end — detection, extraction and isolation for every detection
  it contains, up to the limit — costs no more than $0.05 at the default configuration, verified
  against measured, not estimated, per-strategy costs.
- **SC-009**: A user can add every garment from one flat-lay or stack photo to their closet without
  re-uploading, without manually cropping, and without leaving the review queue.

## Assumptions

- The detection limit is 8 garments per photo. This is a product decision made here, not deferred: it
  covers the cases the issue names (a flat-lay, a folded stack, a rack) while bounding worst-case cost
  and latency, and bounding how many cards one review queue realistically asks a user to page through.
  Revisit if real usage shows photos routinely exceeding it.
- Isolation runs synchronously while a review card is being produced (blocking), not after save. This
  matches the review queue's existing all-scanned-upfront pattern (every photo is already scanned
  before any card is shown) and keeps the state machine to one waiting state instead of two. It is
  bounded by a per-detection timeout that falls through to the existing isolation-failure behavior
  (FR-013) rather than stalling the queue.
- Because isolation must stay within that blocking budget and within the per-photo cost ceiling
  (SC-008), and because in-process segmentation dependencies were already found unacceptable against
  this deployment's image-size and cold-start constraints (`docs/design-decisions.md` §56, §57), every
  isolation strategy is implemented as a hosted/external call rather than an in-process model. The
  segmentation strategy is expected to be the fastest and cheapest of the three and is the working
  default; the plan is expected to confirm this against real measurements (per FR-016) rather than
  assume it.
- The hybrid strategy's exact escalation thresholds (e.g. what counts as an implausibly small or large
  segmented area) are provisional pending the real before/after data the evaluation harness produces
  during planning and implementation. FR-012 fixes the *shape* of the trigger (a measurable property of
  the segmentation output) so it is never re-litigated down to "when it looks bad"; the specific
  threshold values are recorded as a decision once measured.
- The new `wardrobe_items` column added for the isolated image is additive and does not touch the
  frozen item taxonomy (category groups, formality enum, warmth scale, seasons, colors, pattern, fit) —
  Constitution VI's breaking-change process does not apply to this migration.
- The fixture corpus grows from its current two placeholder images to at least ten real closet photos,
  covering: a single garment on a hanger, a flat-lay with several garments, a garment worn by a person,
  and a garment that is partially occluded. Constitution Principle X's tracked-fixture-corpus carve-out
  already permits this.
- Populating the fixture corpus, running the evaluation harness for the before/after prompt comparison
  and the per-strategy isolation comparison, and recording the resulting decisions in
  `docs/design-decisions.md` (starting at §61) are execution-phase work for the planning and
  implementation steps that follow this spec, not this document itself.
- Out of scope for this slice: issue #50's accessory-specific attribute work, issue #51's
  outfit-on-body generation, and issue #53's background styling queue. Anything this slice's planning
  discovers and deliberately parks gets its own row in `docs/deferred-work.md`.
