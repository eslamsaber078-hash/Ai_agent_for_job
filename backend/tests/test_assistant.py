def _setup_profile(client):
    client.put("/api/profile", json=dict(
        full_name="Ahmed", email="a@b.com", summary="Flutter developer",
        desired_titles=["Flutter Developer"], target_levels=["Junior"],
    ))
    client.put("/api/profile/skills", json=[dict(name="Flutter", level=4), dict(name="Dart", level=3)])


def test_generate_without_key_uses_templates(client):
    _setup_profile(client)
    r = client.post("/api/assistant/generate", json=dict(job_id=1, kind="cover_letter"))
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["kind"] == "cover_letter"
    assert len(data["content"]) > 100
    assert data["template_based"] is True  # no OpenAI key in test env
    assert "review" in data["warning"].lower()


def test_generate_all_kinds(client):
    _setup_profile(client)
    for kind in ["summary", "bullets", "cover_letter", "email", "questions", "keywords", "cv"]:
        r = client.post("/api/assistant/generate", json=dict(job_id=1, kind=kind))
        assert r.status_code == 200, kind
        assert r.json()["content"].strip()


def test_generate_invalid_kind(client):
    r = client.post("/api/assistant/generate", json=dict(job_id=1, kind="poem"))
    assert r.status_code == 422


def test_generate_unknown_job(client):
    r = client.post("/api/assistant/generate", json=dict(job_id=999999, kind="summary"))
    assert r.status_code == 404


def test_generate_never_fabricates_name(client):
    # Empty profile: generated texts must use placeholders, not invented facts
    r = client.post("/api/assistant/generate", json=dict(job_id=1, kind="email"))
    content = r.json()["content"]
    assert "[Your Name]" in content or "[your email]" in content
    assert "Ahmed" not in content


def test_materials_list_and_delete(client):
    _setup_profile(client)
    client.post("/api/assistant/generate", json=dict(job_id=1, kind="summary"))
    r = client.get("/api/assistant/materials/1")
    items = r.json()
    assert len(items) == 1
    assert items[0]["kind"] == "summary"
    r = client.delete(f"/api/assistant/materials/{items[0]['id']}")
    assert r.status_code == 200
    assert client.get("/api/assistant/materials/1").json() == []


def _full_profile(client):
    client.put("/api/profile", json=dict(
        full_name="Ahmed Saber", email="ahmed@example.com", summary="Junior Flutter developer",
        desired_titles=["Flutter Developer"], target_levels=["Junior"],
    ))
    client.put("/api/profile/skills", json=[dict(name="Flutter", level=4), dict(name="Dart", level=3),
                                            dict(name="MS Office", level=4)])
    client.put("/api/profile/experiences", json=[
        dict(title="Call Center Agent", company="NBE", description="Handled customer complaints daily.",
             start_date="2022-01-01", end_date="2023-01-01"),
        dict(title="Support Engineer", company="Xceed",
             description="Wrote Dart scripts; fixed Flutter widgets for a friend's app.",
             start_date="2023-02-01", current=True),
    ])


def _cv(client, job_id=1):
    r = client.post("/api/assistant/generate", json=dict(job_id=job_id, kind="cv"))
    assert r.status_code == 200, r.text
    return r.json()["content"]


def test_cv_leads_with_the_skills_the_ad_names(client):
    _full_profile(client)
    content = _cv(client)
    assert "Ahmed Saber" in content
    assert "Junior Flutter Developer" in content
    owned, other = _skills_lines(content)
    assert "Flutter" in owned and "Dart" in owned
    # The ad also wants REST APIs, which his profile cannot back — it must not be claimed
    # as his skill here, only listed in the gap line at the bottom.
    assert "REST" not in owned.upper()
    assert "MS Office" in other
    gaps = content.split("WHAT THIS AD ASKS FOR THAT YOUR CV DOES NOT SHOW YET")[1]
    assert "rest apis" in gaps.lower()


def test_the_reviewed_cv_reports_its_ats_readiness(client):
    _full_profile(client)
    content = _cv(client)
    assert "ATS READINESS CHECK - " in content
    assert "WHAT THIS AD ASKS FOR" in content  # his checklist stays next to the score


def test_cv_puts_the_experience_that_matches_the_ad_first(client):
    _full_profile(client)
    content = _cv(client)
    section = content.split("EXPERIENCE")[1].split("EDUCATION")[0]
    assert section.index("Xceed") < section.index("NBE")



def test_cv_on_an_empty_profile_invents_nothing(client):
    content = _cv(client)
    assert "[YOUR NAME]" in content
    assert "No work experience recorded yet" in content
    assert "Ahmed" not in content
    assert "[Add your education" in content



def _cv_of(ad_skills, his_skills, languages=None):
    """One ad, one profile, no API in the way — the CV must claim only what is really his."""
    from app.models import Job, Skill, UserProfile
    from app.services import ats
    from app.services.assistant import _cv, _facts
    job = Job(title="Developer", company="NileSoft", location="Cairo", source="remotive",
              external_id="x", description="We need " + ", ".join(ad_skills) + " experience.",
              skills=list(ad_skills))
    profile = UserProfile(full_name="Eslam Saber", email="e@example.com")
    for name in his_skills:
        profile.skills.append(Skill(name=name, level=4, years=1))
    if languages:
        profile.languages = list(languages)
    return ats.normalize_cv(_cv(job, _facts(job, profile)))


def _skills_lines(content):
    """The SKILLS lines: what the ad asks for that he has, then his other skills."""
    from app.services.ats import HEADINGS
    tail = content.split("\nSKILLS\n", 1)[1]
    lines = []
    for line in tail.splitlines():
        if line.strip().rstrip(":").upper() in HEADINGS:
            break
        if line.strip():
            lines.append(line)
    return lines[0], (lines[1] if len(lines) > 1 else "")


def _owned_line(content):
    marker = "\nSKILLS\n"
    return _skills_lines(content)[0] if marker in content else ""


def test_a_similarly_spelled_skill_is_never_claimed_for_him():
    # "Java" is not "JavaScript". Saying he was asked for it and has it would put a skill
    # on his CV that he cannot back, which is the one thing this generator must never do.
    content = _cv_of(["Java"], ["JavaScript"])
    owned, other = _skills_lines(content)
    assert owned.strip() == "JavaScript"
    assert other == ""
    assert "java" in content.split("WHAT THIS AD ASKS FOR")[1].lower()


def test_his_skill_is_still_matched_when_the_ad_spells_it_differently():
    # The other half of the rule: singular/plural and spelling variants are still the same
    # skill, or honest matches would disappear from his CV.
    content = _cv_of(["REST APIs"], ["REST API"])
    assert "REST API" in _owned_line(content)


_AI_CV = (
    "ESLAM SABER BADR RAMADAN\n"
    "eslamsaber078@gmail.com | 01096726081 | linkedin.com/in/eslam\n\n"
    "PROFESSIONAL SUMMARY\n"
    "Flutter developer with hands-on Dart experience and strong English communication "
    "skills, tailored for this exact customer-facing role and its listed requirements.\n\n"
    "SKILLS\n"
    "- Flutter\n"
    "- Dart\n"
    "- English\n\n"
    "EXPERIENCE\n"
    "- Support Engineer - Xceed (2023 - present)\n"
    "    Wrote Dart scripts and fixed Flutter widgets.\n\n"
    "EDUCATION\n"
    "- BSc in Computer Science\n\n"
    "LANGUAGES\n"
    "Arabic, English"
)


def test_cv_generation_prefers_the_ai_when_a_key_is_configured(client, monkeypatch):
    _setup_profile(client)
    from app.services import assistant as mod

    monkeypatch.setattr(mod.ai, "ai_available", lambda: True)
    monkeypatch.setattr(mod.ai, "chat_text", lambda *a, **k: _AI_CV)
    mod._CV_AI_CACHE.clear()
    r = client.post("/api/assistant/generate", json=dict(job_id=1, kind="cv"))
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["template_based"] is False
    assert data["content"].startswith("ESLAM SABER BADR RAMADAN")
    # His copy still ends with the honesty notes meant for his eyes only
    assert "WHAT THIS AD ASKS FOR THAT YOUR CV DOES NOT SHOW YET" in data["content"]
    assert data["content"].strip().endswith("Please review and personalize this draft before sending it.")


def test_cv_falls_back_to_the_template_when_the_ai_call_fails(client, monkeypatch):
    _setup_profile(client)
    from app.services import assistant as mod

    monkeypatch.setattr(mod.ai, "ai_available", lambda: True)
    monkeypatch.setattr(mod.ai, "chat_text", lambda *a, **k: None)
    mod._CV_AI_CACHE.clear()
    r = client.post("/api/assistant/generate", json=dict(job_id=1, kind="cv"))
    data = r.json()
    assert data["template_based"] is True
    assert "PROFESSIONAL SUMMARY" in data["content"]


def test_helper_materials_never_spend_ai_calls(client, monkeypatch):
    # One application costs 2 AI calls (CV + cover letter), not 4: the summary,
    # bullets, email, questions and keywords stay on the free templates even when
    # an AI key is configured, so the free daily quotas last twice as long.
    _setup_profile(client)
    from app.services import assistant as mod

    def _boom(*a, **k):
        raise AssertionError("AI was called for a template-only material")

    monkeypatch.setattr(mod.ai, "ai_available", lambda: True)
    monkeypatch.setattr(mod.ai, "chat_text", _boom)
    monkeypatch.setattr(mod.ai, "chat_json", _boom)
    for kind in ["summary", "bullets", "email", "questions", "keywords"]:
        r = client.post("/api/assistant/generate", json=dict(job_id=1, kind=kind))
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["template_based"] is True, kind
        assert "built-in template" in data["warning"], kind
    # The two materials an employer reads still spend AI calls
    monkeypatch.setattr(mod.ai, "chat_json", lambda *a, **k: {"content": "AI cover letter"})
    r = client.post("/api/assistant/generate", json=dict(job_id=1, kind="cover_letter"))
    assert r.json()["template_based"] is False


def test_cv_for_pdf_uses_the_ai_without_the_internal_notes(client, monkeypatch):
    _setup_profile(client)
    from app.database import SessionLocal
    from app.models import Job, UserProfile
    from app.services import assistant as mod
    from app.services.assistant import cv_for_pdf

    monkeypatch.setattr(mod.ai, "ai_available", lambda: True)
    monkeypatch.setattr(mod.ai, "chat_text", lambda *a, **k: _AI_CV)
    mod._CV_AI_CACHE.clear()
    db = SessionLocal()
    try:
        text = cv_for_pdf(db.get(Job, 1), db.get(UserProfile, 1))
    finally:
        db.close()
    assert text.startswith("ESLAM SABER BADR RAMADAN")
    assert "WHAT THIS AD ASKS FOR" not in text
    assert "Please review" not in text
    assert "English" in text


def test_a_material_generated_by_ai_strips_internal_notes_from_its_pdf(client, monkeypatch):
    # The pack dialog shows the honest version; the downloaded PDF must never carry it,
    # even when the AI itself echoes the marker back.
    _setup_profile(client)
    from app.services import assistant as mod

    monkeypatch.setattr(mod.ai, "ai_available", lambda: True)
    monkeypatch.setattr(mod.ai, "chat_text",
                        lambda *a, **k: _AI_CV + "\n\nWHAT THIS AD ASKS FOR THAT YOUR CV DOES NOT SHOW YET\nDjango")
    mod._CV_AI_CACHE.clear()
    client.post("/api/applications", json=dict(job_id=2, status="Discovered"))
    r = client.post("/api/applications/prepare", json=dict(job_id=2))
    assert r.status_code == 200, r.text
    app_id = r.json()["application"]["id"]
    pdf = client.get(f"/api/applications/{app_id}/materials/cv/pdf")
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF-")
    assert "content-disposition" not in {k.lower() for k in pdf.headers}


def test_summary_keeps_sentences_whole_and_punctuated(client):
    _full_profile(client)
    client.put("/api/profile/experiences", json=[
        dict(title="Restaurant Manager", company="", location="Egypt",
             description="Managed daily operations. Also handled payroll.",
             start_date="2024-10-01", current=True),
    ])
    r = client.post("/api/assistant/generate", json=dict(job_id=1, kind="summary"))
    content = r.json()["content"]
    # The old version spliced the raw bullet at 160 characters, mid-sentence; only the
    # first whole sentence belongs in the summary.
    assert "— managed daily operations." in content
    assert "Also handled payroll" not in content
    assert ".." not in content
    assert content.endswith(".")
    assert "Applying for the" in content


def test_cv_has_no_double_periods_and_no_empty_company_dash(client):
    _full_profile(client)
    client.put("/api/profile/experiences", json=[
        dict(title="Restaurant Manager", company="", location="Egypt",
             description="data confidentiality. customer satisfaction levels.",
             start_date="2024-10-01", current=True),
    ])
    content = _cv(client)
    assert "Restaurant Manager - Egypt" in content
    assert "- , Egypt" not in content
    assert "data confidentiality." in content
    assert "customer satisfaction levels." in content
    assert ".." not in content


def test_a_language_he_speaks_is_never_listed_as_a_gap():
    content = _cv_of(["English"], ["Flutter"], languages=["Arabic", "English"])
    assert "Nothing - every skill this ad names already appears in your profile." in content


def test_cv_for_pdf_omits_the_internal_notes():
    from app.models import Job, UserProfile
    from app.services.assistant import cv_for_pdf
    job = Job(title="Developer", company="NileSoft", location="Cairo", source="remotive",
              external_id="x", description="We need Flutter experience.", skills=["Flutter"])
    profile = UserProfile(full_name="Eslam Saber", email="e@example.com")
    text = cv_for_pdf(job, profile)
    assert "PROFESSIONAL SUMMARY" in text
    assert "WHAT THIS AD ASKS FOR" not in text
    assert "review" not in text.lower()


# ---------- the ATS CV and its red-marked additions ----------


def _cv_job_profile():
    """One ad wanting Flutter + REST APIs, one CV that only proves Flutter."""
    from app.models import Job, Skill, UserProfile
    job = Job(title="Junior Flutter Developer", company="NileSoft", location="Cairo",
              source="remotive", external_id="x",
              description="We need Flutter and REST APIs experience.", skills=["Flutter", "REST APIs"])
    profile = UserProfile(full_name="Eslam Saber", email="e@example.com", country="Egypt", city="Cairo")
    profile.skills.append(Skill(name="Flutter", level=4, years=1))
    return job, profile


def test_the_review_cv_adds_the_missing_requirement_marked_red():
    from app.services.assistant import SUGGESTION_HEADING, cv_for_pdf
    job, profile = _cv_job_profile()
    text = cv_for_pdf(job, profile, marked=True)
    assert SUGGESTION_HEADING in text
    assert "[[REST APIs]]" in text
    # The block that holds the suggestion must not claim these are skills he already has.
    assert "[[REST APIs]]" in text.split(SUGGESTION_HEADING)[1]
    assert "RED ITEMS ARE SUGGESTIONS" in text


def test_the_clean_cv_keeps_the_addition_and_drops_only_the_marks(monkeypatch):
    from app.services import assistant as mod
    job, profile = _cv_job_profile()
    ai_cv = ("ESLAM SABER\ne@example.com\n\nPROFESSIONAL SUMMARY\nFlutter developer who ships mobile "
             "apps end to end and keeps the release flow simple.\n\nSKILLS\n- Flutter\n- [[REST APIs]]")
    monkeypatch.setattr(mod.ai, "ai_available", lambda: True)
    monkeypatch.setattr(mod.ai, "chat_text", lambda *a, **k: ai_cv)
    mod._CV_AI_CACHE.clear()
    marked = mod.cv_for_pdf(job, profile, marked=True)
    clean = mod.cv_for_pdf(job, profile, marked=False)
    mod._CV_AI_CACHE.clear()
    assert "[[REST APIs]]" in marked
    assert "[[" not in clean and "]]" not in clean
    assert "REST APIs" in clean  # the tailoring survives, just without the mark
    assert mod.SUGGESTION_HEADING not in clean
    assert "RED ITEMS" not in clean
    assert "Flutter" in clean


def test_the_send_copy_folds_the_suggested_skills_into_the_skills_section():
    from app.services.assistant import SUGGESTION_HEADING, unmark_suggestions
    text = ("SKILLS\n- Flutter\n- REST APIs\n\nEXPERIENCE\n- Built apps in Dart\n\n"
            + SUGGESTION_HEADING + "\n- [[REST APIs]]\n- [[Azure]]\n\nEDUCATION\nBSc")
    out = unmark_suggestions(text)
    # The heading that says "these are only suggestions" can never reach an employer.
    assert SUGGESTION_HEADING not in out
    # The additions still ship, as ordinary bullet lines of the same section.
    assert "- Flutter\n- REST APIs\n- Azure" in out
    assert out.count("REST APIs") == 1  # already stated, never printed twice
    assert "EDUCATION\nBSc" in out


def test_a_comma_skills_line_absorbs_the_suggestions_in_the_same_style():
    from app.services.assistant import SUGGESTION_HEADING, unmark_suggestions
    text = ("SKILLS\nFlutter, Dart\n\nEXPERIENCE\n- Built apps\n\n"
            + SUGGESTION_HEADING + "\n- [[Azure]]\n- [[Java]]\n\nEDUCATION\nBSc")
    out = unmark_suggestions(text)
    assert "Flutter, Dart, Azure, Java" in out
    assert "- Azure" not in out  # the section stays a comma list, not a mixed one


def test_the_send_copy_carries_the_same_missing_skill_the_review_shows(monkeypatch):
    """The employer's copy must not lose an addition just because the AI did not mark it."""
    from app.services import assistant as mod
    job, profile = _cv_job_profile()
    monkeypatch.setattr(mod.ai, "ai_available", lambda: True)
    monkeypatch.setattr(mod.ai, "chat_text", lambda *a, **k: (
        "ESLAM SABER\ne@example.com\n\nPROFESSIONAL SUMMARY\nFlutter developer who ships "
        "mobile apps end to end and keeps the release flow simple.\n\nSKILLS\n- Flutter"))
    mod._CV_AI_CACHE.clear()
    marked = mod.cv_for_pdf(job, profile, marked=True)
    clean = mod.cv_for_pdf(job, profile, marked=False)
    mod._CV_AI_CACHE.clear()
    assert "[[REST APIs]]" in marked  # offered in the review copy
    assert "- Flutter\n- REST APIs" in clean  # and still there, unmarked, in the send copy
    assert mod.SUGGESTION_HEADING not in clean


def test_the_ats_score_is_computed_from_the_copy_the_employer_gets(client):
    _setup_profile(client)
    from app.database import SessionLocal
    from app.models import Job, UserProfile
    from app.services import assistant as mod

    db = SessionLocal()
    try:
        data = mod.generate_material(db, db.get(Job, 1), db.get(UserProfile, 1), "cv")
    finally:
        db.close()
    body = data["content"]
    additions = mod.suggested_items(body)
    assert additions  # the ad wants REST APIs, his profile does not show it
    # Every addition is in the send copy, so the report must not name any of them
    # as a keyword the employer's CV is missing.
    assert not [line for line in body.splitlines() if "the CV does not" in line]


def test_an_ai_that_brackets_twelve_skills_is_cut_back_to_eight(client, monkeypatch):
    """A CV that is nothing but red lines is not credible, and the overflow can never be
    left standing unmarked — that would promote a suggestion to a claim."""
    _setup_profile(client)
    from app.database import SessionLocal
    from app.models import Job, UserProfile
    from app.services import assistant as mod

    overflow = "\n".join(f"- [[Tool {i}]]" for i in range(1, 13))
    monkeypatch.setattr(mod.ai, "ai_available", lambda: True)
    monkeypatch.setattr(mod.ai, "chat_text", lambda *a, **k: _AI_CV + "\n" + overflow)
    mod._CV_AI_CACHE.clear()
    db = SessionLocal()
    try:
        marked = mod.cv_for_pdf(db.get(Job, 1), db.get(UserProfile, 1), marked=True)
        clean = mod.cv_for_pdf(db.get(Job, 1), db.get(UserProfile, 1), marked=False)
    finally:
        db.close()
    assert len(mod.suggested_items(marked)) == mod.MAX_SUGGESTIONS
    for dropped in ("Tool 9", "Tool 10", "Tool 11", "Tool 12"):
        assert dropped not in marked
    assert "Tool 1" in marked and "[[" in marked
    # The send copy keeps the capped additions as plain text — no brackets, no legend.
    assert "[[" not in clean
    assert "Tool 1" in clean
    assert "Tool 12" not in clean
    assert "Flutter" in clean and "RED ITEMS" not in clean


def test_a_suggestion_the_ai_already_marked_is_not_added_twice(client, monkeypatch):
    _setup_profile(client)
    from app.database import SessionLocal
    from app.models import Job, UserProfile
    from app.services import assistant as mod

    monkeypatch.setattr(mod.ai, "ai_available", lambda: True)
    monkeypatch.setattr(mod.ai, "chat_text",
                        lambda *a, **k: _AI_CV.replace("- Flutter", "- Flutter\n- [[Django]]"))
    mod._CV_AI_CACHE.clear()
    db = SessionLocal()
    try:
        text = mod.cv_for_pdf(db.get(Job, 1), db.get(UserProfile, 1), marked=True)
    finally:
        db.close()
    assert text.count("[[Django]]") == 1


def test_the_cv_pdf_is_one_call_away_from_any_ad(client):
    """The download button must not need a tracker entry to exist first."""
    _setup_profile(client)
    for marked in (True, False):
        r = client.get("/api/assistant/cv/1/pdf", params={"marked": marked})
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/pdf"
        assert r.content.startswith(b"%PDF-")
    assert client.get("/api/assistant/cv/999999/pdf").status_code == 404


def test_the_suggested_marks_render_red_in_the_pdf():
    from app.services import pdf as pdf_service
    from app.services.assistant import mark_suggestion

    assert pdf_service.has_suggestions(f"SKILLS\n- {mark_suggestion('REST APIs')}") is True
    marked = pdf_service.render_text_pdf("SKILLS\n- [[REST APIs]]\n- Flutter", name_line=False)
    clean = pdf_service.render_text_pdf("SKILLS\n- Flutter", name_line=False)
    assert marked != clean  # the mark really changes the rendered document
    assert marked.startswith(b"%PDF-")
