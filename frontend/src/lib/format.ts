import { translate } from "@/lib/translations";

function isAr(): boolean {
  return document.documentElement.lang === "ar";
}

export function formatSalary(job: { salary_min: number | null; salary_max: number | null; salary_currency: string | null }): string {
  if (!job.salary_min && !job.salary_max) return translate("Not disclosed");
  const cur = job.salary_currency ?? "";
  const fmt = (n: number) => n.toLocaleString("en-US");
  if (job.salary_min && job.salary_max) return `${cur} ${fmt(job.salary_min)} – ${fmt(job.salary_max)}`;
  if (job.salary_min) return `${cur} ${fmt(job.salary_min)}+`;
  return `${translate("up to")} ${cur} ${fmt(job.salary_max!)}`;
}

/** Local calendar day for an <input type="date"> — slicing a UTC string shifts the day. */
export function toInputDate(value: string | null): string {
  if (!value) return "";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

export function timeAgo(value: string | null): string {
  if (!value) return "—";
  const then = new Date(value).getTime();
  if (Number.isNaN(then)) return "—";
  const diff = Date.now() - then;
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return translate("just now");
  if (mins < 60) return translate("{mins}m ago", { mins });
  const hours = Math.floor(mins / 60);
  if (hours < 24) return translate("{hours}h ago", { hours });
  const days = Math.floor(hours / 24);
  if (days < 30) return translate("{days}d ago", { days });
  const months = Math.floor(days / 30);
  if (months < 12) return translate("{months}mo ago", { months });
  return translate("{years}y ago", { years: Math.floor(months / 12) });
}

export function formatDate(value: string | null): string {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString(isAr() ? "ar-EG" : "en-GB", { day: "2-digit", month: "short", year: "numeric" });
}

/**
 * The age line, worded to match what the source actually told us.
 *
 * "Posted" is only an honest claim when the board states the posting date. Arbeitnow
 * stamps every ad with its own crawl day and Himalayas sends no date at all, so those
 * rows say "Listed" or name the day the ad entered this tracker instead of pretending
 * to be fresh. A board that only gives a day (LinkedIn) is never shown to the hour.
 */
export function postedLabel(job: {
  posted_date?: string | null;
  first_seen?: string | null;
  date_kind?: string;
}): string {
  if (job.date_kind === "unknown" || !job.posted_date) {
    return job.first_seen ? translate("In your tracker since {date}", { date: formatDate(job.first_seen) }) : translate("Date not stated");
  }
  const word = translate(job.date_kind === "listed" ? "Listed" : "Posted");
  if (/T00:00:00(\.0+)?(\+00:00|Z)?$/.test(job.posted_date)) {
    const days = dayCount(job.posted_date);
    if (days < 1) return translate("{word} today", { word });
    if (days === 1) return translate("{word} yesterday", { word });
    return translate("{word} {days}d ago", { word, days });
  }
  return translate("{word} {ago}", { word, ago: timeAgo(job.posted_date) });
}

/** Whole calendar days between a date-only stamp and today, in his own timezone. */
function dayCount(value: string): number {
  const then = new Date(value);
  if (Number.isNaN(then.getTime())) return 0;
  const startOfDay = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  return Math.max(0, Math.round((startOfDay(new Date()) - startOfDay(then)) / 86400000));
}

export function formatDateTime(value: string | null): string {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString(isAr() ? "ar-EG" : "en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
}

/**
 * Some boards (Arbeitnow, LinkedIn) send the ad body as HTML. Printed as-is it shows
 * tags and `&nbsp;` instead of words. This turns it into readable text for display only;
 * the stored ad is never rewritten.
 */
export function plainDescription(value: string | null | undefined): string {
  if (!value) return "";
  if (!/<[a-z][\s\S]*>/i.test(value)) return value;
  const withBreaks = value
    .replace(/<\s*br\s*\/?\s*>/gi, "\n")
    .replace(/<\s*\/\s*(p|div|li|ul|ol|h[1-6]|tr)\s*>/gi, "\n")
    .replace(/<\s*li[^>]*>/gi, "• ");
  const doc = new DOMParser().parseFromString(withBreaks, "text/html");
  doc.querySelectorAll("script, style").forEach((el) => el.remove());
  return (doc.body.textContent ?? "")
    .replace(/\u00a0/g, " ")
    .replace(/[ \t]+/g, " ")
    .replace(/ *\n */g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

/**
 * A score is an estimate of fit, not a verdict, so only the top of the range is allowed
 * to carry colour. Painting everything under 60 red turned a list of ordinary matches
 * into a wall of alarms — the low numbers recede and the good ones are what the eye finds.
 */
export function scoreColor(score: number): string {
  if (score >= 80) return "text-emerald-600 dark:text-emerald-400";
  if (score >= 60) return "text-amber-600 dark:text-amber-400";
  return "text-muted-foreground";
}

export function scoreBg(score: number): string {
  if (score >= 80) return "bg-emerald-500";
  if (score >= 60) return "bg-amber-500";
  return "bg-muted-foreground/45";
}
