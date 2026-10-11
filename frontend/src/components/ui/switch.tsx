import { cn } from "@/lib/utils";

export function Switch({
  checked,
  onChange,
  disabled,
  label,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
  label?: string;
}) {
  return (
    <label className="inline-flex cursor-pointer items-center gap-2">
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={cn(
          "relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50",
          checked ? "bg-primary" : "bg-input"
        )}
      >
        <span
          className={cn(
            "inline-block h-4 w-4 transform rounded-full bg-background shadow transition-transform",
            checked ? "translate-x-[18px]" : "translate-x-[2px]"
          )}
        />
      </button>
      {label && <span className="text-sm">{label}</span>}
    </label>
  );
}
