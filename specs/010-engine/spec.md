# Feature Specification: Engine Approach (Deterministic Selection)

**Feature Branch**: `010-engine`

**Created**: 2026-07-17

**Status**: Draft

**Input**: User description: "WP2 Engine approach for /suggest — an opt-in `approach:\"engine\"` value that brings outfit selection into Principle II compliance (deterministic enumerate + score; the LLM only selects-and-writes from a pre-scored top-K, never invents or ranks combinations). Folds WP0's T0.5 `approach` plumbing into this same feature (plumbing alone has no user value; this is the first and only consumer of it). Opt-in only — not flipped to default, so this merge is purely additive and doesn't require the full eval no-regression gate. New `pipeline/engine.py::enumerate_outfits`: skeletons top×bottom×footwear and full_body×footwear; cross with outerwear when cold/freezing; reuse existing coherence guards; a >20,000-combo safety valve. New graph path: enumerate all combos, score every one with the existing scorer, keep top-6, one LLM call selects-and-writes an ordered 3 with rule_id citations (any out-of-range selection index falls back to deterministic top-3-by-score). Every outfit must be closet/catalog-owned; every citation must resolve. Out of scope: flipping the default, WP1 Direct, WP3 HITL, WP4 weather, WP5 Agentic, WP6 compare, WP7 KB distillation, the constitution amendment itself."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Requesting the deterministic-selection approach (Priority: P1)

A caller of `POST /suggest` who wants outfit selection that is fully accountable to deterministic rules (not left to the language model's own judgment of what "looks good") opts into it with a new request field. The system runs a distinct pipeline path: every possible outfit combination the closet supports (within the already-pruned candidates) is deterministically assembled and scored, and the language model's only remaining job is to pick and narrate 3 outfits from a shortlist the deterministic scorer already ranked — never to invent a combination or to reorder the shortlist itself.

**Why this priority**: This is the constitution-compliance milestone (Principle II — "the LLM MUST NOT select clothing items; selection is deterministic") and the highest-value deliverable of this feature. Without it, there is no approach in the product where item selection is provably deterministic end-to-end.

**Independent Test**: Post to `/suggest` with the new field set to request this approach, using a seeded closet; confirm the response contains 3 outfits, that every returned outfit is a combination the deterministic enumerator actually produced (traceable back to enumeration+scoring, not to free-form model output), and that the caller who omits the field sees no change in behavior at all.

**Acceptance Scenarios**:

1. **Given** a request that asks for the deterministic-selection approach, **When** the closet has enough items to assemble outfits, **Then** the response contains 3 outfits, each one a combination that was enumerated and scored deterministically before the language model ever saw it.
2. **Given** a request that omits the approach field entirely, **When** it is processed, **Then** the system behaves exactly as it did before this feature existed — same pipeline, same output.
3. **Given** a closet that deterministically produces one combination that is a clear best fit (exact formality match, harmonious colors, weather-appropriate), **When** the deterministic-selection approach is requested, **Then** that combination is the top-ranked outfit returned.

---

### User Story 2 - The language model can never smuggle in an unscored or invented outfit (Priority: P1)

Even though a language model still writes the narrative rationale and chooses the final ordering of 3 outfits from the shortlist, the system never trusts it blindly: if the model's output references anything other than one of the shortlisted, deterministically-scored options, the system ignores that output and falls back to a deterministic choice instead — so a malformed or creative model response can degrade the ordering/rationale, at worst, but never violate deterministic selection.

**Why this priority**: This is what actually makes Story 1's guarantee hold under real-world model failure modes (hallucination, malformed structured output) rather than just in the happy path — equally critical to ship alongside Story 1, not a follow-on hardening pass.

**Independent Test**: Simulate the language model responding with a selection that references an option outside the shortlist it was given, and confirm the system still returns exactly 3 valid, deterministically-ranked outfits rather than erroring or passing the bad reference through.

**Acceptance Scenarios**:

1. **Given** the language model's selection response references a shortlist position that doesn't exist, **When** the response is processed, **Then** the system discards that response and returns the top 3 shortlisted outfits by deterministic score instead.
2. **Given** a valid language-model selection, **When** it is processed, **Then** every rationale it wrote cites a rule that was actually retrieved for this request — no citation may reference a rule the user was never shown grounds for.

---

### User Story 3 - Cold-weather requests get outerwear included in the possibilities considered (Priority: P2)

When the weather context calls for it (cold or freezing), the set of combinations considered for deterministic selection includes versions with an outerwear piece added — not just the base top/bottom/footwear combination — so a warm enough option is actually among the possibilities the scorer ranks, not systematically absent from consideration.

**Why this priority**: Secondary to the core compliance mechanism (Stories 1-2), but without it the deterministic approach would silently under-serve exactly the requests where getting the outfit right matters most (genuinely cold weather) — a real usability gap, not just missing polish.

**Independent Test**: Construct a closet and cold-weather request where the only well-scoring option requires outerwear; confirm it's among the enumerated possibilities and can be selected.

**Acceptance Scenarios**:

1. **Given** a request context that calls for cold-weather dressing and a closet containing outerwear, **When** combinations are enumerated, **Then** versions including an outerwear piece are among those considered.
2. **Given** the same cold-weather context but a closet with no outerwear at all, **When** combinations are enumerated, **Then** the system still returns the best available combinations from what exists rather than returning nothing.

### Edge Cases

- A closet whose candidates, after pruning, would produce an extremely large number of combinations: the system must still respond in reasonable time by deterministically narrowing to the most-likely-to-fit candidates first, never by silently timing out or erroring.
- A closet too sparse to complete even one outfit (missing a required slot entirely): the deterministic-selection approach must degrade the same way the existing approach already does (fewer or zero outfits, with an explanatory note) — not crash or return an incomplete outfit.
- A refinement turn ("warmer", "less formal", "show me alternatives") on a conversation that started with the deterministic-selection approach must continue using that same approach for the rest of the conversation, not silently fall back to the prior approach.
- A request naming an approach value the system doesn't recognize is out of scope for this feature's validation depth — standard request-validation rejection is sufficient (no bespoke handling required).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `POST /suggest` MUST accept an optional field naming which selection approach to use, without changing behavior for any request that omits it.
- **FR-002**: When the deterministic-selection approach is requested, the system MUST enumerate outfit combinations from the already-pruned, closet-owned candidates rather than asking the language model to assemble them.
- **FR-003**: Every enumerated combination MUST pass the same coherence rules already enforced elsewhere in the product (a complete, sensible outfit — not two pairs of shoes, not a dress worn with separate trousers, etc.) — this feature must not introduce a second, divergent notion of what counts as a valid outfit.
- **FR-004**: Every enumerated combination MUST be scored using the same deterministic scoring already used elsewhere in the product — this feature must not introduce a second, divergent scoring method.
- **FR-005**: The language model's role in this approach MUST be limited to choosing an ordered subset of already-scored combinations and writing a rationale for each — it MUST NOT be able to introduce an item combination that wasn't already enumerated and scored.
- **FR-006**: If the language model's chosen subset references anything outside the set it was actually offered, the system MUST discard that output and fall back to the top deterministically-ranked combinations instead — the caller always receives a valid, deterministically-grounded result.
- **FR-007**: Every rationale returned to the caller MUST cite only rules that were actually retrieved for that request.
- **FR-008**: Every item in every returned outfit MUST belong to the requester's own closet or the shared catalog, exactly as already required of every other approach.
- **FR-009**: When the request context calls for cold or freezing conditions, the enumerated combinations MUST include versions with an outerwear piece added, when the closet has one available.
- **FR-010**: If enumerating every possible combination would be excessive, the system MUST narrow deterministically to the most-likely-to-fit candidates before enumerating, rather than exhaustively enumerating without bound.
- **FR-011**: A conversation (refinement) that began with the deterministic-selection approach MUST continue using that same approach on every later turn of the same conversation, without the caller having to restate it.
- **FR-012**: This feature MUST NOT change the default behavior of `POST /suggest` for any existing caller — the deterministic-selection approach is opt-in only.
- **FR-013**: This feature MUST NOT change the outfit data model, the suggestion API's existing request/response contract fields, the six-value formality enum, or the category-group taxonomy (constitution Principle VI).

### Key Entities

- **Approach**: which selection strategy a `/suggest` request uses. This feature adds one new value (deterministic-selection) and preserves the existing behavior as the unnamed/default value; other approach values named in the broader roadmap (direct-generation, agentic, compare) are out of scope here.
- **Outfit combination**: a candidate grouping of owned items (e.g. top + bottom + footwear, optionally + outerwear) considered for selection — the unit that gets enumerated, scored, and either shortlisted or discarded.
- **Shortlist**: the top-scoring combinations (by the existing deterministic scorer) offered to the language model for final selection and narration.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A request naming the deterministic-selection approach always receives outfits that are traceable to deterministic enumeration and scoring — never an outfit whose item combination exists only because the language model proposed it.
- **SC-002**: 100% of returned rationale citations resolve to a rule genuinely retrieved for that request, with zero hallucinated citations across repeated runs of the acceptance scenarios.
- **SC-003**: A simulated malformed/out-of-range model selection never results in an error or an invalid outfit reaching the caller — a valid, deterministically-ranked result is returned every time.
- **SC-004**: Requests that omit the new field show no observable difference in behavior from before this feature existed.
- **SC-005**: A cold-weather scenario with outerwear available always includes an outerwear-inclusive combination among the possibilities considered.

## Assumptions

- "The same deterministic scoring already used elsewhere" (FR-004) refers to the existing four-dimension scorer (color harmony, formality coherence, weather fitness, silhouette balance) and its existing ranking strategy, reused unchanged — this feature does not add, remove, or reweight scoring dimensions.
- "The same coherence rules already enforced elsewhere" (FR-003) refers to the existing slot-completeness and valid-combination guards — this feature reuses them exactly, rather than redefining what a valid outfit is.
- Flipping the product's default approach to the deterministic-selection one, and the corresponding constitution amendment formalizing its Principle II compliance, are explicitly out of scope for this feature and tracked as follow-up work.
- The shortlist size (how many top-scoring combinations the language model chooses from) and the exact combination-count threshold that triggers deterministic narrowing are internal tuning parameters, not user-facing behavior — reasonable defaults are chosen during planning rather than specified here.
- This feature depends on the request-context, closet-retrieval, coherence-guard, and scoring capabilities that already exist in the product; it extends them with a new selection path rather than replacing any of them.
