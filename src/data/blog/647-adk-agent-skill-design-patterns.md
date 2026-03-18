---
pubDatetime: 2026-03-18T12:30:16+08:00
title: "5 个 Agent Skill 设计模式，ADK 开发者看这一篇"
description: "SKILL.md 的格式问题已经基本解决了，真正的挑战在于 skill 内部逻辑怎么设计。本文整理了 5 种来自实际生态的 agent skill 设计模式：Tool Wrapper、Generator、Reviewer、Inversion、Pipeline，每种附带可运行的 ADK 代码示例。"
tags: ["AI", "ADK", "Agent", "Google Cloud", "SKILL.md"]
slug: "adk-agent-skill-design-patterns"
ogImage: "../../assets/647/01-cover.png"
source: "https://x.com/GoogleCloudTech/status/2033953579824758855"
---

![5 个 Agent Skill 设计模式封面图](../../assets/647/01-cover.png)

现在有超过 30 个 agent 工具——Claude Code、Gemini CLI、Cursor——都在收敛到同一套 SKILL.md 格式。格式本身已经不是障碍，工具链会帮你验证 YAML 是否合法、目录结构是否对齐。

真正让 skill 效果参差不齐的是内容。一个封装 FastAPI 规范的 skill，和一个四步走的文档生成 pipeline，外表长得一模一样，但内部逻辑完全不同。Google Cloud 的 @Saboo_Shubham_ 和 @lavinigam 从 Anthropic、Vercel、Google 内部的实践里提炼出了 5 种可复用的设计模式。

## Tool Wrapper

最简单的一种，目的是让 agent 在用到某个库的时候自动变成那个库的专家。

做法是把 API 规范、内部编码约定这类文档放进 `references/` 目录，skill 文件只负责声明触发条件和加载逻辑。agent 只在真正需要处理这个技术栈的时候才加载这些文档，不会污染其他场景的上下文。

一个 FastAPI expert skill 的实际写法：

```yaml
# skills/api-expert/SKILL.md
---
name: api-expert
description: FastAPI development best practices and conventions. Use when building, reviewing, or debugging FastAPI applications, REST APIs, or Pydantic models.
metadata:
  pattern: tool-wrapper
  domain: fastapi
---

You are an expert in FastAPI development. Apply these conventions to the user's code or question.

## Core Conventions

Load 'references/conventions.md' for the complete list of FastAPI best practices.

## When Reviewing Code
1. Load the conventions reference
2. Check the user's code against each convention
3. For each violation, cite the specific rule and suggest the fix

## When Writing Code
1. Load the conventions reference
2. Follow every convention exactly
3. Add type annotations to all function signatures
4. Use Annotated style for dependency injection
```

这个模式的价值是分发层面的：团队的内部编码规范、框架最佳实践，可以直接通过 skill 注入到每个开发者的工作流里，不需要每个人手动维护自己的 system prompt。

## Generator

解决的问题是：每次让 agent 生成同类文档，结构都不一样。

Generator 把模板和风格指南分离到 `assets/` 和 `references/` 目录，skill 文件的角色是"项目经理"——告诉 agent 先加载模板、读风格指南、向用户确认缺失的变量，再按格式填写。

一个技术报告生成器的例子：

```yaml
# skills/report-generator/SKILL.md
---
name: report-generator
description: Generates structured technical reports in Markdown. Use when the user asks to write, create, or draft a report, summary, or analysis document.
metadata:
  pattern: generator
  output-format: markdown
---

You are a technical report generator. Follow these steps exactly:

Step 1: Load 'references/style-guide.md' for tone and formatting rules.

Step 2: Load 'assets/report-template.md' for the required output structure.

Step 3: Ask the user for any missing information needed to fill the template:
- Topic or subject
- Key findings or data points
- Target audience (technical, executive, general)

Step 4: Fill the template following the style guide rules. Every section in the template must be present in the output.

Step 5: Return the completed report as a single Markdown document.
```

skill 文件本身不包含模板内容，也不包含语法规则，它只负责协调加载顺序和强制执行步骤。

## Reviewer

把"检查什么"和"怎么检查"拆开管理。

评审标准（checklist）放进 `references/review-checklist.md`，skill 文件只定义流程和输出格式。同一套 skill 基础设施，换一个不同的 checklist 就能做完全不同的审查：Python 风格审查、OWASP 安全审计、PR 审查都是这套结构。

```yaml
# skills/code-reviewer/SKILL.md
---
name: code-reviewer
description: Reviews Python code for quality, style, and common bugs. Use when the user submits code for review, asks for feedback on their code, or wants a code audit.
metadata:
  pattern: reviewer
  severity-levels: error,warning,info
---

You are a Python code reviewer. Follow this review protocol exactly:

Step 1: Load 'references/review-checklist.md' for the complete review criteria.

Step 2: Read the user's code carefully. Understand its purpose before critiquing.

Step 3: Apply each rule from the checklist to the code. For every violation found:
- Note the line number (or approximate location)
- Classify severity: error (must fix), warning (should fix), info (consider)
- Explain WHY it's a problem, not just WHAT is wrong
- Suggest a specific fix with corrected code

Step 4: Produce a structured review with these sections:
- **Summary**: What the code does, overall quality assessment
- **Findings**: Grouped by severity (errors first, then warnings, then info)
- **Score**: Rate 1-10 with brief justification
- **Top 3 Recommendations**: The most impactful improvements
```

这种分离的好处是维护性：checklist 可以独立更新，不需要改动 skill 逻辑。

## Inversion

这是行为上变化最大的一种——翻转 agent 和用户的主动权。

默认情况下 agent 倾向于立即行动、开始生成。Inversion 模式的核心指令是显式的阻断门（比如 "DO NOT start building until all phases are complete"），强制 agent 先走完结构化提问，收集足够的上下文之后再合成输出。

```yaml
# skills/project-planner/SKILL.md
---
name: project-planner
description: Plans a new software project by gathering requirements through structured questions before producing a plan. Use when the user says "I want to build", "help me plan", "design a system", or "start a new project".
metadata:
  pattern: inversion
  interaction: multi-turn
---

You are conducting a structured requirements interview. DO NOT start building or designing until all phases are complete.

## Phase 1 — Problem Discovery (ask one question at a time, wait for each answer)

Ask these questions in order. Do not skip any.

- Q1: "What problem does this project solve for its users?"
- Q2: "Who are the primary users? What is their technical level?"
- Q3: "What is the expected scale? (users per day, data volume, request rate)"

## Phase 2 — Technical Constraints (only after Phase 1 is fully answered)

- Q4: "What deployment environment will you use?"
- Q5: "Do you have any technology stack requirements or preferences?"
- Q6: "What are the non-negotiable requirements? (latency, uptime, compliance, budget)"

## Phase 3 — Synthesis (only after all questions are answered)

1. Load 'assets/plan-template.md' for the output format
2. Fill in every section of the template using the gathered requirements
3. Present the completed plan to the user
4. Ask: "Does this plan accurately capture your requirements? What would you change?"
5. Iterate on feedback until the user confirms
```

这个模式适合需求模糊的场景——用户只有方向，没有细节，让 agent 先猜再生成几乎必然要返工。

## Pipeline

适合不能出错的复杂任务：步骤多、顺序严格、中间需要人工确认。

关键设计是"钻石门"（diamond gate condition）：明确禁止 agent 在用户确认之前跳到下一步。这不只是软约束，而是写进 skill 指令里的阻断逻辑。Pipeline skill 会按需加载不同的 reference 文件和模板，每个步骤只拉取自己需要的上下文，保持 context window 干净。

```yaml
# skills/doc-pipeline/SKILL.md
---
name: doc-pipeline
description: Generates API documentation from Python source code through a multi-step pipeline. Use when the user asks to document a module, generate API docs, or create documentation from code.
metadata:
  pattern: pipeline
  steps: "4"
---

You are running a documentation generation pipeline. Execute each step in order. Do NOT skip steps or proceed if a step fails.

## Step 1 — Parse & Inventory
Analyze the user's Python code to extract all public classes, functions, and constants. Present the inventory as a checklist. Ask: "Is this the complete public API you want documented?"

## Step 2 — Generate Docstrings
For each function lacking a docstring:
- Load 'references/docstring-style.md' for the required format
- Generate a docstring following the style guide exactly
- Present each generated docstring for user approval
Do NOT proceed to Step 3 until the user confirms.

## Step 3 — Assemble Documentation
Load 'assets/api-doc-template.md' for the output structure. Compile all classes, functions, and docstrings into a single API reference document.

## Step 4 — Quality Check
Review against 'references/quality-checklist.md':
- Every public symbol documented
- Every parameter has a type and description
- At least one usage example per function
Report results. Fix issues before presenting the final document.
```

## 选哪个模式

这 5 种模式各自回答不同的问题：

- 你需要让 agent 掌握某个库的规范 → **Tool Wrapper**
- 你需要稳定的结构化输出 → **Generator**
- 你需要对提交物做系统性评审 → **Reviewer**
- 你的需求还不清晰，需要先澄清 → **Inversion**
- 你有多步骤流程，顺序不能乱 → **Pipeline**

这些模式也可以组合。Pipeline 在最后一步加一个 Reviewer 做自检，Generator 在开头接一个 Inversion 先收集变量——只要逻辑说得通，都是合法的用法。ADK 的 `SkillToolset` 支持按需加载，agent 只会在真正用到某个 skill 的时候才消耗对应的 context token。

> Agent Skill 规范是开源的，原生支持于 ADK。格式标准化之后，值得花时间在内容设计上。

## 参考

- [5 Agent Skill design patterns every ADK developer should know](https://x.com/GoogleCloudTech/status/2033953579824758855) — Google Cloud Tech (@Saboo_Shubham_, @lavinigam)
- [Google Agent Development Kit (ADK) 文档](https://google.github.io/adk-docs/)
