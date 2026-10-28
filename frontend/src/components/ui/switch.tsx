import { cn } from "@/lib/utils";

export function Switch({
  checked,
  onChange,
  disabled,
  label,
  ariaLabel,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
  label?: string;
  ariaLabel?: string;
}) {
  return (
    <label className="inline-flex cursor-pointer items-center gap-2.5">
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        // A switch with its name in a neighbouring heading still needs an accessible one.
        aria-label={ariaLabel ?? label}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={cn(
          "relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:opacity-50",
          checked ? "bg-primary" : "bg-input"
        )}
      >
        <span
          className={cn(
            "inline-block h-5 w-5 transform rounded-full bg-background shadow-sm transition-transform duration-200",
            checked ? "translate-x-[22px]" : "translate-x-[2px]"
          )}
        />
      </button>
      {label && <span className="text-sm">{label}</span>}
    </label>
  );
}
