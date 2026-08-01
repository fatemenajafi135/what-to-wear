"""Structured (JSON) logging setup.

`configure_logging()` must be called explicitly — from `main.py`'s startup,
not at import time — so importing this module never has a side effect (see
specs/002-backend-foundation/research.md §1, §9).
"""

from __future__ import annotations

import json
import logging
import warnings
from datetime import UTC, datetime
from typing import Any

from whattowear.core.config import get_settings

# Third-party chatter that drowns this app's own logs at INFO. Every LLM
# call (vision extraction, every styling turn, every eval case) otherwise
# emits a "LiteLLM completion() model=..." line plus a "Wrapper: Completed
# Call" line, each duplicated by the root JSON handler — roughly 40 lines
# per styling request. A real error in the middle of that is invisible,
# which is part of why feature 006's silent bulk-upload failure went
# unnoticed in a log the developer was actively watching. Raised to
# WARNING, not disabled: a genuine LiteLLM warning or error still gets
# through.
_NOISY_LOGGERS = ("LiteLLM", "litellm", "httpx", "httpcore")

_RESERVED_LOG_RECORD_ATTRS = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__)


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        extras = {key: value for key, value in record.__dict__.items() if key not in _RESERVED_LOG_RECORD_ATTRS}
        if extras:
            payload.update(extras)
        return json.dumps(payload)


def configure_logging() -> None:
    """Idempotent: safe to call more than once (e.g. under a test-client
    lifespan run repeatedly), since it always fully replaces the root
    handlers rather than appending to them."""
    settings = get_settings()
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(settings.log_level)

    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)

    # LangSmith's tracer serializes LangChain's own `ChatGeneration`/
    # `AIMessage` objects through a Pydantic model that declares the base
    # `Generation`/`BaseMessage` types, so every traced LLM call emits a
    # four-line `PydanticSerializationUnexpectedValue` UserWarning. It is
    # emitted from inside the tracing library about the tracing library's
    # own models — nothing in this codebase can satisfy it, and the traced
    # payload is unaffected. Filtered narrowly by message and module so a
    # Pydantic serializer warning about OUR models still surfaces.
    warnings.filterwarnings(
        "ignore",
        message="Pydantic serializer warnings",
        category=UserWarning,
        module="pydantic.main",
    )
