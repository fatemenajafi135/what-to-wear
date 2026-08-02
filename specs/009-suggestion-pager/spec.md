# Feature Specification: Outfit suggestion pager

**Feature Branch**: `009-suggestion-pager`

**Created**: 2026-08-02

**Status**: Draft

**Input**: User description: "Feature 009: Outfit suggestion pager. Per docs/handoffs/009-
suggestion-pager.md: the styling route currently returns only the single top-ranked outfit
(outfits[0]) even though the pipeline has always produced a ranked list of ScoredOutfit. This
feature returns all outfits that clear the existing < 0.4 'not surfaced' floor and renders them
as a horizontal pager of outfit cards inside the assistant bubble, replacing 008's single flat
item-thumbnail-row rendering entirely. Each card has its own header (title + match-label pill +
a favorite heart), a plain-text description with NO citation badges, a wrapping item-thumbnail
grid, a meta line, and a thumbs-up/thumbs-down feedback footer that is pure component-local
state. Prev/next controls and a position indicator sit below the card track, hidden outright at
exactly one card. The pager behaves differently at mobile vs. tablet/desktop. This feature also
adds outfit persistence, which does not exist anywhere in the current schema: the pager's
favorite heart and the card's tap-through both need a saved outfit with an id, so this slice
adds a minimal outfits table (RLS + GRANT, two-user test), a save/unsave route, and wires the
heart to it. Feature 010 owns the Outfits gallery and Outfit detail screens that browse this
data. Explicitly out of scope: the Outfits gallery and Outfit detail screens, chat history,
feeding feedback to the recommender, any change to pipeline/scoring/retrieval behavior. Full
scope, constraints, traps and definition of done are in docs/handoffs/009-suggestion-pager.md —
treat it as authoritative and do not re-derive scope."

## Clarifications

None raised — the handoff (`docs/handoffs/009-suggestion-pager.md`) is authoritative on scope,
and the one named open scoping decision (§3, outfit persistence) is resolved in this spec's
Assumptions and recorded with rejected alternatives in `docs/design-decisions.md` §32. Two
further gaps the design system leaves ambiguous for this slice (whether the pager card carries
citations, and what the meta line's `{formality|weather}` actually renders) are resolved the
same way — decided here, recorded in `docs/design-decisions.md` §33-34 with alternatives, not
raised as blocking questions, because each has a single reading that is consistent with the rest
of the design system once § Badge and § Scores are read as authoritative over a briefer,
contradicting aside elsewhere in the same document (see Assumptions).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Page between several suggestions for one request (Priority: P1)

A signed-in user with a ready closet asks for an outfit and, when the pipeline surfaces more
than one viable suggestion, sees them as a set of cards they can page through one at a time,
each showing a distinct outfit with its own match quality, description and items.

**Why this priority**: This is the feature's entire value proposition — 008 already proves the
single-outfit path works; this story is what actually exposes the ranked list the pipeline has
always produced instead of silently discarding it.

**Independent Test**: Send a styling request that produces multiple outfits clearing the score
floor; confirm the assistant reply renders a pager (not a single flat card), the position
indicator reads "1 of N", and paging forward/back reveals a different outfit's items and
description each time.

**Acceptance Scenarios**:

1. **Given** a styling reply with 4 surfaced outfits, **When** the reply renders, **Then** the
   user sees one card at a time with a "1 of 4" indicator and working prev/next controls.
2. **Given** the user is on card 2 of 4, **When** they tap "next", **Then** card 3 becomes
   visible and the indicator updates to "2 of 4" → "3 of 4".
3. **Given** a styling reply with exactly one surfaced outfit, **When** the reply renders,
   **Then** the card appears with no prev/next controls and no position indicator at all (not
   greyed out — absent).
4. **Given** an outfit scores below the match floor, **When** the reply is assembled, **Then**
   that outfit never appears as a card, and the response is not counted against the group's
   card count.

---

### User Story 2 - Save a suggestion so it can be found again later (Priority: P1)

A user who likes one of the suggested outfits taps its heart and it becomes a saved outfit,
visible as favorited wherever saved outfits are later browsed, and the heart's state survives a
reload of the conversation.

**Why this priority**: The heart is one of two elements design specifies on every card (the
other is the card's own tap-through) and today nothing durable exists for either to point at —
without persistence the heart is either missing or a lie that forgets itself.

**Independent Test**: Tap a card's heart, reload the page, send a new styling request, and
confirm a re-fetch of the previously saved outfit (by id) still reports it as saved; tap the
heart again and confirm it now reports unsaved.

**Acceptance Scenarios**:

1. **Given** an unsaved suggestion card, **When** the user taps its heart, **Then** the heart
   fills solid and a row now exists, owned by that user, recording the outfit's items,
   description and match label.
2. **Given** a saved suggestion, **When** the user taps its heart again, **Then** the row's
   saved/favorited state flips off (the row itself is not deleted — a later, out-of-scope
   screen may still need to list a saved-but-unfavorited outfit).
3. **Given** a saved outfit belonging to user A, **When** user B queries their own saved
   outfits, **Then** user A's row never appears (RLS-and-GRANT proven by a two-user test).
4. **Given** a saved suggestion card, **When** the user taps anywhere on the card body (outside
   the heart, thumbnails, and feedback controls), **Then** they are navigated toward that
   outfit's detail destination — which does not exist as a built screen in this feature, so a
   404 there is the expected, honest result, not a defect.

---

### User Story 3 - Give quick feedback without it pretending to be saved (Priority: P2)

A user who wants to signal "this one's good" or "not this" without committing to saving it uses
the thumbs controls, and understands (implicitly, by the UI never claiming otherwise) that this
feedback isn't remembered anywhere.

**Why this priority**: Design specifies this control on every card; getting it backwards (wiring
it to persistence, or to the same state as the heart) would misrepresent what the product
actually does with feedback in this slice.

**Independent Test**: Tap thumbs-up on a card, confirm thumbs-down is unavailable at the same
time (mutually exclusive), tap it again and confirm it toggles off; reload and confirm no trace
of the choice survives anywhere.

**Acceptance Scenarios**:

1. **Given** neither thumb is selected, **When** the user taps thumbs-up, **Then** thumbs-up
   shows selected and thumbs-down is not simultaneously selectable as active.
2. **Given** thumbs-up is selected, **When** the user taps thumbs-down, **Then** thumbs-up
   deselects and thumbs-down becomes the selected one.
3. **Given** either thumb is selected, **When** the user taps the same thumb again, **Then** it
   deselects (back to neither selected).
4. **Given** any thumb state on any card, **When** the page is reloaded or a new request is
   sent, **Then** no prior thumb state is restored or referenced anywhere.

---

### User Story 4 - The pager behaves correctly for the device in hand (Priority: P2)

A user on a phone pages between suggestions using only the arrow buttons, with no ambiguous
swipe gesture competing with the thumbnail grid or the page itself; a user on a tablet or
desktop can also drag/scroll the card track directly, with neighboring cards peeking at the
edges as a hint that more exist.

**Why this priority**: The handoff names this as one of the traps most likely to be gotten
backwards, and the two behaviors are deliberately different, not a single responsive shrink of
the same mechanism.

**Independent Test**: At a mobile viewport, confirm no native horizontal swipe changes the
visible card and only the arrow buttons do; at a tablet/desktop viewport, confirm the card track
is natively scrollable/draggable, snaps one card at a time, and the arrow buttons still work and
stay in sync with manual scroll position.

**Acceptance Scenarios**:

1. **Given** a mobile viewport, **When** the user attempts to swipe the card track directly,
   **Then** the visible card does not change (only the arrow buttons change it).
2. **Given** a tablet/desktop viewport, **When** the user drags/scrolls the card track, **Then**
   the visible card changes and settles on a single card (snap), and the position indicator and
   arrow-button disabled states update to match.
3. **Given** either viewport, **When** `prefers-reduced-motion` is set, **Then** the card change
   is not animated as a sliding motion.

---

### User Story 5 - Nothing appears when nothing is good enough, and failure is honest (Priority: P3)

A user whose request produces no suggestion above the match floor sees a clear, actionable empty
message instead of an empty or broken-looking pager; a user whose request fails outright sees a
distinct error message with a way to retry.

**Why this priority**: Correctness of the floor-filtering rule and honest failure messaging
matter, but are a smaller slice of user-visible behavior than stories 1-2, and reuse patterns
008 already established for the single-outfit case.

**Independent Test**: Force a reply where every candidate scores below 0.4 (or the pipeline
returns zero outfits) and confirm the Empty message appears, not an empty-looking pager; force a
request failure and confirm the distinct Error card with retry appears instead.

**Acceptance Scenarios**:

1. **Given** a reply where all candidate outfits score below the match floor, **When** the
   reply is assembled, **Then** the user sees the Empty message, not a pager with zero cards.
2. **Given** a request that fails outright, **When** the failure occurs, **Then** the user sees
   the Error card with a "Try again" action that re-sends the same request.

---

### Edge Cases

- What happens when a styling reply is still loading? A single skeleton card appears in place of
  the pager (no arrows/indicator, since the eventual count isn't known yet) — this is the
  group's own loading treatment, distinct from the ordinary "Thinking…" row 008 already uses for
  a request in flight.
- What happens to feedback state when the user pages to a different card and back? Each card
  keeps its own independent thumbs state — paging away and back does not reset or share it with
  another card.
- What happens if a user un-saves the one outfit whose detail screen they are mid-navigation
  toward? Out of scope here — the destination screen itself belongs to feature 010, so this
  slice cannot observe or test that interaction.
- What happens when an outfit has many items (up to ~10)? The thumbnail grid wraps onto more
  rows rather than scrolling or truncating; the card grows taller to fit.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST render every surfaced outfit from a styling reply (not just the
  top-ranked one) as its own card in a pager, when the reply produces more than zero.
- **FR-002**: The system MUST exclude any candidate outfit scoring below the existing match
  floor from the pager entirely — never rendered with a discouraging label.
- **FR-003**: The system MUST show a position indicator ("N of M") and prev/next controls when a
  reply's pager has more than one card, and MUST hide both entirely (not merely disable them)
  when it has exactly one.
- **FR-004**: The system MUST let the user page forward and backward through a reply's cards via
  explicit controls, independent of any native scroll/swipe behavior.
- **FR-005**: The system MUST prevent native swipe/scroll from changing the visible card at
  mobile widths, and MUST allow native scroll/drag to change it at tablet/desktop widths.
- **FR-006**: The system MUST let a user toggle a saved/favorited state on any individual
  suggestion card, independent of the reply it appeared in.
- **FR-007**: The system MUST persist a saved suggestion durably enough that its saved state can
  be confirmed again after a reload, independent of the conversation that produced it.
- **FR-008**: The system MUST scope every saved outfit to the user who saved it, and MUST NOT
  let one user observe or modify another user's saved outfit under any access path.
- **FR-009**: The system MUST provide a card-level tap target (outside the heart, thumbnails, and
  feedback controls) that navigates toward that specific saved outfit's own destination.
- **FR-010**: The system MUST NOT render any citation marker on a pager card.
- **FR-011**: The system MUST let a user record one of exactly two mutually-exclusive feedback
  states (or neither) per card, toggling off on a repeat selection of the same state.
- **FR-012**: The system MUST NOT persist card-level feedback anywhere, and MUST NOT feed it to
  any recommendation or personalization logic in this feature.
- **FR-013**: The system MUST render a wrapping item-thumbnail grid on each card that never
  scrolls horizontally, regardless of how many items the outfit carries (1 to ~10).
- **FR-014**: The system MUST show a distinct loading treatment for the pager group while a
  styling reply is in flight, separate from any per-card content.
- **FR-015**: The system MUST show a distinct Empty message (not an empty-looking pager) when a
  reply produces zero outfits above the match floor.
- **FR-016**: The system MUST show a distinct Error message with a retry action when a styling
  request fails outright, separate from the Empty case.
- **FR-017**: The system MUST NOT display a numeric score or percentage anywhere on any pager
  card.
- **FR-018**: The system MUST gate the sliding/transform animation between cards on the user's
  reduced-motion preference.

### Key Entities

- **Outfit suggestion (in-reply)**: one candidate outfit surfaced in a single styling reply —
  its resolved items, a plain-text description, and a match label; exists only for the life of
  that reply's rendering unless the user saves it.
- **Saved outfit**: a durable record of one outfit a user chose to keep — owned by exactly one
  user, holding what is needed to redisplay it as a card later (items, description, match
  label, saved/favorited state) — the first data this project has ever persisted for an outfit.
- **Suggestion feedback**: a per-card, transient thumbs-up/thumbs-down/neither state that exists
  only in the running page; never written anywhere durable.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user asking for an outfit and receiving multiple viable suggestions can view and
  page through all of them, not just the first, in a single conversation turn.
- **SC-002**: 100% of outfits shown anywhere in this feature score at or above the existing match
  floor — never a discouraging label, never a below-floor outfit rendered.
- **SC-003**: A user can save a suggestion and, after reloading, confirm it is still recorded as
  saved 100% of the time.
- **SC-004**: 0% of one user's saved outfits are ever visible or modifiable by a different user.
- **SC-005**: A user on a touch device has exactly one unambiguous way to change the visible
  suggestion (the arrow controls); a user on a larger screen has two (arrows and direct
  drag/scroll), and both always agree on which card is currently visible.
- **SC-006**: No screen in this feature ever displays a raw number or percentage representing
  outfit quality, and no pager card ever displays a citation marker.
- **SC-007**: A user whose request yields nothing above the floor sees an explained, actionable
  Empty state in 100% of such cases, distinguishable from a request that failed outright.

## Assumptions

- **Persistence scope (handoff §3, adopted)**: this feature owns adding the minimal outfit-
  persistence schema and the save/unsave route; it does not build any screen that lists or
  browses saved outfits (feature 010's job). The alternatives the handoff named — deferring the
  heart/tap-through entirely, or faking persistence with component-local state — are rejected
  for the reasons the handoff gives (a heart that forgets on reload misrepresents the product;
  deferring both leaves two design-specified elements missing from every card). Recorded with
  full alternatives in `docs/design-decisions.md` §32.
- **Card citations (design-system.md § Badge vs. § Screen anatomy → Recommend item 3)**: the
  dedicated, detailed § Outfit suggestion pager component spec and § Badge are treated as
  authoritative over a briefer, older aside in the screen-anatomy paragraph that still describes
  each pager card as carrying "its own citation-bearing reasoning block and rule list" — a
  description design-decisions.md judges to be an artifact of 008's single-outfit citation
  pattern not yet reconciled with the pager's own later, more specific spec. Pager cards never
  carry a citation marker. Recorded in `docs/design-decisions.md` §33.
- **Meta line source (`{occasion} · {formality|weather}`)**: both values come from the one
  request-level context the pipeline already produces per reply (not per outfit, since every
  card in one reply answers the same request), preferring the weather condition when the
  pipeline detected one and falling back to the requested formality otherwise. Recorded in
  `docs/design-decisions.md` §34.
- **Saved-outfit schema is minimal by design**: it stores exactly what is needed to reconstruct
  a card (items, description, match label, saved/favorited flag) and a few fields cheap enough
  to capture now that a later read would otherwise have no way to reconstruct faithfully (the
  request text and precomputed meta line); it does not anticipate feature 010's filtering/sort
  facets, which that feature can add via its own migration.
- **Un-saving does not delete**: tapping the heart a second time flips the same saved/favorited
  flag off rather than deleting the row, so a later, out-of-scope screen is not forced to treat
  "unfavorite" and "delete" as the same action (design-system.md's Outfits gallery specifies
  Delete as a distinct, separate action from favorite/unfavorite in its overflow menu).
- Calendar context, closet readiness gating, thread continuity, and the "Start styling"
  send/composer split all already exist (008) and are reused unmodified.
- The pipeline, scoring, and retrieval behavior are unmodified dependencies — this feature only
  changes how many of the pipeline's already-produced outfits reach the response and the screen.
