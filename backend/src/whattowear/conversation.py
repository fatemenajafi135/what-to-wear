"""Conversational styling turns (feature 016) — the reply-and-extract call every Recommend
composer send now makes, before "Start styling" ever runs the real pipeline.

One structured-output chat-model call, on the small chat model, through the same
`adapters.llm_gateway` gateway every other LLM call site in this codebase uses — not a second way
to call an LLM (constitution Principle I). No retrieval, no wardrobe load, no pipeline
invocation: this module never imports anything from `pipeline/`. Mirrors `vision.py`'s exact
`get_chat_model(...).with_structured_output(...)` idiom and its reason for a hand-written schema
rather than one derived from the Pydantic model directly.

Slot names match `GraphState`'s own fields exactly (docs/design-decisions.md §47) — the caller
(`api/v1/routes/recommend.py`) is what actually reads/writes the pipeline's checkpointer; this
module only extracts, it never touches storage of any kind.
"""

from __future__ import annotations

from typing import Any

from langsmith import traceable

from .adapters.llm_gateway import get_chat_model
from .prompts import load_prompt
from .schema import FORMALITY_ORDER, ConversationalTurnResult

# Hand-written nullable-required schema — same reason `vision.py::_EXTRACTION_SCHEMA` gives:
# the gateway's structured-output mode rejects a Pydantic-derived schema for a model with
# optional fields (it expects every property in `required`, optionality expressed as a nullable
# type). `reply_text` is genuinely required (never null); every slot is nullable but still listed
# in `required`, matching the gateway's own expectation.
#
# `formality` carries an explicit `enum` (found live: without one, the model reliably
# understands a phrase like "black tie" well enough to reply in-voice about it, but does not
# reliably map it onto the exact literal the pipeline's `Formality` type expects — a real
# extraction-quality gap, not the schema's optionality itself. Constitution Principle VI: the
# pipeline consumes only these six values, so constraining the model's *output* to them (rather
# than free text ConversationalTurnResult's own validator then has to police) is the fix.
_TURN_SCHEMA = {
    "title": "ConversationalTurnResult",
    "type": "object",
    "properties": {
        "reply_text": {"type": "string"},
        "occasion": {"type": ["string", "null"]},
        "mood": {"type": ["string", "null"]},
        "formality": {"type": ["string", "null"], "enum": [*FORMALITY_ORDER, None]},
        "location": {"type": ["string", "null"]},
        "temp_c": {"type": ["number", "null"]},
    },
    "required": ["reply_text", "occasion", "mood", "formality", "location", "temp_c"],
    "additionalProperties": False,
}

_SLOT_LABELS: dict[str, str] = {
    "occasion": "occasion",
    "mood": "mood",
    "formality": "formality",
    "location": "location",
    "temp_c": "temperature (C)",
}


def _known_slots_line(known_slots: dict[str, Any]) -> str:
    """Formats what's already been gathered so the model doesn't re-ask — omits any slot that's
    still `None`/absent rather than listing it as "unknown", so the prompt states only positive
    facts."""
    known = [
        f"{_SLOT_LABELS[key]}: {value}"
        for key, value in known_slots.items()
        if key in _SLOT_LABELS and value is not None
    ]
    if not known:
        return "Nothing is known yet — this is the first turn."
    return "Already known: " + "; ".join(known) + "."


@traceable(name="conversation.reply", run_type="chain")
def reply(message: str, known_slots: dict[str, Any]) -> ConversationalTurnResult:
    """One conversational turn. Raises on a genuine call failure (network/gateway error,
    unparseable structured output) — the caller (the route) maps that to the fixed
    `copy.CALL_FAILED` fallback, never a 5xx, mirroring `vision.py`'s own call-failure
    philosophy."""
    system_prompt, _version = load_prompt("conversational_turn_system")
    llm = get_chat_model().with_structured_output(_TURN_SCHEMA, method="json_schema")
    human = f"{_known_slots_line(known_slots)}\n\nUser: {message}"
    raw: Any = llm.invoke([("system", system_prompt), ("human", human)])
    return ConversationalTurnResult(**raw)
