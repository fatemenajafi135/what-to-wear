"""Stage 5: cited output.

Map each cited `rule_id` back to its source metadata and render the "why +
sources" text. Also exposes the pure verifiable checks (owned-items,
grounded-cites) that the eval harness reuses.
"""

from __future__ import annotations

from langsmith import traceable

from ..retrieval.base import RetrievalResult
from ..schema import CitedSource, Context, Outfit, OutfitResult, Rationale
from .generator import GenOutput
from .grounding import filter_ungrounded_cites


def cited_rule_ids(gen: GenOutput) -> list[str]:
    ids: list[str] = []
    for outfit in gen.outfits:
        for r in outfit.rationale:
            ids.extend(r.cites)
    return ids


def owned_only(gen: GenOutput, wardrobe_ids: set[str]) -> tuple[bool, list[str]]:
    """True iff every item in every outfit is an owned wardrobe id. Returns
    the offending (hallucinated) ids. This is the highest-value grounding
    check."""
    offending = [i for outfit in gen.outfits for i in outfit.items if i not in wardrobe_ids]
    return (not offending, offending)


def all_cites_grounded(gen: GenOutput, retrieved_ids: set[str]) -> tuple[bool, list[str]]:
    """True iff every cited rule_id was actually retrieved (no invented rules)."""
    bad = [rid for rid in cited_rule_ids(gen) if rid not in retrieved_ids]
    return (not bad, bad)


def every_choice_cites(gen: GenOutput) -> bool:
    """True iff every rationale line cites at least one rule_id."""
    return all(r.cites for outfit in gen.outfits for r in outfit.rationale)


@traceable(name="stage.cite", run_type="chain")
def build_result(ctx: Context, gen: GenOutput, retrieval: RetrievalResult) -> OutfitResult:
    """Assemble the final OutfitResult with resolved source citations.

    Re-applies `filter_ungrounded_cites` as a last-mile safety net (both
    graph paths already drop ungrounded citations at generation time — see
    `graph.py::generate_outfits` and `engine.py::engine_write` — so this is
    normally a no-op; it stays cheap insurance against a future response
    path that forgets to call the upstream guard, matching
    `verify_grounding`'s "safety net on top of, not a replacement for"
    convention for the item-level check)."""
    meta_by_id = {d.metadata["rule_id"]: d.metadata for d in retrieval.all()}
    retrieved_rule_ids = set(meta_by_id)

    outfits = [
        Outfit(
            items=o.items,
            rationale=[
                Rationale(text=r.text, cites=r.cites) for r in filter_ungrounded_cites(o.rationale, retrieved_rule_ids)
            ],
        )
        for o in gen.outfits
    ]

    sources: dict[str, CitedSource] = {}
    for rid in (c for outfit in outfits for r in outfit.rationale for c in r.cites):
        if rid in sources:
            continue
        m = meta_by_id[rid]
        sources[rid] = CitedSource(rule_id=rid, source=m["source"], url=m["url"], layer=m["layer"])

    return OutfitResult(outfits=outfits, sources=list(sources.values()), context=ctx)


def render_text(result: OutfitResult) -> str:
    """Human-readable 'why + sources' rendering."""
    lines = []
    for n, outfit in enumerate(result.outfits, 1):
        lines.append(f"Outfit {n}: {', '.join(outfit.items)}")
        for r in outfit.rationale:
            lines.append(f"  - {r.text}  [cites: {', '.join(r.cites)}]")
        lines.append("")
    if result.sources:
        lines.append("Sources:")
        for s in result.sources:
            lines.append(f"  [{s.rule_id}] {s.source} — {s.url}")
    return "\n".join(lines)
