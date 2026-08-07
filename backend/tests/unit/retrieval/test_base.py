"""Unit tests for retrieval/base.py::RetrievalResult — never had one before
this port despite 11 references across the codebase."""

from __future__ import annotations

from langchain_core.documents import Document

from whattowear.retrieval.base import RetrievalResult


def _doc(rule_id: str) -> Document:
    return Document(page_content="t", metadata={"source": "s", "url": "u", "layer": "L1", "rule_id": rule_id})


def test_defaults_are_empty() -> None:
    result = RetrievalResult()
    assert result.l1 == result.l3 == result.l4 == []
    assert result.strategy == "hybrid"


def test_all_orders_l4_then_l1_then_l3() -> None:
    result = RetrievalResult(l1=[_doc("a")], l3=[_doc("b")], l4=[_doc("c")])
    assert [d.metadata["rule_id"] for d in result.all()] == ["c", "a", "b"]


def test_rule_ids_matches_all_order() -> None:
    result = RetrievalResult(l1=[_doc("a")], l4=[_doc("c")])
    assert result.rule_ids() == ["c", "a"]


def test_independent_instances_do_not_share_default_lists() -> None:
    # dataclass default_factory regression guard: two instances' l1 lists
    # must not be the same object.
    a, b = RetrievalResult(), RetrievalResult()
    a.l1.append(_doc("x"))
    assert b.l1 == []
