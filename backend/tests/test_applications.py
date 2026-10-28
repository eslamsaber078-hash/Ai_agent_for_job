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


PREPARE_KIND_ORDER = ["cv", "cover_letter", "email", "questions", "keywords"]


def test_prepare_writes_the_whole_pack_into_the_tracker(client):
    r = client.post("/api/applications/prepare", json=dict(job_id=1, notes="want this one"))
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["application"]["status"] == "Preparing"
    assert data["application"]["job"]["id"] == 1
    assert data["application"]["notes"] == "want this one"
    assert [m["kind"] for m in data["materials"]] == PREPARE_KIND_ORDER
    assert all(m["content"].strip() for m in data["materials"])
    # Nothing is sent by this endpoint — it only prepares, and says where the ad wants it.
    assert data["apply_channel"] in ("email", "company-link", "listing", "unknown")
    assert data["apply_note"]


def test_prepare_twice_refreshes_instead_of_stacking(client):
    first = client.post("/api/applications/prepare", json=dict(job_id=2)).json()
    app_id = first["application"]["id"]
    second = client.post("/api/applications/prepare", json=dict(job_id=2)).json()
    assert second["application"]["id"] == app_id
    assert len(second["materials"]) == len(PREPARE_KIND_ORDER)
    materials = client.get(f"/api/applications/{app_id}/materials").json()
    assert len(materials) == len(PREPARE_KIND_ORDER)
    assert client.get("/api/applications/99999/materials").status_code == 404


def test_a_draft_made_in_the_assistant_lands_on_the_tracked_application(client):
    app = client.post("/api/applications", json=dict(job_id=3, status="Interested")).json()
    client.post("/api/assistant/generate", json=dict(job_id=3, kind="cv"))
    materials = client.get(f"/api/applications/{app['id']}/materials").json()
    assert [m["kind"] for m in materials] == ["cv"]


def test_prepare_rejects_a_job_that_does_not_exist(client):
    assert client.post("/api/applications/prepare", json=dict(job_id=999999)).status_code == 404


def test_deleting_an_application_takes_its_pack_with_it(client):
    # Otherwise the five documents stay filed under the job, and a second Track + Prepare
    # lists the old pack next to the new one in the Assistant.
    prepared = client.post("/api/applications/prepare", json=dict(job_id=3)).json()
    app_id = prepared["application"]["id"]
    assert client.delete(f"/api/applications/{app_id}").status_code == 200
    assert client.get(f"/api/applications/{app_id}/materials").status_code == 404
    assert client.get("/api/assistant/materials/3").json() == []

    again = client.post("/api/applications/prepare", json=dict(job_id=3)).json()
    assert len(again["materials"]) == len(PREPARE_KIND_ORDER)
    assert len(client.get("/api/assistant/materials/3").json()) == len(PREPARE_KIND_ORDER)


def test_cv_pdf_download_is_a_real_pdf(client):
    prepared = client.post("/api/applications/prepare", json=dict(job_id=1)).json()
    app_id = prepared["application"]["id"]
    r = client.get(f"/api/applications/{app_id}/materials/cv/pdf")
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF-")
    # No "attachment" disposition: Chrome rejects a CORS fetch whose response carries
    # one, and the browser names the saved file itself.
    assert "content-disposition" not in r.headers
    # The internal "what the ad asks for that you do not show" notes are for his eyes,
    # and the employer's copy must not carry them.
    assert b"WHAT THIS AD ASKS FOR" not in r.content
    assert b"ATS READINESS CHECK" not in r.content


def test_pdf_of_an_unprepared_kind_is_404(client):
    prepared = client.post("/api/applications/prepare", json=dict(job_id=1)).json()
    app_id = prepared["application"]["id"]
    assert client.get(f"/api/applications/{app_id}/materials/cv/pdf").status_code == 200
    assert client.get("/api/applications/99999/materials/cv/pdf").status_code == 404
