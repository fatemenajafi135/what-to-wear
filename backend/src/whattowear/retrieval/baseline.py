"""Baseline retriever — naive dense over ALL chunks.

Built on purpose (handoff + cert both stress this). No metadata filtering, no
per-layer logic, one NL query embedded and matched against the whole collection.
This is the comparison floor the advanced retriever must beat with numbers
(Task 6). We know it is worse; it is the evidence.
"""

from __future__ import annotations

from langchain_core.documents import Document

from ..kb import KnowledgeBase
from .base import RetrievalResult


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
