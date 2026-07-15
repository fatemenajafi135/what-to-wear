"""Unit tests for pipeline/cite.py (Feature 002 Phase 1 backfill).

Covers the pure grounding checks reused by eval Harness B (owned-items,
grounded-cites, every-choice-cites) and the final citation assembly/rendering.
No LLM or retrieval I/O — GenOutput and RetrievalResult are constructed by hand.
"""

from __future__ import annotations

from langchain_core.documents import Document

from whattowear.pipeline import cite
from whattowear.pipeline.generator import GenOutfit, GenOutput, GenRationale
from whattowear.retrieval.base import RetrievalResult
from whattowear.schema import Context


def _gen(*outfits: GenOutfit) -> GenOutput:
    return GenOutput(outfits=list(outfits))


def _outfit(items, cites) -> GenOutfit:
    return GenOutfit(items=items, rationale=[GenRationale(text="because", cites=cites)])


def _doc(rule_id, source="Vogue", url="http://x", layer="L1") -> Document:
    return Document(
        page_content="rule text",
        metadata={"rule_id": rule_id, "source": source, "url": url, "layer": layer},
    )


class TestCitedRuleIds:
    def test_collects_all_cites_across_outfits_in_order(self):
        gen = _gen(_outfit(["a"], ["R1", "R2"]), _outfit(["b"], ["R3"]))
        assert cite.cited_rule_ids(gen) == ["R1", "R2", "R3"]


class TestOwnedOnly:
    def test_all_items_owned_passes(self):
        gen = _gen(_outfit(["a", "b"], ["R1"]))
        ok, offending = cite.owned_only(gen, {"a", "b", "c"})
        assert ok is True
        assert offending == []

    def test_hallucinated_item_flagged(self):
        gen = _gen(_outfit(["a", "ghost"], ["R1"]))
        ok, offending = cite.owned_only(gen, {"a"})
        assert ok is False
        assert offending == ["ghost"]


class TestAllCitesGrounded:
    def test_all_cited_ids_retrieved_passes(self):
        gen = _gen(_outfit(["a"], ["R1", "R2"]))
        ok, bad = cite.all_cites_grounded(gen, {"R1", "R2", "R3"})
        assert ok is True
        assert bad == []

    def test_invented_rule_id_flagged(self):
        gen = _gen(_outfit(["a"], ["R1", "MADE_UP"]))
        ok, bad = cite.all_cites_grounded(gen, {"R1"})
        assert ok is False
        assert bad == ["MADE_UP"]


class TestEveryChoiceCites:
    def test_true_when_every_rationale_cites(self):
        assert cite.every_choice_cites(_gen(_outfit(["a"], ["R1"]))) is True

    def test_false_when_a_rationale_has_no_cites(self):
        gen = _gen(_outfit(["a"], []))
        assert cite.every_choice_cites(gen) is False


class TestBuildResult:
    def _ctx(self) -> Context:
        return Context(occasion="dinner", formality="smart_casual")

    def test_resolves_cited_sources_and_dedupes(self):
        gen = _gen(_outfit(["a"], ["R1", "R1"]), _outfit(["b"], ["R2"]))
        retrieval = RetrievalResult(l1=[_doc("R1")], l4=[_doc("R2", layer="L4")])

        result = cite.build_result(self._ctx(), gen, retrieval)

        assert [o.items for o in result.outfits] == [["a"], ["b"]]
        assert sorted(s.rule_id for s in result.sources) == ["R1", "R2"]

    def test_cited_rule_not_in_retrieval_is_skipped_not_crash(self):
        gen = _gen(_outfit(["a"], ["R1", "UNKNOWN"]))
        retrieval = RetrievalResult(l1=[_doc("R1")])

        result = cite.build_result(self._ctx(), gen, retrieval)

        assert [s.rule_id for s in result.sources] == ["R1"]


class TestRenderText:
    def test_renders_items_rationale_and_sources(self):
        gen = _gen(_outfit(["a", "b"], ["R1"]))
        retrieval = RetrievalResult(l1=[_doc("R1", source="Vogue", url="http://v")])
        result = cite.build_result(Context(occasion="x", formality="casual"), gen, retrieval)

        text = cite.render_text(result)

        assert "Outfit 1: a, b" in text
        assert "[cites: R1]" in text
        assert "Sources:" in text
        assert "[R1] Vogue — http://v" in text
