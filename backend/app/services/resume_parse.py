"""Read profile facts out of an already-extracted resume text.

Only text that is literally in the file is copied: no company is guessed, no
date is invented and no title is rewritten. The API returns these suggestions
for the user to review, and nothing is written until they apply them.
"""

from __future__ import annotations

import re

MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10,
    "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}
_MONTH = r"(?:" + "|".join(sorted(MONTHS, key=len, reverse=True)) + r")"
_YEAR = r"(?:19|20)\d{2}"
_RANGE = re.compile(
    rf"(?:(?P<m1>{_MONTH})[a-z]*\.?\s*)?(?P<y1>{_YEAR})\s*"
    r"(?:[–—]|-(?=\s)|\s-\s|\bto\b)\s*"
    rf"(?:(?P<m2>{_MONTH})[a-z]*\.?\s*)?(?P<y2>{_YEAR}|present|current|now)",
    re.IGNORECASE,
)
_SINGLE = re.compile(rf"(?:(?P<m>{_MONTH})[a-z]*\.?\s*)?(?P<y>{_YEAR})", re.IGNORECASE)
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_URL = re.compile(r"(?:https?://|www\.)[^\s|,;)\]]+|(?:linkedin|github)\.com/[^\s|,;)\]]+", re.IGNORECASE)
_PHONE = re.compile(r"(?<![\w])(?:\+|00)?\d(?:[\s().-]?\d){7,14}(?![\w])")
_NAME = re.compile(r"^[A-Za-z][A-Za-z.'-]*(?:\s+[A-Za-z][A-Za-z.'-]*){1,4}$")
_LOCATION = re.compile(r"^([A-Za-z][A-Za-z .'-]*?)\.?,\s*([A-Za-z][A-Za-z .'-]+?)\.?$")

_SECTIONS = [
    ("summary", re.compile(r"^(?:professional\s+)?(?:summary|profile|objective|about(?:\s+me)?)$", re.IGNORECASE)),
    ("experience", re.compile(r"^(?:(?:work|professional|employment)\s+)?(?:experience|history)$", re.IGNORECASE)),
    ("education", re.compile(r"^(?:education|academic\s+background|qualifications)$", re.IGNORECASE)),
    ("skills", re.compile(r"^.{0,40}\bskills?\b.{0,20}$", re.IGNORECASE)),
    ("languages", re.compile(r"^languages?$", re.IGNORECASE)),
    ("courses", re.compile(r"^(?:courses?|certifications?|courses?\s*(?:&|and)\s*certifications?)$", re.IGNORECASE)),
    ("projects", re.compile(r"^projects?$", re.IGNORECASE)),
]
_BULLET = re.compile(r"^[\-•*·\u2022]\s*")
_DASH_SPLIT = re.compile(r"\s+[–—]\s+|\s+-\s+|\s+at\s+", re.IGNORECASE)


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\u00a0", " ").replace("\u200b", "")).strip()


def _section_key(line: str) -> str | None:
    if len(line) > 60 or line.endswith((".", ";")) or _BULLET.match(line):
        return None
    for key, pattern in _SECTIONS:
        if pattern.match(line):
            return key
    return None


def _month_start(month: str | None) -> str:
    if not month:
        return "01"
    return f"{MONTHS.get(month.lower(), 1):02d}"


def _date_value(month: str | None, year: str) -> str:
    return f"{year}-{_month_start(month)}"


def _parse_ranges(line: str) -> tuple[str | None, str | None, bool]:
    match = _RANGE.search(line)
    if match:
        start = _date_value(match.group("m1"), match.group("y1"))
        end_raw = match.group("y2")
        if end_raw.lower() in ("present", "current", "now"):
            return start, None, True
        return start, _date_value(match.group("m2"), end_raw), False
    single = _SINGLE.search(line)
    if single:
        return None, _date_value(single.group("m"), single.group("y")), False
    return None, None, False


def _header_lines(text: str) -> list[str]:
    out: list[str] = []
    for raw in text.splitlines():
        line = _clean(raw)
        if not line:
            continue
        if _section_key(line):
            break
        out.append(line)
        if len(out) >= 10:
            break
    return out


def _contact(lines: list[str]) -> dict[str, str]:
    joined = "\n".join(lines)
    found: dict[str, str] = {}

    email = _EMAIL.search(joined)
    if email:
        found["email"] = email.group(0)

    phones = []
    for match in _PHONE.finditer(joined):
        raw = match.group(0)
        plus = raw.strip().startswith(("+", "00"))
        digits = re.sub(r"\D", "", raw)
        if digits.startswith("00"):
            digits = digits[2:]
        if not 8 <= len(digits) <= 15:
            continue
        phones.append(("+" if plus else "") + digits)
    preferred = next((p for p in phones if p.startswith("+20") or p.startswith("01")), phones[0] if phones else None)
    if preferred:
        found["phone"] = preferred

    links = [u.rstrip(".,;") for u in _URL.findall(joined)]
    for url in links:
        low = url.lower()
        if "linkedin.com/" in low and "linkedin" not in found:
            found["linkedin"] = url
        elif "github.com/" in low and "github" not in found:
            found["github"] = url
        elif "portfolio" not in found:
            found["portfolio"] = url

    for line in lines:
        if len(line) > 60 or line.count(",") != 1 or "|" in line or "@" in line:
            continue
        loc = _LOCATION.match(line)
        if loc:
            city = loc.group(1).strip(" .")
            country = loc.group(2).strip(" .")
            if city and country and not any(ch.isdigit() for ch in city + country):
                found.setdefault("city", city)
                found.setdefault("country", country)
            break

    for line in lines:
        if _NAME.match(line) and "," not in line and "|" not in line:
            found["full_name"] = line
            break
    return found


def _skill_items(lines: list[str]) -> list[str]:
    items: list[str] = []
    seen: set[str] = set()
    for line in lines:
        line = _BULLET.sub("", line).strip()
        if not line:
            continue
        inner = re.findall(r"\(([^)]*)\)", line)
        base = re.sub(r"\([^)]*\)", "", line)
        parts = re.split(r"[,;|•·]", base)
        for group in inner:
            parts.extend(re.split(r"[,;|]", group))
        for part in parts:
            term = part.strip(" .;:-–—•*·\"'")
            if not (2 <= len(term) <= 60) or not re.search(r"[A-Za-z]", term):
                continue
            key = term.casefold()
            if key in seen:
                continue
            seen.add(key)
            items.append(term)
    return items[:50]


def _split_title_company(value: str) -> tuple[str, str]:
    pieces = _DASH_SPLIT.split(value, maxsplit=1)
    title = pieces[0].strip(" .;:-–—")
    company = pieces[1].strip(" .;:-–—") if len(pieces) > 1 else ""
    return title, company


def _experiences(lines: list[str]) -> list[dict]:
    entries: list[dict] = []
    current: dict | None = None
    for line in lines:
        is_bullet = bool(_BULLET.match(line))
        has_year = bool(re.search(rf"\b{_YEAR}\b", line))
        # A year alone is not enough: descriptions often mention one. A job line
        # also carries a pipe, a spaced dash, "at", or a month name.
        has_shape = ("|" in line or bool(_DASH_SPLIT.search(line))
                     or bool(re.search(rf"\b{_MONTH}\b", line, re.IGNORECASE)))
        looks_like_header = (not is_bullet) and has_year and has_shape and len(line) <= 120 \
            and not line.endswith(".")
        if looks_like_header:
            start, end, ongoing = _parse_ranges(line)
            if start is None and end is None:
                looks_like_header = False
            elif start is None:
                # One date on a job line is its start ("August 2025"), not an end.
                start, end = end, None
        if looks_like_header:
            without_dates = _RANGE.sub("", line)
            without_dates = _SINGLE.sub("", without_dates)
            left = without_dates.split("|")[0].strip(" |–—-")
            title, company = _split_title_company(left)
            if not title:
                continue
            current = {
                "title": title[:200],
                "company": company[:200],
                "location": "",
                "start_date": start,
                "end_date": end,
                "current": ongoing,
                "description": "",
            }
            entries.append(current)
            continue
        if current is not None:
            text = _BULLET.sub("", line).strip()
            if text:
                current["description"] = (current["description"] + "\n" + text).strip()[:5000]
    return entries[:20]


def _education(lines: list[str]) -> list[dict]:
    entries: list[dict] = []
    for line in lines:
        years = re.findall(rf"\b{_YEAR}\b", line)
        if not years or _BULLET.match(line):
            continue
        start = end = None
        range_match = _RANGE.search(line)
        if range_match:
            start = range_match.group("y1")
            end_raw = range_match.group("y2")
            end = None if end_raw.lower() in ("present", "current", "now") else end_raw
            if start == end:
                start = None
        else:
            start = None
            end = years[-1]
        main = line.split("|")[0].strip()
        # A comma-separated year at the end ("BSc CS, Cairo University, 2019") is
        # a date, not the institution; drop it before splitting the parts.
        main_parts = [p.strip(" .,;:-") for p in main.split(",")]
        main_parts = [p for p in main_parts if p and not re.fullmatch(
            rf"{_YEAR}(?:\s*[–—-]\s*{_YEAR})?", p)]
        main = ", ".join(main_parts)
        desc_parts = [
            part.strip()
            for part in line.split("|")[1:]
            if part.strip() and not re.fullmatch(rf"{_YEAR}(?:\s*[–—-]\s*{_YEAR})?", part.strip())
        ]
        degree, institution, field = "", "", ""
        halves = _DASH_SPLIT.split(main, maxsplit=1)
        if len(halves) == 2:
            degree = halves[0].strip(" .,;:-")
            rest = [p.strip(" .,;:-") for p in halves[1].split(",") if p.strip(" .,;:-")]
            if rest:
                field = rest[0]
                institution = ", ".join(rest[1:])
        else:
            parts = [p.strip(" .,;:-") for p in main.split(",") if p.strip(" .,;:-")]
            if parts:
                degree = parts[0]
            if len(parts) >= 3:
                field, institution = parts[1], ", ".join(parts[2:])
            elif len(parts) == 2:
                institution = parts[1]
        if not degree:
            continue
        entries.append({
            "degree": degree[:200],
            "institution": institution[:200],
            "field": field[:200],
            "start_date": start,
            "end_date": end,
            "description": " · ".join(desc_parts)[:2000],
        })
    return entries[:10]


def parse_resume(text: str) -> dict:
    """Return suggestions extracted from the resume text (may be empty)."""
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    header = _header_lines(text)
    fields = _contact(header)

    buckets: dict[str, list[str]] = {}
    current = "header"
    for raw in text.splitlines():
        line = _clean(raw)
        if not line:
            continue
        key = _section_key(line)
        if key:
            current = key
            continue
        if current != "header":
            buckets.setdefault(current, []).append(line)

    summary = " ".join(buckets.get("summary", []))[:20000]
    if summary:
        fields["summary"] = summary

    return {
        "fields": fields,
        "skills": _skill_items(buckets.get("skills", [])),
        "experiences": _experiences(buckets.get("experience", [])),
        "education": _education(buckets.get("education", [])),
        "resume_chars": len(text.strip()),
    }
