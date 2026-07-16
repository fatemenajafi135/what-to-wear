"""Preference derivation — pure functions, no DB access (Feature 004:
preference-memory). Kept separate from memory/store.py's storage-access
role so this module is independently unit-testable with plain data,
matching how colors.py/categories.py are separated from the storage/API
layers today. This is the single source of truth for what counts as a
"learned preference" — memory.store.get_profile() (feeds profile_note(),
which softly shapes generation) and the /preferences endpoints (view/
clear/remove) both call derive_signals(), so every surface always agrees.

See specs/004-preference-memory/research.md #2 for the algorithm and
threshold rationale, and #3 for the dismissal mechanism.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Optional

from ..schema import FORMALITY_ORDER

# How many net repeated signals before a preference counts as "learned" —
# a tunable threshold, deliberately left to implementation by spec.md's
# Assumptions. See research.md #2.
MIN_SIGNAL_COUNT = 3


@dataclass
class ItemSnapshot:
    item_id: str
    category: str
    colors: list[str]
    formality: str


@dataclass
class FeedbackRecord:
    """Plain mirror of a SuggestionFeedbackRow — no ORM/session dependency,
    so this module never touches the DB."""

    verdict: Literal["liked", "rejected"]
    item_snapshot: list[ItemSnapshot]
    created_at: datetime


@dataclass
class DerivedSignal:
    key: str  # "color:{hex}" / "category:{value}" / "formality_drift"
    kind: Literal["color", "category", "formality_drift"]
    detail: str  # hex / category value / "less_formal" | "more_formal"
    supporting_count: int


def derive_signals(feedback: list[FeedbackRecord], dismissals: dict[str, datetime]) -> list[DerivedSignal]:
    """`dismissals` maps signal_key -> dismissed_at; a feedback record is
    excluded from a given signal's derivation once dismissed, until a
    record created after that cutoff re-establishes the pattern (research.md
    #3)."""
    signals: list[DerivedSignal] = []
    signals.extend(_derive_net_count_signals(feedback, dismissals, kind="color", key_of=_color_keys_of))
    signals.extend(_derive_net_count_signals(feedback, dismissals, kind="category", key_of=_category_keys_of))
    formality_signal = _derive_formality_drift(feedback, dismissals)
    if formality_signal is not None:
        signals.append(formality_signal)
    return signals


def _visible(record: FeedbackRecord, signal_key: str, dismissals: dict[str, datetime]) -> bool:
    dismissed_at = dismissals.get(signal_key)
    return dismissed_at is None or record.created_at > dismissed_at


def _color_keys_of(item: ItemSnapshot) -> list[str]:
    return [hex_color for hex_color in item.colors]


def _category_keys_of(item: ItemSnapshot) -> list[str]:
    return [item.category]


def _derive_net_count_signals(
    feedback: list[FeedbackRecord],
    dismissals: dict[str, datetime],
    *,
    kind: Literal["color", "category"],
    key_of,
) -> list[DerivedSignal]:
    """Net-count threshold: rejections of a value minus likes of that same
    value. Included once `net >= MIN_SIGNAL_COUNT`. The subtraction is what
    lets a genuine, consistent pattern survive an isolated contradiction
    (spec.md Edge Cases) without being erased by one counterexample."""
    net: dict[str, int] = {}
    for record in feedback:
        delta = 1 if record.verdict == "rejected" else -1
        for item in record.item_snapshot:
            for value in key_of(item):
                signal_key = f"{kind}:{value}"
                if not _visible(record, signal_key, dismissals):
                    continue
                net[value] = net.get(value, 0) + delta
    return [
        DerivedSignal(key=f"{kind}:{value}", kind=kind, detail=value, supporting_count=score)
        for value, score in net.items()
        if score >= MIN_SIGNAL_COUNT
    ]


def _outfit_avg_formality(record: FeedbackRecord) -> Optional[float]:
    if not record.item_snapshot:
        return None
    return sum(FORMALITY_ORDER[item.formality] for item in record.item_snapshot) / len(record.item_snapshot)


def _derive_formality_drift(feedback: list[FeedbackRecord], dismissals: dict[str, datetime]) -> Optional[DerivedSignal]:
    """Only computed once at least MIN_SIGNAL_COUNT liked *and*
    MIN_SIGNAL_COUNT rejected outfits with formality data exist — both
    sides are needed for "drift" to mean anything; a one-sided sample can't
    establish a direction (research.md #2)."""
    signal_key = "formality_drift"
    visible = [r for r in feedback if _visible(r, signal_key, dismissals)]
    rejected_avgs = [a for r in visible if r.verdict == "rejected" and (a := _outfit_avg_formality(r)) is not None]
    liked_avgs = [a for r in visible if r.verdict == "liked" and (a := _outfit_avg_formality(r)) is not None]
    if len(rejected_avgs) < MIN_SIGNAL_COUNT or len(liked_avgs) < MIN_SIGNAL_COUNT:
        return None
    delta = (sum(rejected_avgs) / len(rejected_avgs)) - (sum(liked_avgs) / len(liked_avgs))
    if delta >= 1:
        return DerivedSignal(
            key=signal_key, kind="formality_drift", detail="less_formal", supporting_count=len(rejected_avgs)
        )
    if delta <= -1:
        return DerivedSignal(
            key=signal_key, kind="formality_drift", detail="more_formal", supporting_count=len(rejected_avgs)
        )
    return None
