from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AutomationRun, SearchPreference, UserProfile
from ..schemas import (
    AutomationRunOut,
    RunResult,
    SearchPlanOut,
    SearchPreferenceIn,
    SearchPreferenceOut,
)
from ..services import REGISTRY, apply_settings, get_scheduler, run_search_now, search_plan
from .auth import get_current_profile
from .deps import resolve_sources
from .streaming import stream_run

router = APIRouter(prefix="/api/automation", tags=["automation"])


def _get_pref(db: Session, profile_id: int) -> SearchPreference:
    pref = db.get(SearchPreference, profile_id)
    if pref is None:
        pref = SearchPreference(id=profile_id)
        db.add(pref)
        db.commit()
        db.refresh(pref)
    return pref


def _scheduler_job_id(profile_id: int) -> str:
    return f"scheduled_search:{profile_id}"


@router.get("/settings", response_model=SearchPreferenceOut)
def read_settings(db: Session = Depends(get_db), profile: UserProfile = Depends(get_current_profile)):
    pref = _get_pref(db, profile.id)
    out = SearchPreferenceOut.model_validate(pref)
    out.scheduler_running = bool(get_scheduler().get_job(_scheduler_job_id(profile.id)))
    return out


@router.put("/settings", response_model=SearchPreferenceOut)
def update_settings(data: SearchPreferenceIn, db: Session = Depends(get_db),
                    profile: UserProfile = Depends(get_current_profile)):
    pref = _get_pref(db, profile.id)
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
    apply_settings(db, profile_id=profile.id)
    db.refresh(pref)
    out = SearchPreferenceOut.model_validate(pref)
    out.scheduler_running = bool(get_scheduler().get_job(_scheduler_job_id(profile.id)))
    return out


@router.post("/search-plan", response_model=SearchPlanOut)
def read_search_plan(data: SearchPreferenceIn, db: Session = Depends(get_db),
                     profile: UserProfile = Depends(get_current_profile)):
    """The exact phrases each site would be asked, for a draft or the saved settings.

    Computed by the same code an import runs, so the preview cannot drift from
    what actually happens.
    """
    return search_plan(db, data, profile_id=profile.id)


@router.post("/run", response_model=RunResult)
def trigger_run(sources: list[str] | None = None, db: Session = Depends(get_db),
                profile: UserProfile = Depends(get_current_profile)):
    sites = resolve_sources(db, sources, profile.id)
    try:
        run = run_search_now(db, trigger="manual", sources=sites, profile_id=profile.id)
    except RuntimeError as exc:
        # Already importing for this account; a second click is a conflict, not a 500.
        raise HTTPException(status_code=409, detail=str(exc)) from None
    return RunResult(run_id=run.id, status=run.status, jobs_found=run.jobs_found, log=run.log)


@router.post("/run/stream")
def trigger_run_stream(sources: list[str] | None = None, db: Session = Depends(get_db),
                       profile: UserProfile = Depends(get_current_profile)):
    """"Run search now" with real per-site progress events instead of one long wait."""
    sites = resolve_sources(db, sources, profile.id)

    def runner(session, run_sites, on_progress):
        run = run_search_now(session, trigger="manual", sources=run_sites,
                             on_progress=on_progress, profile_id=profile.id)
        return {
            "type": "done", "run_id": run.id, "status": run.status,
            "jobs_found": run.jobs_found, "log": run.log,
        }

    return stream_run(sites, runner)


@router.get("/runs", response_model=list[AutomationRunOut])
def list_runs(limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db),
              profile: UserProfile = Depends(get_current_profile)):
    return (
        db.query(AutomationRun)
        .filter(AutomationRun.profile_id == profile.id)
        .order_by(AutomationRun.id.desc())
        .limit(limit)
        .all()
    )
