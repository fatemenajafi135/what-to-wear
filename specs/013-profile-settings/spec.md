# Feature Specification: Profile and Settings

**Feature Branch**: `feat/013-profile-settings`

**Created**: 2026-07-31

**Status**: Draft

**Input**: User description: "Profile and Settings. A user can view their profile at /profile (three cards, gear icon to settings, sign-out already exists) and manage their settings at /profile/settings across five in-page sections: Style preferences (style tags, colour tags, brands to avoid), Body & size (body shape, gender, birth date, height, top/bottom/shoe size), Account (editable email), Connected accounts (Google Calendar row rendered disconnected/inert — feature 012 owns the toggle; Weather services 'Coming soon'), and Notifications (push notifications switch, default on, commits immediately). Every section except Notifications has an Edit/Done toggle that commits a draft back to a new `user_profile` table on Done, scoped per-user via RLS."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - View profile (Priority: P1)

A signed-in user opens Profile and sees their account at a glance: three cards summarizing what they've told the app about themselves, with a way to reach deeper settings and to sign out.

**Why this priority**: Profile is the entry point to every other capability in this feature; without it, Settings has no way to be reached from primary navigation.

**Independent Test**: Sign in, navigate to `/profile` via primary nav, confirm the three cards render (or their loading/error/empty state), the gear icon is present, and sign-out still works.

**Acceptance Scenarios**:

1. **Given** a signed-in user with no profile data saved yet, **When** they open `/profile`, **Then** the three cards render with their default/empty values rather than an error.
2. **Given** a signed-in user, **When** they tap the gear icon, **Then** they are taken to `/profile/settings`.
3. **Given** a signed-in user on `/profile`, **When** they tap "Sign out", **Then** they are signed out and returned to `/signin` (existing behavior, unchanged).

---

### User Story 2 - Declare style preferences (Priority: P1)

A user tells the app their style tags, colour tags, and brands to avoid, so this information is available for future features to draw on (this feature only stores it).

**Why this priority**: Style preferences is the section named first in the design and the one most directly tied to the product's stated purpose (personalized styling).

**Independent Test**: Open Settings, select the Style preferences section, tap Edit, change the selected style/colour tags and the brands-to-avoid list, tap Done, reload the page, and confirm the saved values persist.

**Acceptance Scenarios**:

1. **Given** the Style preferences section in its saved (non-edit) state, **When** the user taps "Edit", **Then** the style tags, colour tags, and brands-to-avoid controls become interactive, pre-filled with the last saved values.
2. **Given** the section is in edit mode with changes made, **When** the user taps "Done", **Then** the changes are persisted and the section returns to its saved (non-edit) state showing the new values.
3. **Given** the section is in edit mode with changes made, **When** the user navigates away without tapping "Done", **Then** the changes are discarded and the previously saved values are shown next time the section is opened.

---

### User Story 3 - Declare body & size details (Priority: P1)

A user records their body shape, gender, birth date, height, and garment sizes.

**Why this priority**: Equal in priority to style preferences — both are core declared-taste data this feature exists to capture — but separated because it is a materially different set of controls (illustrated single-select, date, multiple `Select`s) with its own edge cases (e.g., an invalid/future birth date).

**Independent Test**: Open the Body & size section, edit each field, save, reload, and confirm every field's saved value is shown correctly, including the illustrated body-shape selection.

**Acceptance Scenarios**:

1. **Given** the Body & size section, **When** the user selects a body shape, a gender option, a birth date, and each size field, then taps Done, **Then** all fields persist together as one saved state.
2. **Given** a user has never set a birth date, **When** they open the section, **Then** the birth date field shows an empty state rather than an invalid date.
3. **Given** the user enters a birth date in the future, **When** they attempt to save, **Then** the field shows a validation error and the save does not commit invalid data.

---

### User Story 4 - Update account email (Priority: P2)

A user views and edits the email address associated with their account.

**Why this priority**: Useful but narrower in scope (one field) than the two declared-preference sections above.

**Independent Test**: Open the Account section, edit the email field to a validly formatted address, save, and confirm the new value persists across a reload.

**Acceptance Scenarios**:

1. **Given** the Account section, **When** the user edits the email field to an invalid format and attempts to save, **Then** a validation error is shown and the change is not committed.
2. **Given** the Account section, **When** the user edits the email field to a valid address and taps Done, **Then** the new address is saved and shown as the current value.

---

### User Story 5 - View connected accounts and manage notifications (Priority: P3)

A user sees the state of Google Calendar and Weather services connections (without being able to change the calendar connection in this feature), and toggles push notifications on or off.

**Why this priority**: Connected accounts is mostly read-only display in this feature (the calendar toggle itself belongs to a different feature); Notifications is a single, low-complexity control. Both round out Settings but carry the least new capability.

**Independent Test**: Open the Connected accounts section and confirm Google Calendar renders in its disconnected appearance with its action inert, and Weather services shows a "Coming soon" badge. Open Notifications, toggle the switch, reload, and confirm the change persisted without needing an explicit save step.

**Acceptance Scenarios**:

1. **Given** the Connected accounts section, **When** the user views it, **Then** Google Calendar is shown in its disconnected appearance and any tap on its action has no effect.
2. **Given** the Connected accounts section, **When** the user views it, **Then** Weather services is shown with a "Coming soon" badge and is not interactive.
3. **Given** the Notifications section, **When** the user toggles push notifications, **Then** the new state is saved immediately, with no Edit/Done step.

---

### Edge Cases

- What happens when a save request fails (network error or server error) while a section is in edit mode? The section shows the shared Settings error state (`settings.error.body` / `settings.error.cta`) and the user's in-progress edits remain visible so they are not lost by the failure.
- What happens when the user is offline while attempting to save? The global offline banner is shown and the Edit/Done affordance (and the Notifications switch) is disabled for the duration, per the app-wide offline convention.
- What happens the very first time a user (who has never saved a profile) opens Settings? Every section shows sensible empty defaults (no tags selected, no sizes chosen, notifications on) rather than an error, since "no row yet" is expected, not exceptional.
- What happens if two browser tabs edit the same section concurrently? Last write wins; this feature does not implement optimistic-concurrency conflict detection (see Assumptions).
- What happens when the Style preferences "Brands to avoid" list is edited but the user removes every tag? An empty list is a valid, savable state (not the same as "unset").

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a `/profile` screen showing three cards summarizing the signed-in user's profile, reachable from primary navigation, with no separate page title (a single visually-hidden `<h1>`) per the design system.
- **FR-002**: The `/profile` screen MUST provide a control that navigates to `/profile/settings`.
- **FR-003**: The system MUST provide a `/profile/settings` screen with an in-page switcher (not separate routes) across exactly five sections: Style preferences, Body & size, Account, Connected accounts, Notifications.
- **FR-004**: The Style preferences section MUST let a user select any number of style tags from a fixed set (Classic, Minimal, Bold, Casual, Edgy), any number of colour tags from a fixed set (Neutral tones, Jewel tones, Pastels, Monochrome, Earth tones), and freely add/remove text tags naming brands to avoid.
- **FR-005**: The Body & size section MUST let a user select exactly one body shape from a fixed set of five illustrated options (Hourglass, Pear, Rectangle, Apple, Inverted triangle), exactly one gender option from a fixed set (Woman, Man, Non-binary, Prefer not to say), a birth date, a height, a top size, a bottom size, and a shoe size.
- **FR-006**: The Account section MUST let a user view and edit the email address associated with their account.
- **FR-007**: The Connected accounts section MUST display the Google Calendar connection in its disconnected appearance and MUST NOT allow this feature to change that connection state (ownership belongs to a different feature).
- **FR-008**: The Connected accounts section MUST display a Weather services row marked "Coming soon" that is not interactive.
- **FR-009**: The Notifications section MUST let a user turn push notifications on or off, defaulting to on for a user who has never changed it, and MUST persist a change immediately without a separate save step.
- **FR-010**: Every section except Notifications MUST provide an "Edit" control that reveals editable versions of that section's fields, pre-filled with the last saved values, and a "Done" control that persists the edited values as the new saved state and returns the section to its read-only appearance.
- **FR-011**: Navigating away from a section while it is in edit mode, without tapping "Done", MUST discard the in-progress edits; the previously saved values MUST be shown the next time the section is viewed.
- **FR-012**: All profile and settings data MUST be private to the user who owns it — no user can read or write another user's profile data through any path this feature exposes.
- **FR-013**: The system MUST persist Style preferences, Body & size, Account (email), and Notifications data such that it survives a page reload and a new sign-in session.
- **FR-014**: `/profile` and `/profile/settings` MUST each implement loading, error, and offline states in addition to their normal (ready) state, per the design system's state requirements.
- **FR-015**: A user opening Settings for the first time (no profile row saved yet) MUST see each section's defined default/empty values, not an error.

### Key Entities

- **User profile**: One record per user, holding their declared style tags, colour tags, brands-to-avoid list, body shape, gender, birth date, height, top/bottom/shoe size, and push-notification preference. Distinct from any model that infers taste from behavior — this entity only ever holds what the user explicitly stated. Owned exclusively by the user it belongs to.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can view their profile and reach Settings in two taps or fewer from primary navigation.
- **SC-002**: A user can change and save any one Settings section's values, reload the app, and see those exact values reflected, on every supported viewport width, in 100% of manual verification passes.
- **SC-003**: Abandoning an in-progress edit (navigating away without "Done") never alters the previously saved value, in 100% of manual verification passes.
- **SC-004**: No verification pass can retrieve another test user's profile data through the app or its API, under any account.
- **SC-005**: A first-time user (no saved profile) can open every Settings section without encountering an error state.

## Assumptions

- The user is already authenticated by the time they reach `/profile` or `/profile/settings` (feature 003); this feature does not add or change sign-in.
- The Google Calendar connect/disconnect action itself is out of scope — feature 012 owns the OAuth flow and the toggle's live behavior. This feature only renders the row in its specified disconnected appearance.
- Password change, account deletion, and data export are explicitly out of scope (deferred per `known-gaps.md` §0.6); Account exposes only the email field.
- Declared style/body preferences captured here are not consumed by any recommendation or styling logic in this feature — they are stored for a future feature to use, per the product decision recorded in this feature's research.
- Last-write-wins concurrency (no optimistic locking / conflict UI) is acceptable for this feature, consistent with the single-user-editing-their-own-data nature of Settings.
- "Brands to avoid" has no fixed vocabulary or maximum count; any free-text value the user types is accepted as entered (trimmed of surrounding whitespace, duplicates ignored).
