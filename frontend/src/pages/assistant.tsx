import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  Bot,
  Copy,
  Download,
  Eye,
  FileDown,
  Loader2,
  Pencil,
  RefreshCw,
  Sparkles,
  Trash2,
} from "lucide-react";
import { api, qs } from "@/lib/api";
import { GENERATION_KINDS, type GenerationResult, type Job, type JobLite, type PreparedMaterial } from "@/lib/types";
import { fileName, saveBlob } from "@/lib/download";
import { MarkedText, suggestedItems } from "@/components/applications/marked-text";
import { Badge } from "@/components/ui/badge";
import { ConfirmDialog } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { PageHeader } from "@/components/layout/page-header";
import { useToast } from "@/context/toast";
import { useI18n } from "@/context/i18n";
import { cn } from "@/lib/utils";

export function AssistantPage() {
  const { toast } = useToast();
  const { t } = useI18n();
  const [params] = useSearchParams();
  const [jobs, setJobs] = useState<JobLite[]>([]);
  const [jobId, setJobId] = useState<number | "">("");
  const [kind, setKind] = useState("cover_letter");
  const [extraNotes, setExtraNotes] = useState("");
  const [generating, setGenerating] = useState(false);
  const [result, setResult] = useState<GenerationResult | null>(null);
  const [content, setContent] = useState("");
  const [materials, setMaterials] = useState<PreparedMaterial[]>([]);
  const [loadingJobs, setLoadingJobs] = useState(true);
  const [jobsError, setJobsError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [showMarks, setShowMarks] = useState<boolean | null>(null);
  const [deletingMaterial, setDeletingMaterial] = useState<number | null>(null);
  const [savingPdf, setSavingPdf] = useState<"marked" | "clean" | null>(null);
  const activeJob = useRef<number | "">("");

  useEffect(() => {
    const fromParam = Number(params.get("job"));
    let current = true;
    setJobsError("");
    api
      .get<JobLite[]>("/api/jobs/light")
      .then(async (d) => {
        let items = d;
        if (fromParam && !items.some((j) => j.id === fromParam)) {
          // Deep link from Saved Jobs / Matches may point at a job outside the newest 200.
          try {
            const missing = await api.get<Job>(`/api/jobs/${fromParam}`);
            items = [{ id: missing.id, title: missing.title, company: missing.company, location: missing.location }, ...items];
          } catch {
            /* the job was deleted — fall back to the newest one */
          }
        }
        if (!current) return;
        setJobs(items);
        if (fromParam && items.some((j) => j.id === fromParam)) setJobId(fromParam);
        else if (items.length) setJobId(items[0].id);
      })
      .catch((e) => {
        if (!current) return;
        setJobsError(e.message);
        toast(e.message, "error");
      })
      .finally(() => { if (current) setLoadingJobs(false); });
    return () => { current = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [attempt, params]);

  useEffect(() => {
    activeJob.current = jobId;
    setMaterials([]);
    setResult(null);
    setContent("");
    setShowMarks(null);
    // Notes typed for one job must never be sent into another job's letter.
    setExtraNotes("");
    if (jobId === "") return;
    let current = true;
    api
      .get<PreparedMaterial[]>(`/api/assistant/materials/${jobId}`)
      .then((d) => { if (current) setMaterials(d); })
      .catch(() => { if (current) setMaterials([]); });
    return () => { current = false; };
  }, [jobId]);

  const generate = async () => {
    if (jobId === "") {
      toast(t("Select a job first"), "error");
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
      setShowMarks(null);
      api.get<PreparedMaterial[]>(`/api/assistant/materials/${forJob}`)
        .then((d) => { if (activeJob.current === forJob) setMaterials(d); })
        .catch(() => {});
    } catch (e: any) {
      toast(e.message, "error");
    } finally {
      setGenerating(false);
    }
  };

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(content);
      toast(t("Copied to clipboard"));
    } catch {
      toast(t("Could not copy — select the text and copy manually"), "error");
    }
  };

  const download = () => {
    saveBlob(
      new Blob([content], { type: "text/plain;charset=utf-8" }),
      `${result?.kind ?? kind}_${jobId || "draft"}.txt`
    );
  };

  const removeMaterial = async (id: number) => {
    try {
      await api.delete(`/api/assistant/materials/${id}`);
      setMaterials((ms) => ms.filter((m) => m.id !== id));
      toast(t("Material deleted"));
    } catch (e: any) {
      toast(e.message, "error");
    } finally {
      setDeletingMaterial(null);
    }
  };

  /** The CV written for this ad, as a PDF. ``marked`` keeps the red additions for his
   *  own review; the clean copy prints them in black, with no marks and no notes. */
  const saveCvPdf = async (marked: boolean) => {
    if (jobId === "") {
      toast(t("Select a job first"), "error");
      return;
    }
    setSavingPdf(marked ? "marked" : "clean");
    try {
      const blob = await api.downloadPdf(`/api/assistant/cv/${jobId}/pdf${qs({ marked })}`);
      const job = jobs.find((j) => j.id === jobId);
      saveBlob(blob, fileName(marked ? "CV_review" : "CV", job?.title, job?.company));
      toast(
        marked
          ? t("Review copy saved — the lines the assistant added are printed in red")
          : t("Send copy saved — the added lines are printed in black, without the red marks")
      );
    } catch (e: any) {
      toast(e.message, "error");
    } finally {
      setSavingPdf(null);
    }
  };

  const kindLabel = t(GENERATION_KINDS.find((k) => k.value === kind)?.label ?? kind);
  const labelOf = (k: string) => t(GENERATION_KINDS.find((x) => x.value === k)?.label ?? k);
  // The panel shows what was generated, which may predate the current dropdown choice.
  const shownKind = result ? result.kind : kind;
  const shownLabel = result ? labelOf(result.kind) : kindLabel;
  const marks = suggestedItems(content);
  const isCv = shownKind === "cv";
  const previewing = isCv && marks.length > 0 && showMarks !== false;

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow={t("Apply")}
        title={t("AI Application Assistant")}
        description={t("Generate tailored materials from your real profile only — nothing is invented, and nothing is sent for you.")}
      />

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-6">
          <Card>
            <CardHeader className="pb-4">
              <CardTitle>{t("Generate materials")}</CardTitle>
              <CardDescription>{t("Pick the ad, choose what you need, then generate.")}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-5">
              <div>
                <p className="mb-2 block text-[11px] font-medium uppercase tracking-[0.12em] text-muted-foreground">
                  {t("Job")}
                </p>
                {loadingJobs ? (
                  <Skeleton className="h-10 rounded-lg" />
                ) : jobsError ? (
                  <div className="space-y-1.5">
                    <Select value="" disabled aria-label={t("Job")}>
                      <option value="">{t("Jobs unavailable")}</option>
                    </Select>
                    <p className="text-xs text-red-600 dark:text-red-400">
                      {jobsError}{" "}
                      <button
                        className="font-medium text-primary hover:underline"
                        onClick={() => setAttempt((a) => a + 1)}
                      >
                        {t("Retry")}
                      </button>
                    </p>
                  </div>
                ) : jobs.length === 0 ? (
                  <div className="space-y-1.5">
                    <Select value="" disabled aria-label={t("Job")}>
                      <option value="">{t("No jobs stored yet")}</option>
                    </Select>
                    <p className="text-xs text-muted-foreground">
                      <Link to="/jobs" className="font-medium text-primary hover:underline">
                        {t("Find jobs")}
                      </Link>{" "}
                      {t("or run a search in")}{" "}
                      <Link to="/automation" className="font-medium text-primary hover:underline">
                        {t("Automation Settings")}
                      </Link>{" "}
                      {t("first.")}
                    </p>
                  </div>
                ) : (
                  <Select
                    value={String(jobId)}
                    aria-label={t("Job")}
                    onChange={(e) => setJobId(e.target.value === "" ? "" : Number(e.target.value))}
                  >
                    {jobs.map((j) => (
                      <option key={j.id} value={j.id}>
                        {j.title} — {j.company}
                      </option>
                    ))}
                  </Select>
                )}
              </div>

              <div>
                <p className="mb-2 text-[11px] font-medium uppercase tracking-[0.12em] text-muted-foreground">
                  {t("What to generate")}
                </p>
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                  {GENERATION_KINDS.map((k) => (
                    <button
                      key={k.value}
                      type="button"
                      onClick={() => setKind(k.value)}
                      aria-pressed={kind === k.value}
                      className={cn(
                        "truncate rounded-lg border px-3 py-2 text-start text-sm font-medium transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                        kind === k.value
                          ? "border-primary bg-primary text-primary-foreground"
                          : "border-border/80 bg-card text-foreground hover:border-border hover:bg-accent/60"
                      )}
                    >
                      {t(k.label)}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label
                  htmlFor="assistant-notes"
                  className="mb-2 block text-[11px] font-medium uppercase tracking-[0.12em] text-muted-foreground"
                >
                  {t("Extra notes")} <span className="font-normal normal-case tracking-normal text-muted-foreground/70">({t("optional")})</span>
                </label>
                <Textarea
                  id="assistant-notes"
                  rows={2}
                  className="min-h-[72px]"
                  value={extraNotes}
                  onChange={(e) => setExtraNotes(e.target.value)}
                  placeholder={t("e.g. Mention my freelance work, keep it under 200 words, highlight my graduation project…")}
                />
              </div>

              <div className="flex flex-col-reverse items-stretch justify-between gap-3 border-t border-border/70 pt-4 sm:flex-row sm:items-center">
                <p className="text-xs text-muted-foreground">
                  {t("Works with or without an AI key — it falls back to a template built from your profile.")}
                </p>
                <Button onClick={generate} disabled={generating || jobId === ""} className="sm:min-w-40">
                  {generating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                  {generating ? t("Generating…") : t("Generate {kind}", { kind: kindLabel })}
                </Button>
              </div>
            </CardContent>
          </Card>

          {result === null && !generating ? (
            <EmptyState
              icon={Bot}
              title={t("Nothing generated yet")}
              description={t('Pick a job and choose "{kind}", then press Generate. Every draft is built from what you entered in your profile.', { kind: kindLabel })}
            />
          ) : generating ? (
            <Card>
              <CardContent className="flex flex-col items-center gap-3 py-14">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
                <p className="text-sm text-muted-foreground">{t("Writing your {kind}…", { kind: kindLabel.toLowerCase() })}</p>
              </CardContent>
            </Card>
          ) : (
            <Card className="overflow-hidden">
              <CardHeader className="border-b border-border/70 bg-muted/30 pb-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <CardTitle className="text-base">{shownLabel}</CardTitle>
                    <div className="mt-1.5 flex flex-wrap items-center gap-2">
                      {result?.template_based ? (
                        <Badge variant="warning">{t("Template-based")}</Badge>
                      ) : (
                        <Badge variant="success">{t("AI generated")}</Badge>
                      )}
                      <span className="text-xs text-muted-foreground">
                        {previewing ? t("{n} additions in red — confirm them", { n: marks.length }) : t("Editable before you use it")}
                      </span>
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {isCv && (
                      <>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => saveCvPdf(true)}
                          disabled={savingPdf !== null}
                          title={t("The copy you check first: additions the assistant suggested for this ad are printed red")}
                        >
                          {savingPdf === "marked" ? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          ) : (
                            <FileDown className="h-3.5 w-3.5" />
                          )}{" "}
                          {t("CV PDF with red marks")}
                        </Button>
                        <Button
                          size="sm"
                          onClick={() => saveCvPdf(false)}
                          disabled={savingPdf !== null}
                          title={t("The copy for the employer: no red marks, no internal notes, and the added lines stay as normal text")}
                        >
                          {savingPdf === "clean" ? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          ) : (
                            <FileDown className="h-3.5 w-3.5" />
                          )}{" "}
                          {t("Clean CV PDF")}
                        </Button>
                      </>
                    )}
                    <Button size="sm" variant="outline" onClick={copy}>
                      <Copy className="h-3.5 w-3.5" /> {t("Copy")}
                    </Button>
                    <Button size="sm" variant="outline" onClick={download}>
                      <Download className="h-3.5 w-3.5" /> {t("Export .txt")}
                    </Button>
                    <Button size="sm" variant="ghost" onClick={generate} disabled={generating}>
                      <RefreshCw className="h-3.5 w-3.5" /> {t("Regenerate")}
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-3 p-5 sm:p-6">
                {result?.warning && (
                  <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-xs leading-relaxed text-amber-700 dark:text-amber-300">
                    {result.warning}
                  </div>
                )}
                {previewing ? (
                  <>
                    <div className="scrollbar-thin max-h-[520px] overflow-y-auto rounded-xl border border-border/80 bg-muted/30 p-4">
                      <MarkedText text={content} />
                    </div>
                    <Button size="sm" variant="ghost" onClick={() => setShowMarks(false)}>
                      <Pencil className="h-3.5 w-3.5" /> {t("Edit the text")}
                    </Button>
                  </>
                ) : (
                  <>
                    <Textarea
                      value={content}
                      onChange={(e) => setContent(e.target.value)}
                      className="min-h-[360px] rounded-xl font-mono text-xs leading-relaxed"
                    />
                    {isCv && marks.length > 0 && (
                      <Button size="sm" variant="ghost" onClick={() => setShowMarks(true)}>
                        <Eye className="h-3.5 w-3.5" /> {t("Preview with red marks")}
                      </Button>
                    )}
                  </>
                )}
              </CardContent>
            </Card>
          )}
        </div>

        <Card className="h-fit xl:sticky xl:top-24">
          <CardHeader className="pb-3">
            <CardTitle className="text-base">{t("Generated history")}</CardTitle>
            <CardDescription>{t("Materials saved for this job")}</CardDescription>
          </CardHeader>
          <CardContent>
            {materials.length === 0 ? (
              <div className="rounded-xl border border-dashed border-border/80 px-4 py-8 text-center">
                <p className="text-sm text-muted-foreground">{t("No saved materials for this job yet.")}</p>
              </div>
            ) : (
              <div className="scrollbar-thin max-h-[560px] space-y-2 overflow-y-auto pe-1">
                {materials.slice(0, 12).map((m) => (
                  <div
                    key={m.id}
                    className="group flex items-start gap-1.5 rounded-xl border border-border/80 bg-card p-3 transition-colors hover:border-border hover:bg-accent/40"
                  >
                    <button
                      onClick={() => {
                        setKind(m.kind);
                        setContent(m.content);
                        setResult({
                          kind: m.kind,
                          content: m.content,
                          template_based: m.template_based,
                          warning: t("Loaded from history — review before using."),
                        });
                      }}
                      className="min-w-0 flex-1 text-start focus-visible:outline-none"
                    >
                      <p className="flex items-center gap-1.5 text-xs font-semibold">
                        {labelOf(m.kind)}
                        <Badge variant={m.template_based ? "warning" : "success"}>
                          {m.template_based ? t("Template") : "AI"}
                        </Badge>
                      </p>
                      <p className="mt-1 line-clamp-2 text-[11px] leading-relaxed text-muted-foreground">
                        {m.content.slice(0, 90)}…
                      </p>
                    </button>
                    <Button
                      size="icon"
                      variant="ghost"
                      className="h-7 w-7 shrink-0 text-muted-foreground hover:text-red-600"
                      title={t("Delete this material")}
                      onClick={() => setDeletingMaterial(m.id)}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <ConfirmDialog
        open={deletingMaterial !== null}
        onClose={() => setDeletingMaterial(null)}
        onConfirm={() => {
          if (deletingMaterial !== null) void removeMaterial(deletingMaterial);
        }}
        title={t("Delete this document")}
        message={t("This saved draft is removed for good. You can always generate it again, but the AI call costs quota.")}
      />
    </div>
  );
}
