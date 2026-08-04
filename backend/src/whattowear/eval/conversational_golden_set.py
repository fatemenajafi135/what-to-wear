"""Load the hand-assembled conversational-turns golden set (feature 016).

Mirrors `eval/golden_set.py` exactly: `GOLDEN_PATH` resolves to a tracked file under
`backend/evals/` (constitution Principle X's eval-dataset carve-out), a plain dataclass, a
`load_cases()` loader. Kept as a separate file/dataclass from `golden_set.py` rather than folded
into it — that file's `GoldenCase` shape (occasion/mood/formality/temp_c/expected outfit
properties) answers a different question (does the *pipeline* produce a good outfit) than this
one does (did the *conversational turn* extract the right slots and hold the right voice); a
shared dataclass would need optional fields for concepts the other case type doesn't have.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

GOLDEN_PATH = Path(__file__).parent.parent.parent.parent / "evals" / "conversational_golden_set.yaml"


@dataclass
class ConversationalGoldenCase:
    id: str
    utterance: str
    prior_slots: dict = field(default_factory=dict)
    expected_slots: dict = field(default_factory=dict)
    voice_check: str = ""


def load_cases(path: Path = GOLDEN_PATH) -> list[ConversationalGoldenCase]:
    with open(path, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)["cases"]
    return [ConversationalGoldenCase(**c) for c in raw]
