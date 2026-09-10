---
pubDatetime: 2026-09-10T08:06:00+08:00
title: "RAG 黄金评测集：一份可追溯的证据契约"
description: "RAG 黄金评测集是评测的证据契约：每个用例记录查询、预期答案、支撑 chunk、来源版本和人工评审，缺一项就难以复核。本文说明如何构建、校验、用合成数据补候选、用人工校准并随证据更新。"
tags: ["RAG", "评测", "Eval", "数据工程"]
slug: "rag-golden-evaluation-set-evidence-contract"
ogImage: "../../assets/1061/01-cover.jpg"
source: "https://www.devleader.ca/2026/09/09/golden-evaluation-sets-for-rag-synthetic-data-human-calibration-and-drift"
---

换了切分策略后重新跑评测，分数从 0.82 掉到 0.79。这是检索变差了吗？还是切分让 chunk ID 变了、语料被重新组织，评测数据本身已经对不上当前语料？如果评测记录里没有「这次跑在哪个语料快照上」这一项，你无法回答这个问题。数字看起来还是可复现的，但可复现不等于可信：它可能在拿新检索器对比一份早已不存在的证据。

Nick Cosentino 在 [Golden Evaluation Sets for RAG: Synthetic Data, Human Calibration, and Drift](https://www.devleader.ca/2026/09/09/golden-evaluation-sets-for-rag-synthetic-data-human-calibration-and-drift) 里把 RAG golden dataset 定义为一次评测背后的证据契约（evidence contract）：它记录被问的问题、可接受的答案、支撑答案的 chunk，以及让这些判断成立的语料版本。他把它比作一个小而版本化的产品——不是一堆 prompt，而是「人工决策 + 来源溯源 + 何时必须重审的规则」。本文按构建、校验、合成数据、人工校准、刷新的顺序整理这套做法。

## 一个用例：把判定与证据绑在一起

2024 年的 RAG 评测综述 [Evaluation of Retrieval-Augmented Generation: A Survey](https://arxiv.org/abs/2405.07437) 指出，RAG 评测困难，部分原因是系统混合了检索与生成，又依赖动态变化的知识源。这个「动态」正是容易被忽视的操作细节：关于某个 chunk 的判定，只在产生它的语料和切分方案下有效。

从每个有意义的用户需求开始写一个 case。一个 case 应包含：

- 用户查询（query）
- 预期答案（expected answer）
- 作为证据的相关 chunk ID
- 这些 chunk 的来源出处（provenance）
- 不可变的语料版本（corpus revision）

预期答案不是要求系统逐字复述的脚本，而是「当引用的证据可得时，评审人期望看到的事实结果」。这个区分很关键：答案换一种说法仍可以正确；反过来，一段流畅的答案即使与参考答案很像，也可能包含一个没有依据的细节。所以黄金集必须同时记录「答案预期」和「让这个预期站得住的检索证据」。

下面是原文提供的 provider-agnostic C# 表示，只依赖 .NET 基础类库，可直接作为 .NET 8 控制台项目的 `Program.cs`：

```csharp
using System;
using System.Collections.Immutable;
using System.Text.Json;

namespace GoldenDatasetExamples;

public sealed record ChunkProvenance(
    string ChunkId,
    string DocumentId,
    string SourceUri,
    string SourceRevision,
    string ContentHash);

public enum ReviewStatus
{
    Pending,
    Approved,
    Rejected
}

public sealed record ReviewDecision(
    ReviewStatus Status,
    string ReviewedBy,
    DateTimeOffset ReviewedAt,
    string Reason);

public sealed record GoldenCase(
    string Id,
    string Query,
    string ExpectedAnswer,
    ImmutableArray<string> RelevantChunkIds,
    ImmutableArray<ChunkProvenance> Provenance,
    string CorpusRevision,
    ReviewDecision Review);

public static class Program
{
    public static void Main()
    {
        var caseToSerialize = new GoldenCase(
            Id: "refund-policy-001",
            Query: "When can a customer request a refund?",
            ExpectedAnswer: "A customer can request a refund within 30 days of purchase.",
            RelevantChunkIds: ImmutableArray.Create("refund-policy-v4:12"),
            Provenance: ImmutableArray.Create(
                new ChunkProvenance(
                    "refund-policy-v4:12",
                    "refund-policy-v4",
                    "https://docs.example.test/refunds",
                    "v4",
                    "4D1C")),
            CorpusRevision: "corpus-2026-09-01",
            Review: new ReviewDecision(
                ReviewStatus.Approved,
                "Avery",
                new DateTimeOffset(2026, 9, 1, 0, 0, 0, TimeSpan.Zero),
                "The source revision supports the expected answer."));

        Console.WriteLine(JsonSerializer.Serialize(
            caseToSerialize,
            new JsonSerializerOptions { WriteIndented = true }));
    }
}
```

最容易漏的正是那些看起来「多余」的字段。文档标题对评审人有帮助，但 chunk ID 告诉检索层它评的是什么；来源 URL 方便人工查证，而 source revision 和 content hash 用来区分同一份文档的不同版本；`CorpusRevision` 再把单个事实串成整个语料库的可测快照。如果语料混用多种来源类型，保持 provenance 字段形状一致——不要让一个 case 放文件路径、另一个放 URL、再一个放临时备注，评审人应该不用猜「这一版用的是哪套元数据约定」。

同一问题也可以有多个可接受答案：要么把预期答案写成「描述受支持结果」的期望，要么建模多个接受语句，关键是用例里可接受的每个结果都对应记录的语料版本。

## 校验两次，并故意从严

JSON 让黄金集可移植，但可移植不等于可信。校验要做两次：case 编写时一次，加载进评测时再一次。校验器应尽早拒绝这类含糊用例：空查询、空预期答案、重复的相关 chunk ID、缺 provenance，以及 provenance 条目对应不上已记录的 chunk。

```csharp
// 沿用上面的 GoldenCase / ChunkProvenance / ReviewStatus / ReviewDecision 定义
using System;
using System.Collections.Generic;
using System.Collections.Immutable;
using System.Linq;

namespace GoldenDatasetExamples;

public static class GoldenCaseValidator
{
    public static ImmutableArray<string> Validate(GoldenCase testCase)
    {
        var errors = ImmutableArray.CreateBuilder<string>();

        if (string.IsNullOrWhiteSpace(testCase.Query))
        {
            errors.Add("Query is required.");
        }

        if (string.IsNullOrWhiteSpace(testCase.ExpectedAnswer))
        {
            errors.Add("Expected answer is required.");
        }

        if (string.IsNullOrWhiteSpace(testCase.CorpusRevision))
        {
            errors.Add("Corpus revision is required.");
        }

        if (testCase.RelevantChunkIds.IsDefaultOrEmpty)
        {
            errors.Add("At least one relevant chunk is required.");
        }

        if (testCase.RelevantChunkIds.Distinct(StringComparer.Ordinal).Count()
            != testCase.RelevantChunkIds.Length)
        {
            errors.Add("Relevant chunk IDs must be unique.");
        }

        if (testCase.RelevantChunkIds.Any(
                id => testCase.Provenance.Count(provenance =>
                    string.Equals(provenance.ChunkId, id, StringComparison.Ordinal)) != 1))
        {
            errors.Add("Every relevant chunk must have exactly one provenance entry.");
        }

        if (testCase.Review.Status == ReviewStatus.Approved
            && (string.IsNullOrWhiteSpace(testCase.Review.ReviewedBy)
                || string.IsNullOrWhiteSpace(testCase.Review.Reason)))
        {
            errors.Add("Approved cases require reviewer and decision metadata.");
        }

        return errors.ToImmutable();
    }
}
```

原文把这份校验写得故意严格：一个没有相关 chunk 的 case，可能是合法的拒不回答（abstention）场景，但它必须是数据模型里显式的 case 类型，而不是 schema 中偶然出现的空洞。否则，「缺少判定」会被误读为「这个用例预期什么都不用检索」，两类问题就混在一起了。

同样的纪律适用于 chunk 重新生成。如果新的切分器把 `refund-policy-v4:12` 切成三块，不要静默地把旧 ID 映射到第一块新 chunk：重新核对新证据与查询的关系，赋予新的 corpus revision，需要跨版本对比时保留历史 case。

## 合成数据是候选，不是真值

新语料没有查询历史时，合成问答能快速搭起一个起点池。给生成器三个约束：只给一个有边界的源片段、必须返回源 chunk ID、只问真实读者可能问的问题，然后把输出放进评审队列。

边界在于：合成的黄金集条目是关于「什么是好用例」的假设，不是 ground truth。[Ragas: Automated Evaluation of Retrieval Augmented Generation](https://arxiv.org/abs/2309.15217) 的核心做法就是用人工标注的 ground truth 对照生成的数据，这也正是需要人工评审的原因。一个候选被批准之前，必须有人确认查询合理、预期答案不超过源支持的范围、列出的 chunk 确实充分。

生成的用例建议只用在三处：

- 给评审积压队列播种与显式源 chunk 绑定的候选；
- 围绕人工写好的场景拓展措辞，但不替换人工场景；
- 探索新添加的文档，并把每个用例明确标记为未校准（uncalibrated）。

不要因为生成的 JSON 很干净就把它提升为真值。候选的 Q、A、来源版本和 chunk 列表都要过人工确认，任何一项不过就编辑或丢弃。被拒绝的候选可以留着改进生成 prompt，但绝不能因为「还像样」就混进已批准集合。此外，也要人工补上领域语言、不完整提问和拒绝回答这些场景——它们最容易暴露合成的覆盖盲区。

## 人类 sentinel 校准

全套人工评审的成本很高，小型的人类 sentinel 集合是实用补充：刻意维护的一组用例，用于在知情评审下对照合成与自动化评测的结果。选 sentinel 看的是决策价值，不是方便程度：

- 常见查询
- 措辞含糊的问题
- 后果严重的政策问题
- 需要联合两个来源的问题
- 正确结果本身就是「不确定」的问题

还应包含「文档一修订或 chunk 边界一动就容易坏」的用例。对每个 sentinel，两位评审人独立检查查询、预期答案、相关 chunk 和语料版本，再记录分歧的解决方式与理由。下面是原文的一致性检查代码：

```csharp
// 沿用上面的相关类型定义；CaseId 对应 GoldenCase.Id
using System;
using System.Collections.Immutable;
using System.Linq;

namespace GoldenDatasetExamples;

public sealed record SentinelReview(
    string CaseId,
    string Reviewer,
    ImmutableArray<string> RelevantChunkIds,
    bool ExpectedAnswerSupported);

public sealed record CalibrationResult(
    string CaseId,
    bool IsCalibrated,
    ImmutableArray<string> Differences);

public static class SentinelCalibrator
{
    public static CalibrationResult Compare(
        SentinelReview first,
        SentinelReview second)
    {
        var differences = ImmutableArray.CreateBuilder<string>();

        if (!string.Equals(first.CaseId, second.CaseId, StringComparison.Ordinal))
        {
            differences.Add("Reviews refer to different cases.");
        }

        if (first.ExpectedAnswerSupported != second.ExpectedAnswerSupported)
        {
            differences.Add("Reviewers disagree on answer support.");
        }

        if (!first.RelevantChunkIds.Order().SequenceEqual(second.RelevantChunkIds.Order()))
        {
            differences.Add("Reviewers selected different relevant chunks.");
        }

        return new CalibrationResult(
            first.CaseId,
            differences.Count == 0,
            differences.ToImmutable());
    }
}
```

代码只检查一致，不能制造一致。两位评审人分歧时，回到源材料、澄清预期答案或查询范围，然后记录解决方式——而不是把两人的 chunk 列表平均一下。这样的记录写进数据模型，之后重审同一个 case 时，当时的判断依然可查。

这套做法还有一层作用：让评测数据独立于实现热情。团队可以换检索器、换 prompt、换搜索方式，但不该顺手改 sentinel 的预期答案，让新方案「看起来更成功」。如果改动确实合理，那就作为一次修订记录在案。关于语料怎么变成 chunk 的背景，可参考原文提到的 [Chunking Strategies for RAG with Semantic Kernel in C#](https://www.devleader.ca/2026/03/16/chunking-strategies-for-rag-with-semantic-kernel-in-c-fixedsize-sentence-and-semantic-chunking)。

## 证据变化时刷新

黄金集里的声明绑定语料版本，所以需要刷新策略。刷新是被「可能使判定失效的变化」触发的审查，而不是定期重写整个集合。触发条件包括：来源修订变化、chunk 被删除或替换、采用新的切分策略、embedding 迁移需要重建索引、检索过滤条件变化；以及遥测显示出现已评审的真实查询模式、但集合里没有对应用例——原文建议先让这类观察可查询（例如用 OpenTelemetry），再提新增 case。

```csharp
// 为示例简化，只保留刷新所需的字段
using System;
using System.Collections.Immutable;

namespace GoldenDatasetExamples;

public sealed record GoldenCase(string Id, string CorpusRevision);

public sealed record RefreshRequest(
    string CaseId,
    string PreviousCorpusRevision,
    string CurrentCorpusRevision,
    ImmutableArray<string> Reasons);

public static class GoldenSetRefresh
{
    public static RefreshRequest? CreateRequest(
        GoldenCase testCase,
        string currentCorpusRevision,
        bool sourceChanged,
        bool newQueryPatternObserved)
    {
        var reasons = ImmutableArray.CreateBuilder<string>();

        if (!string.Equals(
                testCase.CorpusRevision,
                currentCorpusRevision,
                StringComparison.Ordinal))
        {
            reasons.Add("The corpus revision changed.");
        }

        if (sourceChanged)
        {
            reasons.Add("A source behind the case changed.");
        }

        if (newQueryPatternObserved)
        {
            reasons.Add("A reviewed query pattern is not represented.");
        }

        return reasons.Count == 0
            ? null
            : new RefreshRequest(
                testCase.Id,
                testCase.CorpusRevision,
                currentCorpusRevision,
                reasons.ToImmutable());
    }
}
```

刷新是审查门，不是自动重写。语料版本变化只是告诉你旧证据可能过期，它不回答三个更具体的问题：该插入哪块替代 chunk、预期答案是否变化、这个 case 是否应该变成 abstention。这些决策仍然需要检查源材料；sentinel 用例还需要人工校准。

审查范围与证据变化成比例：只修订某条政策时，检查依赖它的用例即可；切分配置变化会改变全库的标识符和局部上下文，就需要更大范围复查。把触发原因和结论一起记录，之后才能区分「例行维护」和「关于正确性的新判断」。

## 保持小而可信

覆盖率重要，但一个庞大而未评审的集合，不如一个小而 provenance 清晰的集合可信。落地的顺序可以是：

1. 给现有评测数据补齐 `ChunkProvenance`、`CorpusRevision` 和 `Review` 字段；
2. 校验器在编写和加载两处触发，先让含糊用例进不来；
3. 建一小批高决策价值的 sentinel，双人独立评审、记录分歧；
4. 需要扩充时再用合成生成器进评审队列；
5. 把刷新触发器清单写下来，与数据模型一起维护；
6. 每次评测都在结果里带上当时的语料版本。

那些不再代表有效用户需求的用例，也要主动退休。做完这些，评测对话会变得具体：不需要争论一个数字为什么涨跌，而是直接打开背后的记录——查询、预期答案、chunks、来源版本和评审人的决策都摊在桌面上。

Aide Hub 会继续整理 RAG 评测、agent 架构和 .NET 工程实践中可以复用的做法。

## 参考

- [Nick Cosentino：Golden Evaluation Sets for RAG: Synthetic Data, Human Calibration, and Drift](https://www.devleader.ca/2026/09/09/golden-evaluation-sets-for-rag-synthetic-data-human-calibration-and-drift)
- [Yu 等：Evaluation of Retrieval-Augmented Generation: A Survey](https://arxiv.org/abs/2405.07437)
- [Es 等：Ragas: Automated Evaluation of Retrieval Augmented Generation](https://arxiv.org/abs/2309.15217)
- [Gan 等：Retrieval Augmented Generation Evaluation in the Era of Large Language Models: A Comprehensive Survey](https://arxiv.org/abs/2504.14891)
- [Brehme 等：Can LLMs Be Trusted for Evaluating RAG Systems? A Survey of Methods and Datasets](https://arxiv.org/abs/2504.20119)
- [Nick Cosentino：Chunking Strategies for RAG with Semantic Kernel in C#](https://www.devleader.ca/2026/03/16/chunking-strategies-for-rag-with-semantic-kernel-in-c-fixedsize-sentence-and-semantic-chunking)
