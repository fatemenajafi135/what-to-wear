"""FastAPI app. `GET /health` (see contracts/health.md under
specs/002-backend-foundation/) plus `/api/v1/whoami` (see
specs/003-auth/contracts/whoami.md — not a product endpoint, exists to prove
JWT verification works end to end) and `/api/v1/calendar/*` (see
specs/012-calendar/contracts/calendar.md).
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from whattowear.api.v1.routes.calendar import router as calendar_router
from whattowear.api.v1.routes.whoami import router as whoami_router
from whattowear.core.db import get_engine
from whattowear.core.logging import configure_logging

# The Next.js dev server's origin — port 3000 for `npm run dev`, port 3100
# for the e2e suite (matches feature 004's own CORS setup, added
# independently here since this feature is the first browser-calling one
# merged on this branch; additive, no conflict if 004 lands afterward).
_CORS_ALLOWED_ORIGINS = ["http://localhost:3000", "http://localhost:3100"]

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
app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(whoami_router, prefix="/api/v1")
app.include_router(calendar_router, prefix="/api/v1")


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
