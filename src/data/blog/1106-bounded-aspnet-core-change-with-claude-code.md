---
pubDatetime: 2026-10-22T08:25:00+08:00
title: "Claude Code 改 .NET 端点：先划清边界"
description: "端点加一条 pageSize 范围校验看起来简单，但绑定失败、校验失败、默认值和下游查询都在契约里。本文把用 coding agent 做这类改动拆成六步，附 .NET 10 上实跑的七次 HTTP 检查记录。"
tags: ["Claude Code", "ASP.NET Core", ".NET", "Testing"]
slug: "bounded-aspnet-core-change-with-claude-code"
ogImage: "../../assets/1106/01-cover.jpg"
source: "https://www.devleader.ca/2026/10/21/make-a-bounded-aspnet-core-change-with-claude-code"
---

「给这个端点加个分页校验。」你把这句话丢给 Claude Code，它读了几个文件，交回一个 diff：加了范围判断，也补了测试。看起来对，问题是你凭什么合并它。

Diff 小不等于边界清楚。一个看似局部的改动会同时碰到好几层：查询参数绑定、默认值、校验错误格式、授权、租户过滤、响应形状、下游查询是否被执行、以及测试到底证明了什么。这些层里有一层被顺手改掉，客户端就会发现。

Nick Cosentino 在 Dev Leader 上这篇讲的就是怎么把这种改动框成一次可审查的边界。在这篇文章里，Claude Code 的角色就是 coding agent：它能在仓库里读代码、改文件、执行命令，价值不是替你设计系统，而是找出相关契约、做出最小的完整改动。

**一次改动能不能合并，看的是端点契约有没有被写清、被证据覆盖、被 diff 保住，而不是 diff 有多小。**

下面按「先划边界，再让它动手」这条线重述，并把原文散在各节的判断整理成六步。第三步的七次 HTTP 检查，我在本机用 .NET 10 SDK 复现了一遍，其中有一项结果值得单独说。

## 前置条件

- **.NET 10 SDK**。本文的示例在 `10.0.402` 上编译并运行；`net10.0` 之外没有额外 NuGet 依赖。
- **一个现有端点**。示例借用一个订单列表端点的形式：`GET /orders`，接受可选的 `pageSize` 查询参数，负数会被直接带进查询。
- **Claude Code 已安装并在该仓库里可用**。一个 coding agent 需要读文件、写文件、执行命令的权限，这三项要按你的环境分别给。
- **能运行测试的环境**。如果验证要在远端跑，先确认那台机器上有 .NET 10 SDK 和被改动项目需要的依赖。第三步的检查脚本用到 `Invoke-WebRequest -SkipHttpErrorCheck`，它需要 PowerShell 7 及以上（Windows PowerShell 5.1 请改用 `curl.exe`）。

如果你只是想读懂这篇文章，不需要装 Claude Code；但想复现第三步的表格，必须有 .NET 10 SDK。

## 第一步：把改动写成可验收的契约

「加分页校验」听起来精确，其实留了一堆没定的问题：默认值是多少？零允许吗？上限在哪？API 的错误格式是什么？非法输入会不会真的打到数据库？

示例端点的初始代码如下（`OrderCatalog` 和 `OrderPage` 在第三步的完整示例里定义）。缺陷落在 `ReadPage` 那一行：所有解析成功的整数都会直接进查询。

```csharp
app.MapGet("/orders", (int? pageSize, OrderCatalog catalog) =>
{
    var resolvedPageSize = pageSize ?? 20;
    return Results.Ok(new OrderPage(
        resolvedPageSize,
        catalog.ReadPage(resolvedPageSize)));
});
```

示例把契约收得很窄：

| 输入             | 期望结果                   | 要保住的既有行为       |
| ---------------- | -------------------------- | ---------------------- |
| 省略 `pageSize`  | 200，`pageSize` 为 20      | 默认值不变             |
| `pageSize=1`     | 200，返回 1 条             | 下边界包含在内         |
| `pageSize=100`   | 200，`pageSize` 报告为 100 | 上边界包含在内         |
| `0`、`101`、负数 | 400，沿用现有错误格式      | 不触达查询服务         |
| `abc`            | 400                        | 绑定失败的路径不被改变 |

这三个数字（20、1、100）是示例的业务验收条件，**不是 ASP.NET Core 的默认值**。框架不知道你的分页策略；真实仓库里的默认值和范围要从已批准的需求和现有行为里推出来。

边界还要覆盖那些「不该被这次改动碰到」的东西：授权、租户过滤、排序、取消行为、成功响应的字段和类型。如果这些无法从仓库里确认，让 agent 先报告不确定，而不是先改。

原文有个说法值得记住：比「只改 handler 文件」更好的边界定义，是「这个端点的契约」。一次完整的行为改动可能同时涉及 handler、回归测试和接口文档。**范围单位是契约，不是文件数。**

## 第二步：先 trace，再让它动手

Claude Code 的官方文档列出的能力是仓库读取、文件编辑和命令执行，并在常见工作流里建议先定位相关代码、理清交互，再动手改。

对现有端点，第一件事是要求一份「从路由到查询」的追踪：参数在哪绑定、默认值在哪产生、哪一层做校验、哪个服务执行查询。这是一次只读发现，提示词里要把禁止事项写死：

```powershell
Set-Location 'C:\repos\OrderService'
claude "追踪 GET /orders：从 query binding 到 query service，以及它的 HTTP 测试。指出当前 pageSize 的默认值、授权、租户过滤、错误格式和排序，并给出相关文件名和行号。不要修改文件、安装包、运行构建或测试、连接数据库、提交或发布。"
```

换成英文提示词也可以，要点不在语言，而在这四条：**只读发现、指出文件位置、覆盖既有契约、明确禁止执行**。

期望的输出是一段带文件引用的具体说明。一段「Minimal API 通常这样绑定参数」的通用介绍不算，一个绕过你还没看过的校验过滤器的实现方案也不算。

仓库里的说明文件（例如 `CLAUDE.md`）能提供约定，但官方 memory 文档把它定位成上下文，而不是强制约束。所以权限要单独配，尤其在环境里有凭据或连了外部工具的时候。

还有一条容易混：**读测试文件和运行测试是两件事**。后者可能启动服务、连上配置好的依赖，属于验证环境该做的决定，不该混在发现阶段顺手做掉。

## 第三步：分清绑定失败和校验失败

ASP.NET Core 通过参数绑定把请求数据转成 handler 参数。一个数字型查询参数因此引出两个不同的问题：框架能不能把输入解析成声明的类型？解析成功之后，值是否满足业务规则？

`pageSize=abc` 和 `pageSize=-1` 不是同一条路径。前者是绑定失败，后者是绑定成功但被业务规则拒绝。**通过其中一个的测试，不能证明另一个。**

省略输入是第三条路径。把可选的 `int?` 改成必填的 `int`，会让「省略就取默认 20」变成「绑定失败、400」，这是很容易被顺手改掉的客户端行为。

还有一层：查询返回空列表，和拒绝请求不是一个东西。对负数返回空结果，客户端看到的是 200 加空数组；契约要求的是 400。客户端可见的状态码和下游是否被执行，都属于契约。

### 这次复现：七次 HTTP 检查

要跑这七次检查，先有一个能跑的最小项目。两个文件就够，不需要额外的 NuGet 包：

```xml
<Project Sdk="Microsoft.NET.Sdk.Web">
  <PropertyGroup>
    <TargetFramework>net10.0</TargetFramework>
    <Nullable>enable</Nullable>
    <ImplicitUsings>enable</ImplicitUsings>
  </PropertyGroup>
</Project>
```

改动后的完整 `Program.cs`：

```csharp
using System.Collections.Immutable;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using Microsoft.Extensions.DependencyInjection;

var builder = WebApplication.CreateBuilder(args);
builder.Services.AddSingleton<OrderCatalog>();

var app = builder.Build();

app.MapGet("/orders", IResult (int? pageSize, OrderCatalog catalog) =>
{
    var resolvedPageSize = pageSize ?? 20;

    if (resolvedPageSize < 1 || resolvedPageSize > 100)
    {
        return Results.BadRequest(new ApiError(
            "invalid_page_size",
            "pageSize must be between 1 and 100."));
    }

    return Results.Ok(new OrderPage(
        resolvedPageSize,
        catalog.ReadPage(resolvedPageSize)));
});

app.Run();

public sealed class OrderCatalog
{
    private readonly ImmutableArray<OrderSummary> _orders =
    [
        new(1, "First order"),
        new(2, "Second order"),
        new(3, "Third order")
    ];

    public ImmutableArray<OrderSummary> ReadPage(int pageSize)
    {
        return _orders.Take(pageSize).ToImmutableArray();
    }
}

public sealed record OrderSummary(int Id, string Description);

public sealed record OrderPage(
    int PageSize,
    ImmutableArray<OrderSummary> Items);

public sealed record ApiError(string Code, string Message);
```

写成 `IResult` 是为了让返回类型一眼可见；`Results.Ok` 和 `Results.BadRequest` 本来就返回 `IResult`，这个 handler 也可以走类型推断。官方文档还提供了 `TypedResults` 和结果联合类型，类型信息更强，但一次范围校验任务不需要顺手做这个重构。

这不是生产脚手架：它故意没有认证、租户模型、数据库、日志提供者，也没有联网依赖。别把它整段套用到现有服务上。

把项目文件命名为 `OrdersBounded.csproj`，和 `Program.cs` 放在同一个目录，编译后指定端口启动：

```powershell
dotnet build
dotnet run --urls http://127.0.0.1:5099
```

看到 `Now listening on: http://127.0.0.1:5099` 之后，在另一个终端跑下面的检查。我这个工程放在临时目录，用 .NET 10 SDK `10.0.402` 编译（0 警告 0 错误），然后跑了七次检查：

```powershell
$base = "http://127.0.0.1:5099"
$cases = @(
  @{ Name = "omitted"; Url = "/orders" },
  @{ Name = "1"; Url = "/orders?pageSize=1" },
  @{ Name = "100"; Url = "/orders?pageSize=100" },
  @{ Name = "0"; Url = "/orders?pageSize=0" },
  @{ Name = "101"; Url = "/orders?pageSize=101" },
  @{ Name = "-1"; Url = "/orders?pageSize=-1" },
  @{ Name = "abc"; Url = "/orders?pageSize=abc" }
)
foreach ($c in $cases) {
  $r = Invoke-WebRequest -Uri ($base + $c.Url) -SkipHttpErrorCheck
  "{0,-8} {1} {2}" -f $c.Name, $r.StatusCode, $r.Content
}
```

实际输出：

| 输入  | 状态码 | 响应体                                       | 说明                     |
| ----- | ------ | -------------------------------------------- | ------------------------ |
| 省略  | 200    | `{"pageSize":20,"items":[…3 条…]}`           | 默认值生效               |
| `1`   | 200    | `{"pageSize":1,"items":[…1 条…]}`            | 下边界包含               |
| `100` | 200    | `{"pageSize":100,"items":[…3 条…]}`          | 上边界包含，见下方限制   |
| `0`   | 400    | `{"code":"invalid_page_size","message":"…"}` | 业务规则拒绝             |
| `101` | 400    | 同上                                         | 业务规则拒绝             |
| `-1`  | 400    | 同上                                         | 原缺陷在这里被修掉       |
| `abc` | 400    | **空**                                       | 绑定失败，走了另一条路径 |

最后一行是这次复现里最有用的一处观察：`abc` 确实返回 400，但响应体是空的，没有走示例自定义的 `ApiError`。原因很直接——参数绑定失败发生在进入 handler 之前，框架直接回了 400，你的错误格式根本没机会执行。

这正好说明为什么「区分绑定失败和校验失败」不是学术问题：如果客户端依赖 `{"code":"invalid_page_size", …}` 这个结构去提示用户，那么 `pageSize=abc` 这一路它拿到的是空 body，前端解析会失败。原文提醒这个示例「不承诺绑定失败也用同一个错误形状」，实测把它变成了可见的现象。

### 这次复现证明什么，没证明什么

证明了：默认值、两个边界都被接受（item 数量见下）、三种越界拒绝、绑定失败的状态码，都与预期一致。

没证明：真实应用的授权、租户过滤、持久化、错误中间件的行为。

还有个细节：`pageSize=100` 返回 `pageSize: 100` 但只有 3 条数据，因为示例目录里只塞了 3 行。**这个结果证明不了 100 行的边界**，要证明 item 数量，fixture 里得有足够的数据，或者断言只能落在「接受的 pageSize」上。原文专门提醒了这一点。

## 第四步：先写会失败的测试，再让它实现

写代码之前先把验收矩阵定下来。每一行要写清：期望状态码、响应契约、以及下游查询是否允许执行。

矩阵最小覆盖：省略输入（证明默认值兼容）、1 和 100（证明闭合边界）、0 和 101（证明邻近越界被拒）、一个负数（让原缺陷显式化）、一个非数字（证明绑定路径没被忽略）。

不要换成「让 Claude Code 写七个测试」。一个参数化测试能覆盖好几组输入，而授权和下游行为可能需要单独的测试。重要的是断言的行为，不是测试的数量。

在已有仓库里，顺序应该是：**先写回归测试，在基线上证明它失败**；再让 agent 实现改动，证明同一个测试通过。没有基线失败这一步，绿灯可能来自一个根本没戳中缺陷的测试。

选测试类型同样有讲究：

- handler 单元测试能验证隔离的范围策略或结果对象，但它证明不了路由注册、查询绑定、中间件、授权和序列化后的 HTTP 输出。
- HTTP 集成测试让请求真正穿过应用，检查状态码和响应体。如果这次改动的风险包含租户过滤，fixture 就必须真的跑那条关系，而不是把它 mock 掉。

还有一类测试很容易看起来很强：只在响应成功时才执行的断言。如果成功是前提，就无条件先断言成功再检查 body；如果拒绝是要求，就直接断言拒绝。在失败路径上跳掉关键断言的测试，给不出回归覆盖。

本文不提供完整的测试工程：示例本身没有测试宿主，加 xUnit 会引入它自己的依赖。真正要固定下来的是断言清单——第三步那段 PowerShell 循环就是最小可跑的集成检查，换到真实仓库里，把它变成已有测试框架的参数化用例即可。

## 第五步：把构建、测试、发布留在编辑请求之外

官方的 permissions 文档讲的是运行时强制的规则和模式差异。这些控制应该反映你允许的工作范围，而不是把所有开发者命令当成可互换的东西。

一个构建可以触发自定义 target；一次测试可能启动带外部依赖的 fixture；一次迁移会改持久化状态；一条发布命令会把结果暴露给用户。**一个分页校验任务并不隐含地授权这四件事。**

如果验证在远端跑，记录四样东西：确切的 revision、命令、环境、结果。并且保证「被验证的版本」就是「被审查的版本」——上一个 commit 的绿灯不证明最终代码的行为。

## 第六步：把 diff 当契约变更来审

Claude Code 实现完之后，别只看那个 `if`。按这张清单过一遍：

| 检查项     | 要看什么                                                |
| ---------- | ------------------------------------------------------- |
| 参数形状   | 是否仍是可选 `int?`，默认值是否还是 20                  |
| 响应契约   | 成功响应的字段名、类型、集合形状有没有变                |
| 路由上下文 | 路由是否还在原来的授权分组里，没被搬出去                |
| 测试有效性 | 测试是否真的发了 0、101、负数和 `abc`，是否断言了响应体 |
| 数据充分性 | fixture 的数据量够不够支撑 item 数量的断言              |
| 隐藏失败   | 有没有用 skip 或宽泛的异常处理把无关失败藏起来          |
| 文件范围   | 新增包、schema 变更、日志重写、路由搬移，有没有具体理由 |

最后一项最容易放水。一次范围校验不需要迁移，也不需要新包。如果实现里出现了 schema 或依赖变更，那是一个**重新确认范围**的信号，而不是顺手批准的「清理」。日志和追踪同理：校验改动不该变成一次无关的日志配置重写。

## 常见问题

**为什么先 trace 而不是直接让 agent 生成代码？**

Trace 确立了输入、默认值、校验和查询各自住在哪一层。没有这一步，一个看起来合理的实现很容易绕过既有契约，或者把规则重复到错误的层。

**`pageSize` 默认 20 是 ASP.NET Core 的默认值吗？**

不是。它是这篇文章里的示例业务要求。真实端点的默认值和允许范围必须来自它自己的契约。

**非数字和 0 走的是同一条路径吗？**

不是。非数字在参数绑定阶段就失败了，走框架的 400 且不经过 handler；0 是绑定成功的整数，被业务规则拒绝。这次的实测输出把它们区分得很清楚：前者 body 为空，后者是自定义错误载荷。

**示例可以直接盖到生产端点上吗？**

不行。示例用匿名访问、内存数据隔离了校验逻辑，它的 HTTP 检查覆盖不到你的生产契约。真实应用的认证、租户、持久化、可观测性和错误约定都要保留。

**handler 单元测试能证明 HTTP 契约吗？**

不能完全证明。路由、绑定、中间件、授权、序列化需要对应的集成证据；隔离测试仍然适合更小的逻辑边界。

**验证没跑的时候，agent 应该怎么报告？**

它应该说清「代码已写但未执行」、列出缺了哪些检查、并且不要声称成功。这样审查才能把代码阅读和运行时证据分开。

## 下一步

下次把端点改动交给 coding agent，先把契约表和七种输入的断言写好，再让它 trace、再让它实现。它交回 diff 之后，按第六步那张表过一遍。

验证没跑过就别合并。契约写清、证据可复现、边界被 diff 保住，三样都在，这次改动才算有边界——diff 是三行还是三十行并不重要。

如果你也在把 coding agent 接进日常开发，Aide Hub 会继续写 .NET、开发工具和 AI 助手的落地经验。

## 参考

- [Make a Bounded ASP.NET Core Change with Claude Code](https://www.devleader.ca/2026/10/21/make-a-bounded-aspnet-core-change-with-claude-code) — 原文，Nick Cosentino，Dev Leader。
- [Claude Code overview](https://code.claude.com/docs/en/overview) — 原文引用的能力说明。
- [Common workflows](https://code.claude.com/docs/en/common-workflows) — 原文引用的「先定位再修改」工作流。
- [Memory (CLAUDE.md)](https://code.claude.com/docs/en/memory) — 原文引用，说明仓库说明属于上下文而非强制。
- [Permissions](https://code.claude.com/docs/en/permissions) — 原文引用，运行时权限规则。
- [Minimal API parameter binding](https://learn.microsoft.com/en-us/aspnet/core/fundamentals/minimal-apis/parameter-binding?view=aspnetcore-10.0) — 原文引用的绑定文档。
- [Minimal API responses](https://learn.microsoft.com/en-us/aspnet/core/fundamentals/minimal-apis/responses?view=aspnetcore-10.0) — 原文引用，`IResult`、`TypedResults` 与结果联合类型。
