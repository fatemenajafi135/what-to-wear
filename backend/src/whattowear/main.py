"""FastAPI app. One route: `GET /health` (see contracts/health.md under
specs/002-backend-foundation/). No product endpoint exists in this slice.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from sqlalchemy import text

from whattowear.core.db import get_engine
from whattowear.core.logging import configure_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    # Constructed once at startup rather than on the first request — still
    # lazy relative to import time, just not lazy relative to app-run time
    # (research.md §1's refinement; the two are different, and only the
    # former is what "must import with zero env vars" forbids).
    get_engine()
    yield


app = FastAPI(title="What to Wear — backend foundation", lifespan=lifespan)


def _database_reachable() -> bool:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        logger.exception("Database health check failed")
        return False


@app.get("/health")
def health(response: Response) -> dict[str, object]:
    if not _database_reachable():
        response.status_code = 503
        return {"status": "unhealthy", "failed_dependencies": ["database"]}
    return {"status": "ok"}
