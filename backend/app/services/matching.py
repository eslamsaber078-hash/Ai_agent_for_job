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
import threading

from pydantic import BaseModel, ValidationError

from ..models import Job, UserProfile
from . import ai
from .terms import canonical_skill, canonical_title

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
    "android", "ios",
]


def _canonical(skill: str) -> str:
    aliases = {
        "csharp": "C#", "asp.net": ".NET", "rest": "REST APIs", "rest api": "REST APIs",
        "rest apis": "REST APIs",
        "node.js": "Node.js", "sql server": "SQL Server", "power bi": "Power BI",
        "ios": "iOS", "ci/cd": "CI/CD", "aws": "AWS", "sql": "SQL", "html": "HTML",
        "css": "CSS", "oop": "OOP", "etl": "ETL", "rpa": "RPA",
        "javascript": "JavaScript", "typescript": "TypeScript",
    }
    return aliases.get(skill, skill.replace("-", " ").title())


def _norm_skill(name: str) -> str:
    return re.sub(r"[^a-z0-9+#.]", "", (name or "").lower())


# One alternation instead of a per-skill scan: 65 passes over a 3,400-character
# description took 13 seconds to score his live jobs, and the dashboard repeats it
# on every load. Longest first so "rest api" wins over "rest" at the same spot.
_ALTERNATIVES = sorted({s.lower() for s in SKILL_LEXICON}, key=len, reverse=True)
_DETECT_ALL = re.compile(
    r"(?<![a-z0-9+#.])(" + "|".join(re.escape(s) for s in _ALTERNATIVES) + r")(?![a-z0-9])"
)
_TOKEN = re.compile(r"[a-z0-9+#.]+")

# "provider" is both a Flutter package and an ordinary English word ("service provider"),
# so it only counts as a skill where the posting is actually about Flutter/Dart.
_CONTEXT_TERMS = {"provider": ("flutter", "dart")}

# The same skill spelled differently by a job board ("C Sharp", "ci/cd") is one skill.
_LEXICON_BY_NORM = {_norm_skill(s): _canonical(s) for s in SKILL_LEXICON}

LEVEL_ORDER = {
    "intern": 0, "internship": 0, "trainee": 0, "entry": 1, "entry-level": 1, "entry level": 1,
    "junior": 1, "graduate": 1, "new": 1, "mid": 2, "mid-level": 2, "mid level": 2,
    "intermediate": 2, "associate": 2, "senior": 3, "staff": 3, "specialist": 3,
    "lead": 4, "principal": 4, "head": 4, "manager": 4, "director": 4, "": 1,
}

# The level words boards write, spelled in Arabic for the Arabic summary. A value the
# map does not know is left as the board wrote it rather than guessed at.
_LEVEL_AR = {
    "intern": "متدرب", "internship": "تدريب", "trainee": "متدرب", "entry": "مبتدئ",
    "entry-level": "مبتدئ", "entry level": "مبتدئ", "junior": "جونيور",
    "graduate": "حديث التخرج", "new": "مبتدئ", "mid": "متوسط الخبرة",
    "mid-level": "متوسط الخبرة", "mid level": "متوسط الخبرة",
    "intermediate": "متوسط الخبرة", "associate": "مساعد", "senior": "سينيور",
    "staff": "ستاف", "specialist": "سبشياليست", "lead": "قائد فريق",
    "principal": "برينسبال", "head": "رئيس قسم", "manager": "مدير",
    "director": "مدير تنفيذي",
}


def _level_ar(text: str, lang: str) -> str:
    if lang != "ar" or not text:
        return text
    return _LEVEL_AR.get(text.strip().lower(), text)


def _levels_ar(values, lang: str) -> str:
    """"entry, intern, junior" reads as Arabic words in the Arabic summary."""
    words = [_level_ar(v, lang) for v in values]
    return ("، " if lang == "ar" else ", ").join(words)


# Requirements a posting must name before its skills factor counts as full evidence.
MIN_SKILL_EVIDENCE = 3

# A posting that states nothing about a factor gets this much credit, not a neutral 50.
# The neutral value used to hand every empty ad ~34 free points, which put a British
# project-coordinator role within nine points of a Cairo mobile developer opening.
UNKNOWN = 25.0

# Words that name a place only in the sense of "not a place": boards write "Remote",
# "Anywhere" and "Worldwide" into location fields, and matching them as cities gave
# non-remote UK postings a perfect location score.
_PLACE_STOPS = {"remote", "remote only", "anywhere", "worldwide", "global", "any",
                "united states", "usa", "us", "europe", "emea", "latam", "apac"}

# Filler inside the titles he wants: "developer" alone must not pull a PHP shop
# assistant job into his Flutter results.
_TITLE_STOP_WORDS = {"developer", "developers", "software", "engineer", "engineering",
                     "junior", "senior", "mid", "level", "levels", "lead", "entry",
                     "the", "and", "with", "for", "of", "web", "app", "apps"}

_WORD = re.compile(r"[a-z0-9+#.]+")

# A skill his CV states but he never rated himself gets a solid medium, not his top rating.
CV_SKILL_LEVEL = 3

# The most a posting can score when its own headline demands a tool the CV cannot show.
HEADLINE_GAP_CAP = 64

# A headline can name the job or a baseline expectation. "English speaker", "Git" and
# "MS Office" in a title are pluses an HR reader never rejects an otherwise fitting CV
# over, so they do not trigger the cap; the requirements that define the role do.
_HEADLINE_SOFT = {"english", "arabic", "french", "german", "spanish", "portuguese",
                  "italian", "turkish", "hindi", "urdu", "git", "excel", "word",
                  "powerpoint", "outlook", "microsoft office", "ms office", "office"}


def detect_skills(text: str) -> list[str]:
    """Find known skill names inside a free-text job description."""
    lowered = (text or "").lower()
    found = _DETECT_ALL.findall(lowered)
    present = set(found)
    out = []
    for skill in found:
        context = _CONTEXT_TERMS.get(skill)
        if context and not present.intersection(context):
            continue
        out.append(_canonical(skill))
    return list(dict.fromkeys(out))


def _mentioned(name: str, lowered: str, words: set[str]) -> bool:
    """Is this unrecognised tag actually written in the description?"""
    low = name.lower()
    return low in words if " " not in low else low in lowered


def _board_taxonomy(tag: str) -> bool:
    """Shape of a job-board label, not a skill: "10115", "12001 - Account Executives"."""
    return any(char.isdigit() for char in tag) or len(tag.split()) > 2 or len(tag) > 24


_TAG_CACHE: dict[tuple, list[str]] = {}


def job_skill_tags(job: Job) -> list[str]:
    """The skills a posting actually asks for, without the board's own noise.

    Raw provider tags carry job-board numbers, cities and seniority words ("10115",
    "Berlin", "senior", "12001 - Account Executives"). Each one counted as a required
    skill he lacks, so honest matches sank below his minimum score. A tag survives only
    when it is a known skill or the posting genuinely says it.

    The title counts as evidence for *known* skills: LinkedIn's list cards arrive with no
    description at all, and a "Flutter Developer" opening plainly asks for Flutter.
    Unrecognised tags still have to appear in the description, because a headline is full
    of board vocabulary ("Senior", "Urgent Hiring") that is not a requirement list.

    The answer depends on nothing but these three columns, so it is remembered for the
    posting: scanning a 4,000-character ad once per page instead of once per page view is
    most of what the scoring costs. A re-import that edits the text changes the key.
    """
    key = (job.id, job.title, job.description, tuple(job.skills or []))
    cached = _TAG_CACHE.get(key)
    if cached is not None:
        return cached
    out = _derive_skill_tags(job)
    if len(_TAG_CACHE) > 6000:
        _TAG_CACHE.clear()
    _TAG_CACHE[key] = out
    return out


def _derive_skill_tags(job: Job) -> list[str]:
    title_and_text = " ".join(part for part in (job.title, job.description) if part)
    lowered = (job.description or "").lower()
    words = set(_TOKEN.findall(lowered))
    out, seen = [], set()
    for tag in [*(job.skills or []), *detect_skills(title_and_text)]:
        raw = (tag or "").strip()
        norm = _norm_skill(raw)
        name = _LEXICON_BY_NORM.get(norm, raw)
        key = _norm_skill(name)
        if not raw or key in seen or len(key) < 2:
            continue
        if norm not in _LEXICON_BY_NORM and (_board_taxonomy(name) or not _mentioned(name, lowered, words)):
            continue
        seen.add(key)
        out.append(name)
    return out


def _evidence_text(profile: UserProfile) -> str:
    """Everything he has written about himself: CV body, summary, jobs, projects.

    The job titles he held are part of the evidence: an HR screen reads "Customer
    Service & Sales Representative" as proof of customer-service work, and leaving
    titles out of the text made postings ask for things his CV plainly shows.
    """
    parts = [profile.summary or "", profile.resume_text or ""]
    parts += [f"{e.title} {e.description or ''}" for e in profile.experiences]
    parts += [f"{p.name} {' '.join(p.technologies or [])} {p.description or ''}" for p in profile.projects]
    parts += [s.name for s in profile.skills]
    return " \n ".join(parts)


def _profile_signature(profile: UserProfile) -> str:
    """What the score reads from his profile, folded into one key.

    Two profiles with the same signature score every posting identically, so the
    worked-out reading below may be reused for the whole list. Self-rated levels and
    years are part of it: they move both his skill weights and the seniority his CV
    shows, even though the CV text itself does not change.
    """
    return "|".join([
        _evidence_text(profile),
        ";".join(f"{s.name}:{s.level}:{s.years}" for s in profile.skills),
        ",".join(sorted(profile.desired_titles or [])),
        ",".join(sorted(profile.target_levels or [])),
        ",".join(sorted(profile.preferred_locations or [])),
        pref_of(profile), home_country(profile), (profile.city or "").lower(),
        f"{profile.min_salary}:{profile.salary_currency}",
    ])


_PROFILE_CTX: dict[str, dict] = {}


def profile_context(profile: UserProfile) -> dict:
    """His profile, read once instead of once per posting.

    Every job on his list is scored against the same CV, so deriving his role phrases,
    seniority ceiling and proven skills again for each of ~3,700 postings was most of
    the Matches page's wait. The key is his own text, so an edited profile is a
    different key and a stale reading cannot survive a change.
    """
    signature = _profile_signature(profile)
    known = _PROFILE_CTX.get(signature)
    if known is not None:
        return known
    evidence: dict[str, tuple[str, float, bool]] = {}
    for s in profile.skills:
        # A misspelt skill still proves the skill: "Raect" is React, so the posting's
        # React requirement is not counted as missing.
        name = canonical_skill(s.name)
        evidence.setdefault(_norm_skill(name), (name, 0.4 + 0.6 * (s.level or 3) / 5, False))
    text = _evidence_text(profile)
    for name in detect_skills(text):
        key = _norm_skill(name)
        if key not in evidence:
            evidence[key] = (name, 0.4 + 0.6 * CV_SKILL_LEVEL / 5, True)
    desired = _desired_titles(profile)
    role_forms = _cv_role_forms(profile)
    known = {
        "evidence": evidence,
        "proven_skills": sorted(name for name, _, _ in evidence.values()),
        "desired": desired,
        "desired_raw": list(profile.desired_titles or []),
        "role_forms": role_forms,
        # The loose words of his own roles, kept so a posting headline is compared
        # against a finished set instead of re-splitting his titles for each job.
        "desired_tokens": {w for t in desired for w in _WORD.findall(t)} - _TITLE_STOP_WORDS,
        "role_tokens": {w for p in role_forms for w in _WORD.findall(p)} - _TITLE_STOP_WORDS,
        "cv_level": _cv_level(profile),
        "targets": {t.lower().strip() for t in profile.target_levels if t.strip()},
        "wanted_places": {l.lower().strip() for l in profile.preferred_locations if l.strip()} - _PLACE_STOPS,
        "home": home_country(profile),
        "pref": pref_of(profile),
    }
    if len(_PROFILE_CTX) > 8:
        _PROFILE_CTX.clear()
    _PROFILE_CTX[signature] = known
    return known


def _desired_titles(profile: UserProfile) -> list[str]:
    """The roles he is after, spelled the way a posting spells them.

    "Flutter Developr" still names the role he is after, so each title goes through the
    same reconciliation the search terms do before it is compared to a headline.
    """
    out: list[str] = []
    for raw in profile.desired_titles:
        if raw.strip():
            resolved = canonical_title(raw).lower().strip()
            if resolved and resolved not in out:
                out.append(resolved)
    return out


def _skills_factor(job: Job, context: dict, job_tags: list[str], lang: str = "en") -> tuple[float, str, list[str], list[str], list[str]]:
    """How much of what THIS posting asks for, his profile + CV already covers."""
    ar = lang == "ar"
    evidence = context["evidence"]
    matched, missing, from_cv = [], [], []
    points = maximum = 0.0
    for tag in job_tags:
        got = evidence.get(_norm_skill(tag))
        weight = 1.0 if got is None else got[1]
        maximum += weight
        if got is None:
            missing.append(tag)
        else:
            matched.append(got[0])
            points += weight
            if got[2]:
                from_cv.append(got[0])
    if not job_tags:
        return (UNKNOWN, ("الإعلان مش كاتب متطلبات، فمينفعش نتأكد من المهارات" if ar
                          else "The posting lists no requirements, so skills cannot be checked"),
                [], [], [])
    score = (points / maximum) * 100 if maximum else 0.0
    detail = (f"مطابق {len(matched)}/{len(job_tags)} من المتطلبات اللي الإعلان كاتبها" if ar
              else f"Matched {len(matched)}/{len(job_tags)} requirements the posting states")
    if len(job_tags) < MIN_SKILL_EVIDENCE:
        # An ad that names one or two requirements leaves the rest unknown. Half-credit
        # for the unnamed part: a single shared keyword must not claim a full match, but
        # it must not be treated as a mismatch either — that buried his Flutter roles.
        gap = MIN_SKILL_EVIDENCE - len(job_tags)
        score = (points + 0.5 * gap) / (maximum + gap) * 100
        detail += (f" — مكتوب {len(job_tags)} بس، والباقي مش متأكد منه" if ar
                   else f" — only {len(job_tags)} stated, the rest is unverified")
    if from_cv:
        detail += (f" ({', '.join(sorted(from_cv))} مثبتة من سيرتك وخبراتك المكتوبة)" if ar
                   else f" ({', '.join(sorted(from_cv))} proven by your CV and experience text)")
    return score, detail, matched, missing, from_cv


def _level_in_title(title: str) -> tuple[int, str] | None:
    """The seniority a title states when the posting's level field is empty.

    Boards such as LinkedIn and We Work Remotely put "Junior"/"Senior" only in the
    headline. Reading it makes a junior ad score correctly instead of getting the
    no-information mark.
    """
    text = (title or "").lower().replace("-", " ").replace("/", " ")
    found = [(order, word) for word, order in LEVEL_ORDER.items()
             if word and re.search(rf"\b{re.escape(word)}\b", text)]
    return max(found) if found else None


def _cv_level(profile: UserProfile) -> tuple[int, str] | None:
    """The seniority his own CV shows, used when he never set target levels.

    Read from the titles he actually held first (a "Senior" title is evidence), then
    from the years he entered against his strongest skill. When the CV says nothing
    about either, nothing is guessed and None comes back.

    The second element is a wording tag ("title"/"years") plus the raw value, so the
    caller can spell the sentence in either language.
    """
    held = [pair for pair in (_level_in_title(e.title) for e in profile.experiences) if pair]
    if held:
        order, word = max(held)
        return order, f"title|{word}"
    years = max((s.years or 0 for s in profile.skills), default=0)
    if years <= 0:
        return None
    if years >= 5:
        return 3, f"years|{years:g}"
    if years >= 2:
        return 2, f"years|{years:g}"
    return 1, f"years|{years:g}"


def _cv_level_wording(tag: str, lang: str) -> str:
    """Spell the CV-level evidence the way `_cv_level` tagged it, in either language."""
    kind, _, value = tag.partition("|")
    if kind == "title":
        return (f"اشتغلت قبل كده {value}" if lang == "ar" else f"you have worked as a {value}")
    n = float(value)
    if lang == "ar":
        return f"{n:g} سنين في المجال" if n >= 2 else f"{n:g} سنة في المجال"
    return f"{n:g} years in the field" if n >= 2 else f"{n:g} year in the field"


def _level_factor(job: Job, context: dict, lang: str = "en") -> tuple[float, str, str]:
    """Score the seniority, and hand back the level we read ("" when nothing says one).

    The label goes into the written summary too, so the concerns never claim the
    posting hid its level when the headline already stated it.

    When he set no target levels, an HR reader still judges the ad against the CV:
    the seniority of his own last titles and the years he entered decide the ceiling.
    """
    ar = lang == "ar"
    raw = (job.experience_level or "").strip().lower()
    targets = context["targets"]
    label = job.experience_level
    from_title = False
    if raw in ("any", "any level", "all levels"):
        if ar:
            return 80.0, f"المستوى: {_level_ar(job.experience_level, lang)} — مفتوح لأي مستوى", label
        return 80.0, f"Level: {job.experience_level} — open to any", label
    order = LEVEL_ORDER.get(raw) if raw else None
    if not raw:
        in_title = _level_in_title(job.title)
        if in_title:
            order, label = in_title
            from_title = True
    if order is None:
        if ar:
            return (UNKNOWN, ("الإعلان مش محدد مستوى خبرة" if not raw
                              else f"المستوى: {job.experience_level} — مش مستوى معروف عندنا"), "")
        return (UNKNOWN, ("The posting states no experience level" if not raw
                          else f"Level: {job.experience_level} — not a level we recognise"), "")
    shown = _level_ar(label, lang)
    noted = " (مقروء من المسمى)" if (from_title and ar) else (" (read from the title)" if from_title else "")
    if targets:
        ceiling = max(LEVEL_ORDER.get(t, 1) for t in targets)
        basis = (f"المستوى المستهدف بتاعك ({_levels_ar(sorted(targets), lang)})" if ar
                 else f"your target ({', '.join(sorted(targets))})")
    else:
        derived = context["cv_level"]
        if derived is None:
            if ar:
                return 50.0, f"المستوى: {shown} (انت محددتش مستوى مستهدف)", label
            return 50.0, f"Level: {label} (you set no target level)", label
        ceiling, tag = derived
        basis = (f"اللي سيرتك بتوريه ({_cv_level_wording(tag, 'ar')})" if ar
                 else f"what your CV shows ({_cv_level_wording(tag, 'en')})")
    if order <= ceiling:
        return 100.0, (f"مستوى {shown} مناسب مع {basis}{noted}" if ar
                       else f"Level {label} fits {basis}{noted}"), label
    if order == ceiling + 1:
        return 55.0, (f"مستوى {shown} درجة أعلى من {basis}{noted}" if ar
                      else f"Level {label} is one step above {basis}{noted}"), label
    return 20.0, (f"مستوى {shown} أعلى بـ {order - ceiling} درجات من {basis}{noted}" if ar
                  else f"Level {label} is {order - ceiling} steps above {basis}{noted}"), label


_WORLD_WORDS = {"remote", "remotely", "anywhere", "worldwide", "global", "world",
                "distributed", "n", "a", "any"}
_REGION_WORDS = {"europe", "emea", "latam", "apac", "americas", "africa", "asia", "pacific"}


def pref_of(profile: UserProfile) -> str:
    """His remote/hybrid/onsite choice, spelled the way the rules read it."""
    return (profile.remote_preference or "open").lower()


# The dialling codes the accounts here use. A blank country field must not make an
# ad in his own country read as "outside the places you chose".
_PHONE_COUNTRY = {"+20": "Egypt", "0020": "Egypt", "010": "Egypt", "011": "Egypt",
                  "012": "Egypt", "015": "Egypt"}


def home_country(profile: UserProfile) -> str:
    """Where he lives: what the profile states, or what his own account number says."""
    country = (profile.country or "").strip()
    if country:
        return country
    digits = re.sub(r"[^\d+]", "", profile.phone or "")
    for prefix, name in _PHONE_COUNTRY.items():
        if digits.startswith(prefix):
            return name
    return ""


def _place_label(job: Job) -> str:
    """The real place a board names, skipping a filler "Remote" written as the country.

    Jobicy puts the region in `location` and the word "Remote" in `country`; reading the
    country blindly produced limits like "the Remote region".
    """
    filler = {"remote", "remotely", "anywhere", "worldwide", "global", "open to remote"}
    for part in (job.country, job.location):
        text = (part or "").strip()
        if text and text.lower() not in filler:
            return text
    return "an unstated place"


def _title_place(title: str) -> str:
    """A city or country written in the headline, e.g. "Support Engineer (Denver, CO)".

    A board can tick "remote" for a role that is only open to people in one US state, so
    the headline is sometimes the only honest location evidence the ad gives. Only the
    "City, Region" shape is read, so "(New Business)" cannot be mistaken for a place.
    """
    for text in re.findall(r"\(([^()]{4,40})\)", title or ""):
        parts = [p.strip() for p in text.split(",")]
        if len(parts) != 2:
            continue
        city, region = parts
        if not re.fullmatch(r"[A-Z][a-z]{2,15}", city):
            continue
        if not re.fullmatch(r"[A-Z]{2}|[A-Z][a-z]{2,14}", region):
            continue
        words = {w.lower() for w in (city, region)}
        if words & (_WORLD_WORDS | _REGION_WORDS | {"wfh", "remote", "anywhere"}):
            continue
        return text.strip()
    return ""


def _where_wording(job: Job) -> str:
    """The most specific place the board wrote, for sentences that name a city."""
    return (job.location or "").strip() or _place_label(job)


_PREF_AR = {"remote": "ريموت", "hybrid": "هجين", "onsite": "حضوري", "open": "مفتوح"}


def _location_factor(job: Job, profile: UserProfile, context: dict, lang: str = "en") -> tuple[float, str]:
    """Where the posting really is, judged against where he can work.

    "Remote" written as the location counts even when the source left the flag off, and
    a remote job restricted to one country he cannot live in is scored as the near-nothing
    it is for him.
    """
    ar = lang == "ar"
    place = f"{job.location} {job.country}".strip().lower()
    words = set(_WORD.findall(place))
    home = context["home"]
    country = home.lower()
    where = _place_label(job)
    unstated = "بلد مش محدد" if ar else "an unstated country"
    # A board can write "Remote" as the place without setting the remote flag; when the
    # location says nothing but "remote", the posting is open from anywhere.
    worldwide = not words or words <= _WORLD_WORDS or bool(words & {"anywhere", "worldwide", "global", "world"})
    if job.remote or worldwide:
        if country and country in place:
            if ar:
                return 100.0, f"ريموت، وبيذكر {home} — بلدك انت"
            return 100.0, f"Remote, and it names {home} — your own country"
        named = _title_place(job.title)
        if named:
            if any(w in named.lower() for w in [country, (profile.city or "").lower()] if w):
                if ar:
                    return 100.0, f"المسمى بتاعه بيقول {named}، وده مكان تقدر تشتغل فيه"
                return 100.0, f"Its headline says {named}, which is where you can work"
            if ar:
                return 20.0, (f"المسمى بتاعه بيقول {named} — ريموت بس مش متاح غير من هناك "
                              f"(وانت في {home or unstated})")
            return 20.0, (f"Its headline says {named} — remote, but only reachable from there "
                          f"(you are in {home or 'an unstated country'})")
        if worldwide:
            pref = _PREF_AR.get(context["pref"], context["pref"]) if ar else context["pref"]
            if ar:
                return 90.0, f"ريموت من غير تحديد بلد؛ وتفضيلك هو {pref}"
            return 90.0, f"Remote with no country limit; your preference is {context['pref']}"
        if words & _REGION_WORDS:
            if ar:
                return 55.0, f"ريموت، بس محدود بمنطقة {where}"
            return 55.0, f"Remote, but limited to the {where} region"
        if ar:
            return 20.0, f"ريموت، بس لـ {where} — وانت في {home or 'مصر'}"
        return 20.0, f"Remote, but only for {where} — you are in {home or 'Egypt'}"
    if not words:
        return UNKNOWN, ("الإعلان مش محدد مكان" if ar else "The posting states no location")
    wanted = context["wanted_places"]
    if any(w in place for w in wanted if len(w) > 2):
        if ar:
            return 100.0, f"{job.location} من الأماكن اللي اخترتها"
        return 100.0, f"{job.location} is one of the places you chose"
    if not wanted:
        # He never listed cities, so his own address is what an HR reader checks.
        city = (profile.city or "").strip().lower()
        if city and len(city) > 2 and city in place:
            if ar:
                return 100.0, f"{job.location} هي المدينة اللي انت ساكن فيها ({profile.city})"
            return 100.0, f"{job.location} is the city you live in ({profile.city})"
        if country and country in place:
            if ar:
                return 85.0, f"{job.country or job.location} هو بلدك"
            return 85.0, f"{job.country or job.location} is your country"
    if country and country in place:
        if ar:
            return 85.0, f"{job.country or job.location} هو بلدك، بس مش من المدن اللي اخترتها"
        return 85.0, f"{job.country or job.location} is your country, though not one of your cities"
    if not wanted and not profile.city:
        if ar:
            return 15.0, (f"{_where_wording(job)} مش مكان بروفايلك بيقول انك بتشتغل فيه، "
                          f"ومش ريموت")
        return 15.0, (f"{_where_wording(job)} is not a place your profile says you work in, "
                      f"and it is not remote")
    if ar:
        return 15.0, f"{_where_wording(job)} برا الأماكن اللي اخترتها، ومش ريموت"
    return 15.0, f"{_where_wording(job)} is outside the places you chose, and it is not remote"


def _cv_role_forms(profile: UserProfile) -> list[str]:
    """The roles his own work history states, shortened the way a board writes them.

    "Retail Sales Representative" on the CV makes a "Sales Representative" ad a real
    fit even when he never typed a desired title, so the CV is read as the reference.
    """
    from .keywords import role_phrases

    out: list[str] = []
    for exp in profile.experiences:
        for phrase in role_phrases((exp.title or "").strip()):
            low = phrase.casefold()
            if low and low not in out:
                out.append(low)
    return out


def _title_factor(job: Job, context: dict, lang: str = "en") -> tuple[float, str]:
    ar = lang == "ar"
    desired = context["desired"]
    proven = context["role_forms"]
    title = (job.title or "").lower()
    if not desired and not proven:
        return 50.0, ("انت محددتش مسميات وظايف مستهدفة" if ar else "You have not set desired job titles")
    if any(t in title for t in desired):
        return 100.0, (f'"{job.title}" من الأدوار اللي انت بتدوّر عليها' if ar
                       else f"\"{job.title}\" is one of the roles you are after")
    shown = next((p for p in proven if p in title), "")
    if shown:
        # He has done this job; an HR reader weights proven history above a wish list.
        return (85.0 if desired else 90.0), (
            f'"{job.title}" هو الدور اللي سيرتك بتوريه ({shown})'
            + (", بس مش من المسميات اللي انت محددها" if desired else "") if ar else
            f"\"{job.title}\" is the role your CV already shows ({shown})"
            + (", though not one of the titles you set" if desired else ""))
    words = set(_WORD.findall(title))
    shared = sorted(context["desired_tokens"] & words)
    if shared:
        return 60.0, (f"مشترك مع أدوارك المستهدفة في: {', '.join(shared)}، بس مش واحد منهم" if ar
                      else f"Shares {', '.join(shared)} with your target roles, but is not one of them")
    shared_cv = sorted(context["role_tokens"] & words)
    if shared_cv:
        return 55.0, (f"مشترك مع أدوار سيرتك في: {', '.join(shared_cv)}، بس مش واحد منهم" if ar
                      else f"Shares {', '.join(shared_cv)} with the roles on your CV, but is not one of them")
    named = ", ".join(context["desired_raw"] or proven)
    return 20.0, (f'"{job.title}" دور مختلف عن {named}' if ar
                  else f"\"{job.title}\" is a different role from {named}")


def _salary_factor(job: Job, profile: UserProfile, lang: str = "en") -> tuple[float, str]:
    ar = lang == "ar"
    if not job.salary_min:
        return UNKNOWN, ("الإعلان منشرش مرتب" if ar else "The posting publishes no salary")
    if not profile.min_salary:
        if ar:
            return 50.0, f"الوظيفة بتدفع {job.salary_min}+ {job.salary_currency or ''}؛ وانت محددتش حد أدنى"
        return 50.0, f"Job pays {job.salary_min}+ {job.salary_currency or ''}; you set no minimum"
    both = f"{job.salary_min}-{job.salary_max or '?'} {job.salary_currency or '?'}"
    mine = f"{profile.min_salary} {profile.salary_currency or ''}".strip()
    job_cur = (job.salary_currency or "").upper()
    my_cur = (profile.salary_currency or "").upper()
    if job_cur and my_cur and job_cur != my_cur:
        if ar:
            return UNKNOWN, f"{both} — عملة مختلفة، فمينفعش نقارنها بالحد الأدنى بتاعك {mine}"
        return UNKNOWN, f"Job pays {both} — a different currency, so it cannot be compared to your {mine}"
    if job.salary_min >= profile.min_salary:
        if ar:
            return 100.0, f"{both} بتحقق الحد الأدنى بتاعك {mine}"
        return 100.0, f"{both} meets your minimum of {mine}"
    if job.salary_max and job.salary_max >= profile.min_salary:
        if ar:
            return 70.0, f"{both} بتوصل للحد الأدنى بتاعك {mine} في أعلى رينج بس"
        return 70.0, f"{both} only reaches your minimum of {mine} at the top"
    if ar:
        return 20.0, f"{both} أقل من الحد الأدنى بتاعك {mine}"
    return 20.0, f"{both} is under your minimum of {mine}"


class _AIAnalysis(BaseModel):
    why_match: str = ""
    concerns: str = ""
    next_steps: list[str] = []


# The AI narrative for one job/profile pair: opening the same match panel again
# must not spend another free-quota call. Failures are cached too, so an
# exhausted quota does not retry on every view.
_NARRATIVE_CACHE: dict[tuple[int, str, str], _AIAnalysis | None] = {}
_NARRATIVE_INFLIGHT: set[tuple[int, str, str]] = set()
_NARRATIVE_LOCK = threading.Lock()


def _narrative_key(job: Job, profile: UserProfile, lang: str) -> tuple[int, str, str]:
    signature = (
        _evidence_text(profile) + "|" + ",".join(sorted(profile.desired_titles or []))
        + "|" + ",".join(sorted(profile.target_levels or []))
    )
    return (job.id, signature, lang)


def _narrative_prompt(job: Job, facts: dict, lang: str) -> tuple[str, str]:
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
    if lang == "ar":
        system += (" اكتب كل النصوص بالعربي المصري. متكتبش أي كلمة إنجليزية زي \"candidate\" "
                   "أو \"skills\" — استخدم «المتقدم» و«مهاراتك» وسمّي الوظيفة والمهارات "
                   "بأسمائها زي ما هي.")
    return system, json.dumps(payload, ensure_ascii=False)


def _narrative_lookup(key: tuple[int, str, str]) -> tuple[bool, _AIAnalysis | None]:
    with _NARRATIVE_LOCK:
        return key in _NARRATIVE_CACHE, _NARRATIVE_CACHE.get(key)


def _run_narrative(key: tuple[int, str, str], system: str, user: str) -> None:
    """The slow half, off the request path: one provider call, then the cache write."""
    result = None
    try:
        data = ai.chat_json(system, user)
        if data:
            try:
                result = _AIAnalysis(**data)
            except ValidationError:
                result = None
    except Exception:  # noqa: BLE001
        log.exception("Narrative generation failed; keeping the measured prose")
    finally:
        with _NARRATIVE_LOCK:
            if len(_NARRATIVE_CACHE) > 16:
                _NARRATIVE_CACHE.clear()
            _NARRATIVE_CACHE[key] = result
            _NARRATIVE_INFLIGHT.discard(key)


def _schedule_narrative(key: tuple[int, str, str], system: str, user: str) -> None:
    """Start the model's version in the background; never make the panel wait for it.

    A free provider that stalls used to hold the request for its whole 20 s timeout,
    while the measured breakdown was ready in milliseconds and the model only
    rewrites the prose. One worker per answer: a second view while it runs joins the
    first instead of spending another quota call.
    """
    with _NARRATIVE_LOCK:
        if key in _NARRATIVE_CACHE or key in _NARRATIVE_INFLIGHT:
            return
        _NARRATIVE_INFLIGHT.add(key)
    threading.Thread(target=_run_narrative, args=(key, system, user),
                     name="match-narrative", daemon=True).start()


def compute_match(job: Job, profile: UserProfile | None, use_ai: bool = True, lang: str = "en",
                  detail: bool = True) -> dict:
    """Compute a transparent 0-100 match score with a full breakdown.

    ``use_ai`` is turned off by list endpoints: the score is deterministic, so
    paying one AI round-trip per job would only slow the page down.

    ``detail=False`` skips the written explanation and factor rows. Ranking a whole
    account scores thousands of postings to show fifty, and building five paragraphs
    of prose for each posting nobody will read was most of that wait; the fifty that
    are actually returned get the full breakdown.

    Every factor is scored on what the posting and his profile actually state. A
    posting that says nothing about level, salary or requirements gets no neutral
    credit for it, so the number reads as confirmed fit rather than polite filler.
    """
    if profile is None:
        return _empty_match(job, lang)
    if not any([profile.skills, profile.experiences, profile.projects,
                profile.desired_titles, profile.summary, profile.resume_text]):
        return _empty_match(job, lang)

    context = profile_context(profile)
    job_tags = job_skill_tags(job)
    skill_score, skill_detail, matched, missing, from_cv = _skills_factor(job, context, job_tags, lang)
    level_score, level_detail, level_label = _level_factor(job, context, lang)
    location_score, location_detail = _location_factor(job, profile, context, lang)
    title_score, title_detail = _title_factor(job, context, lang)
    salary_score, salary_detail = _salary_factor(job, profile, lang)
    title_hit = title_score == 100.0

    # Title outweighs location and salary: a posting for a role he is not after is not a
    # match no matter how well its stack overlaps his CV.
    weights = {"skills": 0.40, "level": 0.15, "location": 0.15, "title": 0.20, "salary": 0.10}
    total = (
        weights["skills"] * skill_score
        + weights["level"] * level_score
        + weights["location"] * location_score
        + weights["title"] * title_score
        + weights["salary"] * salary_score
    )

    # An HR reader takes the headline first: when the job title itself demands a tool the
    # CV cannot show, the role is not his however well the body of the ad overlaps.
    evidence = context["evidence"]
    headline_gaps = [t for t in detect_skills(job.title or "")
                     if _norm_skill(t) not in evidence and t.lower() not in _HEADLINE_SOFT]
    hard_gap = ""
    if headline_gaps:
        total = min(total, HEADLINE_GAP_CAP)
        gap_list = ", ".join(headline_gaps[:3])
        if lang == "ar":
            hard_gap = f"المسمى الوظيفي نفسه طالب {gap_list}، ودي مش ظاهرة في سيرتك ومهاراتك لسه."
        else:
            hard_gap = f"The job title itself asks for {gap_list}, which your CV and skills do not show yet."
    score = max(0, min(100, round(total)))

    factors = []
    why = concerns = ""
    steps = []
    ai_enhanced = False
    if detail:
        factors = [
            dict(label="Skills", detail=skill_detail, weight=weights["skills"], score=round(skill_score)),
            dict(label="Experience level", detail=level_detail, weight=weights["level"], score=round(level_score)),
            dict(label="Location & remote", detail=location_detail, weight=weights["location"], score=round(location_score)),
            dict(label="Job title fit", detail=title_detail, weight=weights["title"], score=round(title_score)),
            dict(label="Salary", detail=salary_detail, weight=weights["salary"], score=round(salary_score)),
        ]

        why = _why_match(job, profile, matched, from_cv, title_hit, level_score, level_label,
                         location_score, job_tags, lang)
        concerns = _concerns(job, profile, missing, level_score, level_label, location_score,
                             location_detail, hard_gap, lang)
        steps = _next_steps(job, missing, score, profile, lang)

    narrative_pending = False
    if detail and use_ai and ai.ai_available():
        # Only the model needs his history written out as a payload; a list score must
        # not rebuild it for every one of the thousands of postings it passes through.
        facts = {
            "job_skills": job_tags,
            "profile_skills": context["proven_skills"],
            "experience": [
                dict(title=e.title, company=e.company,
                     period=f"{e.start_date or '?'} - {e.end_date or 'present' if e.current else e.end_date or '?'}",
                     description=e.description[:300])
                for e in profile.experiences
            ],
            "projects": [dict(name=p.name, technologies=p.technologies) for p in profile.projects],
            "missing_skills": missing,
            "headline_gap": hard_gap,
            "desired_titles": profile.desired_titles,
        }
        # Every field the worker needs is read here, on the request's thread; it must
        # never touch this session from another thread.
        key = _narrative_key(job, profile, lang)
        known, enriched = _narrative_lookup(key)
        if not known:
            system, user = _narrative_prompt(job, facts, lang)
            _schedule_narrative(key, system, user)
            narrative_pending = True
        if enriched:
            why = enriched.why_match or why
            concerns = enriched.concerns or concerns
            steps = enriched.next_steps or steps
            ai_enhanced = True
            # The model rewrites the prose; the headline gap is a measured fact and stays.
            if hard_gap and hard_gap not in concerns:
                concerns = f"{hard_gap} {concerns}".strip()

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
        hard_gap=hard_gap,
        ai_enhanced=ai_enhanced,
        narrative_pending=narrative_pending,
    )


def _empty_match(job: Job, lang: str = "en") -> dict:
    ar = lang == "ar"
    if ar:
        return dict(
            job_id=job.id, score=0, estimate=True,
            matched_skills=[], missing_skills=job_skill_tags(job),
            factors=[dict(label="Profile", detail="لسه مفيش بروفايل أو سيرة ذاتية — السكور محتاج واحد منهم.",
                          weight=1.0, score=0)],
            why_match="ضيف مهاراتك أو ارفع السيرة الذاتية في صفحة السيرة والملف عشان يظهرلك سكور المطابقة.",
            concerns="لسه مفيش حاجة معروفة عن خبراتك.",
            next_steps=["ارفع سيرتك الذاتية واملأ المهارات والخبرات والمسميات المطلوبة في صفحة السيرة والملف."],
            hard_gap="",
            ai_enhanced=False,
        )
    return dict(
        job_id=job.id, score=0, estimate=True,
        matched_skills=[], missing_skills=job_skill_tags(job),
        factors=[dict(label="Profile", detail="No profile or CV on file yet — scores need one of them.",
                      weight=1.0, score=0)],
        why_match="Add your skills or upload your CV in the Resume & Profile page to get a match score.",
        concerns="Nothing is known about your experience yet.",
        next_steps=["Upload your CV and fill in skills, experience and desired titles in Resume & Profile."],
        hard_gap="",
        ai_enhanced=False,
    )


def _why_match(job, profile, matched, from_cv, title_hit, level_score, level_label,
               location_score, job_tags, lang: str = "en") -> str:
    ar = lang == "ar"
    parts = []
    if matched:
        if ar:
            note = f" ({len(from_cv)} منهم مثبتة من سيرتك الذاتية وخبراتك)" if from_cv else ""
            parts.append(f"عندك {len(matched)} من أصل {len(job_tags)} مهارة الإعلان طالبها{note}: "
                         f"{', '.join(matched[:6])}.")
        else:
            note = f" ({len(from_cv)} proven by your CV and experience text)" if from_cv else ""
            parts.append(f"You already have {len(matched)} of the {len(job_tags)} "
                         f"skills this posting asks for{note}: {', '.join(matched[:6])}.")
    if title_hit:
        parts.append(f"المسمى \"{job.title}\" من الأدوار اللي انت بتدوّر عليها." if ar
                     else f"The title \"{job.title}\" is one of the roles you are after.")
    if level_score >= 80 and level_label:
        parts.append(f"مستوى الإعلان ({_level_ar(level_label, lang)}) مناسب للهدف بتاعك." if ar
                     else f"Its level ({level_label}) fits your target.")
    if location_score >= 90:
        parts.append(f"المكان مناسب ليك ({_where_wording(job)}"
                     f"{', ريموت' if job.remote else ''})." if ar else
                     f"Location works for you ({_where_wording(job)}"
                     f"{', remote' if job.remote else ''}).")
    if profile.projects:
        n = len(profile.projects)
        if ar:
            projects_word = "مشروع واحد" if n == 1 else f"{n} مشاريع"
            parts.append(f"معاك {projects_word} بورتفوليو يدعّم طلب التقديم.")
        else:
            parts.append(f"Your {n} portfolio project{'' if n == 1 else 's'} can support the application.")
    if not parts:
        parts.append("الإعلان ده مكتوب فيه حاجات قليلة بتغطيها بروفايلك وسيرتك، فمفيش حاجة هنا تاخد سكور عالي لسه." if ar
                     else "This posting states little that your profile and CV already cover, "
                          "so there is nothing here that can score high yet.")
    return " ".join(parts)


def _concerns(job, profile, missing, level_score, level_label, location_score,
              location_detail, hard_gap="", lang: str = "en") -> str:
    ar = lang == "ar"
    parts = []
    if hard_gap:
        parts.append(hard_gap)
    if missing:
        if ar:
            parts.append(f"مهارات محتاج تقويها عشان الإعلان ده: {', '.join(missing[:8])}.")
        else:
            parts.append(f"Skills to strengthen for this one: {', '.join(missing[:8])}.")
    if level_label and level_score < 60:
        parts.append(f"مستواه ({_level_ar(level_label, lang)}) أعلى من اللي انت مستهدفه." if ar
                     else f"Its level ({level_label}) is above what you are targeting.")
    elif not level_label:
        parts.append("الإعلان مبيقولش عايز مستوى إيه، فالنقطة دي مش متأكدة." if ar
                     else "It never states which level it wants, so that part stays unverified.")
    if location_score < 60:
        # Quoting the scored detail keeps the prose from inventing a second, and usually
        # contradictory, description of the place.
        parts.append("مكان الشغل مش مناسب ليك." if ar else f"Where it is worked: {location_detail}.")
    if not job.salary_min:
        parts.append("المرتب مش منشور، فمينفعش نتأكد من الحد الأدنى بتاعك." if ar
                     else "No salary published, so your minimum cannot be checked.")
    if not parts:
        parts.append("مفيش مخاوف كبيرة واضحة من اللي مكتوب في بروفايلك وسيرتك." if ar
                     else "No major concerns detected from what your profile and CV state.")
    return " ".join(parts)


def _next_steps(job, missing, score, profile, lang: str = "en") -> list[str]:
    ar = lang == "ar"
    steps = []
    if missing:
        steps.append(f"اعمل مشروع صغير أو خد كورس يغطي: {', '.join(missing[:4])}." if ar
                     else f"Build a small project or take a course covering: {', '.join(missing[:4])}.")
    if not profile.projects:
        steps.append("ضيف على الأقل مشروع بورتفوليو واحد له علاقة بالدور ده." if ar
                     else "Add at least one portfolio project related to this role.")
    steps.append("ظبّط ملخص السيرة الذاتية على وصف الوظيفة قبل ما تقدّم." if ar
                 else "Tailor your resume summary to the job description before applying.")
    steps.append("اقرا عن الشركة وجهّز سؤالين تلاتة للانترفيو." if ar
                 else "Research the company and prepare 2-3 questions for the interview.")
    return steps
