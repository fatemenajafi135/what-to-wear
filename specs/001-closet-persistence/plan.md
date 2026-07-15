# Implementation Plan: Closet Persistence

**Branch**: `001-closet-persistence` | **Date**: 2026-07-15 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-closet-persistence/spec.md`

## Summary

Replace the JSON-fixture-backed wardrobe with a persistent, per-user closet in
Postgres (Supabase), plus a shared, read-only catalog users add items from.
`context_assembler.load_wardrobe()` switches from reading
`data/fixtures/wardrobe.json` to a Postgres query scoped to the requesting
user; every other stage of the existing pipeline (style retrieval, generation,
citation) is untouched. The eval harness is minimally rewired — its `run_case()`
passes a fixed eval-baseline `user_id` whose closet is seeded with the same 40
fixture items — so the golden-set no-regression gate now runs through the real
Postgres path. No Qdrant involvement for wardrobe items
in this feature — Qdrant (cloud-hosted) continues to serve only the style
knowledge base, unchanged. Auth is a FastAPI dependency that verifies the
Supabase JWT's signature locally (ES256 via the project's JWKS endpoint) and
extracts `user_id` from the `sub` claim; row-level security stays off.

## Technical Context

**Language/Version**: Python 3.12, `uv`

**Primary Dependencies**: FastAPI (existing), SQLAlchemy + Alembic (new),
`psycopg[binary]` (new, Postgres driver), `pyjwt[crypto]` (new — the `crypto`
extra is required for ES256/JWKS verification), existing `whattowear` package
(`schema.py`, `categories.py`, `pipeline/context_assembler.py`)

**Storage**: Postgres via Supabase, pooler connection (port 6543). Qdrant
(cloud-hosted) is unaffected — it continues to hold only the style-KB
collection; there is no Qdrant collection for wardrobe/closet items in this
feature.

**Testing**: `pytest` for new CRUD/model unit tests; the existing eval harness
(`backend/evals`, `artifacts/eval_runs`) re-run against a Postgres-seeded
closet to confirm no regression (spec FR-012 / SC-005).

**Target Platform**: Linux (local dev now; Railway deployment is feature 005).

**Project Type**: Web service — backend only, single project. Frontend stays
empty until design lands.

**Performance Goals**: Closet view returns in a single request for closets up
to 200 items (spec SC-001) — no dedicated latency target beyond that.

**Constraints**: No change to retrieval behavior or eval scores (spec FR-012).
Row-level security stays off — the FastAPI JWT dependency is the only access
boundary. Item taxonomy is frozen per constitution Principle VI.

**Scale/Scope**: Solo-project scale. Catalog seeded from
`data/fixtures/wardrobe.json` (40 items today).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Check | Result |
|---|---|---|
| I. Existing pipeline is authoritative | `context_assembler.load_wardrobe()`'s data source changes (file → Postgres query). The eval harness's `run_case()` is minimally rewired to pass a fixed eval-baseline `user_id` whose closet is seeded with the same 40 fixture items, so the golden-set gate exercises the new Postgres path and proves score-for-score equivalence (FR-012/SC-005). Retrieval strategies, KB, generator, and the harness's metrics/comparison logic are otherwise untouched. | PASS |
| II. Deterministic core, LLM at the edges | Not touched by this feature (no scoring/generation changes). | N/A |
| III. Style KB gates wardrobe retrieval | Ordering in `pipeline/run.py` is untouched. | PASS |
| IV. Grounded output only | Unaffected; catalog becomes a real, queryable entity, which strengthens this guarantee for later features. | PASS |
| V. Scoring functions are eval metrics | Not touched by this feature. | N/A |
| VI. Schema stability | `category`, `formality`, `warmth`, `season`, `colors` carry over unchanged. `fabric` (nullable) and `source` (defaulted `'catalog'`) are new, additive fields (see data-model.md / research.md) — not renames or removals of a frozen field. | PASS |
| VII. Single source of truth for contracts | `schema.py` Pydantic models remain the API contract; SQLAlchemy models are a persistence-layer mirror, not a second contract. | PASS |
| Quality Bar: simplicity | No repository-pattern abstraction — CRUD is direct functions over one concrete Postgres implementation (see Project Structure). No local `users` table — `user_id` is read directly from the verified JWT `sub` claim. | PASS |

No violations. Complexity Tracking table omitted (not needed).

## Project Structure

### Documentation (this feature)

```text
specs/001-closet-persistence/
├── plan.md              # this file
├── research.md          # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md         # Phase 1 output
├── contracts/
│   └── wardrobe-api.md    # Phase 1 output
└── tasks.md              # Phase 2 output (/speckit-tasks, not this command)
```

### Source Code (repository root)

```text
backend/
├── src/whattowear/
│   ├── db.py              # NEW: SQLAlchemy engine/session factory (Supabase pooler URL)
│   ├── models.py          # NEW: SQLAlchemy ORM: WardrobeItemRow, CatalogItemRow
│   ├── crud.py            # NEW: direct CRUD functions (list/add/update/delete), no repository interface
│   ├── auth.py            # NEW: FastAPI dependency verifying Supabase JWT signature (ES256 via JWKS) -> user_id
│   ├── schema.py           # MODIFIED: add optional `fabric` and `source` fields to WardrobeItem
│   ├── api.py               # MODIFIED: add /wardrobe/items and /catalog/items routes
│   └── pipeline/
│       └── context_assembler.py  # MODIFIED: load_wardrobe(user_id) reads Postgres, not the JSON fixture
├── src/whattowear/eval/
│   └── harness.py           # MODIFIED: run_case() passes EVAL_BASELINE_USER_ID so the gate reads the seeded closet
├── alembic/                # NEW: migrations
│   ├── env.py
│   └── versions/
│       └── 0001_initial_wardrobe_schema.py
├── alembic.ini             # NEW
└── data/fixtures/wardrobe.json   # UNCHANGED: becomes the one-time catalog seed source
```

**Structure Decision**: Single backend project, flat modules under
`src/whattowear/` — matching the existing convention (`kb.py`, `categories.py`,
`colors.py`, `config.py` are all flat top-level modules, not nested packages).
No new subpackage is introduced for this feature; that would be an
abstraction with only one concrete implementation today, which the
constitution's Quality Bar disallows.

## Complexity Tracking

*Not applicable — no Constitution Check violations.*
