import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api import applications, assistant, automation, dashboard, jobs, matching, profile
from .config import CORS_ORIGINS, OPENAI_API_KEY
from .database import Base, SessionLocal, engine, ensure_schema_upgrades
from .models import DEFAULT_JOB_MAX_AGE_DAYS, SearchPreference, UserProfile
from .schemas import HealthOut
from .services import (
    ensure_default_sources,
    ensure_sources,
    hide_stale_jobs,
    merge_duplicate_jobs,
    start_scheduler,
    stop_scheduler,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
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
        pref = db.query(SearchPreference).first()
        hidden = hide_stale_jobs(db, pref.max_age_days if pref else DEFAULT_JOB_MAX_AGE_DAYS)
        if hidden:
            log.info("Hid %s posting(s) that are no longer live at their source", hidden)
        if db.get(UserProfile, 1) is None:
            db.add(UserProfile(id=1))
            db.commit()
        start_scheduler(db)
        ensure_default_sources(db)
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

for router in (jobs.router, profile.router, matching.router, assistant.router,
               applications.router, dashboard.router, automation.router):
    app.include_router(router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    log.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/api/health", response_model=HealthOut, tags=["system"])
def health():
    return HealthOut(
        status="ok",
        openai_configured=bool(OPENAI_API_KEY),
        demo_mode=not bool(OPENAI_API_KEY),
    )
