import { cn } from "@/lib/utils";

export function Skeleton({ className }: { className?: string }) {
  return (
    <div className={cn("relative overflow-hidden rounded-lg bg-muted", className)}>
      <div className="absolute inset-0 animate-shimmer bg-gradient-to-r from-transparent via-background/70 to-transparent" />
    </div>
  );
}

export function Spinner({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "h-5 w-5 animate-spin rounded-full border-2 border-muted-foreground/25 border-t-foreground",
        className
      )}
    />
  );
}
