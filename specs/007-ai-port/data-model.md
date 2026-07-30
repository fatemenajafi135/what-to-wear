# Phase 1 Data Model: AI layer port

Entities here are the ones this feature's code operates on. All are ported/adapted from
`schema.py`, `retrieval/base.py` and the golden-set/manifest formats — no new domain
concept is invented; this document records the shape, not a redesign.

## `WardrobeItem` (from `schema.py`, unchanged)

- `id: str`, `category: str` (one of the frozen taxonomy's leaf categories),
  `colors: list[str]` (hex, source of truth — `colors.py` derives names, never the reverse),
  `formality: Formality` (six-value enum, frozen), `warmth: int` (0–5),
  `season: list[Season]`, optional `fabric`, `pattern`, `fit`.
- Grouped by `categories.group_of()` into one of `top | bottom | full_body | outerwear |
  footwear | accessory` (constitution Principle VI — frozen, no parallel scale).

## `Context` (from `schema.py`, unchanged)

- `occasion: str`, `formality: Formality`, `mood: Optional[str]`, `temp_c: Optional[float]`,
  `condition: Optional[str]`, `temp_band: Optional[TempBand]`, `season: Optional[Season]`,
  `wardrobe: list[WardrobeItem]`, `user_id: Optional[str]`.
- Built once per turn by `pipeline/context_assembler.assemble_context`; on a refinement turn,
  rebuilt from the persisted `original_context`, never from the incoming refinement utterance.

## `RetrievalResult` (from `retrieval/base.py`, unchanged)

- `l1: list[Document]` (harmony rules), `l3: list[Document]` (trend cards), `l4: list[Document]`
  (dress-code/weather filters), `strategy: str`. `.all()` and `.rule_ids()` are the two
  consuming accessors (citation-building, recall scoring).

## `ScoredOutfit` / `DimensionScore` (from `schema.py`, unchanged)

- Four `DimensionScore` per outfit (`weather_fitness`, `color_harmony`, `silhouette_balance`,
  `formality_coherence`), each `{dimension, value: float, reason: str}`, combined by
  `scoring/combine.py` into one `rank_score` — the sole determinant of final order.

## `SuggestResult` (from `schema.py`, unchanged)

- `outfits: list[ScoredOutfit]`, `sources: list[...]` (citation provenance), `context: Context`.
  What `pipeline/explain` returns; what the eval harness's `cite.render_text` renders for the
  JSONL `response` field.

## `ports.py` Protocols — the new contracts this feature adds

### `VectorStore`

```python
class VectorStore(Protocol):
    def similarity_search(self, query: str, k: int, filter: dict | None = None) -> list[Document]: ...
```

Backed today by `langchain_qdrant.QdrantVectorStore` (production) or an in-memory Qdrant
instance (tests) — both already satisfy this shape without a wrapper class, since
`QdrantVectorStore` already implements it structurally.

### `LLMClient`

```python
class LLMClient(Protocol):
    def with_structured_output(self, schema: type) -> "LLMClient": ...
    def invoke(self, messages: list) -> Any: ...
```

Backed today by `ChatLiteLLM` (`core/config.get_chat_model`/`get_judge_model`) — same
structural-typing relationship as `VectorStore`.

### `ClosetRepository`

```python
class ClosetRepository(Protocol):
    def list_wardrobe_items(self, user_id: str) -> list[WardrobeItem]: ...
    def list_catalog_items(self) -> list[WardrobeItem]: ...
    def get_derivation_inputs(self, user_id: str) -> tuple[list[FeedbackRecord], dict[str, datetime]]: ...
```

Two implementations exist by the end of this feature:
- `adapters/closet_fixture.py::FixtureClosetRepository` — loads `evals/fixtures/wardrobe.json`
  once, serves it for any `user_id` and as the catalog; `get_derivation_inputs` always
  returns `([], {})` (empty feedback list, empty dismissal map — dismissal map is keyed by
  `signal_key -> dismissed_at`, matching `crud.get_derivation_inputs`). Used by the eval
  harness and unit tests.
- The Postgres-backed implementation does **not** land in this feature (Research §5) — no
  wardrobe/catalog schema exists yet in `infra/supabase/migrations/`. The Protocol is the
  seam a future feature implements against; nothing here blocks on it.

## `infra/corpus.yaml` entry (one per KB source)

**Correction after reading the real manifest** (this section originally sketched an
idealized schema before the actual `../w2w-corpus/kb/manifest.yaml` had been read in full;
the implementation carries the manifest's real field vocabulary forward unchanged rather
than inventing a new one):

```yaml
- name: "Chevreul: Principles of Harmony & Contrast of Colours"
  layer: L1                # L1 | L2 | L3 | L4 — matches schema.py's Layer literal, not lowercased
  status: have              # have | fetch | distill | want-later — the manifest's real vocabulary
  license: PD                # PD | CC-BY-SA | own | copyrighted | paid — not "public-domain"
  loader: epub
  path: "books/The laws of contrast of colour.epub"   # relative to $CORPUS_LOCAL_DIR
  url: "https://www.gutenberg.org/ebooks/76939"
  chunker: section
  chunker_options: {}
  ingest: true
  sha256: null              # populated by the ingest CLI on first run
```

`ingest: false` entries (the copyrighted books, and every `status: want-later` entry) keep
every field except `sha256`, which is never populated — the file is never read into memory
by the ingestion CLI at all beyond a manifest existence check, matching
`ingest/build_kb.py::ingest_all`'s `if not source.get("ingest"): continue` behaviour.

**Second correction, made while implementing T049**: `corpus.yaml`'s `sha256` field is
documentation-only (always `null` in the tracked file) — the CLI does **not** write back
into `infra/corpus.yaml` on every run. `corpus.yaml` is authored by a person and carries
the licence-policy comments verbatim from the prototype's manifest (§ above); PyYAML's
`safe_dump` is not comment-preserving, so writing computed hashes back into it would
silently strip that documentation on the very first `ingest` run. The real hash-tracking
state instead lives in `$CORPUS_LOCAL_DIR/.ingest_state.json` (`{source_name: sha256}`) —
outside the repo entirely (same directory as the documents themselves), so it is
automatically covered by constitution Principle X's "regenerable artifacts don't belong in
git" without needing its own `.gitignore` entry. `infra/corpus.yaml` stays exactly what a
person wrote; the CLI's own idempotency bookkeeping never touches it.

## Golden-set case (from `eval/golden_set.py`, unchanged)

- `id`, `occasion`, `mood`, `formality`, `temp_c`, `expected: dict` (property-check inputs —
  `min_formality`, `requires_outer`, `max_warmth`, `forbid_categories`, `forbid_colors`),
  `relevant_rule_ids: list[str]`, `reference: str`. 24 cases, tracked at
  `backend/evals/golden_set.yaml`.

## Eval run row (JSONL artifact, from `eval/harness.py::run_case`, unchanged shape + new fields)

Adds `prompt_versions: dict[str, int]` (per Research §7 — which prompt file/version produced
this row) to the existing row shape (`case_id`, `strategy`, `user_input`, `reference`,
`reference_contexts`, `response`, `retrieved_contexts`, `retrieval_recall`, `checks: dict`,
`hallucinated_items`, `ungrounded_cites`, `num_outfits`, `top_rank_score`, `judge_score`).
Adding a field is additive and does not change any existing metric's computation — the
baseline comparison in Phase 3 reads only the pre-existing keys.
