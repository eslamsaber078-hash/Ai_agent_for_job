import { cn } from "@/lib/utils";
import { scoreBg } from "@/lib/format";

export function Progress({ value, color }: { value: number; color?: string }) {
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
      <div
        className={cn("h-full rounded-full transition-all duration-500", color ?? "bg-primary")}
        style={{ width: `${Math.max(0, Math.min(100, value))}%` }}
      />
    </div>
  );
}

export function ScoreBar({ value }: { value: number }) {
  return <Progress value={value} color={scoreBg(value)} />;
}
