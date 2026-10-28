"""Rank every live posting an owner has, once, and keep the ranking warm.

The Matches page and the dashboard read the same list: each live posting scored against
the same CV, best fit first. Scored per request that is thousands of deterministic
computations to fill one screen, so the ranking is computed once and reused until the
owner writes something (import, profile edit) or the TTL runs out.
"""
from ..models import Job, UserProfile
from . import cache
from .matching import compute_match

RANK_TTL_SECONDS = 900


def job_row(job: Job) -> dict:
    return dict(
        id=job.id, title=job.title, company=job.company, location=job.location,
        country=job.country, remote=job.remote, source=job.source,
        experience_level=job.experience_level, salary_min=job.salary_min,
        salary_max=job.salary_max, salary_currency=job.salary_currency,
        is_demo=job.is_demo, url=job.url,
        date_kind=job.date_kind,
        posted_date=job.posted_date.isoformat() if job.posted_date else None,
        first_seen=job.first_seen.isoformat() if job.first_seen else None,
    )


def _rank(db, profile: UserProfile, lang: str) -> list[dict]:
    jobs = db.query(Job).filter(Job.is_active.is_(True), Job.profile_id == profile.id).all()
    rows = []
    for job in jobs:
        match = compute_match(job, profile, use_ai=False, lang=lang, detail=False)
        match["job"] = job_row(job)
        match["posted_ts"] = job.posted_date.timestamp() if job.posted_date else 0
        rows.append(match)
    # Best fit first; inside the same score the freshest posting wins.
    rows.sort(key=lambda r: (r["score"], r["posted_ts"]), reverse=True)
    return rows


def ranked(db, profile: UserProfile, lang: str = "en") -> list[dict]:
    return cache.cached(profile.id, f"ranked:{lang}", RANK_TTL_SECONDS,
                        lambda: _rank(db, profile, lang))


def decorate(db, profile: UserProfile, rows: list[dict], lang: str = "en") -> list[dict]:
    """The full breakdown, for the rows a screen actually returns."""
    ids = [r["job_id"] for r in rows]
    if not ids:
        return []
    jobs = {j.id: j for j in db.query(Job).filter(Job.id.in_(ids)).all()}
    out = []
    for row in rows:
        job = jobs.get(row["job_id"])
        if job is None:
            continue
        full = compute_match(job, profile, use_ai=False, lang=lang)
        full["job"] = row["job"]
        out.append(full)
    return out
