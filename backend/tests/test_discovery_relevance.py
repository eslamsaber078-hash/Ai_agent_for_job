"""Relevance-aware discovery: profile-derived phrases, the lenient gate, and the
employer-site providers added as a second acquisition channel."""
from datetime import datetime, timezone

from app.database import SessionLocal
from app.models import Job, JobSource, SearchPreference, Skill, UserProfile, WorkExperience
from app.services import providers as providers_mod
from app.services.providers import ProviderJob


CUSTOMER_SKILLS = [
    "Customer Support & Complaint Handling",
    "Retail Banking Sales & Cross-Selling",
    "Cash Handling  & Compliance",
    "POS",
    "CRM Systems & Call Center Operations",
    "MS Office",
    "Word",
    "Excel",
    "PowerPoint",
    "Outlook",
    "Problem Solving & Decision Making",
]


def _customer_profile(db, profile_id=2):
    db.add(UserProfile(id=profile_id, full_name="Customer Service Owner"))
    db.flush()
    for name in CUSTOMER_SKILLS:
        db.add(Skill(profile_id=profile_id, name=name))
    db.add(WorkExperience(profile_id=profile_id, title="Retail Sales Representative"))
    db.add(WorkExperience(profile_id=profile_id, title="Customer Service & Sales Representative"))
    db.add(WorkExperience(profile_id=profile_id, title="Cashier"))
    db.commit()


def test_long_skill_names_become_short_search_phrases():
    from app.services.keywords import skill_phrases
    from app.services.providers import search_terms

    assert skill_phrases("Customer Support & Complaint Handling") == [
        "Customer Support", "Complaint Handling",
    ]
    assert skill_phrases("CRM Systems & Call Center Operations") == ["CRM", "Call Center"]
    assert skill_phrases("Cash Handling  & Compliance") == ["Cash Handling"]
    assert skill_phrases("Problem Solving & Decision Making") == []
    assert skill_phrases("Microsoft Office") == []

    assert search_terms([], CUSTOMER_SKILLS) == [
        "Customer Support", "Complaint Handling", "Retail Banking Sales",
        "Cash Handling", "POS",
    ]


def test_held_job_titles_become_the_search_phrases_when_no_title_is_saved():
    from app.services.providers import role_search_titles

    assert role_search_titles([
        "Retail Sales Representative", "Customer Service & Sales Representative", "Cashier",
    ]) == ["Retail Sales", "Customer Service", "Cashier"]


def test_the_gate_keeps_relevant_work_and_drops_unrelated_work():
    from app.services.keywords import build_gate

    gate = build_gate([], CUSTOMER_SKILLS,
                      ["Retail Sales Representative", "Customer Service & Sales Representative", "Cashier"])
    assert gate(ProviderJob(source="x", external_id="1", title="Customer Service Representative"))
    assert gate(ProviderJob(source="x", external_id="2", title="Cashier",
                            description="Operate the POS and reconcile daily cash."))
    assert gate(ProviderJob(source="x", external_id="3", title="Sales Representative"))
    assert not gate(ProviderJob(source="x", external_id="4", title="Accountant",
                                description="Prepare tax filings and monthly reports in Excel."))
    assert not gate(ProviderJob(source="x", external_id="5", title="Operations Supervisor",
                                description="Manage warehouse shift operations and staff."))
    assert not gate(ProviderJob(source="x", external_id="6", title="Medical Manager",
                                description="Support regulatory compliance for the team."))


def test_the_gate_stays_lenient_for_adjacent_developer_roles():
    from app.services.keywords import build_gate

    gate = build_gate(["Flutter Developer", "Mobile Developer", "Junior Software Developer"],
                      ["Flutter", "Python", "JavaScript", "HTML", "CSS", "CRM Systems"])
    assert gate(ProviderJob(source="x", external_id="1", title="Flutter Developer"))
    assert gate(ProviderJob(source="x", external_id="2", title="Software Engineer"))
    assert gate(ProviderJob(source="x", external_id="3", title="React Developer",
                            description="Build web interfaces with JavaScript, HTML and CSS."))
    assert not gate(ProviderJob(source="x", external_id="4", title="Accountant",
                                description="Monthly closing and tax reports."))


def test_a_profile_with_only_tool_and_soft_skills_is_not_filtered():
    from app.services.keywords import build_gate

    assert build_gate(["Cashier"], ["MS Office", "Excel", "Problem Solving", "English"]) is not None
    assert build_gate([], ["MS Office", "Excel", "Problem Solving", "English"]) is None


def test_discovery_searches_held_roles_and_skips_unrelated_jobs(client, monkeypatch):
    seen = {}

    class FakeProvider(providers_mod.BaseProvider):
        name = "rolefeed"
        label = "Role feed"

        def fetch(self, titles, skills, locations, remote_only):
            seen["titles"] = list(titles)
            seen["skills"] = list(skills)
            return [
                ProviderJob(source="rolefeed", external_id="keep-1",
                            title="Customer Service Agent", posted_date=datetime.now(timezone.utc)),
                ProviderJob(source="rolefeed", external_id="keep-2",
                            title="Retail Sales Associate", posted_date=datetime.now(timezone.utc)),
                ProviderJob(source="rolefeed", external_id="drop-1",
                            title="Diesel Mechanic", posted_date=datetime.now(timezone.utc)),
            ]

    monkeypatch.setitem(providers_mod.REGISTRY, "rolefeed", FakeProvider)
    db = SessionLocal()
    try:
        _customer_profile(db)
        providers_mod.ensure_sources(db)
        total, lines = providers_mod.run_discovery(
            db, [], [], [], False, ["rolefeed"], profile_id=2,
        )
        kept = {j.title for j in db.query(Job).filter(Job.profile_id == 2).all()}
    finally:
        db.close()

    assert seen["titles"] == ["Retail Sales", "Customer Service", "Cashier"]
    assert seen["skills"] == [s.replace("  ", " ") for s in CUSTOMER_SKILLS]
    assert total == 2
    assert kept == {"Customer Service Agent", "Retail Sales Associate"}
    assert any("1 skipped as unrelated" in line for line in lines)


def test_amazon_feed_is_normalized_and_restricted_to_egypt(monkeypatch):
    from app.services.providers import AmazonProvider, clear_fetch_cache

    payload = {"jobs": [
        {"id_icims": "1", "title": " Customer Service Associate ", "company_name": "Souq.com",
         "location": "EG, Cairo", "country_code": "EGY", "posted_date": "October 25, 2026",
         "job_path": "/en/jobs/1/customer-service", "description": "Help customers.",
         "basic_qualifications": "English", "preferred_qualifications": "",
         "job_schedule_type": "full-time"},
        {"id_icims": "2", "title": "Warehouse Associate", "company_name": "Amazon",
         "location": "US, Seattle", "country_code": "USA", "posted_date": "October 24, 2026",
         "job_path": "/en/jobs/2/warehouse"},
    ]}
    monkeypatch.setattr(providers_mod, "_cached_get_json", lambda *a, **k: payload)
    jobs = AmazonProvider().fetch([], [], [], False)
    clear_fetch_cache()

    assert len(jobs) == 1
    job = jobs[0]
    assert job.title == "Customer Service Associate"
    assert job.location == "Cairo, Egypt"
    assert job.url == "https://www.amazon.jobs/en/jobs/1/customer-service"
    assert job.posted_date == datetime(2026, 10, 25, tzinfo=timezone.utc)
    assert "Help customers" in job.description


def test_workday_reads_the_employer_site_and_drops_other_countries(monkeypatch):
    from app.services.providers import WorkdayProvider, clear_fetch_cache

    def fake_post(key, url, payload, **kwargs):
        if "citi" in url:
            return {"jobPostings": [
                {"title": "Sales Representative", "locationsText": "Cairo Egypt",
                 "postedOn": "Posted Today", "externalPath": "/job/Cairo/Sales_1",
                 "bulletFields": ["1"]},
                {"title": "Banker", "locationsText": "Dubai United Arab Emirates",
                 "postedOn": "Posted Today", "externalPath": "/job/Dubai/Banker_2",
                 "bulletFields": ["2"]},
            ]}
        return {"jobPostings": []}

    def fake_get(key, url, **kwargs):
        if url.endswith("/job/Cairo/Sales_1"):
            return {"jobPostingInfo": {
                "jobDescription": "<p>Customer sales and service.</p>",
                "startDate": "2026-10-20", "location": "Cairo",
                "country": {"descriptor": "Egypt"}, "timeType": "Full time",
                "externalUrl": "https://citi.example/job/1",
            }}
        return None

    monkeypatch.setattr(providers_mod, "_cached_post_json", fake_post)
    monkeypatch.setattr(providers_mod, "_cached_get_json", fake_get)
    jobs = WorkdayProvider().fetch([], [], [], False)
    clear_fetch_cache()

    assert [j.title for j in jobs] == ["Sales Representative"]
    job = jobs[0]
    assert job.company == "Citi"
    assert job.external_id == "citi:1"
    assert job.location == "Cairo, Egypt"
    assert job.url == "https://citi.example/job/1"
    assert job.posted_date == datetime(2026, 10, 20, tzinfo=timezone.utc)
    assert job.employment_type == "Full time"


def test_smartrecruiters_reads_the_employer_listing(monkeypatch):
    from app.services.providers import SmartRecruitersProvider, clear_fetch_cache

    listing = {"content": [{
        "id": "7440001", "name": "Customer Service Agent",
        "location": {"city": "Cairo", "country": "eg", "fullLocation": "Cairo, Egypt",
                     "remote": False, "hybrid": False},
        "releasedDate": "2026-10-20T10:00:00.000Z",
        "typeOfEmployment": {"label": "Full time"},
        "experienceLevel": {"label": "Entry Level"},
    }]}

    def fake_get(key, url, **kwargs):
        if url.endswith("/postings/7440001"):
            return {
                "postingUrl": "https://jobs.smartrecruiters.com/DeliveryHero/7440001",
                "jobAd": {"sections": {"jobDescription": "<p>Help customers by phone.</p>"}},
                "location": {"fullLocation": "Cairo, Egypt"},
            }
        return listing

    monkeypatch.setattr(providers_mod, "_cached_get_json", fake_get)
    jobs = SmartRecruitersProvider().fetch([], [], [], False)
    clear_fetch_cache()

    assert len(jobs) == 1
    job = jobs[0]
    assert job.title == "Customer Service Agent"
    assert job.company == "Delivery Hero"
    assert job.external_id == "DeliveryHero:7440001"
    assert job.employment_type == "Full time"
    assert job.posted_date == datetime(2026, 10, 20, 10, 0, tzinfo=timezone.utc)
    assert "Help customers" in job.description


def test_jooble_is_silent_without_a_key_and_parses_with_one(monkeypatch):
    from app.services.providers import JoobleProvider

    monkeypatch.setattr(providers_mod.config, "JOOBLE_API_KEY", "")
    assert JoobleProvider().fetch([], [], [], False) == []

    monkeypatch.setattr(providers_mod.config, "JOOBLE_API_KEY", "test-key")
    payload = {"jobs": [{
        "id": 99, "title": "Call Center Agent", "company": "Telecom Co",
        "location": "Cairo", "snippet": "Handle <b>customer</b> calls.",
        "link": "https://jooble.example/99", "type": "Full-time",
        "updated": "2026-10-20T10:00:00.0000000",
    }]}
    monkeypatch.setattr(providers_mod, "_jooble_search", lambda key, phrase, where: payload)
    jobs = JoobleProvider().fetch(["Cashier"], [], ["Egypt"], False)

    assert len(jobs) == 1
    assert jobs[0].external_id == "99"
    assert jobs[0].description == "Handle customer calls."
    assert jobs[0].posted_date == datetime(2026, 10, 20, 10, 0, tzinfo=timezone.utc)


def test_relative_dates_read_thirty_plus_days_honestly():
    from app.services.providers import _parse_named_date, _relative_to_date

    parsed = _relative_to_date("Posted 30+ Days Ago")
    assert parsed is not None
    assert 29 <= (datetime.now(timezone.utc) - parsed).days <= 31
    assert _parse_named_date("April  2, 2026") == datetime(2026, 4, 2, tzinfo=timezone.utc)


def test_a_newly_added_free_site_joins_existing_preferences_once(client):
    db = SessionLocal()
    try:
        pref = SearchPreference(id=1, sources=["remotive"])
        db.add(pref)
        db.query(JobSource).filter(JobSource.name == "amazon").delete()
        db.commit()

        providers_mod.ensure_sources(db)
        db.refresh(pref)
        assert "amazon" in pref.sources
        assert "jooble" not in pref.sources  # key-gated sites stay unticked
    finally:
        db.close()


def test_employer_boards_keep_only_locations_open_to_egypt(monkeypatch):
    from app.services.providers import EmployerBoardsProvider, clear_fetch_cache

    listing = {
        "jobs": [
            {"id": 1, "title": "Linux Support Engineer", "location": {"name": "Home Based - EMEA"},
             "first_published": "2026-10-20T10:00:00+00:00",
             "absolute_url": "https://canonical.example/jobs/1"},
            {"id": 2, "title": "Sales Director", "location": {"name": "Remote - US"},
             "first_published": "2026-10-20T10:00:00+00:00",
             "absolute_url": "https://canonical.example/jobs/2"},
            {"id": 3, "title": "Accountant", "location": {"name": "Cairo, Egypt"},
             "first_published": "2026-10-20T10:00:00+00:00",
             "absolute_url": "https://canonical.example/jobs/3"},
            {"id": 4, "title": "Onsite Role", "location": {"name": "London"},
             "first_published": "2026-10-20T10:00:00+00:00",
             "absolute_url": "https://canonical.example/jobs/4"},
        ]
    }

    detail_calls = []

    def fake_get(key, url, **kwargs):
        if url.endswith("/jobs"):
            return listing
        detail_calls.append(url)
        posting_id = url.rsplit("/", 1)[-1]
        return {
            "id": posting_id,
            "title": "Linux Support Engineer",
            "content": "<p>Help customers with Ubuntu, Python and networking.</p>",
            "absolute_url": f"https://canonical.example/jobs/{posting_id}",
            "first_published": "2026-10-20T10:00:00+00:00",
        }

    monkeypatch.setattr(providers_mod, "_cached_get_json", fake_get)
    monkeypatch.setattr(providers_mod, "EMPLOYER_BOARDS", (("greenhouse", "canonical", "Canonical"),))
    jobs = EmployerBoardsProvider().fetch([], [], [], False)
    clear_fetch_cache()

    assert {j.title for j in jobs} == {"Linux Support Engineer", "Accountant"}
    egypt = next(j for j in jobs if j.title == "Accountant")
    assert egypt.country == "Egypt"
    assert egypt.external_id == "greenhouse:canonical:3"
    linux = next(j for j in jobs if j.title == "Linux Support Engineer")
    assert "Python" in linux.description
    assert linux.company == "Canonical"
    assert any("/jobs/1" in url for url in detail_calls)
    assert not any("/jobs/2" in url for url in detail_calls)


def test_employer_boards_ashby_lists_carry_their_own_description(monkeypatch):
    from app.services.providers import EmployerBoardsProvider, clear_fetch_cache

    listing = {
        "jobs": [
            {"id": "a1", "title": "Platform Engineer", "location": "Remote, Global",
             "secondaryLocations": [{"location": "Remote, EMEA"}],
             "publishedAt": "2026-10-19T09:00:00.000Z", "jobUrl": "https://supabase.example/a1",
             "descriptionPlain": "Build Postgres tooling with Rust and Python.",
             "employmentType": "FullTime"},
            {"id": "a2", "title": "Sales Engineer", "location": "Remote, AMER",
             "secondaryLocations": [], "publishedAt": "2026-10-19T09:00:00.000Z",
             "jobUrl": "https://supabase.example/a2", "descriptionPlain": "US only."},
            {"id": "a3", "title": "Designer", "location": "San Francisco",
             "secondaryLocations": [], "publishedAt": "2026-10-19T09:00:00.000Z",
             "jobUrl": "https://supabase.example/a3", "descriptionPlain": "Onsite."},
        ]
    }
    monkeypatch.setattr(providers_mod, "_cached_get_json", lambda *a, **k: listing)
    monkeypatch.setattr(providers_mod, "EMPLOYER_BOARDS", (("ashby", "supabase", "Supabase"),))
    jobs = EmployerBoardsProvider().fetch([], [], [], False)
    clear_fetch_cache()

    assert [j.title for j in jobs] == ["Platform Engineer"]
    job = jobs[0]
    assert job.external_id == "ashby:supabase:a1"
    assert "Rust" in job.description
    assert job.remote is True
    assert job.employment_type == "FullTime"
    assert job.posted_date == datetime(2026, 10, 19, 9, 0, tzinfo=timezone.utc)


def test_open_remote_distinguishes_worldwide_from_country_locked():
    from app.services.providers import _open_remote

    assert _open_remote("Remote")
    assert _open_remote("Remote, Global")
    assert _open_remote("Remote - EMEA")
    assert _open_remote("Home Based - Worldwide")
    assert _open_remote("Remote (Middle East)")
    assert not _open_remote("Remote - US")
    assert not _open_remote("Remote, AMER")
    assert not _open_remote("Remote Canada")
    assert not _open_remote("Remote - United Kingdom")
    assert not _open_remote("San Francisco")
    assert not _open_remote("Remote - Abu Dhabi")


def test_talent_reads_egypt_cards_and_skips_locked_locations(monkeypatch):
    from app.services.providers import TalentProvider, clear_fetch_cache

    html = """
    <article class="JobCard_card__a JobCard_cardActive__b">
      <h2 class="JobCard_title__t">Flutter Developer</h2>
      <span class="JobCard_company__c">Advansys</span>
      <span class="JobCard_location__l">Cairo, Cairo Governorate, EG</span>
      <p class="JobCard_snippet__s">Build mobile apps for iOS and Android.</p>
      <time class="JobCard_timeText__w" dateTime="2026-11-08T12:11:42Z">8 days ago</time>
      <a href="/view?id=645107402656583720">more</a>
    </article>
    <article class="JobCard_card__a">
      <h2 class="JobCard_title__t">Backend Engineer</h2>
      <span class="JobCard_company__c">Remote Co</span>
      <span class="JobCard_location__l">Remote - United States</span>
      <time class="JobCard_timeText__w" dateTime="2026-11-09T08:00:00Z">yesterday</time>
      <a href="/view?id=111">more</a>
    </article>
    """

    monkeypatch.setattr(providers_mod, "_cached_get_text", lambda *a, **k: html)
    jobs = TalentProvider().fetch(["Flutter Developer"], ["Flutter"], ["Egypt"], False)
    clear_fetch_cache()

    assert [j.title for j in jobs] == ["Flutter Developer"]
    job = jobs[0]
    assert job.company == "Advansys"
    assert job.location == "Cairo, Cairo Governorate, EG"
    assert job.country == "Egypt"
    assert job.external_id == "645107402656583720"
    assert job.url == "https://eg.talent.com/view?id=645107402656583720"
    assert job.description.startswith("Build mobile apps")
    assert job.posted_date == datetime(2026, 11, 8, 12, 11, 42, tzinfo=timezone.utc)


def test_forasna_parses_card_and_keeps_the_english_slug(monkeypatch):
    from app.services.providers import ForasnaProvider, clear_fetch_cache

    url = ("https://forasna.com/job/p/%D9%85%D8%AD%D8%A7%D8%B3%D8%A8-"
           "Branch-Accountant-447467")
    html = f"""
    <div class="result-wrp">
      <h2 class="job-title"><a href="{url}"><span>محاسب فرع</span></a></h2>
      <span class="date date-desktop">
        <time class="time1 job-date" datetime="2026-11-14T14:09:46+02:00">منذ يومين</time>
      </span>
      <div class="company-meta">
        <span>الشركة السويسرية</span>
        <span class="location location-desktop"> - <span>القاهرة الجديدة</span></span>
      </div>
    </div>
    """

    monkeypatch.setattr(providers_mod, "_cached_get_text", lambda *a, **k: html)
    jobs = ForasnaProvider().fetch(["accountant"], [], ["Egypt"], False)
    clear_fetch_cache()

    assert len(jobs) == 1
    job = jobs[0]
    assert job.title == "محاسب فرع"
    assert job.company == "الشركة السويسرية"
    assert job.location == "القاهرة الجديدة"
    assert job.external_id == "447467"
    # The English words in the slug keep the relevance gate working on Arabic titles.
    assert "Branch Accountant" in job.description
    assert job.posted_date == datetime(2026, 11, 14, 12, 9, 46, tzinfo=timezone.utc)


def test_tanqeeb_keeps_only_egypt_cards_and_reads_attributes(monkeypatch):
    from app.services.providers import TanqeebProvider, clear_fetch_cache

    html = """
    <article class="card" data-job-id="21184560" data-job-name="Flutter Developer"
      data-job-company="Adree" data-job-location="Egypt - Cairo"
      data-job-workplace="Remote" data-job-type="Full Time" data-job-source="LinkedIn"
      data-job-country="Egypt" data-job-date="16 November 2026"
      data-job-url="/jobs-in-egypt/all/jobs/021184560.html"
      data-job-salary="EGP 20000 - 30000" data-job-experience="2 to 5 years"
      data-job-keywords="Flutter,Dart"><div class="card-body">details</div></article>
    <article class="card" data-job-id="99" data-job-name="Sales Rep"
      data-job-country="Jordan" data-job-location="Jordan - Amman"
      data-job-url="/jobs-in-jordan/all/jobs/021184561.html"></article>
    """

    monkeypatch.setattr(providers_mod, "_cached_get_text", lambda *a, **k: html)
    jobs = TanqeebProvider().fetch(["Flutter Developer"], ["Flutter"], ["Egypt"], False)
    clear_fetch_cache()

    assert [j.title for j in jobs] == ["Flutter Developer"]
    job = jobs[0]
    assert job.company == "Adree"
    assert job.location == "Egypt - Cairo"
    assert job.remote is True
    assert job.external_id == "21184560"
    assert job.url == "https://www.tanqeeb.com/jobs-in-egypt/all/jobs/021184560.html"
    assert job.skills == ["Flutter", "Dart"]
    assert (job.salary_min, job.salary_max, job.salary_currency) == (20000, 30000, "EGP")
    assert job.posted_date == datetime(2026, 11, 16, tzinfo=timezone.utc)


def test_every_registered_provider_declares_a_region():
    from app.services import REGISTRY

    assert {cls.region for cls in REGISTRY.values()} <= {"egypt", "worldwide"}
    for name in ("linkedin", "talent", "forasna", "tanqeeb", "jsearch", "amazon", "adzuna"):
        assert REGISTRY[name].region == "egypt"
    for name in ("remotive", "remoteok", "himalayas", "employers"):
        assert REGISTRY[name].region == "worldwide"


def test_adzuna_stays_silent_without_keys_and_parses_with_them(monkeypatch):
    from app.services.providers import AdzunaProvider, clear_fetch_cache

    monkeypatch.setattr(providers_mod.config, "ADZUNA_APP_ID", "")
    monkeypatch.setattr(providers_mod.config, "ADZUNA_APP_KEY", "")
    assert AdzunaProvider().fetch(["Flutter"], [], ["Egypt"], False) == []

    monkeypatch.setattr(providers_mod.config, "ADZUNA_APP_ID", "app-1")
    monkeypatch.setattr(providers_mod.config, "ADZUNA_APP_KEY", "secret")

    captured = {}

    def fake_get(key, url, **kwargs):
        captured["params"] = kwargs.get("params")
        captured["url"] = url
        return {"results": [
            {"id": "42", "title": "Flutter Developer", "company": {"display_name": "NileSoft"},
             "location": {"display_name": "Cairo, Egypt"},
             "salary_min": 15000, "salary_max": 25000, "salary_currency": "EGP",
             "contract_time": "permanent", "description": "<p>Build mobile apps.</p>",
             "redirect_url": "https://adzuna.example/42", "created": "2026-10-25T08:00:00Z"},
        ]}

    monkeypatch.setattr(providers_mod, "_cached_get_json", fake_get)
    jobs = AdzunaProvider().fetch(["Flutter"], [], ["Egypt"], False)
    clear_fetch_cache()

    assert len(jobs) == 1
    job = jobs[0]
    assert job.title == "Flutter Developer"
    assert job.company == "NileSoft"
    assert job.salary_min == 15000 and job.salary_currency == "EGP"
    assert captured["url"].endswith("/eg/search/1")
    assert captured["params"]["app_id"] == "app-1"
    assert captured["params"]["what"] == "Flutter"
    assert job.posted_date == datetime(2026, 10, 25, 8, 0, tzinfo=timezone.utc)
