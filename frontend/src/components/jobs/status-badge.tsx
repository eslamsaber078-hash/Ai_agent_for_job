import { APP_STATUSES, type Job, boardLabel, sourceLabel } from "@/lib/types";
import { Badge } from "@/components/ui/badge";

const STATUS_STYLES: Record<string, { variant: "default" | "secondary" | "success" | "warning" | "danger" | "outline"; label: string }> = {
  Discovered: { variant: "secondary", label: "Discovered" },
  Interested: { variant: "default", label: "Interested" },
  Preparing: { variant: "warning", label: "Preparing" },
  Applied: { variant: "success", label: "Applied" },
  Interview: { variant: "default", label: "Interview" },
  Offer: { variant: "success", label: "Offer" },
  Rejected: { variant: "danger", label: "Rejected" },
  Archived: { variant: "outline", label: "Archived" },
};

export function StatusBadge({ status, className }: { status: string; className?: string }) {
  const s = STATUS_STYLES[status] ?? { variant: "secondary" as const, label: status };
  return (
    <Badge variant={s.variant} className={className}>
      {s.label}
    </Badge>
  );
}

export const STATUS_OPTIONS = APP_STATUSES.map((s) => s);

export function JobTags({ job, limit = 5 }: { job: Job; limit?: number }) {
  const tags = (job.skills ?? []).slice(0, limit);
  if (!tags.length) return null;
  return (
    <div className="flex flex-wrap gap-1.5">
      {tags.map((t) => (
        <Badge key={t} variant="outline" title={t} className="max-w-full whitespace-normal break-words text-xs">
          {t}
        </Badge>
      ))}
      {(job.skills ?? []).length > limit && (
        <Badge variant="outline" className="text-xs">
          +{(job.skills ?? []).length - limit}
        </Badge>
      )}
    </div>
  );
}

export function SourceBadge({ job }: { job: Job }) {
  const board = boardLabel(job);
  const source = sourceLabel(job.source);
  const via = board !== source ? `Imported from ${source}` : undefined;
  return <Badge variant="secondary" className="shrink-0" title={via}>{board}</Badge>;
}
