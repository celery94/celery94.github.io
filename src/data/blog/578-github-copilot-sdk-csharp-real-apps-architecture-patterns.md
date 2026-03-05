---
pubDatetime: 2026-03-05
title: "用 GitHub Copilot SDK 构建真实 C# 应用：端到端架构模式"
description: '"Hello world" 演示和生产级应用之间有一道深沟。本文梳理三种核心模式：CLI 工具、ASP.NET Core API、自主 Console Agent，以及配套的依赖注入、错误处理和可观测性实践，帮你把 GitHub Copilot SDK 真正用到项目里。'
tags: ["C#", ".NET", "GitHub Copilot SDK", "ASP.NET Core", "Architecture"]
slug: "github-copilot-sdk-csharp-real-apps-architecture-patterns"
source: "https://www.devleader.ca/2026/03/03/building-real-apps-with-github-copilot-sdk-in-c-endtoend-patterns-and-architecture"
---

GitHub Copilot SDK 的 "hello world" 样例随手就能跑起来。真正的挑战在于：怎么把它变成一个可维护、可测试、在故障面前不崩溃的生产应用？我花了相当多时间研究这个问题，发现真正的障碍不是 API 调用本身，而是应用架构。

本文梳理三种场景下的架构模式：CLI 开发者工具、ASP.NET Core API 端点、具备自主迭代能力的 Console Agent。外加依赖注入注册、错误处理与弹性策略、结构化日志与 OpenTelemetry 可观测性。这些是把演示代码和真实应用分开的关键。

## 架构的起点：Client 是单例，Session 是会话

所有模式有一个共同基础：`CopilotClient` 是单例，整个应用生命周期内只创建一次；`CopilotSession` 是轻量级的，按请求或按对话创建。把 Client 多次实例化既浪费资源，也会造成连接耗尽。

不同应用类型的生命周期对比：

| 模式             | CopilotClient 生命周期 | Session 生命周期 | 适用场景                  |
| ---------------- | ---------------------- | ---------------- | ------------------------- |
| CLI 工具         | 单例（应用生命周期）   | 每次对话         | 交互式开发工具、代码生成  |
| ASP.NET Core API | 单例（DI）             | Scoped（每请求） | Web API、移动后端、微服务 |
| Console Agent    | 单例（应用生命周期）   | 单个长时间运行   | 批量处理、仓库分析        |
| 桌面应用         | 单例（应用生命周期）   | 每窗口/标签页    | IDE 插件、GUI 助手        |

在此之上，我始终把 Copilot SDK 包在一个 `IAiAssistant` 接口后面。这个[外观模式](https://www.devleader.ca/2024/03/08/the-facade-design-pattern-in-c-how-to-simplify-complex-subsystems)带来三个好处：业务逻辑可以 mock AI 层，具体实现细节不会渗透到领域代码里，未来换 SDK 版本时改的地方也很集中。

```csharp
// AI 助手接口，清晰架构的基础
public interface IAiAssistant
{
    IAsyncEnumerable<string> StreamResponseAsync(
        string userMessage, CancellationToken cancellationToken = default);
    Task<string> GetResponseAsync(
        string userMessage, CancellationToken cancellationToken = default);
}

public class CopilotAiAssistant : IAiAssistant, IAsyncDisposable
{
    private readonly CopilotSession _session;

    public CopilotAiAssistant(CopilotClient client)
    {
        // 简化起见在构造函数同步创建；生产中建议用异步工厂
        _session = client.CreateSessionAsync(new SessionConfig { Model = "gpt-5" })
            .GetAwaiter().GetResult();
    }

    public async Task<string> GetResponseAsync(
        string userMessage, CancellationToken cancellationToken = default)
    {
        var tcs = new TaskCompletionSource<string>(TaskCreationOptions.RunContinuationsAsynchronously);
        var sb = new System.Text.StringBuilder();

        _session.On(evt =>
        {
            switch (evt)
            {
                case AssistantMessageEvent msg: sb.Append(msg.Data.Content); break;
                case SessionIdleEvent: tcs.TrySetResult(sb.ToString()); break;
                case SessionErrorEvent err: tcs.TrySetException(new Exception(err.Data.Message)); break;
            }
        });

        await _session.SendAsync(new MessageOptions { Prompt = userMessage });
        return await tcs.Task.WaitAsync(cancellationToken);
    }

    public async IAsyncEnumerable<string> StreamResponseAsync(
        string userMessage,
        [System.Runtime.CompilerServices.EnumeratorCancellation] CancellationToken cancellationToken = default)
    {
        var channel = System.Threading.Channels.Channel.CreateUnbounded<string?>();

        _session.On(evt =>
        {
            switch (evt)
            {
                case AssistantMessageDeltaEvent delta: channel.Writer.TryWrite(delta.Data.DeltaContent); break;
                case SessionIdleEvent: channel.Writer.TryWrite(null); break;
                case SessionErrorEvent err: channel.Writer.TryComplete(new Exception(err.Data.Message)); break;
            }
        });

        await _session.SendAsync(new MessageOptions { Prompt = userMessage });

        await foreach (var token in channel.Reader.ReadAllAsync(cancellationToken))
        {
            if (token is null) yield break;
            yield return token;
        }
    }

    public async ValueTask DisposeAsync() => await _session.DisposeAsync();
}
```

`IAsyncDisposable` 确保 session 在不再需要时被正确清理。每个 `CopilotAiAssistant` 实例维护独立的对话上下文，这对 Web API 的 Scoped DI 或 CLI 工具里的并发对话都很合适。

## 模式一：CLI 开发者工具

CLI 工具是我最喜欢的 Copilot SDK 应用形态，因为它直接给开发者带来交互价值。架构核心是一个交互循环：读取用户输入，发到 SDK，把流式响应实时打印到终端，然后重复。我通常用 Spectre.Console 做富终端 UI，或者 System.CommandLine 做命令解析。

```csharp
using GitHub.Copilot.SDK;
using Spectre.Console;

public class InteractiveCli
{
    private readonly CopilotClient _client;

    public InteractiveCli(CopilotClient client)
    {
        _client = client;
    }

    public async Task RunAsync(CancellationToken cancellationToken)
    {
        await using var session = await _client.CreateSessionAsync(new SessionConfig
        {
            Model = "gpt-5",
            SystemPrompt = "You are a helpful coding assistant."
        });

        AnsiConsole.MarkupLine("[bold green]AI CLI Tool[/] - Type 'exit' to quit");

        while (!cancellationToken.IsCancellationRequested)
        {
            var userInput = AnsiConsole.Ask<string>("[blue]You:[/]");
            if (userInput.Equals("exit", StringComparison.OrdinalIgnoreCase))
                break;

            AnsiConsole.Markup("[yellow]Assistant:[/] ");

            await foreach (var token in StreamResponseAsync(session, userInput, cancellationToken))
            {
                AnsiConsole.Markup(token);
            }

            AnsiConsole.WriteLine();
        }
    }

    private async IAsyncEnumerable<string> StreamResponseAsync(
        CopilotSession session,
        string prompt,
        [System.Runtime.CompilerServices.EnumeratorCancellation] CancellationToken cancellationToken)
    {
        var channel = System.Threading.Channels.Channel.CreateUnbounded<string?>();

        session.On(evt =>
        {
            switch (evt)
            {
                case AssistantMessageDeltaEvent delta:
                    channel.Writer.TryWrite(delta.Data.DeltaContent);
                    break;
                case SessionIdleEvent:
                    channel.Writer.TryWrite(null);
                    break;
            }
        });

        await session.SendAsync(new MessageOptions { Prompt = prompt });

        await foreach (var token in channel.Reader.ReadAllAsync(cancellationToken))
        {
            if (token is null) yield break;
            yield return token;
        }
    }
}
```

实时流式输出对 CLI 体验至关重要。用户不想盯着光标等十秒钟，然后一口气收到 500 个字。后续我会发布完整的深度文章，涵盖命令历史、语法高亮和多轮对话——这里的骨架是理解整个模式的起点。

## 模式二：ASP.NET Core AI API 端点

把 SDK 暴露成 REST API，可以支撑 Web AI 助手、移动后端、微服务等场景。关键设计决策是选择普通 request/response（简单查询）还是 Server-Sent Events 流式端点（实时 token 推送）。我通常在[同一个 ASP.NET Core 应用](https://www.devleader.ca/2026/02/13/aspnet-core-with-needlr-simplified-web-application-setup)里同时实现两种。

```csharp
using Microsoft.AspNetCore.Mvc;

[ApiController]
[Route("api/[controller]")]
public class AiAssistantController : ControllerBase
{
    private readonly IAiAssistant _assistant;

    public AiAssistantController(IAiAssistant assistant)
    {
        _assistant = assistant;
    }

    [HttpPost("ask")]
    public async Task<ActionResult<string>> AskAsync(
        [FromBody] AskRequest request,
        CancellationToken cancellationToken)
    {
        try
        {
            var response = await _assistant.GetResponseAsync(request.Prompt, cancellationToken);
            return Ok(response);
        }
        catch (Exception ex)
        {
            return StatusCode(500, new { error = ex.Message });
        }
    }

    [HttpPost("stream")]
    public async Task StreamAsync(
        [FromBody] AskRequest request,
        CancellationToken cancellationToken)
    {
        Response.ContentType = "text/event-stream";

        await foreach (var token in _assistant.StreamResponseAsync(request.Prompt, cancellationToken))
        {
            await Response.WriteAsync($"data: {token}\n\n", cancellationToken);
            await Response.Body.FlushAsync(cancellationToken);
        }
    }
}

public record AskRequest(string Prompt);
```

对于实时聊天这类场景，我会改用 SignalR 将 token 推送给连接中的客户端。架构思路相同，只是把 HTTP 响应流换成了 SignalR Hub 的广播调用。这个模式在多个客户端需要实时看到同一段 AI 对话时特别有用。

## 模式三：Console Agent 的迭代循环

Agent 循环模式才是 Copilot SDK 真正发光的地方。它实现的是"检查 → 决策 → 行动 → 观察 → 循环"的自主执行周期，适合代码分析工具、自动重构 Agent、仓库扫描机器人。核心结构是让 `CopilotSession` 跑在一个 while 循环里，由条件逻辑决定何时继续、何时停止。

```csharp
public class CodeAnalysisAgent
{
    private readonly CopilotClient _client;
    private readonly ILogger<CodeAnalysisAgent> _logger;

    public CodeAnalysisAgent(CopilotClient client, ILogger<CodeAnalysisAgent> logger)
    {
        _client = client;
        _logger = logger;
    }

    public async Task AnalyzeRepositoryAsync(string repoPath, CancellationToken cancellationToken)
    {
        await using var session = await _client.CreateSessionAsync(new SessionConfig
        {
            Model = "gpt-5",
            SystemPrompt = @"You are a code analysis agent. Analyze code and suggest improvements.
When you're done analyzing, respond with 'ANALYSIS_COMPLETE'."
        });

        var files = Directory.GetFiles(repoPath, "*.cs", SearchOption.AllDirectories);
        var currentFileIndex = 0;
        var isComplete = false;

        while (!isComplete && currentFileIndex < files.Length && !cancellationToken.IsCancellationRequested)
        {
            // 行动：发送下一个文件进行分析
            var fileContent = await File.ReadAllTextAsync(files[currentFileIndex], cancellationToken);
            var prompt = $"Analyze this C# file and suggest improvements:\n\n{fileContent}";

            // 观察：收集 Agent 的响应
            var response = await GetResponseAsync(session, prompt, cancellationToken);

            _logger.LogInformation("Analyzed {File}: {Response}", files[currentFileIndex], response);

            // 决策：判断是否继续
            if (response.Contains("ANALYSIS_COMPLETE", StringComparison.OrdinalIgnoreCase))
            {
                isComplete = true;
            }
            else
            {
                currentFileIndex++;
            }

            // 可选：限速延迟
            await Task.Delay(TimeSpan.FromSeconds(1), cancellationToken);
        }

        _logger.LogInformation("Repository analysis complete. Analyzed {Count} files.", currentFileIndex);
    }

    private async Task<string> GetResponseAsync(
        CopilotSession session,
        string prompt,
        CancellationToken cancellationToken)
    {
        var tcs = new TaskCompletionSource<string>();
        var sb = new System.Text.StringBuilder();

        session.On(evt =>
        {
            switch (evt)
            {
                case AssistantMessageEvent msg: sb.Append(msg.Data.Content); break;
                case SessionIdleEvent: tcs.TrySetResult(sb.ToString()); break;
            }
        });

        await session.SendAsync(new MessageOptions { Prompt = prompt });
        return await tcs.Task.WaitAsync(cancellationToken);
    }
}
```

这个模式的灵活性极高：你可以加入复杂的决策逻辑，跨迭代维护状态，或者实现让 Agent 从自身行动中学习的反馈循环。

## 依赖注入：正确注册 CopilotClient

[按照 IServiceCollection 最佳实践](https://www.devleader.ca/2024/02/21/iservicecollection-in-c-simplified-beginners-guide-for-dependency-injection)，`CopilotClient` 注册为单例，`IHostedService` 负责在应用启动时初始化客户端，在关闭时优雅处理资源。

```csharp
using GitHub.Copilot.SDK;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;

var builder = Host.CreateApplicationBuilder(args);

builder.Services.AddSingleton<CopilotClient>(sp =>
{
    var client = new CopilotClient();
    return client;
});

builder.Services.AddHostedService<CopilotStartupService>();
builder.Services.AddScoped<IAiAssistant, CopilotAiAssistant>();

var app = builder.Build();
await app.RunAsync();

// 启动服务：确保 Client 在请求到来前完成初始化
public class CopilotStartupService : IHostedService
{
    private readonly CopilotClient _client;

    public CopilotStartupService(CopilotClient client) => _client = client;

    public Task StartAsync(CancellationToken cancellationToken) => _client.StartAsync();
    public Task StopAsync(CancellationToken cancellationToken) => _client.DisposeAsync().AsTask();
}
```

`IAiAssistant` 注册为 Scoped 非常适合 ASP.NET Core：每个 HTTP 请求拿到自己的对话 session。对 CLI 或 Console 应用，你有更多手动控制生命周期的自由，可以注册成 transient 或直接 new。

我进一步把注册逻辑封装成扩展方法，让 `Program.cs` 保持整洁：

```csharp
public static class CopilotServiceExtensions
{
    public static IServiceCollection AddCopilotSdk(
        this IServiceCollection services,
        Action<CopilotOptions>? configure = null)
    {
        var options = new CopilotOptions();
        configure?.Invoke(options);

        services.AddSingleton(options);
        services.AddSingleton<CopilotClient>(sp => new CopilotClient());
        services.AddHostedService<CopilotStartupService>();
        services.AddScoped<IAiAssistant, CopilotAiAssistant>();

        return services;
    }
}

public class CopilotOptions
{
    public string DefaultModel { get; set; } = "gpt-5";
    public string? SystemPrompt { get; set; }
}
```

## 错误处理与弹性策略

Copilot SDK 通过 `SessionErrorEvent` 暴露错误，event callback 里必须处理它。配合 [Polly 重试策略](https://www.devleader.ca/2024/03/03/how-to-use-polly-in-c-easily-handle-faults-and-retries)，可以对瞬态故障优雅重试。

```csharp
using Polly;
using Polly.Retry;

public class ResilientCopilotService
{
    private readonly IAiAssistant _assistant;
    private readonly ResiliencePipeline<string> _pipeline;

    public ResilientCopilotService(IAiAssistant assistant)
    {
        _assistant = assistant;
        _pipeline = new ResiliencePipelineBuilder<string>()
            .AddRetry(new RetryStrategyOptions<string>
            {
                MaxRetryAttempts = 3,
                Delay = TimeSpan.FromSeconds(1),
                BackoffType = DelayBackoffType.Exponential
            })
            .AddTimeout(TimeSpan.FromSeconds(30))
            .Build();
    }

    public async Task<string> AskWithResilienceAsync(string prompt)
    {
        return await _pipeline.ExecuteAsync(
            async ct => await _assistant.GetResponseAsync(prompt, ct));
    }
}
```

高并发服务还需要熔断器，防止级联故障，给底层服务留出恢复时间。对于降级策略，我通常维护一个最近响应缓存，在 AI 服务不可用时作为兜底返回。

流式场景的错误处理需要格外注意：你需要决定是从头重试，还是接受部分数据，或者直接优雅报错。

## 可观测性：日志与指标

生产应用从第一天就需要完整的可观测性。SDK 事件提供了天然的日志插入点，我会记录每个 `SessionErrorEvent`，追踪响应时间，监控 token 用量。

```csharp
public class ObservableCopilotService
{
    private readonly IAiAssistant _assistant;
    private readonly ILogger<ObservableCopilotService> _logger;

    public ObservableCopilotService(IAiAssistant assistant, ILogger<ObservableCopilotService> logger)
    {
        _assistant = assistant;
        _logger = logger;
    }

    public async Task<string> GetResponseWithLoggingAsync(string prompt, CancellationToken cancellationToken)
    {
        var stopwatch = System.Diagnostics.Stopwatch.StartNew();

        try
        {
            _logger.LogInformation(
                "Sending prompt to Copilot SDK. PromptLength={PromptLength}",
                prompt.Length);

            var response = await _assistant.GetResponseAsync(prompt, cancellationToken);

            stopwatch.Stop();

            _logger.LogInformation(
                "Received response from Copilot SDK. ResponseLength={ResponseLength}, Duration={Duration}ms",
                response.Length,
                stopwatch.ElapsedMilliseconds);

            return response;
        }
        catch (Exception ex)
        {
            stopwatch.Stop();
            _logger.LogError(ex, "Error calling Copilot SDK. Duration={Duration}ms", stopwatch.ElapsedMilliseconds);
            throw;
        }
    }
}
```

在分布式系统中，我用 OpenTelemetry Activity 追踪跨服务边界的请求链路，这在微服务架构里特别有价值——一次 AI 请求可能触发多条下游调用。

```csharp
using System.Diagnostics;

public class TelemetryCopilotService
{
    private static readonly ActivitySource ActivitySource = new("Copilot.SDK");
    private readonly IAiAssistant _assistant;

    public TelemetryCopilotService(IAiAssistant assistant)
    {
        _assistant = assistant;
    }

    public async Task<string> GetResponseWithTelemetryAsync(string prompt, CancellationToken cancellationToken)
    {
        using var activity = ActivitySource.StartActivity("GetCopilotResponse");
        activity?.SetTag("prompt.length", prompt.Length);

        try
        {
            var response = await _assistant.GetResponseAsync(prompt, cancellationToken);
            activity?.SetTag("response.length", response.Length);
            return response;
        }
        catch (Exception ex)
        {
            activity?.SetStatus(ActivityStatusCode.Error, ex.Message);
            throw;
        }
    }
}
```

对于指标，我追踪请求量、错误率、响应时间（p50/p95/p99）以及后台处理时的队列深度。这些指标输入到 Dashboard 里，让我在问题影响用户之前就发现性能异常。

## 接下来的四篇深度文章

这篇文章建立了基础架构模式，后续还有四篇文章，每一篇都把这些模式落地成完整可运行的应用：

第一篇：用 Spectre.Console 构建功能完整的 AI CLI 开发工具，包含命令历史、语法高亮、带上下文保存的多轮对话，附完整生产级源码。

第二篇：构建 ASP.NET Core AI 助手 API，同时暴露 request/response 与流式端点，集成 SignalR 实时聊天，支持认证与限流，并部署到 Azure。

第三篇：构建交互式 Coding Agent，能分析代码库、提建议、自主执行重构。深度讲解 Agent 循环，包括决策逻辑、跨迭代状态管理和安全护栏。

第四篇：构建仓库分析机器人，扫描 GitHub 仓库、识别代码异味与安全问题、生成综合报告。

这四篇文章都建立在本文的架构基础之上，所以建议先把这里的模式吃透，再去看具体应用类型。完整系列入口在 [GitHub Copilot SDK .NET 完整指南](https://www.devleader.ca/2026/02/26/github-copilot-sdk-dotnet-complete-guide)。

## 参考

- [原文](https://www.devleader.ca/2026/03/03/building-real-apps-with-github-copilot-sdk-in-c-endtoend-patterns-and-architecture) — Dev Leader（Nick Cosentino）
- [GitHub Copilot SDK .NET 完整指南](https://www.devleader.ca/2026/02/26/github-copilot-sdk-dotnet-complete-guide)
- [GitHub Copilot SDK 入门](https://www.devleader.ca/2026/03/02/getting-started-github-copilot-sdk-csharp)
- [外观设计模式 in C#](https://www.devleader.ca/2024/03/08/the-facade-design-pattern-in-c-how-to-simplify-complex-subsystems)
- [如何使用 Polly 处理故障与重试](https://www.devleader.ca/2024/03/03/how-to-use-polly-in-c-easily-handle-faults-and-retries)
