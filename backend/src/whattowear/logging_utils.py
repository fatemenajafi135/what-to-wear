"""Verbose logging for ingestion (and beyond).

Default (INFO): one line per source with its chunk count.
Verbose (DEBUG): additionally logs every chunk's rule_id + a content preview,
so you can see exactly which source produced which chunks before spending
anything on embeddings.
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
