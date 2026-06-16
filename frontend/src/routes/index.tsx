import { lazy, Suspense } from "react";
import { Routes, Route } from "react-router-dom";
import { Spin } from "antd";
import AppShell from "../components/AppShell";

const DashboardPage = lazy(() => import("../pages/DashboardPage"));
const UploadPage = lazy(() => import("../pages/UploadPage"));
const TaskProgressPage = lazy(() => import("../pages/TaskProgressPage"));
const ElementsPage = lazy(() => import("../pages/ElementsPage"));
const DiffReportPage = lazy(() => import("../pages/DiffReportPage"));
const SettingsPage = lazy(() => import("../pages/SettingsPage"));
const TaskPickerPage = lazy(() => import("../pages/TaskPickerPage"));

export default function AppRoutes() {
  return (
    <Suspense fallback={<Spin fullscreen tip="加载中..." />}>
      <Routes>
        <Route element={<AppShell />}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/tasks/new" element={<UploadPage />} />
          <Route path="/tasks" element={<TaskPickerPage />} />
          <Route path="/diffs" element={<TaskPickerPage />} />
          <Route path="/elements" element={<TaskPickerPage />} />
          <Route path="/tasks/:taskId" element={<TaskProgressPage />} />
          <Route path="/tasks/:taskId/elements" element={<ElementsPage />} />
          <Route path="/tasks/:taskId/diffs" element={<DiffReportPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Route>
      </Routes>
    </Suspense>
  );
}
