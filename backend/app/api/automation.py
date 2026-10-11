from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AutomationRun, SearchPreference
from ..schemas import AutomationRunOut, RunResult, SearchPreferenceIn, SearchPreferenceOut
from ..services import REGISTRY, apply_settings, get_scheduler, run_search_now
from .deps import resolve_sources

router = APIRouter(prefix="/api/automation", tags=["automation"])


def _get_pref(db: Session) -> SearchPreference:
    pref = db.get(SearchPreference, 1)
    if pref is None:
        pref = SearchPreference(id=1)
        db.add(pref)
        db.commit()
        db.refresh(pref)
    return pref


@router.get("/settings", response_model=SearchPreferenceOut)
def read_settings(db: Session = Depends(get_db)):
    pref = _get_pref(db)
    out = SearchPreferenceOut.model_validate(pref)
    scheduler = get_scheduler()
    out.scheduler_running = bool(scheduler.get_job("scheduled_search"))
    return out


@router.put("/settings", response_model=SearchPreferenceOut)
def update_settings(data: SearchPreferenceIn, db: Session = Depends(get_db)):
    pref = _get_pref(db)
    known_sources = set(REGISTRY)
    unknown = [s for s in data.sources if s not in known_sources]
    if unknown:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown job source(s): {', '.join(unknown)}. Available: {', '.join(sorted(known_sources))}",
        )
    for field, value in data.model_dump().items():
        setattr(pref, field, value)
    db.commit()
    apply_settings(db)
    db.refresh(pref)
    out = SearchPreferenceOut.model_validate(pref)
    out.scheduler_running = bool(get_scheduler().get_job("scheduled_search"))
    return out


@router.post("/run", response_model=RunResult)
def trigger_run(sources: list[str] | None = None, db: Session = Depends(get_db)):
    sites = resolve_sources(db, sources)
    run = run_search_now(db, trigger="manual", sources=sites)
    return RunResult(run_id=run.id, status=run.status, jobs_found=run.jobs_found, log=run.log)


@router.get("/runs", response_model=list[AutomationRunOut])
def list_runs(limit: int = 20, db: Session = Depends(get_db)):
    runs = db.query(AutomationRun).order_by(AutomationRun.id.desc()).limit(min(limit, 100)).all()
    return runs
