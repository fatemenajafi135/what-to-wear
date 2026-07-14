"""Stage 1: context assembler.

Gather structured inputs, call the weather API, and normalize everything into one
`Context`. Degrades gracefully: if weather lookup fails (no network / bad
location), fall back to a caller-supplied `temp_c`, else leave weather unset.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from langsmith import traceable

from ..external.weather import month_to_season, temp_to_band
from ..ingest.loaders import REPO_ROOT
from ..schema import Context, Formality, WardrobeItem

WARDROBE_FIXTURE = REPO_ROOT / "data" / "fixtures" / "wardrobe.json"

# Fallback occasion -> default formality (mirrors the L4 occ entries). Used only
# when the caller doesn't state a formality.
OCCASION_FORMALITY: dict[str, Formality] = {
    "office": "business_casual",
    "job_interview": "business_casual",
    "wedding": "formal",
    "date": "smart_casual",
    "brunch": "smart_casual",
    "funeral": "formal",
    "beach": "casual",
    "gala": "black_tie",
    "party": "semi_formal",
}


def load_wardrobe(path: Path = WARDROBE_FIXTURE) -> list[WardrobeItem]:
    with open(path, encoding="utf-8") as fh:
        return [WardrobeItem(**{k: v for k, v in it.items() if k in WardrobeItem.model_fields})
                for it in json.load(fh)]


@traceable(name="stage.context_assembler", run_type="chain")
def assemble_context(
    occasion: str,
    *,
    mood: Optional[str] = None,
    formality: Optional[Formality] = None,
    location: Optional[str] = None,
    temp_c: Optional[float] = None,
    wardrobe: Optional[list[WardrobeItem]] = None,
    user_id: Optional[str] = None,
) -> Context:
    formality = formality or OCCASION_FORMALITY.get(occasion, "smart_casual")
    wardrobe = wardrobe if wardrobe is not None else load_wardrobe()

    condition = None
    temp_band = None
    season = None

    if location:
        try:
            from ..external.weather import get_weather

            wx = get_weather(location)
            temp_c = wx["temp_c"]
            condition = wx["condition"]
            temp_band = wx["temp_band"]
            season = wx["season"]
        except Exception as exc:  # noqa: BLE001 - offline / bad location: fall back
            print(f"[warn] weather lookup failed ({exc}); using provided temp_c if any.")

    if temp_band is None and temp_c is not None:
        temp_band = temp_to_band(temp_c)
    if season is None and temp_c is not None:
        from datetime import datetime, timezone

        season = month_to_season(datetime.now(timezone.utc).month)

    return Context(
        occasion=occasion,
        formality=formality,
        mood=mood,
        temp_c=temp_c,
        condition=condition,
        temp_band=temp_band,
        season=season,
        wardrobe=wardrobe,
        user_id=user_id,
    )
