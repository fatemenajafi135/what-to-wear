"""Stage 4: grounded generator.

Input = wardrobe inventory + retrieved rules (each with a rule_id) + context.
The LLM assembles outfits **from inventory only**, obeys the retrieved
constraints, and **cites a rule_id for every choice**. Structured output makes the
grounding machine-checkable (see eval Harness B).

The `score_combinations` seam is where a learned compatibility model would slot in
later without changing the pipeline (plan: extension seams).
"""

from __future__ import annotations

from typing import Optional

from langchain_core.documents import Document
from langsmith import traceable
from pydantic import BaseModel, Field

from ..colors import nearest_names
from ..config import get_chat_model
from ..schema import Context
from ..retrieval.base import RetrievalResult


class GenRationale(BaseModel):
    text: str = Field(description="one styling reason")
    cites: list[str] = Field(description="rule_id(s) from the provided rules that justify this choice")


class GenOutfit(BaseModel):
    items: list[str] = Field(description="wardrobe item ids used in this outfit (from inventory ONLY)")
    rationale: list[GenRationale]


class GenOutput(BaseModel):
    outfits: list[GenOutfit]


SYSTEM_PROMPT = (
    "You are a professional personal stylist. You assemble complete outfits STRICTLY "
    "from the user's own wardrobe and STRICTLY within the retrieved styling rules.\n"
    "Hard rules:\n"
    "1. Use ONLY item ids that appear in the WARDROBE list. Never invent items.\n"
    "2. Obey the RETRIEVED RULES (dress code, weather, harmony). They are constraints.\n"
    "3. Every rationale MUST cite at least one rule_id from the RETRIEVED RULES, "
    "copied EXACTLY as printed in the brackets (e.g. from '[L1-color-three-max | ...]' "
    "cite 'L1-color-three-max'). Never abbreviate, paraphrase, or drop part of a rule_id.\n"
    "4. A complete outfit covers the body sensibly (e.g. top + bottom + shoes, or a "
    "dress + shoes) and adds outerwear when the weather rule calls for it.\n"
    "5. Prefer items whose formality and season match the context.\n"
    "Return 3-5 distinct complete outfits when the wardrobe supports it "
    "(FR-002); return fewer only if you genuinely cannot assemble more "
    "complete, valid outfits from the inventory — never pad with an "
    "incomplete or repeated outfit just to hit the count."
)


def _format_items(ctx: Context) -> str:
    """Show the LLM the DERIVED color name, not raw hex — a language model
    reasons about "navy" far better than "#1b2a4a", which carries no semantic
    weight to it. Hex stays visible in parens for traceability."""
    lines = []
    for it in ctx.wardrobe:
        colors = ", ".join(f"{n} ({h})" for n, h in zip(nearest_names(it.colors), it.colors))
        lines.append(
            f"- {it.id}: {it.category}, colors=[{colors}], formality={it.formality}, "
            f"warmth={it.warmth}, season={it.season}"
        )
    return "\n".join(lines)


def _format_rules(docs: list[Document]) -> str:
    lines = []
    for d in docs:
        m = d.metadata
        lines.append(f"[{m['rule_id']} | {m['layer']} | {m['source']}] {d.page_content.strip()}")
    return "\n".join(lines)


@traceable(name="stage.generate", run_type="chain")
def generate(
    ctx: Context,
    retrieval: RetrievalResult,
    profile_note: Optional[str] = None,
    model: Optional[str] = None,
) -> GenOutput:
    rules = retrieval.all()
    context_line = (
        f"occasion={ctx.occasion}, formality={ctx.formality}, mood={ctx.mood}, "
        f"temp_c={ctx.temp_c}, temp_band={ctx.temp_band}, season={ctx.season}, "
        f"condition={ctx.condition}"
    )
    human = (
        f"CONTEXT:\n{context_line}\n\n"
        f"WARDROBE (use only these ids):\n{_format_items(ctx)}\n\n"
        f"RETRIEVED RULES (cite these rule_ids):\n{_format_rules(rules)}\n"
    )
    if profile_note:
        human += f"\nUSER STYLE PROFILE (soft preference, never overrides constraints):\n{profile_note}\n"

    llm = get_chat_model(model=model, temperature=0.3).with_structured_output(GenOutput)
    return llm.invoke([("system", SYSTEM_PROMPT), ("human", human)])
