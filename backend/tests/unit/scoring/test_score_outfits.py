"""Unit tests for scoring/__init__.py::score_outfits — never had one before
this port (inventory: the module itself has 45 lines / 2 refs, but no
dedicated test file existed alongside the five per-scorer test files)."""

from __future__ import annotations

from dataclasses import dataclass, field

from whattowear.schema import Context, WardrobeItem
from whattowear.scoring import score_outfits


@dataclass
class _Rationale:
    text: str
    cites: list[str] = field(default_factory=list)


@dataclass
class _GenOutfit:
    items: list[str]
    rationale: list[_Rationale] = field(default_factory=list)


def _item(id: str, category: str, **kwargs: object) -> WardrobeItem:
    defaults = {"colors": ["#000000"], "formality": "casual", "warmth": 1, "season": ["summer"]}
    defaults.update(kwargs)
    return WardrobeItem(id=id, category=category, **defaults)  # type: ignore[arg-type]


def test_scores_every_outfit_on_all_four_dimensions() -> None:
    wardrobe_by_id = {"t": _item("t", "top"), "j": _item("j", "jeans")}
    ctx = Context(occasion="dinner", formality="casual")
    gen_outfits = [_GenOutfit(items=["t", "j"], rationale=[_Rationale(text="because", cites=["r1"])])]

    [scored] = score_outfits(gen_outfits, wardrobe_by_id, ctx)

    assert len(scored.scores) == 4
    assert {s.dimension for s in scored.scores} == {
        "color_harmony",
        "formality_coherence",
        "weather_fitness",
        "silhouette_balance",
    }
    assert scored.rationale[0].text == "because"
    assert scored.rationale[0].cites == ["r1"]


def test_ranks_multiple_outfits_descending_by_rank_score() -> None:
    wardrobe_by_id = {
        "t": _item("t", "top", formality="casual"),
        "j": _item("j", "jeans", formality="casual"),
        "coat": _item("coat", "coat", warmth=4, formality="formal"),
        "gown": _item("gown", "gown", warmth=4, formality="formal"),
    }
    ctx = Context(occasion="dinner", formality="casual", temp_band="cold")
    gen_outfits = [
        _GenOutfit(items=["t", "j"]),  # no outerwear in a cold context — weaker fit
        _GenOutfit(items=["t", "j", "coat"]),  # has outerwear — stronger weather fit
    ]

    ranked = score_outfits(gen_outfits, wardrobe_by_id, ctx)

    assert ranked[0].rank_score >= ranked[1].rank_score


def test_unknown_item_ids_are_silently_skipped_not_errored() -> None:
    wardrobe_by_id = {"t": _item("t", "top")}
    ctx = Context(occasion="dinner", formality="casual")
    gen_outfits = [_GenOutfit(items=["t", "ghost-id"])]

    [scored] = score_outfits(gen_outfits, wardrobe_by_id, ctx)

    assert len(scored.scores) == 4
