"""Search phrases and the relevance gate derived from the owner's own profile.

A profile usually mixes three kinds of wording: desired titles, skills, and the
titles of the jobs actually held. Long skill names ("Customer Support & Complaint
Handling") are good on a CV but useless as a board query and as an exact-phrase
test, so this module turns them into the short phrases a board answers and into a
deliberately lenient gate: a posting is kept when its title or text shares real
role/skill wording with the profile, not only when it repeats a whole phrase.

The gate never invents data and is never stored: it is recomputed from the
profile on each import, and when the profile carries no discriminating wording
(only "Excel", "English" and the like) it is disabled rather than guessing.
"""
from __future__ import annotations

import re

from .matching import _LEXICON_BY_NORM, _norm_skill

_SPLIT = re.compile(r"\s*(?:&|/|,|;|\+|\band\b)\s*", re.I)
_PARENS = re.compile(r"\([^)]*\)")

# Phrases that describe how someone works rather than what the job is. They are
# useless as a search term and match nearly every posting, so they are ignored.
_SOFT_PHRASES = {
    "problem solving", "decision making", "problem solving & decision making",
    "communication", "communication skills", "teamwork", "team work",
    "time management", "leadership", "adaptability", "adaptable",
    "attention to detail", "hard working", "work under pressure",
    "microsoft office", "ms office", "office suite", "computer skills",
}
_LOW_SIGNAL = {
    "problem", "solving", "decision", "making", "communication", "communicate",
    "teamwork", "team", "time", "management", "leadership", "adaptability",
    "adaptable", "detail", "details", "working", "hard", "skill", "skills",
    "knowledge", "ability", "abilities", "strong", "good", "excellent", "basic",
    "advanced", "english", "arabic", "french", "german", "spanish", "language",
    "languages", "excel", "word", "powerpoint", "outlook", "office", "microsoft",
    "windows", "email", "emails", "typing", "internet", "computer", "computers",
    "operations", "operation", "operational", "handling", "duties", "tasks",
    # Ubiquitous in corporate prose ("cross-functional", "support the business",
    # "customer service" already carries "customer"), so they cannot discriminate.
    "support", "service", "cross", "selling", "solutions", "business",
    # A job family of its own, not evidence of his cash-handling skill; and
    # "center" alone matches "distribution center" but says nothing.
    "compliance", "center",
}

# Words every title has; they say nothing about the role being a fit.
_GENERIC_ROLE = {
    "developer", "engineer", "manager", "specialist", "analyst", "officer",
    "agent", "executive", "coordinator", "administrator", "supervisor",
    "assistant", "associate", "representative", "consultant", "technician",
    "lead", "head", "director", "senior", "junior", "intern", "internship",
    "trainee", "entry", "level", "staff", "member", "clerk", "worker",
    "position", "role", "job", "jobs", "and", "the", "of", "for", "with",
    "a", "an", "to", "in", "on", "at",
}
_SENIORITY = {"junior", "senior", "lead", "mid", "entry", "level", "head",
              "chief", "principal", "staff", "trainee", "intern", "internship"}
_ROLE_TAIL = {"rep", "representative", "agent", "specialist", "associate",
              "officer", "executive", "assistant", "coordinator", "consultant",
              "administrator", "admin", "clerk", "worker", "member",
              "technician", "supervisor", "manager", "director"}
_TRAILING_NOUN = {"systems", "system", "tools", "tool", "software",
                  "applications", "application"}

# A few skill names have a shorter form boards actually answer ("CRM Systems"
# is searched as "CRM", "Call Center Operations" as "Call Center").
_SHORT_FORMS = {
    "crm systems": "CRM",
    "crm system": "CRM",
    "call center operations": "Call Center",
    "call centre operations": "Call Center",
    "point of sale": "POS",
    "point-of-sale": "POS",
    "retail banking sales": "Retail Banking Sales",
}


def _clean(text: str) -> str:
    text = _PARENS.sub(" ", text or "")
    return re.sub(r"\s+", " ", text).strip(" -–—.,;")


def _segments(text: str) -> list[str]:
    return [seg for seg in (_clean(part) for part in _SPLIT.split(text or "")) if seg]


def _words(text: str) -> list[str]:
    return [w.strip(".") for w in re.findall(r"[a-z0-9+#.]+", (text or "").casefold())
            if w.strip(".")]


def _signal_words(text: str) -> set[str]:
    return {w for w in _words(text)
            if len(w) > 1 and w not in _LOW_SIGNAL and w not in _GENERIC_ROLE}


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        key = value.casefold()
        if key and key not in seen:
            seen.add(key)
            out.append(value)
    return out


def skill_phrases(skill: str) -> list[str]:
    """The searchable pieces of one saved skill, e.g. "Customer Support" + "Complaint Handling"."""
    out: list[str] = []
    for segment in _segments(skill):
        low = segment.casefold()
        if low in _SOFT_PHRASES:
            continue
        short = _SHORT_FORMS.get(low)
        if short:
            out.append(short)
            continue
        words = segment.split()
        if len(words) > 2 and words[-1].casefold() in _TRAILING_NOUN:
            head = " ".join(words[:-1])
            if _signal_words(head):
                out.append(head)
        if _signal_words(segment) or len(words) == 1 and len(segment) >= 2:
            out.append(segment)
    return _dedupe([p for p in out if _searchable(p)])


def _searchable(phrase: str) -> bool:
    words = _words(phrase)
    if not words:
        return False
    return any(w not in _LOW_SIGNAL and w not in _GENERIC_ROLE for w in words) or (
        len(words) == 1 and len(words[0]) >= 2 and words[0] not in _LOW_SIGNAL
    )


def role_phrases(title: str) -> list[str]:
    """A held job title turned into role wording: "Retail Sales Rep" -> "Retail Sales"."""
    out: list[str] = []
    for segment in _segments(title):
        words = [w for w in segment.split() if w.casefold() not in _SENIORITY] or segment.split()
        if len(words) >= 2 and words[-1].casefold() in _ROLE_TAIL:
            words = words[:-1]
        phrase = " ".join(words)
        if _searchable(phrase):
            out.append(phrase)
    return _dedupe(out)


def expand_terms(titles: list[str], skills: list[str]) -> list[str]:
    """Titles first (as written), then the short pieces of each skill."""
    out = _dedupe([_clean(t) for t in titles if _clean(t)])
    for skill in skills:
        out.extend(skill_phrases(skill))
    return _dedupe(out)


def _phrase_pattern(phrase: str) -> re.Pattern:
    parts = [p for p in re.split(r"[\s/_-]+", phrase.casefold()) if p]
    return re.compile(r"(?<!\w)" + r"[\s/_-]+".join(re.escape(p) for p in parts) + r"(?!\w)")


def _skill_key(name: str) -> str:
    canon = _LEXICON_BY_NORM.get(_norm_skill(name), name)
    return _norm_skill(canon) or name.casefold()


def build_gate(titles: list[str], skills: list[str], roles: list[str] | None = None):
    """A lenient title/text filter, or None when the profile has no usable wording.

    Accepted when the title names a profile role/skill phrase, when it shares a
    real role/skill word, or when the posting text carries at least three distinct
    such words (a description often names the work without repeating the title).
    """
    role_forms = _dedupe([p for raw in [*titles, *(roles or [])] for p in _segments(raw)])
    skill_forms = _dedupe([p for skill in skills for p in skill_phrases(skill)])
    role_words = {w for form in role_forms for w in _signal_words(form)}
    skill_words = {w for form in skill_forms for w in _signal_words(form)}
    if not role_words and not skill_words:
        return None

    title_patterns = [_phrase_pattern(f) for f in role_forms if len(_words(f)) > 1]
    skill_patterns = [_phrase_pattern(f) for f in skill_forms if len(_words(f)) > 1]
    strong = role_words | skill_words
    known_skills = {_skill_key(skill) for skill in skills if _skill_key(skill)}

    def matches(pj) -> bool:
        title = (pj.title or "").casefold()
        if any(p.search(title) for p in title_patterns):
            return True
        if any(p.search(title) for p in skill_patterns):
            return True
        title_words = set(_words(title))
        if title_words & strong:
            return True
        text = f"{title} {pj.description or ''}"
        hits = strong.intersection(_words(text))
        if len(hits) >= 3:
            return True
        tags = {_skill_key(tag) for tag in (pj.skills or []) if tag}
        return bool(known_skills & tags)

    return matches
