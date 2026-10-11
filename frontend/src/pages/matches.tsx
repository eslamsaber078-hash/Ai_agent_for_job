import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Bot, CheckCircle2, Radar, XCircle } from "lucide-react";
import { api, qs } from "@/lib/api";
import { type MatchList, type MatchResult } from "@/lib/types";
import { formatSalary, scoreColor, timeAgo } from "@/lib/format";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { ScoreBar } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";

export function MatchesPage() {
  const [data, setData] = useState<MatchList | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [minScore, setMinScore] = useState(0);
  const [q, setQ] = useState("");
  const [detail, setDetail] = useState<MatchResult | null>(null);
  const reqId = useRef(0);

  const load = () => {
    const my = ++reqId.current;
    setLoading(true);
    setError(null);
    api
      .get<MatchList>(`/api/matches${qs({ min_score: minScore, limit: 100, q })}`)
      .then((d) => { if (my === reqId.current) setData(d); })
      .catch((e) => { if (my === reqId.current) setError(e.message); })
      .finally(() => { if (my === reqId.current) setLoading(false); });
  };

  useEffect(() => {
    const t = setTimeout(load, 300);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [minScore, q]);

  if (error && !data) {
    return (
      <div className="space-y-4">
        <h1 className="text-xl font-bold">AI Job Matches</h1>
        <ErrorState message={error} onRetry={load} busy={loading} />
      </div>
    );
  }

  if (loading && !data) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-72" />
        {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-28" />)}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-bold">AI Job Matches</h1>
        <p className="text-sm text-muted-foreground">
          Transparent match estimates (0–100) computed from your profile. Best fit first; inside the same score the freshest posting wins. Scores are estimates, not guarantees.
        </p>
      </div>

      {data?.profile_empty && (
        <div className="flex flex-wrap items-center gap-3 rounded-xl border border-amber-500/30 bg-amber-500/10 p-4">
          <Radar className="h-5 w-5 shrink-0 text-amber-600 dark:text-amber-400" />
          <p className="flex-1 text-sm">Your profile is empty, so every score is 0. Fill in your skills first.</p>
          <Link to="/profile"><Button size="sm">Go to Profile</Button></Link>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-3 rounded-xl border bg-card p-4">
        <input
          type="text"
          placeholder="Filter by title or company…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          className="h-9 w-64 rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
        <label className="flex items-center gap-2 text-sm text-muted-foreground">
          Minimum score:
          <select
            value={minScore}
            onChange={(e) => setMinScore(Number(e.target.value))}
            className="h-9 rounded-md border border-input bg-background px-2 text-sm"
          >
            <option value={0}>Any</option>
            <option value={50}>50+</option>
            <option value={60}>60+</option>
            <option value={70}>70+</option>
            <option value={80}>80+</option>
          </select>
        </label>
        <span className="text-sm text-muted-foreground">
          {data
            ? data.total > data.items.length
              ? `Showing the top ${data.items.length} of ${data.total} scored jobs`
              : `${data.total} jobs scored`
            : ""}
        </span>
      </div>

      {error && data && (
        <p className="rounded-lg border border-red-500/40 bg-red-500/5 p-3 text-sm text-red-600 dark:text-red-400">
          {error} — showing the last results that loaded.{" "}
          <button className="underline" onClick={load}>Try again</button>
        </p>
      )}

      {!data || data.items.length === 0 ? (
        <EmptyState
          icon={Radar}
          title="No matches at this threshold"
          description="Lower the minimum score or complete your profile to get better matches."
        />
      ) : (
        <div className="space-y-3">
          {data.items.map((m) => (
            <div key={m.job_id} className="flex flex-col gap-3 rounded-xl border bg-card p-4 shadow-sm sm:flex-row sm:items-center">
              <div className="flex items-center gap-3 sm:w-24 sm:shrink-0 sm:flex-col sm:items-start">
                <span className={`text-3xl font-bold ${scoreColor(m.score)}`}>{m.score}</span>
                <span className="text-[10px] text-muted-foreground">match estimate</span>
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="text-sm font-semibold">{m.job?.title}</p>
                  {m.ai_enhanced && <Badge variant="default">AI enhanced</Badge>}
                </div>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  {m.job?.company} · {m.job?.location} {m.job?.remote ? "· Remote" : ""} · {m.job?.experience_level || "level n/a"} · {formatSalary(m.job ?? { salary_min: null, salary_max: null, salary_currency: null })} · posted {timeAgo(m.job?.posted_date ?? null)}
                </p>
                <div className="mt-2 max-w-md">
                  <ScoreBar value={m.score} />
                </div>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {m.matched_skills.slice(0, 6).map((s) => (
                    <Badge key={s} variant="success"><CheckCircle2 className="mr-1 h-3 w-3" />{s}</Badge>
                  ))}
                  {m.missing_skills.slice(0, 6).map((s) => (
                    <Badge key={s} variant="danger"><XCircle className="mr-1 h-3 w-3" />{s}</Badge>
                  ))}
                </div>
              </div>
              <div className="flex shrink-0 gap-2">
                <Button size="sm" variant="outline" onClick={() => setDetail(m)}>Why this score?</Button>
                <Link to={`/assistant?job=${m.job_id}`}>
                  <Button size="sm"><Bot className="h-4 w-4" /> Assistant</Button>
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}

      <Dialog open={!!detail} onClose={() => setDetail(null)} wide
              title={detail?.job ? `${detail.job.title} — match breakdown` : ""}
              description="How the estimate was calculated">
        {detail && (
          <div className="space-y-4">
            <div className="flex items-center gap-3">
              <span className={`text-4xl font-bold ${scoreColor(detail.score)}`}>{detail.score}</span>
              <div className="flex-1">
                <ScoreBar value={detail.score} />
                <p className="mt-1 text-[11px] text-muted-foreground">Deterministic scoring from your profile. Treat as an estimate.</p>
              </div>
            </div>
            <div className="space-y-2">
              {detail.factors.map((f) => (
                <div key={f.label} className="rounded-lg border p-3">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-medium">{f.label}</p>
                    <span className={`text-sm font-bold ${scoreColor(f.score)}`}>{f.score}/100</span>
                  </div>
                  <p className="mt-0.5 text-xs text-muted-foreground">{f.detail}</p>
                  <div className="mt-1.5">
                    <ScoreBar value={f.score} />
                  </div>
                </div>
              ))}
            </div>
            <div className="rounded-lg bg-muted/40 p-4 text-sm">
              <p><span className="font-medium">Why it matches:</span> {detail.why_match}</p>
              <p className="mt-2"><span className="font-medium">Concerns:</span> {detail.concerns}</p>
            </div>
            <div>
              <p className="text-sm font-medium">Suggested next steps</p>
              <ul className="mt-1.5 list-inside list-disc space-y-1 text-sm text-muted-foreground">
                {detail.next_steps.map((s, i) => <li key={i}>{s}</li>)}
              </ul>
            </div>
          </div>
        )}
      </Dialog>
    </div>
  );
}
