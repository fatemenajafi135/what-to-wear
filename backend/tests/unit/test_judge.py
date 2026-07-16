"""Unit tests for eval/judge.py (Feature 002 Phase 4, T046, FR-010).

The reported-only LLM judge score MUST NOT influence selection or ranking
(constitution Principle II) — verified here two ways: the judge call itself
degrades gracefully on failure (never raises into a caller), and an
architectural check that `scoring/` never imports this module at all, so
there is no code path from a judge score into `rank_score` or ordering.
"""

from __future__ import annotations

import ast
from pathlib import Path

from whattowear.eval import judge
from whattowear.schema import DimensionScore, Rationale, ScoredOutfit


def _outfit() -> ScoredOutfit:
    return ScoredOutfit(
        items=["a", "b"],
        rationale=[Rationale(text="goes well together", cites=["L1-x"])],
        scores=[
            DimensionScore(dimension="color_harmony", value=0.5, reason="r"),
            DimensionScore(dimension="formality_coherence", value=0.5, reason="r"),
            DimensionScore(dimension="weather_fitness", value=0.5, reason="r"),
            DimensionScore(dimension="silhouette_balance", value=0.5, reason="r"),
        ],
        rank_score=0.5,
    )


class TestFormatOutfitForJudge:
    def test_includes_items_and_rationale_text(self):
        text = judge.format_outfit_for_judge(_outfit())
        assert "a" in text and "b" in text
        assert "goes well together" in text


class TestJudgeOutfit:
    def test_returns_the_structured_score_on_success(self, mocker):
        fake_llm = mocker.Mock()
        fake_llm.invoke.return_value = mocker.Mock(score=0.8)
        fake_model = mocker.Mock()
        fake_model.with_structured_output.return_value = fake_llm
        mocker.patch.object(judge, "get_judge_model", return_value=fake_model)

        result = judge.judge_outfit("what to wear for the office", "items: a, b")

        assert result == 0.8

    def test_returns_none_and_never_raises_on_failure(self, mocker):
        mocker.patch.object(judge, "get_judge_model", side_effect=RuntimeError("gateway down"))

        result = judge.judge_outfit("what to wear for the office", "items: a, b")

        assert result is None


class TestJudgeNeverInfluencesScoring:
    """Architectural guarantee, not just a docstring promise: nothing under
    scoring/ imports eval.judge, so a judge score has no code path into
    rank_score or ordering."""

    def test_scoring_package_never_imports_eval_judge(self):
        scoring_dir = Path(judge.__file__).parent.parent / "scoring"
        assert scoring_dir.is_dir()

        for py_file in scoring_dir.glob("*.py"):
            tree = ast.parse(py_file.read_text(), filename=str(py_file))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    assert "judge" not in node.module, f"{py_file} imports {node.module}"
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        assert "judge" not in alias.name, f"{py_file} imports {alias.name}"
