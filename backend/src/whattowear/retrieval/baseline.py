"""Baseline retriever — naive dense over ALL chunks.

Built on purpose (the A/B control). No metadata filtering, no per-layer
logic, one NL query embedded and matched against the whole collection.
This is the comparison floor the advanced retriever must beat with
numbers — kept per specs/007-ai-port/spec.md's decision to preserve it as
the A/B control the recorded baselines depend on (inventory §10 Q5).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from langchain_core.documents import Document

from .base import RetrievalResult

if TYPE_CHECKING:
    # kb.py doesn't land until Phase 11 (ingest) — see ports.py's identical
    # TYPE_CHECKING note for why this is safe: only ever used as a type hint.
    from ..kb import KnowledgeBase


def retrieve(kb: KnowledgeBase, nl_query: str, k: int = 8) -> RetrievalResult:
    """One dense query over everything; results bucketed by layer only for
    reporting parity with the hybrid result."""
    docs: list[Document] = kb.vectorstore.similarity_search(nl_query, k=k)
    res = RetrievalResult(strategy="baseline")
    for d in docs:
        layer = d.metadata.get("layer")
        if layer == "L1":
            res.l1.append(d)
        elif layer == "L3":
            res.l3.append(d)
        elif layer == "L4":
            res.l4.append(d)
        else:
            res.l1.append(d)
    return res
