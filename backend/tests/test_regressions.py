"""Regression tests for bugs found in the post-build audit."""
from app.database import SessionLocal
from app.models import Application, Job, SavedJob, Skill
from app.services import merge_duplicate_jobs
from app.services.providers import ProviderJob, ingest_jobs


def test_refresh_is_idempotent(client):
    before = client.get("/api/jobs", params={"page_size": 1}).json()["total"]
    client.post("/api/jobs/refresh", json=["remotive"])
    after = client.get("/api/jobs", params={"page_size": 1}).json()["total"]
    assert after == before
    client.post("/api/jobs/refresh", json=["remotive"])
    assert client.get("/api/jobs", params={"page_size": 1}).json()["total"] == before


def test_merge_duplicate_jobs_repoints_saved_and_applied():
    db = SessionLocal()
    try:
        original = db.query(Job).filter(Job.source == "remotive").first()
        clone = Job(
            external_id=original.external_id + "-clone",
            source="remotive", title=original.title, company=original.company,
            location=original.location, description=original.description, url=original.url,
            skills=original.skills, is_demo=False,
        )
        db.add(clone)
        db.commit()
        db.add(SavedJob(job_id=clone.id))
        db.add(Application(job_id=clone.id, status="Applied"))
        db.commit()
        clone_id = clone.id

        assert merge_duplicate_jobs(db) >= 1
        assert db.get(Job, clone_id) is None
        assert db.query(SavedJob).filter(SavedJob.job_id == original.id).count() == 1
        assert db.query(Application).filter(Application.job_id == original.id).count() == 1
        assert db.query(Job).filter(Job.external_id == original.external_id).count() == 1
    finally:
        db.close()


def test_duplicate_ids_in_one_batch_are_ingested_once():
    db = SessionLocal()
    try:
        jobs = [
            ProviderJob(source="batch", external_id="same-1", title="T", company="C"),
            ProviderJob(source="batch", external_id="same-1", title="T", company="C"),
        ]
        new, _ = ingest_jobs(db, jobs)
        assert new == 1
    finally:
        db.close()


def test_search_treats_wildcards_as_literal_text(client):
    assert client.get("/api/jobs", params={"q": "%_%", "page_size": 100}).json()["total"] == 0
    assert client.get("/api/jobs", params={"q": "flutter", "page_size": 100}).json()["total"] > 5


def test_partial_profile_update_keeps_other_fields(client):
    client.put("/api/profile", json={"full_name": "Ahmed Hassan", "email": "a@b.com"})
    client.put("/api/profile", json={"city": "Cairo"})
    profile = client.get("/api/profile").json()
    assert profile["full_name"] == "Ahmed Hassan"
    assert profile["email"] == "a@b.com"
    assert profile["city"] == "Cairo"


def test_profile_rejects_oversized_text(client):
    assert client.put("/api/profile", json={"summary": "s" * 50000}).status_code == 422


def test_empty_skill_name_has_its_own_message(client):
    r = client.put("/api/profile/skills", json=[{"name": "", "level": 3, "years": 1}])
    assert r.status_code == 422
    assert "name" in r.json()["detail"].lower()


def test_automation_rejects_unknown_source(client):
    r = client.put("/api/automation/settings", json={"sources": ["not_a_source"]})
    assert r.status_code == 422
    assert "not_a_source" in r.json()["detail"]


def test_import_rejects_an_unknown_site_name(client):
    """A typo used to be dropped silently and the run looked successful."""
    for url in ("/api/jobs/refresh", "/api/automation/run"):
        r = client.post(url, json=["remotiv"])
        assert r.status_code == 422, (url, r.text)
        assert "remotiv" in r.json()["detail"]


def test_import_refuses_when_no_site_is_ticked(client):
    """Zero ticked sites must not quietly import all of them."""
    client.put("/api/automation/settings", json={
        "enabled": True, "titles": ["Flutter"], "skills": [], "locations": [],
        "remote_only": False, "interval_minutes": 360, "min_match_score": 40, "sources": [],
    })
    r = client.post("/api/jobs/refresh", json=[])
    assert r.status_code == 422
    assert "ticked" in r.json()["detail"].lower()
    assert client.post("/api/automation/run", json=[]).status_code == 422


def test_run_log_reports_min_match_score(client):
    client.put("/api/profile", json={"full_name": "Ahmed", "summary": "Flutter dev"})
    client.put("/api/automation/settings", json={
        "enabled": True, "titles": ["Flutter"], "skills": [], "locations": [],
        "remote_only": False, "interval_minutes": 360, "min_match_score": 40, "sources": ["remotive"],
    })
    log = client.post("/api/automation/run").json()["log"]
    assert "minimum match score of 40" in log


def test_list_endpoints_do_not_call_ai_per_job(client, monkeypatch):
    from app.models import Skill
    from app.services import matching as matching_service

    monkeypatch.setattr(matching_service.ai, "openai_available", lambda: True)
    calls: list[int] = []

    def fake_narrative(job, profile, facts, lang="en"):
        calls.append(job.id)
        return None

    monkeypatch.setattr(matching_service, "_narrative_ai", fake_narrative)
    client.put("/api/profile", json={
        "full_name": "Ahmed", "summary": "Flutter developer",
        "desired_titles": ["Flutter Developer"],
    })
    db = SessionLocal()
    try:
        db.add(Skill(profile_id=1, name="Flutter", level=4, years=1))
        db.commit()
    finally:
        db.close()

    assert client.get("/api/matches", params={"limit": 20}).status_code == 200
    assert calls == []
    assert client.get("/api/dashboard/stats").status_code == 200
    assert calls == []

    job_id = client.get("/api/jobs", params={"page_size": 1}).json()["items"][0]["id"]
    client.get(f"/api/matches/{job_id}")
    assert calls == [job_id]


def test_saved_jobs_carry_a_match_score(client):
    client.put("/api/profile", json={"full_name": "Ahmed", "summary": "Flutter developer"})
    db = SessionLocal()
    try:
        db.add(Skill(profile_id=1, name="Flutter", level=4, years=1))
        db.commit()
    finally:
        db.close()
    job_id = client.get("/api/jobs", params={"page_size": 1}).json()["items"][0]["id"]
    client.post(f"/api/jobs/{job_id}/save")
    saved = client.get("/api/saved-jobs").json()
    assert len(saved) == 1
    assert isinstance(saved[0]["score"], int)
    assert 0 <= saved[0]["score"] <= 100


def test_generated_material_history_keeps_template_flag(client):
    """History must not relabel template output as AI-generated."""
    job_id = client.get("/api/jobs", params={"page_size": 1}).json()["items"][0]["id"]
    generated = client.post("/api/assistant/generate", json={"job_id": job_id, "kind": "cover_letter"}).json()
    materials = client.get(f"/api/assistant/materials/{job_id}").json()
    assert len(materials) == 1
    assert materials[0]["template_based"] == generated["template_based"]
    assert client.delete(f"/api/assistant/materials/{materials[0]['id']}").status_code == 200
    assert client.get(f"/api/assistant/materials/{job_id}").json() == []


def test_schema_upgrade_adds_missing_column(tmp_path):
    """An existing database predating template_based must be patched, not recreated."""
    from sqlalchemy import create_engine, inspect, text

    from app.database import ensure_schema_upgrades

    legacy = create_engine(f"sqlite:///{(tmp_path / 'legacy.db').as_posix()}")
    with legacy.begin() as conn:
        conn.execute(text(
            "CREATE TABLE generated_materials (id INTEGER PRIMARY KEY, job_id INTEGER, "
            "application_id INTEGER, kind VARCHAR(50), content TEXT, created_at DATETIME)"
        ))

    ensure_schema_upgrades(legacy)
    cols = {c["name"] for c in inspect(legacy).get_columns("generated_materials")}
    assert "template_based" in cols

    ensure_schema_upgrades(legacy)  # idempotent
    assert {c["name"] for c in inspect(legacy).get_columns("generated_materials")} == cols


def test_schema_upgrade_skips_absent_table(tmp_path):
    from sqlalchemy import create_engine

    from app.database import ensure_schema_upgrades

    empty = create_engine(f"sqlite:///{(tmp_path / 'empty.db').as_posix()}")
    ensure_schema_upgrades(empty)  # must not raise


def test_patch_application_can_clear_a_date(client):
    job_id = client.get("/api/jobs", params={"page_size": 1}).json()["items"][0]["id"]
    created = client.post("/api/applications", json={
        "job_id": job_id, "status": "Applied", "follow_up_date": "2026-11-01T09:00:00",
    }).json()
    assert created["follow_up_date"] is not None

    cleared = client.patch(f"/api/applications/{created['id']}", json={"follow_up_date": None}).json()
    assert cleared["follow_up_date"] is None
    # a patch that omits the field must not wipe it
    client.patch(f"/api/applications/{created['id']}", json={"notes": "called back"})
    assert client.patch(f"/api/applications/{created['id']}", json={"status": "Interview"}).json()["follow_up_date"] is None


def test_first_run_ticks_the_registered_sources(client):
    """An empty sources list silently means 'everything', which the UI cannot show ticked."""
    from app.models import SearchPreference
    from app.services import REGISTRY, ensure_sources

    db = SessionLocal()
    try:
        pref = db.get(SearchPreference, 1) or SearchPreference(id=1)
        pref.sources = []
        db.add(pref)
        db.commit()
        ensure_sources(db)
        assert set(pref.sources) == set(REGISTRY)
        assert {"himalayas", "workingnomads"} <= set(pref.sources)  # newly added sites tick too

        pref.sources = ["remotive"]
        db.commit()
        ensure_sources(db)  # never overwrites a user's choice
        assert pref.sources == ["remotive"]
    finally:
        db.close()


def test_api_timestamps_carry_the_utc_offset(client):
    """A naive ISO string is read by the browser as local time, shifting every posting."""
    from datetime import datetime, timezone

    r = client.get("/api/jobs", params={"page_size": 1})
    item = r.json()["items"][0]
    posted = datetime.fromisoformat(item["first_seen"])
    assert posted.tzinfo is not None
    assert abs((datetime.now(timezone.utc) - posted).total_seconds()) < 3600
