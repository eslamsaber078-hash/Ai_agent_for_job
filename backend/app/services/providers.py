"""Job discovery providers.

Modular architecture: each provider implements fetch() and returns normalized
ProviderJob records. Ingest logic deduplicates and stores them in the database.

Freshness rule: a posting is only useful while it is still advertised. Discovery
therefore skips postings older than the user's age cutoff and postings whose feed
carries an expiry timestamp in the past, and it flags stored jobs that have aged
out so they leave the default lists.
"""
from __future__ import annotations

import contextvars
import logging
import re
import time
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from typing import Iterable, Iterator

import httpx
from sqlalchemy import and_, or_

from .. import config
from ..models import (
    DEFAULT_JOB_MAX_AGE_DAYS,
    Job,
    JobSource,
    SearchPreference,
    Skill,
    UserProfile,
)
from .keywords import build_gate, expand_terms, role_phrases
from .terms import clean_term, reconcile_terms

log = logging.getLogger("jobhunter.providers")

REMOTIVE_API = "https://remotive.com/api/remote-jobs"
REMOTEOK_API = "https://remoteok.com/api"
JOBICY_API = "https://jobicy.com/api/v2/remote-jobs"
ARBEITNOW_API = "https://www.arbeitnow.com/api/job-board-api"
WWR_RSS = "https://weworkremotely.com/remote-jobs.rss"
HIMALAYAS_API = "https://himalayas.app/jobs/api"
WORKING_NOMADS_API = "https://www.workingnomads.com/api/exposed_jobs/"
LINKEDIN_GUEST_API = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
JSEARCH_API = "https://jsearch.p.rapidapi.com/search-v2"
JSEARCH_HOST = "jsearch.p.rapidapi.com"
AMAZON_SEARCH_API = "https://www.amazon.jobs/en/search.json"
WORKDAY_BASE = "https://{tenant}.{wd}.myworkdayjobs.com"
SMARTRECRUITERS_API = "https://api.smartrecruiters.com/v1/companies/{company}/postings"
JOOBLE_API = "https://jooble.org/api/"
EMPLOYER_BOARD_APIS = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{company}/jobs",
    "ashby": "https://api.ashbyhq.com/posting-api/job-board/{company}",
}
GREENHOUSE_DETAIL_API = "https://boards-api.greenhouse.io/v1/boards/{company}/jobs/{posting_id}"
JOBGETHER_API = "https://jobgether.com/api/v1/jobs"
ADZUNA_API = "https://api.adzuna.com/v1/api/jobs/{country}/search/1"

# Free public APIs must not be hammered: one GET per provider per TTL window,
# no matter how often the user presses Refresh. Each provider states its own window;
# `fast` below is what a board that has no quota can answer every few minutes.
FETCH_CACHE_TTL_SECONDS = 600
FAST_FEED_TTL_SECONDS = 180
QUOTA_CAPPED_TTL_SECONDS = 900

# How many sites are asked at once, and how many of one site's own job pages are read
# at once. The sites are unrelated servers, so asking them together is pure gain; the
# numbers stay modest because each answer is a real request to a real board.
SITES_IN_FLIGHT = 6
PAGES_PER_SITE = 8

# A ContextVar, not a module global: the sites are fetched on several threads at once
# and each one's window is its own business.
_fetch_policy: contextvars.ContextVar[tuple[int, bool]] = contextvars.ContextVar(
    "fetch_policy", default=(FETCH_CACHE_TTL_SECONDS, False))

# The pages a site failed to answer during this fetch. A ContextVar for the same
# reason as the policy above: one site's outage must never be reported against
# another site's line in the run log.
_fetch_errors: contextvars.ContextVar[tuple[str, ...]] = contextvars.ContextVar(
    "fetch_errors", default=())


def _record_fetch_error(site: str, exc: Exception) -> None:
    """Remember that this fetch could not read a page, so the run log can say so."""
    _fetch_errors.set((*_fetch_errors.get(), f"{site} ({type(exc).__name__})"))


def set_fetch_policy(ttl: int, fresh: bool) -> None:
    """Declare how long this provider's answers stay fresh, and whether to re-read now.

    A manual import is the owner asking for news *right now*, so it breaks the cache
    window for every site that can take the extra request. A site that must not be
    re-read early — a monthly quota, or a host that blocks returning visitors — keeps
    its window no matter who asked; burning the month's allowance on one click would
    only make the next three weeks blind.
    """
    _fetch_policy.set((ttl, fresh))


_fetch_cache: dict[str, tuple[float, object]] = {}


def clear_fetch_cache() -> None:
    _fetch_cache.clear()
    set_fetch_policy(FETCH_CACHE_TTL_SECONDS, False)


# Each keyword site is asked about this many phrases per import, one request
# each. Free APIs and the RapidAPI monthly allowance both set the ceiling.
MAX_SEARCH_TERMS = 5
FALLBACK_TERM = "software developer"

# RapidAPI's free plan allows 250 requests a month, so the JSearch provider
# spends one request per import and rotates through his phrases instead of
# concatenating them — a day of scheduled runs still covers every term.
_jsearch_turn = 0

# Jooble's free key is capped the same way: one phrase per import, rotating.
_jooble_turn = 0


def search_terms(titles: list[str], skills: list[str] | None = None,
                 limit: int = MAX_SEARCH_TERMS) -> list[str]:
    """The distinct phrases a keyword site gets asked about, most specific first.

    Concatenating titles into one string makes "Flutter Developer Mobile Developer"
    behave like an AND search, which drops jobs titled just "Flutter Engineer".
    Asking each phrase on its own is what lifts recall.

    Long saved skills are cut into the short phrases a board actually answers:
    "Customer Support & Complaint Handling" is asked as two searches, not one
    nine-word phrase nobody posts a job under.
    """
    out = expand_terms(titles, skills or [])
    return out[:limit] or [FALLBACK_TERM]


def _clean_terms(values) -> list[str]:
    return [cleaned for cleaned in (clean_term(value) for value in (values or [])) if cleaned]


_SEARCH_FILLER = {"job", "jobs", "work", "remote", "any", "anything", "position", "role",
                  "anywhere", "worldwide", "all", "the", "and", "of", "for", "open",
                  "search", "looking", "employment", "senior", "junior", "entry", "level",
                  "full", "part", "time", "onsite", "hybrid"}


def _meaningful_terms(values) -> list[str]:
    return [term for term in _clean_terms(values)
            if any(word not in _SEARCH_FILLER and any(c.isalpha() for c in word)
                   for word in re.findall(r"\w+", term.casefold()))
            and (len(re.sub(r"\W", "", term)) >= 2
                 or term.casefold() in {"c", "r", "c#", "c++"})]


EMPTY_SEARCH_ERROR = (
    "Add desired job titles or skills to your profile before importing jobs. "
    "If you uploaded a CV, add explicit titles or skills when its profession "
    "cannot be identified from the text."
)


def effective_terms(db, pref, profile_id: int = 1) -> tuple[list[str], list[str], list[str]]:
    """Resolve search settings using only the selected owner's profile."""
    if pref is None:
        pref = db.get(SearchPreference, profile_id)
    elif getattr(pref, "id", profile_id) != profile_id:
        raise ValueError("Search preferences belong to a different profile.")
    profile = db.get(UserProfile, profile_id)

    def saved(field):
        return _clean_terms(getattr(pref, field, None) if pref else None)

    titles = saved("titles")
    if not titles and profile:
        titles = _clean_terms(profile.desired_titles)
    titles += saved("extra_terms")

    skills = saved("skills")
    if not skills and profile:
        skills = _clean_terms([s.name for s in db.query(Skill).filter(Skill.profile_id == profile_id).all()])
    if not _meaningful_terms(titles + skills) and profile and profile.resume_text:
        from .matching import detect_skills

        skills = [s for s in detect_skills(profile.resume_text)
                  if s.casefold() not in {"english", "problem solving"}]
        if not re.search(r"\brest\s+apis?\b", profile.resume_text, re.I):
            skills = [s for s in skills if s != "REST APIs"]

    locations = saved("locations")
    if not locations and profile:
        preferred = _clean_terms(profile.preferred_locations)
        country = (profile.country or "").strip()
        if country and country.casefold() not in {l.casefold() for l in preferred}:
            locations = [country, *preferred]
        else:
            locations = preferred

    return titles, skills, locations


def profile_roles(db, profile_id: int) -> list[str]:
    """Titles of the jobs the owner actually held, newest first when possible."""
    from ..models import WorkExperience

    rows = (
        db.query(WorkExperience)
        .filter(WorkExperience.profile_id == profile_id)
        .order_by(WorkExperience.id)
        .all()
    )
    return [row.title.strip() for row in rows if (row.title or "").strip()]


def role_search_titles(roles: list[str]) -> list[str]:
    """The short role phrases a board answers when no desired title is set."""
    out: list[str] = []
    seen: list[set[str]] = []
    for title in roles:
        for phrase in role_phrases(title):
            words = set(re.findall(r"[a-z0-9+#.]+", phrase.casefold()))
            if not words or any(words <= known for known in seen):
                continue  # "Sales" adds nothing once "Retail Sales" is asked
            seen.append(words)
            out.append(phrase)
    return out


def _cache_hit(key: str, now: float):
    """The stored answer for this key while its window holds; None when it must be re-read."""
    hit = _fetch_cache.get(key)
    ttl, ignore = _fetch_policy.get()
    if hit and (not ignore and now - hit[0] < ttl):
        return hit[1]
    return None


def _cached_fetch(key: str, url: str, *, params: dict | None = None,
                  timeout: float = 25.0, as_json: bool = True, headers: dict | None = None):
    """GET a public feed with a per-provider TTL cache; failures return None, never raise."""
    now = time.monotonic()
    cached = _cache_hit(key, now)
    if cached is not None:
        return cached
    try:
        resp = httpx.get(url, params=params, timeout=timeout,
                         headers={"User-Agent": "jobhunter/1.0 (personal job search assistant)", **(headers or {})})
        resp.raise_for_status()
        data = resp.json() if as_json else resp.text
    except Exception as exc:  # noqa: BLE001 - providers must never crash the pipeline
        log.warning("%s fetch failed: %s", key, exc)
        _record_fetch_error(key, exc)
        return None
    _fetch_cache[key] = (now, data)
    return data


def _cached_get_json(key: str, url: str, *, params: dict | None = None, timeout: float = 25.0,
                     headers: dict | None = None):
    return _cached_fetch(key, url, params=params, timeout=timeout, as_json=True, headers=headers)


def _cached_get_text(key: str, url: str, *, params: dict | None = None, timeout: float = 25.0):
    return _cached_fetch(key, url, params=params, timeout=timeout, as_json=False)


def _cached_post_json(key: str, url: str, payload: dict, *, timeout: float = 25.0,
                      headers: dict | None = None):
    """POST variant for APIs that search by body (Workday, Jooble), same TTL cache."""
    now = time.monotonic()
    cached = _cache_hit(key, now)
    if cached is not None:
        return cached
    try:
        resp = httpx.post(url, json=payload, timeout=timeout,
                          headers={"User-Agent": "jobhunter/1.0 (personal job search assistant)",
                                   **(headers or {})})
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:  # noqa: BLE001 - providers must never crash the pipeline
        log.warning("%s fetch failed: %s", key, exc)
        _record_fetch_error(key, exc)
        return None
    _fetch_cache[key] = (now, data)
    return data


@dataclass
class ProviderJob:
    source: str
    external_id: str
    title: str
    company: str = ""
    location: str = ""
    country: str = ""
    remote: bool = False
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str | None = None
    employment_type: str = ""
    experience_level: str = ""
    description: str = ""
    url: str = ""
    skills: list[str] = field(default_factory=list)
    posted_date: datetime | None = None
    expiry_date: datetime | None = None


class BaseProvider(ABC):
    name = "base"
    label = "Base provider"
    requires_key = False
    # True when the site offers a keyword search we can aim with his terms;
    # False means the feed hands us everything and filtering is ours to do.
    keyword_search = False
    # How long this site's answer stays fresh between reads.
    fetch_ttl = FETCH_CACHE_TTL_SECONDS
    # True for the sites that must not be re-read early: a monthly request
    # allowance (JSearch, Jooble), or a site that blocks returning visitors
    # (LinkedIn's guest listing). Even a manual import keeps their window.
    keep_cache_window = False

    def __init__(self, config: dict | None = None):
        self.config = config or {}

    @abstractmethod
    def fetch(self, titles: list[str], skills: list[str], locations: list[str],
              remote_only: bool) -> list[ProviderJob]:
        ...


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


# Boards such as Arbeitnow re-advertise the same opening under a fresh posting id
# every few days ("flutter-developer-berlin-262635" then "-146596").
_TRAILING_POST_ID = re.compile(r"-\d{4,}$")


def _strip_posting_id(url: str) -> str:
    """Drop only a readable slug's numeric posting id.

    Bare numeric paths ("/job/1234") and slugs containing digits stay untouched,
    since there the number is the posting's real address, not a re-issue counter.
    """
    if not url:
        return ""
    head, sep, tail = url.rstrip("/").rpartition("/")
    stem = _TRAILING_POST_ID.sub("", tail)
    if stem == tail:
        return url
    words = [w for w in stem.split("-") if w]
    if len(words) < 3 or not all(w.isalpha() for w in words):
        return url
    return head + sep + stem


def identity_key(company: str, title: str, url: str, external_id: str) -> tuple:
    """Source-independent identity: the same posting on two boards shares this key."""
    return (_normalize(company), _normalize(title), _normalize(_strip_posting_id(url)) or external_id)


class RemotiveProvider(BaseProvider):
    """Real jobs from the public Remotive API (no key required).

    Fails gracefully: network or API errors are logged and skipped,
    never raising to the caller.
    """

    name = "remotive"
    label = "Remotive (real remote jobs, free API)"
    fetch_ttl = FAST_FEED_TTL_SECONDS
    keyword_search = True
    MAX_JOBS = 100

    def fetch(self, titles, skills, locations, remote_only):
        jobs: list[ProviderJob] = []
        seen: set[str] = set()
        for search in search_terms(titles, skills):
            data = _cached_get_json(f"remotive:{search}", REMOTIVE_API,
                                    params={"search": search, "limit": 50})
            if not isinstance(data, dict):
                continue
            for item in data.get("jobs", [])[:50]:
                external_id = str(item.get("id") or _normalize(f"{item.get('title')}{item.get('company_name')}"))
                if external_id in seen:
                    continue
                seen.add(external_id)
                jobs.append(ProviderJob(
                    source="remotive",
                    external_id=external_id,
                    title=item.get("title", "")[:300],
                    company=item.get("company_name", ""),
                    location=item.get("candidate_required_location", "Remote"),
                    country="Remote",
                    remote=True,
                    salary_min=None,
                    salary_max=None,
                    salary_currency=None,
                    employment_type=item.get("job_type", "") or "",
                    experience_level="",
                    description=(item.get("description") or "")[:4000],
                    url=item.get("url", ""),
                    skills=[],
                    posted_date=_parse_date(item.get("publication_date")),
                ))
                if len(jobs) >= self.MAX_JOBS:
                    return jobs
        return jobs


class RemoteOKProvider(BaseProvider):
    """Real remote jobs from the public RemoteOK API (no key required).

    The feed is one JSON array whose first element is a legal notice. Returns
    the newest N jobs only, so a refresh never floods the local database.
    """

    name = "remoteok"
    label = "Remote OK (real remote jobs, free API)"
    fetch_ttl = FAST_FEED_TTL_SECONDS
    MAX_JOBS = 200

    def fetch(self, titles, skills, locations, remote_only):
        data = _cached_get_json("remoteok", REMOTEOK_API)
        if not isinstance(data, list):
            return []
        jobs: list[ProviderJob] = []
        for item in data[1:]:
            if "id" not in item:
                continue
            jobs.append(ProviderJob(
                source="remoteok",
                external_id=str(item.get("id")),
                title=str(item.get("position") or "")[:300],
                company=item.get("company", ""),
                location=item.get("location", "Remote"),
                country="Remote",
                remote=True,
                salary_min=_int_or_none(item.get("salary_min")),
                salary_max=_int_or_none(item.get("salary_max")),
                salary_currency="USD" if item.get("salary_min") or item.get("salary_max") else None,
                employment_type=item.get("job_type", "") or "",
                experience_level="",
                description=(item.get("description") or "")[:4000],
                url=item.get("url", ""),
                skills=[str(t) for t in (item.get("tags") or [])][:20],
                posted_date=_parse_timestamp(item.get("date")),
            ))
            if len(jobs) >= self.MAX_JOBS:
                break
        return jobs


class JobicyProvider(BaseProvider):
    """Real remote jobs from the public Jobicy API (no key required)."""

    name = "jobicy"
    label = "Jobicy (real remote jobs, free API)"
    fetch_ttl = FAST_FEED_TTL_SECONDS
    MAX_JOBS = 100

    def fetch(self, titles, skills, locations, remote_only):
        data = _cached_get_json("jobicy", JOBICY_API, params={"count": str(self.MAX_JOBS)})
        if not isinstance(data, dict):
            return []
        jobs: list[ProviderJob] = []
        for item in data.get("jobs", [])[: self.MAX_JOBS]:
            jobs.append(ProviderJob(
                source="jobicy",
                external_id=str(item.get("id") or _normalize(f"{item.get('jobTitle')}{item.get('companyName')}")),
                title=str(item.get("jobTitle") or "")[:300],
                company=item.get("companyName", ""),
                location=item.get("jobGeo", "Remote"),
                country="Remote",
                remote=True,
                salary_min=_int_or_none(item.get("annualSalaryMin")),
                salary_max=_int_or_none(item.get("annualSalaryMax")),
                salary_currency=(item.get("salaryCurrency") or None),
                employment_type=_join_or_str(item.get("jobType")),
                experience_level=item.get("jobLevel", "") or "",
                description=((item.get("jobDescription") or item.get("jobExcerpt")) or "")[:4000],
                url=item.get("url", ""),
                skills=[str(i) for i in (item.get("jobIndustry") or [])],
                posted_date=_parse_date(item.get("pubDate")),
            ))
        return jobs


class ArbeitnowProvider(BaseProvider):
    """Real jobs (mostly EU remote) from the public Arbeitnow API (no key required).

    The feed is paginated (325 postings per page, newest first), so two pages are
    pulled per run — that is twice the jobs for two cached GETs per TTL window.
    """

    name = "arbeitnow"
    label = "Arbeitnow (real jobs, free API)"
    fetch_ttl = FAST_FEED_TTL_SECONDS
    MAX_JOBS = 600
    PAGES = 2

    def fetch(self, titles, skills, locations, remote_only):
        jobs: list[ProviderJob] = []
        for page in range(1, self.PAGES + 1):
            data = _cached_get_json(f"arbeitnow:p{page}", ARBEITNOW_API, params={"page": str(page)})
            if not isinstance(data, dict):
                break
            items = data.get("data", [])
            if not items:
                break
            for item in items:
                jobs.append(ProviderJob(
                    source="arbeitnow",
                    external_id=str(item.get("slug") or _normalize(f"{item.get('title')}{item.get('company_name')}")),
                    title=str(item.get("title") or "")[:300],
                    company=item.get("company_name", ""),
                    location=item.get("location", ""),
                    country=item.get("location", ""),
                    remote=bool(item.get("remote")),
                    salary_min=None,
                    salary_max=None,
                    salary_currency=None,
                    employment_type=", ".join(item.get("job_types") or []),
                    experience_level="",
                    description=_strip_html(item.get("description") or "")[:4000],
                    url=item.get("url", ""),
                    skills=[str(t) for t in (item.get("tags") or [])][:20],
                    posted_date=_parse_timestamp(item.get("created_at")),
                ))
                if len(jobs) >= self.MAX_JOBS:
                    return jobs
            if not (data.get("links") or {}).get("next"):
                break
        return jobs


class WeWorkRemotelyProvider(BaseProvider):
    """Real remote jobs from the We Work Remotely public RSS feed (no key required).

    The feed is the site's own syndication feed and carries a publication date plus
    an expiry date per posting, which is the strongest available proof that a job is
    still live.
    """

    name = "weworkremotely"
    label = "We Work Remotely (real remote jobs, public feed)"
    fetch_ttl = FAST_FEED_TTL_SECONDS
    MAX_JOBS = 120

    def fetch(self, titles, skills, locations, remote_only):
        xml_text = _cached_get_text("weworkremotely", WWR_RSS)
        if not xml_text:
            return []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            log.warning("weworkremotely feed is not parseable: %s", exc)
            return []

        jobs: list[ProviderJob] = []
        for item in root.findall("./channel/item")[: self.MAX_JOBS]:
            raw_title = unescape((item.findtext("title") or "").strip())
            if not raw_title:
                continue
            company, title = _split_wwr_title(raw_title)
            location = ", ".join(
                part for part in (
                    unescape(item.findtext("country") or "").strip(),
                    unescape(item.findtext("region") or "").strip(),
                ) if part
            ) or "Remote"
            jobs.append(ProviderJob(
                source="weworkremotely",
                external_id=str(item.findtext("guid") or _normalize(f"{company}{title}")),
                title=title[:300],
                company=company,
                location=location,
                country=unescape(item.findtext("country") or "").strip() or "Remote",
                remote=True,
                employment_type=unescape(item.findtext("type") or "").strip(),
                experience_level="",
                description=_strip_html(item.findtext("description") or "")[:4000],
                url=(item.findtext("link") or "").strip(),
                skills=[s.strip() for s in re.split(r"[,;]", unescape(item.findtext("skills") or "")) if s.strip()][:20],
                posted_date=_parse_rfc822(item.findtext("pubDate")),
                expiry_date=_parse_rfc822(item.findtext("expires_at")),
            ))
        return jobs


class HimalayasProvider(BaseProvider):
    """Real remote jobs from the public Himalayas API (no key required).

    Newest postings first, 20 per page, and every item carries its own expiry date,
    so the feed tells us when a posting stops being a real opening.
    """

    name = "himalayas"
    label = "Himalayas (real remote jobs, free API)"
    fetch_ttl = FAST_FEED_TTL_SECONDS
    MAX_JOBS = 100
    PAGE_SIZE = 20

    def fetch(self, titles, skills, locations, remote_only):
        jobs: list[ProviderJob] = []
        for offset in range(0, self.MAX_JOBS, self.PAGE_SIZE):
            data = _cached_get_json(f"himalayas:o{offset}", HIMALAYAS_API, params={"offset": str(offset)})
            if not isinstance(data, dict):
                break
            items = data.get("jobs") or []
            if not items:
                break
            for item in items:
                restrictions = [str(r) for r in (item.get("locationRestrictions") or [])]
                jobs.append(ProviderJob(
                    source="himalayas",
                    external_id=str(item.get("guid") or item.get("applicationLink")
                                    or _normalize(f"{item.get('title')}{item.get('companyName')}")),
                    # This feed sends titles and company names HTML-escaped ("&#x28;Remote&#x29;");
                    # decoding before the 300-char cut also avoids slicing an entity in half.
                    title=_plain_field(item.get("title"))[:300],
                    company=_plain_field(item.get("companyName")),
                    location=_plain_field(", ".join(restrictions)) or "Remote",
                    country=_plain_field(", ".join(restrictions[:1])) or "Remote",
                    remote=True,
                    salary_min=_int_or_none(item.get("minSalary")),
                    salary_max=_int_or_none(item.get("maxSalary")),
                    salary_currency=(item.get("currency") or None),
                    employment_type=_plain_field(item.get("employmentType")),
                    experience_level=_plain_field(", ".join(str(s) for s in (item.get("seniority") or []))),
                    description=_strip_html(item.get("description") or item.get("excerpt") or "")[:4000],
                    url=item.get("applicationLink") or item.get("guid") or "",
                    # Their categories arrive as url-slugs ("React-Native"); the rest of the
                    # feeds send plain words, and the matcher compares on plain words.
                    skills=[str(c).replace("-", " ").strip() for c in (item.get("categories") or [])][:20],
                    # pubDate/expiryDate are generated when the feed is built: every page
                    # walks backwards in exact 15-second steps from "now". Trusting them would
                    # re-date every ad on each import, so nothing from this site could age out.
                    posted_date=None,
                    expiry_date=None,
                ))
                if len(jobs) >= self.MAX_JOBS:
                    return jobs
        return jobs


class WorkingNomadsProvider(BaseProvider):
    """Real remote jobs from the public Working Nomads feed (no key required)."""

    name = "workingnomads"
    label = "Working Nomads (real remote jobs, free feed)"
    fetch_ttl = FAST_FEED_TTL_SECONDS
    MAX_JOBS = 200

    def fetch(self, titles, skills, locations, remote_only):
        data = _cached_get_json("workingnomads", WORKING_NOMADS_API)
        if not isinstance(data, list):
            return []
        jobs: list[ProviderJob] = []
        for item in data[: self.MAX_JOBS]:
            url = (item.get("url") or "").strip()
            if not item.get("title"):
                continue
            # The link is "/job/go/<numeric id>/", which is the stable posting id.
            external_id = url.rstrip("/").rsplit("/", 1)[-1] or _normalize(
                f"{item.get('title')}{item.get('company_name')}"
            )
            tags = [t.strip() for t in str(item.get("tags") or "").split(",") if t.strip()]
            category = str(item.get("category_name") or "").strip()
            jobs.append(ProviderJob(
                source="workingnomads",
                external_id=external_id,
                title=str(item.get("title") or "")[:300],
                company=item.get("company_name", ""),
                location=item.get("location") or "Remote",
                country="Remote",
                remote=True,
                employment_type=category,
                experience_level="",
                description=_strip_html(unescape(item.get("description") or ""))[:4000],
                url=url,
                skills=(tags + [category])[:20],
                posted_date=_parse_timestamp(item.get("pub_date")),
            ))
        return jobs


class LinkedInProvider(BaseProvider):
    """Real jobs from LinkedIn's public guest listings (no key, no login).

    The guest endpoint serves the same result cards a logged-out browser visitor
    sees. The app sends its honest User-Agent and never signs in, solves a
    CAPTCHA, or bypasses any access control; if LinkedIn blocks or changes the
    feed, the fetch logs a warning and the source contributes nothing that run.
    """

    name = "linkedin"
    label = "LinkedIn (real jobs, public guest listings)"
    keep_cache_window = True  # it blocks a visitor who keeps reloading the same search
    keyword_search = True
    MAX_TERMS = 4
    MAX_JOBS = 150
    PAGES = 2
    PAGE_STEP = 25

    def fetch(self, titles, skills, locations, remote_only):
        where = locations[0].strip() if locations and locations[0].strip() else "Egypt"
        jobs: list[ProviderJob] = []
        seen: set[str] = set()
        for search in search_terms(titles, skills)[: self.MAX_TERMS]:
            for page in range(self.PAGES):
                html = _cached_get_text(
                    f"linkedin:{search}:{where}:p{page}",
                    LINKEDIN_GUEST_API,
                    params={"keywords": search, "location": where,
                            "f_TPR": "r2592000", "start": str(page * self.PAGE_STEP)},
                )
                if not html:
                    break
                cards = _parse_linkedin_cards(html)
                if not cards:
                    break
                for pj in cards:
                    if pj.external_id in seen:
                        continue
                    seen.add(pj.external_id)
                    jobs.append(pj)
                if len(jobs) >= self.MAX_JOBS:
                    return jobs[: self.MAX_JOBS]
        return jobs[: self.MAX_JOBS]


class JSearchProvider(BaseProvider):
    """Real Egypt jobs from Google for Jobs via the JSearch API (needs a RapidAPI key).

    Wuzzuf and other Egyptian boards submit their live openings to Google's public
    job index; JSearch reads that index, so this returns genuine postings without
    scraping any site or bypassing any anti-bot protection. It is the only source
    here that needs a key, and it stays silent when RAPIDAPI_KEY is unset.
    """

    name = "jsearch"
    fetch_ttl = QUOTA_CAPPED_TTL_SECONDS
    keep_cache_window = True
    label = "Google for Jobs — Egypt (JSearch, key required)"
    requires_key = True
    keyword_search = True
    MAX_JOBS = 120

    def fetch(self, titles, skills, locations, remote_only):
        global _jsearch_turn
        key = getattr(config, "RAPIDAPI_KEY", "")
        if not key:
            log.info("jsearch skipped: RAPIDAPI_KEY is not configured")
            return []
        terms = search_terms(titles, skills)
        role = terms[_jsearch_turn % len(terms)]
        _jsearch_turn += 1
        where = locations[0].strip() if locations and locations[0].strip() else "Egypt"
        query = f"{role} jobs in {where}"
        data = _cached_get_json(
            f"jsearch:{query}",
            JSEARCH_API,
            params={"query": query, "num_pages": "3", "country": "eg", "date_posted": "month"},
            headers={"x-rapidapi-key": key, "x-rapidapi-host": JSEARCH_HOST},
        )
        if not isinstance(data, dict):
            return []
        # v1 returned data as a list; v2 nests it under data.jobs.
        payload = data.get("data")
        if isinstance(payload, dict):
            payload = payload.get("jobs")
        if not isinstance(payload, list):
            return []

        jobs: list[ProviderJob] = []
        for item in payload[: self.MAX_JOBS]:
            title = _strip_html(str(item.get("job_title") or ""))[:300]
            external_id = str(item.get("job_id") or item.get("job_uid") or "")
            if not title or not external_id:
                continue
            publisher = str(item.get("job_publisher") or "").strip()
            company = _strip_html(str(item.get("employer_name") or "").strip()) or publisher
            location = _strip_html(str(item.get("job_location") or "").strip())
            # Google appends "• عبر Wuzzuf"-style suffixes; the place name alone is useful.
            location = location.split("•")[0].strip()
            desc = _strip_html(str(item.get("job_description") or ""))[:4000]
            if publisher and publisher.lower() not in desc.lower():
                desc = (f"[via {publisher}] " + desc)[:4000]
            jobs.append(ProviderJob(
                source="jsearch",
                external_id=external_id,
                title=title,
                company=company[:200],
                location=location or where,
                country=str(item.get("job_country") or "Egypt"),
                remote=bool(item.get("job_is_remote")),
                salary_min=_int_or_none(item.get("job_min_salary")),
                salary_max=_int_or_none(item.get("job_max_salary")),
                salary_currency=(str(item.get("job_salary_currency")).strip() or None)
                                if item.get("job_min_salary") or item.get("job_max_salary") else None,
                employment_type=_jsearch_employment(item),
                experience_level="",
                description=desc,
                url=str(item.get("job_apply_link") or item.get("job_onsite_url") or ""),
                skills=[],
                posted_date=_parse_timestamp(item.get("job_posted_at_timestamp"))
                            or _parse_date(item.get("job_posted_at_datetime_utc"))
                            or _relative_to_date(item.get("job_posted_at")),
            ))
        return jobs


_MONTH_DATE_FORMATS = ("%B %d, %Y", "%b %d, %Y", "%d %B %Y", "%d %b %Y")


def _parse_named_date(value) -> datetime | None:
    """'October 25, 2026' — Amazon's date format, which ISO parsing cannot read."""
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    text = re.sub(r"(\d+)(?:st|nd|rd|th)\b", r"\1", text)
    if not text:
        return None
    for fmt in _MONTH_DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _parse_loose_date(value) -> datetime | None:
    """ISO with any fraction length (Jooble/Workday), an epoch, or English words."""
    text = str(value or "").strip()
    if not text:
        return None
    trimmed = re.sub(r"(\.\d{6})\d+", r"\1", text)  # .NET sends 7 fractional digits
    if re.fullmatch(r"\d{13}", trimmed):
        return _parse_epoch(int(trimmed) // 1000)
    return (_parse_date(trimmed) or _parse_date(text) or _parse_epoch(text)
            or _parse_named_date(text) or _relative_to_date(text))


_EGYPT_RE = re.compile(
    r"\b(egypt|eg|cairo|giza|alexandria|qahirah|al qahirah|6th of october|"
    r"10th of ramadan|beni suef|beni sweif|mansoura|tanta|luxor|aswan|hurghada|"
    r"sharm el sheikh|port said|suez|ismailia|new cairo|sheikh zayed|maadi|nasr city)\b"
    r"|مصر|القاهرة|الجيزة|الإسكندرية|الاسكندرية|طنطا|المنصورة"
    r"|\b\d+\s+locations?\b",
    re.I,
)


def _is_egypt(value) -> bool:
    return bool(_EGYPT_RE.search(str(value or "")))


def _remote_word(text: str) -> bool:
    return bool(re.search(r"\bremote|virtual|work from home|عن بعد|من المنزل\b", text, re.I))


# Locations a remote posting can carry that are open to an Egypt-based applicant.
# "Remote - US" or "Remote, AMER" means the role is country/region-locked, so those
# are closed; "Remote", "Remote, Global", "Home Based - EMEA" are open.
_REMOTE_CLOSED_RE = re.compile(
    r"\b(amer|apac|latam|latin america|united states|usa|us|uk|united kingdom|canada|india|"
    r"mexico|colombia|brazil|australia|japan|singapore|germany|france|spain|poland|"
    r"netherlands|portugal|ireland|italy|philippines|europe|north america|south america|"
    r"asia|austria|switzerland|uae|dubai|korea|china|taiwan|hong kong|new zealand|"
    r"argentina|chile|peru|israel|turkey|denmark|sweden|norway|finland|belgium|"
    r"czech|romania|bulgaria|ukraine)\b",
    re.I,
)
_REMOTE_OPEN_RE = re.compile(r"\b(global|anywhere|worldwide|emea|mena|middle east|africa)\b", re.I)


def _open_remote(text: str) -> bool:
    low = (text or "").casefold()
    if not re.search(r"\b(remote|anywhere|worldwide|global|home based|homebased)\b", low):
        return False
    if _REMOTE_OPEN_RE.search(low):
        return True
    if _REMOTE_CLOSED_RE.search(low):
        return False
    norm = re.sub(r"[^a-z]", "", low)
    return norm in {"remote", "remotework", "fullyremote", "100remote", "remoteok", "fullremote",
                    "homebased", "workfromhome"}


class AmazonProvider(BaseProvider):
    """Amazon's own careers API (no key). One request returns every Egypt posting,
    including operations, customer-service and support roles that the remote-only
    boards never carry. Descriptions come with the listing, so the relevance gate
    and the apply-route reader see real text.
    """

    name = "amazon"
    label = "Amazon Careers — Egypt (employer site, free)"
    fetch_ttl = FAST_FEED_TTL_SECONDS
    keyword_search = False
    MAX_JOBS = 100

    def fetch(self, titles, skills, locations, remote_only):
        params = {"base_query": "", "loc_query": "Egypt", "country": "EGY",
                  "result_limit": 100, "sort": "recent"}
        data = _cached_get_json("amazon:egypt", AMAZON_SEARCH_API, params=params, timeout=30.0)
        if not isinstance(data, dict):
            # A single dropped connection used to empty this source for the whole run.
            data = _cached_get_json("amazon:egypt", AMAZON_SEARCH_API, params=params, timeout=30.0)
        if not isinstance(data, dict):
            return []
        jobs: list[ProviderJob] = []
        for item in (data.get("jobs") or [])[: self.MAX_JOBS]:
            title = _plain_field(item.get("title"))[:300]
            external_id = str(item.get("id_icims") or item.get("id") or "").strip()
            if not title or not external_id:
                continue
            raw_location = str(item.get("location") or "").strip()
            if item.get("country_code") and item["country_code"] != "EGY" and not _is_egypt(raw_location):
                continue
            location = re.sub(r"^EG,\s*", "", raw_location)
            if location and "egypt" not in location.casefold():
                location = f"{location}, Egypt"
            description = " ".join(
                _strip_html(str(item.get(key) or ""))
                for key in ("description", "basic_qualifications", "preferred_qualifications")
            )[:4000]
            path = str(item.get("job_path") or "")
            url = f"https://www.amazon.jobs{path}" if path.startswith("/") else str(item.get("url_next_step") or "")
            jobs.append(ProviderJob(
                source=self.name,
                external_id=external_id,
                title=title,
                company=_plain_field(item.get("company_name"))[:200],
                location=location or "Egypt",
                country="Egypt",
                remote=_remote_word(f"{title} {location}"),
                employment_type=str(item.get("job_schedule_type") or ""),
                description=description,
                url=url,
                posted_date=_parse_named_date(item.get("posted_date")),
            ))
        return jobs


# Employers that run their own careers site on Workday. This is a direct channel
# to the company's own ATS — no aggregator, no key, no scraping.
WORKDAY_EMPLOYERS = (
    ("citi", "wd5", "2", "Citi"),
    ("pfizer", "wd1", "PfizerCareers", "Pfizer"),
    ("sanofi", "wd3", "SanofiCareers", "Sanofi"),
    ("astrazeneca", "wd3", "Careers", "AstraZeneca"),
    ("novartis", "wd3", "Novartis_Careers", "Novartis"),
    ("cisco", "wd5", "Cisco_Careers", "Cisco"),
    ("unilever", "wd3", "Unilever_Experienced_Professionals", "Unilever"),
    ("pwc", "wd3", "Global_Experienced_Careers", "PwC"),
    ("hp", "wd5", "ExternalCareerSite", "HP"),
    ("maersk", "wd3", "Maersk_Careers", "Maersk"),
    ("accenture", "wd103", "AccentureCareers", "Accenture"),
)


class WorkdayProvider(BaseProvider):
    """Employer career sites served by Workday, filtered to Egypt.

    Each employer publishes a public JSON search endpoint for its own site; the
    app asks it for "Egypt" and then reads the job page for the real posting date
    and description. Employers whose site is not Workday are simply not listed.
    """

    name = "workday"
    label = "Employer career sites — Egypt (Workday, free)"
    fetch_ttl = FAST_FEED_TTL_SECONDS
    keyword_search = False
    MAX_DETAILS = 30

    def fetch(self, titles, skills, locations, remote_only):
        # These employers are separate servers, so asking them one after another made
        # this provider cost a row of waits. They are asked together, but the answers
        # are read back in list order: which posting comes first must not depend on
        # which server happened to reply first.
        def listings(employer):
            tenant, wd, site, company = employer
            base = WORKDAY_BASE.format(tenant=tenant, wd=wd)
            data = _cached_post_json(
                f"workday:{tenant}:{site}", f"{base}/wday/cxs/{tenant}/{site}/jobs",
                {"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": "Egypt"},
            )
            return base, data

        # A fresh thread starts with an empty context, so the job's own cache window
        # has to be carried into it or these reads fall back to the default.
        policy = contextvars.copy_context()
        with ThreadPoolExecutor(max_workers=min(PAGES_PER_SITE, len(WORKDAY_EMPLOYERS))) as pool:
            answered = list(pool.map(lambda employer: policy.copy().run(listings, employer),
                                     WORKDAY_EMPLOYERS))

        candidates = []
        for (tenant, wd, site, company), (base, data) in zip(WORKDAY_EMPLOYERS, answered):
            postings = data.get("jobPostings") if isinstance(data, dict) else None
            for posting in postings or []:
                title = _plain_field(posting.get("title"))[:300]
                path = str(posting.get("externalPath") or "")
                where = str(posting.get("locationsText") or "")
                if not title or not path or not _is_egypt(where):
                    continue
                candidates.append((tenant, wd, site, company, base, posting, path, where))

        def detail(item):
            tenant, wd, site, company, base, posting, path, where = item
            info = {}
            data = _cached_get_json(
                f"workday:{tenant}:{site}:{path}",
                f"{base}/wday/cxs/{tenant}/{site}{path}",
            )
            if isinstance(data, dict):
                info = data.get("jobPostingInfo") or {}
            title = _plain_field(posting.get("title") or info.get("title"))[:300]
            req = (posting.get("bulletFields") or [""])[0]
            location = _strip_html(str(info.get("location") or where))
            extra = info.get("additionalLocations") or []
            if isinstance(extra, list) and extra:
                location = ", ".join([location, *(_strip_html(str(x)) for x in extra)])
            country = (info.get("country") or {}).get("descriptor") if isinstance(info.get("country"), dict) else ""
            if country and country.casefold() not in location.casefold():
                location = f"{location}, {country}" if location else country
            return ProviderJob(
                source=self.name,
                external_id=f"{tenant}:{req or path}",
                title=title,
                company=company,
                location=location or "Egypt",
                country=country or "Egypt",
                remote=_remote_word(f"{title} {location}"),
                employment_type=str(info.get("timeType") or ""),
                description=_strip_html(str(info.get("jobDescription") or ""))[:4000],
                url=str(info.get("externalUrl") or f"{base}/{site}{path}"),
                posted_date=_parse_loose_date(info.get("startDate")),
            )

        with ThreadPoolExecutor(max_workers=PAGES_PER_SITE) as pool:
            return [job for job in pool.map(
                lambda item: policy.copy().run(detail, item), candidates[: self.MAX_DETAILS]) if job.title]


SMARTRECRUITERS_EMPLOYERS = (("DeliveryHero", "Delivery Hero"),)


class SmartRecruitersProvider(BaseProvider):
    """Employers that publish their own openings through SmartRecruiters (no key)."""

    name = "smartrecruiters"
    label = "Employer career sites — Egypt (SmartRecruiters, free)"
    fetch_ttl = FAST_FEED_TTL_SECONDS
    keyword_search = False
    MAX_JOBS = 60
    MAX_DETAILS = 20

    def fetch(self, titles, skills, locations, remote_only):
        jobs: list[ProviderJob] = []
        for identifier, company_name in SMARTRECRUITERS_EMPLOYERS:
            data = _cached_get_json(
                f"smartrecruiters:{identifier}:eg",
                SMARTRECRUITERS_API.format(company=identifier),
                params={"country": "eg", "limit": 100},
            )
            postings = (data.get("content") if isinstance(data, dict) else None) or []
            postings = sorted(
                postings,
                key=lambda p: _parse_loose_date(p.get("releasedDate")) or datetime(1970, 1, 1, tzinfo=timezone.utc),
                reverse=True,
            )[: self.MAX_JOBS]

            def detail(posting, identifier=identifier, company_name=company_name):
                posting_id = str(posting.get("id") or "")
                if not posting_id:
                    return None
                location = posting.get("location") or {}
                full_location = str(location.get("fullLocation") or "")
                description = ""
                info = _cached_get_json(
                    f"smartrecruiters:{identifier}:{posting_id}",
                    f"https://api.smartrecruiters.com/v1/companies/{identifier}/postings/{posting_id}",
                )
                url = f"https://jobs.smartrecruiters.com/{identifier}/{posting_id}"
                if isinstance(info, dict):
                    sections = ((info.get("jobAd") or {}).get("sections") or {})
                    description = " ".join(
                        _strip_html(str(value)) for value in sections.values() if isinstance(value, str)
                    )[:4000]
                    url = str(info.get("postingUrl") or url)
                    full_location = str((info.get("location") or {}).get("fullLocation") or full_location)
                title = _plain_field(posting.get("name"))[:300]
                if not title:
                    return None
                return ProviderJob(
                    source=self.name,
                    external_id=f"{identifier}:{posting_id}",
                    title=title,
                    company=company_name,
                    location=full_location or "Egypt",
                    country="Egypt",
                    remote=bool(location.get("remote") or location.get("hybrid")),
                    employment_type=str((posting.get("typeOfEmployment") or {}).get("label") or ""),
                    experience_level=str((posting.get("experienceLevel") or {}).get("label") or ""),
                    description=description,
                    url=url,
                    posted_date=_parse_loose_date(posting.get("releasedDate")),
                )

            policy = contextvars.copy_context()
            with ThreadPoolExecutor(max_workers=PAGES_PER_SITE) as pool:
                jobs.extend(job for job in pool.map(
                    lambda posting: policy.copy().run(detail, posting), postings[: self.MAX_DETAILS]) if job)
        return jobs


# Employers whose own careers API lists roles open to worldwide remote applicants.
# Each board was probed live: only companies that publish postings in a location an
# Egypt-based applicant can take ("Remote", "Remote, Global", "Home Based - EMEA"…)
# are listed. Boards whose remote roles are country-locked (Coinbase, Affirm,
# Twilio…) are deliberately absent — importing them would only show jobs he cannot
# apply to.
EMPLOYER_BOARDS = (
    ("greenhouse", "canonical", "Canonical"),
    ("greenhouse", "stripe", "Stripe"),
    ("greenhouse", "mozilla", "Mozilla"),
    ("greenhouse", "gitlab", "GitLab"),
    ("greenhouse", "netlify", "Netlify"),
    ("greenhouse", "airbnb", "Airbnb"),
    ("greenhouse", "cloudflare", "Cloudflare"),
    ("greenhouse", "discord", "Discord"),
    ("greenhouse", "brex", "Brex"),
    ("ashby", "supabase", "Supabase"),
    ("ashby", "railway", "Railway"),
    ("ashby", "posthog", "PostHog"),
)


class EmployerBoardsProvider(BaseProvider):
    """Employer career boards (Greenhouse/Ashby) with roles open worldwide.

    The companies' own applicant-system APIs are public JSON — no key, no scraping.
    Greenhouse's list omits the description, so only the postings whose location is
    open to Egypt get one detail read each (capped: a big board costs a handful of
    requests, not hundreds).
    """

    name = "employers"
    label = "Employer boards — worldwide remote (Greenhouse/Ashby, free)"
    fetch_ttl = FETCH_CACHE_TTL_SECONDS
    keyword_search = False
    MAX_OPEN_PER_BOARD = 6
    MAX_OPEN_TOTAL = 30

    def fetch(self, titles, skills, locations, remote_only):
        def board(entry):
            ats, company, company_name = entry
            url = EMPLOYER_BOARD_APIS[ats].format(company=company)
            data = _cached_get_json(f"employers:{ats}:{company}", url)
            if not isinstance(data, dict):
                return ats, company, company_name, []
            postings = data.get("jobs") or []
            if ats == "greenhouse":
                return ats, company, company_name, [
                    (p, str((p.get("location") or {}).get("name") or ""))
                    for p in postings
                ]
            return ats, company, company_name, [
                (p, " | ".join(
                    [str(p.get("location") or ""), *[
                        str(s.get("location") or "")
                        for s in (p.get("secondaryLocations") or [])]]))
                for p in postings
            ]

        policy = contextvars.copy_context()
        with ThreadPoolExecutor(max_workers=min(PAGES_PER_SITE, len(EMPLOYER_BOARDS))) as pool:
            answered = list(pool.map(lambda entry: policy.copy().run(board, entry),
                                     EMPLOYER_BOARDS))

        def open_job(item):
            ats, company, company_name, postings = item
            kept = []
            for posting, location in postings:
                if not (_is_egypt(location) or _open_remote(location)):
                    continue
                kept.append((ats, company, company_name, posting, location))
                if len(kept) >= self.MAX_OPEN_PER_BOARD:
                    break
            return kept

        candidates: list[tuple] = []
        for item in answered:
            candidates.extend(open_job(item))
            if len(candidates) >= self.MAX_OPEN_TOTAL:
                break
        candidates = candidates[: self.MAX_OPEN_TOTAL]

        def detail(item):
            ats, company, company_name, posting, location = item
            posting_id = str(posting.get("id") or "")
            title = _plain_field(posting.get("title"))[:300]
            if not title or not posting_id:
                return None
            description = ""
            info = posting
            url = ""
            if ats == "greenhouse":
                info = _cached_get_json(
                    f"employers:greenhouse:{company}:{posting_id}",
                    GREENHOUSE_DETAIL_API.format(company=company, posting_id=posting_id),
                ) or posting
                if isinstance(info, dict) and info.get("content"):
                    description = _strip_html(str(info["content"]))[:4000]
                url = str(posting.get("absolute_url") or info.get("absolute_url") or "")
            else:
                description = (
                    str(posting.get("descriptionPlain") or "")
                    or _strip_html(str(posting.get("descriptionHtml") or ""))
                )[:4000]
                url = str(posting.get("jobUrl") or "")
            posted = (_parse_date(posting.get("first_published"))
                      or _parse_date(posting.get("publishedAt")))
            return ProviderJob(
                source=self.name,
                external_id=f"{ats}:{company}:{posting_id}",
                title=title,
                company=company_name,
                location=location[:300],
                country="Egypt" if _is_egypt(location) else "",
                remote=_remote_word(location),
                employment_type=str(posting.get("employmentType") or ""),
                description=description,
                url=url,
                posted_date=posted,
            )

        with ThreadPoolExecutor(max_workers=PAGES_PER_SITE) as pool:
            return [job for job in pool.map(
                lambda item: policy.copy().run(detail, item), candidates) if job]


def _salary_range(text: str) -> tuple[int | None, int | None, str | None]:
    """'67200-80000 USD' or '€45k – €70k' -> (min, max, currency)."""
    match = re.search(r"([€$£]?\s*[\d.,]+[kKmM]?)\s*[-–—]\s*([€$£]?\s*[\d.,]+[kKmM]?)\s*([A-Za-z€$£]{1,3})", text or "")
    if not match:
        return None, None, None

    def amount(raw: str) -> int | None:
        unit = 1
        for suffix, factor in (("k", 1000), ("K", 1000), ("m", 1000000), ("M", 1000000)):
            if suffix in raw:
                raw, unit = raw.replace(suffix, ""), factor
                break
        value = _int_or_none(re.sub(r"[^\d]", "", raw))
        return value * unit if value is not None else None

    currency = match.group(3).upper()
    if currency in {"$", "€", "£"}:
        currency = {"$": "USD", "€": "EUR", "£": "GBP"}[currency]
    return amount(match.group(1)), amount(match.group(2)), currency


class JobgetherProvider(BaseProvider):
    """Jobgether — a worldwide remote-job aggregator with a public JSON feed.

    Its listings carry the employer's own country restrictions, so only postings
    whose location is open to Egypt (Egypt, Worldwide, Anywhere…) are imported.
    """

    name = "jobgether"
    label = "Jobgether — remote aggregator (free)"
    fetch_ttl = FETCH_CACHE_TTL_SECONDS
    keyword_search = False
    MAX_PAGES = 2

    def fetch(self, titles, skills, locations, remote_only):
        jobs: list[ProviderJob] = []
        for page in range(1, self.MAX_PAGES + 1):
            data = _cached_get_json(f"jobgether:{page}", JOBGETHER_API, params={"page": page})
            if not isinstance(data, dict):
                break
            batch = data.get("jobs") or []
            if not batch:
                break
            for item in batch:
                location = str(item.get("location") or "").strip()
                remote = str(item.get("remote") or "").strip()
                combined = f"{remote} {location}".strip()
                if not (_is_egypt(combined) or _open_remote(combined)):
                    continue
                title = _plain_field(item.get("title"))[:300]
                external_id = str(item.get("id") or "").strip()
                if not title or not external_id:
                    continue
                functions = [_plain_field(f) for f in (item.get("jobFunctions") or [])]
                functions = [f for f in functions if f][:10]
                smin, smax, scur = _salary_range(str(item.get("salaryRange") or ""))
                jobs.append(ProviderJob(
                    source=self.name,
                    external_id=external_id,
                    title=title,
                    company=_plain_field(item.get("company"))[:200],
                    location=location[:300],
                    country="Egypt" if _is_egypt(combined) else "",
                    remote=_remote_word(combined),
                    salary_min=smin,
                    salary_max=smax,
                    salary_currency=scur,
                    employment_type=str(item.get("contractType") or ""),
                    experience_level=str(item.get("experience") or ""),
                    description=("Job functions: " + ", ".join(functions)) if functions else "",
                    url=str(item.get("url") or ""),
                    skills=functions,
                    posted_date=_parse_date(item.get("postedAt")),
                ))
        return jobs


_adzuna_turn = 0


class AdzunaProvider(BaseProvider):
    """Adzuna's Egypt index (needs the free Adzuna app id + key pair).

    Adzuna aggregates Egyptian job boards' postings through its public API. It stays
    silent until ADZUNA_APP_ID and ADZUNA_APP_KEY are both set, and then spends one
    request per import, rotating through the search phrases like the other key-capped
    sources.
    """

    name = "adzuna"
    fetch_ttl = QUOTA_CAPPED_TTL_SECONDS
    keep_cache_window = True
    label = "Adzuna — Egypt (aggregator, key required)"
    requires_key = True
    keyword_search = True
    MAX_JOBS = 50

    def fetch(self, titles, skills, locations, remote_only):
        global _adzuna_turn
        app_id = getattr(config, "ADZUNA_APP_ID", "")
        app_key = getattr(config, "ADZUNA_APP_KEY", "")
        if not app_id or not app_key:
            log.info("adzuna skipped: ADZUNA_APP_ID/ADZUNA_APP_KEY are not configured")
            return []
        terms = search_terms(titles, skills)
        phrase = terms[_adzuna_turn % len(terms)]
        _adzuna_turn += 1
        where = locations[0].strip() if locations and locations[0].strip() else "Egypt"
        data = _cached_get_json(
            f"adzuna:{phrase}:{where}",
            ADZUNA_API.format(country="eg"),
            params={"app_id": app_id, "app_key": app_key, "what": phrase,
                    "where": where, "results_per_page": self.MAX_JOBS,
                    "content-type": "application/json"},
        )
        if not isinstance(data, dict):
            return []
        jobs: list[ProviderJob] = []
        for item in (data.get("results") or [])[: self.MAX_JOBS]:
            title = _plain_field(item.get("title"))[:300]
            external_id = str(item.get("id") or "").strip()
            if not title or not external_id:
                continue
            company_data = item.get("company") or {}
            company = _plain_field(company_data.get("display_name"))[:200]
            location = _plain_field((item.get("location") or {}).get("display_name"))
            jobs.append(ProviderJob(
                source=self.name,
                external_id=external_id,
                title=title,
                company=company,
                location=location or where,
                country="Egypt",
                remote=_remote_word(f"{title} {location}"),
                salary_min=_int_or_none(item.get("salary_min")),
                salary_max=_int_or_none(item.get("salary_max")),
                salary_currency=(str(item.get("salary_currency") or "").strip() or None)
                                if item.get("salary_min") or item.get("salary_max") else None,
                employment_type=str(item.get("contract_time") or ""),
                description=_strip_html(str(item.get("description") or ""))[:4000],
                url=str(item.get("redirect_url") or ""),
                posted_date=_parse_date(item.get("created")),
            ))
        return jobs


def _jooble_search(key: str, phrase: str, where: str):
    """Jooble's key lives in the URL, so failures are logged without the exception
    text (it would echo the key) and the cache key never contains it."""
    cache_key = f"jooble:{phrase}:{where}"
    now = time.monotonic()
    hit = _fetch_cache.get(cache_key)
    if hit and now - hit[0] < FETCH_CACHE_TTL_SECONDS:
        return hit[1]
    try:
        resp = httpx.post(
            f"{JOOBLE_API}{key}",
            json={"keywords": phrase, "location": where, "page": "1"},
            timeout=30.0,
            headers={"User-Agent": "jobhunter/1.0 (personal job search assistant)"},
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:  # noqa: BLE001 - never echo a URL that carries the key
        log.warning("jooble fetch failed: %s", type(exc).__name__)
        _record_fetch_error("jooble", exc)
        return None
    _fetch_cache[cache_key] = (now, data)
    return data


class JoobleProvider(BaseProvider):
    """Jooble (free key) — a large Egypt aggregator that indexes local boards.

    It stays perfectly silent without JOOBLE_API_KEY; the UI shows it as
    "needs an API key — skipped until then", exactly like JSearch.
    """

    name = "jooble"
    fetch_ttl = QUOTA_CAPPED_TTL_SECONDS
    keep_cache_window = True
    label = "Jooble — Egypt (aggregator, key required)"
    requires_key = True
    keyword_search = True
    MAX_JOBS = 100

    def fetch(self, titles, skills, locations, remote_only):
        global _jooble_turn
        key = getattr(config, "JOOBLE_API_KEY", "")
        if not key:
            log.info("jooble skipped: JOOBLE_API_KEY is not configured")
            return []
        terms = search_terms(titles, skills)
        phrase = terms[_jooble_turn % len(terms)]
        _jooble_turn += 1
        where = locations[0].strip() if locations and locations[0].strip() else "Egypt"
        data = _jooble_search(key, phrase, where)
        if not isinstance(data, dict):
            return []
        jobs: list[ProviderJob] = []
        for item in (data.get("jobs") or [])[: self.MAX_JOBS]:
            title = _strip_html(str(item.get("title") or ""))[:300]
            url = str(item.get("link") or "")
            external_id = str(item.get("id") or url).strip()
            if not title or not external_id:
                continue
            location = _strip_html(str(item.get("location") or ""))
            jobs.append(ProviderJob(
                source=self.name,
                external_id=external_id,
                title=title,
                company=_strip_html(str(item.get("company") or ""))[:200],
                location=location or where,
                country="Egypt",
                remote=_remote_word(f"{title} {location}"),
                employment_type=str(item.get("type") or ""),
                description=_strip_html(str(item.get("snippet") or ""))[:4000],
                url=url,
                posted_date=_parse_loose_date(item.get("updated")),
            ))
        return jobs


def _jsearch_employment(item: dict) -> str:
    """job_employment_types carries the stable English token (["FULLTIME"]); the plain
    type field is translated into the search language, so prefer the token."""
    mapped = {
        "FULLTIME": "Full-Time", "PARTTIME": "Part-Time", "CONTRACTOR": "Contractor",
        "INTERN": "Internship", "INTERNSHIP": "Internship", "TEMPORARY": "Temporary",
    }
    for token in re.findall(r"[A-Za-z]+", str(item.get("job_employment_types") or "")):
        if token.upper() in mapped:
            return mapped[token.upper()]
    return str(item.get("job_employment_type") or "").strip()


_LI_CARD_FIELDS = {
    "title": re.compile(r'<h3 class="base-search-card__title"[^>]*>(.*?)</h3>', re.S),
    "company": re.compile(r'<h4 class="base-search-card__subtitle"[^>]*>(.*?)</h4>', re.S),
    "location": re.compile(r'<span class="job-search-card__location"[^>]*>(.*?)</span>', re.S),
    "date": re.compile(r'<time[^>]*datetime="([^"]+)"'),
}


def _parse_linkedin_cards(html: str) -> list[ProviderJob]:
    jobs: list[ProviderJob] = []
    for block in html.split("<li>"):
        if "base-search-card" not in block:
            continue
        urn = re.search(r"urn:li:jobPosting:(\d+)", block)
        if not urn:
            continue
        title = _li_field(_LI_CARD_FIELDS["title"], block)
        if not title:
            continue
        location = _li_field(_LI_CARD_FIELDS["location"], block)
        href = re.search(r'base-card__full-link[^"]*"[^>]*href="([^"]+)"', block)
        if not href:
            href = re.search(r'href="(https?://[a-z0-9.-]*linkedin\.com/jobs/view/[^"]+)"', block)
        url = unescape(href.group(1)).split("?", 1)[0] if href else ""
        posted = _LI_CARD_FIELDS["date"].search(block)
        jobs.append(ProviderJob(
            source="linkedin",
            external_id=urn.group(1),
            title=title[:300],
            company=_li_field(_LI_CARD_FIELDS["company"], block),
            location=location or "Remote",
            country="Egypt" if "egypt" in location.lower() else ("Remote" if "remote" in location.lower() else location),
            remote="remote" in location.lower(),
            employment_type="",
            experience_level="",
            # The guest card carries no description text; the full posting lives
            # behind the link, and fetching it per job would hammer the site.
            description="",
            url=url,
            skills=[],
            posted_date=_parse_date(posted.group(1)) if posted else None,
        ))
    return jobs


def _li_field(pattern: re.Pattern, block: str) -> str:
    m = pattern.search(block)
    return _strip_html(m.group(1)) if m else ""


def _split_wwr_title(raw_title: str) -> tuple[str, str]:
    """WWR titles read "Company: Job title" — keep both halves as their own fields."""
    company, _, title = raw_title.partition(":")
    if title.strip() and len(company.strip()) <= 60:
        return company.strip(), title.strip()
    return "", raw_title


def _strip_html(markup: str) -> str:
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", markup or ""))).strip()


def _plain_field(value) -> str:
    """Decode escaped text in single-line fields (title, company) without eating
    angle brackets that are part of the title itself."""
    return re.sub(r"\s+", " ", unescape(str(value or ""))).strip()


def _parse_rfc822(value) -> datetime | None:
    """Feed timestamps are usually RFC-822; some fields use ISO — accept both."""
    if not value:
        return None
    text = str(value).strip()
    try:
        parsed = parsedate_to_datetime(text)
    except (TypeError, ValueError):
        parsed = None
    if parsed is None:
        return _parse_date(text)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _int_or_none(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return None


def _join_or_str(value) -> str:
    if isinstance(value, (list, tuple)):
        return ", ".join(str(v) for v in value)
    return str(value or "")


def _parse_epoch(value) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc)
    except (TypeError, ValueError, OSError, OverflowError):
        return None


def _as_utc(value: datetime | None) -> datetime | None:
    """Feeds sometimes omit the timezone; naive stamps are read as UTC, never left naive.

    A naive value compared against `datetime.now(timezone.utc)` raises, and one provider
    raising would drop the whole source from the run.
    """
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _parse_date(value) -> datetime | None:
    if not value:
        return None
    try:
        return _as_utc(datetime.fromisoformat(str(value).replace("Z", "+00:00")))
    except ValueError:
        return None


_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_ARABIC_DIACRITICS = re.compile(r"[ً-ْـ]")
# "أ/إ/آ" all read as a plain alef, "ى" as "ي", "ة" as "ه" once the marks are gone,
# so one spelling of a unit word covers the variants the feeds send.
_ARABIC_LETTERS = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ة": "ه"})
_RELATIVE_UNIT_DAYS = [
    ("سن", 365), ("عام", 365), ("year", 365),
    ("شهر", 30), ("شهور", 30), ("month", 30),
    ("اسبوع", 7), ("اسابيع", 7), ("week", 7),
    ("يوم", 1), ("ايام", 1), ("day", 1),
]


def _day_only(value: datetime) -> datetime:
    """Land a date on its UTC day.

    A feed that writes "11 days ago" or "today" names a day, never an hour. Kept at the
    instant we read it, the card would print "Posted 4h ago" for a clock time no source
    ever stated; floored, the card shows the day it actually claimed.
    """
    return value.replace(hour=0, minute=0, second=0, microsecond=0)


def _relative_to_date(value) -> datetime | None:
    """Turn a feed's own words — "قبل ١١ يومًا", "3 weeks ago" — into a date.

    JSearch sends this field already translated for the search language and leaves both
    structured date fields null; without reading the words, every aggregator posting
    would arrive with no date at all.
    """
    text = str(value or "").strip().lower()
    if not text:
        return None
    norm = _ARABIC_DIACRITICS.sub("", text).translate(_ARABIC_DIGITS).translate(_ARABIC_LETTERS)
    now = datetime.now(timezone.utc)
    if "اليوم" in norm or "today" in norm or "just posted" in norm:
        return _day_only(now)
    if "امس" in norm or "yesterday" in norm:
        return _day_only(now - timedelta(days=1))
    hit = re.search(r"(\d+)\s*\+?\s*([^\s.,;+]+)", norm)
    if hit:
        count, unit = int(hit.group(1)), hit.group(2)
        for stem, days in _RELATIVE_UNIT_DAYS:
            if stem in unit:
                return _day_only(now - timedelta(days=count * days))
        return None
    for stem, days in _RELATIVE_UNIT_DAYS:
        if stem in norm:
            return _day_only(now - timedelta(days=days))
    return None


def _parse_timestamp(value) -> datetime | None:
    """Feeds disagree: RemoteOK sends an ISO string, Arbeitnow an epoch integer."""
    if value is None or value == "":
        return None
    try:
        return _parse_epoch(value) or _parse_date(value)
    except (TypeError, ValueError):
        return None


REGISTRY: dict[str, type[BaseProvider]] = {
    # This order is the import order: an "all ticked sites" run fetches LinkedIn's
    # newest postings first, then the Egypt index (Wuzzuf and co. via Google for
    # Jobs), then the remaining boards — and the UI lists the sites the same way.
    LinkedInProvider.name: LinkedInProvider,
    JSearchProvider.name: JSearchProvider,
    # Direct-to-employer channels: their own careers APIs, all free and all
    # filtered to Egypt before anything is stored.
    AmazonProvider.name: AmazonProvider,
    WorkdayProvider.name: WorkdayProvider,
    SmartRecruitersProvider.name: SmartRecruitersProvider,
    AdzunaProvider.name: AdzunaProvider,
    JoobleProvider.name: JoobleProvider,
    # Employer boards with roles open to worldwide remote applicants, and Jobgether's
    # remote aggregator feed — both public JSON, no keys.
    EmployerBoardsProvider.name: EmployerBoardsProvider,
    JobgetherProvider.name: JobgetherProvider,
    RemotiveProvider.name: RemotiveProvider,
    RemoteOKProvider.name: RemoteOKProvider,
    JobicyProvider.name: JobicyProvider,
    ArbeitnowProvider.name: ArbeitnowProvider,
    WeWorkRemotelyProvider.name: WeWorkRemotelyProvider,
    HimalayasProvider.name: HimalayasProvider,
    WorkingNomadsProvider.name: WorkingNomadsProvider,
}


def ensure_sources(db) -> None:
    created: list[str] = []
    for name, cls in REGISTRY.items():
        if not db.query(JobSource).filter(JobSource.name == name).first():
            db.add(JobSource(name=name, label=cls.label, enabled=True, requires_key=cls.requires_key))
            created.append(name)
    db.commit()
    for pref in db.query(SearchPreference).all():
        if not pref.sources:
            # Nothing ticked reads as "everything" to the importer but shows as an empty
            # list in the UI, so a first-run row is defaulted to the registered sites.
            pref.sources = list(REGISTRY)
        elif created:
            # An owner's tick list predates a newly added site, so the site would stay
            # invisible forever. Add only free, key-free sites once, on the startup that
            # creates them; sites removed by the owner afterwards stay removed, and a
            # key-gated source waits until the owner ticks it.
            pref.sources = [*pref.sources,
                            *[n for n in created if not REGISTRY[n].requires_key and n not in pref.sources]]
    db.commit()


def search_plan(db, pref=None, profile_id: int = 1) -> dict:
    """Show the owner's actual per-site search phrases."""
    titles, skills, locations = effective_terms(db, pref, profile_id=profile_id)
    titles, skills, locations, corrections = reconcile_terms(titles, skills, locations)
    titles, skills = _meaningful_terms(titles), _meaningful_terms(skills)
    if not titles:
        # No desired title saved: search the roles the owner actually held, which
        # is far closer to his experience than a generic fallback phrase.
        titles = role_search_titles(profile_roles(db, profile_id))
    expanded = expand_terms(titles, skills) if titles or skills else []
    terms = search_terms(titles, skills) if expanded else []
    waiting = expanded[MAX_SEARCH_TERMS:]
    where = locations[0].strip() if locations and locations[0].strip() else "Egypt"
    have_key = bool(getattr(config, "RAPIDAPI_KEY", ""))
    have_jooble = bool(getattr(config, "JOOBLE_API_KEY", ""))
    have_adzuna = bool(getattr(config, "ADZUNA_APP_ID", "")
                       and getattr(config, "ADZUNA_APP_KEY", ""))

    sites = []
    for cls in REGISTRY.values():
        if cls.name == "jsearch":
            asks = [f"{t} jobs in {where}" for t in terms]
            note = ("Asks one phrase per import and rotates through the list, so the whole set "
                    "is covered without burning the free monthly quota.")
        elif cls.name in ("jooble", "adzuna"):
            asks = [f"{t} in {where}" for t in terms]
            note = ("Asks one phrase per import and rotates through the list; the free key has "
                    "a request cap, so it is never asked more than once per import.")
        elif cls.name == "linkedin":
            asks = [f"{t} in {where}" for t in terms[: cls.MAX_TERMS]]
            note = (f"{cls.MAX_TERMS} phrases per import, 2 result pages each."
                    if len(terms) > cls.MAX_TERMS else f"{len(asks)} phrase(s), 2 result pages each.")
        elif cls.keyword_search:
            asks = list(terms)
            note = "One search request per phrase."
        else:
            asks = []
            note = ("Sends its whole live listing; only jobs matching your roles or skills are imported."
                    if titles or skills
                    else "Sends its whole live listing; every new posting there is imported.")
        sites.append({
            "name": cls.name,
            "label": cls.label,
            "mode": "keyword" if cls.keyword_search else "feed",
            "asks": asks,
            "note": note,
            "needs_key": cls.requires_key,
            "key_present": (not cls.requires_key)
                           or (have_jooble if cls.name == "jooble"
                               else have_adzuna if cls.name == "adzuna"
                               else have_key),
        })
    return {"terms": terms, "terms_waiting": waiting, "titles": titles, "skills": skills,
            "locations": locations, "where": where, "sites": sites,
            "corrections": [{"typed": c.typed, "corrected": c.corrected} for c in corrections]}


def get_enabled_providers(db, requested_sources: Iterable[str] | None = None) -> list[BaseProvider]:
    sources = db.query(JobSource).filter(JobSource.enabled.is_(True)).all()
    by_name = {s.name: s for s in sources}
    names = set(requested_sources) if requested_sources else set(by_name)
    providers = []
    for name, cls in REGISTRY.items():
        if name in names and by_name.get(name):
            providers.append(cls(by_name[name].config))
    return providers


def merge_duplicate_jobs(db) -> int:
    """Collapse jobs that represent the same posting into the oldest row.

    Repoints saved jobs, applications and generated materials before
    deleting the clones.
    """
    from ..models import Application, GeneratedMaterial, SavedJob

    groups: dict[tuple, list[Job]] = {}
    for job in db.query(Job).order_by(Job.id).all():
        key = (job.profile_id, job.source, *identity_key(job.company, job.title, job.url, job.external_id))
        groups.setdefault(key, []).append(job)

    merged = 0
    for jobs in groups.values():
        keep, clones = jobs[0], jobs[1:]
        if not clones:
            continue
        clone_ids = [j.id for j in clones]
        for model in (SavedJob, Application):
            # job_id is unique on both: when the survivor already has a row the
            # clones' rows are dropped, and when it does not, only ONE clone row
            # may be repointed — repointing two at once would violate the unique
            # constraint and crash the whole startup merge.
            if db.query(model).filter(model.job_id == keep.id).first():
                db.query(model).filter(model.job_id.in_(clone_ids)).delete(synchronize_session=False)
            else:
                rows = db.query(model).filter(model.job_id.in_(clone_ids)).all()
                for row in rows[1:]:
                    db.delete(row)
                if rows:
                    rows[0].job_id = keep.id
        db.query(GeneratedMaterial).filter(GeneratedMaterial.job_id.in_(clone_ids)).update(
            {GeneratedMaterial.job_id: keep.id}, synchronize_session=False
        )
        for clone in clones:
            db.delete(clone)
            merged += 1
        db.flush()
    if merged:
        db.commit()
    return merged


def is_dead(pj: ProviderJob, now: datetime, max_age_days: int) -> str | None:
    """Why a fetched posting should not enter the database, or None if it is live."""
    expiry = _as_utc(pj.expiry_date)
    posted = _as_utc(pj.posted_date)
    if expiry and expiry <= now:
        return "expired"
    if posted and posted < now - timedelta(days=max_age_days):
        return "old"
    return None


def ingest_jobs(db, provider_jobs: Iterable[ProviderJob], profile_id: int = 1) -> tuple[int, int]:
    """Store provider jobs with owner-scoped deduplication. Returns (new, updated)."""
    new = updated = 0
    seen_in_batch: set[tuple] = set()
    now = datetime.now(timezone.utc)
    known = {(j.source, j.external_id): j for j in db.query(Job).filter(Job.profile_id == profile_id).all()}
    identity_by_title: dict[str, list[tuple]] = {}
    for j in known.values():
        identity_by_title.setdefault((j.title or "").lower(), []).append(
            identity_key(j.company, j.title, j.url, j.external_id)
        )
    for pj in provider_jobs:
        if not pj.title or not pj.external_id:
            continue
        batch_key = (pj.source, pj.external_id)
        if batch_key in seen_in_batch:
            continue  # same provider returned the job twice in one run
        seen_in_batch.add(batch_key)
        job = known.get(batch_key)
        norm_key = identity_key(pj.company, pj.title, pj.url, pj.external_id)
        duplicate = any(k == norm_key for k in identity_by_title.get(pj.title.lower(), []))

        if job:
            job.title, job.company, job.location = pj.title, pj.company, pj.location
            job.country, job.remote = pj.country, pj.remote
            job.salary_min, job.salary_max, job.salary_currency = pj.salary_min, pj.salary_max, pj.salary_currency
            job.employment_type, job.experience_level = pj.employment_type, pj.experience_level
            job.description, job.url, job.skills = pj.description, pj.url, pj.skills
            fresh = _as_utc(pj.posted_date)
            if fresh and (job.posted_date is None or fresh < _as_utc(job.posted_date)):
                # The earliest real date wins. A board that re-advertises an old opening
                # under a fresh stamp must not be able to make it look new again, and an
                # ad we first stored undated still gets its real date when a feed tells us.
                job.posted_date = fresh
            if pj.expiry_date:
                # A feed that omits the expiry must not erase the one we already have.
                job.expiry_date = _as_utc(pj.expiry_date)
            job.last_seen = now
            job.is_active = True  # the source still advertises it
            updated += 1
            continue
        if duplicate:
            continue  # same job already known from another source
        db.add(Job(
            profile_id=profile_id,
            external_id=pj.external_id,
            source=pj.source,
            title=pj.title,
            company=pj.company,
            location=pj.location,
            country=pj.country,
            remote=pj.remote,
            salary_min=pj.salary_min,
            salary_max=pj.salary_max,
            salary_currency=pj.salary_currency,
            employment_type=pj.employment_type,
            experience_level=pj.experience_level,
            description=pj.description,
            url=pj.url,
            skills=pj.skills,
            posted_date=_as_utc(pj.posted_date),
            expiry_date=_as_utc(pj.expiry_date),
            is_demo=False,
            is_active=True,
        ))
        identity_by_title.setdefault(pj.title.lower(), []).append(norm_key)
        new += 1
    db.commit()
    return new, updated


def backfill_posting_dates(db, provider_jobs: Iterable[ProviderJob], profile_id: int = 1) -> int:
    """Hand a stored posting the real date the feed sent, so it can age out.

    An undated row is invisible to the freshness check, so it stays in the live
    lists forever even when the source has been advertising it for months.
    Only a date that is *earlier* than the stored one is adopted — a board re-stamping
    an old ad must never make it younger.
    """
    touched = 0
    for pj in provider_jobs:
        posted = _as_utc(pj.posted_date)
        if not posted:
            continue
        job = (
            db.query(Job)
            .filter(Job.profile_id == profile_id, Job.source == pj.source, Job.external_id == pj.external_id)
            .first()
        )
        if job is None or (job.posted_date and job.posted_date <= posted):
            continue
        job.posted_date = posted
        if pj.expiry_date:
            job.expiry_date = _as_utc(pj.expiry_date)
        touched += 1
    if touched:
        db.commit()
    return touched


def hide_stale_jobs(db, max_age_days: int, profile_id: int | None = 1) -> int:
    """Flag stored postings that have aged out (or passed their feed's expiry).

    They stay in the database so saved jobs and application history keep working,
    but they leave the default lists because they are no longer real openings.

    Feeds that send no date at all are judged by `last_seen` instead: an ad the board
    still advertises this week is a live opening even though nobody knows when it was
    posted, while one no source has repeated for a month is gone.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=max_age_days)
    stale = db.query(Job).filter(
        Job.is_active.is_(True),
        or_(
            and_(Job.posted_date.isnot(None), Job.posted_date < cutoff),
            and_(Job.posted_date.is_(None), Job.last_seen < cutoff),
            and_(Job.expiry_date.isnot(None), Job.expiry_date <= now),
        ),
    )
    if profile_id is not None:
        stale = stale.filter(Job.profile_id == profile_id)
    count = stale.count()
    stale.update({Job.is_active: False}, synchronize_session=False)
    db.commit()
    return count


def _error_summary(errors: tuple[str, ...]) -> str:
    """Turn the pages a site failed to answer into one readable phrase for the run log."""
    unique = list(dict.fromkeys(errors))
    return ", ".join(unique[:3]) + (f" and {len(unique) - 3} more" if len(unique) > 3 else "")


def _fetch_providers(providers: list[BaseProvider], titles: list[str], skills: list[str],
                     locations: list[str], remote_only: bool,
                     fresh: bool) -> Iterator[tuple[list, Exception | None, tuple[str, ...]]]:
    """Start every site at once, then hand out (jobs, error, pages-not-read) per provider, in order.

    The sites are unrelated servers, so fetching them one after another made a full
    import cost the sum of their latencies. The answers arrive as a lazy stream instead
    of a finished batch: the slowest site keeps running in the background while the
    caller ingests the sites that already answered, so its wait is paid once, not twice.
    Ingesting stays sequential and in that same order, because the order is what decides
    which site owns a posting two of them carry. Each fetch runs in its own copy of the
    context so one site's cache window cannot leak into the next one's.
    """

    def call(provider: BaseProvider):
        _fetch_errors.set(())
        set_fetch_policy(provider.fetch_ttl, fresh and not provider.keep_cache_window)
        try:
            return provider.fetch(titles, skills, locations, remote_only), None, _fetch_errors.get()
        except Exception as exc:  # noqa: BLE001 - reported per site, never fatal
            return [], exc, _fetch_errors.get()

    if len(providers) <= 1:
        for provider in providers:
            yield call(provider)
        return
    pool = ThreadPoolExecutor(max_workers=min(SITES_IN_FLIGHT, len(providers)))
    try:
        futures = [pool.submit(contextvars.copy_context().run, call, p) for p in providers]
        yield from (f.result() for f in futures)
    finally:
        pool.shutdown(wait=True)


def run_discovery(db, titles: list[str], skills: list[str], locations: list[str],
                  remote_only: bool, sources: list[str] | None = None,
                  max_age_days: int = DEFAULT_JOB_MAX_AGE_DAYS,
                  on_progress=None, profile_id: int = 1, fresh: bool = False) -> tuple[int, list[str]]:
    """Run all enabled providers, ingest results. Returns (total_new, log lines).

    `on_progress(done, total, name, label, line)` fires after every provider finishes,
    so a streaming endpoint can report real per-site progress to the UI.
    `fresh` is a manual import: it re-reads each site's live feed instead of the
    window's cached copy, so a posting published minutes ago is caught on this click.
    """
    roles = profile_roles(db, profile_id)
    roles_as_titles = role_search_titles(roles)
    titles, skills, locations, corrections = reconcile_terms(titles, skills, locations)
    titles, skills = _meaningful_terms(titles), _meaningful_terms(skills)
    if not titles and not skills:
        titles, skills, saved_locations = effective_terms(db, None, profile_id=profile_id)
        titles, skills, saved_locations, extra = reconcile_terms(titles, skills, saved_locations)
        corrections += extra
        titles, skills = _meaningful_terms(titles), _meaningful_terms(skills)
        locations = locations or saved_locations
    if not titles and not skills and not roles_as_titles:
        raise ValueError(EMPTY_SEARCH_ERROR)
    # No desired title saved: ask for the roles the owner actually held instead of
    # a generic phrase, and keep the gate rooted in the same real experience.
    search_titles = titles or roles_as_titles
    matches = build_gate(search_titles, skills, roles)
    providers = get_enabled_providers(db, sources or None)
    log_lines = []
    if corrections:
        seen: set[tuple[str, str]] = set()
        pairs = []
        for c in corrections:
            key = (c.typed.casefold(), c.corrected.casefold())
            if key not in seen:
                seen.add(key)
                pairs.append(f"'{c.typed}' -> {c.corrected}")
        shown = pairs[:5]
        more = f" (and {len(pairs) - 5} more)" if len(pairs) > 5 else ""
        log_lines.append(
            "Spelling check: " + ", ".join(shown) + more
            + ". The search uses the corrected term; the text you saved is unchanged."
        )
    total_new = 0
    now = datetime.now(timezone.utc)
    answers = _fetch_providers(providers, search_titles, skills, locations, remote_only, fresh)
    for done, (provider, (found, failure, page_errors)) in enumerate(zip(providers, answers), start=1):
        try:
            if failure is not None:
                raise failure
            live: list[ProviderJob] = []
            dead: list[ProviderJob] = []
            unrelated = fetched = 0
            for pj in found:
                fetched += 1
                if matches is not None and not matches(pj):
                    unrelated += 1
                    continue
                (dead if is_dead(pj, now, max_age_days) else live).append(pj)
            new, updated = ingest_jobs(db, live, profile_id=profile_id)
            dated = backfill_posting_dates(db, dead, profile_id=profile_id)
            total_new += new
            # A site that answered nothing because nothing loaded is not a site with no
            # news for him; say which one failed rather than let it look empty.
            if fetched == 0 and page_errors:
                line = f"{provider.label}: could not be read ({_error_summary(page_errors)})"
            else:
                line = f"{provider.label}: fetched {fetched}, {new} new, {updated} updated"
                if page_errors:
                    line += f" (partly read: {_error_summary(page_errors)})"
                if unrelated:
                    line += f", {unrelated} skipped as unrelated to your roles or skills"
                if dead:
                    line += f", {len(dead)} skipped as no longer live"
                if dated:
                    line += f" ({dated} of them dated so they age out of your lists)"
            log_lines.append(line)
        except Exception as exc:  # noqa: BLE001
            db.rollback()  # a failed provider must not poison the shared session
            log.exception("Provider %s failed", provider.name)
            line = f"{provider.label}: ERROR - {type(exc).__name__}: {exc}"
            log_lines.append(line)
        if on_progress is not None:
            on_progress(done, len(providers), provider.name, provider.label, line)
    set_fetch_policy(FETCH_CACHE_TTL_SECONDS, False)
    hidden = hide_stale_jobs(db, max_age_days, profile_id=profile_id)
    if hidden:
        log_lines.append(
            f"Freshness check: {hidden} older job posting{'' if hidden == 1 else 's'} hidden because they are past "
            f"{max_age_days} days or expired at the source."
        )
    return total_new, log_lines
