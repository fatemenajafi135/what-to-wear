# Implementation Plan: Outfits gallery + detail

**Branch**: `feat/010-outfits` | **Date**: 2026-08-02 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/010-outfits/spec.md`

## Summary

Users browse saved outfits in a gallery (`/outfits`), sort them (date/favorited/most worn — no
filter facets this feature, see design-decisions.md §41), open one (`/outfits/:outfitId`) to see
every item, the styling explanation with inline citation badges and the numbered rule list behind
it, and a bars-only match breakdown — then manage it (log worn, rename, favorite, delete-with-
confirmation) from an overflow menu. Backend: extend the existing `recommend.py` router and
`SupabaseOutfitRepository` with list/get/delete/rename/log-worn, migration `0010` widens `outfits`
with citation/score columns captured server-side from the pipeline's own checkpointed thread state
at save time (never trusted from the client, never re-generated), and adds an `outfit_wears`
table. Frontend: two new routes mirroring `/closet`'s exact two-pane list+detail pattern, reusing
existing components (`TopHeader`, `IconButton`, `BottomSheet`, `ItemPhoto`, the bespoke delete-
confirm dialog) and resurrecting the pre-009 citation-badge rendering approach for Outfit detail
only. No change to `pipeline/`, `scoring/`, `retrieval/`, or `ports.py`.

## Technical Context

**Language/Version**: Python 3.12 (backend, `uv`), TypeScript / Next.js App Router (frontend) —
both already fixed by the constitution's Technology Constraints, nothing new introduced.

**Primary Dependencies**: FastAPI, SQLAlchemy (`core/db.py`), LangGraph (`get_compiled_graph(...).get_state(...)`
for the checkpointed `last_result` read, §38) — all already in use, no new dependency added.

**Storage**: Postgres via Supabase (migration `0010`, extending `outfits` + new `outfit_wears`
table). No Qdrant/vector involvement — this feature never queries the knowledge base.

**Testing**: `pytest` (backend unit + `tests/integration/*_rls.py` two-user isolation pattern),
Jest/RTL-equivalent for frontend component tests (matching existing `*.test.tsx` files) — both
already the project's testing stack.

**Target Platform**: Same PWA (Next.js, web + installed) at all three breakpoints (mobile/tablet/
desktop) and both browser-tab/standalone display modes — no new platform surface.

**Project Type**: Web application (existing `frontend/` + `backend/` split) — no new project.

**Performance Goals**: No feature-specific target beyond the project's existing web-app norms;
the gallery list and detail fetch are both single indexed-by-`user_id` queries, no pagination
required at this feature's expected data volume (a user's own saved outfits, not a shared table).

**Constraints**: Every constitution gate below; no numeric score/percentage ever rendered (§ II);
ownership checked in-query for both `outfits` reads/writes and the checkpointer read (§38), not
only via RLS, since the pooler role has BYPASSRLS.

**Scale/Scope**: 2 new frontend routes, ~6 new/changed backend routes on the existing router, 1
migration, 1 new DB table — a single mid-size feature slice, not a new subsystem.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **I — Salvaged AI code is authoritative.** No regeneration. This feature reads
      `GraphState.last_result` (already produced, already checkpointed by the existing graph) —
      it adds no new pipeline node, changes no scoring/retrieval logic, and calls no LLM. No eval
      re-run needed; verified by diff scope (no touch to `pipeline/`, `scoring/`, `retrieval/`,
      `eval/`) — stated as an explicit check to run before merge, not assumed.
- [x] **II — Deterministic scoring.** Unchanged — `dimension_scores` persisted here is a verbatim
      copy of `ScoredOutfit.scores` (already pure-Python, already computed before this feature
      exists), never recomputed. The route is a read-and-store step, not a new scorer. Bars/label
      only on every render surface (data-model.md + contracts enforce no float ever serialized as
      display text — the float travels in the API payload for bar-width math, per §38's explicit
      distinction between transmitting and rendering).
- [x] **III — Style gates wardrobe.** N/A — this feature runs no retrieval of any kind; it only
      reads back what a prior request's retrieval already produced and stored.
- [x] **IV — Grounded output.** Every item shown on Outfit detail is re-resolved from
      `wardrobe_items` by id at read time (mirrors `_resolve_outfit`'s existing "resolve live,
      don't cache" convention, design-decisions.md §24) — an item the user later removes from
      their closet simply drops out of the render, never shown as a stale/broken reference.
      Citations captured are exactly what the pipeline itself cited (§38) or honestly empty,
      never fabricated. Ownership checked in the repository query for every read/write
      (`WHERE user_id = ...`, matching `supabase_outfits.py`'s existing convention) AND on the
      checkpointer read (§38's own ownership check on `state["user_id"]`) — not left to RLS alone.
- [x] **V — Scorers are eval metrics.** N/A — no new scoring function of any kind is introduced;
      `dimension_scores` is stored data, not a judgment computed here.
- [x] **VI — Schema stability.** No taxonomy change. `match_label`'s existing three-value enum is
      untouched; no parallel numeric formality/score scale is added (dimension_scores stores the
      already-existing `SCORE_DIMENSIONS` shape verbatim, not a new scale).
- [x] **VII — Contracts.** New/changed routes are Pydantic response models on the FastAPI side;
      `frontend/lib/api/schema.d.ts` is regenerated from the running backend once routes land
      (task in tasks.md), never hand-edited. No duplicate type definitions.
- [x] **VIII — Visual truth.** Every token, spacing, radius and copy string below comes from
      `design/design-system.md` § Outfit detail / § Outfits (gallery) / § Scores / § Badge, or
      `docs/design-decisions.md` §38-41 where the design system is silent (citation persistence
      shape, wear semantics, delete confirmation, filter deferral). No code copied from
      `design/prototype/`. All four states (loading/error/empty/empty-filtered-N/A-since-no-
      filters/offline) implemented per screen — see data-model.md's per-screen state table.
      WCAG AA: 44px hit areas on every icon control (reusing `IconButton`'s existing pseudo-
      element), real `:focus-visible` (existing component CSS, unchanged), one `<h1>` per screen
      (`TopHeader`'s existing pattern), focus moved to the new screen's heading on navigation,
      focus trapped/restored in the outfit-menu `BottomSheet` and delete dialog (reusing
      `useModalDialog`, the same hook Item detail's own overlays already use),
      `prefers-reduced-motion` honoured (inherited from shared CSS, no new animation introduced).
- [x] **IX — One codebase.** `/outfits` and `/outfits/:outfitId` are ordinary App Router routes,
      identical at every form factor; only the two-pane arrangement changes at desktop (media
      query, mirroring `/closet`'s existing mechanism exactly — no user-agent branching, no
      second route tree).
- [x] **X — Documents are data.** N/A — no corpus/document involvement anywhere in this feature.

No Complexity Tracking entries — no gate is violated.

## Project Structure

### Documentation (this feature)

```text
specs/010-outfits/
├── plan.md              # this file
├── research.md          # Phase 0 output — summarizes design-decisions.md §38-41
├── data-model.md         # Phase 1 output
├── contracts/            # Phase 1 output — recommend-outfits.md (REST contract)
├── quickstart.md         # Phase 1 output
└── tasks.md              # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
frontend/
├── app/(app)/outfits/
│   ├── page.tsx                    # CHANGED — real gallery, replaces the stub
│   ├── page.module.css             # CHANGED — twoPane/gridPane/detailPane, mirrors closet's
│   ├── OutfitsGrid.tsx              # NEW — the shared list component (closet's ClosetGrid analog)
│   ├── OutfitsGrid.module.css       # NEW
│   ├── SortSheet.tsx                # NEW — sort-only BottomSheet trigger (§41: no filter facets)
│   └── [outfitId]/
│       ├── page.tsx                 # NEW — detail screen
│       ├── page.module.css          # NEW
│       ├── OutfitOverflowSheet.tsx  # NEW — mirrors ItemOverflowSheet.tsx exactly
│       ├── DeleteOutfitDialog.tsx   # NEW — mirrors DeleteConfirmDialog.tsx exactly
│       ├── DeleteOutfitDialog.module.css
│       ├── RationaleWithCitations.tsx      # NEW — resurrects renderWithCitations/CITATION_TOKEN
│       ├── CitedRuleList.tsx        # NEW — resurrected from git history (c545533), adapted
│       ├── CitedRuleList.module.css
│       └── MatchBreakdown.tsx       # NEW — label + per-dimension bars, no numbers ever
├── components/recommend/
│   └── SuggestionPager.tsx          # CHANGED — thread `threadId` through to the save call (§38)
│   └── ChatMessageList.tsx          # CHANGED — thread `threadId` prop down to SuggestionPager
│   └── RecommendChat.tsx            # CHANGED — pass its existing `threadId` state down
└── lib/api/schema.d.ts              # REGENERATED, not hand-edited

backend/
├── src/whattowear/
│   ├── api/v1/routes/recommend.py   # CHANGED — new routes + thread_id on save_outfit
│   └── repositories/supabase_outfits.py  # CHANGED — list/get/delete/rename/log_worn added
└── tests/
    ├── unit/test_supabase_outfits_repository.py   # CHANGED — new method coverage
    ├── integration/test_recommend_routes.py        # CHANGED — new route coverage
    ├── integration/test_outfits_rls.py              # CHANGED — outfit_wears + new columns
    └── integration/test_outfit_wears_rls.py         # NEW — mirrors TestItemWearsRLS

infra/supabase/migrations/
└── 0010_outfits_detail.sql          # NEW — see data-model.md
```

**Structure Decision**: extends the existing `recommend.py` router and `SupabaseOutfitRepository`
rather than adding a second router/repository (handoff §4.1: "extend the existing router rather
than adding a second one"). Frontend mirrors `/closet`'s established two-pane file layout exactly
— no new architectural pattern introduced. All paths are within the fixed `frontend/`/`backend/`/
`infra/` layout; nothing falls outside it, so no Complexity Tracking entry is needed for structure.

## Complexity Tracking

*No entries — no Constitution Check gate is violated by this plan.*
