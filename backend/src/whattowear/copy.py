"""Deterministic, Python-owned strings for the conversational-turns surface (feature 016).

Every string below is **DRAFT**, not final copy — `docs/handoffs/016-conversational-turns.md`
§3: the assistant's turn copy is not in `design-system.md`, and Principle VIII forbids inventing
UI copy in code. The design owner is writing the final lines; these exist so the feature is
buildable and demonstrable while that's pending, per the handoff's own instruction ("keep every
string in one module with a comment pointing at §3"). Swap the literal text in place when final
copy arrives — nothing that imports this module needs to change.

These three strings/one function cover only the situations that are Python-decided, not
LLM-generated: a fixed turn cap has been reached, the LLM call itself failed, and the
Start-styling wrap-up (docs/design-decisions.md §49 — "the model extracts; Python composes"
applies to the wrap-up the same way it applies to the pipeline invoke input, so this is not a
second LLM call).
"""

from __future__ import annotations

# DRAFT (handoff §3, row "Turn cap reached") — replace verbatim when final copy arrives.
TURN_CAP_REACHED = "Let's put this to work — tap Start styling and I'll pull some looks together."

# DRAFT (handoff §3, row "Conversational call failed") — replace verbatim when final copy arrives.
CALL_FAILED = "I didn't catch that — try again, or tap Start styling with what we have."


def wrap_up_text(occasion: str, formality: str | None) -> str:
    """DRAFT template (handoff §3, row "Wrap-up on Start styling") — replace verbatim (keeping
    the `{occasion}`/`{formality}` substitution points) when final copy arrives.

    Degrades gracefully when `formality` is unknown (FR-007) rather than rendering a placeholder
    for it — in practice `formality` is rarely `None` by the time this is called, since
    `context_assembler.assemble_context` always infers one when absent, but the degrade path
    exists for honesty regardless.
    """
    if formality:
        return f"Styling for {occasion}, {formality}."
    return f"Styling for {occasion}."
