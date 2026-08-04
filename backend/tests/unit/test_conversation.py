"""Unit tests for conversation.py — the conversational-turn LLM call (feature 016).

Covers the deterministic parts (known-slots formatting, structured-output parsing) with the
model mocked — no live gateway call, no network, same pattern `test_vision.py` uses for
`vision.py`. Extraction quality against real utterances is the golden-set check
(evals/conversational_golden_set.yaml via eval/conversational_harness.py), not this file.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from whattowear import conversation
from whattowear.schema import ConversationalTurnResult


def test_known_slots_line_lists_only_non_null_values():
    line = conversation._known_slots_line({"occasion": "wedding", "formality": None, "mood": "relaxed"})
    assert "occasion: wedding" in line
    assert "mood: relaxed" in line
    assert "formality" not in line


def test_known_slots_line_when_nothing_is_known_yet():
    assert conversation._known_slots_line({}) == "Nothing is known yet — this is the first turn."


def test_reply_returns_structured_output():
    raw = {
        "reply_text": "Got it — what's the occasion?",
        "occasion": None,
        "mood": None,
        "formality": None,
        "location": None,
        "temp_c": None,
    }
    fake_structured_llm = MagicMock()
    fake_structured_llm.invoke.return_value = raw
    fake_chat_model = MagicMock()
    fake_chat_model.with_structured_output.return_value = fake_structured_llm

    with patch.object(conversation, "get_chat_model", return_value=fake_chat_model):
        result = conversation.reply("something for a wedding", {})

    assert result == ConversationalTurnResult(**raw)
    fake_chat_model.with_structured_output.assert_called_once_with(conversation._TURN_SCHEMA, method="json_schema")
    fake_structured_llm.invoke.assert_called_once()


def test_reply_extracts_a_known_slot():
    raw = {
        "reply_text": "Got it — is it a smart place, or more relaxed?",
        "occasion": "wedding",
        "mood": None,
        "formality": None,
        "location": None,
        "temp_c": None,
    }
    fake_structured_llm = MagicMock()
    fake_structured_llm.invoke.return_value = raw
    fake_chat_model = MagicMock()
    fake_chat_model.with_structured_output.return_value = fake_structured_llm

    with patch.object(conversation, "get_chat_model", return_value=fake_chat_model):
        result = conversation.reply("something for a wedding", {})

    assert result.occasion == "wedding"
    assert result.formality is None


def test_reply_drops_an_out_of_enum_formality_rather_than_raising():
    """constitution Principle VI — never a parallel formality scale. An unrecognized value from
    the model must not fail the whole turn (reply_text and every other slot are still worth
    keeping)."""
    raw = {
        "reply_text": "Got it.",
        "occasion": None,
        "mood": None,
        "formality": "extremely_fancy",  # not one of the six known values
        "location": None,
        "temp_c": None,
    }
    fake_structured_llm = MagicMock()
    fake_structured_llm.invoke.return_value = raw
    fake_chat_model = MagicMock()
    fake_chat_model.with_structured_output.return_value = fake_structured_llm

    with patch.object(conversation, "get_chat_model", return_value=fake_chat_model):
        result = conversation.reply("a very fancy party", {})

    assert result.formality is None
    assert result.reply_text == "Got it."


def test_reply_call_failure_propagates():
    """The caller (the route) maps this to the fixed CALL_FAILED copy — this function itself
    must not swallow the error (mirrors vision.py's own call-failure philosophy)."""
    fake_chat_model = MagicMock()
    fake_chat_model.with_structured_output.return_value.invoke.side_effect = RuntimeError("gateway down")

    with patch.object(conversation, "get_chat_model", return_value=fake_chat_model):
        try:
            conversation.reply("hello", {})
        except RuntimeError:
            pass
        else:
            raise AssertionError("expected RuntimeError to propagate")
