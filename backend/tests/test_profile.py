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


def test_a_binary_doc_renamed_to_docx_gets_a_clear_convert_message(client):
    # Word 97-2003 files start with the OLE2 magic; storing them as "0 characters"
    # made his CV look unreadable with no explanation.
    ole2 = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 64
    r = client.post("/api/profile/resume", files={"file": ("cv.docx", ole2, "application/octet-stream")})
    assert r.status_code == 422
    assert "Save As" in r.json()["detail"]
    # The profile keeps the previous upload, not a broken new one
    assert client.get("/api/profile").json()["resume_filename"] is None


def test_a_legacy_doc_upload_is_turned_away_with_the_same_message(client):
    r = client.post("/api/profile/resume", files={"file": ("cv.doc", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 64,
                                                        "application/msword")})
    assert r.status_code == 422
    assert "Save As" in r.json()["detail"]


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


CV_TEXT = """Ahmed Hassan
Cairo, Egypt
Phone: +20 100 000 0000
Email: ahmed@example.com
LinkedIn: linkedin.com/in/ahmed
SUMMARY
Flutter developer with four years of experience.
EXPERIENCE
Mobile Developer - Acme Apps | March 2021
Built Flutter apps for iOS and Android.
TECHNICAL SKILLS
- Flutter
- Dart
- REST APIs
EDUCATION
BSc Computer Science, Cairo University, 2019
"""


def test_resume_parser_reads_literal_facts():
    from app.services.resume_parse import parse_resume

    out = parse_resume(CV_TEXT)
    assert out["fields"]["full_name"] == "Ahmed Hassan"
    assert out["fields"]["email"] == "ahmed@example.com"
    assert out["fields"]["phone"] == "+201000000000"
    assert out["fields"]["city"] == "Cairo"
    assert out["fields"]["country"] == "Egypt"
    assert out["fields"]["linkedin"] == "linkedin.com/in/ahmed"
    assert "Flutter developer" in out["fields"]["summary"]
    assert out["skills"] == ["Flutter", "Dart", "REST APIs"]
    exp = out["experiences"][0]
    assert exp["title"] == "Mobile Developer"
    assert exp["company"] == "Acme Apps"
    assert exp["start_date"] == "2021-03" and exp["end_date"] is None
    assert "Built Flutter apps" in exp["description"]
    edu = out["education"][0]
    assert edu["degree"] == "BSc Computer Science"
    assert edu["institution"] == "Cairo University"
    assert edu["end_date"] == "2019"


def test_resume_parser_invents_nothing():
    from app.services.resume_parse import parse_resume

    out = parse_resume("Ahmed Hassan\nCairo, Egypt\nEmail: ahmed@example.com\n")
    assert out["skills"] == [] and out["experiences"] == [] and out["education"] == []
    assert "summary" not in out["fields"]


def test_resume_autofill_preview_needs_extracted_text(client):
    r = client.post("/api/profile/resume/autofill")
    assert r.status_code == 422


def test_resume_autofill_preview_and_apply(client):
    client.put("/api/profile/skills", json=[dict(name="Flutter", level=4)])
    upload = client.post("/api/profile/resume", files={"file": ("cv.txt", CV_TEXT.encode(), "text/plain")})
    assert upload.status_code == 200

    preview = client.post("/api/profile/resume/autofill")
    assert preview.status_code == 200
    data = preview.json()
    assert data["fields"]["email"] == "ahmed@example.com"
    assert "Dart" in data["skills"]
    assert data["experiences"][0]["title"] == "Mobile Developer"

    payload = {
        "fields": {"email": "ahmed@example.com", "city": "Cairo"},
        "skills": data["skills"],
        "experiences": data["experiences"],
        "education": data["education"],
    }
    applied = client.post("/api/profile/resume/autofill/apply", json=payload)
    assert applied.status_code == 200
    profile = applied.json()
    assert profile["email"] == "ahmed@example.com"
    assert {s["name"] for s in profile["skills"]} == {"Flutter", "Dart", "REST APIs"}
    assert profile["skills"][0]["level"] == 4  # the existing row is untouched
    assert len(profile["experiences"]) == 1
    assert len(profile["education"]) == 1

    again = client.post("/api/profile/resume/autofill/apply", json=payload).json()
    assert len(again["skills"]) == 3
    assert len(again["experiences"]) == 1
    assert len(again["education"]) == 1


def test_resume_autofill_ignores_unknown_fields(client):
    client.post("/api/profile/resume", files={"file": ("cv.txt", CV_TEXT.encode(), "text/plain")})
    r = client.post("/api/profile/resume/autofill/apply", json={"fields": {"password_hash": "x", "city": "Cairo"}})
    assert r.status_code == 200
    assert r.json()["city"] == "Cairo"
    assert client.get("/api/profile").json()["city"] == "Cairo"


def test_real_resume_docx_extracts_and_parses(client):
    """Regression for his own CV: a .docx with en dashes and a courses section."""
    paragraphs = [
        "Eslam saber badr ramadan", "Assiut, Egypt",
        "Phone: +201096726081 | +201501124322",
        "Email: eslamsaber078@gmail.com",
        "LinkedIn: linkedin.com/in/eslam-saber-46226b342",
        "SUMMARY", "Commerce graduate specializing in Accounting.",
        "EXPERIENCE", "Call Center \u2013 National Bank of Egypt | August 2025",
        "Handled customer inquiries.", "EDUCATION",
        "Bachelor of Commerce \u2013 Accounting department, Assiut University | 2023 | Grade: Good",
        "COURSES & CERTIFICATIONS", "Basics of Financial Accounting \u2013 2024",
        "Technical Skills", "- CRM Systems", "- Customer Relationship Management",
    ]
    upload = client.post("/api/profile/resume", files={
        "file": ("cv.docx", _docx(paragraphs),
                 "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    })
    assert upload.status_code == 200
    data = client.post("/api/profile/resume/autofill").json()
    assert data["fields"]["full_name"] == "Eslam saber badr ramadan"
    assert data["fields"]["phone"] == "+201096726081"
    assert data["fields"]["city"] == "Assiut"
    assert data["experiences"][0]["company"] == "National Bank of Egypt"
    assert data["experiences"][0]["start_date"] == "2025-08"
    assert data["education"][0]["institution"] == "Assiut University"
    assert data["education"][0]["field"] == "Accounting department"
    assert "CRM Systems" in data["skills"]
