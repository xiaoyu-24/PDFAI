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

const dashboardSource = read("src/pages/DashboardPage.tsx");
const typesSource = read("src/types/index.ts");

assert(
  typesSource.includes("task_max_workers: number"),
  "PublicSettings must expose task_max_workers"
);
assert(
  dashboardSource.includes("getSettings") &&
    dashboardSource.includes("taskMaxWorkers") &&
    dashboardSource.includes("settings.task_max_workers"),
  "DashboardPage must render the worker limit from public settings"
);
assert(
  !dashboardSource.includes("3 涓") && !dashboardSource.includes("运行 3"),
  "DashboardPage must not hard-code a 3-task worker limit"
);

console.log("dashboard worker limit checks passed");
