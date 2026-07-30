"""The deterministic-selection ("engine") approach — opt-in, per
constitution Principle II's stricter guarantee.

Item selection AND ranking here are enumerate + score, pure Python — the
LLM's only role (`engine_write`) is picking WHICH 3 of an already-scored
top-6 shortlist to surface and writing rationale text; the results are
returned in deterministic rank_score order, so the model never proposes a
combination or controls the final ranking.
"""

from __future__ import annotations

import itertools

from pydantic import BaseModel, Field

from ..adapters.llm_gateway import get_chat_model
from ..prompts import load_prompt
from ..retrieval.base import RetrievalResult
from ..schema import Context, ScoredOutfit, WardrobeItem
from .generator import GenRationale, _format_rules
from .grounding import filter_ungrounded_cites
from .validity import is_slot_complete, is_valid_combination

# >20,000 projected combos tightens each slot to its own top-6 by slicing
# the already-fitness-sorted candidate lists wardrobe_retrieval hands us —
# no new sort, just a narrower slice.
_SAFETY_VALVE_THRESHOLD = 20_000
_SAFETY_VALVE_PER_SLOT = 6

_SHORTLIST_SIZE = 6
_REQUIRED_SELECTIONS = 3


def enumerate_outfits(candidates: dict[str, list[WardrobeItem]], require_outerwear: bool) -> list[list[str]]:
    """Deterministically build every valid, complete outfit combination
    from the already-pruned, already-fitness-sorted per-slot candidates
    (`pipeline/graph.py::wardrobe_retrieval`). Two independent skeleton
    tracks — top x bottom x footwear, and full_body x footwear — each
    additionally crossed with every outerwear candidate when
    `require_outerwear` (outerwear-inclusive versions are ADDED alongside
    the bare skeleton, not a replacement for it — a legitimately
    warm-enough bare outfit is never dropped just because outerwear also
    exists). Every combo is filtered through the same coherence guards
    used elsewhere (`pipeline/validity.py`) — this function never invents
    its own notion of "valid outfit"."""
    tops = candidates.get("top", [])
    bottoms = candidates.get("bottom", [])
    footwear = candidates.get("footwear", [])
    full_body = candidates.get("full_body", [])
    outerwear = candidates.get("outerwear", []) if require_outerwear else []

    projected = len(tops) * len(bottoms) * len(footwear) + len(full_body) * len(footwear)
    if outerwear:
        projected *= len(outerwear)
    if projected > _SAFETY_VALVE_THRESHOLD:
        tops = tops[:_SAFETY_VALVE_PER_SLOT]
        bottoms = bottoms[:_SAFETY_VALVE_PER_SLOT]
        footwear = footwear[:_SAFETY_VALVE_PER_SLOT]
        full_body = full_body[:_SAFETY_VALVE_PER_SLOT]
        outerwear = outerwear[:_SAFETY_VALVE_PER_SLOT]

    wardrobe_by_id = {it.id: it for items in candidates.values() for it in items}
    combos: list[list[str]] = []

    def _add_if_valid(items: list[str]) -> None:
        if is_slot_complete(items, wardrobe_by_id) and is_valid_combination(items, wardrobe_by_id):
            combos.append(items)

    for top, bottom, shoe in itertools.product(tops, bottoms, footwear):
        base = [top.id, bottom.id, shoe.id]
        _add_if_valid(base)
        for outer in outerwear:
            _add_if_valid([*base, outer.id])

    for body, shoe in itertools.product(full_body, footwear):
        base = [body.id, shoe.id]
        _add_if_valid(base)
        for outer in outerwear:
            _add_if_valid([*base, outer.id])

    return combos


class EngineSelection(BaseModel):
    index: int = Field(description="0-based position into the offered shortlist")
    rationale: list[GenRationale] = Field(description="styling rationale for this pick, citing rule_ids")


class EngineWriteOutput(BaseModel):
    selections: list[EngineSelection] = Field(description="an ORDERED pick of exactly 3 shortlist indices")


def _format_shortlist(shortlist: list[ScoredOutfit], wardrobe_by_id: dict[str, WardrobeItem]) -> str:
    lines = []
    for idx, outfit in enumerate(shortlist):
        items_desc = ", ".join(
            f"{i} ({wardrobe_by_id[i].category})" if i in wardrobe_by_id else i for i in outfit.items
        )
        scores_desc = "; ".join(f"{s.dimension}={s.value:.2f} ({s.reason})" for s in outfit.scores)
        lines.append(f"[{idx}] items=[{items_desc}] rank_score={outfit.rank_score:.3f}\n    scores: {scores_desc}")
    return "\n".join(lines)


def _fallback_rationale(outfit: ScoredOutfit) -> list[GenRationale]:
    """Never a fabricated citation: `cites=[]` trivially satisfies "every
    citation resolves" since there's nothing to resolve."""
    top_dim = max(outfit.scores, key=lambda s: s.value)
    return [GenRationale(text=f"Selected by deterministic ranking (top dimension: {top_dim.reason}).", cites=[])]


def _is_valid_selection(output: EngineWriteOutput | None, shortlist_size: int) -> bool:
    if output is None or len(output.selections) != _REQUIRED_SELECTIONS:
        return False
    indices = [s.index for s in output.selections]
    if len(set(indices)) != len(indices):
        return False
    return all(0 <= i < shortlist_size for i in indices)


def engine_write(shortlist: list[ScoredOutfit], ctx: Context, retrieval: RetrievalResult) -> list[ScoredOutfit]:
    """The engine path's one LLM call: selection-and-writing only. A
    structurally or semantically invalid response — wrong count, an
    out-of-range or duplicate index, or a call/parsing failure — is
    discarded entirely in favor of the deterministic top-3-by-`rank_score`
    fallback, so the caller always gets a valid result. On a valid
    response, any citation that doesn't resolve to an actually-retrieved
    rule_id is dropped from that rationale rather than passed through —
    `verify_grounding`'s own pattern applied to citations instead of
    items."""
    wardrobe_by_id = {it.id: it for it in ctx.wardrobe}
    rules = retrieval.all()
    retrieved_rule_ids = {d.metadata["rule_id"] for d in rules}

    output: EngineWriteOutput | None = None
    try:
        context_line = (
            f"occasion={ctx.occasion}, formality={ctx.formality}, mood={ctx.mood}, "
            f"temp_c={ctx.temp_c}, temp_band={ctx.temp_band}, season={ctx.season}"
        )
        human = (
            f"CONTEXT:\n{context_line}\n\n"
            f"SHORTLIST (pick 3 of these by index — already deterministically scored):\n"
            f"{_format_shortlist(shortlist, wardrobe_by_id)}\n\n"
            f"RETRIEVED RULES (cite these rule_ids):\n{_format_rules(rules)}\n"
        )
        system_prompt, _version = load_prompt("engine_system")
        llm = get_chat_model(temperature=0.3).with_structured_output(EngineWriteOutput)
        raw_output = llm.invoke([("system", system_prompt), ("human", human)])
        # with_structured_output's return type is `dict | BaseModel` (covers
        # the include_raw=True / json_mode cases we don't use here); an
        # unexpected shape here is exactly what this try/except already
        # treats as "degrade to the deterministic fallback".
        if not isinstance(raw_output, EngineWriteOutput):
            raise TypeError("expected a structured EngineWriteOutput response")
        output = raw_output
    except Exception:  # noqa: BLE001 - any call/parsing failure degrades to the deterministic fallback
        output = None

    selected: list[ScoredOutfit]
    if not _is_valid_selection(output, len(shortlist)):
        selected = [
            outfit.model_copy(update={"rationale": _fallback_rationale(outfit)})
            for outfit in shortlist[:_REQUIRED_SELECTIONS]
        ]
    else:
        assert output is not None  # _is_valid_selection(None, ...) is always False
        selected = []
        for selection in output.selections:
            outfit = shortlist[selection.index]
            filtered_rationale = filter_ungrounded_cites(selection.rationale, retrieved_rule_ids)
            selected.append(outfit.model_copy(update={"rationale": filtered_rationale}))

    # Principle II: the LLM chooses WHICH 3 to surface, never their order —
    # the returned ranking is always deterministic rank_score-descending.
    # (The fallback slice is already in that order; sorting the LLM-picked
    # path the same way means the model never influences final rank
    # order.)
    selected.sort(key=lambda o: o.rank_score, reverse=True)
    return selected
