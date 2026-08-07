"""Unit tests for eval/harness.py's pure helpers. `run_case`/`run_strategy`/
`main` invoke the real compiled graph end-to-end (a live LLM call) — that
integration behavior is proven by the actual eval gate run against the
golden set (specs/007-ai-port/tasks.md T043, T056-T058), not a mocked
unit test, matching how this module was never unit-tested in the legacy
suite either (inventory: harness.py is a CLI tool, UNREF)."""

from __future__ import annotations

from whattowear.eval.golden_set import GoldenCase
from whattowear.eval.harness import _user_input, summarize


class TestUserInput:
    def test_includes_occasion(self) -> None:
        case = GoldenCase(id="c1", occasion="office")
        assert "office" in _user_input(case)

    def test_includes_mood_when_present(self) -> None:
        case = GoldenCase(id="c1", occasion="dinner", mood="playful")
        assert "playful" in _user_input(case)

    def test_includes_temp_when_present(self) -> None:
        case = GoldenCase(id="c1", occasion="office", temp_c=5.0)
        assert "5.0C" in _user_input(case)

    def test_omits_unset_fields(self) -> None:
        case = GoldenCase(id="c1", occasion="office")
        text = _user_input(case)
        assert "None" not in text


class TestSummarize:
    def test_does_not_raise_on_empty_rows(self, capsys) -> None:
        summarize({"advanced": []})
        captured = capsys.readouterr()
        assert "metric" in captured.out

    def test_prints_mean_retrieval_recall(self, capsys) -> None:
        rows = [
            {"retrieval_recall": 1.0, "checks": {}, "top_rank_score": 0.5},
            {"retrieval_recall": 0.5, "checks": {}, "top_rank_score": 0.7},
        ]
        summarize({"advanced": rows})
        captured = capsys.readouterr()
        assert "0.75" in captured.out
