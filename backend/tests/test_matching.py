from app.database import SessionLocal
from app.models import Job, UserProfile


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
