"""Advanced retriever — hybrid per-layer + Cohere rerank on the L3 trend layer.

This is THE featured advanced technique for the Task-6 baseline→advanced story.
L4 (structured) and L1 (load-all + semantic union, Feature 007 Task A) need no
reranking; the semantic/live L3 layer is where a cross-encoder rerank pays off.
We over-fetch L3 candidates (now live Tavily results, Feature 007 Task B), then
Cohere rerank down to the final top-n — same shape as before, different source.
"""

from __future__ import annotations

from langchain_core.documents import Document

from ..config import get_reranker
from ..kb import KnowledgeBase
from ..schema import Context
from . import hybrid
from .base import RetrievalResult

FIRST_STAGE_K = 8  # over-fetch before rerank


def _rerank_l3(l3_query: str, candidates: list[Document], top_n: int) -> list[Document]:
    if not candidates:
        return []
    reranker = get_reranker(top_n=top_n)
    return list(reranker.compress_documents(documents=candidates, query=l3_query))


def retrieve(
    kb: KnowledgeBase,
    ctx: Context,
    layers: list[str],
    l3_query: str,
    k_l3: int = 5,
    first_stage_k: int = FIRST_STAGE_K,
) -> RetrievalResult:
    res = RetrievalResult(strategy="advanced")
    if "L4" in layers:
        res.l4 = hybrid.retrieve_l4(kb, ctx)
    if "L1" in layers:
        res.l1 = hybrid.retrieve_l1(kb, ctx, semantic_query=l3_query)
    if "L3" in layers:
        candidates = hybrid.retrieve_l3(l3_query, k=first_stage_k)
        res.l3 = _rerank_l3(l3_query, candidates, top_n=k_l3)
    return res
