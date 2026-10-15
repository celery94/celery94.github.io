---
pubDatetime: 2026-10-15T09:28:00+08:00
title: "Azure MCP Server 3.0 升级清单与只读上手"
description: "Azure MCP Server 3.0 稳定版把 Backup、Resilience、SRE Agent 和 Terraform 交给 agent。本文把破坏性变更整理成升级检查表，并给出只读模式的最小工作流。"
tags: ["Azure", "MCP", "AI Agent", "DevTools"]
slug: "azure-mcp-server-3-0-upgrade-checklist"
ogImage: "../../assets/1096/01-cover.jpg"
source: "https://devblogs.microsoft.com/azure-sdk/azure-mcp-server-3-0-stable-release/"
---

Azure MCP Server 3.0 的稳定版在 2026 年 10 月 12 日发布，npm 上 `@azure/mcp` 的 `latest` 标签也已经指向 3.0.0。这一版把 Backup、Resilience、SRE Agent 和 Terraform 这些真正的运维动作交给了 agent。

对已经在用 2.0 或 3.0 preview 的团队来说，新能力清单不是重点。官方博客把迁移信息压缩在「Plan your upgrade」一节里，而 [3.0.0 的 changelog](https://github.com/microsoft/mcp/blob/release/azure/3.x/servers/Azure.Mcp.Server/CHANGELOG.md) 中「Breaking Changes」的条目已经多到需要分类阅读。**升级成本几乎全部来自工具契约、响应结构、配置键名和 MCP 协议这四处，而不是新功能本身。**

## 3.0 把哪些 Azure 操作交给了 agent

新增能力大致落在三个方向，比数量更值得注意的是重心变化。

**第一类是运维上下文。** 以前 agent 能列出订阅里的资源，但回答不了「这个工作负载受保护了吗」。现在补齐了三个方向：

- `azurebackup`：vault、policy、可保护项与容器、受保护项、job、恢复点，以及软删除、不可变性、Multi-User Authorization 的 Resource Guard，另外覆盖客户管理密钥加密和跨区域还原。要注意 private endpoint 命令组只面向 Recovery Services vault，不包含 Data Protection vault。
- `resiliency`：目标、使用计划与登记、恢复计划与作业、就绪检查、故障转移验证和演练生命周期。
- `sreagent`：55 条命令，覆盖 agents、skills、connectors、hooks、threads、scheduled tasks、incidents 和 workflows。

**第二类是把建议变成变更。** `azureterraform` 提供 AzureRM 与 AzAPI provider 文档、Azure Verified Modules（含 pattern module）的检索，并串起 `aztfexport` 导出与 `conftest` 校验。`advisor` 增加建议摘要、元数据、生命周期与退役过滤、修复指引；`optimization` 按影响和预估年节省给成本建议排序，比较 VM 与 VM Scale Set 方案，并解释利用率预测。

能落地的组合是这样一条链：团队在评估 VM 扩容，先用 Advisor 的建议和利用率预测确认方向，再让 agent 生成对应的基础设施即代码改动，最后走既有的审批流程。原文特别说明 Advisor 的 apply 类工具返回的是准备 IaC 改动的规则，而不是直接改动线上资源——这个边界值得记住。

**第三类是既有命名空间的扩面。** `monitor` 支持跨资源查询指标，并对 Basic 与 Auxiliary 日志表做有界搜索；`cosmos` 能推断容器 schema、读取单条或近期修改的项，并支持全文与向量搜索；`iothub` 与 `iotoperations` 覆盖设备标识、孪生、统计和实例发现；`insights` 把 Azure Resource Graph 聚合与 MCP sampling 引进工作流；`compute`、`appservice`、`managedlustre` 分别补上 VM 电源状态与创建输入校验、Web 应用状态切换、Lustre 文件系统扩容。

有一条限制要先讲清楚：服务器进入稳定版，不改变底层 Azure 服务的可用性或前提条件。SRE Agent 工具走的是 `Microsoft.App/SREAgentPreview` 资源提供程序，它自己仍然带着预览属性。

## 升级前必须处理的五类变更

下面这些改动来自 changelog 的 3.0.0 段落，顺序按「会不会立刻报错」排列。前两类会让调用直接失败，后三类更隐蔽。

### 一、参数被删，未知参数不再被忽略

几乎所有命名空间都移除了未使用的参数，包括 `subscription`、`resource-group`、`tenant`、`auth-method`、`user` 和 `sender-name`。自定义重试策略参数也全部删除，改用 Azure SDK 的重试默认值；`sql server delete` 不再接受只用于确认的 `--force`。

更重要的是最后一条：**传未知参数不再被静默忽略，而是明确拒绝。** 如果你把参数拼在 saved prompt 或脚本里手工调用工具，这一步会立刻暴露出来。

### 二、工具名与命名空间重命名

- `azmcp resilience` 改为 `azmcp resiliency`，MCP 工具线上名前缀从 `resilience_*` 改为 `resiliency_*`。直接调用工具、配 allowlist、保存工具名或做命名空间过滤的地方都要同步改。
- `monitor healthmodels entity get` 拆成 `monitor healthmodels list` 和 `monitor healthmodels get`。
- `--tool` 过滤现在严格按暴露的工具名匹配（忽略大小写），名称是子串的工具不会再被顺带暴露出来。

### 三、响应结构变了，解析会静默失败

这是最容易在上线后才被发现的一类：

- Advisor 的建议列表改用 ARM 风格的 `properties`。
- Monitor 日志查询和 Azure AI Search 索引查询的结果放进 `results` 包装。
- 若干命名负载改名：最佳实践用 `{ bestPractices }`，SQL server 列表用 `{ servers }`，Well-Architected Framework 指引用 `{ guidance }`。
- `functions language list` 和 `functions project get` 现在直接返回对象。

客户端解析器和测试 fixture 都要跟着更新。类型没报错但字段读空，通常就出在这里。

### 四、配置键位与代码命名空间搬家

服务器设置从 `appsettings.json` 的根级移到 `MicrosoftMcp` 下。共享代码命名空间从 `Azure.Mcp.Core.*` 迁到 `Microsoft.Mcp.Core.*`；因为日志类别由类型的命名空间推导，任何指向旧类别的日志配置都必须改，包括 `Logging:LogLevel:Azure.Mcp.Core` 这类条目，以及环境变量里的日志过滤器。不改的话不会报错，只是你的日志级别设置悄悄失效。

### 五、HTTP 客户端的协议与请求头

3.0 迁移到 MCP 2026-07-28 无状态协议。使用该协议的客户端必须在每个 POST 请求上带 `Mcp-Method` 和 `Mcp-Name` 路由头。仍使用 2025-11-25 协议的客户端由服务端自动协商，不受影响——所以这一条只对自行实现 HTTP 传输的团队成立。

## 数据库查询工具失去了动词过滤

MySQL 与 PostgreSQL 的查询工具现在被标记为破坏性、非幂等、非只读，SQL 动词过滤也被移除。在 consolidated 模式下，它们从 `get_azure_databases_details` 迁移到 `execute_azure_database_query`。

**动词过滤消失意味着工具层面不再拦截 `DROP` 或 `DELETE`，语句能做什么完全取决于登录身份的数据库权限。** 这是权限模型上的一次明确交棒：原来那层基于关键词的软保护没有了，需要把 least-privilege 的角色配好，最好再叠加 agent 侧的人工确认。

## 安全默认值只对新资源生效

通过服务器创建的新资源，默认值明显变严了：

- 新的 Storage account 关闭 Shared Key 认证；HTTPS、TLS 1.2 和关闭匿名 blob 访问保持不变。
- 新的 Event Hubs 命名空间关闭本地认证。
- 新的 Recovery Services vault 关闭公共网络访问。
- 新的 NFS 文件共享使用 RootSquash 和传输加密。

关键在于作用范围：**这些默认值不会在升级时改写已有资源，更新时省略安全选项也会保留原有的文件共享和 Event Hubs 设置。** 也就是说升级完成后，存量资源还是旧配置，想统一得显式处理，而且 Recovery Services vault 的公共网络访问开关也不适用于 Data Protection vault。

另外三点安全相关的变化值得注意：基于 `Microsoft.Security.AntiSSRF` 的端点校验扩展到更多数据面与控制面的云端点和命名空间端点，并支持命名空间级校验覆盖；校验失败的遥测不再记录选项值；Azure Communication Services 的邮件与短信发送工具在只读模式下被排除。

## 给 agent 开发者的接口变化

除了破坏性变更，3.0 还改了几处会影响工具选择质量的细节，多数需要显式开启。

**结构化输出是可选的。** 用 `--structured-output-mode duplicated` 或 `--structured-output-mode compact`，工具才会声明 `outputSchema` 并返回 `structuredContent`。`duplicated` 保留完整的原始 `content`，`compact` 返回精简版 `content`，两者都给出完整的结构化结果。不加这个参数时响应仍是 content-only。只有在客户端确实支持这两个字段时才开启。在 all-tools 模式下，已开启的命令会提供按命令划分的 schema，App Configuration 是首个实现。

**`--learn` 让命令行可以先看再动。** 用它可以在不执行任何 Azure 操作的前提下逐层发现命令和参数，`azmcp storage --learn`、`azmcp storage account list --learn` 都成立。对于要生成调用的 agent，这比读完整个 command reference 更省上下文。

**`operationPlane` 元数据**在 `azmcp tools list` 输出里标出每个工具是 `data`、`control`、`both` 还是 `notApplicable`，判断依据是工具为产出结果而调用的 API，仅为定位目标而发的 Resource Manager 调用不算。要做分层授权时这个字段有直接用处。

其余几项：新增 `--disable-proxy-tools` 关闭代理工具；支持通过 `AzurePipelinesCredential` 使用 Azure Pipelines 工作负载身份联合的服务连接；输入 schema 改用更贴合规范的 `System.Text.Json` 定义，值类型和数组元素类型都已修正；资源不存在时返回 404 而不是 500 或 400，命令输入非法时返回 400 而不是 500；日志与异常统一写到 stderr，stdout 留给 JSON 和 JSON-RPC；npm wrapper 在安装缺失的平台包时不再修改调用方的 `package.json` 和 lock 文件。

关于性能，这个数字在转述里很容易被放大：**约 39% 的启动提升只针对定向的 CLI 命令调用，不是服务器整体启动时间或吞吐量。**

## 跑通一条只读工作流

下面的流程用 VS Code 演示，目的是在不暴露写操作的前提下熟悉 3.0。

**前置条件**：Node.js LTS（提供 `npm` 和 `npx`）、Azure CLI、一个 Azure 订阅、一个兼容 MCP 的客户端。第一次试跑请用开发订阅，并选择只有该工作流所需权限的身份。

**第一步，登录并选定订阅。**

```bash
az login
az account set --subscription "<subscription-id>"
```

**第二步，把服务器加进 `.vscode/mcp.json`**，与已有的 `servers` 条目合并。这里固定版本号而不是用 `@latest`，避免升级时机不受控：

```json
{
  "servers": {
    "azure-mcp": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@azure/mcp@3.0.0", "server", "start", "--read-only"]
    }
  }
}
```

注意配置键的差异：VS Code 的 `.vscode/mcp.json` 用 `servers`，而官方 README 里给其他客户端的通用示例用 `mcpServers`。抄错会表现为客户端完全看不到这个服务器。

**第三步，从客户端启动服务器并查看工具列表。** `--read-only` 会过滤掉所有写操作工具，列表里应该找不到资源创建类的工具。这一步同时也是对协议兼容性的检查：如果客户端连不上，先确认它使用的 MCP 协议版本。

**第四步，用一句只读提示验证链路。**

```text
List the Azure Advisor recommendations for my subscription and explain one cost recommendation. Don't apply changes.
```

预期结果是 agent 返回你订阅里真实存在的 Advisor 建议，并解释其中一条成本建议的构成。如果返回空列表或权限错误，先查 `az account show` 确认当前订阅，再查身份是否具备该订阅的 Reader 权限。

第一次试跑请把范围限制在查看。启用写工具之前，先把目标资源和团队的审批流程过一遍——**自然语言提示词不能替代访问控制。**

如果工具列表正常但调用失败，优先检查三件事：saved prompt 里是否还残留 `subscription`、`resource-group` 这类已被移除的参数；客户端的解析器是否还在读旧字段名；日志配置里的类别是否已经改成 `Microsoft.Mcp.Core`。

## 谁该现在升，谁该再等等

**现在适合升级的情况**：你已经在用 2.0 或某个 3.0 preview，并且升级窗口可以容纳一次客户端联调；或者你正需要 Backup、Resilience、Terraform、Advisor 这几块能力，愿意接受把它们接进 agent 工作流。

**建议再等的情况**：你依赖 MySQL 或 PostgreSQL 查询工具跑自动化，但还没把数据库权限收到 least-privilege；或者你有自研的 HTTP 客户端和一套靠字段名硬编码的解析逻辑，短期内没有测试资源覆盖响应结构变更。

无论哪种情况，升级顺序都建议是：先读完整 changelog，再改本地配置和 saved prompt，然后在只读模式下联调客户端，最后才动共享部署。原文给的也是这个顺序。

如果这篇对你有用，Aide Hub 之后会继续写 AI 助手、开发工具和软件工程实践相关的整理。

## 参考

- [Azure MCP Server 3.0 stable release: More tools. More possibilities](https://devblogs.microsoft.com/azure-sdk/azure-mcp-server-3-0-stable-release/)：原文。
- [Azure MCP Server 3.x CHANGELOG](https://github.com/microsoft/mcp/blob/release/azure/3.x/servers/Azure.Mcp.Server/CHANGELOG.md)：3.0.0 的完整变更与破坏性变更清单。
- [Command Reference](https://github.com/microsoft/mcp/blob/release/azure/3.x/servers/Azure.Mcp.Server/docs/azmcp-commands.md)：`--learn`、`--structured-output-mode`、`--disable-proxy-tools` 以及各命名空间参数与默认值的权威说明。
- [Azure MCP Server README](https://github.com/microsoft/mcp/blob/release/azure/3.x/servers/Azure.Mcp.Server/README.md)：各客户端的 `mcp.json` 配置示例。
- [Authentication](https://github.com/microsoft/mcp/blob/release/azure/3.x/docs/Authentication.md)：认证方式与身份选择。
- [@azure/mcp on npm](https://www.npmjs.com/package/@azure/mcp)：版本与 dist-tag。
- [Azure MCP Server 文档](https://learn.microsoft.com/azure/developer/azure-mcp-server/)：安装与设置指引。
