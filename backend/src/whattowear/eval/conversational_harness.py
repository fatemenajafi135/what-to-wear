"""Eval harness for the conversational-turn LLM call (feature 016) — live gateway required, not
part of `pytest`/CI (mirrors `eval/harness.py`'s own exclusion; constitution Quality Bar: "CI
MUST NOT make live LLM calls").

Scores `evals/conversational_golden_set.yaml`'s two halves separately (research.md §10):

- **slot extraction** — deterministic dict-equality against `expected_slots`, given `prior_slots`
  as what the turn is told is already known. This is the checkable half; run it whenever
  `conversation.py` or its prompt changes.
- **voice** — a loose LLM-judge score (0.0-1.0) against each case's own `voice_check`
  description, using `prompts/conversational_judge.md`. Never asserts exact `reply_text`.

Run manually: `uv run python -m whattowear.eval.conversational_harness`.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from .. import conversation
from ..adapters.llm_gateway import get_judge_model
from ..prompts import load_prompt
from .conversational_golden_set import ConversationalGoldenCase, load_cases


class _VoiceScore(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    reason: str


def judge_voice(reply_text: str, voice_check: str) -> float | None:
    """Reported-only, like `judge.judge_outfit` — a failure here must never break the run."""
    try:
        prompt_text, _version = load_prompt("conversational_judge")
        llm = get_judge_model().with_structured_output(_VoiceScore)
        result = llm.invoke([("system", prompt_text), ("human", f"REPLY:\n{reply_text}\n\nSHOULD:\n{voice_check}")])
        assert isinstance(result, _VoiceScore)
        return result.score
    except Exception:  # noqa: BLE001 - best-effort reported signal, never fatal
        return None


def run_case(case: ConversationalGoldenCase) -> dict:
    result = conversation.reply(case.utterance, case.prior_slots)
    extracted = {
        key: value
        for key, value in (
            ("occasion", result.occasion),
            ("mood", result.mood),
            ("formality", result.formality),
            ("location", result.location),
            ("temp_c", result.temp_c),
        )
        if value is not None
    }
    slots_match = extracted == case.expected_slots
    voice_score = judge_voice(result.reply_text, case.voice_check) if case.voice_check else None
    return {
        "id": case.id,
        "reply_text": result.reply_text,
        "expected_slots": case.expected_slots,
        "extracted_slots": extracted,
        "slots_match": slots_match,
        "voice_score": voice_score,
    }


def run_all() -> list[dict]:
    return [run_case(case) for case in load_cases()]


if __name__ == "__main__":
    rows = run_all()
    matched = sum(1 for r in rows if r["slots_match"])
    voice_scores = [r["voice_score"] for r in rows if r["voice_score"] is not None]
    print(f"Slot extraction: {matched}/{len(rows)} cases matched exactly.")
    if voice_scores:
        print(f"Voice: mean {sum(voice_scores) / len(voice_scores):.2f} over {len(voice_scores)} judged cases.")
    for row in rows:
        flag = "OK" if row["slots_match"] else "MISMATCH"
        print(f"  [{flag}] {row['id']}: expected={row['expected_slots']} extracted={row['extracted_slots']}")
