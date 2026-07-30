"""Unit tests for pipeline/generator.py — never had one before this port.
No live LLM call — the gateway factory is mocked."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from whattowear.pipeline.generator import GenOutfit, GenOutput, GenRationale, _format_items, _format_rules, generate
from whattowear.retrieval.base import RetrievalResult
from whattowear.schema import Context, WardrobeItem


def _item(id: str, category: str = "top") -> WardrobeItem:
    return WardrobeItem(id=id, category=category, colors=["#1b2a4a"], formality="casual", warmth=1, season=[])


class TestFormatItems:
    def test_shows_derived_color_name_and_hex(self) -> None:
        ctx = Context(occasion="office", formality="business_casual", wardrobe=[_item("a")])
        formatted = _format_items(ctx)
        assert "navy" in formatted
        assert "#1b2a4a" in formatted

    def test_empty_wardrobe_is_empty_string(self) -> None:
        ctx = Context(occasion="office", formality="business_casual", wardrobe=[])
        assert _format_items(ctx) == ""


class TestFormatRules:
    def test_includes_rule_id_layer_source_and_content(self) -> None:
        from langchain_core.documents import Document

        doc = Document(page_content="wear navy", metadata={"rule_id": "L1-a", "layer": "L1", "source": "src"})
        formatted = _format_rules([doc])
        assert "L1-a" in formatted
        assert "L1" in formatted
        assert "src" in formatted
        assert "wear navy" in formatted


class TestGenerate:
    def test_invokes_llm_with_system_and_human_messages(self) -> None:
        fake_llm = MagicMock()
        expected = GenOutput(outfits=[GenOutfit(items=["a"], rationale=[GenRationale(text="r", cites=["L1-a"])])])
        fake_llm.with_structured_output.return_value.invoke.return_value = expected
        ctx = Context(occasion="office", formality="business_casual", wardrobe=[_item("a")])

        with patch("whattowear.pipeline.generator.get_chat_model", return_value=fake_llm):
            result = generate(ctx, RetrievalResult())

        assert result == expected
        fake_llm.with_structured_output.assert_called_once_with(GenOutput)
        call_args = fake_llm.with_structured_output.return_value.invoke.call_args[0][0]
        assert call_args[0][0] == "system"
        assert call_args[1][0] == "human"

    def test_profile_note_included_when_present(self) -> None:
        fake_llm = MagicMock()
        fake_llm.with_structured_output.return_value.invoke.return_value = GenOutput(outfits=[])
        ctx = Context(occasion="office", formality="business_casual", wardrobe=[])

        with patch("whattowear.pipeline.generator.get_chat_model", return_value=fake_llm):
            generate(ctx, RetrievalResult(), profile_note="avoids bright colors")

        human_message = fake_llm.with_structured_output.return_value.invoke.call_args[0][0][1][1]
        assert "avoids bright colors" in human_message

    def test_no_profile_note_omits_the_section(self) -> None:
        fake_llm = MagicMock()
        fake_llm.with_structured_output.return_value.invoke.return_value = GenOutput(outfits=[])
        ctx = Context(occasion="office", formality="business_casual", wardrobe=[])

        with patch("whattowear.pipeline.generator.get_chat_model", return_value=fake_llm):
            generate(ctx, RetrievalResult())

        human_message = fake_llm.with_structured_output.return_value.invoke.call_args[0][0][1][1]
        assert "USER STYLE PROFILE" not in human_message
