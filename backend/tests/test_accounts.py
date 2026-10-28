"""Every account is a separate world: own profile, own jobs, own tracker, own imports."""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import Job, UserProfile
from app.services import providers as providers_mod, run_search_now
from app.services.providers import ProviderJob

HEADERS = {"X-Requested-With": "XMLHttpRequest"}
SECOND_PHONE = "01099999999"
SECOND_PASSWORD = "another-password-1"


@pytest.fixture
def second_client():
    other = TestClient(app)
    other.headers["X-Requested-With"] = "XMLHttpRequest"
    response = other.post(
        "/api/auth/register",
        json={"name": "Second Person", "phone": SECOND_PHONE, "password": SECOND_PASSWORD},
        headers=HEADERS,
    )
    assert response.status_code == 201, response.text
    try:
        yield other
    finally:
        other.close()


class FakeProvider(providers_mod.BaseProvider):
    name = "fake"
    label = "Fake board"

    def fetch(self, titles, skills, locations, remote_only):
        return [ProviderJob(
            source="fake", external_id="same-1", title="Backend Developer",
            company="Acme", location="Cairo", country="Egypt",
            url="https://example.test/1", posted_date=datetime.now(timezone.utc),
        )]


def test_second_account_starts_empty_and_sees_none_of_the_first_accounts_data(client, second_client):
    a_jobs = client.get("/api/jobs").json()
    assert a_jobs["total"] > 0
    job_id = a_jobs["items"][0]["id"]

    b_me = second_client.get("/api/auth/me").json()
    a_me = client.get("/api/auth/me").json()
    assert b_me["profile_id"] != a_me["profile_id"]

    assert second_client.get("/api/jobs").json()["total"] == 0
    assert second_client.get("/api/jobs/light").json() == []
    assert second_client.get("/api/jobs/filters").json() == {"levels": [], "employment_types": [], "sources": []}
    assert second_client.get("/api/dashboard/stats").json()["total_jobs"] == 0
    matches = second_client.get("/api/matches").json()
    assert matches["total"] == 0 and matches["profile_empty"] is True
    assert second_client.get("/api/applications").json() == []
    assert second_client.get("/api/saved-jobs").json() == []
    assert second_client.get("/api/automation/runs").json() == []

    b_profile = second_client.get("/api/profile").json()
    assert b_profile["id"] == b_me["profile_id"]
    assert b_profile["full_name"] == "Second Person"
    assert b_profile["skills"] == [] and b_profile["experiences"] == []
    assert b_profile["resume_text"] is None

    # The first account's rows are invisible and untouchable.
    assert second_client.get(f"/api/jobs/{job_id}").status_code == 404
    assert second_client.post("/api/applications", json={"job_id": job_id}).status_code == 404
    assert second_client.post(f"/api/jobs/{job_id}/save").status_code == 404
    assert second_client.delete(f"/api/jobs/{job_id}/save").status_code == 404
    assert second_client.post("/api/assistant/generate", json={"job_id": job_id, "kind": "summary"}).status_code == 404
    assert second_client.get(f"/api/assistant/materials/{job_id}").status_code == 404

    app_row = client.post("/api/applications", json={"job_id": job_id}).json()
    assert client.post(f"/api/jobs/{job_id}/save").status_code == 200
    assert second_client.get("/api/applications").json() == []
    assert second_client.patch(f"/api/applications/{app_row['id']}", json={"status": "Interview"}).status_code == 404
    assert second_client.delete(f"/api/applications/{app_row['id']}").status_code == 404
    assert second_client.get(f"/api/applications/{app_row['id']}/materials").status_code == 404
    assert second_client.get(f"/api/applications/{app_row['id']}/materials/cv/pdf").status_code == 404

    # Editing one profile never edits the other.
    before = client.get("/api/profile").json()
    changed = dict(b_profile, full_name="Renamed Person", desired_titles=["Backend Developer"])
    assert second_client.put("/api/profile", json=changed).status_code == 200
    assert second_client.get("/api/profile").json()["full_name"] == "Renamed Person"
    assert client.get("/api/profile").json() == before

    assert client.get("/api/applications").json()[0]["id"] == app_row["id"]
    assert len(client.get("/api/saved-jobs").json()) == 1


def test_empty_account_import_is_refused_until_it_has_its_own_terms(client, second_client, monkeypatch):
    b_me = second_client.get("/api/auth/me").json()
    b_profile_id = b_me["profile_id"]

    # No titles and no skills: the import explains what to add and creates no rows.
    refused = second_client.post("/api/jobs/refresh", json=["remotive"])
    assert refused.status_code == 422
    assert "Add desired job titles or skills" in refused.json()["detail"]
    with SessionLocal() as db:
        run = run_search_now(db, trigger="manual", sources=["remotive"], profile_id=b_profile_id)
        assert run.status == "failed"
        assert "Add desired job titles or skills" in run.error
        assert db.query(Job).filter(Job.profile_id == b_profile_id).count() == 0

    # The second account now describes its own profession and imports.
    assert second_client.put("/api/profile", json={
        "desired_titles": ["Backend Developer"],
    }).status_code == 200
    assert second_client.put("/api/profile/skills", json=[{"name": "Python", "level": 4}]).status_code == 200
    monkeypatch.setattr(providers_mod, "get_enabled_providers",
                        lambda db, requested=None: [FakeProvider()])

    with SessionLocal() as db:
        a_before = db.query(Job).filter(Job.profile_id == 1).count()
        b_run = run_search_now(db, trigger="manual", sources=["remotive"], profile_id=b_profile_id)
        assert b_run.status == "success", b_run.error
        assert b_run.jobs_found == 1
        b_jobs = db.query(Job).filter(Job.profile_id == b_profile_id).all()
        assert [(j.source, j.external_id, j.title) for j in b_jobs] == [("fake", "same-1", "Backend Developer")]
        assert db.query(Job).filter(Job.profile_id == 1).count() == a_before

        # The same rule applies to the fixture owner: no terms of their own, no import.
        assert client.put("/api/profile", json={"desired_titles": ["Backend Developer"]}).status_code == 200
        a_run = run_search_now(db, trigger="manual", sources=["remotive"], profile_id=1)
        assert a_run.status == "success", a_run.error
        assert a_run.jobs_found == 1
        assert db.query(Job).filter(Job.source == "fake", Job.external_id == "same-1").count() == 2

    # Both sides only list their own copy.
    b_items = second_client.get("/api/jobs").json()["items"]
    assert [(j["source"], j["title"]) for j in b_items] == [("fake", "Backend Developer")]
    a_items = client.get("/api/jobs").json()["items"]
    assert any(j["source"] == "fake" for j in a_items)
    assert all(j["id"] not in {j2["id"] for j2 in b_items} for j in a_items)

    # The new account's profile row is its own, not the legacy profile.
    with SessionLocal() as db:
        assert db.get(UserProfile, b_profile_id).full_name == "Second Person"
