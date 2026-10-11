"""Job discovery providers.

Modular architecture: each provider implements fetch() and returns normalized
ProviderJob records. Ingest logic deduplicates and stores them in the database.

Freshness rule: a posting is only useful while it is still advertised. Discovery
therefore skips postings older than the user's age cutoff and postings whose feed
carries an expiry timestamp in the past, and it flags stored jobs that have aged
out so they leave the default lists.
"""
from __future__ import annotations

import logging
import re
import time
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from typing import Iterable

import httpx
from sqlalchemy import and_, func, or_

from ..models import DEFAULT_JOB_MAX_AGE_DAYS, Job, JobSource

log = logging.getLogger("jobhunter.providers")

REMOTIVE_API = "https://remotive.com/api/remote-jobs"
REMOTEOK_API = "https://remoteok.com/api"
JOBICY_API = "https://jobicy.com/api/v2/remote-jobs"
ARBEITNOW_API = "https://www.arbeitnow.com/api/job-board-api"
WWR_RSS = "https://weworkremotely.com/remote-jobs.rss"
HIMALAYAS_API = "https://himalayas.app/jobs/api"
WORKING_NOMADS_API = "https://www.workingnomads.com/api/exposed_jobs/"

# Free public APIs must not be hammered: one GET per provider per TTL window,
# no matter how often the user presses Refresh.
FETCH_CACHE_TTL_SECONDS = 600

_fetch_cache: dict[str, tuple[float, object]] = {}


def clear_fetch_cache() -> None:
    _fetch_cache.clear()


def _cached_fetch(key: str, url: str, *, params: dict | None = None,
                  timeout: float = 25.0, as_json: bool = True):
    """GET a public feed with a per-provider TTL cache; failures return None, never raise."""
    now = time.monotonic()
    hit = _fetch_cache.get(key)
    if hit and now - hit[0] < FETCH_CACHE_TTL_SECONDS:
        return hit[1]
    try:
        resp = httpx.get(url, params=params, timeout=timeout,
                         headers={"User-Agent": "jobhunter/1.0 (personal job search assistant)"})
        resp.raise_for_status()
        data = resp.json() if as_json else resp.text
    except Exception as exc:  # noqa: BLE001 - providers must never crash the pipeline
        log.warning("%s fetch failed: %s", key, exc)
        return None
    _fetch_cache[key] = (now, data)
    return data


def _cached_get_json(key: str, url: str, *, params: dict | None = None, timeout: float = 25.0):
    return _cached_fetch(key, url, params=params, timeout=timeout, as_json=True)


def _cached_get_text(key: str, url: str, *, params: dict | None = None, timeout: float = 25.0):
    return _cached_fetch(key, url, params=params, timeout=timeout, as_json=False)


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

    def __init__(self, config: dict | None = None):
        self.config = config or {}

    @abstractmethod
    def fetch(self, titles: list[str], skills: list[str], locations: list[str],
              remote_only: bool) -> list[ProviderJob]:
        ...


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


def identity_key(company: str, title: str, url: str, external_id: str) -> tuple:
    """Source-independent identity: the same posting on two boards shares this key."""
    return (_normalize(company), _normalize(title), _normalize(url) or external_id)


class RemotiveProvider(BaseProvider):
    """Real jobs from the public Remotive API (no key required).

    Fails gracefully: network or API errors are logged and skipped,
    never raising to the caller.
    """

    name = "remotive"
    label = "Remotive (real remote jobs, free API)"

    def fetch(self, titles, skills, locations, remote_only):
        queries = [t for t in (titles + skills) if t.strip()]
        search = " ".join(queries[:3]) if queries else "software developer"
        data = _cached_get_json(f"remotive:{search}", REMOTIVE_API, params={"search": search, "limit": 50})
        if not isinstance(data, dict):
            return []

        jobs: list[ProviderJob] = []
        for item in data.get("jobs", [])[:50]:
            jobs.append(ProviderJob(
                source="remotive",
                external_id=str(item.get("id") or _normalize(f"{item.get('title')}{item.get('company_name')}")),
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
        return jobs


class RemoteOKProvider(BaseProvider):
    """Real remote jobs from the public RemoteOK API (no key required).

    The feed is one JSON array whose first element is a legal notice. Returns
    the newest N jobs only, so a refresh never floods the local database.
    """

    name = "remoteok"
    label = "Remote OK (real remote jobs, free API)"
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
                    title=str(item.get("title") or "")[:300],
                    company=item.get("companyName", ""),
                    location=", ".join(restrictions) or "Remote",
                    country=", ".join(restrictions[:1]) or "Remote",
                    remote=True,
                    salary_min=_int_or_none(item.get("minSalary")),
                    salary_max=_int_or_none(item.get("maxSalary")),
                    salary_currency=(item.get("currency") or None),
                    employment_type=item.get("employmentType", "") or "",
                    experience_level=", ".join(str(s) for s in (item.get("seniority") or [])),
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


def _split_wwr_title(raw_title: str) -> tuple[str, str]:
    """WWR titles read "Company: Job title" — keep both halves as their own fields."""
    company, _, title = raw_title.partition(":")
    if title.strip() and len(company.strip()) <= 60:
        return company.strip(), title.strip()
    return "", raw_title


def _strip_html(markup: str) -> str:
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", markup or ""))).strip()


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
    except (TypeError, ValueError):
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
    except (TypeError, ValueError, OSError):
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


def _parse_timestamp(value) -> datetime | None:
    """Feeds disagree: RemoteOK sends an ISO string, Arbeitnow an epoch integer."""
    if value is None or value == "":
        return None
    try:
        return _parse_epoch(value) or _parse_date(value)
    except (TypeError, ValueError):
        return None


REGISTRY: dict[str, type[BaseProvider]] = {
    RemotiveProvider.name: RemotiveProvider,
    RemoteOKProvider.name: RemoteOKProvider,
    JobicyProvider.name: JobicyProvider,
    ArbeitnowProvider.name: ArbeitnowProvider,
    WeWorkRemotelyProvider.name: WeWorkRemotelyProvider,
    HimalayasProvider.name: HimalayasProvider,
    WorkingNomadsProvider.name: WorkingNomadsProvider,
}


def ensure_sources(db) -> None:
    for name, cls in REGISTRY.items():
        if not db.query(JobSource).filter(JobSource.name == name).first():
            db.add(JobSource(name=name, label=cls.label, enabled=True, requires_key=cls.requires_key))
    db.commit()


def ensure_default_sources(db) -> None:
    """A first-run preference row has no sources ticked; default it to the registered ones."""
    from ..models import SearchPreference

    pref = db.get(SearchPreference, 1)
    if pref is not None and not pref.sources:
        pref.sources = [s.name for s in db.query(JobSource).filter(JobSource.enabled.is_(True)).all()]
        db.commit()


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
        key = (job.source, *identity_key(job.company, job.title, job.url, job.external_id))
        groups.setdefault(key, []).append(job)

    merged = 0
    for jobs in groups.values():
        keep, clones = jobs[0], jobs[1:]
        if not clones:
            continue
        clone_ids = [j.id for j in clones]
        for model in (SavedJob, Application, GeneratedMaterial):
            # job_id is unique on SavedJob/Application: keep the survivor's row,
            # drop the clone's instead of repointing onto a row that already exists.
            if model is not GeneratedMaterial and db.query(model).filter(model.job_id == keep.id).first():
                db.query(model).filter(model.job_id.in_(clone_ids)).delete(synchronize_session=False)
            else:
                db.query(model).filter(model.job_id.in_(clone_ids)).update(
                    {model.job_id: keep.id}, synchronize_session=False
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


def ingest_jobs(db, provider_jobs: Iterable[ProviderJob]) -> tuple[int, int]:
    """Store provider jobs with deduplication. Returns (new, updated)."""
    new = updated = 0
    seen_in_batch: set[tuple] = set()
    now = datetime.now(timezone.utc)
    for pj in provider_jobs:
        if not pj.title or not pj.external_id:
            continue
        batch_key = (pj.source, pj.external_id)
        if batch_key in seen_in_batch:
            continue  # same provider returned the job twice in one run
        seen_in_batch.add(batch_key)
        job = (
            db.query(Job)
            .filter(Job.source == pj.source, Job.external_id == pj.external_id)
            .first()
        )
        norm_key = identity_key(pj.company, pj.title, pj.url, pj.external_id)
        candidates = (
            db.query(Job)
            .filter(Job.source != pj.source, func.lower(Job.title) == pj.title.lower())
            .all()
        )
        duplicate = any(
            identity_key(j.company, j.title, j.url, j.external_id) == norm_key
            for j in candidates
        )

        if job:
            job.title, job.company, job.location = pj.title, pj.company, pj.location
            job.country, job.remote = pj.country, pj.remote
            job.salary_min, job.salary_max, job.salary_currency = pj.salary_min, pj.salary_max, pj.salary_currency
            job.employment_type, job.experience_level = pj.employment_type, pj.experience_level
            job.description, job.url, job.skills = pj.description, pj.url, pj.skills
            if pj.posted_date:
                job.posted_date = pj.posted_date
            elif job.posted_date is None:
                # First time we saw an ad from a dateless feed: date it now so the
                # freshness rule can retire it later instead of keeping it live forever.
                job.posted_date = now
            job.expiry_date = pj.expiry_date
            job.last_seen = now
            job.is_active = True  # the source still advertises it
            updated += 1
            continue
        if duplicate:
            continue  # same job already known from another source
        db.add(Job(
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
            posted_date=pj.posted_date or now,
            expiry_date=pj.expiry_date,
            is_demo=False,
            is_active=True,
        ))
        new += 1
    db.commit()
    return new, updated


def backfill_posting_dates(db, provider_jobs: Iterable[ProviderJob]) -> int:
    """Hand a stored posting the real date the feed sent, so it can age out.

    An undated row is invisible to the freshness check, so it stays in the live
    lists forever even when the source has been advertising it for months.
    """
    touched = 0
    for pj in provider_jobs:
        posted = _as_utc(pj.posted_date)
        if not posted:
            continue
        job = (
            db.query(Job)
            .filter(Job.source == pj.source, Job.external_id == pj.external_id)
            .first()
        )
        if job is None or (job.posted_date and job.posted_date == posted):
            continue
        job.posted_date = posted
        if pj.expiry_date:
            job.expiry_date = _as_utc(pj.expiry_date)
        touched += 1
    if touched:
        db.commit()
    return touched


def hide_stale_jobs(db, max_age_days: int) -> int:
    """Flag stored postings that have aged out (or passed their feed's expiry).

    They stay in the database so saved jobs and application history keep working,
    but they leave the default lists because they are no longer real openings.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=max_age_days)
    stale = db.query(Job).filter(
        Job.is_active.is_(True),
        or_(
            and_(Job.posted_date.isnot(None), Job.posted_date < cutoff),
            and_(Job.expiry_date.isnot(None), Job.expiry_date <= now),
        ),
    )
    count = stale.count()
    stale.update({Job.is_active: False}, synchronize_session=False)
    db.commit()
    return count


def run_discovery(db, titles: list[str], skills: list[str], locations: list[str],
                  remote_only: bool, sources: list[str] | None = None,
                  max_age_days: int = DEFAULT_JOB_MAX_AGE_DAYS) -> tuple[int, list[str]]:
    """Run all enabled providers, ingest results. Returns (total_new, log lines)."""
    providers = get_enabled_providers(db, sources or None)
    log_lines = []
    total_new = 0
    now = datetime.now(timezone.utc)
    for provider in providers:
        try:
            live: list[ProviderJob] = []
            dead: list[ProviderJob] = []
            for pj in provider.fetch(titles, skills, locations, remote_only):
                (dead if is_dead(pj, now, max_age_days) else live).append(pj)
            new, updated = ingest_jobs(db, live)
            dated = backfill_posting_dates(db, dead)
            total_new += new
            line = f"{provider.label}: fetched {len(live) + len(dead)}, {new} new, {updated} updated"
            if dead:
                line += f", {len(dead)} skipped as no longer live"
            if dated:
                line += f" ({dated} of them dated so they age out of your lists)"
            log_lines.append(line)
        except Exception as exc:  # noqa: BLE001
            db.rollback()  # a failed provider must not poison the shared session
            log.exception("Provider %s failed", provider.name)
            log_lines.append(f"{provider.label}: ERROR - {type(exc).__name__}: {exc}")
    hidden = hide_stale_jobs(db, max_age_days)
    if hidden:
        log_lines.append(
            f"Freshness check: {hidden} older job posting(s) hidden because they are past "
            f"{max_age_days} days or expired at the source."
        )
    return total_new, log_lines
