from datetime import datetime, timedelta, timezone

APPLICATION = dict(
    job_id=1, status="Interested", notes="cool company",
    follow_up_date=(datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
)


def test_create_application(client):
    r = client.post("/api/applications", json=APPLICATION)
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["status"] == "Interested"
    assert data["job"]["id"] == 1


def test_duplicate_application_rejected(client):
    assert client.post("/api/applications", json=APPLICATION).status_code == 201
    r = client.post("/api/applications", json=APPLICATION)
    assert r.status_code == 409


def test_invalid_status_rejected(client):
    r = client.post("/api/applications", json=dict(job_id=1, status="Flying"))
    assert r.status_code == 422
    r = client.post("/api/applications", json=dict(job_id=999999, status="Applied"))
    assert r.status_code == 404


def test_status_update_sets_applied_date(client):
    client.post("/api/applications", json=dict(job_id=1, status="Discovered"))
    r = client.patch("/api/applications/1", json=dict(status="Applied"))
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "Applied"
    assert data["date_applied"] is not None


def test_update_fields_and_filter_by_status(client):
    client.post("/api/applications", json=dict(job_id=1, status="Discovered"))
    client.post("/api/applications", json=dict(job_id=2, status="Interview"))
    r = client.get("/api/applications", params={"status": "Interview"})
    items = r.json()
    assert len(items) == 1
    assert items[0]["job"]["id"] == 2
    r = client.patch("/api/applications/1", json=dict(notes="updated note", follow_up_date=None))
    assert r.status_code == 200
    assert r.json()["notes"] == "updated note"


def test_delete_application(client):
    client.post("/api/applications", json=dict(job_id=1, status="Discovered"))
    r = client.delete("/api/applications/1")
    assert r.status_code == 200
    assert client.get("/api/applications").json() == []
    assert client.delete("/api/applications/1").status_code == 404
