---
pubDatetime: 2026-09-14T08:07:00+08:00
title: "OpenTelemetry 观测 .NET RAG 的耗时与成本"
description: "一次 RAG 回答变慢，未必是模型慢。本文整理 .NET 管线的追踪契约：把嵌入、检索、重排、拼装提示词和生成拆成同一 trace 下的 span，只带版本标识与有界计数，离线评测与在线观测靠版本号关联。"
tags: ["RAG", "OpenTelemetry", ".NET", "可观测性", "Microsoft.Extensions.AI"]
slug: "dotnet-rag-opentelemetry-tracing-contract"
ogImage: "../../assets/1064/01-cover.jpg"
source: "https://www.devleader.ca/2026/09/13/observing-net-rag-systems-opentelemetry-latency-and-cost"
---

一个 RAG 回答变差了，你的仪表盘上只有一条「AI 请求 2.3 秒」。文档可能根本没被索引；检索可能返回了弱证据；重排器可能把有用的 chunk 丢掉了；提示词可能太长；也可能检索成功但生成失败。这五个原因需要五种不同的修法，而一条聚合指标把它们压成了同一个数字。

Nick Cosentino 在 [Observing .NET RAG Systems: OpenTelemetry, Latency, and Cost](https://www.devleader.ca/2026/09/13/observing-net-rag-systems-opentelemetry-latency-and-cost) 里给出一条 provider 无关的做法：用 OpenTelemetry 的 trace 把这条管线摊开成一个操作，让父子 span 直接回答「哪一段边界产出了这个结果」。本文按「定 span 契约 → 拆两条 trace → 装饰嵌入边界 → 划延迟与成本边界 → 遥测瘦身 → 与离线评测对齐」的顺序整理，并核对了 Microsoft.Extensions.AI 10.x 与 OpenTelemetry 语义约定的实际版本状态。

## 先定问题，再定 span 名

OpenTelemetry 把 trace 定义成一棵 span 树：一个 span 表示一次操作，嵌套关系保留了「请求」与「它派生的工作」之间的结构（[Tracing API 规范](https://opentelemetry.io/docs/specs/otel/trace/api/)）。RAG 需要的第一件事就是这个：一次问答请求对应一条 trace，为它做出贡献的每个阶段挂上子 span。

在挑 exporter 或画仪表盘之前，先写清楚这条 trace 必须回答什么：

- 请求有没有走到检索？每个阶段各花了多久？
- 有多少候选进入检索、重排和提示词拼装？
- 管线是返回了证据、生成了回答、失败，还是超时？
- 这次请求牵扯到哪个语料版本和嵌入版本（用不含敏感信息的标识）？

目标不是从遥测里重建一段对话，而是用计数、版本、结果和耗时解释请求走过的路径。问题定了，span 名和属性词表自然就稳定了。

用应用自己拥有、名字固定的 `ActivitySource`，不要在运行时动态创建：

```csharp
using System.Diagnostics;

namespace RagObservability;

public static class RagTelemetry
{
    public const string SourceName = "DevLeader.Rag";

    public static readonly ActivitySource Source = new(SourceName);
}

public sealed record RagRequestMetadata(
    int RequestedResultCount,
    string CorpusRevision,
    string RetrievalMode);

public static class RagTracing
{
    public static Activity? StartRequest(RagRequestMetadata metadata)
    {
        Activity? activity = RagTelemetry.Source.StartActivity(
            "rag.request",
            ActivityKind.Internal);

        activity?.SetTag("rag.requested_result_count", metadata.RequestedResultCount);
        activity?.SetTag("rag.corpus_revision", metadata.CorpusRevision);
        activity?.SetTag("rag.retrieval_mode", metadata.RetrievalMode);

        return activity;
    }
}
```

`Activity.Current` 会把当前操作沿异步调用链传递下去，`ActivitySource.StartActivity` 就在这个活动上下文里创建 span。入站的 `ActivityKind.Server` span 由框架的插桩负责创建；当它存在时，`rag.request` 自动成为它的子 span，你不需要自己造关联 ID。如果工作是队列消息或另一个服务发起的，就用宿主已有的 OpenTelemetry 插桩把 trace context 传过去，而不是给每个组件发明一套关联标识。

## 摄入和问答要分成两条 trace

摄入（ingestion）和问答共享同一份语料，但回答的是不同的运维问题。把它们塞进一个通用的 `rag.pipeline`，失败就很难归类。

摄入的根 span 用 `rag.ingest`，子 span 对应抽取、切分、生成嵌入和写入索引。它的属性应该标识源版本或批次数，而不是源文件正文、文件名或上传者身份——这样「索引写入失败」仍然能连到对应的语料版本，而文档内容不会进入遥测存储。

问答请求则挂在宿主入站 span 之下，用应用自己拥有的 `rag.request`，子 span 是：

1. `rag.embed_query`
2. `rag.search`
3. `rag.rerank`
4. `rag.build_prompt`
5. `rag.generate`

这里的 `rag.*` 命名和属性是应用私有约定，不是 OpenTelemetry 语义约定。私有约定更需要在发出第一个 span 之前就写下来：

| 元素                                           | 归属与稳定性                              | 允许的取值形态           | 基数上限                                    | 敏感性                     |
| ---------------------------------------------- | ----------------------------------------- | ------------------------ | ------------------------------------------- | -------------------------- |
| `rag.request`、`rag.search` 等 span 名         | 应用私有，随应用版本走                    | 固定的操作词表           | 固定的阶段名清单                            | 不含内容                   |
| `rag.*_revision`、`rag.retrieval_mode`         | 应用私有，属于发布元数据                  | 不透明版本 ID 或受控模式 | 已部署版本与模式的有限集合                  | 不含用户、文档、租户身份   |
| `rag.*_count`、`rag.timed_out`                 | 应用私有，属于结果元数据                  | 非负整数或布尔值         | 仅数值聚合与布尔值                          | 不含内容                   |
| 装饰器发出的 `gen_ai.*`、`server.*` 与嵌入指标 | Microsoft.Extensions.AI，实验性、可能变化 | 由装饰器决定             | 导出前先审查 provider、model、endpoint 取值 | 元数据同样可能需要访问控制 |

重排是可选的。没有启用时就不要发一个耗时为零的「成功」span——trace 应该描述真实发生过的工作。

检索 span 是一个很好的「窄边界」示例：只记候选数、返回数和结果状态，不记查询语句、过滤表达式、文档 ID 或检索到的文本。

```csharp
using System.Diagnostics;
using OpenTelemetry.Trace;

namespace RagObservability;

public sealed record SearchOutcome(
    int CandidateCount,
    int ReturnedCount,
    bool TimedOut);

public static class SearchTracing
{
    public static SearchOutcome TraceSearch(
        Func<SearchOutcome> search,
        int requestedResultCount)
    {
        using Activity? activity = RagTelemetry.Source.StartActivity(
            "rag.search",
            ActivityKind.Internal);

        activity?.SetTag("rag.requested_result_count", requestedResultCount);

        try
        {
            SearchOutcome outcome = search();

            activity?.SetTag("rag.candidate_count", outcome.CandidateCount);
            activity?.SetTag("rag.returned_count", outcome.ReturnedCount);
            activity?.SetTag("rag.timed_out", outcome.TimedOut);
            activity?.SetStatus(
                outcome.TimedOut ? ActivityStatusCode.Error : ActivityStatusCode.Ok);

            return outcome;
        }
        catch (Exception exception)
        {
            activity?.SetStatus(ActivityStatusCode.Error);
            activity?.RecordException(exception);
            throw;
        }
    }
}
```

这里把 `TimedOut` 当成依赖超时失败，所以置为 error 状态。如果你的应用把它定义为一种预期结果，就置 `Ok` 并额外发一个受控的结果码。正常返回空结果也可以是成功——语料里本来就没有可用来源。

`RecordException` 来自 `OpenTelemetry.Trace` 的扩展方法（需要 OpenTelemetry.Api 包）。要注意异常数据同样必须遵守你的遥测策略：异常消息里经常带着查询语句或文档片段，在把它接进来之前先确认这一点。返回的计数是诊断信号，不是质量分数：一次请求可以取回八个 chunk 却仍然过不了离线相关性评测，零结果也可能是完全正常的。

## 嵌入边界交给 Microsoft.Extensions.AI 的装饰器

嵌入调用在摄入和问答两条路径上都会出现，值得有一个一致的 span，因为它的延迟、错误和批处理行为会影响整条 trace。

`Microsoft.Extensions.AI` 提供了 `EmbeddingGeneratorBuilder` 和它的 `UseOpenTelemetry` 装饰器，作用于 `IEmbeddingGenerator<string, Embedding<float>>`：

```csharp
using Microsoft.Extensions.AI;

namespace RagObservability;

public static class EmbeddingInstrumentation
{
    public static IEmbeddingGenerator<string, Embedding<float>> AddTracing(
        IEmbeddingGenerator<string, Embedding<float>> innerGenerator)
    {
        return new EmbeddingGeneratorBuilder<string, Embedding<float>>(
                innerGenerator)
            .UseOpenTelemetry(
                sourceName: RagTelemetry.SourceName,
                configure: static generator => generator.EnableSensitiveData = false)
            .Build();
    }
}
```

这段代码刻意只接收一个已有的 generator，不在这里选 provider——遥测策略不该和嵌入服务绑在一起。传入 `sourceName` 是为了让 tracer provider 同时订阅应用插桩和嵌入插桩；`Activity.Current` 决定嵌入 span 挂在哪一层。

版本这件事值得说清楚，因为原文写的是「v10.7.0 源码，2026-08-10 核对过」。我复核了当前状态：

- `Microsoft.Extensions.AI` 10.7.0 确实存在，直接依赖 `Microsoft.Extensions.AI.Abstractions` 10.7.0；目前最新版本是 10.10.0。
- 我对比了 10.7.0 与 10.9.0 的 `OpenTelemetryEmbeddingGenerator` 和它的 builder 扩展：文件内容一致，`UseOpenTelemetry` 重载、`EnableSensitiveData` 属性、环境变量名都没变。也就是说原文的代码在那一串版本里可以照抄。
- `OpenTelemetryEmbeddingGenerator` 的类注释写着它实现的是「Generative AI systems 语义约定 v1.41」，并注明该规范仍是实验性的、可能变化。这条注释是准确的：OpenTelemetry 语义约定仓库当前已经发到 v1.44.0（2026-08-04）。所以「实验性」不是免责套话，指的就是这种落后于规范的状态。

关于 `EnableSensitiveData`，源码里的行为比文档一句话更具体：默认值是 `false`，除非环境变量 `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT` 被设为 `true`（大小写不敏感）；显式设置属性会覆盖环境变量。所以在生产配置里应当保持 `false`，并且不要打开那个环境变量——它会让原始请求和响应属性进入遥测。任何打开它的例外都应视为受限诊断配置，而不是「先开一天看看」。

装饰顺序也会改变 trace 的含义。如果缓存包在带追踪的 generator 外面，缓存命中时就不会产生下游嵌入 span；如果追踪包在缓存外面，trace 里会把缓存操作算进嵌入边界。两种都行，但要在契约里选一个、写下来，并且摄入和查询两条路径用同一个顺序，否则两组 trace 不可比。

## 延迟边界与成本边界

端到端耗时当然要，但它只是若干次等待的和。span 应该留在这条管线「把工作委托出去」的边界上：嵌入、检索、重排、提示词拼装、生成。有了每段耗时，才能区分本地计算和依赖调用，才能判断一次性能回退发生在选中证据之前还是之后。

提示词拼装即使很快也该有自己的内部 span：它是检索结果变成模型输入的那条边界。这里适合记有界的结构数据，比如 `rag.context_chunk_count` 和 `rag.context_character_count`，而不要挂上拼装好的提示词。如果确实需要内容级诊断，走单独审批、访问受限、短保留期的通道。一条 trace 只要能说明「上下文从 2 个 chunk 涨到了 12 个」，就已经能解释很多问题，而不必存下用户的问题或文档摘录。

生成阶段只在 provider 真的返回用量时记录用量，不要从捕获的提示词文本里反推 token 数。成本用一个通用的用量记录加外部费率来估算：

```csharp
namespace RagObservability;

public sealed record ModelUsage(int InputTokens, int OutputTokens);

public sealed record UsageRates(
    string RateRecordId,
    string ModelOrRoutingKey,
    string CurrencyCode,
    int TokensPerRateUnit,
    decimal InputCostPerRateUnit,
    decimal OutputCostPerRateUnit,
    DateOnly EffectiveDate);

public static class UsageCost
{
    public static decimal Estimate(ModelUsage usage, UsageRates rates)
    {
        if (rates.TokensPerRateUnit <= 0)
        {
            throw new ArgumentOutOfRangeException(
                nameof(rates.TokensPerRateUnit));
        }

        decimal input =
            usage.InputTokens / (decimal)rates.TokensPerRateUnit * rates.InputCostPerRateUnit;
        decimal output =
            usage.OutputTokens / (decimal)rates.TokensPerRateUnit * rates.OutputCostPerRateUnit;

        return input + output;
    }
}
```

关键是把结果当成一个估计值，并且把它绑在一条带生效日期、模型或路由键、币种和计价单位的费率记录上——这些放在 trace 之外，trace 里只带输入输出 token 数和费率记录 ID。这样既能做成本归因和变化检测，又不用把 provider 价格硬编码进业务代码；更重要的是，将来调价或换路由时，不会悄悄改变历史成本序列的含义。缓存命中、批量、区域和 provider 特有的计费规则，可能需要单独的费率记录或单独的算法。

## 遥测在离开进程之前就该瘦身

RAG 里最有用的遥测通常是元数据，不是内容。查询文本、原始提示词、检索到的段落、用户标识、访问过滤条件、生成的回答都可能含敏感数据（[OpenTelemetry 的敏感数据处理指引](https://opentelemetry.io/docs/security/handling-sensitive-data/)）。默认把它们记下来的实现，等于把自己的可观测性系统变成又一份需要治理、保留和按期删除的语料。

可以按这组边界来设计：

- 只在有另一个受控系统能解析的前提下，使用不透明且可轮换的请求或会话引用。
- 记版本标识、计数、布尔值、耗时、结果码和有界长度。
- 当文档 ID 和 chunk ID 会暴露内部结构时，把它们排除在通用遥测之外；确实需要用于排障时，走受限诊断通道加短保留期，而不是写进普通 trace。
- 在导出之前配置白名单、过滤或脱敏作为纵深防御，并且像检查应用日志一样抽查采样后的 trace。这些处理器不构成「可以抓正文」的许可。
- 在线侧只测隐私友好的信号，比如粗粒度反馈结果或升级（escalation）计数，把需要内容的部分留给离线标注。

顺便说一个容易被误读的点：候选数和返回数描述的是管线行为，不是答案质量。检索到八个 chunk 完全可能通不过离线相关性评测；返回零条也可能正确。trace 负责回答「这次发生了什么」，评测负责回答「这次有没有用」。

## 离线评测与在线观测靠版本号相关

离线评测问的是：在一份带标注的数据集上，某个已知查询有没有检索到有用的证据、产出有依据的回答。它需要保留判定结论、相关的 chunk 标识、语料版本和受控的评测输入。在线观测问的是另一个问题：生产环境里发生了什么——耗时、错误、空检索、有界计数和采样反馈。

这两套系统应该通过安全的版本元数据关联，而不是试图把每一条生产提示词导出成评测数据集。两边都打上同一组版本标识：

```csharp
namespace RagObservability;

public sealed record RagRevision(
    string CorpusRevision,
    string EmbeddingRevision,
    string RetrievalPolicyRevision,
    string PromptTemplateRevision);

public static class RevisionTags
{
    public static void AddTo(Activity? activity, RagRevision revision)
    {
        activity?.SetTag("rag.corpus_revision", revision.CorpusRevision);
        activity?.SetTag("rag.embedding_revision", revision.EmbeddingRevision);
        activity?.SetTag("rag.retrieval_policy_revision", revision.RetrievalPolicyRevision);
        activity?.SetTag("rag.prompt_template_revision", revision.PromptTemplateRevision);
    }
}
```

版本标识让「观察到变化」变成可检验的问题，但它不判断变化是好是坏。语料换版之后线上空结果上升，这是一个假设，需要拿离线评测去验证，而不是「模型退化了」的结论。流程因此可以很具体：上线前跑一次受控的离线对比，上线后用同一组版本标识加最小化字段观测生产行为。

## 一份可以直接照抄的追踪契约

在加更多属性之前，先把契约写下来：

- 摄入 trace 从 `rag.ingest` 开始，子 span 覆盖抽取、切分、嵌入、写索引；属性只有源版本和批次数。
- 问答 trace 从 `rag.request` 开始，子 span 是 `rag.embed_query`、`rag.search`、可选的 `rag.rerank`、`rag.build_prompt`、`rag.generate`。
- 两条 trace 都只带版本字段和连接结果所需的有界计数，不带内容。
- 嵌入边界交给 `UseOpenTelemetry` 装饰器，`EnableSensitiveData` 保持 `false`，装饰顺序在两条路径上一致。
- 生成 span 带输入输出 token 数和费率记录 ID，费率与币种留在 trace 之外。
- 离线评测与在线观测共享同一组版本标识，不共享原始内容。

这比一个「RAG 延迟」数字有用得多：它能告诉你生成变慢其实来自检索超时，新语料版本是不是让空结果变多了，提示词策略变更有没有推高输入 token。目标从来不是最多遥测，而是一条能让开发者解释请求路径的 trace、一个边界明确的成本估计，以及足够安全的版本数据把生产现象和离线评测连起来。

Aide Hub 会继续整理这类「把排障所需的证据提前设计进系统」的做法，覆盖 .NET、AI 助手和软件工程实践。如果你在自己的管线里遇到过无法归因的延迟，或者出于顾虑干脆没开遥测，欢迎把当时的取舍发来交流。

## 参考

- [Observing .NET RAG Systems: OpenTelemetry, Latency, and Cost](https://www.devleader.ca/2026/09/13/observing-net-rag-systems-opentelemetry-latency-and-cost)（原文，Nick Cosentino）
- [OpenTelemetry Tracing API 规范](https://opentelemetry.io/docs/specs/otel/trace/api/)
- [OpenTelemetry：Handling sensitive data](https://opentelemetry.io/docs/security/handling-sensitive-data/)
- [OpenTelemetry GenAI 语义约定](https://opentelemetry.io/docs/specs/semconv/gen-ai/)
- [Microsoft.Extensions.AI：IEmbeddingGenerator](https://learn.microsoft.com/en-us/dotnet/ai/iembeddinggenerator)
- [OpenTelemetryEmbeddingGenerator 源码（v10.7.0）](https://raw.githubusercontent.com/dotnet/extensions/v10.7.0/src/Libraries/Microsoft.Extensions.AI/Embeddings/OpenTelemetryEmbeddingGenerator.cs)
- [UseOpenTelemetry 扩展方法](https://learn.microsoft.com/en-us/dotnet/api/microsoft.extensions.ai.opentelemetryembeddinggeneratorbuilderextensions.useopentelemetry)
- [Microsoft.Extensions.AI 包版本](https://www.nuget.org/packages/Microsoft.Extensions.AI)
