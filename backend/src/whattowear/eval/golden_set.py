"""Load the hand-assembled golden test set."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from ..ingest.loaders import REPO_ROOT

GOLDEN_PATH = REPO_ROOT / "data" / "golden_set.yaml"


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
