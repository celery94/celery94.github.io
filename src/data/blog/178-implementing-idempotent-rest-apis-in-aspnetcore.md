---
pubDatetime: 2024-10-26
tags: []
source: https://www.milanjovanovic.tech/blog/implementing-idempotent-rest-apis-in-aspnetcore?utm_source=newsletter&utm_medium=email&utm_campaign=tnw113
author: Milan Jovanović
title: 在ASP.NET Core中实现幂等性REST API
description: 学习如何在ASP.NET Core Web API中实现幂等性，以提高可靠性并防止分布式系统中的重复操作。
---

幂等性是REST API中的关键概念，可确保系统的可靠性和一致性。幂等操作即使重复多次，也不会改变初始API请求之外的结果。这种特性在分布式系统中特别重要，因为网络故障或超时可能导致请求重复。

在API中实现幂等性有以下几个好处：

- 防止意外的重复操作
- 提高分布式系统中的可靠性
- 优雅地处理网络问题和重试

在本周的内容中，我们将探讨如何在ASP.NET Core API中实现幂等性，确保您的系统保持稳健和可靠。

## 什么是幂等性？

在Web API的上下文中，幂等性意味着多次发出相同请求应该产生与单次请求相同的效果。换句话说，无论客户端发送多少次相同的请求，服务器端的效果只会发生一次。

[RFC 9110](https://www.rfc-editor.org/rfc/rfc9110)标准关于HTTP语义提供了我们可以使用的定义。以下是它对**幂等方法**的描述：

> 如果使用某种方法的多个相同请求对服务器的预期效果与单个请求的效果相同，那么该请求方法被认为是“幂等的”。
>
> 本规范定义的请求方法中，PUT、DELETE和安全请求方法\[（GET、HEAD、OPTIONS和TRACE）- 作者注\]是幂等的。

_— [RFC 9110 (HTTP语义), 第9.2.2节, 第1段](https://www.rfc-editor.org/rfc/rfc9110#section-9.2.2-1)_

然而，接下来的段落相当有趣。它澄清了服务器可以实现不适用于资源的“其他非幂等的副作用”。

> ...幂等性属性仅适用于用户请求的内容；服务器可以自由地单独记录每个请求，保留修订控制历史，或为每个幂等请求实现其他非幂等副作用。

_— [RFC 9110 (HTTP语义), 第9.2.2节, 第2段](https://www.rfc-editor.org/rfc/rfc9110#section-9.2.2-2)_

实现幂等性不仅仅是遵循HTTP方法语义，它显著提高了API的可靠性，特别是在网络问题可能导致请求重试的分布式系统中。通过实现幂等性，您可以防止由于客户端重试而可能发生的重复操作。

## 哪些HTTP方法是幂等的？

一些HTTP方法本质上是幂等的：

- `GET`, `HEAD`: 获取数据而不修改服务器状态。
- `PUT`: 更新资源，无论重复多少次结果相同。
- `DELETE`: 删除资源，多次请求结果相同。
- `OPTIONS`: 获取通信选项信息。

`POST`本质上不是幂等的，因为它通常创建资源或处理数据。重复的`POST`请求可能会创建多个资源或触发多次操作。

然而，我们可以使用自定义逻辑为`POST`方法实现幂等性。

**注意**：尽管`POST`请求本质上不是幂等的，但我们可以设计它们成为幂等。例如，在创建前检查现有资源，确保重复的`POST`请求不会导致重复的操作或资源。

## 在ASP.NET Core中实现幂等性

为了实现幂等性，我们将使用一种涉及幂等性键的策略：

1. 客户端为每个操作生成一个唯一键，并在自定义头中发送。
2. 服务器检查是否已见过此键：
   - 对于新键，处理请求并存储结果。
   - 对于已知键，返回存储的结果而不重新处理。

这确保了由于网络问题导致的重试请求仅在服务器上处理一次。

我们可以通过结合`Attribute`和`IAsyncActionFilter`来为控制器实现幂等性。现在，我们可以指定`IdempotentAttribute`以将幂等性应用于控制器端点。

**注意**：当请求失败（返回4xx/5xx）时，我们不缓存响应。这允许客户端使用相同的幂等性键重试。然而，这意味着相同键的失败请求后紧接着成功请求将会成功——确保这符合您的业务需求。

```csharp
[AttributeUsage(AttributeTargets.Method)]
internal sealed class IdempotentAttribute : Attribute, IAsyncActionFilter
{
    private const int DefaultCacheTimeInMinutes = 60;
    private readonly TimeSpan _cacheDuration;

    public IdempotentAttribute(int cacheTimeInMinutes = DefaultCacheTimeInMinutes)
    {
        _cacheDuration = TimeSpan.FromMinutes(minutes);
    }

    public async Task OnActionExecutionAsync(
        ActionExecutingContext context,
        ActionExecutionDelegate next)
    {
        // 从请求中解析幂等性键头
        if (!context.HttpContext.Request.Headers.TryGetValue(
                "Idempotence-Key",
                out StringValues idempotenceKeyValue) ||
            !Guid.TryParse(idempotenceKeyValue, out Guid idempotenceKey))
        {
            context.Result = new BadRequestObjectResult("无效或缺失的幂等性键头");
            return;
        }

        IDistributedCache cache = context.HttpContext
            .RequestServices.GetRequiredService<IDistributedCache>();

        // 检查是否已处理此请求并返回已缓存的响应（如果存在）
        string cacheKey = $"Idempotent_{idempotenceKey}";
        string? cachedResult = await cache.GetStringAsync(cacheKey);
        if (cachedResult is not null)
        {
            IdempotentResponse response = JsonSerializer.Deserialize<IdempotentResponse>(cachedResult)!;

            var result = new ObjectResult(response.Value) { StatusCode = response.StatusCode };
            context.Result = result;

            return;
        }

        // 执行请求并缓存响应指定的持续时间
        ActionExecutedContext executedContext = await next();

        if (executedContext.Result is ObjectResult { StatusCode: >= 200 and < 300 } objectResult)
        {
            int statusCode = objectResult.StatusCode ?? StatusCodes.Status200OK;
            IdempotentResponse response = new(statusCode, objectResult.Value);

            await cache.SetStringAsync(
                cacheKey,
                JsonSerializer.Serialize(response),
                new DistributedCacheEntryOptions { AbsoluteExpirationRelativeToNow = _cacheDuration }
            );
        }
    }
}

internal sealed class IdempotentResponse
{
    [JsonConstructor]
    public IdempotentResponse(int statusCode, object? value)
    {
        StatusCode = statusCode;
        Value = value;
    }

    public int StatusCode { get; }
    public object? Value { get; }
}
```

**注意**：在检查和设置缓存之间存在一个小的[**竞争条件**](https://www.milanjovanovic.tech/blog/solving-race-conditions-with-ef-core-optimistic-locking)窗口。为了绝对的一致性，我们应考虑使用分布式锁模式，尽管这会增加复杂性和延迟。

现在，我们可以将此属性应用于我们的控制器操作：

```csharp
[ApiController]
[Route("api/[controller]")]
public class OrdersController : ControllerBase
{
    [HttpPost]
    [Idempotent(cacheTimeInMinutes: 60)]
    public IActionResult CreateOrder([FromBody] CreateOrderRequest request)
    {
        // 处理订单...

        return CreatedAtAction(nameof(GetOrder), new { id = orderDto.Id }, orderDto);
    }
}
```

**使用Minimal API实现幂等性**

要在Minimal API中实现幂等性，我们可以使用`IEndpointFilter`。

```csharp
internal sealed class IdempotencyFilter(int cacheTimeInMinutes = 60)
    : IEndpointFilter
{
    public async ValueTask<object?> InvokeAsync(
        EndpointFilterInvocationContext context,
        EndpointFilterDelegate next)
    {
        // 从请求中解析幂等性键头
        if (TryGetIdempotenceKey(out Guid idempotenceKey))
        {
            return Results.BadRequest("无效或缺失的幂等性键头");
        }

        IDistributedCache cache = context.HttpContext
            .RequestServices.GetRequiredService<IDistributedCache>();

        // 检查是否已处理此请求并返回已缓存的响应（如果存在）
        string cacheKey = $"Idempotent_{idempotenceKey}";
        string? cachedResult = await cache.GetStringAsync(cacheKey);
        if (cachedResult is not null)
        {
            IdempotentResponse response = JsonSerializer.Deserialize<IdempotentResponse>(cachedResult)!;
            return new IdempotentResult(response.StatusCode, response.Value);
        }

        object? result = await next(context);

        // 执行请求并缓存响应指定的持续时间
        if (result is IStatusCodeHttpResult { StatusCode: >= 200 and < 300 } statusCodeResult
            and IValueHttpResult valueResult)
        {
            int statusCode = statusCodeResult.StatusCode ?? StatusCodes.Status200OK;
            IdempotentResponse response = new(statusCode, valueResult.Value);

            await cache.SetStringAsync(
                cacheKey,
                JsonSerializer.Serialize(response),
                new DistributedCacheEntryOptions
                {
                    AbsoluteExpirationRelativeToNow = TimeSpan.FromMinutes(cacheTimeInMinutes)
                }
            );
        }

        return result;
    }
}

// 我们必须实现一个自定义结果以写入状态码
internal sealed class IdempotentResult : IResult
{
    private readonly int _statusCode;
    private readonly object? _value;

    public IdempotentResult(int statusCode, object? value)
    {
        _statusCode = statusCode;
        _value = value;
    }

    public Task ExecuteAsync(HttpContext httpContext)
    {
        httpContext.Response.StatusCode = _statusCode;

        return httpContext.Response.WriteAsJsonAsync(_value);
    }
}
```

现在，我们可以将此端点过滤器应用于我们的Minimal API端点：

```csharp
app.MapPost("/api/orders", CreateOrder)
    .RequireAuthorization()
    .WithOpenApi()
    .AddEndpointFilter<IdempotencyFilter>();
```

除了上述两种实现方式外，还可以在自定义中间件中实现幂等性逻辑。

## 最佳实践和注意事项

以下是我在实现幂等性时始终牢记的重要事项。

缓存持续时间比较棘手。我力求覆盖合理的重试窗口而不保留过时数据。合理的缓存时间通常从几分钟到24-48小时不等，具体取决于您的具体用例。

并发可能会很棘手，尤其是在高流量的API中。使用分布式锁的线程安全实现效果很好。当多个请求同时到达时，它可以保持控制。但这应该是罕见的情况。

对于分布式设置，我最常用的是Redis。它作为共享缓存非常适合，保持幂等性在所有API实例中一致。此外，它还处理分布式锁定。

如果客户端使用不同的请求体重复使用幂等性键怎么办？在这种情况下，我会返回错误。我的做法是散列请求体并将其与幂等性键一起存储。当请求到达时，我比较请求体的哈希值。如果它们不同，我会返回错误。这可以防止幂等性键的滥用并维护API的完整性。

## 总结

在REST API中实现幂等性可以增强服务的可靠性和一致性。它确保相同的请求得到相同的结果，防止意外的重复并优雅地处理网络问题。

虽然我们的实现提供了一个基础，但我建议根据您的需求进行调整。专注于API中关键的操作，尤其是那些修改系统状态或触发重要业务流程的操作。

通过拥抱幂等性，您可以构建更稳健且用户友好的API。
