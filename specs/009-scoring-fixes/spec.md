# Feature Specification: Scoring & Retrieval Correctness Fixes

**Feature Branch**: `009-scoring-fixes`

**Created**: 2026-07-17

**Status**: Draft

**Input**: User description: "Fix four correctness bugs in the deterministic outfit-scoring pipeline, verified real by direct code review (not hypothetical), ahead of a certification-challenge resubmission that depends on trustworthy scores. (1) color-harmony scorer is inverted — rewards clashing complementary pairs over tonal/neutral ones; replace with a color-theory-based scorer. (2) outfit-ranking default should be the existing fit-first lexicographic strategy, not equal-weighted average. (3) per-slot candidate cap silently drops the best-fitting items because it isn't sorted before capping; sort by formality/warmth fitness first. (4) color-name lookup table is missing common names (e.g. teal), causing misidentification. No API/taxonomy change, no new dependency."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Color harmony reflects real styling principles (Priority: P1)

A user asks for an outfit suggestion. Among the outfits the system could assemble from their closet, the ones it ranks highest for "color harmony" are the ones a stylist would actually call harmonious — neutral-anchored or tonal/analogous pairings — not the ones that happen to have the starkest color contrast between two clashing hues.

**Why this priority**: Color harmony is one of four scored dimensions surfaced directly to the user with a written rationale (constitution Principle V — "no quality metric may exist only inside a prompt"). An inverted scorer actively misleads the user and undermines the product's core promise on every single suggestion, not just an edge case.

**Independent Test**: Score a fixed set of outfit candidates built from known palette colors (a tonal navy+charcoal outfit, a neutral oatmeal+camel+cream outfit, a clashing tomato-red+emerald-green outfit, a 4-saturated-hue outfit) and confirm the ranking order matches color-theory expectations, independent of any other scoring dimension or the ranking/generation pipeline around it.

**Acceptance Scenarios**:

1. **Given** an outfit whose core items are all neutral or share one dominant hue, **When** it is scored for color harmony, **Then** it receives a high score (≥0.8).
2. **Given** an outfit pairing two roughly-equal-weight complementary hues (e.g. tomato red and emerald green, neither clearly an accent), **When** it is scored for color harmony, **Then** it receives a low score (<0.45), lower than the neutral/tonal outfit in Scenario 1.
3. **Given** an outfit with the same complementary hue pair but where one color is clearly a minor accent (much lower saturation or much lighter/darker), **When** it is scored, **Then** it scores meaningfully higher than the equal-weight complementary pairing in Scenario 2.
4. **Given** an outfit with four or more distinct saturated, clashing hues among its core items, **When** it is scored, **Then** it receives the lowest score band (<0.3).
5. **Given** any outfit scored for color harmony, **When** the result is inspected, **Then** it includes a human-readable reason identifying which color-theory rule produced the score, and the same outfit scores identically on repeated evaluation (deterministic).

---

### User Story 2 - Outfit ranking prioritizes wearability over cosmetic tiebreaks (Priority: P1)

When several candidate outfits are ranked to pick the top 3-5 to show the user, the system should prefer outfits that fit the weather and occasion correctly, using color/silhouette only to break ties among outfits that are already weather- and formality-appropriate — not blend all four scores into one average where a beautiful but weather-inappropriate outfit could outrank a merely-adequate but correctly-weighted one.

**Why this priority**: This determines which outfits the user actually sees first; getting the priority order wrong undermines trust in the "top" suggestion regardless of how good the underlying dimension scores are individually.

**Independent Test**: Given two candidate outfits with the same aggregate average score but a clearly different weather/formality fit, confirm ranking without specifying any override lands on the one with better weather/formality fit at the top.

**Acceptance Scenarios**:

1. **Given** no explicit ranking override is requested, **When** outfits are ranked, **Then** the system uses weather-and-formality-first tie-breaking rather than a flat average across all four dimensions.

---

### User Story 3 - The best-fitting items in a slot are never silently dropped (Priority: P1)

When the system narrows down a closet to a manageable number of candidates per clothing slot (tops, bottoms, footwear, etc.) before assembling outfits, the items it keeps must be the ones that actually fit the request best — not an arbitrary subset that happened to appear first in the user's closet listing.

**Why this priority**: If the single best-fitting item in a slot is dropped before outfit assembly ever considers it, no amount of correct scoring or ranking downstream can recover it — the user's best possible outfit becomes structurally unreachable.

**Independent Test**: Construct a slot with more candidate items than the retained cap, where only one item is an exact formality/warmth match and it is placed after the cap boundary in closet order; confirm it still survives narrowing.

**Acceptance Scenarios**:

1. **Given** a clothing slot with more candidates than the retained limit, **When** candidates are narrowed down, **Then** the retained items are the best-fitting ones by formality closeness and weather/warmth closeness to the request, regardless of their original order in the closet.

---

### User Story 4 - Color names shown to the user are accurate (Priority: P2)

When the system describes an item or outfit's colors in plain language, the name it picks should be the closest actual match, not a misleading fallback because a genuinely close name was missing from the lookup table.

**Why this priority**: Lower priority than the three correctness-of-selection bugs above because it's a presentation/description accuracy issue, not a selection or ranking bug — no outfit is chosen incorrectly because of it, but a wrong color name in a rationale ("light blue" for a teal item) reads as sloppy and erodes trust.

**Independent Test**: Look up the plain-language name for a set of known hex colors that previously had no close match in the table (e.g. a teal hex value) and confirm the closest, correctly-named entry is returned.

**Acceptance Scenarios**:

1. **Given** a color hex value close to a commonly-recognized color name that was previously absent from the lookup table, **When** its name is looked up, **Then** the correct common name is returned instead of a more distant fallback.

### Edge Cases

- An outfit with fewer than two core-item colors to compare (e.g. a single-color outfit): color harmony scoring must still return a valid, deterministic score rather than erroring.
- A clothing slot with fewer candidates than the retention cap: narrowing must be a no-op (nothing dropped) regardless of sort order.
- Two candidates in a slot with exactly tied fitness: narrowing must still be deterministic (stable, reproducible ordering) across repeated runs.
- An outfit combination scenario already covered by existing coherence guards (e.g. two bottoms, or a full-body item paired with a separate bottom) is unaffected by these fixes — those guards are out of scope here and must keep their exact existing behavior.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The color-harmony score MUST rank a neutral-anchored or single-dominant-hue outfit at or above the same high band regardless of which specific neutral/hue is used.
- **FR-002**: The color-harmony score MUST rank an analogous-hue pairing (colors close together on the hue wheel) above an equal-weight complementary pairing (colors opposite on the hue wheel with similar saturation/lightness).
- **FR-003**: The color-harmony score MUST rank an unbalanced complementary pairing (one color clearly a minor accent by saturation or lightness) above an equal-weight complementary pairing of the same two hues.
- **FR-004**: The color-harmony score MUST rank three-or-more clashing saturated hues at the lowest score band, below any two-hue pairing.
- **FR-005**: The color-harmony score MUST remain a deterministic, pure computation (no external calls, no randomness) producing the same score for the same input every time.
- **FR-006**: The color-harmony score MUST include a human-readable reason identifying which color-theory rule produced the result.
- **FR-007**: Outfit ranking MUST, by default (with no explicit override requested), prioritize weather fitness and formality coherence over color harmony and silhouette balance when ordering candidate outfits.
- **FR-008**: Per-slot candidate narrowing MUST retain the candidates that best match the requested formality and the weather-implied ideal warmth, not an arbitrary positional subset.
- **FR-009**: Per-slot candidate narrowing MUST NOT change which items are excluded on hard constraints (season, existing formality/warmth window, exclusions) — it only changes which items survive the soft numeric cap.
- **FR-010**: The plain-language color-name lookup MUST return the closest common color name for hex values that previously had no sufficiently close entry, without changing the name returned for any hex value that already had one and was correctly identified.
- **FR-011**: None of these fixes MAY change the outfit data model, the suggestion API's request/response contract, the six-value formality enum, or the category-group taxonomy (constitution Principle VI).
- **FR-012**: None of these fixes MAY alter the existing outfit-coherence guards (slot-completeness, valid-combination checks) — their exact current semantics must be preserved.

### Key Entities

- **Outfit candidate**: a set of wardrobe items being scored/ranked; carries per-dimension scores (color harmony, formality coherence, weather fitness, silhouette balance) and an overall rank.
- **Wardrobe item**: an owned clothing item with formality, warmth, season, and color attributes; the unit that gets narrowed per-slot before outfit assembly.
- **Color-name lookup table**: the set of named reference colors used to describe an item or outfit's colors in plain language.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Given the same four representative outfits described in User Story 1's acceptance scenarios, the color-harmony ranking order matches color-theory expectations 100% of the time, on every run.
- **SC-002**: In a scenario with tied average scores across dimensions but differing weather/formality fit, the top-ranked outfit is always the one with better weather/formality fit, not whichever has marginally better color/silhouette.
- **SC-003**: In a constructed slot-narrowing scenario where the single best-fitting item starts outside the retained cap by position alone, it is retained 100% of the time after the fix.
- **SC-004**: A previously-unmatched common color (e.g. teal) is identified by its correct name, not a more distant fallback name, on every lookup.
- **SC-005**: The full existing automated test suite and the deterministic portion of the evaluation gate (retrieval recall, grounding, slot-completeness, valid-combination checks) show no regression compared to the pre-fix baseline.

## Assumptions

- The existing `fit_first_lexicographic` ranking strategy (already implemented and tested) is the correct target default for User Story 2 — this feature does not design a new ranking formula, only changes which existing, already-validated strategy is used by default.
- "Ideal warmth for the weather" in FR-008 is a new mapping from temperature band to a target warmth level (still on the existing frozen 0-5 warmth scale — no parallel *scale*, just a new derived constant), distinct from the existing hard-constraint warmth *ceiling* used elsewhere for hot/warm weather — the two serve different purposes (a ranking target vs. an exclusion cap) and this feature does not merge or replace either.
- This feature touches only the scoring and pre-generation retrieval-narrowing logic; it does not touch generation, explanation-writing, or the API layer.
- The certification-challenge deliverable's "found a bug via review, fixed it, re-measured" narrative (User Story 1) is satisfied by comparing eval-harness output before and after this feature, using a baseline snapshot captured before implementation.
