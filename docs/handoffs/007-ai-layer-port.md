# Handoff — Feature 007: AI layer port

**From:** tech lead · **Status:** ready to start · **Branch:** `feat/007-ai-port`, cut from
`rebuild`

**This is the highest-risk slice in the project.** It carries three iterations of measured
quality work out of the prototype and into the rebuild. Its gate is not a screen — it is an
eval run matching recorded baselines.

Backend only. No UI. It runs in parallel with feature 003 and shares no files with it.

---

## 1. Mission

Port the salvaged AI pipeline out of `../app-legacy` into `backend/src/whattowear/`,
**preserving behaviour** — and prove it with evals against the recorded baselines.

### Port with understanding, not transcription

**This is not a copy-paste job.** Read each module and understand why it exists before you
move it. A file that lands here unchanged because nobody looked at it is a worse outcome
than one that lands here improved.

The line to hold is precise:

| | |
|---|---|
| **Behaviour** — what the code computes, what it returns, how it ranks and scores | **Must not change** without an eval run proving it. Principle I. |
| **Everything else** — structure, naming, typing, tests, docstrings, dead code, duplication | **Should improve.** You are expected to leave it better. |

So: fix the coupling defects, extract the prompts, add the type hints that are missing, write
the unit test the module never had, delete the dead branch, rename the variable that lies.
Do **not** rewrite a scorer because you would have written it differently — that code was
evaluated, and replacing it discards the evidence without replacing it.

**Do not inherit stale claims.** Legacy docstrings cite the prototype's constitution, and at
least one is measurably false: `pipeline/graph.py` claims *"the LLM never ranks (constitution
Principle II)"*, which the Feature 010 comparison disproved for the grounded path — the path
this rebuild uses by default. Carrying that comment forward propagates a documented
falsehood. Check the claims you copy.

**Report what you improved and what you deliberately left alone.** Both are decisions.

---

## 2. Setup

Prerequisites: Docker running, `uv`, Node 20+. Feature 002 built the package and the local
database; this slice adds Qdrant and the corpus.

```bash
git checkout rebuild && git checkout -b feat/007-ai-port
cd infra && npm install && npx supabase start
cd ../backend && uv sync && cp .env.example .env
uv run pytest        # baseline: green before you start
```

### Credentials you need — this slice costs money

Unlike 002 and 003, this one needs real accounts. From
`../app-legacy/backend/.env.example`:

| Variable | For |
|---|---|
| `AI_GATEWAY_API_KEY`, `AI_GATEWAY_BASE_URL` | Every LLM and embedding call, via the Vercel AI Gateway |
| `WTW_CHAT_MODEL`, `WTW_EMBEDDING_MODEL`, `WTW_JUDGE_MODEL`, `WTW_EMBEDDING_DIMS` | Model selection |
| `COHERE_API_KEY`, `WTW_RERANK_MODEL` | L3 rerank in `retrieval/advanced.py` |
| `TAVILY_API_KEY` | Live trend search in `external/trends.py` |
| `LANGSMITH_API_KEY`, `LANGSMITH_TRACING`, `LANGSMITH_PROJECT` | Tracing — required by the constitution on every LLM and retrieval call |
| `WTW_QDRANT_URL` | Vector store |

**Ask the project owner for these before starting.** Add every one to `.env.example` as a
placeholder. **Never commit a real key.**

### Qdrant is not in the local stack yet

Adding it is your first task. A pinned `qdrant/qdrant` container alongside the Supabase
stack, documented in `quickstart.md` so the next person gets it in one command.

### The corpus

Lives at **`../w2w-corpus/`** — outside the repo, deliberately. 16 files, 47 MB: three
books, six refined Wikipedia pages, three KB card files, the manifest, the golden set and a
fixture wardrobe.

Constitution Principle X: **no document is ever committed, and none is read from a path
inside the repo.** They belong in Supabase Storage, described by the tracked manifest
`infra/corpus.yaml`.

Per-file licence policy is already set in `../w2w-corpus/kb/manifest.yaml` and **must carry
forward unchanged**: the two public-domain texts (Chevreul, Munsell) are `ingest: true`; *The
Curated Closet* (Rees) is copyrighted, `ingest: false`, reference-only, never embedded. Only
distilled cards in the project's own words enter the index.

---

## 3. How to run this

```
/speckit-specify → /speckit-clarify → /speckit-plan → /speckit-tasks
                 → /speckit-analyze → /speckit-implement
```

Rename the branch Spec Kit cuts: `git branch -m feat/007-ai-port`. Merge into `rebuild` by PR.

---

## 4. Read first

| # | Source | What to take |
|---|---|---|
| 1 | **`docs/legacy-ai-inventory.md`** | **The map.** Every module, what it does, how often it is referenced, and the two coupling defects. Read it fully before planning. |
| 2 | `.specify/memory/constitution.md` | Principles **I, II, III, IV, V, VI, X** all bind here. |
| 3 | `docs/eval-baselines/` in `../app-legacy/docs/` | Three recorded iterations. **Your gate.** |
| 4 | `../app-legacy/backend/src/whattowear/` | The source. **Read-only — never modify anything in that checkout.** |
| 5 | `../app-legacy/.specify/memory/constitution.md` | The prototype's constitution, cited inline throughout the code. Useful for understanding intent. |

---

## 5. Order of work — follow it

Sequence matters more here than anywhere else in the project.

1. **`ports.py` and the package skeleton.** Protocols for what the pipeline needs from
   outside: `VectorStore`, `LLMClient`, `ImageStore`, and a repository Protocol for closet
   reads. This is the slice where `ports.py` belongs — 002 correctly deferred it.
2. **Port one module at a time, one commit each.** Lift it, strip framework imports, add a
   unit test, move on. Start with the leaves: `schema.py`, `colors.py`, `categories.py`,
   then `scoring/`, then `retrieval/`, then `pipeline/`.
3. **Get the evals running against the ported modules before improving anything.** This is
   the whole point. You cannot prove a refactor is safe if the measurement does not run yet.
4. **Then** the corpus manifest, ingestion CLI and Qdrant index.
5. **Then** extend the import-linter contract.

---

## 6. In scope

### 6.1 The two coupling defects — fix them during the port

Recorded in `docs/legacy-ai-inventory.md` §3, both measured:

**Database coupling.** Three modules import the session factory directly —
`pipeline/graph.py:46`, `memory/store.py:39`, `pipeline/context_assembler.py:90`. Because the
legacy `db.py` builds an engine at import time, importing the pipeline requires a configured
database. Feature 002 already fixed the engine to be lazy; **your job is the other half** —
those modules take a repository Protocol, they do not import a session factory.

**Dependency inversion.** `pipeline/graph.py` and `scoring/weather_fitness.py` both import
`eval/properties.py`. Production importing the eval package is backwards. Move those pure
predicates into the domain (`scoring/properties.py`) and let `eval/` import from there. No
logic changes.

### 6.2 Prompts become files

Five inline prompts, all named module constants (inventory §4):

| Prompt | Currently at |
|---|---|
| `SYSTEM_PROMPT` | `pipeline/generator.py:40` |
| `SYSTEM_PROMPT` | `vision.py:23` |
| `_ENGINE_SYSTEM_PROMPT` | `pipeline/engine.py:93` |
| `_DISTILL_PROMPT` | `external/trends.py:23` |
| `_PROMPT` | `eval/judge.py:20` |

Move each to `prompts/<name>.md` with YAML front-matter carrying a version. **Every eval row
records the prompt version and model that produced it**, so a quality change can be
attributed rather than guessed at. Constitution Technology Constraints: inline prompt
strings in Python are prohibited.

### 6.3 Corpus and ingestion

`infra/corpus.yaml` — id, `supabase://` URI, sha256, chunker and embedding model per
document. Ingestion is a **CLI entry point, never an HTTP endpoint**, and idempotent by
content hash. Local corpus path comes from a `CORPUS_LOCAL_DIR` env var — no absolute paths,
no `~`, anywhere in code.

Keep the manifest's `status: want-later` entries (Black tie, Cocktail attire, Semi-formal
wear) as a backlog rather than dropping them.

### 6.4 Both eval projects

`src/whattowear/eval/` *runs* the pipeline and writes JSONL artifacts. `backend/evals/` *reads*
those artifacts and scores them with RAGAS + openevals. **Keep both, and keep them isolated** —
the RAGAS fork pins `langchain-community==0.3.31`, which conflicts with the retrieval layer's
`langchain-cohere>=0.4`. Separate uv projects is the correct fix for a real dependency
conflict, not accidental duplication.

### 6.5 Extend the import-linter contract

`backend/.importlinter` currently covers only `whattowear.core`, with a comment saying this
slice extends it. Add `pipeline`, `retrieval`, `scoring`, `memory`, `ingest` to
`source_modules` **as each lands** — so the contract is always true, never aspirational.

---

## 7. Decisions already made — do not relitigate

| Topic | Decision | Source |
|---|---|---|
| **Default selection path** | **Grounded**, not engine. Engine stays in the codebase as opt-in exactly as Feature 010 shipped it. | inventory §10 Q6 |
| Principle II wording | On the grounded path **the LLM does assemble the combination**. Scoring is deterministic; grounding and scoring are the guarantees. Do **not** re-inherit `graph.py`'s "the LLM never ranks" docstring — it was measured false. | constitution II |
| `retrieval/baseline.py` | Keep. It is the A/B control; the recorded baselines lose meaning without it. | Q5 |
| Both eval projects | Keep both, keep the isolation. | Q4 |
| Corpus location | Supabase Storage + `infra/corpus.yaml`. Local working copy outside the repo. Nothing committed. | Q1–Q3 |
| Books | PD texts ingested; the copyrighted one is reference-only, `ingest: false`. | Q3 |
| Alembic | Not used. Supabase migrations only. | constitution |

---

## 8. Traps

1. **`../app-legacy` is a checkout of the live prototype. Never modify it.** Read, copy out,
   leave untouched.
2. **Do not regenerate.** Principle I. Any refactor of retrieval, chunking, ingest, the KB,
   scoring, the pipeline or the harness needs an eval run showing no regression.
3. **Do not "fix" the harness metrics quietly.** `every_choice_cites` and
   `outfit_count_in_range` have a known blind spot — they score the deterministic fallback's
   *honest* empty citations as failures. That is a harness defect, not a pipeline defect.
   Fixing it is welcome; silently changing what the numbers mean is not, because the recorded
   baselines were measured with the old definition. If you change a metric, re-record and say so.
4. **Carry the pooler reasoning.** 002 already did this in `core/db.py` — do not undo it.
5. **The prototype's `.env` had `SUPABASE_URL`, `REDIS_URL`, `WTW_CORS_ORIGINS`.** Redis and
   the suggestion cache belong to a later slice. Do not drag them in.
6. **No live LLM calls in CI.** Constitution Quality Bar — recorded fixtures only. Otherwise
   the suite is flaky and bills real money on every push.
7. **The fixture corpus under `evals/fixtures/` stays tracked.** It is the one deliberate
   exception to Principle X, and it exists so evals can run in CI, which has no
   object-storage credentials.

---

## 9. Definition of done

- [ ] Every AI module imports with **zero environment variables** — same guarantee 002
      established. Extend `test_import_safety.py`'s parametrised list as modules land.
- [ ] No AI module imports `whattowear.api`, `whattowear.main`, or `fastapi`. Enforced by
      `lint-imports`, with `source_modules` actually listing them.
- [ ] No AI module imports a session factory. Database access goes through `ports.py`.
- [ ] `eval/properties.py` no longer imported by production code.
- [ ] All five prompts are files with versions; no inline prompt string remains in Python.
- [ ] **An eval run reproduces the recorded baselines in `docs/eval-baselines/`** — the
      headline gate. Report the numbers next to the recorded ones, metric by metric. Explain
      any delta; do not average it away.
- [ ] `infra/corpus.yaml` describes every ingested document, and ingestion rebuilds the index
      reproducibly in one command.
- [ ] Nothing from `../w2w-corpus/` is committed.
- [ ] `ruff`, `ruff format --check`, `mypy`, `pytest`, `lint-imports` all clean.
- [ ] `quickstart.md` gets someone from clone to a working index, Qdrant included.
- [ ] `.env.example` lists every variable. No real key in the diff.

---

## 10. Report back with

What you ported and what you deliberately left · **the eval comparison table, your numbers
against the recorded baselines, metric by metric** · which Constitution Check gates you could
not satisfy · anything you had to decide that the inventory did not cover.

**The eval numbers are the report.** Everything else is context. If they do not match, say so
plainly and explain why — a regression you have identified is a normal engineering problem, a
regression you have averaged into a summary is a much worse one.
