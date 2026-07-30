"""Optional reported-only LLM quality judgment.

Computed and attached to eval harness rows purely for reporting/comparison
— MUST NOT influence which items are selected or how outfits are ranked
(constitution Principle II makes this a hard rule, not a soft
recommendation). The enforcement isn't a docstring promise: `scoring/`
never imports this module, so there is no code path from a judge score
into `rank_score` or result ordering.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from ..adapters.llm_gateway import get_judge_model
from ..prompts import load_prompt
from ..schema import ScoredOutfit


class _JudgeScore(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    reason: str


def format_outfit_for_judge(outfit: ScoredOutfit) -> str:
    lines = [f"items: {', '.join(outfit.items)}"]
    lines.extend(f"- {r.text}" for r in outfit.rationale)
    return "\n".join(lines)


def judge_outfit(user_input: str, outfit_text: str) -> float | None:
    """A 0-1 quality score, or None if the judge call fails — this is a
    reported signal, not a required one, so a failure here must never
    break the caller (matches `ExtractedAttributes`/`vision.py`'s own
    graceful-degradation pattern for optional, best-effort LLM signals)."""
    try:
        prompt_text, _version = load_prompt("judge")
        llm = get_judge_model().with_structured_output(_JudgeScore)
        result = llm.invoke([("system", prompt_text), ("human", f"REQUEST:\n{user_input}\n\nOUTFIT:\n{outfit_text}")])
        assert isinstance(result, _JudgeScore)
        return result.score
    except Exception:  # noqa: BLE001 - best-effort reported signal, never fatal
        return None
