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

for (const file of ["src/pages/DashboardPage.tsx", "src/pages/TaskPickerPage.tsx"]) {
  const source = read(file);

  assert(source.includes("const [page, setPage]"), `${file} must keep current page in state`);
  assert(source.includes("const [pageSize, setPageSize]"), `${file} must keep page size in state`);
  assert(source.includes("offset: (page - 1) * pageSize"), `${file} must request server offset from current page`);
  assert(source.includes("limit: pageSize"), `${file} must request only the current server page`);
  assert(source.includes("setTotal(result.total)"), `${file} must use backend total for pagination`);
  assert(source.includes("current: page"), `${file} table pagination must be controlled by server page`);
  assert(source.includes("total"), `${file} table pagination must display backend total`);
  assert(source.includes("setPage(1)"), `${file} filters/search must reset to the first page`);
}

console.log("server pagination checks passed");
