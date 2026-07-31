"""Protocols for what the AI layer needs from outside itself.

Three seams, each drawn where the legacy code actually crossed a boundary
(specs/007-ai-port/research.md §1) — not a speculative "might need later"
abstraction (constitution Quality Bar: "an interface, port, or layer is
introduced only when there are two concrete implementations today or a
measured problem it solves"):

- `VectorStore` — what `retrieval/*` and `kb.py` need from Qdrant.
- `LLMClient` — the `.with_structured_output(...).invoke(...)` shape every
  LLM call site (`pipeline/generator.py`, `pipeline/engine.py`, `vision.py`,
  `external/trends.py`, `eval/judge.py`) actually uses.
- `ClosetRepository` — the one DB-shaped read every AI module needs:
  a user's wardrobe, the shared catalog, and preference-derivation inputs.
  This is Feature 007's fix for the coupling defect recorded in
  docs/legacy-ai-inventory.md §3 — `pipeline/graph.py`, `memory/store.py`
  and `pipeline/context_assembler.py` used to import the DB session factory
  directly; they now take this Protocol instead.

Every concrete binding (`ChatLiteLLM`, `QdrantVectorStore`,
`adapters.closet_fixture.FixtureClosetRepository`) satisfies its Protocol
structurally — no adapter *class* wraps them, only `ClosetRepository`, which
has no existing structural match because nothing in this package already
shapes closet data this way.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from langchain_core.documents import Document
from qdrant_client.models import Filter

if TYPE_CHECKING:
    # Type-checking only — ports.py must import cleanly before schema.py or
    # memory/preferences.py land (specs/007-ai-port/tasks.md T003 runs before
    # T008/T023 per the handoff's "ports.py first" ordering). `from __future__
    # import annotations` above already defers every annotation to a string,
    # so this costs nothing at runtime and never becomes a real import-time
    # coupling from ports.py to the domain modules it describes.
    from .memory.preferences import FeedbackRecord
    from .schema import WardrobeItem


@runtime_checkable
class VectorStore(Protocol):
    """Structurally satisfied by `langchain_qdrant.QdrantVectorStore` today —
    see `retrieval/base.py`'s `RetrievalResult` for how callers consume the
    `Document`s this returns. `filter` is a real `qdrant_client.models.
    Filter` (`retrieval/hybrid.py::_l1_semantic_filter` builds one) — an
    earlier draft of this Protocol typed it as a plain `dict`, which
    doesn't structurally match `QdrantVectorStore`'s actual signature;
    caught by mypy once `kb.py` (Phase 11) made this Protocol's one real
    binding type-checkable for the first time."""

    def similarity_search(self, query: str, k: int = 4, filter: Filter | None = None) -> list[Document]: ...


@runtime_checkable
class LLMClient(Protocol):
    """Structurally satisfied by `ChatLiteLLM` (`adapters/llm_gateway.py`).
    Only the subset of `BaseChatModel` the pipeline actually calls."""

    def with_structured_output(self, schema: type[Any]) -> LLMClient: ...

    def invoke(self, messages: list[Any]) -> Any: ...


@runtime_checkable
class ClosetRepository(Protocol):
    """Read-only access to persisted closet/catalog/feedback data. No
    concrete Postgres-backed implementation ships in this feature — the
    rebuild's schema has no wardrobe/catalog tables yet
    (specs/007-ai-port/research.md §5). `adapters.closet_fixture` is the one
    implementation that exists today, used by the eval harness and tests;
    a Postgres-backed one is a pure swap-in for whichever feature lands
    closet persistence."""

    def list_wardrobe_items(self, user_id: str) -> list[WardrobeItem]: ...

    def list_catalog_items(self) -> list[WardrobeItem]: ...

    def get_derivation_inputs(self, user_id: str) -> tuple[list[FeedbackRecord], dict[str, datetime]]: ...
