---
pubDatetime: 2026-06-21T15:11:46+08:00
title: "EF Core Migrations：把数据库结构变更纳入代码流程"
description: "这篇文章整理 EF Core migrations 的完整使用路径：安装 dotnet-ef、创建和应用迁移、理解历史表、处理种子数据、回滚变更，并在 CI/CD 中更安全地执行数据库结构更新。"
tags: ["C#", ".NET", "EF Core", "数据库", "CI/CD"]
slug: "ef-core-migrations-schema-guide"
source: "https://www.devleader.ca/2026/06/20/ef-core-migrations-in-net-managing-your-database-schema"
ogImage: "../../assets/890/01-cover.png"
---

数据库结构变更最怕靠记忆和手工脚本维护。开发库、测试库、生产库只要有一个环境少跑一段 SQL，应用模型和数据库结构就会开始偏离。

EF Core migrations 的价值在这里很直接：把结构变更写成代码，放进版本控制，让同一批变更可以被生成、审查、应用和回滚。原文示例面向 .NET 10 和 EF Core 10，但核心流程对大多数 EF Core 项目都适用。

## 准备工具

命令行迁移依赖 `dotnet-ef`。全局安装：

```bash
dotnet tool install --global dotnet-ef
```

已经装过时可以更新：

```bash
dotnet tool update --global dotnet-ef
```

项目里还需要引用设计时包：

```bash
dotnet add package Microsoft.EntityFrameworkCore.Design
```

这个包提供 `dotnet ef` 需要的设计时服务。缺了它，`dotnet ef migrations add` 可能会报出很绕的错误。装完后用下面的命令检查：

```bash
dotnet ef --version
```

如果系统提示找不到 `dotnet-ef`，优先检查全局工具目录是否在 `PATH` 里。macOS 和 Linux 通常是 `~/.dotnet/tools`，Windows 通常是 `%USERPROFILE%\.dotnet\tools`。

## 创建迁移

当 `DbContext` 和实体类准备好后，可以创建第一条迁移：

```bash
dotnet ef migrations add InitialCreate
```

EF Core 会检查当前模型，并在 `Migrations` 目录生成三类文件：

- `<timestamp>_InitialCreate.cs`：迁移类，包含 `Up()` 和 `Down()`。
- `<timestamp>_InitialCreate.Designer.cs`：EF Core 使用的元数据。
- `<YourDbContext>ModelSnapshot.cs`：当前模型快照。

`Up()` 表示应用变更，`Down()` 表示回滚变更。EF Core 会自动生成这两个方法，但遇到复杂的数据转换时，`Down()` 可能需要人工补齐，避免回滚时只剩空壳。

迁移名建议直接描述业务动作，例如 `AddUserProfileTable`、`RenameEmailColumn`、`AddIndexOnSlug`。半年后再回头看迁移历史，清楚的名字能省很多时间。

## 应用迁移

应用所有待执行迁移：

```bash
dotnet ef database update
```

只应用到某一条迁移：

```bash
dotnet ef database update AddUserProfileTable
```

EF Core 判断哪些迁移已经跑过，靠的是数据库里的 `__EFMigrationsHistory` 表。每次迁移成功应用后，EF Core 都会写入一条记录，包含 migration id 和 EF Core 版本。

可以直接查看这张表：

```sql
SELECT * FROM __EFMigrationsHistory;
```

它让 `dotnet ef database update` 可以重复执行：已经应用过的迁移会被跳过，尚未应用的迁移按顺序执行。不要手动删除这张表里的记录，除非你非常确定当前数据库状态。删错后，EF Core 可能会再次尝试创建已经存在的表或列。

## 启动时迁移要谨慎

开发环境或简单容器环境里，很多人会在应用启动时调用 `MigrateAsync()`：

```csharp
using Microsoft.EntityFrameworkCore;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddDbContext<AppDbContext>(options =>
    options.UseSqlite(
        builder.Configuration.GetConnectionString("DefaultConnection")));

var app = builder.Build();

using (var scope = app.Services.CreateScope())
{
    var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();
    await db.Database.MigrateAsync();
}

await app.RunAsync();
```

这个调用是幂等的，没有待执行迁移时不会做事。问题在生产环境：如果迁移耗时很长，应用启动会被拖住；如果迁移中途失败，应用可能直接启动失败。生产库更适合把迁移放到发布步骤里单独运行，执行完再发布应用。

## 处理种子数据

EF Core 早就支持 `HasData`，但它适合静态参考数据，因为数据需要在模型构建时确定，还常常要写死主键。

EF Core 9+ 推荐用 `UseSeeding` 和 `UseAsyncSeeding` 处理更动态的初始化数据。它们在迁移应用后运行，可以拿到真实的 `DbContext`：

```csharp
builder.Services.AddDbContext<AppDbContext>(options =>
{
    options.UseSqlite(
        builder.Configuration.GetConnectionString("DefaultConnection"));

    options.UseAsyncSeeding(async (context, _, cancellationToken) =>
    {
        if (!await context.Set<Tag>().AnyAsync(cancellationToken))
        {
            context.Set<Tag>().AddRange(
                new Tag { Name = "csharp" },
                new Tag { Name = "dotnet" },
                new Tag { Name = "efcore" });

            await context.SaveChangesAsync(cancellationToken);
        }
    });
});
```

这里的关键是判断条件。比如 `AnyAsync()` 检查目标表是否已有数据，避免每次启动重复插入。和 `HasData` 相比，这种写法不用硬编码主键，也更适合读取配置或执行异步逻辑。

## 回滚和删除

回滚到某一条迁移后的状态：

```bash
dotnet ef database update AddUserProfileTable
```

清空全部迁移，回到空数据库状态：

```bash
dotnet ef database update 0
```

如果刚创建的迁移还没应用到任何数据库，可以删除最新一条：

```bash
dotnet ef migrations remove
```

只能删除最新迁移。已经应用过的迁移要先把数据库回滚，再删除迁移文件。原文这里有一个容易看错的点：流程应是先 `database update <上一条迁移名>`，再 `migrations remove`，不能直接删一个已经进入数据库历史表的迁移。

## CI/CD 怎么跑

最直接的方式是在发布步骤里跑：

```bash
dotnet ef database update \
  --project src/MyApp.Data \
  --startup-project src/MyApp.Web \
  --connection "$DATABASE_CONNECTION_STRING"
```

这种方式简单，但 CI runner 需要安装 `dotnet-ef`，发布流程也要能访问数据库连接串。

如果生产库由 DBA 管理，可以生成幂等 SQL 脚本：

```bash
dotnet ef migrations script --idempotent --output migrations.sql
```

`--idempotent` 会让脚本根据 `__EFMigrationsHistory` 判断每条迁移是否已经应用，适合数据库状态不完全一致的环境。

更适合生产发布的方式是 migration bundle：

```bash
dotnet ef migrations bundle \
  --project src/MyApp.Data \
  --startup-project src/MyApp.Web \
  --output ./artifacts/efbundle \
  --self-contained

./artifacts/efbundle --connection "$DATABASE_CONNECTION_STRING"
```

bundle 是一个可执行文件。构建阶段把迁移打进去，发布阶段只运行这个产物。部署目标不需要安装 `dotnet-ef`，也不需要带着 EF Core design package。对容器部署、受限环境、需要审计发布产物的团队来说，这种方式更清楚。

## 什么时候压缩迁移

迁移文件积累到几十个、上百个后，历史会变得很吵。可以把旧迁移压缩成一个新的基线迁移：

1. 删除旧的 `Migrations` 文件。
2. 用当前模型重新生成一条 `InitialSchema`。
3. 在已经更新到最新结构的数据库里，手动把这条基线写入 `__EFMigrationsHistory`。

示例：

```sql
INSERT INTO __EFMigrationsHistory (MigrationId, ProductVersion)
VALUES ('20260101000000_InitialSchema', '10.0.0');
```

这一步只适合所有已部署环境都处在同一个迁移版本时做。如果还有环境落后，压缩后它们会丢失追赶所需的中间迁移。

## 常见坑

`dotnet-ef` 没装或不在 `PATH` 里，是入门阶段最常见的问题。先跑 `dotnet ef --version`，比盲查项目代码更快。

多人同时改模型时，`ModelSnapshot` 容易冲突。解决冲突后，要确认最终快照包含双方模型变更。可以再跑一次迁移生成命令检查是否还有未捕获的模型差异。

生产环境直接在应用启动时跑迁移，会把结构变更和应用启动绑在一起。长迁移、失败回滚、备份窗口都会变得难处理。对生产库，优先考虑 SQL 脚本或 migration bundle。

模块化单体或多 `DbContext` 项目要保持迁移边界。一个模块的迁移不要引用另一个模块的实体，否则数据层耦合会变得很难拆。

## 收尾建议

把 migrations 当成代码的一部分：提交到仓库、参与评审、在测试环境执行、发布前确认备份和回滚路径。小项目可以从 `dotnet ef database update` 开始，大项目逐步引入幂等脚本和 migration bundle。

读完原文后，我会把这篇内容归到“教程 / 实操型”：它最适合收藏，价值在于把 EF Core 迁移从创建、应用、回滚到发布串成一条可执行路径。

如果你关注 AI 助手、开发工具和软件工程实践，可以关注 Aide Hub。这里会继续分享能直接用于项目的工具教程、技术观察和项目经验。

## 参考

- [EF Core Migrations in .NET: Managing Your Database Schema](https://www.devleader.ca/2026/06/20/ef-core-migrations-in-net-managing-your-database-schema)
