"""Load the hand-assembled golden test set.

`GOLDEN_PATH` resolves to `backend/evals/golden_set.yaml` — a tracked file
(constitution Principle X carve-out: eval datasets are a deliberate
exception), not a path under `ingest.loaders.REPO_ROOT/data/` the way the
legacy version had it. That also means this module has no dependency on
`ingest/` (which doesn't land until specs/007-ai-port Phase 11) — a leaf
in this feature's own port order, same as it always should have been.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

GOLDEN_PATH = Path(__file__).parent.parent.parent.parent / "evals" / "golden_set.yaml"


@dataclass
class GoldenCase:
    id: str
    occasion: str
    mood: str | None = None
    formality: str | None = None
    temp_c: float | None = None
    expected: dict = field(default_factory=dict)
    relevant_rule_ids: list[str] = field(default_factory=list)
    reference: str = ""


def load_cases(path: Path = GOLDEN_PATH) -> list[GoldenCase]:
    with open(path, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)["cases"]
    return [GoldenCase(**c) for c in raw]
