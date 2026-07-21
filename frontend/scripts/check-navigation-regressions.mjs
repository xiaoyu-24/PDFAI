import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { join } from "node:path";

const root = fileURLToPath(new URL("..", import.meta.url));

function read(path) {
  return readFileSync(join(root, path), "utf8");
}

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

const backButtonSource = read("src/components/PageBackButton.tsx");
assert(
  !backButtonSource.includes("useLocation") && !backButtonSource.includes("navigate(-1)"),
  "PageBackButton must use explicit hierarchy targets instead of browser history"
);

const topLevelPages = [
  "src/pages/SettingsPage.tsx",
  "src/pages/TaskPickerPage.tsx",
  "src/pages/UploadPage.tsx",
];

for (const file of topLevelPages) {
  const source = read(file);
  assert(
    !source.includes("PageBackButton"),
    `${file} is a top-level page and must not render a back button`
  );
}

const secondLevelBackTargets = {
  "src/pages/TaskProgressPage.tsx": 'fallbackTo="/tasks"',
  "src/pages/DiffReportPage.tsx": 'fallbackTo="/diffs"',
  "src/pages/ElementsPage.tsx": 'fallbackTo="/elements"',
};

for (const [file, expectedTarget] of Object.entries(secondLevelBackTargets)) {
  const source = read(file);
  assert(
    source.includes("PageBackButton"),
    `${file} is a second-level page and must render a back button`
  );
  assert(
    source.includes(expectedTarget),
    `${file} must return to its parent top-level page with ${expectedTarget}`
  );
  assert(
    !source.includes("返回工作台") && !source.includes("返回任务详情") && !source.includes("返回控制台"),
    `${file} must not use fixed destination wording`
  );
}

const apiSource = read("src/api/tasks.ts");
const uploadPageSource = read("src/pages/UploadPage.tsx");
assert(
  uploadPageSource.includes("Segmented") &&
    uploadPageSource.includes("baseFileFormat") &&
    uploadPageSource.includes("compareFileFormat"),
  "UploadPage must provide independent PDF/image format switches for base and compare drawings"
);
assert(
  uploadPageSource.includes("image/png,image/jpeg,image/jpg,image/webp") &&
    uploadPageSource.includes("请上传 PNG、JPG/JPEG 或 WebP 图片"),
  "UploadPage image mode must accept PNG, JPG/JPEG and WebP only"
);
assert(
  apiSource.includes("重试接口未加载") && apiSource.includes("Not Found"),
  "retryTask must convert stale-backend 404 Not Found into a clear Chinese message"
);
assert(
  apiSource.includes("uploadTaskFiles") &&
    apiSource.includes("base_file_format") &&
    apiSource.includes("compare_file_format"),
  "task upload API must submit the selected file formats to the backend"
);

const diffReportSource = read("src/pages/DiffReportPage.tsx");
assert(
  !diffReportSource.includes("查看差异报告") && !diffReportSource.includes("view.officeapps.live.com/op/view.aspx"),
  "DiffReportPage must hide the Office Online Viewer button while the service runs on localhost"
);
assert(
  diffReportSource.includes("全屏查看"),
  "DiffReportPage must provide a full-screen report viewing button"
);
assert(
  diffReportSource.indexOf("全屏查看") < diffReportSource.indexOf("导出差异报告"),
  "DiffReportPage full-screen report button must be placed before the export report button"
);
assert(
  diffReportSource.includes("fullscreen-report") && diffReportSource.includes("返回"),
  "DiffReportPage full-screen report view must include a top-left return button"
);
assert(
  diffReportSource.includes("renderReportToolbar(true)") && diffReportSource.includes("!fullscreen"),
  "DiffReportPage full-screen report toolbar must hide the full-screen button"
);
assert(
  diffReportSource.includes("closeFullscreenReport") && diffReportSource.includes("setSelectedRow(null)"),
  "DiffReportPage must close any open report detail drawer when returning from full-screen view"
);
assert(
  diffReportSource.includes("report-table-wrap") && diffReportSource.includes("onRow={(record)"),
  "DiffReportPage full-screen report table must keep row click behavior for the detail drawer"
);
assert(
  diffReportSource.includes("zIndex={isFullscreen ? 2100 : undefined}"),
  "DiffReportPage detail drawer must render above the full-screen report overlay"
);
assert(
  diffReportSource.includes("审核状态"),
  "DiffReportPage online report table must show review status"
);
assert(
  diffReportSource.includes("renderHighlightedConclusion") &&
    diffReportSource.includes("conclusion_highlights") &&
    diffReportSource.includes("report-highlight"),
  "DiffReportPage must render highlighted parameter fragments in conclusions"
);
assert(
  diffReportSource.includes("reviewStatus") && diffReportSource.includes("review_status_label"),
  "DiffReportPage online report table must support review status filtering"
);
assert(
  (diffReportSource.match(/sorter:/g) || []).length >= 5,
  "DiffReportPage online report table must support sorting on key report columns"
);
assert(
  !diffReportSource.includes("RISK_COLORS"),
  "DiffReportPage must not specially color-code the risk/priority column"
);
const diffReportColumnsSource = diffReportSource.slice(
  diffReportSource.indexOf("const columns"),
  diffReportSource.indexOf("const closeFullscreenReport")
);
assert(
  diffReportColumnsSource.indexOf('dataIndex: "manual_check_label"') <
    diffReportColumnsSource.indexOf('dataIndex: "evidence"'),
  "DiffReportPage must place evidence/check area to the right of manual confirmation"
);

const taskProgressSource = read("src/pages/TaskProgressPage.tsx");
assert(
  taskProgressSource.includes("getTaskReportTable") &&
    taskProgressSource.includes("reportRows") &&
    taskProgressSource.includes("task-action-buttons"),
  "TaskProgressPage must load report-table conclusions and render header actions"
);
assert(
  !taskProgressSource.includes('title="结论/差异/原因"') &&
    taskProgressSource.includes("extra={") &&
    !taskProgressSource.includes('title="下一步"'),
  "TaskProgressPage must keep header actions without the conclusion title text"
);
assert(
  taskProgressSource.includes("lg={8}") && taskProgressSource.includes("lg={16}"),
  "TaskProgressPage must narrow current status and widen the conclusion/actions area"
);
assert(
  !taskProgressSource.includes('<Button block type="primary" icon={<FileSearchOutlined />}>查看差异报告</Button>'),
  "TaskProgressPage action buttons must not keep the old full-width button layout"
);
assert(
  taskProgressSource.includes("查看原始文件") &&
    taskProgressSource.includes("getTaskLogs") &&
    taskProgressSource.includes('title="执行日志"'),
  "TaskProgressPage must link to source files and render task execution logs"
);

const routesSource = read("src/routes/index.tsx");
assert(
  routesSource.includes('path="/system-logs"') &&
    routesSource.includes('path="/tasks/:taskId/source-files"') &&
    routesSource.includes("SystemLogsPage") &&
    routesSource.includes("SourceFilesPage"),
  "application routes must include system logs and source file preview pages"
);

const appShellSource = read("src/components/AppShell.tsx");
assert(
  appShellSource.includes("系统日志") && appShellSource.includes('to="/system-logs"'),
  "AppShell must expose the global system log monitor"
);

assert(
  apiSource.includes("getTaskLogs") &&
    apiSource.includes("getSystemLogs") &&
    apiSource.includes("getSystemLogSummary") &&
    apiSource.includes("getSourceFiles") &&
    apiSource.includes("getSourceFilePreviewUrl"),
  "frontend task API must expose log monitoring and source file endpoints"
);

const systemLogsSource = read("src/pages/SystemLogsPage.tsx");
assert(
  systemLogsSource.includes("getSystemLogSummary") &&
    systemLogsSource.includes("error_category") &&
    systemLogsSource.includes("event_type") &&
    systemLogsSource.includes("min_response_time_ms") &&
    systemLogsSource.includes("degraded") &&
    systemLogsSource.includes("Pagination") &&
    systemLogsSource.includes("useAutoRefresh"),
  "SystemLogsPage must show summary, filters, pagination and automatic refresh"
);
assert(
  systemLogsSource.includes("logLevelLabel") &&
    systemLogsSource.includes("errorCategoryLabel") &&
    systemLogsSource.includes("eventTypeLabel") &&
    systemLogsSource.includes("taskStageLabel") &&
    taskProgressSource.includes("logLevelLabel") &&
    taskProgressSource.includes("errorCategoryLabel") &&
    taskProgressSource.includes("eventTypeLabel") &&
    taskProgressSource.includes("taskStageLabel"),
  "all log filters and tables must render shared Chinese enum labels"
);

const sourceFilesSource = read("src/pages/SourceFilesPage.tsx");
assert(
  sourceFilesSource.includes("iframe") &&
    sourceFilesSource.includes("<img") &&
    sourceFilesSource.includes("onError") &&
    sourceFilesSource.includes("下载原文件"),
  "SourceFilesPage must preview PDF/images and keep a download fallback"
);

const dashboardSource = read("src/pages/DashboardPage.tsx");
const taskPickerAutoRefreshSource = read("src/pages/TaskPickerPage.tsx");
const diffReportAutoRefreshSource = read("src/pages/DiffReportPage.tsx");
const elementsAutoRefreshSource = read("src/pages/ElementsPage.tsx");
const autoRefreshPages = {
  "DashboardPage": dashboardSource,
  "TaskPickerPage": taskPickerAutoRefreshSource,
  "TaskProgressPage": taskProgressSource,
  "DiffReportPage": diffReportAutoRefreshSource,
  "ElementsPage": elementsAutoRefreshSource,
  "SystemLogsPage": systemLogsSource,
};
for (const [pageName, source] of Object.entries(autoRefreshPages)) {
  assert(
    source.includes("useAutoRefresh") && !source.includes("window.setInterval"),
    `${pageName} must use the shared automatic refresh hook`
  );
}

const autoRefreshHookSource = read("src/hooks/useAutoRefresh.ts");
assert(
  autoRefreshHookSource.includes("2000") &&
    autoRefreshHookSource.includes("visibilitychange") &&
    autoRefreshHookSource.includes('addEventListener("focus"') &&
    autoRefreshHookSource.includes("runningRef"),
  "useAutoRefresh must poll every two seconds, refresh on focus, and prevent overlapping requests"
);
const dashboardColumnsStart = dashboardSource.indexOf("const columns");
const dashboardColumnsSource = dashboardSource.slice(
  dashboardColumnsStart,
  dashboardSource.indexOf("  return (", dashboardColumnsStart)
);
assert(
  dashboardColumnsSource.indexOf('title: "任务"') <
    dashboardColumnsSource.indexOf('title: "基准图纸"') &&
    dashboardColumnsSource.indexOf('title: "基准图纸"') <
      dashboardColumnsSource.indexOf('title: "对比图纸"') &&
    dashboardColumnsSource.indexOf('title: "对比图纸"') <
      dashboardColumnsSource.indexOf('title: "状态"'),
  "DashboardPage must place base and compare drawing columns between task and status"
);
assert(
  dashboardColumnsSource.includes('dataIndex: "base_file_name"') &&
    dashboardColumnsSource.includes('dataIndex: "compare_file_name"') &&
    dashboardColumnsSource.includes('className="drawing-file-name"'),
  "DashboardPage must render base and compare drawing names in dedicated wrapping columns"
);
const dashboardTaskColumnSource = dashboardColumnsSource.slice(
  dashboardColumnsSource.indexOf('title: "任务"'),
  dashboardColumnsSource.indexOf('title: "基准图纸"')
);
assert(
  !dashboardTaskColumnSource.includes("base_file_name") &&
    !dashboardTaskColumnSource.includes("compare_file_name"),
  "DashboardPage task column must show only the task number"
);

const appCss = read("src/App.css");
const elementsPageSource = read("src/pages/ElementsPage.tsx");
assert(
  !elementsPageSource.includes("normalized_value") && !elementsPageSource.includes("标准化值"),
  "ElementsPage must show only raw element content and must not render normalized content"
);

assert(
  appCss.includes("height: 100vh") && appCss.includes("overflow: hidden"),
  "app shell must keep scrolling inside the content area"
);
assert(
  appCss.includes("position: sticky") && appCss.includes("height: calc(100vh - 64px)"),
  "sidebar must stay fixed while the content area scrolls"
);
assert(
  appCss.includes("overflow-y: auto"),
  "content area must own vertical scrolling"
);
assert(
  appCss.includes("report-table-wrap") &&
    appCss.includes("white-space: normal") &&
    appCss.includes("word-break: break-word"),
  "report table cells must wrap long text in normal and full-screen views"
);
assert(
  appCss.includes(".drawing-file-name") &&
    appCss.includes("white-space: normal") &&
    appCss.includes("overflow-wrap: anywhere"),
  "DashboardPage drawing names must wrap without truncation"
);

console.log("navigation regression checks passed");
