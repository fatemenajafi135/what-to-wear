"""Unit tests for eval/golden_set.py — never had one before this port."""

from __future__ import annotations

from whattowear.eval.golden_set import GOLDEN_PATH, load_cases


def test_golden_path_resolves_to_the_tracked_evals_directory() -> None:
    assert GOLDEN_PATH.exists()
    assert GOLDEN_PATH.parent.name == "evals"


def test_loads_all_24_golden_cases() -> None:
    cases = load_cases()
    assert len(cases) == 24


def test_case_ids_are_unique() -> None:
    cases = load_cases()
    assert len({c.id for c in cases}) == len(cases)


def test_every_case_has_an_occasion() -> None:
    cases = load_cases()
    assert all(c.occasion for c in cases)
