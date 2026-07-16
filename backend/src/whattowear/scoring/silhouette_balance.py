"""Silhouette-balance dimension scorer.

General proportion principles only — a fitted piece paired with a looser
piece (or vice versa) reads as a deliberately balanced silhouette; two loose
pieces together tend to read as shapeless. Deliberately NOT personalized to
any body shape (spec Future Work) — reasons purely from each item's own
`fit` text, never a user attribute.
"""

from __future__ import annotations

from typing import Literal, Optional

from ..categories import group_of
from ..schema import Context, DimensionScore, WardrobeItem

FitBucket = Literal["loose", "fitted", "regular"]

_LOOSE_KEYWORDS = ("loose", "oversized", "relaxed", "wide", "baggy")
_FITTED_KEYWORDS = ("fitted", "slim", "tailored", "skinny", "tight", "bodycon")


def _bucket(fit: Optional[str]) -> Optional[FitBucket]:
    if not fit:
        return None
    text = fit.lower()
    if any(k in text for k in _LOOSE_KEYWORDS):
        return "loose"
    if any(k in text for k in _FITTED_KEYWORDS):
        return "fitted"
    return "regular"


def score(items: list[WardrobeItem], ctx: Context) -> DimensionScore:
    top = next((it for it in items if group_of(it.category) == "top"), None)
    bottom = next((it for it in items if group_of(it.category) == "bottom"), None)

    if top is None or bottom is None:
        return DimensionScore(
            dimension="silhouette_balance",
            value=0.5,
            reason="no separate top+bottom pairing to evaluate proportion on — neutral score",
        )

    top_bucket, bottom_bucket = _bucket(top.fit), _bucket(bottom.fit)
    if top_bucket is None or bottom_bucket is None:
        return DimensionScore(
            dimension="silhouette_balance",
            value=0.5,
            reason="fit not recorded for one or both pieces — neutral score",
        )

    if {top_bucket, bottom_bucket} == {"loose", "fitted"}:
        value, reason = 1.0, "contrasting fit (loose + fitted) balances the silhouette"
    elif top_bucket == bottom_bucket == "loose":
        value, reason = 0.3, "both pieces are loose/oversized — may read as shapeless"
    elif top_bucket == bottom_bucket == "fitted":
        value, reason = 0.7, "both pieces are fitted — streamlined but low proportion contrast"
    else:
        value, reason = 0.6, "regular-fit pairing — balanced by default, no strong contrast"

    return DimensionScore(dimension="silhouette_balance", value=value, reason=reason)
