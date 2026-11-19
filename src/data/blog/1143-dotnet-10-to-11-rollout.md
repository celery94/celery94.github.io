---
pubDatetime: 2026-11-19T09:30:07+08:00
title: "把一个 .NET 10 服务升到 .NET 11"
description: "用选课服务演示 .NET 10 到 .NET 11 的升级评审，记录 SDK、HTTP 契约和数据基线。用新旧版本并存、流量分流和旧镜像恢复来验证发布条件，附可用于团队评审的灰度与回退检查表。"
tags: ["DotNet", "ASP.NET Core", "Deployment"]
slug: "dotnet-10-to-11-rollout"
ogImage: "../../assets/1143/01-cover.jpg"
source: "https://learn.microsoft.com/en-us/dotnet/core/compatibility/11"
---

选课 API 升级当天，真正需要提前回答的问题是：新旧镜像能不能同时写同一张报名表？如果只能单边写，回退镜像时就可能遇到旧程序无法读的字段或数据。先确认数据和客户端契约可跨版本工作，再考虑切多少流量。

本例把 .NET 10 基线和 .NET 11 候选版指向同一份 schema，保留相同的报名唯一键和对外状态码。配套示例可在测试库复现 HTTP 契约回归。生产阈值、代理链路和回滚时间由各团队在自己的环境里演练并填写。

## 基线保存到可以回放的程度

先保留旧镜像的完整摘要和部署配置版本，记录 SDK、目标框架、运行时、NuGet 的直接与传递依赖以及数据库 provider。留下一份 OpenAPI JSON 和 Angular 生成配置。API 日志里选一组可匿名化的请求样本，保存对应状态码、响应体和关键响应头。

然后在升级分支固定 `global.json` 的 SDK，把 Web 项目目标改为 `net11.0`，升级与框架配套的包。基线和候选版可以分别用 `dotnet --version` 验证实际选择的 SDK。开发机如果使用 Visual Studio，正式面向 `net11.0` 需要 18.12 或更新版本。部署侧的 Hosting Bundle、容器基础镜像与构建 SDK 分别核对；目标处理器也要满足 x86-64-v2 或对应 Arm64 平台的要求。

## 用同样的请求跑两份应用

在同版 PostgreSQL 的两个空测试库初始化相同数据，先后运行样本，避免第一次写入改变第二份对照。HTTP 端覆盖正常报名、课程缺失、重复报名和缺少字段，前端还要测认证过期、流式事件断开和客户端对错误体的解析。[配套 Web API 与 Angular 复现说明](https://celery94.github.io/posts/aspnet-core-11-openapi-angular/)

实际使用 EF Core 的服务还要固定 provider。对高频查询记录参数、生成 SQL、结果行数和执行计划。确认变更后的语义，再讨论数据库 CPU 或执行耗时。只需升级运行时的变更可以暂缓采用新的 LINQ 写法，也可以暂时保留经验证兼容的生成器文档版本。

如果发布确实需要引入新字段，先增加旧程序能容忍的列和索引，让两个应用版本分别读写。回填期间持续检查写入量和冲突，再切换读路径。等到旧镜像退出回退窗口，单独安排字段删除等收缩操作。上线前必须试过「旧版写、新版读」与「新版写、旧版读」。

## 灰度和回退使用同一张记录表

| 审查项目   | 记录内容                                                 | 放行条件                             |
| ---------- | -------------------------------------------------------- | ------------------------------------ |
| 构建与启动 | SDK、容器摘要、部署设置、最低规格机器的启动记录          | 候选镜像可从零启动，健康探针通过     |
| 契约       | OpenAPI 差异、Angular 生成产物、成功与错误响应、SSE 记录 | 已审核的差异和实际客户端行为相符     |
| 数据       | provider、迁移脚本、旧新互读、唯一约束、执行计划         | 两版并存，数据仍可回退读取           |
| 灰度       | 试点流量、观察窗口、调用次数、5xx、延迟与数据库等待      | 达到预先约定的样本量，未触发停止条件 |
| 回退       | 旧镜像摘要、配置版本、分流开关、值班人和恢复证据         | 能按演练顺序撤流并核对写入状态       |

报错率要与同一时段的旧实例比较。示例门槛可以是观察 30 分钟且至少收到 1,000 个代表性请求，若 5xx 高出旧版 0.5 个百分点就撤流。这样的数字只是填写范例。低流量服务需要延长观察时间，流式接口还要单独观察非正常断开和重连情况。

撤流时先停止向候选版分配新请求，给进行中的请求留出退出时间，切回记录好的旧镜像与配置。重放一次报名并核对数据库记录，确认没有重复处理。数据库若已发生破坏性变更，切旧镜像前先执行验证过的数据恢复方案。升级评审应在放量之前写清这一点，并把演练结果记在同一张表里。

## 参考

- [.NET 11 破坏性变更](https://learn.microsoft.com/en-us/dotnet/core/compatibility/11)
- [SDK、MSBuild 和 Visual Studio 版本支持](https://learn.microsoft.com/en-us/dotnet/core/porting/versioning-sdk-msbuild-vs)
- [ASP.NET Core 11 破坏性变更](https://learn.microsoft.com/en-us/aspnet/core/breaking-changes/11/overview)
- [EF Core 11 破坏性变更](https://learn.microsoft.com/en-us/ef/core/what-is-new/ef-core-11.0/breaking-changes)
- [EF Core 迁移应用方式](https://learn.microsoft.com/en-us/ef/core/managing-schemas/migrations/applying)
