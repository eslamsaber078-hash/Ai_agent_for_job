import { lazy } from "react";
import { HashRouter, Navigate, Route, Routes } from "react-router-dom";
import { ThemeProvider } from "@/context/theme";
import { ToastProvider } from "@/context/toast";
import { AuthProvider, ProtectedRoute } from "@/context/auth";
import { Layout } from "@/components/layout/layout";
import { LoginPage } from "@/pages/login";

// Every page behind the login is its own file the browser downloads only when it is
// opened. The chart library on the dashboard alone is bigger than the rest of the app
// put together, and making him wait for it on the login screen helped nobody.
const DashboardPage = lazy(() => import("@/pages/dashboard").then((m) => ({ default: m.DashboardPage })));
const FindJobsPage = lazy(() => import("@/pages/find-jobs").then((m) => ({ default: m.FindJobsPage })));
const MatchesPage = lazy(() => import("@/pages/matches").then((m) => ({ default: m.MatchesPage })));
const SavedJobsPage = lazy(() => import("@/pages/saved-jobs").then((m) => ({ default: m.SavedJobsPage })));
const ApplicationsPage = lazy(() => import("@/pages/applications").then((m) => ({ default: m.ApplicationsPage })));
const ProfilePage = lazy(() => import("@/pages/profile").then((m) => ({ default: m.ProfilePage })));
const AssistantPage = lazy(() => import("@/pages/assistant").then((m) => ({ default: m.AssistantPage })));
const AutomationPage = lazy(() => import("@/pages/automation").then((m) => ({ default: m.AutomationPage })));

export default function App() {
  return (
    <ThemeProvider>
      <ToastProvider>
        <HashRouter>
          <AuthProvider>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route element={<ProtectedRoute />}>
                <Route element={<Layout />}>
                  <Route path="/" element={<DashboardPage />} />
                  <Route path="/jobs" element={<FindJobsPage />} />
                  <Route path="/matches" element={<MatchesPage />} />
                  <Route path="/saved" element={<SavedJobsPage />} />
                  <Route path="/applications" element={<ApplicationsPage />} />
                  <Route path="/profile" element={<ProfilePage />} />
                  <Route path="/assistant" element={<AssistantPage />} />
                  <Route path="/automation" element={<AutomationPage />} />
                </Route>
              </Route>
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </AuthProvider>
        </HashRouter>
      </ToastProvider>
    </ThemeProvider>
  );
}
