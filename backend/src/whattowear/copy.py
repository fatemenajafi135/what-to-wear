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


def wrap_up_text(occasion: str, formality: str | None) -> str:
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
    """
    if formality:
        return f"Styling for {occasion}, {formality.lower()}."
    return f"Styling for {occasion}."
