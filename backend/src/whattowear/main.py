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

from whattowear.api.v1.routes.calendar import router as calendar_router
from whattowear.api.v1.routes.closet import router as closet_router
from whattowear.api.v1.routes.profile import router as profile_router
from whattowear.api.v1.routes.recommend import router as recommend_router
from whattowear.api.v1.routes.taxonomy import router as taxonomy_router
from whattowear.api.v1.routes.whoami import router as whoami_router
from whattowear.core.config import get_settings
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
# CORS origins are read from Settings (wtw_cors_origins) or default to
# localhost. BOTH `localhost` and `127.0.0.1` are included in defaults
# deliberately: to a browser, they are different origins even though they
# resolve to the same machine. Supabase's `site_url` is `http://127.0.0.1:3000`,
# and `next.config.ts`'s `allowedDevOrigins` allows 127.0.0.1 (feature 003
# needed that for OAuth), while Playwright and most developers typing a URL use
# `localhost`. Listing only one produces a 400 on every preflight from the
# other, surfacing as the closet's generic "Couldn't load your closet." error
# — invisible to the whole test suite because Playwright runs on the host that
# happens to work. There is no security cost to allowing both locally; a
# deployed frontend gets a single explicit origin from configuration.
#
# In production, set wtw_cors_origins to a comma-separated allowlist (e.g.,
# "https://app.example.com,https://staging.example.com"). Each origin is
# stripped of whitespace and empty entries are filtered.
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_allowed_origins,
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
