import { useState } from "react";
import type { ReactNode } from "react";

import { AppShell } from "../layout/AppShell";
import { AlertsPage } from "../pages/AlertsPage";
import { AssistantPage } from "../pages/AssistantPage";
import { BatchDetectPage } from "../pages/BatchDetectPage";
import { DashboardPage } from "../pages/DashboardPage";
import { DetectPage } from "../pages/DetectPage";
import { HistoryPage } from "../pages/HistoryPage";
import { PredictionPage } from "../pages/PredictionPage";
import { SettingsPage } from "../pages/SettingsPage";
import { SuqianInspectionDemo } from "../pages/SuqianInspectionDemo";

export function App() {
  const [activePage, setActivePage] = useState("dashboard");

  const pages: Record<string, ReactNode> = {
    dashboard: <DashboardPage goTo={setActivePage} />,
    detect: <DetectPage />,
    batch: <BatchDetectPage />,
    suqian: <SuqianInspectionDemo />,
    history: <HistoryPage />,
    alerts: <AlertsPage />,
    prediction: <PredictionPage />,
    assistant: <AssistantPage />,
    settings: <SettingsPage />
  };

  return (
    <AppShell activePage={activePage} setActivePage={setActivePage}>
      {pages[activePage]}
    </AppShell>
  );
}
