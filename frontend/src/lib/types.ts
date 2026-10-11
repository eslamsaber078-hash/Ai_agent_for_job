export interface Skill {
  id?: number;
  name: string;
  level: number;
  years?: number | null;
}

export interface Experience {
  id?: number;
  title: string;
  company: string;
  location: string;
  start_date: string | null;
  end_date: string | null;
  current: boolean;
  description: string;
}

export interface EducationItem {
  id?: number;
  degree: string;
  institution: string;
  field: string;
  start_date: string | null;
  end_date: string | null;
  description: string;
}

export interface Project {
  id?: number;
  name: string;
  description: string;
  url: string;
  technologies: string[];
}

export interface Profile {
  id: number;
  full_name: string;
  email: string;
  phone: string;
  country: string;
  city: string;
  linkedin: string;
  github: string;
  portfolio: string;
  summary: string;
  desired_titles: string[];
  preferred_locations: string[];
  remote_preference: string;
  work_types: string[];
  min_salary: number | null;
  salary_currency: string;
  languages: string[];
  target_levels: string[];
  resume_filename: string | null;
  resume_text: string | null;
  updated_at: string;
  skills: Skill[];
  experiences: Experience[];
  education: EducationItem[];
  projects: Project[];
}

export interface Job {
  id: number;
  external_id: string;
  source: string;
  title: string;
  company: string;
  location: string;
  country: string;
  remote: boolean;
  salary_min: number | null;
  salary_max: number | null;
  salary_currency: string | null;
  employment_type: string;
  experience_level: string;
  description: string;
  url: string;
  skills: string[];
  posted_date: string | null;
  expiry_date: string | null;
  first_seen: string;
  last_seen: string;
  is_demo: boolean;
  is_active: boolean;
  saved: boolean;
  application_status: string | null;
}

/** One importable job site, as reported by GET /api/jobs/sources. */
export interface JobSourceSite {
  name: string;
  label: string;
  enabled: boolean;
  requires_key: boolean;
  live_jobs: number;
}

export const SOURCE_LABELS: Record<string, string> = {
  remotive: "Remotive",
  remoteok: "Remote OK",
  jobicy: "Jobicy",
  arbeitnow: "Arbeitnow",
  weworkremotely: "We Work Remotely",
  himalayas: "Himalayas",
  workingnomads: "Working Nomads",
};

export function sourceLabel(source: string): string {
  return SOURCE_LABELS[source] ?? source;
}

export interface JobPage {
  items: Job[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface SavedJob {
  id: number;
  notes: string;
  saved_at: string;
  job: Job;
  score: number | null;
}

export interface Application {
  id: number;
  status: string;
  date_discovered: string;
  date_applied: string | null;
  follow_up_date: string | null;
  interview_date: string | null;
  notes: string;
  updated_at: string;
  job: Job;
}

export interface MatchFactor {
  label: string;
  detail: string;
  weight: number;
  score: number;
}

export interface MatchResult {
  job_id: number;
  score: number;
  estimate: boolean;
  matched_skills: string[];
  missing_skills: string[];
  factors: MatchFactor[];
  why_match: string;
  concerns: string;
  next_steps: string[];
  ai_enhanced: boolean;
  job?: {
    id: number;
    title: string;
    company: string;
    location: string;
    country: string;
    remote: boolean;
    source: string;
    experience_level: string;
    salary_min: number | null;
    salary_max: number | null;
    salary_currency: string | null;
    is_demo: boolean;
    posted_date?: string | null;
  };
}

export interface MatchList {
  items: MatchResult[];
  total: number;
  profile_empty: boolean;
}

export interface GenerationResult {
  kind: string;
  content: string;
  template_based: boolean;
  warning: string;
}

export interface StatusCount {
  status: string;
  count: number;
}

export interface DashboardStats {
  total_jobs: number;
  stale_hidden_jobs: number;
  high_match_jobs: number;
  saved_jobs: number;
  applications: number;
  interviews: number;
  offers: number;
  status_breakdown: StatusCount[];
  recent_jobs: Job[];
  best_matches: {
    job_id: number;
    title: string;
    company: string;
    location: string;
    remote: boolean;
    score: number;
    missing_skills: string[];
  }[];
  upcoming_follow_ups: Application[];
  profile_complete: boolean;
}

export interface SearchPrefs {
  id: number;
  enabled: boolean;
  titles: string[];
  skills: string[];
  locations: string[];
  remote_only: boolean;
  interval_minutes: number;
  min_match_score: number;
  max_age_days: number;
  sources: string[];
  scheduler_running: boolean;
}

export interface AutomationRun {
  id: number;
  trigger: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  jobs_found: number;
  sources_used: string[];
  error: string;
  log: string;
}

export const APP_STATUSES = [
  "Discovered",
  "Interested",
  "Preparing",
  "Applied",
  "Interview",
  "Offer",
  "Rejected",
  "Archived",
] as const;

export const GENERATION_KINDS = [
  { value: "summary", label: "Resume Summary" },
  { value: "bullets", label: "Resume Bullets" },
  { value: "cover_letter", label: "Cover Letter" },
  { value: "email", label: "Application Email" },
  { value: "questions", label: "Interview Questions" },
  { value: "keywords", label: "Keywords" },
] as const;
