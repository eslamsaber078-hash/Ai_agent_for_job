import { useCallback, useRef, useState } from "react";
import { CheckCircle2, Circle } from "lucide-react";
import { type Job } from "@/lib/types";
import { api } from "@/lib/api";
import { useToast } from "@/context/toast";
import { useI18n } from "@/context/i18n";

/** Desk stages that say nothing has been sent yet, so the tick is still free to move. */
const BEFORE_APPLY = new Set<string | null>([null, "Discovered", "Interested", "Preparing"]);

/** Whether pressing the ad's apply route should check this posting off. */
export const marksOnApply = (job: Job) => BEFORE_APPLY.has(job.application_status ?? null);

/** The three fields the tick moves on a job, and nothing else. */
type AppliedPatch = Pick<Job, "application_status" | "application_id" | "application_docs">;

/**
 * What a page answers to a tick press. Handing the request back as a promise is what
 * lets the chip hold its one press until the desk has actually moved.
 */
export type AppliedResult = void | Promise<boolean | void>;

/**
 * Toggle "I applied" on the server and hand back the stage it actually kept.
 *
 * Every page that lists jobs holds its own copy of each job, so the caller gets the
 * patch and decides which of its lists to write it into.
 */
export function useAppliedMark(patch: (jobId: number, fields: AppliedPatch) => void) {
  const { toast } = useToast();
  const { t, tt } = useI18n();
  // A page can reach the desk through more than one door — the chip on a card, the
  // Apply button on a ranking row, the same button in a detail sheet. The chip holds
  // back its own second press, but those buttons do not, so the request is held back
  // here instead: two clicks on the same job are one click.
  const inFlight = useRef<Set<number>>(new Set());
  return useCallback(
    // Only the id is needed: the desk stage the server keeps is what comes back.
    // Ranking rows carry no desk state, so they tick through this and read the
    // result when the full posting is opened. Resolves to whether the press landed,
    // so the chip can let go of a press the desk refused.
    async (job: { id: number }, applied: boolean) => {
      if (inFlight.current.has(job.id)) return false;
      inFlight.current.add(job.id);
      try {
        const fresh = applied
          ? await api.post<Job>(`/api/jobs/${job.id}/applied`)
          : await api.delete<Job>(`/api/jobs/${job.id}/applied`);
        // A posting already at interview, offer or rejected is left where it is by
        // design, so the toast reports the stage the desk actually kept. Taking the
        // mark off a posting with a pack keeps the documents and says so.
        toast(applied
          ? fresh.application_status === "Applied"
            ? t("Marked as applied")
            : t("Still {stage} in your desk", { stage: tt(fresh.application_status ?? "") })
          : fresh.application_docs
            ? t("Applied mark removed — the pack stays in your desk")
            : t("Applied mark removed"));
        patch(job.id, {
          application_status: fresh.application_status,
          application_id: fresh.application_id,
          application_docs: fresh.application_docs,
        });
        return true;
      } catch (e: any) {
        toast(e.message, "error");
        return false;
      } finally {
        inFlight.current.delete(job.id);
      }
    },
    [patch, t, tt, toast]
  );
}

/**
 * The "I applied" tick on a posting.
 *
 * Pressing the ad's apply route sets it, and pressing the tick takes it back off —
 * even when a prepared pack sits behind it, which stays in the desk untouched. Only
 * a posting that already reached an interview, an offer or a rejection shows its
 * stage without a button: that is a record of what happened, not a mark to undo.
 */
export function AppliedMark({ job, onToggle }: {
  job: Job;
  onToggle?: (applied: boolean) => AppliedResult;
}) {
  const { t, tt } = useI18n();
  const stage = job.application_status ?? null;
  const beforeApply = BEFORE_APPLY.has(stage);
  const ticked = stage === "Applied";
  const togglable = beforeApply || ticked;
  // One press at a time, and one that knows what it just did. Without this a second
  // click lands before the server answer is rendered, reads the old stage, and puts
  // the mark straight back on — which is how it started refusing to come off.
  const [pressed, setPressed] = useState<"idle" | "on" | "off">("idle");

  const shown = pressed === "idle" ? ticked : pressed === "on";

  const classes = shown
    ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400"
    : beforeApply
      ? "border-transparent text-muted-foreground hover:border-border hover:bg-muted"
      : "border-border bg-muted/60 text-foreground";

  const inner = (
    <>
      {shown || !beforeApply ? <CheckCircle2 className="h-3.5 w-3.5" /> : <Circle className="h-3.5 w-3.5" />}
      {beforeApply ? t("Applied") : tt(stage!)}
    </>
  );

  if (!togglable || !onToggle) {
    return (
      <span
        className={`inline-flex items-center gap-1 rounded-md border px-2 py-1 text-[11px] font-semibold ${classes}`}
        title={t("This stage comes from your Applications Desk")}
      >
        {inner}
      </span>
    );
  }

  const label = shown ? t("I have not actually applied yet") : t("I applied to this");

  return (
    <button
      type="button"
      // The press shows on the chip at once, then hands over to what the desk kept.
      disabled={pressed !== "idle"}
      onClick={() => {
        if (pressed !== "idle") return;
        setPressed(shown ? "off" : "on");
        Promise.resolve(onToggle(!shown)).finally(() => setPressed("idle"));
      }}
      title={label}
      aria-label={label}
      aria-pressed={shown}
      className={`inline-flex items-center gap-1 rounded-md border px-2 py-1 text-[11px] font-medium transition-colors ${classes} ${shown ? "font-semibold hover:bg-emerald-500/20" : ""} ${pressed !== "idle" ? "cursor-wait opacity-70" : ""}`}
    >
      {inner}
    </button>
  );
}
