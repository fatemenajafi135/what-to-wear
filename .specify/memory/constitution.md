<!--
Sync Impact Report
==================
Version change: 1.0.0 (legacy prototype) → 2.0.0
Rationale: MAJOR. Principle II is redefined rather than clarified — the legacy
wording ("The LLM MUST NOT select clothing items directly") was measured to be
untrue of its own default path, so continuing to assert it would make the
constitution aspirational. See docs/legacy-ai-inventory.md §Q6.

Carried forward unchanged in substance:
  - III. Style Knowledge Gates Wardrobe Retrieval
  - IV.  Grounded Output Only
  - V.   Scoring Functions Are Eval Metrics
  - VI.  Schema Stability
  - VII. Single Source Of Truth For Contracts

Redefined:
  - I.  Existing Pipeline Is Authoritative → Existing AI Code Is Authoritative
        (paths updated for the rebuild layout; salvage scope made explicit)
  - II. Deterministic Core, LLM At The Edges
        → Deterministic Scoring, LLM Within Guardrails

Added (the rebuild's frontend and data concerns, absent from 1.0.0):
  - VIII. The Design System Is The Source Of Visual Truth
  - IX.   One Codebase Serves Web And Installed PWA
  - X.    Documents Are Data, Not Code

Removed: none.

Templates requiring updates:
  - .specify/templates/plan-template.md: ⚠ NOT YET REVIEWED against this file.
  - .specify/templates/spec-template.md: ⚠ NOT YET REVIEWED.
  - .specify/templates/tasks-template.md: ⚠ NOT YET REVIEWED.
    All three ship as generic Spec Kit defaults and are expected to need no
    principle-specific edits, but that has not been verified. Check before the
    first /speckit-plan run.

Follow-up TODOs:
  - Confirm the three open product decisions in docs/design-decisions.md §11
    (password minimum, body text size at 768px+, wardrobeMinItems).
-->

# What to Wear Constitution

<!-- A from-scratch rebuild of a personal styling agent, delivered as one Next.js
codebase serving both the desktop web experience and the installed mobile PWA,
on top of the prototype's evaluated AI pipeline. -->

## Core Principles

### I. Existing AI Code Is Authoritative

The retrieval strategies (baseline, hybrid, advanced), chunking, ingest, knowledge base,
scoring, LangGraph pipeline, and eval harness salvaged from the prototype are working,
evaluated code. Features MUST integrate with them as they are. Regenerating any of these
components is prohibited; refactoring them is expected and welcome, but any refactor MUST
be justified in the plan and MUST be accompanied by an eval run showing no regression
against the recorded baselines in `docs/eval-baselines/`.

**Rationale:** this code carries three iterations of measured quality work. A rewrite that
"looks cleaner" but is not evaluated is a net loss, and the baselines exist precisely so
that claim can be tested rather than argued.

### II. Deterministic Scoring, LLM Within Guardrails

Outfit **scoring** MUST be pure Python, independently unit-testable, and free of any LLM
call. The four dimension scorers and their combination strategy are the single source of
outfit quality.

On the **grounded path (the default)**, the LLM assembles candidate outfits from an
inventory that deterministic retrieval has already restricted to items the user owns. Every
candidate it proposes MUST then pass the deterministic coherence guards and MUST be scored
by the deterministic scorers before reaching the user. The LLM proposes; Python disposes.

On the **engine path (opt-in)**, enumeration, scoring and final ranking are entirely
deterministic and the LLM only selects which of a pre-scored top-K to surface and writes
the rationale.

In all cases the LLM MUST NOT invent an item, MUST NOT compute or override a score, and
MUST NOT be the last checkpoint before output.

**Rationale:** the previous wording claimed the LLM never selects items, which measurement
showed was false on the default path. A principle that the code visibly violates trains
everyone to read the constitution as decoration. This states the guarantee that is actually
enforced — and it is still a strong one, because grounding and scoring are the two places
correctness matters.

### III. Style Knowledge Gates Wardrobe Retrieval

The style knowledge base MUST be queried first and MUST return structured directives, never
raw prose. Those directives shape the subsequent wardrobe query. Style retrieval and
wardrobe retrieval are never parallel tracks — style retrieval always gates wardrobe
retrieval.

**Rationale:** this ordering is what makes a rationale defensible and traceable to a
specific styling principle, rather than a post-hoc justification of an arbitrary pick.

### IV. Grounded Output Only

Every item in a suggested outfit MUST exist in the requesting user's closet or the shared
catalog. Every rationale MUST cite retrieved style principles (`rule_id`s) or scorer output.
Where the deterministic fallback produces an outfit with nothing honest to cite, it MUST
return an empty citation list rather than fabricate one.

**Rationale:** grounding is the hallucination killer for a product whose entire proposition
is "wear something you actually own." The fallback clause is explicit because the eval
harness previously scored honest empty citations as a failure.

### V. Scoring Functions Are Eval Metrics

Any function that judges outfit quality MUST be written as deterministic code first, then
reused unchanged inside the eval harness. No quality metric may exist only inside a prompt.

**Rationale:** a metric only an LLM can compute cannot be trusted as ground truth for
itself.

### VI. Schema Stability

The item taxonomy is frozen as inherited: category groups (`top`, `bottom`, `full_body`,
`outerwear`, `footwear`, `accessory`), the six-value formality enum (`casual`,
`smart_casual`, `business_casual`, `semi_formal`, `formal`, `black_tie`), warmth 0–5,
seasons, hex colors, plus `pattern` and `fit`. Features MUST conform. They MUST NOT
introduce a parallel numeric formality scale or rename category groups. Any taxonomy change
requires an explicit migration and is a breaking change.

**Rationale:** retrofitting the item taxonomy once other features depend on it is the single
most expensive mistake available on this project.

### VII. Single Source Of Truth For Contracts

Pydantic models in the backend are the API contract. The frontend MUST consume types
generated from OpenAPI. Hand-maintained duplicate type definitions are prohibited.

**Rationale:** a second, hand-written copy of a type drifts the moment either side changes
without the other.

### VIII. The Design System Is The Source Of Visual Truth

Every visual value — color, spacing, radius, type, motion, elevation — MUST come from
`design/design-system.md`, read through a semantic token. Where that file is silent or
contradicts itself, `docs/design-decisions.md` resolves it and is equally binding. No
component may reference a raw hex or a magic pixel value.

`design/prototype/` is reference material for understanding intent. **Code MUST NEVER be
copied from it**, and nothing under `design/prototype/_scaffolding/` may appear in the
product.

Every screen MUST implement its loading, empty, error and offline states — these are
specified, not optional. Accessibility is WCAG 2.1 AA: 44×44px minimum hit targets, a real
`:focus-visible` ring, one `<h1>` per screen, focus moved on navigation, focus trapped and
restored in overlays, and `prefers-reduced-motion` honoured by every animation.

**Rationale:** the design system spells out states, copy and tokens precisely so they are
not reinvented per screen. An invented value is indistinguishable from a bug six screens
later, and the accessibility items listed are the ones the prototype demonstrably got wrong.

### IX. One Codebase Serves Web And Installed PWA

A single Next.js application serves the desktop web experience and the installed mobile PWA.
Routes and destinations are **identical at every form factor**; only the chrome changes
(bottom tab bar → icon rail → sidebar). There is no separate mobile build, no duplicated
route tree, and no user-agent branching to decide what a user can reach.

Behaviour additionally depends on browser-tab versus installed-standalone display mode, not
only on viewport width. All four combinations MUST work.

**Rationale:** two codebases for one product diverge immediately, and the divergence always
lands on the platform with fewer users. Form factor changes the frame, never the map.

### X. Documents Are Data, Not Code

Source documents MUST NEVER be committed, and MUST NEVER be read from a path inside the
repository. They live in object storage and are described in git by the tracked manifest
`infra/corpus.yaml`, which together with the code MUST rebuild the index reproducibly in one
command. Ingestion is a CLI entry point, never an HTTP endpoint, and is idempotent by
content hash.

Tracked as deliberate exceptions: the corpus manifest, prompts, eval datasets, recorded
baselines, the small fixture corpus under `evals/fixtures/`, and database migrations.

If an artifact can be regenerated by running a command, it does not belong in git.

**Rationale:** the prototype committed 48 MB of source books, which is how a repository
becomes permanently expensive to clone. The fixture-corpus exception exists so evals can run
in CI, which has no object-storage credentials.

## Technology Constraints

- **Backend:** Python 3.12, `uv`, FastAPI, LangGraph. Package is `backend/src/whattowear/`
  using a src layout.
- **AI modules are framework-free.** `pipeline/`, `retrieval/`, `scoring/`, `memory/` and
  `ingest/` MUST NOT import `whattowear.api`, `whattowear.main`, or `fastapi`. Enforced in
  CI by `lint-imports`, not by convention. Database access reaches them through a Protocol
  defined in `ports.py`, never by importing a session factory.
- **Prompts are files** under `prompts/`, loaded by name and versioned. Inline prompt
  strings in Python are prohibited. Every eval row records the prompt version and model.
- **Data:** Postgres, auth and object storage via Supabase, through the pooler (port 6543).
  Schema lives in `infra/supabase/migrations/` — Supabase migrations only. **Alembic is not
  used**; it cannot express RLS policies, storage buckets or auth configuration, and two
  migration systems means two sources of truth.
- **Vector search:** Qdrant. Migration to pgvector is out of scope.
- **Frontend:** Next.js App Router, TypeScript, on Vercel. Service worker via Serwist.
- **Backend deployment:** Railway.
- **Tracing:** LangSmith on every LLM and retrieval call, with token count, latency and cost.
- **Layout is fixed:** `frontend/`, `backend/`, `infra/`, `design/`, `docs/`. Do not
  restructure.

## Quality Bar

- Deterministic logic requires unit tests.
- LLM-dependent paths require an entry in the golden set.
- **CI MUST NOT make live LLM calls.** Recorded fixtures only — otherwise the suite is
  flaky and bills real money on every push.
- CI gates: backend `ruff`, `mypy`, `pytest`, `lint-imports`; frontend `eslint`,
  `tsc --noEmit`, `next build`.
- Retrieval output is inspected before generation output is trusted.
- **Simplicity over abstraction.** An interface, port, or layer is introduced only when
  there are two concrete implementations today or a measured problem it solves. `ports.py`
  qualifies on both counts: three retrieval strategies exist, and three AI modules currently
  import a session factory that builds a database engine at import time, which makes the
  pipeline unimportable without a database. Speculative abstraction remains prohibited.
- No secrets in the repository. Only `.env.example` is tracked.

## Governance

This constitution supersedes ad hoc practice. Every `/speckit-plan` MUST include a
Constitution Check gate, and any proposed violation MUST be recorded in that plan's
Complexity Tracking table with the specific principle, why it cannot be satisfied, and why a
simpler alternative was rejected. An unresolved violation blocks `/speckit-implement`.

Amendments are made by editing this file, updating the Sync Impact Report above, and
propagating changed guidance into `.specify/templates/`. Versioning is semantic: MAJOR for
backward-incompatible principle removal or redefinition, MINOR for a new principle or
materially expanded guidance, PATCH for wording fixes.

Principles I, IV and VIII are the ones this project depends on most. Any amendment touching
them requires re-reading `docs/legacy-ai-inventory.md` (for I and IV) or
`design/design-system.md` together with `docs/design-decisions.md` (for VIII) first, to
confirm the change does not undercut evidence already gathered.

A principle that the code visibly violates MUST be amended or the code fixed — never left
standing as aspiration. That failure mode is what produced this version.

**Version**: 2.0.0 | **Ratified**: 2026-07-28 | **Last Amended**: 2026-07-28
