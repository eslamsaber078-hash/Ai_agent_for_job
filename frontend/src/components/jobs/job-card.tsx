import { Bookmark, BookmarkCheck, Briefcase, Building2, Calendar, ExternalLink, MapPin, Wallet } from "lucide-react";
import { type Job } from "@/lib/types";
import { formatSalary, timeAgo } from "@/lib/format";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { SourceBadge, JobTags } from "./status-badge";

export function JobCard({
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
  return (
    <div className="group flex h-full min-w-0 flex-col overflow-hidden rounded-xl border bg-card p-4 shadow-sm transition-shadow hover:shadow-md">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <button
            onClick={() => onOpen?.(job)}
            className="block w-full truncate text-left text-sm font-semibold hover:text-primary hover:underline"
            title={job.title}
          >
            {job.title}
          </button>
          <div className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-1 break-words text-xs text-muted-foreground">
            <span className="inline-flex items-center gap-1">
              <Building2 className="h-3 w-3" /> {job.company}
            </span>
            <span className="inline-flex items-center gap-1">
              <MapPin className="h-3 w-3" /> {job.location}
              {job.country && job.country !== job.location ? `, ${job.country}` : ""}
            </span>
            {job.remote && <Badge variant="outline" className="text-[10px]">Remote</Badge>}
          </div>
        </div>
        <SourceBadge job={job} />
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 break-words text-xs text-muted-foreground">
        <span className="inline-flex items-center gap-1">
          <Briefcase className="h-3 w-3" /> {job.employment_type || "Not specified"}
        </span>
        <span>{job.experience_level || "Level not specified"}</span>
        <span className="inline-flex items-center gap-1">
          <Wallet className="h-3 w-3" /> {formatSalary(job)}
        </span>
        <span className="inline-flex items-center gap-1">
          <Calendar className="h-3 w-3" /> {timeAgo(job.posted_date)}
        </span>
        {!job.is_active && (
          <Badge variant="warning" className="text-[10px]">No longer advertised at the source</Badge>
        )}
      </div>

      <p className="mt-3 line-clamp-2 break-words text-sm text-muted-foreground">{job.description}</p>

      <div className="mt-3 min-w-0">
        <JobTags job={job} />
      </div>

      <div className="mt-auto flex flex-wrap items-center gap-2 border-t pt-3">
        <Button variant="outline" size="sm" onClick={() => onOpen?.(job)}>
          View details
        </Button>
        {job.url && (
          <Button variant="ghost" size="sm" onClick={() => window.open(job.url, "_blank", "noopener")}>
            Apply <ExternalLink className="h-3 w-3" />
          </Button>
        )}
        <div className="ml-auto flex items-center gap-2">
          {onTrack && !job.application_status && (
            <Button variant="outline" size="sm" onClick={() => onTrack(job)}>
              Track
            </Button>
          )}
          {onSave && (
            <Button
              variant={job.saved ? "secondary" : "ghost"}
              size="sm"
              disabled={saving}
              onClick={() => onSave(job)}
              title={job.saved ? "Remove from saved" : "Save job"}
            >
              {job.saved ? <BookmarkCheck className="h-4 w-4 text-primary" /> : <Bookmark className="h-4 w-4" />}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
