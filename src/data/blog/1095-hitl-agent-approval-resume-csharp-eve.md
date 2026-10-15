---
pubDatetime: 2026-10-14T21:40:00+08:00
title: "C# 人的审批：Vercel Eve 暂停与恢复"
description: "Agent 停下来等人审批时，用户点的那一下并不等于授权。用 Vercel Eve 的审批契约加 NexusLabs.Eve，把待批请求、服务端判定和权威恢复结果拆成三层。"
tags: ["AI Agent", "C#", ".NET", "人机协同", "Vercel Eve"]
slug: "hitl-agent-approval-resume-csharp-eve"
ogImage: "../../assets/1095/01-cover.jpg"
source: "https://www.devleader.ca/2026/10/14/humanintheloop-ai-agents-in-c-approval-and-resume-with-vercel-eve"
---

一个 agent 停下来等着审批，页面上弹出一个绿色的按钮。用户点了。请求返回 200。然后应用告诉用户「已批准」。

这四步里，只有第三步是客观事实。**用户点的是哪一条待批请求、服务端最后认定这条请求变成了什么状态，都可能和界面上显示的不一致。**

Nick Cosentino 在 2026 年 10 月写的 [Human-in-the-Loop AI Agents in C#: Approval and Resume with Vercel Eve](https://www.devleader.ca/2026/10/14/humanintheloop-ai-agents-in-c-approval-and-resume-with-vercel-eve) 用 Vercel Eve 的审批契约加他自己的 .NET 客户端 NexusLabs.Eve，把这件事拆成了三层：待批请求怎么分类、决策怎么提交、权威结果怎么读回来。下面是这套做法的中文整理，代码按原文附上并加了我核对后的说明。

一个前提要先说清楚：原文的 C# 例子做过源码级审阅，但**没有重新编译或实际运行过**，本文也没有。下面的代码可以直接抄进项目，但涉及运行结果的地方我都按公开契约描述，不假装有实测数据。另外 NexusLabs.Eve 是作者维护的独立 .NET 客户端，不是 Vercel 官方 SDK。

## 暂停不等于认证

Eve 的人机输入协议把工作停在 `session.waiting`：服务端先发出 `input.requested`，收到被接受的回答后继续这一轮。浏览器可以在这期间关掉，回来的人应该看到同一条待处理任务，而不是一条被重新编出来的替代品。

这意味着整个流程里其实混着三个不同的问题：

- **在讨论哪条记录**：这是会话上下文，模型可以生成，也可以猜错。
- **这个人有没有权限看这个会话**：这是应用层授权，来自服务端的身份和存储。
- **这个人有没有明确选择批准这一个动作**：这是被记录的人为意图。

把它们压成一个「确认」对话框，最典型的后果就是答案被回答给了错误的问题。一个澄清问题（「你说的哪台合成设备？」）和一个资源上限提示（「还要继续吗？」）看起来都像是否题，但**两者都不构成执行待批工具的许可**。Eve 的请求模型里这四种是并列的分类，不是同一件事的强弱程度。

所以第一批要做的决定不是 UI 怎么做，而是先承认暂停是控制边界，不是认证机制。

## 第一步：在工具上写死「每次都要审批」

先定动作边界。Eve 0.63.0 从 `eve/tools` 导出 `defineTool`，从 `eve/tools/approval` 导出 `always`，`always()` 表示每次调用都需要审批。原文选了这条显式策略，而不是分类器或者「有时绕过人」的策略。

在已有的 Eve 0.63.0 工程里建 `agent/tools/propose_mock_checklist.ts`（需要项目里已经有 `zod`）。这个文件不是独立服务，也不是完整的部署配置：

```typescript
import { defineTool } from "eve/tools";
import { always } from "eve/tools/approval";
import { z } from "zod";

export default defineTool({
  description: "Propose a fictional checklist item; perform no real action.",
  inputSchema: z.object({
    equipmentId: z.literal("pump-demo-01"),
    item: z.literal("Review the synthetic inspection note"),
  }),
  approval: {
    request: always(),
    response: ({ responder }) => {
      const allowed = responder.principalId === "demo:reviewer-01";
      return allowed
        ? { status: "allowed" }
        : { status: "rejected", reason: "Not a synthetic checklist reviewer." };
    },
  },
  async execute({ equipmentId, item }) {
    return { equipmentId, item, mocked: true, recordedExternally: false };
  },
});
```

几个容易看漏的点：

- `responder.principalId` 是服务端认定过的身份。**这个字符串如果来自任意请求体，就等于没有认证任何人。**
- `rejected` 的语义是「这个 responder 没资格」，不是「这个动作被取消」。被拒之后共享的审批请求仍然处于待处理状态，可以换一个有资格的 responder 来答。
- 审批的「允许」和「取消」是两个不同的决定：一个拒绝 responder 的权限，一个记录对这项工作的决定。别共用一条错误提示。
- `always()` 好解释、好审计，代价是打断更多。条件策略能减少打断，但会引入需要单独验证的分支。教学示例选前者，是为了让边界一直可见。

这段策略只是**服务端审阅者检查**，不是完整的应用归属策略。下一步的 C# 边界还会单独要求调用方拥有这个会话。真实系统里两项检查都要在可信边界上做，而不是只靠一个藏起来的按钮。

## 第二步：按框架给出的 kind 分类，而不是按长相

NexusLabs.Eve 把服务端的线上 `kind` 映射到 `EveInputRequest.Kind`，取值是 `Question`、`ToolApproval`、`SessionLimit` 和 `Unknown`。原文例子里那个 `frameworkKind` 局部变量存的就是这个属性，不是额外的 SDK API。

分类的依据只有一个，就是 `Kind`。**不要从 `Display`、选项文案或者动作里的工具名去推断语义**——两个看起来都是「是/否」的提示，可能代表完全不同的决定。

把它理解成「选哪种交互」，而不是「选哪个答案」：

| Kind           | 需要的交互             |
| -------------- | ---------------------- |
| `Question`     | 回答问题的工作流       |
| `ToolApproval` | 显式的批准或取消工作流 |
| `SessionLimit` | 单独的继续或停止工作流 |
| `Unknown`      | 报兼容性问题，不猜     |

任何分支都不应该把一个通用的「是」翻译成恰好排在第一个的那个动作。

## 第三步：选中被审阅的那条请求

选择必须从一个**人真的看过**的请求标识开始，而待批请求本身要来自可信的会话状态，不能由调用方提供列表。调用方只提供决定和请求标识，服务端提供用来核对这些信息的事实。

原文的 `ApprovalBoundary.cs` 没有隐藏的辅助依赖，那个合成身份记录是为了演示检查而写的可执行假实现，不是认证提供程序：

```csharp
using System;
using System.Collections.Generic;
using System.Linq;
using NexusLabs.Eve;

namespace MaintenanceDemo;

public sealed record DemoCaller(string PrincipalId, bool IsAuthenticated);
public enum HumanDecision { Approve, Cancel }

public sealed class ApprovalBoundary
{
    public EveInputResponse Prepare(
        DemoCaller caller,
        string sessionOwner,
        IReadOnlyList<EveInputRequest> pending,
        string requestedId,
        HumanDecision decision)
    {
        if (!caller.IsAuthenticated ||
            caller.PrincipalId != sessionOwner ||
            caller.PrincipalId != "demo:reviewer-01")
        {
            throw new UnauthorizedAccessException("Reviewer or owner check failed.");
        }

        EveInputRequest request = pending.Single(
            candidate => candidate.RequestId == requestedId);
        EveInputRequestKind frameworkKind = request.Kind;
        switch (frameworkKind)
        {
            case EveInputRequestKind.Question:
                throw new InvalidOperationException("Use the question-answer workflow.");
            case EveInputRequestKind.SessionLimit:
                throw new InvalidOperationException("Use the session-limit workflow.");
            case EveInputRequestKind.ToolApproval:
                break;
            default:
                throw new NotSupportedException(
                    $"Unhandled input kind: {request.RawKind ?? "(missing)"}");
        }

        string optionId = decision switch
        {
            HumanDecision.Approve => "approve",
            HumanDecision.Cancel => "cancel",
            _ => throw new ArgumentOutOfRangeException(nameof(decision)),
        };
        if (!request.Options.Any(option => option.Id == optionId))
        {
            throw new InvalidOperationException("The chosen option is unavailable.");
        }

        return new EveInputResponse(request.RequestId, optionId: optionId);
    }
}
```

这段代码有几个刻意做成「会失败」的地方：

- `Single` 而不是 `First`：缺失和重复匹配都直接抛错，不会静默挑另一条请求。一批待批问题因此不会悄悄变成一批批准。
- 没有默认决定。调用方必须显式传入人做出的选择，编译器帮着挡住「忘了传」。
- 选项可用性检查发生在分类之后。它是用来核对已经分类好的请求，**不是**靠选项反推 kind。
- `approve` 和 `cancel` 这两个标识来自 Eve 的审批选项契约。

归属检查也是假的。真实应用里，认证和归属要从服务端验证过的身份和存储推导，不能取浏览器字段。而且可信宿主还需要把 owner、待批快照和传进服务的那个 `EveSession` 绑成同一个上下文——**拿真实 owner 的身份去比对另一个会话的待批列表，能通过这里的字符串比较，却越过了真正的资源边界**。会话、owner、快照应该作为一个服务端加载的上下文，而不是三个可以各自编辑的表单值。

还有一个时序问题：即使加载都正确，另一个人也可能在原审阅界面还开着的时候先答了。不要承诺本地看到的待批请求会一直待批。保住被选中请求的标识、只提交这一条决定、然后和服务端返回的结果对账。如果原请求已经不在了，就把这个事实显示出来，而不是让模型重新造一条。

一个够用的决策记录包含：验证过的 principal、会话标识、请求标识、显式决定和时间戳。**提交和接受要分开记录**，并且在权威结果回来之前不要把它叫做「已批准」。

## 第四步：只用 responses 恢复，然后读回真正结算了什么

`EveSession.RespondAsync` 只发送输入回答，不带用户消息。按契约，消息和输入回答是互斥的，把这条路单独留着，可以避免把一个人的决定变成一句含义模糊的对话续写。

原文的 `ApprovalResume.cs` 和上一个文件放在一起。可信宿主提供已有的 session、当前待批快照、验证过的 owner 和调用方，以及显式决定；这个类不创建身份、不加载凭据，也不替人做决定：

```csharp
using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using NexusLabs.Eve;

namespace MaintenanceDemo;

public sealed class ApprovalResume
{
    private readonly ApprovalBoundary _boundary = new();

    public async Task<EveTurnOutcome> ResolveAsync(
        EveSession session,
        DemoCaller caller,
        string sessionOwner,
        IReadOnlyList<EveInputRequest> pending,
        string requestedId,
        HumanDecision decision,
        CancellationToken cancellationToken)
    {
        EveInputResponse answer = _boundary.Prepare(
            caller, sessionOwner, pending, requestedId, decision);
        EveMessageResponse response = await session.RespondAsync(
            [answer], cancellationToken);
        EveTurnOutcome outcome = await response.GetOutcomeAsync(cancellationToken);

        foreach (EveInputResolution resolution in outcome.InputResolutions)
        {
            string meaning = resolution.Kind switch
            {
                EveInputRequestKind.Question => "Question answer",
                EveInputRequestKind.SessionLimit => "Session-limit decision",
                EveInputRequestKind.ToolApproval => "Tool-approval decision",
                _ => "Unsupported request kind",
            };
            Console.WriteLine(
                $"{meaning}: {resolution.RequestId} / {resolution.RawOutcome}");
            if (resolution.RequestId == requestedId &&
                (resolution.Kind != EveInputRequestKind.ToolApproval ||
                 resolution.Outcome == EveInputResolutionOutcome.Unknown))
            {
                throw new NotSupportedException("Unexpected approval resolution.");
            }
        }

        if (outcome.Status == EveTurnStatus.Failed)
        {
            Console.Error.WriteLine(
                $"Session {outcome.SessionId} failed; no successful result is assumed.");
            throw new InvalidOperationException("The resumed turn failed.");
        }

        Console.WriteLine($"Observed boundary: {outcome.Status}");
        Console.WriteLine(outcome.Message ?? "(No completed assistant message)");
        return outcome;
    }
}
```

我核对过 `NexusLabs.Eve` v0.1.0-alpha.14 的源码，这里用到的成员和原文一致：

- `EveInputResponse` 的构造签名是 `(string requestId, string? optionId = null, string? text = null)`。
- `EveInputResolution` 保留了请求 kind、权威结果、被接受的原回答，以及原始那一轮的坐标（`TurnId`、`StepIndex`、`Sequence`）。
- `EveTurnStatus` 只有 `Completed`、`Failed`、`Waiting` 三个值，`session.failed` 会投影成 `Failed`。
- `GetOutcomeAsync` 把消费到的事件聚合成 `InputResolutions`、`InputRequests`、`Message`、`Data` 和 `Status`。

有两个使用上的坑值得单独标出来。第一，**`EveMessageResponse` 是一次性的**：原文直接聚合而没有先枚举一遍再聚合，是因为重复消费同一条响应不成立。第二，`InputResolutions` 只包含本次消费期间观察到的结果，手工枚举过流之后不会再补回来。

这段控制台输出是观察，不是持久化审计存储。宿主可以用返回的 outcome 按真实标识记录被接受的结果。**如果没有出现匹配的 resolution，提交仍然没有被证明被接受**——要去和权威的会话事件对账，而不是因为 HTTP 请求返回了就造一条批准出来。

## 拒绝、候选事件和还没发生的输入

失败的 responder 尝试不一定意味着整条共享请求结束了。按固定的流契约，`approval.candidate` 这类结果（例如 `rejected`、`failed`、`timed-out`、`stale`）和 `approval.settled`（`approved`、`cancelled`）是分开的，而且**这两种事件都不会终止这一轮**。一个没权限的人试过一次，不该让整个工作流变成「被拒绝」。

所以给用户的措辞要分开：

- 「你的尝试被拒绝了」说的是 responder 的结果。
- 「这个动作已被取消」说的是结算。
- 「恢复的这一轮失败了」说的是执行状态。

用一个绿色或红色徽标把这三件事吞掉，人会看不懂还剩什么没处理。

解码器的行为也值得记住：缺少判别字段会报成 `Unknown` 且 `RawKind` 为 `null`；无法识别的字符串报成 `Unknown` 并带上线上原值；判别字段存在但不是字符串，是协议错误。报告兼容性问题时保留这些差别——**信息缺失不等于可以从标签推断出批准**。

传输层的错误也仍然是错误。原文的例子不捕获它们然后返回一个「成功的空结果」。要独立验证缺失请求、未授权调用方、被拒的候选和失败的恢复轮次，可以用 mock handler 在不通真实 agent 的情况下覆盖，比如 [Mocking HttpClient in C#](https://www.devleader.ca/2026/07/02/mock-httpclient-c-delegatinghandler-mock-handlers-and-integration-testing) 里那套 `DelegatingHandler` 的做法。

## 三层检查，各说各知道的事

人机审批容易变复杂，通常是因为一层在替另一层下结论。把它们分开以后，责任就清楚了：

| 层         | 只负责说                     | 不该说                   |
| ---------- | ---------------------------- | ------------------------ |
| 浏览器     | 这个人选了什么               | 这算不算批准             |
| 可信应用   | 归属和权限检查的结果         | 服务端结算成了什么       |
| Eve 服务端 | 这条待批输入最终解析成了什么 | 外部动作是否只执行了一次 |
| 执行结果   | 工作完成还是失败             | 人是否同意过             |

最后一行对应一个容易被过度承诺的说法：**审批不是授权，也不是恰好执行一次**。人机审批回答的是「这个人想不想让这件事继续」，授权回答的是「这个人有没有资格做这个决定」，幂等回答的是「重复执行会不会改变效果」。它们在实际操作中相关，但一个答案替代不了另一个。本文的工具只返回 mock 数据、不做外部写入；真实的集成需要单独设计效果保障，包括操作标识和下游去重契约。

代价也要说清楚：要额外跟踪的状态变多了——提交记录、responder 尝试、权威 resolution、执行结果。原文的判断是这笔账划得来，因为另一种选择是把不确定性藏在一个成功提示后面。我同意这个取舍，但补一句适用边界：**如果你的动作确实不可逆，这四类记录不是「可以加」的审计，而是上线前提**；如果动作只是读数据，那就该老老实实标成只读，别为了流程感加一个假审批。

## 怎么验证这套东西

原文的这些检查都没有被实际执行过，下面是我按代码和公开契约整理的验证路径，可以直接当清单用：

1. **边界层不需要网络。** 给 `ApprovalBoundary.Prepare` 传伪造的 caller 和 pending 列表，确认三件事：owner 不匹配会被拒；`requestedId` 传另一个人的请求会抛 `InvalidOperationException`；`Question` 和 `SessionLimit` 会走到专门的错误上而不是被当成审批。
2. **传输层确认只提交被选中的标识。** 用 mock handler 接住 `RespondAsync` 的请求体，断言里面只有那一条 `requestId` 和那一个 `optionId`，没有第二个待批项。
3. **恢复轮次按 `RawOutcome` 分派。** 构造 `Denied`、`Ignored`、`Invalid`、`Answered` 的 outcome，确认 UI 和审计存储没有把它们统一成「成功」。
4. **兼容性分支。** 让服务端返回缺失判别字段和未知字符串的输入请求，确认 `Kind` 是 `Unknown`、`RawKind` 分别是 `null` 和原值，并且流程停下来等人工处理，而不是猜一个 kind 继续跑。

常见错误和优先检查项：

- **抛 `InvalidOperationException: The chosen option is unavailable.`**：多半是工具端契约变了，`approve` / `cancel` 这两个标识不再出现在 `Options` 里。先去看 `defineTool` 里的审批配置，再改客户端。
- **`Single` 抛「Sequence contains no elements」**：说明本地的待批快照过期了，别人已经答过或被清理。这不是重试就能解决的错误，应该提示用户重新加载待批列表。
- **点了批准但什么都没发生**：先确认 `outcome.InputResolutions` 里有没有匹配的 `requestId`。没有就说明提交没被接受，别在 UI 上打勾。
- **真实身份总是被拒**：检查传给 `Prepare` 的 owner 是不是从这个 session 服务端加载的。用另一个会话的 owner 去比对这个快照，能通过字符串比较，却越过了资源边界。

## 相关阅读

- 原文作者先前写的 [Vercel Eve Explained: Durable AI Agents and C# Integration](https://www.devleader.ca/2026/10/02/vercel-eve-explained-durable-ai-agents-and-c-integration)，讲的是 Eve 的持久运行时和重放边界。
- [Vercel Eve Tutorial for C# Developers](https://www.devleader.ca/2026/10/05/vercel-eve-tutorial-for-c-developers-build-an-aspnet-core-agent-client)，讲 ASP.NET Core 怎么接上同一个 pinned agent。
- 如果你用 Microsoft Agent Framework，类似的工具审批思路在[这篇](https://www.devleader.ca/2026/03/11/tool-approval-and-humanintheloop-in-microsoft-agent-framework)里，但类型和契约不能混用。

## 参考

- [Human-in-the-Loop AI Agents in C#: Approval and Resume with Vercel Eve](https://www.devleader.ca/2026/10/14/humanintheloop-ai-agents-in-c-approval-and-resume-with-vercel-eve)
- [Vercel Eve 0.63.0：human-in-the-loop 与工具审批契约](https://github.com/vercel/eve/blob/eve%400.63.0/docs/tools/human-in-the-loop.md)
- [NexusLabs.Eve 0.1.0-alpha-0014（NuGet）](https://www.nuget.org/packages/NexusLabs.Eve/0.1.0-alpha-0014)
- [eve-client v0.1.0-alpha.14 README](https://github.com/ncosentino/eve-client/blob/v0.1.0-alpha.14/README.md)
- [eve-client 附件与人机输入文档](https://github.com/ncosentino/eve-client/blob/v0.1.0-alpha.14/docs/attachments-and-input.md)
- [eve-client 流式契约文档](https://github.com/ncosentino/eve-client/blob/v0.1.0-alpha.14/docs/streaming.md)
- [EveInputRequest 源码](https://github.com/ncosentino/eve-client/blob/v0.1.0-alpha.14/src/NexusLabs.Eve/EveInputRequest.cs)
- [EveInputResponse 源码](https://github.com/ncosentino/eve-client/blob/v0.1.0-alpha.14/src/NexusLabs.Eve/EveInputResponse.cs)
- [EveInputResolutionOutcome 源码](https://github.com/ncosentino/eve-client/blob/v0.1.0-alpha.14/src/NexusLabs.Eve/EveInputResolutionOutcome.cs)
- [EveTurnOutcome 源码](https://github.com/ncosentino/eve-client/blob/v0.1.0-alpha.14/src/NexusLabs.Eve/EveTurnOutcome.cs)

---

如果这类「agent 停下来等人」的边界设计对你有用，Aide Hub 会继续写 AI 助手接入、开发工具和软件工程实践方面的内容。
