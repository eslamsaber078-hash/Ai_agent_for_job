import { useEffect, useState } from "react";
import { History, Loader2, Play, Save, Settings2 } from "lucide-react";
import { api } from "@/lib/api";
import { SOURCE_LABELS, type AutomationRun, type JobSourceSite, type SearchPrefs } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/error-state";
import { Switch } from "@/components/ui/switch";
import { formatDateTime } from "@/lib/format";
import { useToast } from "@/context/toast";

// A stored value outside the preset list must still show as selected.
function withCurrent(presets: number[], current: number): number[] {
  return [...new Set([...presets, current])].sort((a, b) => a - b);
}

function intervalLabel(n: number): string {
  if (n % 1440 === 0) return n === 1440 ? "Every 24 hours" : `Every ${n / 1440} days`;
  if (n % 60 === 0) return n === 60 ? "Every hour" : `Every ${n / 60} hours`;
  return `Every ${n} minutes`;
}

const AGE_PRESETS = [7, 14, 30, 45, 60, 90];

function CommaInput({ label, values, onChange, placeholder }: { label: string; values: string[]; onChange: (v: string[]) => void; placeholder: string }) {
  const [text, setText] = useState(values.join(", "));
  useEffect(() => setText(values.join(", ")), [values]);
  return (
    <div>
      <p className="mb-1.5 text-sm font-medium">{label}</p>
      <input
        className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        value={text}
        placeholder={placeholder}
        onBlur={() => onChange(text.split(",").map((x) => x.trim()).filter(Boolean))}
        onChange={(e) => setText(e.target.value)}
      />
      <p className="mt-1 text-[11px] text-muted-foreground">Comma separated, e.g. Flutter Developer, Python Developer</p>
    </div>
  );
}

export function AutomationPage() {
  const { toast } = useToast();
  const [prefs, setPrefs] = useState<SearchPrefs | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [runs, setRuns] = useState<AutomationRun[]>([]);
  const [sites, setSites] = useState<JobSourceSite[]>([]);
  const [saving, setSaving] = useState(false);
  const [running, setRunning] = useState(false);
  const [expandedRun, setExpandedRun] = useState<number | null>(null);

  const loadRuns = () => {
    api.get<AutomationRun[]>("/api/automation/runs").then(setRuns).catch(() => {});
  };

  const load = () => {
    setError(null);
    api
      .get<SearchPrefs>("/api/automation/settings")
      .then(setPrefs)
      .catch((e) => setError(e.message));
    api.get<JobSourceSite[]>("/api/jobs/sources").then(setSites).catch(() => {});
    loadRuns();
  };

  useEffect(load, []);

  const save = async () => {
    if (!prefs) return;
    setSaving(true);
    try {
      const updated = await api.put<SearchPrefs>("/api/automation/settings", prefs);
      setPrefs(updated);
      toast("Automation settings saved");
    } catch (e: any) {
      toast(e.message, "error");
    } finally {
      setSaving(false);
    }
  };

  const runNow = async () => {
    setRunning(true);
    try {
      const r = await api.post<{ jobs_found: number; status: string; log: string }>("/api/automation/run", prefs?.sources ?? []);
      toast(r.status === "success" ? `Search finished — ${r.jobs_found} new jobs` : `Search failed: ${r.log}`, r.status === "success" ? "success" : "error");
      loadRuns();
    } catch (e: any) {
      toast(e.message, "error");
    } finally {
      setRunning(false);
    }
  };

  if (!prefs) {
    return error
      ? <div className="space-y-4"><h1 className="text-xl font-bold">Automation Settings</h1><ErrorState message={error} onRetry={load} /></div>
      : <Skeleton className="h-96" />;
  }

  const toggleSource = (name: string) => {
    const on = prefs.sources.includes(name);
    setPrefs({ ...prefs, sources: on ? prefs.sources.filter((s) => s !== name) : [...prefs.sources, name] });
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold">Automation Settings</h1>
        <p className="text-sm text-muted-foreground">
          Scheduled searches run in the backend process. Keep the backend running for automation to work.
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-base"><Settings2 className="h-4 w-4" /> Search configuration</CardTitle>
            <CardDescription>What the scheduled (and manual) search looks for</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between rounded-lg border p-3">
              <div>
                <p className="text-sm font-medium">Scheduled search</p>
                <p className="text-xs text-muted-foreground">
                  {prefs.scheduler_running ? `Active — runs every ${prefs.interval_minutes} minutes` : "Inactive"}
                </p>
              </div>
              <Switch checked={prefs.enabled} onChange={(v) => setPrefs({ ...prefs, enabled: v })} />
            </div>

            <CommaInput label="Job titles" values={prefs.titles} onChange={(v) => setPrefs({ ...prefs, titles: v })} placeholder="Flutter Developer, Python Developer" />
            <CommaInput label="Skills" values={prefs.skills} onChange={(v) => setPrefs({ ...prefs, skills: v })} placeholder="Flutter, Python, C#" />
            <CommaInput label="Locations" values={prefs.locations} onChange={(v) => setPrefs({ ...prefs, locations: v })} placeholder="Cairo, Remote" />

            <div className="grid gap-4 sm:grid-cols-3">
              <div>
                <p className="mb-1.5 text-sm font-medium">Search interval</p>
                <Select value={String(prefs.interval_minutes)} onChange={(e) => setPrefs({ ...prefs, interval_minutes: Number(e.target.value) })}>
                  {withCurrent([15, 30, 60, 360, 720, 1440], prefs.interval_minutes).map((n) => (
                    <option key={n} value={n}>{intervalLabel(n)}</option>
                  ))}
                </Select>
              </div>
              <div>
                <p className="mb-1.5 text-sm font-medium">Min. match score</p>
                <Select value={String(prefs.min_match_score)} onChange={(e) => setPrefs({ ...prefs, min_match_score: Number(e.target.value) })}>
                  {withCurrent([0, 30, 50, 60, 70, 80], prefs.min_match_score).map((n) => (
                    <option key={n} value={n}>{n}+</option>
                  ))}
                </Select>
              </div>
              <div>
                <p className="mb-1.5 text-sm font-medium">Max job age</p>
                <Select value={String(prefs.max_age_days)} onChange={(e) => setPrefs({ ...prefs, max_age_days: Number(e.target.value) })}>
                  {withCurrent(AGE_PRESETS, prefs.max_age_days).map((n) => (
                    <option key={n} value={n}>Newer than {n} days</option>
                  ))}
                </Select>
              </div>
            </div>

            <div className="flex items-center justify-between rounded-lg border p-3">
              <div>
                <p className="text-sm font-medium">Remote only</p>
                <p className="text-xs text-muted-foreground">Only fetch jobs marked as remote</p>
              </div>
              <Switch checked={prefs.remote_only} onChange={(v) => setPrefs({ ...prefs, remote_only: v })} />
            </div>

            <div>
              <p className="mb-1.5 text-sm font-medium">Job sources</p>
              <div className="space-y-1.5">
                {(sites.length ? sites : Object.keys(SOURCE_LABELS).map((name) => ({
                  name, label: SOURCE_LABELS[name], enabled: true, requires_key: false, live_jobs: 0,
                }))).map((s) => (
                  <label key={s.name} className="flex flex-wrap items-center gap-2 rounded-lg border p-2.5 text-sm">
                    <input type="checkbox" className="h-4 w-4 shrink-0" checked={prefs.sources.includes(s.name)} onChange={() => toggleSource(s.name)} />
                    <span className="min-w-0 font-medium">{s.label}</span>
                    <span className="ml-auto shrink-0 text-xs text-muted-foreground">
                      {s.live_jobs ? `${s.live_jobs} live postings` : "no postings imported yet"}
                    </span>
                  </label>
                ))}
              </div>
              <p className="mt-1.5 text-[11px] text-muted-foreground">
                Ticked sites are searched by the schedule and by "Import from all ticked sites" in Find Jobs. To pull one site alone, use its own button there.
              </p>
            </div>

            <div className="flex gap-2 border-t pt-4">
              <Button onClick={save} disabled={saving}>
                {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                {saving ? "Saving…" : "Save settings"}
              </Button>
              <Button variant="outline" onClick={runNow} disabled={running}>
                {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                {running ? "Running…" : "Run search now"}
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-base"><History className="h-4 w-4" /> Run history & logs</CardTitle>
            <CardDescription>Latest automation runs, newest first</CardDescription>
          </CardHeader>
          <CardContent>
            {runs.length === 0 ? (
              <p className="py-6 text-center text-sm text-muted-foreground">
                No runs yet. Press "Run search now" to trigger the first one.
              </p>
            ) : (
              <div className="space-y-2">
                {runs.slice(0, 10).map((r) => (
                  <div key={r.id} className="rounded-lg border p-3">
                    <button className="flex w-full items-center gap-2 text-left" onClick={() => setExpandedRun(expandedRun === r.id ? null : r.id)}>
                      <Badge variant={r.status === "success" ? "success" : "danger"}>{r.status}</Badge>
                      <Badge variant="outline">{r.trigger}</Badge>
                      <span className="text-xs text-muted-foreground">{formatDateTime(r.started_at)}</span>
                      <span className="ml-auto text-xs font-medium">{r.jobs_found} new jobs</span>
                    </button>
                    {expandedRun === r.id && (
                      <pre className="mt-2 whitespace-pre-wrap rounded bg-muted p-2 text-[11px] leading-relaxed">
                        {r.log || r.error || "No log output."}
                      </pre>
                    )}
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
