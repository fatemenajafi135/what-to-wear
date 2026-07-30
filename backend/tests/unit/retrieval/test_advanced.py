"""Unit tests for retrieval/advanced.py.

Feature 007 Task B: retrieve_l3 now does a live Tavily search rather than a
static vector query — advanced.retrieve() should still over-fetch (FIRST_STAGE_K)
then Cohere-rerank down to k_l3, same shape as before, just over live results.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from langchain_core.documents import Document

from whattowear.retrieval import advanced
from whattowear.schema import Context


def _doc(rule_id: str) -> Document:
    return Document(page_content="t", metadata={"source": "s", "url": "u", "layer": "L3", "rule_id": rule_id})


class TestAdvancedRetrieve:
    def test_l3_over_fetches_live_results_then_reranks(self):
        kb = MagicMock()
        ctx = Context(occasion="office", formality="business_casual", season="autumn")
        live_candidates = [_doc(f"L3-live-{i}") for i in range(8)]
        reranked = live_candidates[:5]

        with (
            patch.object(advanced.hybrid, "retrieve_l4", return_value=[]),
            patch.object(advanced.hybrid, "retrieve_l1", return_value=[]),
            patch.object(advanced.hybrid, "retrieve_l3", return_value=live_candidates) as mock_l3,
            patch.object(advanced, "_rerank_l3", return_value=reranked) as mock_rerank,
        ):
            result = advanced.retrieve(kb, ctx, layers=["L4", "L1", "L3"], l3_query="autumn office trends")

        mock_l3.assert_called_once_with("autumn office trends", k=advanced.FIRST_STAGE_K)
        mock_rerank.assert_called_once_with("autumn office trends", live_candidates, top_n=5)
        assert result.l3 == reranked

    def test_l1_call_passes_l3_query_as_the_semantic_query(self):
        kb = MagicMock()
        ctx = Context(occasion="office", formality="business_casual")

        with (
            patch.object(advanced.hybrid, "retrieve_l4", return_value=[]),
            patch.object(advanced.hybrid, "retrieve_l1", return_value=[]) as mock_l1,
        ):
            advanced.retrieve(kb, ctx, layers=["L4", "L1"], l3_query="office outfit")

        mock_l1.assert_called_once_with(kb, ctx, semantic_query="office outfit")

    def test_l3_not_called_when_layer_absent(self):
        kb = MagicMock()
        ctx = Context(occasion="office", formality="business_casual")

        with (
            patch.object(advanced.hybrid, "retrieve_l4", return_value=[]),
            patch.object(advanced.hybrid, "retrieve_l1", return_value=[]),
            patch.object(advanced.hybrid, "retrieve_l3") as mock_l3,
        ):
            advanced.retrieve(kb, ctx, layers=["L4", "L1"], l3_query="office outfit")

        mock_l3.assert_not_called()
