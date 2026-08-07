# Feature Specification: AI layer port

**Feature Branch**: `feat/007-ai-port`

**Created**: 2026-07-30

**Status**: Draft

**Input**: User description: "Port the salvaged AI pipeline from ../app-legacy/backend/src/whattowear/ into backend/src/whattowear/ (feature 007, the AI layer port), preserving behaviour while fixing two known coupling defects and improving structure, naming, typing and tests. Full context is in docs/handoffs/007-ai-layer-port.md and docs/legacy-ai-inventory.md."

## Context

This is an internal, backend-only port — there is no new user-facing surface. The "users"
below are the same end users the prototype already served (people getting outfit
suggestions from their wardrobe); the feature is that the rebuild now has a working,
evaluated AI layer to build the API on, carried over from the prototype without losing the
three iterations of measured quality work behind it. There is no UI in this slice
(feature 003 owns routes/UI); the acceptance bar is therefore an eval run, not a screen.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Grounded outfit suggestions from an owned wardrobe (Priority: P1)

A user with a persisted closet asks for outfit ideas. The system retrieves style knowledge
first, uses it to shape wardrobe retrieval, has the LLM assemble candidate outfits strictly
from items the user owns, scores every candidate deterministically on weather fitness,
color harmony, silhouette balance and formality coherence, and returns 3–5 ranked outfits
with a rationale that cites the style principles or scores that produced it.

**Why this priority**: This is the whole product. Every other capability in this slice
exists to support this path with evidence it still behaves the way three prior iterations
proved it should.

**Independent Test**: Run the eval harness's golden set through the ported pipeline on the
grounded (default) path and confirm every returned item exists in the fixture wardrobe,
every rationale cites a real `rule_id` or score, and the four dimension scores match what
the deterministic scorers compute standalone.

**Acceptance Scenarios**:

1. **Given** a fixture wardrobe and a styling request, **When** the grounded pipeline runs,
   **Then** it returns 3–5 outfits, each entirely composed of owned items, each with a
   non-empty citation list when the retrieval had something honest to cite.
2. **Given** the same golden-set case run through both the grounded path and the opt-in
   engine path, **When** their outputs are compared, **Then** both satisfy `owned_only` and
   `cites_grounded` at parity with the recorded `010-engine` baseline.

---

### User Story 2 - Deterministic-engine fallback selection (Priority: P2)

A caller opts into the deterministic engine path instead of the default grounded path. The
system enumerates valid combinations from retrieved-and-owned items, scores every one with
the same deterministic scorers as the grounded path, and has the LLM only select from a
pre-scored top-K and write the rationale — never invent a combination or a score.

**Why this priority**: Feature 010 proved this path scores better on weather-appropriateness
and top-rank score, and it stays in the codebase as the stricter, opt-in alternative; it is
not default, so it is secondary to Story 1, but it must keep working identically.

**Independent Test**: Run the golden set through the engine path and confirm `ranked_descending`
holds unqualified (Python order, not LLM order) and every output item is grounded.

**Acceptance Scenarios**:

1. **Given** a styling request routed to the engine path, **When** the enumerator finds fewer
   than 3 valid combinations, **Then** the outfit list is honestly short and citations are
   empty rather than fabricated.

---

### User Story 3 - Reproducible knowledge-base ingestion (Priority: P2)

An engineer running the project for the first time (or after a corpus change) runs one CLI
command and gets a Qdrant index that matches the tracked manifest exactly, without any
document ever being committed to the repository or read from a path inside it.

**Why this priority**: Nothing in Story 1 or 2 works without a populated index, and the
constitution (Principle X) makes reproducibility and non-committal a hard requirement, not
a nicety.

**Independent Test**: Point `CORPUS_LOCAL_DIR` at a local corpus checkout, run the ingestion
CLI twice in a row, and confirm the second run is a no-op (idempotent by content hash) and
`git status` shows no document ever staged.

**Acceptance Scenarios**:

1. **Given** an empty Qdrant instance and a populated `CORPUS_LOCAL_DIR`, **When** the
   ingestion CLI runs, **Then** every `ingest: true` entry in the manifest is chunked,
   embedded and indexed, and every `ingest: false` entry (the copyrighted book) is not.
2. **Given** an already-ingested corpus with no source changes, **When** the CLI runs again,
   **Then** no re-embedding happens (content hash matches) and the command reports that
   nothing changed.

---

### User Story 4 - Evidence that the port preserved behaviour (Priority: P1)

The engineer doing the port (or reviewing it) needs to know the refactor did not silently
change what the pipeline computes, returns, ranks or scores.

**Why this priority**: This is the feature's actual gate, per the constitution's Principle I
and the handoff brief — tied with Story 1 as most critical, because Story 1 is not credible
without it.

**Independent Test**: Run the eval harness over the 24-case golden set on the ported code
and diff the resulting metrics against `../app-legacy/docs/eval-baselines/010-engine/`
metric by metric.

**Acceptance Scenarios**:

1. **Given** the ported pipeline and the recorded `010-engine` baseline, **When** the same
   24 golden cases run, **Then** `owned_only` and `cites_grounded` remain at 1.00 and any
   other metric that moves is explained, not averaged away.

---

### Edge Cases

- What happens when the deterministic enumerator (engine path) or the grounded LLM proposal
  finds fewer than 3 valid combinations? → Return fewer than 3 outfits with an honest empty
  citation list rather than fabricating a fourth. (This is the harness's known metric blind
  spot on `every_choice_cites` / `outfit_count_in_range` — a scoring-harness defect, not a
  pipeline defect; not to be silently "fixed" without re-recording baselines.)
- What happens when a requested item does not exist in the user's closet? → Excluded by the
  grounding guardrail before scoring; never surfaced.
- What happens when the copyrighted reference book is queried by ingestion? → It is never
  embedded (`ingest: false`); only the distilled `.jsonl` cards written in the project's own
  words are.
- What happens when the ingestion CLI runs with no local corpus present? → Fails clearly,
  naming the missing `CORPUS_LOCAL_DIR` path, rather than silently indexing nothing.
- What happens when an AI module is imported without any environment variable set (e.g. by
  a unit test)? → Import succeeds; no database, LLM gateway or Qdrant connection is touched
  until a function that needs one is actually called.
- What happens when the two eval projects' dependencies are installed into the same
  environment? → They must not be — `src/whattowear/eval/` and `backend/evals/` are separate
  `uv` projects specifically because their dependency trees (`langchain-community` pin vs.
  `langchain-cohere`) conflict.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The pipeline MUST produce 3–5 ranked outfit suggestions from a user's closet
  on the grounded path, or fewer with an honest empty citation list when fewer valid
  combinations exist.
- **FR-002**: Every suggested item MUST exist in the requesting user's closet or the shared
  catalog (grounding guardrail), on both the grounded and engine paths.
- **FR-003**: Outfit scoring (weather fitness, color harmony, silhouette balance, formality
  coherence, and their combination) MUST be deterministic, pure-Python, independently
  unit-testable, and free of any LLM call.
- **FR-004**: Style-knowledge retrieval MUST run before wardrobe retrieval and MUST produce
  structured directives that shape the wardrobe query, on every path.
- **FR-005**: Every rationale MUST cite retrieved style-principle `rule_id`s or scorer
  output; fabricated citations are prohibited.
- **FR-006**: The system MUST support both a grounded selection path (default) and an
  opt-in deterministic engine path, matching the behaviour recorded in the `010-engine`
  baseline for each.
- **FR-007**: AI modules (`pipeline/`, `retrieval/`, `scoring/`, `memory/`, `ingest/`) MUST
  be importable with zero environment variables set, and MUST NOT import a database session
  factory directly — all persistence access goes through a `ports.py` Protocol.
- **FR-008**: AI modules MUST NOT import `whattowear.api`, `whattowear.main`, or `fastapi`,
  enforced by `lint-imports`.
- **FR-009**: Production scoring/pipeline code MUST NOT import from the `eval` package; any
  pure predicate shared by both MUST live in a domain module that `eval` imports from.
- **FR-010**: All inline LLM prompts MUST be extracted to versioned files under `prompts/`;
  no prompt string may remain inline in Python.
- **FR-011**: The knowledge-base corpus MUST be described by a tracked manifest
  (`infra/corpus.yaml`) and ingested via an idempotent, content-hash-keyed CLI command; no
  source document may be committed to the repository or read from a path inside it.
- **FR-012**: Per-file corpus licensing MUST carry forward unchanged: public-domain texts
  ingested (`ingest: true`), the copyrighted reference book excluded from embedding
  (`ingest: false`, reference-only).
- **FR-013**: The `src/whattowear/eval/` harness MUST run the pipeline over the golden set
  and write JSONL artifacts; `backend/evals/` MUST read those artifacts and score them with
  RAGAS + openevals, kept as an isolated `uv` project.
- **FR-014**: The eval run over the 24-case golden set MUST be reproducible from the ported
  code, and its metrics MUST be compared against the recorded baselines in
  `../app-legacy/docs/eval-baselines/`, metric by metric.
- **FR-015**: No behavioural change (what a function computes, returns, ranks or scores) MAY
  ship without an eval run demonstrating no regression against the recorded baseline.
- **FR-016**: CI MUST NOT make a live LLM, embedding, rerank or web-search call; the test
  suite MUST run against recorded fixtures only.

### Key Entities

- **Outfit suggestion**: A ranked set of owned items plus a rationale, four dimension
  scores, and a citation list back to style-knowledge `rule_id`s or scorer output.
- **Style-knowledge corpus**: L1 static rules, L3 trend cards, L4 dress codes, plus the two
  ingested reference books — described by `infra/corpus.yaml`, indexed in Qdrant.
- **Golden set case**: One recorded user/wardrobe/request scenario with expected properties,
  used by the eval harness to compute the metrics compared against the baseline.
- **Eval baseline**: A recorded, versioned set of metric values for a prior pipeline
  iteration, kept verbatim as the regression gate.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An eval run over the 24-case golden set on the ported grounded path matches
  the recorded `owned_only` (1.00) and `cites_grounded` (1.00) baselines exactly.
- **SC-002**: Every other eval metric in the comparison table is within a documented,
  explained delta of its recorded baseline — no metric is averaged into an aggregate score
  that would obscure a per-metric regression.
- **SC-003**: 100% of AI modules import successfully with zero environment variables set.
- **SC-004**: Zero inline LLM prompt strings remain in the ported Python code; all five are
  files under `prompts/` with a recorded version.
- **SC-005**: The ingestion CLI reproduces the Qdrant index from an empty state in one
  command, and a second run against an unchanged corpus performs zero re-embedding.
- **SC-006**: Zero corpus documents appear in any commit on this feature branch.

## Assumptions

- The 24-case golden set and the fixture wardrobe already exist and only need to be carried
  over (tracked under `evals/fixtures/` per the handoff), not authored fresh.
- The `../w2w-corpus/` local working copy is available on the machine doing the port with
  the same 16 files described in the inventory; if it is not, ingestion and the full eval
  gate cannot run, and that gap is reported rather than worked around with an alternate
  corpus.
- "Preserving behaviour" is scoped to what the recorded baselines actually measure; any
  pipeline behaviour not covered by an eval metric is improved at the implementer's
  judgment per the handoff's port-with-understanding standard, and called out in the final
  report.
- Real API credentials (AI Gateway, Cohere, Tavily, LangSmith) are available via
  `backend/.env` for the one proving eval run; CI itself never makes live calls.
