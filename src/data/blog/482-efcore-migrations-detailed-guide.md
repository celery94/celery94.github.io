---
pubDatetime: 2025-10-13
title: EF Core 迁移完全指南：从基础到最佳实践
description: 深入探讨 Entity Framework Core 数据库迁移的完整实践，涵盖迁移创建、自定义、SQL 脚本生成、多种应用方式及生产环境最佳实践，帮助开发者构建可靠的数据库版本管理体系。
tags: ["EF Core", ".NET", "Database", "Migration", "Best Practices"]
slug: efcore-migrations-detailed-guide
source: https://www.milanjovanovic.tech/blog/efcore-migrations-a-detailed-guide
---

# EF Core 迁移完全指南：从基础到最佳实践

随着应用程序的不断发展，管理数据库架构变更往往会成为一个令人头疼的问题。手动修改数据库容易出错且耗时，这很容易导致开发环境和生产环境之间的不一致。在无数项目中，我们都见证过这些问题带来的混乱场景。那么，如何才能做得更好？

Entity Framework Core（EF Core）迁移提供了一个强大的解决方案，让你能够对数据库架构进行版本控制。想象一下：无需编写 SQL 脚本，你只需在代码中定义变更。需要添加列？重命名表？没问题——EF Core 迁移能够追踪数据模型的每一次修改。你可以自信地在不同环境中审查、测试和应用这些变更。

本文将深入探讨 EF Core 迁移的各个方面，包括如何创建和自定义迁移、生成 SQL 脚本、应用迁移的多种方式，以及在实际项目中积累的最佳实践经验。通过系统化的学习，你将能够建立起可靠的数据库版本管理体系。

## 创建第一个迁移

在开始创建迁移之前，我们需要准备好实体类和数据库上下文。让我们从一个简单的 `Product` 实体开始：

```csharp
public class Product
{
    public int Id { get; set; }
    public string Name { get; set; } = string.Empty;
    public string? Description { get; set; }
    public decimal Price { get; set; }
}
```

接下来，我们需要实现 `DbContext` 类。在 `OnModelCreating` 方法中，我们将配置 `Product` 实体的详细映射规则：

```csharp
public class AppDbContext : DbContext
{
    public AppDbContext(DbContextOptions<AppDbContext> options)
        : base(options)
    {
    }

    public DbSet<Product> Products => Set<Product>();

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.Entity<Product>(builder =>
        {
            // 配置表名和约束
            builder.ToTable("Products", tableBuilder =>
            {
                tableBuilder.HasCheckConstraint(
                    "CK_Price_NotNegative",
                    sql: $"{nameof(Product.Price)} > 0");
            });

            // 配置主键
            builder.HasKey(p => p.Id);

            // 配置属性
            builder.Property(p => p.Name).HasMaxLength(100);
            builder.Property(p => p.Description).HasMaxLength(1000);
            builder.Property(p => p.Price).HasPrecision(18, 2);

            // 配置唯一索引
            builder.HasIndex(p => p.Name).IsUnique();
        });
    }
}
```

这段配置代码展示了 EF Core Fluent API 的几个关键方法：

- **ToTable**：配置实体对应的表名，并通过 `TableBuilder` 委托添加检查约束。在这里我们添加了一个约束，确保价格必须大于零。

- **HasKey**：显式配置表的主键。虽然 EF Core 会根据命名约定自动识别 `Id` 属性作为主键，但显式配置能够提高代码的可读性和可维护性。

- **Property**：这是配置实体属性的入口点。我们可以设置字符串的最大长度、decimal 的精度和小数位数等约束。

- **HasIndex**：在指定的属性上定义索引。通过调用 `IsUnique()` 可以声明该索引为唯一索引，确保列值的唯一性。

现在我们准备好创建第一个迁移了。使用 PowerShell 命令如下：

```powershell
Add-Migration Create_Database
```

这将创建一个名为 `Create_Database` 的数据库迁移文件。该迁移包含了 `Up` 和 `Down` 两个方法，分别用于应用和回滚数据库变更。生成的迁移文件如下：

```csharp
public partial class Create_Database : Migration
{
    protected override void Up(MigrationBuilder migrationBuilder)
    {
        migrationBuilder.CreateTable(
            name: "Products",
            columns: table => new
            {
                Id = table.Column<int>(type: "integer", nullable: false)
                    .Annotation("Npgsql:ValueGenerationStrategy",
                        NpgsqlValueGenerationStrategy.IdentityByDefaultColumn),
                Name = table.Column<string>(
                    type: "character varying(100)",
                    maxLength: 100,
                    nullable: false),
                Description = table.Column<string>(
                    type: "character varying(1000)",
                    maxLength: 1000,
                    nullable: true),
                Price = table.Column<decimal>(
                    type: "numeric(18,2)",
                    precision: 18,
                    scale: 2,
                    nullable: false)
            },
            constraints: table =>
            {
                table.PrimaryKey("PK_Products", x => x.Id);
                table.CheckConstraint("CK_Price_NotNegative", "Price > 0");
            });

        migrationBuilder.CreateIndex(
            name: "IX_Products_Name",
            table: "Products",
            column: "Name",
            unique: true);
    }

    protected override void Down(MigrationBuilder migrationBuilder)
    {
        migrationBuilder.DropTable(name: "Products");
    }
}
```

需要注意的是，某些操作是破坏性的（如删除列或表），可能无法轻易回滚。检查生成的迁移文件并防止可能的数据丢失是你的责任。

## 自定义迁移：处理特殊场景

在实际项目中，我们经常需要修改自动生成的迁移文件以应对特殊场景。

### 列重命名的正确处理

假设我们将 `Description` 属性重命名为 `ShortDescription`。在某些 EF Core 版本中，这可能会生成以下迁移代码：

```csharp
migrationBuilder.DropColumn(
    name: "Description",
    table: "Products");

migrationBuilder.AddColumn<string>(
    name: "ShortDescription",
    table: "Products",
    nullable: true);
```

这段代码存在严重问题：先调用 `DropColumn` 会删除数据库中的列，导致宝贵的数据永久丢失。我们真正想要的是重命名现有列，因此需要手动修改迁移文件使用 `RenameColumn` 方法：

```csharp
migrationBuilder.RenameColumn(
    name: "Description",
    table: "Products",
    newName: "ShortDescription");
```

这种修改保留了列中的所有数据，同时完成了重命名操作。这就是为什么仔细审查自动生成的迁移文件如此重要的原因。

### 执行自定义 SQL 命令

有时我们需要执行一些无法通过 EF Core Fluent API 表达的复杂操作，这时可以在迁移中直接执行自定义 SQL 命令。常见的使用场景包括数据迁移、创建复杂索引、定义存储过程或触发器等：

```csharp
public partial class Update_Products : Migration
{
    protected override void Up(MigrationBuilder migrationBuilder)
    {
        // 执行自定义 SQL，例如数据迁移
        migrationBuilder.Sql(@"
            UPDATE Products
            SET Description = CONCAT('Product: ', Name)
            WHERE Description IS NULL");

        // 创建复杂索引
        migrationBuilder.Sql(@"
            CREATE INDEX IX_Products_Price_Name
            ON Products (Price DESC, Name ASC)");
    }

    protected override void Down(MigrationBuilder migrationBuilder)
    {
        // 你需要负责回滚任何自定义更改
        migrationBuilder.Sql(@"
            DROP INDEX IF EXISTS IX_Products_Price_Name");
    }
}
```

自定义 SQL 为我们提供了最大的灵活性，但也意味着需要承担更多的责任。确保 SQL 语句的正确性、跨数据库兼容性以及回滚逻辑的完整性都是开发者需要考虑的问题。

## 生成 SQL 脚本：审查与部署的桥梁

使用 `Script-Migration` 命令可以从迁移生成 SQL 脚本。这对于在应用到数据库之前审查变更非常有用。SQL 脚本还允许我们在没有直接访问 EF 工具的环境中执行迁移，这在许多企业环境中是常见需求。

### 基本 SQL 脚本生成

以下是几种执行 `Script-Migration` 命令的方式：

```powershell
# 生成所有迁移的脚本
Script-Migration

# 从特定迁移开始生成脚本
Script-Migration <FromMigration>

# 生成特定范围的迁移脚本
Script-Migration <FromMigration> <ToMigration>
```

`<FromMigration>` 参数应该是已应用到数据库的最后一个迁移的名称。正确识别数据库的迁移状态并适当应用脚本是你的责任。

以下是 `Create_Database` 迁移生成的 SQL 脚本示例：

```sql
CREATE TABLE IF NOT EXISTS "__EFMigrationsHistory" (
    "MigrationId" character varying(150) NOT NULL,
    "ProductVersion" character varying(32) NOT NULL,
    CONSTRAINT "PK___EFMigrationsHistory" PRIMARY KEY ("MigrationId")
);

START TRANSACTION;

CREATE TABLE "Products" (
    "Id" integer GENERATED BY DEFAULT AS IDENTITY,
    "Name" character varying(100) NOT NULL,
    "Description" character varying(1000),
    "Price" numeric(18,2) NOT NULL,
    CONSTRAINT "PK_Products" PRIMARY KEY ("Id"),
    CONSTRAINT "CK_Price_NotNegative" CHECK (Price > 0)
);

CREATE UNIQUE INDEX "IX_Products_Name" ON "Products" ("Name");

INSERT INTO "__EFMigrationsHistory" ("MigrationId", "ProductVersion")
VALUES ('20240516095344_Create_Database', '8.0.5');

COMMIT;
```

这个脚本展示了 EF Core 如何追踪迁移历史。`__EFMigrationsHistory` 表记录了所有已应用的迁移，确保每个迁移只会被应用一次。

### 幂等脚本：安全的重复执行

你还可以为 `Script-Migration` 命令指定 `-Idempotent` 参数。这将生成幂等的 SQL 脚本，只应用尚未应用的迁移。当你不确定数据库已应用的最后一个迁移时，这个功能非常有用：

```powershell
Script-Migration -Idempotent
```

幂等脚本的示例：

```sql
CREATE TABLE IF NOT EXISTS "__EFMigrationsHistory" (
    "MigrationId" character varying(150) NOT NULL,
    "ProductVersion" character varying(32) NOT NULL,
    CONSTRAINT "PK___EFMigrationsHistory" PRIMARY KEY ("MigrationId")
);

START TRANSACTION;

DO $EF$
BEGIN
    IF NOT EXISTS(
        SELECT 1 FROM "__EFMigrationsHistory"
        WHERE "MigrationId" = '20240516095344_Create_Database'
    ) THEN
        CREATE TABLE "Products" (
            "Id" integer GENERATED BY DEFAULT AS IDENTITY,
            "Name" character varying(100) NOT NULL,
            "Description" character varying(1000),
            "Price" numeric(18,2) NOT NULL,
            CONSTRAINT "PK_Products" PRIMARY KEY ("Id"),
            CONSTRAINT "CK_Price_NotNegative" CHECK (Price > 0)
        );
    END IF;
END $EF$;

DO $EF$
BEGIN
    IF NOT EXISTS(
        SELECT 1 FROM "__EFMigrationsHistory"
        WHERE "MigrationId" = '20240516095344_Create_Database'
    ) THEN
        CREATE UNIQUE INDEX "IX_Products_Name" ON "Products" ("Name");
    END IF;
END $EF$;

DO $EF$
BEGIN
    IF NOT EXISTS(
        SELECT 1 FROM "__EFMigrationsHistory"
        WHERE "MigrationId" = '20240516095344_Create_Database'
    ) THEN
        INSERT INTO "__EFMigrationsHistory" ("MigrationId", "ProductVersion")
        VALUES ('20240516095344_Create_Database', '8.0.5');
    END IF;
END $EF$;

COMMIT;
```

幂等脚本的优势在于可以安全地重复执行。每个操作都被包裹在条件检查中，只有当迁移尚未应用时才会执行。这使得部署流程更加健壮，特别是在自动化部署场景中。

## 应用迁移：多种方式适应不同场景

EF Core 提供了多种应用迁移的方式，每种方式都有其适用场景和权衡。

### 命令行工具：开发环境的首选

最常见的应用数据库迁移的方法是使用 CLI。你可以使用 `dotnet ef` 工具或 PowerShell 命令。例如，从 PowerShell 执行 `Update-Database` 命令来应用所有待处理的迁移：

```powershell
Update-Database -Migration <ToMigration> -Connection <ConnectionString>
```

命令行工具适合在开发环境中快速迭代，但在生产环境中可能需要更谨慎的方法。

### 通过代码应用迁移：自动化的双刃剑

以下是一个通过代码应用数据库迁移的辅助方法。它使用 `IServiceScope` 来解析 `DbContext` 实例，并调用 `Migrate` 方法：

```csharp
public static void ApplyMigration<TDbContext>(IServiceScope scope)
    where TDbContext : DbContext
{
    using TDbContext context = scope.ServiceProvider
        .GetRequiredService<TDbContext>();

    context.Database.Migrate();
}
```

你可以在应用程序启动时应用迁移：

```csharp
var builder = WebApplication.CreateBuilder(args);

var app = builder.Build();

if (app.Environment.IsDevelopment())
{
    using IServiceScope scope = app.Services.CreateScope();
    ApplyMigration<AppDbContext>(scope);
}

app.Run();
```

这种方法在本地开发和集成测试中搭建数据库时很有用，但**不推荐在生产环境中使用**。原因包括：

- **失败风险**：迁移可能失败，导致应用启动失败
- **并发问题**：多个应用实例同时启动可能导致并发冲突
- **回滚困难**：一旦应用，回滚迁移变得具有挑战性
- **停机时间**：复杂迁移可能需要较长时间，影响服务可用性

### 迁移包（Migration Bundles）：CI/CD 的理想选择

迁移包是可执行文件，可用于应用数据库迁移。它们是独立的，可以从 CI/CD 流水线执行：

```powershell
Bundle-Migration -Connection <ConnectionString>
```

这将创建一个 `efbundle.exe` 文件，我们可以运行它来应用任何待处理的数据库迁移。迁移包的优势在于：

- 不需要在目标环境中安装 .NET SDK 或 EF Core 工具
- 可以轻松集成到现有的部署流程中
- 支持跨平台部署（Windows、Linux、macOS）
- 版本可追溯，便于审计

这使得迁移包成为自动化部署场景的理想选择。

## 其他数据库迁移工具

如果你不想使用 EF Core 迁移，还有其他优秀的工具可供选择：

### FluentMigrator

[FluentMigrator](https://github.com/fluentmigrator/fluentmigrator) 是一个用于 .NET 的迁移框架，提供了流畅的 API 来定义迁移。它支持多种数据库提供程序，并且不依赖于特定的 ORM。这使得它成为不使用 EF Core 的项目的理想选择。

### DbUp

[DbUp](https://github.com/DbUp/DbUp) 是一个轻量级库，用于将 SQL 脚本应用到数据库。它的设计理念是简单明了：你编写标准 SQL 脚本，DbUp 负责跟踪哪些脚本已经执行过。这种方法给予了开发者最大的控制权，但也需要手动编写所有 SQL。

### Grate

[Grate](https://erikbra.github.io/grate/) 是一个依赖 SQL 脚本的自动化数据库部署（变更管理）系统。它提供了一种结构化的方式来组织和应用数据库脚本，支持不同类型的脚本（如运行一次的脚本、每次运行的脚本等）。

### Flyway

[Flyway](https://flywaydb.org/) 是一个开源的数据库迁移工具，简化了数据库架构变更的管理和版本控制。它是跨语言和跨平台的，被广泛应用于 Java 和 .NET 生态系统中。

每个工具都有其特定的优势和适用场景，选择合适的工具取决于项目的具体需求、团队的技术栈以及现有的工作流程。

## EF Core 迁移最佳实践

基于多年使用 EF Core 迁移的经验，以下是一些重要的最佳实践建议：

### 使用有意义的迁移名称

不要使用日期或通用描述来命名迁移。使用清晰、描述性的名称来说明迁移的目的。好的示例包括：`AddProductsTable`、`RenameDescriptionToShortDescription`、`AddPriceIndexToProducts`。这使得理解迁移历史和查找特定变更变得容易得多。

避免使用类似 `Migration1`、`UpdateDatabase` 或 `20231015_Changes` 这样的模糊名称。几个月后，你将很难记起这些迁移究竟做了什么。

### 保持迁移小而专注

避免创建包含多个不相关变更的庞大迁移。较小的迁移更容易审查、测试，并且在出现问题时更容易排查。每个功能或逻辑变更对应一个迁移是理想的做法。

例如，如果你要添加新表并修改现有表的索引，考虑创建两个独立的迁移。这样，如果索引创建出现问题，你可以轻松地回滚该迁移而不影响新表的创建。

### 彻底测试迁移

在将迁移应用到生产环境之前，在开发或预发环境中进行测试。开发和预发环境应尽可能接近生产设置，这将有助于在影响真实用户之前捕获任何意外问题或数据丢失风险。

测试应包括：

- 正向迁移（Up）的执行
- 回滚操作（Down）的验证
- 数据完整性检查
- 性能影响评估（特别是对于大型表的变更）

### 警惕破坏性变更

某些操作（如删除列或表）可能导致不可逆的数据丢失。在将这些变更包含在迁移中之前，仔细考虑其后果。提供迁移数据的方式或创建备份计划。

对于破坏性变更，考虑采用多阶段方法：

1. 第一个迁移：添加新列/表，保留旧的
2. 部署应用程序，同时写入新旧两处
3. 数据迁移脚本：将数据从旧结构复制到新结构
4. 更新应用程序，仅使用新结构
5. 最后的迁移：删除旧的列/表

这种方法虽然需要更多步骤，但大大降低了风险。

### 避免合并冲突

解决 EF 迁移快照的合并冲突可能是一件令人头疼的事情。在创建许多数据库迁移的团队中工作时要注意这一点。建议在创建新迁移之前始终与最新的迁移保持同步，这应该能最大程度地减少产生合并冲突的机会。

如果确实遇到合并冲突，可以考虑：

- 删除冲突的迁移
- 拉取最新的代码
- 重新创建迁移

这通常比手动解决快照文件中的冲突更快、更安全。

### 使用 SQL 脚本进行生产部署

我个人首选的应用迁移方法是使用 SQL 脚本。根据项目的范围和复杂性，可以手动执行或通过自动化工具完成。这种方法的优势包括：

- **完全控制**：可以在执行前审查每一条 SQL 语句
- **灵活性**：可以根据需要调整执行时机和顺序
- **可追溯性**：SQL 脚本可以版本控制，便于审计
- **安全性**：在执行前可以经过多轮审查和批准
- **回滚准备**：可以预先准备回滚脚本

这种方法允许我审查迁移并识别任何潜在问题，在生产环境中提供了额外的安全保障层。

## 总结

EF Core 迁移是管理数据库架构变更的强大工具，它将数据库版本控制与代码版本控制统一起来。通过本文的深入探讨，我们涵盖了从基础的迁移创建到高级的自定义场景，从 SQL 脚本生成到多种应用方式，以及在实际项目中积累的最佳实践经验。

关键要点包括：

- 使用有意义的迁移名称，保持迁移小而专注
- 仔细审查自动生成的迁移，必要时进行自定义
- 利用 SQL 脚本在生产环境中提供额外的安全保障
- 在测试环境中彻底验证迁移，特别是破坏性操作
- 选择适合团队和项目的迁移应用策略

记住，数据库迁移不仅仅是技术工具，更是团队协作和变更管理流程的一部分。建立良好的迁移实践需要时间和经验的积累，但这些投入将在项目的整个生命周期中带来回报。无论选择哪种方法和工具，始终将数据安全和系统稳定性放在首位。
