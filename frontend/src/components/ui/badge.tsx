import { cn } from "@/lib/utils";

const variants: Record<string, string> = {
  default: "bg-primary/8 text-primary dark:bg-primary/15",
  secondary: "bg-secondary text-secondary-foreground",
  success: "bg-emerald-500/12 text-emerald-700 dark:text-emerald-400",
  warning: "bg-amber-500/14 text-amber-700 dark:text-amber-400",
  danger: "bg-red-500/12 text-red-700 dark:text-red-400",
  outline: "border border-border text-muted-foreground",
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
        "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] font-medium leading-5",
        variants[variant],
        className
      )}
    >
      {children}
    </span>
  );
}
