import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { join } from "node:path";

const root = fileURLToPath(new URL("..", import.meta.url));
const read = (path) => readFileSync(join(root, path), "utf8");
const assert = (condition, message) => {
  if (!condition) throw new Error(message);
};

const api = read("src/api/tasks.ts");
const types = read("src/types/index.ts");
const page = read("src/pages/SettingsPage.tsx");
const gitignore = read("../.gitignore");

for (const method of [
  "listAiProfiles",
  "createAiProfile",
  "updateAiProfile",
  "activateAiProfile",
  "deleteAiProfile",
]) {
  assert(api.includes(method), `AI profile API must expose ${method}`);
}

assert(
  types.includes("interface AiProfile") &&
    types.includes("is_active") &&
    types.includes("is_pending") &&
    !types.includes("api_key_encrypted"),
  "AI profile types must expose state without encrypted secrets"
);

for (const text of ["新增 AI 配置", "当前使用", "等待生效", "切换使用", "编辑配置", "停用配置"]) {
  assert(page.includes(text), `SettingsPage must render ${text}`);
}

assert(
  page.includes("Modal") && page.includes("Popconfirm") && page.includes("useAutoRefresh"),
  "SettingsPage must support editing, safe deletion and automatic pending-state refresh"
);

assert(
  gitignore.includes("/storage/config/*.key"),
  "server-side AI encryption keys must never be tracked by Git"
);

console.log("AI profile regression checks passed");
