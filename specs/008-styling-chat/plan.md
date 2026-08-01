# Implementation Plan: Styling chat

**Branch**: `008-styling-chat` | **Date**: 2026-08-01 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/008-styling-chat/spec.md`

## Summary

Wire the already-complete, evaluated LangGraph pipeline (`pipeline/graph.py`, zero callers today)
to two new backend routes and the Recommend screen's chat surface. A user types a plain-English
styling request; the pipeline retrieves grounded style knowledge, assembles a candidate outfit
from their own closet, scores it deterministically, and returns it with real citations. This
feature renders the single top-ranked outfit (the multi-outfit pager is 009) and adds the
server-side insufficient-closet gate design-decisions.md §11 already specified but never
implemented. Technical approach: reuse the pipeline's existing `invoke()` entry point unmodified
(Principle I), resolve outfit items to real closet items server-side (research.md §1), let the
pipeline own `thread_id` generation (research.md §2), keep the request a plain synchronous
response with a generous backstop timeout rather than a tighter UX cap (research.md §3, per the
user's explicit clarification), and warm the checkpointer at process startup rather than adding a
migration for LangGraph's own internal schema (research.md §4).

## Technical Context

**Language/Version**: Python 3.12 (backend, `uv`), TypeScript / Next.js App Router (frontend) —
both fixed by the constitution's Technology Constraints, no choice to make here.

**Primary Dependencies**: FastAPI, LangGraph (`pipeline.graph.get_compiled_graph`, unmodified),
`psycopg_pool`/`PostgresSaver` (existing checkpointer, unmodified), `openapi-fetch` (frontend API
client, existing), Lucide icons (existing `IconButton` keyword set, extended by one keyword).

**Storage**: Postgres via Supabase (existing `wardrobe_items`/`catalog_items` tables, read-only
here) plus the checkpointer's own `checkpoints*` tables (self-managed by `PostgresSaver.setup()`,
research.md §4 — no new migration). Qdrant (existing `whattowear_kb` collection, read-only via the
pipeline's own retrieval nodes — this feature never queries Qdrant directly).

**Testing**: `pytest` (backend unit + integration, LLM gateway mocked per the existing
`patch.object(engine, "get_chat_model", ...)` pattern — research confirmed at
`tests/unit/pipeline/test_engine.py:162-171`), Vitest + Testing Library (frontend).

**Target Platform**: Linux server (Railway, backend), Vercel (frontend) — both fixed.

**Project Type**: Web application (existing Next.js + FastAPI split) — no new project type.

**Performance Goals**: No fixed user-facing latency target (spec.md Clarifications — the user
explicitly chose "no artificial UX cap" over the handoff's own suggestion of a tighter number).
A 120-second backstop timeout is the only hard bound, intended to catch genuinely stuck requests,
not to shape perceived performance.

**Constraints**: No live LLM call in any test (constitution Quality Bar). No change to
`pipeline/`, `scoring/`, `retrieval/`, or `ports.py` (handoff §8, constitution I). No numeric
score/percentage ever rendered (FR-016). Server-side enforcement of the readiness gate independent
of the client (FR-007).

**Scale/Scope**: Two new backend routes (`GET /recommend/readiness`, `POST /recommend/messages`),
one route-local repository call reuse (no new repository methods — `list_wardrobe_items` already
returns everything both the readiness check and item resolution need), one new frontend screen's
worth of components (hero state, chat state, composer, message list, outfit card) replacing the
existing `/recommend` placeholder body.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **I — Salvaged AI code is authoritative.** No changes to `pipeline/`, `retrieval/`,
      `scoring/`, `memory/`, or `ingest/`. The new route calls `pipeline.graph.
      get_compiled_graph(repo).ainvoke(...)`/`.invoke(...)` exactly as the eval harness already
      does. No eval re-run required — nothing evaluated changes.
- [x] **II — Deterministic scoring.** Untouched — `scoring/` isn't touched, and the route only
      reads `ScoredOutfit.rank_score`/`.scores` that the pipeline already computed
      deterministically; it computes no score of its own beyond the existing float→label mapping
      (pure, already-specified thresholds, no new judgement).
- [x] **III — Style gates wardrobe.** Untouched — this ordering lives entirely inside
      `pipeline/graph.py`, which this feature does not modify.
- [x] **IV — Grounded output.** Every item in a response comes from `repository.
      list_wardrobe_items(user_id)` resolution of ids the pipeline itself already grounded
      (`verify_grounding` node, unmodified). Citations are the pipeline's own `filter_ungrounded_
      cites` output, never invented at the route layer — an empty citation list renders as no
      citations, never a fabricated one (data-model.md `CitedRule`).
- [x] **V — Scorers are eval metrics.** No new quality judgement is introduced; `match_label` is
      the design system's own already-specified threshold mapping over `rank_score`, not a new
      metric.
- [x] **VI — Schema stability.** No taxonomy change. `category_group`/`color_names` reused
      unchanged from `ClosetItemView` (closet.py).
- [x] **VII — Contracts.** New route models live in `schema.py`/route-local Pydantic models;
      frontend consumes them via the generated `schema.d.ts` (regenerated after the route lands),
      no hand-maintained duplicate type.
- [x] **VIII — Visual truth.** Every value on the Recommend screen traces to design-system.md §
      Screen anatomy → Recommend, § Badge, § Scores, § Chat input behavior, or design-decisions.md
      §11/§24-27 (this plan). Loading (skeleton per design-system.md's per-screen skeleton table),
      empty (insufficient-closet gate; zero-outfit reply), error (`recommend.error.*` + retry),
      and offline (composer disabled via `useOnlineStatus`, existing hook) states are all
      in scope. 44px hit areas via the existing `IconButton`/hit-area pattern; a real
      `:focus-visible` per the existing token/pattern (no new focus mechanism needed — reusing
      existing `Button`/`IconButton`/`Chip`); one `<h1>` via the existing `TopHeader`; focus moves
      on navigation (existing `FocusOnNavigate` in the app shell layout already covers route
      changes into `/recommend`); no overlay is introduced by this feature, so no new focus-trap
      surface; reduced motion is inherited from the existing skeleton-pulse CSS this feature
      reuses, no new animation is introduced.
- [x] **IX — One codebase.** No new route tree, no user-agent branching. The chat column's own
      480px/560px caps (design-system.md §5) are a CSS reflow of the same single `/recommend`
      route, not a second surface.
- [x] **X — Documents are data.** No new document, no new corpus entry — this feature only calls
      the existing retrieval nodes, which already read from Qdrant, never from a path in-repo.

No violations. Complexity Tracking is empty.

## Project Structure

### Documentation (this feature)

```text
specs/008-styling-chat/
├── plan.md              # this file
├── research.md           # Phase 0 — the four named decisions + two supporting ones
├── data-model.md          # Phase 1 — route-local models, config, frontend conversation state
├── quickstart.md          # Phase 1 — end-to-end validation script
├── contracts/
│   └── recommend.md       # Phase 1 — the two new endpoints
└── tasks.md               # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
frontend/
├── app/(app)/recommend/
│   ├── page.tsx                       # replace placeholder body with <RecommendChat />
│   ├── page.module.css                # drop now-unused .empty/.body styles
│   └── page.test.tsx                  # new — screen-level integration test
├── components/
│   ├── recommend/                     # new directory
│   │   ├── RecommendChat.tsx           # top-level client component: state machine, composer, message list
│   │   ├── RecommendChat.module.css
│   │   ├── RecommendChat.test.tsx
│   │   ├── HeroState.tsx               # brand mark, wordmark, greeting, welcome bubble, suggestion chips
│   │   ├── HeroState.module.css
│   │   ├── ChatMessageList.tsx         # scrollable list, user/assistant bubbles
│   │   ├── ChatMessageList.module.css
│   │   ├── OutfitCard.tsx              # single-outfit reply body: thumbnails + rule list (no citations on the card itself, §3.3)
│   │   ├── OutfitCard.module.css
│   │   ├── Composer.tsx                # pinned input bar + send button, offline/in-flight disabling
│   │   ├── Composer.module.css
│   │   ├── InsufficientClosetGate.tsx  # blocks the composer, names what's missing
│   │   ├── InsufficientClosetGate.module.css
│   │   └── useGreeting.ts              # time-of-day greeting (known-gaps.md §0.7)
│   └── calendar/RecommendCalendarContext.tsx   # unchanged, reused as-is (already built by 012)
└── lib/
    └── recommend/
        └── timeOfDayGreeting.ts        # pure function, unit-testable in isolation

backend/src/whattowear/
├── api/v1/routes/
│   └── recommend.py                    # new — GET /recommend/readiness, POST /recommend/messages
├── main.py                             # +2 lines: include_router(recommend_router), warm get_compiled_graph() in lifespan
├── core/config.py                      # +3 Settings fields (data-model.md)
├── readiness.py                        # new, small — the pure slot-coverage function, unit-tested alone (not pipeline/, so no Principle I concern; not framework-free-restricted either since it never touches AI code)
└── schema.py                           # + route-facing response models if not kept route-local (decide at implement time per closet.py precedent of keeping them route-local)

backend/tests/
├── unit/test_readiness.py              # new — slot-coverage algorithm, all boundary cases
└── integration/test_recommend_routes.py # new — both routes, LLM gateway mocked (research.md, Testing)
```

**Structure Decision**: Everything fits the fixed layout. The one new backend module,
`readiness.py`, sits beside `categories.py`/`colors.py` (existing small, framework-free,
pure-Python helper modules at package root) rather than inside `pipeline/` — it is wardrobe-shape
arithmetic the route needs *before* deciding whether to call the pipeline at all, not part of the
pipeline itself, so it is deliberately kept out of the directory Principle I protects.

## Complexity Tracking

No violations — table intentionally empty.
