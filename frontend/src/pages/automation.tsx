import { useEffect, useRef, useState } from "react";
import {
  ChevronDown,
  History,
  Loader2,
  Play,
  Save,
  X,
} from "lucide-react";
import { api } from "@/lib/api";
import {
  SOURCE_LABELS,
  type AutomationRun,
  type JobSourceSite,
  type SearchPlan,
  type SearchPrefs,
  sourceLabel,
} from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/error-state";
import { Switch } from "@/components/ui/switch";
import { PageHeader } from "@/components/layout/page-header";
import { formatDateTime } from "@/lib/format";
import { useToast } from "@/context/toast";
import { useI18n } from "@/context/i18n";
import { translate } from "@/lib/translations";
import { cn } from "@/lib/utils";

// A stored value outside the preset list must still show as selected.
function withCurrent(presets: number[], current: number): number[] {
  return [...new Set([...presets, current])].sort((a, b) => a - b);
}

function intervalLabel(n: number): string {
  if (n % 1440 === 0) return n === 1440 ? translate("Every 24 hours") : translate("Every {n} days", { n: n / 1440 });
  if (n % 60 === 0) return n === 60 ? translate("Every hour") : translate("Every {n} hours", { n: n / 60 });
  return translate("Every {n} minutes", { n });
}

const AGE_PRESETS = [7, 14, 30, 45, 60, 90];

function FieldLabel({ children }: { children: React.ReactNode }) {
  return <span className="mb-1.5 block text-xs font-semibold text-muted-foreground">{children}</span>;
}

function TermEditor({ label, hint, values, onChange, placeholder }: {
  label: string; hint: string; values: string[]; onChange: (v: string[]) => void; placeholder: string;
}) {
  const { t } = useI18n();
  const [draft, setDraft] = useState("");

  const add = (raw: string) => {
    const merged = [...values];
    for (const piece of raw.split(",")) {
      const term = piece.trim();
      if (term && !merged.some((v) => v.toLowerCase() === term.toLowerCase())) merged.push(term);
    }
    onChange(merged);
    setDraft("");
  };

  return (
    <div>
      <p className="mb-1.5 text-sm font-semibold">{label}</p>
      <div className="flex flex-wrap items-center gap-1.5 rounded-lg border border-input bg-card p-2 transition-[border-color,box-shadow] focus-within:border-ring focus-within:ring-4 focus-within:ring-ring/10">
        {values.map((v) => (
          <span key={v} className="inline-flex items-center gap-1 rounded-md bg-muted px-2 py-1 text-xs font-medium">
            {v}
            <button
              type="button"
              onClick={() => onChange(values.filter((x) => x !== v))}
              className="text-muted-foreground transition-colors hover:text-foreground"
              aria-label={t("Remove {term}", { term: v })}
            >
              <X className="h-3 w-3" />
            </button>
          </span>
        ))}
        <input
          aria-label={label}
          className="min-w-[9rem] flex-1 bg-transparent px-1 py-0.5 text-sm outline-none placeholder:text-muted-foreground/80"
          value={draft}
          placeholder={values.length ? t("Type and press Enter") : t(placeholder)}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === ",") {
              e.preventDefault();
              add(draft);
            } else if (e.key === "Backspace" && !draft && values.length) {
              onChange(values.slice(0, -1));
            }
          }}
          onBlur={() => add(draft)}
        />
      </div>
      <p className="mt-1.5 text-[11px] leading-relaxed text-muted-foreground">{hint}</p>
    </div>
  );
}

function SearchPlanPreview({ plan, inherited }: { plan: SearchPlan; inherited: boolean }) {
  const { t } = useI18n();
  return (
    <div className="space-y-3 rounded-xl border border-border/70 bg-muted/30 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <p className="text-sm font-semibold">{t("This is exactly what an import will ask for")}</p>
        <Badge variant="secondary">{t("Live preview")}</Badge>
      </div>
      {inherited && (
        <p className="text-[11px] leading-relaxed text-muted-foreground">
          {t("These titles and skills were copied from your Resume & Profile page because the automation list was empty. Saving them here pins them, and then this editor is the one that decides.")}
        </p>
      )}
      {plan.corrections.length > 0 && (
        <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-[11px]">
          <p className="font-semibold text-amber-700 dark:text-amber-400">
            {t("Spelling check — the search uses the corrected term")}
          </p>
          <ul className="mt-1.5 space-y-0.5">
            {plan.corrections.map((c) => (
              <li key={`${c.typed}->${c.corrected}`}>
                “{c.typed}” → <span className="font-semibold">{c.corrected}</span>
              </li>
            ))}
          </ul>
          <p className="mt-1.5 text-muted-foreground">
            {t("Your saved text stays exactly as you wrote it; only this search is corrected.")}
          </p>
        </div>
      )}
      {plan.terms_waiting.length > 0 && (
        <p className="text-[11px] leading-relaxed text-muted-foreground">
          {t("{n} phrases are searched per import ({list}).", { n: plan.terms.length, list: plan.terms.join(", ") })}{" "}
          {t(plan.terms_waiting.length === 1 ? "{m} more is not searched yet ({list})" : "{m} more are not searched yet ({list})", { m: plan.terms_waiting.length, list: plan.terms_waiting.slice(0, 3).join(", ") + (plan.terms_waiting.length > 3 ? ", …" : "") })}{" "}
          {t("— free a slot by removing one above.")}
        </p>
      )}
      <div className="space-y-1.5">
        {plan.sites.map((s) => (
          <div key={s.name} className="flex flex-wrap items-baseline gap-x-2 gap-y-1 border-b border-border/60 pb-2 text-xs last:border-0 last:pb-0">
            <span className="font-medium">{sourceLabel(s.name)}</span>
            <Badge variant="outline">
              {s.mode === "keyword" ? t(s.asks.length === 1 ? "{n} search" : "{n} searches", { n: s.asks.length }) : t("full listing")}
            </Badge>
            {s.asks.length > 0
              ? <span className="text-muted-foreground">{s.asks.join("  ·  ")}</span>
              : <span className="text-muted-foreground">{s.note}</span>}
            {s.needs_key && !s.key_present && (
              <span className="text-amber-600 dark:text-amber-400">{t("needs an API key — skipped until then")}</span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

export function AutomationPage() {
  const { toast } = useToast();
  const { t } = useI18n();
  const [prefs, setPrefs] = useState<SearchPrefs | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [runs, setRuns] = useState<AutomationRun[]>([]);
  const [sites, setSites] = useState<JobSourceSite[]>([]);
  const [saving, setSaving] = useState(false);
  const [running, setRunning] = useState(false);
  const [runProgress, setRunProgress] = useState<{ done: number; total: number; label: string } | null>(null);
  const [runLog, setRunLog] = useState<string[]>([]);
  const [expandedRun, setExpandedRun] = useState<number | null>(null);
  const progressThrottle = useRef(0);

  const loadRuns = () => {
    api.get<AutomationRun[]>("/api/automation/runs").then(setRuns).catch(() => {});
  };

  const load = async () => {
    setError(null);
    try {
      const loaded = await api.get<SearchPrefs>("/api/automation/settings");
      let shown = loaded;
      try {
        // Blank fields inherit from the Profile page; show what is actually in use
        // rather than an empty box that hides the real search.
        const p = await api.post<SearchPlan>("/api/automation/search-plan", loaded, { track: false });
        setPlan(p);
        setInherited(loaded.titles.length === 0 && p.titles.length > 0);
        shown = {
          ...loaded,
          titles: loaded.titles.length ? loaded.titles : p.titles,
          skills: loaded.skills.length ? loaded.skills : p.skills,
          locations: loaded.locations.length ? loaded.locations : p.locations,
        };
      } catch {
        /* the editors still work without the preview */
      }
      setPrefs(shown);
    } catch (e: any) {
      setError(e.message);
    }
    api.get<JobSourceSite[]>("/api/jobs/sources").then(setSites).catch(() => {});
    loadRuns();
  };

  useEffect(() => {
    load();
  }, []);

  const [plan, setPlan] = useState<SearchPlan | null>(null);
  const [inherited, setInherited] = useState(false);
  // Only the phrases change the plan; other fields are ignored to avoid refetching on every keystroke.
  const draftKey = prefs ? [...prefs.titles, ...(prefs.extra_terms ?? []), ...prefs.skills, ...prefs.locations].join("|") : "";
  useEffect(() => {
    if (!prefs) return;
    const draft = prefs;
    const timer = setTimeout(() => {
      api.post<SearchPlan>("/api/automation/search-plan", draft, { track: false }).then(setPlan).catch(() => setPlan(null));
    }, 450);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draftKey]);

  const save = async () => {
    if (!prefs) return;
    setSaving(true);
    try {
      const updated = await api.put<SearchPrefs>("/api/automation/settings", prefs);
      setPrefs(updated);
      setInherited(false);
      toast(t("Automation settings saved"));
    } catch (e: any) {
      toast(e.message, "error");
    } finally {
      setSaving(false);
    }
  };

  const runNow = async () => {
    // An empty tick list makes the backend fall back to the saved sites, which is the
    // opposite of what he just unticked. Refuse instead of guessing.
    if (!prefs || !prefs.sources.length) {
      toast(t("Tick at least one job site first — otherwise the search would use the saved list, not the boxes you just cleared"), "error");
      return;
    }
    setRunning(true);
    setRunProgress(null);
    setRunLog([]);
    try {
      // The run reads the saved settings on the server. Save the screen first so the
      // terms and sites the preview names are the ones actually searched.
      const saved = await api.put<SearchPrefs>("/api/automation/settings", prefs);
      setPrefs(saved);
      setInherited(false);
      const ev = await api.postStream("/api/automation/run/stream", saved.sources, (p) => {
        if (p.type !== "progress") return;
        // Same guard as the Find Jobs import: the search can stream hundreds of
        // lines, and re-rendering on every one made the page crawl.
        const now = Date.now();
        if (now - progressThrottle.current >= 100) {
          progressThrottle.current = now;
          setRunProgress({ done: p.done ?? 0, total: p.total ?? 0, label: p.label ?? "" });
        }
        const line = p.line;
        if (line) setRunLog((prev) => [...prev, line]);
      });
      if (ev.type === "done") {
        toast(
          ev.status === "success" ? t("Search finished — {n} new jobs", { n: ev.jobs_found ?? 0 }) : t("Search failed: {log}", { log: ev.log ?? "" }),
          ev.status === "success" ? "success" : "error"
        );
        loadRuns();
      }
    } catch (e: any) {
      toast(e.message, "error");
    } finally {
      setRunning(false);
      setRunProgress(null);
    }
  };

  if (!prefs) {
    return error
      ? (
        <div className="space-y-5">
          <PageHeader eyebrow={t("Setup")} title={t("Automation")} />
          <ErrorState message={error} onRetry={load} />
        </div>
      )
      : (
        <div className="space-y-5">
          <Skeleton className="h-10 w-64" />
          <Skeleton className="h-96 rounded-2xl" />
        </div>
      );
  }

  const toggleSource = (name: string) => {
    const on = prefs.sources.includes(name);
    setPrefs({ ...prefs, sources: on ? prefs.sources.filter((s) => s !== name) : [...prefs.sources, name] });
  };

  const sourceList = sites.length
    ? sites
    : Object.keys(SOURCE_LABELS).map((name) => ({
        name, label: SOURCE_LABELS[name], enabled: true, requires_key: false, live_jobs: 0,
      }));

  return (
    <div className="animate-fade-in space-y-5">
      <PageHeader
        eyebrow={t("Setup")}
        title={t("Automation")}
        description={t("Scheduled searches run in the backend process. Keep the backend running for automation to work.")}
        actions={
          <>
            <Button variant="outline" onClick={runNow} disabled={running}>
              {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
              {running ? t("Running…") : t("Run search now")}
            </Button>
            <Button onClick={save} disabled={saving}>
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
              {saving ? t("Saving…") : t("Save settings")}
            </Button>
          </>
        }
      />

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        <div className="min-w-0 space-y-5 lg:col-span-2">
          <Card>
            <CardHeader className="flex-row flex-wrap items-start justify-between gap-3 space-y-0 pb-4">
              <div className="space-y-1.5">
                <CardTitle>{t("Search schedule")}</CardTitle>
                <CardDescription>{t("When the app looks for new postings")}</CardDescription>
              </div>
              <Badge variant={prefs.scheduler_running ? "success" : "outline"}>
                {prefs.scheduler_running ? t("Active") : t("Inactive")}
              </Badge>
            </CardHeader>
            <CardContent className="space-y-5">
              <div className="flex items-center justify-between gap-3 rounded-xl border border-border/70 bg-muted/25 p-4">
                <div>
                  <p className="text-sm font-semibold">{t("Scheduled search")}</p>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    {prefs.scheduler_running ? t("Runs every {n} minutes", { n: prefs.interval_minutes }) : t("Paused — no automatic runs")}
                  </p>
                </div>
                <Switch ariaLabel={t("Scheduled search")} checked={prefs.enabled} onChange={(v) => setPrefs({ ...prefs, enabled: v })} />
              </div>

              <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                <label className="block">
                  <FieldLabel>{t("Search interval")}</FieldLabel>
                  <Select value={String(prefs.interval_minutes)} onChange={(e) => setPrefs({ ...prefs, interval_minutes: Number(e.target.value) })}>
                    {withCurrent([15, 30, 60, 360, 720, 1440], prefs.interval_minutes).map((n) => (
                      <option key={n} value={n}>{intervalLabel(n)}</option>
                    ))}
                  </Select>
                </label>
                <label className="block">
                  <FieldLabel>{t("Min. match score")}</FieldLabel>
                  <Select value={String(prefs.min_match_score)} onChange={(e) => setPrefs({ ...prefs, min_match_score: Number(e.target.value) })}>
                    {withCurrent([0, 30, 50, 60, 70, 80], prefs.min_match_score).map((n) => (
                      <option key={n} value={n}>{n}+</option>
                    ))}
                  </Select>
                </label>
                <label className="block">
                  <FieldLabel>{t("Max job age")}</FieldLabel>
                  <Select value={String(prefs.max_age_days)} onChange={(e) => setPrefs({ ...prefs, max_age_days: Number(e.target.value) })}>
                    {withCurrent(AGE_PRESETS, prefs.max_age_days).map((n) => (
                      <option key={n} value={n}>{t("Newer than {n} days", { n })}</option>
                    ))}
                  </Select>
                </label>
              </div>

              <div className="flex items-center justify-between gap-3 rounded-xl border border-border/70 p-4">
                <div>
                  <p className="text-sm font-semibold">{t("Remote only")}</p>
                  <p className="mt-0.5 text-xs text-muted-foreground">{t("Only fetch jobs marked as remote")}</p>
                </div>
                <Switch ariaLabel={t("Remote only")} checked={prefs.remote_only} onChange={(v) => setPrefs({ ...prefs, remote_only: v })} />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-4">
              <CardTitle>{t("Search terms")}</CardTitle>
              <CardDescription>{t("What the scheduled (and manual) search looks for. Each phrase is searched on its own.")}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-5">
              <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
                <TermEditor
                  label={t("Job titles")}
                  values={prefs.titles}
                  onChange={(v) => setPrefs({ ...prefs, titles: v })}
                  placeholder="Flutter Developer, Python Developer"
                  hint={t("Each title is searched on its own, so a posting titled just “Flutter Engineer” still gets caught.")}
                />
                <TermEditor
                  label={t("Skills")}
                  values={prefs.skills}
                  onChange={(v) => setPrefs({ ...prefs, skills: v })}
                  placeholder="Flutter, Python, C#"
                  hint={t("Used after the titles, to fill the remaining search slots.")}
                />
                <TermEditor
                  label={t("Extra fields to hunt in — your choice")}
                  values={prefs.extra_terms ?? []}
                  onChange={(v) => setPrefs({ ...prefs, extra_terms: v })}
                  placeholder="Game Developer, Data Analyst, QA Engineer"
                  hint={t("Anything else you want the app to look for, even if it is not in your profile. These rank right after your titles.")}
                />
                <TermEditor
                  label={t("Locations")}
                  values={prefs.locations}
                  onChange={(v) => setPrefs({ ...prefs, locations: v })}
                  placeholder="Cairo, Remote"
                  hint={t("The first location is the one LinkedIn and Google Jobs search. Currently: {where}.", { where: plan?.where ?? "Egypt" })}
                />
              </div>
              {plan && <SearchPlanPreview plan={plan} inherited={inherited} />}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex-row flex-wrap items-start justify-between gap-3 space-y-0 pb-4">
              <div className="space-y-1.5">
                <CardTitle>{t("Job sources")}</CardTitle>
                <CardDescription>{t("Ticked sites are searched by the schedule and by “Import all ticked sites” in Find Jobs.")}</CardDescription>
              </div>
              <Badge variant="secondary">{t("{n} selected", { n: prefs.sources.length })}</Badge>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 gap-x-8 sm:grid-cols-2">
                {sourceList.map((s) => {
                  const on = prefs.sources.includes(s.name);
                  return (
                    <label
                      key={s.name}
                      title={t(s.label)}
                      className={cn(
                        "flex cursor-pointer items-center gap-3 border-b border-border/60 py-2.5 transition-colors hover:bg-muted/30",
                        on && "bg-muted/25"
                      )}
                    >
                      <input type="checkbox" className="h-4 w-4 shrink-0" checked={on} onChange={() => toggleSource(s.name)} />
                      <span className="min-w-0 flex-1 truncate text-[13px] font-medium">{sourceLabel(s.name)}</span>
                      <span className="nums shrink-0 text-[11px] text-muted-foreground">
                        {s.live_jobs ? t("{n} live", { n: s.live_jobs }) : t("no postings yet")}
                      </span>
                      {s.requires_key && <span className="shrink-0 text-[11px] text-muted-foreground">{t("needs a key")}</span>}
                    </label>
                  );
                })}
              </div>
              <p className="mt-3 text-[11px] leading-relaxed text-muted-foreground">
                {t("To pull one site alone, use its own button in Find Jobs.")}
              </p>
            </CardContent>
          </Card>
        </div>

        <div className="min-w-0 space-y-5">
          {running && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin" /> {t("Searching now")}
                </CardTitle>
                <CardDescription>{t("Live progress from the backend")}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex items-center justify-between gap-3 text-xs text-muted-foreground">
                  <span className="truncate">
                    {runProgress ? t("{label} — site {done} of {total}", { label: runProgress.label, done: runProgress.done, total: runProgress.total }) : t("Starting the search…")}
                  </span>
                  <span className="shrink-0 font-semibold text-foreground">
                    {runProgress?.total ? Math.round((runProgress.done / runProgress.total) * 100) : 0}%
                  </span>
                </div>
                <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                  <div
                    className="h-full rounded-full bg-primary transition-[width] duration-300 ease-out"
                    style={{ width: `${runProgress?.total ? (runProgress.done / runProgress.total) * 100 : 0}%` }}
                  />
                </div>
                {runLog.length > 0 && (
                  <pre className="scrollbar-thin max-h-40 overflow-auto whitespace-pre-wrap rounded-lg border border-border/60 bg-muted/40 p-2.5 text-[11px] leading-relaxed">
                    {runLog.join("\n")}
                  </pre>
                )}
              </CardContent>
            </Card>
          )}

          <Card className="lg:sticky lg:top-24">
            <CardHeader className="flex-row items-start justify-between space-y-0 pb-4">
              <div className="space-y-1.5">
                <CardTitle>{t("Run history")}</CardTitle>
                <CardDescription>{t("Latest automation runs, newest first")}</CardDescription>
              </div>
            </CardHeader>
            <CardContent>
              {runs.length === 0 ? (
                <p className="rounded-xl border border-dashed p-6 text-center text-sm text-muted-foreground">
                  {t("No runs yet. Press “Run search now” to trigger the first one.")}
                </p>
              ) : (
                <div className="space-y-2">
                  {runs.slice(0, 10).map((r) => (
                    <div key={r.id} className="rounded-xl border border-border/70 bg-card p-3">
                      <button
                        className="flex w-full items-center gap-2 text-start"
                        onClick={() => setExpandedRun(expandedRun === r.id ? null : r.id)}
                        aria-expanded={expandedRun === r.id}
                      >
                        <Badge variant={r.status === "success" ? "success" : "danger"}>{t(r.status)}</Badge>
                        <span className="text-[11px] text-muted-foreground">{r.trigger}</span>
                        <span className="truncate text-[11px] text-muted-foreground">{formatDateTime(r.started_at)}</span>
                        <span className="ms-auto shrink-0 text-[11px] font-semibold">{t("{n} new", { n: r.jobs_found })}</span>
                        <ChevronDown className={cn("h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform", expandedRun === r.id && "rotate-180")} />
                      </button>
                      {expandedRun === r.id && (
                        <pre className="scrollbar-thin mt-2 max-h-60 overflow-auto whitespace-pre-wrap rounded-lg bg-muted/40 p-2.5 text-[11px] leading-relaxed">
                          {r.log || r.error || t("No log output.")}
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
    </div>
  );
}
