---
pubDatetime: 2024-09-09
tags: []
source: https://www.milanjovanovic.tech/blog/5-ef-core-features-you-need-to-know
author: Milan Jovanović
title: 你需要知道的5个EF Core特性
description: EF Core 非常强大，了解一些关键功能可以为你节省大量时间和挫折。我精心挑选了五个你真的需要知道的重要功能。
---

# 你需要知道的5个EF Core特性

> ## 摘要
>
> EF Core 非常强大，了解一些关键功能可以为你节省大量时间和挫折。我精心挑选了五个你真的需要知道的重要功能。

---

好吧，老实说。我们每个人都有许多事情要做，深入研究EF Core的每个细节可能不是你的优先事项。

但事实是：EF Core非常强大，了解一些关键功能可以为你节省大量时间和挫折。

所以，我不会向你轰炸所有EF Core功能。

相反，我挑选了五个你真的需要知道的关键功能。

我们将探讨：

- **Query Splitting** - 你数据库的新朋友
- **Bulk Updates and Deletes** - 高效率的代名词
- **Raw SQL Queries** - 在你需要“走自己的路”时
- **Query Filters** - 保持干净和整洁
- **Eager Loading** - 因为懒加载有时并不那么好

让我们开始吧！

## Query Splitting

[**Query splitting**](https://www.milanjovanovic.tech/blog/how-to-improve-performance-with-ef-core-query-splitting) 是你不常需要的那些EF Core功能之一，直到有一天你真的需要它。Query splitting在你急切加载多个集合的情况下非常有用。它帮助我们避免 [笛卡尔爆炸](https://learn.microsoft.com/en-us/ef/core/performance/efficient-querying#avoid-cartesian-explosion-when-loading-related-entities) 问题。

假设我们想检索含有所有团队和员工的一个部门。我们可能会写一个这样的查询：

```csharp
Department department =
    context.Departments
        .Include(d => d.Teams)
        .Include(d => d.Employees)
        .Where(d => d.Id == departmentId)
        .First();
```

这会翻译成一个包含两个JOIN的SQL查询。但是，由于这些 `JOIN`语句是在同一级别上，数据库将返回一个 _笛卡尔积_。每一行`Teams`将与每一行`Employees`相连接。在这种情况下，数据库会返回很多行，严重影响性能。

以下是我们如何使用query splitting来避免这些性能问题：

```csharp
Department department =
    context.Departments
        .Include(d => d.Teams)
        .Include(d => d.Employees)
        .Where(d => d.Id == departmentId)
        .AsSplitQuery()
        .First();
```

使用 `AsSplitQuery`，EF Core 将为每个集合导航执行一个额外的SQL查询。

但是，要注意不要过度使用query splitting。我使用拆分查询是在我 _测量_ 到它们的性能始终优于其他方法的时候。

拆分查询会增加数据库的往返次数，如果数据库延迟较高，可能会更慢。多个SQL查询之间也没有一致性保证。

## Bulk Updates and Deletes

EF Core 7 添加了两个用于执行 [**批量更新和删除**](https://www.milanjovanovic.tech/blog/how-to-use-the-new-bulk-update-feature-in-ef-core-7) 的新API，`ExecuteUpdate` 和 `ExecuteDelete`。它们允许你在一次与数据库的往返中高效地更新大量行。

这是一个实际的例子。

公司决定给所有“销售”部门的员工加薪5%。如果没有批量更新，我们可能会遍历每个员工并分别更新他们的工资：

```csharp
var salesEmployees = context.Employees
    .Where(e => e.Department == "Sales")
    .ToList();

foreach (var employee in salesEmployees)
{
    employee.Salary *= 1.05m;
}

context.SaveChanges();
```

这种方法涉及多次数据库往返，对于大数据集来说效率较低。

我们可以使用 `ExecuteUpdate` 在一次往返中实现相同的功能：

```csharp
context.Employees
    .Where(e => e.Department == "Sales")
    .ExecuteUpdate(s => s.SetProperty(e => e.Salary, e => e.Salary * 1.05m));
```

这执行了一个单一的SQL `UPDATE` 语句，直接在数据库中修改工资，无需将实体加载到内存中，从而提高了性能。

还有另一个例子。假设一个电子商务平台想删除所有超过一年未使用的购物车。

可以使用 `ExecuteDelete` 来实现：

```csharp
context.Carts
    .Where(o => o.CreatedOn < DateTime.Now.AddYears(-1))
    .ExecuteDelete();
```

这会产生一个单一的SQL `DELETE` 语句，直接从数据库中删除旧的购物车。

但是，批量更新绕过了EF变更跟踪器。这可能会带来一些问题，我在这篇文章中写到过 [**批量更新的注意事项**](https://www.milanjovanovic.tech/blog/what-you-need-to-know-about-ef-core-bulk-updates)。

## Raw SQL Queries

EF Core 8 添加了一个新功能，使我们可以使用原生SQL查询未映射的类型。

假设我们想从数据库视图、存储过程或不直接对应任何实体类的表中检索数据。

例如，我们想检索每个产品的销售汇总。通过EF Core 8，我们可以定义一个简单的 `ProductSummary` 类来表示结果集的结构，并直接查询它：

```csharp
public class ProductSummary
{
    public int ProductId { get; set; }
    public string ProductName { get; set; }
    public decimal TotalSales { get; set; }
}

var productSummaries = await context.Database
    .SqlQuery<ProductSummary>(
        @$"""
        SELECT p.ProductId, p.ProductName, SUM(oi.Quantity * oi.UnitPrice) AS TotalSales
        FROM Products p
        JOIN OrderItems oi ON p.ProductId = oi.ProductId
        WHERE p.CategoryId = {categoryId}
        GROUP BY p.ProductId, p.ProductName
        """)
    .ToListAsync();
```

`SqlQuery` 方法返回一个 `IQueryable`，允许你使用LINQ组合原生SQL查询。这将原生SQL的强大功能与LINQ的表达能力相结合。

记住使用参数化查询以防止SQL注入漏洞。`SqlQuery` 方法接受一个 `FormattableString`，这意味着你可以安全地使用插值字符串。每个参数都会被转换为SQL参数。

你可以在这篇文章中了解更多关于 [**原生SQL查询**](https://www.milanjovanovic.tech/blog/ef-core-raw-sql-queries) 的信息。

## Query Filters

[**Query filters**](https://www.milanjovanovic.tech/blog/how-to-use-global-query-filters-in-ef-core) 就像可重复使用的 `WHERE` 子句，你可以将它们应用到你的实体上。这些过滤器会自动添加到LINQ查询中，每当你检索相应类型的实体时。这可以让你避免在应用程序的多个地方重复编写相同的过滤逻辑。

Query Filters 通常用于以下场景：

- [**软删除**](https://www.milanjovanovic.tech/blog/implementing-soft-delete-with-ef-core)：过滤掉标记为已删除的记录。
- [**多租户**](https://www.milanjovanovic.tech/blog/multi-tenant-applications-with-ef-core)：根据当前租户过滤数据。
- 行级别安全：根据用户角色或权限限制对某些记录的访问。

在一个多租户应用程序中，你通常需要根据当前租户过滤数据。Query filters 可以让我们轻松处理这个需求：

```csharp
public class Product
{
    public int Id { get; set; }
    public string Name { get; set; }
    // 将产品与租户关联
    public int TenantId { get; set; }
}

protected override void OnModelCreating(ModelBuilder modelBuilder)
{
    // 当前 TenantId 基于当前请求/上下文设置
    modelBuilder.Entity<Product>().HasQueryFilter(p => p.TenantId == _currentTenantId);
}

// 现在，查询会自动根据租户进行过滤：
var productsForCurrentTenant = context.Products.ToList();
```

在同一个实体上配置多个 query filters 时，只有最后一个会生效。你可以使用 `&&` (AND) 和 `||` (OR) 操作符组合多个 query filters。

当需要时，你可以使用 `IgnoreQueryFilters` 绕过特定查询中的过滤器。

## Eager Loading

Eager Loading 是EF Core中的一个功能，它允许你在一个数据库查询中加载相关实体。通过在一个查询中获取所有必要的数据，你可以提高应用程序性能。这在处理复杂对象图或懒加载会导致许多小而低效的查询时尤其适用。

这是一个 `VerifyEmail` 用例。我们想加载一个 `EmailVerificationToken` 并使用 `Include` 方法急切加载一个 `User`，因为我们想同时修改这两个实体。

```csharp
internal sealed class VerifyEmail(AppDbContext context)
{
    public async Task<bool> Handle(Guid tokenId)
    {
        EmailVerificationToken? token = await context.EmailVerificationTokens
            .Include(e => e.User)
            .FirstOrDefaultAsync(e => e.Id == tokenId);

        if (token is null || token.ExpiresOnUtc < DateTime.UtcNow || token.User.EmailVerified)
        {
            return false;
        }

        token.User.EmailVerified = true;

        context.EmailVerificationTokens.Remove(token);

        await context.SaveChangesAsync();

        return true;
    }
}
```

EF Core 将生成一个包含 `EmailVerificationToken` 和 `User` 表连接的SQL查询，一次性检索所有必要的数据。

Eager loading（以及我们之前提到的 query splitting）并不是万灵药。如果你只需要从相关实体中获取特定属性，考虑使用 projections 以避免获取不必要的数据。

## 总结

这就是了！五个你不能不知道的EF Core特性。记住，掌握EF Core需要时间，但这些特性提供了一个扎实的基础。

另一个建议是深入了解你的数据库是如何工作的。掌握SQL也能让你从EF Core中获得最大的价值。

虽然我们重点介绍了五个关键特性，但EF Core还有许多其他特性值得探索：

- [**乐观并发控制**](https://www.milanjovanovic.tech/blog/solving-race-conditions-with-ef-core-optimistic-locking)
- [**数据库迁移**](https://www.milanjovanovic.tech/blog/efcore-migrations-a-detailed-guide)
- [**编译查询**](https://www.milanjovanovic.tech/blog/unleash-ef-core-performance-with-compiled-queries)
- [**事务**](https://www.milanjovanovic.tech/blog/working-with-transactions-in-ef-core)
- [**拦截器**](https://www.milanjovanovic.tech/blog/how-to-use-ef-core-interceptors)

EF Core 不断发展，所以请关注最新的更新和版本，保持领先。
