"""Unit tests for eval/vision_harness.py — never had one before this port.

`_check`/`run` need real image bytes and a live VLM call, so they're not
exercised here; this covers case loading and the pure per-field
comparison logic instead. Note (specs/007-ai-port §10): the
`vision_cases` sample images referenced by golden_set.yaml
(`fixtures/vision_samples/*.png`) were never actually present even in the
legacy checkout — this golden-case check has never been runnable, in
either codebase. Porting the (sound) logic and fixing its path
resolution is this feature's job; sourcing real sample photos is not.

Feature 006 closes that gap: two synthetic (solid-color, not real garment
photo — specs/006-photo-upload-vision/research.md §9) fixture images now
exist at the paths below, AND a real path-doubling bug in golden_set.yaml
is fixed alongside them (its `image:` values duplicated the `fixtures/`
segment `VISION_FIXTURES_DIR` already supplies — never caught before
because the files never existed to trigger it). What's still not
exercised here, deliberately: the live VLM call itself (constitution
Quality Bar — CI must not make live LLM calls).
"""

from __future__ import annotations

from whattowear.eval.vision_harness import VISION_FIXTURES_DIR, load_vision_cases


def test_loads_vision_cases_from_the_golden_set() -> None:
    cases = load_vision_cases()
    assert len(cases) > 0
    assert all(c.image for c in cases)


def test_fixtures_dir_resolves_under_the_tracked_evals_directory() -> None:
    assert VISION_FIXTURES_DIR.parent.name == "evals"
    assert VISION_FIXTURES_DIR.name == "fixtures"


def test_every_golden_case_image_file_actually_exists() -> None:
    """Regression guard for the exact gap this feature closes — fails
    loudly if a fixture image is ever removed or a path regresses, instead
    of silently staying unrunnable the way it did before feature 006."""
    cases = load_vision_cases()
    for case in cases:
        image_path = VISION_FIXTURES_DIR / case.image
        assert image_path.is_file(), f"{case.id}: {image_path} does not exist"


# Feature 018 (photo-to-items): vision_cases can now describe a multi-
# garment photo (`expected_count` + a list-shaped `expected`), not only the
# single-garment shape every pre-018 case uses. These stay fixture-shape
# assertions only — no live call, matching this file's own existing scope.


def test_case_ids_are_unique() -> None:
    cases = load_vision_cases()
    ids = [c.id for c in cases]
    assert len(ids) == len(set(ids)), f"duplicate vision_cases id(s): {[i for i in ids if ids.count(i) > 1]}"


def test_multi_garment_cases_declare_expected_count_and_a_list_of_sub_expectations() -> None:
    """A case describing several garments must say how many (so the
    detection-count check in eval/vision_harness.py::_check has something
    to check) and must shape `expected` as a list, one entry per garment —
    the legacy single-dict shape doesn't have anywhere to name a second
    garment's expectations."""
    cases = load_vision_cases()
    for case in cases:
        if case.expected_count is not None and case.expected_count > 1:
            assert isinstance(
                case.expected, list
            ), f"{case.id}: expected_count={case.expected_count} but `expected` is not a list"
            assert len(case.expected) > 0, f"{case.id}: expected_count > 1 but `expected` is empty"
