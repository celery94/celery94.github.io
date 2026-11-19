---
pubDatetime: 2026-11-19T09:30:02+08:00
title: "ASP.NET Core 11 升级：Angular 契约检查"
description: "用两份 ASP.NET Core 选课 API 和同一个 PostgreSQL 样本，实测异步验证、并发报名、OpenAPI 3.2、Angular 客户端生成与 SSE 恢复，并给出生成器尚未升级时的兼容处理。"
tags: ["DotNet", "ASP.NET Core", "Angular", "OpenAPI"]
slug: "aspnet-core-11-openapi-angular"
ogImage: "../../assets/1138/01-cover.jpg"
source: "https://learn.microsoft.com/en-us/aspnet/core/release-notes/aspnetcore-11?view=aspnetcore-11.0"
---

同一个选课接口升级到 ASP.NET Core 11 后，成功报名依然返回 200，Angular 客户端却可能卡在生成阶段。本例中，OpenAPI Generator 7.22.0 能读 .NET 10 的 3.1.1 文档，拒绝 .NET 11 默认的 3.2.0 文档。显式切到 3.1 后，仍需处理 SSE 的扩展字段，生成才通过。

异步模型验证也改变了客户端看到的错误细节。两版重复报名都返回 400，但响应的媒体类型和字段名可能有差异。把文档生成和真实请求各跑一遍，才能知道前端需要改哪一处。

## 同一个唯一键，两种重复请求

示例在 PostgreSQL 18.3 使用 `PRIMARY KEY (student, course)`。基线使用 .NET SDK 10.0.402、`Microsoft.AspNetCore.OpenApi` 10.0.13。候选版使用 SDK 11.0.100、对应 OpenAPI 包 11.0.0。两个项目都用 Npgsql 10.0.2 直连数据库。用独立的测试库初始化相同数据，再用同一组请求分别检查两版。[下载源码、OpenAPI 文档和生成结果](https://celery94.github.io/assets/1138/enrollment-web-demo.zip)

.NET 10 在处理程序中等待数据库查重。候选版注册 `AddValidation()`，由请求模型的 `IAsyncValidatableObject.ValidateAsync` 查询已存在的报名。验证时传入的取消令牌也传到数据库调用。只支持异步验证的模型让同步入口明确报错，调用方能及时发现走错了验证路径。

写入使用 `INSERT … ON CONFLICT (student, course) DO NOTHING RETURNING course`。两个请求可能同时读到「尚未报名」，此时数据库唯一键决定哪次写入成功。SQL 没有返回行后，处理程序检查课程是否存在，再返回 404 或 409。样本通过测试库触发器让两个请求在插入前短暂停留，以便复现竞争窗口。

| 实测请求              | .NET 10 基线                    | .NET 11 候选            |
| --------------------- | ------------------------------- | ----------------------- |
| S01 报名 C101         | 200，报名回执                   | 200，同结构             |
| S01 报名不存在的 C999 | 404，`course_missing`           | 404，同结构             |
| S01 再次报名 C101     | 400，`application/problem+json` | 400，`application/json` |
| 学号为空              | 400，`errors.request`           | 400，`errors.Student`   |
| 两次并发报名 C102     | 一次 200，一次 409              | 一次 200，一次 409      |

已有前端如果按媒体类型分派错误，或者取固定的 `errors.request`，团队可以为新验证管道配置既有的响应格式，或者显式发布字段变化并更新前端。状态码一致很容易掩盖这类行为变化。

## 3.2 → 3.1 → Angular 生成输入

栈里还加入了返回 C# union 的 `/course-state`，让生成文档中的 `anyOf` 有实际对照。这条演示接口通过 200 返回不同 JSON 形状，报名接口仍使用声明过的独立状态码。

| 输入                     | SSE 媒体节点                             | 固定生成器 7.22.0 的结果 |
| ------------------------ | ---------------------------------------- | ------------------------ |
| .NET 10 生成的 3.1.1     | `schema`，引用 SSE 包装类型              | 成功                     |
| .NET 11 默认的 3.2.0     | `itemSchema`，含 `data`、`event` 和 `id` | 校验失败                 |
| .NET 11 显式生成的 3.1.2 | `x-oai-itemSchema`                       | 校验拒绝保留扩展名       |
| 针对生成器转换的 3.1.2   | 将该 SSE 媒体节点写为字符串 `schema`     | 成功                     |

配置 `options.OpenApiVersion = Microsoft.OpenApi.OpenApiSpecVersion.OpenApi3_1` 可以得到第三行。转换仅应用于 Angular 生成输入，在样本中只改 `/progress` 的 `text/event-stream` 节点，保留完整的 3.2 参考文档。生成时保持 Angular 版本参数为 20.3.0，无需关闭文档校验。

```bash
java -jar openapi-generator-cli-7.22.0.jar generate \
  -g typescript-angular -i snapshots/net11-angular.json \
  -o clients/net11-angular --additional-properties=ngVersion=20.3.0
```

两份客户端的差异里，`courseState` 方法和分支模型是新文件变化，旧 SSE 包装类型被移除。生成器还把 `anyOf` 扁平化成同时要求 `code` 与 `reason` 的 TypeScript 接口，然而真实分支只返回其中一个字段。使用该接口前，用明确的响应字段或标签建立前端类型，再拿两份真实响应消除这种类型误差。进度端点则单独验证流式消费。

## 让浏览器回归覆盖断线和错误分支

本机通过两个版本的 HTTP 请求验证了 200、400、404 和并发 409。模拟会话的过期标记返回 401，换有效标记后返回 200。这个会话端点只用于回归，实际身份提供方与 Angular 拦截器需要在目标环境验证。

SSE 实测按次序返回 `id: 1` 和 `id: 2`，请求带 `Last-Event-ID: 1` 时只返回第二条。这是样本端点显式实现的恢复规则。上线前从浏览器经过同一层反向代理验证 `text/event-stream` 的缓冲、事件顺序、重连、登录状态和请求结束行为。使用原生 `EventSource` 的应用还要检查认证方式，若要求自定义请求头可以使用 fetch 流式读取实现。

回归清单应包括生成代码里的可空与必填字段、`anyOf`、枚举、二进制下载、认证过期以及错误体。保存两份文档和生成命令，在 CI 用固定输入重跑差异。遇到新增的工具限制时，可以从已核对的 3.1 输入继续生成，等生成器支持目标格式后再移除转换。

## 参考

- [ASP.NET Core 11 正式功能说明](https://learn.microsoft.com/en-us/aspnet/core/release-notes/aspnetcore-11?view=aspnetcore-11.0)
- [ASP.NET Core 11 破坏性变更](https://learn.microsoft.com/en-us/aspnet/core/breaking-changes/11/overview)
- [OpenAPI 3.2 规范](https://spec.openapis.org/oas/v3.2.0.html)
- [OpenAPI Generator 的 TypeScript Angular 生成器](https://openapi-generator.tech/docs/generators/typescript-angular/)
- [PostgreSQL INSERT 与 ON CONFLICT](https://www.postgresql.org/docs/18/sql-insert.html)
