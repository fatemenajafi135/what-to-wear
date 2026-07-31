"""Unit tests for ingest/chunkers.py — never had one before this port."""

from __future__ import annotations

from langchain_core.documents import Document

from whattowear.ingest.chunkers import chunk_atomic, chunk_docs, chunk_section


def _doc(text: str, **meta: object) -> Document:
    return Document(page_content=text, metadata={"layer": "L1", "source": "src", **meta})


class TestChunkAtomic:
    def test_preserves_existing_rule_id(self) -> None:
        [chunk] = chunk_atomic([_doc("text", rule_id="L1-my-rule")])
        assert chunk.metadata["rule_id"] == "L1-my-rule"

    def test_synthesizes_rule_id_when_missing(self) -> None:
        [chunk] = chunk_atomic([_doc("navy pairs well with charcoal")])
        assert chunk.metadata["rule_id"]

    def test_stamps_atomic_granularity(self) -> None:
        [chunk] = chunk_atomic([_doc("text", rule_id="r1")])
        assert chunk.metadata["granularity"] == "atomic"


class TestChunkSection:
    def test_splits_long_text_into_multiple_pieces(self) -> None:
        long_text = "\n\n".join(f"Paragraph {i}. " + "word " * 200 for i in range(5))
        chunks = chunk_section([_doc(long_text)])
        assert len(chunks) > 1

    def test_each_piece_gets_a_unique_stable_rule_id(self) -> None:
        long_text = "\n\n".join(f"Paragraph {i}. " + "word " * 200 for i in range(5))
        chunks = chunk_section([_doc(long_text, source="my source")])
        rule_ids = [c.metadata["rule_id"] for c in chunks]
        assert len(rule_ids) == len(set(rule_ids))
        assert all(rid.startswith("L1-my-source-sec-") for rid in rule_ids)

    def test_stamps_section_granularity(self) -> None:
        [chunk] = chunk_section([_doc("short text")])
        assert chunk.metadata["granularity"] == "section"

    def test_inherits_parent_metadata(self) -> None:
        [chunk] = chunk_section([_doc("short text", license="PD")])
        assert chunk.metadata["license"] == "PD"


class TestChunkDocsDispatch:
    def test_atomic_strategy_dispatches_to_chunk_atomic(self) -> None:
        chunks = chunk_docs([_doc("text", rule_id="r1")], "atomic")
        assert chunks[0].metadata["granularity"] == "atomic"

    def test_unknown_strategy_falls_back_to_section(self) -> None:
        chunks = chunk_docs([_doc("text")], "nonexistent-strategy")
        assert chunks[0].metadata["granularity"] == "section"
