import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Bot,
  Bookmark,
  BookmarkCheck,
  ExternalLink,
  FileDown,
  Loader2,
  X,
} from "lucide-react";
import { type Job, type MatchResult, type PreparedApplication, boardLabel, sourceLabel } from "@/lib/types";
import { api, qs } from "@/lib/api";
import { formatDate, formatSalary, plainDescription, postedLabel, scoreColor } from "@/lib/format";
import { fileName, saveBlob } from "@/lib/download";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { ScoreBar } from "@/components/ui/progress";
import { Spinner } from "@/components/ui/skeleton";
import { ApplyRoute } from "@/components/applications/apply-route";
import { PackDialog, type Pack } from "@/components/applications/pack-dialog";
import { useToast } from "@/context/toast";
import { useI18n } from "@/context/i18n";
import { cn } from "@/lib/utils";
import { JobTags, SourceBadge } from "./status-badge";

export function JobDetailDialog({
  job,
  onClose,
  onChanged,
}: {
  job: Job | null;
  onClose: () => void;
  onChanged?: (job: Job) => void;
}) {
  const { toast } = useToast();
  const { t } = useI18n();
  const navigate = useNavigate();
  const [match, setMatch] = useState<MatchResult | null>(null);
  const [matchError, setMatchError] = useState(false);
  const [saving, setSaving] = useState(false);
  const [savingCv, setSavingCv] = useState(false);
  const [pack, setPack] = useState<Pack | null>(null);
  const [preparing, setPreparing] = useState(false);

  useEffect(() => {
    setMatch(null);
    setMatchError(false);
    if (!job?.id) return;
    // Opening another job must not let the previous response land on top of it.
    let current = true;
    api
      .get<MatchResult>(`/api/matches/${job.id}`)
      .then((d) => { if (current) setMatch(d); })
      .catch(() => {
        if (!current) return;
        setMatch(null);
        setMatchError(true);
      });
    return () => { current = false; };
    // Keyed on the id, not the object: saving a job hands back a new object for the
    // same ad, and refetching there would blank the score the moment it appeared.
  }, [job?.id]);

  if (!job) return null;

  const toggleSave = async () => {
    setSaving(true);
    try {
      if (job.saved) {
        await api.delete(`/api/jobs/${job.id}/save`);
        toast(t("Removed from saved jobs"));
      } else {
        await api.post(`/api/jobs/${job.id}/save`);
        toast(t("Job saved"));
      }
      // The parent refetches this one job and feeds the fresh object back —
      // mutating `job` in place would edit the list's shared object.
      onChanged?.(job);
    } catch (e: any) {
      toast(e.message, "error");
    } finally {
      setSaving(false);
    }
  };

  const openAssistant = () => {
    onClose();
    navigate(`/assistant?job=${job.id}`);
  };

  /** The clean, ATS-safe CV for this ad — no pack and no tracker entry needed. */
  const downloadCv = async () => {
    const jobId = job.id;
    setSavingCv(true);
    try {
      const blob = await api.downloadPdf(`/api/assistant/cv/${jobId}/pdf${qs({ marked: false })}`);
      saveBlob(blob, fileName("CV", job.title, job.company));
      toast(t("CV PDF saved — it holds only what your profile proves"));
    } catch (e: any) {
      toast(e.message, "error");
    } finally {
      setSavingCv(false);
    }
  };

  /** Writes the five documents for this ad and shows them. Sending stays his own act. */
  const prepare = async () => {
    setPreparing(true);
    try {
      const res = await api.post<PreparedApplication>("/api/applications/prepare", { job_id: job.id });
      setPack({ job: res.application.job, applicationId: res.application.id, materials: res.materials });
      onChanged?.(job);
    } catch (e: any) {
      toast(e.message, "error");
    } finally {
      setPreparing(false);
    }
  };

  return (
    <Dialog
      open={!!job}
      onClose={onClose}
      wide
      title={job.title}
      description={`${job.company} · ${job.location}${job.country && job.country !== job.location ? ", " + job.country : ""}`}
    >
      <div className="space-y-5">
        <div className="flex flex-wrap items-center gap-2">
          <SourceBadge job={job} />
          {job.remote && <Badge variant="outline">{t("Remote")}</Badge>}
          <Badge variant="secondary">{job.employment_type || t("Type not specified")}</Badge>
          <Badge variant="secondary">{job.experience_level || t("Level not specified")}</Badge>
          {!job.is_active && (
            <Badge variant="warning">{t("No longer advertised by {board}", { board: boardLabel(job) })}</Badge>
          )}
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-xl border border-border/80 bg-muted/30 p-3">
            <p className="text-[11px] font-medium uppercase tracking-[0.12em] text-muted-foreground">
              {t("Salary")}
            </p>
            <p className="mt-1 truncate text-sm font-semibold">{formatSalary(job)}</p>
          </div>
          <div className="rounded-xl border border-border/80 bg-muted/30 p-3">
            <p className="text-[11px] font-medium uppercase tracking-[0.12em] text-muted-foreground">
              {t("Source")}
            </p>
            <p className="mt-1 truncate text-sm font-semibold">{boardLabel(job)}</p>
            {job.publisher && job.publisher !== sourceLabel(job.source) && (
              <p className="mt-0.5 truncate text-[11px] text-muted-foreground">
                {t("via {source}", { source: sourceLabel(job.source) })}
              </p>
            )}
          </div>
          <div className="rounded-xl border border-border/80 bg-muted/30 p-3">
            <p className="text-[11px] font-medium uppercase tracking-[0.12em] text-muted-foreground">
              {t("Posted")}
            </p>
            <p className="mt-1 truncate text-sm font-semibold">{postedLabel(job)}</p>
            {job.expiry_date && (
              <p className="mt-0.5 truncate text-[11px] text-muted-foreground">
                {t("Expires {date}", { date: formatDate(job.expiry_date) })}
              </p>
            )}
          </div>
          <div className="rounded-xl border border-border/80 bg-muted/30 p-3">
            <p className="text-[11px] font-medium uppercase tracking-[0.12em] text-muted-foreground">
              {t("Location")}
            </p>
            <p className="mt-1 truncate text-sm font-semibold">{job.location || t("Not stated")}</p>
            <p className="mt-0.5 truncate text-[11px] text-muted-foreground">{job.country || "—"}</p>
          </div>
        </div>

        <section>
          <h3 className="text-[11px] font-medium uppercase tracking-[0.12em] text-muted-foreground">{t("Description")}</h3>
          <p className="mt-2 whitespace-pre-line break-words pe-1 text-sm leading-relaxed text-foreground/90 sm:max-h-[280px] sm:overflow-y-auto">
            {plainDescription(job.description)}
          </p>
        </section>

        {job.skills?.length > 0 && (
          <section>
            <h3 className="text-[11px] font-medium uppercase tracking-[0.12em] text-muted-foreground">{t("Skills")}</h3>
            <div className="mt-2">
              <JobTags job={job} limit={20} />
            </div>
          </section>
        )}

        <section className="rounded-xl border border-border/80 bg-muted/40 p-4">
          <div className="flex items-center justify-between gap-2">
            <h3 className="text-[11px] font-medium uppercase tracking-[0.12em] text-muted-foreground">
              {t("AI match estimate")}
            </h3>
            {match && (
              <span className={cn("text-2xl font-bold tabular-nums", scoreColor(match.score))}>
                {match.score}
                <span className="text-sm font-medium text-muted-foreground">/100</span>
              </span>
            )}
          </div>
          {match === null && matchError ? (
            <p className="mt-2 text-sm text-muted-foreground">
              {t("Match unavailable — the backend could not score this job. Check that it is reachable on port 8000.")}
            </p>
          ) : match === null ? (
            <div className="mt-2 flex items-center gap-2 text-sm text-muted-foreground">
              <Spinner className="h-4 w-4" /> {t("Calculating…")}
            </div>
          ) : (
            <div className="mt-3 space-y-3">
              <ScoreBar value={match.score} />
              <p className="text-[11px] text-muted-foreground">
                {t("Estimate based on your profile — not a guarantee.")}
              </p>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                {match.matched_skills?.length > 0 && (
                  <div className="rounded-xl border border-emerald-500/25 bg-emerald-500/5 p-3">
                    <p className="text-[11px] font-medium uppercase tracking-[0.12em] text-emerald-700 dark:text-emerald-400">
                      {t("You have")}
                    </p>
                    <p className="mt-1 text-xs leading-relaxed text-foreground/90">
                      {match.matched_skills.join(", ")}
                    </p>
                  </div>
                )}
                {match.missing_skills?.length > 0 && (
                  <div className="rounded-xl border border-red-500/25 bg-red-500/5 p-3">
                    <p className="text-[11px] font-medium uppercase tracking-[0.12em] text-red-700 dark:text-red-400">
                      {t("Missing / weak")}
                    </p>
                    <p className="mt-1 text-xs leading-relaxed text-foreground/90">
                      {match.missing_skills.join(", ")}
                    </p>
                  </div>
                )}
              </div>
              {match.why_match && (
                <p className="text-xs leading-relaxed text-muted-foreground">{match.why_match}</p>
              )}
              {match.hard_gap && (
                <p className="rounded-xl border border-red-500/25 bg-red-500/5 p-3 text-xs leading-relaxed text-red-700 dark:text-red-400">
                  {match.hard_gap}
                </p>
              )}
            </div>
          )}
        </section>

        <ApplyRoute job={job} />

        <div className="flex flex-wrap items-center gap-2 border-t border-border/70 pt-5">
          <Button onClick={prepare} disabled={preparing}>
            <Bot className="h-4 w-4" /> {preparing ? t("Writing your pack…") : t("Prepare the application pack")}
          </Button>
          <Button variant="outline" onClick={downloadCv} disabled={savingCv}>
            {savingCv ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileDown className="h-4 w-4" />}
            {t("Download CV PDF")}
          </Button>
          {job.url && (
            <Button variant="outline" onClick={() => window.open(job.url, "_blank", "noopener")}>
              {t("Open this ad")} <ExternalLink className="h-4 w-4" />
            </Button>
          )}
          <Button variant="outline" onClick={openAssistant}>
            <Bookmark className="h-4 w-4" /> {t("One document in Assistant")}
          </Button>
          <Button variant={job.saved ? "secondary" : "outline"} onClick={toggleSave} disabled={saving}>
            {job.saved ? <BookmarkCheck className="h-4 w-4" /> : <Bookmark className="h-4 w-4" />}
            {job.saved ? t("Saved") : t("Save")}
          </Button>
          <Button variant="ghost" onClick={onClose}>
            <X className="h-4 w-4" /> {t("Close")}
          </Button>
        </div>
      </div>

      <PackDialog pack={pack} onClose={() => setPack(null)} onChanged={() => onChanged?.(job)} />
    </Dialog>
  );
}
