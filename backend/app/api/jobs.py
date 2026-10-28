import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from .. import config
from ..database import get_db
from ..models import AutomationRun, Job, JobSource, SavedJob, UserProfile
from ..schemas import JobLite, JobPage, JobOut, SavedJobOut
from ..services import EMPTY_SEARCH_ERROR, REGISTRY, compute_match, run_search_now
from ..services import cache
from .deps import get_job_or_404, job_to_out, jobs_to_out, like, resolve_sources, with_snippet
from .streaming import stream_run
from .auth import get_current_profile

router = APIRouter(prefix="/api", tags=["jobs"])

# Which environment variable unlocks a key-gated site. Without it the source is not
# "fetched with nothing kept" — it never ran, and the button has to say so.
_SOURCE_KEY_ATTR = {"jsearch": "RAPIDAPI_KEY", "jooble": "JOOBLE_API_KEY", "adzuna": "ADZUNA_APP_ID"}

# Sorts the database can do on its own. `id` breaks every tie so two pages of the same
# list can never show the same posting twice or skip one.
_SQL_SORTS = {
    "date": (Job.posted_date.desc().nullslast(), Job.id.desc()),
    "title": (func.lower(Job.title), Job.id.asc()),
    "company": (func.lower(Job.company), Job.id.asc()),
}


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
    profile: UserProfile = Depends(get_current_profile),
):
    query = db.query(Job).filter(Job.profile_id == profile.id)
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

    # The plain list — newest first, no description hunting — is what he loads on every
    # keystroke and every page turn, so the database orders and slices it. Reading all
    # 3.7k rows meant carrying 13 MB of descriptions through Python for the 20 he sees.
    order = _SQL_SORTS.get(sort) if not skill.strip() else None
    if order is not None:
        total = query.count()
        page_jobs = query.order_by(*order).offset((page - 1) * page_size).limit(page_size).all()
        return JobPage(items=[with_snippet(o) for o in jobs_to_out(db, page_jobs)], total=total,
                       page=page, page_size=page_size,
                       pages=max(1, (total + page_size - 1) // page_size))

    jobs = query.all()
    if skill.strip():
        # Whole-word match: filtering "Java" must not pull in every JavaScript ad.
        needle = skill.strip()
        folded = needle.lower()
        pattern = re.compile(rf"(?<!\w){re.escape(needle)}(?!\w)", re.IGNORECASE)

        # Every description is scanned for this filter, so the cheap substring check
        # runs first: a row that does not even contain the letters cannot contain the
        # whole word, and most rows miss.
        def has_skill(job: Job) -> bool:
            for tag in (job.skills or []):
                text = tag or ""
                if folded in text.lower() and pattern.search(text):
                    return True
            text = job.description or ""
            return folded in text.lower() and pattern.search(text) is not None

        jobs = [j for j in jobs if has_skill(j)]

    if sort == "date":
        # Newest posting first; a posting with no date sorts last, never first.
        jobs.sort(key=lambda j: (j.posted_date.timestamp() if j.posted_date else 0, j.id), reverse=True)
    elif sort == "title":
        jobs.sort(key=lambda j: j.title.lower())
    elif sort == "company":
        jobs.sort(key=lambda j: j.company.lower())
    elif sort == "salary":
        # Money only compares inside one currency: EGP 30,000 is not USD 30,000. Each
        # currency keeps its own block, biggest first, blocks ordered by their best
        # offer — so the list reads high-to-low without mixing two monies together.
        priced: dict[str, list[Job]] = {}
        for job in jobs:
            if job.salary_min:
                priced.setdefault((job.salary_currency or "").upper(), []).append(job)
        unpriced = [j for j in jobs if not j.salary_min]
        for block in priced.values():
            block.sort(key=lambda j: j.salary_min, reverse=True)
        jobs = [j for block in sorted(priced.values(), key=lambda b: b[0].salary_min, reverse=True)
                for j in block] + unpriced

    total = len(jobs)
    pages = max(1, (total + page_size - 1) // page_size)
    page_jobs = jobs[(page - 1) * page_size: (page - 1) * page_size + page_size]
    return JobPage(items=[with_snippet(o) for o in jobs_to_out(db, page_jobs)], total=total,
                   page=page, page_size=page_size, pages=pages)


@router.get("/jobs/filters")
def job_filters(db: Session = Depends(get_db), profile: UserProfile = Depends(get_current_profile)):
    return cache.cached(profile.id, "job-filters", 600, lambda: _filter_values(db, profile.id))


def _filter_values(db: Session, profile_id: int) -> dict:
    mine = db.query(Job).filter(Job.profile_id == profile_id)
    levels = sorted({j.experience_level for j in mine.with_entities(Job.experience_level).distinct() if j[0]})
    types = sorted({j.employment_type for j in mine.with_entities(Job.employment_type).distinct() if j[0]})
    sources = sorted({j.source for j in mine.with_entities(Job.source).distinct() if j[0]})
    return {"levels": levels, "employment_types": types, "sources": sources}


@router.get("/jobs/sources")
def list_sources(db: Session = Depends(get_db), profile: UserProfile = Depends(get_current_profile)):
    """Every importable site, with how many live postings each has already contributed.

    Sites with zero postings are still listed so the per-site import bar is complete.
    """
    rows = {s.name: s for s in db.query(JobSource).all()}
    counts = dict(
        db.query(Job.source, func.count(Job.id))
        .filter(Job.is_active.is_(True), Job.profile_id == profile.id)
        .group_by(Job.source).all()
    )
    # A site that was fetched but kept nothing has zero postings too, and "Not imported
    # yet" on a button whose import just ran reads like the button is broken. The run
    # history says which is which.
    fetched_at: dict[str, datetime] = {}
    recent = (
        db.query(AutomationRun)
        .filter(AutomationRun.profile_id == profile.id, AutomationRun.status == "success")
        .order_by(AutomationRun.id.desc())
        .limit(200)
        .all()
    )
    for run in recent:
        for name in run.sources_used or []:
            fetched_at.setdefault(name, run.finished_at or run.started_at)
    out = []
    for name, cls in REGISTRY.items():
        row = rows.get(name)
        when = fetched_at.get(name)
        key_name = _SOURCE_KEY_ATTR.get(name, "")
        out.append(dict(
            name=name,
            label=row.label if row else cls.label,
            enabled=row.enabled if row else True,
            requires_key=cls.requires_key,
            key_ready=bool(getattr(config, key_name, "")) if key_name else True,
            live_jobs=counts.get(name, 0),
            fetched_at=when,
        ))
    return out


@router.get("/jobs/light", response_model=list[JobLite])
def list_jobs_light(db: Session = Depends(get_db), profile: UserProfile = Depends(get_current_profile)):
    """The newest live jobs, cut down to what a dropdown needs.

    The Assistant's job picker used to pull 100 full postings (descriptions,
    skill lists, dates…) just to render titles. This must stay declared before
    /jobs/{job_id} so "light" is not swallowed by the int converter.
    """
    rows = (
        db.query(Job.id, Job.title, Job.company, Job.location)
        .filter(Job.is_active.is_(True), Job.profile_id == profile.id)
        .order_by(Job.posted_date.desc().nullslast(), Job.id.desc())
        .limit(200)
        .all()
    )
    return [JobLite(id=r.id, title=r.title, company=r.company, location=r.location) for r in rows]


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: int, db: Session = Depends(get_db), profile: UserProfile = Depends(get_current_profile)):
    return job_to_out(db, get_job_or_404(db, job_id, profile.id))


@router.post("/jobs/refresh")
def refresh_jobs(sources: list[str] | None = None, db: Session = Depends(get_db), profile: UserProfile = Depends(get_current_profile)):
    """Import now. With `sources` the user names one site, so a single site is fetched.

    Without it, the sites ticked in Automation settings are the ones searched.
    This runs through the same pipeline as the scheduled search, so the import also
    shows up in the run history and a failure becomes a readable message, not a 500.
    """
    sites = resolve_sources(db, sources, profile.id)
    try:
        run = run_search_now(db, trigger="manual", sources=sites, profile_id=profile.id)
    except RuntimeError as exc:
        # An import for this account is already running; say so instead of a 500.
        raise HTTPException(status_code=409, detail=str(exc)) from None
    if run.status == "failed":
        if (run.error or "").endswith(EMPTY_SEARCH_ERROR):
            # Not a server fault: the account has no titles or skills to search with yet.
            raise HTTPException(status_code=422, detail=EMPTY_SEARCH_ERROR)
        raise HTTPException(status_code=500, detail=run.error or "Import failed")
    return {"jobs_new": run.jobs_found, "log": run.log.splitlines(), "sources_used": sites}


@router.post("/jobs/refresh/stream")
def refresh_jobs_stream(sources: list[str] | None = None, db: Session = Depends(get_db), profile: UserProfile = Depends(get_current_profile)):
    """The same import as /jobs/refresh, but streamed: a progress event arrives after
    each site actually finishes, so the UI can show a real "site x of N" percentage."""
    sites = resolve_sources(db, sources, profile.id)

    def runner(session, run_sites, on_progress):
        run = run_search_now(session, trigger="manual", sources=run_sites,
                             on_progress=on_progress, profile_id=profile.id)
        if run.status == "failed":
            message = run.error or "Import failed"
            if message.endswith(EMPTY_SEARCH_ERROR):
                message = EMPTY_SEARCH_ERROR
            return {"type": "error", "message": message}
        return {"type": "done", "jobs_new": run.jobs_found, "log": run.log, "sources_used": run_sites}

    return stream_run(sites, runner)


# ---------- Saved jobs ----------


@router.post("/jobs/{job_id}/save")
def save_job(job_id: int, notes: str = "", db: Session = Depends(get_db), profile: UserProfile = Depends(get_current_profile)):
    get_job_or_404(db, job_id, profile.id)
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
def unsave_job(job_id: int, db: Session = Depends(get_db), profile: UserProfile = Depends(get_current_profile)):
    get_job_or_404(db, job_id, profile.id)
    saved = db.query(SavedJob).filter(SavedJob.job_id == job_id).first()
    if saved:
        db.delete(saved)
        db.commit()
    return {"saved": False}


@router.get("/saved-jobs", response_model=list[SavedJobOut])
def list_saved_jobs(q: str = "", db: Session = Depends(get_db), profile: UserProfile = Depends(get_current_profile)):
    query = (
        db.query(SavedJob)
        .join(Job, SavedJob.job_id == Job.id)
        .filter(Job.profile_id == profile.id)
        .order_by(SavedJob.saved_at.desc())
    )
    items = query.all()
    saved_jobs = [s for s in items if not q or q.lower() in f"{s.job.title} {s.job.company}".lower()]
    outs = {o.id: o for o in jobs_to_out(db, [s.job for s in saved_jobs])}
    result = []
    for s in saved_jobs:
        out = SavedJobOut.model_validate(s)
        out.job = outs[s.job_id]
        out.score = compute_match(s.job, profile, use_ai=False)["score"]
        result.append(out)
    return result
