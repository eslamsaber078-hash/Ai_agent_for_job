import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  Award,
  BellRing,
  Bookmark,
  Briefcase,
  CalendarClock,
  ListChecks,
  Radar,
  Search,
  UserRound,
} from "lucide-react";
import {
  Bar, BarChart, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { api } from "@/lib/api";
import { type DashboardStats } from "@/lib/types";
import { formatDate, postedLabel, scoreColor } from "@/lib/format";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/error-state";
import { StatusBadge } from "@/components/jobs/status-badge";
import { buttonClassName } from "@/components/ui/button";
import { useAuth } from "@/context/auth";
import { cn } from "@/lib/utils";

const STATUS_COLORS = ["#323847", "#434b5d", "#555e73", "#687189", "#7c85a0", "#919ab5", "#a7b0c9", "#bdc5da"];

function greeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

function StatCard({
  icon: Icon,
  label,
  value,
  to,
}: {
  icon: any;
  label: string;
  value: number | string;
  to: string;
}) {
  return (
    <Link
      to={to}
      className="group rounded-xl border border-border/80 bg-card p-4 shadow-soft transition-colors duration-200 hover:border-foreground/25 hover:bg-muted/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      <p className="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-[0.1em] text-muted-foreground">
        <Icon className="h-3.5 w-3.5" />
        {label}
      </p>
      <p className="nums mt-2 text-[26px] font-bold leading-none tracking-tight">{value}</p>
    </Link>
  );
}

export function DashboardPage() {
  const { user } = useAuth();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    setError("");
    api
      .get<DashboardStats>("/api/dashboard/stats")
      .then(setStats)
      .catch((e) => setError(e.message));
  }, [attempt]);

  if (error) {
    return <ErrorState message={error} onRetry={() => setAttempt((a) => a + 1)} />;
  }

  if (!stats) {
    return (
      <div className="space-y-6">
        <div className="space-y-3">
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-9 w-72" />
        </div>
        <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-6">
          {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-[86px] rounded-xl" />)}
        </div>
        <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-3">
          <Skeleton className="h-72 rounded-2xl lg:col-span-2" />
          <Skeleton className="h-72 rounded-2xl" />
        </div>
      </div>
    );
  }

  const chartData = stats.status_breakdown.map((s, i) => ({
    name: s.status,
    count: s.count,
    fill: STATUS_COLORS[i % STATUS_COLORS.length],
  }));
  // Every status holding the same count used to draw every bar full width, which read
  // as "100%". A little headroom plus the real number on each bar keeps it honest.
  const chartMax = Math.max(1, ...chartData.map((d) => d.count));

  const firstName = user?.full_name?.trim().split(/\s+/)[0] ?? "there";
  const today = new Date().toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long" });

  return (
    <div className="animate-fade-in space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-muted-foreground">{today}</p>
          <h1 className="mt-1 text-2xl font-bold tracking-tight sm:text-[26px]">
            {greeting()}, {firstName}
          </h1>
          <p className="mt-1.5 text-sm text-muted-foreground">
            Here is your job hunt today — every number comes from your own data.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link to="/jobs" className={buttonClassName()}>
            <Search className="h-4 w-4" /> Find jobs
          </Link>
          <Link to="/matches" className={buttonClassName({ variant: "outline" })}>
            <Radar className="h-4 w-4" /> AI matches
          </Link>
        </div>
      </div>

      {!stats.profile_complete && (
        <div className="flex flex-wrap items-center gap-3 rounded-xl border border-amber-500/25 bg-amber-500/[0.06] p-4 sm:p-5">
          <UserRound className="h-[18px] w-[18px] shrink-0 text-amber-600 dark:text-amber-400" />
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold">Your profile needs a little more detail</p>
            <p className="text-xs leading-relaxed text-muted-foreground">
              Match scores get sharper when your skills and experience are filled in.
            </p>
          </div>
          <Link to="/profile" className={buttonClassName({ size: "sm", variant: "outline" })}>
            Complete profile
          </Link>
        </div>
      )}

      <div className="grid grid-cols-2 gap-3 sm:gap-4 md:grid-cols-3 xl:grid-cols-6">
        <StatCard icon={Search} label="Jobs discovered" value={stats.total_jobs} to="/jobs" />
        <StatCard icon={Award} label="Matches 70+" value={stats.high_match_jobs} to="/matches" />
        <StatCard icon={Bookmark} label="Saved jobs" value={stats.saved_jobs} to="/saved" />
        <StatCard icon={ListChecks} label="Applications" value={stats.applications} to="/applications" />
        <StatCard icon={CalendarClock} label="Interviews" value={stats.interviews} to="/applications" />
        <StatCard icon={Briefcase} label="Offers" value={stats.offers} to="/applications" />
      </div>

      {stats.stale_hidden_jobs > 0 && (
        <p className="text-xs text-muted-foreground">
          {stats.stale_hidden_jobs} posting(s) are hidden from the lists because their source no longer advertises them —
          the numbers above count live openings only.
        </p>
      )}

      <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader className="flex-row items-start justify-between space-y-0 pb-3">
            <div className="space-y-1.5">
              <CardTitle>Best matching jobs</CardTitle>
              <CardDescription>Highest estimated scores for your profile</CardDescription>
            </div>
            <Link to="/matches" className="inline-flex items-center gap-1 text-xs font-semibold text-muted-foreground transition-colors hover:text-foreground">
              View all <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </CardHeader>
          <CardContent>
            {stats.best_matches.length === 0 ? (
              <p className="rounded-xl border border-dashed p-6 text-center text-sm text-muted-foreground">
                Complete your profile to see your best matches.
              </p>
            ) : (
              <div className="space-y-2">
                {stats.best_matches.map((m, index) => (
                  <Link
                    key={m.job_id}
                    to="/matches"
                    className="group flex items-center gap-3 rounded-xl border border-transparent p-2.5 transition-colors hover:border-border hover:bg-muted/40"
                  >
                    <span className="w-5 shrink-0 text-center text-xs font-semibold tabular-nums text-muted-foreground/70">
                      {index + 1}
                    </span>
                    <span
                      className={cn(
                        "nums w-7 shrink-0 text-right text-[15px] font-bold tabular-nums tracking-tight",
                        scoreColor(m.score)
                      )}
                    >
                      {m.score}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-semibold">{m.title}</p>
                      <p className="truncate text-xs text-muted-foreground">
                        {m.company} · {m.location} {m.remote ? "· Remote" : ""}
                      </p>
                    </div>
                    <ArrowRight className="h-4 w-4 shrink-0 text-muted-foreground/50 transition-transform group-hover:translate-x-0.5 group-hover:text-foreground" />
                  </Link>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle>Application status</CardTitle>
            <CardDescription>Where your tracked applications stand</CardDescription>
          </CardHeader>
          <CardContent>
            {chartData.length === 0 ? (
              <p className="rounded-xl border border-dashed p-6 text-center text-sm text-muted-foreground">
                No applications tracked yet.
              </p>
            ) : (
              <div style={{ height: chartData.length * 44 + 20 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chartData} layout="vertical" margin={{ left: 0, right: 24, top: 4, bottom: 4 }}>
                    <XAxis type="number" hide domain={[0, Math.ceil(chartMax * 1.15)]} />
                    <YAxis type="category" dataKey="name" width={82} axisLine={false} tickLine={false}
                           tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} />
                    <Tooltip
                      cursor={{ fill: "hsl(var(--muted) / 0.6)" }}
                      contentStyle={{
                        background: "hsl(var(--card))",
                        border: "1px solid hsl(var(--border))",
                        borderRadius: 12,
                        fontSize: 12,
                        color: "hsl(var(--foreground))",
                        boxShadow: "0 12px 30px -14px rgb(18 20 27 / 0.22)",
                      }}
                    />
                    <Bar dataKey="count" radius={[0, 6, 6, 0]} barSize={16}>
                      {chartData.map((d, i) => (
                        <Cell key={i} fill={d.fill} />
                      ))}
                      <LabelList
                        dataKey="count"
                        position="right"
                        offset={6}
                        style={{ fontSize: 11, fontWeight: 600, fill: "hsl(var(--muted-foreground))" }}
                      />
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader className="flex-row items-start justify-between space-y-0 pb-3">
            <div className="space-y-1.5">
              <CardTitle>Recent discoveries</CardTitle>
              <CardDescription>Latest jobs added to your database</CardDescription>
            </div>
            <Link to="/jobs" className="inline-flex items-center gap-1 text-xs font-semibold text-muted-foreground transition-colors hover:text-foreground">
              Browse <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </CardHeader>
          <CardContent className="space-y-1">
            {stats.recent_jobs.length === 0 ? (
              <p className="rounded-xl border border-dashed p-6 text-center text-sm text-muted-foreground">
                No jobs imported yet — start with Find Jobs.
              </p>
            ) : (
              stats.recent_jobs.map((j) => (
                <div key={j.id} className="flex items-center gap-3 rounded-xl border border-transparent p-2.5 transition-colors hover:border-border hover:bg-muted/40">
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">{j.title}</p>
                    <p className="truncate text-xs text-muted-foreground">{j.company} · {j.location}</p>
                  </div>
                  <span className="shrink-0 text-[11px] text-muted-foreground">{postedLabel(j)}</span>
                </div>
              ))
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle>Follow-ups due</CardTitle>
            <CardDescription>Soonest first — overdue ones are marked</CardDescription>
          </CardHeader>
          <CardContent>
            {stats.upcoming_follow_ups.length === 0 ? (
              <div className="flex flex-col items-center py-8 text-center">
                <BellRing className="h-5 w-5 text-muted-foreground/70" />
                <p className="mt-3 max-w-xs text-sm leading-relaxed text-muted-foreground">
                  No follow-ups scheduled yet. Set a follow-up date on an application in the tracker.
                </p>
              </div>
            ) : (
              <div className="space-y-1">
                {stats.upcoming_follow_ups.map((a) => (
                  <div key={a.id} className="flex items-center gap-3 rounded-xl border border-transparent p-2.5 transition-colors hover:border-border hover:bg-muted/40">
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium">{a.job.title}</p>
                      <p className="truncate text-xs text-muted-foreground">{a.job.company}</p>
                    </div>
                    <StatusBadge status={a.status} />
                    {new Date(a.follow_up_date!).getTime() < Date.now() && (
                      <span className="shrink-0 text-[11px] font-semibold text-red-600 dark:text-red-400">Overdue</span>
                    )}
                    <span className="shrink-0 text-[11px] font-semibold text-foreground">{formatDate(a.follow_up_date)}</span>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
