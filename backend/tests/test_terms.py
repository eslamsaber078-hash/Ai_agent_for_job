"""A typo in a skill or title must never cost the user search results."""
import pytest

from app.database import SessionLocal
from app.services import providers as providers_mod
from app.services.keywords import build_gate
from app.services.terms import clean_term, reconcile_terms, suggest


def _plan(client, **terms):
    r = client.post("/api/automation/search-plan", json=terms)
    assert r.status_code == 200, r.text
    return r.json()


def _flutter_profile() -> dict:
    return dict(
        full_name="Ahmed", email="a@b.com", country="Egypt", city="Cairo",
        desired_titles=["Flutter Developer"],
        preferred_locations=["Cairo", "Remote"], remote_preference="open",
        target_levels=["Intern", "Junior", "Entry"],
        summary="Flutter developer building mobile apps.",
    )


@pytest.mark.parametrize("typed,kind,expected", [
    ("Raect", "skill", "React"),
    ("raect", "skill", "React"),
    ("Fluttr", "skill", "Flutter"),
    ("pyton", "skill", "Python"),
    ("javascrpt", "skill", "JavaScript"),
    ("kotline", "skill", "Kotlin"),
    ("Cario", "location", "Cairo"),
    ("Egpt", "location", "Egypt"),
    ("Alexandira", "location", "Alexandria"),
    ("Flutter Developr", "title", "Flutter Developer"),
    ("Full Stack Developr", "title", "Full Stack Developer"),
    ("Data Analyist", "title", "Data Analyst"),
])
def test_a_typo_is_read_as_the_known_term(typed, kind, expected):
    assert suggest(typed, kind) == expected


@pytest.mark.parametrize("term,kind", [
    ("rest", "skill"),      # a real skill (REST APIs); must not become "Rust"
    ("rust", "skill"),
    ("java", "skill"),      # must not become "JavaScript"
    ("c#", "skill"),
    ("css", "skill"),
    ("nodejs", "skill"),
    ("C Sharp", "skill"),
    ("Excel", "skill"),
    ("Cashier", "title"),
    ("Zoho Developer", "title"),   # unknown but valid: leave it alone
    ("Odoo Developer", "title"),
    ("Giza", "location"),
    ("Dubai", "location"),
])
def test_real_terms_are_left_untouched(term, kind):
    assert suggest(term, kind) is None


def test_seniority_is_kept_while_the_role_word_is_fixed():
    fixed = suggest("senior flutter developr", "title")
    assert fixed is not None
    assert fixed.lower() == "senior flutter developer"


def test_reconcile_dedupes_after_correcting():
    titles, skills, locations, corrections = reconcile_terms(
        ["Raect Developer", "Flutter Developr"], ["Raect", "React", "Fluttr"], ["Cario"],
    )
    assert titles == ["React Developer", "Flutter Developer"]
    assert skills == ["React", "Flutter"]
    assert locations == ["Cairo"]
    pairs = {(c.typed, c.corrected) for c in corrections}
    assert ("Raect Developer", "React Developer") in pairs
    assert ("Raect", "React") in pairs


def test_clean_term_strips_control_characters_and_caps_length():
    assert clean_term("  Flutter\n\t Developer  ") == "Flutter Developer"
    assert len(clean_term("x" * 500)) == 80
    assert clean_term(None) == ""
    assert clean_term(123) == ""


def test_search_plan_reports_the_typo_and_searches_the_corrected_phrase(client):
    plan = _plan(client, titles=["Raect Developer", "Flutter Developr"], skills=["Raect"],
                 extra_terms=[], locations=["Cario"])
    assert plan["titles"] == ["React Developer", "Flutter Developer"]
    assert plan["skills"] == ["React"]
    assert plan["where"] == "Cairo"
    assert plan["terms"] == ["React Developer", "Flutter Developer", "React"]
    assert {"typed": "Raect Developer", "corrected": "React Developer"} in plan["corrections"]


def test_search_plan_does_not_report_anything_for_valid_terms(client):
    plan = _plan(client, titles=["Flutter Developer"], skills=["React", "Rust"],
                 extra_terms=[], locations=["Cairo"])
    assert plan["corrections"] == []
    assert plan["terms"] == ["Flutter Developer", "React", "Rust"]


def test_import_searches_the_corrected_terms_and_says_so(client, monkeypatch):
    seen = {}

    class FakeProvider(providers_mod.BaseProvider):
        name = "fake"
        label = "Fake board"
        keyword_search = True

        def fetch(self, titles, skills, locations, remote_only):
            seen["titles"] = list(titles)
            seen["skills"] = list(skills)
            seen["locations"] = list(locations)
            return []

    monkeypatch.setattr(providers_mod, "get_enabled_providers",
                        lambda db, requested=None: [FakeProvider()])
    db = SessionLocal()
    try:
        _, log = providers_mod.run_discovery(
            db, ["Raect Developer"], ["Raect"], ["Cario"], False,
            sources=["fake"], profile_id=1,
        )
    finally:
        db.close()

    assert seen["titles"] == ["React Developer"]
    assert seen["skills"] == ["React"]
    assert seen["locations"] == ["Cairo"]
    assert any("Spelling check" in line and "React" in line for line in log)


def test_relevance_gate_accepts_the_corrected_role():
    titles, skills, _, _ = reconcile_terms(["Flutter Developr"], [], [])
    matches = build_gate(titles, skills)
    assert matches(providers_mod.ProviderJob(source="x", external_id="1", title="Flutter Developer"))
    assert not matches(providers_mod.ProviderJob(source="x", external_id="2", title="Accountant"))


def test_profile_suggestions_are_hints_only(client):
    r = client.put("/api/profile", json={"desired_titles": ["Raect Developer"],
                                         "preferred_locations": ["Cario"]})
    assert r.status_code == 200, r.text
    r = client.put("/api/profile/skills", json=[{"name": "Raect", "level": 3}])
    assert r.status_code == 200, r.text

    r = client.post("/api/profile/term-suggestions", json={
        "titles": ["Raect Developer"], "skills": ["Raect", "React"], "locations": ["Cario"],
    })
    assert r.status_code == 200, r.text
    hints = {(item["kind"], item["term"]): item["suggestion"] for item in r.json()}
    assert hints[("title", "Raect Developer")] == "React Developer"
    assert hints[("skill", "Raect")] == "React"
    assert hints[("location", "Cario")] == "Cairo"
    assert ("skill", "React") not in hints

    stored = client.get("/api/profile").json()
    assert stored["desired_titles"] == ["Raect Developer"]
    assert stored["preferred_locations"] == ["Cario"]
    assert [s["name"] for s in stored["skills"]] == ["Raect"]


def test_misspelt_skill_still_counts_as_proof(client):
    assert client.put("/api/profile", json=_flutter_profile()).status_code == 200
    assert client.put("/api/profile/skills", json=[{"name": "Fluttr", "level": 4}]).status_code == 200
    data = client.get("/api/matches/1").json()  # Junior Flutter Developer
    assert "Flutter" in data["matched_skills"]


def test_misspelt_desired_title_still_recognises_the_role(client):
    assert client.put("/api/profile", json={**_flutter_profile(),
                                            "desired_titles": ["Flutter Developr"]}).status_code == 200
    assert client.put("/api/profile/skills", json=[{"name": "Flutter", "level": 4}]).status_code == 200
    data = client.get("/api/matches/1").json()
    title_factor = next(f for f in data["factors"] if f["label"] == "Job title fit")
    assert title_factor["score"] == 100
