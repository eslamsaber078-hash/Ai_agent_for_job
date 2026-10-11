from ..models import Application, Job, SavedJob, SearchPreference
from ..schemas import JobOut


def like(term: str) -> str:
    """LIKE pattern with the wildcards in the user's text escaped."""
    escaped = "".join(f"\\{c}" if c in "\\%_" else c for c in term)
    return f"%{escaped}%"


def resolve_sources(db, requested: list[str] | None) -> list[str]:
    """Which sites an import should fetch, or a 422 explaining why it cannot.

    An unknown name used to be dropped silently, so a typo looked like a
    successful import that fetched nothing from that site.
    """
    from fastapi import HTTPException

    from ..services import REGISTRY

    known = set(REGISTRY)
    wanted = [s.strip() for s in (requested or []) if s and s.strip()]
    unknown = [s for s in wanted if s not in known]
    if unknown:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown job source(s): {', '.join(unknown)}. Available: {', '.join(sorted(known))}",
        )
    if wanted:
        return wanted

    pref = db.query(SearchPreference).first()
    ticked = [s for s in (pref.sources if pref else []) if s in known]
    if not ticked:
        raise HTTPException(
            status_code=422,
            detail="No job site is ticked. Tick at least one source in Automation settings, "
                   "or pick one in the import bar on the Find Jobs page.",
        )
    return ticked


def job_to_out(db, job: Job) -> JobOut:
    saved = db.query(SavedJob).filter(SavedJob.job_id == job.id).first() is not None
    app = db.query(Application).filter(Application.job_id == job.id).first()
    out = JobOut.model_validate(job)
    return out.model_copy(update={
        "saved": saved,
        "application_status": app.status if app else None,
    })


def get_job_or_404(db, job_id: int) -> Job:
    job = db.get(Job, job_id)
    if job is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Job not found")
    return job
