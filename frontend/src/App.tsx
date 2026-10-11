import { HashRouter, Route, Routes } from "react-router-dom";
import { ThemeProvider } from "@/context/theme";
import { ToastProvider } from "@/context/toast";
import { Layout } from "@/components/layout/layout";
import { DashboardPage } from "@/pages/dashboard";
import { FindJobsPage } from "@/pages/find-jobs";
import { MatchesPage } from "@/pages/matches";
import { SavedJobsPage } from "@/pages/saved-jobs";
import { ApplicationsPage } from "@/pages/applications";
import { ProfilePage } from "@/pages/profile";
import { AssistantPage } from "@/pages/assistant";
import { AutomationPage } from "@/pages/automation";

export default function App() {
  return (
    <ThemeProvider>
      <ToastProvider>
        <HashRouter>
          <Routes>
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
          </Routes>
        </HashRouter>
      </ToastProvider>
    </ThemeProvider>
  );
}
