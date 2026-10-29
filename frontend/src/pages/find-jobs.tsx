import { useCallback, useEffect, useRef, useState } from "react";
import {
  ChevronDown,
  Download,
  ExternalLink,
  Loader2,
  RefreshCw,
  SearchX,
  X,
} from "lucide-react";
import { api, qs } from "@/lib/api";
import { employmentTypeLabel } from "@/lib/employment-type";
import { type Job, type JobPage, type JobSourceSite, sourceLabel } from "@/lib/types";
import { useI18n } from "@/context/i18n";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/layout/page-header";
import { JobCard } from "@/components/jobs/job-card";
import { JobDetailDialog } from "@/components/jobs/job-detail";
import { useAppliedMark } from "@/components/jobs/applied-mark";
import { useToast } from "@/context/toast";
import { cn } from "@/lib/utils";

interface Filters {
  levels: string[];
  employment_types: string[];
  sources: string[];
}

const SORTS = [
  { value: "date", label: "Newest first" },
  { value: "title", label: "Title A–Z" },
  { value: "company", label: "Company A–Z" },
  { value: "salary", label: "Highest salary" },
];

/** Verified search-URL shapes; they open in the browser, the app never scrapes them. */
const EGYPT_SEARCH_SITES = [
  { name: "Forasna", url: (q: string) => `https://forasna.com/search/jobs/?q=${encodeURIComponent(q)}` },
  { name: "Bayt", url: (q: string) => `https://www.bayt.com/en/search/jobs/?q=${encodeURIComponent(q)}` },
];

function FilterLabel({ children }: { children: React.ReactNode }) {
  return <span className="mb-1.5 block text-[11px] font-medium uppercase tracking-[0.12em] text-muted-foreground">{children}</span>;
}

export function FindJobsPage() {
  const { toast } = useToast();
  const { t, tt, lang } = useI18n();
  const [items, setItems] = useState<Job[]>([]);
  const [total, setTotal] = useState<number | null>(null);
  const [filters, setFilters] = useState<Filters>({ levels: [], employment_types: [], sources: [] });
  const [sites, setSites] = useState<JobSourceSite[]>([]);
  const [sitesError, setSitesError] = useState<string | null>(null);
  const [importing, setImporting] = useState<string | null>(null);
  const [importProgress, setImportProgress] = useState<{ done: number; total: number; label: string } | null>(null);
  // The site list is fifteen rows of bookkeeping; the jobs are why he opened this page.
  // It starts folded so the first screen holds postings, and it unfolds on its own the
  // moment an import starts so the progress bar is never hidden.
  const [importOpen, setImportOpen] = useState(false);
  const [importLog, setImportLog] = useState<string[]>([]);
  const [showStale, setShowStale] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Job | null>(null);
  const [savingIds, setSavingIds] = useState<Set<number>>(new Set());
  const savingRef = useRef<Set<number>>(new Set());
  const [trackingIds, setTrackingIds] = useState<Set<number>>(new Set());
  const trackingRef = useRef<Set<number>>(new Set());
  const reqId = useRef(0);
  const progressThrottle = useRef(0);

  const [q, setQ] = useState("");
  const [skill, setSkill] = useState("");
  const [location, setLocation] = useState("");
  const [level, setLevel] = useState("");
  const [empType, setEmpType] = useState("");
  const [source, setSource] = useState("");
  const [remote, setRemote] = useState("");
  const [sort, setSort] = useState("date");
  const [page, setPage] = useState(1);
  const [pageSize] = useState(24);

  const load = useCallback(async () => {
    const my = ++reqId.current;
    setLoading(true);
    setError(null);
    try {
      const result = await api.get<JobPage>(
        `/api/jobs${qs({ q, skill, location, level, emp_type: empType, source, remote: remote === "" ? undefined : remote === "true", include_stale: showStale || undefined, sort, page: 1, page_size: pageSize })}`
      );
      if (my === reqId.current) {
        setItems(result.items);
        setTotal(result.total);
        setPage(1);
      }
    } catch (e: any) {
      if (my === reqId.current) setError(e.message);
    } finally {
      if (my === reqId.current) setLoading(false);
    }
  }, [q, skill, location, level, empType, source, remote, showStale, sort, pageSize]);

  const loadMore = async () => {
    if (loadingMore) return;
    const my = reqId.current;
    setLoadingMore(true);
    try {
      const result = await api.get<JobPage>(
        `/api/jobs${qs({ q, skill, location, level, emp_type: empType, source, remote: remote === "" ? undefined : remote === "true", include_stale: showStale || undefined, sort, page: page + 1, page_size: pageSize })}`
      );
      // A filter changed while this page was in flight — those rows belong to the
      // old search, and appending them would show jobs that do not match the screen.
      if (my !== reqId.current) return;
      setItems((xs) => [...xs, ...result.items]);
      setTotal(result.total);
      setPage((p) => p + 1);
    } catch (e: any) {
      if (my === reqId.current) toast(e.message, "error");
    } finally {
      setLoadingMore(false);
    }
  };

  const loadSites = useCallback(() => {
    // The import buttons live on this list; if it fails, say so instead of an
    // empty "Import from a site" row that looks like the backend has no sources.
    api.get<JobSourceSite[]>("/api/jobs/sources")
      .then((d) => { setSites(d); setSitesError(null); })
      .catch((e: any) => setSitesError(String(e.message)));
  }, []);

  useEffect(() => {
    api.get<Filters>("/api/jobs/filters").then(setFilters).catch(() => {});
    loadSites();
  }, [loadSites]);

  useEffect(() => {
    const t = setTimeout(load, 300);
    return () => clearTimeout(t);
  }, [load]);

  const importSite = async (name: string | null) => {
    setImporting(name ?? "all");
    setImportProgress(null);
    setImportLog([]);
    try {
      const ev = await api.postStream("/api/jobs/refresh/stream", name ? [name] : [], (p) => {
        if (p.type !== "progress") return;
        // An import emits thousands of lines; re-rendering the whole page (and every
        // loaded job card) per line used to make big imports crawl. The progress bar
        // updates at most every 100ms, and the log grows with a functional update
        // instead of copying the whole array each event.
        const now = Date.now();
        if (now - progressThrottle.current > 100 || p.done === p.total) {
          progressThrottle.current = now;
          setImportProgress({ done: p.done ?? 0, total: p.total ?? 0, label: p.label ?? "" });
        }
        const line = p.line;
        if (line) setImportLog((prev) => [...prev, line]);
      });
      if (ev.type === "done") {
        const label = name ? sourceLabel(name) : t("all ticked sources");
        toast(
          (ev.jobs_new ?? 0) > 0
            ? ev.jobs_new === 1
              ? t("{label}: {count} new job imported", { label, count: ev.jobs_new ?? 0 })
              : t("{label}: {count} new jobs imported", { label, count: ev.jobs_new ?? 0 })
            : t("{label}: nothing new — every live posting is already in your database", { label })
        );
        setImportLog((ev.log ?? "").split("\n"));
        // Pressing a site button means "show me this site" too: filter the list to it.
        if ((name ?? "") === source) {
          await Promise.all([load(), loadSites()]);
        } else {
          setSource(name ?? "");
          setPage(1);
          await loadSites();
        }
      }
    } catch (e: any) {
      toast(e.message, "error");
    } finally {
      setImporting(null);
      setImportProgress(null);
    }
  };

  const toggleSave = useCallback(async (job: Job) => {
    // A second click while the first save is in flight would read the old `saved`
    // flag and flip the card back, leaving the screen disagreeing with the server.
    if (savingRef.current.has(job.id)) return;
    savingRef.current.add(job.id);
    setSavingIds(new Set(savingRef.current));
    try {
      if (job.saved) {
        await api.delete(`/api/jobs/${job.id}/save`);
        toast(t("Removed from saved jobs"));
      } else {
        await api.post(`/api/jobs/${job.id}/save`);
        toast(t("Job saved"));
      }
      // Immutable patch: the card object is shared with the dialog, so it must
      // never be mutated in place.
      setItems((xs) => xs.map((x) => (x.id === job.id ? { ...x, saved: !x.saved } : x)));
      setSelected((cur) => (cur && cur.id === job.id ? { ...cur, saved: !cur.saved } : cur));
    } catch (e: any) {
      toast(e.message, "error");
    } finally {
      savingRef.current.delete(job.id);
      setSavingIds(new Set(savingRef.current));
    }
  }, [t, toast]);

  const track = useCallback(async (job: Job) => {
    // The desk refuses a second row for the same posting, so a double click used to
    // answer with a raw English "already exists" toast. One press gets through.
    if (trackingRef.current.has(job.id)) return;
    trackingRef.current.add(job.id);
    setTrackingIds(new Set(trackingRef.current));
    try {
      await api.post("/api/applications", { job_id: job.id, status: "Discovered" });
      toast(t("Added to the Applications Desk"));
      setItems((xs) => xs.map((x) => (x.id === job.id ? { ...x, application_status: "Discovered" } : x)));
      setSelected((cur) => (cur && cur.id === job.id ? { ...cur, application_status: "Discovered" } : cur));
    } catch (e: any) {
      toast(e.message, "error");
    } finally {
      trackingRef.current.delete(job.id);
      setTrackingIds(new Set(trackingRef.current));
    }
  }, [t, toast]);

  /** Write the tick's three fields into every copy this page holds of that job. */
  const patchApplied = useCallback((id: number, fields: Partial<Job>) => {
    setItems((xs) => xs.map((x) => (x.id === id ? { ...x, ...fields } : x)));
    setSelected((cur) => (cur && cur.id === id ? { ...cur, ...fields } : cur));
  }, []);
  const setApplied = useAppliedMark(patchApplied);

  const openJob = useCallback((job: Job) => setSelected(job), []);

  /** One cheap GET for the one job that changed — keeps the Load-more history
   *  and scroll position instead of resetting the list to page 1. */
  const refreshJob = useCallback(async (job: Job) => {
    try {
      const fresh = await api.get<Job>(`/api/jobs/${job.id}`);
      setItems((xs) => xs.map((x) => (x.id === job.id ? fresh : x)));
      setSelected((cur) => (cur && cur.id === job.id ? fresh : cur));
    } catch {
      /* the dialog already shows what changed; the list refreshes next load */
    }
  }, []);

  const dbLive = sites.reduce((a, s) => a + (s.live_jobs || 0), 0);
  const hasFilters = Boolean(q || skill || location || level || empType || source || remote);

  const clearAll = () => {
    setQ("");
    setSkill("");
    setLocation("");
    setLevel("");
    setEmpType("");
    setSource("");
    setRemote("");
    setPage(1);
  };

  const activeFilters = [
    q && { key: "q", label: `“${q}”`, clear: () => setQ("") },
    skill && { key: "skill", label: t("Skill: {skill}", { skill }), clear: () => setSkill("") },
    location && { key: "location", label: t("Location: {location}", { location }), clear: () => setLocation("") },
    level && { key: "level", label: tt(level), clear: () => setLevel("") },
    empType && { key: "type", label: employmentTypeLabel(empType, t, lang), clear: () => setEmpType("") },
    source && { key: "source", label: sourceLabel(source), clear: () => setSource("") },
    remote && { key: "remote", label: t(remote === "true" ? "Remote only" : "Onsite only"), clear: () => setRemote("") },
  ].filter(Boolean) as { key: string; label: string; clear: () => void }[];

  // Open by press, open while a pull is running, and open right after one so the
  // import log he just earned is not folded away behind the button that made it.
  const showImport = importOpen || importing !== null || importLog.length > 0;

  return (
    <div className="animate-fade-in space-y-5">
      <PageHeader
        eyebrow={t("Job database")}
        title={t("Find Jobs")}
        description={
          total === null
            ? t("Searching your job database…")
            : hasFilters
              ? t(
                  showStale
                    ? source
                      ? "{count} postings on {source} match your filters"
                      : "{count} postings match your filters"
                    : source
                      ? "{count} live postings on {source} match your filters"
                      : "{count} live postings match your filters",
                  { count: total, source: source ? sourceLabel(source) : "" }
                ) + (dbLive > total ? t(" · {count} live across all sites", { count: dbLive }) : "")
              : t(
                  showStale
                    ? "{count} postings in your database"
                    : "{count} live postings in your database",
                  { count: total }
                ) + (dbLive > total ? t(" · {count} live across all sites", { count: dbLive }) : "")
        }
        actions={
          <label className="inline-flex h-10 cursor-pointer items-center gap-2 rounded-lg border border-border/80 bg-card px-3 text-xs font-medium text-muted-foreground shadow-soft transition-colors hover:text-foreground">
            <input
              type="checkbox"
              className="h-4 w-4"
              checked={showStale}
              onChange={(e) => { setShowStale(e.target.checked); setPage(1); }}
            />
            {t("Show pulled postings")}
          </label>
        }
      />

      <Card>
        <CardHeader className="flex-row flex-wrap items-start justify-between gap-3 space-y-0 pb-4">
          <div className="min-w-0 space-y-1.5">
            <CardTitle>{t("Import jobs")}</CardTitle>
            <CardDescription>
              {showImport
                ? t("One site at a time keeps each server light — the number is how many live postings that site has given you so far.")
                : t("{n} sites to pull from — open the list to choose one", { n: sites.length || "…" })}
            </CardDescription>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <Button size="sm" variant="secondary" disabled={importing !== null} onClick={() => importSite(null)}>
              <RefreshCw className={cn("h-4 w-4", importing === "all" && "animate-spin")} />
              {importing === "all" ? t("Importing…") : t("Import all ticked sites")}
            </Button>
            <button
              type="button"
              onClick={() => setImportOpen((v) => !v)}
              aria-expanded={showImport}
              title={showImport ? t("Fold the site list") : t("Open the site list")}
              className="rounded-lg border border-border/70 p-2 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <ChevronDown className={cn("h-4 w-4 transition-transform duration-200 ease-smooth", showImport && "rotate-180")} />
            </button>
          </div>
        </CardHeader>
        {showImport && (
        <CardContent className="space-y-4">
          <div className="grid gap-x-8 sm:grid-cols-2">
            {sites.map((s) => {
              const busy = importing === s.name;
              return (
                <button
                  key={s.name}
                  type="button"
                  disabled={importing !== null}
                  onClick={() => importSite(s.name)}
                  title={`${sourceLabel(s.name)} — ${t("import only from this site")}`}
                  className={cn(
                    "group flex min-w-0 items-center gap-3 border-b border-border/60 py-2.5 text-start transition-colors hover:bg-muted/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50",
                    busy && "bg-muted/50"
                  )}
                >
                  <span className="min-w-0 flex-1 truncate text-[13px] font-medium">{sourceLabel(s.name)}</span>
                  <span className={cn("nums shrink-0 text-[11px]", s.live_jobs ? "text-foreground" : "text-muted-foreground")}>
                    {!s.key_ready
                      ? t("needs a key")
                      : s.live_jobs
                        ? t("{n} live", { n: s.live_jobs })
                        : s.fetched_at
                          ? t("nothing new last run")
                          : t("not imported yet")}
                  </span>
                  {busy
                    ? <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin text-muted-foreground" />
                    : <Download className="h-3.5 w-3.5 shrink-0 text-muted-foreground/40 transition-colors group-hover:text-foreground" />}
                </button>
              );
            })}
            {sites.length === 0 && (
              <p className="col-span-full rounded-xl border border-dashed p-4 text-sm text-muted-foreground">
                {sitesError ? (
                  <>{t("The site list did not load: {error}.", { error: sitesError })}{" "}
                    <button type="button" className="font-semibold text-foreground underline underline-offset-2" onClick={loadSites}>
                      {t("Try again")}
                    </button>
                  </>
                ) : t("Loading the site list…")}
              </p>
            )}
          </div>

          {importing && !importProgress && (
            <p className="text-xs text-muted-foreground">{t("Starting the import…")}</p>
          )}
          {importProgress && (
            <div className="rounded-xl border border-border/70 bg-muted/30 p-3">
              <div className="flex items-center justify-between gap-3 text-xs text-muted-foreground">
                <span className="truncate">
                  {t("Importing from {label} — site {done} of {total}", { label: importProgress.label, done: importProgress.done, total: importProgress.total })}
                </span>
                <span className="shrink-0 font-semibold text-foreground">
                  {importProgress.total ? Math.round((importProgress.done / importProgress.total) * 100) : 0}%
                </span>
              </div>
              <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-muted">
                <div
                  className="h-full rounded-full bg-primary transition-[width] duration-300 ease-out"
                  style={{ width: `${importProgress.total ? (importProgress.done / importProgress.total) * 100 : 0}%` }}
                />
              </div>
            </div>
          )}

          <p className="text-[11px] leading-relaxed text-muted-foreground">
            {t("Every import searches for your saved titles, skills and locations (Automation settings), then hides postings older than your max job age.")}
          </p>

          {importLog.length > 0 && (
            <pre className="scrollbar-thin max-h-40 overflow-auto whitespace-pre-wrap rounded-xl border border-border/60 bg-muted/40 p-3 text-[11px] leading-relaxed">
              {importLog.join("\n")}
            </pre>
          )}

          <details className="rounded-xl border border-border/60 bg-muted/20 px-3 py-2">
            <summary className="cursor-pointer text-xs font-medium text-muted-foreground hover:text-foreground">
              {t("Sites that post Egypt jobs but publish no import feed")}
            </summary>
            <p className="mt-2 text-[11px] leading-relaxed text-muted-foreground">
              {t("These block automated access, so the app will not pretend to import them. One click opens your own search there:")}{" "}
              {EGYPT_SEARCH_SITES.map((s) => (
                <a
                  key={s.name}
                  className="me-3 inline-flex items-center gap-1 font-medium text-foreground underline decoration-border underline-offset-2 hover:decoration-foreground"
                  href={s.url(q.trim())}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {s.name} <ExternalLink className="h-3 w-3" />
                </a>
              ))}
            </p>
          </details>
        </CardContent>
        )}
      </Card>

      <Card>
        <CardContent className="space-y-4 p-4 sm:p-5">
          {/* Every field is labelled above itself, so the card needs no title row of its
              own — that line only pushed the jobs another screen further down. */}
          <h2 className="sr-only">{t("Filters")}</h2>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
            <label className="sm:col-span-2 block">
              <FilterLabel>{t("Search")}</FilterLabel>
              <Input placeholder={t("Title, company or description…")} value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} />
            </label>
            <label className="block">
              <FilterLabel>{t("Skill")}</FilterLabel>
              <Input placeholder={t("e.g. Flutter")} value={skill} onChange={(e) => { setSkill(e.target.value); setPage(1); }} />
            </label>
            <label className="block">
              <FilterLabel>{t("Location")}</FilterLabel>
              <Input placeholder={t("e.g. Cairo, Remote")} value={location} onChange={(e) => { setLocation(e.target.value); setPage(1); }} />
            </label>
            <label className="block">
              <FilterLabel>{t("Level")}</FilterLabel>
              <Select value={level} onChange={(e) => { setLevel(e.target.value); setPage(1); }}>
                <option value="">{t("All levels")}</option>
                {filters.levels.map((l) => <option key={l} value={l}>{tt(l)}</option>)}
              </Select>
            </label>
            <label className="block">
              <FilterLabel>{t("Employment type")}</FilterLabel>
              <Select value={empType} onChange={(e) => { setEmpType(e.target.value); setPage(1); }}>
                <option value="">{t("All types")}</option>
                {filters.employment_types.map((et) => <option key={et} value={et}>{employmentTypeLabel(et, t, lang)}</option>)}
              </Select>
            </label>
            <label className="block">
              <FilterLabel>{t("Source")}</FilterLabel>
              <Select value={source} onChange={(e) => { setSource(e.target.value); setPage(1); }}>
                <option value="">{t("All sources")}</option>
                {filters.sources.map((s) => <option key={s} value={s}>{sourceLabel(s)}</option>)}
              </Select>
            </label>
            <label className="block">
              <FilterLabel>{t("Work mode")}</FilterLabel>
              <Select value={remote} onChange={(e) => { setRemote(e.target.value); setPage(1); }}>
                <option value="">{t("Onsite & remote")}</option>
                <option value="true">{t("Remote only")}</option>
                <option value="false">{t("Onsite only")}</option>
              </Select>
            </label>
            <label className="block">
              <FilterLabel>{t("Sort by")}</FilterLabel>
              <Select value={sort} onChange={(e) => { setSort(e.target.value); setPage(1); }}>
                {SORTS.map((s) => <option key={s.value} value={s.value}>{t(s.label)}</option>)}
              </Select>
            </label>
          </div>

          {activeFilters.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5 border-t border-border/60 pt-3">
              <span className="text-[11px] font-medium text-muted-foreground">{t("Active:")}</span>
              {activeFilters.map((f) => (
                <button
                  key={f.key}
                  type="button"
                  onClick={() => { f.clear(); setPage(1); }}
                  className="inline-flex items-center gap-1 rounded-md border border-border bg-muted/60 px-2 py-1 text-[11px] font-medium transition-colors hover:border-foreground/25 hover:bg-muted"
                >
                  {f.label}
                  <X className="h-3 w-3 text-muted-foreground" />
                </button>
              ))}
              <button
                type="button"
                onClick={clearAll}
                className="ms-1 text-[11px] font-semibold text-muted-foreground underline underline-offset-2 transition-colors hover:text-foreground"
              >
                {t("Clear all")}
              </button>
            </div>
          )}
        </CardContent>
      </Card>

      {error && items.length > 0 && (
        <p className="rounded-xl border border-red-500/25 bg-red-500/[0.05] p-3 text-sm text-red-700 dark:text-red-400">
          {t("{error} — showing the last results that loaded.", { error })}{" "}
          <button className="font-semibold underline" onClick={load}>{t("Try again")}</button>
        </p>
      )}

      {loading ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-64 rounded-2xl" />)}
        </div>
      ) : error && items.length === 0 ? (
        <ErrorState message={error} onRetry={load} />
      ) : items.length === 0 ? (
        <EmptyState
          icon={SearchX}
          title={t("No jobs found")}
          description={t("Try different filters, or import from one of the sites above to fill your database.")}
          action={<Button onClick={() => importSite(null)} disabled={importing !== null}>{t("Import jobs now")}</Button>}
        />
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {items.map((job) => (
              <JobCard
                key={job.id}
                job={job}
                onSave={toggleSave}
                onOpen={openJob}
                onTrack={track}
                onAppliedChange={setApplied}
                saving={savingIds.has(job.id)}
                tracking={trackingIds.has(job.id)}
              />
            ))}
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border/70 bg-card/60 px-4 py-3">
            <p className="text-sm text-muted-foreground">
              {t("Showing")}{" "}
              <span className="font-semibold text-foreground">{items.length}</span>{" "}
              {t("of")}{" "}
              <span className="font-semibold text-foreground">{total ?? items.length}</span>
              {" "}{t("— use “Load more” to keep browsing.")}
            </p>
            {items.length < (total ?? items.length) && (
              <Button variant="outline" size="sm" disabled={loadingMore} onClick={loadMore}>
                {loadingMore ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <RefreshCw className="h-4 w-4" />
                )}
                {t("Load more ({n} more)", { n: Math.min(pageSize, (total ?? items.length) - items.length) })}
              </Button>
            )}
          </div>
        </>
      )}

      <JobDetailDialog
        job={selected}
        onClose={() => setSelected(null)}
        onChanged={refreshJob}
        onAppliedChange={setApplied}
      />
    </div>
  );
}
