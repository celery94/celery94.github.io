import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import { findBannedPhrases, validateArticle } from "./validate-article.mjs";

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
  const body = overrides.body ?? "正文。";
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

${body}

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

test("拦截黑名单句式", () => {
  const cases = [
    ["本文把这个问题拆开，分三步处理。", "宣布拆解问题"],
    ["下面按四个问题拆开日常表达式。", "宣布拆解问题"],
    ["这篇带你看懂中央包管理。", "带你看懂"],
    ["瓶颈不是生成代码，而是审查代码。", "不是……而是"],
    ["省下的不是算力，是每一轮判断的延迟。", "不是……而是"],
    ["一文看懂中央包管理。", "带你看懂"],
    ["你以为它在理解上出问题，其实它缺验收标准。", "你以为"],
    ["表面上是性能问题，实际上是锁竞争。", "你以为"],
    ["一个反直觉的观察：日历越满越容易漏事。", "反直觉"],
  ];
  for (const [body, label] of cases) {
    assert.ok(
      findBannedPhrases({ body }).some(hit => hit.includes(label)),
      `未拦截: ${body}`,
    );
  }
  assert.ok(
    findBannedPhrases({ description: "本文拆解四道关口。" })[0].startsWith(
      "description",
    ),
  );
});

test("黑名单不误伤技术表述、代码和参考", () => {
  const body = [
    "差集可能把一个区间拆成两个。",
    "用 `-f` 而不是 `-F`，是为了避免转义。",
    "判别字段存在但不是字符串，是协议错误。",
    "反汇编器也叫拆解工具。",
    "`不是 A，而是 B` 只出现在行内代码里。",
    "```",
    "// 你以为这里会抛异常",
    "```",
    "> 原文引用：你以为这是缓存问题。",
    "",
    "## 参考",
    "",
    "- [一个反直觉的观察](https://example.com)",
  ].join("\n");
  assert.deepEqual(findBannedPhrases({ body }), []);
});

test("文章校验报告黑名单命中", t => {
  const fixture = createFixture({ body: "这类补全不是模型问题，而是上下文问题。" });
  t.after(() => fs.rmSync(fixture.root, { recursive: true, force: true }));

  assert.ok(
    validateArticle(fixture.articlePath, { wechat: true }).some(error =>
      error.includes("命中禁用句式"),
    ),
  );
});
