---
pubDatetime: 2026-09-07T07:50:38+08:00
title: "RAG 评估指标：先测检索，再测答案"
description: "把 RAG 评估拆成检索与答案两层：用可运行的 C# 实现 Precision@K、Recall@K、MRR、nDCG 与 groundedness、答案相关性，说明指标怎么解读、LLM 评判器的边界和离线评估组织，避免用总分掩盖问题。"
tags: ["RAG", ".NET", "AI Evaluation", "Information Retrieval"]
slug: "rag-evaluation-metrics-dotnet"
ogImage: "../../assets/1053/01-cover.jpg"
source: "https://www.devleader.ca/2026/09/05/rag-evaluation-metrics-in-net-measure-retrieval-and-grounding"
---

RAG 应用上线前，你做了一次人工抽查：回答流畅、语气自信，引用也挂着。换几个问题，它要么答非所问，要么把上下文包装成了原文没有的结论。别人问「到底有没有问题」，你手上只有几个截图和一句感觉还行。

问题出在评估被压成了一个总分。Nick Cosentino 在 [RAG Evaluation Metrics in .NET](https://www.devleader.ca/2026/09/05/rag-evaluation-metrics-in-net-measure-retrieval-and-grounding) 里给出一个更实用的做法：**把 RAG 拆成检索层和答案层分别测量，再把结果放在一起解读**。这样「哪个环节坏了」才有答案，而不是只得到一个「整体好像不太行」。

本文按这个思路整理成一次可以照做的离线评估，包含三个只用 .NET 基础类库（BCL）的完整程序，已在 .NET 10.0.301 SDK 下编译运行验证。不涉及评估数据如何构造、生产环境埋点、安全测试和评测包选型——这些是独立话题。

## 先分清：检索层指标和答案层指标

检索是一个排序问题。对一条 query，检索器返回 chunks 的排列顺序，评估就是把这个顺序和相关性判定比较。答案是「答案 + 上下文」问题：**groundedness** 检查答案中的事实性主张是否被当初提供给生成器的检索上下文支持；**答案相关性**（answer relevance）检查回答是否正面回应了用户的问题。[RAG evaluation research](https://arxiv.org/abs/2405.07437) 把检索和生成当作独立组件，两个指标不能互相替代，也无法修复对方的失败。

分层看问题的方式，在应用表现异常时最有用：

| 现象                          | 说明                                                       |
| ----------------------------- | ---------------------------------------------------------- |
| Recall@K 低                   | 必要证据没有进入提示词，改 prompt 也无法让不存在的证据出现 |
| Precision@K 低                | 上下文里无关材料太多，模型要处理的噪声变多                 |
| 检索强但 groundedness 低      | 答案在提供的上下文之外添加或扭曲了主张                     |
| groundedness 高但答案相关性低 | 回答有依据，但避开了问题                                   |

这与「语义搜索返回的相似度分数」不同。向量库特有的相似度分数只在该库内排序时有用，它既不是相关性判定，也不证明答案有依据。评估契约与具体向量库无关，因此下文所有计算均不依赖任何 RAG 或向量检索包。

## 检索层：Precision@K、Recall@K、MRR、nDCG

四个指标描述排序列表的不同性质，先看定义和手算例子：

- **Precision@K**：前 K 个结果里相关项数量除以 K。回答「在上下文预算里有多少是可用的」。前 5 位有 3 个相关 chunk，Precision@5 = 0.6。
- **Recall@K**：前 K 个结果里相关项数量除以该 query 的全部判定相关项数量。回答「检索器找回了多少可用的证据」。某 query 有 4 个判定相关 chunk，前 5 个结果命中 3 个，Recall@5 = 0.75。
- **MRR**（mean reciprocal rank）：只关心第一个相关结果。单条 query 的 reciprocal rank 是该结果的 1/rank，MRR 为所有 query 的平均。适合「读者想快速找到一条权威段落」的场景；它对剩余相关段落几乎不提供信息，不能代替 recall。
- **nDCG**（normalized discounted cumulative gain）：使用分级相关，并对靠后的结果打折。高有用性 chunk 排在靠前比排在靠后更值钱，再用理想排序归一化，使不同判定分布的 query 之间可比。

实现时把 cutoff 写在指标名旁边。从 Precision@5 换到 Precision@10，即使检索系统没变，回答的问题也已经变了。

下面的程序从唯一的排序列表和 chunk-ID 到分级的判定映射计算全部四个指标，只依赖 BCL。前置条件：.NET 7 或更高版本的 SDK（`Enumerable.OrderDescending` 从 .NET 7 起可用），并支持文件作用域命名空间与 record（C# 10 起）。原文在 .NET 7 与 C# 10 下验证，代码放在更高版本 SDK 中同样编译运行。创建控制台项目后粘贴运行即可：

```csharp
using System;
using System.Collections.Generic;
using System.Linq;

namespace RetrievalMetrics;

public sealed record JudgedRanking(
    IReadOnlyList<string> ChunkIds,
    IReadOnlyDictionary<string, int> GradesByChunkId);

public static class Program
{
    public static void Main()
    {
        var ranking = new List<string>
        {
            "chunk-7",
            "chunk-3",
            "chunk-9",
            "chunk-1",
            "chunk-5",
        };

        var gradesByChunkId = new Dictionary<string, int>
        {
            ["chunk-1"] = 0,
            ["chunk-3"] = 3,
            ["chunk-5"] = 2,
            ["chunk-7"] = 0,
            ["chunk-9"] = 1,
        };
        var rankings = new List<JudgedRanking>
        {
            new(ranking, gradesByChunkId),
        };

        Console.WriteLine($"Precision@3: {Metrics.PrecisionAtK(ranking, gradesByChunkId, 3):F3}");
        Console.WriteLine($"Recall@3: {Metrics.RecallAtK(ranking, gradesByChunkId, 3):F3}");
        Console.WriteLine($"MRR: {Metrics.MeanReciprocalRank(rankings):F3}");
        Console.WriteLine($"nDCG@3: {Metrics.NdcgAtK(ranking, gradesByChunkId, 3):F3}");
    }
}

public static class Metrics
{
    public static double PrecisionAtK(
        IReadOnlyList<string> ranking,
        IReadOnlyDictionary<string, int> gradesByChunkId,
        int k)
    {
        ValidateInputs(ranking, gradesByChunkId, k);

        return ranking.Take(k).Count(id => gradesByChunkId[id] > 0) / (double)k;
    }

    public static double RecallAtK(
        IReadOnlyList<string> ranking,
        IReadOnlyDictionary<string, int> gradesByChunkId,
        int k)
    {
        ValidateInputs(ranking, gradesByChunkId, k);

        var relevantCount = gradesByChunkId.Values.Count(grade => grade > 0);
        if (relevantCount == 0)
        {
            return 0;
        }

        return ranking.Take(k).Count(id => gradesByChunkId[id] > 0)
            / (double)relevantCount;
    }

    public static double MeanReciprocalRank(
        IReadOnlyList<JudgedRanking> rankings)
    {
        if (rankings.Count == 0)
        {
            return 0;
        }

        return rankings.Average(ranking =>
        {
            ValidateInputs(ranking.ChunkIds, ranking.GradesByChunkId, 1);
            var firstRelevant = ranking.ChunkIds
                .Select((id, index) => (id, index))
                .FirstOrDefault(item => ranking.GradesByChunkId[item.id] > 0);

            return firstRelevant.id is null
                ? 0
                : 1d / (firstRelevant.index + 1);
        });
    }

    public static double NdcgAtK(
        IReadOnlyList<string> ranking,
        IReadOnlyDictionary<string, int> gradesByChunkId,
        int k)
    {
        ValidateInputs(ranking, gradesByChunkId, k);

        var actual = DiscountedCumulativeGain(ranking.Take(k).Select(id => gradesByChunkId[id]));
        var ideal = DiscountedCumulativeGain(gradesByChunkId.Values.OrderDescending().Take(k));

        return ideal == 0 ? 0 : actual / ideal;
    }

    private static void ValidateInputs(
        IReadOnlyList<string> ranking,
        IReadOnlyDictionary<string, int> gradesByChunkId,
        int k)
    {
        if (k <= 0)
        {
            throw new ArgumentOutOfRangeException(nameof(k), "K must be positive.");
        }

        if (ranking.Count != ranking.Distinct(StringComparer.Ordinal).Count())
        {
            throw new ArgumentException("A ranking must not contain duplicate chunk IDs.", nameof(ranking));
        }

        if (gradesByChunkId.Values.Any(grade => grade < 0))
        {
            throw new ArgumentException("Relevance grades must be non-negative.", nameof(gradesByChunkId));
        }

        if (ranking.Any(id => string.IsNullOrWhiteSpace(id) || !gradesByChunkId.ContainsKey(id)))
        {
            throw new ArgumentException(
                "Every ranking entry must have a stable ID and a corresponding relevance grade.",
                nameof(ranking));
        }
    }

    private static double DiscountedCumulativeGain(IEnumerable<int> grades)
    {
        return grades.Select((grade, index) =>
            (Math.Pow(2, grade) - 1) / Math.Log2(index + 2)).Sum();
    }
}
```

运行结果：

```text
Precision@3: 0.667
Recall@3: 0.667
MRR: 0.500
nDCG@3: 0.523
```

可以手算核对：前 3 位是 chunk-7（0）、chunk-3（3）、chunk-9（1），两个为正 → Precision@3 = 2/3；全部判定相关共 3 个 → Recall@3 同样是 2/3；第一个相关项在第 2 位 → MRR = 1/2；DCG 用 (2^grade − 1) / log2(index + 2) 计算，再除以理想排序的 DCG 得到 nDCG@3。

注意两个实现细节：

- **0 视为不相关，正数视为相关**，只对 Precision@K、Recall@K、MRR 生效；nDCG 保留完整分级。这样「略有用」和「非常有用」仍可区分，又不假装每个指标回答同一个问题。
- **校验放进公共入口**：k 必须为正、chunk ID 不允许重复、分级不允许为负、每个排序项都要有对应分级，理想列表从同一张判定映射推导。因为相关性是输入数据，而不是评分时推断出来的，输出是确定的。

单独看某个指标的涨跌很容易误判，下面说怎么组合使用。

## 指标组合使用，不找单一赢家

没有哪个检索指标能宣布「这个检索器全局更好」，每个指标只是让一种取舍显性化。例如一个配置可能把 Recall@10 提上去，同时 Precision@5 掉下来。这本身不是回归也不是改进，只说明候选集合变了。接下来该问的是：在同一个上下文预算下，生成层是否真的从这些额外证据中获益。

[RAG evaluation survey](https://arxiv.org/abs/2405.07437) 提醒，传统信息检索指标未必预测端到端的答案质量：一个 chunk 可能主题相关，却恰好缺少回答问题所需的细节；而排名靠后的段落里也许藏着决定性约束。**检索分数应该当作诊断信号，而不是「答案正确」的证明。** 这条边界在做文档问答时尤其重要——检索到答案路径的搭建可以参考 [document Q&A RAG example](https://www.devleader.ca/2026/03/17/build-a-document-qa-app-with-rag-and-semantic-kernel-in-c)，本文不做检索器、模型或框架的推荐。

## 答案层：groundedness 和答案相关性

**Groundedness** 是主张支持度检查：把答案拆成事实性 claim，逐条问「这条是否被提供给生成器的检索上下文支持」。一个答案在现实世界里可能完全合理，但在这个测量里依然不 grounded——因为它超出了系统被允许依赖的证据边界。**答案相关性** 是问答契合度检查：回答是否正面处理了用户的问题。

两种失败可以互相独立：一个 grounded 的答案可能因为准确概括了无关 chunk 而答非所问；一个正面回答的答案可能因为编造细节而不 grounded。所以这两个值应该和检索表并排展示，而不是混进检索指标里。

下面的程序把结果保存在独立记录里。它不调用任何 LLM，每条 claim 的支持判定和是否切题由评审人员或单独校准过的评估器提供，程序只负责计算和报告：

```csharp
using System;
using System.Collections.Generic;
using System.Linq;

namespace AnswerMeasurements;

public sealed record ClaimAssessment(string Claim, bool IsSupportedByRetrievedContext);

public sealed record AnswerAssessment(
    string QueryId,
    IReadOnlyList<ClaimAssessment> Claims,
    bool AddressesQuestion)
{
    public double Groundedness =>
        Claims.Count == 0
            ? 0
            : Claims.Count(claim => claim.IsSupportedByRetrievedContext)
                / (double)Claims.Count;

    public double AnswerRelevance => AddressesQuestion ? 1 : 0;
}

public static class Program
{
    public static void Main()
    {
        var assessment = new AnswerAssessment(
            "policy-42",
            new List<ClaimAssessment>
            {
                new("The policy expires at the end of the calendar year.", true),
                new("The policy applies to contractors.", false),
            },
            AddressesQuestion: true);

        Console.WriteLine($"Groundedness: {assessment.Groundedness:F3}");
        Console.WriteLine($"Answer relevance: {assessment.AnswerRelevance:F3}");
    }
}
```

运行结果：

```text
Groundedness: 0.500
Answer relevance: 1.000
```

两条 claim 中一条有依据、一条没有，groundedness 为 0.5；回答确实切题，答案相关性为 1，两个失败维度被区分开。二元标签最直观，团队也可以换成有序量表——前提是先用书面 rubric 定义每个分值代表什么。不要过早把多个维度合成综合分。真正有价值的输出不是漂亮的数字，而是知道**不支持的 claim、答非所问、还是检索缺证据**，是哪一类在产生问题。

## LLM 评判器：易错的测量仪器

LLM 可以在拿到答案和检索上下文之后评估「是否支持」和「是否切题」，这能加快反复的离线比较，尤其是每次都给它相同的 rubric 和输入形状。但这不会让分数变成客观事实。

[Can LLMs Be Trusted for Evaluating RAG Systems?](https://arxiv.org/abs/2504.20119) 调研了自动评估与人工评估及各自局限，已知风险包括：评判器偏爱更长的答案、偏好输入中给出的顺序、与生成答案的模型共享盲点；当上下文不完整、rubric 没有定义「合理推断」与「无依据编造」的边界时，也会被误导。因此评判器分数是**一个配置好的流程产生的观察值**，它的 rubric 和输入本身就是测量的一部分。

给 LLM 评判器一个克制的角色：

1. 传入被评分层对应的原始 query、答案和检索上下文，不传推理过程。
2. 问窄定义的问题，例如「这条 claim 是否被这段上下文支持」，而不是「这个答案好不好」。
3. 把 rubric、评判器身份和原始判定与结果一起保存，后续运行才可比。
4. 依赖分数做重要决策前，抽样与人工评审对照。

这不是对某个具体包或托管评估服务的推荐。评估器在应用里可以先保持为一个接口，直到某个实现经过独立验证。目标是避免把「方便的打分」变成「系统没有问题」的结论。

## 组织一次离线评估

一次离线运行要能在同一组输入上比较两个配置，同时不掩盖层次：取一套现成的 query 判定，执行一个具名配置，针对一个语料版本检索并打分，再单独记录答案层测量。相同的 query ID、判定、语料版本、配置身份和打分规则必须贯穿每个候选配置——否则这次评估就退化成一次凭感觉的提示词测试。

下面的程序只建模聚合边界：接收已经算好的逐 query 指标，输出分离的检索与答案汇总。真实 runner 可以从任何 provider 填充这些记录，只要保留相同的标识与评估规则：

```csharp
using System;
using System.Collections.Generic;
using System.Linq;

namespace OfflineEvaluationRun;

public sealed record QueryResult(
    string QueryId,
    double PrecisionAt5,
    double RecallAt5,
    double ReciprocalRank,
    double NdcgAt5,
    double Groundedness,
    double AnswerRelevance);

public sealed record EvaluationSummary(
    double MeanPrecisionAt5,
    double MeanRecallAt5,
    double MeanReciprocalRank,
    double MeanNdcgAt5,
    double MeanGroundedness,
    double MeanAnswerRelevance);

public static class Program
{
    public static void Main()
    {
        var results = new List<QueryResult>
        {
            new("q-1", 0.80, 0.67, 1.00, 0.92, 1.00, 1.00),
            new("q-2", 0.40, 0.50, 0.50, 0.61, 0.50, 1.00),
        };

        var summary = Summarize(results);
        Console.WriteLine(summary);
    }

    public static EvaluationSummary Summarize(IReadOnlyList<QueryResult> results)
    {
        if (results.Count == 0)
        {
            throw new ArgumentException("At least one query result is required.", nameof(results));
        }

        return new EvaluationSummary(
            results.Average(result => result.PrecisionAt5),
            results.Average(result => result.RecallAt5),
            results.Average(result => result.ReciprocalRank),
            results.Average(result => result.NdcgAt5),
            results.Average(result => result.Groundedness),
            results.Average(result => result.AnswerRelevance));
    }
}
```

在示例之外把配置名和语料版本记下来，并跟随每条结果保存。否则一次指标变化无法归因：是 embedding 换了、检索逻辑换了、语料更新了、提示词改了，还是评判器换了？分层记录让差异可以被解释。

离线打分与生产环境的运行观测是两回事：指标先指出可疑点，后续追踪和遥测是另一种工程。

## 结果怎么读

先看检索表，再在旁边对照 groundedness 和答案相关性。不要因为某一个平均值变高就宣布成功，用组合模式定位问题：

| 观察到的变化                    | 优先排查方向                     |
| ------------------------------- | -------------------------------- |
| Recall@K 下降                   | 相关 chunk 是否根本没有被召回    |
| nDCG 下降但 Recall 保持         | 高价值 chunk 是否被排到了后面    |
| 检索平稳但 groundedness 下降    | 答案在使用同一份上下文时如何扩展 |
| groundedness 高但答案相关性下降 | 问题理解或回答指令是否正确       |

每个模式都指向不同的调查方向：召回缺失查检索配置，排序下降查打分与重排，主张超出上下文查生成契约，答非所问查问题解析与提示词。

## 常见问题

**Precision@K 和 Recall@K 在 RAG 中有什么区别？** Precision@K 衡量前 K 个上下文中有多少相关；Recall@K 衡量判定相关的证据有多少出现在结果里。上下文精简时精度可能很高，但可能漏掉必要证据，所以两个都要看。

**什么时候用 MRR 而不是 nDCG？** 只关心第一个相关结果时用 MRR；多个结果用途不同、排序本身重要时用 nDCG。它们回答不同的排序问题，不是竞争同一个通用分数。

**检索指标高能证明答案正确吗？** 不能。检索指标描述的是排序后的证据列表，不描述生成器如何使用它。答案是否正确要看 groundedness（是否有据）和答案相关性（是否切题）。

**应该只用 LLM 评判器来评估吗？** 不应该单独依赖。评判器提供可重复的自动观察，但其决策可能受提示词、位置、冗长度和模型家族偏好的影响。把 rubric 和评判配置显式保存，并在后果关键处与人工评审对照。

## 从 20 条真实问题开始

如果只想做一个最小可行的版本：挑 20–50 条真实用户问题，人工标注每条 query 的相关 chunk（可以只用 0 和 3 两级起步），让检索器返回排序，用第一段程序跑四个检索指标；再抽查回答，逐条判断 claims 是否有据、是否切题。之后每次改配置，都复用同一套 query 判定和语料版本，输出就变成一张「检索层和答案层分别变化」的报告，而不是无法解释的数字波动。

代码刻意保持朴素 C#，因为它展示的是确定性数学与评估判断的边界。这个边界比任何封装包的便捷 API 更持久，也让你在下一个实验里更诚实：这个分数到底说明了什么。

Aide Hub 会继续分享 AI 助手、开发工具与软件工程实践中的具体做法。

## 参考

- [Dev Leader：RAG Evaluation Metrics in .NET: Measure Retrieval and Grounding](https://www.devleader.ca/2026/09/05/rag-evaluation-metrics-in-net-measure-retrieval-and-grounding)
- [Evaluation of Retrieval-Augmented Generation: A Survey (arXiv:2405.07437)](https://arxiv.org/abs/2405.07437)
- [Can LLMs Be Trusted for Evaluating RAG Systems? A Survey of Methods and Datasets (arXiv:2504.20119)](https://arxiv.org/abs/2504.20119)
- [Introduction to Information Retrieval：Evaluation of ranked retrieval results](https://nlp.stanford.edu/IR-book/html/htmledition/evaluation-of-ranked-retrieval-results-1.html)
- [TREC-8 Question Answering Track Report](https://trec.nist.gov/pubs/trec8/papers/qa_report.pdf)
- [Microsoft Learn：Enumerable.OrderDescending](https://learn.microsoft.com/en-us/dotnet/api/system.linq.enumerable.orderdescending)
- [Dev Leader：Build a document Q&A app with RAG and Semantic Kernel in C#](https://www.devleader.ca/2026/03/17/build-a-document-qa-app-with-rag-and-semantic-kernel-in-c)
