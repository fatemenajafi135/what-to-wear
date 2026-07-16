"""Phase 3: the styling pipeline as an explicit LangGraph `StateGraph`.

Node order (research.md §1): `parse_request -> gather_context ->
style_retrieval -> build_query -> wardrobe_retrieval -> generate_outfits ->
score_and_rank -> explain`, linear edges, no branching. Every node is a thin
wrapper around an existing, unchanged pure function (constitution Principle
I) — `context_assembler.py`, `query_builder.py`, `generator.py`, `cite.py`
are not rewritten here, just orchestrated. `style_retrieval` runs before
`wardrobe_retrieval` to preserve constitution Principle III (style knowledge
gates wardrobe retrieval) verbatim.

Deterministic pruning (`wardrobe_retrieval`) narrows what the LLM in
`generate_outfits` can even see; deterministic scoring/ranking
(`score_and_rank`, `scoring/combine.rank_outfits`) is the only thing that
orders the final result — the LLM never ranks (constitution Principle II).
"""

from __future__ import annotations

import uuid
from typing import Optional, TypedDict

from langgraph.graph import StateGraph
from langsmith import traceable

from .. import categories
from ..eval.properties import weather_appropriate
from ..kb import get_kb
from ..memory import store as memory
from ..retrieval import advanced, baseline, hybrid
from ..retrieval.base import RetrievalResult
from ..schema import FORMALITY_ORDER, Context, Formality, SuggestResult, WardrobeItem
from ..scoring import score_outfits
from . import cite, context_assembler, query_builder
from .generator import GenOutfit, GenOutput, generate

Strategy = str  # "baseline" | "hybrid" | "advanced"

# Candidates are capped at this many items per slot before generation, so the
# combinatorial step downstream stays bounded regardless of closet size
# (research.md §4, FR-014).
_CANDIDATES_PER_SLOT = 8

# Per-band item-level warmth ceiling used to prune obviously-unsuitable core
# items before generation ever sees them (mirrors weather_fitness's own
# per-band expectations — not a second, divergent threshold set).
_MAX_WARMTH_BY_BAND: dict[str, int] = {"warm": 2, "hot": 1}


class GraphState(TypedDict, total=False):
    # parse_request output — normalized request fields
    occasion: str
    mood: Optional[str]
    formality: Optional[Formality]
    location: Optional[str]
    temp_c: Optional[float]
    strategy: Strategy
    thread_id: str
    user_id: Optional[str]

    # gather_context output
    ctx: Context

    # style_retrieval output
    retrieval: RetrievalResult

    # build_query output (informational — the queries retrieval already used
    # internally via _retrieve; kept in state for tracing/observability)
    naive_query: str
    l3_query: str

    # wardrobe_retrieval output — pruned, capped candidates per category slot
    candidates: dict[str, list[WardrobeItem]]

    # generate_outfits output — only slot-complete outfits (FR-011)
    generated: GenOutput

    # score_and_rank output — ranked, descending by rank_score
    scored_outfits: list

    # explain output
    result: SuggestResult
    note: Optional[str]


def _is_slot_complete(items: list[str], wardrobe_by_id: dict[str, WardrobeItem]) -> bool:
    """A complete outfit covers the body: top-or-full_body, bottom-or-
    full_body, and footwear. Missing any -> drop the outfit (FR-011), never
    fill from the catalog."""
    groups = {categories.group_of(wardrobe_by_id[i].category) for i in items if i in wardrobe_by_id}
    has_top_half = "top" in groups or "full_body" in groups
    has_bottom_half = "bottom" in groups or "full_body" in groups
    has_footwear = "footwear" in groups
    return has_top_half and has_bottom_half and has_footwear


def parse_request(state: GraphState) -> dict:
    """New-request parsing (Phase 3). When `thread_id` is present this is
    where Phase 4 will branch into refinement-intent parsing instead — not
    this phase's concern."""
    thread_id = state.get("thread_id") or str(uuid.uuid4())
    return {"thread_id": thread_id}


@traceable(name="node.gather_context", run_type="chain")
def gather_context(state: GraphState) -> dict:
    ctx = context_assembler.assemble_context(
        state["occasion"],
        mood=state.get("mood"),
        formality=state.get("formality"),
        location=state.get("location"),
        temp_c=state.get("temp_c"),
        user_id=state.get("user_id"),
    )
    return {"ctx": ctx}


@traceable(name="stage.retrieve", run_type="chain")
def _retrieve(kb, ctx: Context, strategy: Strategy) -> RetrievalResult:
    """Moved from pipeline/run.py unchanged (that module is retired at
    T037a once /suggest is verified equivalent — this is the one place its
    KB-dispatch logic now lives, not a second, forked copy)."""
    layers = query_builder.route(ctx)
    if strategy == "baseline":
        return baseline.retrieve(kb, query_builder.naive_query(ctx))
    l3q = query_builder.l3_query(ctx)
    if strategy == "hybrid":
        return hybrid.retrieve(kb, ctx, layers, l3q)
    if strategy == "advanced":
        return advanced.retrieve(kb, ctx, layers, l3q)
    raise ValueError(f"unknown strategy: {strategy}")


@traceable(name="node.style_retrieval", run_type="chain")
def style_retrieval(state: GraphState) -> dict:
    kb = get_kb()
    retrieval = _retrieve(kb, state["ctx"], state.get("strategy", "advanced"))
    return {"retrieval": retrieval}


def build_query(state: GraphState) -> dict:
    """Informational only — `style_retrieval`'s `_retrieve` call already
    builds and uses these queries internally (query_builder.py is not
    rewritten); this node re-derives them via the same pure functions purely
    so they're visible in graph state/tracing."""
    ctx = state["ctx"]
    return {"naive_query": query_builder.naive_query(ctx), "l3_query": query_builder.l3_query(ctx)}


def wardrobe_retrieval(state: GraphState) -> dict:
    """Hard-constraint pruning (formality band, per-band warmth ceiling,
    season) before any combination step, capped at k=8 per slot (FR-014).
    Reuses eval/properties.py's weather_appropriate predicate rather than a
    second, forked warmth check."""
    ctx = state["ctx"]
    candidates: dict[str, list[WardrobeItem]] = {}
    for item in ctx.wardrobe:
        if not _item_fits_hard_constraints(item, ctx):
            continue
        slot = categories.group_of(item.category)
        candidates.setdefault(slot, []).append(item)

    candidates = {slot: items[:_CANDIDATES_PER_SLOT] for slot, items in candidates.items()}
    return {"candidates": candidates}


def _item_fits_hard_constraints(item: WardrobeItem, ctx: Context) -> bool:
    if ctx.formality and FORMALITY_ORDER[item.formality] < FORMALITY_ORDER[ctx.formality] - 1:
        return False
    if ctx.season and item.season and ctx.season not in item.season:
        return False
    if ctx.temp_band and ctx.temp_band in _MAX_WARMTH_BY_BAND:
        max_warmth = _MAX_WARMTH_BY_BAND[ctx.temp_band]
        if not weather_appropriate([item.id], {item.id: item}, {"max_warmth": max_warmth}):
            return False
    return True


@traceable(name="node.generate_outfits", run_type="chain")
def generate_outfits(state: GraphState) -> dict:
    ctx = state["ctx"]
    candidates = state["candidates"]
    pruned_ids = {it.id for items in candidates.values() for it in items}
    pruned_wardrobe = [it for it in ctx.wardrobe if it.id in pruned_ids]
    pruned_ctx = ctx.model_copy(update={"wardrobe": pruned_wardrobe})

    note = memory.profile_note(ctx.user_id)
    gen = generate(pruned_ctx, state["retrieval"], profile_note=note)

    wardrobe_by_id = {it.id: it for it in ctx.wardrobe}
    complete: list[GenOutfit] = [o for o in gen.outfits if _is_slot_complete(o.items, wardrobe_by_id)]
    return {"generated": GenOutput(outfits=complete)}


def score_and_rank(state: GraphState) -> dict:
    ctx = state["ctx"]
    wardrobe_by_id = {it.id: it for it in ctx.wardrobe}
    ranked = score_outfits(state["generated"].outfits, wardrobe_by_id, ctx)
    return {"scored_outfits": ranked}


@traceable(name="node.explain", run_type="chain")
def explain(state: GraphState) -> dict:
    ctx = state["ctx"]
    scored = state["scored_outfits"]

    base = cite.build_result(ctx, state["generated"], state["retrieval"])
    result = SuggestResult(outfits=scored, sources=base.sources, context=ctx)

    memory.remember_interaction(
        ctx.user_id, state["thread_id"],
        f"{ctx.occasion}/{ctx.formality}/{ctx.temp_band} -> {[o.items for o in scored]}",
    )

    note = None
    if not scored:
        note = "Your closet doesn't have enough items to assemble an outfit for this request."
    elif len(scored) < 3:
        note = f"Only found {len(scored)} outfit option(s) — add more items to your closet for more variety."

    return {"result": result, "note": note}


def build_graph() -> StateGraph:
    graph = StateGraph(GraphState)
    graph.add_node("parse_request", parse_request)
    graph.add_node("gather_context", gather_context)
    graph.add_node("style_retrieval", style_retrieval)
    graph.add_node("build_query", build_query)
    graph.add_node("wardrobe_retrieval", wardrobe_retrieval)
    graph.add_node("generate_outfits", generate_outfits)
    graph.add_node("score_and_rank", score_and_rank)
    graph.add_node("explain", explain)

    graph.set_entry_point("parse_request")
    graph.add_edge("parse_request", "gather_context")
    graph.add_edge("gather_context", "style_retrieval")
    graph.add_edge("style_retrieval", "build_query")
    graph.add_edge("build_query", "wardrobe_retrieval")
    graph.add_edge("wardrobe_retrieval", "generate_outfits")
    graph.add_edge("generate_outfits", "score_and_rank")
    graph.add_edge("score_and_rank", "explain")
    return graph


def compile_graph():
    return build_graph().compile(checkpointer=memory.get_checkpointer())


_compiled = None


def get_compiled_graph():
    """Process-wide singleton, mirroring kb.get_kb()'s lazy-build pattern."""
    global _compiled
    if _compiled is None:
        _compiled = compile_graph()
    return _compiled
