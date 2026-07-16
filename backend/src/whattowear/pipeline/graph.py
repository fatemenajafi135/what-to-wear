"""Phase 3: the styling pipeline as an explicit LangGraph `StateGraph`.

Node order (research.md §1): `parse_request -> gather_context ->
style_retrieval -> build_query -> wardrobe_retrieval -> generate_outfits ->
score_and_rank -> verify_grounding -> explain`, linear edges, no branching.
`verify_grounding` (Feature 005 US2/FR-003-005) is a post-generation safety
net — see `grounding.py` — dropping any outfit whose items aren't genuinely
in the requester's wardrobe or the shared catalog, before `explain` ever
builds the response. Every node is a thin
wrapper around an existing, unchanged pure function (constitution Principle
I) — `context_assembler.py`, `query_builder.py`, `generator.py`, `cite.py`
are not rewritten here, just orchestrated. `style_retrieval` runs before
`wardrobe_retrieval` to preserve constitution Principle III (style knowledge
gates wardrobe retrieval) verbatim.

Deterministic pruning (`wardrobe_retrieval`) narrows what the LLM in
`generate_outfits` can even see; deterministic scoring/ranking
(`score_and_rank`, `scoring/combine.rank_outfits`) is the only thing that
orders the final result — the LLM never ranks (constitution Principle II).

Phase 4 (refinement, US4): `RefinementTurn` (data-model.md) isn't a separate
stored object — it's exactly the checkpointer-persisted `GraphState` fields
`original_context`/`last_result`/`refinement_deltas`, which LangGraph already
carries across invokes on the same `thread_id` for any key a node doesn't
return a fresh value for. `parse_request` detects a continuing thread by
`original_context` already being present (set once, on the first turn, by
`gather_context`) and keyword-parses the incoming `occasion` string (which
carries the refinement utterance, not a fresh occasion, per
contracts/suggest.md) into deltas instead. `gather_context` then rebuilds
`ctx` from `original_context`'s fields, never the refinement utterance
(FR-013). `wardrobe_retrieval` shifts its pruning bounds per delta (FR-013);
`generate_outfits` drops outfits repeated from `last_result` for an
"alternatives" request (FR-012); `explain` falls back to `last_result` with
a `note` if a refinement's tightened bounds leave nothing (FR-015).
"""

from __future__ import annotations

import uuid
from typing import Optional, TypedDict

from langgraph.graph import StateGraph
from langsmith import traceable

from .. import categories, crud
from ..db import SessionLocal
from ..eval.properties import weather_appropriate
from ..kb import get_kb
from ..memory import store as memory
from ..retrieval import advanced, baseline, hybrid
from ..retrieval.base import RetrievalResult
from ..schema import FORMALITY_ORDER, Context, Formality, SuggestResult, WardrobeItem
from ..scoring import score_outfits
from . import cite, context_assembler, query_builder
from .generator import GenOutfit, GenOutput, generate
from .grounding import verify_outfit_grounding

Strategy = str  # "baseline" | "hybrid" | "advanced"

# Candidates are capped at this many items per slot before generation, so the
# combinatorial step downstream stays bounded regardless of closet size
# (research.md §4, FR-014).
_CANDIDATES_PER_SLOT = 8

# Per-band item-level warmth ceiling used to prune obviously-unsuitable core
# items before generation ever sees them (mirrors weather_fitness's own
# per-band expectations — not a second, divergent threshold set).
_MAX_WARMTH_BY_BAND: dict[str, int] = {"warm": 2, "hot": 1}

# Phase 4 refinement deltas (FR-013) — per-occurrence adjustment to the
# hard-constraint bounds in wardrobe_retrieval, not to ctx itself.
_REFINEMENT_WARMTH_STEP = 2  # warmth floor added per "warmer" utterance
_REFINEMENT_FORMALITY_STEP = 1  # notches shifted down per "less formal" utterance
# schema.py's fixed warmth range (0-5) -- the range _REFINEMENT_WARMTH_STEP was
# implicitly calibrated against. Categories that can't reach 5 (footwear/
# accessories, a fixture-data reality: footwear tops out around warmth=3, most
# accessories sit at 0) get a floor SCALED to their own ceiling instead of
# either this flat absolute number or a blanket exemption (Feature 007 Task C
# -- a flat floor of 2+ per "warmer" silently excluded nearly all footwear/
# accessories, forcing the FR-015 fallback far more than intended; the fix
# replaces the exemption with a per-category-relative floor, never a full
# pass-through, capped so a category's own warmest item always still passes).
_WARMTH_SCALE_REFERENCE = 5

_WARMER_KEYWORDS = ("warmer", "warm")
_LESS_FORMAL_KEYWORDS = ("less formal", "more casual", "casual")
_ALTERNATIVES_KEYWORDS = ("alternative", "different", "something else", "another option")


def _parse_refinement_intent(utterance: str) -> list[str]:
    """Deterministic keyword parsing (constitution Principle II — no LLM in
    the selection/ranking path, and refinement intent gates that path the
    same way an occasion does, so it stays deterministic too)."""
    text = utterance.lower()
    deltas = []
    if any(k in text for k in _WARMER_KEYWORDS):
        deltas.append("warmer")
    if any(k in text for k in _LESS_FORMAL_KEYWORDS):
        deltas.append("less_formal")
    if any(k in text for k in _ALTERNATIVES_KEYWORDS):
        deltas.append("alternatives")
    return deltas


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
    wardrobe: Optional[list[WardrobeItem]]  # explicit override, bypassing DB load (eval/test_users.py)

    # Phase 4 refinement state (RefinementTurn, data-model.md) — persisted
    # across invokes on the same thread_id by the checkpointer; original_context
    # is set once (turn 1) and never overwritten, refinement_deltas accumulates,
    # last_result is the most recently returned SuggestResult.
    original_context: Optional[Context]
    refinement_deltas: list[str]
    last_result: Optional[SuggestResult]

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
    """A continuing thread is detected by `original_context` already being
    present (set on turn 1 by `gather_context`, restored by the checkpointer
    on every later invoke of the same thread_id) — not a request-body flag.
    On a continuing thread, `occasion` carries the refinement utterance
    (contracts/suggest.md), keyword-parsed into deltas here rather than
    treated as a fresh occasion."""
    thread_id = state.get("thread_id") or str(uuid.uuid4())
    if state.get("original_context") is not None:
        new_deltas = _parse_refinement_intent(state["occasion"])
        deltas = [*state.get("refinement_deltas", []), *new_deltas]
        return {"thread_id": thread_id, "refinement_deltas": deltas}
    return {"thread_id": thread_id, "refinement_deltas": []}


@traceable(name="node.gather_context", run_type="chain")
def gather_context(state: GraphState) -> dict:
    """On a refinement turn, rebuilds `ctx` from `original_context`'s own
    fields — never from the incoming request body, which carries the
    refinement utterance in `occasion` and leaves the rest unset
    (FR-013: unstated constraints must be preserved, not dropped)."""
    original = state.get("original_context")
    if original is not None:
        ctx = context_assembler.assemble_context(
            original.occasion,
            mood=original.mood,
            formality=original.formality,
            temp_c=original.temp_c,
            wardrobe=state.get("wardrobe"),
            user_id=state.get("user_id"),
        )
        return {"ctx": ctx}

    ctx = context_assembler.assemble_context(
        state["occasion"],
        mood=state.get("mood"),
        formality=state.get("formality"),
        location=state.get("location"),
        temp_c=state.get("temp_c"),
        wardrobe=state.get("wardrobe"),
        user_id=state.get("user_id"),
    )
    return {"ctx": ctx, "original_context": ctx}


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


def _category_warmth_ceiling(wardrobe: list[WardrobeItem]) -> dict[str, int]:
    """Each category group's own achievable warmth ceiling in this closet —
    what the "warmer" floor (below) scales against instead of assuming every
    category ranges 0-5 like outerwear does (Feature 007 Task C)."""
    ceilings: dict[str, int] = {}
    for item in wardrobe:
        group = categories.group_of(item.category)
        ceilings[group] = max(ceilings.get(group, 0), item.warmth)
    return ceilings


def wardrobe_retrieval(state: GraphState) -> dict:
    """Hard-constraint pruning (formality band, per-band warmth ceiling,
    season) before any combination step, capped at k=8 per slot (FR-014).
    Reuses eval/properties.py's weather_appropriate predicate rather than a
    second, forked warmth check. `refinement_deltas` (Phase 4) shift these
    same bounds — a "warmer"/"less formal" request never touches `ctx`
    itself (FR-013), only what counts as fitting here."""
    ctx = state["ctx"]
    deltas = state.get("refinement_deltas", [])
    category_ceilings = _category_warmth_ceiling(ctx.wardrobe)
    candidates: dict[str, list[WardrobeItem]] = {}
    for item in ctx.wardrobe:
        if not _item_fits_hard_constraints(item, ctx, deltas, category_ceilings):
            continue
        slot = categories.group_of(item.category)
        candidates.setdefault(slot, []).append(item)

    candidates = {slot: items[:_CANDIDATES_PER_SLOT] for slot, items in candidates.items()}
    return {"candidates": candidates}


def _item_fits_hard_constraints(
    item: WardrobeItem,
    ctx: Context,
    deltas: Optional[list[str]] = None,
    category_ceilings: Optional[dict[str, int]] = None,
) -> bool:
    deltas = deltas or []
    less_formal_count = deltas.count("less_formal")
    warmer_count = deltas.count("warmer")

    if ctx.formality:
        base_notch = FORMALITY_ORDER[ctx.formality]
        item_notch = FORMALITY_ORDER[item.formality]
        if less_formal_count:
            # shift the whole acceptable window down, don't just raise the
            # ceiling — a bare ceiling bump would still admit items at the
            # original level, which wouldn't reliably lower the mean (SC-007).
            min_notch = base_notch - 1 - less_formal_count
            max_notch = base_notch - less_formal_count
            if item_notch < min_notch or item_notch > max_notch:
                return False
        elif item_notch < base_notch - 1:
            return False
    if ctx.season and item.season and ctx.season not in item.season:
        return False
    if ctx.temp_band and ctx.temp_band in _MAX_WARMTH_BY_BAND:
        max_warmth = _MAX_WARMTH_BY_BAND[ctx.temp_band]
        if not weather_appropriate([item.id], {item.id: item}, {"max_warmth": max_warmth}):
            return False
    if warmer_count:
        # Floor scales to this category's own achievable ceiling (Feature 007
        # Task C) rather than either a flat absolute number (the original
        # bug) or a blanket exemption (the prior fix) — capped at the
        # ceiling itself, so a category is never fully excluded by its own
        # floor even after many "warmer" requests (a zero-ceiling category,
        # e.g. accessories with no warmth variation, always computes a
        # floor of 0 and never gates at all, which is correct).
        group = categories.group_of(item.category)
        ceilings = category_ceilings if category_ceilings is not None else _category_warmth_ceiling(ctx.wardrobe)
        ceiling = ceilings.get(group, _WARMTH_SCALE_REFERENCE)
        floor = min(ceiling, round(warmer_count * _REFINEMENT_WARMTH_STEP * ceiling / _WARMTH_SCALE_REFERENCE))
        if item.warmth < floor:
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

    last_result = state.get("last_result")
    if "alternatives" in state.get("refinement_deltas", []) and last_result is not None:
        # FR-012: a different set than what was already shown, not a fresh
        # generation that happens to repeat it.
        used_sets = {frozenset(o.items) for o in last_result.outfits}
        complete = [o for o in complete if frozenset(o.items) not in used_sets]

    return {"generated": GenOutput(outfits=complete)}


def score_and_rank(state: GraphState) -> dict:
    ctx = state["ctx"]
    wardrobe_by_id = {it.id: it for it in ctx.wardrobe}
    ranked = score_outfits(state["generated"].outfits, wardrobe_by_id, ctx)
    return {"scored_outfits": ranked}


@traceable(name="node.verify_grounding", run_type="chain")
def verify_grounding(state: GraphState) -> dict:
    """Feature 005 US2/FR-003-005: drop any outfit referencing an item id
    that doesn't genuinely exist in the requester's wardrobe or the shared
    catalog, before the response is ever built (`explain`). A safety net on
    top of, not instead of, the existing deterministic selection guarantee —
    see pipeline/grounding.py."""
    ctx = state["ctx"]
    wardrobe_by_id = {it.id: it for it in ctx.wardrobe}
    with SessionLocal() as session:
        catalog_ids = {it.id for it in crud.list_catalog_items(session)}
    verified = [
        outfit
        for outfit in state["scored_outfits"]
        if verify_outfit_grounding(outfit.items, wardrobe_by_id, catalog_ids)
    ]
    return {"scored_outfits": verified}


@traceable(name="node.explain", run_type="chain")
def explain(state: GraphState) -> dict:
    ctx = state["ctx"]
    scored = state["scored_outfits"]
    deltas = state.get("refinement_deltas", [])
    last_result = state.get("last_result")

    base = cite.build_result(ctx, state["generated"], state["retrieval"])
    result = SuggestResult(outfits=scored, sources=base.sources, context=ctx)

    memory.remember_interaction(
        ctx.user_id,
        state["thread_id"],
        f"{ctx.occasion}/{ctx.formality}/{ctx.temp_band} -> {[o.items for o in scored]}",
    )

    note = None
    if not scored and deltas and last_result is not None:
        # FR-015: the refinement's tightened bounds left nothing — return
        # the best available (prior) result rather than an empty one.
        result = last_result
        note = "Couldn't fully satisfy that request from your closet — showing your previous suggestions instead."
    elif not scored:
        note = "Your closet doesn't have enough items to assemble an outfit for this request."
    elif len(scored) < 3:
        note = f"Only found {len(scored)} outfit option(s) — add more items to your closet for more variety."

    return {"result": result, "note": note, "last_result": result}


def build_graph() -> StateGraph:
    graph = StateGraph(GraphState)
    graph.add_node("parse_request", parse_request)
    graph.add_node("gather_context", gather_context)
    graph.add_node("style_retrieval", style_retrieval)
    graph.add_node("build_query", build_query)
    graph.add_node("wardrobe_retrieval", wardrobe_retrieval)
    graph.add_node("generate_outfits", generate_outfits)
    graph.add_node("score_and_rank", score_and_rank)
    graph.add_node("verify_grounding", verify_grounding)
    graph.add_node("explain", explain)

    graph.set_entry_point("parse_request")
    graph.add_edge("parse_request", "gather_context")
    graph.add_edge("gather_context", "style_retrieval")
    graph.add_edge("style_retrieval", "build_query")
    graph.add_edge("build_query", "wardrobe_retrieval")
    graph.add_edge("wardrobe_retrieval", "generate_outfits")
    graph.add_edge("generate_outfits", "score_and_rank")
    graph.add_edge("score_and_rank", "verify_grounding")
    graph.add_edge("verify_grounding", "explain")
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
