from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Job, JobSource, SavedJob, UserProfile
from ..schemas import JobPage, JobOut, SavedJobOut
from ..services import REGISTRY, compute_match, run_search_now
from .deps import get_job_or_404, job_to_out, like, resolve_sources

router = APIRouter(prefix="/api", tags=["jobs"])


@router.get("/jobs", response_model=JobPage)
def list_jobs(
    q: str = "",
    skill: str = "",
    location: str = "",
    level: str = "",
    emp_type: str = "",
    source: str = "",
    remote: bool | None = None,
    include_stale: bool = Query(False, description="Also list postings the sources no longer advertise"),
    sort: str = Query("date", pattern="^(date|title|company|salary)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(Job)
    if not include_stale:
        query = query.filter(Job.is_active.is_(True))
    if q:
        pattern = like(q)
        query = query.filter(or_(Job.title.ilike(pattern, escape="\\"), Job.company.ilike(pattern, escape="\\"),
                                 Job.description.ilike(pattern, escape="\\")))
    if location:
        pattern = like(location)
        query = query.filter(or_(Job.location.ilike(pattern, escape="\\"), Job.country.ilike(pattern, escape="\\")))
    if level:
        query = query.filter(Job.experience_level == level)
    if emp_type:
        query = query.filter(Job.employment_type == emp_type)
    if source:
        query = query.filter(Job.source == source)
    if remote is not None:
        query = query.filter(Job.remote.is_(remote))

    jobs = query.all()
    if skill:
        skill_l = skill.lower()
        jobs = [j for j in jobs if any(skill_l in (s or "").lower() for s in (j.skills or []))
                or skill_l in (j.description or "").lower()]

    if sort == "date":
        jobs.sort(key=lambda j: (j.posted_date.timestamp() if j.posted_date else 0), reverse=True)
    elif sort == "title":
        jobs.sort(key=lambda j: j.title.lower())
    elif sort == "company":
        jobs.sort(key=lambda j: j.company.lower())
    elif sort == "salary":
        jobs.sort(key=lambda j: j.salary_min or -1, reverse=True)

    total = len(jobs)
    pages = max(1, (total + page_size - 1) // page_size)
    page_jobs = jobs[(page - 1) * page_size: (page - 1) * page_size + page_size]
    return JobPage(items=[job_to_out(db, j) for j in page_jobs], total=total,
                   page=page, page_size=page_size, pages=pages)


@router.get("/jobs/filters")
def job_filters(db: Session = Depends(get_db)):
    levels = sorted({j.experience_level for j in db.query(Job.experience_level).distinct() if j[0]})
    types = sorted({j.employment_type for j in db.query(Job.employment_type).distinct() if j[0]})
    sources = sorted({j.source for j in db.query(Job.source).distinct() if j[0]})
    return {"levels": levels, "employment_types": types, "sources": sources}


@router.get("/jobs/sources")
def list_sources(db: Session = Depends(get_db)):
    """Every importable site, with how many live postings each has already contributed.

    Sites with zero postings are still listed so the per-site import bar is complete.
    """
    rows = {s.name: s for s in db.query(JobSource).all()}
    counts = dict(
        db.query(Job.source, func.count(Job.id)).filter(Job.is_active.is_(True)).group_by(Job.source).all()
    )
    out = []
    for name, cls in REGISTRY.items():
        row = rows.get(name)
        out.append(dict(
            name=name,
            label=row.label if row else cls.label,
            enabled=row.enabled if row else True,
            requires_key=cls.requires_key,
            live_jobs=counts.get(name, 0),
        ))
    return out


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: int, db: Session = Depends(get_db)):
    return job_to_out(db, get_job_or_404(db, job_id))


@router.post("/jobs/refresh")
def refresh_jobs(sources: list[str] | None = None, db: Session = Depends(get_db)):
    """Import now. With `sources` the user names one site, so a single site is fetched.

    Without it, the sites ticked in Automation settings are the ones searched.
    This runs through the same pipeline as the scheduled search, so the import also
    shows up in the run history and a failure becomes a readable message, not a 500.
    """
    sites = resolve_sources(db, sources)
    run = run_search_now(db, trigger="manual", sources=sites)
    if run.status == "failed":
        raise HTTPException(status_code=500, detail=run.error or "Import failed")
    return {"jobs_new": run.jobs_found, "log": run.log.splitlines(), "sources_used": sites}


# ---------- Saved jobs ----------


@router.post("/jobs/{job_id}/save")
def save_job(job_id: int, notes: str = "", db: Session = Depends(get_db)):
    get_job_or_404(db, job_id)
    existing = db.query(SavedJob).filter(SavedJob.job_id == job_id).first()
    if existing:
        existing.notes = notes or existing.notes
        db.commit()
        return {"saved": True, "id": existing.id}
    saved = SavedJob(job_id=job_id, notes=notes)
    db.add(saved)
    db.commit()
    return {"saved": True, "id": saved.id}


@router.delete("/jobs/{job_id}/save")
def unsave_job(job_id: int, db: Session = Depends(get_db)):
    saved = db.query(SavedJob).filter(SavedJob.job_id == job_id).first()
    if saved:
        db.delete(saved)
        db.commit()
    return {"saved": False}


@router.get("/saved-jobs", response_model=list[SavedJobOut])
def list_saved_jobs(q: str = "", db: Session = Depends(get_db)):
    query = db.query(SavedJob).order_by(SavedJob.saved_at.desc())
    items = query.all()
    profile = db.get(UserProfile, 1)
    result = []
    for s in items:
        if q and q.lower() not in f"{s.job.title} {s.job.company}".lower():
            continue
        out = SavedJobOut.model_validate(s)
        out.job = job_to_out(db, s.job)
        if profile is not None:
            out.score = compute_match(s.job, profile, use_ai=False)["score"]
        result.append(out)
    return result
