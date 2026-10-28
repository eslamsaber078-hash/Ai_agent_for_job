import { RefreshCw, ServerCrash } from "lucide-react";
import { useI18n } from "@/context/i18n";
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
  const { t } = useI18n();
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-red-500/25 bg-red-500/[0.04] px-6 py-12 text-center">
      <ServerCrash className="h-5 w-5 text-red-500" aria-hidden />
      <h3 className="mt-4 text-[15px] font-semibold">{t("This could not be loaded")}</h3>
      <p className="mt-1.5 max-w-md text-sm leading-relaxed text-muted-foreground">{message}</p>
      <Button className="mt-5" size="sm" onClick={onRetry} disabled={busy}>
        <RefreshCw className={`h-4 w-4 ${busy ? "animate-spin" : ""}`} /> {t("Retry")}
      </Button>
    </div>
  );
}
