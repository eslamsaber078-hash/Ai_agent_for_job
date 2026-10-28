from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Job, UserProfile
from ..schemas import MatchResult
from ..services import compute_match
from .auth import get_current_profile
from .deps import get_job_or_404, like

router = APIRouter(prefix="/api", tags=["matching"])


@router.get("/matches/{job_id}", response_model=MatchResult)
def match_job(job_id: int, db: Session = Depends(get_db),
              profile: UserProfile = Depends(get_current_profile),
              lang: str = Query("en", pattern="^(en|ar)$")):
    job = get_job_or_404(db, job_id, profile.id)
    return compute_match(job, profile, lang=lang)


@router.get("/matches")
def list_matches(
    min_score: int = Query(0, ge=0, le=100),
    limit: int = Query(50, ge=1, le=200),
    q: str = "",
    db: Session = Depends(get_db),
    profile: UserProfile = Depends(get_current_profile),
    lang: str = Query("en", pattern="^(en|ar)$"),
):
    query = db.query(Job).filter(Job.is_active.is_(True), Job.profile_id == profile.id)
    if q:
        pattern = like(q)
        from sqlalchemy import or_
        query = query.filter(or_(Job.title.ilike(pattern, escape="\\"), Job.company.ilike(pattern, escape="\\")))
    jobs = query.all()
    results = []
    for job in jobs:
        m = compute_match(job, profile, use_ai=False, lang=lang)
        if m["score"] >= min_score:
            m["job"] = dict(
                id=job.id, title=job.title, company=job.company, location=job.location,
                country=job.country, remote=job.remote, source=job.source,
                experience_level=job.experience_level, salary_min=job.salary_min,
                salary_max=job.salary_max, salary_currency=job.salary_currency,
                is_demo=job.is_demo, url=job.url,
                date_kind=job.date_kind,
                posted_date=job.posted_date.isoformat() if job.posted_date else None,
                first_seen=job.first_seen.isoformat() if job.first_seen else None,
            )
            results.append(m)
    # Best fit first; inside the same score the freshest posting wins.
    results.sort(key=lambda r: (r["score"], r["job"]["posted_date"] or ""), reverse=True)
    profile_empty = not any([
        profile.skills, profile.experiences, profile.projects,
        profile.desired_titles, profile.summary,
    ])
    return {"items": results[:limit], "total": len(results), "profile_empty": profile_empty}
