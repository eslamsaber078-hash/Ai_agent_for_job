"""Make a generated CV parse cleanly in an applicant tracking system.

The AI writes the words; this module fixes the mechanics that ATS parsers score:
one canonical name per section, one bullet style, plain ASCII, "Mon YYYY" dates,
no tables, columns, emoji or decorative rules. It moves and reshapes text only —
it never adds a fact, and it leaves the ``[[suggestion]]`` brackets untouched so
the review copy still marks them.
"""
import re
import unicodedata

ATS_HEADING = "ATS READINESS CHECK"

SUMMARY = "PROFESSIONAL SUMMARY"
SKILLS = "SKILLS"
EXPERIENCE = "EXPERIENCE"
PROJECTS = "PROJECTS"
EDUCATION = "EDUCATION"
CERTIFICATIONS = "CERTIFICATIONS"
LANGUAGES = "LANGUAGES"
AWARDS = "AWARDS"

SECTION_ORDER = (SUMMARY, SKILLS, EXPERIENCE, PROJECTS, EDUCATION,
                 CERTIFICATIONS, LANGUAGES, AWARDS)

# Every common spelling of a section an ATS knows, mapped to the one name parsers
# match most reliably. A line with one of these names starts a section.
HEADINGS = {
    "SUMMARY": SUMMARY,
    "PROFESSIONAL SUMMARY": SUMMARY,
    "PROFILE": SUMMARY,
    "PROFESSIONAL PROFILE": SUMMARY,
    "OBJECTIVE": SUMMARY,
    "CAREER OBJECTIVE": SUMMARY,
    "ABOUT ME": SUMMARY,
    "ABOUT": SUMMARY,
    "SKILLS": SKILLS,
    "TECHNICAL SKILLS": SKILLS,
    "CORE SKILLS": SKILLS,
    "KEY SKILLS": SKILLS,
    "SKILLS & TOOLS": SKILLS,
    "SKILLS THIS AD ASKS FOR, WHICH YOU HAVE": SKILLS,
    "OTHER SKILLS": SKILLS,
    "EXPERIENCE": EXPERIENCE,
    "WORK EXPERIENCE": EXPERIENCE,
    "PROFESSIONAL EXPERIENCE": EXPERIENCE,
    "EMPLOYMENT HISTORY": EXPERIENCE,
    "WORK HISTORY": EXPERIENCE,
    "PROJECTS": PROJECTS,
    "PROJECT EXPERIENCE": PROJECTS,
    "SELECTED PROJECTS": PROJECTS,
    "EDUCATION": EDUCATION,
    "EDUCATION & TRAINING": EDUCATION,
    "EDUCATIONAL BACKGROUND": EDUCATION,
    "CERTIFICATIONS": CERTIFICATIONS,
    "CERTIFICATES": CERTIFICATIONS,
    "LICENSES & CERTIFICATIONS": CERTIFICATIONS,
    "LANGUAGES": LANGUAGES,
    "AWARDS": AWARDS,
    "AWARDS & HONORS": AWARDS,
}

_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
_MONTH_LOOKUP = {name.lower(): i + 1 for i, name in enumerate(_MONTHS)}
_MONTH_LOOKUP["sept"] = 9
_MONTH_PATTERN = r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?"

_BULLET = re.compile(r"^\s*[•●▪◦‣·*–—+]\s+")
_RULE = re.compile(r"^\s*[=_~*\-]{3,}\s*$")
_EMOJI = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F\u200B-\u200D\u2060]")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE = re.compile(r"\+?\d[\d\s().-]{7,}\d")
_TIME = re.compile(r"^\s*\d{1,2}:\d{2}\s*$")


def _clean_line(raw: str) -> str:
    line = unicodedata.normalize("NFKC", raw or "")
    for bad, good in (("\u2018", "'"), ("\u2019", "'"), ("\u201c", '"'), ("\u201d", '"'),
                      ("\u2013", "-"), ("\u2014", "-"), ("\u2011", "-"), ("\u2026", "...")):
        line = line.replace(bad, good)
    line = _EMOJI.sub("", line).replace("\t", " ").replace("\u00a0", " ")
    line = re.sub(r"\*{1,2}([^*]+)\*{1,2}", r"\1", line)  # **bold** / *italic* markers
    line = re.sub(r"`([^`]*)`", r"\1", line)
    line = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", " ", line)
    line = re.sub(r"[ \u00a0]{2,}", " ", line)
    line = line.strip()
    while line.startswith("#"):  # markdown headings
        line = line[1:].strip()
    if _RULE.match(line) or _TIME.match(line):
        return ""
    return line


def _canonical_heading(line: str) -> str | None:
    text = re.sub(r"\s+", " ", line.strip()).rstrip(":").strip()
    return HEADINGS.get(text.upper())


def _is_heading(line: str) -> bool:
    text = line.strip()
    return (len(text) > 2 and text[0].isalpha() and "[[" not in text
            and text.isupper() and len(text.split()) <= 6)


def _month_name(index: int, year: str) -> str:
    return f"{_MONTHS[index - 1]} {year}"


def _normalize_dates(line: str) -> str:
    line = re.sub(
        rf"\b{_MONTH_PATTERN}\s*(\d{{4}})",
        lambda m: _month_name(_MONTH_LOOKUP[m.group(1).lower()], m.group(2)),
        line, flags=re.IGNORECASE)
    line = re.sub(r"\b(\d{4})[-/.](\d{1,2})\b",
                  lambda m: _month_name(int(m.group(2)), m.group(1))
                  if 1 <= int(m.group(2)) <= 12 else m.group(0), line)
    line = re.sub(r"\b(\d{1,2})[-/.](\d{4})\b",
                  lambda m: _month_name(int(m.group(1)), m.group(2))
                  if 1 <= int(m.group(1)) <= 12 else m.group(0), line)
    if re.search(r"\b(?:19|20)\d{2}\b", line):
        line = re.sub(r"(?i)\b(present|now|current|till date|to date)\b", "Present", line)
        line = re.sub(r"(?i)\b(\d{4})\s*[-–]\s*(\d{4})\b", r"\1 - \2", line)
        # "Jan 2021-2023" and "2021-Present" read better with the dash spaced.
        line = re.sub(r"(?<=[0-9])\s*-\s*(?=(?:19|20)\d{2}\b|Present\b)", " - ", line)
    return line


def _normalize_bullet(line: str) -> str:
    if _BULLET.match(line):
        return "- " + _BULLET.sub("", line, count=1).strip()
    return line


def _normalize_pipes(line: str) -> str:
    """Roles written as 'Company | Title | Dates' and pasted tables read as columns.

    The contact line may legitimately separate links with pipes, so it is handled as
    header text and never reaches this function.
    """
    if "@" in line or "|" not in line:
        return line
    stripped = line.strip()
    if stripped.startswith("|") and stripped.endswith("|"):
        cells = [cell.strip() for cell in stripped.strip("|").split("|") if cell.strip()]
        return ", ".join(cells) or line
    return re.sub(r"\s*\|\s*", " - ", line)


def normalize_cv(text: str) -> str:
    """The same CV with ATS-proof layout: canonical headings, one bullet style,
    normalized dates, no decorative characters, sections in the standard order."""
    header: list[str] = []
    sections: dict[str, list[str]] = {}
    current: list[str] | None = None
    for raw in (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = _clean_line(raw)
        if not line:
            if current is not None:
                current.append("")
            continue
        canonical = _canonical_heading(line)
        if canonical is None and current is None:
            header.append(line)  # the name and contact lines before the first section
            continue
        if canonical is not None:
            current = sections.setdefault(canonical, [])
            continue
        line = _normalize_pipes(_normalize_bullet(_normalize_dates(line)))
        current.append(line)

    ordered = _trim_blank(header)
    for name in SECTION_ORDER:
        body = _trim_blank(sections.get(name, []))
        if name not in (EXPERIENCE, PROJECTS):
            body = [line for line in body if line.strip()]  # blank lines inside a list are noise
        if not body:
            continue
        if ordered:
            ordered.append("")
        ordered.append(name)
        ordered.extend(body)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(ordered)).strip()


def _trim_blank(lines: list[str]) -> list[str]:
    body = list(lines)
    while body and not body[0].strip():
        body.pop(0)
    while body and not body[-1].strip():
        body.pop()
    return body


def _find_phone(text: str) -> bool:
    for match in _PHONE.finditer(text or ""):
        if len(re.sub(r"\D", "", match.group())) >= 9:
            return True
    return False


def _keywords_in(text: str, keywords: list[str]) -> tuple[list[str], list[str]]:
    haystack = text.lower()
    found, missing = [], []
    for word in keywords:
        (found if word.lower() in haystack else missing).append(word)
    return found, missing


def headings_in(text: str) -> set[str]:
    """The canonical sections a text contains, e.g. {"SKILLS", "EDUCATION"}."""
    found = {_canonical_heading(line) for line in (text or "").splitlines()}
    found.discard(None)
    return found


def ats_check(text: str, required_keywords: list[str] | None = None) -> dict:
    """Score the send copy the way an ATS reads it, and name what still costs points."""
    body = text or ""
    keywords = [k for k in (required_keywords or []) if k]
    headings = headings_in(body)
    email = bool(_EMAIL.search(body))
    phone = _find_phone(body)
    standard = not _has_stray_heading(body)
    graphics = not _has_graphics(body)
    bullets_ok = not _has_bad_bullets(body)
    found, missing = _keywords_in(body, keywords)
    coverage = (len(found) / len(keywords)) if keywords else 1.0

    score = 0
    score += 10 if email else 0
    score += 5 if phone else 0
    score += 10 if SUMMARY in headings else 0
    score += 15 if SKILLS in headings else 0
    score += 15 if EXPERIENCE in headings else 0
    score += 5 if EDUCATION in headings else 0
    score += 10 if standard else 0
    score += 10 if graphics else 0
    score += 5 if bullets_ok else 0
    score += round(15 * coverage)
    score = max(0, min(100, score))

    issues = []
    if not email:
        issues.append("No email address found in the contact line.")
    if not phone:
        issues.append("No phone number found in the contact line.")
    for section in (SUMMARY, SKILLS, EXPERIENCE, EDUCATION):
        if section not in headings:
            issues.append(f"The {section} section is missing.")
    if not standard:
        issues.append("A section label is not one an ATS recognises.")
    if not graphics:
        issues.append("Tables, pipes, emoji or decorative rules are still in the text.")
    if not bullets_ok:
        issues.append("Bullet lines do not all start with '- '.")
    if missing:
        issues.append("The ad names these and the CV does not: " + ", ".join(missing[:8]) + ".")
    return dict(score=score, issues=issues, keywords_found=found,
                keywords_missing=missing, headings=sorted(headings))


def _has_stray_heading(text: str) -> bool:
    """A colon-terminated all-caps label the parser would read as an unknown section."""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.endswith(":") and _is_heading(stripped):
            return True
    return False


def _has_graphics(text: str) -> bool:
    for line in text.splitlines():
        stripped = line.strip()
        if _RULE.match(stripped) or _EMOJI.search(line):
            return True
        if stripped.count("|") >= 2 and "@" not in stripped:
            return True
    return False


def _has_bad_bullets(text: str) -> bool:
    for line in text.splitlines():
        if _BULLET.match(line) and not line.lstrip().startswith("- "):
            return True
    return False


def format_report(report: dict) -> list[str]:
    """The short block shown in the review copy — never in the employer's PDF."""
    score = report["score"]
    headline = ("Ready to send: standard headings, plain single-column text, "
                "no tables or graphics, keywords from the ad present."
                if score >= 90 else
                "Close to ATS-ready; the points below are what still costs you.")
    lines = [f"ATS READINESS CHECK - {score}/100", headline]
    if report["keywords_found"]:
        lines.append("Keywords from the ad found in the CV: "
                     + ", ".join(report["keywords_found"][:12]) + ".")
    for issue in report["issues"]:
        lines.append("- " + issue)
    if not report["issues"]:
        lines.append("- Nothing to fix.")
    return lines
