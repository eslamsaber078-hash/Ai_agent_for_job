"""Freshness rules: a posting is only worth showing while the source still advertises it."""
from datetime import datetime, timedelta, timezone

from app.database import SessionLocal
from app.models import Job
from app.services.providers import (
    DEFAULT_JOB_MAX_AGE_DAYS,
    ProviderJob,
    hide_stale_jobs,
    ingest_jobs,
    is_dead,
    run_discovery,
)


def _days_ago(n: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=n)


def _add_job(db, external_id: str, posted, title: str | None = None, **kwargs) -> int:
    job = Job(
        external_id=external_id, source="remotive", title=title or f"Job {external_id}",
        company="Co", location="Cairo", posted_date=posted, is_active=True, **kwargs
    )
    db.add(job)
    db.commit()
    return job.id


def test_is_dead_classifies_expired_and_old_but_keeps_fresh():
    now = datetime.now(timezone.utc)
    fresh = ProviderJob(source="x", external_id="1", title="Fresh", posted_date=now - timedelta(days=3))
    assert is_dead(fresh, now, DEFAULT_JOB_MAX_AGE_DAYS) is None

    expired = ProviderJob(source="x", external_id="2", title="Expired",
                          posted_date=now - timedelta(days=2), expiry_date=now - timedelta(seconds=1))
    assert is_dead(expired, now, DEFAULT_JOB_MAX_AGE_DAYS) == "expired"

    ancient = ProviderJob(source="x", external_id="3", title="Ancient", posted_date=now - timedelta(days=120))
    assert is_dead(ancient, now, DEFAULT_JOB_MAX_AGE_DAYS) == "old"

    undated = ProviderJob(source="x", external_id="4", title="No date")
    assert is_dead(undated, now, DEFAULT_JOB_MAX_AGE_DAYS) is None  # no date is not proof of death


def test_naive_feed_dates_never_crash_the_freshness_check():
    """Remotive sends timestamps without an offset; comparing those to UTC raised."""
    now = datetime.now(timezone.utc)
    naive_recent = ProviderJob(source="x", external_id="5", title="Naive fresh",
                               posted_date=datetime.now() - timedelta(days=2))
    assert is_dead(naive_recent, now, DEFAULT_JOB_MAX_AGE_DAYS) is None

    naive_old = ProviderJob(source="x", external_id="6", title="Naive stale",
                            posted_date=datetime.now() - timedelta(days=200))
    assert is_dead(naive_old, now, DEFAULT_JOB_MAX_AGE_DAYS) == "old"

    naive_expiry = ProviderJob(source="x", external_id="7", title="Naive expired",
                               posted_date=datetime.now(), expiry_date=datetime.now() - timedelta(days=1))
    assert is_dead(naive_expiry, now, DEFAULT_JOB_MAX_AGE_DAYS) == "expired"


def test_remotive_parses_date_without_offset_as_utc():
    from app.services.providers import _parse_date

    parsed = _parse_date("2026-10-07T01:11:09")
    assert parsed is not None and parsed.tzinfo is not None


def test_discovery_skips_dead_postings_and_logs_it(client, monkeypatch):
    """Every posting the fake site sends is for the owner's own trade; only age separates them."""
    from app.services import providers as providers_mod

    class DeadProvider(providers_mod.BaseProvider):
        name = "deadprov"
        label = "Dead provider"

        def fetch(self, titles, skills, locations, remote_only):
            return [
                ProviderJob(source="deadprov", external_id="live-1", title="Live Junior Flutter Developer",
                            posted_date=datetime.now(timezone.utc)),
                ProviderJob(source="deadprov", external_id="old-1", title="Months Old Flutter Developer",
                            posted_date=_days_ago(90)),
                ProviderJob(source="deadprov", external_id="exp-1", title="Expired Flutter Developer",
                            posted_date=_days_ago(5), expiry_date=_days_ago(1)),
            ]

    monkeypatch.setitem(providers_mod.REGISTRY, "deadprov", DeadProvider)
    db = SessionLocal()
    try:
        providers_mod.ensure_sources(db)
        total, lines = run_discovery(db, ["Flutter Developer"], [], [], False, ["deadprov"])
        titles = {j.title for j in db.query(Job).filter(Job.source == "deadprov").all()}
    finally:
        db.close()

    assert total == 1
    assert "Live Junior Flutter Developer" in titles
    assert "Months Old Flutter Developer" not in titles
    assert "Expired Flutter Developer" not in titles
    assert any("skipped as no longer live" in line for line in lines)


def test_hide_stale_jobs_only_touches_dated_out_rows(client):
    db = SessionLocal()
    try:
        fresh = _add_job(db, "fresh-1", _days_ago(2))
        stale = _add_job(db, "stale-1", _days_ago(120))
        expired = _add_job(db, "expired-1", _days_ago(2), expiry_date=_days_ago(1))
        undated = _add_job(db, "undated-1", None)

        hidden = hide_stale_jobs(db, DEFAULT_JOB_MAX_AGE_DAYS)

        assert hidden == 2
        assert db.get(Job, stale).is_active is False
        assert db.get(Job, expired).is_active is False
        assert db.get(Job, fresh).is_active is True
        assert db.get(Job, undated).is_active is True
    finally:
        db.close()


def test_stale_jobs_leave_default_lists_but_are_still_reachable(client):
    db = SessionLocal()
    try:
        stale = _add_job(db, "stale-list", _days_ago(400), title="Ancient Posting Company")
        hide_stale_jobs(db, DEFAULT_JOB_MAX_AGE_DAYS)
    finally:
        db.close()

    default_titles = [j["title"] for j in client.get("/api/jobs", params={"page_size": 100}).json()["items"]]
    assert "Ancient Posting Company" not in default_titles

    with_stale = client.get("/api/jobs", params={"page_size": 100, "include_stale": True}).json()
    assert "Ancient Posting Company" in [j["title"] for j in with_stale["items"]]
    assert any(j["is_active"] is False for j in with_stale["items"])

    detail = client.get(f"/api/jobs/{stale}").json()
    assert detail["is_active"] is False  # saved jobs and history still resolve

    match_ids = [m["job"]["id"] for m in client.get("/api/matches", params={"limit": 200}).json()["items"]]
    assert stale not in match_ids

    stats = client.get("/api/dashboard/stats").json()
    assert stats["stale_hidden_jobs"] >= 1
    assert stale not in [j["id"] for j in stats["recent_jobs"]]


def test_refresh_reactivates_a_posting_the_source_still_lists(client):
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.external_id == "fixture-1").first()
        job.is_active = False
        db.commit()
        pj = ProviderJob(source="remotive", external_id=job.external_id, title=job.title,
                         company=job.company, posted_date=datetime.now(timezone.utc))
        ingest_jobs(db, [pj])
        db.refresh(job)
        assert job.is_active is True
    finally:
        db.close()


def test_age_cutoff_is_configurable(client):
    from app.models import SearchPreference

    db = SessionLocal()
    try:
        pref = db.query(SearchPreference).first() or SearchPreference(id=1)
        pref.max_age_days = 3
        db.add(pref)
        db.commit()
        hidden = hide_stale_jobs(db, pref.max_age_days)
        titles = {j.title for j in db.query(Job).filter(Job.is_active.is_(False)).all()}
        kept = {j.title for j in db.query(Job).filter(Job.is_active.is_(True)).all()}
    finally:
        db.close()
    assert hidden >= 3  # fixtures are dated one day apart, so the older ones age out
    assert "Backend Developer 1" in titles  # posted 15 days ago
    assert "Junior Flutter Developer" in kept  # posted yesterday


def test_feed_timestamps_parse_whichever_way_the_source_sends_them():
    """RemoteOK sends an ISO string, Arbeitnow an epoch integer — both must become real dates."""
    from app.services.providers import _parse_timestamp

    iso = _parse_timestamp("2026-10-09T08:00:04+00:00")
    assert iso is not None and iso.tzinfo is not None and iso.year == 2026

    epoch = _parse_timestamp(1765000000)
    assert epoch is not None and epoch.tzinfo is not None

    assert _parse_timestamp(None) is None
    assert _parse_timestamp("") is None
    assert _parse_timestamp("not a date") is None


def test_remoteok_rows_get_a_real_posted_date(monkeypatch):
    """An ISO date parsed as an epoch left every RemoteOK posting undated and immortal."""
    from app.services.providers import RemoteOKProvider, clear_fetch_cache

    clear_fetch_cache()
    payload = [
        {"server_time": 1760000000},
        {"id": 123, "position": "Flutter Developer", "company": "ACME",
         "url": "https://remoteok.com/remote-jobs/123", "date": "2026-10-09T08:00:04+00:00"},
    ]
    monkeypatch.setattr("app.services.providers._cached_get_json", lambda *a, **k: payload)

    jobs = RemoteOKProvider().fetch([], [], [], False)
    assert len(jobs) == 1
    assert jobs[0].posted_date is not None
    assert jobs[0].posted_date.tzinfo is not None
    assert jobs[0].posted_date.year == 2026


def test_an_undated_stored_posting_gets_dated_and_hidden(client, monkeypatch):
    """Rows stored before their date parsed would otherwise stay live forever."""
    from app.services import providers as providers_mod

    class OldFeedProvider(providers_mod.BaseProvider):
        name = "oldfeed"
        label = "Old feed"

        def fetch(self, titles, skills, locations, remote_only):
            return [ProviderJob(source="oldfeed", external_id="ad-1", title="Ancient Flutter Developer",
                                posted_date=_days_ago(120))]

    monkeypatch.setitem(providers_mod.REGISTRY, "oldfeed", OldFeedProvider)
    db = SessionLocal()
    try:
        providers_mod.ensure_sources(db)
        job = Job(external_id="ad-1", source="oldfeed", title="Ancient Flutter Developer", company="Co",
                  posted_date=None, is_active=True)
        db.add(job)
        db.commit()

        _, lines = run_discovery(db, ["Flutter Developer"], [], [], False, ["oldfeed"])
        db.refresh(job)
        assert job.posted_date is not None  # dated from the feed
        assert job.is_active is False  # and therefore out of the live lists
        assert any("dated so they age out" in line for line in lines)
    finally:
        db.close()


def test_a_feed_that_sends_no_dates_still_ages_out(client, monkeypatch):
    """An ad with no posting date is shown only while its source keeps advertising it.

    Inventing a date for it made 929 months-old postings look hours fresh; the honest
    anchor is the last time the board itself listed the ad.
    """
    from app.services import providers as providers_mod

    class BlindProvider(providers_mod.BaseProvider):
        name = "blindfeed"
        label = "Blind feed"

        def fetch(self, titles, skills, locations, remote_only):
            return [ProviderJob(source="blindfeed", external_id="b-1", title="Undated Flutter Developer",
                                company="Co", url="http://b/1")]

    monkeypatch.setitem(providers_mod.REGISTRY, "blindfeed", BlindProvider)
    db = SessionLocal()
    try:
        providers_mod.ensure_sources(db)
        run_discovery(db, ["Flutter Developer"], [], [], False, ["blindfeed"], max_age_days=30)
        job = db.query(Job).filter(Job.source == "blindfeed").one()
        assert job.posted_date is None  # nothing was invented
        assert job.date_kind == "unknown"
        assert job.is_active is True  # the board listed it during this run

        job.last_seen = _days_ago(45)  # the board stopped repeating it
        db.commit()
        run_discovery(db, ["Flutter Developer"], [], [], False, ["other"], max_age_days=30)
        db.refresh(job)
        assert job.is_active is False
    finally:
        db.close()
