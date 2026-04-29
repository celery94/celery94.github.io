---
pubDatetime: 2026-04-29T08:40:00+08:00
title: "EF Core 10 迁移清理指南：Squash、Reset 与历史管理"
description: "当 EF Core 迁移文件积累到几百个，构建时间、工具响应、合并冲突都会变成大麻烦。本文梳理从删除最近一条迁移到全量 Squash 的每种策略，并提供一个决策矩阵帮你选对方案。"
tags: ["EF Core", "dotnet", "数据库", "迁移"]
slug: "ef-core-cleaning-migrations"
ogImage: "../../assets/761/01-cover.png"
source: "https://codewithmukesh.com/blog/cleaning-migrations-efcore/"
---

![EF Core 迁移清理：Squash、Reset 与历史管理](../../assets/761/01-cover.png)

EF Core 迁移就像数据库 schema 的 Git 提交记录——忠实记录每一次改动。但就像一个有 500 条碎小提交、从不 squash 的 Git 仓库，项目里的 `Migrations` 目录也会变成一团乱麻。作者曾接手过一个有 200 多个迁移文件、C# 代码接近 1 GB 的项目：构建耗时超过一小时，新增一条迁移会让 Visual Studio 卡死五分钟。

那些迁移大多已经没有价值——添加后又改名的列、原型阶段建了又删的表。迁移历史只是团队所有弯路的记录，而团队真正需要的是一个干净的起点。

本文覆盖 EF Core 10 迁移清理的全部策略：从删单条错误迁移到一次性把历史压缩成一个文件，附带决策矩阵和团队协作冲突处理方案。

## 为什么迁移文件越堆越多

每次执行 `dotnet ef migrations add`，EF Core 会生成三个文件：

1. **迁移文件**（`XXXXXX_MigrationName.cs`）——包含 `Up()` 和 `Down()` 方法，记录实际的 schema 变更。
2. **Designer 文件**（`XXXXXX_MigrationName.Designer.cs`）——EF Core 内部使用的元数据。
3. **模型快照**（`AppDbContextModelSnapshot.cs`）——当前整个模型状态的快照，每次迁移都会更新，随项目演进不断膨胀。

五人团队，每个迭代添加 2-3 条迁移，一年下来轻松超过 300 个文件。真正的问题随之而来：

- **构建时间爆炸**：[GitHub issue #30057](https://github.com/dotnet/efcore/issues/30057) 记录了一个项目在升级到 .NET 6 后，220 个迁移文件导致构建时间从 12 分钟涨到超过一小时。
- **`dotnet ef migrations add` 假死**：[GitHub issue #35976](https://github.com/dotnet/efcore/issues/35976) 报告了 EF Core 9 在迁移历史较长的项目上新增迁移时 CPU 飙升、系统卡死长达 5 分钟的问题。
- **模型快照文件膨胀**：每条迁移都会把完整模型状态写入快照，大型 schema 下这个文件本身就能达到数千行。
- **合并冲突成为常态**：快照文件是单一文件，每条迁移都会改动它。两个开发者在不同分支各自添加迁移，必然冲突。

解决方案不是回避迁移——迁移是必要的。解决方案是定期清理，就像你会 squash commits 或清理 feature branch 一样。

## 删除最近一条迁移

最简单的清理操作。你添加了一条迁移，发现模型改错了，想在应用到任何数据库之前撤销它。

```bash
dotnet ef migrations remove
```

或者在 Visual Studio Package Manager Console 里：

```bash
Remove-Migration
```

这条命令做两件事：
1. 从 `Migrations` 目录删除迁移文件和 designer 文件。
2. 把模型快照回滚到上一个状态。

**重要**：只有在迁移**尚未应用到数据库**时才能直接执行。如果已经运行过 `dotnet ef database update`，需要先回退数据库：

```bash
dotnet ef database update PreviousMigrationName
dotnet ef migrations remove
```

第一条命令让 EF Core 执行最新迁移的 `Down()` 方法，回滚 schema；第二条命令再安全删除迁移文件。

> **警告**：永远不要删除已经应用到生产数据库的迁移文件。那会导致 `__EFMigrationsHistory` 表的记录和磁盘上的文件不一致，后续迁移将会失败。生产环境要回滚某个变更，应当创建一条新的迁移来反转那些改动。

## 回退到某个历史迁移

有时需要回滚多条迁移，而不只是最后一条。先查看所有迁移及其应用状态：

```bash
dotnet ef migrations list
```

找到想保留的那条迁移，然后：

```bash
dotnet ef database update AddBlogCreatedTimestamp
```

EF Core 会按逆序依次执行 `AddBlogCreatedTimestamp` 之后每条迁移的 `Down()` 方法，把数据库 schema 回滚到该迁移应用后的状态。

数据库回退完成后，逐条删除不需要的迁移：

```bash
dotnet ef migrations remove
```

重复执行直到所有不需要的迁移被清空。每次调用删除最后一条未应用的迁移。

这个方式适合开发阶段发现最近几条迁移方向走错时做外科手术式修复。要清理几个月或几年积累的迁移，需要用 Squash。

## 安全地 Squash EF Core 迁移

Squash 迁移意味着用单个"初始化"迁移替换整个迁移历史，这个新迁移代表当前数据库的完整 schema。这相当于 EF Core 版的 `git rebase --squash`——把几百条增量变更折叠成一个干净的快照。

EF Core 没有内置的 squash 命令（[GitHub issue #2174](https://github.com/dotnet/efcore/issues/2174) 从 2015 年就开了），但只要按步骤来，流程并不复杂。

### 第一步：备份所有内容

动手之前先创建备份：

```bash
# 备份 Migrations 目录
cp -r Migrations Migrations_backup

# 备份数据库（PostgreSQL 示例）
pg_dump -U postgres -d your_database > backup_before_squash.sql
```

SQL Server 用 SSMS 或 `sqlcmd` 做备份。出了问题，一切可以还原。

### 第二步：确认所有环境同步

应用程序连接的每个数据库（开发、预发、生产）都必须已经应用了全部现有迁移：

```bash
dotnet ef migrations list --connection "your_connection_string"
```

任何环境有待应用的迁移，先补上。Squash 只在所有环境迁移状态一致时才安全。

### 第三步：清空迁移历史表

连接到数据库，删除 `__EFMigrationsHistory` 表里的所有行：

```sql
-- PostgreSQL
DELETE FROM "__EFMigrationsHistory";

-- SQL Server
DELETE FROM [__EFMigrationsHistory];
```

这告诉 EF Core"没有迁移已经被应用"——尽管实际的 schema 已经完全就绪。

### 第四步：删除 Migrations 目录

从项目中删除所有现有迁移文件：

```bash
rm -rf Migrations/
```

或者直接在 IDE 里删掉这个目录。模型快照文件也一并删除。

### 第五步：创建全新初始迁移

```bash
dotnet ef migrations add InitialCreate
```

EF Core 生成一个全新迁移，代表当前完整模型。`Up()` 方法包含每一个 `CREATE TABLE`、每一个索引、每一个关联关系——从头构建数据库所需的一切。

### 第六步：生成历史记录插入语句

需要 EF Core 会向 `__EFMigrationsHistory` 插入的精确 SQL。生成迁移脚本：

```bash
dotnet ef migrations script
```

输出的最后一行类似：

```sql
INSERT INTO "__EFMigrationsHistory" ("MigrationId", "ProductVersion")
VALUES ('20260310120000_InitialCreate', '10.0.0');
```

复制这条 `INSERT` 语句。

### 第七步：插入历史记录

把复制的 `INSERT` 语句在每个数据库（开发、预发、生产）上分别执行：

```sql
INSERT INTO "__EFMigrationsHistory" ("MigrationId", "ProductVersion")
VALUES ('20260310120000_InitialCreate', '10.0.0');
```

这告诉 EF Core"`InitialCreate` 迁移已经应用"——实际上确实如此，因为 schema 本来就已经在那里了。后续的迁移将基于这个干净的基线叠加。

### 第八步：验证

运行迁移列表确认一切干净：

```bash
dotnet ef migrations list
```

应该看到单条迁移，标记为已应用。做个小的模型改动，添加新迁移测试——应该立刻完成，并且只包含那条增量变更。从几百个文件到一个干净的迁移，完成。

> **警告**：旧迁移里的自定义 SQL（原生 SQL 操作、存储过程、触发器、数据填充逻辑）在 Squash 后会丢失。删除前检查旧迁移里的 `migrationBuilder.Sql()` 调用，手动把这些内容加到新的初始迁移里或单独处理。

## 核弹选项：完全重置迁移

开发阶段不在乎保留数据时，重置比 Squash 更简单：

```bash
rm -rf Migrations/
dotnet ef database drop --force
dotnet ef migrations add InitialCreate
dotnet ef database update
```

只推荐在两种场景使用：

1. **早期开发**：还在原型阶段，schema 每天都在变，没人依赖现有数据。
2. **一次性环境**：CI/CD 每次测试都创建全新数据库。

任何环境有需要保留的数据，用上面的 Squash 方案，不要用重置。

## 团队环境里的迁移合并冲突

团队里想清理迁移，很大原因是被合并冲突拖垮。两个开发者在不同分支各自添加迁移，`AppDbContextModelSnapshot.cs` 必然冲突，因为两条迁移都更新了同一个文件。

### 无实质冲突（最常见）

两个开发者改了不相关的内容——一个加了 `Deactivated` 列，另一个加了 `LoyaltyPoints` 列——快照冲突是表面的：

```
<<<<<<< yours
b.Property<bool>("Deactivated");
=======
b.Property<int>("LoyaltyPoints");
>>>>>>> theirs
```

保留两行就行。两条迁移互相独立，可以共存。

### 真实冲突

两个开发者改了同一个属性——比如都重命名了 `Name` 列但改成了不同的名字——这是无法自动合并的真实冲突。

[Microsoft 官方建议](https://learn.microsoft.com/en-us/ef/core/managing-schemas/migrations/teams) 的正确处理方式：

1. 中止合并，回到合并前的分支状态。
2. 删除你自己的迁移（但保留模型/代码改动）。
3. 把队友的改动合并进你的分支。
4. 在合并后的状态上重新添加你的迁移。

```bash
git merge --abort
dotnet ef migrations remove
git merge teammate-branch
dotnet ef migrations add YourMigrationName
```

这样可以确保迁移顺序始终正确，快照也反映真实的合并后模型状态。

### 预防：团队迁移规则

作者在迁移冲突是每周噩梦的团队工作过，也在几乎从不发生冲突的团队工作过。区别在于流程，而不是工具：

1. **每个 PR 只有一条迁移**——不要在 PR 里包含多条迁移。如果功能需要三次 schema 变更，在开 PR 前合并成一条。
2. **先拉取再迁移**——执行 `dotnet ef migrations add` 前，先拉取最新的 `main` 分支，确保你的迁移基于最新快照。
3. **大 schema 变更提前协调**——两个开发者需要改同一张表，先约好谁先来。五分钟 Slack 消息省去一小时冲突处理。
4. **使用 `has-pending-model-changes`**——EF Core 8+ 新增了 [dotnet ef migrations has-pending-model-changes](https://learn.microsoft.com/en-us/ef/core/managing-schemas/migrations/managing#checking-for-pending-model-changes)，检查模型在上次迁移后是否有变动。加进 CI 流水线，捕获遗漏迁移：

```yaml
# GitHub Actions 示例
- name: Check for pending EF Core model changes
  run: dotnet ef migrations has-pending-model-changes --project src/MyApp.Api
```

如果返回 `Changes`，说明有人忘记提交迁移文件。把这个检查加进每个 CI 流水线——它已经帮作者捕获了十几次被遗忘的迁移。

## 清理时机的信号

不是每个项目都需要清理迁移。以下信号告诉你该动手了：

| 信号 | 优先级 | 建议 |
|------|--------|------|
| `dotnet ef migrations add` 超过 30 秒 | 中 | 考虑 Squash |
| 添加迁移后构建时间明显变长 | 高 | 立即 Squash |
| Migrations 目录有 50+ 文件 | 低 | 计划在下次大版本时 Squash |
| Migrations 目录有 100+ 文件 | 中 | 本迭代安排 Squash |
| Migrations 目录有 200+ 文件 | 高 | 现在就 Squash |
| 模型快照文件超过 2000 行 | 中 | Squash——快照在拖慢迁移脚手架 |
| 每个 PR 都有快照合并冲突 | 高 | Squash + 执行团队迁移规则 |

作者的经验法则：**每次重大 .NET 升级时清理迁移**。本来就要做破坏性变更、更新包、彻底测试，同时 Squash 迁移几乎是免费的，还能给下一个开发周期一个干净的基线。从 .NET 6 开始，每个项目都这样做，每个数据库上下文大约花 15 分钟。

## 决策矩阵

| 场景 | 策略 | 风险 | 时间 |
|------|------|------|------|
| 最近一条迁移写错了，还没应用 | `dotnet ef migrations remove` | 无 | 30 秒 |
| 最近几条开发迁移需要重做 | 回退 + 删除 | 低 | 5 分钟 |
| 50+ 条积累迁移，所有环境已同步 | Squash | 低-中 | 15-30 分钟 |
| 早期开发，schema 不稳定，没有真实数据 | 完全重置（drop + recreate） | 无 | 2 分钟 |
| 有多年历史的生产数据库 | Squash（永远不要重置） | 中 | 30 分钟 + 测试 |
| 一个项目里有多个数据库上下文 | 分别 Squash 每个上下文 | 中 | 每个上下文 15 分钟 |
| 团队频繁遭遇合并冲突 | Squash + 执行迁移规则 | 低 | 15 分钟 + 流程改进 |

要避免的做法：
- **不要在不清空 `__EFMigrationsHistory` 的情况下删除迁移文件**——EF Core 会认为那些迁移还需要应用，随后失败。
- **不要手动编辑快照文件**——始终让 EF Core 通过删除再重新添加迁移来重新生成它。
- **环境不同步时不要 Squash**——如果预发比生产落后 3 条迁移，Squash 后它就无法追上了，先同步再 Squash。

## 在 CI 里检测待处理的模型变更

EF Core 8+ 引入了一个对 CI 流水线非常有用的命令：

```bash
dotnet ef migrations has-pending-model-changes
```

如果实体模型在上次迁移创建后有变动，这个命令返回非零退出码。也可以在单元测试里程序化地检查：

```csharp
[Fact]
public void No_Pending_Model_Changes()
{
    using var context = new AppDbContext(options);
    Assert.False(context.Database.HasPendingModelChanges(),
        "Model has changed since the last migration. Run 'dotnet ef migrations add'.");
}
```

这个测试会在有人修改了实体类但忘记创建迁移时失败。搭配 CI 流水线使用，它已经帮作者发现了至少十几次被遗漏的迁移。

## 常见问题排查

### "The migration has already been applied to the database"

**原因**：尝试删除已经通过 `dotnet ef database update` 应用的迁移。

**解决**：先回退再删除：
```bash
dotnet ef database update PreviousMigrationName
dotnet ef migrations remove
```

### "No migration was found with the ID specified"

**原因**：传给 `dotnet ef database update` 的迁移名称不匹配项目里的任何迁移，迁移名称区分大小写。

**解决**：运行 `dotnet ef migrations list` 查看准确名称，使用正确的名称。

### Squash 后快照文件冲突

**原因**：在你的分支上 Squash 了迁移，但队友在 `main` 上基于旧快照状态添加了新迁移。

**解决**：先把 `main` 合并进你的分支，应用所有待处理迁移，**然后**再 Squash。Squash 必须在包含所有历史迁移的分支上进行。

### "The model backing the context has changed since the database was created"

**原因**：Squash 后忘记向 `__EFMigrationsHistory` 插入历史记录。EF Core 认为没有任何迁移已被应用，想运行 `InitialCreate`，但表已经存在，所以失败。

**解决**：对受影响的数据库执行 Squash 流程第七步里的 `INSERT` 语句。

### Squash 后构建速度仍然很慢

**原因**：Squash 了迁移但旧的迁移文件还在 Git 历史里，IDE 在索引它们。

**解决**：确认 Migrations 目录只包含新的 `InitialCreate` 文件和快照。从命令行运行 `dotnet build` 确认构建时间已改善。如果 IDE 还慢，清除其缓存。

### EF Core 在新增迁移时卡死

**原因**：[EF Core 9 的已知问题](https://github.com/dotnet/efcore/issues/35976)——在模型较大的项目上添加迁移会导致 CPU 飙升和系统卡死。

**解决**：Squash 现有迁移以减少 EF Core 需要处理的历史。如果干净的迁移历史后问题依然存在，考虑使用[编译模型](https://learn.microsoft.com/en-us/ef/core/performance/advanced-performance-topics#compiled-models)来提升启动性能。

## 总结

迁移清理不是一次性的事情，而是像更新 NuGet 包或轮换密钥一样的周期性维护任务。关键在于知道用哪个工具：`remove` 用于快速修复，Squash 用于周期性清理，重置只在可以接受数据丢失时使用。

作者在每个项目上遵循的策略：**每次重大 .NET 升级时 Squash**。15 分钟，消除几个月积累的噪音，给团队下一个发布周期一个干净的基础。结合团队规则（每个 PR 只有一条迁移、迁移前先拉取）和 CI 里的待处理模型变更检查，迁移管理就从每周的麻烦变成了几乎不用操心的事情。

## 参考

- [Cleaning Migrations in EF Core 10 - Squash, Reset & Manage History](https://codewithmukesh.com/blog/cleaning-migrations-efcore/)
- [EF Core Migrations - Managing Schemas](https://learn.microsoft.com/en-us/ef/core/managing-schemas/migrations/)
- [Migrations in Team Environments](https://learn.microsoft.com/en-us/ef/core/managing-schemas/migrations/teams)
- [Checking for Pending Model Changes](https://learn.microsoft.com/en-us/ef/core/managing-schemas/migrations/managing#checking-for-pending-model-changes)
- [EF Core Migrations History Table](https://learn.microsoft.com/en-us/ef/core/managing-schemas/migrations/history-table)
