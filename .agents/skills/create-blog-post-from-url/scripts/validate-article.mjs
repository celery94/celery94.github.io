#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const REQUIRED_FIELDS = [
  "pubDatetime",
  "title",
  "description",
  "tags",
  "slug",
  "source",
];

function parseScalar(raw) {
  const value = raw.trim();
  if (value.startsWith('"') && value.endsWith('"')) {
    try {
      return JSON.parse(value);
    } catch {
      return value.slice(1, -1);
    }
  }
  if (value.startsWith("'") && value.endsWith("'")) {
    return value.slice(1, -1).replaceAll("''", "'");
  }
  return value;
}

function parseFrontmatter(text) {
  const normalized = text.replace(/^\uFEFF/, "").replaceAll("\r\n", "\n");
  if (!normalized.startsWith("---\n")) {
    return { error: "文件必须以 YAML frontmatter 开头" };
  }

  const end = normalized.indexOf("\n---\n", 4);
  if (end === -1) {
    return { error: "找不到 frontmatter 结束标记" };
  }

  const values = {};
  for (const line of normalized.slice(4, end).split("\n")) {
    const match = line.match(/^([A-Za-z][\w]*):\s*(.*)$/);
    if (match) {
      values[match[1]] = parseScalar(match[2]);
    }
  }

  return { values, body: normalized.slice(end + 5) };
}

function charLength(value) {
  return [...value].length;
}

function resolveLocalReference(articlePath, reference) {
  const clean = decodeURIComponent(reference.split(/[?#]/, 1)[0]);
  return path.resolve(path.dirname(articlePath), clean);
}

function validateCoverBrief(briefPath, title, errors) {
  let brief;
  try {
    brief = JSON.parse(fs.readFileSync(briefPath, "utf8"));
  } catch (error) {
    errors.push(`封面 brief 无法读取: ${error.message}`);
    return;
  }

  const required = [
    "article_title",
    "cover_type",
    "core_theme",
    "reader_takeaway",
    "summary_angle",
    "narrative_flow",
    "information_blocks",
    "selected_style",
    "selected_style_prompt_descriptor",
    "final_prompt",
  ];
  for (const field of required) {
    if (
      brief[field] === undefined ||
      brief[field] === null ||
      brief[field] === ""
    ) {
      errors.push(`cover-brief.json 缺少 ${field}`);
    }
  }

  if (brief.article_title && brief.article_title !== title) {
    errors.push("cover-brief.json 的 article_title 与文章标题不一致");
  }
  if (
    !Array.isArray(brief.information_blocks) ||
    brief.information_blocks.length < 2 ||
    brief.information_blocks.length > 4
  ) {
    errors.push("cover-brief.json 的 information_blocks 必须为 2–4 项");
  } else if (
    brief.information_blocks.some(
      block => !block || typeof block.source_anchor !== "string" || !block.source_anchor.trim()
    )
  ) {
    errors.push("每个 information_blocks 项都必须包含 source_anchor");
  }
}

export function validateArticle(articlePath, options = {}) {
  const errors = [];
  const resolvedArticle = path.resolve(articlePath);
  let text;

  try {
    text = fs.readFileSync(resolvedArticle, "utf8");
  } catch (error) {
    return [`文章无法读取: ${error.message}`];
  }

  const parsed = parseFrontmatter(text);
  if (parsed.error) {
    return [parsed.error];
  }

  const { values, body } = parsed;
  for (const field of REQUIRED_FIELDS) {
    if (values[field] === undefined || values[field] === "") {
      errors.push(`frontmatter 缺少 ${field}`);
    }
  }

  const title = String(values.title ?? "");
  const description = String(values.description ?? "");
  const slug = String(values.slug ?? "");
  const source = String(values.source ?? "");

  if (/[\u2018\u2019\u201c\u201d]/u.test(title + description)) {
    errors.push("title 和 description 不能包含中文弯引号");
  }
  if (description && (charLength(description) < 80 || charLength(description) > 120)) {
    errors.push(
      `description 必须为 80–120 个字符，当前 ${charLength(description)} 个`,
    );
  }
  if (options.wechat && title && charLength(title) > 32) {
    errors.push(`微信标题最多 32 个字符，当前 ${charLength(title)} 个`);
  }

  if (slug && !/^[a-z0-9]+(?:-[a-z0-9]+)*$/u.test(slug)) {
    errors.push("slug 必须使用小写 kebab-case");
  }
  const filenameMatch = path.basename(resolvedArticle).match(/^\d{3,}-(.+)\.md$/u);
  if (!filenameMatch) {
    errors.push("文章文件名必须使用 {ID}-{slug}.md");
  } else if (slug && filenameMatch[1] !== slug) {
    errors.push("文件名中的 slug 与 frontmatter slug 不一致");
  }

  if (values.pubDatetime) {
    const timestamp = String(values.pubDatetime);
    if (
      !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/u.test(
        timestamp,
      )
    ) {
      errors.push("pubDatetime 必须是带时区的 ISO 8601 时间");
    } else if (!options.allowFuture && Date.parse(timestamp) > Date.now() + 60_000) {
      errors.push("pubDatetime 不能晚于当前时间，除非使用 --allow-future");
    }
  }

  if (values.tags) {
    try {
      const tags = JSON.parse(String(values.tags));
      if (!Array.isArray(tags) || tags.length === 0 || tags.some(tag => !tag)) {
        errors.push("tags 必须是非空字符串数组");
      }
    } catch {
      errors.push("tags 必须使用 JSON 风格的行内数组");
    }
  }

  try {
    const sourceUrl = new URL(source);
    if (!["http:", "https:"].includes(sourceUrl.protocol)) {
      errors.push("source 必须是 HTTP 或 HTTPS URL");
    }
  } catch {
    if (source) {
      errors.push("source 不是有效 URL");
    }
  }

  if (!/^##\s+参考\s*$/mu.test(body)) {
    errors.push("正文必须包含 ## 参考 小节");
  }
  if (source && !body.includes(source)) {
    errors.push("## 参考 小节必须包含原文 URL");
  }

  const localReferences = new Set();
  const imagePattern = /!\[[^\]]*\]\(\s*(?:<([^>]+)>|([^\s)]+))/gu;
  for (const match of body.matchAll(imagePattern)) {
    const reference = match[1] ?? match[2];
    if (!/^(?:https?:|data:|#)/iu.test(reference)) {
      localReferences.add(reference);
    }
  }

  const ogImage = values.ogImage ? String(values.ogImage) : "";
  if (ogImage) {
    localReferences.add(ogImage);
  } else if (options.wechat) {
    errors.push("微信发布必须提供 ogImage 封面");
  }

  for (const reference of localReferences) {
    let localPath;
    try {
      localPath = resolveLocalReference(resolvedArticle, reference);
    } catch {
      errors.push(`资源路径无法解析: ${reference}`);
      continue;
    }
    if (!fs.existsSync(localPath)) {
      errors.push(`资源不存在: ${reference}`);
    }
  }

  if (options.wechat && ogImage) {
    const coverPath = resolveLocalReference(resolvedArticle, ogImage);
    validateCoverBrief(path.join(path.dirname(coverPath), "cover-brief.json"), title, errors);
  }

  return errors;
}

function parseArguments(argv) {
  const options = {
    wechat: argv.includes("--wechat"),
    allowFuture: argv.includes("--allow-future"),
  };
  const articlePath = argv.find(argument => !argument.startsWith("--"));
  return { articlePath, options };
}

const isMain =
  process.argv[1] &&
  path.resolve(process.argv[1]) === fileURLToPath(import.meta.url);

if (isMain) {
  const { articlePath, options } = parseArguments(process.argv.slice(2));
  if (!articlePath) {
    console.error(
      "用法: node validate-article.mjs <article.md> [--wechat] [--allow-future]",
    );
    process.exit(2);
  }

  const errors = validateArticle(articlePath, options);
  if (errors.length) {
    for (const error of errors) {
      console.error(`- ${error}`);
    }
    process.exit(1);
  }

  console.log(`文章校验通过: ${path.resolve(articlePath)}`);
}
