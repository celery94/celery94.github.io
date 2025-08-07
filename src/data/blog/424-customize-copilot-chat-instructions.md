---
pubDatetime: 2025-08-07
tags: ["GitHub Copilot", "VS Code", "AI定制", "Prompt Engineering"]
slug: customize-copilot-chat-instructions
source: https://example.com/your-url
title: 深入解析：在 VS Code 中定制 GitHub Copilot Chat 响应
description: 探索如何通过自定义指令和可复用 Prompt 文件，在 VS Code 中让 Copilot Chat 更贴合你的开发规范与项目需求，打造高效的 AI 辅助编程环境。
---

# 深入解析：在 VS Code 中定制 GitHub Copilot Chat 响应

随着 AI 编程助手在开发流程中的广泛应用，越来越多的团队和开发者希望 Copilot Chat 不只是“智能”，更能**充分匹配自身的编码规范、技术栈和项目需求**。本文将以专业角度，系统梳理如何通过自定义指令（custom instructions）和 prompt 文件，在 VS Code 中最大化发挥 GitHub Copilot Chat 的辅助价值。

## AI 响应定制：三大能力与场景解读

**GitHub Copilot Chat** 在 VS Code 支持三种主要方式来定制 AI 响应：

1. **自定义指令（Custom Instructions）**：为代码生成、评审、提交信息等常见任务设定规范或约束。指令描述“怎么做”，如应优先用何种编程范式、如何命名变量、需关注哪些安全检查等。
2. **Prompt 文件（Prompt Files）**：定义可复用的任务模板，比如自动生成组件、执行代码审查等。“指明做什么”，同时可包含部分“怎么做”的说明，并可关联指令文件。
3. **自定义聊天模式（Chat Modes）**：限定聊天环境可访问的工具范围和操作权限，比如只允许 AI 生成实现计划、只处理前端代码等。

这种分层定制不仅提升了开发效率，更有助于在团队协作、代码审查、安全合规等场景下规范化 AI 行为。

### 应用举例

- 设定统一代码风格、技术栈优先级，避免“野生代码”。
- 针对不同项目或模块（如前端/后端），使用专属指令文件。
- 快速复用常见任务流程，如新建组件、生成测试用例或安全审查清单。

## 自定义指令：规范 AI 响应，落实团队标准

自定义指令可通过多种方式落地于 VS Code 开发环境中：

### 主要类型与作用场景

| 指令类型                          | 说明                                                                                     |
| --------------------------------- | ---------------------------------------------------------------------------------------- |
| `.github/copilot-instructions.md` | 单一文件全局适用，描述项目通用的代码生成规范、技术选型和开发要求。跨编辑器支持。         |
| `.instructions.md`                | 可多文件分布，按 glob 模式对不同文件或目录自动应用，便于细粒度控制和任务专属指令管理。   |
| VS Code 设置                      | 直接在用户或工作区设置中填写，适用于代码生成、评审、测试、提交等多种场景，支持引用文件。 |

#### 实战示例：如何编写高质量指令

**例1：通用项目代码规范**

```markdown
---
applyTo: "**"
---

# 项目代码规范

## 命名约定

- 组件、接口、类型别名使用 PascalCase
- 变量、函数、方法使用 camelCase
- 私有成员前缀加下划线 \_
- 常量使用 ALL_CAPS

## 错误处理

- 异步操作需包裹 try/catch
- React 组件实现错误边界
- 错误日志需包含上下文信息
```

**例2：TypeScript + React 项目专属规范**

```markdown
---
applyTo: "**/*.ts,**/*.tsx"
---

# TypeScript & React 规范

继承[通用规范](./general-coding.instructions.md)。

## TypeScript

- 所有新代码均使用 TypeScript
- 倡导函数式编程
- 数据结构与类型定义首选 interface
- 推崇不可变数据（const/readonly）
- 善用 ?. 和 ?? 操作符

## React

- 全部采用函数组件与 hooks
- 遵循 React hooks 规则（禁止条件钩子）
- 有 children 的组件用 React.FC
- 组件设计单一职责
- 样式采用 CSS modules
```

#### 指令文件结构与自动应用

每个指令文件建议包含：

- YAML 格式头部（Front Matter），如 `applyTo` 控制自动应用范围
- 详细 Markdown 规范内容
- 可引用其他指令文件，便于分层管理和复用

![配置 Chat 菜单截图](https://code.visualstudio.com/assets/docs/copilot/customization/configure-chat-instructions.png)

> VS Code 支持通过界面或命令面板快捷创建和编辑指令文件，支持本地和用户配置同步。

### 设置与管理

指令可集中管理于工作区 `.github/instructions` 文件夹或用户配置文件夹，通过 Settings Sync 可跨设备同步。支持通过设置自动启用或禁用指定文件夹下的指令文件。

```json
"chat.instructionsFilesLocations": {
    "src/frontend/instructions": true,
    "src/backend/instructions": false
}
```

## Prompt 文件：高效复用、任务驱动的 AI 提示工程

Prompt 文件是为常见任务定制的可复用对话模板。其最大优势在于支持结构化元数据、引用自定义指令和变量插值，使 AI 行为更可控、响应更精确。

### Prompt 文件结构

- 头部元数据（mode/model/tools/description）
- 主体为 Markdown 格式的详细任务描述
- 支持引用变量、其他 prompt/指令文件，实现模块化和上下文扩展

**生成 React 表单组件示例：**

```markdown
---
mode: "agent"
model: GPT-4o
tools: ["githubRepo", "codebase"]
description: "Generate a new React form component"
---

基于 #githubRepo contoso/react-templates 的模板生成新 React 表单组件。

如未指定，需先询问表单名称和字段。

要求：

- 组件基于 [design-system/Form.md](../docs/design-system/Form.md)
- 表单状态管理用 react-hook-form
- 类型定义严格使用 TypeScript
- 优先采用非受控组件
- 使用 yup 进行表单校验，校验逻辑独立文件，校验规则友好、类型安全
```

### Prompt 文件的创建与调用

- 可在 `.github/prompts` 文件夹下新建 `.prompt.md` 文件
- 可通过菜单、命令面板或直接输入 `/prompt-name` 快速调用
- 支持变量传递（如 `/create-react-form: formName=MyForm`）

> Prompt 文件及指令文件均可通过 VS Code 设置同步跨设备管理，便于团队协作与标准统一。

## 一体化管理与组织级落地

通过 VS Code 配置项，可灵活集中管理 prompt 文件和指令文件在工作区的生效范围，支持企业级设备统一配置。

```json
"chat.promptFilesLocations": {
    ".github/prompts": false,
    "setup/**/prompts": true
}
```

## 实用技巧与最佳实践

- 指令力求简洁明确，复杂规范建议拆分多文件按需组合。
- 尽量避免指令间冲突，必要时明确适用范围（如 `applyTo`）。
- 鼓励在团队内同步与复用指令和 prompt 文件，实现知识积累与协作提效。
- 不建议在指令中引用外部链接，所有规则应明确写入指令内容。
- 通过 prompt 文件结合变量、引用机制，实现个性化、动态化的 AI 交互。

## 结语

AI 已经成为现代开发流程的得力助手，但“聪明”只是基础——真正高效的 Copilot，需要**定制化、工程化的指令与 prompt 体系**。通过本文介绍的方法，开发者和团队可以全面掌控 Copilot Chat 的行为与产出，让 AI 更懂你、更懂业务、更懂协作。

---

如需进一步探索，可参考：

- [创建自定义聊天模式](https://docs.github.com/en/copilot/chat/chat-modes)
- [VS Code Copilot Chat 快速入门](https://docs.github.com/en/copilot/chat/copilot-chat)
- [VS Code 聊天代理与工具配置](https://docs.github.com/en/copilot/chat/chat-agent-mode#agent-mode-tools)
