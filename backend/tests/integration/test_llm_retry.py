"""Integration test for automatic retry on a transient AI-provider failure
(Feature 005 US4/FR-009).

`litellm.completion` is the actual transport `ChatLiteLLM` calls
(`self.client == litellm`, confirmed by inspecting `langchain_litellm`'s
source) — patched here to fail once with a transient error, then fall
through to the real gateway call, so this exercises `config.get_chat_model`'s
real `max_retries` setting end-to-end rather than asserting against a mock.
"""

from __future__ import annotations

import litellm

from whattowear import config


def test_transient_failure_is_retried_transparently():
    real_completion = litellm.completion
    calls = {"n": 0}

    def flaky(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise litellm.exceptions.APIConnectionError(
                message="simulated transient failure",
                llm_provider="openai",
                model=kwargs.get("model", "test"),
            )
        return real_completion(*args, **kwargs)

    litellm.completion = flaky
    try:
        result = config.get_chat_model(temperature=0.0).invoke("Say OK in one word.")
    finally:
        litellm.completion = real_completion

    assert calls["n"] >= 2, "the first (transient) failure must have been retried, not surfaced"
    assert result.content
