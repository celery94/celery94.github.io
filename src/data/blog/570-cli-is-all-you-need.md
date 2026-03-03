---
pubDatetime: 2026-03-03
title: "CLI 就是你所需要的一切"
description: "MCP 的热潮退去，越来越多的开发者发现：把 AI 代理直接扔进终端、给它 shell 访问权限，才是最高效的编码工作流。Claude Code、Codex CLI、Gemini CLI 这些纯 CLI 代理正在领跑，而 Unix 管道和经典命令行工具从未过时。"
tags: ["AI", "CLI", "MCP", "Agentic Coding"]
slug: "cli-is-all-you-need"
source: "https://x.com/mfranz_on/status/2021364017147818434"
---

![CLI 就是你所需要的一切](../../assets/570/01-cli-is-all-you-need.jpg)

MCP 的故事发展得太快了。

六个月前它还是 "AI agent 工具链的未来"，是结构化、类型安全、面向企业的标准化工具服务器协议。现在，大量开发者已经悄悄地把它卸载了。

2026 年，跑得最快、代码最干净的那批开发者，回到了他们出发的地方：终端。

他们给 agent 直接的 shell 访问权限，让它用已经存在了几十年的工具：`git`、`rg`、`grep`、`npm`、`docker`、`curl`、`jq`、`tail`。没有自定义服务器，没有把上下文窗口撑爆的 schema 描述，只有一个推理能力强的模型加上 bash/zsh。

然后，agentic coding 突然就有了魔法感。

## MCP 为什么在日常开发里失去了吸引力

对于典型的开发工作流，MCP 带来的往往是阻力，而不是杠杆：

**Token 开销。** 冗长的工具目录和 schema 会消耗宝贵的上下文窗口，留给实际任务的空间就少了。

**重新发明轮子。** 大量自定义 MCP server 做的事情，官方 CLI 早就能做，而且做得更可靠。

**失去可组合性。** Unix 花了几十年打磨的那套管道、链式调用、一次性 hack 的能力，在 MCP 架构里全部消失了。

**模型对齐。** Claude、GPT 系列、Gemini 这些前沿模型，训练数据里塞满了 shell 用法。它们对 flags、pipes、错误信息、man page 风格文档的理解，已经达到了荒诞的好。给它 shell，它如鱼得水；给它 MCP，它还要先学规则。

规律很清晰：把 agent 扔进项目目录，给它 shell 执行权限（加上适当的安全边界），描述任务。agent 会自己规划、跑命令、改文件、跑测试、提交、调试，在一个紧凑的循环里持续迭代。

MCP 在高度结构化的企业集成场景里仍然有价值，比如受监管环境里类型安全的 SaaS API 对接。但对于 80-90% 的日常工作流，它是噪音。

## CLI 原生代理方阵

**Claude Code（Anthropic）**

目前深度推理大型或复杂代码库的领导者。架构讨论、谨慎的重构、跨多文件修改加上清晰的解释，这是它的主场。原生终端工作流，文件编辑、shell 访问、git 集成全部内置。按用量计费，但遇到硬问题时完全值得。

**Codex CLI（OpenAI）**

轻量、快、直接访问 OpenAI 的强力模型。代码生成、测试、快速迭代场景表现好。开源基础让它容易定制甚至本地运行。

**Gemini CLI（Google）**

有免费额度，多模态能力强。快速原型、UI 任务、大型项目是它的优势。纯终端操作，ReAct 风格的推理循环干净清晰。开源且对隐私友好。

**OpenCode**

支持 75+ 模型提供商，有 LSP 集成，隐私保护做得扎实。很多开发者称它是目前最高效的终端代理。社区增长很快。

## CLI 碾压 MCP 的场景

**Monorepo 范围的重构**

agent 从一句搜索出发：

```bash
rg "oldDeprecatedFunction" .
```

然后规划跨文件的定向修改，用 `git diff` 审查，跑 `npm test` 或 `cargo test`，最后提交：

```
refactor: remove deprecated API calls
```

没有 GitHub MCP server，没有臃肿上下文，只有 `rg`、`git` 和测试工具。

**生产 Bug 的全栈调试**

指令："在 staging 环境复现这个 auth 失败。"

agent 自己跑起来：

```bash
git pull
npm install
npm run dev
tail -f logs/server.log | grep error
curl -v api/auth/check
docker-compose up -d db redis
npm test -- --grep auth
```

改文件，重跑测试，探测端点，循环迭代。没有 Docker MCP，没有 logging MCP，只有 shell 流利度。

**新微服务脚手架**

指令："用 Axum + sqlx 写一个 Rust 用户 Profile API，连接 Postgres。"

```bash
cargo new --bin user-service
cargo add axum sqlx --features postgres
cargo watch -x run
curl localhost:3000/health
```

沿途提交。没有 Rust MCP，没有 database MCP。现有工具链已经足够。

**CI/CD 修 Flake**

agent 克隆仓库，用 `act` 本地跑 workflow，定位失败，编辑 `.github/workflows/ci.yml` 或 Dockerfile，用 `docker build` 验证，推分支，用 `gh` 开 PR。全程标准 CLI 工具，没有任何定制 CI 集成层。

## 开发者反复提到的规律

拥抱 CLI 原生代理的团队持续报告：更高的速度、更少的 token 意外、更透明的 agent 行为、更容易调试 agent 在做什么。

最近流传的几句话：

> "停止构建集成。构建 CLI。"
>
> "Bash 才是终极的 MCP。"
>
> "Agent 是在 Unix 管道上训练的，它们在这里强得离谱。"
>
> "CLI 就是你所需要的一切。其他都是仪式感。"

终端一直是通用的开发者环境。在 2026 年，它也是 AI coding agent 最强大的界面。

除非你深陷专有企业工具链的内部，否则跳过那套 MCP 重型架构。

```
cd 进你的项目
启动你喜欢的 CLI 代理
给它 shell 访问权限
描述任务
```

然后看它工作。

## 参考

- [原文](https://x.com/mfranz_on/status/2021364017147818434) — Marco Franzon (@mfranz_on)
