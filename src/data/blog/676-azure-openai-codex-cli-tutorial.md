---
pubDatetime: 2026-03-26T16:00:31+08:00
title: "在 Azure 上运行 OpenAI Codex CLI 编程智能体"
description: "Codex CLI 是驱动 ChatGPT Codex 的同款编程智能体，本文手把手介绍如何将其接入 Azure AI Foundry，在自己的合规边界内完成代码生成、重构、写测试和自动开 PR 等任务。"
tags: ["AI", "Azure", "OpenAI", "Codex", "CLI"]
slug: "azure-openai-codex-cli-tutorial"
ogImage: "../../assets/676/01-cover.png"
source: "https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/codex?tabs=npm"
---

![在 Azure 上运行 OpenAI Codex CLI 编程智能体](../../assets/676/01-cover.png)

OpenAI 的 [Codex CLI](https://github.com/openai/codex) 与 ChatGPT 里内置的 Codex 是同一个编程智能体。它不只是"和代码对话"——它是一个异步的代理，能从终端、VS Code 或 GitHub Actions runner 触发，自动打开 PR、重构文件、编写测试。

把它接到 Azure，好处是数据不会离开你的合规边界，同时拿到企业级安全、私有网络、RBAC 权限控制和可预测的成本管理。本文是完整的上手教程，从部署模型到配置 CI 流水线，一步一步来。

## 前置条件

开始之前确认以下几项都准备好：

- Azure 订阅（没有可以[免费创建](https://azure.microsoft.com/pricing/purchase-options/azure-account?cid=msft_learn)）
- [Microsoft Foundry](https://ai.azure.com/) 项目的 Contributor 权限
- Node.js + npm（用来安装 Codex CLI）；macOS 也可以用 Homebrew
- Windows 用户：需要先安装并配置好 WSL2

系统和硬件要求：

| 要求 | 说明 |
|------|------|
| 操作系统 | macOS 12+、Ubuntu 20.04+/Debian 10+，或通过 WSL2 的 Windows 11 |
| Git（可选，推荐） | 2.23+ 以使用内置 PR 辅助功能 |
| 内存 | 最低 4 GB，推荐 8 GB |

## 在 Foundry 部署模型

1. 打开 [Foundry](https://ai.azure.com)，创建一个新项目。
2. 进入[模型目录](https://ai.azure.com/catalog/)，选择一个推理模型部署。支持的模型包括 `gpt-5.3-codex`、`gpt-5.2-codex`、`gpt-5.1-codex-max`、`gpt-5.1-codex`、`gpt-5.1-codex-mini`、`gpt-5-codex`、`gpt-5`、`gpt-5-mini`、`gpt-5-nano` 等。
3. 在模型目录页点击 **Use this model**，或在 Azure OpenAI 的 **Deployments** 面板里选 **deploy model**。
4. 部署完成后，复制 endpoint **URL** 和 **API Key**，后面配置时要用到。

## 安装 Codex CLI

在终端里执行以下命令安装 Codex CLI：

```bash
npm install -g @openai/codex
codex --version  # 验证安装成功
```

## 配置 config.toml

Codex CLI 用 `~/.codex/config.toml` 文件读取 Azure 的连接信息。

**第一步：创建或编辑配置文件**

```bash
cd ~/.codex
nano config.toml
```

**第二步：写入以下内容**

```toml
model = "gpt-5-codex"  # 替换为你实际的 Azure 模型部署名称
model_provider = "azure"
model_reasoning_effort = "medium"

[model_providers.azure]
name = "Azure OpenAI"
base_url = "https://YOUR_RESOURCE_NAME.openai.azure.com/openai/v1"
env_key = "AZURE_OPENAI_API_KEY"
wire_api = "responses"
```

几个注意点：

- `base_url` 里的 `YOUR_RESOURCE_NAME` 换成你的 Azure OpenAI 资源名称
- 使用 v1 Responses API，路径里必须包含 `/v1`，不需要再传 `api-version`
- `env_key` 必须指向一个**环境变量名**，不能直接写 API Key 字符串

**第三步：设置环境变量**

```bash
# Linux、macOS 或 WSL
export AZURE_OPENAI_API_KEY="<你的 API Key>"
```

**第四步：验证配置**

| 命令 | 作用 |
|------|------|
| `codex` | 启动交互式终端 UI（TUI） |
| `codex "初始提示词"` | 带初始提示词启动 TUI |
| `codex exec "初始提示词"` | 以非交互的自动化模式启动 |

运行 `codex` 能进入 TUI 说明配置正常。

## 在 VS Code 中使用 Codex

Codex 也有 VS Code 扩展，安装后就能直接在编辑器里调用。

1. 安装 [OpenAI Codex 扩展](https://marketplace.visualstudio.com/items?itemName=openai.chatgpt)，它会复用已有的 `config.toml` 配置。

2. 确保终端里设置了环境变量：

   ```bash
   export OPENAI_API_KEY="<你的 Azure API Key>"
   ```

   > 如果你用的是 WSL，Windows 宿主机上也需要设置同名环境变量，否则扩展可能读不到。

3. **从同一个终端会话启动 VS Code**：

   ```bash
   code .
   ```

   不要从应用启动器打开，否则环境变量不会被扩展继承。

### 三种审批模式

| 模式 | 说明 |
|------|------|
| Chat | 只对话、做规划，不执行操作 |
| Agent | 可读写文件、在工作目录内执行命令，工作目录外或访问网络时需手动确认 |
| Agent（完全访问） | Agent 模式的所有能力，且不需要逐步确认。仅在了解风险并有沙箱保护时使用 |

## 用 AGENTS.md 给 Codex 加持久指令

Codex 会按照以下顺序读取 `AGENTS.md` 文件并合并内容，用于理解你的偏好和项目背景：

- `~/.codex/AGENTS.md`：个人全局指令
- 仓库根目录的 `AGENTS.md`：项目共享说明
- 当前工作目录的 `AGENTS.md`：子目录或功能模块专用说明

举个例子，如果你的项目用到了 Azure AI Agents SDK，可以在项目根目录创建一个 `AGENTS.md`，里面写清楚如何初始化客户端、如何创建 Agent、Tools 的用法等，Codex 生成代码时就会遵循这些约定。

## 上手体验

配置完成后，可以用这条命令试试效果：

```bash
codex "write a python script to create an Azure AI Agent with file search capabilities"
```

其他可以测试的场景：

```bash
# 为某个工具函数生成单元测试
codex "generate a unit test for src/utils/date.ts"

# 把某个 Agent 重构成使用 Code Interpreter 工具
codex "refactor this agent to use the Code Interpreter tool instead"
```

## 接入 GitHub Actions

Codex 可以作为 CI 流水线的一个 Job 运行。把 API Key 存到仓库的 Secrets 里（名称为 `AZURE_OPENAI_KEY`），然后在 workflow 文件里加一个类似这样的 Job：

```yaml
jobs:
  update_changelog:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Update changelog via Codex
        run: |
          npm install -g @openai/codex
          export AZURE_OPENAI_API_KEY="${{ secrets.AZURE_OPENAI_KEY }}"
          codex -p azure exec --full-auto "update CHANGELOG for next release"
```

这样每次发版前就能自动更新 CHANGELOG，不需要手动维护。

## 常见问题排查

| 症状 | 解决方法 |
|------|----------|
| `401 Unauthorized` 或 `403 Forbidden` | 确认 `AZURE_OPENAI_API_KEY` 已正确导出；`env_key` 必须是环境变量名，不能是 Key 字符串本身 |
| `ENOTFOUND`、DNS 错误或 `404 Not Found` | 检查 `config.toml` 中的 `base_url`：资源名称是否正确、域名是否正确、路径是否包含 `/v1` |
| CLI 忽略 Azure 配置 | 确认 `model_provider = "azure"` 已设置、`[model_providers.azure]` 节存在、`env_key` 的环境变量名与实际一致 |
| Entra ID 支持 | 当前 Codex 不支持 Entra ID 认证 |
| WSL + VS Code 扩展报 `401` | 扩展可能从 Windows 宿主机读取环境变量，在 Windows 侧也设置一次，然后重新从 WSL 终端执行 `code .` 启动 VS Code |

## 参考

- [原文：How to use OpenAI Codex with Azure AI Foundry](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/codex?tabs=npm)
- [Codex CLI GitHub 仓库](https://github.com/openai/codex)
- [OpenAI Codex VS Code 扩展](https://marketplace.visualstudio.com/items?itemName=openai.chatgpt)
- [Azure AI Foundry](https://ai.azure.com)
