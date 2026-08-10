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
- `IsolationClient` — feature 018 (photo-to-items, specs/018-photo-to-items/
  research.md §5): what `api/v1/routes/closet.py`'s extract route needs
  from whichever image-isolation strategy is configured. Three concrete
  implementations exist (segmentation, generative reconstruction, hybrid —
  `adapters/isolation_*.py`), each a hosted HTTP call, chosen at runtime by
  `adapters.isolation.get_isolation_client()` reading `wtw_isolation_
  strategy` — the same shape `kb.py`'s `wtw_kb_mode` selection already
  establishes for `VectorStore`-adjacent code, applied to a different
  Protocol. Qualifies for a port the same way this file's other three do:
  three concrete implementations today, not a speculative "might need
  later" abstraction.

Every concrete binding (`ChatLiteLLM`, `QdrantVectorStore`,
`adapters.closet_fixture.FixtureClosetRepository`, the three
`adapters.isolation_*` modules) satisfies its Protocol structurally — no
adapter *class* wraps them, only `ClosetRepository`, which has no existing
structural match because nothing in this package already shapes closet
data this way.
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
    from .schema import BoundingBox, IsolationOutcome, WardrobeItem


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
    """Read-only access to persisted closet/catalog/feedback data.

    Two implementations satisfy this today: `adapters.closet_fixture`
    (used by the eval harness and tests, so evals run with no database at
    all) and `repositories.supabase_closet.SupabaseClosetRepository`, the
    Postgres-backed one feature 004 landed and 008 passes straight to
    `pipeline.graph.get_compiled_graph`. The swap-in this Protocol was
    written to anticipate (specs/007-ai-port/research.md §5, when the
    rebuild's schema still had no wardrobe tables) has since happened,
    unchanged — no adapter class was needed.

    Caveat worth knowing before relying on it: `SupabaseClosetRepository.
    get_derivation_inputs` is still a stub returning `([], {})`, so
    preference memory derives from nothing on the Postgres path. Feeding
    it is its own feature's work, not something a caller can compensate
    for."""

    def list_wardrobe_items(self, user_id: str) -> list[WardrobeItem]: ...

    def list_catalog_items(self) -> list[WardrobeItem]: ...

    def get_derivation_inputs(self, user_id: str) -> tuple[list[FeedbackRecord], dict[str, datetime]]: ...


@runtime_checkable
class IsolationClient(Protocol):
    """Structurally satisfied by each of `adapters/isolation_segmentation.
    py`, `isolation_generative.py`, `isolation_hybrid.py`. `isolate` MUST
    NEVER raise for an ordinary call/timeout failure — it returns an
    `IsolationOutcome` with `image_bytes=None` instead (mirrors `adapters/
    storage.py::create_signed_url`'s fail-soft pattern), so the extract
    route handles success/failure identically across all three strategies
    without per-adapter try/except (spec.md FR-013: an isolation failure
    is never surfaced as an error, always falls back silently)."""

    def isolate(self, image_bytes: bytes, mime_type: str, region: BoundingBox) -> IsolationOutcome: ...
