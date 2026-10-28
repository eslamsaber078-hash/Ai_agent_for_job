from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import UserProfile
from ..schemas import MatchResult
from ..services import cache, compute_match
from ..services.scored import RANK_TTL_SECONDS, decorate, ranked
from .auth import get_current_profile
from .deps import get_job_or_404

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
    # The whole account is ranked once and cached; a page turn only rewrites the fifty
    # rows it returns in full. Building that fifty-row breakdown is the expensive part
    # of this endpoint, and the page it fills changes only when the owner writes
    # something — so the built page is kept too. A search box narrows an arbitrary
    # query, which cache entries would only crowd out, so those run fresh.
    profile_empty = not any([
        profile.skills, profile.experiences, profile.projects,
        profile.desired_titles, profile.summary,
    ])

    def build():
        rows = ranked(db, profile, lang)
        if q:
            needle = q.lower()
            rows = [r for r in rows
                    if needle in (r["job"]["title"] or "").lower()
                    or needle in (r["job"]["company"] or "").lower()]
        results = [r for r in rows if r["score"] >= min_score]
        return {"items": decorate(db, profile, results[:limit], lang),
                "total": len(results), "profile_empty": profile_empty}

    if q:
        return build()
    return cache.cached(profile.id, f"matches:{lang}:{min_score}:{limit}",
                        RANK_TTL_SECONDS, build)
