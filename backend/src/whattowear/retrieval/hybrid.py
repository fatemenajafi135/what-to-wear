"""Hybrid per-layer retriever — the advanced design (minus the rerank stage).

Retrieval method is chosen per layer by query shape (handoff §3):
- **L4** structured metadata *lookup* — occasion/formality/temp_band map to fields,
  nothing fuzzy to embed. Pure metadata filter (a Python lookup over the small L4
  set; forcing vector search here would be worse).
- **L1** load-all of the atomic harmony rules (small, injected wholesale, always
  present), UNIONED with a genuine semantic search over the long-form section
  chunks (Wikipedia color theory/harmony, Chevreul, Munsell) that build_kb.py
  already embeds into the same L1 layer but that retrieval never queried before
  (Feature 007 Task A) — optionally narrowed to rules touching the wardrobe's
  colors (atomic pool only).
- **L3** a live Tavily web search performed at request time (Feature 007 Task B),
  turned into citable Documents — no longer a static pre-ingested collection for
  the hybrid/advanced strategies (baseline still queries the whole corpus
  including the static trend cards directly, untouched by this change).

"It's RAG with hybrid retrieval — structured filtering on the constraint layers,
dense retrieval on the trend layer, and a live search tool for what's current."
"""

from __future__ import annotations

import hashlib

from langchain_core.documents import Document
from qdrant_client import models

from ..colors import nearest_names
from ..kb import KnowledgeBase
from ..logging_utils import get_logger
from ..schema import Context
from .base import RetrievalResult

log = get_logger(__name__)

_L1_SEMANTIC_K = 5


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


# --- L1: load-all atomic harmony rules + semantic search over long-form chunks -


def _l1_semantic_filter() -> models.Filter:
    # metadata is stored under the "metadata" payload key by langchain-qdrant.
    # granularity=="section" excludes the atomic cards (already returned by the
    # load-all below) so the union never double-counts a card against itself.
    return models.Filter(
        must=[
            models.FieldCondition(key="metadata.layer", match=models.MatchValue(value="L1")),
            models.FieldCondition(key="metadata.granularity", match=models.MatchValue(value="section")),
        ]
    )


def retrieve_l1(
    kb: KnowledgeBase, ctx: Context, semantic_query: str = "", color_filter: bool = False
) -> list[Document]:
    """Atomic L1 rules (load-all, small, injected wholesale) UNIONED with a
    similarity_search over the long-form section chunks build_kb.py already
    embeds into the L1 layer (Wikipedia color theory/harmony, Chevreul,
    Munsell) — genuine chunked-embedding retrieval, not just hand-written
    cards (Feature 007 Task A). `color_filter` narrows the atomic pool only;
    the semantic branch is already query-relevant by construction."""
    rules = [c for c in kb.by_layer("L1") if c.metadata.get("granularity") == "atomic"]
    if color_filter and ctx.wardrobe:
        # wardrobe colors are hex (source of truth); rule prose uses color
        # names, so match on the DERIVED name, never the hex value itself.
        colors = {n for item in ctx.wardrobe for n in nearest_names(item.colors)}
        narrowed = [r for r in rules if any(col in r.page_content.lower() for col in colors)]
        # only narrow if it leaves a useful set; else fall back to all rules
        if len(narrowed) >= 3:
            rules = narrowed

    semantic: list[Document] = []
    if semantic_query:
        semantic = kb.vectorstore.similarity_search(semantic_query, k=_L1_SEMANTIC_K, filter=_l1_semantic_filter())

    seen = {r.metadata["rule_id"] for r in rules}
    return rules + [s for s in semantic if s.metadata["rule_id"] not in seen]


# --- L3: live Tavily search, request-time ------------------------------------


def retrieve_l3(l3_query: str, k: int = 5) -> list[Document]:
    """Live trend search via the gateway's Tavily tool (Feature 007 Task B) —
    replaces the old static pre-ingested trend collection for the hybrid/
    advanced strategies (baseline still queries the whole corpus, including
    the still-ingested static trend cards, directly and never calls this).
    Degrades gracefully: a Tavily failure/timeout returns [] rather than
    propagating, mirroring context_assembler's weather-lookup fallback, so a
    suggestion is still produced without trend-sourced rationale."""
    from ..external.trends import search_trends

    try:
        results = search_trends(l3_query, max_results=k)
    except Exception as exc:  # noqa: BLE001 - live external call: degrade, don't crash
        log.warning("Tavily live trend search failed (%s); proceeding without L3 content.", exc)
        return []

    docs: list[Document] = []
    for r in results:
        url = r.get("url", "")
        title = r.get("title", "web result")
        content = r.get("content") or title
        if not content:
            continue
        docs.append(
            Document(
                page_content=content,
                metadata={
                    "source": f"Live trend search: {title}",
                    "url": url,
                    "layer": "L3",
                    "rule_id": f"L3-live-{hashlib.sha1(url.encode()).hexdigest()[:10]}",
                    "granularity": "live",
                },
            )
        )
    return docs


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
        res.l1 = retrieve_l1(kb, ctx, semantic_query=l3_query)
    if "L3" in layers:
        res.l3 = retrieve_l3(l3_query, k=k_l3)
    return res
