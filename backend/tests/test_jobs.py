from datetime import datetime, timedelta, timezone

from app.database import SessionLocal
from app.models import Job
from app.services.providers import ProviderJob, RemotiveProvider
from fixture_jobs import FIXTURE_JOBS


def test_fixture_jobs_populated(client):
    r = client.get("/api/jobs", params={"page_size": 100})
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 20
    assert all(not j["is_demo"] for j in data["items"])


def test_dedup_same_external_id():
    db = SessionLocal()
    try:
        pj = ProviderJob(source="test", external_id="abc-1", title="Tester", company="ACME")
        from app.services.providers import ingest_jobs
        new1, _ = ingest_jobs(db, [pj])
        new2, updated = ingest_jobs(db, [pj])
        assert new1 == 1
        assert new2 == 0
        assert updated == 1
        count = db.query(Job).filter(Job.source == "test").count()
        assert count == 1
    finally:
        db.close()


def test_dedup_across_sources_by_normalized_key():
    db = SessionLocal()
    try:
        from app.services.providers import ingest_jobs
        a = ProviderJob(source="src-a", external_id="1", title="Flutter Dev", company="NileSoft", url="http://x.com/j")
        b = ProviderJob(source="src-b", external_id="99", title="flutter dev", company="nilesoft", url="http://x.com/j")
        new1, _ = ingest_jobs(db, [a])
        new2, _ = ingest_jobs(db, [b])
        assert new1 == 1
        assert new2 == 0
        assert db.query(Job).count() == len(FIXTURE_JOBS) + 1  # fixture jobs + 1
    finally:
        db.close()


def test_job_filtering_and_pagination(client):
    r = client.get("/api/jobs", params={"skill": "flutter", "page_size": 100})
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) > 5
    assert all(any("flutter" in (s or "").lower() for s in j["skills"]) or "flutter" in j["description"].lower()
               for j in items)

    r = client.get("/api/jobs", params={"page": 2, "page_size": 10})
    data = r.json()
    assert data["page"] == 2
    assert len(data["items"]) == 10
    assert data["pages"] >= 2

    r = client.get("/api/jobs", params={"level": "Intern", "page_size": 100})
    assert all(j["experience_level"] == "Intern" for j in r.json()["items"])

    r = client.get("/api/jobs", params={"remote": "true", "page_size": 100})
    assert all(j["remote"] for j in r.json()["items"])

    r = client.get("/api/jobs", params={"q": "NileSoft"})
    assert all("nilesoft" in j["company"].lower() for j in r.json()["items"])


def test_job_404(client):
    r = client.get("/api/jobs/999999")
    assert r.status_code == 404


def test_save_and_unsave(client):
    r = client.post("/api/jobs/1/save", params={"notes": "looks good"})
    assert r.status_code == 200
    assert r.json()["saved"] is True
    r = client.get("/api/saved-jobs")
    assert len(r.json()) == 1
    assert r.json()[0]["job"]["id"] == 1
    r = client.delete("/api/jobs/1/save")
    assert r.json()["saved"] is False
    assert client.get("/api/saved-jobs").json() == []


def test_a_paged_list_shows_every_posting_once_in_the_same_order(client):
    """The newest-first list is now ordered by SQL, so the tiebreaker has to be real.

    Two pages that disagree on where equal rows go would show him the same posting
    twice and hide another one — the classic paging bug.
    """
    for sort in ("date", "title", "company"):
        pages: list[int] = []
        page = 1
        while True:
            body = client.get("/api/jobs", params={"sort": sort, "page": page, "page_size": 7}).json()
            pages.extend(j["id"] for j in body["items"])
            if page >= body["pages"]:
                break
            page += 1
        assert len(pages) == len(set(pages)), sort
        whole = [j["id"] for j in client.get("/api/jobs", params={"sort": sort, "page_size": 100}).json()["items"]]
        assert pages == whole, sort


def _owner_describes_their_trade(client, titles: list[str]) -> None:
    """Every import now searches and keeps only what matches the owner's own wording."""
    assert client.put("/api/profile", json={"desired_titles": titles}).status_code == 200


def test_refresh_endpoint(client):
    _owner_describes_their_trade(client, ["Flutter Developer"])
    r = client.post("/api/jobs/refresh", json=["remotive"])
    assert r.status_code == 200
    body = r.json()
    assert "jobs_new" in body
    assert any("Remotive" in line for line in body["log"])


def test_a_site_that_was_fetched_but_kept_nothing_is_not_called_unimported(client, monkeypatch):
    """A button that reads "Never imported" right after its own import ran looks broken.

    The run history is what tells a fetched-but-gated site apart from one never touched,
    and a key-gated site without its key is neither — it never ran at all.
    """
    from app import config

    monkeypatch.setattr(config, "RAPIDAPI_KEY", "", raising=False)
    _owner_describes_their_trade(client, ["Flutter Developer"])
    before = {s["name"]: s for s in client.get("/api/jobs/sources").json()}
    assert before["weworkremotely"]["fetched_at"] is None
    assert before["jsearch"]["key_ready"] is False  # no key: the site cannot have run
    assert before["remotive"]["key_ready"] is True  # keyless sites are always ready

    client.post("/api/jobs/refresh", json=["weworkremotely"])

    after = {s["name"]: s for s in client.get("/api/jobs/sources").json()}
    assert after["weworkremotely"]["fetched_at"] is not None
    assert after["jsearch"]["fetched_at"] is None  # the other site was not part of that run


def test_remotive_provider_handles_api_failure(monkeypatch):
    def boom(*args, **kwargs):
        raise ConnectionError("no internet")

    import app.services.providers as providers_mod
    monkeypatch.setattr(providers_mod.httpx, "get", boom)
    p = RemotiveProvider()
    assert p.fetch([], [], [], False) == []


def test_remotive_provider_parses_response(monkeypatch):
    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"jobs": [{
                "id": 123, "title": "Remote Python Dev", "company_name": "ACME",
                "candidate_required_location": "Worldwide", "job_type": "full_time",
                "description": "Build APIs", "url": "http://x.com", "publication_date": "2026-01-01T00:00:00Z",
            }]}

    def fake_get(*args, **kwargs):
        return FakeResp()

    import app.services.providers as providers_mod
    monkeypatch.setattr(providers_mod.httpx, "get", fake_get)
    jobs = RemotiveProvider().fetch(["Python"], [], [], False)
    assert len(jobs) == 1
    assert jobs[0].external_id == "123"
    assert jobs[0].remote is True
    assert jobs[0].posted_date is not None


def test_remoteok_provider_parses_and_skips_legal_notice(monkeypatch):
    from app.services.providers import RemoteOKProvider, clear_fetch_cache
    clear_fetch_cache()

    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return [
                {"legal": "notice"},
                {"id": 9, "position": "Flutter Dev", "company": "ACME", "location": "Worldwide",
                 "salary_min": 50000, "salary_max": 70000, "job_type": "full_time",
                 "description": "Build apps", "url": "http://x.com/9", "tags": ["flutter"],
                 "date": 1765000000},
            ]

    import app.services.providers as providers_mod
    monkeypatch.setattr(providers_mod.httpx, "get", lambda *a, **k: FakeResp())
    jobs = RemoteOKProvider().fetch([], [], [], False)
    assert len(jobs) == 1
    assert jobs[0].external_id == "9"
    assert jobs[0].remote is True
    assert jobs[0].salary_min == 50000
    assert jobs[0].posted_date is not None


def test_jobicy_provider_parses_response(monkeypatch):
    from app.services.providers import JobicyProvider, clear_fetch_cache
    clear_fetch_cache()

    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"jobs": [{
                "id": 77, "jobTitle": "Junior Python Dev", "companyName": "Beta",
                "jobGeo": "Anywhere", "jobType": ["Full-Time"], "jobLevel": "Junior Level",
                "jobExcerpt": "APIs", "jobDescription": "Build APIs", "url": "http://y.com",
                "pubDate": "2026-01-02T00:00:00Z", "annualSalaryMin": 30000,
                "annualSalaryMax": 40000, "salaryCurrency": "USD",
            }]}

    import app.services.providers as providers_mod
    monkeypatch.setattr(providers_mod.httpx, "get", lambda *a, **k: FakeResp())
    jobs = JobicyProvider().fetch([], [], [], False)
    assert len(jobs) == 1
    assert jobs[0].external_id == "77"
    assert jobs[0].experience_level == "Junior Level"
    assert jobs[0].employment_type == "Full-Time"
    assert jobs[0].salary_currency == "USD"


def test_arbeitnow_provider_parses_response(monkeypatch):
    from app.services.providers import ArbeitnowProvider, clear_fetch_cache
    clear_fetch_cache()

    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"data": [{
                "slug": "job-1", "title": "Remote Flutter Engineer", "company_name": "Gamma",
                "remote": True, "job_types": ["full_time"], "location": "Berlin",
                "url": "http://z.com", "tags": ["flutter"], "created_at": 1765000000,
            }]}

    import app.services.providers as providers_mod
    monkeypatch.setattr(providers_mod.httpx, "get", lambda *a, **k: FakeResp())
    jobs = ArbeitnowProvider().fetch([], [], [], False)
    assert len(jobs) == 1
    assert jobs[0].external_id == "job-1"
    assert jobs[0].remote is True
    assert jobs[0].posted_date is not None


def test_new_providers_handle_api_failure(monkeypatch):
    from app.services.providers import ArbeitnowProvider, JobicyProvider, RemoteOKProvider, clear_fetch_cache
    clear_fetch_cache()

    def boom(*args, **kwargs):
        raise ConnectionError("no internet")

    import app.services.providers as providers_mod
    monkeypatch.setattr(providers_mod.httpx, "get", boom)
    assert RemoteOKProvider().fetch([], [], [], False) == []
    assert JobicyProvider().fetch([], [], [], False) == []
    assert ArbeitnowProvider().fetch([], [], [], False) == []


def test_provider_fetch_cache_prevents_hammering(monkeypatch):
    """Repeated fetches inside the TTL window must hit the API only once."""
    from app.services.providers import JobicyProvider, clear_fetch_cache
    clear_fetch_cache()
    calls = {"n": 0}

    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"jobs": []}

    def fake_get(*args, **kwargs):
        calls["n"] += 1
        return FakeResp()

    import app.services.providers as providers_mod
    monkeypatch.setattr(providers_mod.httpx, "get", fake_get)
    p = JobicyProvider()
    assert p.fetch([], [], [], False) == []
    assert p.fetch([], [], [], False) == []
    assert p.fetch([], [], [], False) == []
    assert calls["n"] == 1
    clear_fetch_cache()


def test_ingest_updates_existing_job():
    db = SessionLocal()
    try:
        from app.services.providers import ingest_jobs
        pj = ProviderJob(source="test", external_id="x1", title="Old Title", company="ACME", salary_min=100)
        ingest_jobs(db, [pj])
        pj2 = ProviderJob(source="test", external_id="x1", title="New Title", company="ACME", salary_min=200)
        _, updated = ingest_jobs(db, [pj2])
        assert updated == 1
        job = db.query(Job).filter(Job.source == "test").one()
        assert job.title == "New Title"
        assert job.salary_min == 200
    finally:
        db.close()


def test_republished_post_with_a_new_board_id_is_not_stored_twice():
    """Arbeitnow re-advertises the same opening under a fresh URL id each run."""
    db = SessionLocal()
    try:
        from app.services.providers import ingest_jobs

        base = dict(source="test", title="Senior Rust Engineer", company="Rustworks")
        first = ProviderJob(external_id="a1", url="https://rustworks.example/jobs/senior-rust-engineer-london-262635", **base)
        again = ProviderJob(external_id="a2", url="https://rustworks.example/jobs/senior-rust-engineer-london-146596", **base)
        assert ingest_jobs(db, [first]) == (1, 0)
        assert ingest_jobs(db, [again]) == (0, 0)
        assert db.query(Job).filter(Job.company == "Rustworks").count() == 1

        numeric = ProviderJob(external_id="n9", url="https://other.example/job/1234", **base)
        other = ProviderJob(external_id="n8", url="https://other.example/job/5678", **base)
        assert ingest_jobs(db, [numeric, other]) == (2, 0)  # ids, not slugs: separate ads
    finally:
        db.close()


def test_an_undated_feed_leaves_the_date_empty_instead_of_inventing_one():
    """Himalayas sends a date that is generated when the feed is built; storing "today"
    for every one of its ads made 929 jobs look hours old."""
    db = SessionLocal()
    try:
        from app.services.providers import ingest_jobs
        pj = ProviderJob(source="himalayas", external_id="h1", title="Flutter Dev", company="ACME")
        assert ingest_jobs(db, [pj]) == (1, 0)
        job = db.query(Job).filter(Job.external_id == "h1").one()
        assert job.posted_date is None
        assert job.date_kind == "unknown"
    finally:
        db.close()


def test_a_board_that_re_stamps_an_ad_never_makes_it_younger():
    db = SessionLocal()
    try:
        from app.services.providers import hide_stale_jobs, ingest_jobs
        old = datetime.now(timezone.utc) - timedelta(days=90)
        first = ProviderJob(source="test", external_id="s1", title="PHP Dev", company="ACME",
                            posted_date=old)
        ingest_jobs(db, [first])
        re_stamped = ProviderJob(source="test", external_id="s1", title="PHP Dev", company="ACME",
                                 posted_date=datetime.now(timezone.utc))
        ingest_jobs(db, [re_stamped])
        job = db.query(Job).filter(Job.external_id == "s1").one()
        assert job.posted_date.date() == old.date()
        assert hide_stale_jobs(db, 30) == 1
    finally:
        db.close()


def test_a_date_that_arrives_later_is_still_used():
    """An ad stored before the relative-date parser existed gets its real age on the next run."""
    db = SessionLocal()
    try:
        from app.services.providers import ingest_jobs
        ingest_jobs(db, [ProviderJob(source="jsearch", external_id="j1", title="QA Dev", company="ACME")])
        real = datetime.now(timezone.utc) - timedelta(days=40)
        ingest_jobs(db, [ProviderJob(source="jsearch", external_id="j1", title="QA Dev",
                                     company="ACME", posted_date=real)])
        job = db.query(Job).filter(Job.external_id == "j1").one()
        assert job.posted_date.date() == real.date()
    finally:
        db.close()


def test_an_undated_ad_only_ages_out_when_its_source_stops_listing_it():
    db = SessionLocal()
    try:
        from app.services.providers import hide_stale_jobs, ingest_jobs
        now = datetime.now(timezone.utc)
        for ext, seen in (("fresh", now), ("abandoned", now - timedelta(days=45))):
            ingest_jobs(db, [ProviderJob(source="himalayas", external_id=ext,
                                         title=f"{ext} dev", company="ACME")])
        db.query(Job).filter(Job.external_id == "abandoned").update(
            {Job.last_seen: now - timedelta(days=45)}, synchronize_session=False)
        db.commit()
        assert hide_stale_jobs(db, 30) == 1
        assert db.query(Job).filter(Job.external_id == "fresh", Job.is_active.is_(True)).count() == 1
    finally:
        db.close()


def test_feed_words_that_only_say_when_are_turned_into_a_real_date():
    from app.services.providers import _relative_to_date

    now = datetime.now(timezone.utc)
    for text, days in (("قبل ١١ يومًا", 11), ("منذ 3 أيام", 3), ("11 days ago", 11),
                       ("3 weeks ago", 21), ("2 months ago", 60)):
        parsed = _relative_to_date(text)
        assert parsed is not None, text
        assert abs((now - parsed).total_seconds() - days * 86400) < 3600, text
    assert (_relative_to_date("Today") - now).total_seconds() < 60
    assert _relative_to_date("just posted") is not None
    assert _relative_to_date("") is None
    assert _relative_to_date("soon") is None


def test_a_crawl_stamped_source_is_labelled_as_listing_not_posting():
    db = SessionLocal()
    try:
        from app.services.providers import ingest_jobs
        ingest_jobs(db, [ProviderJob(source="arbeitnow", external_id="a1", title="Go Dev",
                                     company="ACME", posted_date=datetime.now(timezone.utc))])
        assert db.query(Job).filter(Job.external_id == "a1").one().date_kind == "listed"
    finally:
        db.close()


WWR_RSS_SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <title>We Work Remotely</title>
  <item>
    <title>Pixel Forge: Junior Flutter Developer</title>
    <link>https://weworkremotely.com/remote-jobs/pixel-forge-junior-flutter-developer</link>
    <guid>https://weworkremotely.com/remote-jobs/pixel-forge-junior-flutter-developer</guid>
    <category>Programming</category>
    <country>Egypt</country>
    <region>Africa</region>
    <skills>Flutter, Dart, Firebase</skills>
    <type>Full-Time</type>
    <pubDate>Fri, 09 Oct 2026 17:46:45 +0000</pubDate>
    <expires_at>Wed, 09 Dec 2026 17:46:45 +0000</expires_at>
    <description>&lt;p&gt;Build &amp; ship Flutter apps for a &lt;b&gt;growing&lt;/b&gt; team.&lt;/p&gt;</description>
  </item>
</channel></rss>"""


def test_weworkremotely_parses_feed_including_expiry(monkeypatch):
    from app.services.providers import WeWorkRemotelyProvider, clear_fetch_cache
    clear_fetch_cache()

    class FakeResp:
        text = WWR_RSS_SAMPLE

        def raise_for_status(self):
            pass

        def json(self):
            return {}

    import app.services.providers as providers_mod
    monkeypatch.setattr(providers_mod.httpx, "get", lambda *a, **k: FakeResp())
    jobs = WeWorkRemotelyProvider().fetch([], [], [], False)
    assert len(jobs) == 1
    job = jobs[0]
    assert job.company == "Pixel Forge"
    assert job.title == "Junior Flutter Developer"
    assert job.external_id.endswith("junior-flutter-developer")
    assert "Egypt" in job.location
    assert job.skills == ["Flutter", "Dart", "Firebase"]
    assert job.employment_type == "Full-Time"
    assert job.posted_date is not None and job.posted_date.year == 2026
    assert job.expiry_date is not None and job.expiry_date > job.posted_date
    assert "&" in job.description and "<" not in job.description


def test_weworkremotely_survives_unparsable_feed(monkeypatch):
    from app.services.providers import WeWorkRemotelyProvider, clear_fetch_cache
    clear_fetch_cache()

    class FakeResp:
        text = "<rss><not closed"

        def raise_for_status(self):
            pass

        def json(self):
            return {}

    import app.services.providers as providers_mod
    monkeypatch.setattr(providers_mod.httpx, "get", lambda *a, **k: FakeResp())
    assert WeWorkRemotelyProvider().fetch([], [], [], False) == []


def test_weworkremotely_handles_api_failure(monkeypatch):
    from app.services.providers import WeWorkRemotelyProvider, clear_fetch_cache
    clear_fetch_cache()

    def boom(*args, **kwargs):
        raise ConnectionError("no internet")

    import app.services.providers as providers_mod
    monkeypatch.setattr(providers_mod.httpx, "get", boom)
    assert WeWorkRemotelyProvider().fetch([], [], [], False) == []


def test_arbeitnow_walks_pagination_until_the_feed_runs_out(monkeypatch):
    from app.services.providers import ArbeitnowProvider, clear_fetch_cache
    clear_fetch_cache()

    pages = {
        "1": {"data": [{"slug": f"p1-{i}", "title": f"Job P1 {i}", "company_name": "A",
                        "url": f"http://a/{i}", "created_at": 1765000000} for i in range(3)],
              "links": {"next": "https://www.arbeitnow.com/api/job-board-api?page=2"}},
        "2": {"data": [{"slug": f"p2-{i}", "title": f"Job P2 {i}", "company_name": "B",
                        "url": f"http://b/{i}", "created_at": 1765000000} for i in range(2)],
              "links": {"next": None}},
    }
    seen = []

    class FakeResp:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            pass

        def json(self):
            return self._payload

    def fake_get(url, params=None, **kwargs):
        page = str((params or {}).get("page", "1"))
        seen.append(page)
        return FakeResp(pages[page])

    import app.services.providers as providers_mod
    monkeypatch.setattr(providers_mod.httpx, "get", fake_get)
    jobs = ArbeitnowProvider().fetch([], [], [], False)
    assert [j.external_id for j in jobs] == ["p1-0", "p1-1", "p1-2", "p2-0", "p2-1"]
    assert seen == ["1", "2"]
    clear_fetch_cache()


def test_arbeitnow_stops_at_the_cap(monkeypatch):
    from app.services.providers import ArbeitnowProvider, clear_fetch_cache
    clear_fetch_cache()

    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"data": [{"slug": f"big-{i}", "title": f"Job {i}", "company_name": "A",
                              "url": f"http://a/{i}", "created_at": 1765000000} for i in range(400)],
                    "links": {"next": "https://www.arbeitnow.com/api/job-board-api?page=2"}}

    import app.services.providers as providers_mod
    monkeypatch.setattr(providers_mod.httpx, "get", lambda *a, **k: FakeResp())
    jobs = ArbeitnowProvider().fetch([], [], [], False)
    assert len(jobs) == ArbeitnowProvider.MAX_JOBS
    clear_fetch_cache()


def test_sources_endpoint_lists_every_registered_site_with_live_counts(client):
    r = client.get("/api/jobs/sources")
    assert r.status_code == 200
    sources = {s["name"]: s for s in r.json()}
    from app.services import REGISTRY
    assert set(sources) == set(REGISTRY)
    assert sources["remotive"]["live_jobs"] >= 20  # the fixture jobs
    assert sources["weworkremotely"]["live_jobs"] == 0  # listed before its first import
    assert all(s["requires_key"] is False for s in sources.values()
               if s["name"] not in {"jsearch", "jooble", "adzuna"})
    assert sources["jsearch"]["requires_key"] is True
    assert sources["jooble"]["requires_key"] is True  # silent until its free key is set
    assert sources["adzuna"]["requires_key"] is True  # silent until its free key pair is set


def test_refresh_searches_with_the_saved_preferences(client, monkeypatch):
    from app.services import providers as providers_mod

    calls = []

    class SpyProvider(providers_mod.BaseProvider):
        name = "spy"
        label = "Spy provider"

        def fetch(self, titles, skills, locations, remote_only):
            calls.append((titles, skills, locations, remote_only))
            return []

    monkeypatch.setitem(providers_mod.REGISTRY, "spy", SpyProvider)
    client.put("/api/automation/settings", json=dict(
        enabled=False, titles=["Flutter Developer"], skills=["Flutter"],
        locations=["Cairo"], remote_only=True, interval_minutes=60,
        min_match_score=50, sources=["spy"], max_age_days=45,
    ))
    db = SessionLocal()
    try:
        providers_mod.ensure_sources(db)
    finally:
        db.close()

    r = client.post("/api/jobs/refresh", json=["spy"])
    assert r.status_code == 200
    assert calls == [(["Flutter Developer"], ["Flutter"], ["Cairo"], True)]


def test_per_site_import_fetches_only_that_site(client, monkeypatch):
    from app.services import providers as providers_mod

    fetched = []

    def make(name):
        class Only(providers_mod.BaseProvider):
            label = f"{name} provider"

            def fetch(self, titles, skills, locations, remote_only):
                fetched.append(name)
                return [ProviderJob(source=name, external_id=f"{name}-1",
                                    title=f"{name} Flutter Developer", posted_date=datetime.now(timezone.utc))]
        Only.name = name
        return Only

    for name in ("sitea", "siteb"):
        monkeypatch.setitem(providers_mod.REGISTRY, name, make(name))
    db = SessionLocal()
    try:
        providers_mod.ensure_sources(db)
    finally:
        db.close()

    _owner_describes_their_trade(client, ["Flutter Developer"])
    r = client.post("/api/jobs/refresh", json=["sitea"])
    assert r.status_code == 200
    assert fetched == ["sitea"]
    assert r.json()["sources_used"] == ["sitea"]
    titles = [j["title"] for j in client.get("/api/jobs", params={"page_size": 100}).json()["items"]]
    assert any(t.startswith("sitea") for t in titles)
    assert not any(t.startswith("siteb") for t in titles)


def test_arbeitnow_keeps_the_real_description(monkeypatch):
    """The feed's own text is what the matcher scores against — it must survive ingest."""
    from app.services.providers import ArbeitnowProvider, clear_fetch_cache
    clear_fetch_cache()

    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"data": [{
                "slug": "d-1", "title": "Flutter Engineer", "company_name": "ACME",
                "url": "http://a/1", "created_at": 1765000000,
                "description": "<p>We use <b>Flutter</b> &amp; Dart daily</p>",
            }], "links": {}}

    import app.services.providers as providers_mod
    monkeypatch.setattr(providers_mod.httpx, "get", lambda *a, **k: FakeResp())
    jobs = ArbeitnowProvider().fetch([], [], [], False)
    assert "Flutter" in jobs[0].description
    assert "Dart" in jobs[0].description
    assert "<" not in jobs[0].description


def test_jobicy_asks_the_api_for_its_whole_cap(monkeypatch):
    from app.services.providers import JobicyProvider, clear_fetch_cache
    clear_fetch_cache()
    seen = {}

    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"jobs": []}

    import app.services.providers as providers_mod

    def fake_get(url, params=None, **kwargs):
        seen.update(params or {})
        return FakeResp()

    monkeypatch.setattr(providers_mod.httpx, "get", fake_get)
    JobicyProvider().fetch([], [], [], False)
    assert int(seen["count"]) == JobicyProvider.MAX_JOBS
    clear_fetch_cache()


def test_refresh_without_a_site_name_uses_the_ticked_ones(client, monkeypatch):
    from app.services import providers as providers_mod
    from app.services.providers import clear_fetch_cache

    class SpyProvider(providers_mod.BaseProvider):
        name = "tickme"
        label = "Tick me"

        def fetch(self, titles, skills, locations, remote_only):
            clear_fetch_cache()
            return []

    monkeypatch.setitem(providers_mod.REGISTRY, "tickme", SpyProvider)
    client.put("/api/automation/settings", json=dict(
        enabled=False, titles=["Flutter Developer"], skills=["Flutter"],
        locations=["Cairo"], remote_only=False, interval_minutes=60,
        min_match_score=50, sources=["tickme"], max_age_days=30,
    ))
    db = SessionLocal()
    try:
        providers_mod.ensure_sources(db)
    finally:
        db.close()

    r = client.post("/api/jobs/refresh", json=[])
    assert r.status_code == 200
    assert r.json()["sources_used"] == ["tickme"]


def test_refresh_records_sources_in_import_order_not_saved_order(client, monkeypatch):
    """The import runs LinkedIn first, then the Egypt index, then the rest; the
    recorded sources_used must match even when the stored preference predates
    that order."""
    from app.services import providers as providers_mod
    from app.services.providers import clear_fetch_cache

    class SpyA(providers_mod.BaseProvider):
        name = "spy_a"
        label = "Spy A"

        def fetch(self, titles, skills, locations, remote_only):
            clear_fetch_cache()
            return []

    class SpyB(providers_mod.BaseProvider):
        name = "spy_b"
        label = "Spy B"

        def fetch(self, titles, skills, locations, remote_only):
            clear_fetch_cache()
            return []

    monkeypatch.setitem(providers_mod.REGISTRY, "spy_a", SpyA)
    monkeypatch.setitem(providers_mod.REGISTRY, "spy_b", SpyB)
    # Saved scrambled (old order); the run must still report registry order.
    client.put("/api/automation/settings", json=dict(
        enabled=False, titles=["Flutter Developer"], skills=["Flutter"],
        locations=["Cairo"], remote_only=False, interval_minutes=60,
        min_match_score=50, sources=["spy_b", "spy_a"], max_age_days=30,
    ))
    db = SessionLocal()
    try:
        providers_mod.ensure_sources(db)
    finally:
        db.close()

    r = client.post("/api/jobs/refresh", json=[])
    assert r.status_code == 200
    assert r.json()["sources_used"] == ["spy_a", "spy_b"]


def test_himalayas_ignores_the_dates_its_feed_invents(monkeypatch):
    """Himalayas is keyless and real, but its pubDate is generated at feed build time."""
    from app.services.providers import HimalayasProvider, clear_fetch_cache
    clear_fetch_cache()

    payload = {"jobs": [{
        "title": "Junior Flutter Developer", "companyName": "Pixel Forge",
        "pubDate": 1791621041, "expiryDate": 1796805040,
        "applicationLink": "https://himalayas.app/companies/pixel-forge/jobs/jr-flutter",
        "guid": "https://himalayas.app/companies/pixel-forge/jobs/jr-flutter",
        "employmentType": "Full Time", "seniority": ["Junior"], "currency": "USD",
        "minSalary": 40000, "maxSalary": 60000, "locationRestrictions": ["Egypt", "EMEA"],
        "categories": ["Flutter", "Mobile-Job"], "description": "<p>Build <b>Dart</b> apps &amp; ship daily</p>",
    }] * 20}

    seen: list[dict] = []

    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return payload

    import app.services.providers as providers_mod

    def fake_get(url, params=None, **kwargs):
        seen.append(params or {})
        return FakeResp()

    monkeypatch.setattr(providers_mod.httpx, "get", fake_get)
    jobs = HimalayasProvider().fetch([], [], [], False)

    assert jobs, "the feed must produce postings"
    job = jobs[0]
    assert job.title == "Junior Flutter Developer"
    assert job.company == "Pixel Forge"
    assert job.remote is True
    assert "Egypt" in job.location
    assert job.experience_level == "Junior"
    # their categories arrive as url-slugs; a chip reading "Mobile-Job" is not how
    # every other source spells a skill, and the matcher compares plain words
    assert job.skills == ["Flutter", "Mobile Job"]
    assert job.salary_min == 40000 and job.salary_currency == "USD"
    assert job.posted_date is None and job.expiry_date is None
    assert "Dart" in job.description and "<" not in job.description
    # the paging walks offsets, it does not re-request page one forever
    assert [p.get("offset") for p in seen] == ["0", "20", "40", "60", "80"][: len(seen)]
    clear_fetch_cache()


def test_working_nomads_parses_feed_and_id(monkeypatch):
    from app.services.providers import WorkingNomadsProvider, clear_fetch_cache
    clear_fetch_cache()

    payload = [{
        "title": "Flutter Developer", "company_name": "Remote Co",
        "location": "Time zone: CET (+/- 3 hours)",
        "url": "https://www.workingnomads.com/job/go/1925654/",
        "pub_date": "2026-10-08T12:54:14-04:00",
        "category_name": "Development", "tags": "flutter,dart,mobile",
        "description": "&lt;h3&gt;We use &lt;b&gt;Flutter&lt;/b&gt; daily&lt;/h3&gt;",
    }]

    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return payload

    import app.services.providers as providers_mod
    monkeypatch.setattr(providers_mod.httpx, "get", lambda *a, **k: FakeResp())

    jobs = WorkingNomadsProvider().fetch([], [], [], False)
    assert len(jobs) == 1
    job = jobs[0]
    assert job.external_id == "1925654"
    assert job.source == "workingnomads"
    assert job.remote is True
    assert job.skills[:3] == ["flutter", "dart", "mobile"]
    assert job.posted_date is not None and job.posted_date.tzinfo is not None
    assert "Flutter" in job.description and "<" not in job.description
    clear_fetch_cache()


def test_working_nomads_handles_a_non_list_response(monkeypatch):
    """A blocked or changed feed must cost one warning line, not a crashed import."""
    from app.services.providers import WorkingNomadsProvider, clear_fetch_cache
    clear_fetch_cache()

    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"error": "nope"}

    import app.services.providers as providers_mod
    monkeypatch.setattr(providers_mod.httpx, "get", lambda *a, **k: FakeResp())
    assert WorkingNomadsProvider().fetch([], [], [], False) == []
    clear_fetch_cache()


def test_a_manual_import_re_reads_the_feed_a_scheduled_one_does_not(monkeypatch):
    """He asked for a hunter: pressing Import must see what was posted minutes ago.

    The cache window exists to keep free APIs off the back of a reload-happy browser,
    not to answer an explicit Import with a stale copy. A site with a monthly request
    allowance is the exception — spending it twice in a minute only blinds the month.
    """
    from app.services import providers as mod
    from app.services.providers import clear_fetch_cache, run_discovery

    clear_fetch_cache()
    hits: list[str] = []

    class Counting(mod.BaseProvider):
        name = "openfeed"
        label = "Open feed"
        fetch_ttl = 3600

        def fetch(self, titles, skills, locations, remote_only):
            mod._cached_get_json("openfeed:one", "http://example.invalid/feed")
            return []

    class Capped(Counting):
        name = "cappedfeed"
        label = "Capped feed"
        keep_cache_window = True

        def fetch(self, titles, skills, locations, remote_only):
            mod._cached_get_json("cappedfeed:one", "http://example.invalid/feed")
            return []

    class Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"jobs": []}

    def fake_get(url, *args, **kwargs):
        hits.append(url)
        return Resp()

    monkeypatch.setitem(mod.REGISTRY, "openfeed", Counting)
    monkeypatch.setitem(mod.REGISTRY, "cappedfeed", Capped)
    monkeypatch.setattr(mod.httpx, "get", fake_get)

    db = SessionLocal()
    try:
        mod.ensure_sources(db)
    finally:
        db.close()

    db = SessionLocal()
    try:
        for _ in range(2):
            run_discovery(db, ["Flutter Developer"], [], [], False, ["openfeed", "cappedfeed"])
        assert hits.count("http://example.invalid/feed") == 2  # one read each, second from cache

        for _ in range(2):
            run_discovery(db, ["Flutter Developer"], [], [], False, ["openfeed", "cappedfeed"], fresh=True)
        assert hits.count("http://example.invalid/feed") == 4  # the open site re-read twice
        # The capped site still answered once: its window held through both manual runs.
        run_discovery(db, ["Flutter Developer"], [], [], False, ["openfeed", "cappedfeed"])
        assert hits.count("http://example.invalid/feed") == 4  # a manual read refreshes the window
    finally:
        db.close()
    clear_fetch_cache()


def test_discovery_reports_real_per_site_progress(monkeypatch):
    """The import UI shows 'site x of N', so the callback must fire once per site, in order."""
    from app.services import providers as providers_mod
    from app.services.providers import clear_fetch_cache, run_discovery
    clear_fetch_cache()

    class SpyProvider(providers_mod.BaseProvider):
        name = "prog_one"
        label = "Progress One"

        def fetch(self, titles, skills, locations, remote_only):
            return []

    class SpyProviderTwo(SpyProvider):
        name = "prog_two"
        label = "Progress Two"

    monkeypatch.setitem(providers_mod.REGISTRY, "prog_one", SpyProvider)
    monkeypatch.setitem(providers_mod.REGISTRY, "prog_two", SpyProviderTwo)
    db = SessionLocal()
    try:
        providers_mod.ensure_sources(db)
    finally:
        db.close()

    events: list[tuple] = []
    db = SessionLocal()
    try:
        run_discovery(
            db, ["Flutter Developer"], [], [], False, ["prog_one", "prog_two"],
            on_progress=lambda done, total, name, label, line: events.append((done, total, name, label, line)),
        )
    finally:
        db.close()
    assert [(e[0], e[1], e[2]) for e in events] == [(1, 2, "prog_one"), (2, 2, "prog_two")]
    assert all("fetched 0" in e[4] for e in events)


def test_a_site_that_could_not_be_read_says_so(client, monkeypatch):
    """A board that never answered must not be reported as a board with nothing posted."""
    from app.services import providers as mod
    from app.services.providers import clear_fetch_cache, run_discovery

    clear_fetch_cache()

    class Silent(mod.BaseProvider):
        name = "silentfeed"
        label = "Silent feed"

        def fetch(self, titles, skills, locations, remote_only):
            mod._cached_get_json("silentfeed:one", "http://example.invalid/feed")
            return []

    def boom(url, *args, **kwargs):
        raise ConnectionError("no route to host")

    monkeypatch.setitem(mod.REGISTRY, "silentfeed", Silent)
    monkeypatch.setattr(mod.httpx, "get", boom)
    db = SessionLocal()
    try:
        mod.ensure_sources(db)
        _, lines = run_discovery(db, ["Flutter Developer"], [], [], False, ["silentfeed"])
    finally:
        db.close()
    assert any("Silent feed: could not be read" in line and "ConnectionError" in line for line in lines)
    assert not any(line.startswith("Silent feed: fetched 0") for line in lines)


def test_a_site_that_only_partly_answered_reports_the_pages_it_lost(client, monkeypatch):
    """The jobs it did send are still real, but the run says the rest went unread."""
    from app.services import providers as mod
    from app.services.providers import clear_fetch_cache, run_discovery

    clear_fetch_cache()

    class Half(mod.BaseProvider):
        name = "halffeed"
        label = "Half feed"

        def fetch(self, titles, skills, locations, remote_only):
            mod._cached_get_json("halffeed:one", "http://example.invalid/one")
            return [ProviderJob(source="halffeed", external_id="half-1",
                                title="Junior Flutter Developer",
                                posted_date=datetime.now(timezone.utc))]

    def once_then_boom(url, *args, **kwargs):
        if str(url).endswith("/one"):
            raise ConnectionError("no route to host")

        class Resp:
            def raise_for_status(self):
                pass

            def json(self):
                return {"jobs": []}

        return Resp()

    monkeypatch.setitem(mod.REGISTRY, "halffeed", Half)
    monkeypatch.setattr(mod.httpx, "get", once_then_boom)
    db = SessionLocal()
    try:
        mod.ensure_sources(db)
        _, lines = run_discovery(db, ["Flutter Developer"], [], [], False, ["halffeed"])
    finally:
        db.close()
    assert any(line.startswith("Half feed: fetched 1") and "partly read" in line for line in lines)


LI_CARDS_SAMPLE = """<li>
  <div class="base-card base-search-card job-search-card" data-entity-urn="urn:li:jobPosting:4470811064">
    <a class="base-card__full-link absolute" href="https://eg.linkedin.com/jobs/view/junior-mobile-developer-at-blnk-4470811064?position=1&amp;pageNum=0&amp;trackingId=abc">
      <span class="sr-only">Junior Mobile Developer</span>
    </a>
    <div class="base-search-card__info">
      <h3 class="base-search-card__title"> Junior Mobile Developer </h3>
      <h4 class="base-search-card__subtitle"><a class="hidden-nested-link" href="https://eg.linkedin.com/company/blnk"> blnk </a></h4>
      <div class="base-search-card__metadata">
        <span class="job-search-card__location"> Giza, Al Jizah, Egypt </span>
        <time class="job-search-card__listdate" datetime="2026-09-27"> 1 week ago </time>
      </div>
    </div>
  </div>
</li>
<li>
  <div class="base-card base-search-card job-search-card" data-entity-urn="urn:li:jobPosting:4470999001">
    <a class="base-card__full-link absolute" href="https://www.linkedin.com/jobs/view/remote-flutter-engineer-at-xyz-4470999001?position=2">
      <span class="sr-only">Remote Flutter Engineer</span>
    </a>
    <div class="base-search-card__info">
      <h3 class="base-search-card__title"> Remote Flutter Engineer </h3>
      <h4 class="base-search-card__subtitle"><a href="https://www.linkedin.com/company/xyz"> XYZ </a></h4>
      <div class="base-search-card__metadata">
        <span class="job-search-card__location"> Remote </span>
        <time class="job-search-card__listdate" datetime="2026-10-05"> 2 days ago </time>
      </div>
    </div>
  </div>
</li>"""


def test_linkedin_parses_guest_cards_with_clean_urls_and_dates(monkeypatch):
    from app.services.providers import LinkedInProvider, clear_fetch_cache
    clear_fetch_cache()

    class FakeResp:
        text = LI_CARDS_SAMPLE

        def raise_for_status(self):
            pass

        def json(self):
            return {}

    import app.services.providers as providers_mod
    monkeypatch.setattr(providers_mod.httpx, "get", lambda *a, **k: FakeResp())
    jobs = LinkedInProvider().fetch(["Flutter"], [], ["Egypt"], False)
    assert len(jobs) == 2
    first = jobs[0]
    assert first.source == "linkedin"
    assert first.external_id == "4470811064"
    assert first.title == "Junior Mobile Developer"
    assert first.company == "blnk"
    assert "Egypt" in first.location
    assert first.country == "Egypt"
    assert not first.remote
    # The tracking query is stripped so the same posting dedups across runs.
    assert first.url == "https://eg.linkedin.com/jobs/view/junior-mobile-developer-at-blnk-4470811064"
    assert first.posted_date is not None and first.posted_date.year == 2026
    second = jobs[1]
    assert second.remote and second.country == "Remote"


def test_linkedin_dedupes_repeated_postings_across_pages(monkeypatch):
    from app.services.providers import LinkedInProvider, clear_fetch_cache
    clear_fetch_cache()

    class FakeResp:
        text = LI_CARDS_SAMPLE

        def raise_for_status(self):
            pass

        def json(self):
            return {}

    import app.services.providers as providers_mod
    # Same two cards returned on every page: the seen-set must keep them unique.
    monkeypatch.setattr(providers_mod.httpx, "get", lambda *a, **k: FakeResp())
    jobs = LinkedInProvider().fetch([], [], [], False)
    ids = [j.external_id for j in jobs]
    assert ids == ["4470811064", "4470999001"]


def test_linkedin_handles_api_failure(monkeypatch):
    from app.services.providers import LinkedInProvider, clear_fetch_cache
    clear_fetch_cache()

    def boom(*args, **kwargs):
        raise ConnectionError("no internet")

    import app.services.providers as providers_mod
    monkeypatch.setattr(providers_mod.httpx, "get", boom)
    assert LinkedInProvider().fetch([], [], [], False) == []


JSEARCH_V2_SAMPLE = {
    "status": "OK",
    "data": {
        "jobs": [
            {
                "job_id": "abc123",
                "job_title": "Junior Flutter Developer",
                "employer_name": "Nile Apps",
                "job_publisher": "Wuzzuf",
                "job_location": "القاهرة",
                "job_country": "EG",
                "job_is_remote": False,
                "job_employment_types": "['FULLTIME']",
                "job_description": "Build Flutter apps for a growing Cairo team.",
                "job_apply_link": "https://wuzzuf.net/jobs/p/abc123",
                "job_min_salary": 30000,
                "job_max_salary": 55000,
                "job_salary_currency": "EGP",
                "job_posted_at_datetime_utc": "2026-10-04T10:00:00",
            },
            {
                "job_id": "def456",
                "job_title": "Remote Mobile Engineer",
                "employer_name": "",
                "job_publisher": "RemoteOK",
                "job_location": "Remote",
                "job_is_remote": True,
                "job_employment_type": "FULLTIME",
                "job_description": "Dart and Flutter, fully remote.",
                "job_apply_link": "https://remoteok.com/def456",
            },
        ],
        "cursor": None,
    },
}


def test_jsearch_skips_without_key(monkeypatch):
    from app.services.providers import JSearchProvider, clear_fetch_cache
    import app.config as config_mod
    clear_fetch_cache()
    monkeypatch.setattr(config_mod, "RAPIDAPI_KEY", "", raising=False)
    assert JSearchProvider().fetch(["Flutter"], [], [], False) == []


def test_jsearch_parses_v2_nested_payload(monkeypatch):
    from app.services.providers import JSearchProvider, clear_fetch_cache
    import app.config as config_mod
    clear_fetch_cache()
    monkeypatch.setattr(config_mod, "RAPIDAPI_KEY", "test-key", raising=False)

    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return JSEARCH_V2_SAMPLE

    import app.services.providers as providers_mod
    seen = {}

    def fake_get(url, params=None, headers=None, **k):
        seen["url"] = url
        seen["headers"] = headers
        return FakeResp()

    monkeypatch.setattr(providers_mod.httpx, "get", fake_get)
    jobs = JSearchProvider().fetch(["Flutter"], [], [], False)
    assert seen["headers"]["x-rapidapi-key"] == "test-key"
    assert seen["headers"]["x-rapidapi-host"] == "jsearch.p.rapidapi.com"
    assert len(jobs) == 2
    first = jobs[0]
    assert first.source == "jsearch"
    assert first.external_id == "abc123"
    assert first.title == "Junior Flutter Developer"
    assert first.company == "Nile Apps"
    assert first.employment_type == "Full-Time"
    assert first.salary_min == 30000 and first.salary_currency == "EGP"
    assert first.posted_date is not None and first.posted_date.year == 2026
    # The publisher is kept in the description so the user can see where it came from.
    assert "Wuzzuf" in first.description
    second = jobs[1]
    assert second.remote and second.company == "RemoteOK"  # falls back to publisher


def test_jsearch_handles_api_failure(monkeypatch):
    from app.services.providers import JSearchProvider, clear_fetch_cache
    import app.config as config_mod
    clear_fetch_cache()
    monkeypatch.setattr(config_mod, "RAPIDAPI_KEY", "test-key", raising=False)

    def boom(*args, **kwargs):
        raise ConnectionError("no internet")

    import app.services.providers as providers_mod
    monkeypatch.setattr(providers_mod.httpx, "get", boom)
    assert JSearchProvider().fetch([], [], [], False) == []


# --- search terms: what an import actually asks the keyword sites ---


def test_search_terms_keeps_order_dedupes_and_caps():
    from app.services.providers import FALLBACK_TERM, MAX_SEARCH_TERMS, search_terms

    assert search_terms(["Flutter Developer", "flutter developer", "Python"], ["Flutter"]) == [
        "Flutter Developer", "Python", "Flutter",
    ]
    assert len(search_terms([f"term {i}" for i in range(9)])) == MAX_SEARCH_TERMS
    assert search_terms([], []) == [FALLBACK_TERM]


def test_remotive_asks_each_term_as_its_own_request(monkeypatch):
    from app.services.providers import RemotiveProvider, clear_fetch_cache
    clear_fetch_cache()
    asked: list[str] = []

    class FakeResp:
        def __init__(self, search):
            self.search = search

        def raise_for_status(self):
            pass

        def json(self):
            other = 200 if self.search.startswith("Flutter") else 300
            return {"jobs": [
                {"id": 1, "title": "On every search", "company_name": "ACME", "url": "http://x/1"},
                {"id": other, "title": f"{self.search} role", "company_name": "CO",
                 "url": f"http://x/{other}"},
            ]}

    def fake_get(url, params=None, **kw):
        asked.append(params["search"])
        return FakeResp(params["search"])

    import app.services.providers as providers_mod
    monkeypatch.setattr(providers_mod.httpx, "get", fake_get)
    jobs = RemotiveProvider().fetch(["Flutter Developer", "Python Developer"], [], [], False)

    assert asked == ["Flutter Developer", "Python Developer"]
    assert len({j.external_id for j in jobs}) == len(jobs) == 3


def test_linkedin_loops_terms_and_merges_without_duplicates(monkeypatch):
    from app.services.providers import LinkedInProvider, clear_fetch_cache
    clear_fetch_cache()
    asked: list[tuple] = []

    class FakeResp:
        def __init__(self, keywords):
            self.keywords = keywords

        def raise_for_status(self):
            pass

        @property
        def text(self):
            return LI_CARDS_SAMPLE if self.keywords == "Flutter Developer" else ""

    def fake_get(url, params=None, **kw):
        asked.append((params["keywords"], params["start"]))
        return FakeResp(params["keywords"])

    import app.services.providers as providers_mod
    monkeypatch.setattr(providers_mod.httpx, "get", fake_get)
    jobs = LinkedInProvider().fetch(["Flutter Developer", "Python Developer"], [], ["Egypt"], False)

    assert [k for k, _ in asked] == ["Flutter Developer", "Flutter Developer", "Python Developer"]
    assert [s for _, s in asked][:2] == ["0", "25"]
    assert len(jobs) == 2


def test_jsearch_spends_one_request_per_import_and_rotates_the_term(monkeypatch):
    from app.services.providers import JSearchProvider, clear_fetch_cache
    clear_fetch_cache()
    asked: list[str] = []

    class FakeResp:
        def __init__(self, query):
            self.query = query

        def raise_for_status(self):
            pass

        def json(self):
            return JSEARCH_V2_SAMPLE

    def fake_get(url, params=None, **kw):
        asked.append(params["query"])
        return FakeResp(params["query"])

    import app.services.providers as providers_mod
    monkeypatch.setattr(providers_mod, "_jsearch_turn", 0)
    monkeypatch.setattr(providers_mod.config, "RAPIDAPI_KEY", "test-key", raising=False)
    monkeypatch.setattr(providers_mod.httpx, "get", fake_get)

    titles = ["Flutter Developer", "Python Developer"]
    JSearchProvider().fetch(titles, [], ["Egypt"], False)
    JSearchProvider().fetch(titles, [], ["Egypt"], False)

    assert asked == ["Flutter Developer jobs in Egypt", "Python Developer jobs in Egypt"]


def test_effective_terms_falls_back_to_the_profile_when_settings_are_blank():
    from app.database import SessionLocal
    from app.models import SearchPreference, Skill, UserProfile
    from app.services.providers import effective_terms

    db = SessionLocal()
    try:
        prof = db.query(UserProfile).first()
        prof.desired_titles = ["Flutter Developer"]
        prof.preferred_locations = ["Cairo"]
        db.add(Skill(profile_id=prof.id, name="Dart", level=4))
        pref = SearchPreference(id=1)
        db.add(pref)
        db.commit()

        titles, skills, locations = effective_terms(db, pref)
        assert titles == ["Flutter Developer"]
        assert skills == ["Dart"]
        # The country leads so a city in the profile cannot narrow the whole search.
        assert locations == ["Egypt", "Cairo"]

        pref.locations = ["Dubai"]
        db.commit()
        _, _, locations = effective_terms(db, pref)
        assert locations == ["Dubai"]

        pref.extra_terms = ["Game Developer"]
        db.commit()
        titles, _, _ = effective_terms(db, pref)
        assert titles == ["Flutter Developer", "Game Developer"]
    finally:
        db.close()


def test_search_plan_endpoint_shows_the_phrase_each_site_will_be_asked(client):
    r = client.post("/api/automation/search-plan", json={
        "titles": ["Flutter Developer"],
        "skills": ["Python"],
        "extra_terms": ["Game Developer"],
        "locations": ["Cairo"],
    })
    assert r.status_code == 200
    plan = r.json()

    assert plan["terms"] == ["Flutter Developer", "Game Developer", "Python"]
    assert plan["where"] == "Cairo"

    sites = {s["name"]: s for s in plan["sites"]}
    assert sites["linkedin"]["asks"] == [
        "Flutter Developer in Cairo", "Game Developer in Cairo", "Python in Cairo",
    ]
    assert sites["remotive"]["mode"] == "keyword"
    assert sites["arbeitnow"]["mode"] == "feed"
    assert sites["arbeitnow"]["asks"] == []
    assert sites["jsearch"]["needs_key"] is True
    assert sites["jsearch"]["asks"] == [
        "Flutter Developer jobs in Cairo", "Game Developer jobs in Cairo", "Python jobs in Cairo",
    ]
    assert "quota" in sites["jsearch"]["note"]
    assert sites["arbeitnow"]["note"]


def test_search_plan_marks_terms_that_have_to_wait(client):
    extra = ["React Developer", "Flutter Developer", "Python Developer", "QA Engineer",
             "Data Analyst", "DevOps Engineer", "Product Manager", "UI Designer"]
    r = client.post("/api/automation/search-plan", json={"titles": extra, "extra_terms": []})
    plan = r.json()
    assert len(plan["terms"]) == 5
    assert plan["terms_waiting"] == extra[5:]


def test_salary_sort_never_compares_one_currency_against_another(client):
    """"Highest salary" used to rank EGP 30,000 above USD 3,000 as if they were one money."""
    from app.database import SessionLocal
    from app.models import Job

    db = SessionLocal()
    try:
        jobs = db.query(Job).order_by(Job.id).all()
        for job, amount, currency in (
            (jobs[0], 30000, "EGP"), (jobs[1], 3000, "USD"), (jobs[2], 9000, "USD"),
            (jobs[3], None, "ZAR"), (jobs[4], 1500, None),
        ):
            job.salary_min = job.salary_max = amount
            job.salary_currency = currency
        db.commit()
    finally:
        db.close()

    items = client.get("/api/jobs?sort=salary&page_size=100").json()["items"]
    priced = [i for i in items if i["salary_min"]]
    amounts = [(i["salary_min"], (i["salary_currency"] or "").upper()) for i in priced]
    assert amounts[:4] == [(30000, "EGP"), (9000, "USD"), (3000, "USD"), (1500, "")]
    # A posting that publishes no amount never leads the list.
    assert not any(i["salary_min"] is None for i in items[: len(priced)])


def test_list_rows_carry_a_snippet_and_the_detail_carries_the_whole_ad(client):
    """Twenty full ads were ~90 KB to draw twenty two-line snippets."""
    with SessionLocal() as db:
        job = Job(profile_id=1, source="test", external_id="long-ad",
                  title="Long Ad Tester", company="ACME",
                  description="sentence about Flutter and Python " * 200)
        db.add(job)
        db.commit()
        job_id = job.id
    items = client.get("/api/jobs", params={"q": "Long Ad Tester"}).json()["items"]
    item = next(j for j in items if j["id"] == job_id)
    assert len(item["description"]) <= 600
    assert len(client.get(f"/api/jobs/{job_id}").json()["description"]) > 2000
