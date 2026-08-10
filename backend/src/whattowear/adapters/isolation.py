"""Isolation strategy selection — feature 018 (photo-to-items).

`get_isolation_client()` chooses which `ports.IsolationClient` adapter to
use, mirroring `kb.py`'s `wtw_kb_mode` selection pattern applied to a
different Protocol (ports.py's own docstring makes this parallel
explicit).
"""

from __future__ import annotations

from ..core.config import get_settings
from ..ports import IsolationClient
from .isolation_generative import GenerativeIsolationClient
from .isolation_hybrid import HybridIsolationClient
from .isolation_segmentation import SegmentationIsolationClient

_STRATEGIES: dict[str, type[IsolationClient]] = {
    "segmentation": SegmentationIsolationClient,
    "generative": GenerativeIsolationClient,
    "hybrid": HybridIsolationClient,
}


def get_isolation_client(strategy: str | None = None) -> IsolationClient:
    """Returns the configured `IsolationClient`. `strategy` overrides
    `wtw_isolation_strategy` when given — used by `eval/vision_harness.py`
    `isolation_report()` (research.md §9) to run all three strategies
    against the same corpus in one pass; the extract route itself never
    passes an override, always reading the configured default."""
    resolved = strategy or get_settings().wtw_isolation_strategy
    try:
        adapter_cls = _STRATEGIES[resolved]
    except KeyError:
        raise ValueError(f"Unknown wtw_isolation_strategy {resolved!r}; must be one of {sorted(_STRATEGIES)}") from None
    return adapter_cls()
