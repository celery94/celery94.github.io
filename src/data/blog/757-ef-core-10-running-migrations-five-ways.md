---
pubDatetime: 2026-04-27T09:40:00+08:00
title: "EF Core 10 数据库迁移的五种执行方式对比"
description: "本文系统对比 EF Core 10 提供的五种迁移执行方式——CLI、Database.Migrate()、SQL 脚本、Migration Bundle 和 EnsureCreated()，给出决策矩阵和生产环境上线清单，帮助你在不同场景下选对方案。"
tags: ["EF Core", ".NET", "dotnet", "数据库", "CI/CD"]
slug: "ef-core-10-running-migrations-five-ways"
ogImage: "../../assets/757/01-cover.png"
source: "https://codewithmukesh.com/blog/running-migrations-efcore/"
---

在本地开发时，`dotnet ef database update` 用起来非常顺手——写完实体、生成迁移、执行更新，一气呵成。但一旦到了部署阶段，事情就开始复杂起来：CI/CD 流水线里没有 SDK、多个实例同时启动、DBA 要求审批每一条 SQL……同一套迁移文件，放在不同环境下，需要完全不同的执行方式。

EF Core 10 一共提供了五种执行迁移的方案，每种都有明确的适用边界。本文把它们逐一拆开，给出可以直接落地的决策矩阵，以及一份生产上线前必查的清单。

## EF Core 迁移是什么

EF Core 迁移是数据库 Schema 的版本控制系统。每当修改 C# 实体类或 Fluent API 配置后，EF Core 会生成对应的迁移文件，描述将数据库同步到当前代码模型所需的 SQL 变更。迁移按顺序执行，就像 Git 提交一样。

EF Core 用一张特殊的 `__EFMigrationsHistory` 表记录哪些迁移已经执行。每次运行迁移时，EF Core 先查这张表，找出待执行的迁移，再按顺序应用。同一个迁移命令可以安全地执行多次——已经执行过的迁移会被跳过。

**真正重要的问题不是"迁移是什么"，而是"在哪里、用什么方式执行"**。开发、预发和生产环境各有不同的约束，用错方案可能导致停机、数据丢失或部署失败。

## 五种方式一览

在深入每种方案之前，先看一张整体对比：

| 方式 | 执行者 | 需要 SDK | 适用场景 | 风险等级 |
|---|---|---|---|---|
| `dotnet ef database update` | 开发者手动执行 | 是 | 本地开发 | 低 |
| `Database.Migrate()` | 应用启动时自动 | 否 | 简单单实例应用 | 中 |
| SQL 脚本 | DBA / DevOps 手动执行 | CLI 生成 | 受监管环境 | 低 |
| Migration Bundle | CI/CD 流水线 | CLI 生成 | 自动化部署 | 低 |
| `EnsureCreated()` | 应用启动时自动 | 否 | 仅原型/测试 | 高 |

## 方式一：CLI `dotnet ef database update`

这是最直接的方式，也是大多数开发者最先接触到的。

### 常用命令

```bash
# 添加新迁移
dotnet ef migrations add AddMovieRating --project MovieApi.Api

# 应用所有待执行的迁移
dotnet ef database update --project MovieApi.Api

# 删除最后一条迁移（仅限未执行的迁移）
dotnet ef migrations remove --project MovieApi.Api

# 列出所有迁移及其状态
dotnet ef migrations list --project MovieApi.Api
```

### 执行原理

运行 `dotnet ef database update` 时，EF Core 会：

1. 根据 C# 代码构建 `DbContext` 模型
2. 连接数据库，读取 `__EFMigrationsHistory` 表
3. 对比已执行的迁移和本地迁移文件，找出差异
4. 按顺序执行每条待执行迁移的 `Up()` 方法
5. 每条迁移成功后，向 `__EFMigrationsHistory` 插入一条记录

如果某条迁移执行失败，EF Core 立即停止，不会跳过继续执行后续迁移——因为迁移之间往往存在依赖关系。

### 指定目标迁移版本

```bash
# 执行到（包含）指定迁移
dotnet ef database update AddMovieRating --project MovieApi.Api

# 回滚到指定迁移（撤销该迁移之后的所有变更）
dotnet ef database update AddMovieGenre --project MovieApi.Api

# 回滚所有迁移（只保留空数据库结构）
dotnet ef database update 0 --project MovieApi.Api
```

> **注意**：回滚会执行 `Down()` 方法，逆向 Schema 变更。如果 `Up()` 里删除了某列，`Down()` 会重建这列——但该列的数据已经永久丢失。生产环境回滚前务必备份。

### 指定连接字符串

CLI 默认从应用配置读取连接字符串，也可以覆盖：

```bash
dotnet ef database update --project MovieApi.Api \
  --connection "Host=staging-db;Database=movies;Username=admin;Password=secret"
```

### 适用场景

CLI 方式非常适合本地开发——可以立即看到输出，出问题马上修复。但它不适合生产环境，你不会希望 SSH 到生产服务器上手动执行命令。接下来的四种方案都是为了解决这个问题。

## 方式二：应用启动时调用 `Database.Migrate()`

这种方式在应用启动时自动执行待执行的迁移，是最省心的选择——部署完应用，数据库自动更新。

### 实现方式

在 `Program.cs` 里添加：

```csharp
var app = builder.Build();

// 启动时执行待执行的迁移（推荐使用异步版本）
await using (var scope = app.Services.CreateAsyncScope())
{
    var dbContext = scope.ServiceProvider.GetRequiredService<MovieDbContext>();
    await dbContext.Database.MigrateAsync();
}

app.MapOpenApi();
app.MapScalarApiReference();
// ... 其余 pipeline
```

### 多实例并发问题

这里有一个重要风险：如果你在负载均衡、Kubernetes 多副本或 Azure App Service 弹性扩容的环境下运行多个实例，所有实例会在启动时同时调用 `Migrate()`。两个实例同时执行同一条迁移，可能导致：

- `__EFMigrationsHistory` 表上的死锁
- "表已存在"之类的重复 Schema 变更错误
- 迁移只执行了一半，数据库处于不一致状态

从 EF Core 9 开始，`Migrate()` 和 `MigrateAsync()` 会自动获取一个数据库级别的锁，防止并发竞争（[官方文档](https://learn.microsoft.com/en-us/ef/core/managing-schemas/migrations/applying#migration-locking)）。不同数据库提供程序的锁实现不同——SQL Server 和 PostgreSQL 处理得很干净，SQLite 使用锁表，进程崩溃时可能残留。

各版本行为：

| EF Core 版本 | 并发行为 |
|---|---|
| EF Core 7 及更早 | 无内置锁，多实例竞争，第一个成功，其他报错 |
| EF Core 8 | 同上，需外部协调 |
| EF Core 9+ | 自动获取数据库级锁，提供程序各自实现 |
| EF Core 10 | 同 EF Core 9，所有关系型提供程序默认开启 |

### 适用场景

`Database.Migrate()` 适合：

- 单实例应用——没有并发风险
- 小型内部工具——部署简单比严格流程更重要
- 开发/预发环境——偶尔出问题可以接受

不适合：

- 多实例生产部署——用 Migration Bundle 替代
- 受监管环境——需要审计追踪和审批流程
- 大型数据库——长时间运行的迁移会拖慢应用启动

## 方式三：SQL 脚本

对于需要完全控制和可审计性的团队来说，生成 SQL 脚本是最安全的选择。EF Core 不直接执行迁移，而是生成 SQL 文件，交给 DBA 或数据库变更管理工具处理。

### 生成完整脚本

```bash
dotnet ef migrations script --project MovieApi.Api --output migrations.sql
```

这会生成一个包含所有迁移 `Up()` 方法的 SQL 文件。但有一个问题——这个脚本假设数据库是全新的，如果数据库已经执行了部分迁移，直接运行会报错。

### 生成幂等脚本

更安全的选项是幂等脚本，它在每条迁移前检查 `__EFMigrationsHistory`，已经执行过的迁移会被跳过：

```bash
dotnet ef migrations script --idempotent --project MovieApi.Api --output migrations.sql
```

生成的 SQL 会在每条迁移外面包一层条件检查。以 PostgreSQL 为例：

```sql
DO $EF$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM "__EFMigrationsHistory"
        WHERE "MigrationId" = '20260305120000_AddMovieRating'
    ) THEN
        ALTER TABLE app."Movies" ADD "Rating" double precision NOT NULL DEFAULT 0.0;

        INSERT INTO "__EFMigrationsHistory" ("MigrationId", "ProductVersion")
        VALUES ('20260305120000_AddMovieRating', '10.0.0');
    END IF;
END $EF$;
```

> **实践建议**：生产环境的脚本始终加 `--idempotent`。它可以安全地重复运行，部署失败重试时不用担心重复执行 Schema 变更。

### 生成指定范围的脚本

也可以为特定的迁移范围生成脚本：

```bash
# 从 AddMovieGenre 到 AddMovieRating（含）
dotnet ef migrations script AddMovieGenre AddMovieRating \
  --project MovieApi.Api --output patch.sql
```

这在需要针对热修复部署特定迁移时很有用。

### 适用场景

SQL 脚本适合：

- 受监管行业（金融、医疗）——DBA 必须审查并批准每一个 Schema 变更
- 使用 Flyway、Liquibase 等数据库变更管理工具的团队
- 大型生产数据库——需要先在数据副本上测试脚本
- 审计合规——需要留存实际执行的 SQL 记录

缺点是需要人工操作，不能直接接入自动化 CI/CD 流水线。这正是 Migration Bundle 要解决的问题。

## 方式四：Migration Bundle（CI/CD 推荐方案）

Migration Bundle 在 EF Core 6 中引入，是生产环境 CI/CD 部署的推荐方案。Bundle 是一个独立的可执行文件，包含所有迁移逻辑——部署机器上不需要 .NET SDK、CLI 工具或源代码。

### 创建 Bundle

```bash
dotnet ef migrations bundle --project MovieApi.Api --output efbundle --force
```

生成的可执行文件（Linux/Mac 是 `efbundle`，Windows 是 `efbundle.exe`）包含：

- 编译后的所有迁移文件
- 执行迁移所需的 EF Core 库
- 连接字符串解析逻辑

Bundle 默认是框架依赖的，运行时需要安装 .NET 运行时。如果想要完全自包含（不依赖任何 .NET 安装），加上 `--self-contained` 和运行时标识符：

```bash
dotnet ef migrations bundle --project MovieApi.Api --output efbundle --force \
  --self-contained -r linux-x64
```

运行时标识符根据部署目标选择：`linux-x64`、`win-x64`、`linux-arm64` 等。

### 运行 Bundle

```bash
# 使用项目配置中的连接字符串
./efbundle

# 显式指定连接字符串
./efbundle --connection "Host=prod-db;Database=movies;Username=deploy;Password=secret"
```

Bundle 同样做幂等检查——读取 `__EFMigrationsHistory`，只执行待执行的迁移，可以安全地多次运行。

### 在 CI/CD 流水线中使用

下面是一个真实的 GitHub Actions 工作流，将 Bundle 作为构建产物，在部署阶段执行：

```yaml
# .github/workflows/deploy.yml
name: Deploy with Migrations

on:
  push:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      - uses: actions/setup-dotnet@v6
        with:
          dotnet-version: '10.0.x'
      - run: dotnet tool install --global dotnet-ef
      - run: dotnet ef migrations bundle --project MovieApi.Api --output efbundle --force
      - uses: actions/upload-artifact@v7
        with:
          name: migration-bundle
          path: efbundle

  deploy:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - uses: actions/download-artifact@v8
        with:
          name: migration-bundle
      - run: chmod +x efbundle
      - run: ./efbundle --connection "${{ secrets.PROD_CONNECTION_STRING }}"
```

### 在 Docker 中使用

如果用 Docker 部署，可以在多阶段 Dockerfile 中构建 Bundle：

```dockerfile
# 构建阶段
FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
WORKDIR /src
COPY . .
RUN dotnet tool install --global dotnet-ef
ENV PATH="$PATH:/root/.dotnet/tools"
RUN dotnet ef migrations bundle --project MovieApi.Api --output /app/efbundle --force

# 运行阶段
FROM mcr.microsoft.com/dotnet/aspnet:10.0
WORKDIR /app
COPY --from=build /app/efbundle .
COPY --from=build /src/MovieApi.Api/bin/Release/net10.0/publish .
ENTRYPOINT ["dotnet", "MovieApi.Api.dll"]
```

然后在启动应用前作为独立步骤运行 Bundle：

```bash
docker run --rm myapp ./efbundle --connection "$PROD_CONNECTION_STRING"
docker run -d myapp
```

### Bundle 为什么是生产环境最佳选项

| 其他方案的痛点 | Bundle 的解决方式 |
|---|---|
| 生产服务器需要安装 SDK | Bundle 自包含，无需 SDK |
| 多实例同时调用 `Migrate()` | Bundle 独立于应用启动，只运行一次 |
| DBA 需要审查 SQL | 从同一套迁移文件生成 `--idempotent` 脚本即可 |
| CI/CD 自动化 | Bundle 是构建产物，像其他二进制文件一样部署 |
| 连接字符串管理 | 通过参数或环境变量传入 |

## 方式五：`EnsureCreated()`——只用于测试的快捷方式

`EnsureCreated()` 根据当前模型创建数据库和所有表，但完全绕过迁移系统。没有迁移文件，没有 `__EFMigrationsHistory`，没有增量变更。

```csharp
// 不要在生产环境用这个
using (var scope = app.Services.CreateScope())
{
    var dbContext = scope.ServiceProvider.GetRequiredService<MovieDbContext>();
    dbContext.Database.EnsureCreated(); // 创建表，忽略迁移
}
```

### 为什么它很危险

用 `EnsureCreated()` 会掉进这个坑：

1. 第一次运行：根据当前模型创建所有表，一切正常。
2. 给 `Movie` 添加了新属性：`EnsureCreated()` 看到数据库已存在，什么都不做，新列没有加进去。
3. 你想切换到 `Migrate()`：失败了，因为没有 `__EFMigrationsHistory` 表，EF Core 不知道数据库处于什么状态。
4. 进退两难：唯一的出路是删掉数据库重来，或者手动创建迁移历史表并伪造条目。

这个场景在生产环境真实发生过：一个团队用 `EnsureCreated()` 做原型，直接上了生产，三个月后需要加列时发现什么都改不了，最后不得不手写 SQL 修改表结构并手动插入迁移历史记录。

### 唯一合理的用法

`EnsureCreated()` 只有一个正当用途：集成测试里用内存数据库或临时数据库，测试结束后直接销毁。

```csharp
// 这样用没问题——测试数据库在测试后直接丢弃
var options = new DbContextOptionsBuilder<MovieDbContext>()
    .UseInMemoryDatabase(databaseName: Guid.NewGuid().ToString())
    .Options;

using var context = new MovieDbContext(options);
context.Database.EnsureCreated(); // 测试场景下 OK
```

除此之外——开发、预发、生产——用 `Migrate()` 或其他方案。

## 场景决策矩阵

根据团队规模、CI/CD 成熟度和合规要求，选择最合适的方案：

| 场景 | 推荐方案 | 原因 |
|---|---|---|
| 独立开发者，本地开发 | CLI（`dotnet ef database update`） | 简单、反馈即时、完全可控 |
| 小团队，没有 CI/CD | `Database.Migrate()` in Program.cs | 零人工步骤，部署即更新 |
| 有 CI/CD 流水线的团队 | Migration Bundle | 自动化、生产服务器无需 SDK、与应用启动解耦 |
| 受监管行业（金融、医疗） | SQL 脚本 + DBA 审查 | 完整审计追踪，人工审批关卡 |
| Kubernetes / 多实例部署 | Migration Bundle 作为 init container | 在任何应用实例启动前只运行一次 |
| 集成测试 | `EnsureCreated()` | 临时数据库，不需要迁移历史 |

**默认推荐**：只要有 CI/CD 流水线，就用 Migration Bundle。它是最健壮的选项——自包含、幂等、专为这个场景设计。在流水线里配置一次，之后不需要再操心迁移部署的问题。

小项目或早期开发阶段，`Database.Migrate()` 完全够用，不必过度设计。但要清楚它的局限，等应用规模扩大后及时切换到 Bundle。

## 生产上线前的检查清单

### 上线之前

1. **备份数据库**——无条件执行。即使用了幂等脚本，意外依然会发生。
2. **审查迁移 SQL**——用 `dotnet ef migrations script --idempotent` 生成脚本并逐行阅读，重点关注 `DROP` 语句、数据类型变更和可能造成数据丢失的操作。
3. **在预发环境的生产数据副本上测试**——不要在空数据库上测，空数据库通过的迁移可能在千万行数据上触发锁超时或约束冲突。
4. **检查长时间运行的查询**——在千万行的表上添加索引可能锁表数分钟，考虑安排在低流量窗口执行。
5. **验证 `Down()` 方法**——如果需要回滚，`Down()` 必须干净地逆向 `Up()` 的变更。自动生成的 `Down()` 通常没问题，复杂迁移可能需要手动修正。

### 上线过程中

6. **先执行迁移，再部署新版本应用代码**——新代码依赖新 Schema，如果应用先于迁移启动，会产生运行时异常。
7. **只用一个迁移执行者**——无论是 CI/CD 步骤、init container 还是 DBA 手动运行脚本，同一时间只允许一个进程执行迁移。
8. **监控迁移过程**——关注锁等待超时、死锁和约束错误。如果迁移挂住了，在强行终止前先排查原因，以免留下半执行状态的迁移。

### 上线之后

9. **验证 `__EFMigrationsHistory`**——确认所有预期的迁移都出现在历史表里。
10. **对 API 做冒烟测试**——访问关键接口。Schema 变更有时会引入单元测试无法发现的细微问题，比如某些查询才用到的列缺失。

## 常见错误及修复方法

### 错误一：在生产环境使用 `EnsureCreated()`

**症状**：数据库在没有迁移追踪的情况下被创建，之后永远无法切换到 `Migrate()`。

**修复**：用 `Database.Migrate()` 替换。如果已经掉坑，创建一条初始迁移，然后手动向 `__EFMigrationsHistory` 插入记录，标记为已执行。

### 错误二：生成 SQL 脚本时忘了 `--idempotent`

**症状**：在已有部分迁移的数据库上运行脚本，因为试图重建已有的表而报错。

**修复**：始终用 `dotnet ef migrations script --idempotent`，额外的条件检查零风险，让脚本可以安全重试。

### 错误三：生产迁移前没有备份

**症状**：迁移删除了某列，发现需要那份数据时已经来不及，`DROP COLUMN` 没有撤销按钮。

**修复**：把数据库备份作为部署流水线的第一个步骤，让执行迁移离不开备份。

### 错误四：多实例部署中使用 `Migrate()`

**症状**：三个 Kubernetes Pod 同时启动，同时调用 `Migrate()`，两个因并发错误失败，健康检查把这两个 Pod 标记为不健康。

**修复**：用 Kubernetes init container 或独立的 CI/CD 步骤运行 Migration Bundle，在任何应用实例启动前完成迁移。

### 错误五：修改已执行的迁移文件

**症状**：修改了已经在预发环境执行过的迁移文件，EF Core 检测到模型快照不匹配，后续迁移开始报错。

**修复**：已执行的迁移文件永远不要修改。需要变更就新建迁移；如果迁移尚未同步到任何共享环境，先用 `dotnet ef migrations remove` 删除再重建。

### 错误六：删除迁移文件

**症状**：删除旧的迁移文件想"清理"目录，导致模型快照不同步，EF Core 之后生成的迁移不正确。

**修复**：不要随意删除迁移文件——每个文件都参与构成累积的模型快照，删掉会断链。如果确实需要"瘦身"，参考 [清理迁移](https://codewithmukesh.com/blog/cleaning-migrations-efcore/) 文章，走正式的迁移压缩流程。

## 故障排查

**"该迁移已经被应用到数据库"**：想用 `dotnet ef migrations remove` 删除迁移，但迁移已经执行了。先用 `dotnet ef database update PreviousMigrationName` 回滚，再删除。

**"找到多个 DbContext"**：项目里有多个 DbContext 类，没有指定使用哪个。加上 `--context` 标志：`dotnet ef database update --context MovieDbContext`。

**"已存在同名迁移"**：迁移名必须唯一。换一个更具体的名字，或者如果刚刚删除了一个迁移想重建，先用 `dotnet ef migrations list` 确认删除操作已经完成。

**迁移在大表上挂住**：在大表上加列或索引可能长时间锁表。对 PostgreSQL，可以编辑迁移文件使用原生 SQL：`migrationBuilder.Sql("CREATE INDEX CONCURRENTLY ...")`。注意[并发创建索引不能在事务中运行](https://www.postgresql.org/docs/current/sql-createindex.html#SQL-CREATEINDEX-CONCURRENTLY)，需要同时禁用该迁移的事务。

**Bundle 报"找不到连接字符串"**：Bundle 默认从项目配置读取连接字符串，在项目目录之外运行时会找不到。显式传入：`./efbundle --connection "your-connection-string"`。

**"Pending model changes 警告，但没有改动任何内容"**：模型快照不同步。运行 `dotnet ef migrations add CheckSnapshot --project MovieApi.Api`，检查生成的迁移是否为空（如果没有真实变更应该是空的），然后删除。如果不是空的，说明有未提交的模型变更需要正式迁移。

## 小结

EF Core 10 提供了五种执行迁移的方案，每种都有它的位置：CLI 对应本地开发，`Database.Migrate()` 对应简单单实例应用，Migration Bundle 对应 CI/CD 流水线，SQL 脚本对应受监管环境，`EnsureCreated()` 对应测试数据库。

最核心的一条原则：**把迁移当作部署产物，而不是事后才想到的事**。在 CI 里构建 Bundle、在预发环境测试、在应用部署之前作为独立步骤执行。这套模式可以避免绝大多数因迁移引发的生产事故。

## 参考

- [Running Migrations in EF Core 10 - 5 Ways Compared](https://codewithmukesh.com/blog/running-migrations-efcore/)
- [EF Core Migration Locking (官方文档)](https://learn.microsoft.com/en-us/ef/core/managing-schemas/migrations/applying#migration-locking)
- [PostgreSQL 并发创建索引](https://www.postgresql.org/docs/current/sql-createindex.html#SQL-CREATEINDEX-CONCURRENTLY)
- [Kubernetes Init Containers](https://kubernetes.io/docs/concepts/workloads/pods/init-containers/)
