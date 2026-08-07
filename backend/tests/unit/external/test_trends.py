"""Unit tests for external/trends.py — never had one before this port.

No live Tavily/gateway calls (constitution Quality Bar) — everything here
is mocked at the module boundary.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from whattowear.external import trends


class TestSearchTrends:
    def test_dict_response_returns_its_results_key(self) -> None:
        mock_tool = MagicMock()
        mock_tool.invoke.return_value = {"results": [{"title": "t", "url": "u", "content": "c"}]}
        with patch("langchain_tavily.TavilySearch", return_value=mock_tool):
            results = trends.search_trends("autumn trends")
        assert results == [{"title": "t", "url": "u", "content": "c"}]

    def test_list_response_returned_as_is(self) -> None:
        mock_tool = MagicMock()
        mock_tool.invoke.return_value = [{"title": "t", "url": "u", "content": "c"}]
        with patch("langchain_tavily.TavilySearch", return_value=mock_tool):
            results = trends.search_trends("autumn trends")
        assert results == [{"title": "t", "url": "u", "content": "c"}]

    def test_none_response_becomes_empty_list(self) -> None:
        mock_tool = MagicMock()
        mock_tool.invoke.return_value = None
        with patch("langchain_tavily.TavilySearch", return_value=mock_tool):
            assert trends.search_trends("q") == []


class TestDistillCard:
    def test_parses_well_formed_json_from_llm_response(self) -> None:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = (
            '{"claim": "Wide trousers are trending", "season": "autumn", "formality": "smart_casual"}'
        )
        with patch("whattowear.external.trends.get_chat_model", return_value=mock_llm):
            card = trends.distill_card("autumn trends", [{"title": "t", "content": "wide trousers everywhere"}])
        assert card == {"claim": "Wide trousers are trending", "season": "autumn", "formality": "smart_casual"}

    def test_extracts_json_even_with_surrounding_prose(self) -> None:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = 'Here is the card: {"claim": "x", "season": "autumn"} - hope that helps'
        with patch("whattowear.external.trends.get_chat_model", return_value=mock_llm):
            card = trends.distill_card("q", [{"title": "t", "content": "c"}])
        assert card == {"claim": "x", "season": "autumn"}

    def test_malformed_json_returns_none(self) -> None:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = "not json at all"
        with patch("whattowear.external.trends.get_chat_model", return_value=mock_llm):
            assert trends.distill_card("q", [{"title": "t", "content": "c"}]) is None


class TestRefreshTrendCards:
    @pytest.fixture(autouse=True)
    def _corpus_dir(self, tmp_path, monkeypatch: pytest.MonkeyPatch):
        (tmp_path / "kb").mkdir()
        monkeypatch.setenv("CORPUS_LOCAL_DIR", str(tmp_path))
        from whattowear.core.config import get_settings

        get_settings.cache_clear()
        yield tmp_path
        get_settings.cache_clear()

    def test_appends_new_cards_to_the_card_file(self, _corpus_dir) -> None:
        with (
            patch(
                "whattowear.external.trends.search_trends", return_value=[{"title": "t", "url": "u", "content": "c"}]
            ),
            patch("whattowear.external.trends.distill_card", return_value={"claim": "x", "season": "autumn"}),
        ):
            cards = trends.refresh_trend_cards(["autumn trends"])

        assert len(cards) == 1
        assert cards[0]["rule_id"] == "L3-live-001"
        assert cards[0]["text"] == "x"

        written = (_corpus_dir / "kb" / "l3_trend_cards.jsonl").read_text()
        assert json.loads(written.strip())["rule_id"] == "L3-live-001"

    def test_no_results_skips_the_query(self, _corpus_dir) -> None:
        with patch("whattowear.external.trends.search_trends", return_value=[]):
            cards = trends.refresh_trend_cards(["obscure query"])
        assert cards == []

    def test_distillation_failure_skips_the_query(self, _corpus_dir) -> None:
        with (
            patch("whattowear.external.trends.search_trends", return_value=[{"title": "t", "content": "c"}]),
            patch("whattowear.external.trends.distill_card", return_value=None),
        ):
            cards = trends.refresh_trend_cards(["q"])
        assert cards == []

    def test_append_false_does_not_write_the_file(self, _corpus_dir) -> None:
        with (
            patch(
                "whattowear.external.trends.search_trends", return_value=[{"title": "t", "url": "u", "content": "c"}]
            ),
            patch("whattowear.external.trends.distill_card", return_value={"claim": "x"}),
        ):
            trends.refresh_trend_cards(["q"], append=False)
        assert not (_corpus_dir / "kb" / "l3_trend_cards.jsonl").exists()

    def test_missing_corpus_local_dir_raises_clearly(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CORPUS_LOCAL_DIR", "")
        from whattowear.core.config import get_settings

        get_settings.cache_clear()
        with pytest.raises(RuntimeError, match="CORPUS_LOCAL_DIR"):
            trends.refresh_trend_cards(["q"])
        get_settings.cache_clear()
