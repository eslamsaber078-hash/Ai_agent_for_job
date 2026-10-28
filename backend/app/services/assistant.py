"""Application assistant: generates tailored materials grounded in the real profile.

With an AI key configured (OpenAI or the free Gemini) the texts are AI-written
from the profile facts; without a key, deterministic templates are used and
clearly labeled. Nothing is ever fabricated: missing profile fields are called
out instead.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re

from pydantic import BaseModel, ValidationError

from ..models import Job, UserProfile
from . import ai, ats
from .ats import ATS_HEADING
from .matching import _norm_skill, job_skill_tags

log = logging.getLogger("jobhunter.assistant")

REVIEW_REMINDER = "Please review and personalize this draft before sending it."

# ---------- the red marks ----------
# He asked the assistant to complete the CV for the ad, including skills his CV does not
# state yet. Those stay suggestions, never claims: every one is written inside [[double
# brackets]], which the PDF renders red and underlined and the clean copy removes entirely.
_SUGGESTED_RE = re.compile(r"\[\[([^\[\]\n]{1,80})\]\]")

CV_LEGEND = ("RED ITEMS ARE SUGGESTIONS FOR THIS AD, NOT PARTS OF YOUR CV. Delete every one "
             "you cannot back up before sending; the clean download leaves them out.")

# The block header the suggestions get. Named here so the clean copy can remove it too —
# an orphan heading claiming "suggested for this ad" must never reach an employer.
SUGGESTION_HEADING = "SUGGESTED FOR THIS AD - CONFIRM BEFORE SENDING"


def mark_suggestion(item: str) -> str:
    return f"[[{item.strip()}]]"


# A CV that is mostly red is not a CV. The AI is told to bracket at most a handful, and
# this is the hard limit behind it — overflow additions are deleted, never left standing
# unmarked, which would turn a suggestion into a claim.
MAX_SUGGESTIONS = 8


def suggested_items(text: str) -> list[str]:
    """Every bracketed addition found in a CV, in the order the document lists them."""
    return [m.strip() for m in _SUGGESTED_RE.findall(text or "") if m.strip()]


def _limit_suggestions(text: str, limit: int = MAX_SUGGESTIONS) -> str:
    """Keep the first ``limit`` bracketed additions and delete the rest outright."""
    remaining = limit
    lines = []
    for line in (text or "").split("\n"):
        def keep(match: re.Match) -> str:
            nonlocal remaining
            if remaining <= 0:
                return ""
            remaining -= 1
            return match.group(0)

        pruned = _SUGGESTED_RE.sub(keep, line)
        if pruned != line:
            pruned = re.sub(r",\s*,", ", ", pruned)
            pruned = re.sub(r"[ \t]+", " ", pruned).rstrip(" ,;")
            if not pruned.strip(" -•\t"):
                continue
        lines.append(pruned)
    return "\n".join(lines)


def review_copy(text: str) -> str:
    """The document for his eyes: internal checklists and build warnings removed.

    The stored material carries the gap checklist and a review reminder for the screen.
    They are meant for him, not for a PDF that may reach an employer, so both copies
    cut them — the review copy keeps only the red legend.
    """
    body = text or ""
    for marker in ("WHAT THIS AD ASKS FOR", ATS_HEADING, REVIEW_REMINDER,
                   "Generated with templates because", "Generated from your real profile data"):
        if marker in body:
            body = body.split(marker)[0]
    return re.sub(r"\n{3,}", "\n\n", body).strip()


def unmark_suggestions(text: str) -> str:
    """The send copy: the same CV, with the suggested additions printed as plain text.

    The addition keeps its words and loses only the brackets and the review furniture —
    the legend, the separate suggestion list and the reminders are cut, so the document
    the employer receives reads as one ordinary CV. He reviews the marked copy first;
    this one is never generated on its own, only derived from that reviewed document.
    """
    body = review_copy(text)
    lines = []
    skipping = False
    for line in body.split("\n"):
        stripped = line.strip()
        if stripped == SUGGESTION_HEADING:
            skipping = True
            continue
        if stripped.startswith("RED ITEMS ARE SUGGESTIONS"):
            continue
        if skipping:
            if not stripped or stripped.startswith("- "):
                continue
            skipping = False
        cleaned = _SUGGESTED_RE.sub(lambda m: m.group(1), line)
        cleaned = re.sub(r"[ \t]+", " ", cleaned).rstrip()
        lines.append(cleaned)
    result = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", result).strip()


def _word_set(name: str) -> frozenset:
    """The meaningful words of a skill name, singularised so "apis" and "api" are one word."""
    out = set()
    for word in re.split(r"[^a-z0-9+#.]+", (name or "").lower()):
        if not word:
            continue
        out.add(word[:-1] if len(word) > 3 and word.endswith("s") else word)
    return frozenset(out)


def _skill_claim(tag: str, skill: str) -> bool:
    """Whether this ad's requirement is one of his skills.

    Whole words only. Plain substring matching let the ad's "Java" claim his "JavaScript",
    and a CV that states a skill he does not have is the one thing this generator must never do.
    """
    if _norm_skill(tag) == _norm_skill(skill):
        return True
    t, s = _word_set(tag), _word_set(skill)
    return bool(t and s and (t <= s or s <= t))


def _end_period(text: str) -> str:
    """Trimmed text ending in exactly one terminal punctuation mark."""
    text = (text or "").strip()
    if not text:
        return ""
    return text if text[-1] in ".!?" else text + "."


def _first_sentence(text: str) -> str:
    """The first sentence of a text, whole and punctuated — never a mid-sentence splice."""
    first = re.split(r"(?<=[.!?])\s+", (text or "").strip())[0].strip()
    return _end_period(first)


def _first_sentences(text: str, count: int) -> str:
    """The first ``count`` sentences, so a pasted profile blurb cannot become a wall."""
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", _usable(text)) if s.strip()]
    return " ".join(_end_period(s) for s in sentences[:count])


_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]+")


def _usable(text: str) -> str:
    """Extracted resume text can carry DEL/control bytes from the PDF bullets."""
    return _CONTROL_RE.sub(" ", text or "")


class _Generated(BaseModel):
    content: str


def _ai_generate(instruction: str, facts: dict) -> str | None:
    if not ai.ai_available():
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


# Re-preparing the same ad must not re-spend the free quota on the letter:
# same cache shape as _CV_AI_CACHE, keyed by job + facts.
_COVER_AI_CACHE: dict[tuple[int, str], str] = {}


def _cover_letter_ai(job: Job, f: dict, extra: str) -> str | None:
    if not ai.ai_available():
        return None
    signature = hashlib.sha256(
        json.dumps({"f": f, "extra": extra}, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()
    cached = _COVER_AI_CACHE.get((job.id, signature))
    if cached is not None:
        return cached
    text = _ai_generate(
        "Write a customized cover letter (3-4 paragraphs, professional, honest) for this candidate "
        "applying to this job. Sign with the candidate's real name or [Your Name]." + extra, f)
    if text:
        if len(_COVER_AI_CACHE) > 8:
            _COVER_AI_CACHE.clear()
        _COVER_AI_CACHE[(job.id, signature)] = text
    return text


_CV_AI_CACHE: dict[tuple[int, str], str] = {}


def _cv_ai(job: Job, f: dict, extra_notes: str = "") -> str | None:
    """The sendable CV written by the AI, aimed at this one ad and built ONLY from
    his real facts. Returns None when no AI key is configured or the call fails,
    so the deterministic template stays the fallback.

    The output is plain text in the PDF renderer's vocabulary (ALL-CAPS headings,
    "- " bullets), and the internal honesty notes are never part of it.
    """
    if not ai.ai_available():
        return None
    signature = hashlib.sha256(
        json.dumps({"f": f, "extra": extra_notes}, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()
    cached = _CV_AI_CACHE.get((job.id, signature))
    if cached is not None:
        return cached
    system = (
        "You are an expert resume writer. You receive structured JSON facts about a real candidate "
        "and the exact job posting he is applying to. Rewrite his CV so it targets THIS job. "
        "Hard rules: "
        "Use ONLY the facts given — NEVER invent experience, qualifications, projects, certificates, "
        "metrics, dates, or personal details. "
        "If he has no evidence for something the posting asks for, mark it as a suggestion instead of "
        "claiming it: write it inside double square brackets, exactly like [[REST APIs]]. Only a skill, "
        "tool or competency may be bracketed — never an employer, a job, a date, a degree, a "
        "certificate, a number or a project, and never bracket something already in his facts. "
        "Bracket at most six, starting with the ones the posting names first, so the CV stays credible. "
        "Keep his name, email, phone and links exactly as given. "
        "If a company/employer name is empty in the facts, never invent one — write that role with "
        "its dates and location only. "
        "The SKILLS section is his proven skills from candidate_skills plus his languages, with any "
        "bracketed suggestions last. "
        "Omit any section the facts have no entries for (e.g. PROJECTS, EDUCATION) — never print an "
        "empty heading. "
        "Weave the posting's real keywords (its skill list and key phrases) into the summary and "
        "bullets only where they truthfully match his facts. "
        "If the candidate_resume fact is present, treat it as his base CV and keep its real content; "
        "reword, reorder and tailor, never add to it. "
        "His base CV may be messy — broken lines, tables, columns, icons, mixed bullet styles, "
        "dates written any way. Do not copy its layout: rebuild every fact into the clean "
        "structure below, drop decorative separators, page numbers and repeated headers, and "
        "write dates as 'Mon YYYY' (Jan 2024 - Present). "
        "Use exactly one SKILLS section; never split it into several skills headings. "
        "Format for an applicant tracking system: plain single-column text, the ALL-CAPS headings "
        "given below, one line per item, no tables, no columns, no graphics, no emoji, no markdown, "
        "no brackets other than the suggestion brackets."
    )
    instruction = (
        "LAYOUT (plain text): "
        "NAME (in ALL CAPS) on the first line; "
        "a contact line with email, phone and links under it; "
        "section headings in ALL CAPS: PROFESSIONAL SUMMARY, SKILLS, EXPERIENCE, PROJECTS, "
        "EDUCATION, LANGUAGES; "
        "skills and experience as '- ' bullets; "
        "lead with the skills and roles this ad names that he truly has; "
        "each experience bullet starts with the job title, company and period, then 2-3 short "
        "achievement sentences taken from his real description. "
        "Keep it to one page. The job is: \"{job_title}\" at {company}.{extra}"
    ).format(job_title=job.title, company=job.company or "an unnamed company",
             extra=f"\nThe user added: {extra_notes}" if extra_notes else "")
    text = ai.chat_text(system, instruction + "\n\nFACTS:\n" + json.dumps(f, ensure_ascii=False),
                        temperature=0.4)
    if not text or len(text.strip()) < 100:
        return None
    text = text.strip()
    for marker in ("WHAT THIS AD ASKS FOR", REVIEW_REMINDER):
        if marker in text:
            text = text.split(marker)[0].strip()
    if len(_CV_AI_CACHE) > 8:
        _CV_AI_CACHE.clear()
    _CV_AI_CACHE[(job.id, signature)] = text
    return text


def _facts(job: Job, profile: UserProfile | None) -> dict:
    profile = profile or UserProfile()
    return dict(
        job_title=job.title,
        company=job.company,
        job_description=(job.description or "")[:2500],
        job_skills=job_skill_tags(job),
        candidate_name=profile.full_name,
        candidate_email=profile.email,
        candidate_phone=profile.phone,
        candidate_city=profile.city,
        candidate_country=profile.country,
        candidate_summary=profile.summary,
        candidate_resume=(profile.resume_text or "")[:6000],
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

    # Only the two materials an employer reads (the CV and the cover letter) spend
    # AI quota; the helpers below stay on the free deterministic templates so one
    # application costs 2 AI calls instead of 4.
    if kind == "keywords":
        content = _keywords(job, f)

    elif kind == "summary":
        content = _summary(job, f)

    elif kind == "bullets":
        content = _bullets(job, f)

    elif kind == "cover_letter":
        content = _cover_letter(job, f)
        ai_text = _cover_letter_ai(job, f, extra)
        if ai_text:
            content, template_based = ai_text, False

    elif kind == "email":
        content = _email(job, f)

    elif kind == "cv":
        # The same AI pass serves both: the marked copy he reviews here and the PDF later.
        ai_text = _cv_ai(job, f, extra_notes)
        content = _cv_pack(job, f, marked=True, ai_text=ai_text)
        send_copy = _cv_pack(job, f, marked=False, ai_text=ai_text)
        report = ats.format_report(ats.ats_check(send_copy, job_skill_tags(job)))
        content += ("\n\n" + "\n".join(_gap_notes(job, f))
                    + "\n\n" + "\n".join(report)
                    + "\n\n" + REVIEW_REMINDER)
        template_based = ai_text is None

    elif kind == "questions":
        content = _questions(job, f)

    warning = ""
    if template_based:
        if kind in ("cv", "cover_letter"):
            warning = "Generated with templates because no AI API key is configured (or the AI call failed). " + REVIEW_REMINDER
        else:
            warning = "Generated from your real profile data with the built-in template. " + REVIEW_REMINDER
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
        company = f" at {exp['company']}" if exp.get("company") else ""
        if exp.get("current"):
            period = f" ({exp['start']} - present)" if exp.get("start") else " (currently)"
        elif exp.get("start") or exp.get("end"):
            start, end = exp.get("start"), exp.get("end")
            period = f" ({start} - {end})" if start and end else f" ({start or end})"
        else:
            period = ""
        first = _first_sentence(_usable(exp["description"]))
        detail = ""
        if first:
            # Lowercased and closed by this sentence's own period: "— managed ... ."
            detail = f" — {(first[0].lower() + first[1:]).rstrip('.!?')}"
        parts.append(f"Most recently, {name} worked as {exp['title']}{company}{period}{detail}.")
    if projects:
        parts.append(f"{name} has built {len(projects)} project(s), including "
                     + ", ".join(p["name"] for p in projects[:3]) + ".")
    if f["candidate_summary"]:
        parts.append(_first_sentences(f["candidate_summary"], 2))
    parts.append("Applying for the " + job.title + " role"
                 + (f" at {job.company}" if job.company else "") + ".")
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


def _evidence_words(f: dict) -> frozenset:
    evidence = " ".join([s["name"].lower() for s in f["candidate_skills"]]
                        + [f"{e['title']} {e['description']}".lower() for e in f["experience"]]
                        + [f"{p['name']} {p['description']} {' '.join(p['technologies'])}".lower()
                           for p in f["projects"]]
                        + [(f["candidate_summary"] or "").lower()]
                        + [lang.lower() for lang in f["languages"]])
    return _word_set(evidence)


def _unproven_requirements(job: Job, f: dict) -> list[str]:
    """What this ad asks for that his own data cannot show yet."""
    evidence_words = _evidence_words(f)
    owned = [s["name"] for s in f["candidate_skills"]]
    out: list[str] = []
    for tag in job_skill_tags(job):
        low = tag.lower()
        if any(_skill_claim(low, name) for name in owned) or _word_set(low) <= evidence_words:
            continue
        if low not in {o.casefold() for o in out}:
            out.append(tag)
    return out


def _gap_notes(job: Job, f: dict, marked: bool = False) -> list[str]:
    """The honesty section for HIS eyes: what this ad asks that his data cannot show."""
    gaps = _unproven_requirements(job, f)[:8]
    shown = [mark_suggestion(g) for g in gaps] if marked else gaps
    return ["WHAT THIS AD ASKS FOR THAT YOUR CV DOES NOT SHOW YET",
            (", ".join(shown) + "." if shown
             else "Nothing - every skill this ad names already appears in your profile.")]


def _heading(line: str) -> str:
    """A CV section heading line, or "" when the line is ordinary text.

    Only a line that is entirely upper case, starts with a letter and carries no
    suggestion brackets counts, so "POS" on a skills line is never read as a heading.
    """
    text = line.strip()
    if len(text) > 2 and text[0].isalpha() and "[[" not in text and text.isupper():
        return text
    return ""


def _insert_suggestions(cv_text: str, items: list[str]) -> str:
    """Add the red block under the CV's last skills heading.

    An ATS reads the skills section first and so does a recruiter, which is where the
    lines he has to confirm or delete belong. The block gets its own heading so a
    suggestion can never sit under a line that claims these are skills he already has.
    A CV whose AI left a skills heading out gets the block appended instead, never
    dropped.
    """
    block = [SUGGESTION_HEADING] + [f"- {mark_suggestion(item)}" for item in items]
    lines = cv_text.split("\n")
    start = next((i for i in range(len(lines) - 1, -1, -1) if _heading(lines[i]).startswith("SKILL")),
                 None)
    if start is None:
        return cv_text.rstrip() + "\n\n" + "\n".join(block)
    end = start + 1
    while end < len(lines) and not _heading(lines[end]):
        end += 1
    while end > start + 1 and not lines[end - 1].strip():
        end -= 1
    lines[end:end] = [""] + block
    return "\n".join(lines)


def _cv(job: Job, f: dict, include_gaps: bool = True) -> str:
    """A whole CV aimed at this one ad, built only from what he really entered.

    Ordering is the tailoring: the skills and roles the ad names come first, and anything
    the ad asks for that his own data cannot back is listed as a gap instead of being
    quietly claimed. The gap list is for his eyes, so the sendable PDF renders the same
    CV with ``include_gaps=False`` and drops it.
    """
    name = f["candidate_name"] or "[Your name]"
    contact = " | ".join(x for x in [
        f["candidate_email"], f["links"].get("linkedin"), f["links"].get("github"),
        f["links"].get("portfolio")] if x) or "[add your email and links in Resume & Profile]"
    tags = [t.lower() for t in job_skill_tags(job)]
    skills = f["candidate_skills"]
    evidence_words = _evidence_words(f)
    asked = [s for s in skills if any(_skill_claim(t, s["name"]) for t in tags)]
    rest = [s for s in skills if s not in asked]

    def relevance(entry: dict) -> int:
        text = f"{entry.get('title', '')} {entry.get('description', '')}".lower()
        return sum(1 for t in tags if t in text)

    experience = sorted(f["experience"], key=relevance, reverse=True)
    lines = [
        name.upper(), contact, "",
        f"TARGET ROLE: {job.title}" + (f" at {job.company}" if job.company else ""),
        "", "PROFESSIONAL SUMMARY", _summary(job, f), "",
    ]
    if asked:
        lines += ["SKILLS THIS AD ASKS FOR, WHICH YOU HAVE",
                  ", ".join(s["name"] for s in asked), ""]
    if rest:
        lines += ["OTHER SKILLS", ", ".join(s["name"] for s in rest), ""]
    lines.append("EXPERIENCE")
    if experience:
        for e in experience:
            period = e.get("start") or ""
            if e.get("current"):
                period = f"{period} - present" if period else "present"
            elif e.get("end"):
                period = f"{period} - {e['end']}" if period else e["end"]
            at = ", ".join(x for x in [e.get("company"), e.get("location")] if x)
            lines.append(f"- {e['title']}" + (f" - {at}" if at else "")
                         + (f" ({period})" if period else ""))
            for sentence in [s.strip() for s in re.split(r"[.;·\n]\s*", _usable(e["description"]))
                             if s.strip()][:4]:
                lines.append(f"    {_end_period(sentence)}")
    else:
        lines.append("- [No work experience recorded yet - add it in Resume & Profile.]")
    lines.append("")
    if f["projects"]:
        lines.append("PROJECTS")
        for p in f["projects"]:
            tech = ", ".join(p["technologies"])
            lines.append(f"- {p['name']}" + (f" ({tech})" if tech else "")
                         + (f" - {p['url']}" if p["url"] else ""))
            if p["description"]:
                lines.append(f"    {p['description']}")
        lines.append("")
    lines.append("EDUCATION")
    if f["education"]:
        for ed in f["education"]:
            lines.append(f"- {ed['degree']}" + (f" in {ed['field']}" if ed["field"] else "")
                         + (f" - {ed['institution']}" if ed["institution"] else ""))
    else:
        lines.append("- [Add your education in Resume & Profile.]")
    if f["languages"]:
        lines += ["", "LANGUAGES", ", ".join(f["languages"])]
    if include_gaps:
        lines += ["", *_gap_notes(job, f), "", REVIEW_REMINDER]
    return "\n".join(lines)


def _cv_pack(job: Job, f: dict, marked: bool, ai_text: str | None = None) -> str:
    """The tailored CV, either as the review copy (additions in red) or the send copy.

    Every copy first passes the ATS normalizer, so an AI draft that copied a messy
    base CV still comes out with standard headings, one bullet style and plain text.
    ``marked`` puts every requirement this ad wants that his data cannot show into the
    skills block as a bracketed suggestion, which the PDF renderer draws red and
    underlined. ``marked=False`` keeps those same additions, bracketed text unwrapped
    and the legend cut, so the employer's copy carries the tailoring but none of the
    review marks — he decides himself what to stand behind before sending it.
    """
    body = (ai_text if ai_text is not None else _cv_ai(job, f)) or _cv(job, f, include_gaps=False)
    body = ats.normalize_cv(body)
    body = _limit_suggestions(body)
    if not marked:
        return unmark_suggestions(body)
    already = {item.casefold() for item in suggested_items(body)}
    items = [gap for gap in _unproven_requirements(job, f)
             if gap.casefold() not in already][:max(0, MAX_SUGGESTIONS - len(already))]
    if items:
        body = _insert_suggestions(body, items)
    # The AI brackets its own suggestions too, so the legend follows any red line
    # that survived into this copy — never only the ones this function inserted.
    if suggested_items(body):
        body = body.rstrip() + "\n\n" + CV_LEGEND
    return body


def cv_for_pdf(job: Job, profile: UserProfile | None, marked: bool = True) -> str:
    """The CV text the PDF is built from — never the checklist meant for his eyes.

    ``marked`` (the default) is the copy he reviews before sending: the ad's missing
    requirements sit in the skills block in red with the legend that says they are
    suggestions. ``marked=False`` is the copy for an employer: the same text without
    the brackets, the legend or the review notes.
    """
    return _cv_pack(job, _facts(job, profile), marked)


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
