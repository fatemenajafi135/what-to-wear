# Implementation Plan: Chat history

**Branch**: `feat/011-chat-history` | **Date**: 2026-08-03 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/011-chat-history/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Persist styling conversations durably (a session row from the first user message onward, one
message row per turn) so a reload doesn't lose them, add a read-only `/history` list and
`/history/:sessionId` detail screen, wire "Continue conversation" to resume the same
`thread_id`, and link newly-created outfits back to the session that produced them. No pipeline,
scoring, or retrieval change — this is persistence and UI wrapped around the existing
`POST /recommend/messages` route.

## Technical Context

**Language/Version**: Python 3.12 (backend, `uv`), TypeScript (frontend, Next.js App Router)

**Primary Dependencies**: FastAPI, SQLAlchemy Core (`text()` + raw SQL, matching every existing
repository — no ORM models), Pydantic (API contracts); React 19, `openapi-fetch` generated client

**Storage**: Postgres via Supabase, through the pooler — two new tables (`sessions`, `messages`),
one new nullable column on `outfits` (`thread_id`)

**Testing**: `pytest` (unit + integration, backend), Vitest + Testing Library (frontend)

**Target Platform**: Next.js web app + installed PWA (desktop and mobile, one codebase)

**Project Type**: web-service + web-app (fixed layout: `frontend/`, `backend/`)

**Performance Goals**: No new latency budget — reuses `POST /recommend/messages`'s existing
120s backstop; new reads (`GET /recommend/sessions`, `GET /recommend/sessions/{id}`) are simple
indexed queries at personal-app scale, no target beyond "not perceptibly slow"

**Constraints**: Must not change pipeline/scoring/retrieval behavior or how `thread_id` is
minted (§25); must not touch `ports.py`; every new table needs RLS + GRANT + query-level
ownership check, proven by a two-user test (pooler role has BYPASSRLS)

**Scale/Scope**: Single-user-owned rows, personal-app volume (tens to low hundreds of sessions
per user, not a scale requiring pagination in this slice — matches Outfits gallery's own
unpaginated `list_outfits`)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **I — Salvaged AI code is authoritative.** No change to retrieval, chunking, ingest, KB,
      scoring, pipeline, or eval harness. `graph.invoke(...)` is called exactly as today;
      `thread_id` minting in `parse_request` is untouched. No eval run needed — nothing in
      `pipeline/`, `retrieval/`, or `scoring/` is touched.
- [x] **II — Deterministic scoring.** N/A to this feature — no new scoring logic. Existing
      scorers/guards are unchanged; this feature only persists their already-computed output.
- [x] **III — Style gates wardrobe.** N/A — no new retrieval path. Unchanged ordering.
- [x] **IV — Grounded output.** Archived citations are read back from `outfits.citations`
      (already grounded at write time, §38) — never re-generated or fabricated for display.
- [x] **V — Scorers are eval metrics.** N/A — no new quality judgement of any kind.
- [x] **VI — Schema stability.** No taxonomy field touched. `messages.kind` is a new
      discriminator on a brand-new table, not a parallel formality/category scale.
- [x] **VII — Contracts.** New routes get Pydantic response models; frontend regenerates
      `schema.d.ts` and consumes it — no hand-written duplicate types.
- [x] **VIII — Visual truth.** `/history` and `/history/:sessionId` build only from
      `design/design-system.md` §§ Chat history/Session detail screen anatomy, § Badge, § Copy
      inventory, and `docs/design-decisions.md` (including the new §44/§45 this plan adds).
      Loading/empty/error/offline states are explicit tasks. No code copied from
      `design/prototype/`.
- [x] **IX — One codebase.** `/history` is a normal App Router route, reachable at every form
      factor via the existing Recommend header icon; desktop gets the same CSS-only two-pane
      pattern Outfits/Closet already use (`page.module.css`, `min-width:1024px`), not a second
      build.
- [x] **X — Documents are data.** N/A — no corpus/document involved.

No violations. Complexity Tracking is empty.

## Project Structure

### Documentation (this feature)

```text
specs/011-chat-history/
├── plan.md              # This file
├── research.md          # Phase 0 output — §44/§45 full reasoning
├── data-model.md         # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
frontend/
├── app/(app)/history/
│   ├── page.tsx                    # /history — list + desktop two-pane shell
│   ├── page.module.css             # mirrors app/(app)/outfits/page.module.css
│   ├── HistoryList.tsx             # owns fetch/loading/empty/error state
│   ├── HistoryList.test.tsx
│   └── [sessionId]/
│       ├── page.tsx                # /history/:sessionId
│       └── SessionDetail.test.tsx  # (or co-located with a SessionDetail component)
├── app/(app)/recommend/page.tsx    # wire the "history" IconButton (currently inert)
├── components/recommend/RecommendChat.tsx  # accept an initial thread_id + messages to resume
└── lib/api/schema.d.ts             # regenerated, not hand-edited

backend/
├── src/whattowear/api/v1/routes/recommend.py   # extend: list/get sessions, persist messages
├── src/whattowear/repositories/
│   └── supabase_sessions.py        # new — sessions + messages persistence
└── tests/
    ├── unit/test_supabase_sessions_repository.py
    ├── integration/test_sessions_rls.py
    └── (recommend route tests extended in place)

infra/supabase/migrations/
└── 0011_chat_history.sql           # sessions, messages, outfits.thread_id — RLS + GRANT
```

**Structure Decision**: Extends the existing `recommend` router and `outfits` table rather than
adding a second router or a parallel persistence module (handoff §4.1: "Extend the existing
router rather than adding a second one"). One new repository (`supabase_sessions.py`) matching
the one-repository-per-owned-table-group convention already used for closet/outfits/calendar.
Frontend adds exactly one new route segment (`app/(app)/history/`); no other directory moves.
