"""Application assistant: generates tailored materials grounded in the real profile.

With an OpenAI key configured the texts are AI-written from the profile facts;
without a key, deterministic templates are used and clearly labeled.
Nothing is ever fabricated: missing profile fields are called out instead.
"""
from __future__ import annotations

import json
import logging

from pydantic import BaseModel, ValidationError

from ..models import Job, UserProfile
from . import ai
from .matching import job_skill_tags

log = logging.getLogger("jobhunter.assistant")

REVIEW_REMINDER = "Please review and personalize this draft before sending it."


class _Generated(BaseModel):
    content: str


def _ai_generate(instruction: str, facts: dict) -> str | None:
    if not ai.openai_available():
        return None
    system = (
        "You are an expert job-application writer. You receive structured JSON facts about a real "
        "candidate and a job. Write the requested text using ONLY those facts. "
        "NEVER invent experience, qualifications, projects, certificates, or personal details. "
        "If a needed fact is missing, write a clear placeholder like [Your Name] or mention the gap. "
        "Respond ONLY with JSON: {\"content\": string}."
    )
    data = ai.chat_json(system, instruction + "\n\nFACTS:\n" + json.dumps(facts, ensure_ascii=False))
    if not data:
        return None
    try:
        return _Generated(**data).content
    except ValidationError:
        return None


def _facts(job: Job, profile: UserProfile | None) -> dict:
    profile = profile or UserProfile()
    return dict(
        job_title=job.title,
        company=job.company,
        job_description=(job.description or "")[:2500],
        job_skills=job_skill_tags(job),
        candidate_name=profile.full_name,
        candidate_email=profile.email,
        candidate_summary=profile.summary,
        candidate_skills=[dict(name=s.name, level=s.level, years=s.years) for s in profile.skills],
        experience=[
            dict(title=e.title, company=e.company, location=e.location,
                 start=e.start_date, end=e.end_date, current=e.current, description=e.description)
            for e in profile.experiences
        ],
        education=[
            dict(degree=e.degree, institution=e.institution, field=e.field, start=e.start_date, end=e.end_date)
            for e in profile.education
        ],
        projects=[dict(name=p.name, description=p.description, url=p.url, technologies=p.technologies)
                  for p in profile.projects],
        languages=profile.languages or [],
        desired_titles=profile.desired_titles or [],
        links=dict(linkedin=profile.linkedin, github=profile.github, portfolio=profile.portfolio),
    )


def generate_material(db, job: Job, profile: UserProfile | None, kind: str,
                      extra_notes: str = "") -> dict:
    f = _facts(job, profile)
    template_based = True
    content = ""
    extra = f"\nAdditional notes from the user: {extra_notes}" if extra_notes else ""

    if kind == "keywords":
        content = _keywords(job, f)

    elif kind == "summary":
        content = _summary(job, f)
        ai_text = _ai_generate(
            "Write a 3-4 sentence tailored professional summary for this candidate applying to this job."
            + extra, f)
        if ai_text:
            content, template_based = ai_text, False

    elif kind == "bullets":
        content = _bullets(job, f)
        ai_text = _ai_generate(
            "Suggest improved resume bullet points for this candidate applying to this job. "
            "Use the STAR style and only real facts. Return 5-7 bullets separated by newlines." + extra, f)
        if ai_text:
            content, template_based = ai_text, False

    elif kind == "cover_letter":
        content = _cover_letter(job, f)
        ai_text = _ai_generate(
            "Write a customized cover letter (3-4 paragraphs, professional, honest) for this candidate "
            "applying to this job. Sign with the candidate's real name or [Your Name]." + extra, f)
        if ai_text:
            content, template_based = ai_text, False

    elif kind == "email":
        content = _email(job, f)
        ai_text = _ai_generate(
            "Write a short professional application email for this candidate applying to this job. "
            "Keep it under 150 words. Sign with the candidate's real name or [Your Name]." + extra, f)
        if ai_text:
            content, template_based = ai_text, False

    elif kind == "questions":
        content = _questions(job, f)
        ai_text = _ai_generate(
            "Generate 6 likely interview questions for this job plus a suggested answer for each, "
            "based ONLY on the candidate's real background. Format: 'Q: ...\nA: ...' blocks." + extra, f)
        if ai_text:
            content, template_based = ai_text, False

    warning = ""
    if template_based:
        warning = "Generated with templates because no OpenAI API key is configured (or the AI call failed). " + REVIEW_REMINDER
    else:
        warning = REVIEW_REMINDER

    return dict(kind=kind, content=content, template_based=template_based, warning=warning)


def _keywords(job: Job, f: dict) -> str:
    tags = job_skill_tags(job)
    desc_words = set((job.description or "").lower().replace(",", " ").replace(".", " ").split())
    extra = [w for w in ["team", "agile", "mentorship", "training", "growth", "remote", "hybrid",
                         "startup", "product", "customer", "testing", "deployment"]
             if w in desc_words]
    lines = ["Keywords extracted from the job description:"]
    lines.append("Technical skills: " + (", ".join(tags) or "none detected"))
    if extra:
        lines.append("Other notable terms: " + ", ".join(extra))
    lines.append("")
    lines.append("Tip: use these exact words in your resume and cover letter where they truthfully apply.")
    return "\n".join(lines)


def _summary(job: Job, f: dict) -> str:
    name = f["candidate_name"] or "[Your Name]"
    skills = ", ".join(s["name"] for s in f["candidate_skills"]) or "[list your skills]"
    role = (f["desired_titles"] or [job.title])[0]
    exp = f["experience"][0] if f["experience"] else None
    projects = f["projects"]
    parts = [f"{name} is a {role} with hands-on experience in {skills}."]
    if exp:
        parts.append(f"Most recently, {name} worked as {exp['title']} at {exp['company']}"
                     + (f" ({exp['start']} - present)" if exp.get("current") else
                        (f" ({exp['start']} - {exp['end']})" if exp.get("start") else ""))
                     + ", " + (exp["description"][:160] or ""))
    if projects:
        parts.append(f"{name} has built {len(projects)} project(s) including "
                     + ", ".join(p["name"] for p in projects[:3]) + ".")
    if f["candidate_summary"]:
        parts.append(f["candidate_summary"])
    parts.append(f"Currently seeking {job.experience_level or 'suitable'} roles like \"{job.title}\" "
                 f"at companies such as {job.company}.")
    return " ".join(parts)


def _bullets(job: Job, f: dict) -> str:
    job_tags = [t.lower() for t in job_skill_tags(job)]
    lines = ["Suggested resume bullets (based only on your real entries):", ""]
    used = False
    for e in f["experience"]:
        desc = e["description"] or f"Worked as {e['title']} at {e['company']}"
        lines.append(f"- {desc[0].upper() + desc[1:] if desc else ''}")
        used = True
    for p in f["projects"]:
        tech = ", ".join(p["technologies"]) or "modern tools"
        lines.append(f"- Built \"{p['name']}\" using {tech}" + (f" ({p['url']})" if p["url"] else "") + ".")
        used = True
    if not used:
        lines.append("- [Add your experience or projects in the Resume & Profile page to generate bullets.]")
    lines.append("")
    lines.append("Tip: quantify results where possible (e.g. \"reduced load time by 30%\").")
    return "\n".join(lines)


def _cover_letter(job: Job, f: dict) -> str:
    name = f["candidate_name"] or "[Your Name]"
    skills = ", ".join(s["name"] for s in f["candidate_skills"]) or "[your main skills]"
    exp = f["experience"][0] if f["experience"] else None
    projects = f["projects"]
    para2 = (f"I have been working as {exp['title']} at {exp['company']} where "
             f"{exp['description'][:200]}" if exp and exp["description"] else
             (f"I have built practical experience through my projects"
              + (": " + ", ".join(p['name'] for p in projects[:2]) if projects else ".")
              if projects else
              "I am at the start of my career and highly motivated to grow in this role."))
    return "\n\n".join([
        f"Dear Hiring Manager at {job.company or '[Company]'},",
        f"I am writing to apply for the {job.title} position. "
        f"My skills in {skills} and my focus on "
        f"{', '.join(f['desired_titles'][:2]) or 'software development'} make me a strong fit for your team.",
        para2 + " I am eager to bring this experience to " + (job.company or "your company")
        + " and contribute to the team from day one.",
        "I have attached my resume for your review and would welcome the opportunity to discuss "
        "how I can contribute. Thank you for your time and consideration.",
        "Sincerely,\n" + name + ("\n" + f["candidate_email"] if f["candidate_email"] else "") +
        ("\nLinkedIn: " + f["links"]["linkedin"] if f["links"]["linkedin"] else ""),
    ])


def _email(job: Job, f: dict) -> str:
    name = f["candidate_name"] or "[Your Name]"
    skills = ", ".join(s["name"] for s in f["candidate_skills"][:5]) or "[your main skills]"
    return "\n\n".join([
        f"Subject: Application for {job.title} - {name}",
        f"Dear Hiring Team,",
        f"I am writing to apply for the {job.title} role at {job.company or 'your company'}. "
        f"My background in {skills} matches the requirements of the position, and I would be excited "
        f"to contribute to your team.",
        f"My resume is attached. I am available for an interview at your convenience and can be reached "
        f"at {f['candidate_email'] or '[your email]'}.",
        "Thank you for your consideration.",
        name,
    ])


def _questions(job: Job, f: dict) -> str:
    tags = job_skill_tags(job)
    lines = ["Likely interview questions for this role:", ""]
    if tags:
        lines.append(f"1. Can you describe a project where you used {tags[0]}? What challenges did you face?")
        if len(tags) > 1:
            lines.append(f"2. How do you keep up with new developments in {tags[1]}?")
    lines.append("3. Tell me about yourself and why you are interested in this role.")
    lines.append("4. Describe a time you faced a difficult bug or problem - how did you solve it?")
    lines.append("5. Where do you see yourself in two years?")
    lines.append("6. Do you have any questions for us about the team or the role?")
    lines.append("")
    lines.append("Tip: prepare answers based on your real projects and experiences.")
    return "\n".join(lines)
