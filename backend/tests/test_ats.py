"""The ATS pass: rebuild a messy CV into a parseable one without inventing a fact."""
from app.services import ats

MESSY = """JOHN   DOE
john@example.com | +20 109 672 6081 | linkedin.com/in/john
============================================
Work Experience:
• Built **flutter** apps (2023 - now)
● REST APIs, databases
Some Company | Senior Dev | Jan. 2021 – 03/2023
--------------------------------------------
Skills
Flutter, Dart, MS Office
Technical Skills
Java, Python
Education:
B.Sc. Computer Science, Cairo University, 2020
"""


def test_a_messy_cv_is_rebuilt_for_a_parser():
    out = ats.normalize_cv(MESSY)
    assert "JOHN DOE" in out  # the name survives, extra spaces gone
    assert "•" not in out and "●" not in out and "=" not in out and "---" not in out
    assert out.count("\nSKILLS\n") == 1  # the two skills headings became one
    assert "EXPERIENCE\n" in out and "EDUCATION\n" in out
    assert "2023 - Present" in out and "Jan 2021 - Mar 2023" in out
    assert "Some Company - Senior Dev" in out  # pipes are not a table for the parser
    assert "**" not in out


def test_sections_come_out_in_the_order_parsers_expect():
    out = ats.normalize_cv("X\nx@example.com\n\nEDUCATION\nB.Sc.\n\nSKILLS\nFlutter\n\nEXPERIENCE\n- Dev")
    assert out.index("SKILLS") < out.index("EXPERIENCE") < out.index("EDUCATION")


def test_suggestion_brackets_survive_the_rebuild():
    out = ats.normalize_cv("X\n\nSKILLS\n- Flutter\n- [[REST APIs]]")
    assert "[[REST APIs]]" in out


def test_dates_the_ad_system_has_to_parse_are_all_normalized():
    line = ats.normalize_cv(
        "X\nx@example.com\n\nEXPERIENCE\n"
        "- Dev - A (September 2020 - Sept 2021)\n"
        "- Dev - B (2022-06 - 06/2023)\n"
        "- Dev - C (2021-Present)")
    assert "Sep 2020 - Sep 2021" in line
    assert "Jun 2022 - Jun 2023" in line
    assert "2021 - Present" in line


def test_a_pasted_table_row_becomes_plain_text():
    out = ats.normalize_cv("X\nx@example.com\n\nSKILLS\n| Flutter | Dart | REST APIs |")
    assert "|" not in out
    assert "Flutter, Dart, REST APIs" in out


def test_the_normalizer_is_stable_when_run_twice():
    once = ats.normalize_cv(MESSY)
    assert ats.normalize_cv(once) == once


def test_a_contact_line_keeps_its_pipe_separators():
    out = ats.normalize_cv("X\nx@example.com | +20 109 672 6081 | github.com/x\n\nSKILLS\nFlutter")
    assert "x@example.com | +20 109 672 6081 | github.com/x" in out


def test_the_report_names_what_is_still_missing():
    out = ats.normalize_cv(MESSY)
    report = ats.ats_check(out, ["Flutter", "REST APIs", "Docker"])
    assert report["score"] < 100
    assert any("PROFESSIONAL SUMMARY" in issue for issue in report["issues"])
    assert report["keywords_missing"] == ["Docker"]


def test_a_clean_tailored_cv_scores_full_marks():
    cv = ("JOHN DOE\njohn@example.com | +20 109 672 6081\n\n"
          "PROFESSIONAL SUMMARY\nFlutter developer for mobile apps.\n\n"
          "SKILLS\nFlutter, Dart, REST APIs\n\n"
          "EXPERIENCE\n- Flutter Developer - Nile Apps (Jan 2023 - Present)\n"
          "- Built the app with Dart and REST APIs\n\n"
          "EDUCATION\n- B.Sc. Computer Science - Cairo University (2020)")
    report = ats.ats_check(cv, ["Flutter", "REST APIs"])
    assert report["score"] == 100 and report["issues"] == []


def test_the_report_block_is_cut_from_both_pdf_copies():
    from app.services.assistant import ATS_HEADING, review_copy, unmark_suggestions
    doc = ("ESLAM\n\nSKILLS\n- Flutter\n- [[REST APIs]]\n\n"
           + ATS_HEADING + " - 90/100\nReady to send.\n\n"
           "WHAT THIS AD ASKS FOR THAT YOUR CV DOES NOT SHOW YET\n- REST APIs")
    for copy in (review_copy(doc), unmark_suggestions(doc)):
        assert "ATS READINESS CHECK" not in copy
        assert "REST APIs" in copy


def test_a_degree_on_his_profile_survives_a_draft_that_dropped_it():
    """The AI leaves out sections it thinks are empty; a real degree must not vanish with
    them, because the standard EDUCATION heading is part of what an ATS scores."""
    from app import models
    from app.services import assistant as mod
    job = models.Job(title="Flutter Developer", company="NileSoft", location="Cairo",
                     source="remotive", external_id="x", description="Flutter.",
                     skills=["Flutter"])
    profile = models.UserProfile(full_name="Eslam Saber", email="e@example.com")
    profile.skills.append(models.Skill(name="Flutter", level=4, years=1))
    profile.education.append(models.Education(degree="B.Sc. Computer Science",
                                              institution="Cairo University"))
    draft = ("ESLAM SABER\ne@example.com\n\nPROFESSIONAL SUMMARY\nFlutter developer.\n\n"
             "SKILLS\n- Flutter\n\nEXPERIENCE\n- Flutter Developer - Nile (Jan 2023 - Present)")
    out = mod._cv_pack(job, mod._facts(job, profile), marked=True, ai_text=draft)
    assert "EDUCATION\n- B.Sc. Computer Science - Cairo University" in out
    assert ats.EDUCATION in ats.headings_in(out)


def test_no_education_section_is_invented_for_a_profile_without_one():
    from app import models
    from app.services import assistant as mod
    job = models.Job(title="Flutter Developer", company="NileSoft", location="Cairo",
                     source="remotive", external_id="x", description="Flutter.",
                     skills=["Flutter"])
    profile = models.UserProfile(full_name="Eslam Saber", email="e@example.com")
    draft = "ESLAM SABER\ne@example.com\n\nSKILLS\n- Flutter"
    out = mod._cv_pack(job, mod._facts(job, profile), marked=True, ai_text=draft)
    assert ats.EDUCATION not in ats.headings_in(out)


def test_an_all_caps_skill_bullet_is_drawn_as_a_bullet_not_a_heading():
    """'- AWS' is upper case like a heading, but a 11.5pt bold line where a 10pt bullet
    belongs breaks the skills list for the reader and for the parser."""
    import io
    from pypdf import PdfReader
    from app.services import pdf as pdf_service
    blob = pdf_service.render_text_pdf("SKILLS\n- AWS\n- Flutter", name_line=False)
    page = PdfReader(io.BytesIO(blob)).pages[0]
    stream = page["/Contents"].get_data().decode("latin-1")
    at = stream.find("(AWS)")
    assert at != -1
    assert "/F1 10 Tf" in stream[max(0, at - 200):at]
    # Bullets are real bullets: the body font draws one on that line.
    assert "(\\177)" in stream[max(0, at - 200):at]


def test_a_messy_ai_draft_is_normalized_before_it_reaches_him(monkeypatch):
    from app import models
    from app.services import assistant as mod
    job = models.Job(title="Flutter Developer", company="NileSoft", location="Cairo",
                     source="remotive", external_id="x", description="Flutter and REST APIs.",
                     skills=["Flutter", "REST APIs"])
    profile = models.UserProfile(full_name="Eslam Saber", email="e@example.com")
    profile.skills.append(models.Skill(name="Flutter", level=4, years=1))
    f = mod._facts(job, profile)
    messy = ("ESLAM SABER\ne@example.com | 01096726081\n\n"
             "Work Experience:\n● Built **flutter** apps (2023 - now)\n\n"
             "Technical Skills\nFlutter\n\nEDUCATION\nB.Sc.")
    marked = mod._cv_pack(job, f, marked=True, ai_text=messy)
    assert "\nSKILLS\n" in marked and "•" not in marked and "**" not in marked
    assert "2023 - Present" in marked
    assert "[[REST APIs]]" in marked  # the ad's missing skill is still offered in red
