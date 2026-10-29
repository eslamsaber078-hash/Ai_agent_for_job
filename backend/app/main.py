import asyncio
import logging
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .api import applications, assistant, auth, automation, dashboard, jobs, matching, profile
from .config import CORS_ORIGINS, OPENAI_API_KEY
from .database import Base, SessionLocal, engine, ensure_schema_upgrades, warm_pool
from .models import SearchPreference
from .schemas import HealthOut
from .services import (
    ai_available,
    ensure_sources,
    hide_stale_jobs,
    merge_duplicate_jobs,
    start_scheduler,
    stop_scheduler,
)
from .services import cache

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
# httpx logs every request URL at INFO; provider URLs must never end up in logs
# with credentials attached.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
log = logging.getLogger("jobhunter")

# The test suite rebuilds the database between cases, so a housekeeping pass that
# wakes up mid-run would race it; conftest turns this off. Nothing else does.
STARTUP_HOUSEKEEPING = True


def _size_threadpool_for_db() -> None:
    # Endpoints here are sync functions, so each hop through a sync dependency or the
    # endpoint itself borrows a worker from anyio's pool. A request keeps its DB
    # connection while it moves between hops, so when the pool has exactly as many
    # connections as workers, a burst can close into a cycle: every worker is on a
    # connection that another waiting request is holding, and nobody moves until the
    # pool timeout. Spare workers break the cycle — a request holding a connection
    # always finds a free thread to finish on.
    import anyio.to_thread

    pool = engine.pool
    connections = pool.size() + getattr(pool, "_max_overflow", 0)
    limiter = anyio.to_thread.current_default_thread_limiter()
    limiter.total_tokens = max(limiter.total_tokens, connections * 2)


def _startup_housekeeping() -> None:
    """Maintenance that does not have to finish before the first request.

    Every step here is a round trip to a database that a free host leaves suspended
    while nobody is using the site, so on a cold start they add up to seconds in which
    the port is open but nothing is answering. Schema work stays synchronous — a
    request must never meet a missing column — everything else moves here.

    The pause lets the visit that woke the host finish loading first: these passes
    write, and a write landing on top of that first page made it measurably slower.
    """
    time.sleep(5)
    db = SessionLocal()
    try:
        warm_pool(engine)
        ensure_sources(db)
        cleaned = merge_duplicate_jobs(db)
        if cleaned:
            log.info("Merged %s duplicate job rows", cleaned)
        for pref in db.query(SearchPreference).all():
            hide_stale_jobs(db, pref.max_age_days, profile_id=pref.id)
        start_scheduler(db)
    except Exception:  # noqa: BLE001
        # A failed tidy-up must never keep the site offline.
        log.exception("Startup housekeeping failed; the API keeps serving")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    _size_threadpool_for_db()
    Base.metadata.create_all(bind=engine)
    ensure_schema_upgrades()
    if STARTUP_HOUSEKEEPING:
        threading.Thread(target=_startup_housekeeping, name="startup-housekeeping", daemon=True).start()
    yield
    stop_scheduler()


app = FastAPI(
    title="AI Job Hunter API",
    description="Personal AI-powered job-search agent: discovery, matching, applications, and generated materials.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(GZipMiddleware, minimum_size=1024, compresslevel=6)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
# Only these writes can change a match score: the CV itself and the postings it is
# scored against. Saving a job or moving a tracker card must not throw away every
# owner's ranking.
_SCORE_AFFECTING = ("/api/profile", "/api/jobs/refresh", "/api/automation")


class PrivateResponses:
    """Pure ASGI middleware: no extra task or memory stream per request.

    The function-based version runs inside BaseHTTPMiddleware, which wraps every
    call in its own task group; under a burst that doubled the task count and left
    the threadpool limit fully borrowed while its workers sat idle.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")
        status = {"code": 500}

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
                if path.startswith("/api/"):
                    # Endpoints that already set the header must not end up with two.
                    message["headers"] = [(k, v) for k, v in message.get("headers", [])
                                          if k.lower() != b"cache-control"]
                    message["headers"].append((b"cache-control", b"no-store"))
            await send(message)

        await self.app(scope, receive, send_wrapper)
        if (path.startswith("/api/") and scope.get("method") not in _SAFE_METHODS
                and status["code"] < 400 and path.startswith(_SCORE_AFFECTING)):
            cache.invalidate()


app.add_middleware(PrivateResponses)


class Admission:
    """Keep in-flight API work within what the DB pool can actually serve.

    Sync endpoints run on worker threads and hold a pooled connection for the whole
    request. Above that limit the extra threads queue inside the pool, so a burst of
    a few hundred visitors used to burn the pool timeout and return 500s while the
    database was idle. Waiting in the event loop instead costs a coroutine and is
    released the moment a slot frees up.
    """

    WAIT_SECONDS = 30

    def __init__(self, app):
        self.app = app
        pool = engine.pool
        self.limit = pool.size() + getattr(pool, "_max_overflow", 0)
        self.slots = asyncio.Semaphore(self.limit)

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")
        # Health checks must never queue behind user traffic: the platform reads a
        # timeout as a dead process and restarts it.
        if scope["type"] != "http" or not path.startswith("/api/") or path == "/api/health":
            await self.app(scope, receive, send)
            return
        try:
            await asyncio.wait_for(self.slots.acquire(), self.WAIT_SECONDS)
        except (asyncio.TimeoutError, TimeoutError):
            response = JSONResponse(status_code=503, content={"detail": "Server is busy, retry shortly"},
                                    headers={"Retry-After": "5"})
            await response(scope, receive, send)
            return
        try:
            await self.app(scope, receive, send)
        finally:
            self.slots.release()


app.add_middleware(Admission)


for router in (auth.router, jobs.router, profile.router, matching.router, assistant.router,
               applications.router, dashboard.router, automation.router):
    app.include_router(router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    log.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/api/health", response_model=HealthOut, tags=["system"])
def health():
    ai_on = ai_available()
    return HealthOut(
        status="ok",
        openai_configured=bool(OPENAI_API_KEY),
        demo_mode=not ai_on,
    )


# When the frontend has been built (frontend/dist), the backend serves it on the
# same origin — one service runs the whole app in production. The app uses
# HashRouter, so every page lives under /#/ and index.html is the only entry.
# Mounted last: /api, /docs and /openapi.json are matched first.
class CachedStaticFiles(StaticFiles):
    """Build assets carry a content hash in their name, so they never change.

    Without a cache header the browser re-downloads ~300 KB of JavaScript on every
    visit, and every one of those visits is a request this server has to answer.
    """

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        if response.status_code == 200:
            if path.startswith("assets/"):
                response.headers.setdefault("Cache-Control", "public, max-age=31536000, immutable")
            else:
                response.headers.setdefault("Cache-Control", "no-cache")
        return response


FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if FRONTEND_DIST.is_dir():
    app.mount("/", CachedStaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
