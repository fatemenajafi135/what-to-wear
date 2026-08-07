"""Unit tests for ingest/cli.py's idempotency bookkeeping — never had one
before this port (this whole file is new — FR-011/SC-005). No live
gateway/embedding call; `main()`'s embed path isn't exercised here.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from whattowear.ingest.cli import _current_hashes, _hash_file, _load_state, _save_state


def _patch_load_manifest(monkeypatch: pytest.MonkeyPatch, manifest_path: Path) -> None:
    sources = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))["sources"]
    monkeypatch.setattr("whattowear.ingest.cli.load_manifest", lambda: sources)


class TestHashFile:
    def test_same_content_same_hash(self, tmp_path) -> None:
        a = tmp_path / "a.txt"
        b = tmp_path / "b.txt"
        a.write_text("identical content", encoding="utf-8")
        b.write_text("identical content", encoding="utf-8")
        assert _hash_file(a) == _hash_file(b)

    def test_different_content_different_hash(self, tmp_path) -> None:
        a = tmp_path / "a.txt"
        b = tmp_path / "b.txt"
        a.write_text("content one", encoding="utf-8")
        b.write_text("content two", encoding="utf-8")
        assert _hash_file(a) != _hash_file(b)


class TestStateRoundTrip:
    def test_missing_state_file_is_empty_dict(self, tmp_path) -> None:
        assert _load_state(tmp_path) == {}

    def test_save_then_load_round_trips(self, tmp_path) -> None:
        state = {"source-a": "hash1", "source-b": "hash2"}
        _save_state(tmp_path, state)
        assert _load_state(tmp_path) == state

    def test_state_file_lives_inside_corpus_dir_not_the_repo(self, tmp_path) -> None:
        _save_state(tmp_path, {"x": "y"})
        assert (tmp_path / ".ingest_state.json").exists()


class TestCurrentHashes:
    def test_hashes_every_ingestable_file_backed_source(self, tmp_path, monkeypatch) -> None:
        (tmp_path / "kb").mkdir()
        card_path = tmp_path / "kb" / "l1_rules.jsonl"
        card_path.write_text(json.dumps({"rule_id": "L1-a", "text": "x"}), encoding="utf-8")

        manifest_path = tmp_path / "corpus.yaml"
        manifest_path.write_text(
            yaml.safe_dump(
                {
                    "sources": [
                        {"name": "distilled rules", "ingest": True, "path": "kb/l1_rules.jsonl"},
                        {"name": "not ingestable", "ingest": False, "path": "kb/other.jsonl"},
                        {"name": "no path field", "ingest": True},
                    ]
                }
            ),
            encoding="utf-8",
        )
        # _current_hashes calls the `load_manifest` name as imported into
        # ingest/cli.py's own namespace (`from .build_kb import
        # load_manifest`) — patching build_kb's copy of the name doesn't
        # reach it; cli.py's binding is what has to be patched.
        _patch_load_manifest(monkeypatch, manifest_path)

        hashes = _current_hashes(tmp_path)

        assert set(hashes) == {"distilled rules"}
        assert hashes["distilled rules"] == _hash_file(card_path)

    def test_missing_local_file_is_silently_skipped(self, tmp_path, monkeypatch) -> None:
        manifest_path = tmp_path / "corpus.yaml"
        manifest_path.write_text(
            yaml.safe_dump({"sources": [{"name": "missing", "ingest": True, "path": "kb/missing.jsonl"}]}),
            encoding="utf-8",
        )
        _patch_load_manifest(monkeypatch, manifest_path)

        assert _current_hashes(tmp_path) == {}

    def test_unchanged_content_reproduces_the_same_hash_map(self, tmp_path, monkeypatch) -> None:
        (tmp_path / "kb").mkdir()
        (tmp_path / "kb" / "l1_rules.jsonl").write_text(json.dumps({"rule_id": "L1-a", "text": "x"}), encoding="utf-8")
        manifest_path = tmp_path / "corpus.yaml"
        manifest_path.write_text(
            yaml.safe_dump({"sources": [{"name": "distilled rules", "ingest": True, "path": "kb/l1_rules.jsonl"}]}),
            encoding="utf-8",
        )
        _patch_load_manifest(monkeypatch, manifest_path)

        first = _current_hashes(tmp_path)
        second = _current_hashes(tmp_path)

        assert first == second
