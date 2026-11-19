---
pubDatetime: 2026-11-19T09:30:09+08:00
title: "10｜Blazor、SignalR 和 AI：哪些现在能用？"
description: "围绕选课导入进度面板，实测 .NET 11 SignalR 在同一连接刷新身份和取消普通调用，解释 Blazor circuit 暂停，并给出独立试验 Blazor AI 的最小接入范围。"
tags: ["DotNet", "Blazor", "SignalR", "AI"]
slug: "dotnet-11-blazor-signalr-ai"
ogImage: "../../assets/1145/01-cover.jpg"
source: "https://learn.microsoft.com/en-us/aspnet/core/release-notes/aspnetcore-11?view=aspnetcore-11.0"
---

导入选课名单时，用户打开进度页等第一条回执，可能遇到登录续期，也可能点取消。ASP.NET Core 11 的 SignalR 可以在同一连接刷新身份，并把普通 Hub 调用的取消传到服务器。Blazor Interactive Server 还能选择暂停隐藏标签页的 circuit。三项能力各自解决连接、执行和 UI 状态中的不同问题，适合分开验收。

本机用 .NET 11.0.100 SDK 和 SignalR .NET 客户端 11.0.0 验证了刷新与取消。Blazor 的 circuit 是服务器为互动页面保留的会话状态，暂停和恢复需要用浏览器另测。实验性 Blazor AI 组件可以接在独立页面上，进度和导入状态仍由应用自身维护。

## 连接续期时核对用户和连接 ID

解压后用两个终端启动服务与客户端，或直接运行 `python check.py`。示例监听 loopback，使用两枚明确标记的测试令牌模拟同一学生的不同权限版本。实际项目须替换为已有的认证服务与令牌流转方式。[下载可运行的 SignalR 示例](https://celery94.github.io/assets/1145/realtime-progress-demo.zip)

```bash
dotnet run --project Server -- --urls http://127.0.0.1:5115
dotnet run --project Client
```

服务端针对 Hub 启用 `EnableAuthenticationRefresh`。示例还启用了 `CloseOnAuthenticationExpiration`，用 `OnAuthenticationRefresh` 检查刷新前后的用户主体相同。客户端获得新令牌后调用 `RefreshAuthenticationAsync()`，后续方法能读到更新后的声明。输出中的连接 ID 检查确认这次操作用的是同一连接。

```text
demo-v1
demo-v2 (same connection)
Progress: 1
Server observed cancellation.
```

生产回归时再检查自动续期、身份提供方失败、主体变化、撤销权限及过期关闭。授权仍应在敏感操作入口校验，刷新失败也要让页面有明确的重新登录入口。

## 页面上的取消按钮要对应服务端行为

客户端调用 `hub.InvokeAsync("Import", cts.Token)`。收到第一条 `Progress` 后取消令牌，服务端 Hub 参数中的令牌会触发，样本也等到服务器发回 `Cancelled`。应用要把令牌传入数据库查询、等待和其他协作式操作。已成功提交的批次需要明确恢复规则，取消令牌不会撤销已提交事务。

Blazor 页面可以用进度事件更新视图，通过 `InvokeAsync` 回到组件的渲染上下文。按钮将取消请求发给当前导入任务，收到服务端确认后再更新最终状态。页面离开时释放事件订阅和连接。长期任务应有服务端任务 ID，用户重新打开进度页时先取任务快照，再继续订阅。

隐藏标签页自动暂停是可选功能。Interactive Server 引用 `Microsoft.AspNetCore.Components.Server.AutoPause` 后，在原有根组件映射上配置 `WithBrowserOptions`，测试时可以将 `HiddenDelay` 设为 30 秒。分别验证切回前台、刷新和多标签页。稳定的办法是用任务 ID 恢复业务状态，让 circuit 只承担 UI 会话。该配置需要在实际 Blazor 页面验证，下载样本演示的是独立的 SignalR Hub。

## Blazor AI 放在可独立关闭的页面

`Microsoft.AspNetCore.Components.AI` 目前标为实验性。可以做一个只读的「解释导入错误」页面，向 `ChatPage` 提供 `UIAgent`，先接入固定的模拟消息和活动进度，再加模型客户端。官方示例中的 `ContentBlock` 可承载文本、活动、工具结果和审批交互。涉及写入、重跑或删除导入的工具要通过应用现有授权和服务端操作入口，避免把聊天流当成任务状态库。

```razor
<ChatPage Agent="agent">
    <ChatPage.MessageListContent>
        <BlockRenderer TBlock="ActivityContentBlock" Context="activity">
            <p>正在处理导入说明</p>
        </BlockRenderer>
    </ChatPage.MessageListContent>
</ChatPage>
```

这个局部示例依赖实验包和已配置的 `agent`，用于验证活动块渲染。把版本锁定在该实验项目，检查取消、刷新和 UI 重新挂载，必要时直接关闭路由。Aspire、Microsoft.Extensions.AI、MCP SDK 与 Microsoft Agent Framework 各有独立发布线。只安装 SDK 11 不会为应用提供这些包的版本或兼容保证。

先把进度快照、取消和身份续期的契约测清楚，再开实验页。即使团队暂时撤下该页面，用户也能在已有进度面板查看导入结果。

## 参考

- [ASP.NET Core 11 的 Blazor、SignalR 和实验组件](https://learn.microsoft.com/en-us/aspnet/core/release-notes/aspnetcore-11?view=aspnetcore-11.0)
- [SignalR 的身份认证和授权](https://learn.microsoft.com/en-us/aspnet/core/signalr/authn-and-authz?view=aspnetcore-11.0)
- [Blazor 服务端状态管理](https://learn.microsoft.com/en-us/aspnet/core/blazor/state-management/server?view=aspnetcore-11.0)
- [.NET 11 公告中的独立 AI 生态](https://devblogs.microsoft.com/dotnet/announcing-dotnet-11/)
