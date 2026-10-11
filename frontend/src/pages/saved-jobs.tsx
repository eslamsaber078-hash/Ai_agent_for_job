import { useEffect, useRef, useState } from "react";
import { BookmarkX, Bot, Link2 } from "lucide-react";
import { Link } from "react-router-dom";
import { api, qs } from "@/lib/api";
import { type Job, type SavedJob } from "@/lib/types";
import { formatDate, formatSalary, scoreColor } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { JobDetailDialog } from "@/components/jobs/job-detail";
import { useToast } from "@/context/toast";

export function SavedJobsPage() {
  const { toast } = useToast();
  const [items, setItems] = useState<SavedJob[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [selected, setSelected] = useState<Job | null>(null);
  const reqId = useRef(0);

  const load = () => {
    const my = ++reqId.current;
    setError(null);
    api
      .get<SavedJob[]>(`/api/saved-jobs${qs({ q })}`)
      .then((d) => { if (my === reqId.current) setItems(d); })
      .catch((e) => { if (my === reqId.current) setError(e.message); });
  };

  useEffect(() => {
    const t = setTimeout(load, 300);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q]);

  const remove = async (jobId: number) => {
    try {
      await api.delete(`/api/jobs/${jobId}/save`);
      toast("Removed from saved jobs");
      load();
    } catch (e: any) {
      toast(e.message, "error");
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold">Saved Jobs</h1>
          <p className="text-sm text-muted-foreground">Jobs you bookmarked for later</p>
        </div>
        <Input
          placeholder="Filter saved jobs…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          className="w-64"
        />
      </div>

      {error && items && (
        <p className="rounded-lg border border-red-500/40 bg-red-500/5 p-3 text-sm text-red-600 dark:text-red-400">
          {error} — showing the last results that loaded.{" "}
          <button className="underline" onClick={load}>Try again</button>
        </p>
      )}

      {error && !items ? (
        <ErrorState message={error} onRetry={load} />
      ) : items === null ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-24" />)}
        </div>
      ) : items.length === 0 ? (
        <EmptyState
          icon={BookmarkX}
          title={q ? "No saved jobs match your filter" : "No saved jobs yet"}
          description={q ? "Try a different filter." : "Browse Find Jobs and bookmark interesting roles to see them here."}
          action={
            !q ? (
              <Link to="/jobs"><Button>Find jobs</Button></Link>
            ) : undefined
          }
        />
      ) : (
        <div className="space-y-3">
          {items.map((s) => (
            <div key={s.id} className="flex flex-col gap-3 rounded-xl border bg-card p-4 sm:flex-row sm:items-center">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  {s.score !== null && (
                    <span
                      className={`shrink-0 text-2xl font-bold ${scoreColor(s.score)}`}
                      title="Estimated match score from your profile — not a guarantee"
                    >
                      {s.score}
                    </span>
                  )}
                  <button
                    onClick={() => setSelected(s.job)}
                    className="text-sm font-semibold hover:text-primary hover:underline"
                  >
                    {s.job.title}
                  </button>
                </div>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  {s.job.company} · {s.job.location} {s.job.remote ? "· Remote" : ""} · {formatSalary(s.job)}
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Saved {formatDate(s.saved_at)} {s.notes ? `· ${s.notes}` : ""}
                </p>
              </div>
              <div className="flex shrink-0 gap-2">
                {s.job.url && (
                  <Button size="sm" variant="outline" onClick={() => window.open(s.job.url, "_blank", "noopener")}>
                    <Link2 className="h-4 w-4" /> Apply
                  </Button>
                )}
                <Link to={`/assistant?job=${s.job.id}`}>
                  <Button size="sm" variant="outline"><Bot className="h-4 w-4" /> Assistant</Button>
                </Link>
                <Button size="sm" variant="ghost" onClick={() => remove(s.job.id)}>
                  <BookmarkX className="h-4 w-4" /> Remove
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}

      <JobDetailDialog job={selected} onClose={() => setSelected(null)} onChanged={load} />
    </div>
  );
}
