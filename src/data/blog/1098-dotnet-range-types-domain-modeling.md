---
pubDatetime: 2026-10-19T07:43:22+08:00
title: "别再存两个日期：.NET 区间类型建模"
description: "两个日期字段会让空值、开闭边界和重叠判断散落在各处。本文用五种区间形状重新建模，说明 NpgsqlRange 的边界，并给出可在内存和 PostgreSQL 中运行的 .NET 示例。"
tags: ["C#", ".NET", "Domain Modeling", "PostgreSQL", "EF Core"]
slug: "dotnet-range-types-domain-modeling"
ogImage: "../../assets/1098/01-cover.jpg"
source: "https://dev.to/caffeinatedcoder/the-interval-is-the-thing-modelling-range-types-as-first-class-domain-objects-in-net-3jha"
---

会议室预订系统里，最早出现的模型通常是这样：

```csharp
public sealed class Booking
{
    public DateTime Start { get; set; }
    public DateTime End { get; set; }
}
```

它能编译，也能跑。问题从第二个调用点开始。`End` 为空代表永不过期，还是数据缺失？结束时间当天的 23:59 算不算占用？如果 `End` 早于 `Start`，数据库该拒绝，还是交给业务代码处理？

两个字段只保存了数据，没有保存关于数据的约定。预订、排班、会员有效期、促销周期都会遇到同一个问题：真正有业务含义的对象是一段时间，代码却把它拆成了两个可以各自修改的日期。

DEV 的原文作者 Ricardo Groß 是 `CodoMetis.ValueRanges` 的维护者。原文围绕这个库展开，本文沿着设计问题重新组织材料，并核对了当前 NuGet 与 PostgreSQL 的实际状态。

## 两个日期字段丢掉了什么

半开区间 `[Start, End)` 的重叠判断可以写成一行：

```csharp
public static bool Overlaps(Booking a, Booking b)
    => a.Start < b.End && b.Start < a.End;
```

这行代码默认了两个边界规则：开始时间包含，结束时间不包含。如果产品要求结束时间也包含，比较符就要改。如果允许没有结束时间，还要额外判断 `End == default`。如果数据库里混用了两套规则，第三个调用点就会出现第三种解释。

字段本身无法阻止这些情况：

```csharp
var booking = new Booking
{
    Start = new DateTime(2026, 10, 20, 9, 0, 0),
    End = new DateTime(2026, 10, 19, 9, 0, 0)
};
```

这会创建一个前一个对象，类型系统不会阻止，构造函数也不会报告问题。校验代码可能散落在控制器、服务、数据库检查和前端表单里。每增加一个入口，就多一次遗漏边界的机会。

这里缺少的对象是一段区间。它需要同时回答三个问题：区间是什么形状，边界是否包含，空区间如何表示。把答案写进类型，比写进注释更可靠。

## 用五种形状表示一段区间

`CodoMetis.ValueRanges` 把区间分成五种形状：

| 形状             | 含义                       | 典型例子                   |
| ---------------- | -------------------------- | -------------------------- |
| `Finite`         | 两端都有界                 | `[2026-01-01, 2026-12-31]` |
| `UnboundedStart` | 只有上界                   | `(-∞, 2026-12-31]`         |
| `UnboundedEnd`   | 只有下界                   | `[2026-01-01, +∞)`         |
| `Infinity`       | 两端都无界，覆盖整个定义域 | `(-∞, +∞)`                 |
| `EmptyRange`     | 不包含任何值               | `∅`                        |

这种拆分让「没有上界」和「上界等于最大值」成为两件事。前者没有 `End` 属性，后者有明确的边界值。调用者不需要先读一个布尔标志，再判断某个属性是否有效。

在领域对象里，一个订阅周期可以只保留一个字段：

```csharp
using CodoMetis.ValueRanges;

public sealed class MemberSubscription
{
    public int MemberId { get; }
    public DateRange Period { get; }

    public MemberSubscription(int memberId, DateRange period)
    {
        if (period is DateRange.EmptyRange)
            throw new ArgumentException("订阅周期至少需要一天。", nameof(period));

        MemberId = memberId;
        Period = period;
    }

    public bool IsActiveOn(DateOnly date) => Period.Contains(date);

    public bool ConflictsWith(MemberSubscription other) =>
        Period.Overlaps(other.Period);
}
```

构造对象时只校验一次空区间。后面的查询直接调用 `Contains` 和 `Overlaps`，不需要在每个调用点重复判断空值、反序边界和结束日期是否包含。

离散值和连续值的边界规则要分开看。整数和日期可以数出「下一个值」，所以 `[1, 5]` 与 `[6, 10]` 相邻。小数没有这种步长，`[1.0, 5.0]` 与 `(5.0, 10.0]` 可以通过互补的开闭边界判断相邻。库把这两种规则放进各自的工厂方法，调用者仍然需要先确定业务语义。

## NpgsqlRange 适合传输，不适合充当领域模型

Npgsql 用 `NpgsqlRange<T>` 表示 PostgreSQL 的 range 值。它按照数据库线路格式组织数据：两个可空边界，加上一个 `RangeFlags` 位标志。边界是否有效，要先检查对应标志。

这种设计适合驱动层。Npgsql 需要在 .NET 和 PostgreSQL 之间传输 range，并把 LINQ 表达式翻译成 SQL，`NpgsqlRange<T>` 正好承担这个职责。

把它直接放进领域层会遇到另一个问题：Npgsql 的 EF Core 扩展方法主要用于表达式翻译。`Contains`、`Overlaps`、`Intersect` 写在 LINQ 查询里会生成 SQL 运算符，离开 EF Core 查询后在进程内调用，没有对应的内存实现，会抛出 `InvalidOperationException`。

这意味着领域代码无法靠它完成普通的单元测试。为了判断两个区间是否重叠，测试还得准备数据库和执行 LINQ。数据库驱动因此进入了本来不需要数据库的业务逻辑。

一个可维护的边界是：

- 领域层使用 `DateRange` 这类值对象，负责业务规则和内存运算。
- Npgsql 和 EF Core 留在数据访问层，负责列映射、SQL 翻译和线路格式。
- 两者之间通过明确的映射连接，避免业务代码直接引用数据库驱动。

## 五种形状怎么变成类型

区间不能用一个字段组合覆盖所有情况。有限区间的属性是 `Start` 和 `End`，无上界区间只有 `Start`，空区间没有边界。把它们压成一个带可空字段和布尔标志的结构，就回到了 `NpgsqlRange<T>` 的状态校验问题。

原文建议用封闭的继承层次表达五种形状。概念上接近下面这样：

```csharp
public abstract record DateRange
{
    private DateRange() { }

    public sealed record EmptyRange : DateRange;
    public sealed record Finite(DateOnly Start, DateOnly End) : DateRange;
    public sealed record UnboundedStart(DateOnly End) : DateRange;
    public sealed record UnboundedEnd(DateOnly Start) : DateRange;
    public sealed record Infinity : DateRange;
}
```

私有构造函数封闭了继承层次，外部代码无法增加第六种形状。基类使用引用类型，因为 C# 的继承和多态建立在类上。`record` 提供结构相等，适合不可变的领域对象。

代价是每个实例一次堆分配。对于订阅、班次、合同期限这类业务对象，这个成本通常可以接受。真正需要高性能的地方是数据库里的大表范围查询，那部分交给 PostgreSQL 的索引和运算符处理。

模式匹配可以写出清晰的业务分支：

```csharp
string Describe(DateRange range) => range switch
{
    DateRange.EmptyRange => "没有覆盖任何日期",
    DateRange.Finite f => $"{f.Start:yyyy-MM-dd} 到 {f.End:yyyy-MM-dd}",
    DateRange.UnboundedStart s => $"截至 {s.End:yyyy-MM-dd}",
    DateRange.UnboundedEnd e => $"{e.Start:yyyy-MM-dd} 起",
    DateRange.Infinity => "全部日期",
    _ => throw new UnreachableException()
};
```

当前 C# 编译器不会根据私有构造函数推断出分支已经穷尽，所以仍然需要最后一个抛异常的分支。这个分支表示调用方遇到了不可能出现的情况，不应返回一个看似合理的默认值。

## 选型：自己写，还是引入库

如果系统里只有一个「开始日期、结束日期」字段，判断逻辑也只有包含和重叠，一个几百行的内部值对象就够用。先明确边界规则，再补单元测试，往往比引入依赖更直接。

如果还需要无界区间、空区间、相邻判断、交集、并集、差集、PostgreSQL 字面量、JSON 序列化和 EF Core 翻译，自己实现的面积会迅速扩大。区间运算的边界组合很多，差集还可能把一个区间拆成两个。

可以用下面的条件做初步判断：

| 场景                            | 建议                             |
| ------------------------------- | -------------------------------- |
| 单一日期窗口，只有少量判断      | 写精简的值对象                   |
| 需要无界、空区间和集合运算      | 使用成熟的区间库                 |
| 领域层直接依赖 `NpgsqlRange<T>` | 避免                             |
| 只使用 SQL Server 或 MySQL      | 先确认数据库映射，再决定是否引入 |

截至 2026 年 10 月，`CodoMetis.ValueRanges` 的 NuGet 稳定版是 9.1.0。核心包要求 .NET 10 或更高版本，不依赖 Npgsql 或 EF Core。原文发布时列出了六种 range 类型，9.1.0 还提供 `TimeRange`，并有独立的 NodaTime 包。

配套的 `CodoMetis.ValueRanges.EFCore.PostgreSQL` 负责把领域类型映射到 `NpgsqlRange<T>`，再由 Npgsql 翻译成 SQL。当前 EF 包要求 PostgreSQL 16 或更高版本。PostgreSQL 的 range 类型从 9.2 开始提供，multirange 从 14 开始提供，这些版本事实与库自身的最低要求需要分开确认。

原作者维护这个库，因此原文带有明显的产品介绍色彩。评估时仍应按团队场景核对 API、版本要求和依赖成本。

## 在项目里接入

准备一个 .NET 10 项目，并安装核心包：

```bash
dotnet add package CodoMetis.ValueRanges
dotnet add package CodoMetis.ValueRanges.EFCore.PostgreSQL
```

先在领域层使用区间类型。下面的班次模型不引用 EF Core 或 Npgsql：

```csharp
public sealed class ShiftAssignment
{
    public int EmployeeId { get; }
    public DateRange Period { get; }

    public ShiftAssignment(int employeeId, DateRange period)
    {
        if (period is DateRange.EmptyRange)
            throw new ArgumentException("班次至少需要覆盖一天。", nameof(period));

        EmployeeId = employeeId;
        Period = period;
    }

    public bool ConflictsWith(ShiftAssignment other) =>
        Period.Overlaps(other.Period);
}
```

EF Core 的配置仍然只有一行：

```csharp
options.UseNpgsql(connectionString, npgsql => npgsql.UseValueRanges());
```

配置完成后，`DateRange` 属性按约定映射为 `daterange`，`RangeSet<DateRange, DateOnly>` 映射为 `datemultirange`。LINQ 查询里的区间方法会在数据库端执行：

```csharp
var day = new DateOnly(2026, 10, 19);

var active = await db.ShiftAssignments
    .Where(s => s.Period.Contains(day))
    .ToListAsync();
```

应用层的「先查询，再插入」无法解决并发冲突。两个请求可以同时查到空档，然后都尝试插入。要让重叠在存储层无法发生，需要使用 PostgreSQL 的排他约束：

```sql
CREATE EXTENSION IF NOT EXISTS btree_gist;

ALTER TABLE "ShiftAssignments"
  ADD CONSTRAINT "ex_shift_employee_period"
  EXCLUDE USING gist ("EmployeeId" WITH =, "Period" WITH &&);
```

同一个员工的两条班次发生重叠时，数据库会拒绝写入，并返回 `23P01` 错误。不同员工的班次不受影响，相邻的日期区间仍然可以保存。

如果使用 EF Core 迁移，建议在清理完历史重叠数据后再添加约束。已有数据违反约束时，迁移会直接失败，这比上线后才发现重复数据更容易定位。

## 单元测试应该验证什么

领域层不依赖数据库，测试可以直接构造区间：

```csharp
[Fact]
public void Open_ended_shift_conflicts_with_a_later_finite_shift()
{
    var openEnded = new ShiftAssignment(
        7,
        DateRange.CreateUnboundedEnd(new DateOnly(2025, 1, 1)));

    var annual = new ShiftAssignment(
        7,
        DateRange.CreateFinite(
            new DateOnly(2025, 6, 1),
            new DateOnly(2025, 12, 31)));

    Assert.True(openEnded.ConflictsWith(annual));
}
```

还值得补三类断言：

- 结束日期前后各一天是否符合业务约定。
- 空区间在构造函数里是否被拒绝。
- 两个不连续区间合并后，差集是否保留中间的缺口。

下面的例子验证覆盖缺口。`Complement().Intersect(...)` 返回一个 `RangeSet`，无需数据库：

```csharp
var required = DateRange.CreateFinite(
    new DateOnly(2026, 10, 1),
    new DateOnly(2026, 10, 31));

var covered = RangeSet<DateRange, DateOnly>.From(
[
    DateRange.CreateFinite(
        new DateOnly(2026, 10, 1),
        new DateOnly(2026, 10, 10)),
    DateRange.CreateFinite(
        new DateOnly(2026, 10, 11),
        new DateOnly(2026, 10, 20))
]);

var missing = covered.Complement().Intersect(required);
Assert.Single(missing);
Assert.Equal(DateRange.CreateFinite(
    new DateOnly(2026, 10, 21),
    new DateOnly(2026, 10, 31)), missing[0]);
```

## 迁移时的边界

从两个日期字段迁移到区间类型，可以按下面的顺序推进：

1. 找出成对出现的开始、结束字段，确认它们代表同一个业务概念。
2. 固化边界规则，包括空值含义、开闭区间和离散值的步长。
3. 编写内存测试，用旧数据和新类型跑同一组业务判断。
4. 建立数据库列和索引，清理历史重叠数据，再添加排他约束。
5. 检查 API 和 JSON 输出，避免把内部类型的变化直接暴露成不兼容接口。

几个容易忽略的点：

- PostgreSQL 的离散 range 会规范化为半开形式，库在内存里使用闭区间并通过边界转换保持结果一致。跨层比较时不能只看字面量。
- 当前 EF Core 反向工程会把 range 列生成为 `NpgsqlRange<T>`，需要手工把实体属性改成领域类型。
- 核心包和 EF 包的 .NET、PostgreSQL 版本要求不同，升级前要同时检查。
- 只在 PostgreSQL 内部使用的系统，排他约束能直接解决并发重叠。需要跨数据库时，约束和类型映射要重新设计。

区间类型带来的主要变化发生在建模阶段。字段变成一个有边界语义的值，重叠和集合运算有了唯一实现，数据库约束负责并发下的最后一道检查。读者可以从一个最常出现的时间窗口开始，把它的边界规则和测试写清楚，再决定是否需要引入完整库。

如果团队正在维护 AI 助手、开发工具或软件工程实践，Aide Hub 会继续整理这类可验证的技术拆解。

## 参考

- [The Interval Is the Thing: Modelling Range Types as First-Class Domain Objects in .NET](https://dev.to/caffeinatedcoder/the-interval-is-the-thing-modelling-range-types-as-first-class-domain-objects-in-net-3jha)
- [CodoMetis.ValueRanges on NuGet](https://www.nuget.org/packages/CodoMetis.ValueRanges)
- [CodoMetis.ValueRanges.EFCore.PostgreSQL on NuGet](https://www.nuget.org/packages/CodoMetis.ValueRanges.EFCore.PostgreSQL)
- [CodoMetis.ValueRanges source code](https://github.com/CaffeinatedCoder/CodoMetis.ValueRanges)
- [PostgreSQL: Range Types](https://www.postgresql.org/docs/current/rangetypes.html)
- [Npgsql EF Core: Range Mapping](https://www.npgsql.org/efcore/mapping/range.html)
