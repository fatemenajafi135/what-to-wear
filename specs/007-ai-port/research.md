# Phase 0 Research: AI layer port

All items below were resolved by reading the legacy source directly (not just the inventory
summary) — `db.py`, `pipeline/graph.py`, `memory/store.py`, `pipeline/context_assembler.py`,
`kb.py`, `retrieval/base.py`, `config.py`, `eval/properties.py`, `scoring/weather_fitness.py`,
`ingest/build_kb.py`, `eval/harness.py`, `eval/test_users.py`, `eval/golden_set.py`, `crud.py`
(seed functions only). No `[NEEDS CLARIFICATION]` remained after that reading — every item
here is a decision, not an open question.

## 1. `ports.py` Protocol surface

**Decision**: Three Protocols, not four as the handoff's shorthand ("VectorStore, LLMClient,
ImageStore, and a repository Protocol") suggested — `ImageStore` is dropped.

- `VectorStore` — what `kb.py`/`retrieval/*` need: `similarity_search`,
  `similarity_search_with_filter` (layer + granularity metadata filter), matching
  `QdrantVectorStore`'s actual usage surface in `hybrid.py`/`advanced.py`/`baseline.py`.
- `LLMClient` — what `pipeline/generator.py`, `pipeline/engine.py`, `vision.py`,
  `external/trends.py`, `eval/judge.py` need: a `.with_structured_output(...)` +
  `.invoke(...)` surface matching `ChatLiteLLM`'s `BaseChatModel` interface (`config.py`
  already returns this exact type — the Protocol documents the subset actually called, it
  does not replace `config.py`).
- `ClosetRepository` — `list_wardrobe_items(user_id) -> list[WardrobeItem]`,
  `list_catalog_items() -> list[WardrobeItem]`, `get_derivation_inputs(user_id) ->
  tuple[list[FeedbackRecord], list[str]]` (feedback rows + dismissed signal keys, matching
  `crud.get_derivation_inputs`'s return shape used by `memory/preferences.derive_signals`).

**Rationale**: reading `graph.py`, `context_assembler.py` and `memory/store.py` together
shows exactly three DB touchpoints across the whole AI layer (`context_assembler.load_wardrobe`,
`graph.verify_grounding`'s catalog read, `memory.store.get_profile`'s feedback read) and they
share one shape: read-only access to persisted, per-user or shared closet data. One cohesive
Protocol covers all three without over-fragmenting (constitution Quality Bar: "an interface,
port, or layer is introduced only when there are two concrete implementations today or a
measured problem it solves" — one Protocol with a fixture and a (future) Postgres
implementation clears that bar; three single-method Protocols would not).

**`ImageStore` dropped**: `vision.py` (photo → attributes) takes image bytes/URL as a plain
argument — it never uploads or reads from Supabase Storage itself. Storage I/O is `storage.py`
(explicitly out of scope, feature 003/006 territory). Introducing an `ImageStore` Protocol
with no current caller would violate the same Quality Bar clause the `ClosetRepository`
decision above satisfies. If a future feature needs it, it is added then, against a real
call site.

**Alternatives considered**: A single fat `Ports` bundle Protocol (rejected — hides which
capability a given module actually needs, defeats the point of typed injection). Per-node
Protocols mirroring every `graph.py` DB touchpoint 1:1 (rejected — three near-identical
Protocols for one repository shape is the over-fragmentation the Quality Bar warns against).

## 2. `eval/properties.py` → `scoring/properties.py`

**Decision**: Move the four pure predicates (`owned_only`, `weather_appropriate`,
`occasion_fit`, `respects_exclusions`) and `check_outfit` verbatim to
`scoring/properties.py`. `eval/properties.py` becomes a thin re-export
(`from ..scoring.properties import *`, explicit `__all__`) so nothing importing
`eval.properties` today (the golden-set harness, existing tests) needs to change, and so the
git history of the file's line-by-line content isn't obscured by treating this as a delete +
new-file.

**Rationale**: `pipeline/graph.py` and `scoring/weather_fitness.py` both need
`weather_appropriate` for production hard-constraint pruning and scoring; importing it from
`eval` makes production code depend on the eval package, backwards per Principle V ("scorers
are eval metrics", not the reverse). No logic changes — same functions, same signatures,
same behaviour, corrected import direction only.

**Alternatives considered**: A new `domain/` top-level package for shared predicates
(rejected — `scoring/` already is exactly this domain, and the plan-template's fixed layout
doesn't list a `domain/` directory; adding one is an unjustified structure deviation).

## 3. Correcting `graph.py`'s stale docstring

**Decision**: Replace every "the LLM never ranks (constitution Principle II)" occurrence
(module docstring line 19, mirrored in `engine_enumerate_and_score`'s docstring) with wording
that matches constitution v2.0.0 Principle II precisely: deterministic scoring and final
ordering (`score_and_rank` → `scoring.combine.rank_outfits`) are what the code actually
guarantees on every path; on the **grounded** (default) path the LLM assembles/selects which
items compose each candidate outfit before that deterministic scoring ever runs — it is
selection, not final ranking, and the distinction matters because the prior wording collapsed
them. On the **engine** path, both selection (enumeration) and ranking are deterministic;
the LLM there only writes the rationale for a pre-scored top-K choice.

**Rationale**: read literally, "the LLM never ranks" is not what made the docstring false —
`score_and_rank`'s deterministic order is untouched by the LLM on both paths. What was false
is the implied stronger claim (mirrored in the constitution's own Sync Impact Report) that the
LLM never *decides which items appear at all* — it does, on the grounded path, in
`generate_outfits`. Fixing only the literal word "ranks" without addressing that stronger
implied claim would still leave a misleading docstring.

## 4. Harness metric blind spot — leave it, document it, don't fix it silently

**Decision**: Port `every_choice_cites` and `outfit_count_in_range` unchanged in this feature.
Do not alter their scoring logic.

**Rationale**: per the handoff (Trap 3) and inventory §10, both metrics score the
deterministic fallback's honest empty-citation outfits as failures — a harness defect, not a
pipeline defect, and the recorded baselines were measured with this exact definition. Fixing
it now would silently change what the two numbers mean without a re-recorded baseline to
compare against, which the handoff explicitly forbids ("if you change a metric, re-record and
say so"). This feature's job is proving parity with the existing baselines, not improving the
harness; a harness fix is a legitimate future task, tracked here as a documented gap rather
than attempted mid-port.

## 5. `ClosetRepository`'s concrete adapter is fixture-backed, not Postgres-backed

**Decision**: `adapters/closet_fixture.py` implements `ClosetRepository` by loading the
tracked `evals/fixtures/wardrobe.json` (40 items) once and serving it as both the wardrobe
for any user id and the shared catalog — reproducing `crud.seed_catalog` +
`crud.seed_eval_baseline_user`'s effective behavior (both seed from the identical fixture)
without touching Postgres. `get_derivation_inputs` returns `([], [])` unconditionally,
matching `seed_eval_baseline_user`'s documented guarantee that the eval baseline user has no
feedback rows, so `memory.profile_note()` stays `None` — identical to today's baseline runs.

**Rationale**: this was not in the inventory — found by reading `eval/harness.py::run_case`
closely. It calls `graph.invoke(...)` **without** a `wardrobe` override, meaning
`context_assembler.load_wardrobe(user_id)` executes for real on every eval case, and
`graph.verify_grounding` unconditionally opens a session for `crud.list_catalog_items`. Both
require a populated closet/catalog. This rebuild's migrations
(`infra/supabase/migrations/0001_init.sql`) create no wardrobe/catalog tables yet — that
schema belongs to whichever feature lands closet persistence, not this one. Blocking the
entire eval gate on an unrelated feature's schema would be a worse outcome than a documented,
swappable fixture adapter that reproduces the exact seeded data the baselines were originally
measured against.

**Alternatives considered**: Passing `wardrobe=` explicitly into every eval-harness
`graph.invoke` call, bypassing `ClosetRepository` for wardrobe reads entirely (rejected —
still leaves `verify_grounding`'s catalog read uncovered, and it would silently change
`eval/harness.py`'s call shape from what produced the recorded baselines, which is itself a
behavioural change needing its own eval proof). Standing up a minimal wardrobe/catalog schema
just for this feature (rejected — a schema decision belongs to the feature that owns closet
persistence; duplicating or pre-empting it here risks a second, divergent migration later).

## 6. Qdrant version pin

**Decision**: `qdrant/qdrant:v1.15.5`, matching the `qdrant-client>=1.15.0,<2.0.0` pin already
in the legacy `pyproject.toml` (carried forward unchanged). Not the newest available tag
(`v1.18.x` per a July 2026 check) — server and client are kept in the same minor line
deliberately, since that is the actual tested combination this codebase's history reflects.

**Rationale**: `qdrant-client` documents that a client should not run against a server more
than one minor version behind it; pinning to the client's own minor line is the conservative,
already-proven choice rather than chasing latest.

## 7. Prompt file format

**Decision**: Each of the five prompts becomes `prompts/<name>.md`:

```markdown
---
version: 1
model: openai/gpt-5.4-mini
role: system
---
<prompt text, verbatim from the legacy constant>
```

`version` starts at `1` for every prompt (unchanged text = unchanged version — this is a
carry-over, not an edit). `model` records the model the prompt was authored/evaluated
against (from `config.py`'s `CHAT_MODEL`/`JUDGE_MODEL` defaults), so a future model swap is
visible as a version-adjacent fact. A small loader (`prompts/__init__.py` or a `load_prompt`
helper in each consuming module) parses the front-matter and returns `(text, version)`; the
eval harness records `(prompt_name, version, model)` per row per the handoff's requirement
that "every eval row records the prompt version and model that produced it."

**Rationale**: YAML front-matter is the lightest structure that satisfies "carrying a
version" (handoff §6.2) without inventing a bespoke prompt-manifest format; it's the same
shape Markdown-based tooling already expects.

## 8. `infra/corpus.yaml` schema

**Decision**: One entry per `kb/manifest.yaml` source, carrying forward every field the
legacy manifest already has (`name`, `layer`, `loader`, `status`, `ingest`, `license`,
`chunker`, `chunker_options`, `url`) plus two new fields this feature's reproducibility
requirement needs: `path` (relative to `CORPUS_LOCAL_DIR`, replacing the legacy's
repo-relative `data/...` path) and `sha256` (populated by the ingestion CLI on first run,
checked on every subsequent run for the idempotency guarantee). `want-later` entries (Black
tie, Cocktail attire, Semi-formal wear) carry forward with `ingest: false, status: want-later`
unchanged — a visible backlog, not dropped.

**Rationale**: `infra/corpus.yaml` is this feature's Principle X artifact — "together with the
code MUST rebuild the index reproducibly in one command." A per-file hash is what makes a
second CLI run correctly skip unchanged sources (FR-011/SC-005) instead of re-embedding
everything every time.

## 9. Two eval projects — mechanics of the isolation

**Decision**: `backend/evals/` keeps its own `pyproject.toml`, its own `uv.lock`, and is run
via `uv run --project backend/evals ...` — never installed into `backend/`'s own environment.
No changes to this isolation mechanism; carried forward exactly as the inventory found it
(Q4). Documented explicitly in `quickstart.md` so a new contributor doesn't try to
`uv sync` both projects into one venv.

**Rationale**: already a correct fix for a real conflict (`langchain-community==0.3.31` vs.
`langchain-cohere>=0.4`); nothing to change, only to carry forward and document clearly.

## 10. `CORPUS_LOCAL_DIR` and no-absolute-paths

**Decision**: One new env var, `CORPUS_LOCAL_DIR`, read once by `ingest/cli.py` (and nowhere
else — `infra/corpus.yaml`'s `path` fields are always relative to it). No code path
constructs a path from `~` or a hardcoded absolute string; `Path(os.environ["CORPUS_LOCAL_DIR"])
/ entry.path` is the only join.

**Rationale**: constitution Principle X, restated in the handoff §6.3 ("no absolute paths,
no `~`, anywhere in code"). Matches the pattern `core/config.py` already uses for
`DATABASE_URL` — read once, through one settings surface, never scattered `os.environ.get`
calls across modules (the legacy code's `config.py`/`db.py`/`build_kb.py` each call
`load_dotenv()` independently; this port consolidates env reads into `core/config.py`
additions where practical, noted per-module during the actual port).
