---
pubDatetime: 2025-09-24
title: GPT-5-Codex 提示工程实践指南：最小化提示、工具协作与 Anti-Prompting
description: 系统梳理 GPT-5-Codex 在交互式与代理型编码场景下的最小化提示原则、工具调用模式、apply_patch 用法与 Anti-Prompting 策略，结合示例与最佳实践，帮助工程团队构建高质量、可控与高效的自动化开发工作流。
tags: ["AI", "prompt-engineering", "LLM", "developer-tools", "productivity"]
slug: gpt5-codex-prompting-guide
source: https://cookbook.openai.com/examples/gpt-5-codex_prompting_guide
draft: false
featured: false
---

## 背景与问题

随着大模型从“被动补全”走向“主动代理（Agentic Coding）”，开发者在实际工程中面临两个新的核心挑战：

1. 如何设计“最小却充分”的系统提示，让模型既不啰嗦也不走偏？
2. 如何为模型提供结构化的工具（如 shell、apply_patch）协作能力，同时避免过度干预导致“提示噪声”与性能下降？

传统针对通用模型的提示技巧（大段规则、冗长上下文、显式规划指令等）在 GPT-5-Codex 上很多已经“内建”，继续沿用会带来：

- Token 负担 → 降低有效上下文密度
- 反直觉行为 → 触发早停或忽略关键意图
- 维护难度高 → 提示文件成为“新技术债”

因此，需要一套重新校准的实践：用“去冗余 + 明确工具协议 + 边界约束”替代“堆砌式”提示。

## 核心概念与原理

### 1. Minimal Prompt（最小化提示）

GPT-5-Codex 针对真实工程场景强化训练：

- 具备自适应推理（简单任务快速响应，复杂任务主动规划）
- 具备代码审查、重构、测试生成固化能力
- 已内建规划与分步执行模式（无需强制加“think step-by-step”）

因此系统提示应聚焦三个“必要而不可省略”的维度：

- 约束边界（禁止操作 / 风险区）
- 工具契约（如何调用 / 何时使用 / 结构要求）
- 输出格式（补丁、说明、验证片段）

### 2. Tool-Oriented Prompting（工具导向）

与其描述“你是一位资深工程师…请先分析…再……”，不如直接给出：

- shell 工具调用约束：必须显式 workdir；优先 `bash -lc`；只在需要时执行构建/测试
- apply_patch 结构：单一变更批、最小 diff、避免无关重排
- 失败分支策略：构建/测试失败时复述日志关键行 + 修复假设

### 3. Anti-Prompting（反过度提示）

“删除无效指令”往往比“新增一堆规则”更能提升质量：

- 不再显式要求“先列计划”——模型已在复杂任务中自适应
- 不再强制添加思维链格式化语句（可能引起啰嗦或早停）
- 避免重复描述工具功能（训练语料已包含）

### 4. 可靠变更：apply_patch 优先

直接整体重写文件 → 增加审查成本；
精细 diff (patch) → 对齐版本控制认知模式。模型在训练中已高频学习“增量补丁”分布，因此 apply_patch 更符合其内部偏好。

### 5. 安全与约束控制

通过“白名单 + 显性不可更改区域”降低破坏性风险：

- 可写路径：`src/`, `tests/`
- 禁止：`infra/`, `migrations/`, `LICENSE`, 生成产物
- 保留：未知二进制 / 大文件不回显（只引用路径）

## 实战与代码示例

### 1. 最小系统提示骨架

```text
You are an autonomous coding agent.
Goals: Implement feature X safely with minimal necessary edits.
Constraints:
- Only modify files in src/ and tests/.
- Do not touch infra/, build scripts, or dependency versions.
Tools:
- shell(cmd, workdir): run build/test when needed.
- apply_patch(patch): create minimal diffs; no unrelated reformatting.
Output:
- First: brief intent summary (one sentence).
- Then: apply_patch calls (one per logical change).
- If build/test run: summarize key output lines only.
If failure: provide hypothesis + next attempted fix.
```

### 2. 典型“差异补丁”用法

```diff
*** Begin Patch
*** Update File: src/math/add.ts
@@
-export function add(a: number, b: number) {
-  return a + b;
-}
+// Adds two numbers with input validation to avoid silent NaN propagation.
+export function add(a: number, b: number) {
+  if (Number.isNaN(a) || Number.isNaN(b)) {
+    throw new Error("Invalid number input");
+  }
+  return a + b;
+}
*** End Patch
```

要点：

- 仅修改必要行；
- 添加高信噪比注释；
- 无无关格式化（例如不改 import 顺序）。

### 3. shell 工具调用模式（伪示例）

```json
{
  "tool": "shell",
  "args": {
    "command": ["bash", "-lc", "npm test --silent"],
    "workdir": "/workspace"
  }
}
```

失败时不全量粘贴日志，提炼关键：

```text
Test failed: add() throws on NaN (Expected error not thrown)
Hypothesis: validation branch not covered due to early return.
```

### 4. 好 / 坏提示对比

| 类型         | 示例                                             | 问题             | 改进                                      |
| ------------ | ------------------------------------------------ | ---------------- | ----------------------------------------- |
| 过度指令     | “你是 20 年经验全栈架构师，请深呼吸后逐步思考……” | 无新增结构性价值 | 删除情绪化/冗余语句                       |
| 重复工具说明 | “apply_patch 用于打补丁，必须写 Begin Patch…”    | 训练中已知       | 保留最小契约（必须最小 diff）             |
| 模糊约束     | “不要改太多文件”                                 | 不可衡量         | 改为：最多 3 个文件 / 每文件 < 60 行 diff |

### 5. 组合任务：修复 + 回归测试

提示要素：

1. 指定 bug 现象（含复现步骤 / 输入输出差异）
2. 限定修改半径
3. 要求新增测试覆盖失败路径
4. 结果格式：补丁 + 覆盖说明

示例补充段（嵌入在主 Prompt 最后）：

```text
Bug:
Calling add(-0, 1) returns 1 but should preserve -0 semantics for downstream formatting.
Acceptance:
- Existing tests pass; new test asserts Object.is(result, -0) when adding -0 and 0.
Limits:
- Touch only add.ts and add.test.ts.
```

### 6. 回滚与再尝试策略（模型可引用）

```text
If first patch fails tests, do one of:
1. Minimal follow-up patch (preferred)
2. If uncertainty > 60%, explain hypothesis and ask for clarification (skip guessing)
Never: rewrite entire module unless explicitly requested.
```

## 常见陷阱与最佳实践

| 误区                    | 影响                     | 优化策略                                   |
| ----------------------- | ------------------------ | ------------------------------------------ |
| 提示过长堆满“身份/人格” | Token 浪费 / 噪声学习    | 限定在任务与约束本身                       |
| 重写整个文件            | Diff 难审查 / 回归风险高 | 使用 apply_patch 精准增量                  |
| 盲目运行大量 shell 命令 | 时间浪费 / 噪声输出      | 只在语义边界（构建 / 单测 / 性能验证）触发 |
| 不限制可写路径          | 误改基础设施或许可证     | 明确 allowlist / denylist                  |
| 测试失败直接继续生成    | 错误放大 / 次生缺陷      | 先总结失败 → 提出修复假设 → 再次补丁       |
| 复制全量日志或大文件    | 失焦 / 上下文溢出        | 摘要关键行 + 错误类型 + 触发条件           |
| 过度“鼓励思维链”        | 冗长 + 早停风险          | 让模型自适应；只在诊断时要结构化分析       |

最佳实践要点（精炼版）：

- 先裁剪（删除无效指令）再添加（缺失约束）
- 明确 _可修改范围 + 文件/行数硬上限_
- 输出 = “意图一句话 + 增量补丁 + 验证摘要”
- 失败路径要求“日志片段 + 假设 + 下一步”三元结构
- 所有工具调用都显式 `workdir`
- 评审提示文件本身 → 当作“配置代码”维护版本差异

## 总结与参考资料

GPT-5-Codex 的核心使用方式不是“让它多想”，而是“别替它想太多”：减少噪声、强化边界、提供结构化工具契约，让模型在高质量上下文中发挥“自适应推理 + 代码演进”能力。工程团队应把提示文件视为“演化型协作协议”——持续审计、差异化回顾、度量其对迭代速度与缺陷率的影响。配合最小化提示与 apply_patch 流程，可以显著提升自动化修改的可审查性与稳定性。

参考资料：

- 原文：GPT-5-Codex Prompting Guide（OpenAI Cookbook）
- Codex CLI Prompt 源文件与对比：[GitHub 仓库](https://github.com/openai/codex/)
- apply_patch 示例（OpenAI Cookbook 仓库 scripts）
- 相关理念：Minimal Prompting / Tool Augmented Agents / Incremental Diff Workflow
