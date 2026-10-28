import { NavLink } from "react-router-dom";
import {
  Bot,
  Bookmark,
  BriefcaseBusiness,
  LayoutDashboard,
  ListChecks,
  Loader2,
  LogOut,
  Radar,
  Search,
  Settings2,
  UserRound,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/context/auth";
import { useToast } from "@/context/toast";
import { useI18n } from "@/context/i18n";

const GROUPS = [
  {
    label: "Discover",
    items: [
      { to: "/", label: "Dashboard", icon: LayoutDashboard },
      { to: "/jobs", label: "Find Jobs", icon: Search },
      { to: "/matches", label: "AI Matches", icon: Radar },
      { to: "/saved", label: "Saved Jobs", icon: Bookmark },
    ],
  },
  {
    label: "Apply",
    items: [
      { to: "/applications", label: "Applications Desk", icon: ListChecks },
      { to: "/assistant", label: "AI Assistant", icon: Bot },
    ],
  },
  {
    label: "Setup",
    items: [
      { to: "/profile", label: "Resume & Profile", icon: UserRound },
      { to: "/automation", label: "Automation", icon: Settings2 },
    ],
  },
];

function initials(name: string): string {
  return name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}

export function Sidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { user, logout, busy } = useAuth();
  const { toast } = useToast();
  const { t } = useI18n();

  async function handleLogout() {
    if (busy) return;
    try {
      await logout();
    } catch {
      toast(t("Couldn't confirm sign-out. Your account is still open here — try again."), "error");
    }
  }

  return (
    <>
      {open && (
        <div className="fixed inset-0 z-40 bg-foreground/35 backdrop-blur-[2px] lg:hidden" onClick={onClose} aria-hidden />
      )}
      <aside
        className={cn(
          "fixed inset-y-0 start-0 z-50 flex w-[276px] shrink-0 flex-col border-e border-border/70 bg-card/95 backdrop-blur-xl transition-transform duration-300 lg:sticky lg:top-0 lg:z-20 lg:h-screen lg:translate-x-0",
          // The off-screen state belongs to the mobile drawer only. Without the max-lg
          // guard it also lands on desktop, and in RTL it wins over lg:translate-x-0
          // (same specificity, later in the sheet), hiding the whole sidebar.
          open ? "translate-x-0" : "max-lg:-translate-x-full max-lg:rtl:translate-x-full"
        )}
      >
        <div className="flex h-[76px] items-center gap-3 border-b border-border/60 px-5">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-lift">
            <BriefcaseBusiness className="h-5 w-5" />
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-[15px] font-bold leading-tight tracking-tight">JobHunter</p>
            <p className="truncate text-[11px] text-muted-foreground">{t("Your AI job-search desk")}</p>
          </div>
          <button
            className="rounded-lg p-1.5 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground lg:hidden"
            onClick={onClose}
            aria-label={t("Close menu")}
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <nav className="scrollbar-thin flex-1 space-y-6 overflow-y-auto px-3 py-5">
          {GROUPS.map((group) => (
            <div key={group.label}>
              <p className="px-3 pb-2 text-[10px] font-medium uppercase tracking-[0.14em] text-muted-foreground/80">
                {t(group.label)}
              </p>
              <div className="space-y-1">
                {group.items.map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.to === "/"}
                    onClick={onClose}
                    className={({ isActive }) =>
                      cn(
                        "group flex h-10 items-center gap-3 rounded-xl px-3 text-sm font-medium transition-all duration-150",
                        isActive
                          ? "bg-primary text-primary-foreground shadow-soft"
                          : "text-muted-foreground hover:bg-accent hover:text-foreground"
                      )
                    }
                  >
                    <item.icon className="h-4 w-4 shrink-0" strokeWidth={2.1} />
                    <span className="truncate">{t(item.label)}</span>
                  </NavLink>
                ))}
              </div>
            </div>
          ))}
        </nav>

        <div className="border-t border-border/60 p-3">
          {user && (
            <div className="flex items-center gap-3 rounded-xl border border-border/70 bg-muted/40 p-2.5">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary text-xs font-bold text-primary-foreground">
                {initials(user.full_name) || <UserRound className="h-4 w-4" />}
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold leading-tight" title={user.full_name}>
                  {user.full_name}
                </p>
                <p className="truncate text-[11px] text-muted-foreground">{t("Personal workspace")}</p>
              </div>
              <button
                type="button"
                onClick={() => void handleLogout()}
                disabled={busy}
                className="shrink-0 rounded-lg p-2 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground disabled:opacity-50"
                title={t("Sign out")}
                aria-label={t("Sign out")}
                aria-busy={busy}
              >
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <LogOut className="h-4 w-4" />}
              </button>
            </div>
          )}
          <p className="mt-2.5 px-2 text-[10px] leading-relaxed text-muted-foreground/80">
            {t("Private to your account. Jobs come from real public sources.")}
          </p>
        </div>
      </aside>
    </>
  );
}
