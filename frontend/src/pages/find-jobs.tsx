import { useCallback, useEffect, useRef, useState } from "react";
import { Download, ExternalLink, Loader2, RefreshCw, SearchX } from "lucide-react";
import { api, qs } from "@/lib/api";
import { type Job, type JobPage, type JobSourceSite, sourceLabel } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { JobCard } from "@/components/jobs/job-card";
import { JobDetailDialog } from "@/components/jobs/job-detail";
import { useToast } from "@/context/toast";

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
  { name: "Wuzzuf", url: (q: string) => `https://wuzzuf.net/search/jobs/?q=${encodeURIComponent(q)}` },
  { name: "Forasna", url: (q: string) => `https://forasna.com/search/jobs/?q=${encodeURIComponent(q)}` },
  { name: "Bayt", url: (q: string) => `https://www.bayt.com/en/search/jobs/?q=${encodeURIComponent(q)}` },
  { name: "LinkedIn Egypt", url: (q: string) => `https://www.linkedin.com/jobs/search/?keywords=${encodeURIComponent(q)}&location=Egypt` },
];

export function FindJobsPage() {
  const { toast } = useToast();
  const [data, setData] = useState<JobPage | null>(null);
  const [filters, setFilters] = useState<Filters>({ levels: [], employment_types: [], sources: [] });
  const [sites, setSites] = useState<JobSourceSite[]>([]);
  const [importing, setImporting] = useState<string | null>(null);
  const [importLog, setImportLog] = useState<string[]>([]);
  const [showStale, setShowStale] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Job | null>(null);
  const reqId = useRef(0);

  const [q, setQ] = useState("");
  const [skill, setSkill] = useState("");
  const [location, setLocation] = useState("");
  const [level, setLevel] = useState("");
  const [empType, setEmpType] = useState("");
  const [source, setSource] = useState("");
  const [remote, setRemote] = useState("");
  const [sort, setSort] = useState("date");
  const [page, setPage] = useState(1);
  const [pageSize] = useState(12);

  const load = useCallback(async () => {
    const my = ++reqId.current;
    setLoading(true);
    setError(null);
    try {
      const result = await api.get<JobPage>(
        `/api/jobs${qs({ q, skill, location, level, emp_type: empType, source, remote: remote === "" ? undefined : remote === "true", include_stale: showStale || undefined, sort, page, page_size: pageSize })}`
      );
      if (my === reqId.current) setData(result);
    } catch (e: any) {
      if (my === reqId.current) setError(e.message);
    } finally {
      if (my === reqId.current) setLoading(false);
    }
  }, [q, skill, location, level, empType, source, remote, showStale, sort, page, pageSize]);

  const loadSites = useCallback(() => {
    api.get<JobSourceSite[]>("/api/jobs/sources").then(setSites).catch(() => {});
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
    try {
      const r = await api.post<{ jobs_new: number; log: string[]; sources_used: string[] }>(
        "/api/jobs/refresh",
        name ? [name] : []
      );
      const label = name ? sourceLabel(name) : "all ticked sources";
      toast(
        r.jobs_new > 0
          ? `${label}: ${r.jobs_new} new job(s) imported`
          : `${label}: nothing new — every live posting is already in your database`
      );
      setImportLog(r.log);
      await Promise.all([load(), loadSites()]);
    } catch (e: any) {
      toast(e.message, "error");
    } finally {
      setImporting(null);
    }
  };

  const toggleSave = async (job: Job) => {
    try {
      if (job.saved) {
        await api.delete(`/api/jobs/${job.id}/save`);
        toast("Removed from saved jobs");
      } else {
        await api.post(`/api/jobs/${job.id}/save`);
        toast("Job saved");
      }
      job.saved = !job.saved;
      setData((d) => (d ? { ...d } : d));
    } catch (e: any) {
      toast(e.message, "error");
    }
  };

  const track = async (job: Job) => {
    try {
      await api.post("/api/applications", { job_id: job.id, status: "Discovered" });
      toast("Added to Applications Tracker");
      job.application_status = "Discovered";
      setData((d) => (d ? { ...d } : d));
    } catch (e: any) {
      toast(e.message, "error");
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold">Find Jobs</h1>
          <p className="text-sm text-muted-foreground">
            {data
              ? `${data.total} ${showStale ? "job postings" : "live job postings"} in your database`
              : "Searching your job database…"}
          </p>
        </div>
        <label className="flex items-center gap-2 text-xs text-muted-foreground">
          <input
            type="checkbox"
            className="h-4 w-4"
            checked={showStale}
            onChange={(e) => { setShowStale(e.target.checked); setPage(1); }}
          />
          Show postings the source no longer advertises
        </label>
      </div>

      <div className="rounded-xl border bg-card p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-sm font-medium">Import from a site</p>
          <p className="text-xs text-muted-foreground">
            One site at a time keeps each server light — the number is how many live postings that site has given you so far.
          </p>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          {sites.map((s) => (
            <Button
              key={s.name}
              variant="outline"
              size="sm"
              disabled={importing !== null}
              onClick={() => importSite(s.name)}
              title={`Import only from ${s.label}`}
            >
              {importing === s.name ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Download className="h-4 w-4" />
              )}
              {sourceLabel(s.name)}
              <Badge variant={s.live_jobs ? "secondary" : "outline"} className="ml-1 text-[10px]">
                {s.live_jobs ? `${s.live_jobs} live` : "not imported"}
              </Badge>
            </Button>
          ))}
          <Button size="sm" variant="secondary" disabled={importing !== null} onClick={() => importSite(null)}>
            <RefreshCw className={`h-4 w-4 ${importing === "all" ? "animate-spin" : ""}`} />
            {importing === "all" ? "Importing…" : "Import from all ticked sites"}
          </Button>
        </div>
        <p className="mt-2 text-[11px] text-muted-foreground">
          Every import searches for your saved titles, skills and locations (Automation settings), then hides postings older than your max job age.
        </p>
        {importLog.length > 0 && (
          <pre className="mt-3 max-h-40 overflow-auto whitespace-pre-wrap rounded bg-muted p-2 text-[11px] leading-relaxed">
            {importLog.join("\n")}
          </pre>
        )}
        <div className="mt-3 border-t pt-3">
          <p className="text-xs font-medium">Sites that post Egypt jobs but publish no import feed</p>
          <p className="mt-1 text-[11px] text-muted-foreground">
            These block automated access, so the app will not pretend to import them. One click opens your own search there:
            {" "}
            {EGYPT_SEARCH_SITES.map((s) => (
              <a
                key={s.name}
                className="mr-3 inline-flex items-center gap-1 underline hover:text-primary"
                href={s.url(q.trim())}
                target="_blank"
                rel="noopener noreferrer"
              >
                {s.name} <ExternalLink className="h-3 w-3" />
              </a>
            ))}
          </p>
        </div>
      </div>

      <div className="grid gap-3 rounded-xl border bg-card p-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="sm:col-span-2 lg:col-span-2">
          <Input placeholder="Search title, company, description…" value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} />
        </div>
        <Input placeholder="Skill (e.g. Flutter)" value={skill} onChange={(e) => { setSkill(e.target.value); setPage(1); }} />
        <Input placeholder="Location (e.g. Cairo, Remote)" value={location} onChange={(e) => { setLocation(e.target.value); setPage(1); }} />
        <Select value={level} onChange={(e) => { setLevel(e.target.value); setPage(1); }}>
          <option value="">All levels</option>
          {filters.levels.map((l) => <option key={l} value={l}>{l}</option>)}
        </Select>
        <Select value={empType} onChange={(e) => { setEmpType(e.target.value); setPage(1); }}>
          <option value="">All types</option>
          {filters.employment_types.map((t) => <option key={t} value={t}>{t}</option>)}
        </Select>
        <Select value={source} onChange={(e) => { setSource(e.target.value); setPage(1); }}>
          <option value="">All sources</option>
          {filters.sources.map((s) => <option key={s} value={s}>{sourceLabel(s)}</option>)}
        </Select>
        <Select value={remote} onChange={(e) => { setRemote(e.target.value); setPage(1); }}>
          <option value="">Onsite & remote</option>
          <option value="true">Remote only</option>
          <option value="false">Onsite only</option>
        </Select>
        <Select value={sort} onChange={(e) => setSort(e.target.value)}>
          {SORTS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
        </Select>
      </div>

      {error && data && (
        <p className="rounded-lg border border-red-500/40 bg-red-500/5 p-3 text-sm text-red-600 dark:text-red-400">
          {error} — showing the last results that loaded.{" "}
          <button className="underline" onClick={load}>Try again</button>
        </p>
      )}

      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-56" />)}
        </div>
      ) : error && !data ? (
        <ErrorState message={error} onRetry={load} />
      ) : !data || data.items.length === 0 ? (
        <EmptyState
          icon={SearchX}
          title="No jobs found"
          description="Try different filters, or import from one of the sites above to fill your database."
          action={<Button onClick={() => importSite(null)} disabled={importing !== null}>Import from all ticked sites</Button>}
        />
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {data.items.map((job) => (
              <JobCard
                key={job.id}
                job={job}
                onSave={toggleSave}
                onOpen={(j) => setSelected(j)}
                onTrack={track}
              />
            ))}
          </div>

          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground">
              Page {data.page} of {data.pages}
            </p>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
                Previous
              </Button>
              <Button variant="outline" size="sm" disabled={page >= data.pages} onClick={() => setPage((p) => p + 1)}>
                Next
              </Button>
            </div>
          </div>
        </>
      )}

      <JobDetailDialog
        job={selected}
        onClose={() => setSelected(null)}
        onChanged={() => load()}
      />
    </div>
  );
}
