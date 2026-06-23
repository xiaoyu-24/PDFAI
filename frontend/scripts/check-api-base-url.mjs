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

const clientSource = read("src/api/client.ts");
const tasksSource = read("src/api/tasks.ts");

assert(
  clientSource.includes("VITE_API_BASE_URL"),
  "api client must support VITE_API_BASE_URL for separate frontend/backend domains"
);
assert(
  clientSource.includes("getApiBaseUrl") && clientSource.includes("buildApiUrl"),
  "api client must expose helpers for API-relative and absolute URL construction"
);
assert(
  tasksSource.includes("buildApiUrl") &&
    !tasksSource.includes("return `/api/tasks/${taskId}/exports/${type}`;"),
  "export URLs must follow the configured API base URL"
);

console.log("api base URL checks passed");
