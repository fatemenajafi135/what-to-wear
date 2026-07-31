"""Unit tests for kb.py — never had one before this port. `get_kb()`'s
success path needs a live embedding call, so only its config-validation
failure path is exercised directly here; `KnowledgeBase.by_layer` is pure.
"""

from __future__ import annotations

import pytest
from langchain_core.documents import Document

from whattowear.core.config import get_settings
from whattowear.kb import KnowledgeBase, get_kb


def _doc(rule_id: str, layer: str) -> Document:
    return Document(page_content="t", metadata={"source": "s", "url": "u", "layer": layer, "rule_id": rule_id})


class TestKnowledgeBaseByLayer:
    def test_filters_chunks_to_the_requested_layer(self) -> None:
        kb = KnowledgeBase(vectorstore=object(), chunks=[_doc("a", "L1"), _doc("b", "L3"), _doc("c", "L1")])  # type: ignore[arg-type]
        l1 = kb.by_layer("L1")
        assert {d.metadata["rule_id"] for d in l1} == {"a", "c"}

    def test_unknown_layer_returns_empty_list(self) -> None:
        kb = KnowledgeBase(vectorstore=object(), chunks=[_doc("a", "L1")])  # type: ignore[arg-type]
        assert kb.by_layer("L99") == []

    def test_default_collection_name(self) -> None:
        kb = KnowledgeBase(vectorstore=object(), chunks=[])  # type: ignore[arg-type]
        assert kb.collection == "whattowear_kb"


class TestGetKbRequiresCorpusLocalDir:
    @pytest.fixture(autouse=True)
    def _reset_caches(self):
        get_kb.cache_clear()
        get_settings.cache_clear()
        yield
        get_kb.cache_clear()
        get_settings.cache_clear()

    def test_raises_clearly_when_corpus_local_dir_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost/db")
        monkeypatch.setenv("CORPUS_LOCAL_DIR", "")
        with pytest.raises(RuntimeError, match="CORPUS_LOCAL_DIR"):
            get_kb()
