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

On first start the app creates the database and registers the seventeen real job
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

### Block 4 — open the app and make your account

<http://127.0.0.1:5173>

The first screen asks for a phone number and a password. **حساب جديد** (new account) registers
one; every account gets its own empty profile, saved jobs and history, and no other account can
see them. Nothing is shared and nothing is sent anywhere.

To stop: `Ctrl+C` in each window.

---

## 2. Configuration (environment variables)

Copy `backend/.env.example` to `backend/.env` and edit it. The backend reads that file
automatically at startup (real environment variables win over `.env`).

| Variable | Default | What it does |
| --- | --- | --- |
| `OPENAI_API_KEY` | *(empty)* | Enables real AI scoring narratives and AI-written materials. Without it the app uses built-in deterministic templates. |
| `OPENAI_MODEL` | `gpt-4o-mini` | Which OpenAI model to call. |
| `GEMINI_API_KEY` | *(empty)* | Free alternative to OpenAI: a Gemini key from Google AI Studio makes the AI-written CV and cover letter work at no cost. |
| `GEMINI_MODEL` | `gemini-3.8-flash` | Which Gemini model to call (older free models are tried automatically if this one is unavailable). |
| `GROQ_API_KEY` | *(empty)* | Second free backup: when Gemini's free daily quota is exhausted the app falls back to Groq automatically. Free key at <https://console.groq.com/keys>. |
| `GROQ_MODEL` | `qwen/qwen3.8-27b` | Which Groq model to call (newer models are tried automatically if this one is retired). |
| `DATABASE_URL` | `sqlite:///backend/jobhunter.db` | Database location. |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Which browser origins may call the API. |
| `HOST` / `PORT` | `127.0.0.1` / `8000` | Where uvicorn listens (read by the app; still pass them on the command line too). |

Frontend override (optional): set `VITE_API_URL` in `frontend/.env` if the backend is not
on `http://127.0.0.1:8000`.

### Using an AI provider

The app works without any key (deterministic templates), and three providers can
unlock the AI-written texts, tried in this order — OpenAI, the **free** Google Gemini,
then the **free** Groq as backup when Gemini's daily quota is out:

1. **Gemini (free):** open <https://aistudio.google.com/apikey>, sign in with any Google
   account and click "Create API key". Put it in `backend/.env` as `GEMINI_API_KEY=...`.
   `/api/health` then reports `"demo_mode": false`.
2. **Groq (free backup):** open <https://console.groq.com/keys> and create a free key.
   Put it in `backend/.env` as `GROQ_API_KEY=...`. The app only calls it when Gemini
   answers 429/503 (quota exhausted or overloaded), so both free quotas last longer.
3. **OpenAI:** get a key from <https://platform.openai.com/api-keys> and put it in
   `backend/.env` as `OPENAI_API_KEY=sk-...`.

Restart uvicorn after editing `.env`. The AI is only spent on the two materials an
employer reads — the per-job CV and the cover letter (2 calls per application); the
summary, bullets, email, keywords and interview questions always use the built-in
templates, which keeps each application cheap on the free daily quotas. Every
generated card shows a **"Template-based"** badge when the AI path was not used, so
you can always tell where the text came from.
The AI is only ever given the facts you entered — it is instructed to never invent
experience, qualifications, or personal details.

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
| `linkedin` | **Yes** | LinkedIn's public guest job listings — the same result cards a logged-out visitor sees. No login, no key, no CAPTCHA, no bypass: an honest `User-Agent` and nothing more. Searched with your own phrases in your own location, last 30 days, up to 150 postings. If LinkedIn ever blocks it, the source contributes nothing that run and says so. |
| `jsearch` | **Yes** | Google for Jobs via RapidAPI's JSearch (`/search-v2`). **Needs `RAPIDAPI_KEY`.** This is how Wuzzuf, Bayt and GulfTalent postings arrive: they publish to Google's job index, and each imported job keeps a `[via Wuzzuf]` style tag in its description. `num_pages=3` triples the results for the same one request. **Google's index mixes boards** — one import carries Wuzzuf, LinkedIn, Bayt and BeBee ads — so every such job is labelled with the board it really lives on, and its Apply button opens that same page ("Apply on Wuzzuf", "Apply on LinkedIn"). |
| `amazon` | **Yes** | Amazon's own careers API, filtered to Egypt (`country=EGY`), no key and no scraping. Unlike the boards below it carries on-site Egyptian roles — operations, support, customer service — and every listing arrives with its full description, so the relevance gate reads real text instead of a title. |
| `workday` | **Yes** | Employers that run their own careers site on Workday (Citi, Pfizer, Sanofi, AstraZeneca, Novartis, Cisco, Unilever, PwC, HP, Maersk, Accenture). Their public per-site JSON search is asked for "Egypt", the returned location is checked before anything is stored, and each hit's own job page is fetched for the real posting date and description. No aggregator and no key. |
| `smartrecruiters` | **Yes** | The same direct-to-employer idea on SmartRecruiters' public postings API (Delivery Hero today), country-filtered to Egypt, newest first. |
| `adzuna` | **Yes, needs keys** | Adzuna's Egypt job index (`api.adzuna.com/v1/api/jobs/eg/search/1`). **Needs `ADZUNA_APP_ID` + `ADZUNA_APP_KEY`** (free pair at developer.adzuna.com). Without them it fetches nothing and the log says so — the UI shows it as "needs an API key — skipped until then". One phrase per import, rotating like JSearch, so the free daily allowance lasts. |
| `jooble` | **Yes, needs a key** | Jooble's Egypt aggregator, which indexes the local boards. **Needs `JOOBLE_API_KEY`** (free registration at jooble.org/api). Without a key it fetches nothing and the log says `jooble skipped: JOOBLE_API_KEY is not configured` — the UI shows it as "needs an API key — skipped until then", exactly like JSearch. One phrase per import, rotating like JSearch. |
| `employers` | **Yes** | Worldwide-remote roles at employers that hire through their own public Greenhouse/Ashby boards (Canonical, Stripe, GitLab, Supabase, Railway, Netlify, Airbnb, Mozilla, PostHog, Cloudflare, Discord, Brex). Every posting's location is checked against two honest rules before anything is stored: it must be open to Egypt or open worldwide — a "Remote - US" or "Remote - Canada" ad is skipped, never relabelled. |
| `jobgether` | **Yes** | Jobgether's remote aggregator feed (jobgether.com/api/v1/jobs), no key. Two pages per import, same Egypt-or-worldwide location gate, salary range read when the ad states one. |

Network failures are logged and skipped, never crash the search. Free public APIs must not
be hammered, so each feed's answer is cached for a while: **3 minutes** for the keyless
boards and employer sites, **10 minutes** for LinkedIn's guest listing (it throttles
fastest), and **15 minutes** for the three quota-capped sites, JSearch, Jooble and
Adzuna, whose monthly allowance cannot be bought back. Pressing Import breaks that window
for every site except the four that must keep it (LinkedIn's guest listing and the three
quota-capped ones) — a manual import is you asking what was posted *just now*, and a
scheduled run is the app asking politely on a timer.

### What gets searched — and what it cannot promise

Automation Settings has a **What gets searched** card that shows the phrases themselves as
chips you can delete and add to: your job titles, your skills, an **Extra fields to hunt in**
list of your own, and your locations. If those lists are blank, the app inherits your titles,
skills and locations from the Resume & Profile page and says so — an unset field never
silently widens the search to a generic "software developer".

Below the editors, a live preview states exactly what each site will be asked. It is computed
by `POST /api/automation/search-plan` using the same code an import runs, so the preview
cannot drift from reality.

How the phrases are used:

- **One request per phrase.** Concatenating them ("Flutter Developer Mobile Developer")
  behaves like an AND search and drops postings titled just "Flutter Engineer", so each
  phrase is asked on its own and the results are merged and de-duplicated.
- **5 phrases per import**, most specific first (titles → your extra fields → skills). The
  preview names the ones not reached yet; remove one above to free a slot.
- **LinkedIn**: its first 4 phrases, 2 result pages each.
- **JSearch, Jooble and Adzuna**: one phrase per import, rotating through the list. Their
  free plans are quota-capped (250 requests a month for JSearch, an hourly/daily allowance
  for the other two), so rotation covers every phrase at ~1 request per import instead of 5.

This raises how much of a site's relevant inventory a run touches, but it is still a search
of a third party's index, not a firehose of everything posted. No source can promise 100%:
each one ranks and caps what it returns, LinkedIn is limited to the guest listing window, and
the Egyptian boards that block automated access (Wuzzuf's own site, Forasna, Bayt) only
contribute whatever Google has indexed of them.

### Importing one site at a time

Find Jobs has one import button per registered site, each showing how many live postings
that site has contributed. A click fetches only that site, so gathering every source never
loads one server with a pile of simultaneous searches. "Import from all ticked sites" runs the
sites ticked in Automation Settings. A name that is not a registered source, or an import
with **no** site ticked, is refused with a readable 422 instead of silently fetching
everything.

### Keeping it fast

Nothing was cut to get the speed — the same sites, the same postings and the same scores come
back, only sooner:

- **Six sites are asked at once** instead of one after another. A full import used to cost the
  sum of every site's waiting time (about a minute); the sites that answer now finish their
  searches in roughly 13 seconds.
- **Each site's jobs enter the database as soon as that site answers**, while the slower ones
  are still replying, so the first result appears in seconds rather than at the end.
- **Employer career sites are asked together**: Workday's eleven companies reply in parallel,
  the twelve Greenhouse/Ashby boards reply in parallel, and each site's own job pages are read
  eight at a time.
- **Lists are sorted and paginated by the database**, so opening page 3 of 3,700 postings reads
  20 rows instead of loading every description on the server (~0.02s, was ~0.18s).
- **A job is worked out once per change.** The requirements a posting states, and the reading of
  your own CV, are remembered, so re-opening AI Matches costs about 0.5s instead of 3.4s. Edit
  your CV, or let a posting come back with new text, and it is worked out again: what is
  remembered is keyed by the text itself, so a stale answer cannot survive a change.
- **Each screen downloads only its own code.** The chart library the dashboard uses no longer
  sits in the file the login page waits for (745 kB to 231 kB on first load).

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
| Amazon Careers — Egypt | Integrated | Amazon's own careers API, no key, filtered to `country=EGY`. One request returns every Egypt posting (operations, support and customer-service roles the remote-only boards never carry), description included. |
| Employer career sites (Workday) | Integrated | Free per-employer Workday endpoints, searched for "Egypt" and location-checked before anything is stored. Citi, Pfizer, Sanofi, AstraZeneca, Novartis, Cisco, Unilever, PwC, HP, Maersk and Accenture are listed today; each Egypt hit's own job page is fetched for the real posting date and description. |
| Employer career sites (SmartRecruiters) | Integrated | Same idea on SmartRecruiters' public postings API, no key. Delivery Hero is listed today. |
| Employer boards (Greenhouse / Ashby) | Integrated | Free per-employer board APIs for 12 remote-first employers: Canonical, Stripe, GitLab, Supabase, Railway, Netlify, Airbnb, Mozilla, PostHog, Cloudflare, Discord, Brex. Only postings genuinely open to Egypt or worldwide are kept — "Remote - US/Canada/EU" ads are skipped, never relabelled. |
| Jobgether | Integrated | Free remote aggregator feed, two pages per import, same Egypt-or-worldwide location gate. |
| Jooble — Egypt | Integrated, needs a key | `JOOBLE_API_KEY` (free at jooble.org/api) unlocks a large Egypt aggregator that indexes the local boards. Without the key the source stays silent and the UI says "needs an API key — skipped until then". |
| Adzuna — Egypt | Integrated, needs keys | The `adzuna` provider is wired and honest: set `ADZUNA_APP_ID` + `ADZUNA_APP_KEY` (free pair at developer.adzuna.com) and it imports Egypt postings at one rotating phrase per run; without the pair it stays silent. |
| Findwork | Needs a key | `findwork.dev/api/jobs/` answers **401** — a token is issued only after sign-up. |
| USAJOBS | Needs a key + US-only | Free registration required, and it lists United States government jobs only. |
| Reed | No working API | Key was always mandatory; the public job endpoints now answer **404**. UK-focused. |
| The Muse | Blocked | Documented public API, but every request from here returns **403** (CloudFront). |
| Wellfound (AngelList) | Blocked | JS single page behind a Cloudflare Turnstile challenge; no unauthenticated JSON. |
| LinkedIn Jobs | Integrated | The public guest listings (`linkedin.com/jobs-guest/...`) answer without a login, so those are fetched. The authenticated job-search API is still off-limits and is not used. |
| Indeed | Blocked | Publisher API retired in 2018; the search page answers **403** to automated calls. Its postings do arrive through the Google for Jobs index (`jsearch`). |
| Wuzzuf | Integrated via Google | Wuzzuf's own search pages answer **403** (Cloudflare) and are never scraped. Wuzzuf publishes its openings to Google for Jobs, which the `jsearch` source reads, so they land tagged `[via Wuzzuf]`. |
| Forasna | Blocked | No public API; automated access refused. Link only. |
| Bayt | Blocked | No public API for anonymous search; **403**. Like Wuzzuf, its postings reach the app through the Google for Jobs index tagged `[via Bayt.com]`. |
| Lever boards | Not added | Keyless but no global search; the useful Lever boards (Spotify, Binance, Kraken) mostly carry US/EU-locked postings, and the probe found nothing open to Egypt. Greenhouse and Ashby cover the same ground with the twelve boards above. |

For the blocked sites Find Jobs shows one-click links that open *your* search on those
sites in the browser instead of pretending to import them. To add a source,
create a class in `backend/app/services/providers.py` that extends `BaseProvider`, returns
normalized `ProviderJob` objects, and register it in `REGISTRY`. It appears in the import
bar and in Automation Settings on the next restart.

---

## 4. The eight screens

1. **Dashboard** — jobs discovered, high-match count, saved, applications, interviews,
   offers, best matches, status breakdown. All numbers are computed from the database.
2. **Find Jobs** — per-site import bar (one row per source, with its live posting
   count), search, filters (level, employment type, source, remote), sort (newest first by
   default), save, open details, "Track application", plus deep links to the Egyptian boards
   that cannot be imported.
3. **AI Job Matches** — 0–100 estimated score per job with the weighted reasons behind it
   (skills 40%, title 20%, level 15%, location 15%, salary 10%), matched vs missing skills,
   concerns and next steps. Scores are labelled *estimates*, and the same inputs always
   produce the same score.
4. **Saved Jobs** — everything you bookmarked, with score and quick actions.
5. **Applications Desk** — the tracker and the preparation desk in one place: table **and**
   Kanban views, 8 statuses (Discovered → Interested → Preparing → Applied → Interview →
   Offer → Rejected → Archived), notes, follow-up and interview dates, edit and delete.
   "Prepare" builds the whole pack for that one ad — the tailored CV, the cover letter, the
   application email, the interview questions and the keywords from the ad (five documents, one
   click) — and shows the real apply route the ad itself
   named — an address it wrote, its own careers page, or the board listing. Nothing is sent:
   a mail draft opens in *your* program with the text ready and you press send.
6. **Resume & Profile** — profile, skills with levels, experience, education, projects, and
   resume upload (`.pdf .txt .md .doc .docx`, max 5 MB; PDF text is extracted with pypdf,
   `.docx`/`.txt`/`.md` with the stdlib; legacy `.doc` is stored as a reference only;
   files are stored, never executed). **This page is the source of truth** — the AI only
   rephrases what is stored here and never invents experience. **Auto-fill from CV** reads
   the extracted resume text and shows every name, contact field, skill, job and degree it
   found; nothing is written until you tick the items and press Apply, and a field that
   already has a value is only replaced if you explicitly select it.
7. **AI Application Assistant** — resume summary, tailored bullet points, cover letter,
   application email, interview questions, keywords. Edit, copy, regenerate, export `.txt`,
   plus a pre-submission checklist and a delete-able history per job (each entry is labelled
   *Template* or *AI*).
   **ATS CV with the additions shown in red:** the assistant writes a CV aimed at one specific
   ad and may suggest skills or phrasing that would make it pass the ATS screen. Anything it
   suggested that is **not** already in your stored profile is drawn red and underlined in the
   preview, so you see exactly what to confirm or cut — it is never silently mixed into the
   document. **Download CV (PDF)** gives you two copies: the marked one for you to review, and
   a clean ATS copy where those unconfirmed lines are removed rather than just uncoloured
   (`?marked=true` / `?marked=false`). It stays a draft: nothing is uploaded or submitted for you.
8. **Automation Settings** — a **What gets searched** card with editable chips for your job
   titles, skills, **extra fields of your own**, and locations, plus a live preview of the
   exact phrase each site will be asked; remote-only, minimum match score,
   max job age (freshness cutoff), enabled sources (each showing its live posting count),
   run interval (5 min – 7 days), on/off toggle, "Run now", and a full
   run history with per-source logs. The on/off toggle only controls the *schedule*;
   "Run now" always performs a search.

---

## 5. API reference

Interactive docs: <http://127.0.0.1:8000/docs>

| Method & path | Purpose |
| --- | --- |
| `GET /api/health` | Backend + AI-provider status |
| `POST /api/auth/register` · `/auth/login` · `/auth/logout` · `GET /auth/me` | Phone + password accounts. Login sets one `HttpOnly` session cookie; every other route resolves the profile from it, and both `/register` and `/login` are rate-limited. State-changing requests must carry `X-Requested-With: XMLHttpRequest` (CSRF guard). |
| `GET /api/jobs` | List jobs (`q`, `skill`, `location`, `level`, `emp_type`, `source`, `remote`, `sort=date\|title\|company\|salary`, `page`, `page_size`) — paginated response: `items`, `total`, `pages` |
| `GET /api/jobs/filters` · `/jobs/sources` · `/jobs/{id}` | Filter values; every registered site with its `live_jobs` count; job detail (`/jobs?include_stale=true` also lists postings the source dropped) |
| `POST /api/jobs/refresh` | Import now. Body is a JSON array of source names for a single-site import (`["remotive"]`); `[]` uses the sources ticked in Automation Settings |
| `POST /api/jobs/refresh/stream` · `/api/automation/run/stream` | Same imports as Server-Sent Events, so the UI shows each site's progress as it answers instead of one bar at the end |
| `POST` / `DELETE /api/jobs/{id}/save` | Save / unsave a job |
| `GET /api/saved-jobs` | Saved list with scores (a bare JSON array) |
| `GET /api/matches` · `/matches/{id}` | Ranked matches (paginated) / one score with factors |
| `GET` / `PUT /api/profile` | Read / update profile. `PUT` only touches the fields you send; skills, experience, education and projects are sub-lists with their own endpoints |
| `PUT /api/profile/skills\|experiences\|education\|projects` | Replace those sub-lists |
| `POST` / `DELETE /api/profile/resume` | Upload / remove resume |
| `POST /api/profile/resume/autofill` | Read profile suggestions from the uploaded resume text (read-only) |
| `POST /api/profile/resume/autofill/apply` | Apply only the selected suggestions; lists are appended, never replaced |
| `POST /api/profile/term-suggestions` | Spelling-tolerant fixes for a phrase you typed, matched against the terms the app actually knows |
| `POST /api/assistant/generate` | Generate a material |
| `GET /api/assistant/cv/{job_id}/pdf?marked=true\|false` | The CV written for this ad as a PDF. `marked` (default) draws the assistant's unconfirmed additions red and underlined; `marked=false` is the clean ATS copy with them removed |
| `GET /api/assistant/materials/{job_id}` · `DELETE /api/assistant/materials/{id}` | History |
| `GET` / `POST` / `PATCH` / `DELETE /api/applications` | Tracker CRUD |
| `POST /api/applications/prepare` | Build the whole pack for one ad in one call and open a *Preparing* tracker row |
| `GET /api/applications/{id}/materials` · `/materials/{kind}/pdf` | Everything prepared for one application, and any piece of it as a PDF |
| `GET /api/dashboard/stats` | All dashboard numbers |
| `GET` / `PUT /api/automation/settings` · `POST /api/automation/run` · `GET /api/automation/runs` · `POST /api/automation/search-plan` | Automation. `POST /run` takes an optional JSON array of source names (`["remotive"]`); omit it to use the saved sources. `POST /search-plan` takes a settings body (saved or unsaved draft) and returns the exact phrase each site would be asked |

Validation errors return `422` with a readable message; duplicates return `409`; unknown
ids return `404`.

---

## 6. Running the tests

```powershell
cd "F:\AI agent Gob\backend"
.\.venv\Scripts\Activate.ps1
python -m pytest tests/ -q
```

323 backend tests cover: health, profile CRUD and skill-level validation (including that a
partial `PUT` keeps the fields you did not send), resume upload rejection of bad types and
oversized files, the read-only CV auto-fill and the fact that nothing is written until you
approve it, job listing + filters + pagination, dedup across sources (including a re-published
ad entering the database twice), refresh idempotency, provider network failure not crashing
discovery or poisoning the session, a site that could not be read saying so in the run log
instead of looking empty, the relevance gate rejecting ads outside your own wording, escaped
search wildcards, match-score determinism and range, scores that behave like an HR reader
(proved experience beats a wish list, missing stated requirements cost real points), list
endpoints not calling the AI once per job, the AI quota chain (OpenAI → Gemini → Groq) and the
template fallback being labelled, generated materials keeping their template/AI label, the red
suggestion marks being deleted — not just uncoloured — in the clean CV PDF, clearing an
application date, the startup column patch, per-account data isolation, the CSRF guard and
login rate limits, manual runs ignoring the schedule toggle, automation settings, first-run
source ticking, and unknown-source rejection.

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
| No OpenAI key but want AI text | Free works: put a `GEMINI_API_KEY` (or a `GROQ_API_KEY` as backup) in `backend/.env` and restart. With no key at all the app falls back to templates and labels them. |
| AI text suddenly stops mid-day | Gemini's free daily quota is out; Groq takes over if configured, otherwise the cards are labelled "Template-based". Nothing is lost — regenerate tomorrow. |
| A source returns nothing | You are offline or that API is down; the run log in Automation Settings now names the site as "could not be read" rather than reporting zero jobs. Other sources still work. |

---

## 8. Privacy & safety rules this app follows

- Local-only: the accounts are phone + password rows in your own SQLite file, one `HttpOnly`
  session cookie per login, and each account sees only its own profile, jobs and history.
  No telemetry, no third-party analytics, no outbound call except the job APIs you import from
  and the AI provider you configure. Keys live in `.env`, which is git-ignored.
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
- **Accounts are phone + password** with one HttpOnly session cookie and per-account data
  isolation — but there is no email verification or password-recovery flow. For a public
  address that means anyone can register (their data stays invisible to other accounts);
  see section 10 for the deployment path.
- **Match scores are estimates** from your stated profile, not a guarantee of an interview.
- Seventeen real job sources ship: LinkedIn guest listings, Google for Jobs Egypt via
  JSearch, six direct-to-employer or Egypt aggregator channels (Amazon Careers Egypt, Workday
  career sites, SmartRecruiters, Jooble Egypt, Adzuna Egypt, and the worldwide-remote
  Greenhouse/Ashby employer boards), Jobgether's remote feed, and the seven remote boards
  (Remotive, RemoteOK, Jobicy, Arbeitnow, We Work Remotely, Himalayas, Working Nomads).
  JSearch needs `RAPIDAPI_KEY`, Jooble needs `JOOBLE_API_KEY`, and Adzuna needs
  `ADZUNA_APP_ID` + `ADZUNA_APP_KEY`; the other fourteen need nothing. Wuzzuf, Bayt and
  Indeed postings arrive through Google's job index rather than from their own sites, which
  refuse automated access. Forasna still cannot be fetched at all, so Find Jobs links out
  to it instead. See "Every site you asked about" in section 3 for each verdict.
- **Discovery is a search, not a firehose.** Each import asks each keyword site a few of your
  phrases and keeps what comes back, and every source caps and ranks its own results. That
  covers a good share of what is posted for your profile, but no honest tool can promise you
  100% of LinkedIn or of Google's index — see "What gets searched" in section 3.
- OpenAI calls are skipped entirely without a key.

---

## 10. Deploying (Render + Neon)

The repo ships a `render.yaml` blueprint for a **single web service**: the build installs
the Python requirements, builds the frontend, and uvicorn serves both the API and the built
frontend on one domain (`frontend/.env.production` sets `VITE_API_URL=/` for the build, and
`app/main.py` mounts `frontend/dist`). Steps:

1. **Free Postgres at Neon** (<https://neon.tech>, no card): create a project and copy its
   connection string (`postgresql://...`).
2. **Push this repo to GitHub.**
3. **Render** (<https://render.com>) → New → **Blueprint** → pick the repo. In the env form,
   paste the Neon string as `DATABASE_URL` and add any API keys you want (they are all
   optional); `SESSION_COOKIE_SECURE` is already set to `true` by the blueprint.
4. Deploy. The site gets an `https://<name>.onrender.com` address; `/api/health` is the
   health check. The hosted database starts empty — register with your phone + password and
   fill the profile (or upload your CV and use Auto-fill).

Honest platform notes:

- **Never point `DATABASE_URL` at SQLite on Render**: the disk is wiped on every deploy.
- **Render's own free Postgres expires after 30 days** — that is why step 1 uses Neon.
- **The free web service sleeps after ~15 minutes without visitors**; the first visit wakes
  it (a cold start of ~30–60 s). Two things soften that: the frontend waits, retries, and
  says "waking the server" instead of failing, and `.github/workflows/keep-alive.yml` pings
  `/api/health` every five minutes so the service never idles long enough to sleep. The
  workflow needs one repository variable — **Settings → Secrets and variables → Actions →
  Variables → New repository variable**, name `SITE_URL`, value the service address from the
  Render dashboard (`https://something.onrender.com`, no trailing slash) — and does nothing
  until it is set. GitHub pauses scheduled workflows after 60 quiet days; one commit or a
  manual **Run workflow** turns it back on. A paid instance (~$7/month) stays up without
  any of this. Scheduled searches still only run while the service is awake.
- The app has no email verification, so on a public address anyone can register an account;
  accounts are fully isolated from each other (per-account data + scrypt password hashes +
  HttpOnly session cookie + rate-limited login/register), and nothing is auto-sent.
