"""Deterministic, Python-owned strings for the conversational-turns surface (feature 016).

These are the only lines on this surface that are NOT written by the model. Everything the
assistant says during an ordinary turn — acknowledging, asking about the occasion, asking about
formality — is generated per turn against `prompts/conversational_turn_system.md`, which is
where that voice is actually specified. The three below exist because each fires in a moment
where there is no model reply to show: the turn cap has been reached and no call is made, the
call itself failed, or the wrap-up is composed from accumulated slots in Python rather than by a
second LLM call (docs/design-decisions.md §49 — "the model extracts; Python composes").

Voice, per design-system.md §9: the assistant speaks in the first person, and error copy names
the problem and gives a recovery action rather than a bare failure.

§9 also carves out connection and system-state copy as impersonal ("That didn't save."), on the
grounds that it describes the device or network rather than a styling decision. `CALL_FAILED` is
deliberately **not** written that way — the design owner chose to keep the stylist's own voice
here. Recorded so it is not later "corrected" into the impersonal form to match the carve-out.
"""

from __future__ import annotations

from .schema import TempBand

# The conversation has hit its per-thread cap, so no further model call is made. Every
# subsequent send returns this same line, so it has to read sensibly more than once, and it must
# never blame the user for having said too much — it points forward to the next action instead
# of naming the limit it just hit.
TURN_CAP_REACHED = "Let's put this to work. Tap Start styling and I'll put some looks together."

# The conversational call failed (gateway, network, timeout). Offers BOTH recoveries
# deliberately: retrying is the obvious one, but everything gathered before the failure still
# works, so "Start styling" remains available — saying so is what stops a failed turn reading as
# a dead end. First person by design-owner choice; see the module docstring.
CALL_FAILED = "I didn't catch that. Try again, or tap Start styling with what we have so far."


# condition -> emoji (design-decisions.md §65). Covers every string `external/weather.py`'s
# `_WMO` table can produce. Product-owner-supplied palette of 10 emoji against 13 conditions is
# not a 1:1 fit — two deliberate reuses (mostly clear/partly cloudy -> 🌤, overcast/fog -> ☁️,
# drizzle/showers -> 🌦, rain/heavy showers -> 🌧) rather than left to guesswork. 🌪 is
# deliberately never assigned — see §65.
_CONDITION_EMOJI: dict[str, str] = {
    "clear": "☀️",
    "mostly clear": "🌤",
    "partly cloudy": "🌤",
    "overcast": "☁️",
    "fog": "☁️",
    "drizzle": "🌦",
    "rain": "🌧",
    "heavy rain": "🌩",
    "showers": "🌦",
    "heavy showers": "🌧",
    "snow": "🌨",
    "heavy snow": "❄️",
    "thunderstorm": "⛈",
}

# temp_band -> emoji (design-decisions.md §65). Fallback ONLY: used when `condition` is None but
# `temp_c`/`temp_band` are known — the refinement-turn case, since `condition` doesn't survive a
# refinement today but `temp_band` does (see context_assembler.py). None of the 10 condition
# emoji above are temperature-only, so this is a second, independent table, not a subset lookup.
_TEMP_BAND_EMOJI: dict[TempBand, str] = {
    "freezing": "❄️",
    "cold": "❄️",
    "cool": "🌤",
    "mild": "🌤",
    "warm": "☀️",
    "hot": "☀️",
}


def wrap_up_text(
    occasion: str,
    formality: str | None,
    *,
    temp_c: float | None = None,
    condition: str | None = None,
    temp_band: TempBand | None = None,
) -> str:
    """The summary shown as its own assistant message the moment "Start styling" is tapped,
    directly above the outfits — what the app understood, in the user's own terms, while the
    expensive call runs.

    Deliberately short: it sits between the conversation and the results, and anything longer
    reads as padding in front of the thing actually being waited for.

    `formality` arrives title-cased (`_FORMALITY_LABELS`, shared with the outfit meta line, where
    it starts a segment and so is capitalised correctly). It is lowered here because mid-sentence
    "Black tie" renders as a stray capital — found by reading a real wrap-up, not by inspection.

    Degrades to occasion-only when formality is unknown, rather than showing an empty slot or a
    placeholder (FR-007).

    Appends a weather clause — "— {emoji} {temp_c:g}°C." — when `temp_c` is known (issue #67,
    design-decisions.md §65). `condition` (an `external/weather.py` `_WMO` label) picks the emoji
    when available; when it's `None` but `temp_band` is known — a refinement turn, where
    `condition` doesn't survive but `temp_band` does — falls back to the temp_band table instead.
    No clause at all when `temp_c` itself is unknown; the fallback table can't be reached from
    `temp_band` alone without a temperature to show next to it.
    """
    stem = f"Styling for {occasion}, {formality.lower()}" if formality else f"Styling for {occasion}"
    if temp_c is None:
        return f"{stem}."
    if condition is not None:
        emoji = _CONDITION_EMOJI.get(condition)
    elif temp_band is not None:
        emoji = _TEMP_BAND_EMOJI.get(temp_band)
    else:
        emoji = None
    if emoji is None:
        return f"{stem}."
    return f"{stem} — {emoji} {temp_c:g}°C."
