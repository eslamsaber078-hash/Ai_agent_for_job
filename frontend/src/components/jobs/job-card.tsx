import { memo } from "react";
import { Bookmark, BookmarkCheck, ExternalLink } from "lucide-react";
import { type Job } from "@/lib/types";
import { formatSalary, plainDescription, postedLabel } from "@/lib/format";
import { employmentTypeLabel } from "@/lib/employment-type";
import { useI18n } from "@/context/i18n";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { SourceBadge, JobTags } from "./status-badge";

export const JobCard = memo(function JobCard({
  job,
  onSave,
  onOpen,
  onTrack,
  saving,
}: {
  job: Job;
  onSave?: (job: Job) => void;
  onOpen?: (job: Job) => void;
  onTrack?: (job: Job) => void;
  saving?: boolean;
}) {
  const { t, tt, lang } = useI18n();
  return (
    <article className="group flex h-full min-w-0 flex-col overflow-hidden rounded-xl border border-border/80 bg-card p-5 shadow-soft transition-colors duration-200 hover:border-foreground/25 hover:bg-muted/30">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <button
            onClick={() => onOpen?.(job)}
            className="block w-full text-start text-[15px] font-semibold leading-snug tracking-tight transition-colors hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            title={job.title}
          >
            <span className="line-clamp-2">{job.title}</span>
          </button>
          <p className="mt-1.5 truncate text-[13px] text-muted-foreground" title={`${job.company} · ${job.location}`}>
            {job.company}
            <span className="mx-1.5 text-muted-foreground/50">·</span>
            {job.location}
            {job.country && job.country !== job.location ? `, ${job.country}` : ""}
          </p>
        </div>
        <SourceBadge job={job} />
      </div>

      <p className="mt-3 flex flex-wrap items-center gap-x-1.5 text-xs text-muted-foreground">
        {employmentTypeLabel(job.employment_type, t, lang) || t("Type n/a")}
        <span className="text-muted-foreground/50">·</span>
        {tt(job.experience_level) || t("Level n/a")}
        {job.remote && (
          <>
            <span className="text-muted-foreground/50">·</span>
            <span className="text-emerald-700 dark:text-emerald-400">{t("Remote")}</span>
          </>
        )}
        {!job.is_active && <Badge variant="warning" className="ms-1">{t("No longer advertised")}</Badge>}
      </p>

      <p className="mt-3 line-clamp-2 break-words text-[13px] leading-relaxed text-muted-foreground">
        {plainDescription(job.description)}
      </p>

      <div className="mt-3 min-w-0">
        <JobTags job={job} limit={4} />
      </div>

      <p className="nums mt-3.5 flex flex-wrap items-center gap-x-1.5 text-[11px] text-muted-foreground">
        {formatSalary(job)}
        <span className="text-muted-foreground/50">·</span>
        {postedLabel(job)}
      </p>

      <div className="mt-auto flex flex-wrap items-center gap-2 border-t border-border/60 pt-4">
        <Button variant="outline" size="sm" onClick={() => onOpen?.(job)}>
          {t("View details")}
        </Button>
        {job.url && (
          <Button variant="ghost" size="sm" onClick={() => window.open(job.url, "_blank", "noopener")}>
            {t("Apply")} <ExternalLink className="h-3 w-3" />
          </Button>
        )}
        <div className="ms-auto flex items-center gap-1.5">
          {onTrack && !job.application_status && (
            <Button variant="outline" size="sm" onClick={() => onTrack(job)}>
              {t("Track")}
            </Button>
          )}
          {onSave && (
            <Button
              variant={job.saved ? "secondary" : "ghost"}
              size="icon"
              className="h-8 w-8"
              disabled={saving}
              onClick={() => onSave(job)}
              title={job.saved ? t("Remove from saved") : t("Save job")}
              aria-label={job.saved ? t("Remove from saved") : t("Save job")}
            >
              {job.saved ? <BookmarkCheck className="h-4 w-4 text-primary" /> : <Bookmark className="h-4 w-4" />}
            </Button>
          )}
        </div>
      </div>
    </article>
  );
});
