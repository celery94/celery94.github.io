---
pubDatetime: 2025-08-20
tags: [".NET", "C#", "AI"]
slug: gpt-oss-csharp-ollama-local-ai-development
source: https://devblogs.microsoft.com/dotnet/gpt-oss-csharp-ollama
title: GPT-OSS 与 C# 开发指南：基于 Ollama 的本地 AI 应用构建完整实战
description: 深入探索 OpenAI 首个开源权重模型 GPT-OSS 在 C# 开发中的应用，从环境配置到实际部署，包含完整的聊天应用、流式响应、函数调用等高级特性的实现指南。
---

# GPT-OSS 与 C# 开发指南：基于 Ollama 的本地 AI 应用构建完整实战

## GPT-OSS：开源 AI 的革命性突破

GPT-OSS 是 OpenAI 自 GPT-2 以来首个开源权重模型，这一里程碑式的发布为开发者社区带来了前所未有的机遇。与依赖云端服务的传统 AI 模型不同，GPT-OSS 完全可以在本地运行，为开发者提供了强大的 AI 能力而无需担心数据隐私、网络延迟或使用成本等问题。

GPT-OSS 提供了两个版本：gpt-oss-120b 和 gpt-oss-20b。120B 版本提供了最强的性能表现，适合对计算能力和内存有充足预算的生产环境。而 20B 版本则是开发者的理想选择，它只需要 16GB 内存即可运行，在编程、数学计算和工具使用方面依然表现出色，特别适合本地开发和实验场景。

这种本地化的 AI 能力开启了全新的应用可能性。开发者可以构建完全离线的智能应用，处理敏感数据而无需担心隐私泄露，进行大规模的实验而不受 API 调用次数限制，甚至可以根据特定需求对模型进行微调。对于企业级应用而言，这意味着可以将 AI 能力完全集成到内部系统中，确保数据的完全控制和合规性。

## 技术架构与环境准备

### 系统要求与硬件配置

要充分发挥 GPT-OSS 的性能，合适的硬件配置至关重要。对于 gpt-oss:20b 模型，推荐的最低配置包括至少 16GB 的系统内存，如果有独立显卡（如 NVIDIA RTX 系列），可以显著加速推理过程。对于 Apple Silicon Mac 用户，统一内存架构使得模型可以更高效地利用系统资源。

CPU 方面，现代多核处理器（如 Intel i7/i9 或 AMD Ryzen 7/9 系列）能够提供良好的性能。如果配备了支持 CUDA 的 NVIDIA 显卡，Ollama 会自动利用 GPU 加速，大幅提升推理速度。对于生产环境，建议使用至少 32GB 内存和专业级显卡。

### Ollama 服务配置与优化

Ollama 是一个优秀的本地 LLM 运行平台，它简化了模型的部署和管理。安装 Ollama 后，首先需要拉取 GPT-OSS 模型：

```bash
# 安装较小的 20B 版本，适合开发和测试
ollama pull gpt-oss:20b

# 如果系统资源充足，也可以使用 120B 版本
ollama pull gpt-oss:120b
```

Ollama 服务默认在 11434 端口运行，可以通过环境变量进行配置：

```bash
# 设置服务端口
export OLLAMA_HOST=0.0.0.0:11434

# 配置 GPU 内存限制（如果使用 GPU）
export OLLAMA_GPU_MEMORY_FRACTION=0.8

# 设置并发请求数量
export OLLAMA_NUM_PARALLEL=4
```

### .NET 开发环境配置

确保安装了 .NET 8 SDK 或更高版本。GPT-OSS 的强大之处在于可以与现有的 .NET 生态系统无缝集成，利用 Microsoft.Extensions.AI 库提供的统一抽象层，开发者可以编写与提供商无关的代码。

```bash
# 检查 .NET 版本
dotnet --version

# 创建新的控制台项目
dotnet new console -n GPTOSSChatApp
cd GPTOSSChatApp
```

## Microsoft.Extensions.AI：统一的 AI 开发体验

Microsoft.Extensions.AI 是微软提供的一套 AI 开发抽象库，它的设计理念是让开发者能够编写一次代码，在不同的 AI 提供商之间无缝切换。这种抽象层的好处在于：

首先是提供商独立性。同样的代码可以与 Ollama、Azure AI、OpenAI 或其他兼容的提供商配合使用，只需要更改配置即可。其次是一致的开发体验，无论使用哪种 AI 服务，开发者都能享受相同的 API 接口和编程模式。最后是企业级特性支持，包括依赖注入、配置管理、日志记录等 .NET 生态系统的核心特性。

### 核心组件和接口设计

Microsoft.Extensions.AI 的核心是 IChatClient 接口，它定义了与聊天式 AI 模型交互的标准方法：

```csharp
public interface IChatClient
{
    Task<ChatCompletion> CompleteAsync(
        IList<ChatMessage> chatMessages,
        ChatOptions? options = null,
        CancellationToken cancellationToken = default);

    IAsyncEnumerable<StreamingChatCompletionUpdate> CompleteStreamingAsync(
        IList<ChatMessage> chatMessages,
        ChatOptions? options = null,
        CancellationToken cancellationToken = default);
}
```

这个接口抽象了不同 AI 提供商的具体实现细节，让开发者可以专注于业务逻辑而不是技术集成的复杂性。

## 依赖包管理与项目配置

### NuGet 包的选择和配置

对于 GPT-OSS 和 Ollama 的集成，需要添加两个核心包：

```bash
# 添加 Microsoft.Extensions.AI 核心抽象库
dotnet add package Microsoft.Extensions.AI

# 添加 OllamaSharp 作为 Ollama 的具体实现
dotnet add package OllamaSharp
```

需要注意的是，Microsoft.Extensions.AI.Ollama 包已被弃用，官方推荐使用 OllamaSharp 作为连接 Ollama 的首选库。OllamaSharp 提供了更好的性能、更丰富的功能和更活跃的社区支持。

### 项目结构的最佳实践

对于更复杂的应用程序，建议采用分层架构：

```
GPTOSSChatApp/
├── Program.cs                 # 应用程序入口点
├── Services/
│   ├── IChatService.cs       # 聊天服务接口
│   ├── ChatService.cs        # 聊天服务实现
│   └── IConversationHistory.cs # 对话历史管理
├── Models/
│   ├── ChatMessage.cs        # 消息模型
│   ├── ChatSession.cs        # 会话模型
│   └── AppConfig.cs          # 应用配置
├── Extensions/
│   └── ServiceCollectionExtensions.cs # DI 扩展
└── appsettings.json          # 配置文件
```

## 基础聊天应用的完整实现

### 核心聊天逻辑设计

让我们构建一个功能完整的聊天应用，它不仅支持基本的对话功能，还包含对话历史管理、错误处理和性能优化：

```csharp
using Microsoft.Extensions.AI;
using OllamaSharp;
using System.Text.Json;

namespace GPTOSSChatApp
{
    public class ChatSession
    {
        public string Id { get; set; } = Guid.NewGuid().ToString();
        public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
        public List<ChatMessage> Messages { get; set; } = new();
        public string ModelName { get; set; } = string.Empty;
    }

    public class ChatService
    {
        private readonly IChatClient _chatClient;
        private readonly ILogger<ChatService>? _logger;
        private ChatSession _currentSession;

        public ChatService(IChatClient chatClient, ILogger<ChatService>? logger = null)
        {
            _chatClient = chatClient;
            _logger = logger;
            _currentSession = new ChatSession { ModelName = "gpt-oss:20b" };
        }

        public async Task<string> SendMessageAsync(string userMessage, CancellationToken cancellationToken = default)
        {
            if (string.IsNullOrWhiteSpace(userMessage))
                throw new ArgumentException("消息不能为空", nameof(userMessage));

            try
            {
                // 添加用户消息到会话历史
                var userChatMessage = new ChatMessage(ChatRole.User, userMessage);
                _currentSession.Messages.Add(userChatMessage);

                _logger?.LogInformation("发送消息: {Message}", userMessage);

                // 获取 AI 响应
                var completion = await _chatClient.CompleteAsync(
                    _currentSession.Messages,
                    new ChatOptions
                    {
                        Temperature = 0.7f,
                        MaxOutputTokens = 2048,
                        TopP = 0.9f
                    },
                    cancellationToken);

                var assistantResponse = completion.Message.Text ?? "抱歉，我无法生成响应。";

                // 添加助手响应到会话历史
                var assistantMessage = new ChatMessage(ChatRole.Assistant, assistantResponse);
                _currentSession.Messages.Add(assistantMessage);

                _logger?.LogInformation("收到响应，长度: {Length} 字符", assistantResponse.Length);

                return assistantResponse;
            }
            catch (Exception ex)
            {
                _logger?.LogError(ex, "发送消息时发生错误");
                throw new InvalidOperationException($"处理消息时发生错误: {ex.Message}", ex);
            }
        }

        public async IAsyncEnumerable<string> SendMessageStreamAsync(
            string userMessage,
            [EnumeratorCancellation] CancellationToken cancellationToken = default)
        {
            if (string.IsNullOrWhiteSpace(userMessage))
                throw new ArgumentException("消息不能为空", nameof(userMessage));

            var userChatMessage = new ChatMessage(ChatRole.User, userMessage);
            _currentSession.Messages.Add(userChatMessage);

            var completeResponse = new StringBuilder();

            try
            {
                await foreach (var update in _chatClient.CompleteStreamingAsync(
                    _currentSession.Messages,
                    new ChatOptions { Temperature = 0.7f },
                    cancellationToken))
                {
                    if (!string.IsNullOrEmpty(update.Text))
                    {
                        completeResponse.Append(update.Text);
                        yield return update.Text;
                    }
                }

                // 将完整响应添加到会话历史
                if (completeResponse.Length > 0)
                {
                    var assistantMessage = new ChatMessage(ChatRole.Assistant, completeResponse.ToString());
                    _currentSession.Messages.Add(assistantMessage);
                }
            }
            catch (Exception ex)
            {
                _logger?.LogError(ex, "流式消息处理时发生错误");
                yield return $"错误: {ex.Message}";
            }
        }

        public void ClearHistory()
        {
            _currentSession = new ChatSession { ModelName = _currentSession.ModelName };
            _logger?.LogInformation("对话历史已清除");
        }

        public async Task SaveSessionAsync(string filePath)
        {
            try
            {
                var json = JsonSerializer.Serialize(_currentSession, new JsonSerializerOptions
                {
                    WriteIndented = true,
                    Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping
                });
                await File.WriteAllTextAsync(filePath, json);
                _logger?.LogInformation("会话已保存到: {FilePath}", filePath);
            }
            catch (Exception ex)
            {
                _logger?.LogError(ex, "保存会话时发生错误");
                throw;
            }
        }

        public async Task LoadSessionAsync(string filePath)
        {
            try
            {
                if (File.Exists(filePath))
                {
                    var json = await File.ReadAllTextAsync(filePath);
                    var session = JsonSerializer.Deserialize<ChatSession>(json);
                    if (session != null)
                    {
                        _currentSession = session;
                        _logger?.LogInformation("会话已从 {FilePath} 加载，包含 {Count} 条消息",
                            filePath, _currentSession.Messages.Count);
                    }
                }
            }
            catch (Exception ex)
            {
                _logger?.LogError(ex, "加载会话时发生错误");
                throw;
            }
        }

        public int GetMessageCount() => _currentSession.Messages.Count;
        public DateTime GetSessionStartTime() => _currentSession.CreatedAt;
    }
}
```

### 主程序的实现与用户交互

```csharp
using Microsoft.Extensions.AI;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;
using OllamaSharp;

namespace GPTOSSChatApp
{
    class Program
    {
        static async Task Main(string[] args)
        {
            // 配置服务容器
            var services = new ServiceCollection();
            services.AddLogging(builder => builder.AddConsole().SetMinimumLevel(LogLevel.Information));

            // 注册 Ollama 客户端
            services.AddSingleton<IChatClient>(serviceProvider =>
            {
                var logger = serviceProvider.GetService<ILogger<OllamaApiClient>>();
                return new OllamaApiClient(new Uri("http://localhost:11434/"), "gpt-oss:20b");
            });

            services.AddSingleton<ChatService>();

            var serviceProvider = services.BuildServiceProvider();
            var chatService = serviceProvider.GetRequiredService<ChatService>();
            var logger = serviceProvider.GetRequiredService<ILogger<Program>>();

            // 应用程序启动
            Console.OutputEncoding = System.Text.Encoding.UTF8;
            Console.WriteLine("🤖 GPT-OSS 聊天助手");
            Console.WriteLine("=====================================");
            Console.WriteLine("命令列表:");
            Console.WriteLine("  /help     - 显示帮助信息");
            Console.WriteLine("  /clear    - 清除对话历史");
            Console.WriteLine("  /save     - 保存对话会话");
            Console.WriteLine("  /load     - 加载对话会话");
            Console.WriteLine("  /info     - 显示会话信息");
            Console.WriteLine("  /stream   - 切换流式/非流式模式");
            Console.WriteLine("  /exit     - 退出程序");
            Console.WriteLine("=====================================");
            Console.WriteLine();

            bool useStreaming = true;
            string sessionFile = "chat_session.json";

            // 尝试加载之前的会话
            try
            {
                await chatService.LoadSessionAsync(sessionFile);
                Console.WriteLine("✅ 已加载之前的对话会话");
            }
            catch
            {
                Console.WriteLine("ℹ️ 开始新的对话会话");
            }

            // 主交互循环
            while (true)
            {
                Console.Write($"\n👤 您 ({(useStreaming ? "流式" : "标准")}): ");
                var userInput = Console.ReadLine();

                if (string.IsNullOrWhiteSpace(userInput))
                    continue;

                // 处理命令
                if (userInput.StartsWith("/"))
                {
                    await HandleCommandAsync(userInput, chatService, ref useStreaming, sessionFile);
                    continue;
                }

                // 处理正常消息
                try
                {
                    Console.Write("🤖 助手: ");

                    if (useStreaming)
                    {
                        await foreach (var chunk in chatService.SendMessageStreamAsync(userInput))
                        {
                            Console.Write(chunk);
                        }
                        Console.WriteLine();
                    }
                    else
                    {
                        var response = await chatService.SendMessageAsync(userInput);
                        Console.WriteLine(response);
                    }

                    // 自动保存会话
                    await chatService.SaveSessionAsync(sessionFile);
                }
                catch (Exception ex)
                {
                    logger.LogError(ex, "处理用户输入时发生错误");
                    Console.WriteLine($"❌ 错误: {ex.Message}");
                }
            }
        }

        static async Task HandleCommandAsync(string command, ChatService chatService, ref bool useStreaming, string sessionFile)
        {
            switch (command.ToLower())
            {
                case "/help":
                    Console.WriteLine("\n📖 帮助信息:");
                    Console.WriteLine("这是一个基于 GPT-OSS 模型的本地聊天助手。");
                    Console.WriteLine("您可以直接输入消息与 AI 对话，或使用以下命令:");
                    Console.WriteLine("• /clear - 清除当前对话历史");
                    Console.WriteLine("• /save - 手动保存对话会话");
                    Console.WriteLine("• /load - 重新加载对话会话");
                    Console.WriteLine("• /info - 查看当前会话统计信息");
                    Console.WriteLine("• /stream - 在流式和标准响应模式间切换");
                    Console.WriteLine("• /exit - 退出程序");
                    break;

                case "/clear":
                    chatService.ClearHistory();
                    Console.WriteLine("✅ 对话历史已清除");
                    break;

                case "/save":
                    try
                    {
                        await chatService.SaveSessionAsync(sessionFile);
                        Console.WriteLine("✅ 会话已保存");
                    }
                    catch (Exception ex)
                    {
                        Console.WriteLine($"❌ 保存失败: {ex.Message}");
                    }
                    break;

                case "/load":
                    try
                    {
                        await chatService.LoadSessionAsync(sessionFile);
                        Console.WriteLine("✅ 会话已重新加载");
                    }
                    catch (Exception ex)
                    {
                        Console.WriteLine($"❌ 加载失败: {ex.Message}");
                    }
                    break;

                case "/info":
                    var messageCount = chatService.GetMessageCount();
                    var sessionStart = chatService.GetSessionStartTime();
                    var duration = DateTime.UtcNow - sessionStart;

                    Console.WriteLine($"\n📊 会话信息:");
                    Console.WriteLine($"• 消息数量: {messageCount}");
                    Console.WriteLine($"• 会话开始: {sessionStart:yyyy-MM-dd HH:mm:ss}");
                    Console.WriteLine($"• 会话时长: {duration.TotalMinutes:F1} 分钟");
                    Console.WriteLine($"• 响应模式: {(useStreaming ? "流式" : "标准")}");
                    break;

                case "/stream":
                    useStreaming = !useStreaming;
                    Console.WriteLine($"✅ 已切换到{(useStreaming ? "流式" : "标准")}响应模式");
                    break;

                case "/exit":
                    Console.WriteLine("👋 再见！感谢使用 GPT-OSS 聊天助手。");
                    Environment.Exit(0);
                    break;

                default:
                    Console.WriteLine($"❌ 未知命令: {command}。输入 /help 查看可用命令。");
                    break;
            }
        }
    }
}
```

## 流式响应的技术实现

### 实时响应的用户体验优化

流式响应是现代 AI 应用的重要特性，它允许用户在 AI 生成完整响应之前就开始看到内容，大大改善了用户体验。在 GPT-OSS 的集成中，流式响应通过 IAsyncEnumerable 接口实现，这是 C# 中处理异步数据流的标准方式。

流式响应的核心优势在于降低了感知延迟。用户不需要等待完整的响应生成完毕，而是可以立即看到 AI 开始"思考"的过程。对于长篇回答，这种体验改进尤为明显。此外，流式响应还允许用户在必要时提前中断生成过程，节省计算资源。

### 高级流式处理实现

```csharp
public class AdvancedStreamingChatService : IChatService
{
    private readonly IChatClient _chatClient;
    private readonly ILogger<AdvancedStreamingChatService> _logger;

    public async IAsyncEnumerable<ChatStreamUpdate> SendMessageStreamAsync(
        string userMessage,
        StreamingOptions options,
        [EnumeratorCancellation] CancellationToken cancellationToken = default)
    {
        var startTime = DateTime.UtcNow;
        var tokenCount = 0;
        var responseBuilder = new StringBuilder();

        try
        {
            // 发送开始事件
            yield return new ChatStreamUpdate
            {
                Type = StreamUpdateType.Started,
                Timestamp = startTime,
                Metadata = new { Message = "开始生成响应..." }
            };

            await foreach (var update in _chatClient.CompleteStreamingAsync(
                GetChatHistory(userMessage),
                ToChatOptions(options),
                cancellationToken))
            {
                if (!string.IsNullOrEmpty(update.Text))
                {
                    responseBuilder.Append(update.Text);
                    tokenCount++;

                    yield return new ChatStreamUpdate
                    {
                        Type = StreamUpdateType.Content,
                        Content = update.Text,
                        Timestamp = DateTime.UtcNow,
                        PartialContent = responseBuilder.ToString(),
                        TokenCount = tokenCount,
                        Metadata = new
                        {
                            ElapsedMs = (DateTime.UtcNow - startTime).TotalMilliseconds,
                            TokensPerSecond = tokenCount / Math.Max((DateTime.UtcNow - startTime).TotalSeconds, 0.1)
                        }
                    };
                }

                // 检查是否需要应用内容过滤
                if (options.EnableContentFilter && ContainsInappropriateContent(responseBuilder.ToString()))
                {
                    yield return new ChatStreamUpdate
                    {
                        Type = StreamUpdateType.Warning,
                        Content = "检测到可能不当的内容，响应已被过滤。",
                        Timestamp = DateTime.UtcNow
                    };
                    yield break;
                }

                // 检查长度限制
                if (options.MaxResponseLength > 0 && responseBuilder.Length > options.MaxResponseLength)
                {
                    yield return new ChatStreamUpdate
                    {
                        Type = StreamUpdateType.Truncated,
                        Content = $"响应已达到最大长度限制 ({options.MaxResponseLength} 字符)。",
                        Timestamp = DateTime.UtcNow
                    };
                    break;
                }
            }

            // 发送完成事件
            var duration = DateTime.UtcNow - startTime;
            yield return new ChatStreamUpdate
            {
                Type = StreamUpdateType.Completed,
                Content = responseBuilder.ToString(),
                Timestamp = DateTime.UtcNow,
                TokenCount = tokenCount,
                Metadata = new
                {
                    TotalDurationMs = duration.TotalMilliseconds,
                    TotalTokens = tokenCount,
                    AverageTokensPerSecond = tokenCount / Math.Max(duration.TotalSeconds, 0.1),
                    ResponseLength = responseBuilder.Length
                }
            };
        }
        catch (OperationCanceledException)
        {
            yield return new ChatStreamUpdate
            {
                Type = StreamUpdateType.Cancelled,
                Content = "响应生成已被用户取消。",
                Timestamp = DateTime.UtcNow
            };
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "流式响应生成时发生错误");
            yield return new ChatStreamUpdate
            {
                Type = StreamUpdateType.Error,
                Content = $"生成响应时发生错误: {ex.Message}",
                Timestamp = DateTime.UtcNow
            };
        }
    }

    private bool ContainsInappropriateContent(string content)
    {
        // 实现内容过滤逻辑
        var inappropriateKeywords = new[] { "敏感词1", "敏感词2" };
        return inappropriateKeywords.Any(keyword =>
            content.Contains(keyword, StringComparison.OrdinalIgnoreCase));
    }
}

public class ChatStreamUpdate
{
    public StreamUpdateType Type { get; set; }
    public string Content { get; set; } = string.Empty;
    public string PartialContent { get; set; } = string.Empty;
    public DateTime Timestamp { get; set; }
    public int TokenCount { get; set; }
    public object? Metadata { get; set; }
}

public enum StreamUpdateType
{
    Started,
    Content,
    Warning,
    Truncated,
    Completed,
    Cancelled,
    Error
}

public class StreamingOptions
{
    public bool EnableContentFilter { get; set; } = true;
    public int MaxResponseLength { get; set; } = 4000;
    public float Temperature { get; set; } = 0.7f;
    public bool ShowMetadata { get; set; } = false;
}
```

## 函数调用与智能代理开发

### 扩展 AI 能力的函数调用机制

GPT-OSS 支持函数调用（Function Calling），这是构建智能代理应用的关键特性。通过函数调用，AI 可以访问外部系统、执行特定操作或获取实时数据，从而大大扩展了其能力边界。

```csharp
public class WeatherFunction
{
    [Description("获取指定城市的当前天气信息")]
    public async Task<WeatherInfo> GetWeatherAsync(
        [Description("城市名称，例如：北京、上海")]
        string city,
        [Description("温度单位，celsius 或 fahrenheit")]
        string unit = "celsius")
    {
        // 模拟调用天气 API
        await Task.Delay(100); // 模拟网络延迟

        var random = new Random();
        var temperature = unit == "celsius" ? random.Next(-10, 35) : random.Next(14, 95);
        var conditions = new[] { "晴朗", "多云", "小雨", "阴天" };

        return new WeatherInfo
        {
            City = city,
            Temperature = temperature,
            Unit = unit,
            Condition = conditions[random.Next(conditions.Length)],
            Humidity = random.Next(30, 90),
            WindSpeed = random.Next(0, 20),
            LastUpdated = DateTime.Now
        };
    }
}

public class WeatherInfo
{
    public string City { get; set; } = string.Empty;
    public int Temperature { get; set; }
    public string Unit { get; set; } = string.Empty;
    public string Condition { get; set; } = string.Empty;
    public int Humidity { get; set; }
    public int WindSpeed { get; set; }
    public DateTime LastUpdated { get; set; }

    public override string ToString()
    {
        return $"{City}当前天气：{Condition}，温度 {Temperature}°{(Unit == "celsius" ? "C" : "F")}，" +
               $"湿度 {Humidity}%，风速 {WindSpeed} km/h (更新时间：{LastUpdated:HH:mm})";
    }
}

public class FileSystemFunction
{
    [Description("列出指定目录下的文件和文件夹")]
    public async Task<DirectoryInfo> ListDirectoryAsync(
        [Description("目录路径")]
        string path,
        [Description("是否包含隐藏文件")]
        bool includeHidden = false)
    {
        try
        {
            var directory = new DirectoryInfo(path);
            if (!directory.Exists)
            {
                throw new DirectoryNotFoundException($"目录不存在: {path}");
            }

            var files = directory.GetFiles()
                .Where(f => includeHidden || !f.Attributes.HasFlag(FileAttributes.Hidden))
                .Select(f => new FileItemInfo
                {
                    Name = f.Name,
                    Type = "文件",
                    Size = f.Length,
                    LastModified = f.LastWriteTime
                })
                .ToList();

            var directories = directory.GetDirectories()
                .Where(d => includeHidden || !d.Attributes.HasFlag(FileAttributes.Hidden))
                .Select(d => new FileItemInfo
                {
                    Name = d.Name,
                    Type = "文件夹",
                    Size = 0,
                    LastModified = d.LastWriteTime
                })
                .ToList();

            return new DirectoryInfo
            {
                Path = path,
                Files = files,
                Directories = directories,
                TotalItems = files.Count + directories.Count
            };
        }
        catch (Exception ex)
        {
            throw new InvalidOperationException($"无法访问目录 {path}: {ex.Message}");
        }
    }

    [Description("读取文本文件的内容")]
    public async Task<string> ReadTextFileAsync(
        [Description("文件路径")]
        string filePath,
        [Description("编码方式，默认为 UTF-8")]
        string encoding = "utf-8")
    {
        try
        {
            if (!File.Exists(filePath))
            {
                throw new FileNotFoundException($"文件不存在: {filePath}");
            }

            var encodingObj = encoding.ToLower() switch
            {
                "utf-8" => System.Text.Encoding.UTF8,
                "gbk" => System.Text.Encoding.GetEncoding("GBK"),
                "ascii" => System.Text.Encoding.ASCII,
                _ => System.Text.Encoding.UTF8
            };

            var content = await File.ReadAllTextAsync(filePath, encodingObj);

            // 限制返回内容的长度，防止过长的文件内容
            if (content.Length > 2000)
            {
                content = content.Substring(0, 2000) + "...\n(文件内容已截断)";
            }

            return content;
        }
        catch (Exception ex)
        {
            throw new InvalidOperationException($"无法读取文件 {filePath}: {ex.Message}");
        }
    }
}

public class DirectoryInfo
{
    public string Path { get; set; } = string.Empty;
    public List<FileItemInfo> Files { get; set; } = new();
    public List<FileItemInfo> Directories { get; set; } = new();
    public int TotalItems { get; set; }

    public override string ToString()
    {
        var result = new StringBuilder();
        result.AppendLine($"目录: {Path}");
        result.AppendLine($"总计: {TotalItems} 项");

        if (Directories.Any())
        {
            result.AppendLine("\n📁 文件夹:");
            foreach (var dir in Directories.Take(10)) // 限制显示数量
            {
                result.AppendLine($"  {dir.Name} (修改时间: {dir.LastModified:yyyy-MM-dd HH:mm})");
            }

            if (Directories.Count > 10)
            {
                result.AppendLine($"  ... 还有 {Directories.Count - 10} 个文件夹");
            }
        }

        if (Files.Any())
        {
            result.AppendLine("\n📄 文件:");
            foreach (var file in Files.Take(10)) // 限制显示数量
            {
                var sizeStr = FormatFileSize(file.Size);
                result.AppendLine($"  {file.Name} ({sizeStr}, 修改时间: {file.LastModified:yyyy-MM-dd HH:mm})");
            }

            if (Files.Count > 10)
            {
                result.AppendLine($"  ... 还有 {Files.Count - 10} 个文件");
            }
        }

        return result.ToString();
    }

    private string FormatFileSize(long bytes)
    {
        string[] sizes = { "B", "KB", "MB", "GB" };
        double len = bytes;
        int order = 0;
        while (len >= 1024 && order < sizes.Length - 1)
        {
            order++;
            len /= 1024;
        }
        return $"{len:0.##} {sizes[order]}";
    }
}

public class FileItemInfo
{
    public string Name { get; set; } = string.Empty;
    public string Type { get; set; } = string.Empty;
    public long Size { get; set; }
    public DateTime LastModified { get; set; }
}
```

### 智能代理的集成实现

```csharp
public class IntelligentAgentService
{
    private readonly IChatClient _chatClient;
    private readonly WeatherFunction _weatherFunction;
    private readonly FileSystemFunction _fileSystemFunction;
    private readonly ILogger<IntelligentAgentService> _logger;
    private readonly List<ChatMessage> _conversationHistory;

    public IntelligentAgentService(
        IChatClient chatClient,
        WeatherFunction weatherFunction,
        FileSystemFunction fileSystemFunction,
        ILogger<IntelligentAgentService> logger)
    {
        _chatClient = chatClient;
        _weatherFunction = weatherFunction;
        _fileSystemFunction = fileSystemFunction;
        _logger = logger;
        _conversationHistory = new List<ChatMessage>();

        // 设置系统提示，定义代理的角色和能力
        _conversationHistory.Add(new ChatMessage(ChatRole.System, """
            你是一个智能助手，具备以下能力：
            1. 获取天气信息 - 可以查询任何城市的实时天气
            2. 文件系统访问 - 可以列出目录内容和读取文本文件

            使用这些功能时请：
            - 确保参数正确和完整
            - 为用户提供清晰、有用的回答
            - 在访问文件系统时要小心，只访问用户明确指定的路径
            - 如果操作失败，请向用户解释原因并提供替代建议

            请以友好、专业的方式与用户交互。
            """));
    }

    public async Task<string> ProcessUserRequestAsync(string userMessage)
    {
        _conversationHistory.Add(new ChatMessage(ChatRole.User, userMessage));

        try
        {
            // 分析用户意图并决定是否需要调用函数
            var analysisPrompt = $"""
                用户消息: "{userMessage}"

                请分析用户的请求，确定是否需要调用以下任何功能：
                1. 天气查询 - 如果用户询问天气信息
                2. 文件系统操作 - 如果用户想要查看文件或目录

                如果需要调用功能，请以 JSON 格式回复：
                {{
                    "needsFunction": true,
                    "functionName": "功能名称",
                    "parameters": {{ "参数名": "参数值" }}
                }}

                如果不需要调用功能，请回复：
                {{
                    "needsFunction": false,
                    "response": "直接回答用户的问题"
                }}
                """;

            var analysisMessages = new List<ChatMessage>
            {
                new(ChatRole.System, "你是一个意图分析助手，专门分析用户请求并决定是否需要调用外部功能。"),
                new(ChatRole.User, analysisPrompt)
            };

            var analysisResult = await _chatClient.CompleteAsync(analysisMessages);
            var analysisText = analysisResult.Message.Text ?? "";

            _logger.LogInformation("意图分析结果: {Analysis}", analysisText);

            // 尝试解析分析结果
            try
            {
                var analysis = JsonSerializer.Deserialize<IntentAnalysis>(analysisText);

                if (analysis?.NeedsFunction == true)
                {
                    var functionResult = await ExecuteFunctionAsync(analysis.FunctionName, analysis.Parameters);

                    // 将函数结果整合到对话中
                    var contextMessage = $"函数调用结果: {functionResult}";
                    _conversationHistory.Add(new ChatMessage(ChatRole.System, contextMessage));

                    // 生成基于函数结果的回答
                    var responsePrompt = $"""
                        基于以下函数调用结果，请为用户提供一个清晰、有用的回答：

                        用户问题: {userMessage}
                        函数结果: {functionResult}

                        请用自然、友好的语言回答用户的问题。
                        """;

                    var responseMessages = new List<ChatMessage>
                    {
                        new(ChatRole.System, "请基于提供的信息生成有用的回答。"),
                        new(ChatRole.User, responsePrompt)
                    };

                    var finalResponse = await _chatClient.CompleteAsync(responseMessages);
                    var response = finalResponse.Message.Text ?? "抱歉，我无法生成合适的回答。";

                    _conversationHistory.Add(new ChatMessage(ChatRole.Assistant, response));
                    return response;
                }
                else if (!string.IsNullOrEmpty(analysis?.Response))
                {
                    _conversationHistory.Add(new ChatMessage(ChatRole.Assistant, analysis.Response));
                    return analysis.Response;
                }
            }
            catch (JsonException ex)
            {
                _logger.LogWarning("无法解析意图分析结果: {Error}", ex.Message);
            }

            // 如果分析失败，直接使用标准对话模式
            var standardResponse = await _chatClient.CompleteAsync(_conversationHistory);
            var response = standardResponse.Message.Text ?? "抱歉，我无法理解您的请求。";

            _conversationHistory.Add(new ChatMessage(ChatRole.Assistant, response));
            return response;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "处理用户请求时发生错误");
            return $"抱歉，处理您的请求时发生了错误: {ex.Message}";
        }
    }

    private async Task<string> ExecuteFunctionAsync(string functionName, Dictionary<string, object>? parameters)
    {
        try
        {
            switch (functionName?.ToLower())
            {
                case "weather" or "天气":
                    var city = parameters?.GetValueOrDefault("city")?.ToString() ?? "";
                    var unit = parameters?.GetValueOrDefault("unit")?.ToString() ?? "celsius";
                    var weather = await _weatherFunction.GetWeatherAsync(city, unit);
                    return weather.ToString();

                case "listdirectory" or "文件列表":
                    var path = parameters?.GetValueOrDefault("path")?.ToString() ?? "";
                    var includeHidden = bool.Parse(parameters?.GetValueOrDefault("includeHidden")?.ToString() ?? "false");
                    var dirInfo = await _fileSystemFunction.ListDirectoryAsync(path, includeHidden);
                    return dirInfo.ToString();

                case "readfile" or "读取文件":
                    var filePath = parameters?.GetValueOrDefault("filePath")?.ToString() ?? "";
                    var encoding = parameters?.GetValueOrDefault("encoding")?.ToString() ?? "utf-8";
                    var content = await _fileSystemFunction.ReadTextFileAsync(filePath, encoding);
                    return $"文件内容:\n{content}";

                default:
                    return $"未知的功能: {functionName}";
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "执行功能 {FunctionName} 时发生错误", functionName);
            return $"执行功能时发生错误: {ex.Message}";
        }
    }

    public void ClearHistory()
    {
        _conversationHistory.Clear();
        _conversationHistory.Add(new ChatMessage(ChatRole.System, """
            你是一个智能助手，具备天气查询和文件系统访问能力。
            请以友好、专业的方式与用户交互。
            """));
    }
}

public class IntentAnalysis
{
    [JsonPropertyName("needsFunction")]
    public bool NeedsFunction { get; set; }

    [JsonPropertyName("functionName")]
    public string FunctionName { get; set; } = string.Empty;

    [JsonPropertyName("parameters")]
    public Dictionary<string, object> Parameters { get; set; } = new();

    [JsonPropertyName("response")]
    public string Response { get; set; } = string.Empty;
}
```

## 性能优化与生产部署

### 内存管理与资源优化

在生产环境中部署 GPT-OSS 应用时，内存管理和性能优化至关重要。以下是一些关键的优化策略：

```csharp
public class OptimizedChatService : IDisposable
{
    private readonly IChatClient _chatClient;
    private readonly IMemoryCache _responseCache;
    private readonly ILogger<OptimizedChatService> _logger;
    private readonly SemaphoreSlim _concurrencyLimiter;
    private readonly Timer _cleanupTimer;
    private bool _disposed = false;

    public OptimizedChatService(
        IChatClient chatClient,
        IMemoryCache memoryCache,
        ILogger<OptimizedChatService> logger,
        IOptions<ChatServiceOptions> options)
    {
        _chatClient = chatClient;
        _responseCache = memoryCache;
        _logger = logger;

        // 限制并发请求数量，防止内存溢出
        _concurrencyLimiter = new SemaphoreSlim(options.Value.MaxConcurrentRequests, options.Value.MaxConcurrentRequests);

        // 定期清理过期缓存
        _cleanupTimer = new Timer(CleanupExpiredCache, null, TimeSpan.FromMinutes(5), TimeSpan.FromMinutes(5));
    }

    public async Task<string> SendMessageAsync(string userMessage, CancellationToken cancellationToken = default)
    {
        // 检查缓存
        var cacheKey = GenerateCacheKey(userMessage);
        if (_responseCache.TryGetValue(cacheKey, out string cachedResponse))
        {
            _logger.LogInformation("返回缓存的响应，键: {CacheKey}", cacheKey);
            return cachedResponse;
        }

        await _concurrencyLimiter.WaitAsync(cancellationToken);

        try
        {
            using var activity = ChatServiceMetrics.StartActivity("send_message");
            var stopwatch = Stopwatch.StartNew();

            var messages = new List<ChatMessage>
            {
                new(ChatRole.User, userMessage)
            };

            var completion = await _chatClient.CompleteAsync(
                messages,
                new ChatOptions
                {
                    Temperature = 0.7f,
                    MaxOutputTokens = 1024 // 限制输出长度以控制内存使用
                },
                cancellationToken);

            var response = completion.Message.Text ?? "无法生成响应";

            stopwatch.Stop();

            // 记录性能指标
            ChatServiceMetrics.RecordResponseTime(stopwatch.ElapsedMilliseconds);
            ChatServiceMetrics.RecordTokenCount(EstimateTokenCount(response));

            // 缓存响应（只缓存较短的响应以节省内存）
            if (response.Length <= 2000)
            {
                var cacheOptions = new MemoryCacheEntryOptions
                {
                    SlidingExpiration = TimeSpan.FromMinutes(30),
                    Size = response.Length
                };

                _responseCache.Set(cacheKey, response, cacheOptions);
            }

            return response;
        }
        catch (Exception ex)
        {
            ChatServiceMetrics.RecordError(ex.GetType().Name);
            _logger.LogError(ex, "发送消息时发生错误");
            throw;
        }
        finally
        {
            _concurrencyLimiter.Release();
        }
    }

    private string GenerateCacheKey(string userMessage)
    {
        using var sha256 = SHA256.Create();
        var hashBytes = sha256.ComputeHash(Encoding.UTF8.GetBytes(userMessage));
        return Convert.ToBase64String(hashBytes)[..12]; // 使用部分哈希作为键
    }

    private int EstimateTokenCount(string text)
    {
        // 简单的令牌计数估算（实际应用中可能需要更精确的方法）
        return text.Split(' ', StringSplitOptions.RemoveEmptyEntries).Length;
    }

    private void CleanupExpiredCache(object? state)
    {
        try
        {
            // 触发缓存压缩
            if (_responseCache is MemoryCache mc)
            {
                mc.Compact(0.2); // 移除 20% 的缓存条目
            }

            // 强制垃圾回收（在高负载环境中谨慎使用）
            if (GC.GetTotalMemory(false) > 500_000_000) // 500MB
            {
                GC.Collect(2, GCCollectionMode.Optimized);
                _logger.LogInformation("执行了垃圾回收，当前内存使用: {Memory} MB",
                    GC.GetTotalMemory(false) / 1024 / 1024);
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "清理缓存时发生错误");
        }
    }

    public void Dispose()
    {
        if (!_disposed)
        {
            _concurrencyLimiter?.Dispose();
            _cleanupTimer?.Dispose();
            _disposed = true;
        }
    }
}

public class ChatServiceOptions
{
    public int MaxConcurrentRequests { get; set; } = 10;
    public int CacheSizeLimitMB { get; set; } = 100;
    public bool EnableMetrics { get; set; } = true;
}

public static class ChatServiceMetrics
{
    private static readonly ActivitySource ActivitySource = new("ChatService");
    private static readonly Meter Meter = new("ChatService");

    private static readonly Counter<long> RequestCounter = Meter.CreateCounter<long>("chat_requests_total");
    private static readonly Histogram<double> ResponseTimeHistogram = Meter.CreateHistogram<double>("chat_response_time_ms");
    private static readonly Counter<long> ErrorCounter = Meter.CreateCounter<long>("chat_errors_total");
    private static readonly Histogram<long> TokenHistogram = Meter.CreateHistogram<long>("chat_tokens");

    public static Activity? StartActivity(string name) => ActivitySource.StartActivity(name);

    public static void RecordRequest() => RequestCounter.Add(1);

    public static void RecordResponseTime(double milliseconds) => ResponseTimeHistogram.Record(milliseconds);

    public static void RecordError(string errorType) => ErrorCounter.Add(1, new KeyValuePair<string, object?>("error_type", errorType));

    public static void RecordTokenCount(int tokenCount) => TokenHistogram.Record(tokenCount);
}
```

### 容器化部署与 Docker 配置

```dockerfile
# Dockerfile
FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS base
WORKDIR /app
EXPOSE 8080

FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src
COPY ["GPTOSSChatApp.csproj", "."]
RUN dotnet restore "GPTOSSChatApp.csproj"
COPY . .
WORKDIR "/src"
RUN dotnet build "GPTOSSChatApp.csproj" -c Release -o /app/build

FROM build AS publish
RUN dotnet publish "GPTOSSChatApp.csproj" -c Release -o /app/publish /p:UseAppHost=false

FROM base AS final
WORKDIR /app
COPY --from=publish /app/publish .

# 配置环境变量
ENV ASPNETCORE_ENVIRONMENT=Production
ENV OLLAMA_HOST=http://ollama:11434
ENV DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=false

# 安装中文字体支持
RUN apt-get update && apt-get install -y fonts-noto-cjk && rm -rf /var/lib/apt/lists/*

ENTRYPOINT ["dotnet", "GPTOSSChatApp.dll"]
```

```yaml
# docker-compose.yml
version: "3.8"

services:
  ollama:
    image: ollama/ollama:latest
    container_name: ollama-server
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    environment:
      - OLLAMA_HOST=0.0.0.0
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

  gpt-oss-app:
    build: .
    container_name: gpt-oss-chat
    ports:
      - "8080:8080"
    depends_on:
      - ollama
    environment:
      - OLLAMA_HOST=http://ollama:11434
      - ASPNETCORE_ENVIRONMENT=Production
    volumes:
      - ./logs:/app/logs
      - ./sessions:/app/sessions

volumes:
  ollama_data:
```

## 未来发展与 Foundry Local 集成

### Windows 原生 GPU 加速

微软正在推进 Foundry Local 项目，这是一个专为 Windows 平台优化的本地 AI 运行时。相比 Ollama，Foundry Local 提供了更深度的 Windows 系统集成和原生 GPU 加速支持。

Foundry Local 的主要优势包括：

首先是原生的 DirectML 支持，可以更高效地利用 Windows 系统上的各种 GPU，包括 Intel、AMD 和 NVIDIA 的硬件。其次是与 Windows AI Platform 的深度集成，提供更好的系统级优化和资源管理。最后是针对企业环境的增强安全性和管理功能。

### 与 Foundry Local 的代码兼容性

得益于 Microsoft.Extensions.AI 的抽象层设计，从 Ollama 迁移到 Foundry Local 将非常简单：

```csharp
// Ollama 配置
services.AddSingleton<IChatClient>(serviceProvider =>
{
    return new OllamaApiClient(new Uri("http://localhost:11434/"), "gpt-oss:20b");
});

// 未来的 Foundry Local 配置（预期接口）
services.AddSingleton<IChatClient>(serviceProvider =>
{
    return new FoundryLocalClient(new FoundryOptions
    {
        ModelName = "gpt-oss:20b",
        EnableGpuAcceleration = true,
        MaxMemoryUsage = "8GB"
    });
});
```

这种抽象化的好处是开发者可以在不同的运行时之间自由切换，根据具体的部署环境和性能需求选择最适合的解决方案。

## 总结与最佳实践

GPT-OSS 与 C# 的结合为开发者提供了构建强大本地 AI 应用的完整解决方案。通过本指南，你已经学会了：

设置和配置 .NET 环境以使用 GPT-OSS 模型，利用 Microsoft.Extensions.AI 抽象层构建可维护的 AI 应用，实现流式响应以提供更好的用户体验，通过函数调用扩展 AI 的能力边界，优化性能和资源使用以适应生产环境。

在实际开发中，建议遵循以下最佳实践：

始终使用依赖注入来管理服务生命周期，实现适当的错误处理和重试机制，监控应用性能和资源使用情况，为不同的部署环境准备配置选项，定期更新依赖包以获得最新的功能和安全修复。

GPT-OSS 的开源特性为 AI 应用开发带来了新的可能性。无论是构建智能客服系统、代码助手还是数据分析工具，本地运行的 AI 模型都能提供更好的隐私保护、成本控制和定制化能力。随着技术的不断发展，我们可以期待看到更多创新的应用场景和更强大的本地 AI 解决方案。
