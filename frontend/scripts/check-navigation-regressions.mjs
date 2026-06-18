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

console.log("navigation regression checks passed");
