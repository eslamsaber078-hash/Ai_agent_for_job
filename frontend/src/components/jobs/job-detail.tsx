import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bot, Bookmark, BookmarkCheck, Building2, Calendar, ExternalLink, MapPin, Wallet, X } from "lucide-react";
import { type Job, type MatchResult, sourceLabel } from "@/lib/types";
import { api } from "@/lib/api";
import { formatDate, formatSalary, scoreColor, timeAgo } from "@/lib/format";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { ScoreBar } from "@/components/ui/progress";
import { Spinner } from "@/components/ui/skeleton";
import { useToast } from "@/context/toast";
import { JobTags, SourceBadge } from "./status-badge";

export function JobDetailDialog({
  job,
  onClose,
  onChanged,
}: {
  job: Job | null;
  onClose: () => void;
  onChanged?: () => void;
}) {
  const { toast } = useToast();
  const navigate = useNavigate();
  const [match, setMatch] = useState<MatchResult | null>(null);
  const [matchError, setMatchError] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setMatch(null);
    setMatchError(false);
    if (!job) return;
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
  }, [job]);

  if (!job) return null;

  const toggleSave = async () => {
    setSaving(true);
    try {
      if (job.saved) {
        await api.delete(`/api/jobs/${job.id}/save`);
        toast("Removed from saved jobs");
      } else {
        await api.post(`/api/jobs/${job.id}/save`);
        toast("Job saved");
      }
      onChanged?.();
      job.saved = !job.saved;
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

  return (
    <Dialog open={!!job} onClose={onClose} wide title={job.title}
            description={`${job.company} · ${job.location}${job.country && job.country !== job.location ? ", " + job.country : ""}`}>
      <div className="flex flex-wrap items-center gap-2">
        <SourceBadge job={job} />
        {job.remote && <Badge variant="outline">Remote</Badge>}
        <Badge variant="secondary">{job.employment_type || "Type not specified"}</Badge>
        <Badge variant="secondary">{job.experience_level || "Level not specified"}</Badge>
        {!job.is_active && (
          <Badge variant="warning">No longer advertised by {sourceLabel(job.source)}</Badge>
        )}
        <span className="text-xs text-muted-foreground">Posted {timeAgo(job.posted_date)}</span>
        {job.expiry_date && (
          <span className="text-xs text-muted-foreground">
            · Listing expires {formatDate(job.expiry_date)}
          </span>
        )}
      </div>

      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <div className="rounded-lg border p-3 text-sm">
          <p className="text-xs text-muted-foreground">Salary</p>
          <p className="mt-0.5 inline-flex items-center gap-1.5 font-medium">
            <Wallet className="h-3.5 w-3.5 text-muted-foreground" /> {formatSalary(job)}
          </p>
        </div>
        <div className="rounded-lg border p-3 text-sm">
          <p className="text-xs text-muted-foreground">Source</p>
          <p className="mt-0.5">{sourceLabel(job.source)}</p>
        </div>
      </div>

      <div className="mt-4">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Description</p>
        <p className="mt-1.5 break-words whitespace-pre-line text-sm leading-relaxed">{job.description}</p>
      </div>

      {job.skills?.length > 0 && (
        <div className="mt-4">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Skills</p>
          <div className="mt-1.5">
            <JobTags job={job} limit={20} />
          </div>
        </div>
      )}

      <div className="mt-4 rounded-lg border bg-muted/40 p-4">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">AI match estimate</p>
        {match === null && matchError ? (
          <p className="mt-2 text-sm text-muted-foreground">
            Match unavailable — the backend could not score this job. Check that it is reachable on port 8000.
          </p>
        ) : match === null ? (
          <div className="mt-2 flex items-center gap-2 text-sm text-muted-foreground">
            <Spinner className="h-4 w-4" /> Calculating…
          </div>
        ) : (
          <div className="mt-2">
            <div className="flex items-center gap-3">
              <span className={`text-3xl font-bold ${scoreColor(match.score)}`}>{match.score}</span>
              <div className="flex-1">
                <ScoreBar value={match.score} />
                <p className="mt-1 text-[11px] text-muted-foreground">
                  Estimate based on your profile — not a guarantee.
                </p>
              </div>
            </div>
            {match.matched_skills?.length > 0 && (
              <p className="mt-2 text-xs">
                <span className="font-medium text-emerald-600 dark:text-emerald-400">You have:</span>{" "}
                {match.matched_skills.join(", ")}
              </p>
            )}
            {match.missing_skills?.length > 0 && (
              <p className="mt-1 text-xs">
                <span className="font-medium text-red-600 dark:text-red-400">Missing/weak:</span>{" "}
                {match.missing_skills.join(", ")}
              </p>
            )}
            {match.why_match && <p className="mt-2 text-xs text-muted-foreground">{match.why_match}</p>}
          </div>
        )}
      </div>

      <div className="mt-5 flex flex-wrap items-center gap-2 border-t pt-4">
        {job.url && (
          <Button onClick={() => window.open(job.url, "_blank", "noopener")}>
            Apply on company site <ExternalLink className="h-4 w-4" />
          </Button>
        )}
        <Button variant="outline" onClick={openAssistant}>
          <Bot className="h-4 w-4" /> Open in Assistant
        </Button>
        <Button variant={job.saved ? "secondary" : "outline"} onClick={toggleSave} disabled={saving}>
          {job.saved ? <BookmarkCheck className="h-4 w-4" /> : <Bookmark className="h-4 w-4" />}
          {job.saved ? "Saved" : "Save"}
        </Button>
        <Button variant="ghost" onClick={onClose}>
          <X className="h-4 w-4" /> Close
        </Button>
      </div>
    </Dialog>
  );
}
