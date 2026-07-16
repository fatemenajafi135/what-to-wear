"""Lightweight golden-case check for photo -> attribute extraction (Feature
003: mvp-app, US2). Satisfies the constitution's Quality Bar ("LLM-dependent
paths require an entry in data/golden_set.yaml") for this feature's one new
LLM-dependent path, WITHOUT touching or plugging into the existing
`eval/harness.py` no-regression gate (Principle I) -- vision_cases: is a
structurally separate section that harness.py never loads.

LOOSE checks only (category match, formality-in-set, warmth-in-range) --
extraction is inherently less exact than harness.py's hard outfit-property
constraints. Run: `uv run python -m whattowear.eval.vision_harness`
"""

from __future__ import annotations

import mimetypes
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from ..ingest.loaders import REPO_ROOT
from ..vision import extract_attributes_from_image
from .golden_set import GOLDEN_PATH


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
    image_path = REPO_ROOT / "data" / case.image
    mime_type = mimetypes.guess_type(image_path.name)[0] or "image/png"
    extracted = extract_attributes_from_image(image_path.read_bytes(), mime_type)

    failures: list[str] = []
    expected = case.expected

    if "category" in expected and extracted.category != expected["category"]:
        failures.append(f"category: expected {expected['category']!r}, got {extracted.category!r}")

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
