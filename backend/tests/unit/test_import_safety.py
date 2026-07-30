"""Regression test for trap 1 (specs/002-backend-foundation/research.md §1):
`import whattowear` must never require a configured database, or any
environment variable at all.

Each module that could grow a module-level `get_settings()`/`create_engine()`
call is imported on its own, in its own zero-environment subprocess — not
just the empty `whattowear/__init__.py`, which loads none of them and would
stay green forever regardless of what `core.config`, `core.db`, `core.logging`
or `main` do at import time.

The subprocess also runs with `cwd` set to an empty temporary directory, not
`backend/`. `core.config.Settings` reads `.env` straight off disk
(`pydantic-settings`, relative to cwd) independent of `env={}` clearing OS
variables — so a contributor who followed quickstart.md and has a real
`backend/.env` sitting around would make this test pass even with a genuine
regression in place. Verified: without the `cwd` isolation, this test stayed
green with a deliberate module-level `get_settings()` added to `main.py`,
purely because `backend/.env` existed locally.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile

import pytest

REGRESSION_SURFACE_MODULES = [
    "whattowear.core.config",
    "whattowear.core.db",
    "whattowear.core.logging",
    "whattowear.main",  # transitively imports config and db — the one most likely to catch a real regression
    # --- feature 007 (AI layer port) — extended per module as each lands ---
    "whattowear.ports",
    "whattowear.adapters.llm_gateway",
    "whattowear.prompts",
    "whattowear.schema",
    "whattowear.colors",
    "whattowear.categories",
    "whattowear.adapters.closet_fixture",
    "whattowear.scoring",
    "whattowear.scoring.properties",
    "whattowear.scoring.color_harmony",
    "whattowear.scoring.combine",
    "whattowear.scoring.formality_coherence",
    "whattowear.scoring.silhouette_balance",
    "whattowear.scoring.weather_fitness",
    "whattowear.retrieval.base",
    "whattowear.retrieval.baseline",
    "whattowear.retrieval.hybrid",
    "whattowear.retrieval.advanced",
    "whattowear.memory.preferences",
    "whattowear.memory.store",
    "whattowear.external.weather",
    "whattowear.external.trends",
]


@pytest.mark.parametrize("module", REGRESSION_SURFACE_MODULES)
def test_import_succeeds_with_zero_environment_variables(module: str) -> None:
    with tempfile.TemporaryDirectory() as empty_cwd:
        result = subprocess.run(
            [sys.executable, "-c", f"import {module}"],
            env={},
            cwd=empty_cwd,
            capture_output=True,
            text=True,
            timeout=30,
        )

    assert result.returncode == 0, f"stdout={result.stdout!r} stderr={result.stderr!r}"
