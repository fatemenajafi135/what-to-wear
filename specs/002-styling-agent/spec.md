# Feature Specification: Styling Agent

**Feature Branch**: `002-styling-agent`

**Created**: 2026-07-15

**Status**: Draft

**Input**: User description: "A user describes what they need in plain English and receives three to five complete outfit suggestions from their own closet, each with a written rationale. The system accounts for local weather, the occasion and mood in the request, the season, and the user's body shape. Suggestions follow professional styling principles retrieved from the style knowledge base. The retrieved principles determine what is asked of the closet, and the rationale is grounded in those same principles. Each outfit is scored on separately reportable dimensions: color harmony, formality coherence, weather fitness, and silhouette balance. These scores are computed by deterministic code, not by a language model. If the closet cannot fill a required slot, a similar catalog item is suggested and clearly marked as one the user does not own. The user can ask for alternatives, and can refine conversationally ("warmer", "less formal") without restating the original request."

## Overview

This feature turns the existing linear recommendation pipeline into the product's
core styling experience: an authenticated user describes an occasion in plain
English and gets several complete, grounded outfit suggestions **built only from
items they own**, each explained and each scored on objective dimensions. The
suggestion engine selects and ranks outfits with deterministic code; the language
model only parses the request and writes the human-readable rationale — it never
picks the clothes.

The feature is delivered in **four phases** (see the delivery note below). Phase 1
is pure hardening with no user-visible change; Phases 2–4 build up the scored,
grounded, refinable suggestion experience. Each phase is independently mergeable.

## Clarifications

### Session 2026-07-15

- Q: Where does the user's body shape come from for silhouette scoring? → A: Out of
  scope for the MVP; deferred to a later feature. Silhouette balance is scored on
  general proportion/balance principles, not personalized to a body shape.
- Q: How should the four dimension scores combine into the ranking order? → A: Do
  not lock in one formula. Ship a single default (equal-weighted average) but keep
  the combination strategy **swappable/configurable** so alternatives (fixed
  weights, fit-first lexicographic) can be experimented with and compared during
  evaluation; document the alternatives rather than hard-coding one.
- Q: How many not-owned catalog substitutes may an outfit contain? → A: Catalog
  substitution is **not supported in this feature** — when the closet cannot fill a
  required slot, the outfit is omitted. Recorded as future work.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Suggestions are private to the requester (Priority: P1)

A signed-in user asks for outfit ideas and only ever receives suggestions built
from **their own** closet. No one can obtain another person's closet contents or
suggestions by supplying someone else's identifier.

**Why this priority**: This is a live data-privacy gap in the current system — the
suggestion endpoint accepts a free-form user identifier with no authentication, so
anyone who knows or guesses another user's identifier can read that user's closet
through it. Closing this is a prerequisite for every other story: suggestions are
meaningless (and unsafe) if they aren't correctly scoped to the requester. It also
carries the backfill of automated checks for the existing deterministic logic so
later phases build on a tested base.

**Independent Test**: Call the suggestion flow without valid credentials and
confirm it is refused; call it with valid credentials and confirm the suggestions
are drawn only from the authenticated user's own closet, regardless of any
identifier present in the request body.

**Acceptance Scenarios**:

1. **Given** a request with no valid credentials, **When** the user requests
   suggestions, **Then** the request is refused as unauthorized and no closet data
   is returned.
2. **Given** a signed-in user A whose request body also contains user B's
   identifier, **When** A requests suggestions, **Then** the suggestions are built
   from A's closet only and B's closet is never read.
3. **Given** the existing deterministic building blocks (color handling, category
   grouping, citation assembly, query building, property checks), **When** the test
   suite runs, **Then** each has automated unit coverage that passes without
   depending on the language model.

---

### User Story 2 - Get grounded outfit suggestions from my own closet (Priority: P1)

A signed-in user describes what they need ("smart dinner on Friday, want to feel
put-together") and receives **three to five complete outfits** assembled entirely
from garments they own. Each outfit covers the body sensibly (e.g. top + bottom +
footwear, or a full-body piece + footwear, plus outerwear when the weather calls
for it) and comes with a written rationale. Every item shown is one the user owns,
and every rationale sentence cites the styling principle or objective signal it
rests on.

**Why this priority**: This is the feature's central promise and the product's
reason to exist. Without it there is no styling agent. It depends on US1 for
correct scoping.

**Independent Test**: As a user with a sufficiently stocked closet, submit a
plain-English request and confirm 3–5 complete outfits come back, each containing
only owned items, each covering the required garment slots, each with a rationale
that cites retrieved principles.

**Acceptance Scenarios**:

1. **Given** a user with a closet that can dress the occasion, **When** they submit
   a plain-English request, **Then** they receive between three and five complete
   outfits, each built only from items in their closet.
2. **Given** any returned outfit, **When** the user reads its rationale, **Then**
   every rationale sentence cites at least one retrieved styling principle or a
   reported objective score, and no item or principle is invented.
3. **Given** a request that implies cold or wet weather for the user's location,
   **When** suggestions are generated, **Then** each outfit includes appropriate
   warmth/outerwear, and warmth-inappropriate items are excluded.
4. **Given** a request stating an occasion and mood, **When** suggestions are
   generated, **Then** the retrieved styling principles reflect that occasion and
   mood and shape which closet items are considered.

---

### User Story 3 - See why each outfit works, on objective dimensions (Priority: P2)

Alongside each suggested outfit, the user sees a separate score for **color
harmony**, **formality coherence**, **weather fitness**, and **silhouette
balance**, each with a short human-readable reason. These scores are computed by
deterministic rules — the same rules used to rank the outfits and the same ones the
evaluation harness checks — not produced by a language model.

**Why this priority**: The objective scores are what let the user (and the project's
evaluation) trust a suggestion, and they are what drive ranking. They build directly
on US2's outfits. Prioritized just below the core suggestion flow because a
suggestion is still useful before the scores are surfaced, but the scores are what
make ranking and quality claims defensible.

**Independent Test**: For a given outfit, confirm four independently reported scores
are returned with reasons; confirm the same scoring code, run inside the evaluation
harness, produces the same numbers; confirm no score depends on a language-model
call.

**Acceptance Scenarios**:

1. **Given** a suggested outfit, **When** it is returned, **Then** it carries four
   separately reported dimension scores (color harmony, formality coherence, weather
   fitness, silhouette balance), each with a short reason.
2. **Given** two candidate outfits for the same request, **When** they are ranked,
   **Then** the higher-ranked outfit is the one the deterministic scores rate higher,
   and the ranking does not depend on any language-model judgment.
3. **Given** the same outfit and context, **When** scored twice, **Then** the four
   scores are identical (deterministic, no sampling variance).

---

### User Story 4 - Refine conversationally and get alternatives (Priority: P2)

After seeing suggestions, the user can ask for alternatives, or refine with short
follow-ups like "warmer" or "less formal", **without restating** the original
occasion, weather, or constraints. The follow-up is interpreted against the ongoing
conversation and produces updated suggestions.

**Why this priority**: Refinement is what makes the agent feel like a stylist rather
than a one-shot generator, but the one-shot suggestion (US2) already delivers value,
so this follows it.

**Independent Test**: Submit an initial request, then send "warmer" as a follow-up
in the same conversation, and confirm the new suggestions are warmer than the
previous set while preserving the original occasion and other unstated constraints.

**Acceptance Scenarios**:

1. **Given** a completed suggestion turn, **When** the user says "warmer" without
   restating the occasion, **Then** the new suggestions' mean item warmth rating
   (0–5 scale) increases by at least 1 compared to the previous suggestion set,
   while keeping the original occasion, mood, and other constraints.
2. **Given** a completed suggestion turn, **When** the user says "less formal",
   **Then** the new suggestions lower the formality band while keeping other
   constraints.
3. **Given** a completed suggestion turn, **When** the user asks for alternatives,
   **Then** a different set of outfits is returned for the same request.

### Edge Cases

- **Empty or tiny closet**: a closet with too few items to complete any outfit
  returns a clear "not enough items to build an outfit" outcome rather than an error
  or an incomplete outfit presented as complete.
- **No location / offline weather**: when local weather can't be resolved, the
  system falls back to a caller-supplied temperature or to season-only reasoning,
  and says which it used, rather than failing.
- **Contradictory refinement**: a refinement that can't be honored from the closet
  (e.g. "warmer" when the user owns nothing warmer) returns the best available set
  and states that the request couldn't be fully satisfied.
- **Retrieved principles conflict**: when two retrieved principles pull in opposite
  directions, the deterministic scoring breaks the tie; the rationale cites the
  principle that won.
- **Required slot cannot be filled from the closet**: the outfit is omitted rather
  than shown incomplete (catalog substitution is deferred — see Future Work).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The suggestion flow MUST require an authenticated user and MUST build
  suggestions only from that authenticated user's closet; it MUST NOT accept a
  user identity supplied in the request body as the basis for whose closet to read.
- **FR-002**: Given a plain-English request, the system MUST return between three
  and five complete outfits when the user's closet can support them, and fewer (down
  to a clear "not enough items" outcome) when it cannot.
- **FR-003**: Every item in every suggested outfit MUST be an item the user owns.
  The system MUST NOT present an item the user does not own. (Catalog substitution
  for unfillable slots is out of scope this feature — see FR-011 and Future Work.)
- **FR-004**: The system MUST retrieve professional styling principles from the
  style knowledge base **before** selecting closet items, and those retrieved
  principles MUST shape what is asked of the closet (they are not retrieved in
  parallel with, or after, wardrobe selection).
- **FR-005**: Every rationale statement attached to an outfit MUST cite at least one
  retrieved styling principle or a reported objective score; the system MUST NOT
  present rationale that cites an item or principle that was not actually retrieved
  or produced.
- **FR-006**: The system MUST account for local weather (resolved from the user's
  location, with a documented fallback), the occasion and mood in the request, and
  the season. (Body shape is out of scope this feature — see Future Work.)
- **FR-007**: Item selection, combination, and ranking MUST be performed by
  deterministic code. A language model MUST NOT choose which items appear in an
  outfit or determine the ranking order.
- **FR-008**: Each returned outfit MUST carry four separately reported dimension
  scores — color harmony, formality coherence, weather fitness, and silhouette
  balance — each accompanied by a short human-readable reason.
- **FR-009**: The four dimension scores MUST be computed by deterministic code that
  is reusable, unchanged, inside the evaluation harness; the same outfit and context
  MUST produce identical scores on repeated runs.
- **FR-009a**: The strategy for combining the four dimension scores into a single
  ranking order MUST be an isolated, swappable unit (not inlined into the ranking
  step), with one default strategy (equal-weighted average) shipped and at least one
  documented alternative — so combination strategies can be experimented with and
  compared during evaluation without changing calling code.
- **FR-010**: A language-model quality judgment MAY be computed and reported as an
  additional signal for evaluation/reporting, but it MUST NOT influence which items
  are selected or how outfits are ranked.
- **FR-011**: When the closet cannot fill a required slot for an otherwise-complete
  outfit, the system MUST omit that outfit rather than presenting it incomplete.
  Filling the gap from the shared catalog is explicitly out of scope for this
  feature (see Future Work).
- **FR-012**: The user MUST be able to request alternative outfits for the same
  request without restating it.
- **FR-013**: The user MUST be able to refine suggestions with short follow-ups
  (e.g. "warmer", "less formal") that are interpreted against the ongoing
  conversation, without restating the original request; unstated constraints from
  the original request MUST be preserved across refinement.
- **FR-014**: The system MUST prune the closet by hard constraints (warmth band,
  formality band, season) before combining candidates, and MUST NOT exhaustively
  combine the entire raw closet.
- **FR-015**: When a requested refinement cannot be satisfied from the available
  items, the system MUST return the best available result and state that the request
  could not be fully satisfied, rather than failing silently or inventing items.

### Key Entities *(include if feature involves data)*

- **Styling request**: the user's plain-English description plus derived context —
  occasion, mood, formality, resolved weather/temperature, and season. Belongs to
  the authenticated user.
- **Retrieved styling principle**: a structured directive drawn from the style
  knowledge base, carrying a stable identifier and provenance, used both to shape
  closet selection and to ground rationale.
- **Outfit suggestion**: an ordered set of owned items that together form a
  complete outfit, plus its rationale and its four dimension scores.
- **Dimension score**: one of color harmony / formality coherence / weather fitness
  / silhouette balance — a value on a consistent scale plus a short reason, produced
  deterministically.
- **Score combination strategy**: the swappable unit (FR-009a) that reduces the four
  dimension scores to a single ranking value; the default is equal-weighted average.
- **RefinementTurn** (conversation/refinement thread): the ongoing exchange that
  lets follow-ups ("warmer") be interpreted without restating the original
  request; scoped to one user and one styling session.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of suggestion requests made without valid credentials are
  refused, and no closet data is returned in those responses.
- **SC-002**: In 100% of authenticated suggestion responses, every item shown is
  owned by the requester — zero invented or not-owned items across the evaluation
  set.
- **SC-003**: For requests whose closet can support them, 95% of responses return
  between three and five complete outfits.
- **SC-004**: 100% of rationale statements cite a retrieved principle or a reported
  score; zero citations reference a principle that was not retrieved (measured by
  the evaluation harness).
- **SC-005**: Every returned outfit carries all four dimension scores with reasons;
  re-scoring the same outfit and context yields identical scores on 100% of repeats.
- **SC-006**: The deterministic scoring functions used to rank outfits are the same
  functions the evaluation harness runs — one implementation, no prompt-only metric.
- **SC-007**: A "warmer" refinement issued without restating the request raises
  mean item warmth (0–5 scale) by at least 1, and a "less formal" refinement
  lowers the formality band by at least one notch (per `FORMALITY_ORDER`), in at
  least 90% of cases, while preserving the original occasion.
- **SC-008**: The evaluation no-regression gate (deterministic retrieval metric)
  after this feature is no worse than the recorded baseline in the eval-run
  archive.
- **SC-009**: All deterministic logic introduced or touched by this feature has
  passing automated unit tests that do not depend on a language model.

## Delivery Phases *(informative — see planning artifacts for detail)*

This feature ships as four independently-mergeable phases; the feature is the
umbrella, the phases are the mergeable units. Each phase touching retrieval or
generation re-runs the evaluation no-regression gate before merge.

- **Phase 1 — essentials (no behavior change)**: satisfies US1 — authenticate the
  suggestion flow and scope it to the requester; backfill unit tests for the
  existing deterministic logic. (SC-001, SC-009.)
- **Phase 2 — deterministic scoring**: satisfies US3's scoring foundation — the four
  reusable, deterministic dimension scorers plus the swappable score-combination
  strategy (FR-009a). (SC-005, SC-006.)
- **Phase 3 — graph + real selection**: satisfies US2 and US3's ranking — the
  pipeline becomes an agent graph with deterministic pruning/combination/scoring
  replacing any model-driven item picking; the suggestion surface is delivered.
  Unfillable slots omit the outfit (FR-011). (SC-002, SC-003, SC-004.)
- **Phase 4 — refinement + optional judge**: satisfies US4, plus the reported-only
  language-model judge signal. (SC-007, FR-010.)

## Future Work *(explicitly out of scope — see Clarifications)*

- **Body shape / silhouette personalization**: no user-profile store for body shape
  is introduced this feature; silhouette balance uses general proportion/balance
  principles for everyone. A later feature can add a stored body-shape attribute
  without changing this spec's contracts.
- **Catalog substitution**: when the closet can't fill a required slot, this
  feature omits the outfit rather than offering a not-owned catalog item. Filling
  gaps from the shared catalog (with clear "not owned" marking) is deferred to a
  later feature.
- **Score combination alternatives**: FR-009a ships one default (equal-weighted
  average) but keeps the combination strategy swappable. Trying and comparing
  alternative strategies (fixed weights, fit-first lexicographic, learned weights)
  is ongoing evaluation work, not a one-time decision made in this feature.

## Assumptions

- **Number of outfits**: "three to five" is the target when the closet can support
  it; a smaller closet yields fewer, and the floor is a clear "not enough items"
  outcome rather than padding with incomplete outfits.
- **Weather resolution**: local weather is resolved from the user's location via the
  existing weather integration, with a documented fallback to a caller-supplied
  temperature and then to season-only reasoning when location weather is
  unavailable.
- **Existing pipeline is authoritative**: the current retrieval strategies, query
  building, context assembly, KB, and evaluation harness are reused as-is and wired
  into the agent graph rather than rewritten (per the project constitution).
- **Existing taxonomy is frozen**: category groups, the six-value formality enum,
  warmth 0–5, seasons, and hex colors are used unchanged; this feature introduces no
  parallel formality scale or renamed groups.
- **Persistence of refinement**: conversational refinement is scoped to a single
  user's styling session and persists across follow-ups within that session; long-
  term preference learning from feedback is a separate later feature, out of scope
  here.
- **Authentication mechanism**: the suggestion flow reuses the same token-based
  authentication already protecting the closet-management endpoints; no new auth
  mechanism is introduced.
