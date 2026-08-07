"""Unit tests for pipeline/cite.py — never had one before this port."""

from __future__ import annotations

from langchain_core.documents import Document

from whattowear.pipeline.cite import (
    all_cites_grounded,
    build_result,
    cited_rule_ids,
    every_choice_cites,
    owned_only,
    render_text,
)
from whattowear.pipeline.generator import GenOutfit, GenOutput, GenRationale
from whattowear.retrieval.base import RetrievalResult
from whattowear.schema import Context


def _gen(outfits: list[GenOutfit]) -> GenOutput:
    return GenOutput(outfits=outfits)


class TestCitedRuleIds:
    def test_collects_all_cites_across_outfits_and_rationale_lines(self) -> None:
        gen = _gen(
            [
                GenOutfit(
                    items=["a"],
                    rationale=[
                        GenRationale(text="r1", cites=["L1-a", "L1-b"]),
                        GenRationale(text="r2", cites=["L1-c"]),
                    ],
                )
            ]
        )
        assert cited_rule_ids(gen) == ["L1-a", "L1-b", "L1-c"]


class TestOwnedOnly:
    def test_true_when_all_items_owned(self) -> None:
        gen = _gen([GenOutfit(items=["a", "b"], rationale=[])])
        ok, offending = owned_only(gen, {"a", "b"})
        assert ok is True
        assert offending == []

    def test_false_with_hallucinated_item(self) -> None:
        gen = _gen([GenOutfit(items=["a", "ghost"], rationale=[])])
        ok, offending = owned_only(gen, {"a"})
        assert ok is False
        assert offending == ["ghost"]


class TestAllCitesGrounded:
    def test_true_when_every_cite_was_retrieved(self) -> None:
        gen = _gen([GenOutfit(items=["a"], rationale=[GenRationale(text="r", cites=["L1-a"])])])
        ok, bad = all_cites_grounded(gen, {"L1-a"})
        assert ok is True
        assert bad == []

    def test_false_with_invented_rule_id(self) -> None:
        gen = _gen([GenOutfit(items=["a"], rationale=[GenRationale(text="r", cites=["L1-invented"])])])
        ok, bad = all_cites_grounded(gen, {"L1-a"})
        assert ok is False
        assert bad == ["L1-invented"]


class TestEveryChoiceCites:
    def test_true_when_every_rationale_line_cites(self) -> None:
        gen = _gen([GenOutfit(items=["a"], rationale=[GenRationale(text="r", cites=["L1-a"])])])
        assert every_choice_cites(gen) is True

    def test_false_when_a_rationale_line_has_no_citation(self) -> None:
        gen = _gen([GenOutfit(items=["a"], rationale=[GenRationale(text="r", cites=[])])])
        assert every_choice_cites(gen) is False

    def test_honest_empty_outfit_list_is_vacuously_true(self) -> None:
        # constitution Principle IV: the deterministic fallback returns
        # cites=[] rather than fabricate one -- an outfit list with no
        # rationale lines at all must not be penalized here.
        assert every_choice_cites(_gen([])) is True


class TestBuildResult:
    def test_resolves_sources_from_retrieval_metadata(self) -> None:
        doc = Document(page_content="text", metadata={"rule_id": "L1-a", "source": "src", "url": "u", "layer": "L1"})
        gen = _gen([GenOutfit(items=["a"], rationale=[GenRationale(text="r", cites=["L1-a"])])])
        ctx = Context(occasion="office", formality="business_casual")

        result = build_result(ctx, gen, RetrievalResult(l1=[doc]))

        assert len(result.sources) == 1
        assert result.sources[0].rule_id == "L1-a"
        assert result.outfits[0].items == ["a"]

    def test_unresolvable_cite_is_silently_skipped_in_sources(self) -> None:
        gen = _gen([GenOutfit(items=["a"], rationale=[GenRationale(text="r", cites=["L1-unknown"])])])
        ctx = Context(occasion="office", formality="business_casual")

        result = build_result(ctx, gen, RetrievalResult())

        assert result.sources == []

    def test_duplicate_cites_produce_one_source_entry(self) -> None:
        doc = Document(page_content="text", metadata={"rule_id": "L1-a", "source": "src", "url": "u", "layer": "L1"})
        gen = _gen(
            [
                GenOutfit(items=["a"], rationale=[GenRationale(text="r1", cites=["L1-a"])]),
                GenOutfit(items=["b"], rationale=[GenRationale(text="r2", cites=["L1-a"])]),
            ]
        )
        ctx = Context(occasion="office", formality="business_casual")

        result = build_result(ctx, gen, RetrievalResult(l1=[doc]))

        assert len(result.sources) == 1


class TestRenderText:
    def test_includes_outfit_and_rationale_and_sources(self) -> None:
        doc = Document(page_content="text", metadata={"rule_id": "L1-a", "source": "src", "url": "u", "layer": "L1"})
        gen = _gen([GenOutfit(items=["a"], rationale=[GenRationale(text="great pick", cites=["L1-a"])])])
        ctx = Context(occasion="office", formality="business_casual")
        result = build_result(ctx, gen, RetrievalResult(l1=[doc]))

        text = render_text(result)

        assert "great pick" in text
        assert "L1-a" in text
        assert "Sources:" in text

    def test_no_sources_omits_the_sources_section(self) -> None:
        gen = _gen([])
        ctx = Context(occasion="office", formality="business_casual")
        result = build_result(ctx, gen, RetrievalResult())

        text = render_text(result)

        assert "Sources:" not in text
