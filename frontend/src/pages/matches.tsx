import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Bot, CheckCircle2, ExternalLink, Radar, Sparkles, XCircle } from "lucide-react";
import { api, qs } from "@/lib/api";
import { type Job, type MatchList, type MatchResult, sourceLabel } from "@/lib/types";
import { formatSalary, postedLabel, scoreColor } from "@/lib/format";
import { Badge } from "@/components/ui/badge";
import { Button, buttonClassName } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { ScoreBar } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/layout/page-header";
import { JobDetailDialog } from "@/components/jobs/job-detail";
import { useToast } from "@/context/toast";
import { useI18n } from "@/context/i18n";
import { cn } from "@/lib/utils";

const SCORE_OPTIONS = [
  { value: 0, label: "Any" },
  { value: 50, label: "50+" },
  { value: 60, label: "60+" },
  { value: 70, label: "70+" },
  { value: 80, label: "80+" },
];

export function MatchesPage() {
  const { toast } = useToast();
  const { t, tt, lang } = useI18n();
  const [data, setData] = useState<MatchList | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [minScore, setMinScore] = useState(0);
  const [q, setQ] = useState("");
  const [detail, setDetail] = useState<MatchResult | null>(null);
  const [openJob, setOpenJob] = useState<Job | null>(null);
  const reqId = useRef(0);
  const detailId = useRef(0);

  // The match list carries a short summary of each job; the full posting (description,
  // apply link, save state) only comes from /api/jobs/{id}.
  const openDetails = (job_id: number) => {
    const my = ++detailId.current;
    api.get<Job>(`/api/jobs/${job_id}`)
      .then((d) => { if (my === detailId.current) setOpenJob(d); })
      .catch((e) => { if (my === detailId.current) toast(e.message, "error"); });
  };

  // The dialog hands back the job it just changed (saved / tracked); re-read that
  // one posting so its bookmark reflects the server instead of the old list copy.
  const refreshOpenJob = (job: Job) => {
    api.get<Job>(`/api/jobs/${job.id}`)
      .then((fresh) => setOpenJob((cur) => (cur && cur.id === fresh.id ? fresh : cur)))
      .catch(() => {});
  };

  const load = () => {
    const my = ++reqId.current;
    setLoading(true);
    setError(null);
    api
      .get<MatchList>(`/api/matches${qs({ min_score: minScore, limit: 100, q, lang })}`)
      .then((d) => { if (my === reqId.current) setData(d); })
      .catch((e) => { if (my === reqId.current) setError(e.message); })
      .finally(() => { if (my === reqId.current) setLoading(false); });
  };

  useEffect(() => {
    const timer = setTimeout(load, 300);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [minScore, q, lang]);

  if (error && !data) {
    return (
      <div className="space-y-4">
        <PageHeader eyebrow={t("Ranking")} title={t("AI Job Matches")} />
        <ErrorState message={error} onRetry={load} busy={loading} />
      </div>
    );
  }

  if (loading && !data) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-72" />
        <Skeleton className="h-20 rounded-2xl" />
        {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-36 rounded-2xl" />)}
      </div>
    );
  }

  return (
    <div className="animate-fade-in space-y-5">
      <PageHeader
        eyebrow={t("Ranking")}
        title={t("AI Job Matches")}
        description={t("Transparent match estimates (0–100) computed from your profile. Best fit first; inside the same score the freshest posting wins. Scores are estimates, not guarantees.")}
      />

      {data?.profile_empty && (
        <div className="flex flex-wrap items-center gap-3 rounded-xl border border-amber-500/25 bg-amber-500/[0.06] p-4 sm:p-5">
          <Radar className="h-[18px] w-[18px] shrink-0 text-amber-600 dark:text-amber-400" />
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold">{t("Your profile is empty")}</p>
            <p className="text-xs text-muted-foreground">{t("Every score is 0 until you add your skills.")}</p>
          </div>
          <Link to="/profile" className={buttonClassName({ size: "sm" })}>{t("Go to Profile")}</Link>
        </div>
      )}

      <div className="flex flex-col gap-3 rounded-xl border border-border/80 bg-card p-3.5 shadow-soft sm:flex-row sm:items-center">
        <div className="relative min-w-0 flex-1">
          <Radar className="pointer-events-none absolute start-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            aria-label={t("Filter matches by title or company")}
            placeholder={t("Filter by title or company…")}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            className="ps-10"
          />
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="me-1 text-[11px] font-medium uppercase tracking-[0.12em] text-muted-foreground">{t("Min score")}</span>
          {SCORE_OPTIONS.map((option) => (
            <button
              key={option.value}
              type="button"
              aria-pressed={minScore === option.value}
              onClick={() => setMinScore(option.value)}
              className={cn(
                "nums h-8 rounded-md border px-2.5 text-xs font-medium transition-colors",
                minScore === option.value
                  ? "border-primary bg-primary text-primary-foreground"
                  : "border-border bg-card text-muted-foreground hover:bg-muted hover:text-foreground"
              )}
            >
              {t(option.label)}
            </button>
          ))}
        </div>
        <span className="shrink-0 text-xs text-muted-foreground sm:border-s sm:border-border/70 sm:ps-3">
          {data
            ? data.total > data.items.length
              ? t("Top {n} of {total}", { n: data.items.length, total: data.total })
              : t("{total} scored", { total: data.total })
            : ""}
        </span>
      </div>

      {error && data && (
        <p className="rounded-xl border border-red-500/25 bg-red-500/[0.05] p-3 text-sm text-red-700 dark:text-red-400">
          {t("{error} — showing the last results that loaded.", { error })}{" "}
          <button className="font-semibold underline" onClick={load}>{t("Try again")}</button>
        </p>
      )}

      {!data || data.items.length === 0 ? (
        <EmptyState
          icon={Radar}
          title={t("No matches at this threshold")}
          description={t("Lower the minimum score or complete your profile to get better matches.")}
        />
      ) : (
        <div className="space-y-3">
          {data.items.map((m) => (
            <article
              key={m.job_id}
              className="group flex flex-col gap-4 rounded-xl border border-border/80 bg-card p-4 shadow-soft transition-colors duration-200 hover:border-foreground/25 hover:bg-muted/30 sm:flex-row sm:p-5"
            >
              <div className="flex shrink-0 items-baseline gap-2 sm:w-[74px] sm:flex-col sm:items-start sm:gap-1">
                <span className={cn("nums text-[26px] font-bold leading-none tracking-tight", scoreColor(m.score))}>
                  {m.score}
                </span>
                <span className="text-[10px] font-medium uppercase tracking-[0.12em] text-muted-foreground">{t("match")}</span>
              </div>

              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    onClick={() => openDetails(m.job_id)}
                    title={t("Open the full posting and its apply link")}
                    className="block max-w-full text-start text-[15px] font-semibold leading-snug transition-colors hover:text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    {m.job?.title}
                  </button>
                  {m.ai_enhanced && (
                    <Badge variant="default"><Sparkles className="h-3 w-3" /> {t("AI enhanced")}</Badge>
                  )}
                </div>
                <p className="mt-1 text-xs text-muted-foreground">
                  {m.job?.company} · {m.job?.location} {m.job?.remote ? `· ${t("Remote")}` : ""} · {tt(m.job?.experience_level ?? "") || t("level n/a")} · {formatSalary(m.job ?? { salary_min: null, salary_max: null, salary_currency: null })} · {postedLabel(m.job ?? { posted_date: null })}
                </p>
                <div className="mt-3 max-w-[260px]">
                  <ScoreBar value={m.score} />
                </div>
                {(m.matched_skills.length > 0 || m.missing_skills.length > 0) && (
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {m.matched_skills.slice(0, 6).map((s) => (
                      <Badge key={s} variant="success"><CheckCircle2 className="h-3 w-3" />{s}</Badge>
                    ))}
                    {m.missing_skills.slice(0, 6).map((s) => (
                      <Badge key={s} variant="danger"><XCircle className="h-3 w-3" />{s}</Badge>
                    ))}
                  </div>
                )}
              </div>

              <div className="flex shrink-0 flex-row gap-2 sm:flex-col sm:items-end">
                {m.job?.url && (
                  <Button size="sm" onClick={() => window.open(m.job!.url, "_blank", "noopener")}>
                    {t("Apply")} <ExternalLink className="h-3.5 w-3.5" />
                  </Button>
                )}
                <div className="flex gap-2">
                  <Button size="sm" variant="ghost" onClick={() => setDetail(m)}>{t("Why this score?")}</Button>
                  <Link to={`/assistant?job=${m.job_id}`} className={buttonClassName({ size: "sm", variant: "ghost" })}>
                    <Bot className="h-3.5 w-3.5" /> {t("Assistant")}
                  </Link>
                </div>
              </div>
            </article>
          ))}
        </div>
      )}

      <Dialog open={!!detail} onClose={() => setDetail(null)} wide
              title={detail?.job ? `${detail.job.title} — ${t("match breakdown")}` : ""}
              description={t("How the estimate was calculated")}>
        {detail && (
          <div className="space-y-5">
            <div className="flex items-center gap-4 rounded-xl border border-border/70 bg-muted/30 p-4">
              <span className={cn("text-4xl font-bold tabular-nums", scoreColor(detail.score))}>{detail.score}</span>
              <div className="flex-1">
                <ScoreBar value={detail.score} />
                <p className="mt-2 text-[11px] text-muted-foreground">{t("Deterministic scoring from your profile. Treat as an estimate.")}</p>
              </div>
            </div>
            <div className="space-y-2">
              {detail.factors.map((f) => (
                <div key={f.label} className="rounded-xl border border-border/70 p-3.5">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-semibold">{t(f.label)}</p>
                    <span className={cn("text-sm font-bold tabular-nums", scoreColor(f.score))}>{f.score}/100</span>
                  </div>
                  <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{f.detail}</p>
                  <div className="mt-2">
                    <ScoreBar value={f.score} />
                  </div>
                </div>
              ))}
            </div>
            <div className="rounded-xl border border-border/70 bg-muted/30 p-4 text-sm">
              <p><span className="font-semibold">{t("Why it matches:")}</span> {detail.why_match}</p>
              <p className="mt-2"><span className="font-semibold">{t("Concerns:")}</span> {detail.concerns}</p>
              {detail.hard_gap && (
                <p className="mt-2 rounded-lg border border-red-500/25 bg-red-500/5 px-3 py-2 text-xs leading-relaxed text-red-700 dark:text-red-400">
                  {detail.hard_gap}
                </p>
              )}
            </div>
            <div>
              <p className="text-sm font-semibold">{t("Suggested next steps")}</p>
              <ul className="mt-2 list-inside list-disc space-y-1.5 text-sm leading-relaxed text-muted-foreground">
                {detail.next_steps.map((s, i) => <li key={i}>{s}</li>)}
              </ul>
            </div>
            <div className="flex flex-wrap gap-2 border-t border-border/70 pt-4">
              {detail.job?.url && (
                <Button onClick={() => window.open(detail.job!.url, "_blank", "noopener")}>
                  {t("Apply on {board}", { board: sourceLabel(detail.job.source) })} <ExternalLink className="h-4 w-4" />
                </Button>
              )}
              <Button variant="outline" onClick={() => { const id = detail.job_id; setDetail(null); openDetails(id); }}>
                {t("Open the full posting")}
              </Button>
            </div>
          </div>
        )}
      </Dialog>

      <JobDetailDialog job={openJob} onClose={() => setOpenJob(null)} onChanged={refreshOpenJob} />
    </div>
  );
}
