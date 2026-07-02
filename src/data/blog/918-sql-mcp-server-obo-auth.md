---
pubDatetime: 2026-07-02T07:55:27+08:00
title: "SQL MCP Server OBO 认证：让 AI Agent 操作数据库时可追溯用户身份"
description: "当 AI Agent 通过 MCP Server 操作 Azure SQL 数据库时，审计日志记录的是谁？用户名密码和托管身份两种方式只能记录服务账号，无法追溯到真实用户。本文讲解 SQL MCP Server 的 On-Behalf-Of（OBO）认证机制，利用 Microsoft Entra ID 实现用户 token 从 Agent 到数据库的完整透传，让审计日志回答「谁做了这个操作」。"
tags: ["SQL", "MCP", "Azure", "OBO", "Agent"]
slug: "sql-mcp-server-obo-auth"
ogImage: "../../assets/918/01-cover.png"
source: "https://devblogs.microsoft.com/azure-sql/sql-mcp-server-obo-auth"
---

当 AI Agent 开始操作生产数据库，企业关心的不止是权限有没有给够，还有一个更难缠的问题：审计日志里记的是谁？

SQL MCP Server 提供了三种 SQL 认证方式。前两种用起来简单，但审计上存在问题——日志里看不到真实用户。第三种方式叫 On-Behalf-Of（OBO），需要多配几步，但能让 Azure SQL 的审计日志精确记录到发起操作的那个用户。

这篇文章逐一拆解三种方式的行为差异，给出 OBO 的配置步骤，以及怎么验证和审计最终结果。

## 三种认证方式，三种审计结果

### 方式一：用户名 + 密码

连接字符串里直接写账号密码，数据库日志记录的自然是这个凭据对应的身份。无论 Agent 背后是哪个用户在调用，日志里看到的都是同一个服务账号。

```
用户 → Agent → MCP Server → (传用户名密码) → SQL → 日志记的是连接凭据
```

用起来最省事，但随着安全实践演进，这种方式正在逐渐退场。

### 方式二：托管身份（Managed Identity）

托管身份省掉了密码管理，但在审计结果上和第一种没有本质区别——Azure SQL 验证的是应用的身份，日志记录的也是应用，不是调用它的用户。

```
用户 → Agent → MCP Server → (传 MCP Server 的托管身份) → SQL → 日志记的是应用标识
```

### 方式三：On-Behalf-Of（OBO）透传认证

这才是面向 Agent 场景的正解。OBO 基于 Microsoft Entra ID，让服务之间交换用户 token：Agent 把用户的 bearer token 传给 MCP Server，MCP Server 再把它换成访问 Azure SQL 的 token 去连数据库。

```
用户 → (Entra ID 认证) → Agent → (转发 user token) → MCP Server → (交换 token 后以用户身份连接) → SQL → 日志记的是真实用户
```

关键区别：Azure SQL 认证的是**发起操作的真实用户**，不是应用、不是 Agent、不是 MCP Server。操作日志里能看到用户的身份、执行的语句、以及中间经过的 OBO 中间层应用 ID。

## DAB 2.0 中的 OBO 配置

Data API builder（DAB）2.0 配合 SQL MCP Server 原生支持 OBO。配置写在 DAB 的数据源配置里，连接字符串不能包含 `User ID`、`Password` 或 `Authentication`——DAB 会在打开 SQL 连接时注入每个用户的访问 token。

```json
{
  "data-source": {
    "database-type": "mssql",
    "connection-string": "@env('MSSQL_CONNECTION_STRING')",
    "user-delegated-auth": {
      "enabled": true,
      "provider": "EntraId",
      "database-audience": "https://database.windows.net"
    }
  }
}
```

因为每个用户会拿到独立的数据库连接，缓存可能会引起顾虑。DAB 对此做了硬性校验：响应缓存和用户委派认证互斥，同时启用两者会被配置校验器直接拒绝。OBO token 缓存本身是按用户隔离的。

## 验证身份：WhoAmI

官方文档的 OBO 示例里用了一个简单的 `WhoAmI` 视图来验证效果：

```sql
CREATE VIEW [dbo].[WhoAmI] AS
SELECT SUSER_NAME() AS [UserName];
```

通过 DAB 暴露给认证用户后，前端发一个带 token 的请求，看看 SQL 到底认为是谁在操作：

```javascript
const headers = await getAuthHeaders();

const response = await fetch(`${API_URL}/api/WhoAmI`, {
  method: "GET",
  headers,
});

const payload = await response.json();
const sqlUserName = payload.value[0].UserName;

console.log(`SQL sees this request as: ${sqlUserName}`);
```

示例 UI 会显示 "SQL Server sees you as: user@example.com"。SQL 认识的是真正的用户，不是服务账号。

## MCP 模式下也一样

同一个 DAB 运行时可以同时暴露 REST、GraphQL 和 MCP 端点。在 OBO 示例中，MCP 和 Entra ID 认证、用户委派认证写在同一份配置文件里。

Agent 通过 MCP 工具调用也一样走透传：

```json
{
  "tool": "read_records",
  "arguments": {
    "entity": "WhoAmI"
  }
}
```

Agent 仍然是在调工具，DAB 仍然在执行实体权限校验，Azure SQL 仍然认证的是用户。这是一个关键区别：**Agent 执行操作，但 SQL 记录的是授权这次操作的用户上下文。**

## 审计日志里能看到什么

Azure SQL 审计功能可以追踪数据库事件，输出到 Blob 存储、Event Hubs 或 Log Analytics。审计 schema 包含 `database_principal_name`、`server_principal_name`、`statement` 以及 `obo_middle_tier_app_id`——最后这个字段记录的是通过 OBO 接入的中间层应用标识。

在 Log Analytics 中，一条简单的 Kusto 查询就能看到 SQL 眼中的操作者：

```kusto
AzureDiagnostics
  | where Category == "SQLSecurityAuditEvents"
  | where database_name_s == ""
  | project
  event_time_t,
  action_name_s,
  database_principal_name_s,
  server_principal_name_s,
  obo_middle_tier_app_id_s,
  statement_s
  | order by event_time_t desc
```

这套组合给了 Agentic 系统一个更可靠的审计边界——你看到的是哪个用户、什么操作、哪条语句、以及经过哪个 OBO 中间层。

## 小结

OBO 透传认证让 DAB 2.0 配合 SQL MCP Server 不仅是 Agent 和数据库之间的一条便捷通道，更是一条**可问责的通道**。

对简单的应用，用托管身份或服务凭据连接可能就够了。但对需要触碰敏感数据的企业级 Agent，数据库通常要知道真正是谁在操作。有了 SQL MCP Server 和 DAB OBO 认证，Azure SQL 能审计到 Agent 操作背后的真实登录用户——这意味着你的 Agent 可以调用工具，DAB 可以执行权限校验，而 SQL 仍然能回答那个最重要的问题：**谁做的？**

---

如果你关注 AI 助手、开发工具和软件工程实践，可以关注 Aide Hub。这里会继续分享能落地的工具教程、技术观察和项目经验。

## 参考

- [Audit Frontier AI Agents with SQL MCP Server - Microsoft Dev Blogs](https://devblogs.microsoft.com/azure-sql/sql-mcp-server-obo-auth)
- [SQL MCP Server authentication docs](https://learn.microsoft.com/en-us/azure/data-api-builder/mcp/how-to-configure-authentication)
- [DAB On-Behalf-Of authentication docs](https://learn.microsoft.com/en-us/azure/data-api-builder/concept/security/authenticate-on-behalf-of)
- [DAB OBO quickstart sample](https://learn.microsoft.com/en-us/azure/data-api-builder/quickstart/authentication-on-behalf-of)
- [SQL MCP Server NL2SQL](https://devblogs.microsoft.com/azure-sql/sql-mcp-server-nl2sql)
