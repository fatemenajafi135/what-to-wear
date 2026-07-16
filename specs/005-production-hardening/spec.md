# Feature Specification: Production Hardening

**Feature Branch**: `005-production-hardening`

**Created**: 2026-07-16

**Status**: Draft

**Input**: User description: "The app must be reliably and safely usable by
real people over the public internet, not just on a developer's machine.
First, it must actually be publicly reachable: the backend and frontend need
to be deployed (this was planned once already but the deployment steps were
never completed), and photo uploads for wardrobe items need durable,
private-per-user storage. Second, every outfit suggestion the system returns
must be verified to only ever reference items that genuinely exist in the
requesting user's own closet or the shared catalog -- if that verification
ever fails, the system must refuse to return the fabricated suggestion
rather than show it to the user. Third, when a user (or many users) make the
same or a near-identical styling request repeatedly, the system should reuse
the prior result instead of re-running the full retrieval-and-generation
pipeline and paying for another AI call every time. Fourth, calls to AI
model providers should go through one consistent routing layer instead of
being made ad hoc, so retries on provider failures, and visibility into
what's being spent and on what, aren't scattered across the codebase. Out of
scope: any change to what an outfit suggestion contains or how it's chosen,
and any new user-facing feature."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Reach the app from anywhere, not just localhost (Priority: P1)

A prospective user (or grader, or the developer showing this off) opens a
public URL in a browser, signs up, adds a wardrobe item by photo, and gets
an outfit suggestion — without anyone needing to run a local backend or
frontend first. This was already planned as part of an earlier feature, but
the actual deployment steps (a live backend URL, a live frontend URL, and a
durable place to store uploaded photos) were never completed — today the
product only exists on one developer's machine.

**Why this priority**: Nothing else in this feature matters if there's no
publicly reachable place to demonstrate any of it. It's also a hard blocker
already called out as outstanding work from a prior feature.

**Independent Test**: From a machine that has never run any part of this
project locally, visit the public frontend URL, complete sign-up, add one
item by photo, and receive a suggestion — all without touching a terminal.

**Acceptance Scenarios**:

1. **Given** the deployed system, **When** a new user visits the public
   frontend URL, **Then** they can sign up, sign in, and reach the closet
   view without any local backend running.
2. **Given** a signed-in user on the deployed system, **When** they upload a
   photo of a garment, **Then** the photo is stored durably (survives a
   backend restart) and only that user can access it later.
3. **Given** a signed-in user with at least one item in their closet on the
   deployed system, **When** they request a suggestion, **Then** they
   receive one grounded in their real closet, served by the publicly
   deployed backend.

---

### User Story 2 - Never see a fabricated outfit (Priority: P2)

A user requests an outfit suggestion. Whatever internal step assembled it,
the system double-checks the final answer before showing it: every item
referenced must genuinely exist in that user's closet or in the shared
catalog. If that check ever fails, the user sees a clear "couldn't put
together a suggestion" outcome instead of an outfit containing an item they
don't own.

**Why this priority**: A trust and safety property, not a new capability —
the system already only ever selects owned/cataloged items by design; this
adds an explicit, automatic check that catches it if that guarantee is ever
violated by a bug, rather than relying on it always holding.

**Independent Test**: Deliberately make one outfit's item list reference a
nonexistent item id before it reaches the user, and confirm the system
withholds that suggestion instead of displaying it.

**Acceptance Scenarios**:

1. **Given** a normal request where every generated outfit only references
   real items, **When** the response is prepared, **Then** the user sees
   all of the outfits, unaffected.
2. **Given** a request where an internal step produces an outfit
   referencing an item that doesn't exist in that user's closet or the
   catalog, **When** the response is prepared, **Then** that specific
   outfit is silently dropped from what's shown to the user, and any
   remaining valid outfits are still shown.
3. **Given** a request where every generated outfit fails the check,
   **When** the response is prepared, **Then** the user sees the existing
   "couldn't put together a suggestion" outcome, not an error page.

---

### User Story 3 - Repeated requests come back faster and cheaper (Priority: P3)

Two users — or the same user twice — ask for styling advice for the same or
a near-identical occasion/context. The second time, the system recognizes
the similarity and reuses the prior result instead of re-running the full
styling pipeline and paying for another round of AI calls.

**Why this priority**: Valuable for cost and responsiveness at real usage
volume, but the product works correctly without it — an efficiency
improvement, not a correctness or reachability requirement.

**Independent Test**: Issue the same styling request twice in a row and
confirm the second response returns markedly faster than the first, with no
new AI-provider usage recorded for the second call.

**Acceptance Scenarios**:

1. **Given** a styling request that has been served once already, **When**
   the same user makes the same request again shortly after, **Then** they
   receive an equivalent result noticeably faster than the first time.
2. **Given** a styling request that has never been made before, **When** a
   user makes it, **Then** it's processed in full (no incorrect cache
   reuse) and the result becomes reusable for future matching requests.
3. **Given** a cached result whose underlying closet or catalog data has
   since changed, **When** a matching request is made, **Then** the system
   does not serve a now-inaccurate cached result.

---

### User Story 4 - One place to see and control AI spend and failures (Priority: P4)

Whoever operates the product can see, in one place, what AI provider calls
are being made and what they're costing, and can rely on a transient
provider failure being retried automatically rather than immediately
surfacing as an error to the end user.

**Why this priority**: Purely an operational/observability improvement for
whoever runs this in production; it doesn't change what any user
experiences on the happy path.

**Independent Test**: Simulate a transient failure from the AI provider and
confirm the request still succeeds (via automatic retry) without the caller
ever seeing an error, and confirm a record of the call's cost/usage is
visible afterward.

**Acceptance Scenarios**:

1. **Given** a transient (one-time) failure response from an AI provider,
   **When** the system makes a call that hits it, **Then** the call is
   automatically retried and the caller still gets a successful result.
2. **Given** normal operation, **When** any AI provider call is made,
   **Then** its cost and usage are recorded somewhere the operator can
   review.

---

### Edge Cases

- What happens when the deployed backend can't reach the database or vector
  store at all (not just one bad request)? Surfaced as a clear health-check
  failure, not a silent partial outage.
- What happens when the semantic cache store itself is unavailable? The
  system falls back to processing the request fresh rather than failing the
  request.
- What happens when every AI provider configured is down? The existing
  error-handling behavior applies — this feature adds retries for transient
  failures, not a guarantee of success when a provider is fully
  unavailable.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST be reachable by any user with a web browser
  and internet connection, requiring no local setup.
- **FR-002**: Uploaded wardrobe photos MUST be stored durably (surviving a
  backend restart/redeploy) and MUST be accessible only to the user who
  uploaded them.
- **FR-003**: The system MUST verify, for every outfit it is about to
  return, that every item referenced genuinely exists in the requesting
  user's closet or the shared catalog.
- **FR-004**: If that verification fails for a given outfit, the system
  MUST withhold that specific outfit rather than return it to the user.
- **FR-005**: If every outfit in a response fails verification, the system
  MUST fall back to the existing "no suggestion available" outcome, not an
  error.
- **FR-006**: The system MUST be able to recognize when a new styling
  request is equivalent to (or close enough to) one it has already
  answered, and reuse that prior result rather than reprocessing.
- **FR-007**: The system MUST NOT serve a cached result once it is no
  longer accurate — a cached suggestion becomes invalid the moment the
  requesting user's closet changes (any wardrobe item added, edited, or
  removed), not merely after a fixed time limit.
- **FR-008**: All calls to AI model providers MUST go through a single
  consistent code path within the system (not multiple ad hoc call sites),
  enabling uniform retry and usage-tracking behavior.
- **FR-009**: A transient (non-permanent) AI provider call failure MUST be
  retried automatically before being surfaced as an error to the caller.
- **FR-010**: The system MUST make AI provider call cost/usage visible to
  whoever operates it, without requiring code changes to inspect.
- **FR-011**: None of the above MAY change what an outfit suggestion
  contains or how it is selected — the existing deterministic
  scoring/retrieval behavior is preserved exactly.

### Key Entities *(include if feature involves data)*

- **Deployment target**: the publicly reachable instances of the backend
  and frontend, and the durable photo storage location, as opposed to any
  developer's local machine.
- **Cached suggestion**: a previously computed styling result, keyed by the
  request's meaningful inputs (occasion/context and the requesting user's
  closet state), reusable for a matching later request until the user's
  closet changes.
- **Provider call record**: one AI-provider call's cost, usage, and
  outcome, visible after the fact.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A person with no prior local setup can sign up, add an item,
  and receive a suggestion entirely through a public URL, start to finish,
  in one sitting.
- **SC-002**: 100% of outfits ever shown to a user reference only items
  that exist in that user's closet or the shared catalog — verified
  automatically on every response, not just by code review.
- **SC-003**: A repeated, equivalent styling request (same user, unchanged
  closet) returns markedly faster than the first time it was made.
- **SC-004**: A single transient AI-provider failure never results in a
  visible error to the end user.
- **SC-005**: Anyone operating the system can answer "what did we spend on
  AI calls, and on what" without reading source code.

## Assumptions

- "Real people over the public internet" means the app is reachable via
  public URLs on the already-locked hosting stack (Railway for the backend,
  Vercel for the frontend, Supabase for storage) — no new hosting decision
  to make.
- The prior, unfinished deployment steps from Feature 003 (backend,
  frontend, and photo storage all not yet live) are absorbed into this
  feature's scope rather than treated as a separate prerequisite effort,
  since they are a hard blocker for everything else here.
- "Near-identical" styling requests, for caching purposes, means requests
  whose meaningful inputs (occasion, mood, formality, temperature/season,
  and the requesting user's closet contents) match closely enough that
  reusing a prior result would still be an accurate answer — not simply
  identical request text.
- Cache invalidation is tied to closet changes (FR-007), not a time limit —
  chosen because this system's suggestions are grounded in the user's own
  closet (constitution Principle 4), so a stale cache entry served after a
  wardrobe edit would be a correctness violation, not just a staleness
  inconvenience. A short safety-net time limit may still be applied
  underneath this, decided at planning time, not here.
- The grounding verification (User Story 2) is a final safety check in
  addition to, not a replacement for, the existing constitution-level
  guarantee that generation only ever selects from real items.
- Retry/fallback behavior (User Story 4) applies to transient failures
  only; a fully unavailable provider is out of scope for automatic recovery
  here.
