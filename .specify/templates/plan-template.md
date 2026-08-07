# Implementation Plan: [FEATURE]

**Branch**: `[###-feature-name]` | **Date**: [DATE] | **Spec**: [link]

**Input**: Feature specification from `/specs/[###-feature-name]/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

[Extract from feature spec: primary requirement + technical approach from research]

## Technical Context

<!--
  ACTION REQUIRED: Replace the content in this section with the technical details
  for the project. The structure here is presented in advisory capacity to guide
  the iteration process.
-->

**Language/Version**: [e.g., Python 3.11, Swift 5.9, Rust 1.75 or NEEDS CLARIFICATION]

**Primary Dependencies**: [e.g., FastAPI, UIKit, LLVM or NEEDS CLARIFICATION]

**Storage**: [if applicable, e.g., PostgreSQL, CoreData, files or N/A]

**Testing**: [e.g., pytest, XCTest, cargo test or NEEDS CLARIFICATION]

**Target Platform**: [e.g., Linux server, iOS 15+, WASM or NEEDS CLARIFICATION]

**Project Type**: [e.g., library/cli/web-service/mobile-app/compiler/desktop-app or NEEDS CLARIFICATION]

**Performance Goals**: [domain-specific, e.g., 1000 req/s, 10k lines/sec, 60 fps or NEEDS CLARIFICATION]

**Constraints**: [domain-specific, e.g., <200ms p95, <100MB memory, offline-capable or NEEDS CLARIFICATION]

**Scale/Scope**: [domain-specific, e.g., 10k users, 1M LOC, 50 screens or NEEDS CLARIFICATION]

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Answer each gate explicitly. Mark N/A where a principle genuinely does not apply to this
feature, and say why in one line. Any gate that cannot be satisfied goes into Complexity
Tracking with a justification, or the plan does not proceed to `/speckit-tasks`.

- [ ] **I — Salvaged AI code is authoritative.** Does this plan regenerate any of
      retrieval, chunking, ingest, the knowledge base, scoring, the pipeline, or the eval
      harness? Refactoring is fine; regenerating is prohibited. If it refactors any of
      them, is an eval run against `docs/eval-baselines/` included as a task?
- [ ] **II — Deterministic scoring.** Is every outfit score pure Python with no LLM call?
      Is a deterministic guard, not the LLM, the last checkpoint before output?
- [ ] **III — Style gates wardrobe.** Does style retrieval run first and shape the wardrobe
      query? The two are never parallel tracks.
- [ ] **IV — Grounded output.** Is every surfaced item provably owned by the requester?
      Is every rationale cited, or honestly uncited rather than fabricated?
- [ ] **V — Scorers are eval metrics.** Is every new quality judgement deterministic code,
      reused unchanged by the harness, rather than living inside a prompt?
- [ ] **VI — Schema stability.** Does this conform to the frozen taxonomy, without adding a
      parallel formality scale or renaming a category group?
- [ ] **VII — Contracts.** Does the frontend consume OpenAPI-generated types, with no
      hand-maintained duplicate?
- [ ] **VIII — Visual truth.** Does every visual value read a token from
      `design/design-system.md` or `docs/design-decisions.md`? Is no code copied from
      `design/prototype/`? Does every screen implement loading, empty, error and offline?
      Is WCAG AA met — 44px targets, real `:focus-visible`, one `<h1>` per screen, focus
      moved on navigation, focus trapped and restored in overlays, reduced motion honoured?
- [ ] **IX — One codebase.** Identical routes at every form factor, with only the chrome
      changing? No separate mobile build and no user-agent branching on what a user can
      reach? Do all four display-mode × form-factor combinations work?
- [ ] **X — Documents are data.** Is no document committed or read from a path inside the
      repo? Is any new corpus entry described in `infra/corpus.yaml`?

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

<!--
  The repository layout is FIXED by the constitution ("Technology Constraints":
  frontend/, backend/, infra/, design/, docs/ — do not restructure). There is no
  layout choice to make. List only the concrete paths this feature touches.

  There is deliberately no mobile-app option. Principle IX: one Next.js codebase
  serves the desktop web experience and the installed mobile PWA. Creating ios/,
  android/, or any second frontend is a constitutional violation, not an option.
-->

```text
frontend/                     # Next.js App Router + TypeScript. Web AND installed PWA.
├── app/                      # routes — identical at every form factor
├── components/
├── styles/                   # token layers: system → semantic → theme blocks
└── public/                   # icons/ and logo.svg already exist; do not regenerate

backend/
├── pyproject.toml
├── src/whattowear/           # src layout, single package
│   ├── main.py  api/v1/routes/  core/  schemas/  models/
│   ├── repositories/         # ALL database access
│   ├── services/             # use cases: repositories + AI
│   ├── pipeline/ retrieval/ scoring/ memory/ ingest/   # framework-free
│   ├── prompts/              # prompt FILES, loaded by name — never inline strings
│   ├── adapters/  ports.py   # Protocols; AI reaches the DB only through these
│   └── evals/
└── tests/{unit,integration,evals}

infra/
├── corpus.yaml               # the tracked corpus manifest
└── supabase/migrations/      # the ONLY migration system — Alembic is not used
```

**Structure Decision**: list the concrete files and directories this feature adds or
changes, within the fixed layout above. If this feature appears to need a path outside it,
that is a Complexity Tracking entry, not a restructure.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |
