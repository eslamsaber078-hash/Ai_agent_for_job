import { useCallback, useEffect, useRef, useState } from "react";
import { BookmarkX, Bot, Link2, Search } from "lucide-react";
import { Link } from "react-router-dom";
import { api, qs } from "@/lib/api";
import { type Job, type SavedJob } from "@/lib/types";
import { formatDate, formatSalary, scoreColor } from "@/lib/format";
import { Button, buttonClassName } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/layout/page-header";
import { AppliedMark, marksOnApply, useAppliedMark } from "@/components/jobs/applied-mark";
import { JobDetailDialog } from "@/components/jobs/job-detail";
import { useToast } from "@/context/toast";
import { useI18n } from "@/context/i18n";
import { cn } from "@/lib/utils";

export function SavedJobsPage() {
  const { toast } = useToast();
  const { t } = useI18n();
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
    const timer = setTimeout(load, 300);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q]);

  const remove = async (jobId: number) => {
    try {
      await api.delete(`/api/jobs/${jobId}/save`);
      toast(t("Removed from saved jobs"));
      load();
    } catch (e: any) {
      toast(e.message, "error");
    }
  };

  /** Write the tick's fields into the saved row and the open dialog copy together. */
  const patchApplied = useCallback((id: number, fields: Partial<Job>) => {
    setItems((xs) => (xs ?? []).map((x) => (x.job.id === id ? { ...x, job: { ...x.job, ...fields } } : x)));
    setSelected((cur) => (cur && cur.id === id ? { ...cur, ...fields } : cur));
  }, []);
  const setApplied = useAppliedMark(patchApplied);

  return (
    <div className="animate-fade-in space-y-5">
      <PageHeader
        eyebrow={t("Shortlist")}
        title={t("Saved Jobs")}
        description={t("Jobs you bookmarked for later — review them, prep the application, and apply when you are ready.")}
        actions={
          <div className="relative w-full sm:w-72">
            <Search className="pointer-events-none absolute start-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              aria-label={t("Filter saved jobs")}
              placeholder={t("Filter saved jobs…")}
              value={q}
              onChange={(e) => setQ(e.target.value)}
              className="ps-10"
            />
          </div>
        }
      />

      {error && items && (
        <p className="rounded-xl border border-red-500/25 bg-red-500/[0.05] p-3 text-sm text-red-700 dark:text-red-400">
          {t("{error} — showing the last results that loaded.", { error })}{" "}
          <button className="font-semibold underline" onClick={load}>{t("Try again")}</button>
        </p>
      )}

      {error && !items ? (
        <ErrorState message={error} onRetry={load} />
      ) : items === null ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-28 rounded-2xl" />)}
        </div>
      ) : items.length === 0 ? (
        <EmptyState
          icon={BookmarkX}
          title={q ? t("No saved jobs match your filter") : t("No saved jobs yet")}
          description={q ? t("Try a different filter.") : t("Browse Find Jobs and bookmark interesting roles to see them here.")}
          action={
            !q ? (
              <Link to="/jobs" className={buttonClassName()}>{t("Find jobs")}</Link>
            ) : undefined
          }
        />
      ) : (
        <div className="space-y-3">
          {items.map((s) => (
            <article key={s.id} className="group flex flex-col gap-3 rounded-xl border border-border/80 bg-card p-4 shadow-soft transition-colors duration-200 hover:border-foreground/25 hover:bg-muted/30 sm:flex-row sm:items-center sm:p-5">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2.5">
                  {s.score !== null && (
                    <span
                      className={cn(
                        "flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-current/15 bg-muted/50 text-base font-bold tabular-nums",
                        scoreColor(s.score)
                      )}
                      title={t("Estimated match score from your profile — not a guarantee")}
                    >
                      {s.score}
                    </span>
                  )}
                  <button
                    onClick={() => setSelected(s.job)}
                    className="min-w-0 text-start text-[15px] font-semibold leading-snug transition-colors hover:text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    <span className="line-clamp-2">{s.job.title}</span>
                  </button>
                </div>
                <p className="mt-1.5 text-xs text-muted-foreground">
                  {s.job.company} · {s.job.location} {s.job.remote ? `· ${t("Remote")}` : ""} · {formatSalary(s.job)}
                </p>
                <p className="mt-1 text-[11px] text-muted-foreground">
                  {t("Saved")} {formatDate(s.saved_at)} {s.notes ? `· ${s.notes}` : ""}
                </p>
              </div>
              <div className="flex shrink-0 flex-wrap items-center gap-2">
                <AppliedMark job={s.job} onToggle={(applied) => setApplied(s.job, applied)} />
                {s.job.url && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      window.open(s.job.url, "_blank", "noopener");
                      if (marksOnApply(s.job)) setApplied(s.job, true);
                    }}
                  >
                    <Link2 className="h-4 w-4" /> {t("Apply")}
                  </Button>
                )}
                <Link to={`/assistant?job=${s.job.id}`} className={buttonClassName({ size: "sm", variant: "outline" })}>
                  <Bot className="h-4 w-4" /> {t("Assistant")}
                </Link>
                <Button size="sm" variant="ghost" onClick={() => remove(s.job.id)} title={t("Remove from saved")}>
                  <BookmarkX className="h-4 w-4" /> {t("Remove")}
                </Button>
              </div>
            </article>
          ))}
        </div>
      )}

      <JobDetailDialog job={selected} onClose={() => setSelected(null)} onChanged={load} onAppliedChange={setApplied} />
    </div>
  );
}
