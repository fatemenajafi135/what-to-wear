"""Hand-built test-user personas with distinct, deliberately constrained
wardrobes — for manually exercising `recommend()` against edge cases the
default 40-item `data/fixtures/wardrobe.json` doesn't surface (a near-complete
wardrobe rarely stress-tests "what if the user owns almost nothing
appropriate for this request"). Not part of the golden-set eval harness
(`eval/golden_set.py`/`eval/harness.py`) — these are for ad hoc, manual
checking of a specific persona + occasion.

Nothing in this module is executed at import time. Get a persona, optionally
seed their preferences into memory, and invoke the compiled graph
(`pipeline.graph.get_compiled_graph()`) yourself — or run this file
directly (see the __main__ block at the bottom).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..colors import name_to_hex
from ..schema import Formality, Season, WardrobeItem


def _item(
    id: str, category: str, colors: list[str], formality: Formality, warmth: int, season: list[Season]
) -> WardrobeItem:
    """Author items by color NAME for readability; converts to the hex the
    schema actually requires (colors.py: hex is the source of truth, names are
    never stored)."""
    return WardrobeItem(
        id=id,
        category=category,
        colors=[name_to_hex(c) for c in colors],
        formality=formality,
        warmth=warmth,
        season=season,
    )


@dataclass
class TestUser:
    user_id: str
    name: str
    description: str
    wardrobe: list[WardrobeItem]
    # Descriptive only, for a human reading this file -- as of Feature 004
    # (preference-memory), the profile is derived exclusively from real
    # recorded feedback (memory.store.get_profile() aggregates Postgres
    # suggestion_feedback rows); there's no longer a way to inject an
    # arbitrary preference string directly, so this dict is no longer
    # threaded into memory (see seed_test_user_memory's docstring below).
    preferences: dict[str, str] = field(default_factory=dict)


# --- Maya: minimalist office capsule, deliberately owns nothing formal/beachy
MAYA = TestUser(
    user_id="test-maya",
    name="Maya Chen",
    description=(
        "Minimalist capsule wardrobe for a conservative office job. Deliberately "
        "owns no black-tie/gown pieces and no beachwear — good for testing what "
        "recommend() does when a request has no well-matching items at all."
    ),
    preferences={
        "color_preference": "navy, charcoal, cream — avoids bright/saturated colors",
        "fit_preference": "prefers looser, relaxed silhouettes over fitted",
    },
    wardrobe=[
        _item("maya-01", "dress_shirt", ["light blue"], "business_casual", 1, ["spring", "summer", "autumn"]),
        _item("maya-02", "sweater", ["charcoal"], "smart_casual", 3, ["autumn", "winter"]),
        _item("maya-03", "trousers", ["charcoal"], "business_casual", 2, ["spring", "autumn", "winter"]),
        _item("maya-04", "jeans", ["indigo denim"], "casual", 2, ["spring", "autumn", "winter"]),
        _item("maya-05", "blazer", ["navy"], "business_casual", 2, ["spring", "autumn", "winter"]),
        _item("maya-06", "outerwear", ["camel"], "smart_casual", 4, ["winter"]),
        _item("maya-07", "loafers", ["brown"], "smart_casual", 1, ["spring", "summer", "autumn"]),
        _item("maya-08", "shoes", ["black"], "formal", 2, ["spring", "autumn", "winter"]),
        _item("maya-09", "scarf", ["grey"], "casual", 3, ["autumn", "winter"]),
    ],
)

# --- Leo: trend-forward, colorful going-out wardrobe, thin on business wear -
LEO = TestUser(
    user_id="test-leo",
    name="Leo Fontaine",
    description=(
        "Trend-forward, colorful going-out wardrobe with statement jewelry. "
        "Thin on business/office coverage — good for testing L3 trend retrieval "
        "and occasion mismatches (e.g. an office request against this closet)."
    ),
    preferences={
        "color_preference": "bold, saturated colors — tomato red, cobalt, emerald",
        "style_preference": "likes current trends, statement pieces over basics",
    },
    wardrobe=[
        _item("leo-01", "t-shirt", ["tomato red"], "casual", 0, ["summer"]),
        _item("leo-02", "blouse", ["butter yellow"], "smart_casual", 0, ["spring", "summer"]),
        _item("leo-03", "trousers", ["black"], "smart_casual", 2, ["spring", "autumn", "winter"]),
        _item("leo-04", "jeans", ["black"], "smart_casual", 2, ["autumn", "winter"]),
        _item("leo-05", "dress", ["emerald green"], "semi_formal", 1, ["spring", "summer", "autumn"]),
        _item("leo-06", "outerwear", ["black"], "casual", 5, ["winter"]),
        _item("leo-07", "heels", ["black"], "formal", 1, ["spring", "summer", "autumn", "winter"]),
        _item("leo-08", "sneakers", ["white"], "casual", 1, ["spring", "summer", "autumn"]),
        _item("leo-09", "jewelry", ["gold"], "semi_formal", 0, ["spring", "summer", "autumn", "winter"]),
        _item("leo-10", "jewelry", ["silver"], "smart_casual", 0, ["spring", "summer", "autumn", "winter"]),
    ],
)

# --- Amara: warm-climate wardrobe, almost nothing warm ----------------------
AMARA = TestUser(
    user_id="test-amara",
    name="Amara Okafor",
    description=(
        "Warm-climate wardrobe — mostly linen/cotton, sandals, light dresses. "
        "Only ONE moderately warm layer and no real winter coat. Good for "
        "testing graceful degradation when requires_outer can't really be met "
        "from what the user actually owns."
    ),
    preferences={
        "climate_note": "lives somewhere warm; rarely needs cold-weather layering",
    },
    wardrobe=[
        _item("amara-01", "t-shirt", ["white"], "casual", 0, ["summer"]),
        _item("amara-02", "blouse", ["butter yellow"], "smart_casual", 0, ["spring", "summer"]),
        _item("amara-03", "linen_trousers", ["oatmeal"], "smart_casual", 0, ["summer"]),
        _item("amara-04", "shorts", ["khaki"], "casual", 0, ["summer"]),
        _item("amara-05", "dress", ["emerald green"], "semi_formal", 1, ["spring", "summer", "autumn"]),
        _item("amara-06", "cardigan", ["cream"], "smart_casual", 2, ["spring", "autumn"]),  # the ONLY warm-ish layer
        _item("amara-07", "sandals", ["tan"], "casual", 0, ["summer"]),
        _item("amara-08", "heels", ["black"], "formal", 1, ["spring", "summer", "autumn", "winter"]),
        _item("amara-09", "jewelry", ["gold"], "smart_casual", 0, ["spring", "summer", "autumn", "winter"]),
    ],
)

TEST_USERS: dict[str, TestUser] = {u.user_id: u for u in (MAYA, LEO, AMARA)}


def get_test_user(user_id: str) -> TestUser:
    return TEST_USERS[user_id]


if __name__ == "__main__":
    # Manual check — NOT run automatically. Example:
    #   uv run python -m whattowear.eval.test_users test-amara office --temp-c 2
    import argparse
    import uuid

    from ..pipeline.graph import get_compiled_graph

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("user_id", choices=sorted(TEST_USERS))
    ap.add_argument("occasion")
    ap.add_argument("--mood", default=None)
    ap.add_argument("--temp-c", type=float, default=None)
    ap.add_argument("--strategy", default="advanced", choices=["baseline", "hybrid", "advanced"])
    args = ap.parse_args()

    user = get_test_user(args.user_id)
    # Profile seeding is no longer available here (Feature 004: the profile
    # is derived only from real recorded feedback, via /preferences/feedback
    # -> memory.store.get_profile()) -- this persona's `preferences` dict is
    # descriptive only. To exercise profile_note()'s effect manually, record
    # real feedback for this user_id through the API first.
    thread_id = str(uuid.uuid4())
    final_state = get_compiled_graph().invoke(
        {
            "occasion": args.occasion,
            "mood": args.mood,
            "temp_c": args.temp_c,
            "wardrobe": user.wardrobe,
            "user_id": user.user_id,
            "strategy": args.strategy,
            "thread_id": thread_id,
        },
        config={"configurable": {"thread_id": thread_id}},
    )
    print(f"=== {user.name} — {args.occasion} ===")
    for i, outfit in enumerate(final_state["scored_outfits"], 1):
        print(f"Outfit {i}: {', '.join(outfit.items)} (rank_score={outfit.rank_score:.2f})")
        for r in outfit.rationale:
            print(f"  - {r.text}  [cites: {', '.join(r.cites)}]")
    if final_state.get("note"):
        print(f"\nNote: {final_state['note']}")
