"""What the ad itself says about how to apply.

Boards differ: some put a recruiter mailbox in the text, some a company careers page,
most only give their own listing URL. Reading the description means a real apply route
is offered instead of guessing, and guessing wrong would send his CV to a privacy
mailbox or a "no-reply" address.
"""
from __future__ import annotations

import html
import re
from urllib.parse import parse_qs, unquote, urlsplit

from ..models import Job

# An email is only an apply route when the words around it ask for a CV or an application.
_APPLY_WORDS = re.compile(
    r"\b(apply|application|candidate|cv|resume|résumé|recruit|hir(e|ing)|career|send|submit|"
    r"forward|please\s+email)\b", re.I)
# A mailbox named for hiring needs no surrounding sentence to prove what it is for.
_HIRING_MAILBOX = re.compile(r"(apply|application|applicant|careers?|hir(e|ing)|talent|recruit|jobs?)", re.I)
# These mailboxes exist in ad text but never take an application.
_NON_APPLY_MAILBOX = re.compile(
    r"^(privacy|legal|abuse|security|saf(e|ety)|nocop|no-?reply|donotreply|do-?not-?reply|"
    r"support|help|info|sales|press|media|billing|account|compliance|dpo|gdpr)", re.I)
# A link is an apply route when its host or path says so.
_APPLY_LINK_HINT = re.compile(
    r"(apply|application|career|jobs?$|/jobs/|recruit|hiring|candidate|opening|vacancy|"
    r"greenhouse|workable|lever\.co|ashbyhq|smartrecruiters|bamboohr|myworkdayjobs|taleo|"
    r"jazzhr|teamtailor|recruitee|zoho.?recruit|formassembly|jotform|typeform)", re.I)
# Pages an ad may link to that are never where you apply.
_NON_APPLY_PAGE = re.compile(
    r"(privacy|legal|terms|cookie|security|abuse|press|newsroom|/news/|news-release|newswire|"
    r"businesswire|/blog/|culture|/about|investor|status|support|contact|our-work|"
    r"linkedin\.com/(in|company)/|/feed/|googlegroups|googleusercontent|/secure-media|"
    r"google\.com/search)", re.I)
# Gmail and LinkedIn wrap the real address in a redirect of their own.
_REDIRECT = re.compile(
    r"(google\.com/url|linkedin\.com/safety/go|l\.linkedin\.com/(redirect|in\.html))", re.I)
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_URL = re.compile(r"https?://[^\s<>'\"\)\]}]+")
_WINDOW = 120
# [text](url) — the visible text is not the address, only the part in brackets is.
_MARKDOWN_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
# An index (Google for Jobs via JSearch) carries ads from several boards; the provider
# stamps each one with the board that published it.
_VIA_PREFIX = re.compile(r"^\s*\[via ([^\]\n]{1,60})\]", re.I)
_BOARD_BY_HOST = (
    ("wuzzuf.net", "Wuzzuf"),
    ("linkedin.com", "LinkedIn"),
    ("bayt.com", "Bayt"),
    ("bebee.com", "BeBee"),
    ("gulftalent.com", "GulfTalent"),
    ("dubizzle.com.eg", "Dubizzle"),
    ("talent.com", "Talent.com"),
    ("trabajo.org", "Trabajo.org"),
    ("founditgulf.com", "Foundit Gulf"),
)


def board_of(job: Job) -> str:
    """The board whose page this ad actually lives on, or "" when the source is the board.

    "Google for Jobs" is an index, not a board: one import mixes Wuzzuf, LinkedIn and Bayt
    ads, so a button reading "Apply on Google Jobs" hid where the click would really go.
    """
    match = _VIA_PREFIX.match(job.description or "")
    if match:
        return match.group(1).strip()
    try:
        host = (urlsplit(job.url or "").hostname or "").lower()
    except ValueError:
        return ""
    for suffix, name in _BOARD_BY_HOST:
        if host == suffix or host.endswith("." + suffix):
            return name
    return ""


def _readable(text: str) -> str:
    """Markdown links replaced by their real target, HTML entities decoded.

    Without this an ad's link text ("https://…/company/13144301/") was harvested as if it
    were the destination, which pointed him at a profile page instead of the application.
    """
    return html.unescape(_MARKDOWN_LINK.sub(r" \1 ", text))


def _unwrap(url: str) -> str:
    """The address behind a redirect wrapper, or the URL itself when there is none."""
    if not _REDIRECT.search(url):
        return url
    try:
        query = parse_qs(urlsplit(url).query)
    except ValueError:
        # An ad can paste a half-broken wrapper ("https://[google.com/url?q=..."). It is
        # nothing worth following, and it must not take down every page that lists the job.
        return url
    for key in ("url", "q"):
        for value in query.get(key, []):
            target = unquote(value)
            if target.startswith(("http://", "https://")):
                return target
    return url


def _trim(url: str) -> str:
    return url.rstrip(".,;:!?'\"")


def _well_formed(url: str) -> bool:
    """Only an address his browser can actually open is offered as a route.

    Ads paste fragments as well as links, and sending him to "https://[google.com/url?..."
    wastes the one click that matters.
    """
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    return bool(parts.netloc) and "[" not in parts.netloc and "]" not in parts.netloc


def _same_site(a: str, b: str) -> bool:
    """Two URLs on the same registered site, so a board's own link never counts as the
    company's application page."""
    def host(url: str) -> str:
        return re.sub(r"^www\.", "", (re.sub(r"^https?://", "", url or "").split("/")[0])).lower()

    ha, hb = host(a), host(b)
    if not ha or not hb:
        return False
    return ha == hb or ha.endswith("." + hb) or hb.endswith("." + ha)


def _apply_emails(text: str) -> list[str]:
    """Mailboxes the ad asks for a CV at — matched on the sentence around them."""
    found: list[str] = []
    for match in _EMAIL.finditer(text):
        email = match.group(0)
        local = email.split("@")[0]
        if _NON_APPLY_MAILBOX.match(local):
            continue
        window = text[max(0, match.start() - _WINDOW): match.end() + _WINDOW]
        wanted = _HIRING_MAILBOX.search(local) or _APPLY_WORDS.search(window)
        if wanted and email.lower() not in [f.lower() for f in found]:
            found.append(email)
    return found[:3]


def _apply_links(text: str, listing_url: str) -> list[str]:
    """Company links the ad points at *for applying* — judged by the words around them.

    A bare host hint was not enough: ads also link their privacy notice, their blog and
    their culture page, and sending him there would waste the one click that matters.
    """
    found: list[str] = []
    for match in _URL.finditer(text):
        url = _unwrap(_trim(match.group(0)))
        if not _well_formed(url):
            continue
        path = re.sub(r"^https?://", "", url).lower()
        if _same_site(url, listing_url) or _NON_APPLY_PAGE.search(path):
            continue
        window = text[max(0, match.start() - _WINDOW): match.end() + _WINDOW]
        if not _APPLY_WORDS.search(window) and not _APPLY_LINK_HINT.search(path):
            continue
        if url.lower() not in [f.lower() for f in found]:
            found.append(url)
    return found[:3]


def apply_method(job: Job) -> dict:
    """How this specific ad wants to be applied to, in the fields the API already serves."""
    text = _readable((job.description or "")[:8000])
    emails = _apply_emails(text)
    links = _apply_links(text, job.url or "")
    if emails:
        return dict(apply_emails=emails, apply_links=links, apply_channel="email",
                    apply_note=f"The ad asks for the CV at {emails[0]}")
    if links:
        return dict(apply_emails=[], apply_links=links, apply_channel="company-link",
                    apply_note="The ad links to the company's own application page")
    if job.url:
        board = board_of(job)
        return dict(apply_emails=[], apply_links=[], apply_channel="listing",
                    apply_note=f"Apply on {board} — the ad gives no other address" if board
                    else "Apply on the board page — the ad gives no other address")
    return dict(apply_emails=[], apply_links=[], apply_channel="unknown",
                apply_note="No way to apply is stated in this ad")
