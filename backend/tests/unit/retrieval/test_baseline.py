"""Unit tests for retrieval/baseline.py — never had one before this port
despite being the A/B control the recorded baselines depend on."""

from __future__ import annotations

from dataclasses import dataclass, field

from langchain_core.documents import Document

from whattowear.retrieval import baseline


def _doc(rule_id: str, layer: str) -> Document:
    return Document(page_content="t", metadata={"source": "s", "url": "u", "layer": layer, "rule_id": rule_id})


@dataclass
class _FakeKB:
    docs: list[Document] = field(default_factory=list)
    last_query: str | None = None
    last_k: int | None = None

    @property
    def vectorstore(self) -> _FakeVectorStore:
        return _FakeVectorStore(self)


@dataclass
class _FakeVectorStore:
    kb: _FakeKB

    def similarity_search(self, query: str, k: int = 8) -> list[Document]:
        self.kb.last_query = query
        self.kb.last_k = k
        return self.kb.docs


def test_buckets_results_by_layer() -> None:
    kb = _FakeKB(docs=[_doc("a", "L1"), _doc("b", "L3"), _doc("c", "L4")])

    result = baseline.retrieve(kb, "office outfit")

    assert [d.metadata["rule_id"] for d in result.l1] == ["a"]
    assert [d.metadata["rule_id"] for d in result.l3] == ["b"]
    assert [d.metadata["rule_id"] for d in result.l4] == ["c"]
    assert result.strategy == "baseline"


def test_unknown_layer_defaults_to_l1_bucket() -> None:
    kb = _FakeKB(docs=[_doc("x", "L2")])
    result = baseline.retrieve(kb, "q")
    assert [d.metadata["rule_id"] for d in result.l1] == ["x"]


def test_passes_query_and_k_through_to_the_vectorstore() -> None:
    kb = _FakeKB(docs=[])
    baseline.retrieve(kb, "cold weather formal", k=3)
    assert kb.last_query == "cold weather formal"
    assert kb.last_k == 3


def test_default_k_is_eight() -> None:
    kb = _FakeKB(docs=[])
    baseline.retrieve(kb, "q")
    assert kb.last_k == 8
