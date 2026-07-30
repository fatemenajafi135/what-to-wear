"""Unit tests for retrieval/hybrid.py.

Feature 007 Task A: retrieve_l1() gains a semantic-search branch over the
already-embedded long-form L1 chunks, unioned with the existing atomic
load-all.
Feature 007 Task B: retrieve_l3() calls Tavily live instead of querying a
static pre-ingested collection, and degrades gracefully on failure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from unittest.mock import patch

from langchain_core.documents import Document

from whattowear.retrieval import hybrid
from whattowear.schema import Context


def _doc(rule_id: str, layer: str, granularity: str, text: str = "text") -> Document:
    return Document(
        page_content=text,
        metadata={
            "source": "src",
            "url": "https://example.com",
            "layer": layer,
            "rule_id": rule_id,
            "granularity": granularity,
        },
    )


@dataclass
class _FakeKB:
    """Minimal KnowledgeBase double: .by_layer() over static chunks, plus a
    stubbed .vectorstore.similarity_search()."""

    chunks: list[Document] = field(default_factory=list)
    semantic_results: list[Document] = field(default_factory=list)
    last_search_args: dict | None = None

    def by_layer(self, layer: str) -> list[Document]:
        return [c for c in self.chunks if c.metadata.get("layer") == layer]

    @property
    def vectorstore(self):
        outer = self

        class _VS:
            def similarity_search(self, query, k=5, filter=None):
                outer.last_search_args = {"query": query, "k": k, "filter": filter}
                return outer.semantic_results

        return _VS()


class TestRetrieveL1:
    def test_returns_union_of_atomic_and_semantic_chunks(self):
        atomic = [_doc("L1-card-1", "L1", "atomic")]
        semantic = [_doc("L1-wiki-sec-000", "L1", "section")]
        kb = _FakeKB(chunks=atomic, semantic_results=semantic)
        ctx = Context(occasion="wedding", formality="formal")

        result = hybrid.retrieve_l1(kb, ctx, semantic_query="formal wedding attire")

        granularities = {d.metadata["granularity"] for d in result}
        assert granularities == {"atomic", "section"}
        assert {d.metadata["rule_id"] for d in result} == {"L1-card-1", "L1-wiki-sec-000"}

    def test_no_semantic_query_skips_the_semantic_branch(self):
        kb = _FakeKB(
            chunks=[_doc("L1-card-1", "L1", "atomic")], semantic_results=[_doc("L1-wiki-sec-000", "L1", "section")]
        )
        ctx = Context(occasion="wedding", formality="formal")

        result = hybrid.retrieve_l1(kb, ctx, semantic_query="")

        assert kb.last_search_args is None
        assert {d.metadata["rule_id"] for d in result} == {"L1-card-1"}

    def test_semantic_branch_filters_by_layer_and_section_granularity(self):
        kb = _FakeKB(chunks=[], semantic_results=[])
        ctx = Context(occasion="office", formality="business_casual")

        hybrid.retrieve_l1(kb, ctx, semantic_query="color contrast")

        assert kb.last_search_args["query"] == "color contrast"
        must = kb.last_search_args["filter"].must
        conditions = {c.key: c.match.value for c in must}
        assert conditions == {"metadata.layer": "L1", "metadata.granularity": "section"}

    def test_no_duplicate_rule_ids_between_atomic_and_semantic_pools(self):
        # defensive de-dup: even if the semantic branch somehow returned a
        # rule_id already in the atomic pool, it shouldn't appear twice.
        shared = _doc("L1-card-1", "L1", "atomic")
        kb = _FakeKB(chunks=[shared], semantic_results=[shared])
        ctx = Context(occasion="office", formality="business_casual")

        result = hybrid.retrieve_l1(kb, ctx, semantic_query="anything")

        assert [d.metadata["rule_id"] for d in result].count("L1-card-1") == 1

    def test_color_filter_narrows_only_the_atomic_pool(self):
        from whattowear.schema import WardrobeItem

        atomic = [
            _doc("L1-navy", "L1", "atomic", text="navy pairs well with white"),
            _doc("L1-unrelated", "L1", "atomic", text="a general proportion rule"),
            _doc("L1-also-unrelated", "L1", "atomic", text="another general rule"),
        ]
        semantic = [_doc("L1-wiki-sec-000", "L1", "section", text="a long passage about color theory")]
        kb = _FakeKB(chunks=atomic, semantic_results=semantic)
        wardrobe = [WardrobeItem(id="1", category="top", colors=["#000080"], formality="casual", warmth=1)]
        ctx = Context(occasion="office", formality="business_casual", wardrobe=wardrobe)

        result = hybrid.retrieve_l1(kb, ctx, semantic_query="office outfit", color_filter=True)

        rule_ids = {d.metadata["rule_id"] for d in result}
        # the semantic chunk is present regardless of color_filter (unaffected by it)
        assert "L1-wiki-sec-000" in rule_ids
        # the atomic pool's narrowing behavior is unchanged: too few matches
        # (<3) falls back to all atomic rules, same as before this feature
        assert "L1-navy" in rule_ids


class TestRetrieveL3Live:
    def test_maps_tavily_results_into_citable_documents(self):
        fake_results = [
            {"title": "Autumn trends", "url": "https://example.com/a", "content": "Wide trousers are back."},
            {"title": "Layering guide", "url": "https://example.com/b", "content": "Layer light knits under coats."},
        ]
        with patch("whattowear.external.trends.search_trends", return_value=fake_results) as mock_search:
            docs = hybrid.retrieve_l3("autumn office trends", k=5)

        mock_search.assert_called_once_with("autumn office trends", max_results=5)
        assert len(docs) == 2
        for d, r in zip(docs, fake_results, strict=True):
            assert d.page_content == r["content"]
            assert d.metadata["url"] == r["url"]
            assert d.metadata["layer"] == "L3"
            assert d.metadata["rule_id"].startswith("L3-live-")
            assert d.metadata["granularity"] == "live"

    def test_same_url_produces_a_stable_rule_id_within_a_run(self):
        fake_results = [{"title": "t", "url": "https://example.com/a", "content": "c"}]
        with patch("whattowear.external.trends.search_trends", return_value=fake_results):
            docs1 = hybrid.retrieve_l3("q", k=5)
            docs2 = hybrid.retrieve_l3("q", k=5)
        assert docs1[0].metadata["rule_id"] == docs2[0].metadata["rule_id"]

    def test_tavily_failure_degrades_to_empty_list(self):
        with patch("whattowear.external.trends.search_trends", side_effect=RuntimeError("timeout")):
            docs = hybrid.retrieve_l3("autumn office trends", k=5)
        assert docs == []

    def test_no_kb_parameter_required(self):
        # retrieve_l3 no longer needs the KnowledgeBase -- it never touches
        # the vectorstore now that L3 is live.
        with patch("whattowear.external.trends.search_trends", return_value=[]):
            docs = hybrid.retrieve_l3("q")
        assert docs == []
