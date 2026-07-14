"""The stable entrypoint: `recommend(...) -> OutfitResult`.

This is the single interface every downstream surface calls (test API, Demo Day
UI, MCP tool). It runs the deterministic 5-stage pipeline and wires in the memory
component.

`run_pipeline(...)` exposes the intermediate stages (context, retrieval, raw
generation) for the eval harness; `recommend(...)` is the thin public wrapper.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Optional

from langsmith import traceable

from ..kb import get_kb
from ..memory import store as memory
from ..retrieval import advanced, baseline, hybrid
from ..retrieval.base import RetrievalResult
from ..schema import Context, Formality, OutfitResult, WardrobeItem
from . import cite, context_assembler, query_builder
from .generator import GenOutput, generate

Strategy = str  # "baseline" | "hybrid" | "advanced"


@dataclass
class PipelineRun:
    ctx: Context
    retrieval: RetrievalResult
    generation: GenOutput
    result: OutfitResult


@traceable(name="stage.retrieve", run_type="chain")
def _retrieve(kb, ctx: Context, strategy: Strategy) -> RetrievalResult:
    layers = query_builder.route(ctx)
    if strategy == "baseline":
        return baseline.retrieve(kb, query_builder.naive_query(ctx))
    l3q = query_builder.l3_query(ctx)
    if strategy == "hybrid":
        return hybrid.retrieve(kb, ctx, layers, l3q)
    if strategy == "advanced":
        return advanced.retrieve(kb, ctx, layers, l3q)
    raise ValueError(f"unknown strategy: {strategy}")


@traceable(name="whattowear.recommend", run_type="chain")
def run_pipeline(
    occasion: str,
    *,
    mood: Optional[str] = None,
    formality: Optional[Formality] = None,
    location: Optional[str] = None,
    temp_c: Optional[float] = None,
    wardrobe: Optional[list[WardrobeItem]] = None,
    user_id: Optional[str] = None,
    thread_id: Optional[str] = None,
    strategy: Strategy = "advanced",
) -> PipelineRun:
    kb = get_kb()
    thread_id = thread_id or str(uuid.uuid4())

    # stage 1
    ctx = context_assembler.assemble_context(
        occasion, mood=mood, formality=formality, location=location,
        temp_c=temp_c, wardrobe=wardrobe, user_id=user_id,
    )
    # stages 2-3
    retrieval = _retrieve(kb, ctx, strategy)
    # memory: soft preference note
    note = memory.profile_note(user_id)
    # stage 4
    gen = generate(ctx, retrieval, profile_note=note)
    # stage 5
    result = cite.build_result(ctx, gen, retrieval)

    # memory: record the interaction (short-term thread history)
    memory.remember_interaction(
        user_id, thread_id,
        f"{ctx.occasion}/{ctx.formality}/{ctx.temp_band} -> {[o.items for o in result.outfits]}",
    )
    return PipelineRun(ctx=ctx, retrieval=retrieval, generation=gen, result=result)


def recommend(occasion: str, **kwargs) -> OutfitResult:
    """Public entrypoint. See run_pipeline for kwargs."""
    return run_pipeline(occasion, **kwargs).result
