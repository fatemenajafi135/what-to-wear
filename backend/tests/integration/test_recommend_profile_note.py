"""Wiring test for profile_note() -> generate() (Feature 004:
preference-memory).

Confirms two things deterministically, with `generate()` and
`memory.profile_note()` mocked (same pattern as
`tests/unit/pipeline/test_graph.py` -- no DB, no LLM call, no network):

1. `memory.profile_note()`'s output reaches `generate()`'s `profile_note`
   kwarg when a user has a learned profile. Before Feature 004, nothing ever
   called `set_preference()` in production, so `profile_note()` always
   returned `None` and this branch of `generate()` was never actually
   exercised -- this closes that gap (code-review finding C1).
2. The `Context` passed to `generate()` keeps the caller's explicit request
   (here, formality) unaffected by the presence of a profile note -- the
   wiring can't let a learned preference clobber an explicit request
   (FR-005 / code-review finding C2). Whether the LLM itself obeys the
   note's text is a separate, non-deterministic concern handled by
   quickstart.md's manual check and the eval harness, not here (see root
   CLAUDE.md's eval-harness gotcha).

Originally wired through `pipeline.run.run_pipeline` (the pre-Feature-002
linear pipeline); updated to call `pipeline.graph.generate_outfits`
directly, the node that now owns this call, after `pipeline/run.py` was
retired (Feature 002 Phase 3, T037a) in favor of the LangGraph `/suggest`
path.
"""

from __future__ import annotations

from whattowear.pipeline import graph
from whattowear.pipeline.generator import GenOutput
from whattowear.schema import Context


def _run_generate_outfits(mocker, ctx: Context, *, profile_note_return, captured: dict) -> None:
    mocker.patch.object(graph.memory, "profile_note", return_value=profile_note_return)

    def fake_generate(pruned_ctx, retrieval, profile_note=None, model=None):
        captured["ctx"] = pruned_ctx
        captured["profile_note"] = profile_note
        return GenOutput(outfits=[])

    mocker.patch.object(graph, "generate", side_effect=fake_generate)

    state = {
        "ctx": ctx,
        "candidates": {},
        "retrieval": object(),
        "refinement_deltas": [],
        "last_result": None,
    }
    graph.generate_outfits(state)


def test_learned_profile_note_reaches_generate(mocker):
    ctx = Context(occasion="dinner", formality="casual", user_id="user-with-profile")
    captured: dict = {}

    _run_generate_outfits(mocker, ctx, profile_note_return="color:#1b2a4a: #1b2a4a", captured=captured)

    assert captured["profile_note"] == "color:#1b2a4a: #1b2a4a"


def test_no_profile_note_reaches_generate_as_none(mocker):
    ctx = Context(occasion="dinner", formality="casual", user_id="user-with-no-feedback")
    captured: dict = {}

    _run_generate_outfits(mocker, ctx, profile_note_return=None, captured=captured)

    assert captured["profile_note"] is None


def test_explicit_context_unchanged_by_presence_of_a_profile_note(mocker):
    # FR-005: an explicit request (here, formality="black_tie") must reach
    # generate() unchanged, regardless of whether a learned profile note is
    # also present.
    ctx = Context(occasion="wedding", formality="black_tie", user_id="user-with-profile")
    captured: dict = {}

    _run_generate_outfits(mocker, ctx, profile_note_return="formality_drift: less_formal", captured=captured)

    assert captured["ctx"].formality == "black_tie"
    assert captured["profile_note"] == "formality_drift: less_formal"
