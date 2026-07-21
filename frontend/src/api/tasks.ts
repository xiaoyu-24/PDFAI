import apiClient, { buildApiUrl } from "./client";
import type {
  CompareTask,
  DrawingElement,
  CompareDiff,
  DiffSummary,
  PublicSettings,
  ReportTableResponse,
  TaskListResponse,
  TaskLogListResponse,
  TaskLogSummary,
  SourceFilesResponse,
  UpdateSettingsRequest,
  AiProfile,
  AiProfileActivationResponse,
  AiProfileListResponse,
  SaveAiProfileRequest,
  LogViewMode,
  FullLogListResponse,
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

export type UploadFileFormat = "pdf" | "image";

export async function uploadTaskFiles(
  baseFile: File,
  compareFile: File,
  baseFileFormat: UploadFileFormat = "pdf",
  compareFileFormat: UploadFileFormat = "pdf"
): Promise<CompareTask> {
  const formData = new FormData();
  formData.append("base_file", baseFile);
  formData.append("compare_file", compareFile);
  formData.append("base_file_format", baseFileFormat);
  formData.append("compare_file_format", compareFileFormat);
  const { data } = await apiClient.post<CompareTask>("/tasks", formData);
  return data;
}

export async function uploadPdfs(
  baseFile: File,
  compareFile: File
): Promise<CompareTask> {
  return uploadTaskFiles(baseFile, compareFile, "pdf", "pdf");
}

export async function getTask(taskId: number): Promise<CompareTask> {
  if (!Number.isFinite(taskId)) {
    throw new Error("无效的任务ID");
  }
  const { data } = await apiClient.get<CompareTask>(`/tasks/${taskId}`);
  return data;
}

export async function getTaskLogs(
  taskId: number,
  params?: { view?: LogViewMode; level?: string; limit?: number; offset?: number; cursor?: number }
): Promise<TaskLogListResponse | FullLogListResponse> {
  const { data } = await apiClient.get(`/tasks/${taskId}/logs`, { params });
  return data;
}

export async function getSystemLogs(params?: {
  view?: LogViewMode;
  task_no?: string;
  level?: string;
  error_category?: string;
  stage?: string;
  event_type?: string;
  degraded?: boolean;
  min_response_time_ms?: number;
  limit?: number;
  offset?: number;
}): Promise<TaskLogListResponse | FullLogListResponse> {
  const { data } = await apiClient.get("/system-logs", { params });
  return data;
}

export async function getSystemLogSummary(params?: {
  task_no?: string;
  level?: string;
  error_category?: string;
  stage?: string;
  event_type?: string;
  degraded?: boolean;
  min_response_time_ms?: number;
}): Promise<TaskLogSummary> {
  const { data } = await apiClient.get<TaskLogSummary>("/system-logs/summary", { params });
  return data;
}

export async function getSourceFiles(taskId: number): Promise<SourceFilesResponse> {
  const { data } = await apiClient.get<SourceFilesResponse>(`/tasks/${taskId}/source-files`);
  return data;
}

export function getSourceFilePreviewUrl(taskId: number, role: "base" | "compare"): string {
  return buildApiUrl(`/tasks/${taskId}/source-files/${role}/preview`);
}

export function getSourceFileDownloadUrl(taskId: number, role: "base" | "compare"): string {
  return buildApiUrl(`/tasks/${taskId}/source-files/${role}/download`);
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

export async function listAiProfiles(): Promise<AiProfileListResponse> {
  const { data } = await apiClient.get<AiProfileListResponse>("/settings/ai-profiles");
  return data;
}

export async function createAiProfile(request: SaveAiProfileRequest): Promise<AiProfile> {
  const { data } = await apiClient.post<AiProfile>("/settings/ai-profiles", request);
  return data;
}

export async function updateAiProfile(
  profileId: number,
  request: Partial<SaveAiProfileRequest>
): Promise<AiProfile> {
  const { data } = await apiClient.put<AiProfile>(`/settings/ai-profiles/${profileId}`, request);
  return data;
}

export async function activateAiProfile(profileId: number): Promise<AiProfileActivationResponse> {
  const { data } = await apiClient.post<AiProfileActivationResponse>(
    `/settings/ai-profiles/${profileId}/activate`
  );
  return data;
}

export async function deleteAiProfile(profileId: number): Promise<void> {
  await apiClient.delete(`/settings/ai-profiles/${profileId}`);
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
  return buildApiUrl(`/tasks/${taskId}/exports/${type}`);
}
