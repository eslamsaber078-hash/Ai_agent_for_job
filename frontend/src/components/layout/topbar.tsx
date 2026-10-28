import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { Menu, Moon, Sun } from "lucide-react";
import { useTheme } from "@/context/theme";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

const PAGE_LABELS: Record<string, string> = {
  "/": "Dashboard",
  "/jobs": "Find Jobs",
  "/matches": "AI Matches",
  "/saved": "Saved Jobs",
  "/applications": "Applications Desk",
  "/assistant": "AI Assistant",
  "/profile": "Resume & Profile",
  "/automation": "Automation",
};

export function Topbar({ onMenu }: { onMenu: () => void }) {
  const { theme, toggle } = useTheme();
  const { pathname } = useLocation();
  const [backendOk, setBackendOk] = useState<boolean | null>(null);
  const pageLabel = PAGE_LABELS[pathname] ?? "Workspace";

  useEffect(() => {
    let alive = true;
    const check = () => {
      api
        .get<{ status: string }>("/api/health", { track: false, retries: 0 })
        .then(() => alive && setBackendOk(true))
        .catch(() => alive && setBackendOk(false));
    };
    check();
    const t = setInterval(check, 30000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, []);

  return (
    <header className="sticky top-0 z-30 flex h-16 shrink-0 items-center gap-3 border-b border-border/60 bg-background/75 px-4 backdrop-blur-xl sm:px-6 lg:px-8">
      <button
        className="rounded-lg p-2 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground lg:hidden"
        onClick={onMenu}
        aria-label="Open menu"
      >
        <Menu className="h-5 w-5" />
      </button>

      <div className="min-w-0 flex-1">
        <p className="text-[10px] font-medium uppercase tracking-[0.14em] text-muted-foreground/80">Workspace</p>
        <p className="truncate text-sm font-semibold leading-tight">{pageLabel}</p>
      </div>

      <div
        className={cn(
          "hidden h-8 items-center gap-2 rounded-full border border-border/70 bg-card/70 px-3 text-xs font-medium text-muted-foreground sm:inline-flex",
          backendOk === false && "border-red-500/25 bg-red-500/5 text-red-600 dark:text-red-400"
        )}
        title={backendOk === null ? "Checking the backend" : backendOk ? "Backend connected" : "Backend offline — start it on port 8000"}
      >
        <span
          className={cn(
            "inline-block h-2 w-2 rounded-full",
            backendOk === null ? "animate-pulse bg-amber-400" : backendOk ? "bg-emerald-500" : "bg-red-500"
          )}
        />
        {backendOk === null ? "Connecting" : backendOk ? "All systems ready" : "Backend offline"}
      </div>

      <button
        onClick={toggle}
        className="rounded-lg p-2 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
        title={theme === "dark" ? "Light mode" : "Dark mode"}
      >
        {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
      </button>
    </header>
  );
}
