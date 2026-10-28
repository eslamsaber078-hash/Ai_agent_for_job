"""Spelling tolerance for the terms people type by hand.

A single swapped letter in a skill or a job title ("Raect", "Fluttr Developer")
used to become a search phrase no board answers, and the relevance filter then
rejected every job the feeds did return. This module maps a typed term to the
closest known term so a typo costs nothing, and it reports the change so the UI
can show what was actually searched.

Rules that keep the correction honest:
- exact known terms are never touched;
- a correction needs a close edit distance, the same first letter, and a clear
  best candidate (two equally close terms mean "cannot tell", so nothing moves);
- unknown terms are left exactly as typed — the vocabulary only covers terms
  this app knows, not the user's private wording;
- stored profile data is never rewritten; corrections apply to search and
  matching only, and are shown to the user.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

MAX_TERM_LENGTH = 80
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")

# Terms the matcher's lexicon does not need (it only detects text), but the typo
# check must know so it never "corrects" a valid term into a different one
# ("Rust" must never become "REST").
EXTRA_SKILLS = [
    "ai", "go", "rust", "ruby", "ruby on rails", "rails", "php", "laravel", "codeigniter",
    "swiftui", "objective-c", "jetpack compose", "next.js", "nuxt", "svelte", "express",
    "nestjs", "spring boot", "hibernate", "jpa", "oracle", "sqlite", "dynamodb", "cassandra",
    "elasticsearch", "rabbitmq", "kafka", "grpc", "websockets", "socket.io", "jwt", "oauth",
    "terraform", "ansible", "jenkins", "github actions", "gitlab ci", "nginx", "apache",
    "prometheus", "grafana", "cypress", "playwright", "postman", "swagger", "manual testing",
    "test automation", "unit testing", "figma", "adobe xd", "canva", "photoshop",
    "illustrator", "premiere pro", "after effects", "blender", "autocad", "solidworks",
    "revit", "3d modeling", "unreal engine", "game design", "level design", "seo",
    "google ads", "meta ads", "tiktok ads", "email marketing", "content marketing",
    "digital marketing", "social media marketing", "salesforce", "hubspot", "crm", "erp",
    "sap", "quickbooks", "tally", "bookkeeping", "payroll", "accounting", "auditing",
    "financial analysis", "data entry", "translation", "arabic", "french", "german",
    "spanish", "it support", "help desk", "active directory", "ccna", "ccnp",
    "comptia a+", "windows server", "ubuntu", "lead generation", "cold calling",
    "negotiation", "business development", "video editing", "motion graphics",
    "photography", "copywriting", "content writing", "project management", "agile",
    "scrum", "jira", "trello", "business analysis", "matlab", "simulink", "plc", "scada",
    "powerpoint", "google sheets", "power query", "vba",
]

# Shorthands people legitimately type; they must be understood, not "corrected".
SKILL_ALIASES = {
    "js": "JavaScript", "ts": "TypeScript", "py": "Python", "k8s": "Kubernetes",
    "postgres": "PostgreSQL", "mongo": "MongoDB", "mssql": "SQL Server",
    "nodejs": "Node.js", "node": "Node.js", "reactjs": "React", "vuejs": "Vue",
    "angularjs": "Angular", "html5": "HTML", "css3": "CSS", "golang": "Go",
    "dotnet": ".NET", "csharp": "C#", "ml": "Machine Learning", "qa": "QA",
    "ui": "UI", "ux": "UX", "ui ux": "UI/UX", "api": "REST APIs",
}

TITLE_VOCAB = [
    "Software Developer", "Software Engineer", "Full Stack Developer",
    "Frontend Developer", "Backend Developer", "Web Developer", "Mobile Developer",
    "Flutter Developer", "Flutter Engineer", "Android Developer", "iOS Developer",
    "React Developer", "React Native Developer", "Angular Developer", "Vue Developer",
    "JavaScript Developer", "TypeScript Developer", "Node.js Developer",
    "Python Developer", "Python Engineer", "Django Developer", "Java Developer",
    "Spring Boot Developer", ".NET Developer", "C# Developer", "PHP Developer",
    "Laravel Developer", "WordPress Developer", "Shopify Developer", "Game Developer",
    "Embedded Software Engineer", "Robotics Engineer", "RPA Developer",
    "Machine Learning Engineer", "AI Engineer", "Data Scientist", "Data Analyst",
    "Data Engineer", "Business Intelligence Developer", "Database Administrator",
    "DevOps Engineer", "Cloud Engineer", "Site Reliability Engineer",
    "QA Engineer", "QA Tester", "Test Automation Engineer", "Software Tester",
    "Security Engineer", "Cybersecurity Analyst", "Network Engineer",
    "System Administrator", "IT Support Specialist", "Help Desk Technician",
    "UI Designer", "UX Designer", "UI/UX Designer", "Product Designer",
    "Graphic Designer", "Motion Designer", "Video Editor", "Photographer",
    "Product Manager", "Project Manager", "Program Manager", "Scrum Master",
    "Business Analyst", "Technical Writer", "Technical Support Engineer",
    "Customer Support Specialist", "Customer Service Representative",
    "Sales Engineer", "Sales Representative", "Account Manager", "Accountant",
    "Auditor", "Financial Analyst", "HR Specialist", "Recruiter",
    "Operations Manager", "Marketing Specialist", "Digital Marketing Specialist",
    "Social Media Specialist", "Content Writer", "Copywriter", "SEO Specialist",
    "Administrative Assistant", "Office Manager", "Receptionist", "Store Manager",
    "Retail Manager", "Logistics Coordinator", "Procurement Specialist",
    "Supply Chain Manager", "Mechanical Engineer", "Civil Engineer",
    "Electrical Engineer", "Industrial Engineer", "Architect", "Teacher",
    "Nurse", "Pharmacist", "Doctor", "Lawyer", "Translator", "Chef", "Cashier",
    "Call Center Agent", "Customer Success Manager", "Business Development Manager",
]

LOCATION_VOCAB = [
    "Egypt", "Cairo", "New Cairo", "Alexandria", "Giza", "6th of October",
    "Mansoura", "Tanta", "Aswan", "Luxor", "Port Said", "Suez", "Ismailia",
    "Hurghada", "Sharm El Sheikh", "Remote", "Riyadh", "Jeddah", "Dammam",
    "Mecca", "Medina", "Dubai", "Abu Dhabi", "Sharjah", "Doha", "Kuwait City",
    "Manama", "Muscat", "Amman", "Beirut", "Damascus", "Baghdad", "Casablanca",
    "Rabat", "Tunis", "Algiers", "Tripoli", "Khartoum", "Istanbul", "Ankara",
    "London", "Berlin", "Paris", "Amsterdam", "Madrid", "Rome", "Toronto",
    "New York", "USA", "UK", "Germany", "France", "Canada", "Saudi Arabia",
    "UAE", "Qatar", "Kuwait", "Jordan", "Lebanon", "Morocco", "Tunisia",
    "Algeria", "Turkey", "Europe",
]

_KIND_SKILL = "skill"
_KIND_TITLE = "title"
_KIND_LOCATION = "location"

# Words inside titles that say nothing about the role itself; correcting a
# misspelt one is not useful, and "senior" is not a role name.
_TOKEN_STOP = {"senior", "junior", "lead", "mid", "entry", "level",
               "and", "the", "of", "for", "with"}


@dataclass(frozen=True)
class Correction:
    typed: str
    corrected: str
    kind: str


@dataclass(frozen=True)
class _Vocabulary:
    display: dict[str, str]
    tokens: dict[str, str]


def normalize(text: str) -> str:
    """Comparison form: lowercase, punctuation and spacing removed ("Node.js" -> "nodejs")."""
    return re.sub(r"[^a-z0-9+#.]+", "", (text or "").lower())


def clean_term(raw) -> str:
    """Trim, collapse whitespace and cap length so one pasted essay cannot become a query."""
    if not isinstance(raw, str):
        return ""
    text = _CONTROL.sub(" ", raw)
    return " ".join(text.split())[:MAX_TERM_LENGTH].strip()


def _distance(a: str, b: str, limit: int) -> int:
    """Optimal-string-alignment distance (a transposition costs one edit: "raect" -> "react")."""
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    prev2 = None
    prev = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        cur = [i]
        row_min = i
        for j in range(1, len(b) + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            value = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                value = min(value, prev2[j - 2] + 1)
            cur.append(value)
            if value < row_min:
                row_min = value
        if row_min > limit:
            return limit + 1
        prev2, prev = prev, cur
    return prev[-1]


def _limits(length: int) -> tuple[int, float]:
    if length <= 5:
        return 1, 0.70
    if length <= 8:
        return 2, 0.68
    if length <= 14:
        return 3, 0.65
    return 4, 0.62


def _closest(norm: str, vocab: dict[str, str]) -> str | None:
    """The one close known term, or None when nothing is close or two are equally close."""
    if len(norm) < 4 or norm in vocab:
        return None
    max_edits, min_ratio = _limits(len(norm))
    best_key, best_ratio, second_ratio = None, 0.0, 0.0
    for key in vocab:
        if key[0] != norm[0] or abs(len(key) - len(norm)) > max_edits + 1:
            continue
        dist = _distance(norm, key, max_edits)
        if dist > max_edits:
            continue
        ratio = 1 - dist / max(len(norm), len(key))
        if ratio < min_ratio:
            continue
        if ratio > best_ratio:
            second_ratio, best_ratio, best_key = best_ratio, ratio, key
        elif ratio > second_ratio:
            second_ratio = ratio
    if best_key is None or best_ratio - second_ratio < 0.05:
        return None
    return vocab[best_key]


@lru_cache(maxsize=1)
def _vocabularies() -> dict[str, _Vocabulary]:
    from .matching import SKILL_LEXICON, _canonical

    skills: dict[str, str] = {}
    # Every spelling the matcher already recognises is exact: "rest" is a known
    # skill ("REST APIs"), not a typo of "Rust".
    for raw in SKILL_LEXICON:
        canonical = _canonical(raw)
        for spelling in (raw, canonical):
            key = normalize(spelling)
            if key:
                skills.setdefault(key, canonical)
    for name in EXTRA_SKILLS:
        key = normalize(name)
        if key:
            skills.setdefault(key, name)
    for alias, target in SKILL_ALIASES.items():
        key = normalize(alias)
        if key:
            skills.setdefault(key, target)

    titles: dict[str, str] = {}
    for name in TITLE_VOCAB:
        titles.setdefault(normalize(name), name)

    locations: dict[str, str] = {}
    for name in LOCATION_VOCAB:
        locations.setdefault(normalize(name), name)

    tokens: dict[str, str] = {}
    for display in titles.values():
        for word in re.split(r"[\s/-]+", display):
            key = normalize(word)
            if len(key) >= 4 and key not in _TOKEN_STOP:
                tokens.setdefault(key, word)

    return {
        _KIND_SKILL: _Vocabulary(skills, {}),
        _KIND_TITLE: _Vocabulary(titles, tokens),
        _KIND_LOCATION: _Vocabulary(locations, {}),
    }


def _capitalize_like(original: str, replacement: str) -> str:
    return replacement[:1].upper() + replacement[1:] if original[:1].isupper() else replacement


def _fix_words(text: str, tokens: dict[str, str]) -> str | None:
    """Correct the misspelled word(s) of a phrase that is not itself in the vocabulary.

    A single edit, keeping the first and last letter, is what separates a typo
    ("developr" -> "developer") from a different word ("developer" -> "development").
    Larger changes are left alone: guessing those would rewrite real role names.
    """
    changed = False
    words = []
    for word in text.split():
        norm = normalize(word)
        fixed = None
        if tokens and len(norm) >= 4 and norm not in tokens:
            candidates = {
                display for key, display in tokens.items()
                if (len(key) == len(norm) or abs(len(key) - len(norm)) == 1) and key[0] == norm[0]
                and key[-1] == norm[-1] and _distance(norm, key, 1) <= 1
            }
            if len(candidates) == 1:
                fixed = candidates.pop()
        if fixed:
            words.append(_capitalize_like(word, fixed))
            changed = True
        else:
            words.append(word)
    return " ".join(words) if changed else None


def suggest(term: str, kind: str) -> str | None:
    """The term this one most likely meant, or None when it is already known or unclear."""
    term = clean_term(term)
    norm = normalize(term)
    if not norm:
        return None
    vocab = _vocabularies().get(kind)
    if vocab is None:
        return None
    if norm in vocab.display:
        return None
    fixed = _closest(norm, vocab.display)
    if fixed:
        return fixed
    if kind == _KIND_TITLE:
        return _fix_words(term, vocab.tokens)
    return None


def canonical_skill(name: str) -> str:
    """The known spelling of a skill, or the user's own text when it is not a known typo."""
    resolved = suggest(name, _KIND_SKILL)
    return resolved or (name or "").strip()


def canonical_title(name: str) -> str:
    return suggest(name, _KIND_TITLE) or (name or "").strip()


def _reconcile_list(values, kind: str, corrections: list[Correction]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in values or []:
        term = clean_term(raw)
        if not term:
            continue
        fixed = suggest(term, kind) or term
        key = fixed.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(fixed)
        if fixed.casefold() != term.casefold():
            corrections.append(Correction(typed=term, corrected=fixed, kind=kind))
    return out


def reconcile_terms(titles, skills, locations) -> tuple[list[str], list[str], list[str], list[Correction]]:
    """The corrected search lists plus the changes, ready to report to the user."""
    corrections: list[Correction] = []
    clean_titles = _reconcile_list(titles, _KIND_TITLE, corrections)
    clean_skills = _reconcile_list(skills, _KIND_SKILL, corrections)
    clean_locations = _reconcile_list(locations, _KIND_LOCATION, corrections)
    return clean_titles, clean_skills, clean_locations, corrections
