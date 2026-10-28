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
