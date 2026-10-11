import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Bot, Copy, Download, History, Loader2, RefreshCw, Trash2, Wand2 } from "lucide-react";
import { api, qs } from "@/lib/api";
import { GENERATION_KINDS, type GenerationResult, type Job, type JobPage } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/context/toast";

interface Material {
  id: number;
  kind: string;
  content: string;
  template_based: boolean;
  created_at: string;
}

export function AssistantPage() {
  const { toast } = useToast();
  const [params] = useSearchParams();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [jobId, setJobId] = useState<number | "">("");
  const [kind, setKind] = useState("cover_letter");
  const [extraNotes, setExtraNotes] = useState("");
  const [generating, setGenerating] = useState(false);
  const [result, setResult] = useState<GenerationResult | null>(null);
  const [content, setContent] = useState("");
  const [materials, setMaterials] = useState<Material[]>([]);
  const [loadingJobs, setLoadingJobs] = useState(true);
  const [jobsError, setJobsError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const activeJob = useRef<number | "">("");

  useEffect(() => {
    const fromParam = Number(params.get("job"));
    setJobsError("");
    api
      .get<JobPage>(`/api/jobs${qs({ page_size: 100, sort: "date" })}`)
      .then(async (d) => {
        let items = d.items;
        if (fromParam && !items.some((j) => j.id === fromParam)) {
          // Deep link from Saved Jobs / Matches may point at a job outside this page.
          try {
            const missing = await api.get<Job>(`/api/jobs/${fromParam}`);
            items = [missing, ...items];
          } catch {
            /* the job was deleted — fall back to the newest one */
          }
        }
        setJobs(items);
        if (fromParam && items.some((j) => j.id === fromParam)) setJobId(fromParam);
        else if (items.length) setJobId(items[0].id);
      })
      .catch((e) => {
        setJobsError(e.message);
        toast(e.message, "error");
      })
      .finally(() => setLoadingJobs(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [attempt]);

  useEffect(() => {
    activeJob.current = jobId;
    setMaterials([]);
    setResult(null);
    setContent("");
    // Notes typed for one job must never be sent into another job's letter.
    setExtraNotes("");
    if (jobId === "") return;
    let current = true;
    api
      .get<Material[]>(`/api/assistant/materials/${jobId}`)
      .then((d) => { if (current) setMaterials(d); })
      .catch(() => { if (current) setMaterials([]); });
    return () => { current = false; };
  }, [jobId]);

  const generate = async () => {
    if (jobId === "") {
      toast("Select a job first", "error");
      return;
    }
    setGenerating(true);
    const forJob = jobId;
    try {
      const r = await api.post<GenerationResult>("/api/assistant/generate", {
        job_id: forJob,
        kind,
        extra_notes: extraNotes,
      });
      // The request outlives the panel it was for if he switches job mid-generation.
      if (activeJob.current !== forJob) return;
      setResult(r);
      setContent(r.content);
      api.get<Material[]>(`/api/assistant/materials/${forJob}`).then(setMaterials).catch(() => {});
    } catch (e: any) {
      toast(e.message, "error");
    } finally {
      setGenerating(false);
    }
  };

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(content);
      toast("Copied to clipboard");
    } catch {
      toast("Could not copy — select the text and copy manually", "error");
    }
  };

  const download = () => {
    const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${result?.kind ?? kind}_${jobId || "draft"}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const removeMaterial = async (id: number) => {
    try {
      await api.delete(`/api/assistant/materials/${id}`);
      setMaterials((ms) => ms.filter((m) => m.id !== id));
      toast("Material deleted");
    } catch (e: any) {
      toast(e.message, "error");
    }
  };

  const kindLabel = GENERATION_KINDS.find((k) => k.value === kind)?.label ?? kind;
  const labelOf = (k: string) => GENERATION_KINDS.find((x) => x.value === k)?.label ?? k;
  // The panel shows what was generated, which may predate the current dropdown choice.
  const shownLabel = result ? labelOf(result.kind) : kindLabel;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-bold">AI Application Assistant</h1>
        <p className="text-sm text-muted-foreground">
          Generate tailored materials from your real profile only — nothing is invented.
        </p>
      </div>

      <Card>
        <CardContent className="grid gap-4 p-5 md:grid-cols-3">
          <div>
            <p className="mb-1.5 text-sm font-medium">Job</p>
            {loadingJobs ? (
              <Skeleton className="h-9" />
            ) : jobsError ? (
              <div className="space-y-1.5">
                <Select value="" disabled>
                  <option value="">Jobs unavailable</option>
                </Select>
                <p className="text-xs text-red-600 dark:text-red-400">
                  {jobsError}{" "}
                  <button className="text-primary hover:underline" onClick={() => setAttempt((a) => a + 1)}>Retry</button>
                </p>
              </div>
            ) : jobs.length === 0 ? (
              <div className="space-y-1.5">
                <Select value="" disabled>
                  <option value="">No jobs stored yet</option>
                </Select>
                <p className="text-xs text-muted-foreground">
                  <Link to="/jobs" className="text-primary hover:underline">Find jobs</Link> or run a search in{" "}
                  <Link to="/automation" className="text-primary hover:underline">Automation Settings</Link> first.
                </p>
              </div>
            ) : (
              <Select value={String(jobId)} onChange={(e) => setJobId(e.target.value === "" ? "" : Number(e.target.value))}>
                {jobs.map((j) => (
                  <option key={j.id} value={j.id}>
                    {j.title} — {j.company}
                  </option>
                ))}
              </Select>
            )}
          </div>
          <div>
            <p className="mb-1.5 text-sm font-medium">What to generate</p>
            <Select value={kind} onChange={(e) => setKind(e.target.value)}>
              {GENERATION_KINDS.map((k) => <option key={k.value} value={k.value}>{k.label}</option>)}
            </Select>
          </div>
          <div className="flex items-end">
            <Button onClick={generate} disabled={generating || jobId === ""} className="w-full">
              {generating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Wand2 className="h-4 w-4" />}
              {generating ? "Generating…" : "Generate"}
            </Button>
          </div>
          <div className="md:col-span-3">
            <p className="mb-1.5 text-sm font-medium">Extra notes (optional)</p>
            <Textarea
              rows={2}
              value={extraNotes}
              onChange={(e) => setExtraNotes(e.target.value)}
              placeholder="e.g. Mention my freelance work, keep it under 200 words, highlight my graduation project…"
            />
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          {result === null && !generating ? (
            <EmptyState
              icon={Bot}
              title="Nothing generated yet"
              description={`Pick a job and choose "${kindLabel}", then press Generate. Works with or without an OpenAI API key.`}
            />
          ) : generating ? (
            <Card>
              <CardContent className="flex flex-col items-center gap-3 py-12">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
                <p className="text-sm text-muted-foreground">Writing your {kindLabel.toLowerCase()}…</p>
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardHeader className="pb-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <CardTitle className="text-base">{shownLabel}</CardTitle>
                  <div className="flex gap-1.5">
                    {result?.template_based && <Badge variant="warning">Template-based</Badge>}
                    {!result?.template_based && <Badge variant="success">AI generated</Badge>}
                  </div>
                </div>
                <CardDescription className="flex flex-wrap items-center gap-2">
                  <button onClick={generate} className="inline-flex items-center gap-1 text-primary hover:underline" disabled={generating}>
                    <RefreshCw className="h-3 w-3" /> Regenerate
                  </button>
                  <button onClick={copy} className="inline-flex items-center gap-1 text-primary hover:underline">
                    <Copy className="h-3 w-3" /> Copy
                  </button>
                  <button onClick={download} className="inline-flex items-center gap-1 text-primary hover:underline">
                    <Download className="h-3 w-3" /> Export .txt
                  </button>
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {result?.warning && (
                  <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-700 dark:text-amber-300">
                    {result.warning}
                  </div>
                )}
                <Textarea
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                  className="min-h-[320px] font-mono text-xs leading-relaxed"
                />
              </CardContent>
            </Card>
          )}
        </div>

        <Card className="self-start">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-base"><History className="h-4 w-4" /> Generated history</CardTitle>
            <CardDescription>Materials saved for this job</CardDescription>
          </CardHeader>
          <CardContent>
            {materials.length === 0 ? (
              <p className="py-4 text-center text-sm text-muted-foreground">No saved materials for this job yet.</p>
            ) : (
              <div className="space-y-2">
                {materials.slice(0, 12).map((m) => (
                  <div key={m.id} className="flex items-start gap-1.5 rounded-lg border p-2.5">
                    <button
                      onClick={() => {
                        setContent(m.content);
                        setResult({ kind: m.kind, content: m.content, template_based: m.template_based, warning: "Loaded from history — review before using." });
                      }}
                      className="min-w-0 flex-1 text-left hover:opacity-80"
                    >
                      <p className="flex items-center gap-1.5 text-xs font-medium">
                        {labelOf(m.kind)}
                        <Badge variant={m.template_based ? "warning" : "success"} className="text-[9px]">
                          {m.template_based ? "Template" : "AI"}
                        </Badge>
                      </p>
                      <p className="mt-0.5 truncate text-[11px] text-muted-foreground">{m.content.slice(0, 60)}…</p>
                    </button>
                    <Button size="icon" variant="ghost" className="h-6 w-6 shrink-0" title="Delete this material"
                            onClick={() => removeMaterial(m.id)}>
                      <Trash2 className="h-3.5 w-3.5 text-red-500" />
                    </Button>
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
