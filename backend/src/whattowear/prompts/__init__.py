"""Loads versioned prompt files.

Constitution Technology Constraints: "Prompts are files under `prompts/`,
loaded by name and versioned. Inline prompt strings in Python are
prohibited. Every eval row records the prompt version and model." This
module is the one place that reads a prompt file, so every one of the five
extracted prompts (specs/007-ai-port/contracts/prompt-front-matter.md)
resolves its path the same way — a future prompt-storage change touches
this function, not five call sites.
"""

from __future__ import annotations

from pathlib import Path

import yaml

_PROMPTS_DIR = Path(__file__).parent


def load_prompt(name: str) -> tuple[str, int]:
    """Returns `(prompt_text, version)` for `prompts/<name>.md`.

    Raises `FileNotFoundError` if the file doesn't exist, `ValueError` if the
    YAML front-matter is missing or malformed (no `---`-delimited header, or
    no `version` key) — a prompt file without a version is exactly the
    silent-drift failure mode this loader exists to prevent.
    """
    path = _PROMPTS_DIR / f"{name}.md"
    raw = path.read_text(encoding="utf-8")

    if not raw.startswith("---\n"):
        raise ValueError(f"prompts/{name}.md: missing YAML front-matter (must start with '---')")
    _, _, rest = raw.partition("---\n")
    front_matter_raw, sep, body = rest.partition("\n---\n")
    if not sep:
        raise ValueError(f"prompts/{name}.md: unterminated YAML front-matter (missing closing '---')")

    front_matter = yaml.safe_load(front_matter_raw) or {}
    if "version" not in front_matter:
        raise ValueError(f"prompts/{name}.md: front-matter missing required 'version' field")

    return body.strip("\n"), int(front_matter["version"])
