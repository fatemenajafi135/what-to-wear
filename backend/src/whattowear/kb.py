"""Process-wide knowledge-base singleton.

Builds the KB once per process and hands the same vectorstore + raw
chunks to every retriever. Persists via a real Qdrant server by default
(`WTW_QDRANT_URL` — set it to an empty string to force in-memory) so
multiple concurrent processes/notebook kernels can all connect at once —
a plain local on-disk store only supports one process at a time.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

from langchain_core.documents import Document

from .core.config import get_settings
from .ingest.build_kb import COLLECTION, build_vectorstore, ingest_all
from .logging_utils import get_logger
from .ports import VectorStore

if TYPE_CHECKING:  # import-time cost stays out of the runtime path
    from qdrant_client import QdrantClient

    from .core.config import Settings

log = get_logger(__name__)


@dataclass
class KnowledgeBase:
    vectorstore: VectorStore  # QdrantVectorStore (structurally satisfies ports.VectorStore)
    chunks: list[Document]
    collection: str = COLLECTION

    def by_layer(self, layer: str) -> list[Document]:
        return [c for c in self.chunks if c.metadata.get("layer") == layer]


_VALID_MODES = ("auto", "corpus", "reconnect")

# Qdrant's own scroll page size. Purely a network-batching choice — every page
# is appended to one list, so this affects round trips, not the result.
_SCROLL_PAGE = 256


def _chunks_from_qdrant(client: QdrantClient, collection: str) -> list[Document]:
    """Rebuild the chunk list from the collection's stored payloads.

    `retrieval/hybrid.py` reads `kb.by_layer("L1")` and `kb.by_layer("L4")` off
    the raw chunks, not through the vectorstore, so a knowledge base is not
    usable without them — which is why `get_kb()` re-read the corpus even when
    it was only going to reconnect.

    `QdrantVectorStore.from_documents` writes each Document to the point
    payload under langchain-qdrant's default keys (`page_content`, `metadata`),
    verified against a real collection, so the chunks can be read back out
    without the corpus files being present at all.
    """
    documents: list[Document] = []
    offset = None
    while True:
        points, offset = client.scroll(
            collection_name=collection,
            limit=_SCROLL_PAGE,
            offset=offset,
            with_payload=True,
            with_vectors=False,  # never needed here, and they dominate transfer size
        )
        for point in points:
            payload = point.payload or {}
            documents.append(
                Document(
                    page_content=payload.get("page_content", ""),
                    metadata=payload.get("metadata") or {},
                )
            )
        if offset is None:
            return documents


def _reconnect_client(settings: Settings) -> QdrantClient:
    """Split out purely as a seam: it lets the reconnect guards be tested
    without a live Qdrant, so they run in CI with no services."""
    from qdrant_client import QdrantClient

    return QdrantClient(url=settings.wtw_qdrant_url, api_key=settings.wtw_qdrant_api_key)


def _reconnect_kb(settings: Settings) -> KnowledgeBase:
    """Attach to a populated Qdrant collection without reading the corpus.

    Every failure here is loud. An empty or missing collection would otherwise
    produce a knowledge base that answers every retrieval with nothing — which
    does not crash, and instead yields ungrounded styling output that looks
    like working software (Principle IV). The same reasoning as the
    checkpointer's `postgres` mode: a misconfigured deployment must fail at
    startup, not degrade quietly.
    """
    from langchain_qdrant import QdrantVectorStore

    from .adapters.llm_gateway import get_embeddings

    url = settings.wtw_qdrant_url
    if not url:
        raise RuntimeError(
            "WTW_KB_MODE=reconnect requires WTW_QDRANT_URL — there is no collection to attach to "
            "without it. Set WTW_QDRANT_URL (and WTW_QDRANT_API_KEY), or use WTW_KB_MODE=corpus "
            "with CORPUS_LOCAL_DIR to build the knowledge base from source documents."
        )

    client = _reconnect_client(settings)
    if not client.collection_exists(COLLECTION):
        raise RuntimeError(
            f"WTW_KB_MODE=reconnect, but collection {COLLECTION!r} does not exist at {url}. "
            "Populate it first from a machine that has the corpus: "
            "`uv run python -m whattowear.ingest.cli` with WTW_QDRANT_URL pointed at this cluster."
        )
    count = client.count(COLLECTION).count
    if count == 0:
        raise RuntimeError(
            f"WTW_KB_MODE=reconnect, but collection {COLLECTION!r} at {url} is empty. "
            "Retrieval would return nothing and styling would be ungrounded, so this fails "
            "rather than serving an empty knowledge base."
        )

    chunks = _chunks_from_qdrant(client, COLLECTION)
    log.info(
        "reconnected to Qdrant collection '%s' at %s (%d points, %d chunks rebuilt from payloads, corpus not read)",
        COLLECTION,
        url,
        count,
        len(chunks),
    )
    return KnowledgeBase(
        vectorstore=QdrantVectorStore(client=client, collection_name=COLLECTION, embedding=get_embeddings()),
        chunks=chunks,
    )


@lru_cache(maxsize=1)
def get_kb() -> KnowledgeBase:
    settings = get_settings()
    mode = settings.wtw_kb_mode.strip().lower()
    if mode not in _VALID_MODES:
        raise RuntimeError(f"WTW_KB_MODE must be one of {', '.join(_VALID_MODES)} — got {settings.wtw_kb_mode!r}.")

    if mode == "reconnect":
        return _reconnect_kb(settings)

    # --- "corpus" mode (and "auto"): unchanged from the evaluated implementation ---
    #
    # `auto` deliberately does NOT fall back to reconnect here. It briefly did,
    # and that was a silent-fallback bug: with no CORPUS_LOCAL_DIR set, a local
    # process would quietly attach to whatever Qdrant collection its config
    # happened to point at — in practice the deployed one — and serve it as if
    # it had built the KB itself. No error, no warning, just someone else's
    # knowledge base. Caught by `test_kb.py`'s pre-existing contract test, which
    # this branch had stopped satisfying.
    #
    # Reconnecting reads a collection this process cannot verify against the
    # corpus that produced it, so it is a deliberate operational choice, not a
    # default worth inferring. `render.yaml` sets WTW_KB_MODE=reconnect
    # explicitly for exactly that reason.
    if not settings.corpus_local_dir:
        raise RuntimeError(
            "CORPUS_LOCAL_DIR is required to build the knowledge base. Set it in .env "
            "(see .env.example), or set WTW_KB_MODE=reconnect to attach to an already-populated "
            "Qdrant collection instead — which is what a deployed instance without the corpus wants. "
            "It is not inferred: attaching to a collection this process did not build is an explicit "
            "choice."
        )
    corpus_dir = Path(settings.corpus_local_dir)
    chunks = ingest_all(corpus_dir)

    if settings.wtw_qdrant_url is None:
        return KnowledgeBase(vectorstore=build_vectorstore(chunks), chunks=chunks)

    from langchain_qdrant import QdrantVectorStore
    from qdrant_client import QdrantClient

    from .adapters.llm_gateway import get_embeddings

    client = QdrantClient(url=settings.wtw_qdrant_url, api_key=settings.wtw_qdrant_api_key)
    # Stale-corpus guard: if the collection is missing, or its point count
    # no longer matches the freshly-ingested corpus (a source was
    # added/removed, or chunker params changed), rebuild instead of
    # silently serving embeddings for a different corpus. This does NOT
    # catch a same-count content edit (e.g. rewording a card's text in
    # place) — drop the collection for a hard reset if you need one after
    # an edit like that.
    fresh = client.collection_exists(COLLECTION) and client.count(COLLECTION).count == len(chunks)
    vectorstore: VectorStore
    if fresh:
        log.info(
            "reconnecting to Qdrant server collection '%s' at %s (%d points, no re-embed)",
            COLLECTION,
            settings.wtw_qdrant_url,
            len(chunks),
        )
        vectorstore = QdrantVectorStore(client=client, collection_name=COLLECTION, embedding=get_embeddings())
    else:
        log.info("no fresh collection at %s — embedding %d chunks now", settings.wtw_qdrant_url, len(chunks))
        vectorstore = build_vectorstore(chunks, url=settings.wtw_qdrant_url, api_key=settings.wtw_qdrant_api_key)
    return KnowledgeBase(vectorstore=vectorstore, chunks=chunks)
