"""The ranked list: shared between pages, fully explained where it is shown, and never
stale after the owner writes something."""
from app.services import scored
from app.services.matching import compute_match
from app.database import SessionLocal
from app.models import Job, UserProfile


def _flutter_profile(client):
    r = client.put("/api/profile", json=dict(
        full_name="Ahmed", country="Egypt", city="Cairo",
        desired_titles=["Flutter Developer", "Mobile Developer"],
        preferred_locations=["Cairo", "Remote"], remote_preference="open",
        target_levels=["Intern", "Junior", "Entry"],
        summary="Flutter and Python developer building mobile apps.",
    ))
    assert r.status_code == 200, r.text
    r = client.put("/api/profile/skills", json=[
        dict(name="Flutter", level=4, years=1.5), dict(name="Dart", level=4, years=1.5),
        dict(name="Firebase", level=3, years=1), dict(name="REST APIs", level=3, years=1),
    ])
    assert r.status_code == 200, r.text


def test_returned_matches_keep_the_full_breakdown(client):
    """Ranking is cheap and unexplained; the rows the page shows are not."""
    _flutter_profile(client)
    data = client.get("/api/matches?limit=5").json()
    assert data["items"]
    for item in data["items"]:
        assert len(item["factors"]) == 5
        assert item["why_match"]
        assert item["next_steps"]
        assert item["job"]["title"]


def test_ranking_is_exactly_ordered_and_counted(client):
    _flutter_profile(client)
    data = client.get("/api/matches?limit=200").json()
    scores = [item["score"] for item in data["items"]]
    assert scores == sorted(scores, reverse=True)
    with SessionLocal() as db:
        live = db.query(Job).filter(Job.profile_id == 1, Job.is_active.is_(True)).count()
    assert data["total"] == live


def test_ranking_stays_within_the_minimum_score(client):
    _flutter_profile(client)
    everything = client.get("/api/matches?limit=200").json()["items"]
    cutoff = everything[0]["score"]
    top = client.get(f"/api/matches?min_score={cutoff}&limit=200").json()
    assert top["total"] == sum(1 for item in everything if item["score"] >= cutoff)
    assert all(item["score"] >= cutoff for item in top["items"])


def test_dashboard_and_matches_agree_on_the_best_fit(client):
    _flutter_profile(client)
    best = client.get("/api/dashboard/stats").json()["best_matches"]
    matches = client.get("/api/matches?limit=6").json()["items"]
    assert [row["job_id"] for row in best] == [row["job_id"] for row in matches]


def test_ranking_is_computed_once_per_owner(client, monkeypatch):
    _flutter_profile(client)
    calls = []
    original = scored._rank

    def counting(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(scored, "_rank", counting)
    client.get("/api/matches?limit=5")
    client.get("/api/matches?limit=5")
    client.get("/api/dashboard/stats")
    assert len(calls) == 1


def test_a_profile_edit_replaces_the_ranking(client):
    _flutter_profile(client)
    before = client.get("/api/matches?limit=200").json()["items"]
    # Firebase is listed in his skills and in several postings; the summary never
    # mentions it, so dropping it is visible even though "Flutter" stays in the text.
    assert any("Firebase" in item["matched_skills"] for item in before)
    r = client.put("/api/profile/skills", json=[dict(name="Cooking", level=5)])
    assert r.status_code == 200, r.text
    after = client.get("/api/matches?limit=200").json()["items"]
    assert not any("Firebase" in item["matched_skills"] for item in after)
    assert after[0]["score"] < before[0]["score"]


def test_brief_and_full_scoring_agree(client):
    _flutter_profile(client)
    with SessionLocal() as db:
        profile = db.get(UserProfile, 1)
        jobs = db.query(Job).filter(Job.profile_id == 1).all()
        for job in jobs:
            brief = compute_match(job, profile, use_ai=False, detail=False)
            full = compute_match(job, profile, use_ai=False)
            assert brief["score"] == full["score"]
            assert brief["matched_skills"] == full["matched_skills"]
            assert brief["missing_skills"] == full["missing_skills"]
            assert brief["factors"] == []
            assert brief["why_match"] == ""


def test_search_narrows_the_same_ranking(client):
    _flutter_profile(client)
    data = client.get("/api/matches?q=flutter&limit=200").json()
    assert data["items"]
    assert all("flutter" in f"{i['job']['title']} {i['job']['company']}".lower()
               for i in data["items"])


def test_cache_drops_one_owner_and_keeps_the_other():
    from app.services import cache
    calls = []
    cache.cached(1, "x", 60, lambda: calls.append(1) or "a")
    cache.cached(1, "x", 60, lambda: calls.append(1) or "a")
    cache.cached(2, "x", 60, lambda: calls.append(1) or "b")
    assert calls == [1, 1]
    cache.invalidate(1)
    assert cache.cached(1, "x", 60, lambda: "a2") == "a2"
    assert cache.cached(2, "x", 60, lambda: "b2") == "b"


def test_the_matches_page_is_built_once_until_the_owner_writes(client, monkeypatch):
    """The returned rows carry the full breakdown, which is the costly part of the
    endpoint; a second visit to the same page must not rebuild it."""
    _flutter_profile(client)
    from app.api import matching as matching_api
    calls = []
    original = matching_api.decorate

    def counting(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(matching_api, "decorate", counting)
    client.get("/api/matches?limit=50")
    client.get("/api/matches?limit=50")
    assert len(calls) == 1
    assert client.put("/api/profile/skills", json=[dict(name="Cooking", level=5)]).status_code == 200
    client.get("/api/matches?limit=50")
    assert len(calls) == 2
