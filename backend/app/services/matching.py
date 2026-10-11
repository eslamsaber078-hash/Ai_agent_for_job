"""Deterministic, transparent job matching.

The 0-100 score is always computed with deterministic rules from the real
profile and job data. When an OpenAI key is configured, the narrative parts
(why_match / concerns / next_steps) are enhanced by the model but the score
itself stays deterministic. Scores are estimates, never guarantees.
"""
from __future__ import annotations

import json
import logging
import re

from pydantic import BaseModel, ValidationError

from ..models import Job, UserProfile
from . import ai

log = logging.getLogger("jobhunter.matching")

SKILL_LEXICON = [
    "flutter", "dart", "python", "django", "fastapi", "flask", "c#", "csharp", ".net", "asp.net",
    "react", "react native", "javascript", "typescript", "node.js", "vue", "angular", "html", "css",
    "tailwind", "sql", "postgresql", "mysql", "sql server", "mongodb", "firebase", "docker",
    "kubernetes", "aws", "azure", "git", "rest api", "rest", "graphql", "linux", "bash", "ci/cd",
    "selenium", "machine learning", "pandas", "scikit-learn", "unity", "java", "spring", "kotlin",
    "swift", "bloc", "riverpod", "provider", "state management", "oop", "data structures",
    "problem solving", "excel", "power bi", "mqtt", "bluetooth", "wordpress", "etl", "airflow",
    "redis", "microservices", "winforms", "rpa", "web scraping", "technical writing", "networking",
    "troubleshooting", "customer service", "english", "payments", "secure coding", "rest apis",
]


def _skill_pattern(skill: str) -> re.Pattern:
    """Whole-word match only.

    Plain substring matching scored "Excel" from "excellent", "Java" from "JavaScript"
    and "OOP" from "loop" — every false tag inflated the required-skill count and
    pushed the real score down.
    """
    return re.compile(
        r"(?<![a-z0-9+#.])" + re.escape(skill.lower()) + r"(?![a-z0-9])"
    )


_SKILL_PATTERNS = [(skill, _skill_pattern(skill)) for skill in SKILL_LEXICON]

# "provider" is both a Flutter package and an ordinary English word ("service provider"),
# so it only counts as a skill where the posting is actually about Flutter/Dart.
_CONTEXT_TERMS = {"provider": ("flutter", "dart")}

LEVEL_ORDER = {
    "intern": 0, "entry": 1, "junior": 1, "graduate": 1, "mid": 2, "mid-level": 2,
    "senior": 3, "lead": 4, "": 1,
}


def detect_skills(text: str) -> list[str]:
    """Find known skill names inside a free-text job description."""
    lowered = (text or "").lower()
    found = []
    for skill, pattern in _SKILL_PATTERNS:
        if not pattern.search(lowered):
            continue
        context = _CONTEXT_TERMS.get(skill)
        if context and not any(_skill_pattern(term).search(lowered) for term in context):
            continue
        found.append(_canonical(skill))
    return list(dict.fromkeys(found))


def _canonical(skill: str) -> str:
    aliases = {
        "csharp": "C#", "asp.net": ".NET", "rest": "REST APIs", "rest api": "REST APIs",
        "rest apis": "REST APIs",
        "node.js": "Node.js", "sql server": "SQL Server", "power bi": "Power BI",
    }
    return aliases.get(skill, skill.replace("-", " ").title())


def _norm_skill(name: str) -> str:
    return re.sub(r"[^a-z0-9+#.]", "", (name or "").lower())


def job_skill_tags(job: Job) -> list[str]:
    tags = [t for t in (job.skills or []) if t]
    detected = detect_skills(job.description)
    for d in detected:
        if not any(_norm_skill(t) == _norm_skill(d) for t in tags):
            tags.append(d)
    return tags


class _AIAnalysis(BaseModel):
    why_match: str = ""
    concerns: str = ""
    next_steps: list[str] = []


def _narrative_ai(job: Job, profile: UserProfile, facts: dict) -> _AIAnalysis | None:
    if not ai.openai_available():
        return None
    payload = {
        "job_title": job.title,
        "job_company": job.company,
        "job_level": job.experience_level,
        "job_skills": facts["job_skills"],
        "candidate_skills": facts["profile_skills"],
        "candidate_experience": facts["experience"],
        "candidate_projects": facts["projects"],
        "missing_skills": facts["missing_skills"],
        "candidate_desired_titles": facts["desired_titles"],
    }
    system = (
        "You are a career coach. You receive structured JSON facts about a job and a real candidate. "
        "Write a short honest analysis: why the job fits (or not), the main concerns, and 3-5 next steps. "
        "NEVER invent experience, qualifications, projects, or personal details. "
        "If the candidate profile lacks information, say so instead of assuming. "
        "Respond ONLY with JSON: {\"why_match\": string, \"concerns\": string, \"next_steps\": [string]}."
    )
    data = ai.chat_json(system, json.dumps(payload, ensure_ascii=False))
    if not data:
        return None
    try:
        return _AIAnalysis(**data)
    except ValidationError:
        return None


def compute_match(job: Job, profile: UserProfile | None, use_ai: bool = True) -> dict:
    """Compute a transparent 0-100 match score with a full breakdown.

    ``use_ai`` is turned off by list endpoints: the score is deterministic, so
    paying one AI round-trip per job would only slow the page down.
    """
    if profile is None:
        return _empty_match(job)
    if not any([profile.skills, profile.experiences, profile.projects,
                profile.desired_titles, profile.summary]):
        return _empty_match(job)

    job_tags = job_skill_tags(job)
    profile_skills = {s.name: s for s in profile.skills}
    norm_profile = {_norm_skill(n): s for n, s in profile_skills.items()}

    matched, missing = [], []
    skill_points, max_points = 0.0, 0.0
    for tag in job_tags:
        s = norm_profile.get(_norm_skill(tag))
        weight = 1.0 if s is None else (0.4 + 0.6 * (s.level or 3) / 5)
        max_points += weight
        if s is not None:
            matched.append(s.name)
            skill_points += weight
        else:
            missing.append(tag)

    skill_score = (skill_points / max_points) * 100 if max_points else 50.0

    desired = {t.lower().strip() for t in profile.desired_titles if t.strip()}
    title_hit = any(t in job.title.lower() for t in desired)
    title_score = 100.0 if title_hit else (40.0 if desired else 50.0)

    job_level = (job.experience_level or "").lower()
    targets = {t.lower() for t in profile.target_levels}
    if targets:
        if job_level in targets:
            level_score = 100.0
        elif LEVEL_ORDER.get(job_level, 1) <= max(LEVEL_ORDER.get(t, 1) for t in targets):
            level_score = 75.0
        else:
            level_score = 25.0
    else:
        level_score = 50.0

    locs = {l.lower().strip() for l in profile.preferred_locations if l.strip()}
    job_loc = f"{job.location} {job.country}".lower()
    loc_match = any(l in job_loc for l in locs)
    if job.remote and profile.remote_preference == "remote":
        location_score = 100.0
    elif job.remote and profile.remote_preference in ("open", "hybrid"):
        location_score = 90.0
    elif job.remote and profile.remote_preference == "onsite":
        location_score = 30.0
    elif not job.remote and profile.remote_preference == "remote":
        location_score = 30.0
    elif loc_match:
        location_score = 100.0
    else:
        location_score = 60.0

    if profile.min_salary and job.salary_min:
        currency_ok = not job.salary_currency or not profile.salary_currency or \
            job.salary_currency.upper() == profile.salary_currency.upper()
        if not currency_ok:
            salary_score = 50.0
        elif job.salary_min >= profile.min_salary:
            salary_score = 100.0
        elif job.salary_max and job.salary_max >= profile.min_salary:
            salary_score = 70.0
        else:
            salary_score = 20.0
    else:
        salary_score = 50.0

    weights = {"skills": 0.45, "level": 0.15, "location": 0.15, "title": 0.15, "salary": 0.10}
    total = (
        weights["skills"] * skill_score
        + weights["level"] * level_score
        + weights["location"] * location_score
        + weights["title"] * title_score
        + weights["salary"] * salary_score
    )
    score = max(0, min(100, round(total)))

    factors = [
        dict(label="Skills", detail=f"Matched {len(matched)}/{len(job_tags)} required skills",
             weight=weights["skills"], score=round(skill_score)),
        dict(label="Experience level", detail=f"Job level: {job.experience_level or 'not specified'}",
             weight=weights["level"], score=round(level_score)),
        dict(label="Location & remote", detail=f"{job.location}, {job.country}; remote={job.remote}",
             weight=weights["location"], score=round(location_score)),
        dict(label="Job title fit", detail=f"Desired titles: {', '.join(profile.desired_titles) or 'not set'}",
             weight=weights["title"], score=round(title_score)),
        dict(label="Salary", detail=_salary_detail(job, profile),
             weight=weights["salary"], score=round(salary_score)),
    ]

    facts = {
        "job_skills": job_tags,
        "profile_skills": [s.name for s in profile.skills],
        "experience": [
            dict(title=e.title, company=e.company,
                 period=f"{e.start_date or '?'} - {e.end_date or 'present' if e.current else e.end_date or '?'}",
                 description=e.description[:300])
            for e in profile.experiences
        ],
        "projects": [dict(name=p.name, technologies=p.technologies) for p in profile.projects],
        "missing_skills": missing,
        "desired_titles": profile.desired_titles,
    }

    why = _why_match(job, profile, matched, title_hit, level_score, location_score)
    concerns = _concerns(job, profile, missing, level_score, location_score)
    steps = _next_steps(job, missing, score, profile)

    ai_enhanced = False
    if use_ai and ai.openai_available():
        enriched = _narrative_ai(job, profile, facts)
        if enriched:
            why = enriched.why_match or why
            concerns = enriched.concerns or concerns
            steps = enriched.next_steps or steps
            ai_enhanced = True

    return dict(
        job_id=job.id,
        score=score,
        estimate=True,
        matched_skills=sorted(set(matched)),
        missing_skills=sorted(set(missing), key=str.lower),
        factors=factors,
        why_match=why,
        concerns=concerns,
        next_steps=steps,
        ai_enhanced=ai_enhanced,
    )


def _empty_match(job: Job) -> dict:
    return dict(
        job_id=job.id, score=0, estimate=True,
        matched_skills=[], missing_skills=job_skill_tags(job),
        factors=[dict(label="Profile", detail="No profile configured yet. Complete your profile to get match scores.",
                      weight=1.0, score=0)],
        why_match="Complete your profile in the Resume & Profile page to get an accurate match score.",
        concerns="Profile is missing.",
        next_steps=["Fill in your skills, experience, and desired job titles in the Resume & Profile page."],
        ai_enhanced=False,
    )


def _salary_detail(job: Job, profile: UserProfile) -> str:
    if profile.min_salary:
        if job.salary_min:
            return f"Job: {job.salary_min}-{job.salary_max or '?'} {job.salary_currency or ''} vs your minimum {profile.min_salary} {profile.salary_currency}"
        return "Job salary not published"
    return "No minimum salary set in your profile"


def _why_match(job, profile, matched, title_hit, level_score, location_score) -> str:
    parts = []
    if matched:
        parts.append(f"You already have {len(matched)} of the required skills ({', '.join(matched[:6])}).")
    if title_hit:
        parts.append(f"The title \"{job.title}\" matches your desired roles.")
    if level_score >= 75:
        parts.append(f"The {job.experience_level or 'unspecified'} level fits your target level.")
    if location_score >= 90:
        parts.append(f"Location works for you ({job.location}, {job.country}, remote={job.remote}).")
    if profile.projects:
        parts.append(f"Your {len(profile.projects)} portfolio project(s) can support the application.")
    if not parts:
        parts.append("This job may require skills or experience beyond your current profile.")
    return " ".join(parts)


def _concerns(job, profile, missing, level_score, location_score) -> str:
    parts = []
    if missing:
        parts.append(f"Skills you may need to strengthen: {', '.join(missing[:8])}.")
    if level_score < 50:
        parts.append(f"The job targets a level above your current profile target.")
    if location_score < 50:
        parts.append(f"Location or remote preference does not match your profile.")
    if not parts:
        parts.append("No major concerns detected based on the information in your profile.")
    return " ".join(parts)


def _next_steps(job, missing, score, profile) -> list[str]:
    steps = []
    if missing:
        steps.append(f"Build a small project or take a course covering: {', '.join(missing[:4])}.")
    if not profile.projects:
        steps.append("Add at least one portfolio project related to this role.")
    steps.append("Tailor your resume summary to the job description before applying.")
    steps.append("Research the company and prepare 2-3 questions for the interview.")
    return steps
