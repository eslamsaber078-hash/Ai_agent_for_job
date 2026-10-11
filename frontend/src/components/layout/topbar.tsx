import { useEffect, useState } from "react";
import { Menu, Moon, Sun } from "lucide-react";
import { useTheme } from "@/context/theme";
import { api } from "@/lib/api";

export function Topbar({ onMenu }: { onMenu: () => void }) {
  const { theme, toggle } = useTheme();
  const [backendOk, setBackendOk] = useState<boolean | null>(null);

  useEffect(() => {
    let alive = true;
    const check = () => {
      api
        .get<{ status: string }>("/api/health")
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
    <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b bg-background/90 px-4 backdrop-blur">
      <button
        className="rounded-md p-1.5 text-muted-foreground hover:bg-accent lg:hidden"
        onClick={onMenu}
        aria-label="Open menu"
      >
        <Menu className="h-5 w-5" />
      </button>
      <div className="flex-1" />
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <span
          className={`inline-block h-2 w-2 rounded-full ${
            backendOk === null ? "bg-amber-400" : backendOk ? "bg-emerald-500" : "bg-red-500"
          }`}
        />
        {backendOk === null ? "Connecting…" : backendOk ? "Backend connected" : "Backend offline"}
      </div>
      <button
        onClick={toggle}
        className="rounded-md p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground"
        aria-label="Toggle theme"
      >
        {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
      </button>
    </header>
  );
}
