# Implementation Plan: Preference Memory

**Branch**: `004-preference-memory` | **Date**: 2026-07-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/004-preference-memory/spec.md`

## Summary

A signed-in user can react (liked/rejected, optional reason) to an outfit
suggestion from `/recommend`. Reactions persist in a new `suggestion_feedback`
Postgres table, storing the reacted-to outfit's item attributes (category,
colors, formality) as a snapshot at feedback time — not just item ids —
because rejected wardrobe items can later be edited or deleted and the
learned signal must still reflect what was actually rejected. There is no
separate materialized "preference profile" table: the profile is computed on
read by aggregating a user's `suggestion_feedback` rows with fixed
pattern-threshold rules (documented in research.md), matching the shape
`memory/store.py`'s in-memory `get_profile()` already returns. `set_preference`
and `get_profile` in `memory/store.py` swap their `InMemoryStore` backing for
Postgres queries; `profile_note(user_id)` keeps its exact signature and return
shape, so `pipeline/run.py` and `pipeline/generator.py` (the consumption side,
already wired) need zero changes. Four new endpoints — record a reaction,
view the derived profile, clear it entirely, remove one signal — reuse the
existing `get_current_user_id` JWT dependency and `get_session` DB dependency,
following the exact pattern of `/wardrobe/items`. Frontend adds a reaction
affordance to `SuggestionResult.tsx` and a new preferences view, regenerating
OpenAPI types per Principle VII.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript / Next.js 16 App Router (frontend) — both already locked, unchanged.

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0, Alembic, Pydantic (backend, all already in use); no new backend dependency. Frontend: existing Next.js app, no new dependency.

**Storage**: Postgres via Supabase (existing `DATABASE_URL`/`db.py` engine, pooler port 6543) — one new additive table, one new Alembic migration. No new storage technology.

**Testing**: pytest against the live Supabase DB via the existing rollback-transaction fixture (`backend/tests/conftest.py`), matching Feature 001/003's pattern. Deterministic profile-derivation logic gets unit tests (constitution Quality Bar: "deterministic logic requires unit tests").

**Target Platform**: Linux server (Railway, backend), Vercel (frontend) — unchanged, no new deploy surface.

**Project Type**: Web application (existing `backend/` + `frontend/` split).

**Performance Goals**: No stated numeric target; profile derivation is a read-time aggregation over one user's own feedback rows (solo/small-scale per FR/SC), not expected to need indexing beyond `user_id`.

**Constraints**: `profile_note(user_id)` signature and return shape MUST NOT change (zero-change requirement on `pipeline/run.py`/`generator.py`). A single feedback event MUST NOT swing the derived profile (FR-006) — pattern-threshold, not reactive-to-one-event.

**Scale/Scope**: 4 new endpoints, 1 new table, 1 migration, profile-derivation module, 1 frontend reaction affordance + 1 new preferences view.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Existing Pipeline Is Authoritative** — PASS. No retrieval/generation/eval-harness code is touched or rewritten. `memory/store.py`'s public functions (`profile_note`, `remember_interaction`, `recent_interactions`) keep their exact signatures; only `set_preference`/`get_profile`'s internal storage swaps backends.
- **II. Deterministic Core, LLM At The Edges** — PASS. Preference derivation (rejected colors, avoided categories, formality drift) is pure Python aggregation over structured `suggestion_feedback` rows (per spec.md's Assumptions) — no LLM interpretation of the free-text reason drives derivation.
- **III. Style Knowledge Gates Wardrobe Retrieval** — N/A. This feature doesn't touch retrieval ordering; it only adds a soft profile note the generator already consumes.
- **IV. Grounded Output Only** — PASS. A reaction's item_ids are looked up against the caller's own `wardrobe_items` (existing JWT-scoped query) before being snapshotted — a reaction can't reference items outside the wardrobe visible to that user's own auth context. No new invented items enter any suggestion.
- **V. Scoring Functions Are Eval Metrics** — N/A. This feature adds no outfit-quality scorer; profile derivation is a preference summary, not a quality metric, so it has no eval-harness counterpart to reuse.
- **VI. Schema Stability** — PASS. `suggestion_feedback` stores a *snapshot* of category/colors/formality using the exact existing vocab (category groups, six-value formality enum, hex colors) — no parallel taxonomy introduced.
- **VII. Single Source Of Truth For Contracts** — PASS. Four new Pydantic models define the new endpoints; frontend regenerates OpenAPI types after they land, matching Feature 003's precedent exactly.

No violations. Complexity Tracking table not needed.

## Project Structure

### Documentation (this feature)

```text
specs/004-preference-memory/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── preferences.md   # Phase 1 output
└── tasks.md              # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
backend/
├── alembic/versions/
│   └── 0003_add_suggestion_feedback.py   # new, additive-only
├── src/whattowear/
│   ├── models.py            # + SuggestionFeedbackRow
│   ├── schema.py            # + SuggestionFeedbackIn/Out, PreferenceProfile
│   ├── crud.py               # + record_feedback/get_feedback/delete_feedback ops
│   ├── memory/
│   │   ├── store.py          # set_preference/get_profile -> Postgres-backed;
│   │   │                     #   profile_note() signature unchanged
│   │   └── preferences.py    # NEW: derive_profile() -- pure aggregation over
│   │                         #   SuggestionFeedbackRow, the eval-testable unit
│   └── api.py                 # + 4 endpoints under /preferences
└── tests/
    ├── unit/
    │   └── test_preferences.py       # derive_profile() pure-function tests
    └── integration/
        └── test_preferences_api.py   # 4 endpoints, auth + isolation

frontend/
├── components/
│   ├── SuggestionResult.tsx   # + reaction affordance (like/reject/reason)
│   └── PreferencesView.tsx    # NEW
├── app/preferences/
│   └── page.tsx               # NEW route
└── lib/api-types.ts           # regenerated after backend lands (Principle VII)
```

**Structure Decision**: Existing `backend/` + `frontend/` split, unchanged.
No new top-level directory. New backend logic follows Feature 001/003's flat
module layout exactly (`models.py`/`schema.py`/`crud.py`/`api.py` each grow;
no new package except `memory/preferences.py`, justified because it's the one
piece of new *deterministic logic* this feature adds — the derivation
function — kept separate from `memory/store.py`'s storage-access role so the
pure function can be unit-tested without a DB session, matching how
`colors.py`/`categories.py` are separated from the storage/API layers today.

## Complexity Tracking

*No constitution violations — table not applicable.*
