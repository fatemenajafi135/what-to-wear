"""Unit tests for ingest/loaders.py — never had one before this port.
All paths resolve relative to an injected `corpus_dir` (tmp_path), never
`REPO_ROOT` — the fix this feature makes (constitution Principle X)."""

from __future__ import annotations

import json

from whattowear.ingest.loaders import load_cards, load_epub, load_source, load_wiki_md


class TestLoadCards:
    def test_loads_one_document_per_jsonl_line(self, tmp_path) -> None:
        cards_dir = tmp_path / "kb"
        cards_dir.mkdir()
        cards_file = cards_dir / "l1_rules.jsonl"
        cards_file.write_text(
            "\n".join(
                [
                    json.dumps({"rule_id": "L1-a", "text": "rule one", "url": "u1"}),
                    json.dumps({"rule_id": "L1-b", "text": "rule two", "url": "u2"}),
                ]
            ),
            encoding="utf-8",
        )
        source = {"name": "cards", "path": "kb/l1_rules.jsonl", "layer": "L1", "license": "own"}

        docs = load_cards(source, tmp_path)

        assert len(docs) == 2
        assert docs[0].metadata["rule_id"] == "L1-a"
        assert docs[0].page_content == "rule one"
        assert docs[0].metadata["license"] == "own"

    def test_skips_blank_lines(self, tmp_path) -> None:
        cards_file = tmp_path / "cards.jsonl"
        cards_file.write_text(json.dumps({"rule_id": "L1-a", "text": "x", "url": "u"}) + "\n\n\n", encoding="utf-8")
        source = {"name": "cards", "path": "cards.jsonl", "layer": "L1"}

        docs = load_cards(source, tmp_path)

        assert len(docs) == 1

    def test_optional_structured_fields_carried_when_present(self, tmp_path) -> None:
        cards_file = tmp_path / "cards.jsonl"
        cards_file.write_text(
            json.dumps({"rule_id": "L4-a", "text": "x", "formality": "formal", "temp_band": "cold"}),
            encoding="utf-8",
        )
        source = {"name": "cards", "path": "cards.jsonl", "layer": "L4"}

        [doc] = load_cards(source, tmp_path)

        assert doc.metadata["formality"] == "formal"
        assert doc.metadata["temp_band"] == "cold"


class TestLoadWikiMd:
    def test_loads_refined_markdown_file(self, tmp_path) -> None:
        wiki_dir = tmp_path / "wikipedia"
        wiki_dir.mkdir()
        md_file = wiki_dir / "Color theory - Wikipedia.md"
        md_file.write_text("<!-- refined from: x.html -->\n\n# Color theory\n\nSome prose.", encoding="utf-8")
        source = {"name": "Wikipedia: Color theory", "path": "wikipedia/Color theory - Wikipedia.md", "layer": "L1"}

        [doc] = load_wiki_md(source, tmp_path)

        assert "<!--" not in doc.page_content
        assert "# Color theory" in doc.page_content
        assert doc.metadata["layer"] == "L1"

    def test_missing_file_returns_empty_list_not_an_error(self, tmp_path) -> None:
        source = {"name": "missing", "path": "wikipedia/does-not-exist.md", "layer": "L1"}
        assert load_wiki_md(source, tmp_path) == []


class TestLoadEpub:
    def test_missing_file_returns_empty_list_not_an_error(self, tmp_path) -> None:
        source = {"name": "missing book", "path": "books/does-not-exist.epub", "layer": "L1"}
        assert load_epub(source, tmp_path) == []


class TestLoadSource:
    def test_ingest_false_returns_nothing_regardless_of_loader(self, tmp_path) -> None:
        source = {"name": "ref only", "ingest": False, "loader": "epub", "path": "books/x.epub", "layer": "L1"}
        assert load_source(source, tmp_path) == []

    def test_unknown_loader_returns_nothing(self, tmp_path) -> None:
        source = {"name": "x", "ingest": True, "loader": "not-a-real-loader", "layer": "L1"}
        assert load_source(source, tmp_path) == []

    def test_dispatches_to_the_named_loader(self, tmp_path) -> None:
        cards_file = tmp_path / "cards.jsonl"
        cards_file.write_text(json.dumps({"rule_id": "L1-a", "text": "x"}), encoding="utf-8")
        source = {"name": "cards", "ingest": True, "loader": "cards", "path": "cards.jsonl", "layer": "L1"}

        docs = load_source(source, tmp_path)

        assert len(docs) == 1
