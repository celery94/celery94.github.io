---
pubDatetime: 2024-03-04
tags: [".NET", "C#"]
  [
    .net,
    c#,
    csharp,
    dotnet,
    dotnet core,
    fault handling,
    polly,
    programming,
    retry mechanisms,
    retry policies,
    software architecture,
    software engineering,
    c# / .net / dotnet,
    tutorial,
  ]
source: https://www.devleader.ca/2024/03/03/how-to-use-polly-in-c-easily-handle-faults-and-retries/
author: Nick Cosentino
title: 如何在C#中使用Polly：轻松处理故障和重试
description: 学习如何在C#中使用Polly处理故障和重试并变得轻松！查看这3个代码示例，展示了C#中不同用例的Polly使用情况！
---

# 如何在C#中使用Polly：轻松处理故障和重试

> ## 摘录
>
> 学习如何在C#中使用Polly处理故障和重试并变得轻松！查看这3个代码示例，展示了C#中不同用例的Polly使用情况！
>
> 原文链接：[How To Use Polly In C# Easily Handle Faults And Retries](https://www.devleader.ca/2024/03/03/how-to-use-polly-in-c-easily-handle-faults-and-retries/)

---

在本文中，我们将探索如何在C#中使用Polly，以及它如何帮助我们轻松处理故障和重试。Polly是一个流行的NuGet包，提供了一系列强大的工具和模式，可以极大地简化我们代码中的故障处理和重试机制。

通过在我们的代码中利用Polly，我们可以处理各种类型的故障，如网络错误或数据库连接失败。我们可以[实现智能的重试策略](https://www.devleader.ca/2023/11/22/how-to-implement-the-strategy-pattern-in-c-for-improved-code-flexibility/)，以确保我们的应用程序在其中一个不可避免出现问题时不会崩溃（记住：墨菲定律）。无论我们需要处理短暂的故障还是简单地重试失败的操作，Polly都提供了一个灵活可配置的方法来处理这些场景。

我将向您展示3个有趣的代码示例，展示了C#中不同用例的Polly使用情况——让我们马上开始吧！

---

## 1 – 在C#中使用Polly处理故障

在构建稳健可靠的应用程序时，有效地处理故障非常重要。故障处理是指处理程序执行过程中可能发生的错误、异常和失败——我们将在C#中使用Polly来帮助我们。

为了演示Polly如何处理连接问题，让我们考虑一个我们的应用程序需要对外部API进行网络请求的场景。我们希望确保在出现任何与连接相关的故障时，请求能够自动重试，比如临时的网络中断或间歇性故障。

让我们看看如何在C#中使用Polly处理网络请求中的连接问题：

```csharp
using Polly;
using Polly.Retry;

var handler = new NetworkRequestHandler();
var response = await handler.MakeNetworkRequestAsync("https://www.devleader.ca/sitemap.xml");
Console.WriteLine($"Response status code: {response.StatusCode}");

public class NetworkRequestHandler
{
    private readonly HttpClient _httpClient;
    private readonly AsyncRetryPolicy<HttpResponseMessage> _retryPolicy;

    public NetworkRequestHandler()
    {
        _httpClient = new HttpClient();

        // 定义一个重试策略：在HttpRequestException出现时重试，使用指数退避机制重试3次
        _retryPolicy = Policy
            .HandleResult<HttpResponseMessage>(r => !r.IsSuccessStatusCode)
            .Or<HttpRequestException>()
            .WaitAndRetryAsync(3, retryAttempt =>
                TimeSpan.FromSeconds(Math.Pow(2, retryAttempt)),
                onRetry: (outcome, timespan, retryAttempt, context) =>
                {
                    Console.WriteLine($"Request failed with {outcome.Exception?.Message}. Waiting {timespan} before next retry. Retry attempt {retryAttempt}.");
                });
    }

    public async Task<HttpResponseMessage> MakeNetworkRequestAsync(string requestUri)
    {
        return await _retryPolicy.ExecuteAsync(async () =>
        {
            Console.WriteLine($"Making request to {requestUri}");
            var response = await _httpClient.GetAsync(requestUri);
            if (!response.IsSuccessStatusCode)
            {
                Console.WriteLine($"Request failed with status code: {response.StatusCode}");
                throw new HttpRequestException($"Request to {requestUri} failed with status code {response.StatusCode}");
            }
            return response;
        });
    }
}
```

在上面的代码示例中，我们定义了一个`NetworkRequestHandler`类，该类封装了使用来自.NET框架的`HttpClient`类进行网络请求的逻辑。我们使用Polly初始化了一个具有`HttpRequestException`故障条件的`AsyncRetryPolicy`。这意味着每当抛出`HttpRequestException`时，该策略就会被触发。

`WaitAndRetry`方法用于指定重试次数和每次重试之间的时间延迟。在本示例中，我们会重试3次请求，并使用公式`TimeSpan.FromSeconds(Math.Pow(2, retryAttempt))`来递增延时。

在`MakeNetworkRequest`方法中，我们使用Polly策略来执行网络请求，通过在策略上调用`Execute`方法。如果在执行过程中发生了`HttpRequestException`，Polly将自动根据定义的策略重试请求。

---

## 2 – 在C#中使用Polly的重试机制

在软件工程中，常常会遇到特定操作由于网络问题、资源限制或其他短暂的故障而临时失败的情况。在这些情况下，重试机制被实现为自动重试失败的操作若干次，直至成功或到达最大重试次数。这有助于提高软件应用程序的可靠性和鲁棒性。

### 使用Polly在C#中简化重试机制：

当涉及到在C#中实现重试机制时，NuGet包Polly派上了用场。Polly是一个功能强大的库，提供了一种既简单又优雅的方式来在代码中处理故障和重试。它通过将复杂的重试逻辑封装成一组可重用的策略来简化重试的实现过程。

### 使用Polly自动重试失败的数据库操作：

我们来考虑一个场景，我们需要执行一个数据库操作，例如将记录插入到表中，但可能由于临时的连接问题或资源限制导致操作失败。有了Polly，我们可以通过应用重试策略来轻松处理这种失败。

首先，我们需要通过将以下行添加到我们项目文件的依赖关系部分来安装Polly NuGet包（请记住，您想要获取的版本很可能是更新的！）:

```xml
<ItemGroup>
    <PackageReference Include="Polly" Version="8.3.0" />
</ItemGroup>
```

安装包后，我们可以开始使用Polly来实现重试机制。这里有一个代码片段示例，演示了如何使用Polly来自动重试失败的数据库操作：

```csharp
using Polly;

using System.Data.SqlClient;

async Task<bool> InsertRecordAsync(
    Record record,
    CancellationToken cancellationToken)
{
    int maxRetryCount = 3;
    var connectionString = "// TODO: configure this elsewhere...";

    var retryPolicy = Policy
        .Handle<SqlException>() // Specify the type of exception to handle
        .WaitAndRetryAsync(maxRetryCount, retryAttempt =>
            TimeSpan.FromSeconds(Math.Pow(2, retryAttempt))); // Exponential backoff strategy

    return await retryPolicy.ExecuteAsync(async ct =>
    {
        using var connection = new SqlConnection(connectionString);
        await connection.OpenAsync();

        using var command = connection.CreateCommand();
        command.CommandText = "INSERT INTO Records (Id, Name) VALUES (@Id, @Name)";
        command.Parameters.AddWithValue("@Id", record.Id);
        command.Parameters.AddWithValue("@Name", record.Name);

        try
        {
            // Perform the database operation
            var result = await command.ExecuteNonQueryAsync(ct);
            return result == 1;
        }
        catch (SqlException)
        {
            // Rethrow the exception to let Polly handle the retry logic
            throw;
        }
    }, cancellationToken);
}

public sealed record Record(
    int Id,
    string Name);
```

上述示例中，我们使用 `Policy.Handle<SqlException>()` 方法定义了一个重试策略，以指定我们希望处理的异常类型，在本例中是SQL异常。接着我们使用 `WaitAndRetryAsync` 方法配置策略去尝试操作直到 `maxRetryCount` 次，采用了指数退避策略，其中每次重试尝试都会等待逐渐增加的时间。

在 `ExecuteAsync` 方法内，我们在 try-catch 块中包装了数据库操作。如果由于SQL异常导致操作失败，我们抛出该异常，让 Polly 处理重试逻辑。Polly 将根据定义的策略自动重试操作，为处理临时性故障提供了无缝体验。

---

## 3 – 使用Polly在C#中高级重试和熔断器模式

有时我们需要更高级的重试机制和熔断器模式，以提高我们应用程序的弹性到下一层次。幸运的是，C#中的Polly库也能为这些提供支持！

在与外部服务或资源工作时，我们常常会遇到诸如网络问题或服务不可用之类的临时故障。Polly允许我们定义自定义重试策略，指定重试次数及重试之间的延迟。这确保了我们的应用程序能够优雅地处理临时失败，并提高系统的整体可靠性。

### 使用Polly自定义重试策略

Polly 提供了灵活的选项，根据具体需求自定义重试策略。我们可以定义重试次数，退避策略以确定重试之间的延迟，甚至定义谓词以仅在某些异常上有选择性地重试。通过定制这些策略，我们可以有效地处理不同的场景。

以下是一个展示如何使用 Polly 实现具有指数退避策略的重试策略的例子：

```csharp
var retryPolicy = Policy
    .Handle<HttpRequestException>()
    .OrResult<HttpResponseMessage>(response => response.StatusCode == HttpStatusCode.InternalServerError)
    .WaitAndRetryAsync(3, retryAttempt => TimeSpan.FromSeconds(Math.Pow(2, retryAttempt)));
```

在此示例中，我们定义了一个重试策略，如果发生 `HttpRequestException` 或 `HttpResponseMessage` 的状态码为 `InternalServerError`，则会重试操作最多3次。退避策略是指数的，重试之间的延迟根据重试尝试的编号指数增加。

### 在C#中实现使用Polly的熔断器模式

熔断器模式在防止级联失败和保护系统免受对失败服务的大量重复请求中起着重要作用。Polly 提供了内置支持来实现熔断器模式，这有助于自动管理熔断器状态和控制请求流。

要使用 Polly 实现熔断器模式，我们需要定义故障和成功的阈值，以及监控这些指标的时间窗口。一旦熔断器触发，进一步的请求将被短路，防止对失败服务进行不必要的调用。

以下是如何使用 Polly 实现熔断器模式的示例：

```csharp
var circuitBreakerPolicy = Policy
    .Handle<HttpRequestException>()
    .OrResult<HttpResponseMessage>(response => response.StatusCode == HttpStatusCode.InternalServerError)
    .CircuitBreakerAsync(3, TimeSpan.FromSeconds(30));
```

在此示例中，配置的熔断器策略在30秒的窗口期内如果有3次连续失败将跳闸打开。一旦熔断器打开，随后的请求将自动被拒绝，防止进一步调用，直到指定的恢复期过去。

---

## 常见问题：如何在C#中使用Polly

### Polly在C#中是什么？

Polly是C#中的一个NuGet包，它提供了工具和模式，用于处理软件工程中的故障和重试。

### Polly如何帮助处理故障？

Polly通过提供一套可以处理常见问题，如网络连接问题的工具，简化了C#中的故障处理。

### 什么是软件应用中的重试机制？

重试机制是软件工程中使用的模式，用于自动重试失败的操作，提高成功的机会。

### Polly如何简化C#中的重试机制？

Polly通过提供一整套策略来定义何时以及重试操作多少次，简化了C#中实现重试机制。

### Polly在C#中支持自定义重试策略吗？

是的，Polly允许C#开发者根据他们的具体需要自定义重试策略，提供了在处理重试方面的灵活性。

### 我可以使用Polly在C#中实现熔断器模式吗？

Polly提供了支持在C#中实现熔断器模式，这有助于保护系统免受级联失败并提升弹性。
