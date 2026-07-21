const LOG_LEVEL_LABELS: Record<string, string> = {
  info: "信息",
  warning: "警告",
  error: "错误",
};

const ERROR_CATEGORY_LABELS: Record<string, string> = {
  none: "无",
  model_api: "模型 API",
  network: "网络",
  code: "代码",
  database: "数据库",
  retrieval: "检索",
};

const EVENT_TYPE_LABELS: Record<string, string> = {
  queued: "进入队列",
  started: "开始",
  succeeded: "成功",
  failed: "失败",
  timeout: "超时",
  retry: "重试",
  degraded: "降级",
  paused: "暂停",
  resumed: "继续",
  completed: "完成",
};

const TASK_STAGE_LABELS: Record<string, string> = {
  queued: "任务排队",
  uploaded: "文件已上传",
  rendering_pages: "PDF 页面转换",
  rendered: "页面转换完成",
  detecting_regions: "图纸区域识别",
  regions_detected: "区域识别完成",
  cropping_regions: "关键区域裁剪",
  regions_cropped: "区域裁剪完成",
  extracting_full_page_elements: "整页元素识别",
  full_page_elements_skipped: "跳过整页识别",
  extracting_region_elements: "区域元素识别",
  region_elements_skipped: "跳过区域识别",
  merging_elements: "识别结果合并",
  saving_elements: "保存图纸元素",
  comparing_elements: "生成图纸差异",
  saving_diffs: "保存差异结果",
  source_file_preview: "原始文件预览",
  paused: "任务暂停",
  completed: "任务完成",
  failed: "任务失败",
};

export const LOG_LEVEL_OPTIONS = Object.entries(LOG_LEVEL_LABELS).map(([value, label]) => ({ value, label }));
export const ERROR_CATEGORY_OPTIONS = Object.entries(ERROR_CATEGORY_LABELS)
  .filter(([value]) => value !== "none")
  .map(([value, label]) => ({ value, label }));
export const EVENT_TYPE_OPTIONS = Object.entries(EVENT_TYPE_LABELS).map(([value, label]) => ({ value, label }));
export const TASK_STAGE_OPTIONS = Object.entries(TASK_STAGE_LABELS).map(([value, label]) => ({ value, label }));

export function logLevelLabel(value: string): string {
  return LOG_LEVEL_LABELS[value] || "未知等级";
}

export function errorCategoryLabel(value: string): string {
  return ERROR_CATEGORY_LABELS[value] || "未知分类";
}

export function eventTypeLabel(value: string): string {
  return EVENT_TYPE_LABELS[value] || "未知事件";
}

export function taskStageLabel(value: string): string {
  return TASK_STAGE_LABELS[value] || "未知阶段";
}
