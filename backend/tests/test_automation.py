SETTINGS = dict(
    enabled=True,
    titles=["Flutter Developer", "Python Developer"],
    skills=["Flutter", "Python"],
    locations=["Cairo", "Remote"],
    remote_only=False,
    interval_minutes=60,
    min_match_score=50,
    sources=["remotive"],
)


def test_settings_default_and_update(client):
    r = client.get("/api/automation/settings")
    assert r.status_code == 200
    assert r.json()["enabled"] is False

    r = client.put("/api/automation/settings", json=SETTINGS)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["enabled"] is True
    assert data["titles"] == SETTINGS["titles"]
    assert data["scheduler_running"] is True  # interval job registered

    # persisted
    data2 = client.get("/api/automation/settings").json()
    assert data2["titles"] == SETTINGS["titles"]


def test_settings_validation(client):
    r = client.put("/api/automation/settings", json={**SETTINGS, "interval_minutes": 1})
    assert r.status_code == 422
    r = client.put("/api/automation/settings", json={**SETTINGS, "min_match_score": 150})
    assert r.status_code == 422


def test_disable_removes_job(client):
    client.put("/api/automation/settings", json=SETTINGS)
    assert client.get("/api/automation/settings").json()["scheduler_running"] is True
    client.put("/api/automation/settings", json={**SETTINGS, "enabled": False})
    assert client.get("/api/automation/settings").json()["scheduler_running"] is False


def test_manual_run_ignores_schedule_toggle(client):
    """"Run now" is an explicit user action, so it searches even when scheduling is off."""
    client.put("/api/automation/settings", json={**SETTINGS, "enabled": False})
    r = client.post("/api/automation/run", json=["remotive"])
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "success"
    assert "disabled" not in data["log"].lower()
    assert "minimum match score" in data["log"].lower()


def test_scheduled_run_respects_toggle(client):
    from app.database import SessionLocal
    from app.services import run_search_now

    client.put("/api/automation/settings", json={**SETTINGS, "enabled": False})
    db = SessionLocal()
    try:
        run = run_search_now(db, trigger="scheduled")
        status, log = run.status, run.log
    finally:
        db.close()
    assert status == "success"
    assert "disabled" in log.lower()


def test_manual_run_with_settings_discovers_jobs(client):
    client.put("/api/automation/settings", json=SETTINGS)
    r = client.post("/api/automation/run", json=["remotive"])
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "success"
    assert data["jobs_found"] >= 0
    assert "Remotive" in data["log"]


def test_runs_are_listed(client):
    assert client.put("/api/profile", json={"desired_titles": ["Flutter Developer"]}).status_code == 200
    client.post("/api/automation/run", json=["remotive"])
    r = client.get("/api/automation/runs")
    assert r.status_code == 200
    runs = r.json()
    assert len(runs) >= 1
    assert runs[0]["trigger"] == "manual"
    assert runs[0]["status"] == "success"
