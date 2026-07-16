# Feature Specification: Preference Memory

**Feature Branch**: `004-preference-memory`

**Created**: 2026-07-16

**Status**: Draft

**Input**: User description: "A signed-in user can react to an outfit suggestion they received, saying whether they liked it or rejecting it, optionally with a reason (e.g. \"don't like this color\", \"too formal for what I asked\"). Over time, the system learns from a user's rejections -- which colors they tend to reject, which categories they tend to avoid, whether they consistently want suggestions more or less formal than what was suggested -- and uses that learned preference to make future suggestions for that user better fit their taste, without the user having to restate their preferences every time. A user can see what the system has learned about their preferences, and can clear or correct it if it's wrong. A user's learned preferences are private to them and are not lost when the app restarts or is redeployed -- unlike today, where nothing about a user's feedback or preferences is saved anywhere."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - React to a suggestion (Priority: P1)

A signed-in user who just received an outfit suggestion tells the system
whether they liked it or not, and — when rejecting it — can optionally say
why in their own words.

**Why this priority**: Every other capability in this feature depends on
feedback existing to learn from. Without it, there's nothing to derive a
preference from and nothing to show the user.

**Independent Test**: After receiving a suggestion, react to it as liked;
react to a different suggestion as rejected, with and without a reason; in
both cases confirm the reaction is recorded and attributed to the correct
suggestion and the correct user.

**Acceptance Scenarios**:

1. **Given** a user has just received an outfit suggestion, **When** they
   mark it as liked, **Then** that reaction is recorded against that specific
   suggestion for that user.
2. **Given** a user has just received an outfit suggestion, **When** they
   mark it as rejected and optionally add a short reason, **Then** both the
   rejection and the reason (if given) are recorded against that suggestion.
3. **Given** a suggestion a user never reacts to, **When** time passes,
   **Then** it contributes no preference signal at all — silence is not
   treated as either a like or a rejection.

---

### User Story 2 - Future suggestions reflect what I've taught it (Priority: P1)

Without the user ever having to restate a preference, later suggestions for
that same user increasingly avoid colors and categories they've repeatedly
rejected, and trend toward the formality level they seem to actually want.

**Why this priority**: This is the entire point of the feature — collecting
feedback that never influences anything would be pointless. This is what
turns User Story 1's raw signal into user-visible value.

**Independent Test**: Have a user reject several suggestions that share a
common color, then request a new suggestion, and confirm that color appears
less often than it would have for a user with no such rejection history.

**Acceptance Scenarios**:

1. **Given** a user has repeatedly rejected suggestions containing a
   particular color, **When** they receive a new suggestion, **Then** that
   color is measurably less likely to appear than for a user with no
   rejection history.
2. **Given** a user has repeatedly rejected suggestions containing a
   particular category, **When** they receive a new suggestion, **Then**
   that category is avoided where a reasonable alternative exists.
3. **Given** a user's rejections show a consistent formality drift (e.g. they
   keep rejecting formal suggestions), **When** they receive a new
   suggestion, **Then** it trends toward the formality level implied by that
   pattern.
4. **Given** a user's explicitly stated request for a specific occasion or
   formality, **When** a suggestion is generated, **Then** the explicit
   request always takes precedence over a learned preference — a learned
   preference softly influences, and never overrides, what the user actually
   asked for this time.
5. **Given** a user with no feedback history yet, **When** they receive a
   suggestion, **Then** it is generated exactly as it would be today, with no
   degradation caused by the absence of a preference profile.

---

### User Story 3 - See what the system has learned about me (Priority: P2)

A user can look at a plain-language summary of the preferences the system
has derived from their feedback, so they understand why suggestions are
trending the way they are and can judge whether it's accurate.

**Why this priority**: Builds trust in User Story 2's effect — a user who
can't see what's influencing their suggestions has no way to tell whether
the system is learning correctly or just behaving strangely.

**Independent Test**: After a user has given enough feedback to produce a
derived preference (e.g. a rejected color pattern), open the preferences
view and confirm that signal appears in plain language, not raw data.

**Acceptance Scenarios**:

1. **Given** a user with a derived preference profile, **When** they view
   their preferences, **Then** they see a plain-language summary covering
   whatever has actually been learned (rejected colors, avoided categories,
   formality drift) — not shown as raw counts or internal identifiers.
2. **Given** a user with no feedback history yet, **When** they view their
   preferences, **Then** they see a clear "nothing learned yet" state, not an
   error or a blank/broken screen.

---

### User Story 4 - Clear or correct a learned preference (Priority: P2)

A user who disagrees with what the system has inferred can remove one
specific learned signal, or wipe their entire learned profile and start
over, without needing to delete their account or their feedback history
piecemeal.

**Why this priority**: A preference system a user can't correct will
eventually suggest things the user actively dislikes, with no way out except
abandoning the feature — this is what keeps it trustworthy over time.

**Independent Test**: With a user who has a multi-part derived preference
profile, remove one specific learned signal and confirm the rest of the
profile is untouched; separately, clear the entire profile and confirm
subsequent suggestions behave as if the user had no feedback history.

**Acceptance Scenarios**:

1. **Given** a user with several derived preference signals, **When** they
   remove one specific signal, **Then** only that signal is gone — the rest
   of the profile is unaffected.
2. **Given** a user with a derived preference profile, **When** they clear it
   entirely, **Then** subsequent suggestions are generated exactly as they
   would be for a user with no feedback history.
3. **Given** a user has corrected or cleared a preference, **When** they
   later give more feedback that would re-derive the same signal, **Then**
   it can be learned again — clearing is not a permanent block on that
   specific signal ever being learned in the future.

---

### Edge Cases

- What happens when a user tries to view, react to, or clear another user's
  feedback or preferences? Not reachable — same isolation guarantee as the
  existing closet system.
- What happens when a user reacts to the same suggestion twice (e.g. taps
  "like" then "reject")? The later reaction replaces the earlier one for
  that suggestion — a suggestion has at most one current reaction per user,
  not an accumulating history of reactions to itself.
- What happens with a single, one-off rejection (not a repeated pattern)?
  It MUST NOT immediately and drastically change future suggestions — a
  derived preference reflects a pattern across multiple feedback events, not
  an overreaction to one data point (see User Story 2, Acceptance Scenario
  1–3, and Assumptions).
- What happens when learned preferences conflict with each other (e.g. a
  user rejects blue in one outfit but likes a different blue outfit later)?
  The derived signal reflects the overall pattern across all feedback, not
  just the most recent event — an isolated contradiction doesn't erase an
  otherwise consistent pattern, and a genuine change in taste is reflected
  once enough new feedback establishes a new pattern.
- What happens to a user's feedback and preferences after the app restarts
  or is redeployed? Nothing is lost (FR-010) — this is explicitly the gap
  this feature closes relative to today's behavior.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST let a signed-in user record a reaction — liked or
  rejected — to a specific outfit suggestion they received.
- **FR-002**: System MUST let the user optionally attach a short free-text
  reason when rejecting a suggestion.
- **FR-003**: System MUST derive, from a user's pattern of rejections, at
  least: colors they tend to reject, categories they tend to avoid, and
  whether they consistently want suggestions more or less formal than what
  was given.
- **FR-004**: System MUST apply a user's derived preferences to future
  suggestions generated for that same user, without requiring the user to
  restate them.
- **FR-005**: A derived preference MUST only softly influence a suggestion —
  it MUST NOT override an explicit constraint the user stated in that
  request (e.g. a specific requested formality or occasion always wins over
  a learned drift).
- **FR-006**: A single feedback event MUST NOT cause a large, immediate
  change in future suggestions — derived preferences reflect a pattern
  across multiple feedback events, not a reaction to one data point.
- **FR-007**: System MUST let a user view a plain-language summary of the
  preferences currently derived from their feedback.
- **FR-008**: System MUST let a user with no feedback history see a clear
  "nothing learned yet" state when viewing their preferences, not an error.
- **FR-009**: System MUST let a user remove one specific derived preference
  signal without affecting the rest of their profile.
- **FR-010**: System MUST let a user clear their entire derived preference
  profile in a single action, after which future suggestions behave as if
  they had no feedback history.
- **FR-011**: A user's feedback and derived preferences MUST be visible and
  usable only by that user — never by any other user.
- **FR-012**: A user's feedback history and derived preferences MUST persist
  across application restarts and redeployments.
- **FR-013**: System MUST continue generating suggestions normally for a
  user with no feedback history — absence of a preference profile is not an
  error or degraded state.

### Key Entities

- **Suggestion Feedback**: One user's reaction (liked or rejected) to one
  specific outfit suggestion they received, with an optional free-text
  reason and when it happened. At most one current feedback record per
  suggestion per user (a later reaction replaces an earlier one on the same
  suggestion).
- **Preference Profile**: A per-user derived summary of learned taste
  signals (rejected colors, avoided categories, formality drift direction),
  computed from that user's accumulated feedback and used to softly
  influence future suggestions for that user only.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can react to a suggestion, liked or rejected, in a
  single action.
- **SC-002**: After a user rejects multiple suggestions sharing a common
  color, that color appears measurably less often in that user's next
  suggestions than it would for a user with no such history.
- **SC-003**: A user can view a plain-language summary of everything learned
  about their preferences in a single screen, with no raw internal data
  exposed.
- **SC-004**: A user can clear their entire preference profile in a single
  action, and their very next suggestion is generated exactly as it would be
  for a brand-new user.
- **SC-005**: Preferences learned in one session are still in effect in a
  later session, including after the application has been restarted or
  redeployed.
- **SC-006**: A new user with no feedback history receives suggestions with
  no visible degradation, delay, or error caused by the absence of a
  preference profile.

## Assumptions

- **Preference derivation is computed from structured suggestion data, not
  from interpreting the free-text reason.** Every outfit suggestion is
  already built from real closet items with known colors, categories, and
  formality. Deriving "rejected colors," "avoided categories," and
  "formality drift" from the *known attributes of rejected outfits*
  (aggregated across multiple rejections) is deterministic, testable, and
  needs no natural-language interpretation — consistent with the project's
  constitution (deterministic core, LLM at the edges). The free-text reason
  is captured and stored for the record (and may be shown back to the user
  alongside their feedback history) but does not itself drive derivation in
  this feature.
- **What counts as a "pattern"** (how many repeated signals before a
  preference is considered learned) is a tunable threshold decided at
  implementation time, not fixed by this spec — FR-006/Edge Cases only
  require that derivation is pattern-based, not reactive to a single event.
- **Reaction vocabulary is binary**: liked or rejected. No neutral/skip
  state, no star ratings, no partial-outfit (per-item) reactions — a
  reaction applies to the suggestion as a whole, matching how suggestions
  are already presented as complete outfits.
- **This feature does not require Feature 002's `/suggest`/graph work to
  exist.** The existing suggestion path already has a working preference
  hook (`profile_note`, read and injected into generation) that is simply
  never written to today — this feature closes that gap on the currently
  live suggestion path, not on not-yet-built infrastructure. If/when
  `/suggest` ships, the same preference profile applies there too.
- **Persistence mechanism is an implementation decision, not specified
  here** — this spec only requires that feedback and derived preferences
  survive restarts/redeploys (FR-012), not any particular storage
  technology.
- **No feedback UI is assumed to exist yet on suggestion results** — this
  feature adds it; today's suggestion screen (Feature 003) has no reaction
  affordance.
- **Suggestions themselves are not persisted as a separate history a user
  browses.** `/recommend` today returns an outfit and nothing about it is
  stored. Nothing in this spec (User Story 3 only surfaces the *aggregated*
  derived Preference Profile, never a log of individual past suggestions)
  requires that to change. A reaction can carry the reacted-to outfit's own
  item data directly (already known to whoever is submitting the reaction,
  since they just displayed it) rather than referencing a separately stored
  "suggestion" record — the simpler shape, and sufficient for every FR/SC
  above.
