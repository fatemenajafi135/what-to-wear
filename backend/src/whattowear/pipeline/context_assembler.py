"""Stage 1: context assembler.

Gather structured inputs, call the weather API, and normalize everything into one
`Context`. Degrades gracefully: if weather lookup fails (no network / bad
location), fall back to a caller-supplied `temp_c`, else leave weather unset.
"""

from __future__ import annotations

import re
from typing import Optional

from langsmith import traceable

from ..external.weather import month_to_season, temp_to_band
from ..schema import FORMALITY_ORDER, Context, Formality, WardrobeItem

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

# Whole-word keywords scanned inside a FREE-TEXT occasion ("wedding party",
# "beach day") when the whole string isn't an exact OCCASION_FORMALITY key.
# Single tokens only; the multi-word "black tie" cue is matched separately.
OCCASION_KEYWORDS: dict[str, Formality] = {
    "gala": "black_tie",
    "wedding": "formal",
    "funeral": "formal",
    "cocktail": "semi_formal",
    "party": "semi_formal",
    "prom": "semi_formal",
    "interview": "business_casual",
    "office": "business_casual",
    "work": "business_casual",
    "business": "business_casual",
    "meeting": "business_casual",
    "conference": "business_casual",
    "date": "smart_casual",
    "dinner": "smart_casual",
    "brunch": "smart_casual",
    "restaurant": "smart_casual",
    "beach": "casual",
    "gym": "casual",
    "workout": "casual",
    "hike": "casual",
    "hiking": "casual",
    "picnic": "casual",
}


def infer_formality(occasion: str) -> Formality:
    """Resolve a free-text occasion to a formality.

    Exact match on the known occasions first (backward compatible), then a
    WHOLE-WORD keyword scan, so a free-text occasion like "wedding party"
    resolves to "formal" instead of silently defaulting to smart_casual (the
    reported "casual dress suggested for a wedding" bug). Whole-word, not
    substring, so "homework" never trips the "work" keyword. When several
    keywords match (e.g. "beach wedding"), the MOST FORMAL wins — under-
    dressing a formal event is the worse failure. Falls back to smart_casual.
    """
    text = occasion.strip().lower()
    if text in OCCASION_FORMALITY:
        return OCCASION_FORMALITY[text]
    matches: list[Formality] = []
    if "black tie" in text or "black-tie" in text:
        matches.append("black_tie")
    tokens = set(re.findall(r"[a-z]+", text))
    matches.extend(OCCASION_KEYWORDS[t] for t in tokens if t in OCCASION_KEYWORDS)
    if not matches:
        return "smart_casual"
    return max(matches, key=lambda f: FORMALITY_ORDER[f])


def load_wardrobe(user_id: str) -> list[WardrobeItem]:
    """The requesting user's persisted closet (Feature 001: closet
    persistence) — replaces the old JSON-fixture read. The fixture now only
    serves as the one-time catalog seed source (crud.seed_catalog)."""
    from .. import crud
    from ..db import SessionLocal

    with SessionLocal() as session:
        return crud.list_wardrobe_items(session, user_id)


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
    formality = formality or infer_formality(occasion)
    wardrobe = wardrobe if wardrobe is not None else (load_wardrobe(user_id) if user_id else [])

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
