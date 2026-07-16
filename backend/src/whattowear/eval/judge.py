"""Optional reported-only LLM quality judgment (FR-010, Feature 002 Phase 4).

Computed and attached to eval harness rows purely for reporting/comparison —
MUST NOT influence which items are selected or how outfits are ranked
(constitution Principle II makes this a hard rule, not just FR-010's "MAY").
The enforcement isn't a docstring promise: `scoring/` never imports this
module, so there is no code path from a judge score into `rank_score` or
result ordering (see tests/unit/eval/test_judge.py's architectural check).
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from ..config import get_judge_model
from ..schema import ScoredOutfit

_PROMPT = (
    "You are a fashion-styling judge. Given a styling REQUEST and a recommended "
    "OUTFIT with its rationale, rate how stylistically coherent and occasion-"
    "appropriate the outfit is, from 0.0 (incoherent/inappropriate) to 1.0 "
    "(coherent, well-reasoned, occasion-appropriate). This score is reported "
    "for evaluation only — it does not affect selection or ranking."
)


class _JudgeScore(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    reason: str


def format_outfit_for_judge(outfit: ScoredOutfit) -> str:
    lines = [f"items: {', '.join(outfit.items)}"]
    lines.extend(f"- {r.text}" for r in outfit.rationale)
    return "\n".join(lines)


def judge_outfit(user_input: str, outfit_text: str) -> Optional[float]:
    """A 0-1 quality score, or None if the judge call fails — this is a
    reported signal, not a required one, so a failure here must never break
    the caller (matches ExtractedAttributes/vision.py's own graceful-
    degradation pattern for optional, best-effort LLM signals)."""
    try:
        llm = get_judge_model().with_structured_output(_JudgeScore)
        result = llm.invoke(
            [("system", _PROMPT), ("human", f"REQUEST:\n{user_input}\n\nOUTFIT:\n{outfit_text}")]
        )
        return result.score
    except Exception:  # noqa: BLE001 - best-effort reported signal, never fatal
        return None
