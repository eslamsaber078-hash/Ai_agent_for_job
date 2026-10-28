import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .api import applications, assistant, auth, automation, dashboard, jobs, matching, profile
from .config import CORS_ORIGINS, OPENAI_API_KEY
from .database import Base, SessionLocal, engine, ensure_schema_upgrades
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
# httpx logs every request URL at INFO; provider URLs must never end up in logs
# with credentials attached.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
log = logging.getLogger("jobhunter")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    ensure_schema_upgrades()
    db = SessionLocal()
    try:
        ensure_sources(db)
        cleaned = merge_duplicate_jobs(db)
        if cleaned:
            log.info("Merged %s duplicate job rows", cleaned)
        for pref in db.query(SearchPreference).all():
            hide_stale_jobs(db, pref.max_age_days, profile_id=pref.id)
        start_scheduler(db)
    finally:
        db.close()
    yield
    stop_scheduler()


app = FastAPI(
    title="AI Job Hunter API",
    description="Personal AI-powered job-search agent: discovery, matching, applications, and generated materials.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def private_responses(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


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
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
