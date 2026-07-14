"""Process-wide knowledge-base singleton.

Builds the KB once per process and hands the same vectorstore + raw chunks to
every retriever. Persists via a real Qdrant server by default (QDRANT_URL /
QDRANT_API_KEY, from build_kb.py — set WTW_QDRANT_URL="" to force in-memory)
so multiple concurrent processes/notebook kernels can all connect at once — a
plain local on-disk store only supports one process at a time and kept
producing "already locked" errors under ordinary multi-notebook usage; a
server (local Docker or Qdrant Cloud, see build_kb.py's comment) is the actual
fix, not a workaround.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from langchain_core.documents import Document

from .ingest.build_kb import COLLECTION, QDRANT_API_KEY, QDRANT_URL, build_vectorstore, ingest_all
from .logging_utils import get_logger

log = get_logger(__name__)


@dataclass
class KnowledgeBase:
    vectorstore: object  # QdrantVectorStore
    chunks: list[Document]
    collection: str = COLLECTION

    def by_layer(self, layer: str) -> list[Document]:
        return [c for c in self.chunks if c.metadata.get("layer") == layer]


@lru_cache(maxsize=1)
def get_kb() -> KnowledgeBase:
    chunks = ingest_all()

    if QDRANT_URL is None:
        return KnowledgeBase(vectorstore=build_vectorstore(chunks), chunks=chunks)

    from qdrant_client import QdrantClient

    from .config import get_embeddings
    from langchain_qdrant import QdrantVectorStore

    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
    # Stale-corpus guard: if the collection is missing, or its point count no
    # longer matches the freshly-ingested corpus (a source was added/removed,
    # or chunker params changed), rebuild instead of silently serving
    # embeddings for a different corpus. This does NOT catch a same-count
    # content edit (e.g. rewording a card's text in place) — drop the
    # collection for a hard reset if you need one after an edit like that.
    fresh = client.collection_exists(COLLECTION) and client.count(COLLECTION).count == len(chunks)
    if fresh:
        log.info("reconnecting to Qdrant server collection '%s' at %s (%d points, no re-embed)",
                  COLLECTION, QDRANT_URL, len(chunks))
        vectorstore = QdrantVectorStore(client=client, collection_name=COLLECTION, embedding=get_embeddings())
    else:
        log.info("no fresh collection at %s — embedding %d chunks now", QDRANT_URL, len(chunks))
        vectorstore = build_vectorstore(chunks, url=QDRANT_URL, api_key=QDRANT_API_KEY)
    return KnowledgeBase(vectorstore=vectorstore, chunks=chunks)
