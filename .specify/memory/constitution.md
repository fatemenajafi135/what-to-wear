<!--
Sync Impact Report
==================
Version change: (template, unratified) → 1.0.0
Rationale: initial ratification, MINOR/MAJOR n/a — treated as first release (1.0.0)
per semantic versioning for a first-time constitution.

Modified principles: n/a (template → concrete, no prior named principles)
Added principles:
  - I. Existing Pipeline Is Authoritative
  - II. Deterministic Core, LLM At The Edges
  - III. Style Knowledge Gates Wardrobe Retrieval
  - IV. Grounded Output Only
  - V. Scoring Functions Are Eval Metrics
  - VI. Schema Stability
  - VII. Single Source Of Truth For Contracts
Added sections: Technology Constraints, Quality Bar, Governance (amendment +
  versioning + compliance procedure)
Removed sections: none (template placeholders only)

Templates requiring updates:
  - .specify/templates/plan-template.md: ✅ no changes needed — its
    "Constitution Check" gate is generic and already defers to this file.
  - .specify/templates/spec-template.md: ✅ no changes needed — generic,
    no principle-specific references to update.
  - .specify/templates/tasks-template.md: ✅ no changes needed — generic,
    no principle-specific references to update.
  - docs/SDD-HANDOFF.md: ✅ appendix already aligned (edited prior to this run
    to match schema.py's actual taxonomy — see principle VI).
  - Installed speckit skills (.claude/skills/speckit-*): ✅ reviewed, all
    generic / agent-agnostic, no hardcoded principle text to update.

Follow-up TODOs: none.
-->

# What to Wear Constitution
<!-- Solo-developer AI personal styling agent; course capstone that may become a product. -->

## Core Principles

### I. Existing Pipeline Is Authoritative
The retrieval strategies (baseline, hybrid, advanced), chunking, ingest, knowledge
base, and eval harness in `backend/src/whattowear` are working and already
evaluated. New features MUST integrate with them as-is. Rewriting any of these
components requires explicit justification in the plan and a passing eval run
showing no regression against `backend/artifacts/eval_runs`. Rationale: this
code represents validated, graded work; unjustified rewrites risk losing
evaluated behavior for no measurable gain.

### II. Deterministic Core, LLM At The Edges
Outfit generation and scoring MUST be pure Python and independently unit-testable.
The LLM's role is limited to parsing intent and writing rationale text. The LLM
MUST NOT select clothing items directly — item selection is the output of
deterministic pruning, combination, and scoring code. Rationale: deterministic
selection is reproducible, unit-testable, and immune to hallucinated items;
confining the LLM to language tasks keeps the one failure-prone component out
of the one place correctness matters most.

### III. Style Knowledge Gates Wardrobe Retrieval
The style knowledge base MUST be queried first and MUST return structured
directives, never raw prose. Those structured directives shape the subsequent
wardrobe query. Style retrieval and wardrobe retrieval are never parallel
tracks — style retrieval always gates wardrobe retrieval. Rationale: this
ordering is what makes the generated rationale defensible and traceable back
to a specific styling principle, rather than a post-hoc justification.

### IV. Grounded Output Only
Every item in a suggested outfit MUST exist in the user's closet or the shared
catalog — no invented items. Every rationale MUST cite retrieved style
principles (rule_ids) or scorer output. Rationale: grounding is the
hallucination killer for a system whose entire value proposition is "wear
something you actually own."

### V. Scoring Functions Are Eval Metrics
Any function that judges outfit quality (color harmony, formality coherence,
weather fitness, silhouette balance, etc.) MUST be written as deterministic
code first, then reused unchanged inside the eval harness. No quality metric
may exist only inside a prompt. Rationale: a metric that only an LLM can
compute cannot be trusted as ground truth for the metric itself.

### VI. Schema Stability
The item taxonomy already exists in `backend/src/whattowear/schema.py` and
`categories.py` and is frozen as-is: category groups (`top`, `bottom`,
`full_body`, `outerwear`, `footwear`, `accessory`), the six-value formality
enum (`casual`, `smart_casual`, `business_casual`, `semi_formal`, `formal`,
`black_tie`), warmth 0-5, seasons, and hex colors. New features MUST conform to
this taxonomy. They MUST NOT introduce a parallel numeric formality scale or
rename existing category groups. Any change to the taxonomy requires an
explicit migration and is a breaking change. Rationale: retrofitting the item
taxonomy after other features depend on it is the single most expensive
mistake available on this project.

### VII. Single Source Of Truth For Contracts
Pydantic models defined in the backend are the API contract. The frontend MUST
consume generated types from OpenAPI. Hand-maintained duplicate type
definitions are prohibited. Rationale: a second, hand-written copy of a type
drifts from the source the moment either side changes without the other.

## Technology Constraints

- Python 3.12, `uv`, FastAPI, LangGraph.
- Postgres, auth, and image storage via Supabase, using the pooler connection
  (port 6543).
- Vector search via Qdrant, hybrid dense similarity plus metadata filtering.
  Qdrant is kept; migration to pgvector is out of scope.
- Redis and backend deployment on Railway.
- LangSmith tracing on every LLM and retrieval call.
- Frontend is Next.js on Vercel, built only after design is finalized.
- Backend code lives in `backend/`, frontend in `frontend/`. Do not
  restructure the repository layout.

## Quality Bar

- Deterministic logic requires unit tests.
- LLM-dependent paths require an entry in `data/golden_set.yaml`.
- Retrieval output is inspected before generation output is trusted.
- Simplicity over abstraction: this is a solo project. Repository patterns,
  service layers, or abstract base classes are not introduced unless two
  concrete implementations exist today.

## Governance

This constitution supersedes ad hoc practice for this project. Every
`/speckit.plan` MUST include a Constitution Check gate, and any proposed
violation MUST be recorded in that plan's Complexity Tracking table with the
specific principle, the reason it cannot be satisfied, and why a simpler
alternative was rejected — an unresolved violation blocks `/speckit.implement`.

Amendments are made by editing this file directly, updating the Sync Impact
Report, and propagating any changed guidance into
`.specify/templates/plan-template.md`, `.specify/templates/spec-template.md`,
`.specify/templates/tasks-template.md`, and `docs/SDD-HANDOFF.md`. Versioning
follows semantic versioning: MAJOR for backward-incompatible principle removal
or redefinition, MINOR for a new principle or materially expanded guidance,
PATCH for wording and clarification fixes.

Principles I ("Existing pipeline is authoritative") and III ("Style knowledge
gates wardrobe retrieval") are the two clauses this project depends on most —
any amendment touching them requires re-reading `docs/SDD-HANDOFF.md` first to
confirm the change doesn't undercut the architecture it describes.

**Version**: 1.0.0 | **Ratified**: 2026-07-15 | **Last Amended**: 2026-07-15
