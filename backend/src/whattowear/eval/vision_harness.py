"""Lightweight golden-case check for photo -> attribute extraction.
Satisfies the constitution's Quality Bar ("LLM-dependent paths require an
entry in the golden set") for vision's one LLM-dependent path, WITHOUT
touching or plugging into the existing `eval/harness.py` no-regression
gate (Principle I) — `vision_cases:` is a structurally separate section
that `harness.py` never loads.

LOOSE checks only (category match, formality-in-set, warmth-in-range) —
extraction is inherently less exact than harness.py's hard outfit-property
constraints. Run: `uv run python -m whattowear.eval.vision_harness`
"""

from __future__ import annotations

import mimetypes
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from ..categories import group_of
from ..vision import extract_attributes_from_image
from .golden_set import GOLDEN_PATH

# Images referenced by golden_set.yaml's `image:` field resolve relative
# to this — the tracked evals/fixtures/ directory (constitution Principle
# X's carve-out), not a REPO_ROOT/data/ path inside the repo the way the
# legacy version had it.
VISION_FIXTURES_DIR = GOLDEN_PATH.parent / "fixtures"


@dataclass
class VisionCase:
    id: str
    image: str
    expected: dict = field(default_factory=dict)


def load_vision_cases(path: Path = GOLDEN_PATH) -> list[VisionCase]:
    with open(path, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh).get("vision_cases", [])
    return [VisionCase(**c) for c in raw]


def _check(case: VisionCase) -> tuple[bool, list[str]]:
    image_path = VISION_FIXTURES_DIR / case.image
    mime_type = mimetypes.guess_type(image_path.name)[0] or "image/png"
    extracted = extract_attributes_from_image(image_path.read_bytes(), mime_type)

    failures: list[str] = []
    expected = case.expected

    if "category" in expected:
        # Compared at GROUP level, not as an exact string. The golden set
        # names a group ("top"); the prompt asks the model for a SPECIFIC
        # type ("t-shirt", "blouse") since feature 006 needs one, so exact
        # equality would fail every correct answer. `group_of` is the same
        # mapping the app itself uses to slot an item, which is what this
        # case is really asserting — did it identify the right kind of
        # garment. Consistent with this module's "LOOSE checks only".
        expected_group = group_of(str(expected["category"]))
        actual_group = group_of(extracted.category) if extracted.category else None
        if actual_group != expected_group:
            failures.append(
                f"category group: expected {expected_group!r} "
                f"(from {expected['category']!r}), got {actual_group!r} (from {extracted.category!r})"
            )

    if "formality_in" in expected and extracted.formality not in expected["formality_in"]:
        failures.append(f"formality: expected one of {expected['formality_in']}, got {extracted.formality!r}")

    if "warmth_range" in expected:
        lo, hi = expected["warmth_range"]
        if extracted.warmth is None or not (lo <= extracted.warmth <= hi):
            failures.append(f"warmth: expected in [{lo}, {hi}], got {extracted.warmth!r}")

    return not failures, failures


def run() -> int:
    cases = load_vision_cases()
    passed = 0
    for case in cases:
        ok, failures = _check(case)
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {case.id} ({case.image})")
        for f in failures:
            print(f"    - {f}")
        passed += ok
    print(f"\n{passed}/{len(cases)} vision golden cases passed")
    return 0 if passed == len(cases) else 1


if __name__ == "__main__":
    raise SystemExit(run())
