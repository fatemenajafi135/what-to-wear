"""FastAPI app. `GET /health` (see contracts/health.md under
specs/002-backend-foundation/) plus `/api/v1/whoami` (see
specs/003-auth/contracts/whoami.md) — the latter is not a product endpoint,
it exists to prove JWT verification works end to end.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from whattowear.api.v1.routes.closet import router as closet_router
from whattowear.api.v1.routes.whoami import router as whoami_router
from whattowear.core.db import get_engine
from whattowear.core.logging import configure_logging

# The Next.js dev server's origin — port 3000 for `npm run dev`, port 3100
# for the e2e suite (frontend/playwright.config.ts runs its own `next dev`
# on a separate port so it never collides with a developer's own running
# dev server). Hardcoded rather than threaded through Settings: this
# project has no deployed frontend yet (local Supabase only, per every
# other feature's "local only" scoping), and reading it via get_settings()
# at module level would break the zero-env-vars import contract
# test_import_safety.py exists specifically to catch — its own docstring
# documents this exact mistake as the regression it protects against.
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
# Feature 004 is the first slice where a browser calls this API directly
# (003's /whoami was never called from the UI) — without this, every
# request from the Next.js dev server is blocked by the browser's CORS
# preflight before it ever reaches a route.
app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(whoami_router, prefix="/api/v1")
app.include_router(closet_router, prefix="/api/v1")


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
