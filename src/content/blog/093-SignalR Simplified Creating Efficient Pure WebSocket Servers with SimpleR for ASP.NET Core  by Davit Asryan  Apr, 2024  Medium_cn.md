---
pubDatetime: 2024-04-09
tags: [C#, SignalR]
source: https://medium.com/@vadrsa/signalr-simplified-creating-efficient-pure-websocket-servers-with-simpler-for-asp-net-core-dcac0535ff66
author: Davit Asryan
title: SignalR 简化：使用 SimpleR 为 ASP.NET Core 创建高效的纯 WebSocket 服务器
description: 互联网的发展使得即时通信技术变得比以往任何时候都重要，特别是对于物联网 (IoT)。有如此多的设备，比如智能家居小工具和工业传感器需要平稳地相互通信，因此，拥有快速可靠的通信变得至关重要。这就是 WebSockets 发挥作用的地方。它们非常适合 IoT 设备和服务器之间快速的双向交流，帮助一切保持实时连接和更新。
---

> 原文链接：[SignalR Simplified: Creating Efficient Pure WebSocket Servers with SimpleR for ASP.NET Core | by Davit Asryan | Apr, 2024 | Medium](https://medium.com/@vadrsa/signalr-simplified-creating-efficient-pure-websocket-servers-with-simpler-for-asp.net-core-dcac0535ff66)

互联网的发展使得即时通信技术变得比以往任何时候都重要，特别是对于物联网 (IoT)。随着如此多设备，如智能家居小工具和工业传感器需要平稳相互通信，快速可靠的通信变得至关重要。这就是 WebSockets 的用武之地。它们非常适合 IoT 设备和服务器之间的快速双向聊天，帮助一切实时保持连接和更新。

## 什么是SignalR?

[Real-time ASP.NET with SignalR | .NET (microsoft.com)](https://dotnet.microsoft.com/en-us/apps/aspnet/signalr)

SignalR 现在是 ASP.NET Core 框架的一部分，是用于创建 .net 实时应用的事实标准。

SignalR 是 ASP.NET Core 套件中设计用于构建实时 Web 应用的高级框架。通过使用自定义协议，它抽象了实时通信的复杂性，允许开发者将更多注意力放在应用逻辑而不是底层协议上。SignalR 的一个关键优势是其支持多种传输方式，以便于客户端和服务器之间的通信，确保应用在不同环境下都能维持实时功能。这些传输方式包括：

1. WebSockets，用于全双工通信，非常适合需要高频数据交换的场景。
2. 服务器发送事件 (SSE)，允许服务器在仅需要单向通信的场景中向客户端推送更新。
3. 长轮询，当客户端或服务器环境不支持更高级通信方法时可用的一种回退机制。

通过自动选择最佳可用的传输方法，SignalR 保证了 Web 应用在各种设备和网络条件下的最佳功能和性能。

SignalR 是用于开发实时 Web 应用的出色框架。**然而**，它对特定协议和客户端兼容性的依赖可能会引入限制，尤其是在需要直接 WebSocket 通信的场景中。

## SimpleR

[vadrsa/SimpleR: 基于 SignalR 的高性能纯 WebSocket 服务器库 (github.com)](https://github.com/vadrsa/SimpleR)

引入 SimpleR，这是一个基于 ASP.NET Core 的高性能、低开销、纯 WebSocket 服务器库。为了弥补 SignalR 可能不是最佳选择的情况，SimpleR 以简单和灵活为亮点。它舍弃了更重的协议和抽象，提供了一种直接、高效的方式来实现纯 WebSocket 服务器。这使得它成为需要直接控制 WebSocket 通信、自定义协议实现或与非 SignalR 客户端（例如，使用自己的自定义协议的 IoT 设备）工作的项目的理想选择。

在这次对 SimpleR 的介绍中，我们将探索其关键特性，并演示如何与 ASP.NET Core 无缝集成，以启用轻量级高性能 WebSocket 服务器的开发。

## 设计理念

SimpleR 主要基于 SignalR 构建，借鉴了 ASP.NET Core 团队的卓越工作。它旨在提供

1. 高性能、低分配的网络传输抽象，同时完全集成所有 ASP.NET Core 功能。
2. 性能和最小分配优先于易用性。
3. 协议不可知的方法。

## 设置环境

在深入了解使用 SimpleR 的具体内容之前，你需要从基础开始——创建一个空的 ASP.NET Core Web 应用。这为设置你的 WebSocket 服务器提供了一个干净的画布。

1. **打开你的命令行界面 (CLI)**：导航到你希望创建项目的文件夹。
2. **创建一个新的 Web 项目**：运行以下命令生成一个空的 ASP.NET Core Web 应用

```bash
dotnet new web -n SimpleThermostat.Server
```

3\. **导航到你的项目文件夹**：改变目录到你新创建的项目文件夹

```bash
cd SimpleThermostat.Server
```

4\. **安装 SimpleR.Server 包**：在项目目录中，运行以下命令将 SimpleR.Server 包添加到你的项目中。在本文撰写时，SimpleR 仍处于 alpha 版本。

```bash
dotnet add package SimpleR.Server
```

## 定义协议

我们首先定义客户端和服务器消息。为了支持不同类型的消息，我们将使用 _System.Text.Json_ 的多态序列化特性。

客户端，在这种情况下是温控器，将指标发送给服务器。

```csharp
[JsonDerivedType(typeof(ThermostatTemperatureMetric), "temperature")]
public class ThermostatMetric;

public class ThermostatTemperatureMetric : ThermostatMetric
{
    public ThermostatTemperatureMetric(float temperature)
    {
        Temperature = temperature;
    }

    public float Temperature { get; };
}
```

服务器则将命令发送给温控器。

```csharp
[JsonDerivedType(typeof(SetThermostatModeCommand), "setMode")]
public class ThermostatCommand;

public class SetThermostatModeCommand : ThermostatCommand
{
    public SetThermostatModeCommand(ThermostatMode mode)
    {
        Mode = mode;
    }

    public ThermostatMode Mode { get; }
}

public enum ThermostatMode
{
    Off,
    Heat,
    Cool
}
```

现在我们已经定义了协议所支持的所有消息，让我们定义如何将它们转换为字节，反之亦然。

SimpleR 的一个关键点是，它是协议不可知的。这意味着它需要用户提供一个协议定义，以便能够从字节流中构造消息。

对于这个演示，我们将不深入定义我们自己的自定义协议，而是将使用 WebSocket 的 EndOfMessage 作为我们消息的分隔符。

为此，我们需要定义一对读取器和写入器类。

```csharp
public class ThermostatMessageReader : IDelimitedMessageReader<ThermostatMetric>
{
    public ThermostatMetric ParseMessage(ref ReadOnlySequence<byte> input)
    {
        var jsonReader = new Utf8JsonReader(input);

        return JsonSerializer.Deserialize<ThermostatMetric>(ref jsonReader)!;
    }
}
```

```csharp
public class ThermostatMessageWriter : IMessageWriter<ThermostatCommand>
{
    public void WriteMessage(ThermostatCommand message, IBufferWriter<byte> output)
    {
        var jsonWriter = new Utf8JsonWriter(output);
        JsonSerializer.Serialize(jsonWriter, message);
    }
}
```

现在我们已经成功定义了我们自己的消息协议，我们准备继续进行应用逻辑。

## 转发消息

SimpleR 中的下一个重要主题是消息分配器。简而言之，消息分配器是一个高级管道，封装了分派连接消息的逻辑。这是进入我们应用逻辑的初始入口。

```csharp
public class ThermostatMessageDispatcher : IWebSocketMessageDispatcher<ThermostatMetric, ThermostatCommand>
{
    private float _targetTemp = 22;

    public Task OnConnectedAsync(IWebsocketConnectionContext<ThermostatCommand> connection)
    {
        return Task.CompletedTask;
    }

    public Task OnDisconnectedAsync(IWebsocketConnectionContext<ThermostatCommand> connection, Exception? exception)
    {
        return Task.CompletedTask;
    }

    public async Task DispatchMessageAsync(IWebsocketConnectionContext<ThermostatCommand> connection, ThermostatMetric message)
    {
        if(message is ThermostatTemperatureMetric temperatureMetric)
        {


            if (temperatureMetric.Temperature < _targetTemp)
            {

                await connection.WriteAsync(new SetThermostatModeCommand(ThermostatMode.Heat));
            }
            else if (temperatureMetric.Temperature > _targetTemp)
            {

                await connection.WriteAsync(new SetThermostatModeCommand(ThermostatMode.Cool));
            }
            else
            {

                await connection.WriteAsync(new SetThermostatModeCommand(ThermostatMode.Off));
            }
        }
    }
}
```

## 全部连接起来

在我们定义了消息协议和消息分配器之后，我们准备在 **Program.cs** 文件中将其全部连接起来。

```csharp
var builder = WebApplication.CreateBuilder(args);

builder.Services.AddSimpleR();

var app = builder.Build();

app.MapSimpleR<ThermostatMetric, ThermostatCommand>("thermostat/{deviceId}", b =>
{
    b.UseDispatcher<ThermostatMessageDispatcher>()
        .UseEndOfMessageDelimitedProtocol(
            MessageProtocol.From(new ThermostatMessageReader(), new ThermostatMessageWriter()));
});

app.Run();
```

就这么简单！

你可以在[这里](<http://simpler/examples%20at%20master%20%C2%B7%20vadrsa/SimpleR%20(github.com)>)找到服务器的源代码以及一个简单的客户端。

要探索 SimpleR 的所有功能，请查看 [Github 仓库](<http://vadrsa/SimpleR:%20High%20Performance%20Pure%20WebSocket%20Server%20Library%20based%20on%20SignalR%20(github.com)>)中的文档。如果你觉得它有用，请不要忘记给我们的仓库打个星标。这对我们很重要，并且有助于其他人找到我们。

## 结论

在我们结束对 SimpleR 的探索时，很明显，这个库是那些需要在 ASP.NET Core 中直接控制 WebSocket 通信的人的优秀选择。 展望未来，我们计划使 SimpleR 更加出色。我们将添加现成的协议以便更容易地构建应用，并包括针对广泛使用的标准（如 OCPP）的特殊包。

我们希望您能加入我们，帮助使 SimpleR 变得更好。无论您有什么想法、想修复bug，还是只是想说些什么，我们都洗耳恭听。您的帮助和反馈是这个项目成长的原因。而且，如果您喜欢 SimpleR 的作用和它对简单性的处理方式，请给我们的 GitHub 仓库打星。这对我们来说意义重大，有助于其他人找到我们。
