---
pubDatetime: 2026-09-08T08:37:04+08:00
title: "谁拥有 next：Pipeline、职责链与中间件"
description: "Pipeline、职责链与 ASP.NET Core 中间件都像一串组件，真正的区别是谁拥有 continuation、组件被期望做什么。对照转换、选择与拦截三种契约，配可运行示例、短路含义与顺序解读，帮你命名并审查现有设计。"
tags: ["Pipeline", "Design Patterns", "ASP.NET Core", "Architecture"]
slug: "pipeline-chain-of-responsibility-middleware"
ogImage: "../../assets/1059/01-cover.jpg"
source: "https://www.devleader.ca/2026/09/07/pipeline-vs-chain-of-responsibility-vs-aspnet-core-middleware"
---

三个名字经常被互换：Pipeline、Chain of Responsibility、ASP.NET Core middleware。它们确实都像「一串有序组件」——但这正是混淆的来源。Nick Cosentino 在 [Pipeline vs Chain of Responsibility vs ASP.NET Core Middleware](https://www.devleader.ca/2026/09/07/pipeline-vs-chain-of-responsibility-vs-aspnet-core-middleware) 里给出的区分标准很干脆：**看谁拥有 continuation，以及每个组件被期望做什么。**

本文的三段示例按 net10.0、C# 14 与可空引用类型编写，我已在 .NET 10.0.301 SDK 下编译运行验证；中间件行为与 [ASP.NET Core 10 官方文档](https://learn.microsoft.com/en-us/aspnet/core/fundamentals/middleware)核对一致。

## 一表看清三种模型

| 问题                | Pipeline             | Chain of Responsibility      | ASP.NET Core 中间件                 |
| ------------------- | -------------------- | ---------------------------- | ----------------------------------- |
| 主要目的            | 分阶段转换或处理     | 选出有能力的处理器           | 拦截并组合 HTTP 请求/响应行为       |
| 正常参与方式        | 每个必需阶段按序运行 | 一个或多个候选处理器可能拒绝 | 每个被到达的中间件决定是否调用 next |
| Continuation 所有者 | 通常是外部 runner    | 通常是当前处理器             | 当前中间件                          |
| 输入/输出形态       | 常随阶段变化         | 通常同一个请求保持同型       | 共享 HttpContext，异步 Task 返回    |
| 短路含义            | 到达终止结果而停止   | 处理器接受了请求而停止       | 中间件未调用 next 而停止            |
| 逆向回卷            | 非固有               | 非固有                       | 内建：`await next` 之后的代码       |
| 顺序的意义          | 转换依赖             | 候选优先级                   | 请求顺序 + 响应逆序                 |

表中描述的是每个模型的「重心」。真实系统可以混合特征：pipeline 可以拒绝一项；职责链的处理器可以在转发前丰富请求；中间件可以改造 HttpContext 里的值。关键问题是，**哪个行为定义了架构**。

## Pipeline：分阶段转换

微软的 Pipes and Filters 模式指南把流水线描述为「由管道连接的独立过滤器，每个过滤器消费输入、产出输出」。在进程内的 C# Pipeline 里，这些边界可能就是方法调用与类型值。

重要的不变量是：**阶段属于计划内的转换。** 校验不是「可能处理订单的候选者」，定价也不是「同一请求的另一个候选」。校验的输出成为定价的输入：

```csharp
namespace PatternComparison.PipelineExample;

public sealed record RawOrder(
    string CustomerId,
    IReadOnlyList<RawOrderLine> Lines);

public sealed record RawOrderLine(
    string Sku,
    int Quantity,
    decimal UnitPrice);

public sealed record ValidatedOrder(
    string CustomerId,
    IReadOnlyList<RawOrderLine> Lines);

public sealed record PricedOrder(
    string CustomerId,
    decimal Total);

public static class OrderPipeline
{
    public static PricedOrder Execute(RawOrder input)
    {
        ValidatedOrder validated = Validate(input);
        PricedOrder priced = CalculatePrice(validated);

        return priced;
    }

    private static ValidatedOrder Validate(RawOrder input)
    {
        if (string.IsNullOrWhiteSpace(input.CustomerId))
        {
            throw new ArgumentException(
                "A customer identifier is required.",
                nameof(input));
        }

        if (input.Lines.Count == 0)
        {
            throw new ArgumentException(
                "At least one order line is required.",
                nameof(input));
        }

        return new ValidatedOrder(
            input.CustomerId.Trim(),
            input.Lines);
    }

    private static PricedOrder CalculatePrice(
        ValidatedOrder input)
    {
        decimal total = input.Lines.Sum(
            line => line.Quantity * line.UnitPrice);

        return new PricedOrder(input.CustomerId, total);
    }
}
```

`Execute` 拥有 continuation。每个转换不接收 `next` 委托，也不去寻找有能力的后继者。序列是显式的：`RawOrder` 变成 `ValidatedOrder`，再变成 `PricedOrder`。即使你用可复用 runner 统一执行同一契约的阶段，架构要点不变：**runner 决定下一个阶段是谁。**

## Chain of Responsibility：候选处理器选择

GoF 风格的职责链意图是：给多个对象处理请求的机会，沿链传递直到某个对象处理它——发送者不需要知道最终接收者。

这是选择模型。支持请求可以由账单、技术支持或兜底处理。每个处理器是**本质上同一个请求**的候选：

```csharp
namespace PatternComparison.ChainExample;

public sealed record SupportRequest(
    string Category,
    string Description);

public interface ISupportHandler
{
    ISupportHandler SetNext(ISupportHandler next);

    string Handle(SupportRequest request);
}

public abstract class SupportHandler : ISupportHandler
{
    private ISupportHandler? _next;

    public ISupportHandler SetNext(ISupportHandler next)
    {
        _next = next;
        return next;
    }

    public virtual string Handle(SupportRequest request)
    {
        return _next?.Handle(request)
            ?? "No handler accepted the request.";
    }
}

public sealed class BillingHandler : SupportHandler
{
    public override string Handle(SupportRequest request)
    {
        return request.Category.Equals(
            "billing",
            StringComparison.OrdinalIgnoreCase)
            ? $"Billing accepted: {request.Description}"
            : base.Handle(request);
    }
}

public sealed class TechnicalHandler : SupportHandler
{
    public override string Handle(SupportRequest request)
    {
        return request.Category.Equals(
            "technical",
            StringComparison.OrdinalIgnoreCase)
            ? $"Technical support accepted: {request.Description}"
            : base.Handle(request);
    }
}

public static class SupportChain
{
    public static ISupportHandler Create()
    {
        BillingHandler billing = new();
        TechnicalHandler technical = new();

        billing.SetNext(technical);

        return billing;
    }
}
```

请求不会在每一跳变成不同的类型：账单处理器检查它，要么处理要么委托；只有账单拒绝，技术支持才接到同一个概念上的请求。这里决定架构的边界是**候选选择**，而不是基类语法。

## ASP.NET Core 中间件：自己拥有 continuation

中间件的续延契约比典型 Pipeline 更强。官方文档写明：**每个中间件选择是否把请求传给下一个组件，并可以在该调用前后执行工作。**

`RequestDelegate` 接收 `HttpContext`、返回 `Task`；用 `Use` 注册的组件拿到 `next` 委托；`Run` 注册终点委托，那个分支不再继续到后续中间件：

```csharp
using Microsoft.AspNetCore.Http;

WebApplicationBuilder builder =
    WebApplication.CreateBuilder(args);
WebApplication app = builder.Build();

app.Use(async (HttpContext context, RequestDelegate next) =>
{
    Console.WriteLine("A: request");

    await next(context);

    Console.WriteLine("A: response");
});

app.Use(async (HttpContext context, RequestDelegate next) =>
{
    Console.WriteLine("B: request");

    if (context.Request.Path == "/blocked")
    {
        context.Response.StatusCode =
            StatusCodes.Status403Forbidden;
        await context.Response.WriteAsync("Blocked.");
        return;
    }

    await next(context);

    Console.WriteLine("B: response");
});

app.Run(async context =>
{
    Console.WriteLine("Endpoint");
    await context.Response.WriteAsync("Hello.");
});

await app.RunAsync();
```

正常请求按注册顺序进入、按逆序返回（我本地实测输出与此完全一致）：

```text
A: request
B: request
Endpoint
B: response
A: response
```

访问 `/blocked` 时，中间件 B 不调用 `next`，剩余请求管道被短路：endpoint 不执行，B 的 after-next 代码不出现在该分支，控制权回到 A——A 已经调用了 B 并在回卷，所以它的响应侧代码照常运行（实测 `A: request → B: request → A: response`，HTTP 403）。

这个嵌套调用形状是关键：**中间件不是向前迭代，而是每个组件包住它调用的下游委托。**

## 只有中间件会逆序回卷

假设注册 A、B、C：请求侧执行 A、B、C；如果每个组件都 `await next`，完成顺序从 C 回到 B 回到 A。于是产生两种顺序：

- 请求侧工作：A, B, C。
- 响应侧工作：C, B, A。

普通分阶段 Pipeline 没有自动反向回卷：三个转换 A、B、C 运行完，结果直接离开 C——除非 runner 显式添加清理、补偿或其他反向操作。职责链也没有固有的响应回卷：处理器可以调用后继再执行后续工作，但那让它更像中间件或 Decorator，不属于 GoF 选择意图的要求。

「中间件像 Decorator 又像职责链」正是这个包裹质量：它把候选续延与嵌套包裹结合，而经典 Pipeline 通常强调前向转换。

## 短路并不总是同一个意思

「short-circuit」三个设计都有，含义却跟着模型走：

- **Pipeline 短路**：runner 停在某个阶段产生了终止结果（如拒绝）。runner 仍然拥有规则——阶段返回结果，通常不会接收或扣住续延委托。
- **职责链短路**：处理器接受了请求且不转发。这正是期望的选择行为，链找到了接收者。
- **中间件短路**：某组件不调用 `next`，后续组件被短路，它成为该请求分支的终点，通常表现为写出响应或以其他方式完成请求处理。

三种情况可能产生相似的控制流，但表达的契约不同。把三者都叫「带提前退出的管道」，就丢掉了它们各自存在的理由。

## 顺序回答不同的问题

- **Pipeline 中**，顺序回答：哪个转换必须发生在下一个转换能消费它的输入之前？
- **职责链中**，顺序回答：哪个候选最先有机会处理请求？
- **中间件中**，顺序同时回答：哪个组件先看到请求？哪个包裹最后看到响应？

这就是注册顺序后果不同的原因：把校验移到定价之后，可能违反数据依赖；把通用处理器放到特定处理器之前，特定处理器可能永远收不到匹配请求；移动授权或响应压缩中间件，会改变哪些 HTTP 行为包裹哪些下游组件。**顺序不只是列表位置，它表达依赖、优先级或嵌套关系。**

## 同一需求，三个模型各司其职

考虑这个需求：「拒绝无效订单、记录诊断、返回 HTTP 响应」。一句话可能同时涉及三个模型，但不会让它们等价：

- **Pipeline** 校验并定价。校验返回终止拒绝，runner 不再执行定价。它的结果描述业务处理，不是 HTTP 响应。
- **职责链** 选出能处理该订单类型的组件：零售处理器拒绝批发订单，批发处理器接受。选型决定接收者，不替代接收者内部的订单校验阶段。
- **中间件** 在 endpoint 前附加关联 ID，把下游未处理的异常翻译成 HTTP 响应。它包裹 HTTP 执行——但不应仅仅因为每个请求都经过它，就成为定价规则的藏身处。

最后形成的调用路径可以是：中间件建立 HTTP 上下文并调用 `next`；endpoint 代码请职责链选出负责的用例；选出的处理器执行类型化的业务 Pipeline；控制权沿中间件响应路径返回。**每一层都有独立的存在理由。** 去掉名字、只看「一串组件」，这些职责就被抹掉了。

## 混合设计：重心变了要及时改名

一个设计可以从某个模型开始，逐步采用另一个模型的定义性行为。这不自动是错的，但在调用者形成错误预期之前，契约应该改名或记录。

衡量的方法是看行为契约，而不是类名：

- 每个阶段都收到 `next`、可以包裹下游工作 → 中间件式。
- 阶段主要检查同一个请求、第一个有能力的组件接管 → 职责链式。
- 处理器总是都运行、各自产出下一个类型化表示 → Pipeline 式——即使类名叫 Handler。

类名（Processor、Handler、Filter、Middleware）是线索，不是证据。按行为契约分类，也给了审查者一个共同的词汇去质疑顺序、所有权与短路的假设。

## 保持 HTTP 生命周期边界可见

ASP.NET Core 中间件绑定 `HttpContext`、HTTP 请求生命周期与框架启动时的组合。官方文档说明：约定式中间件**按应用生命周期构造一次**；scoped 依赖应放入 `InvokeAsync`；工厂激活的 `IMiddleware` 支持按请求激活。

这提醒我们 middleware 不是与传输无关的阶段抽象——它的生命周期与契约都是为 ASP.NET Core 请求设计的。如果同一个业务转换必须从 HTTP endpoint、队列消费者和命令行工具运行，把它放进普通服务或 Pipeline 阶段，让中间件处理 HTTP 特有的事情，并在合适的边界调用那个服务。

另外提一句（原文的谨慎立场）：Microsoft Agent Framework 的 middleware（agent-run、function-calling、IChatClient 中间件）在续延链意义上可用作**类比**，但它不是这三个通用模式的权威定义，具体实现请以当前 Microsoft 文档为准。

## 按续延所有权选择

名字模糊时，按顺序问自己：

1. 每个组件都必须转换数据供下一个必需组件消费？→ Pipeline。
2. 多个组件是候选、真实接收者对发送者未知？→ 职责链。
3. 每个组件收到 `next`、包裹下游工作、操作 `HttpContext`？→ ASP.NET Core 中间件。
4. 逆序响应行为必不可少？→ 中间件直接具备这个形状。
5. 逻辑必须在 HTTP 之外运行？→ 把业务处理留在中间件之外，即使中间件是发起者。

也可以不把单一标签强加给一个有意组合多个模型的系统：HTTP endpoint 经中间件进入，调用职责链选择处理器，处理器内部执行类型化 Pipeline——只要每层遵守自己的契约，架构依然是可理解的。

落到具体动作：去你的代码库里找一个「叫 Handler 但每层都运行、每层都转换类型」的类，以及一个「里面藏着业务转换」的中间件——前者按续延契约改名或补文档，后者把转换抽到普通服务。区分这三者节省的不是命名功夫，是等 bug 出在「该谁负责」上的排查时间。

Aide Hub 会继续分享 AI 助手、开发工具与软件工程实践中的具体做法。

## 参考

- [Dev Leader：Pipeline vs Chain of Responsibility vs ASP.NET Core Middleware](https://www.devleader.ca/2026/09/07/pipeline-vs-chain-of-responsibility-vs-aspnet-core-middleware)
- [Microsoft Learn：ASP.NET Core middleware](https://learn.microsoft.com/en-us/aspnet/core/fundamentals/middleware)
