# Implementation Plan: Calendar Pick Reaches Recommend

**Branch**: `feat/020-calendar-pick-to-recommend` | **Date**: 2026-08-11 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/020-calendar-pick-to-recommend/spec.md`

## Summary

Three linked defects (GitHub issue #41), fixed together because each hides the next: (1)
`handlePick` on the Calendar screen never navigates after a successful save, and discards the
save's own result, so a failed save is indistinguishable from a successful one; (2)
`RecommendCalendarContext` fetches the picked event once on mount, and Next's Router Cache
serving `/recommend` without a remount on in-app navigation means the label can be stale for
minutes; (3) `recommend.py` never reads the picked event at all, so picking one has no effect
on the styling conversation. The fix for (3) — which slots a picked event may fill, and how —
is decided in `docs/design-decisions.md` §61 before this plan: `location` is silently seeded
into the conversation's slot state as a reliable fact; the event's title/time are offered back
as editable, unsent Composer text, never asserted as occasion/formality fact.

## Technical Context

**Language/Version**: TypeScript (frontend, Next.js App Router), Python 3.12 (backend, `uv`)

**Primary Dependencies**: Next.js, React (`useSyncExternalStore`), `openapi-fetch` generated
client; FastAPI, LangGraph (`get_compiled_graph`, `graph.update_state`), SQLAlchemy (existing
`SupabaseCalendarRepository`)

**Storage**: Supabase Postgres — no schema change. Reads the existing `picked_events` table
(migration `0004`, unchanged) through the existing `SupabaseCalendarRepository`. Writes only
to the existing LangGraph checkpoint (`thread_id`-keyed conversation state), no new table.

**Testing**: `pytest` (backend unit/integration, mocked LLM/gateway per constitution's "no
live LLM calls in CI"), Vitest + Testing Library (frontend unit/component), Playwright
(`npm run e2e:pwa`)

**Target Platform**: Web + installed PWA, single Next.js codebase (Principle IX) — no new
platform surface

**Project Type**: Web application (fixed frontend/ + backend/ layout, Principle IX/Technology
Constraints — no structure decision to make)

**Performance Goals**: No new perf budget — this is UI wiring plus one additional repository
read and one additional (already-cheap) LangGraph checkpoint write per new thread; no new
network round trip is added to the hot path (defect 2's fix removes a round trip rather than
adding one, by writing through from the pick's own PUT response instead of a fresh GET).

**Constraints**: Constitution I — `pipeline/`, `scoring/`, `retrieval/` untouched, no eval run
required. Constitution IV — no title-derived formality presented as fact. Constitution VI — no
taxonomy/schema change. Constitution VIII — no new chat-surface copy or component; reuses
`Banner` (error variant, already built) and the existing `Composer` input.

**Scale/Scope**: 3 frontend files changed/added (`calendar/page.tsx`,
`RecommendCalendarContext.tsx`, a new `lib/calendar/pickedEventStore.ts`), `Composer.tsx` gains
one optional prop, `HeroState`/`RecommendChat` wire the pre-fill through; 1 backend route file
changed (`recommend.py`), no new backend module. `frontend/lib/api/schema.d.ts` does **not**
need regeneration — no request/response shape changes (§ Structure Decision explains why).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **I — Salvaged AI code is authoritative.** No changes to `retrieval/`, `chunking`,
      `ingest/`, the knowledge base, `scoring/`, the LangGraph pipeline module, or the eval
      harness. `recommend.py` (a route, not pipeline code) gains one more repository
      dependency and one more `graph.update_state(...)` call — the same public method
      `/recommend/turns` already calls after every turn's extraction. No eval run required.
- [x] **II — Deterministic scoring.** N/A — no scoring code touched. The one new piece of
      "judgement" this feature adds (seeding `location`) is a straight field copy from a
      database row, not a score or a guard.
- [x] **III — Style gates wardrobe.** N/A — no retrieval ordering touched.
- [x] **IV — Grounded output.** Directly engaged, and this is the plan's central gate: no
      occasion/formality is derived from the picked event's title and presented as fact
      (§61). `location` is treated as grounded user data (literally the address on the
      user's own calendar entry), the same trust level already given to a location the user
      types mid-conversation.
- [x] **V — Scorers are eval metrics.** N/A.
- [x] **VI — Schema stability.** No taxonomy change. `GraphState`/`Context` gain no new
      field — `location` already exists on both; this feature only adds one more code path
      that populates it.
- [x] **VII — Contracts.** No backend request/response shape changes (see Structure Decision)
      — `schema.d.ts` stays untouched, so there is nothing to regenerate and nothing that
      could drift.
- [x] **VIII — Visual truth.** No new component. `Banner` (existing, `error` variant) surfaces
      a failed pick save. `Composer`'s existing `<input>` gains an optional pre-filled initial
      value — a data behavior, not a new visual element. The hero's specified "row of 3
      suggestion chips" is unchanged (§61 explicitly rejects a 4th chip). The calendar row
      dimming (§"Connected, has events") is unchanged, per the task's own instruction not to
      "fix" it. Loading/empty/error states: the Calendar screen already has all four
      (unaffected by this change) and gains one more — the pick-save error, using the
      existing `Banner` pattern. WCAG: rows keep their existing 44px hit areas; the new Banner
      inherits `role="status" aria-live="polite"` from the component itself.
- [x] **IX — One codebase.** No platform-specific branching added.
- [x] **X — Documents are data.** N/A — no corpus/document change.

No Complexity Tracking entries — every gate passes without a justified violation.

## Project Structure

### Documentation (this feature)

```text
specs/020-calendar-pick-to-recommend/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md         # Phase 1 output
├── contracts/             # Phase 1 output
└── tasks.md               # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
frontend/
├── app/(app)/calendar/
│   ├── page.tsx                              # CHANGED — handlePick: check PUT result,
│   │                                          # navigate on success, rollback/error on failure
│   └── page.test.tsx                         # CHANGED — new pick-flow test cases
├── components/calendar/
│   ├── RecommendCalendarContext.tsx           # CHANGED — reads pickedEventStore via
│   │                                          # useSyncExternalStore instead of its own fetch
│   └── RecommendCalendarContext.test.tsx      # CHANGED — store-driven test cases
├── lib/calendar/
│   ├── pickedEventStore.ts                    # NEW — write-through module-level store,
│   │                                          # same useSyncExternalStore idiom as
│   │                                          # lib/recommend/recommendChatStore.ts
│   └── pickedEventStore.test.ts                # NEW
├── components/recommend/
│   ├── Composer.tsx                            # CHANGED — optional `initialValue` prop
│   ├── RecommendChat.tsx                       # CHANGED — passes the composer pre-fill
│   │                                          # through when the thread is fresh
│   └── *.test.tsx                              # CHANGED where behavior is covered
└── lib/recommend/
    └── recommendChatStore.ts                   # UNCHANGED — read for precedent only

backend/
├── src/whattowear/api/v1/routes/
│   └── recommend.py                            # CHANGED — send_turn reads the caller's
│                                                # picked event on a brand-new thread and
│                                                # seeds `location` before the first
│                                                # conversational reply
└── tests/
    └── unit/ or integration/ (existing dirs)   # CHANGED/NEW — coverage for the seed

docs/
└── design-decisions.md                          # ALREADY CHANGED (§61, committed before plan)
```

**Structure Decision**: All changes fit the existing fixed layout — no new directory. The
backend route (`recommend.py`) already depends on `SupabaseClosetRepository` and
`SupabaseSessionRepository` via FastAPI `Depends`; this feature adds one more,
`SupabaseCalendarRepository` (already built by feature 012, `_get_calendar_repository()`
mirrors the route's existing `_get_repository()`/`_get_session_repository()` pattern —
no new module). **No OpenAPI contract change**: `PickedEventView`/`CalendarEventView`
(already in `calendar.py`) are unchanged; `SendTurnRequest`/`SendTurnResponse` gain no new
field — the picked event is read server-side from the authenticated user's own row, not
passed in the request body, so `frontend/lib/api/schema.d.ts` needs no regeneration.

## Complexity Tracking

*No entries — see Constitution Check above.*
