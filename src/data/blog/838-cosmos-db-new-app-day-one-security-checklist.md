---
pubDatetime: 2026-05-28T07:22:25+08:00
title: "Cosmos DB 新项目安全起步：8 步最小可行安全清单"
description: "刚创建 Cosmos DB 账户？别拿着密钥就走。这份 8 步 day-one 清单覆盖禁用密钥、托管标识、RBAC、诊断日志、网络限制、参数化查询和持续备份，帮你避免后期高成本返工。"
tags: ["Azure", "CosmosDB", "Security"]
slug: "cosmos-db-new-app-day-one-security-checklist"
ogImage: "../../assets/838/01-cover.png"
source: "https://devblogs.microsoft.com/cosmosdb/im-starting-a-new-cosmos-db-app-what-security-do-i-actually-need"
---

你刚创建了一个 Cosmos DB 账户。门户给了你两把密钥和一条连接字符串，能用，于是你继续往下走了。大多数开发者都这样做，然后后面出问题。

这篇文章面向正在启动新 Cosmos DB 应用的开发者，目标是：在写第一行业务逻辑之前，把安全底线配好——不需要企业级复杂度，但要避免后面推倒重来。

## 两分钟威胁模型

先搞清楚实际项目里到底在哪些地方出事。大多数安全问题不是高级攻击，而是简单的失误：

1. **连接字符串泄漏**——出现在 `.env` 文件、日志、截图或 PR 里。
2. **权限过大**——应用拿到的访问远超实际需要，出事时爆炸半径变大。
3. **端点对互联网敞开**——没有网络限制的 Cosmos DB 端点从任何地方都能访问。密钥一旦泄漏，攻击者和你的数据之间没有任何屏障。
4. **不校验客户端数据**——Cosmos DB NoSQL 接受任何 JSON。你的应用是用户输入和数据库之间唯一的屏障。未消毒的查询、不限大小的文档、字符串拼接注入，全是风险。
5. **出事后没有审计日志**——如果事前没开日志，事后无法确定什么被访问了、什么时候、被谁。
6. **开发环境的"临时"配置被带到了生产环境**——那个"上线前我再改"的配置原封不动地上了线。

## 先理解两个概念

### 密钥还是 Entra ID？

创建 Cosmos DB 账户时你会得到两对主/辅密钥。它们能直接用，很简单，几乎所有教程都用它们。但简单本身就是问题。

**密钥是不记名令牌（bearer token）。** 任何人拿到一把就能读、改、删你的数据。开了诊断日志后你能看到发生了什么、什么时候发生的、IP 和 User Agent 等细节，但共享密钥无法可靠地追溯到"谁用了这把密钥"。密钥一旦泄漏，唯一选择是重新生成并更新所有依赖它的系统——痛苦、容易出错、而且经常不彻底。

**Entra ID（原 Azure AD）是替代方案。** 应用获得一个身份（托管标识或服务主体），你给这个身份授予特定权限。访问可以限定范围、可以审计、可以在不轮换密钥的情况下撤销。

**建议：从第一天就用 Entra ID，即使在开发阶段。** 初始配置量很小，却能避免一整类风险。

### 应用到底需要什么权限？

Cosmos DB 有两种访问层面：

- **数据平面（Data Plane）**：读写数据——大多数应用只需要这个。
- **控制平面（Control Plane）**：修改账户本身的配置。

典型做法：

- **应用**只需要数据平面访问，用最小权限角色（reader vs contributor），范围限定到具体的数据库或容器。
- **开发者**需要本地开发的数据平面访问，最好也限定范围。
- **CI/CD 管线**只需要部署所需的权限——通常是数据平面写入，有时加控制平面来管理 schema/容器。

每个身份应该有自己的访问。避免在用户、环境、系统之间共享一条连接字符串。

## 8 步最小可行安全配置

### 第 1 步：禁用本地认证（密钥）

对，即使在开发阶段也禁用。这会从一开始就强制使用正确的认证方式。

```bash
az cosmosdb update \
  --name <your-account> \
  --resource-group <your-rg> \
  --disable-local-auth true
```

禁用后，密钥不再生效，所有访问必须通过 Entra ID 身份。这能防止任何人——包括你自己——意外使用密钥。

如果还没准备好完全禁用，至少做到：不把连接字符串存进源代码。用环境变量或 Azure Key Vault 这样的安全存储，并使用仓库密钥扫描工具。

### 第 2 步：为应用创建托管标识

如果应用跑在 Azure 上（App Service、Functions、Container Apps、AKS 等），给它分配一个系统分配的托管标识。这样不需要直接管理凭据，Azure 自动处理轮换。

```bash
az webapp identity assign \
  --name <your-app> \
  --resource-group <your-rg>
```

这会返回一个 `principalId`，下一步要用。

本地开发时，用你的开发者身份通过 `az login` 或用户分配的托管标识。Azure SDK 的 `DefaultAzureCredential` 类能自动处理两种场景。

### 第 3 步：分配正确的 RBAC 角色

只给应用需要的权限，使用数据平面角色：

- **Cosmos DB Built-in Data Reader**（`00000000-0000-0000-0000-000000000001`）：只读。
- **Cosmos DB Built-in Data Contributor**（`00000000-0000-0000-0000-000000000002`）：读写。

```bash
az cosmosdb sql role assignment create \
  --account-name <your-account> \
  --resource-group <your-rg> \
  --role-definition-id "00000000-0000-0000-0000-000000000002" \
  --principal-id <your-apps-principal-id> \
  --scope "/"
```

`--scope "/"` 授权整个账户。要更窄，用 `"/dbs/<database>"` 或 `"/dbs/<database>/colls/<container>"`。尽可能限定到应用实际需要的范围。

### 第 4 步：用身份连接，不用密钥

更新应用代码，用托管标识认证。C# 示例：

```csharp
using Azure.Identity;
using Microsoft.Azure.Cosmos;

var client = new CosmosClient(
    accountEndpoint: "https://<your-account>.documents.azure.com:443/",
    tokenCredential: new DefaultAzureCredential()
);
```

`DefaultAzureCredential` 到处都能用：本地开发走 `az login` 会话，Azure 上走托管标识，CI/CD 走服务主体或联合身份。同一套代码，最理想的情况下，零密钥。

### 第 5 步：开启诊断日志

在需要之前就开好。没有日志，事后调查基本是猜。启用诊断设置，把日志路由到 Log Analytics 工作区。

推荐启用的类别：

- **DataPlaneRequests**：每条数据请求（高流量时考虑采样）
- **QueryRuntimeStatistics**：查询级遥测
- **PartitionKeyStatistics**：对性能调优有用
- **ControlPlaneRequests**：配置变更，合规必备

### 第 6 步：限制网络访问

默认情况下，Cosmos DB 端点对公网可达。把访问限制到已知 IP 范围来降低暴露面。

```bash
az cosmosdb update \
  --name <your-account> \
  --resource-group <your-rg> \
  --ip-range-filter "<your-ip>,<ci-cd-egress-ip>"
```

这是在你迁移到 Private Endpoints 之前的基线防护。

### 第 7 步：始终使用参数化查询

Cosmos DB NoSQL 接受你发给它的任何 JSON，它不会帮你防范畸形查询或注入。唯一的防线是你的应用。

```csharp
// 不要这样——字符串拼接：
var query = $"SELECT * FROM c WHERE c.userId = '{userInput}'";

// 要这样——参数化查询：
var query = new QueryDefinition(
    "SELECT * FROM c WHERE c.userId = @userId")
    .WithParameter("@userId", userInput);
```

这个原则适用于所有 SDK 语言。任何来自用户输入、查询参数或外部系统的值，都必须走参数化，不拼字符串。

### 第 8 步：开启持续备份（按时间点还原）

数据丢失往往是失误造成的，不是攻击者。持续备份提供可靠的恢复选项。

启用持续备份（7 天或 30 天），支持按时间点还原。如果可以，在创建账户时就启用。从周期性备份切换到持续备份是单向操作。

```bash
az cosmosdb update \
  --name <your-account> \
  --resource-group <your-rg> \
  --backup-policy-type Continuous \
  --continuous-tier Continuous7Days
```

## Day one 之后再做的事

这篇文章只管第一天。以下这些很重要，但不需要第一天就做：

- **VNet 和 Private Endpoints**：第 6 步的 IP 白名单是起点，Private Endpoints 是下一步。
- **客户托管密钥（CMK）**：合规场景需要，但增加运维开销。大多数应用初期不需要。
- **Microsoft Defender for Cosmos DB**：强烈推荐，但可以等到有值得保护的数据后再开。

目标是把地基打对，这样后面不需要推倒重来。

## 最难回头的一件事

从密钥迁移到托管标识意味着触碰每个部署、每个环境、可能还有每个 SDK 调用。这是一个多天的项目，有真实的破坏性变更风险。

从第一天就用 `DefaultAzureCredential` 可以完全避免这个问题。

## 快速参考清单

在提交第一行真正的业务代码之前，确认这些：

- [ ] 本地认证已禁用；源代码里没有密钥或连接字符串
- [ ] 计算资源已分配托管标识；RBAC 角色已限定范围并分配；应用使用 `DefaultAzureCredential`
- [ ] 每个开发者用自己的 Entra ID 身份在开发账户上认证
- [ ] 诊断日志已启用，路由到 Log Analytics Workspace
- [ ] 公网访问已限制到已知 IP
- [ ] 所有查询使用参数化值，不拼字符串
- [ ] 持续备份已启用（7 天或 30 天）

如果你关注 AI 助手、开发工具和软件工程实践，可以关注 Aide Hub。这里会继续分享能落地的工具教程、技术观察和项目经验。

## 参考

- [I'm Starting a New Cosmos DB App. What Security Do I Actually Need? - Azure Cosmos DB Blog](https://devblogs.microsoft.com/cosmosdb/im-starting-a-new-cosmos-db-app-what-security-do-i-actually-need)
- [Secure your Azure Cosmos DB for NoSQL account](https://learn.microsoft.com/azure/cosmos-db/security)
- [Connect to Azure Cosmos DB using RBAC and Microsoft Entra ID](https://learn.microsoft.com/azure/cosmos-db/nosql/how-to-connect-role-based-access-control)
- [DefaultAzureCredential Class](https://learn.microsoft.com/dotnet/api/azure.identity.defaultazurecredential)
- [Parameterized queries in Cosmos DB](https://learn.microsoft.com/azure/cosmos-db/nosql/query/parameterized-queries)
- [Continuous backup with point-in-time restore](https://learn.microsoft.com/azure/cosmos-db/continuous-backup-restore-introduction)
