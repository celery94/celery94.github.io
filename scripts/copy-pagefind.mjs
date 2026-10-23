import { cpSync } from "node:fs";
import { resolve } from "node:path";

cpSync(resolve("dist/pagefind"), resolve("public/pagefind"), {
  recursive: true,
  force: true,
});
