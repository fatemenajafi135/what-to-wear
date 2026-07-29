"""Structured (JSON) logging setup.

`configure_logging()` must be called explicitly — from `main.py`'s startup,
not at import time — so importing this module never has a side effect (see
specs/002-backend-foundation/research.md §1, §9).
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from whattowear.core.config import get_settings

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
