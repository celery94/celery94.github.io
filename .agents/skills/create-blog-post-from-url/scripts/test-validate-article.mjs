import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import { validateArticle } from "./validate-article.mjs";

function createFixture(overrides = {}) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "blog-validator-"));
  const articleDir = path.join(root, "src", "data", "blog");
  const assetDir = path.join(root, "src", "assets", "001");
  fs.mkdirSync(articleDir, { recursive: true });
  fs.mkdirSync(assetDir, { recursive: true });
  fs.writeFileSync(path.join(assetDir, "01-cover.png"), "");

  const title = overrides.title ?? "测试工具：完成可靠发布";
  const description =
    overrides.description ??
    "这是一段用于验证博客发布流程的中文摘要，说明文章解决的问题、适合的读者、可以获得的结果，以及执行过程中需要关注的限制和检查方法，确保长度符合博客列表和微信预览要求。";
  const source = "https://example.com/source";
  const articlePath = path.join(articleDir, "001-test-article.md");

  fs.writeFileSync(
    path.join(assetDir, "cover-brief.json"),
    JSON.stringify({
      article_title: title,
      cover_type: "tutorial",
      core_theme: "可靠发布",
      reader_takeaway: "完成发布",
      summary_angle: "从输入到验证",
      narrative_flow: "3-beat process",
      information_blocks: [
        { role: "step", source_anchor: "原文步骤一", visual_idea: "输入" },
        { role: "step", source_anchor: "原文步骤二", visual_idea: "验证" },
      ],
      selected_style: "极简线稿风",
      selected_style_prompt_descriptor: "minimalist line-art illustration",
      final_prompt: "wide cover illustration",
    }),
  );

  fs.writeFileSync(
    articlePath,
    `---
pubDatetime: 2026-01-01T12:00:00+08:00
title: "${title}"
description: "${description}"
tags: ["Test"]
slug: "test-article"
ogImage: "../../assets/001/01-cover.png"
source: "${source}"
---

正文。

## 参考

- [原文](${source})
`,
  );

  return { root, articlePath };
}

test("有效的微信文章通过校验", t => {
  const fixture = createFixture();
  t.after(() => fs.rmSync(fixture.root, { recursive: true, force: true }));

  assert.deepEqual(validateArticle(fixture.articlePath, { wechat: true }), []);
});

test("拦截微信超长标题", t => {
  const fixture = createFixture({ title: "题".repeat(33) });
  t.after(() => fs.rmSync(fixture.root, { recursive: true, force: true }));

  assert.ok(
    validateArticle(fixture.articlePath, { wechat: true }).some(error =>
      error.includes("微信标题最多 32"),
    ),
  );
});

test("拦截缺失的本地资源", t => {
  const fixture = createFixture();
  t.after(() => fs.rmSync(fixture.root, { recursive: true, force: true }));
  fs.rmSync(path.join(fixture.root, "src", "assets", "001", "01-cover.png"));

  assert.ok(
    validateArticle(fixture.articlePath, { wechat: true }).some(error =>
      error.includes("资源不存在"),
    ),
  );
});
