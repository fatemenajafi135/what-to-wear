"""Regression test for trap 1 (specs/002-backend-foundation/research.md §1):
`import whattowear` must never require a configured database, or any
environment variable at all.
"""

from __future__ import annotations

import subprocess
import sys


def test_import_succeeds_with_zero_environment_variables() -> None:
    result = subprocess.run(
        [sys.executable, "-c", "import whattowear"],
        env={},
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, f"stdout={result.stdout!r} stderr={result.stderr!r}"
