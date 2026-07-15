# Feature Specification: MVP App

**Feature Branch**: `003-mvp-app`

**Created**: 2026-07-16

**Status**: Draft

**Input**: User description: "A user can sign in to the app and have their own private account. A user can add an item to their closet by taking or uploading a photo of a garment or accessory; the system automatically extracts its category, colors, fabric, warmth, formality, and season from the photo, and the user can review and correct any of these before it's saved to their closet. A user can view everything currently in their closet. A user can describe in plain English what they need to wear for an occasion and receive an outfit suggestion assembled from items they own, with a written rationale. The app is usable in a web browser on both a phone and a laptop, and is reachable at a public web address rather than only running locally. Every closet item carries the same attributes as the existing closet: a category (from the full existing set: top, bottom, full_body, outerwear, footwear, accessory), colors as hex values, a fabric, a warmth rating, a formality rating (the full existing six-value scale from casual to black tie), and applicable seasons, plus a pattern and a fit -- two new attributes not previously captured. Adding an item by photo is the primary way a user builds their closet in this feature; selecting from the shared catalog (already supported) remains available but is not the focus here. A user only ever sees and edits their own closet, never another user's."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Sign in to a private account (Priority: P1)

A person opens the app and creates an account or signs back in, so that
everything they do afterward — their closet, their suggestions — belongs to
them alone and nobody else can see or touch it.

**Why this priority**: Every other capability in this feature requires a
signed-in identity. Without this, nothing else can be demonstrated or used at
all.

**Independent Test**: A new person can create an account and reach a signed-in
state; closing and reopening the app in the same browser keeps them signed in;
signing out and back in with the same credentials restores access to the same
account.

**Acceptance Scenarios**:

1. **Given** a person has never used the app, **When** they complete account
   creation, **Then** they are signed in and land on a screen that is theirs
   alone.
2. **Given** a signed-in person closes and reopens the app, **When** the app
   loads again, **Then** they are still signed in without re-entering
   credentials (within a reasonable session window).
3. **Given** a person is not signed in, **When** they try to view a closet, add
   an item, or ask for a suggestion, **Then** they are directed to sign in
   first — none of these are reachable anonymously.

---

### User Story 2 - Add an item to my closet from a photo (Priority: P1)

A signed-in user photographs or uploads a picture of something they own —
a shirt, a jacket, a pair of shoes — and the app figures out what it is
(category, colors, fabric, warmth, formality, season, pattern, fit) so the
user doesn't have to type it all in by hand. The user checks the result and
fixes anything that's wrong before it's saved.

**Why this priority**: This is the primary, and for this feature the only
required, way a user actually builds a closet with their real belongings —
without it there's nothing for the suggestion flow to work from beyond
catalog seed data.

**Independent Test**: Starting from an empty closet, submit one photo of a
single garment, confirm the app returns a pre-filled set of attributes,
change at least one of them, save, and confirm the item appears in the
closet with the corrected values — not the original extracted ones.

**Acceptance Scenarios**:

1. **Given** a signed-in user with a photo of a garment, **When** they submit
   it, **Then** the app returns category, colors, fabric, warmth, formality,
   season, pattern, and fit pre-filled from the photo, and the item is not
   yet saved.
2. **Given** a pre-filled result from a photo, **When** the user changes one
   or more fields and confirms, **Then** the item is saved to their closet
   with the corrected values, not the originally extracted ones.
3. **Given** a photo the system cannot confidently interpret (blurry, no
   garment visible, extraction fails), **When** the user submits it,
   **Then** they see a clear message that extraction didn't work and can
   either retry with a different photo or fill in the attributes themselves
   — submitting a bad photo never silently fails or crashes.
4. **Given** a photo containing more than one garment, **When** the user
   submits it, **Then** the app treats the photo as depicting a single item
   (the primary/most prominent garment) — detecting and separating multiple
   garments from one photo is out of scope for this feature (see Assumptions).

---

### User Story 3 - View my closet (Priority: P1)

A signed-in user opens their closet and sees every item currently in it, so
they know what they actually have before asking for a suggestion.

**Why this priority**: Both the add-item flow (US2) and the suggestion flow
(US4) are meaningless to a user who can't see the result — this is the
confirmation loop that makes the other two trustworthy.

**Independent Test**: With a closet containing several items (some added by
photo, some pre-existing from catalog seeding), open the closet view and
confirm every item appears with its attributes; with an empty closet, confirm
an empty state is shown, not an error.

**Acceptance Scenarios**:

1. **Given** a user with items in their closet, **When** they open their
   closet, **Then** every item they own appears, each with its category,
   colors, and other attributes visible.
2. **Given** a user with an empty closet, **When** they open their closet,
   **Then** they see an empty state, not an error.
3. **Given** two different users each with their own items, **When** either
   opens their closet, **Then** they see only their own items, never the
   other's.

---

### User Story 4 - Get an outfit suggestion (Priority: P1)

A signed-in user types in plain language what they need ("something for a
casual dinner tonight") and gets back an outfit assembled entirely from
items in their own closet, along with a short written explanation of why it
works.

**Why this priority**: This is the actual point of the app — the other three
stories all exist to make this one possible and trustworthy.

**Independent Test**: With a closet stocked well enough to dress the
occasion, submit a plain-English request and confirm an outfit comes back
built only from owned items, with an accompanying rationale.

**Acceptance Scenarios**:

1. **Given** a user with a closet that can dress a stated occasion, **When**
   they describe what they need in plain English, **Then** they receive an
   outfit made only of items they own, with a written explanation.
2. **Given** a user whose closet cannot dress the stated occasion (missing
   required pieces), **When** they ask for a suggestion, **Then** they see a
   clear explanation that their closet doesn't have enough, not an error or a
   fabricated outfit.
3. **Given** a returned suggestion, **When** the user asks a completely new,
   unrelated question afterward, **Then** it is treated as a new request —
   conversational follow-up ("warmer", "less formal") on the same request is
   out of scope for this feature (see Assumptions).

---

### Edge Cases

- What happens when a user tries to view or add to another user's closet?
  Not reachable — same isolation guarantee as the existing closet system.
- What happens when photo upload succeeds but attribute extraction returns
  nothing usable? The user sees a clear "couldn't process that photo" state
  and can retry or fill in fields manually (US2, Acceptance Scenario 3) —
  never a raw error or a silently empty item.
- What happens when a user's session expires mid-action (e.g., mid-photo
  upload)? They're prompted to sign in again; nothing partially-entered is
  silently lost without a clear message.
- What happens when the app is opened on a very small phone screen vs. a
  laptop? All four flows above remain fully usable at both sizes — this is
  what "usable in a browser on both a phone and a laptop" means concretely.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST let a person create an account and sign in, and
  MUST NOT allow viewing or modifying closet data, or requesting a
  suggestion, without being signed in.
- **FR-002**: System MUST keep a signed-in session valid across normal app
  use (closing/reopening the app) without requiring re-entry of credentials
  every time.
- **FR-003**: System MUST let a signed-in user submit a photo (captured live
  or chosen from an existing photo) of a single garment or accessory to add
  it to their own closet.
- **FR-004**: System MUST automatically extract, from a submitted photo:
  category, colors, fabric, warmth, formality, season, pattern, and fit.
- **FR-005**: System MUST let the user review every extracted attribute and
  correct any of them before the item is saved; the saved item MUST reflect
  the user's corrections, not the raw extraction, wherever they differ.
- **FR-006**: System MUST let the user save the item even when extraction
  could not confidently determine one or more attributes, by having the user
  fill in those attributes directly — extraction failure MUST NOT block
  adding the item.
- **FR-007**: System MUST let a signed-in user view every item currently in
  their own closet, and MUST NOT show items belonging to any other user.
- **FR-008**: System MUST let a signed-in user describe, in free-form plain
  English, what they need to wear, and receive an outfit suggestion.
- **FR-009**: Every returned outfit suggestion MUST be built only from items
  that exist in the requesting user's own closet — no invented or
  other-user items.
- **FR-010**: Every returned outfit suggestion MUST include a written
  rationale explaining why it was chosen.
- **FR-011**: System MUST be usable end-to-end (sign in, add by photo, view
  closet, get a suggestion) from a standard web browser running on a mobile
  phone screen and on a laptop/desktop screen.
- **FR-012**: System MUST be reachable at a public web address, usable
  without any local development setup on the accessing device.
- **FR-013**: Every closet item MUST carry: category (one of the existing six
  groups — top, bottom, full_body, outerwear, footwear, accessory), one or
  more colors as hex values, a fabric, a warmth rating, a formality rating
  (the existing six-value scale, casual through black tie), one or more
  applicable seasons, a pattern, and a fit.
- **FR-014**: Selecting an item from the shared catalog to add to a closet
  MUST remain available (it already exists) but is not required to be
  exposed as a primary flow in this feature's user-facing surface.

### Key Entities

- **Account**: A person's private identity in the app. Owns exactly one
  closet; nobody else can see or modify it.
- **Closet Item**: A single garment or accessory a specific user owns,
  carrying category, colors, fabric, warmth, formality, season, pattern, and
  fit, and how it entered the closet (photo-extracted-and-corrected, or
  selected from the shared catalog).
- **Outfit Suggestion**: A set of the user's own closet items assembled to
  answer one plain-English request, together with a written explanation of
  why those items were chosen.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A first-time visitor can go from no account to seeing their
  first outfit suggestion in a single sitting, without any developer
  assistance or manual data setup on their behalf.
- **SC-002**: A user can add one item to their closet from a photo, including
  reviewing and correcting its attributes, in under 2 minutes.
- **SC-003**: 100% of items saved to a closet have every required attribute
  populated (category, colors, fabric, warmth, formality, season, pattern,
  fit) — none left blank, whether from extraction or manual entry.
- **SC-004**: All four core flows (sign in, add by photo, view closet, get a
  suggestion) are fully completable on a phone-sized browser window and on a
  laptop-sized browser window, without any flow being unreachable or broken
  at either size.
- **SC-005**: The app is reachable and fully usable from a public web address
  by someone who has never accessed the project's local development
  environment.
- **SC-006**: A user asking for a suggestion their closet cannot fulfill sees
  a clear explanation within the same interaction, never a raw error or a
  fabricated outfit.

## Assumptions

- **Account creation method**: standard email/password sign-up and sign-in.
  No social/OAuth login, no magic-link, no invite system — the simplest path
  that satisfies "a person can get their own private account," matching this
  feature's minimal-first framing.
- **One garment per photo**: a submitted photo is treated as depicting a
  single item. Detecting and separating multiple garments within one photo
  is explicitly out of scope for this feature (deferred to a later,
  non-minimal iteration).
- **Suggestion flow is single-turn**: a request produces one suggestion
  response; conversational refinement of that same request ("warmer", "less
  formal") without restating it is explicitly out of scope for this feature
  — it depends on conversational-refinement capability that is a separate,
  not-yet-built feature. A user can always ask a new, fully-restated request.
- **Catalog-based adding is unchanged, not rebuilt**: the existing
  catalog-selection path for adding an item is not removed and is not
  required to be a primary, prominent flow in this feature's interface.
- **Occasion input has no fixed picker**: the user's request is free text,
  not a fixed set of occasion buttons — matches how outfit suggestions are
  already generated today.
- **Underlying suggestion generation reuses what already exists**: this
  feature does not require building new item-selection logic — it surfaces
  the existing suggestion capability through a real interface, reachable by
  a signed-in user for their own closet only.
- **Deployment**: "reachable at a public web address" means the app is
  live and accessible over the internet at the time it's demonstrated; it
  does not imply production-grade scaling, monitoring, or hardening (those
  remain a separate, later concern).
- **Schema is additive only**: pattern and fit are new, optional attributes
  added to the existing closet item shape; no existing attribute is renamed,
  removed, or redefined.
- **Pattern and fit are free-text, not a fixed set of options**: matching the
  existing `fabric` attribute's precedent (also free-text) rather than the
  controlled vocabularies used for category/formality/season. No product
  reason surfaced to constrain them, and a closed list can always be added
  later without breaking existing data.
- **No confidence-level flagging on extracted fields**: every extracted
  attribute is presented as an equally editable, pre-filled value (FR-005);
  the system does not distinguish "confident" from "uncertain" extractions
  for the user. Matches this feature's minimal-first framing — confidence
  scoring is real added complexity (the extraction step would need to report
  per-field confidence, the interface would need to visually distinguish it)
  with no functional requirement driving it; every field is reviewable and
  correctable regardless, which already satisfies FR-005/FR-006.
