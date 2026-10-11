# AI Job Hunter

A personal AI job-search agent that runs on your own machine: it discovers jobs, scores
them against your real profile, helps you write application materials, and tracks every
application you send.

Everything is local. Nothing is submitted or emailed automatically — you always copy the
text and send it yourself.

- **Backend:** FastAPI + SQLAlchemy + Pydantic + APScheduler (SQLite by default, PostgreSQL supported)
- **Frontend:** React + TypeScript + Vite + Tailwind (shadcn-style components) + Recharts + Lucide
- **Requirements tested with:** Python 3.12+ (3.14 works), Node.js 20+ (24 works)

---

## 1. Quick start on Windows

Open **PowerShell** and run the four blocks below. Do them in order.

### Block 1 — backend virtual environment

```powershell
cd "F:\AI agent Gob\backend"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

> If activation fails with an "execution policies" error, run once:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`
> Alternative activation: `.\.venv\Scripts\activate.cmd` (cmd.exe) or
> `source .venv/Scripts/activate` (Git Bash).

### Block 2 — start the backend

```powershell
cd "F:\AI agent Gob\backend"
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Leave this window open. Check it works:

- API docs: <http://127.0.0.1:8000/docs>
- Health: <http://127.0.0.1:8000/api/health> → `{"status":"ok", ...}`

On first start the app creates the database and registers the four real job
sources. Jobs are fetched from the live public APIs — nothing is pre-seeded.

> `--reload` restarts the backend when a `.py` file changes. Changes to `.env` are **not**
> picked up automatically — stop with <kbd>Ctrl</kbd>+<kbd>C</kbd> and run the command again.
> If the backend looks like it is running old behaviour, restart it the same way (a reload
> can wait while a browser tab keeps polling `/api/health`).

### Block 3 — start the frontend (new PowerShell window)

```powershell
cd "F:\AI agent Gob\frontend"
npm install
npm run dev
```

### Block 4 — open the app

<http://127.0.0.1:5173>

To stop: `Ctrl+C` in each window.

---

## 2. Configuration (environment variables)

Copy `backend/.env.example` to `backend/.env` and edit it. The backend reads that file
automatically at startup (real environment variables win over `.env`).

| Variable | Default | What it does |
| --- | --- | --- |
| `OPENAI_API_KEY` | *(empty)* | Enables real AI scoring narratives and AI-written materials. Without it the app uses built-in deterministic templates. |
| `OPENAI_MODEL` | `gpt-4o-mini` | Which OpenAI model to call. |
| `DATABASE_URL` | `sqlite:///backend/jobhunter.db` | Database location. |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Which browser origins may call the API. |
| `HOST` / `PORT` | `127.0.0.1` / `8000` | Where uvicorn listens (read by the app; still pass them on the command line too). |

Frontend override (optional): set `VITE_API_URL` in `frontend/.env` if the backend is not
on `http://127.0.0.1:8000`.

### Using OpenAI

1. Get a key from <https://platform.openai.com/api-keys>.
2. Put it in `backend/.env` as `OPENAI_API_KEY=sk-...`.
3. Restart uvicorn. `/api/health` now reports `"openai_configured": true`.

Every generated card shows a **"Template-based"** badge when the AI path was not used, so
you can always tell where the text came from.

### Using PostgreSQL instead of SQLite

```powershell
$env:DATABASE_URL = "postgresql+psycopg2://user:password@localhost:5432/jobhunter"
pip install psycopg2-binary
```

Tables are created automatically on startup.

### Resetting all data

Delete `backend/jobhunter.db` and restart the backend — the database is re-created
empty, then filled by the next refresh from the real sources.

---

## 3. Job sources

| Source | Real? | Notes |
| --- | --- | --- |
| `remotive` | **Yes** | Free public API, no key needed. Real remote jobs (searched with your own titles/skills). |
| `remoteok` | **Yes** | Free public API (remoteok.com/api), no key needed. Up to 100 newest real remote jobs. |
| `jobicy` | **Yes** | Free public API (jobicy.com), no key needed. 100 real remote jobs. |
| `arbeitnow` | **Yes** | Free public API (arbeitnow.com), no key needed. Up to 600 real jobs, mostly EU/remote. |
| `weworkremotely` | **Yes** | The site's own public RSS feed, no key needed. ~89 real remote jobs, each with a publication **and** expiry date. |
| `himalayas` | **Yes** | Free public API (himalayas.app/jobs/api), no key needed. 100 newest real remote jobs. Its `pubDate`/`expiryDate` are generated when the feed is built (each row exactly 15 s apart), so they are ignored and the posting is dated the first time we see it. |
| `workingnomads` | **Yes** | Free public feed (workingnomads.com/api/exposed_jobs), no key needed. ~54 real remote jobs with publication dates. |

Network failures are logged and skipped, never crash the search. To protect the free
APIs from being hammered, every provider GET is cached for 10 minutes: pressing Import
repeatedly re-reads the cached feed instead of hitting the API again.

### Importing one site at a time

Find Jobs has one import button per registered site, each showing how many live postings
that site has contributed. A click fetches only that site, so gathering every source never
loads one server with seven simultaneous searches. "Import from all ticked sites" runs the
sites ticked in Automation Settings. A name that is not a registered source, or an import
with **no** site ticked, is refused with a readable 422 instead of silently fetching
everything.

### Freshness: no months-old dead ads

Every fetched posting is checked before it enters the database:

- past the feed's own expiry date → skipped as `expired`;
- posted earlier than **Max job age** (Automation Settings, default 30 days) → skipped as `old`;
- postings already stored that have since aged out are flagged `is_active = false` — they
  leave Find Jobs, Matches and the Dashboard but stay linked to your saved jobs and history;
- a stored posting that arrives with a date it never had before is dated and then aged out
  the same way (an undated row is invisible to the freshness check);
- a feed that never sends a usable date is dated on first sight, so its ads still expire
  in your lists;
- a posting the source still advertises is re-activated on the next import.

Every timestamp is stored and served in UTC (the API emits a trailing `Z`), so "posted 40m
ago" means 40 minutes ago wherever you are — Cairo's clock is applied by your browser, not
guessed from a bare time string.

Undated postings are kept: absence of a date is not proof the job is gone. Every list is
ordered newest-first, and Matches breaks score ties by recency.

The UI labels which source each job came from.

### Every site you asked about, and its honest status

Each line below was checked with a real request from this machine, not from memory.
Nothing is listed as integrated unless it actually returns live jobs.

| Site | Status | Why |
| --- | --- | --- |
| Remotive | Integrated | Free JSON API, no key. |
| Remote OK | Integrated | Free JSON API, no key. |
| Jobicy | Integrated | Free JSON API, no key. |
| Arbeitnow | Integrated | Free JSON API, no key. |
| We Work Remotely | Integrated | Public RSS feed, no key. |
| Himalayas | Integrated | Free JSON API, no key. Its `categories` arrive as URL-slugs (`React-Native`), so they are re-spaced on import. |
| Working Nomads | Integrated | Free JSON feed, no key. |
| Findwork | Needs a key | `findwork.dev/api/jobs/` answers **401** — a token is issued only after sign-up. |
| USAJOBS | Needs a key + US-only | Free registration required, and it lists United States government jobs only. |
| Adzuna | Needs a key | `developer.adzuna.com` requires an `app_id` + `app_key`; no Egypt index. |
| Jooble | Needs a key | Token-based API, and the endpoint is behind a Cloudflare challenge from this network. |
| Reed | No working API | Key was always mandatory; the public job endpoints now answer **404**. UK-focused. |
| The Muse | Blocked | Documented public API, but every request from here returns **403** (CloudFront). |
| Wellfound (AngelList) | Blocked | JS single page behind a Cloudflare Turnstile challenge; no unauthenticated JSON. |
| LinkedIn Jobs | Blocked | No open job-search API; login and anti-bot protection. Link only. |
| Indeed | Blocked | Publisher API retired in 2018; the search page answers **403** to automated calls. Link only. |
| Wuzzuf | Blocked | No public API; search pages answer **403**. Link only. |
| Forasna | Blocked | No public API; automated access refused. Link only. |
| Bayt | Blocked | No public API for anonymous search; **403**. Link only. |
| Greenhouse / Lever boards | Possible, not added | Both are keyless and reliable, but only per company (`boards-api.greenhouse.io/v1/boards/<company>/jobs`, `api.lever.co/v0/postings/<company>`). There is no global search, so it would mean hard-coding a list of companies — mostly senior US/EU roles. Say the word and I will add the companies you want to target. |

For the blocked sites Find Jobs shows one-click links that open *your* search on those
sites in the browser instead of pretending to import them. To add a source,
create a class in `backend/app/services/providers.py` that extends `BaseProvider`, returns
normalized `ProviderJob` objects, and register it in `REGISTRY`. It appears in the import
bar and in Automation Settings on the next restart.

---

## 4. The eight screens

1. **Dashboard** — jobs discovered, high-match count, saved, applications, interviews,
   offers, best matches, status breakdown. All numbers are computed from the database.
2. **Find Jobs** — per-site import bar (one button per source, with its live posting
   count), search, filters (level, employment type, source, remote), sort (newest first by
   default), save, open details, "Track application", plus deep links to the Egyptian boards
   that cannot be imported.
3. **AI Job Matches** — 0–100 estimated score per job with the weighted reasons behind it
   (skills 45%, level 15%, location 15%, title 15%, salary 10%), matched vs missing skills,
   concerns and next steps. Scores are labelled *estimates*, and the same inputs always
   produce the same score.
4. **Saved Jobs** — everything you bookmarked, with score and quick actions.
5. **Applications Tracker** — table **and** Kanban views, 8 statuses (Discovered →
   Interested → Preparing → Applied → Interview → Offer → Rejected → Archived), notes,
   follow-up and interview dates, edit and delete.
6. **Resume & Profile** — profile, skills with levels, experience, education, projects, and
   resume upload (`.pdf .txt .md .doc .docx`, max 5 MB; PDF text is extracted with pypdf,
   `.docx`/`.txt`/`.md` with the stdlib; legacy `.doc` is stored as a reference only;
   files are stored, never executed). **This page is the source of truth** — the AI only
   rephrases what is stored here and never invents experience.
7. **AI Application Assistant** — resume summary, tailored bullet points, cover letter,
   application email, interview questions, keywords. Edit, copy, regenerate, export `.txt`,
   plus a pre-submission checklist and a delete-able history per job (each entry is labelled
   *Template* or *AI*).
8. **Automation Settings** — search keywords, locations, remote-only, minimum match score,
   max job age (freshness cutoff), enabled sources (each showing its live posting count),
   run interval (5 min – 7 days), on/off toggle, "Run now", and a full
   run history with per-source logs. The on/off toggle only controls the *schedule*;
   "Run now" always performs a search.

---

## 5. API reference

Interactive docs: <http://127.0.0.1:8000/docs>

| Method & path | Purpose |
| --- | --- |
| `GET /api/health` | Backend + OpenAI status |
| `GET /api/jobs` | List jobs (`q`, `skill`, `location`, `level`, `emp_type`, `source`, `remote`, `sort=date\|title\|company\|salary`, `page`, `page_size`) — paginated response: `items`, `total`, `pages` |
| `GET /api/jobs/filters` · `/jobs/sources` · `/jobs/{id}` | Filter values; every registered site with its `live_jobs` count; job detail (`/jobs?include_stale=true` also lists postings the source dropped) |
| `POST /api/jobs/refresh` | Import now. Body is a JSON array of source names for a single-site import (`["remotive"]`); `[]` uses the sources ticked in Automation Settings |
| `POST` / `DELETE /api/jobs/{id}/save` | Save / unsave a job |
| `GET /api/saved-jobs` | Saved list with scores (a bare JSON array) |
| `GET /api/matches` · `/matches/{id}` | Ranked matches (paginated) / one score with factors |
| `GET` / `PUT /api/profile` | Read / update profile. `PUT` only touches the fields you send; skills, experience, education and projects are sub-lists with their own endpoints |
| `PUT /api/profile/skills\|experiences\|education\|projects` | Replace those sub-lists |
| `POST` / `DELETE /api/profile/resume` | Upload / remove resume |
| `POST /api/assistant/generate` | Generate a material |
| `GET /api/assistant/materials/{job_id}` · `DELETE /api/assistant/materials/{id}` | History |
| `GET` / `POST` / `PATCH` / `DELETE /api/applications` | Tracker CRUD |
| `GET /api/dashboard/stats` | All dashboard numbers |
| `GET` / `PUT /api/automation/settings` · `POST /api/automation/run` · `GET /api/automation/runs` | Automation. `POST /run` takes an optional JSON array of source names (`["remotive"]`); omit it to use the saved sources |

Validation errors return `422` with a readable message; duplicates return `409`; unknown
ids return `404`.

---

## 6. Running the tests

```powershell
cd "F:\AI agent Gob\backend"
.\.venv\Scripts\Activate.ps1
python -m pytest tests/ -q
```

64 backend tests cover: health, profile CRUD and skill-level validation (including that a
partial `PUT` keeps the fields you did not send), resume upload rejection of bad types and
oversized files, job listing + filters + pagination, dedup across sources and refresh
idempotency, provider network failure not crashing discovery or poisoning the session,
escaped search wildcards, match-score determinism and range, list endpoints not calling the
AI once per job, saved jobs carrying a score, generated materials keeping their
template/AI label, clearing an application date, the startup column patch, manual runs
ignoring the schedule toggle, automation settings, and unknown-source rejection.

The frontend has no automated UI tests; check it compiles and builds instead:

```powershell
cd "F:\AI agent Gob\frontend"
npx tsc -b --force
npm run build
```

---

## 7. Troubleshooting

| Symptom | Fix |
| --- | --- |
| Header shows **"Backend offline"** | uvicorn is not running, or on another port. Start block 2; confirm <http://127.0.0.1:8000/api/health>. |
| `pip install` is very slow or fails | `python -m pip install -r requirements.txt -i https://pypi.org/simple` |
| `npm install` fails with proxy/EEXIST | Delete `frontend\node_modules` and `package-lock.json`, then `npm install` again. |
| Port 5173 or 8000 already in use | `netstat -ano \| findstr :8000` then `taskkill /PID <pid> /F`, or change the port and update `VITE_API_URL` / `CORS_ORIGINS`. |
| PowerShell refuses to activate venv | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, or use `activate.cmd`. |
| No OpenAI key but want AI text | Not possible — the app falls back to templates and labels them. Everything else works. |
| A source returns nothing | You are offline or that API is down; the run log in Automation Settings shows the exact error. Other sources still work. |

---

## 8. Privacy & safety rules this app follows

- Single-user, local-only; no accounts, no telemetry, no passwords. Keys live in `.env`,
  which is git-ignored.
- All database access goes through SQLAlchemy (parameterized), never string SQL.
- Uploaded resumes are validated by extension and size and are never executed.
- Job search uses documented public APIs only — no CAPTCHA, login, paywall or anti-bot
  bypassing.
- Generated text only restates your profile; missing details become `[Your Name]`-style
  placeholders rather than invented facts.
- Applications are never submitted or emails sent automatically. You review and send.

## 9. Known limitations

- **No Alembic migrations.** `create_all` builds the tables, and `ensure_schema_upgrades()`
  in `app/database.py` patches *newly added columns* into tables that already exist (see
  `ADDED_COLUMNS`). Renames, drops and type changes still need Alembic or deleting
  `jobhunter.db` (the real jobs are re-fetched on the next refresh).
- **No authentication** — it is a personal local tool; do not expose port 8000 publicly.
- **Match scores are estimates** from your stated profile, not a guarantee of an interview.
- Seven free real job sources ship enabled (Remotive, RemoteOK, Jobicy, Arbeitnow,
  We Work Remotely, Himalayas, Working Nomads); Egypt-specific boards (Wuzzuf, Forasna,
  LinkedIn, Bayt) need an official API before they can be added honestly — Find Jobs links
  out to them instead. See "Every site you asked about" in section 3 for each verdict.
- OpenAI calls are skipped entirely without a key.
"# Ai_agent_for_job" 
