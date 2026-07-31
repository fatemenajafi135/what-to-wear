"""Verifiable outfit-property checks (pure functions).

These are the crisp, machine-checkable half of the eval. The fuzzy half
(coherence, occasion nuance) is scored by the LLM judge in the isolated
`backend/evals/` project. Expected values are PROPERTIES, not fixed
outfits.

Moved here from `eval/properties.py` (specs/007-ai-port/research.md §2):
`pipeline/graph.py` and `scoring/weather_fitness.py` both need
`weather_appropriate` for production hard-constraint pruning and scoring,
and production code importing the `eval` package has the dependency
backwards (constitution Principle V — scorers are eval metrics, not the
reverse). `eval/properties.py` now re-exports from here, so nothing that
imports `eval.properties` needs to change. No logic changes from the
legacy version.
"""

from __future__ import annotations

from ..categories import group_of, is_core
from ..colors import nearest_names
from ..schema import FORMALITY_ORDER, WardrobeItem


def _core_items(items: list[str], wardrobe: dict[str, WardrobeItem]) -> list[WardrobeItem]:
    return [wardrobe[i] for i in items if i in wardrobe and is_core(wardrobe[i].category)]


def owned_only(items: list[str], wardrobe: dict[str, WardrobeItem]) -> bool:
    return all(i in wardrobe for i in items)


def weather_appropriate(items: list[str], wardrobe: dict[str, WardrobeItem], expected: dict) -> bool:
    core = _core_items(items, wardrobe)
    if not core:
        return False
    if expected.get("requires_outer"):
        # group-based, not a literal "outerwear" string match — a "coat" or
        # "jacket" category (grouped as outerwear in categories.py) must count
        # too, not just items literally named "outerwear".
        has_warm = any(group_of(it.category) == "outerwear" or it.warmth >= 3 for it in _resolved(items, wardrobe))
        if not has_warm:
            return False
    if "max_warmth" in expected and any(it.warmth > expected["max_warmth"] for it in core):
        return False
    return True


def occasion_fit(items: list[str], wardrobe: dict[str, WardrobeItem], expected: dict) -> bool:
    """No core item more than one formality notch below the required floor."""
    required = FORMALITY_ORDER[expected["min_formality"]]
    core = _core_items(items, wardrobe)
    if not core:
        return False
    return min(FORMALITY_ORDER[it.formality] for it in core) >= required - 1


def respects_exclusions(items: list[str], wardrobe: dict[str, WardrobeItem], expected: dict) -> bool:
    resolved = _resolved(items, wardrobe)
    forbid_cats = set(expected.get("forbid_categories", []))
    forbid_cols = {c.lower() for c in expected.get("forbid_colors", [])}
    for it in resolved:
        if it.category in forbid_cats:
            return False
        # wardrobe colors are hex (source of truth); forbid_colors is expressed
        # in names, so match on the DERIVED name, never the hex value itself
        # (same fix as hybrid.py::retrieve_l1 and generator.py::_format_items).
        if any(name.lower() in forbid_cols for name in nearest_names(it.colors)):
            return False
    return True


def _resolved(items: list[str], wardrobe: dict[str, WardrobeItem]) -> list[WardrobeItem]:
    return [wardrobe[i] for i in items if i in wardrobe]


def check_outfit(items: list[str], wardrobe: dict[str, WardrobeItem], expected: dict) -> dict:
    """Run all property checks for one outfit; return a bool per check."""
    return {
        "owned_only": owned_only(items, wardrobe),
        "weather_appropriate": weather_appropriate(items, wardrobe, expected),
        "occasion_fit": occasion_fit(items, wardrobe, expected),
        "respects_exclusions": respects_exclusions(items, wardrobe, expected),
    }
