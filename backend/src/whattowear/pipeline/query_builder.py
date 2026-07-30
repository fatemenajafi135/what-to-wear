"""Stage 2: query builder + router.

There is no single query. From the normalized context we build:
- a **naive NL query** (used by the baseline retriever, over all chunks),
- an **L3 NL query** (synthesized string, embedded for dense trend search),
- a **router** decision: which layers to hit (rules, not an LLM).

Router rules: L1 + L4 always; L3 only if season known; L2 never (no user
coloring captured yet). Keeping `route()` as a function is the seam for a
future agentic router.
"""

from __future__ import annotations

from ..schema import Context


def route(ctx: Context) -> list[str]:
    """Which knowledge layers to retrieve for this request."""
    layers = ["L4", "L1"]  # Filter + Combine, always
    if ctx.season is not None:
        layers.append("L3")  # Elevate, only when season is known
    # L2 (Personalize) is deliberately never selected — gated on user coloring.
    return layers


def naive_query(ctx: Context) -> str:
    """Single natural-language query for the baseline retriever."""
    bits = [ctx.occasion, ctx.formality.replace("_", " ")]
    if ctx.mood:
        bits.append(f"{ctx.mood} mood")
    if ctx.temp_band:
        bits.append(f"{ctx.temp_band} weather")
    if ctx.season:
        bits.append(ctx.season)
    return "what to wear for " + ", ".join(b for b in bits if b)


def l3_query(ctx: Context) -> str:
    """Synthesized NL string for the L3 dense trend search — the fiddly
    step where retrieval quality most easily slips, kept explicit so it
    can be tuned/measured."""
    season = ctx.season or ""
    mood = f"{ctx.mood} tone" if ctx.mood else ""
    band = f"{ctx.temp_band} weather" if ctx.temp_band else ""
    parts = [season, ctx.occasion, "outfit", ctx.formality.replace("_", " "), mood, band]
    return " ".join(p for p in parts if p).strip()
