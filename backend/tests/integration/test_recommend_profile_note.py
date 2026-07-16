"""Wiring test for profile_note() -> generate() (Feature 004:
preference-memory).

Confirms two things deterministically, with the pipeline stages mocked (same
pattern as test_recommend_auth.py -- no DB, no LLM call, no network):

1. `memory.profile_note()`'s output reaches `generate()`'s `profile_note`
   kwarg when a user has a learned profile. Before this feature, nothing
   ever called `set_preference()` in production, so `profile_note()` always
   returned `None` and this branch of `generate()` was never actually
   exercised -- this closes that gap (code-review finding C1).
2. The explicit `Context` object passed to `generate()` is exactly the one
   `assemble_context()` produced, unaffected by the presence of a profile
   note -- the wiring can't let a learned preference clobber an explicit
   request (FR-005 / code-review finding C2). Whether the LLM itself obeys
   the note's text is a separate, non-deterministic concern handled by
   quickstart.md's manual check and the eval harness, not here (see root
   CLAUDE.md's eval-harness gotcha).
"""

from __future__ import annotations

from types import SimpleNamespace

from whattowear.pipeline import run
from whattowear.pipeline.generator import GenOutput
from whattowear.schema import Context


def _fake_retrieval():
    return SimpleNamespace(all=lambda: [])


def _fixed_context(user_id: str) -> Context:
    return Context(occasion="dinner", formality="casual", user_id=user_id)


def _patch_pipeline_stages(mocker, *, profile_note_return, captured: dict):
    mocker.patch.object(run, "get_kb", return_value=object())
    mocker.patch.object(run, "_retrieve", return_value=_fake_retrieval())
    mocker.patch.object(run.memory, "remember_interaction")
    mocker.patch.object(run.memory, "profile_note", return_value=profile_note_return)

    def fake_generate(ctx, retrieval, profile_note=None, model=None):
        captured["ctx"] = ctx
        captured["profile_note"] = profile_note
        return GenOutput(outfits=[])

    mocker.patch.object(run, "generate", side_effect=fake_generate)


def test_learned_profile_note_reaches_generate(mocker):
    ctx = _fixed_context("user-with-profile")
    mocker.patch.object(run.context_assembler, "assemble_context", return_value=ctx)
    captured: dict = {}
    _patch_pipeline_stages(mocker, profile_note_return="color:#1b2a4a: #1b2a4a", captured=captured)

    run.run_pipeline("dinner", formality="casual", user_id="user-with-profile")

    assert captured["profile_note"] == "color:#1b2a4a: #1b2a4a"


def test_no_profile_note_reaches_generate_as_none(mocker):
    ctx = _fixed_context("user-with-no-feedback")
    mocker.patch.object(run.context_assembler, "assemble_context", return_value=ctx)
    captured: dict = {}
    _patch_pipeline_stages(mocker, profile_note_return=None, captured=captured)

    run.run_pipeline("dinner", formality="casual", user_id="user-with-no-feedback")

    assert captured["profile_note"] is None


def test_explicit_context_unchanged_by_presence_of_a_profile_note(mocker):
    # FR-005: an explicit request (here, formality="black_tie") must reach
    # generate() exactly as assemble_context() produced it, regardless of
    # whether a learned profile note is also present.
    ctx = Context(occasion="wedding", formality="black_tie", user_id="user-with-profile")
    mocker.patch.object(run.context_assembler, "assemble_context", return_value=ctx)
    captured: dict = {}
    _patch_pipeline_stages(mocker, profile_note_return="formality_drift: less_formal", captured=captured)

    run.run_pipeline("wedding", formality="black_tie", user_id="user-with-profile")

    assert captured["ctx"] is ctx
    assert captured["ctx"].formality == "black_tie"
    assert captured["profile_note"] == "formality_drift: less_formal"
