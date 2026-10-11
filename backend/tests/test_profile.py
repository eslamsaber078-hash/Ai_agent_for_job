PROFILE = dict(
    full_name="Ahmed Hassan", email="ahmed@example.com", phone="+20100000000",
    country="Egypt", city="Cairo", summary="Flutter developer",
    desired_titles=["Flutter Developer"], preferred_locations=["Cairo"],
    remote_preference="open", work_types=["Full-time"],
    target_levels=["Junior"], languages=["Arabic", "English"],
)


def test_profile_persistence(client):
    r = client.put("/api/profile", json=PROFILE)
    assert r.status_code == 200
    data = r.json()
    assert data["full_name"] == "Ahmed Hassan"
    assert data["email"] == "ahmed@example.com"
    # read back
    data2 = client.get("/api/profile").json()
    assert data2["full_name"] == "Ahmed Hassan"


def test_replace_skills(client):
    r = client.put("/api/profile/skills", json=[
        dict(name="Flutter", level=4, years=2),
        dict(name="Dart", level=3),
    ])
    assert r.status_code == 200
    skills = r.json()["skills"]
    assert {s["name"] for s in skills} == {"Flutter", "Dart"}
    # replace entirely
    r = client.put("/api/profile/skills", json=[dict(name="Python", level=2)])
    assert {s["name"] for s in r.json()["skills"]} == {"Python"}


def test_invalid_skill_rejected(client):
    r = client.put("/api/profile/skills", json=[dict(name="Flutter", level=99)])
    assert r.status_code == 422
    r = client.put("/api/profile/skills", json=[dict(level=3)])
    assert r.status_code == 422


def test_experience_education_projects(client):
    r = client.put("/api/profile/experiences", json=[dict(
        title="Freelance Dev", company="Self", current=True, description="Built apps",
    )])
    assert r.status_code == 200
    assert r.json()["experiences"][0]["title"] == "Freelance Dev"
    client.put("/api/profile/education", json=[dict(degree="BSc", institution="Cairo Uni")])
    r = client.put("/api/profile/projects", json=[dict(name="App", technologies=["Flutter", "Dart"])])
    assert r.json()["projects"][0]["technologies"] == ["Flutter", "Dart"]
    data = client.get("/api/profile").json()
    assert len(data["experiences"]) == 1
    assert len(data["education"]) == 1
    assert len(data["projects"]) == 1


def test_resume_upload_rejects_bad_type(client):
    r = client.post("/api/profile/resume", files={"file": ("evil.exe", b"MZ...", "application/octet-stream")})
    assert r.status_code == 422


def test_resume_upload_txt_and_delete(client):
    r = client.post("/api/profile/resume", files={"file": ("resume.txt", b"Ahmed Hassan - Flutter Developer", "text/plain")})
    assert r.status_code == 200
    data = r.json()
    assert data["resume_filename"] == "resume.txt"
    assert "Flutter" in (data["resume_text"] or "")
    r = client.delete("/api/profile/resume")
    assert r.status_code == 200
    assert r.json()["resume_filename"] is None


def _docx(paragraphs: list[str]) -> bytes:
    import io
    import zipfile

    body = "".join(f'<w:p><w:r><w:t>{p}</w:t></w:r></w:p>' for p in paragraphs)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        archive.writestr("word/document.xml", f'<w:document>{body}</w:document>')
    return buf.getvalue()


def test_docx_resume_is_read_as_text(client):
    """A .docx CV is the common case; without parsing it, matching runs blind."""
    r = client.post("/api/profile/resume", files={
        "file": ("cv.docx", _docx(["Ahmed Hassan", "Flutter &amp; Dart developer", "Cairo, Egypt"]),
                 "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    })
    assert r.status_code == 200
    text = r.json()["resume_text"]
    assert "Ahmed Hassan" in text
    assert "Flutter & Dart developer" in text
    assert "\n" in text


def test_fake_docx_does_not_crash(client):
    r = client.post("/api/profile/resume", files={"file": ("cv.docx", b"not a zip at all", "application/octet-stream")})
    assert r.status_code == 200
    assert r.json()["resume_filename"] == "cv.docx"
    assert r.json()["resume_text"] is None


def test_raw_dict_fields_cannot_crash_the_profile_writers(client):
    """These endpoints take bare dicts, so junk values must not reach SQLite."""
    r = client.put("/api/profile/experiences", json=[dict(
        title="Dev", company="Self", start_date={"year": 2024}, end_date="", current=True,
    )])
    assert r.status_code == 200
    exp = r.json()["experiences"][0]
    assert exp["start_date"] is None and exp["end_date"] is None

    r = client.put("/api/profile/skills", json=[dict(name="Flutter", level=3, years=250)])
    assert r.status_code == 422
