import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Award, BellRing, Bookmark, Briefcase, CalendarClock, ListChecks, Radar, Search, UserRound } from "lucide-react";
import {
  Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { api } from "@/lib/api";
import { type DashboardStats } from "@/lib/types";
import { formatDate, scoreColor } from "@/lib/format";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/error-state";
import { StatusBadge } from "@/components/jobs/status-badge";
import { Button } from "@/components/ui/button";

const STATUS_COLORS = ["#0a0a0a", "#2e2e2e", "#4f4f4f", "#707070", "#8d8d8d", "#a8a8a8", "#c2c2c2", "#d6d6d6"];

function StatCard({ icon: Icon, label, value, to }: { icon: any; label: string; value: number | string; to?: string }) {
  const inner = (
    <Card className="min-w-0 transition-shadow hover:shadow-md">
      <CardContent className="flex items-center gap-4 p-4">
        <div className="shrink-0 rounded-lg bg-primary/10 p-2.5 text-primary">
          <Icon className="h-5 w-5" />
        </div>
        <div className="min-w-0">
          <p className="text-2xl font-bold leading-none">{value}</p>
          <p className="mt-1 text-xs text-muted-foreground">{label}</p>
        </div>
      </CardContent>
    </Card>
  );
  return to ? <Link to={to} className="min-w-0">{inner}</Link> : inner;
}

export function DashboardPage() {
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
      <div className="space-y-4">
        <Skeleton className="h-24 w-full" />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Skeleton className="h-48" />
          <Skeleton className="h-48" />
          <Skeleton className="h-48" />
        </div>
      </div>
    );
  }

  const chartData = stats.status_breakdown.map((s, i) => ({
    name: s.status,
    count: s.count,
    fill: STATUS_COLORS[i % STATUS_COLORS.length],
  }));

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold">Dashboard</h1>
          <p className="text-sm text-muted-foreground">Your job hunt at a glance — all numbers come from your real data.</p>
        </div>
        <div className="flex gap-2">
          <Link to="/jobs">
            <Button size="sm"><Search className="h-4 w-4" /> Find jobs</Button>
          </Link>
          <Link to="/matches">
            <Button size="sm" variant="outline"><Radar className="h-4 w-4" /> AI matches</Button>
          </Link>
        </div>
      </div>

      {!stats.profile_complete && (
        <div className="flex flex-wrap items-center gap-3 rounded-xl border border-amber-500/30 bg-amber-500/10 p-4">
          <UserRound className="h-5 w-5 shrink-0 text-amber-600 dark:text-amber-400" />
          <p className="flex-1 text-sm">
            Your profile is incomplete, so match scores may be inaccurate. Add your skills and experience to get real estimates.
          </p>
          <Link to="/profile">
            <Button size="sm" variant="outline">Complete profile</Button>
          </Link>
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-6">
        <StatCard icon={Search} label="Jobs discovered" value={stats.total_jobs} to="/jobs" />
        <StatCard icon={Award} label="High match (70+)" value={stats.high_match_jobs} to="/matches" />
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

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="min-w-0 lg:col-span-2">
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Best matching jobs</CardTitle>
            <CardDescription>Highest estimated match scores for your profile</CardDescription>
          </CardHeader>
          <CardContent>
            {stats.best_matches.length === 0 ? (
              <p className="py-6 text-center text-sm text-muted-foreground">
                Complete your profile to see your best matches.
              </p>
            ) : (
              <div className="space-y-2">
                {stats.best_matches.map((m) => (
                  <div key={m.job_id} className="flex items-center gap-3 rounded-lg border p-3">
                    <span className={`w-12 shrink-0 text-center text-lg font-bold ${scoreColor(m.score)}`}>
                      {m.score}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium">{m.title}</p>
                      <p className="truncate text-xs text-muted-foreground">
                        {m.company} · {m.location} {m.remote ? "· Remote" : ""}
                      </p>
                    </div>
                    <Link to="/matches" className="shrink-0 text-xs font-medium text-primary hover:underline">
                      Details
                    </Link>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="min-w-0">
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Application status</CardTitle>
            <CardDescription>Breakdown of your tracked applications</CardDescription>
          </CardHeader>
          <CardContent>
            {chartData.length === 0 ? (
              <p className="py-6 text-center text-sm text-muted-foreground">No applications tracked yet.</p>
            ) : (
              <div className="h-52">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chartData} layout="vertical" margin={{ left: 8, right: 8 }}>
                    <XAxis type="number" hide />
                    <YAxis type="category" dataKey="name" width={78} axisLine={false} tickLine={false}
                           tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} />
                    <Tooltip cursor={{ fill: "hsl(var(--muted))" }} />
                    <Bar dataKey="count" radius={[0, 4, 4, 0]} barSize={18}>
                      {chartData.map((d, i) => (
                        <Cell key={i} fill={d.fill} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="min-w-0">
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Recent discoveries</CardTitle>
            <CardDescription>Latest jobs added to your database</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {stats.recent_jobs.map((j) => (
              <div key={j.id} className="flex items-center gap-3 rounded-lg border p-3">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">{j.title}</p>
                  <p className="truncate text-xs text-muted-foreground">{j.company} · {j.location}</p>
                </div>
                <span className="shrink-0 text-xs text-muted-foreground">{formatDate(j.posted_date)}</span>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card className="min-w-0">
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Follow-ups due</CardTitle>
            <CardDescription>Soonest first — overdue ones are marked</CardDescription>
          </CardHeader>
          <CardContent>
            {stats.upcoming_follow_ups.length === 0 ? (
              <div className="flex flex-col items-center py-6 text-center">
                <BellRing className="h-6 w-6 text-muted-foreground" />
                <p className="mt-2 text-sm text-muted-foreground">
                  No follow-ups scheduled yet. Set a follow-up date on an application in the tracker.
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                {stats.upcoming_follow_ups.map((a) => (
                  <div key={a.id} className="flex items-center gap-3 rounded-lg border p-3">
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium">{a.job.title}</p>
                      <p className="truncate text-xs text-muted-foreground">{a.job.company}</p>
                    </div>
                    <StatusBadge status={a.status} />
                    {new Date(a.follow_up_date!).getTime() < Date.now() && (
                      <span className="shrink-0 text-xs font-medium text-red-600 dark:text-red-400">Overdue</span>
                    )}
                    <span className="shrink-0 text-xs font-medium text-primary">{formatDate(a.follow_up_date)}</span>
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
