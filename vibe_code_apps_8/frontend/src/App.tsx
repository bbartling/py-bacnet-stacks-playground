import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { ThemeProvider } from "@/contexts/theme-context";
import { AppLayout } from "@/components/layout/AppLayout";
import { BasOverviewPage } from "@/components/pages/BasOverviewPage";
import { BasLivePointsPage } from "@/components/pages/BasLivePointsPage";
import { BasDriverConfigPage } from "@/components/pages/BasDriverConfigPage";
import { BasSystemPage } from "@/components/pages/BasSystemPage";
import { BasFaultsPage } from "@/components/pages/BasFaultsPage";
import { BasAlarmsPage } from "@/components/pages/BasAlarmsPage";
import { BasSchedulePage } from "@/components/pages/BasSchedulePage";
import { BasDocsPage } from "@/components/pages/BasDocsPage";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: true },
  },
});

function routerBasename(): string | undefined {
  const b = import.meta.env.BASE_URL ?? "/";
  if (b === "/" || b === "") return undefined;
  return b.endsWith("/") ? b.slice(0, -1) : b;
}

function App() {
  return (
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter basename={routerBasename()}>
          <Routes>
            <Route element={<AppLayout />}>
              <Route index element={<BasOverviewPage />} />
              <Route path="live-points" element={<BasLivePointsPage />} />
              <Route path="driver" element={<BasDriverConfigPage />} />
              <Route path="system" element={<BasSystemPage />} />
              <Route path="faults" element={<BasFaultsPage />} />
              <Route path="alarms" element={<BasAlarmsPage />} />
              <Route path="schedule" element={<BasSchedulePage />} />
              <Route path="docs" element={<BasDocsPage />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </QueryClientProvider>
    </ThemeProvider>
  );
}

export default App;
