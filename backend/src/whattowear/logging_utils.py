"""Verbose logging for ingestion (and other CLI tools) — human-readable,
plain-text, a `--verbose`/`-v` toggle. Distinct from `core/logging.py`,
which is structured JSON logging for the running API service, configured
from `Settings.log_level` at app startup: a chunk-by-chunk ingestion
preview rendered as JSON blobs would be unreadable, and this module has
no `Settings`/env dependency at all — it's a pure CLI concern, not an app
one.

Default (INFO): one line per source with its chunk count.
Verbose (DEBUG): additionally logs every chunk's rule_id + a content
preview, so you can see exactly which source produced which chunks before
spending anything on embeddings.
"""

from __future__ import annotations

import logging

_CONFIGURED = False


def configure_logging(verbose: bool = False) -> None:
    global _CONFIGURED
    level = logging.DEBUG if verbose else logging.INFO
    if not _CONFIGURED:
        logging.basicConfig(level=level, format="%(levelname)-7s %(name)s: %(message)s")
        _CONFIGURED = True
    logging.getLogger("whattowear").setLevel(level)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
