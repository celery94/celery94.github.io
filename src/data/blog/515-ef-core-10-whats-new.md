---
pubDatetime: 2025-11-04
title: "EF Core 10 新功能详解：向量搜索、JSON 支持与复杂类型的全面革新"
description: "深入探讨 Entity Framework Core 10 的重大更新，包括原生向量搜索支持、全新的 JSON 数据类型、复杂类型增强、LINQ 查询优化以及安全性改进，为构建现代 AI 驱动的应用程序提供强大支持。"
tags: [".NET", "EF Core", "Entity Framework", "Azure SQL", "Vector Search", "AI", "Database"]
slug: ef-core-10-whats-new
source: https://learn.microsoft.com/en-us/ef/core/what-is-new/ef-core-10.0/whatsnew
---

# EF Core 10 新功能详解：向量搜索、JSON 支持与复杂类型的全面革新

## 引言

Entity Framework Core 10（EF10）是微软在 .NET 10 生态系统中推出的最新一代对象关系映射（ORM）框架，计划于 2025 年 11 月正式发布。作为 EF Core 9 的后续版本，EF10 带来了一系列突破性的功能更新，特别是在支持现代 AI 工作负载、文档建模和查询性能优化方面取得了重大进展。

EF10 的核心亮点包括对 Azure SQL Database 和 SQL Server 2025 新增的 **vector 数据类型**的原生支持，这为构建语义搜索和检索增强生成（RAG）等 AI 应用场景提供了强大的基础设施。此外，框架还全面拥抱了 SQL Server 2025 引入的原生 **json 数据类型**，显著提升了 JSON 数据的存储效率和查询安全性。

本文将从数据库提供程序特性、复杂类型建模、LINQ 翻译改进、ExecuteUpdate 增强以及安全性提升等多个维度，全面解析 EF Core 10 的技术革新及其实际应用价值。

## Azure SQL 与 SQL Server 的新特性

### 原生向量搜索支持

EF Core 10 最令人瞩目的功能之一是对向量数据类型的完整支持。向量（vector）在机器学习和 AI 领域被用来表示数据的语义含义，通过将文本、图像等非结构化数据转换为高维向量，可以实现高效的相似性搜索，这是语义搜索、推荐系统和 RAG 应用的核心技术。

**配置向量属性**

要使用向量类型，首先需要在实体类中添加 `SqlVector<float>` 类型的属性，并通过 Data Annotations 或 Fluent API 指定向量维度：

```csharp
// 使用 Data Annotations
public class Blog
{
    public int Id { get; set; }
    public string Name { get; set; }
    
    [Column(TypeName = "vector(1536)")]
    public SqlVector<float> Embedding { get; set; }
}

// 或使用 Fluent API
protected override void OnModelCreating(ModelBuilder modelBuilder)
{
    modelBuilder.Entity<Blog>()
        .Property(b => b.Embedding)
        .HasColumnType("vector(1536)");
}
```

这里的维度值（1536）需要与所使用的嵌入模型匹配。例如，OpenAI 的 `text-embedding-ada-002` 模型生成的向量维度为 1536。

**生成和存储嵌入向量**

向量的生成通常通过外部服务完成，.NET 的 `Microsoft.Extensions.AI` 库提供了 `IEmbeddingGenerator` 抽象接口，支持多种嵌入生成提供商：

```csharp
// 配置嵌入生成器
IEmbeddingGenerator<string, Embedding<float>> embeddingGenerator = 
    /* 配置你选择的嵌入生成提供商，如 Azure OpenAI、OpenAI 等 */;

// 为文本生成嵌入向量
var textToVectorize = "深度学习与自然语言处理的最新进展";
var embeddingVector = await embeddingGenerator.GenerateVectorAsync(textToVectorize);

// 创建实体并保存到数据库
context.Blogs.Add(new Blog
{
    Name = "AI技术博客",
    Embedding = new SqlVector<float>(embeddingVector)
});

await context.SaveChangesAsync();
```

**执行向量相似性搜索**

EF Core 10 通过 `EF.Functions.VectorDistance()` 方法支持向量相似性搜索。该方法支持多种距离度量算法，包括余弦相似度（cosine）、欧几里得距离（euclidean）和点积（dot product）：

```csharp
// 用户查询文本
var userQuery = "如何实现高性能的数据库查询？";
var queryVector = await embeddingGenerator.GenerateVectorAsync(userQuery);
var sqlVector = new SqlVector<float>(queryVector);

// 查找最相似的前 3 篇博客
var topSimilarBlogs = await context.Blogs
    .OrderBy(b => EF.Functions.VectorDistance("cosine", b.Embedding, sqlVector))
    .Take(3)
    .Select(b => new { b.Name, b.Id })
    .ToListAsync();
```

这个查询会生成如下 SQL：

```sql
SELECT TOP(3) [b].[Name], [b].[Id]
FROM [Blogs] AS [b]
ORDER BY VECTOR_DISTANCE('cosine', [b].[Embedding], @sqlVector)
```

**向量搜索的应用场景**

向量搜索在以下场景中具有重要价值：

1. **语义搜索引擎**：相比传统的关键词匹配，向量搜索能理解查询的语义，返回语义相关的结果
2. **推荐系统**：根据用户历史行为生成的嵌入向量，推荐相似的内容或产品
3. **检索增强生成（RAG）**：为大型语言模型提供相关的上下文信息，提升生成质量
4. **图像相似性搜索**：基于图像特征向量，查找视觉上相似的图片
5. **异常检测**：识别与正常模式距离较远的异常数据点

### JSON 数据类型的原生支持

SQL Server 2025 和 Azure SQL Database 引入了原生的 `json` 数据类型，相比之前将 JSON 数据存储在 `nvarchar(max)` 列中的方式，新类型提供了更高的存储效率、更好的查询性能和更强的类型安全性。

**自动采用 JSON 类型**

当使用 `UseAzureSql()` 配置 EF Core 或将兼容性级别设置为 170 及以上（对应 SQL Server 2025）时，EF Core 会自动为原始集合和复杂类型使用 `json` 数据类型：

```csharp
public class Blog
{
    public int Id { get; set; }
    public string Name { get; set; }
    
    // 原始集合 - 将映射为 json 类型
    public string[] Tags { get; set; }
    
    // 复杂类型 - 配置为 JSON 映射
    public required BlogDetails Details { get; set; }
}

public class BlogDetails
{
    public string? Description { get; set; }
    public int Viewers { get; set; }
    public DateTime CreatedDate { get; set; }
}

protected override void OnModelCreating(ModelBuilder modelBuilder)
{
    modelBuilder.Entity<Blog>()
        .ComplexProperty(b => b.Details, b => b.ToJson());
}
```

EF Core 会生成以下表结构：

```sql
CREATE TABLE [Blogs] (
    [Id] int NOT NULL IDENTITY,
    [Name] nvarchar(max) NOT NULL,
    [Tags] json NOT NULL,
    [Details] json NOT NULL,
    CONSTRAINT [PK_Blogs] PRIMARY KEY ([Id])
);
```

**查询 JSON 列**

EF Core 的 LINQ 查询可以直接访问 JSON 文档中的属性，框架会将其翻译为高效的 SQL 查询：

```csharp
// 查询浏览量超过 1000 的博客
var popularBlogs = await context.Blogs
    .Where(b => b.Details.Viewers > 1000)
    .OrderByDescending(b => b.Details.Viewers)
    .Select(b => new 
    { 
        b.Name, 
        b.Details.Description,
        b.Details.Viewers 
    })
    .ToListAsync();
```

生成的 SQL 利用 SQL Server 2025 新增的 `JSON_VALUE()` 函数和 `RETURNING` 子句：

```sql
SELECT [b].[Name], 
       JSON_VALUE([b].[Details], '$.Description' RETURNING nvarchar(max)),
       JSON_VALUE([b].[Details], '$.Viewers' RETURNING int)
FROM [Blogs] AS [b]
WHERE JSON_VALUE([b].[Details], '$.Viewers' RETURNING int) > 1000
ORDER BY JSON_VALUE([b].[Details], '$.Viewers' RETURNING int) DESC
```

**迁移注意事项**

如果现有应用程序已经使用 `nvarchar(max)` 存储 JSON 数据，升级到 EF Core 10 后，第一次迁移会自动将这些列转换为 `json` 类型。如果需要保持旧的列类型，可以显式配置：

```csharp
protected override void OnModelCreating(ModelBuilder modelBuilder)
{
    // 显式使用 nvarchar(max) 而非 json
    modelBuilder.Entity<Blog>()
        .ComplexProperty(b => b.Details)
        .ToJson()
        .HasColumnType("nvarchar(max)");
}
```

### 自定义默认约束名称

在数据库设计中，为约束指定明确的名称有助于提高可维护性，特别是在大型项目中。EF Core 10 允许为默认约束（Default Constraint）指定自定义名称：

```csharp
protected override void OnModelCreating(ModelBuilder modelBuilder)
{
    // 为单个属性指定默认约束名称
    modelBuilder.Entity<Post>()
        .Property(p => p.CreatedDate)
        .HasDefaultValueSql("GETDATE()", "DF_Post_CreatedDate");
    
    // 全局启用命名默认约束
    modelBuilder.UseNamedDefaultConstraints();
}
```

需要注意的是，如果已有迁移历史，启用全局命名后，下一次迁移将重命名模型中的所有默认约束，这可能会产生大量的迁移操作。

## Azure Cosmos DB for NoSQL 的增强

### 全文搜索支持

Azure Cosmos DB 现在支持全文搜索功能，这为在 NoSQL 文档数据库中执行文本搜索提供了原生支持。全文搜索可以与向量搜索结合使用，提升 AI 应用的检索精度。

**配置全文搜索索引**

```csharp
public class Blog
{
    public int Id { get; set; }
    public string Name { get; set; }
    public string Contents { get; set; }
}

protected override void OnModelCreating(ModelBuilder modelBuilder)
{
    modelBuilder.Entity<Blog>(b =>
    {
        // 启用全文搜索
        b.Property(x => x.Contents).EnableFullTextSearch();
        // 创建全文索引
        b.HasIndex(x => x.Contents).IsFullTextIndex();
    });
}
```

**使用全文搜索函数**

EF Core 10 提供了多个全文搜索函数：

```csharp
// FullTextContains - 检查是否包含指定词汇
var cosmosBlogs = await context.Blogs
    .Where(x => EF.Functions.FullTextContains(x.Contents, "cosmos database"))
    .ToListAsync();

// FullTextContainsAll - 必须包含所有指定词汇
var preciseResults = await context.Blogs
    .Where(x => EF.Functions.FullTextContainsAll(x.Contents, "azure", "sql", "nosql"))
    .ToListAsync();

// FullTextContainsAny - 包含任意一个指定词汇
var broadResults = await context.Blogs
    .Where(x => EF.Functions.FullTextContainsAny(x.Contents, "mongodb", "cosmos", "dynamodb"))
    .ToListAsync();

// FullTextScore - 获取相关性评分
var rankedResults = await context.Blogs
    .OrderByDescending(x => EF.Functions.FullTextScore(x.Contents, "machine learning"))
    .Take(10)
    .ToListAsync();
```

### 混合搜索（Hybrid Search）

混合搜索是全文搜索和向量搜索的结合，通过 Reciprocal Rank Fusion（RRF）算法融合两种检索结果的排名，提供更准确的搜索体验：

```csharp
// 用户查询
var userQuery = "云数据库性能优化";
float[] queryVector = await embeddingGenerator.GenerateVectorAsync(userQuery);

// 执行混合搜索
var hybridResults = await context.Blogs
    .OrderBy(x => EF.Functions.Rrf(
        EF.Functions.FullTextScore(x.Contents, "性能 优化 数据库"),
        EF.Functions.VectorDistance(x.Vector, queryVector)))
    .Take(10)
    .ToListAsync();
```

还可以为不同的搜索结果分配权重，例如让向量搜索的权重更高：

```csharp
var weightedHybrid = await context.Blogs
    .OrderBy(x => EF.Functions.Rrf(
        new[]
        {
            EF.Functions.FullTextScore(x.Contents, "性能优化"),
            EF.Functions.VectorDistance(x.Vector, queryVector)
        },
        weights: new[] { 1, 2 }))  // 向量搜索权重为全文搜索的两倍
    .Take(10)
    .ToListAsync();
```

### 向量搜索正式发布

在 EF Core 9 中作为实验性功能引入的向量搜索，在 EF Core 10 中正式转为稳定功能，并进行了以下改进：

1. **支持更多场景**：现在可以为拥有引用实体（owned reference entities）上定义的向量属性生成容器
2. **API 重命名**：使用更清晰的方法名称
   - `IsVectorProperty()` 配置向量属性
   - `IsVectorIndex()` 配置向量索引

```csharp
protected override void OnModelCreating(ModelBuilder modelBuilder)
{
    modelBuilder.Entity<Blog>(b =>
    {
        // 配置向量属性（指定距离函数和维度）
        b.Property(x => x.Vector)
            .IsVectorProperty(DistanceFunction.Cosine, dimensions: 1536);
        
        // 配置向量索引（指定索引类型）
        b.HasIndex(x => x.Vector)
            .IsVectorIndex(VectorIndexType.Flat);
    });
}
```

### 改进的模型演化体验

在之前的版本中，向 Cosmos DB 实体添加新的必需属性会导致 EF Core 无法反序列化旧文档（因为缺少新属性的值）。EF Core 10 改进了这一体验，当文档中缺少必需属性的值时，EF 会自动使用默认值进行物化，而不是抛出异常。

这大大简化了数据库模式演化过程，无需先将属性标记为可选、手动更新数据、再改回必需的繁琐流程。

## 复杂类型的全面革新

复杂类型（Complex Types）是 EF Core 用于建模无独立标识的值对象的机制。与实体类型不同，复杂类型始终作为其容器实体的一部分存在，可以映射为表中的额外列（表分割）或 JSON 列。

### 表分割（Table Splitting）

表分割允许将复杂类型的属性映射为主表中的额外列，避免使用外键和 JOIN 操作：

```csharp
public class Customer
{
    public int Id { get; set; }
    public string Name { get; set; }
    
    // 必需的复杂类型
    public Address ShippingAddress { get; set; }
    
    // 可选的复杂类型（EF Core 10 新增）
    public Address? BillingAddress { get; set; }
}

public class Address
{
    public required string Street { get; set; }
    public required string City { get; set; }
    public required string PostalCode { get; set; }
    public int StreetNumber { get; set; }
}

protected override void OnModelCreating(ModelBuilder modelBuilder)
{
    modelBuilder.Entity<Customer>(b =>
    {
        b.ComplexProperty(c => c.ShippingAddress);
        b.ComplexProperty(c => c.BillingAddress);
    });
}
```

生成的表结构：

```sql
CREATE TABLE [Customers] (
    [Id] int NOT NULL IDENTITY,
    [Name] nvarchar(max) NOT NULL,
    [BillingAddress_City] nvarchar(max) NOT NULL,
    [BillingAddress_PostalCode] nvarchar(max) NOT NULL,
    [BillingAddress_Street] nvarchar(max) NOT NULL,
    [BillingAddress_StreetNumber] int NOT NULL,
    [ShippingAddress_City] nvarchar(max) NOT NULL,
    [ShippingAddress_PostalCode] nvarchar(max) NOT NULL,
    [ShippingAddress_Street] nvarchar(max) NOT NULL,
    [ShippingAddress_StreetNumber] int NOT NULL,
    CONSTRAINT [PK_Customers] PRIMARY KEY ([Id])
);
```

### JSON 映射

复杂类型也可以映射为 JSON 列，这在处理具有嵌套结构的数据时特别有用：

```csharp
protected override void OnModelCreating(ModelBuilder modelBuilder)
{
    modelBuilder.Entity<Customer>(b =>
    {
        b.ComplexProperty(c => c.ShippingAddress, c => c.ToJson());
        b.ComplexProperty(c => c.BillingAddress, c => c.ToJson());
    });
}
```

生成的表结构：

```sql
CREATE TABLE [Customers] (
    [Id] int NOT NULL IDENTITY,
    [Name] nvarchar(max) NOT NULL,
    [ShippingAddress] json NOT NULL,
    [BillingAddress] json NULL,
    CONSTRAINT [PK_Customers] PRIMARY KEY ([Id])
);
```

### 结构体（Struct）支持

EF Core 10 支持将 .NET 结构体映射为复杂类型，这与复杂类型的值语义完美契合：

```csharp
public struct Address
{
    public required string Street { get; set; }
    public required string City { get; set; }
    public required string ZipCode { get; set; }
}
```

注意：目前不支持结构体集合。

### 复杂类型 vs 拥有实体类型

虽然拥有实体类型（Owned Entity Types）也可以实现表分割和 JSON 映射，但它们存在一些语义上的限制：

**问题 1：不能重复引用**

```csharp
// 使用拥有实体类型会失败
var customer = await context.Customers.SingleAsync(c => c.Id == someId);
customer.BillingAddress = customer.ShippingAddress; // ERROR: 同一实体不能被引用多次

// 使用复杂类型则正常工作（值拷贝）
var customer = await context.Customers.SingleAsync(c => c.Id == someId);
customer.BillingAddress = customer.ShippingAddress; // OK: 属性值被复制
await context.SaveChangesAsync();
```

**问题 2：比较语义不同**

```csharp
// 拥有实体类型按标识比较（可能不符合预期）
var sameAddressCustomers = await context.Customers
    .Where(c => c.ShippingAddress == c.BillingAddress)
    .ToListAsync(); // 比较实体标识

// 复杂类型按内容比较（符合预期）
var sameAddressCustomers = await context.Customers
    .Where(c => c.ShippingAddress == c.BillingAddress)
    .ToListAsync(); // 比较属性值
```

**问题 3：ExecuteUpdate 支持**

复杂类型完全支持 `ExecuteUpdate` 操作，而拥有实体类型不支持批量赋值。

因此，对于表分割和 JSON 映射场景，建议使用复杂类型而非拥有实体类型。

## LINQ 与 SQL 翻译的优化

### 参数化集合的改进翻译

参数化集合查询一直是关系型数据库的难题。考虑以下查询：

```csharp
int[] ids = [1, 2, 3];
var blogs = await context.Blogs
    .Where(b => ids.Contains(b.Id))
    .ToListAsync();
```

**EF Core 8.0 之前的方式**（内联常量）

```sql
SELECT [b].[Id], [b].[Name]
FROM [Blogs] AS [b]
WHERE [b].[Id] IN (1, 2, 3)
```

这种方式的问题是不同的集合会生成不同的 SQL，导致数据库查询计划缓存失效。

**EF Core 8.0-9.0 的方式**（JSON 数组参数）

```sql
@__ids_0='[1,2,3]'

SELECT [b].[Id], [b].[Name]
FROM [Blogs] AS [b]
WHERE [b].[Id] IN (
    SELECT [i].[value]
    FROM OPENJSON(@__ids_0) WITH ([value] int '$') AS [i]
)
```

这种方式解决了缓存问题，但数据库查询优化器无法获知集合的基数信息，可能选择不合适的执行计划。

**EF Core 10 的新方式**（多标量参数）

```sql
SELECT [b].[Id], [b].[Name]
FROM [Blogs] AS [b]
WHERE [b].[Id] IN (@ids1, @ids2, @ids3)
```

这种方式兼顾了缓存和查询优化器的需求。EF Core 还会对参数列表进行"填充"，例如 8 个值的集合会生成 10 个参数（最后两个重复第 8 个值），以减少不同 SQL 的数量。

**自定义翻译策略**

EF Core 10 允许全局或按查询控制翻译策略：

```csharp
// 全局配置
protected override void OnConfiguring(DbContextOptionsBuilder optionsBuilder)
    => optionsBuilder
        .UseSqlServer("<连接字符串>", 
            o => o.UseParameterizedCollectionMode(ParameterTranslationMode.Constant));

// 按查询配置
var blogs = await context.Blogs
    .Where(b => EF.Constant(ids).Contains(b.Id))  // 强制使用常量内联
    .ToListAsync();
```

### LeftJoin 和 RightJoin 操作符支持

.NET 10 引入了 LINQ 的 `LeftJoin` 和 `RightJoin` 操作符，EF Core 10 提供了完整支持：

```csharp
var query = context.Students
    .LeftJoin(
        context.Departments,
        student => student.DepartmentID,
        department => department.ID,
        (student, department) => new 
        { 
            student.FirstName,
            student.LastName,
            Department = department.Name ?? "[无所属部门]"
        });
```

这比之前使用 `SelectMany`、`GroupJoin` 和 `DefaultIfEmpty` 的组合简洁得多。

### 分割查询的一致性排序

分割查询（Split Query）可以避免 JOIN 导致的笛卡尔积性能问题，但在 EF Core 10 之前可能存在数据一致性问题。EF Core 10 确保子查询的排序包含所有必要的列：

```csharp
var blogs = await context.Blogs
    .AsSplitQuery()
    .Include(b => b.Posts)
    .OrderBy(b => b.Name)
    .Take(2)
    .ToListAsync();
```

**EF Core 10 生成的 SQL**（正确）

```sql
-- 查询 Blogs
SELECT TOP(@__p_0) [b].[Id], [b].[Name]
FROM [Blogs] AS [b]
ORDER BY [b].[Name], [b].[Id]

-- 查询 Posts
SELECT [p].[Id], [p].[BlogId], [p].[Title], [b0].[Id]
FROM (
    SELECT TOP(@__p_0) [b].[Id], [b].[Name]
    FROM [Blogs] AS [b]
    ORDER BY [b].[Name], [b].[Id]  -- 包含 Id 确保一致性
) AS [b0]
INNER JOIN [Post] AS [p] ON [b0].[Id] = [p].[BlogId]
ORDER BY [b0].[Name], [b0].[Id]
```

### 其他查询改进

EF Core 10 还包含大量的查询翻译改进：

- 支持 `DateOnly.ToDateTime()`、`DateOnly.DayNumber` 等日期函数翻译
- 支持 `DatePart.Microsecond` 和 `DatePart.Nanosecond` 参数
- SQL Server 上将 `COALESCE` 翻译为更高效的 `ISNULL`
- SQLite 上支持 `decimal` 类型的 `MAX`/`MIN`/`ORDER BY` 操作
- 修复了 `DefaultIfEmpty` 在多种场景下的翻译问题
- 优化了连续多个 `LIMIT` 操作
- 简化参数名称（如从 `@__city_0` 改为 `@city`）

## ExecuteUpdate 对 JSON 列的支持

EF Core 10 允许在 `ExecuteUpdate` 操作中更新 JSON 列中的属性，实现高效的批量更新：

```csharp
// 为所有博客的浏览量加 1
await context.Blogs.ExecuteUpdateAsync(s => 
    s.SetProperty(b => b.Details.Views, b => b.Details.Views + 1));
```

在 SQL Server 2025 上生成的 SQL 使用了新的 `modify` 函数：

```sql
UPDATE [b]
SET [Details].modify('$.Views', JSON_VALUE([b].[Details], '$.Views' RETURNING int) + 1)
FROM [Blogs] AS [b]
```

注意：此功能仅支持复杂类型映射到 JSON，不支持拥有实体类型。

## 命名查询过滤器

EF Core 的全局查询过滤器（Global Query Filters）用于实现软删除、多租户等模式。EF Core 10 引入了命名查询过滤器，允许定义多个过滤器并选择性地禁用：

```csharp
protected override void OnModelCreating(ModelBuilder modelBuilder)
{
    modelBuilder.Entity<Blog>()
        .HasQueryFilter("SoftDeletionFilter", b => !b.IsDeleted)
        .HasQueryFilter("TenantFilter", b => b.TenantId == currentTenantId);
}

// 仅忽略软删除过滤器，保留租户过滤器
var allBlogsIncludingDeleted = await context.Blogs
    .IgnoreQueryFilters(["SoftDeletionFilter"])
    .ToListAsync();
```

这个特性由社区贡献者 [@bittola](https://github.com/bittola) 提供。

## ExecuteUpdateAsync 接受非表达式 Lambda

在 EF Core 10 之前，`ExecuteUpdateAsync` 的 setter 参数必须是表达式树，这使得动态构建更新操作非常困难。EF Core 10 支持普通 lambda：

```csharp
await context.Blogs.ExecuteUpdateAsync(s =>
{
    s.SetProperty(b => b.Views, 8);
    
    if (nameChanged)
    {
        s.SetProperty(b => b.Name, "新名称");
    }
    
    if (descriptionChanged)
    {
        s.SetProperty(b => b.Description, "新描述");
    }
});
```

这个改进大大简化了条件更新的编写，感谢 [@aradalvand](https://github.com/aradalvand) 的提案和推动。

## 安全性相关改进

### 默认隐藏内联常量

EF Core 10 在日志中默认隐藏内联到 SQL 中的常量值，以防止敏感信息泄露：

```csharp
Task<List<User>> GetUsersByRoles(BlogContext context, string[] roles)
    => context.Users
        .Where(b => EF.Constant(roles).Contains(b.Role))
        .ToListAsync();
```

**记录的日志 SQL**（敏感数据已隐藏）

```sql
SELECT [u].[Id], [u].[Role]
FROM [Users] AS [u]
WHERE [u].[Role] IN (?, ?)
```

**实际发送的 SQL**（包含真实值）

```sql
SELECT [u].[Id], [u].[Role]
FROM [Users] AS [u]
WHERE [u].[Role] IN (N'Administrator', N'Manager')
```

可以通过 `EnableSensitiveDataLogging()` 启用完整日志。

### 原始 SQL API 的字符串拼接警告

EF Core 10 新增了分析器，当在原始 SQL API 中检测到字符串拼接时会发出警告，帮助防止 SQL 注入漏洞：

```csharp
// 分析器会警告此代码存在 SQL 注入风险
var users = context.Users.FromSqlRaw("SELECT * FROM Users WHERE [" + fieldName + "] IS NULL");
```

如果 `fieldName` 已经过验证或来自可信源，可以抑制警告。

## 其他改进

- **迁移事务策略调整**：撤销了 EF Core 9 中将所有迁移包含在单个事务中的更改，以解决某些场景下的问题
- **Azure Data Explorer 兼容性**：使 SQL Server 脚手架工具与 Azure Data Explorer 兼容（由 [@barnuri](https://github.com/barnuri) 贡献）
- **作用域选项关联**：将 `DatabaseRoot` 与作用域选项实例而非单例选项关联（由 [@koenigst](https://github.com/koenigst) 贡献）
- **LoadExtension 改进**：改进 SQLite 的 `LoadExtension` 在 `dotnet run` 和以 `lib*` 命名的库中的工作方式（由 [@krwq](https://github.com/krwq) 贡献）
- **AsyncLocal 性能优化**：优化 `AsyncLocal` 的使用以提升延迟加载性能（由 [@henriquewr](https://github.com/henriquewr) 贡献）

## 总结与展望

Entity Framework Core 10 代表了微软在 ORM 领域的重大技术进步，特别是在支持现代 AI 工作负载方面。原生向量搜索支持为构建语义搜索、推荐系统和 RAG 应用提供了坚实的基础设施，而 JSON 数据类型的全面拥抱则显著提升了文档建模的性能和安全性。

复杂类型的增强使得值对象建模更加自然和高效，LINQ 查询翻译的持续优化确保了生成的 SQL 既高效又智能。`ExecuteUpdate` 对 JSON 列的支持和命名查询过滤器等新特性进一步扩展了框架的应用边界。

从架构角度看，EF Core 10 的设计体现了以下几个趋势：

1. **拥抱 AI 生态**：向量搜索的原生支持标志着传统 ORM 框架开始为 AI 应用场景提供一等公民支持
2. **文档与关系的融合**：JSON 类型和复杂类型的增强体现了关系型数据库向半结构化数据建模能力的演进
3. **性能与安全并重**：查询优化和安全性改进表明框架在追求性能的同时不忘基础安全
4. **社区驱动创新**：大量社区贡献特性证明了开源协作在推动技术进步中的重要作用

对于开发者而言，EF Core 10 不仅是一个 ORM 升级，更是一个构建下一代智能应用的技术平台。无论是实现企业级搜索引擎、构建个性化推荐系统，还是开发基于大型语言模型的应用，EF Core 10 都能提供强大的数据访问支持。

随着 .NET 10 和 EF Core 10 的正式发布，我们期待看到更多创新应用场景的出现，也期待社区能继续为这个优秀的开源项目贡献力量。

## 参考资源

- [EF Core 10 官方发布说明](https://learn.microsoft.com/en-us/ef/core/what-is-new/ef-core-10.0/whatsnew)
- [SQL Server 向量搜索文档](https://learn.microsoft.com/en-us/sql/t-sql/data-types/vector-data-type)
- [Azure Cosmos DB 全文搜索](https://learn.microsoft.com/en-us/azure/cosmos-db/gen-ai/full-text-search)
- [Microsoft.Extensions.AI 文档](https://learn.microsoft.com/en-us/dotnet/ai/microsoft-extensions-ai)
- [EF Core GitHub 仓库](https://github.com/dotnet/efcore)
