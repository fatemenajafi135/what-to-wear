# Implementation Plan: Outfit suggestion pager

**Branch**: `009-suggestion-pager` | **Date**: 2026-08-02 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/009-suggestion-pager/spec.md`

## Summary

Stop discarding `SuggestResult.outfits[1:]`: the styling route returns every outfit that clears
the existing `< 0.4` floor (not just `outfits[0]`), and the frontend renders them as a horizontal
pager of cards inside the assistant bubble instead of 008's single flat item-thumbnail row —
including the single-outfit case, which now renders as a one-card, arrow-less pager rather than
008's bubble-plus-citations layout (design-decisions.md §35). This slice also adds the project's
first outfit-persistence: a minimal `outfits` table (RLS + GRANT, §32), a save/toggle-favorite
route pair, and wires the pager card's heart to it — the card's tap-through points at
`/outfits/:id`, a route 010 will build; a 404 there today is expected and correct. Feedback
(thumbs) stays pure component-local state (§5.3 of the handoff), never persisted, never touching
`memory/preferences.py`. The pager differs genuinely between mobile (CSS-transform slide,
arrow-only paging, no native swipe) and tablet/desktop (native `scroll-snap` track, ~92% card
width, arrows kept in sync via a `scroll` listener) — design-decisions.md has no open question
here, the design system's own § Outfit suggestion pager section is fully explicit.

## Technical Context

**Language/Version**: Python 3.12 (backend, `uv`), TypeScript / Next.js App Router (frontend) —
fixed by the constitution, no choice to make.

**Primary Dependencies**: FastAPI (existing `recommend.py` router, extended in place),
`pipeline.graph.get_compiled_graph` (unmodified, Principle I — this feature changes how many of
its already-produced `outfits` reach the response, never how it produces them), `sqlalchemy` +
raw `text()` (existing pattern in `supabase_closet.py`, mirrored for the new `SupabaseOutfitRepository`),
`openapi-fetch` (existing frontend API client), no new frontend dependency for the pager's
scroll-snap/CSS-transform mechanics — both are plain CSS + a `scroll` event listener, matching
the "no new abstraction without a measured need" Quality Bar.

**Storage**: Postgres via Supabase. One new table, `outfits` (migration `0009`, design-
decisions.md §32) — owned rows, RLS + GRANT following the `0002` pattern, proven by a two-user
isolation test mirroring `004`'s. No change to `wardrobe_items`, `catalog_items`, or any existing
table. Qdrant unchanged (still read-only, still only inside the pipeline's own retrieval nodes).

**Testing**: `pytest` (backend unit + integration — the readiness/pipeline-invocation test
pattern 008 established is reused; the new floor-filtering and outfit-persistence logic gets its
own unit tests; the two-user RLS+GRANT proof mirrors `tests/integration/test_closet_routes.py`'s
existing isolation test shape). Vitest + Testing Library (frontend) for the new pager components,
plus a mobile-vs-desktop behavioral test for the two paging mechanisms.

**Target Platform**: Linux server (Railway, backend), Vercel (frontend) — unchanged.

**Project Type**: Web application (existing Next.js + FastAPI split) — no new project type.

**Performance Goals**: Unchanged from 008 — no new user-facing latency target; the existing
120-second backstop timeout around the graph invocation is untouched (this feature does not add
a second pipeline call — the same single `invoke()` per request now yields a list instead of one
item pulled from it).

**Constraints**: No live LLM call in any test. No change to `pipeline/`, `scoring/`,
`retrieval/`, or `ports.py` (handoff §8, traps #1-2). Never render a numeric score or percentage
(FR-017). No citation marker on any pager card (FR-010, design-decisions.md §33). Any new table
gets RLS *and* a table-level GRANT, proven by a two-user test (handoff constraint). Feedback
(thumbs) never persisted, never wired to `memory/preferences.py` (FR-012).

**Scale/Scope**: One existing route file extended (`recommend.py`: `POST /recommend/messages`'s
response shape changes; two new routes — save and toggle-favorite an outfit), one new repository
(`SupabaseOutfitRepository`), one new migration (`0009`), roughly seven new frontend components
(pager card, pager track/controls, group-state wrapper, plus updates to `ChatMessageList`) and
one regenerated `schema.d.ts`.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **I — Salvaged AI code is authoritative.** No change to `pipeline/`, `retrieval/`,
      `scoring/`, `memory/`, or `ingest/`. The route still calls
      `pipeline.graph.get_compiled_graph(repo).invoke(...)` exactly as before and as the eval
      harness does — only how many of `result.outfits` are resolved and returned changes, which
      is route-layer post-processing, not pipeline behavior. No eval re-run required.
- [x] **II — Deterministic scoring.** Untouched. The route still only reads
      `ScoredOutfit.rank_score`/`.scores` the pipeline already computed; the `< 0.4` filter is
      the same existing `match_label`-returns-`None` convention applied per-outfit instead of
      only to `outfits[0]`, not a new judgement.
- [x] **III — Style gates wardrobe.** Untouched — lives entirely inside `pipeline/graph.py`.
- [x] **IV — Grounded output.** Every item on every card still resolves through
      `repository.list_wardrobe_items(user_id)` (existing pattern, now applied per outfit in the
      list instead of once). A saved outfit's `item_ids` are validated against the same
      ownership-scoped wardrobe read before insert — a save can never record an item the caller
      doesn't own.
- [x] **V — Scorers are eval metrics.** No new quality judgement — `match_label` per outfit is
      the same existing threshold mapping, run once per outfit instead of once total.
- [x] **VI — Schema stability.** No taxonomy change. The new `outfits` table stores
      `match_label` as the same three-value literal already returned today (never a new numeric
      scale — design-decisions.md §32 rejects storing the raw score expressly on these grounds).
- [x] **VII — Contracts.** `SendMessageResponse.outfits`, the new save/favorite route models, and
      `StylingOutfit.id` are Pydantic models the frontend consumes via a regenerated
      `schema.d.ts` (handoff trap #6) — no hand-maintained duplicate type.
- [x] **VIII — Visual truth.** Every value on the new pager traces to design-system.md § Outfit
      suggestion pager, § Badge, § Scores, or design-decisions.md §32-35 (this plan's own
      research). Loading (inline skeleton card, no arrows/indicator), Empty (`recommend`-style
      message + Add-item link), Error (existing `recommend.error.*` + retry), and offline
      (existing composer-disable path, untouched) states are all in scope for the pager group.
      44px hit areas on the heart/thumbs/arrows via the existing `IconButton` hit-area pattern; a
      real `:focus-visible` via existing tokens; arrows get `disabled` at the ends and are
      removed from tab order; `prefers-reduced-motion` gates the slide transform (FR-018). No
      code copied from `design/prototype/`.
- [x] **IX — One codebase.** No new route tree. The mobile-vs-desktop pager difference is a CSS
      breakpoint within the one `/recommend` route (matching the existing §5 breakpoint
      mechanism), not a second surface or user-agent branch.
- [x] **X — Documents are data.** No new document, no new corpus entry.

No violations. Complexity Tracking is empty.

## Project Structure

### Documentation (this feature)

```text
specs/009-suggestion-pager/
├── plan.md              # this file
├── research.md           # Phase 0 — persistence mechanics, citation contradiction, meta line, response-shape migration
├── data-model.md          # Phase 1 — outfits table, route-local models, frontend pager state
├── quickstart.md          # Phase 1 — end-to-end validation script
├── contracts/
│   └── recommend.md       # Phase 1 — changed + new endpoints
└── tasks.md               # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
frontend/
├── components/recommend/
│   ├── ChatMessageList.tsx / .module.css / .test.tsx   # outfit rendering delegates to SuggestionPager; citation-badge rendering stays only for the no-outfit reply_text path
│   ├── SuggestionPager.tsx            # new — group-state wrapper (Loading/Ready/Empty/Error), owns index state + the mobile/desktop mechanics split
│   ├── SuggestionPager.module.css
│   ├── SuggestionPager.test.tsx
│   ├── OutfitCard.tsx                 # new — header (title/pill/heart), plain-text description, ItemThumbnailRow (reused), meta line, feedback footer
│   ├── OutfitCard.module.css
│   ├── OutfitCard.test.tsx
│   ├── PagerControls.tsx              # new — prev/next buttons + "N of M", hidden at count===1
│   ├── PagerControls.module.css
│   ├── PagerControls.test.tsx
│   ├── ItemThumbnailRow.tsx            # unchanged — already wraps, already 56px, reused as-is per card
│   └── CitedRuleList.tsx               # unchanged — still used by the no-outfit-in-reply bubble path, never by OutfitCard
└── lib/api/schema.d.ts                 # regenerated after the backend response shape changes

backend/src/whattowear/
├── api/v1/routes/recommend.py          # SendMessageResponse.outfits: list[StylingOutfit]; new POST /recommend/outfits, POST /recommend/outfits/{id}/favorite
├── repositories/
│   └── supabase_outfits.py             # new — SupabaseOutfitRepository: create, toggle_favorite (mirrors supabase_closet.py's session/RLS pattern)
└── schema.py                            # no change — StylingOutfit/CitedRule stay route-local in recommend.py per closet.py precedent

infra/supabase/migrations/
└── 0009_outfits.sql                     # new table, RLS policy, GRANT (design-decisions.md §32)

backend/tests/
├── unit/test_recommend_routes.py        # extend — per-outfit floor filtering, response shape
├── integration/test_recommend_routes.py # extend — save/favorite routes, ownership validation
└── integration/test_outfits_isolation.py # new — two-user RLS+GRANT proof (mirrors closet's isolation test)
```

**Structure Decision**: Everything fits the fixed layout. `supabase_outfits.py` sits beside
`supabase_closet.py`/`supabase_calendar.py` in `repositories/` — same convention, no new
directory. No `ports.py` change: outfit persistence is route-layer CRUD the AI modules never
touch, so it doesn't belong behind the Protocol seam `ports.py` exists for.

## Complexity Tracking

No violations — table intentionally empty.
