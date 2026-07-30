"""ports.py Protocol shapes — structural (duck-typed) conformance only.

Deliberately does not import `schema.WardrobeItem` or any concrete binding
(`ChatLiteLLM`, `QdrantVectorStore`) — those land in later phases. What this
test protects is the Protocol *shape* itself: a plain object with the right
method names satisfies it, and one missing a method does not.
"""

from __future__ import annotations

from whattowear.ports import ClosetRepository, LLMClient, VectorStore


class _FakeVectorStore:
    def similarity_search(self, query: str, k: int, filter: dict | None = None) -> list:
        return []


class _FakeLLMClient:
    def with_structured_output(self, schema: type) -> _FakeLLMClient:
        return self

    def invoke(self, messages: list) -> object:
        return None


class _FakeClosetRepository:
    def list_wardrobe_items(self, user_id: str) -> list:
        return []

    def list_catalog_items(self) -> list:
        return []

    def get_derivation_inputs(self, user_id: str) -> tuple[list, dict]:
        return [], {}


class _Incomplete:
    """Missing every Protocol method — must satisfy none of them."""


def test_vector_store_protocol_structural_match() -> None:
    assert isinstance(_FakeVectorStore(), VectorStore)
    assert not isinstance(_Incomplete(), VectorStore)


def test_llm_client_protocol_structural_match() -> None:
    assert isinstance(_FakeLLMClient(), LLMClient)
    assert not isinstance(_Incomplete(), LLMClient)


def test_closet_repository_protocol_structural_match() -> None:
    assert isinstance(_FakeClosetRepository(), ClosetRepository)
    assert not isinstance(_Incomplete(), ClosetRepository)
