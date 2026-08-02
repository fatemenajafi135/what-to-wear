# Feature Specification: Outfits gallery + detail

**Feature Branch**: `feat/010-outfits`

**Created**: 2026-08-02

**Status**: Draft

**Input**: User description: "Outfits gallery + detail (feature 010) — browse saved outfits, filter/sort them, open one to see the full reasoning behind it (item photos, styling description with citations, styling rules, and a match breakdown), and manage a saved outfit (log as worn, rename, delete)."

## Clarifications

### Session 2026-08-02

- Q: The Outfits gallery needs to filter by occasion/weather/formality and sort by "most worn" —
  but the outfits table only stores free-text occasion and a single combined meta line, not
  discrete categories. How should filtering/sorting actually work given that gap? → A: Drop
  occasion/weather/formality filtering from this feature entirely for now — ship sort only (date
  added, most worn; favorited-first is unaffected since it's already a plain boolean). Track the
  dropped filter facets as a deliberate, recorded gap for a later feature, not a silent omission.
- Q: When a user taps "Log as worn today" on a saved outfit, should that also count as wearing
  each individual item in it (affecting per-item wear stats), or is outfit-level wear tracking
  completely separate? → A: Both — logging an outfit as worn today also logs every item in it as
  worn today (feature 005's existing per-item, per-day mechanism), because physically wearing the
  outfit means wearing every item in it.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Browse saved outfits (Priority: P1)

A user who has saved one or more outfits from the styling assistant opens the Outfits tab and
sees every outfit they've saved, most recently saved first, each shown as a card with its title,
overall match level, save date, and a preview of its items.

**Why this priority**: Without a working gallery, nothing saved from the styling assistant is
ever visible again — this is the entire reason the feature exists.

**Independent Test**: Save two or more outfits from the styling assistant, open the Outfits tab,
and confirm every saved outfit appears with its correct title, match level, date, and item
preview, newest first.

**Acceptance Scenarios**:

1. **Given** the user has saved 3 outfits, **When** they open the Outfits tab, **Then** they see
   3 cards ordered newest-saved-first, each showing a title, a match-level indicator, a save
   date, and up to 4 item thumbnails.
2. **Given** an outfit has more than 4 items, **When** its card renders, **Then** the user sees
   the first 3 item thumbnails plus a clear indicator of how many more items the outfit has.
3. **Given** the user has saved no outfits yet, **When** they open the Outfits tab, **Then** they
   see an explanation of what will appear there and a way to go start a styling conversation.
4. **Given** the user's outfits fail to load, **When** the Outfits tab opens, **Then** they see an
   explanation that loading failed and a way to retry.

---

### User Story 2 - See the full reasoning behind a saved outfit (Priority: P1)

A user taps a saved outfit to see every item in it clearly, read the styling explanation with
exactly which style guidance backed each part of it, see the underlying style rules spelled out,
and see how well each aspect of the outfit (color, formality, weather-fit, silhouette) scored —
without ever seeing a raw number.

**Why this priority**: This is the feature's other half of the mission ("see the full reasoning
behind it") and the reason a user would ever revisit a saved outfit instead of just glancing at
the gallery card.

**Independent Test**: Open a saved outfit's detail page and confirm every item is shown clearly,
the styling explanation references specific style guidance inline, the referenced guidance is
listed below in full, and a match breakdown shows one indicator per scoring aspect with an
overall level — with no numeric score or percentage displayed anywhere on the page.

**Acceptance Scenarios**:

1. **Given** a saved outfit with 5 items, **When** the user opens its detail page, **Then** every
   one of the 5 items is shown as its own clear, sizeable image — none hidden, none requiring a
   scroll gesture beyond the normal page scroll.
2. **Given** an outfit whose styling explanation was backed by specific style guidance when it
   was generated, **When** the user reads the explanation on the detail page, **Then** they see
   numbered markers inline in the text and, below it, a numbered list explaining what each marker
   refers to.
3. **Given** an outfit that was generated with no citable style guidance (the honest,
   nothing-to-cite case), **When** the user opens its detail page, **Then** the explanation reads
   as ordinary prose with no markers and no rules list, rather than showing an error or a broken
   reference.
4. **Given** any saved outfit, **When** the user views its match breakdown, **Then** they see an
   overall match-level label and one visual indicator per scoring aspect, and at no point on the
   page can they find a raw number or a percentage standing in for a score.
5. **Given** the user opens an outfit that no longer exists (e.g. already deleted from another
   session), **When** the detail page loads, **Then** they see a clear explanation and a way back
   to the gallery, not a blank or broken page.

---

### User Story 3 - Manage a saved outfit (Priority: P2)

From a saved outfit — either its gallery card or its detail page — a user can mark today as a day
they wore it, rename it to something more memorable, favorite/unfavorite it, or remove it
entirely from their saved outfits.

**Why this priority**: Valuable once outfits can be seen (P1s), but the feature is still usable
without it for a first pass — a user can browse and review reasoning without yet being able to
manage what they saved.

**Independent Test**: From an outfit's detail page, log it as worn, rename its title, and delete
it, confirming each action's effect is visible in the right place (worn status, updated title
across gallery and detail, and removal from the gallery after delete).

**Acceptance Scenarios**:

1. **Given** a saved outfit, **When** the user marks it as worn today from its management menu,
   **Then** the action succeeds once, and repeating it later the same day has no additional
   effect (it isn't possible to "wear an outfit twice" in a way the user can observe or that
   inflates any future count for that day).
2. **Given** a saved outfit titled "Business casual dinner", **When** the user renames it to
   "Friday client dinner" from the gallery card, **Then** the new title appears immediately on
   the card and also on that outfit's detail page.
3. **Given** a saved outfit, **When** the user taps the favorite heart on the gallery card or the
   detail page header, **Then** both stay in sync with the same favorited/unfavorited state
   regardless of which one was tapped (the management menu does not have its own separate
   favorite control — the heart is a direct action on both surfaces, not routed through a menu).
4. **Given** a saved outfit, **When** the user chooses to delete it, **Then** they are asked to
   confirm the irreversible action before it happens, and only after confirming is the outfit
   permanently removed from the gallery.
5. **Given** the user is offline, **When** they attempt to log a wear, rename, favorite, or
   delete, **Then** the action is disabled or clearly fails rather than appearing to succeed and
   silently being lost.

---

### User Story 4 - Sort saved outfits (Priority: P3)

A user with many saved outfits orders the gallery by save date, favorited-first, or how often
each outfit has been worn.

**Why this priority**: Pure quality-of-life once a user has accumulated enough saved outfits that
scrolling the full list is inconvenient — not needed for the gallery or detail page to deliver
value on day one.

**Independent Test**: With several outfits saved with different save dates, favorite states, and
worn counts, apply each sort order in turn and confirm the resulting order changes accordingly.

**Acceptance Scenarios**:

1. **Given** outfits with different save dates, favorite states, and worn counts, **When** the
   user changes the sort order, **Then** the list re-orders accordingly without changing which
   outfits are shown.
2. **Given** no sort has been explicitly chosen, **When** the user opens the gallery, **Then** it
   is ordered newest-saved-first by default.

> **Deferred, not dropped**: filtering by occasion, weather, or formality is out of scope for this
> feature (see Clarifications) because the data needed to classify a saved outfit into those
> categories doesn't exist yet in a reliable form. This is recorded as a known gap for a future
> feature, not silently omitted.

### Edge Cases

- An outfit is saved without the assistant's original conversation still available (e.g. the
  conversation state has since expired or the user saved it long ago in a previous session) — its
  detail page must still show every item, the plain description, and the overall match level; it
  degrades to showing no citation markers and no per-aspect score bars rather than failing to
  load, since that reasoning detail is genuinely unavailable, not merely slow to fetch.
- A saved outfit references an item the user has since removed from their closet — the detail
  page and gallery card show the outfit's remaining items rather than erroring on the missing one.
- Two rapid double-taps on "log as worn today" must not be visible to the user as two distinct
  events, and must not let a worn-count-based sort (User Story 4) count the same day twice — this
  applies both to the outfit's own worn-count and to each item's, since logging an outfit as worn
  also logs every item in it as worn (see Clarifications).
- An outfit contains an item the user has since removed from their closet, and the user logs the
  outfit as worn — the outfit-level wear still records normally; the removed item obviously can't
  receive its own item-level wear record, and this is not an error.
- A user attempts to view, rename, or delete an outfit that belongs to another account — this
  must fail exactly as if the outfit didn't exist, never revealing that it belongs to someone
  else.
- A title is renamed to an empty or whitespace-only value — the rename is rejected rather than
  leaving the outfit with a blank, unreadable title.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST show every outfit the signed-in user has saved, ordered newest
  first by default, each showing a title, an overall match-level indicator, the date saved, and a
  preview of its items (up to 4 shown; additional items indicated but not individually shown in
  the preview).
- **FR-002**: The system MUST let a user open any of their saved outfits to a dedicated view
  showing every item in that outfit at a clearly viewable size, with none hidden or requiring
  extra interaction to reveal.
- **FR-003**: The system MUST show a saved outfit's styling explanation as text, and, whenever
  that explanation was originally backed by specific style guidance, MUST show numbered inline
  markers in the text plus a corresponding numbered list explaining each one. When no style
  guidance backed the explanation (or that detail is no longer available), the system MUST show
  the explanation as plain prose with no markers and no list, never a fabricated or broken
  reference.
- **FR-004**: The system MUST show, for every saved outfit, an overall match-level label and one
  visual indicator per scoring aspect (color, formality, weather-fit, silhouette) that reflects
  the outfit's relative strength on that aspect. The system MUST NOT display a raw numeric score
  or a percentage for any score, on any screen, at any time.
- **FR-005**: A user MUST be able to mark a saved outfit as worn today. This MUST also mark every
  item currently in that outfit as worn today (consistent with feature 005's existing per-item
  wear tracking), skipping only items the user no longer owns. Repeating this action later the
  same calendar day for the same outfit MUST have no additional, user-visible, or count-inflating
  effect — for the outfit or for any of its items — beyond the first time that day.
- **FR-006**: A user MUST be able to rename a saved outfit's title directly from the gallery
  card. The new title MUST appear consistently everywhere that outfit's title is shown (gallery
  card and detail page). The system MUST reject a rename to an empty or whitespace-only title.
- **FR-007**: A user MUST be able to favorite or unfavorite a saved outfit directly from the
  gallery card and from the detail page, with the favorited state kept in sync regardless of
  which surface was used. The management menu does not offer a separate favorite action — the
  heart is a direct control on both surfaces, not a menu entry.
- **FR-008**: A user MUST be able to permanently delete a saved outfit, and the system MUST
  require an explicit confirmation step before deletion happens — a single tap MUST NOT be
  sufficient to delete an outfit.
- **FR-009**: *Deferred (see Clarifications) — not built in this feature.* Filtering saved
  outfits by occasion, weather, or formality is out of scope until a future feature gives saved
  outfits a reliable, structured category to filter by.
- **FR-010**: The system MUST let a user sort their saved outfits by save date (default), by
  favorited-first, or by how often worn.
- **FR-011**: The system MUST show a distinct message when the user has saved no outfits at all,
  guiding them to go start a styling conversation.
- **FR-012**: The system MUST prevent one user from viewing, renaming, logging a wear on, or
  deleting another user's saved outfit — any such attempt MUST behave identically to the outfit
  not existing at all.
- **FR-013**: The system MUST continue to show a saved outfit's items, plain description, and
  overall match level even when the citation markers and per-aspect score indicators are
  unavailable for that outfit (see Edge Cases) — the absence of that additional reasoning detail
  MUST NOT block viewing the outfit at all.
- **FR-014**: The system MUST disable or clearly fail any outfit-management action (wear, rename,
  favorite, delete) while the user has no network connection, rather than appearing to succeed.

### Key Entities

- **Saved outfit**: A styling suggestion the user has chosen to keep. Carries a user-editable
  title, the occasion and styling context it was generated for, its items, its styling
  explanation, its overall match level, whether it's favorited, and when it was saved. May
  additionally carry the specific style guidance that backed its explanation and its per-aspect
  score breakdown, when that detail was captured at save time.
- **Outfit wear log**: A record that a specific saved outfit was worn on a specific calendar day,
  used to support "how often worn" sorting. At most one such record exists per outfit per day.
  Logging one of these also produces an item-level wear record (feature 005's existing mechanism)
  for every item in the outfit the user still owns, on the same day.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can find and open any outfit they've saved in the last month within two taps
  from the Outfits tab.
- **SC-002**: 100% of saved outfits display every one of their items on the detail page with no
  items hidden behind scrolling, paging, or truncation.
- **SC-003**: 0% of screens in this feature ever display a raw numeric score or percentage in
  place of a match indicator, verified by review of every screen state.
- **SC-004**: A user can rename, favorite, log a wear on, or delete a saved outfit in a single
  focused interaction (one menu or one direct tap) without leaving the screen they started on.
- **SC-005**: Accidental deletion of a saved outfit without explicit confirmation occurs 0% of the
  time.
- **SC-006**: A user with an empty gallery always sees an explanation of why and a way to recover
  (go start styling) rather than a blank screen.
- **SC-007**: No user can ever retrieve, modify, or delete another user's saved outfit through any
  path this feature exposes.

## Assumptions

- This feature extends the `outfits` table and save/favorite mechanics feature 009 already built;
  it does not change how an outfit is first saved from the styling assistant.
- Citations and per-aspect scores are captured at the moment an outfit is saved, from the same
  styling result that produced it — they are never recomputed or re-generated afterward, since
  re-running the styling assistant later would produce different reasoning than what the user
  actually saved and acted on.
- "Worn today" for a saved outfit is tracked at the outfit level (needed to support "most worn"
  sorting for outfits specifically) and additionally logs a wear for every item still owned by the
  user (see Clarifications) — physically wearing the outfit means wearing its items.
- Deleting a saved outfit is permanent (no recovery/undo path) but requires an explicit
  confirmation step first, given the action cannot be undone.
- Filtering by occasion, weather, or formality is explicitly out of scope for this feature (see
  Clarifications) — only sorting ships now.
- Chat history, conversational-turn behavior, and any change to how outfits are generated,
  scored, or retrieved are out of scope for this feature.
- Sharing or exporting a saved outfit outside the app is out of scope for this feature.