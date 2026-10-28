from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Application, Job, SavedJob, UserProfile
from ..schemas import STATUSES, DashboardStats, StatusCount
from ..services.scored import ranked
from .applications import _to_out
from .auth import get_current_profile
from .deps import jobs_to_out, with_snippet

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _owned_applications(db: Session, profile_id: int):
    """Every tracker row belongs to the owner of the job it points at."""
    return db.query(Application).join(Job, Application.job_id == Job.id).filter(Job.profile_id == profile_id)


@router.get("/stats", response_model=DashboardStats)
def stats(db: Session = Depends(get_db), profile: UserProfile = Depends(get_current_profile)):
    # One grouped read for both job totals, one grouped read for every tracker count:
    # the page used to issue a separate COUNT per number it draws, and on the hosted
    # database every one of those was a network round-trip of its own.
    by_active = {bool(active): count for active, count in
                 db.query(Job.is_active, func.count(Job.id))
                 .filter(Job.profile_id == profile.id).group_by(Job.is_active).all()}
    total_jobs = by_active.get(True, 0)
    stale_hidden = by_active.get(False, 0)
    saved_jobs = db.query(SavedJob).join(Job, SavedJob.job_id == Job.id).filter(Job.profile_id == profile.id).count()
    status_counts = dict(
        _owned_applications(db, profile.id)
        .with_entities(Application.status, func.count(Application.id))
        .group_by(Application.status).all()
    )
    applications = sum(status_counts.values())
    interviews = status_counts.get("Interview", 0)
    offers = status_counts.get("Offer", 0)

    breakdown = [StatusCount(status=status, count=status_counts[status])
                 for status in STATUSES if status_counts.get(status)]

    recent_jobs = (
        db.query(Job)
        .filter(Job.is_active.is_(True), Job.profile_id == profile.id)
        .order_by(Job.posted_date.desc().nullslast(), Job.id.desc())
        .limit(8)
        .all()
    )

    high_match_jobs = 0
    best_matches = []
    rows = ranked(db, profile)
    for row in rows:
        if row["score"] >= 70:
            high_match_jobs += 1
    for row in rows[:6]:
        best_matches.append(dict(
            job_id=row["job_id"], title=row["job"]["title"], company=row["job"]["company"],
            location=row["job"]["location"], remote=row["job"]["remote"], score=row["score"],
            missing_skills=row["missing_skills"][:5],
        ))

    # Overdue follow-ups come first — they are the ones that need action.
    # A Rejected or Archived application has nothing left to follow up on.
    upcoming = (
        _owned_applications(db, profile.id)
        .filter(Application.follow_up_date.isnot(None))
        .filter(Application.status.notin_(["Rejected", "Archived"]))
        .order_by(Application.follow_up_date.asc())
        .limit(6)
        .all()
    )

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
        recent_jobs=[with_snippet(out) for out in jobs_to_out(db, recent_jobs)],
        best_matches=best_matches,
        upcoming_follow_ups=[_to_out(db, a) for a in upcoming],
        profile_complete=profile_complete,
    )
