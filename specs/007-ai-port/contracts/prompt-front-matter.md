# Contract: prompt file format

Every file under `backend/src/whattowear/prompts/` follows this shape (Research §7):

```markdown
---
version: 1
model: <gateway model id this prompt was authored/evaluated against>
role: system
---
<prompt text, verbatim>
```

## Fields

- `version: int` — starts at `1`. Bumped only when the prompt **text** changes. Carrying a
  legacy prompt over unedited keeps `version: 1`; the number exists so a future edit is
  attributable, not so this port artificially increments it.
- `model: str` — the gateway-qualified model id (`config.py`'s `CHAT_MODEL`/`JUDGE_MODEL`
  default at the time this prompt was last evaluated against a baseline). Informational,
  read by the eval harness for the JSONL row's `prompt_versions` field — not enforced at
  runtime (a caller may still pass a different model to `get_chat_model`).
- `role: system` — every one of the five ported prompts is a system prompt; the field exists
  so a future non-system prompt (e.g. a user-turn template) is self-describing rather than
  assumed.

## The five files this feature creates

| File | Ported from | Role |
|---|---|---|
| `prompts/generator_system.md` | `pipeline/generator.py:SYSTEM_PROMPT` | Stylist; assembles outfits strictly from inventory (grounded path) |
| `prompts/vision_system.md` | `vision.py:SYSTEM_PROMPT` | Garment attribute extractor (VLM) |
| `prompts/engine_system.md` | `pipeline/engine.py:_ENGINE_SYSTEM_PROMPT` | Stylist selecting from a pre-scored shortlist (engine path) |
| `prompts/trends_distill.md` | `external/trends.py:_DISTILL_PROMPT` | Distils web results into one factual trend card |
| `prompts/judge.md` | `eval/judge.py:_PROMPT` | Fashion-styling judge (reported-only) |

## Loading contract

Each consuming module calls one shared helper (added alongside `ports.py` or in a small
`prompts/__init__.py`):

```python
def load_prompt(name: str) -> tuple[str, int]:
    """Returns (prompt_text, version). Raises if the file or front-matter is malformed."""
```

No module reads a prompt file path itself beyond passing `name` — the resolution
(`Path(__file__).parent / "prompts" / f"{name}.md"`) lives in one place, so a future prompt
storage change (e.g. a database-backed prompt registry) touches one function, not five call
sites.
