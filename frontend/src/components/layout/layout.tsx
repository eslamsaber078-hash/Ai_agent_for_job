import { Suspense, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { Sidebar } from "@/components/layout/sidebar";
import { Topbar } from "@/components/layout/topbar";
import { TopProgress } from "@/components/layout/top-progress";
import { ErrorBoundary } from "@/components/error-boundary";

// Shown for the moment a page's own file is still arriving. It stands where the page
// will stand, with the sidebar and top bar still in place, so the screen never jumps.
function PageGap() {
  return (
    <div className="space-y-3 py-2" aria-busy="true" aria-label="Loading this page">
      {[0, 1, 2].map((i) => (
        <div key={i} className="h-16 animate-pulse rounded-xl border bg-muted/30" />
      ))}
    </div>
  );
}

export function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { pathname } = useLocation();
  return (
    <div className="flex min-h-screen">
      <TopProgress />
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar onMenu={() => setSidebarOpen(true)} />
        <main className="mx-auto w-full max-w-[1440px] flex-1 px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <Suspense fallback={<PageGap />}>
            <ErrorBoundary key={pathname}>
              <Outlet />
            </ErrorBoundary>
          </Suspense>
        </main>
      </div>
    </div>
  );
}
