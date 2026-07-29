# Contract: `ports.py`

Not an HTTP/API contract — this feature has none. This is the **internal interface
contract** between the AI layer and everything outside it (database, vector store, LLM
gateway), which is what makes `pipeline/`, `retrieval/`, `scoring/`, `memory/`, `ingest/`
importable and testable with zero environment variables set (constitution Technology
Constraints, DoD item 1).

## `VectorStore`

| Method | Signature | Used by |
|---|---|---|
| `similarity_search` | `(query: str, k: int, filter: dict \| None = None) -> list[Document]` | `retrieval/baseline.py`, `hybrid.py`, `advanced.py` |

Production binding: `langchain_qdrant.QdrantVectorStore` (structural match, no adapter class
needed). Test binding: an in-memory Qdrant collection built from the tracked fixture corpus.

## `LLMClient`

| Method | Signature | Used by |
|---|---|---|
| `with_structured_output` | `(schema: type[BaseModel]) -> LLMClient` | `pipeline/generator.py`, `pipeline/engine.py`, `vision.py`, `external/trends.py`, `eval/judge.py` |
| `invoke` | `(messages: list) -> Any` | same call sites, via the object `with_structured_output` returns |

Production binding: `ChatLiteLLM` via `core/config.get_chat_model`/`get_judge_model`
(unchanged from legacy `config.py`, extended into `core/config.py`). Test binding: a
recorded-fixture stub returning fixed structured output — never a live call in CI
(constitution Quality Bar).

## `ClosetRepository`

| Method | Signature | Used by |
|---|---|---|
| `list_wardrobe_items` | `(user_id: str) -> list[WardrobeItem]` | `pipeline/context_assembler.load_wardrobe` |
| `list_catalog_items` | `() -> list[WardrobeItem]` | `pipeline/graph.verify_grounding` |
| `get_derivation_inputs` | `(user_id: str) -> tuple[list[FeedbackRecord], list[str]]` | `memory/store.get_profile` |

Production binding: none in this feature (data-model.md, Research §5) — the Protocol is the
seam; a Postgres-backed implementation lands with closet persistence. Test/eval binding:
`adapters/closet_fixture.FixtureClosetRepository`, backed by the tracked
`evals/fixtures/wardrobe.json`.

## Compliance check every ported module must pass

1. `env -i python3 -c "import whattowear.<module>"` succeeds — no environment variable read
   at import time (mirrors feature 002's `test_import_safety.py` pattern, extended per DoD).
2. `lint-imports` passes with `pipeline`, `retrieval`, `scoring`, `memory`, `ingest` listed in
   `.importlinter`'s `source_modules`, forbidding `whattowear.api`, `whattowear.main`,
   `fastapi`.
3. No `from ..db import SessionLocal` / `from whattowear.core.db import ...` inside
   `pipeline/`, `retrieval/`, `scoring/`, `memory/`, `ingest/` — only `ports.py` Protocol
   types appear in their signatures; a concrete implementation is injected by the caller
   (the eval harness, a test, or — later — the API layer).
