"""Re-exports the verifiable outfit-property checks from `scoring.properties`.

specs/007-ai-port/research.md §2: these predicates moved to
`scoring/properties.py` because production code (`pipeline/graph.py`,
`scoring/weather_fitness.py`) needs `weather_appropriate`, and importing it
from `eval` had the dependency backwards (constitution Principle V —
scorers are eval metrics, not the reverse). This module exists only so
`eval.harness` and any other eval-side caller keep importing from `eval`,
where they conceptually belong for reporting purposes — the implementation
itself lives in the domain package now.
"""

from __future__ import annotations

from ..scoring.properties import (
    check_outfit,
    occasion_fit,
    owned_only,
    respects_exclusions,
    weather_appropriate,
)

__all__ = [
    "check_outfit",
    "occasion_fit",
    "owned_only",
    "respects_exclusions",
    "weather_appropriate",
]
