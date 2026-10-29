from sqlalchemy import func

from ..models import Application, GeneratedMaterial, Job, SavedJob, SearchPreference
from ..schemas import JobOut
from ..services.apply_method import apply_method, board_of


def like(term: str) -> str:
    """LIKE pattern with the wildcards in the user's text escaped."""
    escaped = "".join(f"\\{c}" if c in "\\%_" else c for c in term)
    return f"%{escaped}%"


def resolve_sources(db, requested: list[str] | None, profile_id: int) -> list[str]:
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
        final = wanted
    else:
        pref = db.get(SearchPreference, profile_id)
        ticked = [s for s in (pref.sources if pref else []) if s in known]
        if not ticked:
            raise HTTPException(
                status_code=422,
                detail="No job site is ticked. Tick at least one source in Automation settings, "
                       "or pick one in the import bar on the Find Jobs page.",
            )
        final = ticked
    selected = set(final)
    return [name for name in REGISTRY if name in selected]


def job_to_out(db, job: Job) -> JobOut:
    saved = db.query(SavedJob).filter(SavedJob.job_id == job.id).first() is not None
    app = db.query(Application).filter(Application.job_id == job.id).first()
    docs = (db.query(func.count(GeneratedMaterial.id))
            .filter(GeneratedMaterial.application_id == app.id).scalar() if app else 0)
    out = JobOut.model_validate(job)
    return out.model_copy(update={
        "saved": saved,
        "application_status": app.status if app else None,
        "application_id": app.id if app else None,
        "application_docs": docs or 0,
        "publisher": board_of(job),
        **apply_method(job),
    })


LIST_SNIPPET_CHARS = 600


def with_snippet(out: JobOut, limit: int = LIST_SNIPPET_CHARS) -> JobOut:
    """The list card clamps the ad to two lines; the full text is fetched on open.

    A page of twenty postings carried ~90 KB of descriptions to render a snippet of
    each. Cutting the text here keeps the payload to what the card actually draws.
    """
    text = out.description or ""
    if len(text) <= limit:
        return out
    cut = text[:limit]
    space = cut.rfind(" ")
    if space > limit // 2:
        cut = cut[:space]
    return out.model_copy(update={"description": cut})


def jobs_to_out(db, jobs: list[Job]) -> list[JobOut]:
    """job_to_out for a whole page: a handful of bulk queries instead of per job."""
    if not jobs:
        return []
    ids = [j.id for j in jobs]
    saved = {s.job_id for s in db.query(SavedJob.job_id).filter(SavedJob.job_id.in_(ids)).all()}
    apps = db.query(Application.id, Application.job_id, Application.status) \
        .filter(Application.job_id.in_(ids)).all()
    desk = {a.job_id: a for a in apps}
    docs = dict(db.query(GeneratedMaterial.application_id, func.count(GeneratedMaterial.id))
                .filter(GeneratedMaterial.application_id.in_([a.id for a in apps]))
                .group_by(GeneratedMaterial.application_id).all()) if apps else {}
    out = []
    for job in jobs:
        j = JobOut.model_validate(job)
        app = desk.get(job.id)
        out.append(j.model_copy(update={
            "saved": job.id in saved,
            "application_status": app.status if app else None,
            "application_id": app.id if app else None,
            "application_docs": docs.get(app.id, 0) if app else 0,
            "publisher": board_of(job),
            **apply_method(job),
        }))
    return out


def get_job_or_404(db, job_id: int, profile_id: int) -> Job:
    job = db.query(Job).filter(Job.id == job_id, Job.profile_id == profile_id).first()
    if job is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Job not found")
    return job
