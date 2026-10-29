import { cn } from "@/lib/utils";

export function Tabs({
  tabs,
  value,
  onChange,
  className,
}: {
  tabs: { value: string; label: string }[];
  value: string;
  onChange: (v: string) => void;
  className?: string;
}) {
  return (
    <div className={cn("inline-flex h-10 items-center gap-1 rounded-xl border border-border/50 bg-muted/60 p-1 text-muted-foreground", className)}>
      {tabs.map((t) => (
        <button
          key={t.value}
          onClick={() => onChange(t.value)}
          aria-pressed={value === t.value}
          className={cn(
            "inline-flex h-8 items-center justify-center whitespace-nowrap rounded-lg px-3.5 text-sm font-medium transition-all duration-200 ease-smooth focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            value === t.value ? "bg-card text-foreground shadow-soft" : "hover:bg-card/50 hover:text-foreground"
          )}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}
