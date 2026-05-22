---
pubDatetime: 2026-05-22T07:48:38+08:00
title: "用 AGENTS.md 和 Skills 让 AI 编程更像团队协作"
description: "Microsoft ISE 介绍了一套团队使用 AI 编程工具的做法：用 AGENTS.md 提供项目上下文，用 skills 固化重复任务步骤，再让测试、静态检查和评审兜住质量。"
tags: ["AI", "GitHub Copilot", "AGENTS.md", "工程实践"]
slug: "agents-md-skills-ai-assisted-development"
ogImage: "../../assets/819/01-cover.png"
source: "https://devblogs.microsoft.com/ise/ai-assisted-development-agents-skills-copilot-cli/"
---

团队里每个人都在用 AI 写代码时，一个常见问题很快会出现：生成结果不稳定。有人拿到的代码符合项目结构，有人拿到的是通用模板；有人让 AI 生成了合适的测试，有人的测试和团队习惯完全不一致。

Microsoft ISE 这篇文章讲了一种解决办法：把团队约定写进仓库，让 AI 工具每次开始工作前先读这些约定。它把信息分成三层：`AGENTS.md` 负责项目级上下文，skills 负责具体任务步骤，CI 和评审负责检查结果。

## 问题从哪里来

原文来自一次 ISE 客户项目。团队同时维护两个部署在 Azure 上的 SaaS 产品，每个产品都是 polyglot monorepo，里面有基础设施、后端和前端。

工程师都在用 GitHub Copilot CLI，但每个人的使用方式各自独立。团队观察到几个问题：

- 生成代码放错目录
- 测试没有遵循 AAA，也就是 Arrange、Act、Assert 的结构
- import 路径、命名、依赖注入写法不一致
- 后续要花不少时间把 AI 生成内容改回项目习惯

问题根源很直接：每次调用都从零上下文开始。AI 不知道项目架构、目录结构、技术栈和编码约定，自然容易生成通用结果。

## AGENTS.md 管项目上下文

`AGENTS.md` 是面向 AI coding agents 的仓库说明文件。原文把它类比成新成员入组时的项目导览：产品做什么、部署在哪里、目录怎么组织、技术栈是什么、写代码和写测试有什么约定。

一个有用的 `AGENTS.md` 至少应该包含：

- 项目概览：产品用途、目标用户、部署目标
- 架构说明：带注释的目录结构
- 技术栈：语言、框架、版本
- 编码约定：命名、import 顺序、错误处理、测试结构

原文示例是一个环境风险评估平台，前端是 Next.js 15、React 19 和 TypeScript，后端是 Python 3.13 与 FastAPI，基础设施是 Terraform。文档里明确写了 `Frontend/`、`Backend/`、`Infrastructure/` 的结构，也写了测试要用 AAA，服务依赖 repository interface，import 使用项目根路径。

GitHub Docs 也提到，Copilot 可以使用仓库里的 agent instructions。一个仓库可以有多个 `AGENTS.md`，目录树中离当前工作位置最近的文件优先。

## Skills 管具体任务

如果 `AGENTS.md` 解决的是“项目是什么”，skills 解决的是“这类任务怎么做”。

原文中的 skills 放在 `.github/skills/` 下，每个 skill 负责一个重复任务。例如这次项目里有 4 个 skill：

- `create-api-endpoint`
- `create-langgraph-graph`
- `create-langgraph-tool`
- `create-terraform-module`

每个 skill 文件会写清楚这些内容：

- 什么时候使用这个 skill
- 运行前需要哪些前置条件
- 要创建哪些文件，放在哪些目录
- 代码模板和占位符怎么写
- 对应测试文件怎么生成

以 `Create API Endpoint` 为例，它会要求先创建 Pydantic schema，再创建 repository interface，再写 SQL implementation，然后创建 service、router，注册路由，补单元测试和集成测试。

GitHub Docs 对 skills 的说明也类似：一个 skill 是一个目录，里面必须有 `SKILL.md`，也可以包含脚本、示例和其他资源。项目级 skill 可以放在 `.github/skills`、`.claude/skills` 或 `.agents/skills`。

## 两者一起用

原文给出的工作流很清楚：

```bash
gh copilot suggest "Create a new API endpoint for environmental reports"
```

Copilot CLI 先读取 `AGENTS.md`，知道项目结构和约定；然后匹配 `create-api-endpoint` skill，按步骤生成 schema、repository、service、router、unit test 和 integration test。

这样生成出来的文件更容易符合团队习惯。工程师不用在每次提示词里重复说明目录、命名、依赖注入和测试布局。

## 还要有验证层

原文强调，提速不能跳过检查。这个项目把 AI 辅助变更都放进常规工程流程里：

- targeted CI：前端变更不触发基础设施测试
- 单元测试、使用 Testcontainers 的集成测试、使用 Playwright 的 E2E 测试
- CodeQL 安全检查
- Ruff、Prettier、Checkov 等 lint 和静态检查
- PR review

这部分很关键。`AGENTS.md` 和 skills 能让 AI 更懂项目，但不能保证每次结果都正确。测试、静态检查和评审仍然是合并前的基本门槛。

## 如何开始

可以按这个顺序做：

1. 先写 `AGENTS.md`。把目录、技术栈、测试结构、命名和常用命令写清楚。先覆盖最常见的开发路径。
2. 找第一个 skill。选择团队最常重复、步骤最固定的任务，比如新增 API endpoint、加 feature flag、补观测日志。
3. 把检查放进 CI。测试、lint、静态检查和评审规则要先跑起来。
4. 定期更新。目录调整、测试方式变化、依赖升级后，对应的 `AGENTS.md` 和 skill 也要改。

原文还提醒，skill 要小而窄。像“新增一个 API endpoint”这种任务适合写成 skill；“搭一个完整前端”这类范围太大，AI 更难稳定执行。

## 维护也很重要

随着 skill 数量增加，要把它们当成代码管理：

- 名字要清楚，比如 `create-api-endpoint`、`add-feature-flag`
- 每个 skill 有明确 owner
- 修改走 PR review
- 跟代码一起版本管理，别放到外部 wiki
- 过期 skill 先标记 deprecated，再移除
- 定期抽样检查 AI 生成结果是否仍符合团队习惯

原文的经验也值得记住：`AGENTS.md` 写得太泛，结果会继续通用；写得太长，又可能挤占上下文窗口。skill 过期后，会稳定地产出过期写法。

## 结语

这篇文章的核心价值，是把 AI 编程从个人提示词习惯，转成仓库里的共同约定。

`AGENTS.md` 让 AI 先理解项目；skills 把高频任务拆成可复用步骤；CI、测试和评审负责拦住错误。无论项目是 Python/FastAPI、.NET、Node.js 还是 Go，这个思路都能复用。

## 参考

- [Coordinating AI-Assisted Development with AGENTS.md and Skills](https://devblogs.microsoft.com/ise/ai-assisted-development-agents-skills-copilot-cli/)
- [Using GitHub Copilot in the command line](https://docs.github.com/en/copilot/using-github-copilot/using-github-copilot-in-the-command-line)
- [Adding agent skills for GitHub Copilot CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/create-skills)
- [Adding repository custom instructions for GitHub Copilot](https://docs.github.com/en/copilot/customizing-copilot/adding-repository-custom-instructions-for-github-copilot)
