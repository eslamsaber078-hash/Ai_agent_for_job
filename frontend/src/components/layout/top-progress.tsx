import { useEffect, useRef, useState } from "react";
import { useI18n } from "@/context/i18n";
import { useProgress } from "@/lib/progress";

/** The thin bar under the window's top edge, plus a floating percentage pill.
 *
 *  The number is real wherever reality provides one: during a multi-site import it
 *  is exactly sites-done / sites-total. For ordinary requests the bar advances at a
 *  pace derived from how long your recent requests actually took (avgMs), so a slow
 *  backend makes a slow bar and a fast one finishes instantly — it never invents a
 *  fake byte count. */
export function TopProgress() {
  const { pending, task, avgMs, slow } = useProgress();
  const { t } = useI18n();
  const busy = pending > 0 || task !== null;
  const [pct, setPct] = useState(0);
  const [shown, setShown] = useState(false);
  const shownRef = useRef(false);
  const pctRef = useRef(0);
  const hideTimer = useRef<number | undefined>(undefined);

  useEffect(() => {
    if (busy && !shownRef.current) {
      clearTimeout(hideTimer.current); // a new request inside the fade window stays visible
      shownRef.current = true;
      setShown(true);
    }
  }, [busy]);

  useEffect(() => {
    let raf = 0;
    let last = performance.now();
    const frame = (now: number) => {
      const dt = Math.min(0.1, (now - last) / 1000);
      last = now;
      const p = pctRef.current;
      if (busy) {
        if (task) {
          const target = task.total > 0 ? (task.done / task.total) * 100 : 0;
          pctRef.current = p + (Math.max(target, p) - p) * (1 - Math.exp(-dt * 9));
        } else {
          // Trickle toward 90% at the pace of the average real request time,
          // so the bar reaches ~90% right around when the response usually lands.
          // avgMs is milliseconds; 90000 = 90% x 1000ms gives % per second.
          // Never drop below a value a finished task already reached.
          const rate = 90000 / Math.max(800, avgMs);
          pctRef.current = p >= 90 ? p : Math.min(90, p + rate * dt);
        }
        setPct(pctRef.current);
        raf = requestAnimationFrame(frame);
        return;
      }
      // All requests done: complete the bar with a gentle finish (~0.5-0.9s),
      // regardless of where it currently is, then fade it out and reset.
      const next = p + (100 - p) * (1 - Math.exp(-dt * 6.5));
      pctRef.current = next;
      if (next >= 99.7) {
        setPct(100);
        hideTimer.current = window.setTimeout(() => {
          shownRef.current = false;
          setShown(false);
          pctRef.current = 0;
          setPct(0);
        }, 350);
        return;
      }
      setPct(next);
      raf = requestAnimationFrame(frame);
    };
    if (shown) raf = requestAnimationFrame(frame);
    return () => {
      cancelAnimationFrame(raf);
      clearTimeout(hideTimer.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [busy, task, shown]);

  if (!shown) return null;

  const label = task ? `${task.label} ${task.done}/${task.total}` : slow ? t("Waking the server") : t("Loading");

  return (
    <>
      <div className="pointer-events-none fixed inset-x-0 top-0 z-50 h-[3px]">
        <div
          className="h-full bg-primary shadow-[0_0_10px_hsl(var(--primary)/0.5)]"
          style={{ width: `${pct}%` }}
        />
      </div>
      <div className="pointer-events-none fixed start-1/2 top-2 z-50 -translate-x-1/2">
        <span className="inline-flex max-w-[80vw] items-center gap-2 rounded-full bg-primary px-3 py-1 text-[11px] font-semibold text-primary-foreground shadow-md">
          {!task && (
            <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-primary-foreground/30 border-t-primary-foreground" />
          )}
          {label} · {Math.round(pct)}%
        </span>
      </div>
    </>
  );
}
