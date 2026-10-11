"""APScheduler integration.

A single BackgroundScheduler is shared across the app. The scheduled job
reads the stored SearchPreference and runs the discovery pipeline. Manual
triggers reuse the same job function synchronously.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from ..config import DATABASE_URL
from ..database import SessionLocal
from ..models import AutomationRun, SearchPreference
from .providers import run_discovery

log = logging.getLogger("jobhunter.scheduler")

_scheduler: BackgroundScheduler | None = None
JOB_ID = "scheduled_search"


def get_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler(timezone="UTC")
    return _scheduler


def run_search_now(db, trigger: str = "manual", sources: list[str] | None = None) -> AutomationRun:
    """Run one discovery pass now. Used by both manual calls and the scheduler."""
    pref = db.query(SearchPreference).first()
    if pref is None:
        # A manual import must still work on a database that has no settings row yet.
        pref = SearchPreference(id=1)
        db.add(pref)
        db.commit()
    run = AutomationRun(trigger=trigger, status="running", sources_used=sources or [])
    db.add(run)
    db.commit()
    log_lines: list[str] = []
    total = 0
    try:
        if pref and (trigger == "manual" or pref.enabled):
            total, log_lines = run_discovery(
                db, pref.titles, pref.skills, pref.locations, pref.remote_only,
                sources or pref.sources or None,
                max_age_days=pref.max_age_days,
            )
            log_lines.append(_threshold_line(db, pref))
        else:
            log_lines.append("Scheduled search is disabled. Enable it in Automation Settings.")
        run.status = "success"
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        log.exception("Search run failed")
        run.status = "failed"
        run.error = f"{type(exc).__name__}: {exc}"
        log_lines.append(f"ERROR: {exc}")
    run.jobs_found = total
    run.log = "\n".join(log_lines)
    run.finished_at = datetime.now(timezone.utc)
    try:
        db.commit()
    except Exception:  # noqa: BLE001 - never leave the run row stuck in "running"
        db.rollback()
        db.merge(run)
        run.status = "failed"
        db.commit()
    return run


def _threshold_line(db, pref) -> str:
    """Report how many stored jobs meet the user's minimum match score."""
    from ..models import Job, UserProfile
    from .matching import compute_match

    profile = db.get(UserProfile, 1)
    if profile is None:
        return "Minimum match score not evaluated: no profile yet."
    hits = sum(
        1 for job in db.query(Job).filter(Job.is_active.is_(True)).all()
        if compute_match(job, profile, use_ai=False)["score"] >= pref.min_match_score
    )
    return f"{hits} job(s) currently meet your minimum match score of {pref.min_match_score}."


def _scheduled_entrypoint() -> None:
    db = SessionLocal()
    try:
        run_search_now(db, trigger="scheduled")
    except Exception:  # noqa: BLE001
        log.exception("Scheduled search crashed")
    finally:
        db.close()


def apply_settings(db) -> None:
    """Sync the scheduler job with stored search preferences."""
    pref = db.query(SearchPreference).first()
    if pref is None:
        pref = SearchPreference(id=1)
        db.add(pref)
        db.commit()
    scheduler = get_scheduler()
    existing = scheduler.get_job(JOB_ID)
    if pref.enabled and existing is None:
        scheduler.add_job(
            _scheduled_entrypoint,
            trigger=IntervalTrigger(minutes=pref.interval_minutes),
            id=JOB_ID,
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        log.info("Scheduled search started (every %s minutes)", pref.interval_minutes)
    elif pref.enabled and existing is not None:
        trigger = existing.trigger
        if not isinstance(trigger, IntervalTrigger) or trigger.interval.total_seconds() / 60 != pref.interval_minutes:
            scheduler.reschedule_job(JOB_ID, trigger=IntervalTrigger(minutes=pref.interval_minutes))
    elif not pref.enabled and existing is not None:
        scheduler.remove_job(JOB_ID)
        log.info("Scheduled search stopped")


def start_scheduler(db) -> None:
    if DATABASE_URL.startswith("sqlite"):
        pass  # no extra setup needed
    scheduler = get_scheduler()
    if not scheduler.running:
        scheduler.start()
    apply_settings(db)


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        try:
            if _scheduler.running:
                _scheduler.shutdown(wait=False)
        except Exception:  # noqa: BLE001
            pass
        _scheduler = None
