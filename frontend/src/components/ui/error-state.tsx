import { RefreshCw, ServerCrash } from "lucide-react";
import { Button } from "./button";

export function ErrorState({
  message,
  onRetry,
  busy,
}: {
  message: string;
  onRetry: () => void;
  busy?: boolean;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-red-500/40 bg-red-500/5 px-6 py-14 text-center">
      <div className="rounded-full bg-red-500/10 p-4">
        <ServerCrash className="h-7 w-7 text-red-500" />
      </div>
      <h3 className="mt-4 text-base font-semibold">This could not be loaded</h3>
      <p className="mt-1 max-w-md text-sm text-muted-foreground">{message}</p>
      <Button className="mt-5" size="sm" onClick={onRetry} disabled={busy}>
        <RefreshCw className={`h-4 w-4 ${busy ? "animate-spin" : ""}`} /> Retry
      </Button>
    </div>
  );
}
