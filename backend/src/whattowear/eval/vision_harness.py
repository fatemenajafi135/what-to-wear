"""Lightweight golden-case check for photo -> garment detection and
attribute extraction. Satisfies the constitution's Quality Bar
("LLM-dependent paths require an entry in the golden set") for vision's
LLM-dependent path, WITHOUT touching or plugging into the existing
`eval/harness.py` no-regression gate (Principle I) — `vision_cases:` is a
structurally separate section that `harness.py` never loads.

LOOSE checks only (category match, formality-in-set, warmth-in-range) —
extraction is inherently less exact than harness.py's hard outfit-property
constraints. Run: `uv run python -m whattowear.eval.vision_harness`

Feature 018 (photo-to-items) extended this in two ways, both live-gateway
only and excluded from CI (Quality Bar — CI must not make live LLM calls):
- `_check` now calls `detect_garments_from_image` (one photo -> N
  detections) instead of the retired single-item `extract_attributes_
  from_image`. A case's `expected_count`, when set, checks the detection
  count; `expected` may be either the legacy single dict (checked against
  the first/only detection — the exact shape every pre-018 case already
  used) or a list of per-garment expected dicts for a multi-garment photo,
  matched to each detection by closest category group.
- `isolation_report()` (--isolation-report) runs every fixture through
  each configured isolation strategy and prints per-strategy cost/latency/
  success, feeding the FR-016/SC-008 default-strategy decision
  (specs/018-photo-to-items/research.md §9).
"""

from __future__ import annotations

import argparse
import mimetypes
import time
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from ..categories import group_of
from ..schema import DetectedGarment, ExtractedAttributes
from ..vision import detect_garments_from_image
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
    # Either the legacy single-garment shape (a flat dict, checked against
    # the photo's first/only detection — every case before feature 018 uses
    # this) or a list of per-garment expected dicts for a multi-garment
    # photo, one entry per garment the fixture is known to contain.
    expected: dict | list[dict] = field(default_factory=dict)
    # Feature 018: set only on multi-garment fixtures. None means "don't
    # check the count" (every pre-018 case).
    expected_count: int | None = None


def load_vision_cases(path: Path = GOLDEN_PATH) -> list[VisionCase]:
    with open(path, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh).get("vision_cases", [])
    return [VisionCase(**c) for c in raw]


def _check_attributes(attrs: ExtractedAttributes, expected: dict) -> list[str]:
    failures: list[str] = []

    if "category" in expected:
        # Compared at GROUP level, not as an exact string. The golden set
        # names a group ("top"); the prompt asks the model for a SPECIFIC
        # type ("t-shirt", "blouse") since feature 006 needs one, so exact
        # equality would fail every correct answer. `group_of` is the same
        # mapping the app itself uses to slot an item, which is what this
        # case is really asserting — did it identify the right kind of
        # garment. Consistent with this module's "LOOSE checks only".
        expected_group = group_of(str(expected["category"]))
        actual_group = group_of(attrs.category) if attrs.category else None
        if actual_group != expected_group:
            failures.append(
                f"category group: expected {expected_group!r} "
                f"(from {expected['category']!r}), got {actual_group!r} (from {attrs.category!r})"
            )

    if "formality_in" in expected and attrs.formality not in expected["formality_in"]:
        failures.append(f"formality: expected one of {expected['formality_in']}, got {attrs.formality!r}")

    if "warmth_range" in expected:
        lo, hi = expected["warmth_range"]
        if attrs.warmth is None or not (lo <= attrs.warmth <= hi):
            failures.append(f"warmth: expected in [{lo}, {hi}], got {attrs.warmth!r}")

    return failures


def _closest_expected(detection: DetectedGarment, expected_list: list[dict]) -> dict:
    """Picks the expected sub-case whose category group most closely
    matches this detection's own category group — "matched to the closest
    expected sub-case by category group" (specs/018-photo-to-items/
    tasks.md T029). Falls back to the first entry when nothing in the
    photo's own extraction resolved a category, or none matches, so a
    genuinely wrong detection still gets checked against *something*
    rather than silently skipped."""
    if not expected_list:
        return {}
    detected_group = group_of(detection.attributes.category) if detection.attributes.category else None
    for exp in expected_list:
        if "category" in exp and group_of(str(exp["category"])) == detected_group:
            return exp
    return expected_list[0]


def _check(case: VisionCase) -> tuple[bool, list[str]]:
    image_path = VISION_FIXTURES_DIR / case.image
    mime_type = mimetypes.guess_type(image_path.name)[0] or "image/png"
    detections, _truncated = detect_garments_from_image(image_path.read_bytes(), mime_type)

    failures: list[str] = []

    if case.expected_count is not None and len(detections) != case.expected_count:
        failures.append(f"detection count: expected {case.expected_count}, got {len(detections)}")

    if isinstance(case.expected, list):
        for detection in detections:
            sub_expected = _closest_expected(detection, case.expected)
            failures.extend(
                f"[{detection.attributes.category or '?'}] {f}"
                for f in _check_attributes(detection.attributes, sub_expected)
            )
    elif case.expected:
        # Legacy single-garment shape — checked against the first/only
        # detection, identical to every case's behavior before feature 018.
        target = detections[0].attributes if detections else ExtractedAttributes()
        failures.extend(_check_attributes(target, case.expected))

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


def isolation_report() -> int:
    """Runs every fixture-corpus image through each configured isolation
    strategy and prints a per-strategy cost/latency/success summary — the
    real numbers specs/018-photo-to-items/research.md §6 and §9 need before
    the hybrid thresholds and the default strategy (FR-016) can be anything
    but placeholders. Imports `adapters.isolation` lazily (not at module
    level) so this file stays importable — and the rest of this harness
    runnable — before Phase 6 lands the isolation adapters themselves."""
    from ..adapters.isolation import get_isolation_client  # type: ignore[import-untyped]  # Phase 6, not yet landed

    cases = load_vision_cases()
    strategies = ["segmentation", "generative", "hybrid"]
    print(f"Isolation report over {len(cases)} fixture(s), {len(strategies)} strategy(ies)\n")

    for strategy in strategies:
        client = get_isolation_client(strategy)
        successes = 0
        total_cost = 0.0
        latencies: list[float] = []
        for case in cases:
            image_path = VISION_FIXTURES_DIR / case.image
            mime_type = mimetypes.guess_type(image_path.name)[0] or "image/png"
            image_bytes = image_path.read_bytes()
            start = time.monotonic()
            # A whole-frame region is a reasonable stand-in here — this
            # report measures the isolation call itself, not detection;
            # a real per-detection region only exists once T041 wires this
            # into the live extract route.
            from ..schema import BoundingBox

            outcome = client.isolate(image_bytes, mime_type, BoundingBox(x=0, y=0, width=1, height=1))
            elapsed = time.monotonic() - start
            latencies.append(outcome.latency_seconds if outcome.latency_seconds else elapsed)
            if outcome.image_bytes is not None:
                successes += 1
            total_cost += outcome.cost_usd or 0.0

        latencies.sort()
        p50 = latencies[len(latencies) // 2] if latencies else 0.0
        success_rate = successes / len(cases) if cases else 0.0
        print(
            f"[{strategy:>12}] success={success_rate:.0%} ({successes}/{len(cases)})  "
            f"p50={p50:.2f}s  total_cost=${total_cost:.4f}  avg_cost=${(total_cost / len(cases)) if cases else 0:.4f}"
        )

    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--isolation-report", action="store_true", help="Run the per-strategy isolation report instead")
    args = parser.parse_args()
    raise SystemExit(isolation_report() if args.isolation_report else run())
