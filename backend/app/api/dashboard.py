from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Application, Job, SavedJob, UserProfile
from ..schemas import STATUSES, DashboardStats, StatusCount
from ..services import compute_match
from .applications import _to_out
from .deps import job_to_out

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=DashboardStats)
def stats(db: Session = Depends(get_db)):
    live = db.query(Job).filter(Job.is_active.is_(True))
    total_jobs = live.count()
    stale_hidden = db.query(Job).filter(Job.is_active.is_(False)).count()
    saved_jobs = db.query(SavedJob).count()
    applications = db.query(Application).count()
    interviews = db.query(Application).filter(Application.status == "Interview").count()
    offers = db.query(Application).filter(Application.status == "Offer").count()

    breakdown = []
    for status in STATUSES:
        count = db.query(Application).filter(Application.status == status).count()
        if count:
            breakdown.append(StatusCount(status=status, count=count))

    recent_jobs = (
        live.order_by(Job.posted_date.desc().nullslast(), Job.id.desc())
        .limit(8)
        .all()
    )

    profile = db.get(UserProfile, 1)
    high_match_jobs = 0
    best_matches = []
    if profile is not None:
        scored = []
        for job in live.all():
            m = compute_match(job, profile, use_ai=False)
            if m["score"] >= 70:
                high_match_jobs += 1
            scored.append((m["score"], job.posted_date.timestamp() if job.posted_date else 0, job, m))
        scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
        for score, _recency, job, m in scored[:6]:
            best_matches.append(dict(
                job_id=job.id, title=job.title, company=job.company,
                location=job.location, remote=job.remote, score=score,
                missing_skills=m["missing_skills"][:5],
            ))

    # Overdue follow-ups come first — they are the ones that need action.
    upcoming = (
        db.query(Application)
        .filter(Application.follow_up_date.isnot(None))
        .order_by(Application.follow_up_date.asc())
        .limit(6)
        .all()
    )

    profile_complete = False
    if profile is not None:
        profile_complete = bool(profile.full_name and (profile.skills or profile.experiences))

    return DashboardStats(
        total_jobs=total_jobs,
        stale_hidden_jobs=stale_hidden,
        high_match_jobs=high_match_jobs,
        saved_jobs=saved_jobs,
        applications=applications,
        interviews=interviews,
        offers=offers,
        status_breakdown=breakdown,
        recent_jobs=[job_to_out(db, j) for j in recent_jobs],
        best_matches=best_matches,
        upcoming_follow_ups=[_to_out(db, a) for a in upcoming],
        profile_complete=profile_complete,
    )
