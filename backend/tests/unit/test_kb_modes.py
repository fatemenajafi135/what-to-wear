"""`WTW_KB_MODE` — how the knowledge base is obtained (feature 017).

A deployed backend has no corpus on disk: `CORPUS_LOCAL_DIR` points at a
directory outside the repository, and the Docker build context is `backend/`.
Before this, `get_kb()` raised `CORPUS_LOCAL_DIR is required` on the first
styling request of the first real deploy — the corpus was read even when the
Qdrant collection was already populated and only needed attaching to, because
`retrieval/hybrid.py` reads `kb.by_layer(...)` off the raw chunks.

These tests cover the mode dispatch and the reconnect guards. They use a fake
client rather than a live Qdrant so they run in CI with no services; the
payload shape they fake was verified against a real populated collection.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from whattowear import kb as kb_module


@dataclass
class _Point:
    payload: dict[str, Any] | None


class _FakeClient:
    """Enough of QdrantClient for the reconnect path: existence, count, scroll."""

    def __init__(self, points: list[_Point] | None, *, exists: bool = True) -> None:
        self._points = points or []
        self._exists = exists
        self.scroll_calls = 0

    def collection_exists(self, _collection: str) -> bool:
        return self._exists

    def count(self, _collection: str) -> Any:
        return type("C", (), {"count": len(self._points)})()

    def scroll(
        self, *, collection_name: str, limit: int, offset: Any, with_payload: bool, with_vectors: bool
    ) -> tuple[list[_Point], Any]:
        assert with_vectors is False, "vectors are never needed to rebuild chunks and dominate transfer size"
        self.scroll_calls += 1
        start = offset or 0
        page = self._points[start : start + limit]
        next_offset = start + limit if start + limit < len(self._points) else None
        return page, next_offset


def _doc_point(text: str, layer: str, rule_id: str) -> _Point:
    """The payload shape langchain-qdrant actually writes — confirmed against a
    real collection: top-level `page_content` and `metadata` keys."""
    return _Point(payload={"page_content": text, "metadata": {"layer": layer, "rule_id": rule_id}})


class TestChunkReconstruction:
    def test_rebuilds_documents_from_payloads(self) -> None:
        client = _FakeClient([_doc_point("navy pairs with camel", "L1", "L1-a")])
        chunks = kb_module._chunks_from_qdrant(client, "whattowear_kb")
        assert len(chunks) == 1
        assert chunks[0].page_content == "navy pairs with camel"
        assert chunks[0].metadata["layer"] == "L1"

    def test_pages_through_every_point(self) -> None:
        """391 points in the real collection — well over one scroll page, so a
        single-page implementation would silently drop most of the corpus and
        leave retrieval quietly worse rather than broken."""
        points = [_doc_point(f"rule {i}", "L1", f"L1-{i}") for i in range(kb_module._SCROLL_PAGE * 2 + 7)]
        client = _FakeClient(points)
        chunks = kb_module._chunks_from_qdrant(client, "whattowear_kb")
        assert len(chunks) == len(points)
        assert client.scroll_calls > 1
        assert chunks[-1].page_content == f"rule {len(points) - 1}"

    def test_by_layer_works_on_reconstructed_chunks(self) -> None:
        """`retrieval/hybrid.py` filters by `metadata['layer']`; if metadata
        were lost in reconstruction, retrieval would return nothing and
        styling would be ungrounded rather than failing."""
        client = _FakeClient([_doc_point("a", "L1", "L1-a"), _doc_point("b", "L4", "L4-b")])
        chunks = kb_module._chunks_from_qdrant(client, "whattowear_kb")
        base = kb_module.KnowledgeBase(vectorstore=object(), chunks=chunks)  # type: ignore[arg-type]
        assert [c.page_content for c in base.by_layer("L1")] == ["a"]
        assert [c.page_content for c in base.by_layer("L4")] == ["b"]

    def test_tolerates_a_payload_missing_metadata(self) -> None:
        chunks = kb_module._chunks_from_qdrant(_FakeClient([_Point(payload={"page_content": "x"})]), "c")
        assert chunks[0].metadata == {}


class _Settings:
    def __init__(self, **kw: Any) -> None:
        self.wtw_kb_mode = kw.get("mode", "auto")
        self.corpus_local_dir = kw.get("corpus")
        self.wtw_qdrant_url = kw.get("url")
        self.wtw_qdrant_api_key = None


class TestReconnectGuards:
    """Every one of these must raise rather than return an empty knowledge
    base. An empty KB does not crash — retrieval just returns nothing, and the
    result is ungrounded output that looks like working software."""

    def test_requires_a_qdrant_url(self) -> None:
        with pytest.raises(RuntimeError, match="requires WTW_QDRANT_URL"):
            kb_module._reconnect_kb(_Settings(mode="reconnect"))

    def test_missing_collection_names_how_to_populate_it(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(kb_module, "_reconnect_client", lambda _s: _FakeClient([], exists=False), raising=False)
        with pytest.raises(RuntimeError) as exc:
            kb_module._reconnect_kb(_Settings(mode="reconnect", url="http://q:6333"))
        assert "does not exist" in str(exc.value)
        assert "ingest.cli" in str(exc.value)

    def test_empty_collection_is_an_error_not_an_empty_kb(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(kb_module, "_reconnect_client", lambda _s: _FakeClient([], exists=True), raising=False)
        with pytest.raises(RuntimeError, match="is empty"):
            kb_module._reconnect_kb(_Settings(mode="reconnect", url="http://q:6333"))


class TestModeDispatch:
    def test_rejects_an_unknown_mode(self, monkeypatch: pytest.MonkeyPatch) -> None:
        kb_module.get_kb.cache_clear()
        monkeypatch.setattr(kb_module, "get_settings", lambda: _Settings(mode="postgres"))
        with pytest.raises(RuntimeError, match="WTW_KB_MODE must be one of"):
            kb_module.get_kb()
        kb_module.get_kb.cache_clear()

    def test_corpus_mode_without_a_corpus_points_at_reconnect(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The message a deployed instance hits must say what to do about it —
        the original named only CORPUS_LOCAL_DIR, which is unactionable on a
        host that will never have the corpus."""
        kb_module.get_kb.cache_clear()
        monkeypatch.setattr(kb_module, "get_settings", lambda: _Settings(mode="corpus"))
        with pytest.raises(RuntimeError) as exc:
            kb_module.get_kb()
        assert "WTW_KB_MODE=reconnect" in str(exc.value)
        kb_module.get_kb.cache_clear()

    def test_auto_reconnects_when_no_corpus_is_configured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        kb_module.get_kb.cache_clear()
        monkeypatch.setattr(kb_module, "get_settings", lambda: _Settings(mode="auto", corpus=None))
        called: list[bool] = []

        def _fake_reconnect(_s: Any) -> Any:
            called.append(True)
            return "kb"

        monkeypatch.setattr(kb_module, "_reconnect_kb", _fake_reconnect)
        assert kb_module.get_kb() == "kb"
        assert called == [True]
        kb_module.get_kb.cache_clear()

    def test_auto_prefers_the_corpus_when_one_is_configured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The evaluated path must stay the default wherever a corpus exists —
        local development and the eval harness both depend on it."""
        kb_module.get_kb.cache_clear()
        monkeypatch.setattr(kb_module, "get_settings", lambda: _Settings(mode="auto", corpus="/tmp/corpus"))

        def _must_not_run(_s: Any) -> Any:
            raise AssertionError("auto must not reconnect when CORPUS_LOCAL_DIR is set")

        monkeypatch.setattr(kb_module, "_reconnect_kb", _must_not_run)
        monkeypatch.setattr(kb_module, "ingest_all", lambda *_a, **_k: [])
        monkeypatch.setattr(kb_module, "build_vectorstore", lambda *_a, **_k: object())
        kb_module.get_kb()
        kb_module.get_kb.cache_clear()
