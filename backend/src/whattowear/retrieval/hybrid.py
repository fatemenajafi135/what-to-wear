"""Hybrid per-layer retriever — the advanced design (minus the rerank stage).

Retrieval method is chosen per layer by query shape (handoff §3):
- **L4** structured metadata *lookup* — occasion/formality/temp_band map to fields,
  nothing fuzzy to embed. Pure metadata filter (a Python lookup over the small L4
  set; forcing vector search here would be worse).
- **L1** load-all of the atomic harmony rules (small, injected wholesale),
  optionally narrowed to rules touching the wardrobe's colors.
- **L3** dense vector search with a metadata filter (`layer == L3`) — the one
  genuine semantic layer.

"It's RAG with hybrid retrieval — structured filtering on the constraint layers,
dense retrieval on the trend layer."
"""

from __future__ import annotations

from langchain_core.documents import Document
from qdrant_client import models

from ..colors import nearest_names
from ..kb import KnowledgeBase
from ..schema import Context
from .base import RetrievalResult


# --- L4: structured metadata lookup ------------------------------------------


def retrieve_l4(kb: KnowledgeBase, ctx: Context) -> list[Document]:
    """Dress-code eligibility (occasion+formality) + the weather garment rule
    (temp_band). Pure structured filter, no embedding."""
    out: list[Document] = []
    for c in kb.by_layer("L4"):
        m = c.metadata
        occ, band, form = m.get("occasion"), m.get("temp_band"), m.get("formality")
        is_dresscode = form == ctx.formality and occ in (ctx.occasion, "default")
        is_weather = band is not None and band == ctx.temp_band
        if is_dresscode or is_weather:
            out.append(c)
    return out


# --- L1: load-all atomic harmony rules ---------------------------------------


def retrieve_l1(kb: KnowledgeBase, ctx: Context, color_filter: bool = False) -> list[Document]:
    """All atomic L1 rules (the PD-prose section chunks stay out of the generator
    context; they live in the store for the retrieval experiment only)."""
    rules = [c for c in kb.by_layer("L1") if c.metadata.get("granularity") == "atomic"]
    if color_filter and ctx.wardrobe:
        # wardrobe colors are hex (source of truth); rule prose uses color
        # names, so match on the DERIVED name, never the hex value itself.
        colors = {n for item in ctx.wardrobe for n in nearest_names(item.colors)}
        narrowed = [r for r in rules if any(col in r.page_content.lower() for col in colors)]
        # only narrow if it leaves a useful set; else fall back to all rules
        if len(narrowed) >= 3:
            return narrowed
    return rules


# --- L3: dense vector search + metadata filter -------------------------------


def _l3_filter() -> models.Filter:
    # metadata is stored under the "metadata" payload key by langchain-qdrant
    return models.Filter(
        must=[models.FieldCondition(key="metadata.layer", match=models.MatchValue(value="L3"))]
    )


def retrieve_l3(kb: KnowledgeBase, l3_query: str, k: int = 5) -> list[Document]:
    """Dense trend retrieval, filtered to the L3 layer. Season is carried in the
    query text (ranks the right-season trends up) rather than hard-filtered, so
    general trend chunks aren't excluded."""
    return kb.vectorstore.similarity_search(l3_query, k=k, filter=_l3_filter())


# --- combined ----------------------------------------------------------------


def retrieve(
    kb: KnowledgeBase,
    ctx: Context,
    layers: list[str],
    l3_query: str,
    k_l3: int = 5,
) -> RetrievalResult:
    res = RetrievalResult(strategy="hybrid")
    if "L4" in layers:
        res.l4 = retrieve_l4(kb, ctx)
    if "L1" in layers:
        res.l1 = retrieve_l1(kb, ctx)
    if "L3" in layers:
        res.l3 = retrieve_l3(kb, l3_query, k=k_l3)
    return res
