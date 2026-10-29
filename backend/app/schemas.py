from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .models import DEFAULT_JOB_MAX_AGE_DAYS

# ---------- Profile ----------


class SkillIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    level: int = Field(ge=1, le=5, default=3)
    years: float | None = Field(default=None, ge=0, le=60)


class SkillOut(SkillIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


class ExperienceIn(BaseModel):
    title: str = ""
    company: str = ""
    location: str = ""
    start_date: str | None = None
    end_date: str | None = None
    current: bool = False
    description: str = ""


class ExperienceOut(ExperienceIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


class EducationIn(BaseModel):
    degree: str = ""
    institution: str = ""
    field: str = ""
    start_date: str | None = None
    end_date: str | None = None
    description: str = ""


class EducationOut(EducationIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


class ProjectIn(BaseModel):
    name: str = ""
    description: str = ""
    url: str = ""
    technologies: list[str] = []


class ProjectOut(ProjectIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


class ProfileIn(BaseModel):
    full_name: str = Field(default="", max_length=200)
    email: str = Field(default="", max_length=300)
    phone: str = Field(default="", max_length=50)
    country: str = Field(default="Egypt", max_length=100)
    city: str = Field(default="", max_length=100)
    linkedin: str = Field(default="", max_length=300)
    github: str = Field(default="", max_length=300)
    portfolio: str = Field(default="", max_length=300)
    summary: str = Field(default="", max_length=20000)
    desired_titles: list[str] = Field(default_factory=list, max_length=50)
    preferred_locations: list[str] = Field(default_factory=list, max_length=50)
    remote_preference: Literal["remote", "onsite", "hybrid", "open"] = "open"
    work_types: list[str] = Field(default_factory=list, max_length=20)
    min_salary: int | None = Field(default=None, ge=0)
    salary_currency: str = Field(default="USD", max_length=10)
    languages: list[str] = Field(default_factory=list, max_length=30)
    target_levels: list[str] = Field(default_factory=list, max_length=20)


class ProfileOut(ProfileIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    resume_filename: str | None = None
    resume_text: str | None = None
    updated_at: datetime
    skills: list[SkillOut] = []
    experiences: list[ExperienceOut] = []
    education: list[EducationOut] = []
    projects: list[ProjectOut] = []


class ResumeAutofillOut(BaseModel):
    """What the CV parser found; nothing here has been saved yet."""

    fields: dict[str, str] = {}
    skills: list[str] = []
    experiences: list[ExperienceIn] = []
    education: list[EducationIn] = []
    resume_chars: int = 0


class ResumeAutofillApply(BaseModel):
    fields: dict[str, str] = {}
    skills: list[str] = Field(default_factory=list, max_length=100)
    experiences: list[ExperienceIn] = Field(default_factory=list, max_length=50)
    education: list[EducationIn] = Field(default_factory=list, max_length=50)


# ---------- Jobs ----------


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    external_id: str
    source: str
    title: str
    company: str
    location: str
    country: str
    remote: bool
    salary_min: int | None
    salary_max: int | None
    salary_currency: str | None
    employment_type: str
    experience_level: str
    description: str
    url: str
    skills: list[str]
    posted_date: datetime | None
    expiry_date: datetime | None
    first_seen: datetime
    last_seen: datetime
    date_kind: str = "posted"
    publisher: str = ""
    apply_emails: list[str] = []
    apply_links: list[str] = []
    apply_channel: str = "listing"
    apply_note: str = ""
    is_demo: bool
    is_active: bool = True
    saved: bool = False
    application_status: str | None = None
    application_id: int | None = None
    application_docs: int = 0


class JobLite(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    company: str
    location: str


class JobPage(BaseModel):
    items: list[JobOut]
    total: int
    page: int
    page_size: int
    pages: int


class SavedJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    notes: str
    saved_at: datetime
    job: JobOut
    score: int | None = None


# ---------- Applications ----------

STATUSES = ["Discovered", "Interested", "Preparing", "Applied", "Interview", "Offer", "Rejected", "Archived"]


class ApplicationIn(BaseModel):
    job_id: int
    status: str = "Discovered"
    date_applied: datetime | None = None
    follow_up_date: datetime | None = None
    interview_date: datetime | None = None
    notes: str = ""


class ApplicationUpdate(BaseModel):
    status: str | None = None
    date_applied: datetime | None = None
    follow_up_date: datetime | None = None
    interview_date: datetime | None = None
    notes: str | None = None


class ApplicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    status: str
    date_discovered: datetime
    date_applied: datetime | None
    follow_up_date: datetime | None
    interview_date: datetime | None
    notes: str
    updated_at: datetime
    job: JobOut
    materials_count: int = 0


# ---------- Matching ----------


class MatchFactor(BaseModel):
    label: str
    detail: str
    weight: float
    score: float


class MatchResult(BaseModel):
    job_id: int
    score: int
    estimate: bool = True
    matched_skills: list[str] = []
    missing_skills: list[str] = []
    factors: list[MatchFactor] = []
    why_match: str = ""
    concerns: str = ""
    next_steps: list[str] = []
    hard_gap: str = ""
    ai_enhanced: bool = False
    # The model's prose is being written off the request path; ask again shortly.
    narrative_pending: bool = False


# ---------- Assistant ----------

GENERATION_KINDS = ["summary", "bullets", "cover_letter", "email", "questions", "keywords", "cv"]


class GenerationRequest(BaseModel):
    job_id: int
    kind: Literal["summary", "bullets", "cover_letter", "email", "questions", "keywords", "cv"]
    extra_notes: str = ""


class GenerationResult(BaseModel):
    kind: str
    content: str
    template_based: bool = False
    warning: str = ""


class PreparedMaterial(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    kind: str
    content: str
    template_based: bool
    created_at: datetime


class PrepareIn(BaseModel):
    job_id: int
    notes: str = ""


class PreparedApplication(BaseModel):
    """One click of preparation: the tracker row, the documents, and how to apply."""
    application: "ApplicationOut"
    materials: list[PreparedMaterial]
    apply_emails: list[str] = []
    apply_links: list[str] = []
    apply_channel: str = "listing"
    apply_note: str = ""


# ---------- Dashboard ----------


class StatusCount(BaseModel):
    status: str
    count: int


class DashboardStats(BaseModel):
    total_jobs: int
    stale_hidden_jobs: int = 0
    high_match_jobs: int
    saved_jobs: int
    applications: int
    interviews: int
    offers: int
    status_breakdown: list[StatusCount]
    recent_jobs: list[JobOut]
    best_matches: list[dict]
    upcoming_follow_ups: list[ApplicationOut]
    profile_complete: bool


# ---------- Automation ----------


class SearchPreferenceIn(BaseModel):
    enabled: bool = False
    titles: list[str] = []
    skills: list[str] = []
    extra_terms: list[str] = []
    locations: list[str] = []
    remote_only: bool = False
    interval_minutes: int = Field(default=360, ge=5, le=10080)
    min_match_score: int = Field(default=50, ge=0, le=100)
    max_age_days: int = Field(default=DEFAULT_JOB_MAX_AGE_DAYS, ge=3, le=180)
    sources: list[str] = []


class SearchPreferenceOut(SearchPreferenceIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    scheduler_running: bool = False


class SearchPlanSite(BaseModel):
    name: str
    label: str
    mode: str  # keyword | feed
    asks: list[str]
    note: str = ""
    needs_key: bool
    key_present: bool


class TermCorrection(BaseModel):
    typed: str
    corrected: str


class SearchPlanOut(BaseModel):
    terms: list[str]
    terms_waiting: list[str]
    titles: list[str]
    skills: list[str]
    locations: list[str]
    where: str
    sites: list[SearchPlanSite]
    corrections: list[TermCorrection] = []


class TermSuggestIn(BaseModel):
    titles: list[str] = Field(default_factory=list, max_length=100)
    skills: list[str] = Field(default_factory=list, max_length=100)
    locations: list[str] = Field(default_factory=list, max_length=50)


class TermSuggestion(BaseModel):
    term: str
    suggestion: str
    kind: str  # title | skill | location


class AutomationRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    trigger: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    jobs_found: int
    sources_used: list[str]
    error: str
    log: str


class RunResult(BaseModel):
    run_id: int
    status: str
    jobs_found: int
    log: str


class HealthOut(BaseModel):
    status: str
    openai_configured: bool
    demo_mode: bool
