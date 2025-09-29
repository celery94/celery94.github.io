---
pubDatetime: 2025-09-29
title: 在 C# 中掌握 Expression Trees：构建可运行时组装的 LINQ 查询
description: Expression Tree 让 C# 在运行时拼装表达式，本篇从语法树结构、LINQ 翻译流程、动态查询工厂到性能调优与治理策略，帮助你落地企业级筛选与规则引擎并避开常见陷阱。
tags: [".NET", "C#", "LINQ", "Architecture"]
slug: expression-trees-dynamic-linq
source: https://blog.elmah.io/expression-trees-in-c-building-dynamic-linq-queries-at-runtime/
---

借助 Expression Tree，C# 可以在运行时把代码结构化为一棵树，再把树翻译成可执行逻辑或交给 LINQ 提供程序转换成 SQL。它既是动态查询的底层基础，也是规则引擎、报表系统和可配置化平台的关键砝码。理解它的结构与运行机制，才能在项目中写出既灵活又可维护的动态查询。

## 为何在现代 .NET 项目中需要表达式树

传统的动态过滤往往写成一长串 `if-else` 或拼接字符串 SQL，这不仅难以维护，也留下了安全隐患。Expression Tree 则把条件表达式表示为抽象语法树，允许在运行时根据用户输入选择性地拼接节点，再交由 LINQ Provider 校验并生成最终执行计划。这种能力尤其适用于：

- 多维过滤界面：用户可自由组合字段、比较符号与取值，后端则把这些输入转换成表达式树并传给 Entity Framework、Dapper 或 ElasticLINQ。
- 规则驱动平台：业务人员在后台配置规则（例如风控阈值），平台在运行时生成对应的表达式，再编译成委托执行。
- 可观察性工具：通过 Expression Tree 访问表达式节点，平台可以记录或重写查询，实现诊断、缓存和审计。

这些场景的共同挑战在于“组合爆炸”与“可读性下降”。表达式树通过结构化的数据模型使动态组合成为可能，同时保留类型检查的保障。

## 深入理解 Expression Tree 的结构与运行机制

Expression Tree 是一组不可变的节点类型，每个节点描述一个操作。以 `Expression<Func<Order, bool>>` 为例，`ParameterExpression` 表示输入参数，`MemberExpression` 表示访问的属性，`BinaryExpression` 表示比较运算，最终通过 `Expression.Lambda` 封装成强类型表达式。表达式既可以被编译为委托（`lambda.Compile()`），也可以作为查询表达式传递给支持 LINQ 的库，让 Provider 自行翻译为 SQL、Elastic 查询或 GraphQL。

理解运行链路需要区分两个阶段：

1. 构建树：在运行时把用户意图映射为节点，并组合出完整的 `Expression<TDelegate>`。
2. 消费树：当表达式传入 `IQueryable` 时，LINQ Provider 遍历树结构，生成底层查询；若调用 `Compile()`，则由运行时生成 IL，再在进程内执行。

Provider 通常无法理解被编译后的委托，因此当你希望数据库执行过滤逻辑时，应避免在中途调用 `Compile()`。与此同时，表达式树是不可变的，修改节点需要创建新树或借助 `ExpressionVisitor` 深拷贝并替换目标节点。

## 案例：构建可组合的动态过滤器

设想一个后台报表需要支持多字段组合过滤，还要允许不同字段使用不同的比较符号。可以先把前端提交的条件转换成领域模型，然后动态生成表达式：

```csharp
using System;
using System.Collections.Generic;
using System.Linq.Expressions;

enum ComparisonOperator
{
    Equals,
    NotEquals,
    GreaterThan,
    LessThan,
    Contains
}

sealed record FilterCondition(string Property, ComparisonOperator Operator, object? Value);

public static Expression<Func<T, bool>> BuildPredicate<T>(IEnumerable<FilterCondition> conditions)
{
    var parameter = Expression.Parameter(typeof(T), "entity");
    Expression body = Expression.Constant(true);

    foreach (var condition in conditions)
    {
        var member = Expression.Property(parameter, condition.Property);
        var targetType = Nullable.GetUnderlyingType(member.Type) ?? member.Type;

        if (condition.Value is null && targetType.IsValueType && Nullable.GetUnderlyingType(member.Type) is null)
        {
            throw new InvalidOperationException($"字段 {condition.Property} 不接受 null 值");
        }

        object? convertedValue = condition.Value;

        if (convertedValue is not null && convertedValue.GetType() != targetType)
        {
            convertedValue = Convert.ChangeType(convertedValue, targetType);
        }

        var constant = Expression.Constant(convertedValue, member.Type);
        Expression comparison = condition.Operator switch
        {
            ComparisonOperator.Equals => Expression.Equal(member, constant),
            ComparisonOperator.NotEquals => Expression.NotEqual(member, constant),
            ComparisonOperator.GreaterThan => Expression.GreaterThan(member, constant),
            ComparisonOperator.LessThan => Expression.LessThan(member, constant),
            ComparisonOperator.Contains => BuildContains(member, constant),
            _ => throw new NotSupportedException()
        };

        body = Expression.AndAlso(body, comparison);
    }

    return Expression.Lambda<Func<T, bool>>(body, parameter);
}

static Expression BuildContains(MemberExpression member, ConstantExpression constant)
{
    if (member.Type != typeof(string))
    {
        throw new NotSupportedException("Contains 仅支持字符串字段");
    }

    var method = typeof(string).GetMethod(nameof(string.Contains), new[] { typeof(string) })
        ?? throw new InvalidOperationException("未能找到 string.Contains 方法");

    return Expression.Call(member, method, constant);
}
```

在真实项目里可以进一步扩展 `BuildContains`，例如统一大小写、在空值时直接返回 `false` 表达式，或通过自定义方法映射到数据库特定的 `LIKE` 语法。生成的表达式可以直接传给 `dbContext.Set<T>().Where(predicate)`，由 Provider 翻译到数据库层。

为了让表达式树更易于扩展，可以引入“构建器”模式：把每类操作封装成独立的方法或 `ExpressionVisitor`，让每个条件都能单独测试。当过滤条件为空时，返回 `Expression.Constant(true)` 确保组合逻辑仍然成立，避免 `Where` 抛出空引用异常。

## 在真实项目中部署的策略与陷阱

虽然表达式树带来了灵活性，但也附带一系列工程化挑战。以下实践可以帮助落地：

- 缓存编译结果：`lambda.Compile()` 的成本不菲。若同一个表达式会重复执行，把编译后的委托存入缓存（如 `MemoryCache`），结合字段哈希或序列化方式生成键值。
- 保持 Provider 友好：确保使用的节点类型可被目标 Provider 识别，例如 Entity Framework Core 无法翻译 `DateOnly` 自定义扩展方法。可通过 `QueryTranslationPreprocessor` 或 `ExpressionVisitor` 在提交之前替换为可翻译的形式。
- 处理类型转换：前端输入通常是字符串，可先用 `Convert.ChangeType` 或 `Expression.Convert` 把常量转换成属性类型，避免运行时异常。
- 推迟副作用：表达式树应保持纯函数，避免在节点中引入 `DateTime.Now` 等非确定性操作，改用参数注入或数据库函数，以便 Provider 能够下推。

同时，要警惕以下陷阱：

- 盲目编译：一旦调用 `Compile()` 并执行，所有逻辑都发生在内存中，数据库端失去索引优化能力。
- 节点深度过大：过度嵌套的 `AndAlso` 会导致 SQL 非常冗长，必要时可以拆成分页查询或构建批量管道。
- 不可变性误解：表达式树每次修改都会生成新实例，如果在循环里频繁复制，要留意内存开销。

## 小结

Expression Tree 把一段 C# 代码拆解成结构化节点，让我们根据运行时的业务意图重新组装查询。理解树的不可变特性、Provider 翻译行为，以及编译与缓存策略，是把它落地到生产系统的关键。只要提前设计好条件模型、节点拼装与生命周期管理，就能在企业级项目中为报表、搜索和规则引擎带来灵活而可靠的动态查询能力。

## 参考资料

- [Expression Trees in C#: Building Dynamic LINQ Queries at Runtime](https://blog.elmah.io/expression-trees-in-c-building-dynamic-linq-queries-at-runtime/)
