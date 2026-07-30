"""Output grounding guardrail.

A safety net on top of, not a replacement for, the existing deterministic
selection guarantee (constitution Principle IV): every item in a
suggested outfit already only ever comes from the requester's own
wardrobe (`generate_outfits`/`is_slot_complete` in `pipeline/graph.py`).
This module is the explicit, automatic check that catches it if that
guarantee is ever violated by a bug.

`filter_ungrounded_cites` is the citation-side counterpart — Principle IV's
second clause ("every rationale cites retrieved style principles"), enforced
the same way: a guard the pipeline calls, not just an eval-time metric
(`pipeline/cite.py::all_cites_grounded`, which stays a read-only check).
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from ..schema import WardrobeItem
from .generator import GenRationale

log = logging.getLogger(__name__)


def verify_outfit_grounding(
    item_ids: list[str],
    wardrobe_by_id: dict[str, WardrobeItem],
    catalog_ids: set[str],
) -> bool:
    """True iff every item id genuinely exists in the requester's own
    wardrobe or the shared catalog (constitution Principle IV, checked
    literally). No outfit can contain a catalog-only item today (catalog
    substitution is deferred) — checking it anyway costs one cheap
    membership test, not a redesign."""
    return all(item_id in wardrobe_by_id or item_id in catalog_ids for item_id in item_ids)


def filter_ungrounded_cites(rationale: Sequence[GenRationale], retrieved_rule_ids: set[str]) -> list[GenRationale]:
    """Drop any cited rule_id that was never actually retrieved from each
    rationale line — an LLM citation typo or hallucination should not ship
    as a dangling badge with no resolvable source. Drops only the offending
    id(s), never the whole rationale line or outfit: a single bad citation
    doesn't cost a valid outfit, and a line left with no cites at all is the
    same honestly-empty convention the deterministic fallback already uses
    (constitution Principle IV). Logged as a warning so a hallucinated
    citation is observable rather than silently vanishing — the gap that let
    this go unnoticed through the eval-baseline history this guard responds
    to."""
    result: list[GenRationale] = []
    for r in rationale:
        grounded = [c for c in r.cites if c in retrieved_rule_ids]
        dropped = [c for c in r.cites if c not in retrieved_rule_ids]
        if not dropped:
            result.append(r)
            continue
        log.warning("Dropping ungrounded citation(s) %s from rationale %r", dropped, r.text)
        result.append(GenRationale(text=r.text, cites=grounded))
    return result
