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

from langchain_core.documents import Document

from .core.config import get_settings
from .ingest.build_kb import COLLECTION, build_vectorstore, ingest_all
from .logging_utils import get_logger
from .ports import VectorStore

log = get_logger(__name__)


@dataclass
class KnowledgeBase:
    vectorstore: VectorStore  # QdrantVectorStore (structurally satisfies ports.VectorStore)
    chunks: list[Document]
    collection: str = COLLECTION

    def by_layer(self, layer: str) -> list[Document]:
        return [c for c in self.chunks if c.metadata.get("layer") == layer]


@lru_cache(maxsize=1)
def get_kb() -> KnowledgeBase:
    settings = get_settings()
    if not settings.corpus_local_dir:
        raise RuntimeError(
            "CORPUS_LOCAL_DIR is required to build/reconnect to the knowledge base. Set it in .env (see .env.example)."
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
