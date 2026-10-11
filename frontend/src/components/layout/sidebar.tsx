import { NavLink } from "react-router-dom";
import {
  Bot,
  Briefcase,
  LayoutDashboard,
  ListChecks,
  Bookmark,
  Radar,
  Search,
  Settings2,
  UserRound,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/jobs", label: "Find Jobs", icon: Search },
  { to: "/matches", label: "AI Job Matches", icon: Radar },
  { to: "/saved", label: "Saved Jobs", icon: Bookmark },
  { to: "/applications", label: "Applications Tracker", icon: ListChecks },
  { to: "/profile", label: "Resume & Profile", icon: UserRound },
  { to: "/assistant", label: "AI Application Assistant", icon: Bot },
  { to: "/automation", label: "Automation Settings", icon: Settings2 },
];

export function Sidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  return (
    <>
      {open && (
        <div className="fixed inset-0 z-30 bg-black/50 lg:hidden" onClick={onClose} aria-hidden />
      )}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r bg-card transition-transform lg:static lg:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full"
        )}
      >
        <div className="flex h-14 items-center gap-2.5 border-b px-4">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <Briefcase className="h-4 w-4" />
          </div>
          <div className="flex-1">
            <p className="text-sm font-bold leading-tight">AI Job Hunter</p>
            <p className="text-[10px] text-muted-foreground">Your job-search agent</p>
          </div>
          <button className="rounded-md p-1 text-muted-foreground hover:bg-accent lg:hidden" onClick={onClose} aria-label="Close menu">
            <X className="h-4 w-4" />
          </button>
        </div>

        <nav className="flex-1 space-y-0.5 overflow-y-auto p-3">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              onClick={onClose}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-primary/10 text-primary"
                    : "text-muted-foreground hover:bg-accent hover:text-foreground"
                )
              }
            >
              <item.icon className="h-4 w-4 shrink-0" />
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="border-t p-4 text-[11px] leading-relaxed text-muted-foreground">
          Local single-user app. All jobs come from real public sources.
        </div>
      </aside>
    </>
  );
}
