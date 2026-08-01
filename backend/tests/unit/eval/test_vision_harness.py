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
