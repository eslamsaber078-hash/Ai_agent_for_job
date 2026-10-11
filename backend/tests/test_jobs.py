from datetime import datetime, timedelta, timezone

from app.database import SessionLocal
from app.models import Job
from app.services import run_discovery
from app.services.providers import BaseProvider, ProviderJob, RemotiveProvider
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


def test_refresh_endpoint(client):
    r = client.post("/api/jobs/refresh", json=["remotive"])
    assert r.status_code == 200
    body = r.json()
    assert "jobs_new" in body
    assert any("Remotive" in line for line in body["log"])


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
    assert all(s["requires_key"] is False for s in sources.values())


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
                                    title=f"{name} posting", posted_date=datetime.now(timezone.utc))]
        Only.name = name
        return Only

    for name in ("sitea", "siteb"):
        monkeypatch.setitem(providers_mod.REGISTRY, name, make(name))
    db = SessionLocal()
    try:
        providers_mod.ensure_sources(db)
    finally:
        db.close()

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
