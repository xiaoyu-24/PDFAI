export interface PdfFile {
  id: number;
  original_name: string;
  stored_path: string;
  file_hash: string;
  page_count: number;
  file_role: "base" | "compare";
  status: string;
  created_at: string;
}

export interface PdfPage {
  id: number;
  file_id: number;
  page_no: number;
  image_path: string;
  width: number;
  height: number;
  dpi: number;
  created_at: string;
}

export interface PageRegion {
  id: number;
  file_id: number;
  page_id: number;
  page_no: number;
  region_type: string;
  region_name: string;
  crop_image_path: string | null;
  bbox_json: { x: number; y: number; width: number; height: number };
  ai_reason: string | null;
  created_at: string;
}

export interface DrawingElement {
  id: number;
  file_id: number;
  page_id: number | null;
  region_id: number | null;
  extraction_run_id: number | null;
  category: string;
  element_name: string;
  raw_value: string | null;
  normalized_value: string | null;
  unit: string | null;
  importance: "high" | "medium" | "low";
  confidence: number | null;
  need_manual_check: boolean;
  source_image_path: string | null;
  region_desc: string | null;
  extra_json: Record<string, unknown> | null;
  created_at: string;
}

export type TaskStatus =
  | "queued"
  | "uploaded"
  | "paused"
  | "rendering_pages"
  | "rendered"
  | "detecting_regions"
  | "regions_detected"
  | "cropping_regions"
  | "regions_cropped"
  | "extracting_full_page_elements"
  | "full_page_elements_skipped"
  | "extracting_region_elements"
  | "region_elements_skipped"
  | "merging_elements"
  | "saving_elements"
  | "comparing_elements"
  | "saving_diffs"
  | "completed"
  | "failed"
  | "deleted";

export interface CompareTask {
  id: number;
  task_no: string;
  base_file_id: number;
  compare_file_id: number;
  status: TaskStatus;
  progress: number;
  summary: string | null;
  created_at: string;
  started_at?: string | null;
  updated_at?: string | null;
  completed_at: string | null;
  failed_stage?: string | null;
  last_error?: string | null;
  ai_call_count?: number;
  ai_total_duration_ms?: number;
  last_ai_error?: string | null;
  base_file_name?: string | null;
  compare_file_name?: string | null;
  base_page_count?: number | null;
  compare_page_count?: number | null;
  current_step_label?: string | null;
  current_step_hint?: string | null;
  error_hint?: string | null;
  recognition_strategy?: RecognitionStrategy | null;
}

export interface TaskListItem extends CompareTask {
  diff_count: number;
  high_risk_count: number;
  pending_review_count: number;
}

export interface TaskListResponse {
  items: TaskListItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface TaskLog {
  id: number;
  task_id: number;
  task_no: string | null;
  run_id: string;
  stage: string;
  component: string;
  event_type: string;
  level: "info" | "warning" | "error";
  status: string;
  error_category: "none" | "model_api" | "network" | "code" | "database" | "retrieval";
  error_code: string | null;
  message: string;
  error_detail: string | null;
  attempt_no: number | null;
  max_attempts: number | null;
  timeout_ms: number | null;
  response_time_ms: number | null;
  is_degraded: boolean;
  fallback_action: string | null;
  metadata_json: Record<string, unknown> | null;
  is_timeline: boolean;
  created_at: string;
}

export interface TaskLogListResponse {
  items: TaskLog[];
  total: number;
  limit: number;
  offset: number;
}

export type LogViewMode = "timeline" | "exceptions" | "full";

export interface FullLogListResponse {
  items: Record<string, unknown>[];
  total: number;
  cursor: number;
  next_cursor: number | null;
  status_message: string | null;
}

export interface TaskLogSummary {
  total: number;
  errors: number;
  timeouts: number;
  retries: number;
  degraded: number;
  average_response_time_ms: number;
  p95_response_time_ms: number;
  category_counts: Record<string, number>;
}

export interface SourceFileInfo {
  role: "base" | "compare";
  original_name: string;
  file_type: "pdf" | "image";
  page_count: number;
  preview_url: string;
  download_url: string;
}

export interface SourceFilesResponse {
  task_id: number;
  files: SourceFileInfo[];
}

export interface ReportTableRow {
  section: string;
  section_index: number;
  category: string;
  risk_label: string;
  base_content: string;
  compare_content: string;
  conclusion: string;
  impact: string;
  suggestion: string;
  evidence: string;
  confidence: number | null;
  manual_check_label: string;
  diff_id: number;
  review_status: ReviewStatus;
  review_status_label: string;
  conclusion_highlights: Array<{ start: number; end: number }>;
}

export interface ReportTableResponse {
  task_id: number;
  task_no: string;
  columns: string[];
  rows: ReportTableRow[];
}

export interface ElementMatch {
  id: number;
  compare_task_id: number;
  base_element_id: number | null;
  compare_element_id: number | null;
  match_type: "exact" | "semantic" | "suspicious" | "base_missing" | "compare_missing";
  match_reason: string | null;
  confidence: number | null;
  created_at: string;
}

export type RiskLevel = "high" | "medium" | "low" | "manual_check";
export type ReviewStatus = "pending" | "confirmed" | "ignored" | "misjudged" | "modified";

export interface CompareDiff {
  id: number;
  compare_task_id: number;
  match_id: number | null;
  base_element_id: number | null;
  compare_element_id: number | null;
  risk_level: RiskLevel;
  diff_category: string;
  base_content: string | null;
  compare_content: string | null;
  diff_summary: string | null;
  impact: string | null;
  suggestion: string | null;
  confidence: number | null;
  need_manual_check: boolean;
  review_status: ReviewStatus;
  reviewer_comment: string | null;
  created_at: string;
}

export interface DiffSummary {
  total_count: number;
  risk_counts: Record<RiskLevel, number>;
  review_counts: Record<ReviewStatus, number>;
}

export interface RecognitionStrategy {
  full_page_enabled: boolean;
  region_enabled: boolean;
  pdf_dpi: number;
  image_max_edge: number;
  jpeg_quality: number;
}

export interface PublicSettings {
  app_env: string;
  task_max_workers: number;
  ai_base_url: string;
  ai_model: string;
  has_ai_api_key: boolean;
  ai_timeout_seconds: number;
  ai_max_retries: number;
  storage_root: string;
  recognition_strategy: RecognitionStrategy;
}

export interface ReviewLog {
  id: number;
  compare_diff_id: number;
  action: "confirm" | "ignore" | "modify" | "mark_misjudged";
  old_value: string | null;
  new_value: string | null;
  comment: string | null;
  reviewer: string | null;
  created_at: string;
}

export interface UpdateSettingsRequest {
  ai_base_url?: string;
  ai_model?: string;
  ai_api_key?: string;
  ai_timeout_seconds?: number;
  ai_max_retries?: number;
  pdf_render_dpi?: number;
  ai_enable_full_page_extraction?: boolean;
  ai_enable_region_extraction?: boolean;
  ai_image_max_edge?: number;
  ai_image_jpeg_quality?: number;
}

export interface AiProfile {
  id: number;
  name: string;
  base_url: string;
  model: string;
  timeout_seconds: number;
  max_retries: number;
  has_api_key: boolean;
  is_active: boolean;
  is_pending: boolean;
  is_enabled: boolean;
}

export interface AiProfileListResponse {
  items: AiProfile[];
  active_profile_id: number | null;
  pending_profile_id: number | null;
}

export interface SaveAiProfileRequest {
  name: string;
  base_url: string;
  api_key?: string;
  model: string;
  timeout_seconds: number;
  max_retries: number;
}

export interface AiProfileActivationResponse {
  activation_status: "active" | "pending";
  profile: AiProfile;
}
