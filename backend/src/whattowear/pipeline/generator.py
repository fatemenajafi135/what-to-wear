"""Stage 4: grounded generator.

Input = wardrobe inventory + retrieved rules (each with a rule_id) +
context. The LLM assembles outfits **from inventory only**, obeys the
retrieved constraints, and **cites a rule_id for every choice**. Structured
output makes the grounding machine-checkable (see `eval/harness.py`).

This is the grounded (default) path's one LLM call — constitution
Principle II: the LLM assembles the combination here; the four
deterministic scorers and `verify_grounding` are what runs on its output
before anything reaches a user (specs/007-ai-port/research.md §3).
"""

from __future__ import annotations

from langchain_core.documents import Document
from langsmith import traceable
from pydantic import BaseModel, Field

from ..adapters.llm_gateway import get_chat_model
from ..colors import nearest_names
from ..prompts import load_prompt
from ..retrieval.base import RetrievalResult
from ..schema import Context


class GenRationale(BaseModel):
    text: str = Field(description="one styling reason")
    cites: list[str] = Field(description="rule_id(s) from the provided rules that justify this choice")


class GenOutfit(BaseModel):
    items: list[str] = Field(description="wardrobe item ids used in this outfit (from inventory ONLY)")
    rationale: list[GenRationale]


class GenOutput(BaseModel):
    outfits: list[GenOutfit]


def _format_items(ctx: Context) -> str:
    """Show the LLM the DERIVED color name, not raw hex — a language model
    reasons about "navy" far better than "#1b2a4a", which carries no
    semantic weight to it. Hex stays visible in parens for traceability."""
    lines = []
    for it in ctx.wardrobe:
        colors = ", ".join(f"{n} ({h})" for n, h in zip(nearest_names(it.colors), it.colors, strict=True))
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
    profile_note: str | None = None,
    model: str | None = None,
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

    system_prompt, _version = load_prompt("generator_system")
    llm = get_chat_model(model=model, temperature=0.3).with_structured_output(GenOutput)
    result = llm.invoke([("system", system_prompt), ("human", human)])
    # with_structured_output's return type is `dict | BaseModel` (covers the
    # include_raw=True / json_mode cases we don't use here); this call site
    # always gets back the pydantic model itself.
    assert isinstance(result, GenOutput)
    return result
