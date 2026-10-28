import { cn } from "@/lib/utils";

const variants: Record<string, string> = {
  default: "bg-primary/10 text-primary border-primary/15 dark:bg-primary/15",
  secondary: "bg-secondary text-secondary-foreground border-border/70",
  success: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/20",
  warning: "bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-500/25",
  danger: "bg-red-500/10 text-red-700 dark:text-red-400 border-red-500/20",
  outline: "border-border text-muted-foreground",
};

export function Badge({
  className,
  variant = "default",
  children,
  title,
}: {
  className?: string;
  variant?: keyof typeof variants;
  children: React.ReactNode;
  title?: string;
}) {
  return (
    <span
      title={title}
      className={cn(
        "inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[11px] font-medium leading-5",
        variants[variant],
        className
      )}
    >
      {children}
    </span>
  );
}
