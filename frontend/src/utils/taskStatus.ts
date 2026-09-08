/** 任务仍在流水线中、进度会自行推进的状态。与后端 ACTIVE_TASK_STATUSES 保持一致。 */
export const ACTIVE_TASK_STATUSES = new Set<string>([
  "queued",
  "uploaded",
  "rendering_pages",
  "rendered",
  "detecting_regions",
  "regions_detected",
  "cropping_regions",
  "regions_cropped",
  "extracting_full_page_elements",
  "full_page_elements_skipped",
  "extracting_region_elements",
  "region_elements_skipped",
  "merging_elements",
  "saving_elements",
  "comparing_elements",
  "saving_diffs",
]);

export function isTaskActive(status: string): boolean {
  return ACTIVE_TASK_STATUSES.has(status);
}

const ACTIVE_REFRESH_MS = 2000;
const IDLE_REFRESH_MS = 15000;

/**
 * 列表页的轮询间隔：有任务在跑时保持 2 秒，全部结束后退到 15 秒。
 *
 * 列表接口要为每个任务汇总差异行，空转轮询的代价并不便宜；切回标签页或窗口获得
 * 焦点时 useAutoRefresh 会立即刷新一次，所以放慢间隔不会让用户看到过期数据。
 */
export function taskListRefreshInterval(statuses: string[]): number {
  return statuses.some(isTaskActive) ? ACTIVE_REFRESH_MS : IDLE_REFRESH_MS;
}
