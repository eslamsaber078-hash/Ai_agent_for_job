from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, TypeDecorator, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator):
    """Store naive UTC (SQLite has no timezone column type) but always hand back aware UTC.

    Without this the API emits timestamps with no offset, the browser reads them as
    local wall-clock time (Cairo is UTC+3) and every posting looks 3 hours older than it is.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is not None:
            value = value.astimezone(timezone.utc)
        return value.replace(tzinfo=None)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc)


# Postings older than this are treated as closed ads, not live openings.
DEFAULT_JOB_MAX_AGE_DAYS = 30


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(200), default="")
    email: Mapped[str] = mapped_column(String(200), default="")
    phone: Mapped[str] = mapped_column(String(50), default="")
    country: Mapped[str] = mapped_column(String(100), default="Egypt")
    city: Mapped[str] = mapped_column(String(100), default="")
    linkedin: Mapped[str] = mapped_column(String(300), default="")
    github: Mapped[str] = mapped_column(String(300), default="")
    portfolio: Mapped[str] = mapped_column(String(300), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    desired_titles: Mapped[list] = mapped_column(JSON, default=list)
    preferred_locations: Mapped[list] = mapped_column(JSON, default=list)
    remote_preference: Mapped[str] = mapped_column(String(30), default="open")  # remote | onsite | hybrid | open
    work_types: Mapped[list] = mapped_column(JSON, default=list)  # full-time, part-time, internship, contract
    min_salary: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_currency: Mapped[str] = mapped_column(String(10), default="USD")
    languages: Mapped[list] = mapped_column(JSON, default=list)
    target_levels: Mapped[list] = mapped_column(JSON, default=list)  # intern, junior, entry, mid
    resume_filename: Mapped[str | None] = mapped_column(String(300), nullable=True)
    resume_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)

    skills: Mapped[list["Skill"]] = relationship(back_populates="profile", cascade="all, delete-orphan")
    experiences: Mapped[list["WorkExperience"]] = relationship(back_populates="profile", cascade="all, delete-orphan")
    education: Mapped[list["Education"]] = relationship(back_populates="profile", cascade="all, delete-orphan")
    projects: Mapped[list["Project"]] = relationship(back_populates="profile", cascade="all, delete-orphan")


class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("user_profiles.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100))
    level: Mapped[int] = mapped_column(Integer, default=3)  # 1 beginner .. 5 expert
    years: Mapped[float | None] = mapped_column(Float, nullable=True)

    profile: Mapped["UserProfile"] = relationship(back_populates="skills")


class WorkExperience(Base):
    __tablename__ = "work_experiences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("user_profiles.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(200), default="")
    company: Mapped[str] = mapped_column(String(200), default="")
    location: Mapped[str] = mapped_column(String(200), default="")
    start_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    end_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    current: Mapped[bool] = mapped_column(Boolean, default=False)
    description: Mapped[str] = mapped_column(Text, default="")

    profile: Mapped["UserProfile"] = relationship(back_populates="experiences")


class Education(Base):
    __tablename__ = "education"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("user_profiles.id", ondelete="CASCADE"))
    degree: Mapped[str] = mapped_column(String(200), default="")
    institution: Mapped[str] = mapped_column(String(200), default="")
    field: Mapped[str] = mapped_column(String(200), default="")
    start_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    end_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    description: Mapped[str] = mapped_column(Text, default="")

    profile: Mapped["UserProfile"] = relationship(back_populates="education")


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("user_profiles.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str] = mapped_column(String(300), default="")
    technologies: Mapped[list] = mapped_column(JSON, default=list)

    profile: Mapped["UserProfile"] = relationship(back_populates="projects")


# Feeds whose timestamp is the crawl, not the company: their newest page always reads
# "today", so the date they send says when the board listed the ad.
# Sources whose stamp is when the listing appeared, not when the company published the
# ad. Himalayas is here for the rows stored before its feed was distrusted: its "pubDate"
# is generated at feed-build time in 15-second steps, so those dates are ours, not the
# advertiser's, and calling them "Posted" would claim a freshness the source never said.
LISTING_STAMP_SOURCES = {"arbeitnow", "himalayas"}


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("profile_id", "source", "external_id", name="uq_job_profile_source_external"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("user_profiles.id"), default=1, index=True)
    external_id: Mapped[str] = mapped_column(String(300))
    source: Mapped[str] = mapped_column(String(100), default="")
    title: Mapped[str] = mapped_column(String(300))
    company: Mapped[str] = mapped_column(String(200), default="")
    location: Mapped[str] = mapped_column(String(200), default="")
    country: Mapped[str] = mapped_column(String(100), default="")
    remote: Mapped[bool] = mapped_column(Boolean, default=False)
    salary_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    employment_type: Mapped[str] = mapped_column(String(50), default="")
    experience_level: Mapped[str] = mapped_column(String(50), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str] = mapped_column(String(500), default="")
    skills: Mapped[list] = mapped_column(JSON, default=list)
    posted_date: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    expiry_date: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    first_seen: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    last_seen: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    @property
    def date_kind(self) -> str:
        """Which of three truths `posted_date` is, so the UI can name it correctly.

        "posted"  — the board states when the company published the ad.
        "listed"  — the stamp is when the board indexed it; Arbeitnow re-stamps every
                    page on each crawl, so such a date can never be older than today.
        "unknown" — the feed sends no date at all and `first_seen` is all we have.
        """
        if self.posted_date is None:
            return "unknown"
        return "listed" if (self.source or "").lower() in LISTING_STAMP_SOURCES else "posted"


class JobSource(Base):
    __tablename__ = "job_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    label: Mapped[str] = mapped_column(String(200), default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    requires_key: Mapped[bool] = mapped_column(Boolean, default=False)
    config: Mapped[dict] = mapped_column(JSON, default=dict)


class SavedJob(Base):
    __tablename__ = "saved_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), unique=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    saved_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    job: Mapped["Job"] = relationship()


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), unique=True)
    status: Mapped[str] = mapped_column(String(30), default="Discovered")
    date_discovered: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    date_applied: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    follow_up_date: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    interview_date: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)

    job: Mapped["Job"] = relationship()


class GeneratedMaterial(Base):
    __tablename__ = "generated_materials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    application_id: Mapped[int | None] = mapped_column(ForeignKey("applications.id", ondelete="SET NULL"), nullable=True)
    kind: Mapped[str] = mapped_column(String(50))  # summary, bullets, cover_letter, email, questions, keywords
    content: Mapped[str] = mapped_column(Text, default="")
    template_based: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    job: Mapped["Job"] = relationship()


class SearchPreference(Base):
    __tablename__ = "search_preferences"

    id: Mapped[int] = mapped_column(ForeignKey("user_profiles.id"), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    titles: Mapped[list] = mapped_column(JSON, default=list)
    skills: Mapped[list] = mapped_column(JSON, default=list)
    # Extra fields he adds himself to widen the hunt beyond his profile.
    extra_terms: Mapped[list] = mapped_column(JSON, default=list)
    locations: Mapped[list] = mapped_column(JSON, default=list)
    remote_only: Mapped[bool] = mapped_column(Boolean, default=False)
    interval_minutes: Mapped[int] = mapped_column(Integer, default=360)
    min_match_score: Mapped[int] = mapped_column(Integer, default=50)
    max_age_days: Mapped[int] = mapped_column(Integer, default=DEFAULT_JOB_MAX_AGE_DAYS)
    sources: Mapped[list] = mapped_column(JSON, default=list)


class AutomationRun(Base):
    __tablename__ = "automation_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("user_profiles.id"), default=1, index=True)
    trigger: Mapped[str] = mapped_column(String(20), default="manual")  # manual | scheduled
    status: Mapped[str] = mapped_column(String(20), default="running")  # running | success | failed
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    jobs_found: Mapped[int] = mapped_column(Integer, default=0)
    sources_used: Mapped[list] = mapped_column(JSON, default=list)
    error: Mapped[str] = mapped_column(Text, default="")
    log: Mapped[str] = mapped_column(Text, default="")


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    phone: Mapped[str] = mapped_column(String(32), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    profile_id: Mapped[int] = mapped_column(ForeignKey("user_profiles.id"), unique=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())
