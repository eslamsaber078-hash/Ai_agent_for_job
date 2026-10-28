import { useEffect, useId, useRef, type ReactNode } from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";
import { useI18n } from "@/context/i18n";
import { Button } from "./button";

interface DialogProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  description?: string;
  children: ReactNode;
  wide?: boolean;
}

// Dialogs nest (the application pack opens inside a job), and every open one used to answer
// the same Escape keypress: both vanished at once and the pack he had just prepared looked
// lost. Only the topmost dialog gets the key, and scrolling unlocks when the last one goes.
// The stack holds a per-instance id, never the callback, because callers pass a new arrow
// function on every render and the registration would churn.
const openStack: symbol[] = [];

const FOCUSABLE =
  'a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])';

export function Dialog({ open, onClose, title, description, children, wide }: DialogProps) {
  const { t } = useI18n();
  const self = useRef<symbol>(Symbol("dialog")).current;
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  const panelRef = useRef<HTMLDivElement>(null);
  const returnRef = useRef<HTMLElement | null>(null);
  const titleId = useId();
  const descriptionId = useId();

  useEffect(() => {
    if (!open) return;
    openStack.push(self);
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape" && openStack[openStack.length - 1] === self) closeRef.current();
    };
    window.addEventListener("keydown", handler);
    document.body.style.overflow = "hidden";
    return () => {
      const i = openStack.lastIndexOf(self);
      if (i >= 0) openStack.splice(i, 1);
      window.removeEventListener("keydown", handler);
      if (openStack.length === 0) document.body.style.overflow = "";
    };
  }, [open, self]);

  useEffect(() => {
    if (!open) return;
    // A keyboard user who just pressed "Apply" expects to be inside the dialog that
    // opened, and expects Tab to stay inside it until it closes.
    returnRef.current = document.activeElement as HTMLElement | null;
    panelRef.current?.focus();
    const trap = (e: KeyboardEvent) => {
      if (e.key !== "Tab" || !panelRef.current) return;
      const items = [...panelRef.current.querySelectorAll<HTMLElement>(FOCUSABLE)].filter(
        (el) => el.offsetParent !== null
      );
      if (items.length === 0) return;
      const first = items[0];
      const last = items[items.length - 1];
      const active = document.activeElement;
      if (e.shiftKey && (active === first || active === panelRef.current)) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && active === last) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", trap);
    return () => {
      document.removeEventListener("keydown", trap);
      // Back to the button that opened this dialog, so the next Tab is not a mystery.
      returnRef.current?.focus?.();
    };
  }, [open]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto p-3 sm:p-6 lg:p-8">
      <div className="fixed inset-0 bg-foreground/35 backdrop-blur-[3px] dark:bg-black/65" onClick={onClose} aria-hidden />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={title ? titleId : undefined}
        aria-describedby={description ? descriptionId : undefined}
        tabIndex={-1}
        className={cn(
          "animate-fade-up relative z-10 my-auto flex max-h-[calc(100vh-1.5rem)] w-full flex-col overflow-hidden rounded-2xl border border-border/80 bg-card shadow-pop focus:outline-none sm:max-h-[calc(100vh-3rem)]",
          wide ? "max-w-3xl" : "max-w-lg"
        )}
      >
        <div className="flex shrink-0 items-start justify-between gap-4 border-b border-border/70 bg-card/95 p-5 backdrop-blur sm:p-6">
          <div className="min-w-0">
            {title && <h2 id={titleId} className="break-words text-lg font-semibold leading-snug tracking-tight">{title}</h2>}
            {description && <p id={descriptionId} className="mt-1 break-words text-sm text-muted-foreground">{description}</p>}
          </div>
          <button
            onClick={onClose}
            className="shrink-0 rounded-lg p-1.5 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            aria-label={t("Close")}
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="scrollbar-thin min-h-0 overflow-y-auto p-5 sm:p-6">{children}</div>
      </div>
    </div>
  );
}

export function ConfirmDialog({
  open,
  onClose,
  onConfirm,
  title,
  message,
  confirmLabel,
}: {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  message: string;
  confirmLabel?: string;
}) {
  const { t } = useI18n();
  return (
    <Dialog open={open} onClose={onClose} title={title}>
      <p className="text-sm leading-relaxed text-muted-foreground">{message}</p>
      <div className="mt-6 flex justify-end gap-2">
        <Button variant="outline" onClick={onClose}>{t("Cancel")}</Button>
        <Button
          variant="destructive"
          onClick={() => {
            onConfirm();
            onClose();
          }}
        >
          {confirmLabel ?? t("Delete")}
        </Button>
      </div>
    </Dialog>
  );
}
