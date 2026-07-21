import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const taskPagePath = path.resolve(scriptDir, "../src/pages/TaskProgressPage.tsx");
const systemPagePath = path.resolve(scriptDir, "../src/pages/SystemLogsPage.tsx");
const taskSource = fs.readFileSync(taskPagePath, "utf8");
const systemSource = fs.readFileSync(systemPagePath, "utf8");

assert.match(taskSource, /const \[fullLogItems, setFullLogItems\]/);
assert.match(taskSource, /setFullLogItems\(\(response as FullLogListResponse\)\.items\)/);
assert.match(taskSource, /dataSource=\{fullLogItems\}/);
assert.match(taskSource, /logViewMode === "full"/);
assert.match(systemSource, /const \[fullLogItems, setFullLogItems\]/);
assert.match(systemSource, /setFullLogItems\(list\.items\)/);
assert.match(systemSource, /dataSource=\{fullLogItems\}/);
assert.match(systemSource, /viewMode === "full"/);

console.log("full log rendering checks passed");
