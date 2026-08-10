# Implementation Plan: Recommend Chat Persists Across In-App Navigation

**Branch**: `feat/019-recommend-chat-persistence` | **Date**: 2026-08-11 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/019-recommend-chat-persistence/spec.md`

## Summary

The Recommend screen's styling chat resets on in-app navigation because its conversation state
lives only in `RecommendChat`'s local `useState`, and Next.js unmounts that component on every
route change (GitHub issue #47). The backend's own persistence (LangGraph checkpointer,
`chat_history`) is confirmed intact via the existing `?thread_id=` resume path — this is a
frontend-only fix, no backend change.

Technical approach: relocate the conversation state (and the two network actions that mutate it)
from component-local `useState` into a module-level external store
(`frontend/lib/recommend/recommendChatStore.ts`), read reactively via `useSyncExternalStore`.
Module scope survives component unmount/remount but not a real JS-context reload, which is
exactly the persist/reset split the spec requires — for free, not by detecting "was this a
reload." `RecommendChat` becomes a thin view over the store; "New chat" and the `hasUserMessage`
read move to `page.tsx` calling the store directly, retiring the current
`forwardRef`/`useImperativeHandle` indirection. Closet readiness stays local and refetches on
every mount per the `/speckit-clarify` decision (FR-009). See research.md for full rationale and
rejected alternatives (Context, sessionStorage/localStorage).

## Technical Context

**Language/Version**: TypeScript (repo-standard), Next.js App Router

**Primary Dependencies**: React `useSyncExternalStore` (built-in, no new dependency); existing
`apiClient` (`frontend/lib/api/client.ts`) for the two network actions, unchanged endpoints
(`POST /recommend/turns`, `POST /recommend/messages`, `GET /recommend/sessions/{id}`,
`GET /recommend/readiness`)

**Storage**: N/A — no persistence layer touched; the store is in-memory only, by design (it must
NOT survive a real reload, per FR-002)

**Testing**: Vitest + Testing Library (repo-standard), `frontend/vitest.config.ts`

**Target Platform**: Browser + installed PWA, both form factors, per Principle IX — this feature
touches no chrome, only the Recommend screen's own state, so no new form-factor branching

**Project Type**: web (Next.js frontend only; no backend project touched)

**Performance Goals**: No regression — the fix removes a redundant remount/re-render, if anything
it's a net reduction in work (no re-fetch flash)

**Constraints**: Must not change any API contract (FR-008); must not regress the existing
`?thread_id=` resume path (FR-004); frontend test count must not drop (baseline 347)

**Scale/Scope**: One screen (`app/(app)/recommend/`), one new module
(`lib/recommend/recommendChatStore.ts`), no other route or backend code

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **I — Salvaged AI code is authoritative.** N/A. No retrieval, chunking, ingest, knowledge
      base, scoring, pipeline, or eval-harness code is touched — this is a Recommend-screen
      frontend state fix.
- [x] **II — Deterministic scoring.** N/A. No scoring code touched.
- [x] **III — Style gates wardrobe.** N/A. No retrieval ordering touched.
- [x] **IV — Grounded output.** N/A. No item/rationale generation touched; the store relocates
      existing response data, it doesn't alter what's shown.
- [x] **V — Scorers are eval metrics.** N/A. No quality judgement code touched.
- [x] **VI — Schema stability.** N/A. No taxonomy touched. `ChatMessage`/`StylingOutfit` types are
      reused unchanged (see data-model.md).
- [x] **VII — Contracts.** Satisfied. No API contract changes; `frontend/lib/api/schema.d.ts` is
      not regenerated because nothing in `backend/` changes. The store's own internal interface
      (contracts/recommend-chat-store.md) is documented but is not an OpenAPI contract — it's
      frontend-internal, same category as any other hook's public shape.
- [x] **VIII — Visual truth.** Satisfied. No new visual value is introduced — every bubble, state,
      and copy string already exists and is reused verbatim; this feature only changes *where the
      data backing them lives*, never what's rendered or how it looks. Loading/empty/error/offline
      states for Recommend are unchanged (still `RecommendChat`'s existing branches); this feature
      adds no new visual state of its own.
- [x] **IX — One codebase.** Satisfied. The module singleton has no form-factor branching and no
      user-agent checks; identical behavior on web and installed PWA, at every viewport.
- [x] **X — Documents are data.** N/A. No document/corpus touched.

No violations. Complexity Tracking is not needed.

## Project Structure

### Documentation (this feature)

```text
specs/019-recommend-chat-persistence/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md         # Phase 1 output
├── contracts/
│   └── recommend-chat-store.md
└── tasks.md              # Phase 2 output (/speckit-tasks — not yet created)
```

### Source Code (repository root)

```text
frontend/
├── lib/
│   └── recommend/
│       ├── recommendChatStore.ts        # NEW — the module singleton + actions
│       └── recommendChatStore.test.ts   # NEW — store-level unit tests
├── components/
│   └── recommend/
│       ├── RecommendChat.tsx            # MODIFIED — thin view over the store
│       └── RecommendChat.test.tsx       # MODIFIED — beforeEach store.reset(); prop-shape updates
└── app/(app)/recommend/
    ├── page.tsx                          # MODIFIED — reads store directly, drops ref/callback
    └── page.test.tsx                     # MODIFIED — beforeEach store.reset()
```

No other path is touched. No backend, no `infra/`, no `design/`.

**Structure Decision**: the new store lives in `frontend/lib/recommend/`, matching the existing
convention for feature-scoped non-component logic in this codebase (`lib/recommend/
timeOfDayGreeting.ts`, `lib/calendar/useCalendarConnection.ts`, `lib/pwa/useServiceWorkerUpdate.ts`
— each a small file + colocated test, no subdirectory nesting beyond the feature name). No new
top-level directory, no restructure.

## Complexity Tracking

*No violations — table intentionally omitted per template instructions.*
