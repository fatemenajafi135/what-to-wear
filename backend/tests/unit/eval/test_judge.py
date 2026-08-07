"""Unit tests for eval/judge.py — never had one before this port. No live
LLM call — the judge model factory is mocked.
"""

from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import MagicMock, patch

from whattowear.eval.judge import _JudgeScore, format_outfit_for_judge, judge_outfit
from whattowear.schema import DimensionScore, Rationale, ScoredOutfit


def _outfit() -> ScoredOutfit:
    return ScoredOutfit(
        items=["a", "b"],
        rationale=[Rationale(text="navy pairs well with charcoal", cites=["L1-x"])],
        scores=[
            DimensionScore(dimension="color_harmony", value=0.9, reason="r"),
            DimensionScore(dimension="formality_coherence", value=0.9, reason="r"),
            DimensionScore(dimension="weather_fitness", value=0.9, reason="r"),
            DimensionScore(dimension="silhouette_balance", value=0.9, reason="r"),
        ],
        rank_score=1.0,
    )


class TestFormatOutfitForJudge:
    def test_includes_items_and_rationale_text(self) -> None:
        text = format_outfit_for_judge(_outfit())
        assert "items: a, b" in text
        assert "navy pairs well with charcoal" in text


class TestJudgeOutfit:
    def test_returns_the_score_on_success(self) -> None:
        fake_llm = MagicMock()
        fake_llm.with_structured_output.return_value.invoke.return_value = _JudgeScore(score=0.8, reason="coherent")
        with patch("whattowear.eval.judge.get_judge_model", return_value=fake_llm):
            score = judge_outfit("office request", "outfit text")
        assert score == 0.8

    def test_call_failure_returns_none_never_raises(self) -> None:
        fake_llm = MagicMock()
        fake_llm.with_structured_output.return_value.invoke.side_effect = RuntimeError("gateway down")
        with patch("whattowear.eval.judge.get_judge_model", return_value=fake_llm):
            score = judge_outfit("office request", "outfit text")
        assert score is None


class TestJudgeNeverInfluencesScoring:
    """Constitution Principle II: a judge score MUST NOT affect selection or
    ranking. Enforced architecturally, not by convention — this test reads
    scoring/'s own source and fails if it ever imports eval.judge."""

    def test_scoring_package_never_imports_eval_judge(self) -> None:
        scoring_dir = Path(__file__).parent.parent.parent.parent / "src" / "whattowear" / "scoring"
        for path in scoring_dir.glob("*.py"):
            tree = ast.parse(path.read_text(), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module and "judge" in node.module:
                    raise AssertionError(f"{path} imports from a 'judge' module: {node.module}")
