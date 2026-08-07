"""Unit tests for ingest/build_kb.py — never had one before this port.
Covers the offline-safe parts (_validate, ingest_all against a small fake
manifest+corpus, the reference-only-leak guard in print_report). No
embedding/gateway call — build_vectorstore itself isn't exercised here.
"""

from __future__ import annotations

import json

import pytest
import yaml
from langchain_core.documents import Document

from whattowear.ingest.build_kb import _validate, ingest_all, load_manifest, print_report


def _doc(rule_id: str, **extra: object) -> Document:
    return Document(
        page_content="text", metadata={"source": "s", "url": "u", "layer": "L1", "rule_id": rule_id, **extra}
    )


class TestValidate:
    def test_passes_with_complete_unique_metadata(self) -> None:
        _validate([_doc("a"), _doc("b")])  # must not raise

    def test_raises_on_missing_required_metadata(self) -> None:
        incomplete = Document(page_content="t", metadata={"source": "s", "url": "u", "layer": "L1"})
        with pytest.raises(ValueError, match="rule_id"):
            _validate([incomplete])

    def test_raises_on_duplicate_rule_id(self) -> None:
        with pytest.raises(ValueError, match="duplicate rule_id"):
            _validate([_doc("dup"), _doc("dup")])


class TestIngestAll:
    def _write_manifest_and_corpus(self, tmp_path, manifest_entries: list[dict]) -> tuple:
        corpus_dir = tmp_path / "corpus"
        (corpus_dir / "kb").mkdir(parents=True, exist_ok=True)
        manifest_path = tmp_path / "corpus.yaml"
        manifest_path.write_text(yaml.safe_dump({"sources": manifest_entries}), encoding="utf-8")
        return manifest_path, corpus_dir

    def test_loads_and_chunks_ingestable_sources(self, tmp_path) -> None:
        (tmp_path / "corpus" / "kb").mkdir(parents=True, exist_ok=True)
        cards_path = tmp_path / "corpus" / "kb" / "l1_rules.jsonl"
        cards_path.write_text(json.dumps({"rule_id": "L1-a", "text": "rule text", "url": "u"}), encoding="utf-8")
        manifest_path, corpus_dir = self._write_manifest_and_corpus(
            tmp_path,
            [
                {
                    "name": "distilled rules",
                    "layer": "L1",
                    "loader": "cards",
                    "path": "kb/l1_rules.jsonl",
                    "chunker": "atomic",
                    "ingest": True,
                }
            ],
        )
        chunks = ingest_all(corpus_dir, manifest_path=manifest_path)
        assert len(chunks) == 1
        assert chunks[0].metadata["rule_id"] == "L1-a"

    def test_skips_non_ingestable_sources(self, tmp_path) -> None:
        manifest_path, corpus_dir = self._write_manifest_and_corpus(
            tmp_path,
            [{"name": "want-later", "layer": "L1", "status": "want-later", "ingest": False}],
        )
        chunks = ingest_all(corpus_dir, manifest_path=manifest_path)
        assert chunks == []

    def test_skips_a_source_with_zero_loaded_docs_without_raising(self, tmp_path) -> None:
        manifest_path, corpus_dir = self._write_manifest_and_corpus(
            tmp_path,
            [
                {
                    "name": "missing wiki page",
                    "layer": "L1",
                    "loader": "wiki_md",
                    "path": "wikipedia/does-not-exist.md",
                    "chunker": "section",
                    "ingest": True,
                }
            ],
        )
        chunks = ingest_all(corpus_dir, manifest_path=manifest_path)
        assert chunks == []


class TestPrintReportReferenceOnlyGuard:
    def test_raises_if_reference_only_book_text_leaked_into_chunks(self, monkeypatch) -> None:
        # patch load_manifest itself, not MANIFEST_PATH: it's a default
        # *argument value*, bound once when the module was first imported
        # — reassigning the module-level constant afterward doesn't change
        # what an already-defined function's default already captured.
        fake_sources = [{"name": "Copyrighted Book", "layer": "L1", "loader": "reference_only", "ingest": False}]
        monkeypatch.setattr("whattowear.ingest.build_kb.load_manifest", lambda: fake_sources)
        leaked_chunk = _doc("L1-leaked", source="Copyrighted Book")

        with pytest.raises(AssertionError, match="leaked"):
            print_report([leaked_chunk])

    def test_passes_when_no_reference_only_source_leaked(self, monkeypatch, capsys) -> None:
        fake_sources = [{"name": "PD Book", "layer": "L1", "loader": "epub", "ingest": True}]
        monkeypatch.setattr("whattowear.ingest.build_kb.load_manifest", lambda: fake_sources)

        print_report([_doc("L1-clean", source="PD Book")])

        assert "OK" in capsys.readouterr().out


def test_load_manifest_reads_the_sources_key(tmp_path) -> None:
    manifest_path = tmp_path / "corpus.yaml"
    manifest_path.write_text(yaml.safe_dump({"sources": [{"name": "x"}]}), encoding="utf-8")
    assert load_manifest(manifest_path) == [{"name": "x"}]
