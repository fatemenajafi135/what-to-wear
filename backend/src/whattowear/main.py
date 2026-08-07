"""FastAPI app. `GET /health` (see contracts/health.md under
specs/002-backend-foundation/) plus `/api/v1/whoami` (see
specs/003-auth/contracts/whoami.md) — the latter is not a product endpoint,
it exists to prove JWT verification works end to end.
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from whattowear.api.v1.routes.calendar import router as calendar_router
from whattowear.api.v1.routes.closet import router as closet_router
from whattowear.api.v1.routes.profile import router as profile_router
from whattowear.api.v1.routes.recommend import router as recommend_router
from whattowear.api.v1.routes.taxonomy import router as taxonomy_router
from whattowear.api.v1.routes.whoami import router as whoami_router
from whattowear.core.config import parse_cors_origins
from whattowear.core.db import get_engine
from whattowear.core.logging import configure_logging
from whattowear.pipeline.graph import get_compiled_graph
from whattowear.repositories.supabase_closet import SupabaseClosetRepository

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    # Constructed once at startup rather than on the first request — still
    # lazy relative to import time, just not lazy relative to app-run time
    # (research.md §1's refinement; the two are different, and only the
    # former is what "must import with zero env vars" forbids).
    get_engine()
    # Feature 008: warms the checkpointer's PostgresSaver.setup() call at
    # boot rather than on whichever request happens to invoke the graph
    # first — same rationale as get_engine() above, one line further.
    # docs/design-decisions.md §27: this is deliberately not a migration,
    # since PostgresSaver's schema is LangGraph's to change, not ours to pin.
    # Degrades to lazy (first-request) setup on failure rather than blocking
    # boot — /health already reports DB reachability independently.
    try:
        get_compiled_graph(SupabaseClosetRepository())
    except Exception:
        logger.exception("Checkpointer warm-up failed at startup; will retry lazily on first request")
    yield


app = FastAPI(title="What to Wear — backend foundation", lifespan=lifespan)

# Feature 004 is the first slice where a browser calls this API directly
# (003's /whoami was never called from the UI) — without this, every
# request from the Next.js dev server is blocked by the browser's CORS
# preflight before it ever reaches a route.
#
# `os.getenv`, NOT `get_settings()`: middleware has to be registered at import
# time, and `Settings` requires `DATABASE_URL`, so calling it here would break
# the zero-env-vars import contract `test_import_safety.py` enforces on this
# exact module. `os.getenv` never raises. The parsing (and the local defaults,
# with the reason both host spellings are listed) lives in
# `core.config.parse_cors_origins`, which `Settings.cors_allowed_origins` also
# delegates to — one implementation, so the deployed path and the Settings path
# cannot drift.
#
# This wiring is what makes `WTW_CORS_ORIGINS` do anything at all. It was
# briefly reverted to a hardcoded list while resolving the import-contract
# conflict above, which left the env var, its tests and `render.yaml`'s entry
# all inert — every request from a deployed frontend would have been rejected
# by CORS. `test_cors.py::test_a_configured_deployment_origin_is_allowed`
# exists to catch that regression; do not inline this list again.
app.add_middleware(
    CORSMiddleware,
    allow_origins=parse_cors_origins(os.getenv("WTW_CORS_ORIGINS")),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(whoami_router, prefix="/api/v1")
app.include_router(closet_router, prefix="/api/v1")
app.include_router(profile_router, prefix="/api/v1")
app.include_router(calendar_router, prefix="/api/v1")
app.include_router(taxonomy_router, prefix="/api/v1")
app.include_router(recommend_router, prefix="/api/v1")


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
