# Feature Specification: L1/L3 Retrieval Restructure + Refinement Warmth-Floor Fix

**Feature Branch**: `007-AI-improvements`

**Created**: 2026-07-16

**Status**: Draft

**Input**: User description: "L1/L3 retrieval restructure + refinement warmth-floor fix — L1 gains a
genuine chunked-embedding semantic sub-layer over already-embedded long-form sources; L3 moves from a
static pre-ingested trend KB to a live Tavily web search at request time; the 'warmer' refinement's
warmth floor moves from a blanket footwear/accessory exemption to a per-category-relative floor.
Closes cert-challenge rubric gaps (a genuine chunked-embedding RAG layer, a live agentic search tool)
before the AI part is frozen."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Deeper style rationale from long-form sources (Priority: P1)

A user asks for an outfit suggestion. Today the system's harmony/proportion guidance comes only from a
small set of hand-written rule cards. The system should also be able to draw a specific, relevant
passage out of the longer color-theory and proportion source material it already holds (already
processed into passages, just never searched) when that passage is a better match for the user's
request than the rule cards alone.

**Why this priority**: This is the deepest retrieval-quality gap — the system currently ignores most of
the source material it holds a license to use directly, falling back to only its own hand-written
summaries.

**Independent Test**: Ask for styling guidance on a query where a hand-written card is generic but a
specific passage in the long-form source is directly on-point (e.g. a specific color-contrast
relationship). Confirm the suggestion's rationale can cite that specific passage, not just a card.

**Acceptance Scenarios**:

1. **Given** a request whose intent matches a passage in the long-form color-theory/proportion sources,
   **When** the suggestion is generated, **Then** the rationale can cite that passage's source and the
   hand-written rule cards are still present in what was retrieved (neither replaces the other).
2. **Given** any request, **When** retrieval runs, **Then** no full text of a copyrighted, rights-restricted
   source ever appears in what was retrieved or cited — only material the system holds rights to use
   directly.

---

### User Story 2 - Suggestions reflect current trends, not a fixed snapshot (Priority: P2)

A user asks for a season-appropriate outfit. Today "current trend" guidance comes from a fixed set of
trend notes written once and never updated. The system should instead look up what's being said about
trends for the relevant season/occasion at the moment of the request.

**Why this priority**: Trend guidance is explicitly time-sensitive; a fixed snapshot goes stale, and the
cert requirement is a genuinely live lookup, not a bigger static list.

**Independent Test**: Ask for a seasonal suggestion twice, with the underlying live trend source content
different between the two calls (or simulate a lookup failure). Confirm each successful call's rationale
can cite a trend claim retrieved on that specific call, and confirm a failed lookup still returns a
usable suggestion (just without trend-sourced rationale).

**Acceptance Scenarios**:

1. **Given** a request where the season is known, **When** the suggestion is generated, **Then** the
   system performs a live lookup for current trend information as part of assembling the suggestion, before
   it looks at the user's closet.
2. **Given** a request where the season is not known, **When** the suggestion is generated, **Then** no
   trend lookup happens (unchanged from today).
3. **Given** the live trend lookup fails or times out, **When** the suggestion is generated, **Then** the
   user still receives a suggestion (degraded, without trend-sourced rationale) rather than an error.
4. **Given** a rationale cites a trend claim, **When** that citation is checked, **Then** it resolves to a
   trend result actually returned by that request's own live lookup — never a claim from a previous
   request or an invented one.

---

### User Story 3 - "Warmer" reliably works across the whole outfit (Priority: P1)

A user gets a suggestion and asks for something warmer. Today this frequently fails to produce a new
suggestion at all for closets where shoes/accessories don't carry much warmth variation, because the
system demands the same absolute warmth increase from every item in the outfit, including categories
that can't realistically supply it — so instead of gently upgrading what it can, it gives up. This is
a bug fix on an existing feature.

**Why this priority**: This is a already-diagnosed, reproducible defect in a shipped, user-facing
capability (not a gap) — it silently degrades a feature users already rely on.

**Independent Test**: Request a suggestion, then ask for something warmer, against a closet whose
footwear/accessories have low absolute warmth ratings but whose core layers (tops/bottoms/outerwear) do
have room to go warmer. Confirm the request succeeds with a genuinely warmer outfit rather than falling
back to "couldn't satisfy that."

**Acceptance Scenarios**:

1. **Given** a closet where a category (e.g. footwear) has a low achievable warmth ceiling and another
   category (e.g. outerwear) has a high one, **When** the user asks for something warmer, **Then** each
   category's warmth requirement scales to what that category can actually offer, so the low-ceiling
   category isn't held to the same absolute bar as the high-ceiling one — but also isn't given a free
   pass, since it's a small deterministic step at a time.
2. **Given** repeated "warmer" requests, **When** a category has already reached the warmest item it
   owns in that category, **Then** further "warmer" requests keep the rest of the outfit's warmth
   climbing without discarding that category's best available item.
3. **Given** a closet that genuinely has no warmer options anywhere, **When** the user asks for
   something warmer, **Then** the system still falls back gracefully to the previous suggestion with an
   explanatory note (existing behavior, unchanged).

---

### Edge Cases

- A long-form source passage and a hand-written card both match a query strongly — both may be
  retrieved and cited; neither is preferred over the other by construction.
- The live trend lookup returns zero results for an obscure season/occasion combination — the system
  proceeds without trend-sourced rationale, same as a lookup failure.
- A user issues "warmer" multiple times in the same conversation — each request's floor is computed
  fresh from the current step count, never compounding on a previous request's already-adjusted floor
  in a way that could exceed what any item in a category actually has.
- A closet category has zero items at all — no floor computation is needed for a category with nothing
  to filter.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST be able to retrieve specific passages from long-form source material
  (already-processed, rights-cleared color-theory/proportion sources) via semantic search, in addition
  to its existing hand-written rule cards — both retrieved together, neither replacing the other.
- **FR-002**: The system MUST NOT allow any passage sourced from a copyrighted, rights-restricted work
  to enter the searchable pool — only material the system holds the rights to use directly.
- **FR-003**: Every passage retrieved under FR-001 MUST carry enough provenance (source, link, stable
  identifier) that a suggestion's rationale can cite it and that citation can be verified as genuinely
  retrieved for that request.
- **FR-004**: The system MUST perform a live lookup for current trend information at the time of the
  request, when the request's season is known, instead of relying only on a fixed, pre-written set of
  trend notes.
- **FR-005**: The live trend lookup MUST NOT run when the request's season is unknown (unchanged
  trigger condition from today).
- **FR-006**: The live trend lookup MUST complete (or be determined to have failed/timed out) before the
  system looks at the user's own closet for this request.
- **FR-007**: Each result from the live trend lookup MUST carry enough provenance (source, link, stable
  identifier scoped to that request) that a suggestion's rationale can cite it and that citation can be
  verified as genuinely retrieved for that request — a citation must never resolve to a claim from a
  different request.
- **FR-008**: If the live trend lookup fails or times out, the system MUST still produce a suggestion,
  simply without trend-sourced rationale for that request — never an error or a crash.
- **FR-009**: The system's existing comparison between its plain, structured, and enhanced retrieval
  approaches MUST keep working after FR-001–FR-008 land — the plain approach's overall pool of material
  is unaffected by these changes; the structured/enhanced approaches are where the new behavior shows up.
- **FR-010**: When a user asks for a warmer suggestion, the system MUST compute how much warmer to
  require in each clothing category relative to what that category can actually provide, rather than
  applying one fixed absolute requirement to every category alike.
- **FR-011**: The per-category warmth requirement in FR-010 MUST NOT exceed what the warmest item
  actually available in that category can satisfy — a category is never fully excluded by its own floor.
- **FR-012**: The "warmer" fix MUST NOT change the system's existing separate warm-weather warmth
  ceiling check (the hard upper limit used to keep hot-weather suggestions light) — only the "warmer"
  refinement's own floor calculation changes.
- **FR-013**: The system MUST record, before and after the FR-010 fix, how often a "warmer" request
  fails to produce anything and falls back to the prior suggestion, so the fix's effect is demonstrated
  with real numbers rather than asserted.

### Key Entities

- **Semantic passage (L1 semantic chunk)**: A retrievable excerpt of a long-form, rights-cleared style
  source, distinct from the existing hand-written rule cards, carrying the same citation provenance
  (source, link, stable id) those cards already carry.
- **Live trend result**: A single result from a live, request-time trend lookup, holding a claim plus
  provenance (source, link, an id unique to that request) so it can be cited and verified the same way
  a knowledge-base passage can — but scoped to one request, not persisted as reusable knowledge.
- **Category warmth ceiling**: The warmest rating actually achievable within one clothing category in a
  given closet, used to scale that category's "warmer" requirement instead of applying one number to
  every category.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A styling rationale can be traced to a specific passage from the long-form sources, not
  only to a hand-written card, for at least one representative request per long-form source.
- **SC-002**: Zero occurrences of copyrighted reference-only source text appearing in the retrievable
  pool, verified on every rebuild of that pool.
- **SC-003**: A styling rationale can be traced to a live trend result fetched during that same request,
  for at least one representative seasonal request.
- **SC-004**: A live-trend-lookup failure never surfaces as a user-visible error — 100% of simulated
  failures still return a usable suggestion.
- **SC-005**: Across a fixed set of "warmer" requests run against closets with uneven per-category
  warmth ranges, the share of requests that fall back to "couldn't satisfy that" drops measurably
  (recorded as a before/after comparison, not just asserted) after the fix.
- **SC-006**: The existing plain-vs-structured-vs-enhanced retrieval comparison keeps producing results
  for all three approaches after this feature lands, with the plain approach's own measured numbers
  unaffected by these changes.

## Assumptions

- The long-form color-theory/proportion sources referenced in FR-001 are already processed into
  retrievable passages with the necessary provenance metadata as part of the system's existing
  knowledge-base build step; this feature adds retrieval over what's already been processed, not new
  processing of new sources.
- "Live lookup for current trend information" (FR-004) means a real-time web search performed at request
  time, not a scheduled background refresh of a stored snapshot.
- The system already has an established pattern for degrading gracefully when a live external lookup
  fails (used today for weather); the same pattern applies to FR-008.
- A citation "resolving to a claim actually retrieved for that request" (FR-007) means the identifier
  used to cite a live result is scoped to the request that fetched it, not reused or predictable across
  requests.
- The "before/after" comparison in FR-013/SC-005 is a one-time diagnostic capture to demonstrate the fix,
  not a permanently running metric.
- No change to what a user directly controls or sees as a setting — both changes in this feature affect
  suggestion quality and reliability, not new user-facing controls.
