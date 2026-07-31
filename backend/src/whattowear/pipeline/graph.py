"""The styling pipeline as an explicit LangGraph `StateGraph`.

Node order: `parse_request -> gather_context -> style_retrieval ->
build_query -> wardrobe_retrieval -> generate_outfits -> score_and_rank ->
verify_grounding -> explain`, linear edges except the one conditional
branch to the opt-in engine path. `verify_grounding` is a post-generation
safety net (see `grounding.py`) — dropping any outfit whose items aren't
genuinely in the requester's wardrobe or the shared catalog, before
`explain` ever builds the response. Every node is a thin wrapper around an
existing, unchanged pure function (constitution Principle I) —
`context_assembler.py`, `query_builder.py`, `generator.py`, `cite.py` are
not rewritten here, just orchestrated. `style_retrieval` runs before
`wardrobe_retrieval` to preserve constitution Principle III (style
knowledge gates wardrobe retrieval) verbatim.

Deterministic pruning (`wardrobe_retrieval`) narrows what the LLM in
`generate_outfits` can even see; deterministic scoring/ranking
(`score_and_rank`, `scoring.combine.rank_outfits`) is the only thing that
orders the final result on every path. On the **grounded** (default) path,
the LLM still assembles/selects which items compose each candidate outfit
in `generate_outfits`, before that deterministic scoring ever runs —
selection is not deterministic there, only final ordering is (constitution
Principle II, v2.0.0; specs/007-ai-port/research.md §3 traces exactly why
the prior "the LLM never ranks" wording overclaimed and shouldn't be
carried forward). On the **engine** path, both selection (enumeration) and
ranking are deterministic; the LLM there only writes the rationale for a
pre-scored top-K choice.

DB coupling fix (specs/007-ai-port/research.md §1): `verify_grounding` used
to open its own `SessionLocal()` and call `crud.list_catalog_items`
directly — the third of the three documented coupling defects
(docs/legacy-ai-inventory.md §3). It, `gather_context` and
`generate_outfits` now take an injected `ports.ClosetRepository`, wired as
a closure at `build_graph()` time rather than threaded through
`GraphState` — a repository object in LangGraph's checkpointed state risks
breaking `PostgresSaver` serialization (memory/store.py's own note).

Dependency-inversion fix (research.md §2): `wardrobe_retrieval` used to
import `weather_appropriate` from `eval.properties`; it now imports from
`scoring.properties`, where the predicate actually lives now.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, TypedDict

from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph
from langsmith import traceable

from .. import categories
from ..memory import store as memory
from ..retrieval import advanced, baseline, hybrid
from ..retrieval.base import RetrievalResult
from ..schema import FORMALITY_ORDER, Context, Formality, SuggestResult, WardrobeItem
from ..scoring import score_outfits
from ..scoring.properties import weather_appropriate
from . import cite, context_assembler, engine, query_builder
from .generator import GenOutfit, GenOutput, GenRationale, generate
from .grounding import verify_outfit_grounding
from .validity import is_slot_complete as _is_slot_complete
from .validity import is_valid_combination as _is_valid_combination

if TYPE_CHECKING:
    from ..kb import KnowledgeBase
    from ..ports import ClosetRepository

Strategy = str  # "baseline" | "hybrid" | "advanced"

# Candidates are capped at this many items per slot before generation, so the
# combinatorial step downstream stays bounded regardless of closet size.
_CANDIDATES_PER_SLOT = 8

# Per-band item-level warmth ceiling used to prune obviously-unsuitable core
# items before generation ever sees them (mirrors weather_fitness's own
# per-band expectations — not a second, divergent threshold set).
_MAX_WARMTH_BY_BAND: dict[str, int] = {"warm": 2, "hot": 1}

# Ideal target warmth per band, used only to *rank* candidates within a slot
# before the per-slot cap below — distinct from _MAX_WARMTH_BY_BAND above,
# which is a hard-constraint ceiling for warm/hot only. This is a ranking
# target across all six bands and never excludes an item on its own.
_IDEAL_WARMTH_BY_BAND: dict[str, int] = {
    "freezing": 4,
    "cold": 3,
    "cool": 2,
    "mild": 2,
    "warm": 1,
    "hot": 0,
}

# Refinement deltas — per-occurrence adjustment to the hard-constraint bounds
# in wardrobe_retrieval, not to ctx itself.
_REFINEMENT_WARMTH_STEP = 2  # warmth floor added per "warmer" utterance
_REFINEMENT_FORMALITY_STEP = 1  # notches shifted down per "less formal" utterance
# schema.py's fixed warmth range (0-5) -- the range _REFINEMENT_WARMTH_STEP was
# implicitly calibrated against. Categories that can't reach 5 (footwear/
# accessories, a fixture-data reality: footwear tops out around warmth=3, most
# accessories sit at 0) get a floor SCALED to their own ceiling instead of
# either this flat absolute number or a blanket exemption (a flat floor of 2+
# per "warmer" silently excluded nearly all footwear/accessories, forcing the
# deterministic-fallback note far more than intended; the fix replaces the
# exemption with a per-category-relative floor, never a full pass-through,
# capped so a category's own warmest item always still passes).
_WARMTH_SCALE_REFERENCE = 5

_WARMER_KEYWORDS = ("warmer", "warm")
_LESS_FORMAL_KEYWORDS = ("less formal", "more casual", "casual")
_ALTERNATIVES_KEYWORDS = ("alternative", "different", "something else", "another option")


def _parse_refinement_intent(utterance: str) -> list[str]:
    """Deterministic keyword parsing (constitution Principle II — refinement
    intent gates the selection/ranking path the same way an occasion does,
    so it stays deterministic too)."""
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
    mood: str | None
    formality: Formality | None
    location: str | None
    temp_c: float | None
    strategy: Strategy
    thread_id: str
    user_id: str | None
    wardrobe: list[WardrobeItem] | None  # explicit override, bypassing repo load (eval/test_users.py)

    # Refinement state (persisted across invokes on the same thread_id by
    # the checkpointer); original_context is set once (turn 1) and never
    # overwritten, refinement_deltas accumulates, last_result is the most
    # recently returned SuggestResult.
    original_context: Context | None
    refinement_deltas: list[str]
    last_result: SuggestResult | None

    # Which selection approach this thread uses. Sticky across refinement
    # turns the same way original_context is.
    approach: str

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

    # generate_outfits output — only slot-complete outfits. Also set by the
    # engine path's engine_write node (mirrored from its final ScoredOutfit
    # selection) purely so explain()'s existing cite.build_result(...) call
    # needs zero changes for either path.
    generated: GenOutput

    # engine_enumerate_and_score output — top-6 deterministically scored
    # candidates offered to engine_write for selection-and-writing only.
    engine_shortlist: list

    # score_and_rank output — ranked, descending by rank_score. Also the
    # engine path's engine_write output (same key, so verify_grounding/
    # explain consume either path identically).
    scored_outfits: list

    # explain output
    result: SuggestResult
    note: str | None


def parse_request(state: GraphState) -> dict:
    """A continuing thread is detected by `original_context` already being
    present (set on turn 1 by `gather_context`, restored by the
    checkpointer on every later invoke of the same thread_id) — not a
    request-body flag. On a continuing thread, `occasion` carries the
    refinement utterance, keyword-parsed into deltas here rather than
    treated as a fresh occasion."""
    thread_id = state.get("thread_id") or str(uuid.uuid4())
    if state.get("original_context") is not None:
        new_deltas = _parse_refinement_intent(state["occasion"])
        deltas = [*state.get("refinement_deltas", []), *new_deltas]
        return {"thread_id": thread_id, "refinement_deltas": deltas}
    return {"thread_id": thread_id, "refinement_deltas": []}


@traceable(name="node.gather_context", run_type="chain")
def gather_context(state: GraphState, repo: ClosetRepository) -> dict:
    """On a refinement turn, rebuilds `ctx` from `original_context`'s own
    fields — never from the incoming request body, which carries the
    refinement utterance in `occasion` and leaves the rest unset (unstated
    constraints must be preserved, not dropped)."""
    original = state.get("original_context")
    if original is not None:
        ctx = context_assembler.assemble_context(
            original.occasion,
            mood=original.mood,
            formality=original.formality,
            temp_c=original.temp_c,
            wardrobe=state.get("wardrobe"),
            user_id=state.get("user_id"),
            repo=repo,
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
        repo=repo,
    )
    return {"ctx": ctx, "original_context": ctx}


@traceable(name="stage.retrieve", run_type="chain")
def _retrieve(kb: KnowledgeBase, ctx: Context, strategy: Strategy) -> RetrievalResult:
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
    from ..kb import get_kb  # lazy: kb.py lands in specs/007-ai-port Phase 11

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
    category ranges 0-5 like outerwear does."""
    ceilings: dict[str, int] = {}
    for item in wardrobe:
        group = categories.group_of(item.category)
        ceilings[group] = max(ceilings.get(group, 0), item.warmth)
    return ceilings


def wardrobe_retrieval(state: GraphState) -> dict:
    """Hard-constraint pruning (formality band, per-band warmth ceiling,
    season) before any combination step, capped at k=8 per slot. Reuses
    `scoring.properties`'s `weather_appropriate` predicate rather than a
    second, forked warmth check. `refinement_deltas` shift these same
    bounds — a "warmer"/"less formal" request never touches `ctx` itself,
    only what counts as fitting here. Each slot is sorted by fitness before
    the cap — the closet's original order must never decide which items
    survive."""
    ctx = state["ctx"]
    deltas = state.get("refinement_deltas", [])
    category_ceilings = _category_warmth_ceiling(ctx.wardrobe)
    candidates: dict[str, list[WardrobeItem]] = {}
    for item in ctx.wardrobe:
        if not _item_fits_hard_constraints(item, ctx, deltas, category_ceilings):
            continue
        slot = categories.group_of(item.category)
        candidates.setdefault(slot, []).append(item)

    candidates = {
        slot: sorted(items, key=lambda item: _slot_fitness_key(item, ctx))[:_CANDIDATES_PER_SLOT]
        for slot, items in candidates.items()
    }
    return {"candidates": candidates}


def _slot_fitness_key(item: WardrobeItem, ctx: Context) -> tuple[int, int]:
    """Ascending-badness sort key: exact formality match and ideal-for-weather
    warmth sort first, so `wardrobe_retrieval`'s per-slot cap can no longer
    silently drop the best-fitting item just because it wasn't early in
    closet order. `ctx.formality` is always populated by the time this runs
    — `context_assembler.assemble_context` already resolves it (inferring
    from free-text occasion if unset) before `ctx` is ever constructed, on
    every path including refinement — so no fallback inference is needed
    here."""
    formality_distance = abs(FORMALITY_ORDER[item.formality] - FORMALITY_ORDER[ctx.formality])
    warmth_distance = abs(item.warmth - _IDEAL_WARMTH_BY_BAND[ctx.temp_band]) if ctx.temp_band else 0
    return formality_distance, warmth_distance


def _item_fits_hard_constraints(
    item: WardrobeItem,
    ctx: Context,
    deltas: list[str] | None = None,
    category_ceilings: dict[str, int] | None = None,
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
            # original level, which wouldn't reliably lower the mean.
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
        # Floor scales to this category's own achievable ceiling rather
        # than either a flat absolute number (the original bug) or a
        # blanket exemption (the prior fix) — capped at the ceiling
        # itself, so a category is never fully excluded by its own floor
        # even after many "warmer" requests (a zero-ceiling category, e.g.
        # accessories with no warmth variation, always computes a floor of
        # 0 and never gates at all, which is correct).
        group = categories.group_of(item.category)
        ceilings = category_ceilings if category_ceilings is not None else _category_warmth_ceiling(ctx.wardrobe)
        ceiling = ceilings.get(group, _WARMTH_SCALE_REFERENCE)
        floor = min(ceiling, round(warmer_count * _REFINEMENT_WARMTH_STEP * ceiling / _WARMTH_SCALE_REFERENCE))
        if item.warmth < floor:
            return False
    return True


@traceable(name="node.generate_outfits", run_type="chain")
def generate_outfits(state: GraphState, repo: ClosetRepository) -> dict:
    ctx = state["ctx"]
    candidates = state["candidates"]
    pruned_ids = {it.id for items in candidates.values() for it in items}
    pruned_wardrobe = [it for it in ctx.wardrobe if it.id in pruned_ids]
    pruned_ctx = ctx.model_copy(update={"wardrobe": pruned_wardrobe})

    note = memory.profile_note(ctx.user_id, repo)
    gen = generate(pruned_ctx, state["retrieval"], profile_note=note)

    wardrobe_by_id = {it.id: it for it in ctx.wardrobe}
    complete: list[GenOutfit] = [
        o
        for o in gen.outfits
        if _is_slot_complete(o.items, wardrobe_by_id) and _is_valid_combination(o.items, wardrobe_by_id)
    ]

    last_result = state.get("last_result")
    if "alternatives" in state.get("refinement_deltas", []) and last_result is not None:
        # a different set than what was already shown, not a fresh
        # generation that happens to repeat it.
        used_sets = {frozenset(o.items) for o in last_result.outfits}
        complete = [o for o in complete if frozenset(o.items) not in used_sets]

    return {"generated": GenOutput(outfits=complete)}


def score_and_rank(state: GraphState) -> dict:
    ctx = state["ctx"]
    wardrobe_by_id = {it.id: it for it in ctx.wardrobe}
    ranked = score_outfits(state["generated"].outfits, wardrobe_by_id, ctx)
    return {"scored_outfits": ranked}


@traceable(name="node.engine_enumerate_and_score", run_type="chain")
def engine_enumerate_and_score(state: GraphState) -> dict:
    """Deterministic enumeration + scoring for the engine approach.
    `require_outerwear` reuses the same freezing/cold band split
    `_MAX_WARMTH_BY_BAND` already encodes for the hot/warm side — no new
    threshold. Scoring is the exact same `scoring.score_outfits` call
    `score_and_rank` uses above (constitution Principle V) — never a
    second scoring implementation. Both selection (enumeration) and
    ranking are fully deterministic on this path — the opt-in path where
    Principle II holds unqualified."""
    ctx = state["ctx"]
    require_outerwear = ctx.temp_band in {"freezing", "cold"}
    combos = engine.enumerate_outfits(state["candidates"], require_outerwear=require_outerwear)
    wardrobe_by_id = {it.id: it for it in ctx.wardrobe}
    unscored = [GenOutfit(items=combo, rationale=[]) for combo in combos]
    ranked = score_outfits(unscored, wardrobe_by_id, ctx)
    return {"engine_shortlist": ranked[: engine._SHORTLIST_SIZE]}


@traceable(name="node.engine_write", run_type="chain")
def engine_write_node(state: GraphState) -> dict:
    """Wraps `engine.engine_write` (the engine path's one LLM call) and
    mirrors its result into both `scored_outfits` (what `verify_grounding`/
    `explain` already read from `score_and_rank`) and `generated` (what
    `explain`'s `cite.build_result` call needs for `sources`) — so neither
    downstream node requires an engine-specific branch."""
    ctx = state["ctx"]
    final = engine.engine_write(state["engine_shortlist"], ctx, state["retrieval"])
    generated = GenOutput(
        outfits=[
            GenOutfit(items=o.items, rationale=[GenRationale(text=r.text, cites=r.cites) for r in o.rationale])
            for o in final
        ]
    )
    return {"scored_outfits": final, "generated": generated}


@traceable(name="node.verify_grounding", run_type="chain")
def verify_grounding(state: GraphState, repo: ClosetRepository) -> dict:
    """Drop any outfit referencing an item id that doesn't genuinely exist
    in the requester's wardrobe or the shared catalog, before the response
    is ever built (`explain`). A safety net on top of, not instead of, the
    existing deterministic selection guarantee — see `pipeline/
    grounding.py`."""
    ctx = state["ctx"]
    wardrobe_by_id = {it.id: it for it in ctx.wardrobe}
    catalog_ids = {it.id for it in repo.list_catalog_items()}
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
        # the refinement's tightened bounds left nothing — return the best
        # available (prior) result rather than an empty one.
        result = last_result
        note = "Couldn't fully satisfy that request from your closet — showing your previous suggestions instead."
    elif not scored:
        note = "Your closet doesn't have enough items to assemble an outfit for this request."
    elif len(scored) < 3:
        note = f"Only found {len(scored)} outfit option(s) — add more items to your closet for more variety."

    return {"result": result, "note": note, "last_result": result}


def _route_by_approach(state: GraphState) -> str:
    """`"engine"` routes to the deterministic-selection path; every other
    value (including absent, the default) routes to the grounded
    generate-then-rank path."""
    return "engine" if state.get("approach") == "engine" else "grounded"


def build_graph(repo: ClosetRepository) -> StateGraph:
    """`repo` is closed over by the three nodes that need persisted-data
    access (`gather_context`, `generate_outfits`, `verify_grounding`) —
    never threaded through `GraphState` (research.md §1's DI fix note)."""
    graph = StateGraph(GraphState)
    graph.add_node("parse_request", parse_request)
    graph.add_node("gather_context", lambda state: gather_context(state, repo))
    graph.add_node("style_retrieval", style_retrieval)
    graph.add_node("build_query", build_query)
    graph.add_node("wardrobe_retrieval", wardrobe_retrieval)
    graph.add_node("generate_outfits", lambda state: generate_outfits(state, repo))
    graph.add_node("score_and_rank", score_and_rank)
    graph.add_node("engine_enumerate_and_score", engine_enumerate_and_score)
    graph.add_node("engine_write", engine_write_node)
    graph.add_node("verify_grounding", lambda state: verify_grounding(state, repo))
    graph.add_node("explain", explain)

    graph.set_entry_point("parse_request")
    graph.add_edge("parse_request", "gather_context")
    graph.add_edge("gather_context", "style_retrieval")
    graph.add_edge("style_retrieval", "build_query")
    graph.add_edge("build_query", "wardrobe_retrieval")
    graph.add_conditional_edges(
        "wardrobe_retrieval",
        _route_by_approach,
        {"engine": "engine_enumerate_and_score", "grounded": "generate_outfits"},
    )
    graph.add_edge("generate_outfits", "score_and_rank")
    graph.add_edge("engine_enumerate_and_score", "engine_write")
    graph.add_edge("score_and_rank", "verify_grounding")
    graph.add_edge("engine_write", "verify_grounding")
    graph.add_edge("verify_grounding", "explain")
    return graph


def compile_graph(repo: ClosetRepository) -> CompiledStateGraph:
    return build_graph(repo).compile(checkpointer=memory.get_checkpointer())


_compiled: CompiledStateGraph | None = None


def get_compiled_graph(repo: ClosetRepository) -> CompiledStateGraph:
    """Process-wide singleton, mirroring `kb.get_kb()`'s lazy-build
    pattern. `repo` is only consulted on the FIRST call — later calls
    return the already-compiled graph regardless of what's passed, since
    the repo is baked into the closures at compile time. Callers (the eval
    harness, the future API layer) are expected to pass the same repo
    every time within one process."""
    global _compiled
    if _compiled is None:
        _compiled = compile_graph(repo)
    return _compiled
