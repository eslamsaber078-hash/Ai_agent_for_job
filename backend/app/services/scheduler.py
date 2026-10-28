"""APScheduler integration.

A single BackgroundScheduler is shared across the app. The scheduled job
reads the stored SearchPreference and runs the discovery pipeline. Manual
triggers reuse the same job function synchronously.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from threading import Lock

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from ..database import SessionLocal
from ..models import AutomationRun, SearchPreference
from .providers import EMPTY_SEARCH_ERROR, effective_terms, run_discovery

log = logging.getLogger("jobhunter.scheduler")

_scheduler: BackgroundScheduler | None = None
JOB_ID = "scheduled_search"
_profile_locks: dict[int, Lock] = {}
_profile_locks_guard = Lock()


def get_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler(timezone="UTC")
    return _scheduler


def run_search_now(db, trigger: str = "manual", sources: list[str] | None = None,
                   on_progress=None, profile_id: int = 1) -> AutomationRun:
    """Run one owner's import; concurrent imports for that owner fail immediately."""
    with _profile_locks_guard:
        profile_lock = _profile_locks.setdefault(profile_id, Lock())
        if not profile_lock.acquire(blocking=False):
            raise RuntimeError("An import is already running for this profile. Wait for it to finish.")
    try:
        pref = db.get(SearchPreference, profile_id)
        if pref is None:
            pref = SearchPreference(id=profile_id)
            db.add(pref)
            db.commit()
        run = AutomationRun(profile_id=profile_id, trigger=trigger, status="running",
                            sources_used=sources or pref.sources or [])
        db.add(run)
        db.commit()
        log_lines: list[str] = []
        total = 0
        try:
            if trigger == "manual" or pref.enabled:
                titles, skills, locations = effective_terms(db, pref, profile_id=profile_id)
                total, log_lines = run_discovery(
                    db, titles, skills, locations, pref.remote_only,
                    sources or pref.sources or None,
                    max_age_days=pref.max_age_days,
                    on_progress=on_progress,
                    profile_id=profile_id,
                    # He pressed Import: he wants what is posted *now*, not what this
                    # browser window cached a few minutes ago.
                    fresh=trigger == "manual",
                )
                log_lines.append(_threshold_line(db, pref, profile_id=profile_id))
            else:
                log_lines.append("Scheduled search is disabled. Enable it in Automation Settings.")
            run.status = "success"
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            if str(exc) == EMPTY_SEARCH_ERROR:
                # A brand-new account with no titles or skills yet; not a crash.
                log.info("Search run for profile %s needs titles or skills first", profile_id)
            else:
                log.exception("Search run failed for profile %s", profile_id)
            run.status = "failed"
            run.error = f"{type(exc).__name__}: {exc}"
            log_lines.append(f"ERROR: {exc}")
        run.jobs_found = total
        run.log = "\n".join(log_lines)
        run.finished_at = datetime.now(timezone.utc)
        error_msg, log_text = run.error, run.log
        try:
            db.commit()
        except Exception:  # noqa: BLE001
            # The import itself is over; only storing its result failed, and the rollback
            # discards the log and the error text along with everything else. Rewrite the
            # real outcome on the row that is already in the database, so the history never
            # keeps a run stuck at "running" with an empty log.
            log.exception("Could not store the import result for profile %s", profile_id)
            db.rollback()
            try:
                stored = db.get(AutomationRun, run.id)
                if stored is not None:
                    stored.status = "failed"
                    stored.error = error_msg or "The import finished but its result could not be stored."
                    stored.log = log_text
                    stored.jobs_found = total
                    stored.finished_at = datetime.now(timezone.utc)
                    db.commit()
                    run = stored
            except Exception:  # noqa: BLE001
                db.rollback()
        return run
    finally:
        with _profile_locks_guard:
            profile_lock.release()
            del _profile_locks[profile_id]


def _threshold_line(db, pref, profile_id: int = 1) -> str:
    """Report how many of the owner's stored jobs meet their minimum score."""
    from ..models import Job, UserProfile
    from .matching import compute_match

    profile = db.get(UserProfile, profile_id)
    if profile is None:
        return "Minimum match score not evaluated: no profile yet."
    hits = sum(
        1 for job in db.query(Job).filter(Job.profile_id == profile_id, Job.is_active.is_(True)).all()
        if compute_match(job, profile, use_ai=False)["score"] >= pref.min_match_score
    )
    return f"{hits} job{'' if hits == 1 else 's'} currently meet your minimum match score of {pref.min_match_score}."


def _scheduled_entrypoint(profile_id: int) -> None:
    from ..models import Account

    db = SessionLocal()
    try:
        if db.query(Account).filter(Account.profile_id == profile_id).first() is None:
            log.info("Skipping scheduled search for unclaimed profile %s", profile_id)
            return
        run_search_now(db, trigger="scheduled", profile_id=profile_id)
    except Exception:  # noqa: BLE001
        log.exception("Scheduled search crashed for profile %s", profile_id)
    finally:
        db.close()


def apply_settings(db, profile_id: int = 1) -> None:
    """Sync this owner's interval job; never schedule an unclaimed profile."""
    from ..models import Account

    pref = db.get(SearchPreference, profile_id)
    owner = db.query(Account).filter(Account.profile_id == profile_id).first()
    scheduler = get_scheduler()
    job_id = f"{JOB_ID}:{profile_id}"
    existing = scheduler.get_job(job_id)
    if owner is None or pref is None or not pref.enabled:
        if existing is not None:
            scheduler.remove_job(job_id)
        return
    if existing is None:
        scheduler.add_job(
            _scheduled_entrypoint,
            args=[profile_id],
            trigger=IntervalTrigger(minutes=pref.interval_minutes),
            id=job_id,
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        log.info("Scheduled search for profile %s (every %s minutes)", profile_id, pref.interval_minutes)
    else:
        trigger = existing.trigger
        if not isinstance(trigger, IntervalTrigger) or trigger.interval.total_seconds() / 60 != pref.interval_minutes:
            scheduler.reschedule_job(job_id, trigger=IntervalTrigger(minutes=pref.interval_minutes))


def start_scheduler(db) -> None:
    from ..models import Account

    scheduler = get_scheduler()
    profile_ids = {row[0] for row in db.query(Account.profile_id).distinct().all()}
    expected_ids = {f"{JOB_ID}:{profile_id}" for profile_id in profile_ids}
    for job in scheduler.get_jobs():
        if (job.id == JOB_ID or job.id.startswith(f"{JOB_ID}:")) and job.id not in expected_ids:
            scheduler.remove_job(job.id)
    for profile_id in sorted(profile_ids):
        apply_settings(db, profile_id=profile_id)
    if not scheduler.running:
        scheduler.start()


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        try:
            if _scheduler.running:
                _scheduler.shutdown(wait=False)
        except Exception:  # noqa: BLE001
            pass
        _scheduler = None
