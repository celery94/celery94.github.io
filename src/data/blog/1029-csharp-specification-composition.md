---
pubDatetime: 2026-08-27T08:05:03+08:00
title: "C# Specification 组合：AND、OR 与 NOT"
description: "C# Specification 组合看似只是布尔运算，真正难点在于内存委托、表达式树、EF Core 翻译和空值语义。本文用可运行示例讲清参数重绑定、短路、测试与查询边界。"
tags: ["C#", ".NET", "Specification Pattern", "LINQ", "Expression Trees"]
slug: "csharp-specification-composition"
ogImage: "../../assets/1029/01-cover.jpg"
source: "https://www.devleader.ca/2026/08/25/combining-c-specifications-with-and-or-and-not"
---

把 `Active` 与 `Not(Suspended)` 拼成客户筛选条件，看起来只需要三个布尔操作符。一旦同一条规则既要在内存中调用，又要交给 EF Core 转成 SQL，问题马上从语法变成契约：参数是否绑定到同一个实例、空值如何解释、短路是否依赖执行顺序、组合的边界在哪里。

Dev Leader 的[原文《Combining C# Specifications With AND, OR, and NOT》](https://www.devleader.ca/2026/08/25/combining-c-specifications-with-and-or-and-not)围绕这个问题给出了一套完整实现。本文保留它最有价值的主线，再用中文把实现拆成可以测试的步骤：

- 纯内存 Specification 使用 `&&`、`||`、`!`，保留正常的短路语义；
- 表达式 Specification 先重绑定参数，再生成 `AndAlso`、`OrElse`、`Not` 节点；
- 用真值表、布尔恒等式和关系数据库测试检查行为；
- 只组合谓词条件，排序、投影、分页和 `Include` 继续使用各自的规则。

## 先分清两种 Specification

Specification 可以理解成一个有名字、可复用的判断规则。这里有两个执行面：

| 类型                 | 形态                                 | 运行方式     | 适用位置                                  |
| -------------------- | ------------------------------------ | ------------ | ----------------------------------------- |
| 领域 Specification   | `bool IsSatisfiedBy(T candidate)`    | 立即执行委托 | 已加载对象、领域逻辑、单元测试            |
| 表达式 Specification | `Expression<Func<T, bool>> Criteria` | 保存表达式树 | `IQueryable`、EF Core、其他 LINQ provider |

这两个接口返回的最终布尔值可以一致，内部结构却承担不同职责。委托可以调用普通 .NET 方法；表达式树会被 LINQ provider 检查和翻译，因此表达式的节点形状也属于实现边界。

先把两种容器写出来。下面的代码放入 `Specification.cs`：

```csharp
using System;
using System.Linq.Expressions;

namespace SpecificationComposition;

public interface IDomainSpecification<in T>
    where T : class
{
    bool IsSatisfiedBy(T candidate);
}

public sealed class DomainSpecification<T>
    : IDomainSpecification<T>
    where T : class
{
    private readonly Func<T, bool> _predicate;

    public DomainSpecification(Func<T, bool> predicate)
    {
        _predicate = predicate
            ?? throw new ArgumentNullException(nameof(predicate));
    }

    public bool IsSatisfiedBy(T candidate)
    {
        ArgumentNullException.ThrowIfNull(candidate);

        return _predicate(candidate);
    }
}

public interface IExpressionSpecification<T>
    where T : class
{
    Expression<Func<T, bool>> Criteria { get; }
}

public sealed class ExpressionSpecification<T>
    : IExpressionSpecification<T>
    where T : class
{
    public ExpressionSpecification(
        Expression<Func<T, bool>> criteria)
    {
        Criteria = criteria
            ?? throw new ArgumentNullException(nameof(criteria));
    }

    public Expression<Func<T, bool>> Criteria { get; }
}
```

领域版本在入口处拒绝空候选对象，避免把误用混成业务结果。表达式版本保存的是规则描述，真正的候选对象会在内存编译执行，或交给数据库 provider 处理。

## 用真值表固定三个操作

对只返回普通 `bool`、没有副作用的规则，AND、OR、NOT 应符合下面的表：

| A     | B     | A AND B | A OR B | NOT A |
| ----- | ----- | ------- | ------ | ----- |
| false | false | false   | false  | true  |
| false | true  | false   | true   | true  |
| true  | false | false   | true   | false |
| true  | true  | true    | true   | false |

这张表可以直接变成测试输入。还应检查几条恒等式：

```text
A AND true = A
A OR false = A
A AND false = false
A OR true = true
NOT NOT A = A
NOT (A AND B) = (NOT A) OR (NOT B)
NOT (A OR B) = (NOT A) AND (NOT B)
```

最后两条是 De Morgan 定律。它们能同时覆盖 AND、OR 和 NOT，适合在组合器重构后保留为回归测试。对于三个输入，结合律也可以用 8 组组合完整检查。

这里的前提是二值、无副作用的谓词。若规则返回 `bool?`，C# 的 `&&` 和 `||` 不接受这种操作数；`&` 和 `|` 则带有三值逻辑。数据库又有自己的 NULL 规则，不能把这两种语义悄悄混在一个通用 helper 里。

## 纯内存版本：直接保留短路

领域 Specification 只需要把两个判断包进 lambda：

```csharp
public static class DomainSpecificationExtensions
{
    public static IDomainSpecification<T> And<T>(
        this IDomainSpecification<T> left,
        IDomainSpecification<T> right)
        where T : class
    {
        ArgumentNullException.ThrowIfNull(left);
        ArgumentNullException.ThrowIfNull(right);

        return new DomainSpecification<T>(
            candidate =>
                left.IsSatisfiedBy(candidate) &&
                right.IsSatisfiedBy(candidate));
    }

    public static IDomainSpecification<T> Or<T>(
        this IDomainSpecification<T> left,
        IDomainSpecification<T> right)
        where T : class
    {
        ArgumentNullException.ThrowIfNull(left);
        ArgumentNullException.ThrowIfNull(right);

        return new DomainSpecification<T>(
            candidate =>
                left.IsSatisfiedBy(candidate) ||
                right.IsSatisfiedBy(candidate));
    }

    public static IDomainSpecification<T> Not<T>(
        this IDomainSpecification<T> specification)
        where T : class
    {
        ArgumentNullException.ThrowIfNull(specification);

        return new DomainSpecification<T>(
            candidate => !specification.IsSatisfiedBy(candidate));
    }
}
```

`&&` 和 `||` 会按需计算右侧：AND 的左侧为 false 时停止，OR 的左侧为 true 时停止。[C# 语言参考](https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/operators/boolean-logical-operators)还明确区分了总会计算两侧的 `&`、`|`。如果右侧规则有昂贵计算或异常风险，操作符选择会直接影响运行结果。

Specification 自身仍应保持无副作用。短路测试可以验证组合器的行为，但不应把写数据库、发请求或累加全局计数器放进业务谓词。

## 表达式版本：先重绑定，再拼树

表达式树不能直接把两个 lambda 的 body 拿来拼接。即使两个参数都叫 `customer`，它们也可能是两个不同的 `ParameterExpression` 实例。组合器需要创建一个新参数，把左右 body 中的旧参数都替换成它，然后再构造二元节点。

参数替换器很小：

```csharp
public sealed class ParameterReplacingVisitor
    : ExpressionVisitor
{
    private readonly ParameterExpression _source;
    private readonly ParameterExpression _target;

    public ParameterReplacingVisitor(
        ParameterExpression source,
        ParameterExpression target)
    {
        _source = source;
        _target = target;
    }

    protected override Expression VisitParameter(
        ParameterExpression node)
    {
        return ReferenceEquals(node, _source)
            ? _target
            : base.VisitParameter(node);
    }
}
```

Microsoft 的[表达式树转换文档](https://learn.microsoft.com/en-us/dotnet/csharp/advanced-topics/expression-trees/expression-trees-translating)说明，`ExpressionVisitor` 可以遍历节点并构造修改后的新树。组合器利用的就是这个能力。

接着写表达式版本的扩展方法：

```csharp
public static class ExpressionSpecificationExtensions
{
    public static IExpressionSpecification<T> And<T>(
        this IExpressionSpecification<T> left,
        IExpressionSpecification<T> right)
        where T : class
    {
        return Compose(
            left,
            right,
            (a, b) => Expression.AndAlso(a, b));
    }

    public static IExpressionSpecification<T> Or<T>(
        this IExpressionSpecification<T> left,
        IExpressionSpecification<T> right)
        where T : class
    {
        return Compose(
            left,
            right,
            (a, b) => Expression.OrElse(a, b));
    }

    public static IExpressionSpecification<T> Not<T>(
        this IExpressionSpecification<T> specification)
        where T : class
    {
        ArgumentNullException.ThrowIfNull(specification);

        var parameter = Expression.Parameter(
            typeof(T),
            "candidate");
        var body = new ParameterReplacingVisitor(
            specification.Criteria.Parameters[0],
            parameter).Visit(specification.Criteria.Body)!;

        return new ExpressionSpecification<T>(
            Expression.Lambda<Func<T, bool>>(
                Expression.Not(body),
                parameter));
    }

    private static IExpressionSpecification<T> Compose<T>(
        IExpressionSpecification<T> left,
        IExpressionSpecification<T> right,
        Func<Expression, Expression, BinaryExpression> merge)
        where T : class
    {
        ArgumentNullException.ThrowIfNull(left);
        ArgumentNullException.ThrowIfNull(right);
        ArgumentNullException.ThrowIfNull(merge);

        var parameter = Expression.Parameter(
            typeof(T),
            "candidate");
        var leftBody = new ParameterReplacingVisitor(
            left.Criteria.Parameters[0],
            parameter).Visit(left.Criteria.Body)!;
        var rightBody = new ParameterReplacingVisitor(
            right.Criteria.Parameters[0],
            parameter).Visit(right.Criteria.Body)!;

        return new ExpressionSpecification<T>(
            Expression.Lambda<Func<T, bool>>(
                merge(leftBody, rightBody),
                parameter));
    }
}
```

这里有三个关键点：

1. `And` 使用 `Expression.AndAlso`，`Or` 使用 `Expression.OrElse`，对应 C# 的条件逻辑操作；
2. 每次组合都创建一个新的参数，并把左右表达式改写到这个参数上；
3. 返回一棵新树，不修改原来的 Specification。

可以用 `Expression.Invoke` 把一个 lambda 包起来再调用，但这会产生 `InvocationExpression`。不同 provider 对这类节点的处理能力可能不同。直接重写 body 并生成普通的 `AndAlso`、`OrElse` 和 `Not` 节点，组合契约更容易检查，也更少依赖 provider 的特殊展开。

## 跑通一个 EF Core 查询

原文示例锁定 `net10.0`、C# 14 和 EF Core 10.0.10，并使用 SQLite 做关系 provider 测试。截至 2026 年 8 月 27 日，[NuGet 上的 SQLite provider 稳定版本已更新到 10.0.11](https://www.nuget.org/packages/Microsoft.EntityFrameworkCore.Sqlite/10.0.11)，下面的命令使用这个版本，以避开临时测试中出现的 SQLite 原生依赖安全告警。当前 [.NET 支持策略](https://dotnet.microsoft.com/en-us/platform/support/policy/dotnet-core)显示 .NET 10 处于支持周期；组合器只使用基础语法，换用同一项目中的其他受支持版本时，应让 SDK、EF Core 主版本和测试 provider 保持相容。

创建测试项目并添加 SQLite provider：

```bash
dotnet new xunit -n SpecificationComposition -f net10.0
cd SpecificationComposition
dotnet add package Microsoft.EntityFrameworkCore.Sqlite --version 10.0.11
```

把前面的接口、容器、领域扩展和表达式扩展放进 `Specification.cs`。再新建 `Customer.cs`：

```csharp
using System.Linq.Expressions;
using Microsoft.EntityFrameworkCore;

namespace SpecificationComposition;

public sealed class Customer
{
    private Customer()
    {
        Name = string.Empty;
    }

    public Customer(
        int id,
        string name,
        bool isActive,
        bool isSuspended,
        decimal creditLimit,
        string? nickname)
    {
        Id = id;
        Name = name;
        IsActive = isActive;
        IsSuspended = isSuspended;
        CreditLimit = creditLimit;
        Nickname = nickname;
    }

    public int Id { get; private set; }

    public string Name { get; private set; }

    public bool IsActive { get; private set; }

    public bool IsSuspended { get; private set; }

    public decimal CreditLimit { get; private set; }

    public string? Nickname { get; private set; }
}

public sealed class CustomerDbContext
    : DbContext
{
    public CustomerDbContext(
        DbContextOptions<CustomerDbContext> options)
        : base(options)
    {
    }

    public DbSet<Customer> Customers => Set<Customer>();
}

public static class CustomerSpecifications
{
    public static IExpressionSpecification<Customer> Active()
    {
        return new ExpressionSpecification<Customer>(
            customer => customer.IsActive);
    }

    public static IExpressionSpecification<Customer> Suspended()
    {
        return new ExpressionSpecification<Customer>(
            customer => customer.IsSuspended);
    }

    public static IExpressionSpecification<Customer> CreditAtLeast(
        decimal minimum)
    {
        return new ExpressionSpecification<Customer>(
            customer => customer.CreditLimit >= minimum);
    }

    public static IExpressionSpecification<Customer> HasNickname()
    {
        return new ExpressionSpecification<Customer>(
            customer => customer.Nickname != null);
    }
}
```

最后新建 `SpecificationCompositionTests.cs`，先验证真值表和短路：

```csharp
using System.Linq.Expressions;
using Xunit;

namespace SpecificationComposition;

public sealed record BooleanPair(bool A, bool B);

public sealed class DomainCompositionTests
{
    [Theory]
    [InlineData(false, false, false, false, true)]
    [InlineData(false, true, false, true, true)]
    [InlineData(true, false, false, true, false)]
    [InlineData(true, true, true, true, false)]
    public void Composition_FollowsTruthTable(
        bool a,
        bool b,
        bool expectedAnd,
        bool expectedOr,
        bool expectedNotA)
    {
        var left = new DomainSpecification<BooleanPair>(
            pair => pair.A);
        var right = new DomainSpecification<BooleanPair>(
            pair => pair.B);
        var candidate = new BooleanPair(a, b);

        Assert.Equal(
            expectedAnd,
            left.And(right).IsSatisfiedBy(candidate));
        Assert.Equal(
            expectedOr,
            left.Or(right).IsSatisfiedBy(candidate));
        Assert.Equal(
            expectedNotA,
            left.Not().IsSatisfiedBy(candidate));
    }

    [Fact]
    public void And_WhenLeftIsFalse_SkipsRight()
    {
        var rightEvaluations = 0;
        var left = new DomainSpecification<BooleanPair>(
            _ => false);
        var right = new DomainSpecification<BooleanPair>(
            _ =>
            {
                rightEvaluations++;
                return true;
            });

        var result = left.And(right)
            .IsSatisfiedBy(new BooleanPair(false, true));

        Assert.False(result);
        Assert.Equal(0, rightEvaluations);
    }
}

public sealed class ExpressionCompositionTests
{
    [Theory]
    [InlineData(false, false, false, false)]
    [InlineData(false, true, false, true)]
    [InlineData(true, false, false, true)]
    [InlineData(true, true, true, true)]
    public void ExpressionComposition_FollowsTruthTable(
        bool a,
        bool b,
        bool expectedAnd,
        bool expectedOr)
    {
        IExpressionSpecification<BooleanPair> left =
            new ExpressionSpecification<BooleanPair>(
                pair => pair.A);
        IExpressionSpecification<BooleanPair> right =
            new ExpressionSpecification<BooleanPair>(
                pair => pair.B);
        var candidate = new BooleanPair(a, b);

        Assert.Equal(
            expectedAnd,
            left.And(right).Criteria.Compile()(candidate));
        Assert.Equal(
            expectedOr,
            left.Or(right).Criteria.Compile()(candidate));
    }

    [Fact]
    public void Composition_UsesOneParameterWithoutInvocation()
    {
        var criteria = CustomerSpecifications.Active()
            .And(CustomerSpecifications.Suspended().Not())
            .And(CustomerSpecifications.CreditAtLeast(1000m))
            .And(CustomerSpecifications.HasNickname());

        Assert.Single(criteria.Criteria.Parameters);
        Assert.Equal(
            0,
            InvocationCountingVisitor.Count(criteria.Criteria));
    }

    private sealed class InvocationCountingVisitor
        : ExpressionVisitor
    {
        private int _count;

        public static int Count(Expression expression)
        {
            var visitor = new InvocationCountingVisitor();
            visitor.Visit(expression);
            return visitor._count;
        }

        protected override Expression VisitInvocation(
            InvocationExpression node)
        {
            _count++;
            return base.VisitInvocation(node);
        }
    }
}
```

`And_WhenLeftIsFalse_SkipsRight`证明了内存委托的短路行为。表达式测试检查最终 lambda 只有一个绑定参数，并且没有依赖 `InvocationExpression`。这类断言比比较完整的 `ToString()` 输出更稳定，因为表达式的字符串格式并非业务契约。

再加一个关系 provider 测试，确认表达式确实能执行：

```csharp
using Microsoft.Data.Sqlite;
using Microsoft.EntityFrameworkCore;
using Xunit;

namespace SpecificationComposition;

public sealed class RelationalCompositionTests
{
    [Fact]
    public async Task ComposedCriteria_ExecutesAgainstSqlite()
    {
        await using var connection =
            new SqliteConnection("Data Source=:memory:");
        await connection.OpenAsync();

        var options = new DbContextOptionsBuilder<CustomerDbContext>()
            .UseSqlite(connection)
            .Options;

        await using var db = new CustomerDbContext(options);
        await db.Database.EnsureCreatedAsync();

        db.Customers.AddRange(
            new Customer(
                1,
                "Ada",
                true,
                false,
                2000m,
                "ada"),
            new Customer(
                2,
                "Grace",
                true,
                true,
                3000m,
                "grace"),
            new Customer(
                3,
                "Linus",
                true,
                false,
                500m,
                "linus"),
            new Customer(
                4,
                "Sam",
                true,
                false,
                2500m,
                null));

        await db.SaveChangesAsync();

        var criteria = CustomerSpecifications.Active()
            .And(CustomerSpecifications.Suspended().Not())
            .And(CustomerSpecifications.CreditAtLeast(1000m))
            .And(CustomerSpecifications.HasNickname());

        var query = db.Customers
            .AsNoTracking()
            .Where(criteria.Criteria)
            .OrderBy(customer => customer.Id)
            .Select(customer => customer.Name);

        var sql = query.ToQueryString();
        Assert.Contains("WHERE", sql.ToUpperInvariant());

        var names = await query.ToListAsync();

        Assert.Equal(new[] { "Ada" }, names);
    }
}
```

运行：

```bash
dotnet test
```

预期只有 Ada 符合条件：

- Grace 被 `Suspended().Not()` 排除；
- Linus 的额度低于 1000；
- Sam 没有 nickname。

SQLite 测试证明了这棵具体表达式树能经过该 provider 执行。它不能替代生产数据库的集成测试；不同 EF Core provider 对成员、方法和 NULL 的翻译可能不同。

## 为什么要同时做两层测试

组合器测试和 provider 测试回答的问题不同：

| 测试               | 检查内容            | 能说明什么             |
| ------------------ | ------------------- | ---------------------- |
| 真值表             | AND、OR、NOT 的结果 | 布尔含义没有被写反     |
| 恒等式 / De Morgan | 组合规律            | 重构后仍保持代数契约   |
| 短路测试           | 右侧是否按需执行    | 领域委托使用了条件逻辑 |
| 参数检查           | 参数数量、节点类型  | 表达式树绑定清楚       |
| SQLite 执行        | provider 翻译和结果 | 这条查询路径可以运行   |

Microsoft 的 [EF Core 测试策略文档](https://learn.microsoft.com/en-us/ef/core/testing/choosing-a-testing-strategy)建议根据真实数据库行为选择测试方式。SQLite 测试速度快，适合检查关系查询的基本路径；生产使用 SQL Server、PostgreSQL 或其他 provider 时，仍应补充对应 provider 的关键查询测试。

也不要把编译后的委托传给需要服务端查询的 `IQueryable.Where`。编译后得到的是 `Func<T, bool>`，provider 看不到原始表达式树。[EF Core 客户端评估文档](https://learn.microsoft.com/en-us/ef/core/querying/client-eval)说明了查询中客户端代码与服务端翻译之间的边界。

## 短路语义到了数据库边界要收敛

在内存里，`a && b` 的确会在 `a` 为 false 时跳过 `b`。表达式树里的 `AndAlso` 表达了同样的条件逻辑意图。

表达式交给数据库以后，provider 会把树翻译成自己的查询语言。不要把右侧一定先后执行、异常顺序、计数器变化或 I/O 结果写进 Specification。可靠规则应当满足：

- 读取字段和参数；
- 使用 provider 能处理的成员访问与比较；
- 不访问网络、时钟、服务容器和可变全局状态；
- 不依赖某个 SQL provider 的具体生成文本。

例如下面这种规则虽然能在内存里工作，却不适合交给数据库：

```csharp
customer => customer.IsActive
    && AuditAndReturn(customer.Id);
```

`AuditAndReturn` 让结果依赖副作用和执行路径。把它移出 predicate，在查询执行前后单独记录，Specification 才能同时保持可测试和可翻译。

## 空值要写成业务选择

空值至少有两个层面：

1. 候选对象本身是否允许为 null；
2. 候选对象的某个可空属性，null 到底表示缺失、未知，还是不适用。

领域版本用 `ArgumentNullException.ThrowIfNull` 拒绝空候选。数据库版本则会面对 SQL NULL；例如 `Nickname != null` 表达的是“存在 nickname”。如果业务需要“非空白 nickname”，还应显式加入字符串规则，并确认目标 provider 的翻译。

不要把所有可空属性都自动套上相同的否定规则。`RenewalDate == null` 可能表示“尚未安排”，也可能表示“未知”，它们在业务上可能完全不同。把含义写成命名清楚的原子 Specification，组合后的代码才容易复核。

EF Core 会对很多比较加入 NULL 补偿，让结果尽量接近 C# 语义，但生成的查询可能更复杂。[EF Core NULL 比较文档](https://learn.microsoft.com/en-us/ef/core/querying/null-comparisons)建议在关心性能或语义时检查查询形状。关键规则应在目标关系 provider 上执行测试。

## 只组合谓词，不拼整个查询对象

这篇文章里的组合器只处理：

```text
Expression<Func<T, bool>>
```

完整查询还可能携带其他状态：

| 查询部分  | 组合时要回答的问题                     |
| --------- | -------------------------------------- |
| `Include` | 两组关联是否兼容，是否会造成重复载荷   |
| 排序      | 谁优先，还是按多个键继续排序           |
| 投影      | 输出类型是否相同，是否需要重新定义结果 |
| 分页      | 页码与大小如何处理，是否允许组合       |
| 跟踪策略  | 查询级别的执行策略是否应由调用方决定   |
| 缓存信息  | 两条规则怎样生成稳定的缓存键           |

这些状态没有统一的 AND、OR、NOT 语义。若把完整查询规范强行当作一个布尔谓词，会得到含义模糊的合并结果。更稳妥的结构是让 predicate 组合器保持小而明确，其他查询选项使用专门的策略或在调用处显式决定。

这也解释了为什么一个 Specification 类型不一定要承载所有查询能力。一个类可以保存 `Criteria`，另一个查询对象负责排序和分页；边界越清楚，组合越容易测试。

## 生产代码的几条护栏

### 给原子规则起有业务意义的名字

`Active().And(Suspended().Not())` 在示例里还能阅读。若这条组合反复出现，可以定义 `OperationalCustomer` 之类的命名规则。命名能帮助代码审查者理解意图，也能减少连续否定。

### 先测试行为，再检查树形状

真值表、恒等式和 provider 查询结果应该优先于完整树字符串。只有在参数数量、节点类型或禁止调用节点属于明确约束时，才检查这些结构。

### 新增表达式成员时补 provider 测试

组合器已经通过测试，不能替代新原子条件的翻译验证。每加入方法调用、复杂可空比较或 provider 特有函数，就在目标数据库上增加一条有代表性的查询测试。

### 给组合器设清晰的输入边界

组合器可以要求每个表达式只有一个 lambda 参数，且返回普通 `bool`。如果项目还需要 nullable bool、异步判断或带上下文的规则，应设计另一种明确的抽象，避免让当前 helper 静默承担额外语义。

### 让查询执行策略留在调用方

取消、跟踪、分页、投影、物化和超时都属于执行场景。Specification 负责判断条件，调用方负责决定怎样执行查询。

## 常见问题

### AND 应该用 `Expression.And` 还是 `Expression.AndAlso`？

普通布尔组合使用 `AndAlso`，它对应 C# 的 `&&` 并保留条件求值意图。`Expression.And` 对应 `&`，会让两侧都参与求值。OR 组合则使用 `OrElse`。

### 可以先把每个表达式 Compile 成委托吗？

纯内存集合可以这样做。若目标是 EF Core 的 `IQueryable`，应把表达式树传给 `Where`，保留 provider 翻译所需的信息。

### NOT 也必须创建新参数吗？

单独的 NOT 可以在原参数上包一层。统一重绑定到新参数能让 AND、OR、NOT 使用同一种实现路径，组合后的树也更容易检查。

### `bool?` 能直接套用这些 helper 吗？

当前 helper 面向普通 `bool`。可空布尔需要先决定 unknown 如何参与 AND、OR、NOT，再设计对应的结果模型和 provider 测试。

### 能把两个完整的 EF 查询 Specification 直接合并吗？

这组 helper 只合并 predicate。`Include`、排序、投影、分页、缓存和执行选项需要各自的冲突规则；它们不能从布尔代数中自动推导出来。

## 一条可靠的组合规则

Specification 组合表面上只有三个操作符，可靠性来自三件事同时清楚：内存委托的短路行为、表达式树的参数绑定，以及关系 provider 的实际翻译。

可以用下面的清单检查一次实现：

- 是否分别提供了领域委托和 provider 可读的表达式树？
- AND、OR、NOT 是否有真值表与恒等式测试？
- 表达式组合是否只有一个共享参数，且没有无必要的调用节点？
- 空值策略是否写进原子规则和关系测试？
- 新的 provider-bound 表达式是否在目标数据库上验证过？
- Specification 是否只负责 predicate，查询执行选项是否留在调用方？

先把这条边界守住，再考虑更复杂的 Specification 框架。这样规则组合才会同时适合内存测试和真实查询。

如果你在实践 C#、.NET 和软件工程设计，欢迎关注 Aide Hub。这里会继续记录可验证的开发工具与工程经验。

## 参考

- [Dev Leader：Combining C# Specifications With AND, OR, and NOT（原文）](https://www.devleader.ca/2026/08/25/combining-c-specifications-with-and-or-and-not)
- [Microsoft Learn：Boolean logical operators](https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/operators/boolean-logical-operators)
- [Microsoft Learn：Translate expression trees](https://learn.microsoft.com/en-us/dotnet/csharp/advanced-topics/expression-trees/expression-trees-translating)
- [Microsoft Learn：ExpressionVisitor API](https://learn.microsoft.com/en-us/dotnet/api/system.linq.expressions.expressionvisitor?view=net-10.0)
- [Microsoft Learn：EF Core NULL comparisons](https://learn.microsoft.com/en-us/ef/core/querying/null-comparisons)
- [Microsoft Learn：EF Core providers](https://learn.microsoft.com/en-us/ef/core/providers/)
- [Microsoft Learn：Choosing a testing strategy](https://learn.microsoft.com/en-us/ef/core/testing/choosing-a-testing-strategy)
- [Microsoft Learn：Client vs. server evaluation](https://learn.microsoft.com/en-us/ef/core/querying/client-eval)
- [.NET：Official support policy](https://dotnet.microsoft.com/en-us/platform/support/policy/dotnet-core)
- [NuGet：Microsoft.EntityFrameworkCore.Sqlite 10.0.11](https://www.nuget.org/packages/Microsoft.EntityFrameworkCore.Sqlite/10.0.11)
