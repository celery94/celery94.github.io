---
pubDatetime: 2026-04-08T20:21:45+08:00
title: "解剖 .claude 文件夹：每个文件的作用详解（2026）"
description: "完整解析 .claude 文件夹的结构——CLAUDE.md、rules、skills、agents、commands、settings.json、全局 ~/.claude/ 目录，附 .NET 项目实践示例，让你彻底搞清楚每个配置文件的加载时机和使用场景。"
tags: ["Claude Code", "AI", "开发工具", "dotnet"]
slug: "anatomy-of-the-claude-folder"
ogImage: "../../assets/720/01-cover.png"
source: "https://codewithmukesh.com/blog/anatomy-of-the-claude-folder/"
---

大多数用过 Claude Code 的开发者都知道 `.claude` 文件夹的存在。它会出现在项目根目录，有些人甚至打开过它。但真正理解里面每个文件的作用、加载时机、以及各部分如何配合的人，其实并不多。

这是个不小的代价。`.claude` 文件夹是控制 Claude 在项目中行为的核心。它存放你的指令、自定义工作流、权限规则，甚至 Claude 跨会话的记忆。一个只有 20 行 `CLAUDE.md` 的初级配置和一个成熟项目的完整配置之间，差距直接体现在 Claude 对你团队的实际用处上。

本文会逐一介绍 `.claude/` 里每个文件和目录，解释加载时机、交互方式，并给出可直接用于 .NET 项目的实践示例。不留黑盒，不靠猜测，只提供清晰的地图：什么放哪里，为什么放那里。

`.claude` 文件夹控制 5 个不同子系统：**指令**（CLAUDE.md 和 rules）、**工作流**（skills 和 commands）、**专家**（agents）、**权限**（settings.json）、**记忆**（全局 `~/.claude/` 目录）。理解这些部分如何配合，配置 Claude 就不再是靠直觉摸索了。

![.claude 文件夹架构示意图](../../assets/720/01-cover.png)

## 完整结构：.claude/ 里有什么

在深入每个部分之前，先看看完整结构。并非每个项目都需要所有这些文件，但这是一个成熟的 `.claude` 配置长什么样：

```
your-project/
├── CLAUDE.md                    # 团队指令（提交到 git）
│
└── .claude/
    ├── settings.json            # 权限 + 配置（提交到 git）
    ├── settings.local.json      # 个人权限覆盖（gitignore 掉）
    │
    ├── rules/                   # 模块化指令文件
    │   ├── dotnet-conventions.md # 每次都加载
    │   ├── ef-core.md           # 路径限定到 DbContext/Migrations
    │   └── api-design.md        # 路径限定到 API controllers
    │
    ├── skills/                  # 可复用工作流
    │   ├── code-review/
    │   │   └── SKILL.md
    │   ├── deploy/
    │   │   └── SKILL.md
    │   └── fix-issue/
    │       └── SKILL.md
    │
    ├── agents/                  # 专业子代理人格
    │   ├── code-reviewer.md
    │   └── security-auditor.md
    │
    ├── docs/                    # 共享参考文档
    │   ├── architecture.md
    │   └── coding-standards.md
    │
    └── worktrees/               # 隔离的 git worktree 会话

~/.claude/                       # 全局（个人，适用所有项目）
├── CLAUDE.md                    # 你的全局指令
├── settings.json                # 你的全局设置
├── rules/                       # 个人规则（所有项目）
├── skills/                      # 个人技能（所有项目）
├── agents/                      # 个人代理（所有项目）
└── projects/                    # 会话历史 + 自动记忆
```

东西不少。下面逐一拆解。

## 两个文件夹，不是一个

首先要明确：实际上存在**两个** `.claude` 目录，不是一个。

**项目级**（repo 根目录的 `.claude/`）：存放团队配置，提交到 git，团队所有成员使用相同的规则、技能和权限策略。

**全局**（主目录的 `~/.claude/`）：存放个人偏好和机器本地状态，包括会话历史、自动记忆，以及适用于你所有项目的全局设置。

这个区别决定了什么内容会共享、什么保持个人化。团队的编码标准放在项目文件夹；你个人偏好的详细错误输出放在全局文件夹。

以下是完整的优先级顺序，从高到低：

| 优先级 | 来源 | 位置 |
|--------|------|------|
| 1（最高） | 托管策略 | 系统级（由 IT 设置） |
| 2 | CLI 参数 | 命令行参数 |
| 3 | 本地覆盖 | `.claude/settings.local.json` |
| 4 | 项目设置 | `.claude/settings.json` |
| 5（最低） | 用户设置 | `~/.claude/settings.json` |

当两个设置冲突时，优先级较高的来源获胜。这意味着团队可以设置项目默认值，但每个开发者可以在本地覆盖，而不影响其他人。

## CLAUDE.md：最高杠杆的文件

这是整个系统中最重要的单个文件。当你启动 Claude Code 会话时，它读取的第一件事就是 `CLAUDE.md`，将内容直接加载到系统提示中，并在整个对话过程中保持记忆。

简单说：你在 CLAUDE.md 中写什么，Claude 就遵守什么。如果你告诉 Claude 总是在实现之前写测试，它就会这样做。如果你说"永远不要用 `Console.WriteLine` 处理错误，始终使用 `ILogger` 抽象"，它每次都会遵守。

### CLAUDE.md 可以放哪里

Claude Code 从你当前工作目录**向上遍历目录树**，加载它找到的每一个 `CLAUDE.md`：

| 位置 | 范围 | 是否共享 |
|------|------|---------|
| `./CLAUDE.md`（项目根） | 团队指令 | 通过 git |
| `./.claude/CLAUDE.md`（文件夹内） | 备用位置 | 通过 git |
| `./CLAUDE.local.md` | 个人项目偏好 | 仅自己（gitignore） |
| `~/.claude/CLAUDE.md` | 个人，所有项目 | 仅自己 |
| 托管策略路径 | 组织级 | 所有用户 |

如果你在 `src/Api/Handlers/` 工作，而该子目录有 `CLAUDE.md`，Claude 会在读取该目录文件时**按需**加载它。父目录的 CLAUDE.md 在启动时加载。这意味着在 monorepo 中，你可以为不同文件夹设置特定指令，而不会搞乱根文件。

### 好的 CLAUDE.md 长什么样

下面是一个 .NET API 项目的实用 CLAUDE.md：

```markdown
# Acme API

ASP.NET Core 10 Web API，采用 Clean Architecture。

## 命令

dotnet build src/Acme.sln          # 构建
dotnet test tests/Acme.Tests/      # 运行测试（xUnit）
dotnet format src/Acme.sln         # 格式化代码
dotnet ef database update           # 应用迁移

## 架构

- Clean Architecture：Api → Application → Domain → Infrastructure
- 使用 `src/Api/Endpoints/` 中的端点类的 Minimal APIs
- MediatR 实现 CQRS：命令在 Application/Commands/，查询在 Application/Queries/
- EF Core 10 配合 PostgreSQL

## 关键路径

| 内容 | 位置 |
|------|------|
| 端点 | `src/Api/Endpoints/` |
| 领域实体 | `src/Domain/Entities/` |
| EF 迁移 | `src/Infrastructure/Persistence/Migrations/` |
| 集成测试 | `tests/Acme.IntegrationTests/` |

## 约定

- API 文档使用 Scalar（不用 Swagger）
- 端点返回 `Results<Ok<T>, NotFound, ValidationProblem>`
- 所有处理器以 `CancellationToken` 作为最后一个参数
- 请求验证使用 FluentValidation
- 永远不要向客户端暴露堆栈跟踪

## 注意事项

- 测试通过 Testcontainers 使用真实的 PostgreSQL，不用 mock
- React 前端使用严格 TypeScript：不允许未使用的 imports
- `src/Shared/` 项目同时被 Api 和 Workers 引用——那里的改动会影响两者
```

大约 35 行。这给了 Claude 在这个代码库中高效工作所需的一切，不需要反复澄清。注意结构：**命令、架构、路径、约定、坑点**。这涵盖了 Claude 需要了解内容的 95%。

### 不该放什么

- linter 或 formatter 已经处理的内容（缩进、导入排序）
- 可以链接替代的完整文档
- 解释理论的长段落
- 代码片段（这些属于 skills 或 docs）

### 文件大小与效果

**目标控制在 200 行以内。** 超过这个长度会消耗过多上下文，Claude 的指令遵守率实际上会下降。如果你的文件越来越臃肿，这是拆分到 `.claude/rules/` 文件的信号。

还有一点值得了解：CLAUDE.md **在压缩后仍然存在**。当你运行 `/compact` 或 Claude 自动压缩时，它会从磁盘重新读取 CLAUDE.md。你只在对话中给出的指令在压缩后会丢失，但 CLAUDE.md 指令会持久存在。这使得 CLAUDE.md 成为给 Claude 永久指令的最可靠方式。

### 个人覆盖与 @import

有时你需要一个特定于你自己而非整个团队的偏好。也许你想用不同的测试运行器，或者在调试会话期间更偏好详细输出。

推荐的方法是使用 `~/.claude/CLAUDE.md` 存放适用于所有项目的个人偏好，或者使用 `@import` 语法引入个人文件：

```markdown
# 在你的项目 CLAUDE.md 中
@~/.claude/my-dotnet-preferences.md
```

`@import` 语法支持相对路径和绝对路径，最大递归导入深度为 **5 跳**。首次遇到外部导入时会触发安全审核对话框。

## rules/ 文件夹：模块化、路径限定的指令

CLAUDE.md 对小项目效果很好。但一旦你的指令超过 200 行，或者团队多个成员需要维护不同部分，你就需要模块化——这就是 `.claude/rules/` 的用武之地。

`.claude/rules/` 里的每个 Markdown 文件都会与你的 CLAUDE.md 一起加载。你可以按关注点拆分指令，而不是维护一个巨大的文件：

```
.claude/rules/
├── code-style.md        # C# 约定，命名规范
├── testing.md           # 测试要求，mock 规则
├── api-conventions.md   # REST 标准，响应体格式
└── security.md          # 认证模式，密钥处理
```

每个文件保持专注，易于更新。负责 API 约定的团队成员编辑 `api-conventions.md`，负责测试标准的人编辑 `testing.md`，互不干扰。

Claude Code **递归**发现文件，所以你也可以用子目录组织：

```
.claude/rules/
├── backend/
│   ├── ef-core.md
│   └── api-design.md
└── frontend/
    ├── react-conventions.md
    └── testing.md
```

### 不带路径限定的规则（每次都加载）

没有 frontmatter 的规则在每个会话启动时加载。适用于无论 Claude 在编辑什么文件都需要遵守的指令：

```markdown
# .NET 约定

## 常规

- 所有新代码面向 .NET 10
- 所有地方使用文件范围命名空间
- 依赖注入使用主构造函数
- DTO 和值对象使用 Records
- 每个异步方法都带 `CancellationToken` 的 `async/await`

## 命名

- 接口前缀 `I`（IUserRepository、IEmailService）
- 异步方法后缀 `Async`（GetUserAsync、SendEmailAsync）
- 私有字段前缀 `_`（_logger、_repository）

## 错误处理

- 使用 Result<T> 模式，预期失败不要抛异常
- 意外错误在中间件中使用全局异常处理器
- 永远不要向 API 消费者暴露内部异常详情
```

这在每个会话都加载，因为这些约定适用于项目中的每个 C# 文件。

### 路径限定的规则（按需加载）

这是规则真正强大的地方。添加一个带 `paths` 的 YAML frontmatter 块，规则就只会在 Claude 处理匹配文件时激活：

```markdown
---
paths:
  - "src/Infrastructure/Persistence/**/*.cs"
  - "**/*DbContext*.cs"
  - "**/Migrations/**"
---

# EF Core 规则

- 始终在字符串属性上使用 `HasMaxLength()`，不要依赖默认值
- 每个外键列都加索引
- 枚举到字符串的数据库映射使用 `ValueConverter`
- 迁移名称必须描述性：`AddUserEmailIndex` 而不是 `Migration_001`
- 始终包含能反转迁移的 `Down()` 方法
- 应用前运行 `dotnet ef migrations script` 验证 SQL
```

这个规则只在 Claude 编辑 EF Core 相关文件时加载。当它在处理 React 组件或 API 端点时，这些数据库规则不会消耗上下文。打开迁移文件时，它们自动激活。

glob 模式支持标准语法：

| 模式 | 匹配范围 |
|------|---------|
| `**/*.ts` | 任何位置的所有 TypeScript 文件 |
| `src/Api/**/*.cs` | 仅 `src/Api/` 下的 C# 文件 |
| `*.md` | 仅项目根目录的 Markdown 文件 |
| `src/**/*.{ts,tsx}` | 多扩展名的大括号展开 |
| `**/*DbContext*.cs` | 名称包含 "DbContext" 的任何文件 |

### 何时从 CLAUDE.md 拆分

根据经验：如果 CLAUDE.md 中某个部分超过 15-20 行，并且针对特定关注点（测试、API 设计、格式化），就将其移到规则文件中。如果它只适用于特定文件类型，就添加路径限定。

对于 .NET 项目，一个实用的拆分方案：

```
.claude/rules/
├── dotnet-conventions.md          # 无 paths - 每次都加载
├── ef-core.md                     # paths: ["**/*DbContext*.cs", "**/Migrations/**"]
├── api-conventions.md             # paths: ["src/Api/**/*.cs"]
├── test-standards.md              # paths: ["tests/**/*.cs"]
└── docker.md                      # paths: ["**/Dockerfile*", "docker-compose*.yml"]
```

### 用户级规则

`~/.claude/rules/` 中的个人规则适用于每个项目，在项目规则**之前**加载，给予项目规则在冲突时更高的优先级。这是放置你希望在任何地方都生效的个人编码偏好的好地方。

## skills/ 文件夹：核心所在

如果 CLAUDE.md 是说明手册，skills 就是自动化引擎。每个 skill 是一个可复用的工作流，Claude 可以通过斜杠命令调用，或根据你的对话自动触发。

### 规则与技能的区别

这是个容易混淆的关键区别：

| | 规则 | 技能 |
|--|------|------|
| 加载时机 | 启动时（路径限定的在访问文件时） | 按需调用时 |
| 调用方式 | 自动——Claude 静默读取 | `/skill-name` 或由 Claude 自动调用 |
| 目的 | 被动指令（"总是做 X"） | 主动工作流（"执行这一序列步骤"） |
| 大小 | 短（10-50 行） | 长（50-300 行） |
| 上下文开销 | 始终消耗上下文 | 仅在激活时 |

规则告诉 Claude **如何行为**。技能告诉 Claude **做什么**。

### SKILL.md 格式

每个 skill 存放在自己的子目录中，以 `SKILL.md` 文件作为入口：

```
.claude/skills/
├── code-review/
│   └── SKILL.md       # 必需的入口点
├── fix-issue/
│   └── SKILL.md
└── deploy/
    ├── SKILL.md
    └── templates/
        └── release-notes.md    # 支持文件
```

技能可以将支持文件与 SKILL.md 打包在一起。在技能中用 `@` 语法引用它们：`@templates/release-notes.md` 在技能运行时会引入模板内容。

SKILL.md 使用 YAML frontmatter 配置行为：

```markdown
---
name: code-review
description: >
  Review the current branch for bugs, security issues, and code
  quality. Use when the user asks to review code, check a PR, or audit changes.
allowed-tools: Read Grep Glob Bash
argument-hint: [branch-name]
---

# /code-review - Code Review

对当前分支相对 main 的所有改动进行代码审查。

## 工作流

### 第 1 步：获取 diff
!`git diff main...HEAD --stat`

### 第 2 步：读取变更文件
完整阅读每个修改过的文件。不只看 diff——理解周围的上下文。

### 第 3 步：对照标准检查
阅读 `.claude/docs/coding-standards.md` 获取团队的质量基准。

### 第 4 步：报告
对每个文件，报告：
- **Bug**：逻辑错误、空引用风险、竞态条件
- **安全**：注入风险、认证漏洞、暴露的密钥
- **质量**：命名、复杂度、缺少错误处理
- **测试**：改动是否有覆盖？缺少哪些测试用例？

总体评级：APPROVE、REQUEST CHANGES 或 NEEDS DISCUSSION。
```

### frontmatter 字段参考

以下是 SKILL.md frontmatter 中可以使用的完整字段列表：

| 字段 | 作用 | 示例 |
|------|------|------|
| `name` | 斜杠命令名称（最多 64 个字符） | `code-review` 变为 `/code-review` |
| `description` | Claude 何时应该自动调用此技能 | `"Use when reviewing code for quality"` |
| `allowed-tools` | 无需权限提示即可运行的工具（空格分隔或 YAML 列表） | `Read Grep Glob` |
| `model` | 覆盖此技能的模型 | `sonnet`（更便宜的简单任务） |
| `argument-hint` | 斜杠菜单中显示的自动补全提示 | `[branch-name]` |
| `context` | 设为 `fork` 以在隔离的子代理上下文中运行 | `fork` |
| `agent` | `context: fork` 时的子代理类型 | `Explore`、`Plan` 或自定义代理 |
| `effort` | 覆盖努力级别 | `high`、`low` |
| `disable-model-invocation` | 阻止 Claude 自动调用 | `true` |
| `user-invocable` | 从 `/` 菜单隐藏（仅作为背景知识） | `false` |
| `hooks` | 此技能范围内的生命周期钩子 | 见钩子文档 |

`description` 字段尤其重要。Claude 在会话开始时读取所有技能描述，并用它们决定何时自动调用。如果你的描述模糊，Claude 会在错误的时机调用技能；如果描述具体，Claude 就能精准匹配。

### Shell 注入与 ! 语法

`!`command`` 语法在技能内容到达 Claude 之前运行 shell 命令并注入输出。这是预处理，不是 Claude 执行的东西：

```markdown
## 当前 PR 上下文

- 变更文件：!`git diff main...HEAD --name-only`
- 测试结果：!`dotnet test --no-build --verbosity quiet 2>&1 | tail -5`
- 分支：!`git branch --show-current`
```

当你调用技能时，Claude 看到的是这些命令的实际输出，而不是命令本身。这让技能具有动态性和上下文感知能力。

### 变量替换

| 变量 | 描述 |
|------|------|
| `$ARGUMENTS` | 调用时传入的所有参数 |
| `$ARGUMENTS[0]` 或 `$0` | 按 0 为基数的索引取第一个参数 |
| `${CLAUDE_SESSION_ID}` | 当前会话 ID |
| `${CLAUDE_SKILL_DIR}` | 包含 SKILL.md 文件的目录 |

使用 `/fix-issue 234` 调用技能时，`$ARGUMENTS` 会被替换为 `234`。

### 构建链式数据的技能示例

一个调查并修复 GitHub issue 的实用技能：

```markdown
---
name: fix-issue
description: >
  Investigate and fix a GitHub issue. Use when the user mentions
  an issue number or asks to fix a bug from GitHub.
argument-hint: [issue-number]
allowed-tools: Read Edit Write Grep Glob Bash
---

# /fix-issue - 调查并修复 GitHub Issue

## 第 1 步：理解 issue
!`gh issue view $ARGUMENTS --json title,body,labels,comments`

## 第 2 步：复现
根据 issue 描述，确定失败行为。运行相关测试套件，看是否已有失败的测试：

dotnet test --filter "Category=Integration" --verbosity normal

## 第 3 步：找到根本原因
追踪代码库中的 issue。不要只修复症状——理解它为什么发生。

## 第 4 步：修复并测试
1. 用最小改动实现修复
2. 写一个本来能捕获这个 issue 的测试
3. 运行完整测试套件检查回归
4. 根据原始 issue 描述验证修复

## 第 5 步：总结
报告你发现了什么，改了什么，添加了什么测试。
```

这个技能将多个步骤串联起来：获取 GitHub issue、帮助复现、找到根本原因、修复。每一步都在上一步的基础上构建。这就是技能的力量——不只是提示，而是多步骤工作流。

### 自动调用 vs 手动调用

技能可以两种方式调用：

| 方式 | 发生什么 |
|------|---------|
| 手动 | 你输入 `/fix-issue 234` |
| 自动调用 | 你说"能帮我看 GitHub 上的 issue 234 吗？"，Claude 读取技能描述，匹配你的意图，自动调用 `/fix-issue` |

你可以控制这种行为：

| frontmatter | 用户调用 | Claude 调用 | 使用场景 |
|-------------|---------|------------|---------|
| （默认） | 是 | 是 | 大多数技能 |
| `disable-model-invocation: true` | 是 | 否 | 破坏性或高成本操作 |
| `user-invocable: false` | 否 | 是 | 背景知识技能 |

对于部署技能和任何修改生产资源的操作，`disable-model-invocation: true` 是值得设置的——你需要主动决策才触发。

### 技能的上下文预算

技能描述消耗约 **1% 的上下文窗口**（回退到 **8000 个字符**），每个独立描述在列表中上限为 **250 个字符**。如果你有很多带长描述的技能，描述会被截短以适应，这可能会去掉 Claude 匹配你请求所需的关键词。运行 `/context` 查看。在描述的前 250 个字符中优先写核心用例，对少用的技能设置 `disable-model-invocation: true` 以将它们完全从 Claude 的上下文中移除。要提高预算，设置 `SLASH_COMMAND_TOOL_CHAR_BUDGET` 环境变量。

## commands/ 文件夹：技能的前身

在技能出现之前，`commands/` 文件夹是创建自定义斜杠命令的方式。你放入 `.claude/commands/` 的每个 Markdown 文件都会成为一个命令。

名为 `review.md` 的文件创建 `/project:review`，名为 `fix-issue.md` 的文件创建 `/project:fix-issue`。文件名就是命令名。

### 命令 vs 技能：实际情况

**命令已被合并进技能系统。** `.claude/commands/deploy.md` 和 `.claude/skills/deploy/SKILL.md` 都创建 `/deploy` 命令，工作方式相同。现有命令文件继续有效，但如果技能和命令同名，**技能优先**。

经验总结：

| 使用**命令**当… | 使用**技能**当… |
|----------------|----------------|
| 是单文件提示 | 需要旁边的支持文件 |
| 你总是手动调用它 | Claude 应该根据上下文自动调用 |
| 简单（< 50 行） | 多步骤工作流（50-300 行） |
| 不需要特殊工具限制 | 你想限制可用的工具 |

如果你从头开始，**直接用技能**。它们功能更强大。命令更容易创建（单文件，不需要目录），但这大概是唯一的优势。

命令的位置：

| 位置 | 显示为 | 是否共享 |
|------|--------|---------|
| `.claude/commands/review.md` | `/project:review` | 通过 git |
| `~/.claude/commands/standup.md` | `/user:standup` | 仅自己 |

## agents/ 文件夹：专业子代理人格

当一个任务复杂到足以受益于专门专家时，你可以在 `.claude/agents/` 中定义子代理人格。每个代理都是一个 Markdown 文件，有自己的系统提示、工具访问权限和模型偏好。

```
.claude/agents/
├── code-reviewer.md
├── security-auditor.md
└── documentation-writer.md
```

一个真实的代理文件长这样：

```markdown
---
name: security-auditor
description: >
  Security specialist. Use PROACTIVELY when reviewing code for
  vulnerabilities, before deployments, or when touching auth/payment logic.
tools: Read, Glob, Grep
model: sonnet
maxTurns: 50
---

你是一名专注于 .NET 的资深应用安全工程师。

审查代码时：
- 检查 SQL 注入，即使使用 EF Core（原始 SQL 查询、FromSqlRaw）
- 验证每个端点的认证属性
- 在代码、配置或注释中寻找密钥
- 检查 CORS 配置，确认没有过于宽松的来源
- 验证所有面向用户端点的输入验证
- 检查批量赋值漏洞（DTO 与实体）
- 审查 JWT 配置（过期时间、签名算法、发行者验证）

对每个发现评级：CRITICAL、HIGH、MEDIUM、LOW。
提供带代码示例的具体修复建议。
```

### 代理如何工作

当 Claude 委托给代理时，它会生成一个**独立的上下文窗口**。代理完成工作——读取文件、运行搜索、分析代码——然后将发现压缩成摘要发送回你的主会话。你的主对话不会被数百行中间探索过程所干扰。

想象成委托给同事。你说"审查这个 PR 的安全问题"，他们带着报告回来。你看不到他们打开的每个文件或运行的每次 grep。

### 所有代理 frontmatter 字段

| 字段 | 用途 | 示例 |
|------|------|------|
| `name` | 标识符（必需） | `security-auditor` |
| `description` | 何时委托给这个代理（必需） | `"Use when reviewing for security"` |
| `tools` | 代理可以做什么（省略则继承所有） | `Read, Glob, Grep`（只读） |
| `disallowedTools` | 工具黑名单 | `Bash, Write` |
| `model` | 使用哪个模型 | `sonnet`（更便宜）、`haiku`（最快）、`inherit` |
| `maxTurns` | 最大代理迭代次数 | `50` |
| `permissionMode` | 权限级别 | `default`、`acceptEdits`、`plan` |
| `isolation` | 在 git worktree 中运行 | `worktree` |
| `memory` | 持久记忆范围 | `user`、`project`、`local` |
| `background` | 始终作为后台任务运行 | `true` |
| `skills` | 预加载到代理上下文的技能 | `["api-conventions"]` |
| `mcpServers` | 对代理可用的 MCP 服务器 | 行内或引用 |
| `hooks` | 此代理范围内的生命周期钩子 | 见钩子文档 |

### 工具限制是刻意设计

安全审计员只需要 `Read`、`Grep` 和 `Glob`，没有理由写文件。文档编写者需要 `Read`、`Write`、`Edit`，但不需要 `Bash`。明确指定工具访问是一个安全特性，不只是配置。

### 模型选择可以省钱

`model` 字段让你为专注任务使用更便宜、更快的模型。只读取和分析的代码审查员可以在 Sonnet 或 Haiku 上运行。把 Opus 留给真正需要复杂推理的任务。实践中发现 Haiku 处理大多数只读探索效果出奇地好。

### 代理 vs 技能

这是个常见困惑点：

| | 技能 | 代理 |
|--|------|------|
| 上下文 | 在你的主对话中运行（除非 `context: fork`） | 始终在独立上下文中运行 |
| 身份 | Claude 加特定指令 | 有自己系统提示的独立人格 |
| 工具 | 可通过 `allowed-tools` 限制 | 可通过 `tools` 限制 |
| 持久性 | 无持久状态 | 可以跨会话保持持久记忆 |
| 嵌套 | 可以生成代理 | 代理不能生成其他代理 |
| 使用时机 | 可重复工作流 | 受益于隔离的专业专长 |

经验法则：如果你需要 Claude **做一个特定任务**（运行代码审查、部署、修复 bug），使用技能。如果你需要 Claude **成为一个专家**（有自己视角的安全审计员、对代码库有持久记忆的代码审查员），受益于隔离和专注工具限制，使用代理。

## docs/ 文件夹：共享知识库

这是一个对任何非平凡 `.claude` 配置变得必不可少的模式。`.claude/docs/` 目录存放技能按需读取的参考文档。这不是官方记录的 Claude Code 目录，只是一个 Markdown 文件的文件夹。但这个模式很强大。

一个 .NET 项目的典型 docs 文件夹：

```
.claude/docs/
├── architecture.md       # 系统架构，模块边界
├── coding-standards.md   # C# 风格指南，命名约定
├── deployment.md         # 部署流程，环境，回滚
├── testing-strategy.md   # 测什么，如何测，覆盖目标
└── api-guidelines.md     # REST 约定，版本控制，分页
```

### 为什么不放在规则里

规则是自动加载的——这正是问题所在。如果我将一个 200 行的架构文档放入规则文件，它会在**每个**会话中消耗上下文，即使我只是在修复前端的一个 CSS bug，架构文档完全无关。

Docs 保持休眠状态，直到技能明确读取它们。`/code-review` 技能读取 `coding-standards.md` 以对照团队约定进行检查。`/deploy` 技能读取 `deployment.md` 以遵循部署清单。每个技能只加载它需要的文档。

### 提示词工程的 DRY 原则

这是真正的洞见。没有 docs 文件夹，每个需要编码标准的技能都会有自己的副本："使用文件范围命名空间，接口前缀 I，异步方法以 Async 结尾"。更新约定时，你必须在每个引用它的技能中更新。

有了 docs，编码标准只存在于一个地方。技能引用它：

```markdown
### 第 3 步：对照标准检查
阅读 `.claude/docs/coding-standards.md` 获取团队的质量基准。
```

一个数据源，被多个技能引用。让代码优秀的原则同样让 Claude 配置优秀。

### 放在哪里的决策表

| 放在… | 当… |
|-------|-----|
| `CLAUDE.md` | Claude 在每个会话都需要，每节很短（< 20 行） |
| `rules/` | Claude 在每个会话（或路径限定的会话）都需要，专注于一个关注点 |
| `docs/` | 只有特定技能需要，是详细的参考资料（> 50 行） |
| `skills/` | 它是带步骤的可复用工作流 |

## settings.json：权限和护栏

`.claude/` 内的 `settings.json` 文件控制 Claude 可以做什么、不可以做什么。这里定义工具权限、钩子配置和项目级设置。

### 权限模型

Claude Code 有三个权限级别：

| 级别 | 效果 | 配置在 |
|------|------|--------|
| 允许 | 不需要询问即可运行 | `permissions.allow` |
| 询问 | 请求你批准 | 未列出工具的默认行为 |
| 拒绝 | 完全阻止 | `permissions.deny` |

如果命令既不在 `allow` 也不在 `deny` 中，Claude 会在继续之前询问。这个中间地带是刻意的——你不需要提前预判所有可能的命令。

一个 .NET 项目的实用 `settings.json`：

```json
{
  "$schema": "https://json.schemastore.org/claude-code-settings.json",
  "permissions": {
    "allow": [
      "Bash(dotnet build *)",
      "Bash(dotnet test *)",
      "Bash(dotnet run *)",
      "Bash(dotnet format *)",
      "Bash(dotnet ef *)",
      "Bash(git status)",
      "Bash(git diff *)",
      "Bash(git log *)",
      "Bash(git branch *)",
      "Read",
      "Write",
      "Edit",
      "Glob",
      "Grep"
    ],
    "deny": [
      "Bash(rm -rf *)",
      "Bash(curl *)",
      "Bash(wget *)",
      "Bash(git push *)",
      "Bash(git reset --hard *)",
      "Read(./.env)",
      "Read(./.env.*)",
      "Read(**/*secret*)",
      "Read(**/appsettings.Production.json)"
    ]
  }
}
```

`$schema` 行会在 VS Code 或 Cursor 中启用自动补全和内联验证，始终包含它。

### 权限规则语法

模式匹配很灵活：

| 规则 | 匹配范围 |
|------|---------|
| `Bash` | 所有 Bash 命令 |
| `Bash(dotnet test *)` | 以 `dotnet test` 开头的命令 |
| `Bash(npm run *)` | 以 `npm run` 开头的命令 |
| `Read(./.env)` | 读取 .env 文件 |
| `WebFetch(domain:github.com)` | 对 github.com 的获取请求 |
| `Agent(Explore)` | 生成 Explore 子代理 |
| `Skill(deploy *)` | 特定技能调用 |

规则按此顺序评估：**先 deny，再 ask，再 allow**。这意味着 deny 规则始终获胜，即使有匹配的 allow 规则。

**实用建议**：从最小的 `settings.json` 开始，让 Claude 提示你。当你发现自己对同一命令反复点击"允许"时，将其添加到允许列表。这比提前猜测允许什么更安全。

### settings.local.json：个人覆盖

创建 `.claude/settings.local.json` 用于你不想提交到 git 的权限更改。Claude Code 在创建时会**自动配置 git 忽略**此文件。

使用场景：env vars 中的 API 密钥、特定域名的 `WebFetch` 权限、机器特定的路径。团队的 `settings.json` 保持干净，只有精要内容。

### 超出权限的其他配置

`settings.json` 的能力不止权限。一些有用的字段：

```json
{
  "env": {
    "ASPNETCORE_ENVIRONMENT": "Development"
  },
  "model": "claude-opus-4-6",
  "effortLevel": "high",
  "autoMemoryEnabled": true,
  "includeGitInstructions": true,
  "claudeMdExcludes": [
    "**/node_modules/**/CLAUDE.md"
  ]
}
```

| 字段 | 用途 |
|------|------|
| `env` | 为每个会话设置环境变量 |
| `model` | 覆盖默认模型 |
| `effortLevel` | 持久化努力级别（`low`、`medium`、`high`） |
| `autoMemoryEnabled` | 切换自动记忆（默认 `true`） |
| `claudeMdExcludes` | 在 monorepo 中跳过不相关的 CLAUDE.md 文件 |
| `statusLine` | 自定义状态栏配置 |
| `sandbox` | 文件系统和网络沙箱 |
| `worktree` | Worktree 配置（符号链接、稀疏路径） |
| `attribution` | 自定义 git commit/PR 归因 |

对于 monorepo，`claudeMdExcludes` 特别有用。你可以跳过其他团队目录中的 CLAUDE.md 文件。

## 全局 ~/.claude/ 文件夹

你不会经常直接与这个文件夹打交道，但了解它的内容有助于理解 Claude 如何在会话之间"记住"事情。

### 里面有什么

| 路径 | 用途 |
|------|------|
| `~/.claude/CLAUDE.md` | 所有项目的个人指令 |
| `~/.claude/settings.json` | 你的全局权限设置 |
| `~/.claude/rules/` | 在每个项目加载的个人规则 |
| `~/.claude/skills/` | 随处可用的个人技能 |
| `~/.claude/agents/` | 随处可用的个人代理 |
| `~/.claude/projects/<project>/memory/` | 每个项目的自动记忆 |

### 自动记忆系统

这是最少被理解的功能之一。Claude Code 在工作时自动向自身保存笔记：发现的命令、观察到的模式、架构洞见。这些跨会话持久存储在 `~/.claude/projects/<project>/memory/` 中。

`<project>` 目录来自你的 git repo，所以同一仓库的所有 worktrees 和子目录共享一个自动记忆目录。

该目录包含：
- `MEMORY.md`：索引文件（**前 200 行或 25KB 取先到者**，在每个会话开始加载；超出部分启动时不加载）
- 主题特定的记忆文件（如 `feedback_testing.md`、`user_preferences.md`）

用 `/memory` 命令浏览和管理记忆。你也可以告诉 Claude 明确记住事情："记住我更喜欢集成测试而不是 mock"，它就会保存一个记忆文件。

关键一点：自动记忆是**机器本地的**，不会跨机器同步，不与团队共享。这是 Claude 关于你项目的个人笔记本。用 `autoMemoryEnabled` 设置或 `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1` 环境变量来切换。

### 全局 CLAUDE.md

你的 `~/.claude/CLAUDE.md` 会加载到每个 Claude Code 会话中。适合放无论项目如何都适用的偏好：

```markdown
# 个人偏好

- 我偏好简洁的解释——跳过显而易见的东西
- 在代码引用中始终显示完整文件路径
- 建议重构时，解释权衡，而不只是好处
- 我在 Windows 上使用 WSL——在 Bash 中使用 Unix 命令
- 写 C# 时，偏好主构造函数和文件范围命名空间
```

`~/.claude/rules/` 中的用户级规则在项目规则之前加载，给予项目规则在冲突时更高的优先级。

## worktrees/ 文件夹

这个文件夹服务于 Claude Code 的 git worktree 集成。当你或代理使用 `isolation: worktree` 运行时，Claude 会在一个独立的 git worktree 中创建一个临时的仓库副本，让代理在不影响你主工作目录的情况下处理隔离的分支。

`worktrees/` 目录本身通常是空的。Claude 按需创建 worktrees，代理完成后（如果没有做任何更改）会清理它们。如果做了更改，worktree 会保留其分支，以便你审查和合并。

这对代理特别有用。在 worktree 中运行的代码审查员可以检出 PR 分支、运行测试、分析更改，而不会打扰你当前的工作。

## 我的建议：实践进阶路径

以下是我推荐的配置进阶方式。不要一次性构建所有内容，从小处着手，遇到真实阻力时再添加层次。

### 阶段 1：基础（第 1 天）

创建一个包含构建命令、架构概览和前 5 个约定的 `CLAUDE.md`。仅此一项就能让 Claude 的用处大幅提升。

```
your-project/
├── CLAUDE.md              # 30-50 行
└── .claude/
    └── settings.json      # 基本允许/拒绝规则
```

### 阶段 2：模块化规则（第 2-3 周）

当 CLAUDE.md 开始臃肿，拆分它。为代码库的不同部分添加路径限定规则。

```
your-project/
├── CLAUDE.md              # 精简到核心
└── .claude/
    ├── settings.json
    └── rules/
        ├── dotnet.md      # .NET 约定
        ├── ef-core.md     # EF Core 规则（路径限定）
        └── testing.md     # 测试标准（路径限定）
```

### 阶段 3：第一批技能（第 2 个月）

当你发现自己复制粘贴同一个提示超过两次时，将其打包成技能。从最经常重复的工作流开始：代码审查、issue 修复、部署。

```
your-project/
├── CLAUDE.md
└── .claude/
    ├── settings.json
    ├── rules/
    └── skills/
        ├── code-review/
        │   └── SKILL.md
        └── fix-issue/
            └── SKILL.md
```

### 阶段 4：完整系统（第 3 个月以后）

为专业任务添加代理，为共享参考资料添加 docs，为确定性自动化添加钩子。

```
your-project/
├── CLAUDE.md
└── .claude/
    ├── settings.json
    ├── rules/           # 3-5 个规则文件
    ├── skills/          # 5-15 个技能
    ├── agents/          # 2-3 个专业代理
    └── docs/            # 跨技能共享的参考文档
```

### 决策矩阵：创建哪些文件

| 你的情况 | 创建这个 |
|---------|---------|
| 刚开始使用 Claude Code | `CLAUDE.md` + `settings.json` |
| CLAUDE.md 超过 200 行 | 拆分到 `.claude/rules/` 文件 |
| 不同文件类型需要不同规则 | 在规则中添加 `paths:` frontmatter |
| 在重复复制同一个提示 | 创建技能 |
| 需要专家视角（安全审计、代码审查） | 创建代理 |
| 多个技能引用相同信息 | 移到 `.claude/docs/` |
| 对同一命令反复点击"允许" | 添加到 `settings.json` |
| 不想提交的个人偏好 | `settings.local.json` 或 `~/.claude/` |

每个阶段都建立在前一个基础上。每一层都应该解决你实际经历的阻力，而不是假设的阻力。

## 总结

`.claude` 文件夹是控制 Claude 在你项目中行为的核心，它有一个**项目级**实例（提交到 git，共享）和一个**全局**实例（`~/.claude/`，个人）。

**CLAUDE.md** 是杠杆最高的文件，保持在 200 行以内，专注于架构和约定，它在压缩后依然存在。

**Rules** 提供模块化的路径限定指令，当 CLAUDE.md 开始臃肿或不同文件类型需要不同规则时使用。

**Skills** 是替代并取代命令的可复用工作流，支持自动调用、工具限制、模型覆盖、参数和 shell 注入。

**Agents** 是在独立上下文窗口中运行的专业人格，有自己的工具和模型偏好，需要隔离和专家专长时使用。

**从 CLAUDE.md 和 settings.json 开始。** 指令增多时添加规则。发现自己重复提示时添加技能。需要专家视角时添加代理。每一层都应该解决真实的阻力，而不是假设的阻力。

## 参考

- [Anatomy of the .claude Folder - Every File Explained (2026) - codewithmukesh](https://codewithmukesh.com/blog/anatomy-of-the-claude-folder/)
- [Claude Code for Beginners](https://codewithmukesh.com/blog/claude-code-for-beginners/)
- [CLAUDE.md for .NET Developers](https://codewithmukesh.com/blog/claude-md-mastery-dotnet/)
- [Skills in Claude Code](https://codewithmukesh.com/blog/skills-claude-code/)
- [Claude Code Agent Teams for .NET](https://codewithmukesh.com/blog/claude-code-agent-teams-dotnet/)
- [Git Worktrees in Claude Code](https://codewithmukesh.com/blog/git-worktrees-claude-code/)
- [Hooks in Claude Code](https://codewithmukesh.com/blog/hooks-in-claude-code/)
