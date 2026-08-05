"""Unit tests for copy.py — the DRAFT-flagged deterministic strings feature 016 owns
(docs/handoffs/016-conversational-turns.md §3, docs/design-decisions.md §49)."""

from __future__ import annotations

from whattowear import copy


def test_wrap_up_text_includes_formality_when_known():
    assert copy.wrap_up_text("wedding", "formal") == "Styling for wedding, formal."


def test_wrap_up_text_degrades_gracefully_without_formality():
    assert copy.wrap_up_text("wedding", None) == "Styling for wedding."


def test_turn_cap_reached_and_call_failed_are_non_empty_strings():
    assert copy.TURN_CAP_REACHED
    assert copy.CALL_FAILED
