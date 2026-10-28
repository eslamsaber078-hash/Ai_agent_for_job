from app.database import SessionLocal
from app.models import Job


def _put_profile(client, payload: dict):
    r = client.put("/api/profile", json=payload)
    assert r.status_code == 200, r.text
    return r.json()


def _add_skills(client, skills):
    r = client.put("/api/profile/skills", json=skills)
    assert r.status_code == 200, r.text


def _flutter_profile() -> dict:
    return dict(
        full_name="Ahmed", email="a@b.com", country="Egypt", city="Cairo",
        desired_titles=["Flutter Developer", "Mobile Developer"],
        preferred_locations=["Cairo", "Remote"], remote_preference="open",
        work_types=["Full-time", "Internship"], target_levels=["Intern", "Junior", "Entry"],
        summary="Flutter and Python developer building mobile apps.",
        languages=["Arabic", "English"],
    )


def test_empty_profile_gives_zero_and_explains(client):
    r = client.get("/api/matches/1")
    assert r.status_code == 200
    data = r.json()
    assert data["score"] == 0
    assert "profile" in data["why_match"].lower()
    r = client.get("/api/matches")
    assert r.json()["profile_empty"] is True


def test_matching_with_skills(client):
    _put_profile(client, _flutter_profile())
    _add_skills(client, [
        dict(name="Flutter", level=4, years=1.5),
        dict(name="Dart", level=4, years=1.5),
        dict(name="Git", level=3, years=1),
    ])
    r = client.get("/api/matches/1")  # fixture job #1 = Junior Flutter Developer
    data = r.json()
    assert 0 <= data["score"] <= 100
    assert "Flutter" in data["matched_skills"]
    assert data["estimate"] is True
    assert data["factors"]
    assert data["next_steps"]


def test_matching_lists_sorted_with_min_score(client):
    _put_profile(client, _flutter_profile())
    _add_skills(client, [
        dict(name="Flutter", level=5, years=2),
        dict(name="Dart", level=5, years=2),
        dict(name="Firebase", level=3, years=1),
        dict(name="REST APIs", level=3, years=1),
        dict(name="Git", level=3, years=1),
    ])
    r = client.get("/api/matches", params={"limit": 100})
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) > 10
    scores = [i["score"] for i in items]
    assert scores == sorted(scores, reverse=True)
    top = items[0]
    assert "flutter" in top["job"]["title"].lower() or "flutter" in top["matched_skills"] or top["score"] >= 60
    r = client.get("/api/matches", params={"min_score": 95})
    assert all(i["score"] >= 95 for i in r.json()["items"])


def test_matching_missing_skills_listed(client):
    _put_profile(client, _flutter_profile())
    _add_skills(client, [dict(name="Flutter", level=3)])
    db = SessionLocal()
    try:
        jobs = db.query(Job).all()
        job = next(j for j in jobs if any("c#" in (s or "").lower() for s in (j.skills or [])))
        job_id = job.id
    finally:
        db.close()
    data = client.get(f"/api/matches/{job_id}").json()
    assert any("c#" in m.lower() for m in data["missing_skills"])
    assert data["score"] < 60


def test_match_404(client):
    assert client.get("/api/matches/999999").status_code == 404


def test_skill_detection_needs_the_whole_word():
    """Substring matching invented skills: "Excel" inside "excellent", "Java" inside "JavaScript"."""
    from app.services.matching import detect_skills

    assert detect_skills("An excellent, highly motivated team player who loops fast.") == []
    found = {s.lower() for s in detect_skills("Java, JavaScript, Excel and loop-free C# with REST APIs")}
    assert {"java", "javascript", "excel", "c#", "rest apis"} <= found
    assert "oop" not in found


def test_provider_only_counts_when_the_context_is_real():
    from app.services.matching import detect_skills

    # "provider" is Flutter's Provider package in a Flutter post, plain English elsewhere.
    assert "provider" in [s.lower() for s in detect_skills("Flutter app built with the Provider package")]
    assert detect_skills("Hosted on a cloud provider") == []


def test_board_junk_is_not_scored_as_a_required_skill():
    """Job boards tag their own taxonomy: "10115", "senior", "Anywhere".

    Each one used to count as a skill the candidate lacks, which sank honest matches
    below the minimum score.
    """
    from app.models import Job
    from app.services.matching import job_skill_tags

    job = Job(
        title="Senior Engineer", company="Acme", source="arbeitnow",
        description="You will write C# and React all day.",
        skills=["10115", "12001 - Account Executives", "senior", "Anywhere",
                "C#", "c sharp", "CI/CD", "ci/cd"],
    )
    assert job_skill_tags(job) == ["C#", "CI/CD", "React"]


def test_a_real_skill_the_lexicon_does_not_know_survives():
    from app.models import Job
    from app.services.matching import job_skill_tags

    job = Job(title="x", company="y", source="remotive",
              description="Build and tune Shopify storefronts.", skills=["Shopify"])
    assert job_skill_tags(job) == ["Shopify"]


def _match_of(client, *, title="Data Platform Worker", description="", resume_text=None,
              profile=None, skills=None, experiences=None, **job_fields):
    """Score one throwaway posting against Python/Git/Docker at top level in Cairo.

    ``profile``, ``skills`` and ``experiences`` replace the defaults when a test needs
    to show the scorer a different CV.
    """
    from app.database import SessionLocal
    from app.models import Job, UserProfile

    payload = dict(
        full_name="Ahmed", summary="Looking for developer work.", desired_titles=["Flutter Developer"],
        target_levels=["Junior"], country="Egypt", preferred_locations=["Cairo", "Remote"],
        remote_preference="open", min_salary=10000, salary_currency="EGP",
    )
    payload.update(profile or {})
    client.put("/api/profile", json=payload)
    client.put("/api/profile/skills", json=skills if skills is not None else [
        dict(name=n, level=5) for n in ("Python", "Git", "Docker")])
    if experiences is not None:
        client.put("/api/profile/experiences", json=experiences)
    defaults = dict(location="Cairo", country="Egypt", remote=False,
                    experience_level="", salary_min=None, salary_max=None, salary_currency=None)
    defaults.update(job_fields)
    db = SessionLocal()
    try:
        job = db.query(Job).order_by(Job.id).first()
        job.title, job.description, job.skills = title, description, []
        for key, value in defaults.items():
            setattr(job, key, value)
        job_id = job.id
        db.get(UserProfile, 1).resume_text = resume_text
        db.commit()
    finally:
        db.close()
    return client.get(f"/api/matches/{job_id}").json()


def _factor(match, label):
    return next(f for f in match["factors"] if f["label"] == label)


def test_one_shared_keyword_is_not_a_full_skills_match(client):
    """A posting naming one requirement he has must not claim a 100% skills match."""
    skills = _factor(_match_of(client, description="You will write Python here."), "Skills")
    assert skills["score"] == 67
    assert "unverified" in skills["detail"]


def test_a_stated_requirement_he_lacks_still_costs_him(client):
    skills = _factor(_match_of(client, description="You will manage Kubernetes here."), "Skills")
    assert skills["score"] == 33


def test_three_stated_requirements_are_full_evidence(client):
    skills = _factor(_match_of(client, description="You will write Python, ship with Git and run Docker."),
                     "Skills")
    assert skills["score"] == 100
    assert "unverified" not in skills["detail"]


def test_a_card_with_only_a_title_still_asks_for_flutter(client):
    """LinkedIn's list cards arrive with no description; the title is the requirement."""
    match = _match_of(client, title="Flutter Developer", description="",
                      location="Nasr City", country="Egypt", remote=False)
    skills = _factor(match, "Skills")
    assert "Flutter" in match["missing_skills"]
    assert skills["score"] == 33


def test_a_stated_level_at_his_target_is_worth_full_credit(client):
    level = _factor(_match_of(client, experience_level="Junior"), "Experience level")
    assert level["score"] == 100


def test_an_unstated_level_is_not_free_credit(client):
    """Silence about seniority used to pay 75/100, which inflated every thin posting."""
    level = _factor(_match_of(client, experience_level=""), "Experience level")
    assert level["score"] == 25
    assert "no experience level" in level["detail"]


def test_a_senior_role_is_marked_above_his_target(client):
    level = _factor(_match_of(client, experience_level="Senior"), "Experience level")
    assert level["score"] == 20


def test_a_level_only_in_the_title_is_still_read(client):
    """LinkedIn cards and WWR ads state seniority in the headline and leave the field empty."""
    level = _factor(_match_of(client, title="Junior Flutter Developer", experience_level=""),
                    "Experience level")
    assert level["score"] == 100
    assert "read from the title" in level["detail"]

    above = _factor(_match_of(client, title="Senior Flutter Developer", experience_level=""),
                    "Experience level")
    assert above["score"] == 20


def test_the_concerns_agree_with_a_level_read_from_the_title(client):
    """The prose must not claim the ad is silent about level when the title said it."""
    senior = _match_of(client, title="Senior Flutter Developer", experience_level="")
    assert "above what you are targeting" in senior["concerns"]
    assert "never states which level" not in senior["concerns"]

    quiet = _match_of(client, title="Data Platform Worker", experience_level="")
    assert "never states which level" in quiet["concerns"]


def test_an_office_role_in_another_country_is_not_a_location_match(client):
    """The word 'Remote' inside a UK location string is not his 'Remote' preference."""
    loc = _factor(_match_of(client, location="Remote UK - North", country="Remote UK - North",
                            remote=False), "Location & remote")
    assert loc["score"] == 15


def test_a_worldwide_remote_role_wins_on_location(client):
    loc = _factor(_match_of(client, location="Remote", country="Remote", remote=True),
                  "Location & remote")
    assert loc["score"] == 90


def test_a_remote_role_limited_to_another_country_is_penalised(client):
    """A US-only remote ad is not 'remote' for someone living in Egypt."""
    loc = _factor(_match_of(client, location="Remote", country="United States", remote=True),
                  "Location & remote")
    assert loc["score"] == 20
    assert "you are in Egypt" in loc["detail"]


def test_a_remote_role_limited_to_a_region_is_partially_reachable(client):
    loc = _factor(_match_of(client, location="Remote - EMEA", country="EMEA", remote=True),
                  "Location & remote")
    assert loc["score"] == 55
    assert "region" in loc["detail"]


def test_a_remote_tag_on_a_city_only_ad_does_not_earn_him_credit(client):
    """"Remote" in the fields plus "(Denver, CO)" in the headline means US-only."""
    match = _match_of(client, title="Support Engineer (Denver, CO)",
                      location="", country="Remote", remote=True)
    loc = _factor(match, "Location & remote")
    assert loc["score"] == 20
    assert "Denver, CO" in loc["detail"]
    assert "not remote" not in match["concerns"]


def test_a_headline_city_he_lives_in_is_still_full_credit(client):
    loc = _factor(_match_of(client, title="Flutter Developer (Cairo, Egypt)",
                            location="", country="Remote", remote=True), "Location & remote")
    assert loc["score"] == 100


def test_a_parenthetical_that_is_not_a_place_is_not_read_as_one(client):
    """SMB Account Executive (New Business) must not be treated as a location limit."""
    loc = _factor(_match_of(client, title="SMB Account Executive (New Business)",
                            location="", country="Remote", remote=True), "Location & remote")
    assert loc["score"] == 90


def test_no_salary_published_is_not_half_a_match(client):
    salary = _factor(_match_of(client), "Salary")
    assert salary["score"] == 25
    assert "no salary" in salary["detail"]


def test_a_foreign_currency_cannot_be_compared_to_his_minimum(client):
    salary = _factor(_match_of(client, salary_min=50000, salary_max=70000, salary_currency="USD"),
                     "Salary")
    assert salary["score"] == 25
    assert "cannot be compared" in salary["detail"]


def test_the_cv_proves_a_skill_he_never_rated(client):
    """A CV paragraph counts as evidence even when the skills list omits that tool."""
    match = _match_of(client, description="You will write Flutter and Firebase here.",
                      resume_text="Built iOS screens in Flutter with Firebase and Dart.")
    skills = _factor(match, "Skills")
    assert {"Flutter", "Firebase"} <= set(match["matched_skills"])
    assert "proven by your CV" in skills["detail"]
    assert skills["score"] == 80


# ---------- the scorer reads the CV the way a hiring reviewer does ----------


def test_the_roles_already_on_his_cv_count_as_a_fit_without_a_wishlist(client):
    """He never typed desired titles, but his CV says he sold in a store for years."""
    cv = dict(desired_titles=[], target_levels=["Junior"], city="Cairo")
    skills = [dict(name="POS", level=4), dict(name="Cash Handling", level=4)]
    history = [dict(title="Retail Sales Representative", company="Store",
                    description="Sold goods and handled the till.")]

    match = _match_of(client, title="Retail Sales Associate", description="", profile=cv,
                      skills=skills, experiences=history)
    assert _factor(match, "Job title fit")["score"] == 90
    assert "your CV already shows" in _factor(match, "Job title fit")["detail"]

    away = _match_of(client, title="Warehouse Storekeeper", description="", profile=cv,
                     skills=skills, experiences=history)
    assert _factor(away, "Job title fit")["score"] == 20


def test_a_headline_that_demands_a_tool_his_cv_cannot_show_caps_the_score(client):
    """An ad whose own title says React is not a 71% fit for a CV that never mentions it."""
    match = _match_of(client, title="React Developer",
                      description="You will write Python, ship with Git and run Docker.",
                      profile=dict(desired_titles=["React Developer"]))
    assert "React" in match["hard_gap"]
    assert match["score"] == 64


def test_a_language_in_the_headline_is_not_the_job(client):
    """"Fluent English required" is a plus, not the tool an HR reader rejects a CV over."""
    match = _match_of(client, title="Backend Engineer (Fluent English Required)",
                      description="You will write Python, ship with Git and run Docker.",
                      profile=dict(desired_titles=["Backend Engineer"]))
    assert match["hard_gap"] == ""
    assert match["score"] > 64  # the cap that a real headline gap would have applied


def test_his_own_seniority_replaces_the_target_level_he_never_set(client):
    """No target levels typed, but the CV shows he has already worked as a Senior."""
    match = _match_of(client, title="Sales Lead", experience_level="Senior",
                      profile=dict(target_levels=[]),
                      experiences=[dict(title="Senior Sales Engineer", company="Co")])
    level = _factor(match, "Experience level")
    assert level["score"] == 100
    assert "what your CV shows" in level["detail"]

    by_years = _match_of(client, title="Data Platform Worker", experience_level="Senior",
                         profile=dict(target_levels=[]),
                         skills=[dict(name="Python", level=4, years=6)])
    assert _factor(by_years, "Experience level")["score"] == 100

    one_over = _match_of(client, title="Data Platform Worker", experience_level="Lead",
                         profile=dict(target_levels=[]),
                         skills=[dict(name="Python", level=4, years=1)])
    assert _factor(one_over, "Experience level")["score"] == 55


def test_home_country_falls_back_to_the_number_the_account_was_registered_with():
    from app.models import UserProfile
    from app.services.matching import home_country

    assert home_country(UserProfile(country="", phone="+20 109 672 6081")) == "Egypt"
    assert home_country(UserProfile(country="Egypt", phone="")) == "Egypt"
    assert home_country(UserProfile(country="UAE", phone="+20100000000")) == "UAE"
    assert home_country(UserProfile(country="", phone="")) == ""


def test_an_ad_in_his_country_is_not_outside_every_place_he_chose(client):
    """He left the country field blank, so an Egyptian posting scored as unplaceable."""
    match = _match_of(client, title="Data Platform Worker", location="Cairo", country="Egypt",
                      profile=dict(country="", city="", preferred_locations=[],
                                   phone="+201096726081"))
    location = _factor(match, "Location & remote")
    assert location["score"] == 85
    assert "your country" in location["detail"]


def test_the_city_he_lives_in_is_a_place_even_when_he_listed_none(client):
    match = _match_of(client, title="Data Platform Worker", location="Assiut", country="Egypt",
                      profile=dict(city="Assiut", preferred_locations=[]))
    assert _factor(match, "Location & remote")["score"] == 100



def test_scoring_the_same_posting_twice_gives_the_same_numbers(client):
    """Both the profile reading and each posting's requirements are remembered to keep a
    3,700-job list page fast, so a remembered answer has to be the computed one."""
    first = _match_of(client, title="Backend Engineer",
                      description="Cache sessions with Redis and run the API in Python.")
    second = client.get(f"/api/matches/{first['job_id']}").json()
    assert second == first


def test_an_edit_to_his_skills_is_not_scored_from_the_old_reading(client):
    """The cached reading is keyed by his CV text, so a new skill must move the score."""
    before = _match_of(client, title="Backend Engineer",
                       description="Cache sessions with Redis and run the API in Python.",
                       skills=[dict(name="Python", level=5, years=3)])
    after = _match_of(client, title="Backend Engineer",
                      description="Cache sessions with Redis and run the API in Python.",
                      skills=[dict(name="Python", level=5, years=3), dict(name="Redis", level=5, years=3)])
    assert "Redis" in before["missing_skills"]
    assert _factor(before, "Skills")["score"] < _factor(after, "Skills")["score"]


def test_an_edited_posting_has_its_requirements_re_read():
    from app.models import Job
    from app.services.matching import job_skill_tags

    job = Job(title="Analyst", company="Acme", source="manual",
              description="Track KPIs in Excel.", skills=[])
    assert job_skill_tags(job) == ["Excel"]
    job.description = "Track KPIs in Airtable."
    assert job_skill_tags(job) == []
