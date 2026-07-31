"""eval/properties.py is a thin re-export of scoring/properties.py
(specs/007-ai-port/research.md §2) — verifies the re-export is real and
the two modules never drift into two implementations."""

from __future__ import annotations

from whattowear.eval import properties as eval_properties
from whattowear.scoring import properties as scoring_properties


def test_reexported_functions_are_the_same_objects() -> None:
    assert eval_properties.owned_only is scoring_properties.owned_only
    assert eval_properties.weather_appropriate is scoring_properties.weather_appropriate
    assert eval_properties.occasion_fit is scoring_properties.occasion_fit
    assert eval_properties.respects_exclusions is scoring_properties.respects_exclusions
    assert eval_properties.check_outfit is scoring_properties.check_outfit


def test_all_matches_the_reexported_names() -> None:
    assert set(eval_properties.__all__) == {
        "owned_only",
        "weather_appropriate",
        "occasion_fit",
        "respects_exclusions",
        "check_outfit",
    }
