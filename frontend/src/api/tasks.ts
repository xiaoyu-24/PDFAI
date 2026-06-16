import apiClient from "./client";
import type {
  CompareTask,
  DrawingElement,
  CompareDiff,
  DiffSummary,
  PublicSettings,
  ReportTableResponse,
  TaskListResponse,
  UpdateSettingsRequest,
} from "../types";

export async function listTasks(params?: {
  status?: string;
  keyword?: string;
  limit?: number;
  offset?: number;
}): Promise<TaskListResponse> {
  const { data } = await apiClient.get<TaskListResponse>("/tasks", { params });
  return data;
}

export async function uploadPdfs(
  baseFile: File,
  compareFile: File
): Promise<CompareTask> {
  const formData = new FormData();
  formData.append("base_file", baseFile);
  formData.append("compare_file", compareFile);
  const { data } = await apiClient.post<CompareTask>("/tasks", formData);
  return data;
}

export async function getTask(taskId: number): Promise<CompareTask> {
  if (!Number.isFinite(taskId)) {
    throw new Error("无效的任务ID");
  }
  const { data } = await apiClient.get<CompareTask>(`/tasks/${taskId}`);
  return data;
}

export async function pauseTask(taskId: number): Promise<CompareTask> {
  const { data } = await apiClient.post<CompareTask>(`/tasks/${taskId}/pause`);
  return data;
}

export async function resumeTask(taskId: number): Promise<CompareTask> {
  const { data } = await apiClient.post<CompareTask>(`/tasks/${taskId}/resume`);
  return data;
}

export async function retryTask(taskId: number): Promise<CompareTask> {
  try {
    const { data } = await apiClient.post<CompareTask>(`/tasks/${taskId}/retry`);
    return data;
  } catch (error) {
    if (error instanceof Error && error.message === "Not Found") {
      throw new Error("重试接口未加载，请重启后端服务后再重试。", { cause: error });
    }
    throw error;
  }
}

export async function deleteTask(taskId: number): Promise<void> {
  await apiClient.delete(`/tasks/${taskId}`);
}

export async function getTaskElements(
  taskId: number,
  params?: Record<string, string>
): Promise<DrawingElement[]> {
  const { data } = await apiClient.get<DrawingElement[]>(
    `/tasks/${taskId}/elements`,
    { params }
  );
  return data;
}

export async function getTaskDiffs(
  taskId: number
): Promise<CompareDiff[]> {
  const { data } = await apiClient.get<CompareDiff[]>(
    `/tasks/${taskId}/diffs`
  );
  return data;
}

export async function getTaskDiffSummary(taskId: number): Promise<DiffSummary> {
  const { data } = await apiClient.get<DiffSummary>(
    `/tasks/${taskId}/diff-summary`
  );
  return data;
}

export async function getTaskReportTable(taskId: number): Promise<ReportTableResponse> {
  const { data } = await apiClient.get<ReportTableResponse>(
    `/tasks/${taskId}/report-table`
  );
  return data;
}

export async function getSettings(): Promise<PublicSettings> {
  const { data } = await apiClient.get<PublicSettings>("/settings");
  return data;
}

export async function updateSettings(
  request: UpdateSettingsRequest
): Promise<PublicSettings> {
  const { data } = await apiClient.put<PublicSettings>("/settings", request);
  return data;
}

export async function reviewDiff(
  diffId: number,
  payload: {
    review_status: string;
    reviewer_comment?: string;
    risk_level?: string;
  }
): Promise<CompareDiff> {
  const { data } = await apiClient.patch<CompareDiff>(
    `/tasks/diffs/${diffId}/review`,
    payload
  );
  return data;
}

export function getExportUrl(
  taskId: number,
  type: "diffs" | "elements" | "final"
): string {
  return `/api/tasks/${taskId}/exports/${type}`;
}
