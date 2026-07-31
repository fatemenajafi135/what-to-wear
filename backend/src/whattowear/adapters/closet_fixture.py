"""Fixture-backed `ClosetRepository` — the eval/test binding.

specs/007-ai-port/research.md §5: `eval/harness.py::run_case` invokes the
compiled graph without a `wardrobe` override, so `context_assembler.
load_wardrobe` and `graph.verify_grounding` both need a real closet/catalog
read on every case. Legacy `crud.seed_catalog`/`crud.seed_eval_baseline_user`
seeded both from the identical 40-item fixture
(`data/fixtures/wardrobe.json`); this reproduces that behaviour without a
database, because this rebuild's schema has no wardrobe/catalog tables yet —
that lands with whichever feature owns closet persistence, not this one.

Loads the fixture once (module-level, but only read at first construction —
no I/O at import time) and serves it for any `user_id`, matching how the
legacy eval baseline user's wardrobe and the shared catalog were the exact
same seeded data.
"""

from __future__ import annotations

import json
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

from ..schema import WardrobeItem

if TYPE_CHECKING:
    # Type-checking only — see ports.py's identical note. Lets this module
    # (and its test) land right after schema.py (Phase 2), not blocked on
    # memory/preferences.py (Phase 5), since FeedbackRecord only ever
    # appears in a return-type annotation here.
    from ..memory.preferences import FeedbackRecord

_FIXTURE_PATH = Path(__file__).parent.parent.parent.parent / "evals" / "fixtures" / "wardrobe.json"


@lru_cache
def _load_fixture_items(path: Path = _FIXTURE_PATH) -> tuple[WardrobeItem, ...]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return tuple(WardrobeItem(**item) for item in raw)


class FixtureClosetRepository:
    """Satisfies `ports.ClosetRepository`. `get_derivation_inputs` always
    returns `([], {})` — the legacy eval baseline user is seeded with closet
    items only, never feedback, so `memory.store.get_profile()` stays `None`
    exactly as it does against the real seeded baseline (matches
    `crud.seed_eval_baseline_user`'s documented guarantee)."""

    def __init__(self, fixture_path: Path = _FIXTURE_PATH) -> None:
        self._fixture_path = fixture_path

    def list_wardrobe_items(self, user_id: str) -> list[WardrobeItem]:
        return list(_load_fixture_items(self._fixture_path))

    def list_catalog_items(self) -> list[WardrobeItem]:
        return list(_load_fixture_items(self._fixture_path))

    def get_derivation_inputs(self, user_id: str) -> tuple[list[FeedbackRecord], dict[str, datetime]]:
        return [], {}
