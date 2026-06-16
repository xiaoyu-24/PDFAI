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
assert(
  apiSource.includes("重试接口未加载") && apiSource.includes("Not Found"),
  "retryTask must convert stale-backend 404 Not Found into a clear Chinese message"
);

const appCss = read("src/App.css");
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

console.log("navigation regression checks passed");
