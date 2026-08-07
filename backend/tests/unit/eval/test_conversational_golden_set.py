"""Unit tests for eval/conversational_golden_set.py — feature 016, never had one before this
slice. Fixture-shape assertions only, no live call (mirrors test_golden_set.py)."""

from __future__ import annotations

from whattowear.eval.conversational_golden_set import GOLDEN_PATH, load_cases


def test_golden_path_resolves_to_the_tracked_evals_directory() -> None:
    assert GOLDEN_PATH.exists()
    assert GOLDEN_PATH.parent.name == "evals"


def test_loads_all_cases() -> None:
    cases = load_cases()
    assert len(cases) == 7


def test_case_ids_are_unique() -> None:
    cases = load_cases()
    assert len({c.id for c in cases}) == len(cases)


def test_every_case_has_an_utterance_and_a_voice_check() -> None:
    cases = load_cases()
    assert all(c.utterance for c in cases)
    assert all(c.voice_check for c in cases)


def test_at_least_one_case_covers_each_slot() -> None:
    cases = load_cases()
    covered = {key for c in cases for key in c.expected_slots}
    assert covered == {"occasion", "formality", "mood", "temp_c", "location"}


def test_at_least_one_case_has_prior_slots_and_must_not_re_ask() -> None:
    cases = load_cases()
    assert any(c.prior_slots for c in cases)


def test_at_least_one_case_extracts_nothing_new() -> None:
    cases = load_cases()
    assert any(c.prior_slots and not c.expected_slots for c in cases)
