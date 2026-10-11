from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Job, UserProfile
from ..schemas import MatchResult
from ..services import compute_match
from .deps import get_job_or_404, like

router = APIRouter(prefix="/api", tags=["matching"])


def _profile(db: Session) -> UserProfile | None:
    return db.get(UserProfile, 1)


@router.get("/matches/{job_id}", response_model=MatchResult)
def match_job(job_id: int, db: Session = Depends(get_db)):
    job = get_job_or_404(db, job_id)
    return compute_match(job, _profile(db))


@router.get("/matches")
def list_matches(
    min_score: int = Query(0, ge=0, le=100),
    limit: int = Query(50, ge=1, le=200),
    q: str = "",
    db: Session = Depends(get_db),
):
    profile = _profile(db)
    query = db.query(Job).filter(Job.is_active.is_(True))
    if q:
        pattern = like(q)
        from sqlalchemy import or_
        query = query.filter(or_(Job.title.ilike(pattern, escape="\\"), Job.company.ilike(pattern, escape="\\")))
    jobs = query.all()
    results = []
    for job in jobs:
        m = compute_match(job, profile, use_ai=False)
        if m["score"] >= min_score:
            m["job"] = dict(
                id=job.id, title=job.title, company=job.company, location=job.location,
                country=job.country, remote=job.remote, source=job.source,
                experience_level=job.experience_level, salary_min=job.salary_min,
                salary_max=job.salary_max, salary_currency=job.salary_currency,
                is_demo=job.is_demo,
                posted_date=job.posted_date.isoformat() if job.posted_date else None,
            )
            results.append(m)
    # Best fit first; inside the same score the freshest posting wins.
    results.sort(key=lambda r: (r["score"], r["job"]["posted_date"] or ""), reverse=True)
    profile_empty = profile is None or not any([
        profile.skills, profile.experiences, profile.projects,
        profile.desired_titles, profile.summary,
    ])
    return {"items": results[:limit], "total": len(results), "profile_empty": profile_empty}
