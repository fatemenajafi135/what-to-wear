# Legacy AI inventory

Phase 3 of the rebuild. A read-only survey of `../app-legacy` (branch `main`, still live).
Nothing in the legacy checkout was modified, moved, or deleted.

**Purpose:** decide what carries into the rebuild. The `Decision` column is deliberately
blank — marking each row keep / adapt / drop is a product call, not a model call. The
`Suggested` column is a recommendation only; override it freely.

**Scope surveyed:** `backend/src/whattowear/` (53 files, 6,044 lines), `backend/tests/`,
`backend/evals/`, `backend/scripts/`, `backend/data/`, `backend/alembic/`,
`docs/eval-baselines/`, `specs/`, `.specify/memory/constitution.md`.

---

## 1. Headline findings

1. **The code is in far better shape than the runbook assumed.** The runbook says the AI
   code "is mixed into the API and DB layers, so it cannot simply be copied." That is only
   half true — see §3. FastAPI appears in exactly two files. Every module carries a real
   docstring explaining *why*, not just *what*, and most cite the spec or constitution
   principle that produced them.
2. **Only 5 inline prompts exist**, all as named module constants (§4). Extracting them to
   `prompts/` is a small, mechanical change, not a rewrite.
3. **The book-licensing question is already answered, and answered well** (§5). The KB
   manifest sets an explicit legal policy and applies it per file: public-domain texts
   (Chevreul, Munsell) are ingested normally; copyrighted books are `ingest: false`,
   reference-only, never stored or embedded, with only distilled cards in the project's
   own words entering the index. Just one of the three present books is copyrighted. The
   policy was sound; only the *storage* practice — committing 48 MB of books to git — was
   wrong.
4. **A legacy constitution exists with 7 numbered principles**, and the code cites them
   inline throughout (§8). This is the single most valuable artifact for Phase 4.
5. **Real eval discipline already exists** — recorded baselines across three iterations,
   with written comparisons (§7).
6. **Two genuine architectural smells** worth fixing during the port, both in §3:
   production code importing the eval package, and AI modules importing the DB session
   factory at module import time.

---

## 2. Module inventory

`Refs` = how many times the module is referenced across `src`, `tests`, `evals`, `scripts`.
`UNREF` means no other module imports it; all four such modules are CLI entry points with a
`__main__` guard, so none are dead code.

### Web / persistence layer

| Module | Lines | Refs | What it does | Suggested | Decision |
|---|---:|---:|---|---|---|
| `api.py` | 439 | 13 | Every FastAPI route in the app | drop — rewrite as `api/v1/routes/` | |
| `auth.py` | 70 | 13 | Verifies a Supabase JWT signature locally | adapt → `core/security.py` | |
| `db.py` | 45 | 13 | SQLAlchemy engine/session factory, Supavisor pooler workarounds | adapt → `core/db.py` | |
| `crud.py` | 420 | 13 | All database access | adapt → `repositories/` | |
| `models.py` | 114 | 14 | SQLAlchemy ORM models | adapt → `models/` | |
| `storage.py` | 47 | 4 | Supabase Storage upload for item photos | adapt → `adapters/` | |

### Shared core

| Module | Lines | Refs | What it does | Suggested | Decision |
|---|---:|---:|---|---|---|
| `schema.py` | 323 | **51** | Shared data contracts — the spine of the whole system | **keep** | |
| `colors.py` | 179 | 8 | Color model; hex is source of truth, names derived | **keep** | |
| `categories.py` | 109 | 8 | Garment taxonomy and slot grouping | **keep** | |
| `config.py` | 104 | 10 | Single LLM-gateway config (litellm + LangChain) | adapt → `core/config.py` | |
| `logging_utils.py` | 26 | 6 | Verbose ingestion logging | adapt → `core/logging.py` | |
| `kb.py` | 63 | 5 | Process-wide knowledge-base singleton | adapt (see §3) | |
| `vision.py` | 103 | 3 | Photo → garment attributes, one VLM call | **keep** | |

### `pipeline/` — LangGraph styling pipeline

| Module | Lines | Refs | What it does | Suggested | Decision |
|---|---:|---:|---|---|---|
| `graph.py` | **526** | 11 | The `StateGraph`. Largest and most central module | **keep** (see §3) | |
| `engine.py` | 189 | 6 | Deterministic enumerate + score, Feature 010 | **keep** | |
| `generator.py` | 106 | 13 | Stage 4, grounded generation | **keep** | |
| `context_assembler.py` | 143 | 6 | Stage 1, gathers inputs + weather | **keep** (see §3) | |
| `cache.py` | 155 | 3 | Per-user suggestion cache | **keep** | |
| `cite.py` | 80 | 5 | Stage 5, maps `rule_id` back to source | **keep** | |
| `validity.py` | 59 | 3 | Deterministic outfit-coherence guards | **keep** | |
| `query_builder.py` | 48 | 2 | Stage 2, query builder + router | **keep** | |
| `grounding.py` | 26 | 2 | Guardrail: every item must be genuinely owned | **keep** | |

### `retrieval/`

| Module | Lines | Refs | What it does | Suggested | Decision |
|---|---:|---:|---|---|---|
| `base.py` | 24 | 11 | The `Retriever` protocol | **keep** → basis for `ports.py` | |
| `hybrid.py` | 157 | 3 | Per-layer hybrid retrieval | **keep** | |
| `advanced.py` | 46 | 2 | Hybrid + Cohere rerank on L3 | **keep** | |
| `baseline.py` | 32 | 1 | Naive dense over all chunks | keep — it is the A/B control (Q5) | |

### `scoring/` — deterministic, no LLM

| Module | Lines | Refs | What it does | Suggested | Decision |
|---|---:|---:|---|---|---|
| `__init__.py` | 45 | 2 | `rank_outfits` across all four dimensions | **keep** | |
| `color_harmony.py` | 162 | 2 | Color-theory harmony scorer (rewritten in 009) | **keep** | |
| `combine.py` | 49 | 2 | Swappable score-combination strategy | **keep** | |
| `weather_fitness.py` | 69 | 2 | Warmth vs. conditions | **keep** (see §3) | |
| `silhouette_balance.py` | 62 | 2 | Proportion principles | **keep** | |
| `formality_coherence.py` | 36 | 2 | Formality spread across an outfit | **keep** | |

### `memory/`

| Module | Lines | Refs | What it does | Suggested | Decision |
|---|---:|---:|---|---|---|
| `store.py` | 156 | 3 | LangGraph checkpointer + profile projection | adapt (see §3) | |
| `preferences.py` | 134 | 6 | Preference derivation — pure, no DB | **keep** | |

### `external/`

| Module | Lines | Refs | What it does | Suggested | Decision |
|---|---:|---:|---|---|---|
| `weather.py` | 82 | 3 | Open-Meteo geocode + forecast, no API key | **keep** → `adapters/` | |
| `trends.py` | 96 | 1 | Tavily trend search + LLM distillation | **keep** → `adapters/` | |

### `ingest/`

| Module | Lines | Refs | What it does | Suggested | Decision |
|---|---:|---:|---|---|---|
| `build_kb.py` | 299 | 3 | Manifest-driven KB build → Qdrant | adapt — must honour the new corpus rules | |
| `chunkers.py` | 192 | 1 | Pluggable chunker registry (atomic/section/token/semantic) | **keep** | |
| `loaders.py` | 176 | 6 | Per-source-type loaders → LangChain `Document`s | **keep** | |
| `wiki_refine.py` | 202 | UNREF | CLI: Wikipedia HTML → clean Markdown | keep as a tool, outside the service | |

### `eval/`

| Module | Lines | Refs | What it does | Suggested | Decision |
|---|---:|---:|---|---|---|
| `harness.py` | 239 | UNREF | CLI: runs the graph over the golden set | **keep** | |
| `properties.py` | 75 | 4 | Verifiable outfit-property checks, pure | **keep** but relocate (§3) | |
| `judge.py` | 50 | 4 | Optional LLM quality judgment, reported-only | **keep** | |
| `golden_set.py` | 30 | 2 | Loads the golden set | **keep** | |
| `test_users.py` | 181 | UNREF | Hand-built personas with constrained wardrobes | **keep** | |
| `vision_harness.py` | 76 | UNREF | Golden-case check for photo → attributes | **keep** | |

### Outside `src/`

| Path | What it is | Suggested | Decision |
|---|---|---|---|
| `tests/unit/` (24 files) | Mirrors the package; covers scoring, pipeline, retrieval, colors, crud | **keep** | |
| `tests/integration/` (16 files) | Route-level tests: suggest, wardrobe, preferences, cache, grounding | adapt with the routes | |
| `backend/evals/` | A **second** eval setup with its own `pyproject.toml` (`common.py`, `judge.py`, `score_ragas.py`) | unclear — see Q4 | |
| `backend/scripts/warmth_floor_evidence.py` | One-off evidence script for the 007 warmth-floor fix | drop — its finding is in the spec | |
| `backend/alembic/` (4 migrations) | Full schema: 4 tables | drop — superseded by Supabase migrations | |

---

## 3. Coupling — what blocks a clean lift

**Correction to an earlier assumption.** The AI modules are decoupled from *FastAPI*, but
not from the *database*.

- **FastAPI:** confined to `api.py` and `auth.py`. No AI module imports it. ✅
- **Database:** three AI modules import the session factory directly:

  | Site | Import |
  |---|---|
  | `pipeline/graph.py:46` | `from ..db import SessionLocal` — module level |
  | `memory/store.py:39` | `from ..db import SessionLocal` — module level |
  | `pipeline/context_assembler.py:90` | `from ..db import SessionLocal` — function level |

  This matters because `db.py` calls `create_engine()` **at import time** and raises if
  `DATABASE_URL` is unset. So importing `pipeline.graph` — to run an eval, or a unit test —
  requires a configured database that the eval does not otherwise need. This is precisely
  what `ports.py` fixes: define a `ClosetRepository` / `CheckpointStore` Protocol, inject
  the concrete implementation, and the pipeline becomes importable and testable standalone.
  Two of the three are already single-line lifts.

- **Dependency inversion — production imports the eval package:**

  | Site | Import |
  |---|---|
  | `pipeline/graph.py` | `from ..eval.properties import …` |
  | `scoring/weather_fitness.py` | `from ..eval.properties import …` |

  `eval/properties.py` holds pure outfit-property predicates used by *both* production
  scoring and the eval harness. The direction is backwards: evals should depend on the
  domain, never the reverse. Fix by moving it to `scoring/properties.py` (or a `domain/`
  module) and having `eval/` import from there. No logic changes.

Everything else in `pipeline/`, `retrieval/`, `scoring/`, `memory/preferences.py` and
`external/` is already framework-free.

---

## 4. Inline prompt census

Five prompts, all named module-level constants — none buried in f-strings mid-function.
Each becomes a file under `prompts/`, loaded by name.

| Prompt | Location | Size | Role |
|---|---|---:|---|
| `SYSTEM_PROMPT` | `pipeline/generator.py:40` | 1244 ch | Stylist; assembles outfits strictly from inventory |
| `SYSTEM_PROMPT` | `vision.py:23` | 832 ch | Garment attribute extractor (VLM) |
| `_ENGINE_SYSTEM_PROMPT` | `pipeline/engine.py:93` | 832 ch | Stylist selecting from a pre-scored shortlist |
| `_DISTILL_PROMPT` | `external/trends.py:23` | 379 ch | Distils web results into one factual trend card |
| `_PROMPT` | `eval/judge.py:20` | 351 ch | Fashion-styling judge (reported-only) |

Recommended: `prompts/<name>.md` with YAML front-matter carrying a version, and every eval
row recording the prompt version and model that produced it — so a quality change can be
attributed to a prompt edit rather than guessed at.

---

## 5. `backend/data/` classification

Per the decision that no corpus lives in the repo: local working copy at `../w2w-corpus/`
(outside the repo), canonical copy in Supabase Storage, described by `infra/corpus.yaml`.

| Path | Size | License / status | Ingested? | Destination |
|---|---:|---|---|---|
| `books/…Curated Closet (Rees, 2016).epub` | 44.6 MB | **copyrighted** | **no** | local only — never upload (Q3) |
| `books/The laws of contrast of colour.epub` (Chevreul) | 2.1 MB | **PD** | **yes** | Supabase Storage |
| `books/A Color Notation (Munsell).epub` | 1.9 MB | **PD** | **yes** | Supabase Storage |
| *(manifest also lists `Dressing the Man` (Flusser), copyrighted, `ingest: false` — **file is absent** from `data/books/`)* | — | copyrighted | no | n/a |
| `wikipedia/` (6 files) | 162 KB | CC-BY-SA, refined `.md` | yes | Supabase Storage |
| `kb/l1_rules.jsonl` | 5.0 KB | own / distilled | yes | Supabase Storage (Q1) |
| `kb/l3_trend_cards.jsonl` | 3.7 KB | own / distilled | yes | Supabase Storage (Q1) |
| `kb/l4_dresscodes.jsonl` | 7.1 KB | own / distilled | yes | Supabase Storage (Q1) |
| `kb/manifest.yaml` | 7.5 KB | the source registry itself | n/a | **tracked** → `infra/corpus.yaml` (Q1) |
| `kb/cache/…txt` | 12 KB | build cache | n/a | discard — regenerable |
| `golden_set.yaml` | 9.9 KB | eval dataset | n/a | **tracked** (Q2) |
| `fixtures/wardrobe.json` | 8.1 KB | test fixture | n/a | **tracked** → `evals/fixtures/` (Q2) |

**The licensing policy already in place, quoted from `kb/manifest.yaml`:**

> Legal policy: PD + CC-BY-SA + own + API data are ingestable. Copyrighted books are
> REFERENCE-ONLY: a human/LLM distills rules in our own words into jsonl cards; the book
> text itself is never stored → `ingest: false` on the book, `ingest: true` on the
> distilled card file.

This is a defensible position and it is already enforced per-file in the manifest. Of the
three books actually present, **two are public domain and legitimately ingested**
(Chevreul 1854, Munsell 1905 — both foundational colour-theory texts feeding layer L1);
only *The Curated Closet* (Rees, 2016) is copyrighted, and it is correctly marked
`ingest: false`, used solely as human research input that distilled cards were written
from. The only defect was committing all of them to git.

The manifest also tracks a `status: want-later` set (Black tie, Cocktail attire,
Semi-formal wear) — logged but not ingested. Worth carrying forward as a backlog.

---

## 6. What the legacy stack actually is

Useful for the constitution, since these are load-bearing choices:

- **Orchestration:** LangGraph `StateGraph` (`pipeline/graph.py`)
- **LLM access:** litellm + LangChain, routed through a **Vercel AI Gateway**; one config
  layer (`config.py`) for every model and embedding call
- **Vector store:** Qdrant
- **Rerank:** Cohere (L3 only, `retrieval/advanced.py`)
- **Web search:** Tavily (trend cards)
- **Weather:** Open-Meteo (no key)
- **Database:** Postgres via SQLAlchemy through the Supabase transaction pooler
- **KB layers:** L1 static rules · L3 trend cards · L4 dress codes

---

## 7. Eval assets

`docs/eval-baselines/` — three recorded iterations, each with the raw `.jsonl` and a
written comparison:

| Iteration | Files | What it captures |
|---|---|---|
| `pre-009/` | baseline, hybrid, advanced + `COMPARISON.md`, `NOTES.md` | Retriever A/B before the scoring fixes |
| `post-009/` | baseline, hybrid, advanced | Same three retrievers after the 009 fixes |
| `010-engine/` | advanced-grounded, advanced-engine + `COMPARISON.md`, `NOTES.md` | Grounded vs. deterministic-engine selection |

This is the "prove the refactor didn't regress" gate Phase 5 asks for, and it already
exists. Carry all of it over verbatim — it is worthless if regenerated.

---

## 8. The legacy constitution

`.specify/memory/constitution.md` defines 7 principles, cited inline across the code
(`crud.py`, `grounding.py`, `validity.py`, `engine.py`, `vision.py`, `schema.py`,
`eval/vision_harness.py`):

| | Principle |
|---|---|
| I | Existing Pipeline Is Authoritative |
| II | Deterministic Core, LLM At The Edges |
| III | Style Knowledge Gates Wardrobe Retrieval |
| IV | Grounded Output Only |
| V | Scoring Functions Are Eval Metrics |
| VI | Schema Stability |
| VII | Single Source Of Truth For Contracts |

Principles II and IV are the ones the code enforces most actively — deterministic scoring
with the LLM only selecting and writing, and every surfaced item provably owned. **These
should be inherited near-verbatim by the rebuild's constitution**, alongside the new
frontend and PWA principles.

---

## 9. The ten legacy specs

Recommend carrying all ten into `docs/legacy-specs/` as reference. They are the recorded
"why" behind the current behaviour, and several record decisions the rebuild must honour.

| # | Feature | Decision the rebuild must honour |
|---|---|---|
| 001 | Closet persistence | Closet is per-user, private, editable; retrieval reads the persisted closet, not a fixture |
| 002 | Styling agent | 3–5 outfits with rationale; **four score dimensions computed by code, never by an LLM**; conversational refinement without restating |
| 003 | MVP app | Photo → attribute extraction with user review before save; six-value formality scale; `pattern` and `fit` attributes |
| 004 | Preference memory | Reactions derive preferences over time; user can view, correct and clear them; survives restart |
| 005 | Production hardening | Per-user suggestion cache; output-grounding guardrail |
| 006 | Wardrobe item photos | Per-item photo card |
| 007 | AI improvements | L1/L3 retrieval restructure; refinement warmth-floor fix |
| 008 | Bulk upload | Photo management expansion. **Note:** spec directory only — developed on the `006` branch, not its own |
| 009 | Scoring fixes | Four real correctness bugs: inverted color-harmony scorer, ranking default, unsorted per-slot cap, missing color names |
| 010 | Engine approach | Deterministic enumerate + score; LLM selects-and-writes from a pre-scored top-K only. **Opt-in, never made default** |

---

## 10. Open questions

Answers needed before the constitution is written.

| # | Question | Recommendation |
|---|---|---|
| Q1 | You said all of `data/` goes to Supabase. But `kb/manifest.yaml` is the reproducibility contract — the rules doc requires the manifest to be **tracked**. Confirm it stays in git as `infra/corpus.yaml` while the `.jsonl` cards it points at move to Storage? | Yes — manifest tracked, contents in Storage |
| Q2 | `golden_set.yaml` (9.9 KB) and `fixtures/wardrobe.json` (8.1 KB) are eval data, which your rules doc says is always tracked. Keep them in git? | Yes — CI has no Supabase credentials, so evals cannot run on a PR without them |
| Q3 | Split the books by licence: the two **public-domain** texts (Chevreul, Munsell) are `ingest: true` and belong in Supabase Storage like any other corpus. Only *The Curated Closet* (Rees, 44.6 MB, copyrighted, `ingest: false`) has no reason to be uploaded — it is human reading material, not corpus. Keep that one local-only? | Yes — PD books to Storage, Rees local-only |
| Q4 | ~~Two eval setups — which is current?~~ **Answered by inspection, no longer a question.** They are complementary, not duplicates: `src/whattowear/eval/` *runs* the pipeline and writes JSONL artifacts; `backend/evals/` *reads* those artifacts and scores them with RAGAS + openevals. It is a separate uv project on purpose — the RAGAS fork pins `langchain-community==0.3.31`, which conflicts with the `langchain-cohere>=0.4` the retrieval layer needs. | Keep both, and keep the isolation — it is a correct fix for a real dependency conflict |
| Q5 | `retrieval/baseline.py` exists purely as an A/B control for eval comparison, not for production. Carry it forward to keep baselines meaningful, or drop it? | Carry it — the recorded baselines lose meaning without it |
| Q6 | Which selection path is the rebuild's default: the grounded graph path, or the `engine` path (010, left opt-in)? **The comparison data answers this** — see below. | **Engine**, with two follow-ups |

### Q6 in detail — why `engine` should be the default

From `docs/eval-baselines/010-engine/COMPARISON.md`, 24 golden cases, retrieval strategy
held constant so the comparison isolates the selection approach:

| Metric | grounded | engine | Read |
|---|---:|---:|---|
| `owned_only` | 1.00 | 1.00 | Safety guarantee holds on both |
| `cites_grounded` | 1.00 | 1.00 | Zero hallucinated citations on either |
| `retrieval_recall` | 0.94 | 0.94 | Upstream of the split, as expected |
| `weather_appropriate` | 0.83 | **0.92** | **Engine better** |
| `top_rank_score` (mean) | 782.74 | **798.65** | **Engine better** on the shared deterministic scorer |
| `respects_exclusions` | 1.00 | 0.96 | Engine worse by one case in 24 — the one real regression |
| `every_choice_cites` | 1.00 | 0.79 | **Not a regression** — metric blind spot, see below |
| `outfit_count_in_range` | 0.92 | 0.79 | **Not a regression** — same root cause |
| `ranked_descending` | 1.00 | 0.92 | **Already fixed** after the snapshot was taken |

Three things make this a clear call rather than a close one:

1. **The two large apparent regressions are not real.** Both fail on the identical 5 of 24
   cases, all of which returned fewer than 3 outfits because the enumerator genuinely had
   fewer than 3 valid combinations. The deterministic fallback then returns `cites=[]`
   rather than fabricate a citation. The harness metric cannot distinguish "nothing honest
   to cite" from "the model was lazy", so correct behaviour scores as failure. The
   comparison traces this to source with a worked example.
2. **`ranked_descending` was already resolved.** `engine_write` now sorts its picks into
   deterministic `rank_score` order, so on the engine path the LLM neither selects nor
   ranks — Principle II holds unqualified, which it does *not* on the grounded path.
3. **The wins are structural, not noise.** Deterministic weather scoring shapes which
   combinations reach the shortlist at all, instead of asking an LLM to reason about warmth
   while simultaneously inventing the combination.

Two follow-ups if engine becomes the default: teach the harness to treat a
fallback-produced outfit as its own case rather than a bare failure (otherwise the metrics
stay uninterpretable), and investigate the single `respects_exclusions` case.

---

*Generated in Phase 3. `../app-legacy` was not modified.*
