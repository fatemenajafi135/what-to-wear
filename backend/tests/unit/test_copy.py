"""Unit tests for copy.py — the DRAFT-flagged deterministic strings feature 016 owns
(docs/handoffs/016-conversational-turns.md §3, docs/design-decisions.md §49)."""

from __future__ import annotations

from whattowear import copy
from whattowear.external.weather import _WMO


def test_wrap_up_text_includes_formality_when_known():
    assert copy.wrap_up_text("wedding", "formal") == "Styling for wedding, formal."


def test_wrap_up_text_degrades_gracefully_without_formality():
    assert copy.wrap_up_text("wedding", None) == "Styling for wedding."


def test_turn_cap_reached_and_call_failed_are_non_empty_strings():
    assert copy.TURN_CAP_REACHED
    assert copy.CALL_FAILED


# issue #67 (design-decisions.md §65) — weather clause on the wrap-up line.


def test_wrap_up_text_appends_condition_emoji_when_condition_known():
    text = copy.wrap_up_text("dinner", "Semi-formal", temp_c=14, condition="rain", temp_band="cool")
    assert text == "Styling for dinner, semi-formal — 🌧 14°C."


def test_wrap_up_text_falls_back_to_temp_band_emoji_when_condition_unknown():
    """The refinement-turn case: `condition` doesn't survive a refinement, `temp_band` does."""
    text = copy.wrap_up_text("dinner", "Semi-formal", temp_c=14, condition=None, temp_band="cool")
    assert text == "Styling for dinner, semi-formal — 🌤 14°C."


def test_wrap_up_text_has_no_weather_clause_when_neither_known():
    """No regression: byte-identical to the pre-#67 occasion/formality-only text."""
    text = copy.wrap_up_text("dinner", "Semi-formal", temp_c=None, condition=None, temp_band=None)
    assert text == "Styling for dinner, semi-formal."


def test_condition_emoji_table_covers_every_wmo_condition():
    """Acceptance criterion: the mapping covers every string `_WMO` can produce, not just the
    common ones."""
    assert set(_WMO.values()) == set(copy._CONDITION_EMOJI.keys())


def test_tornado_emoji_is_never_assigned_to_a_condition():
    """🌪 is deliberately unused — design-decisions.md §65. Forcing it onto an unrelated
    condition would be worse than leaving it out."""
    assert "🌪" not in copy._CONDITION_EMOJI.values()
