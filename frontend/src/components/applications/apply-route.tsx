import { Copy, ExternalLink, Mail } from "lucide-react";
import { type Job, boardLabel } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useToast } from "@/context/toast";
import { useI18n } from "@/context/i18n";

const CHANNEL_LABEL: Record<string, string> = {
  email: "Email",
  "company-link": "Company page",
  listing: "Board page",
  unknown: "Not stated",
};

/** A badge naming the route this ad asked for — never a guess. */
export function ApplyRouteTag({ job }: { job: Job }) {
  const { t } = useI18n();
  return (
    <Badge
      variant={job.apply_channel === "email" || job.apply_channel === "company-link" ? "success" : "outline"}
      className="whitespace-nowrap text-[10px]"
      title={job.apply_note}
    >
      {t(CHANNEL_LABEL[job.apply_channel] ?? "Board page")}
    </Badge>
  );
}

/** A mailto draft: his mail program opens with the text ready, and he presses send. */
function mailto(job: Job, body: string): string {
  const email = job.apply_emails[0];
  if (!/^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$/.test(email || "")) return "";
  const subject = `Application for ${job.title}${job.company ? ` — ${job.company}` : ""}`;
  // The drafted email already begins with its own "Subject:" line; the header carries it.
  // A mailto cannot carry a file, so the sentence claiming one is dropped must be replaced,
  // not left to send him off with an attachment that was never attached.
  const cleaned = body
    .replace(/^Subject:[^\n]*\n+/, "")
    .replace(/My resume is attached\./i, "[Attach your CV to this message before you send it]");
  return `mailto:${email}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(cleaned)}`;
}

/**
 * The route the ad itself named: an address it wrote, its own careers page, or nothing but
 * the board listing. `emailBody` lets the prepared application text ride inside the mailto.
 */
export function ApplyRoute({ job, emailBody }: { job: Job; emailBody?: string }) {
  const { toast } = useToast();
  const { t } = useI18n();
  const copy = (text: string, what: string) => {
    navigator.clipboard.writeText(text)
      .then(() => toast(t("{what} copied", { what })))
      .catch(() => toast(t("Could not copy — select it manually"), "error"));
  };
  const mailHref = mailto(job, emailBody || `Dear Hiring Team,\n\nI am applying for ${job.title}.\n\n[Your name]`);
  const link = job.apply_links[0];

  return (
    <div className="rounded-xl border border-border/80 bg-muted/40 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-[11px] font-medium uppercase tracking-[0.12em] text-muted-foreground">
          {t("How to apply")}
        </p>
        <ApplyRouteTag job={job} />
      </div>
      <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">{job.apply_note}</p>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        {job.apply_channel === "email" && mailHref && (
          <a
            href={mailHref}
            className="inline-flex h-9 items-center gap-2 rounded-lg bg-primary px-3.5 text-xs font-semibold text-primary-foreground shadow-soft transition-colors hover:bg-primary/90"
          >
            <Mail className="h-3.5 w-3.5" /> {t("Open the mail draft")}
          </a>
        )}
        {job.apply_channel === "company-link" && link && (
          <Button size="sm" onClick={() => window.open(link, "_blank", "noopener")}>
            <ExternalLink className="h-3.5 w-3.5" /> {t("Open the company page")}
          </Button>
        )}
        {(job.apply_channel === "listing" || job.apply_channel === "unknown") && job.url && (
          <Button size="sm" onClick={() => window.open(job.url, "_blank", "noopener")}>
            <ExternalLink className="h-3.5 w-3.5" /> {t("Apply on {board}", { board: boardLabel(job) })}
          </Button>
        )}
        {job.apply_emails.map((e) => (
          <button
            key={e}
            onClick={() => copy(e, t("Address"))}
            title={t("Copy this address")}
            className="inline-flex items-center gap-1.5 rounded-lg border border-border/80 bg-card px-2.5 py-1.5 text-xs transition-colors hover:bg-accent"
          >
            <Mail className="h-3 w-3 text-muted-foreground" /> {e}
            <Copy className="h-3 w-3 text-muted-foreground" />
          </button>
        ))}
        {job.apply_links.filter((l) => l !== link).map((l) => (
          <button
            key={l}
            onClick={() => window.open(l, "_blank", "noopener")}
            title={t("Open this page")}
            className="inline-flex items-center gap-1.5 rounded-lg border border-border/80 bg-card px-2.5 py-1.5 text-xs transition-colors hover:bg-accent"
          >
            <ExternalLink className="h-3 w-3 text-muted-foreground" />
            {l.replace(/^https?:\/\//, "").slice(0, 40)}
          </button>
        ))}
      </div>

      <p className="mt-3 text-[11px] leading-relaxed text-muted-foreground">
        {t("Read from the ad itself. Nothing leaves this app: the mail draft only opens in your own program, and you press send.")}
      </p>
    </div>
  );
}
