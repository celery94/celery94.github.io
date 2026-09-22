---
pubDatetime: 2026-09-22T10:12:00+08:00
title: "RAG 检索授权：租户过滤、溯源与删除"
description: "检索权限必须由服务端从身份推导，而不是接受客户端传来的租户 ID。本文把 RAG 的隔离边界、溯源修订、删除传播与缓存键拆成一组可测试的 .NET 契约，并给出四段可运行示例。"
tags: ["RAG", "访问控制", "多租户", "数据生命周期", ".NET"]
slug: "rag-retrieval-authorization-and-data-lifecycle"
ogImage: "../../assets/1081/01-cover.jpg"
source: "https://www.devleader.ca/2026/09/21/rag-retrieval-authorization-and-data-lifecycle-tenant-filters-provenance-and-deletion"
---

一个能用的 RAG 系统要能找到相关的 chunk。一个可信的 RAG 系统还要多做三件事：在服务端判断调用方有没有资格拿到这些 chunk、记住产出它们的是哪个源修订、以及在源数据或权限变化时把派生数据一起处理掉。

问题在于这三件事的默认行为全都是错的。

浏览器传来的租户 ID 是**待校验的输入**，不是授权证明。删掉一个源文件，不会连带删掉它的 chunk、embedding、索引项和缓存答案。把文档切块再向量化之后，文档上的权限不会自动跟着走。

Nick Cosentino 在 [RAG Retrieval Authorization and Data Lifecycle](https://www.devleader.ca/2026/09/21/rag-retrieval-authorization-and-data-lifecycle-tenant-filters-provenance-and-deletion) 里的判断是：这些属于**检索的职责**，而不是答案生成之后的收尾工作。边界必须落在 prompt 拼装之前。

本号此前梳理过这个问题的另一面——[提示注入与语料投毒](https://celery94.github.io/posts/dotnet-rag-prompt-injection-corpus-poisoning/)关心的是「检索到的东西能不能当指令」；这一篇关心的是「它凭什么到这个调用方手里，以及怎么让它消失」。两篇文章对应 OWASP 同一条备忘单的不同章节。

## 服务端推导作用域，而不是接受它

一次检索请求有两个输入，信任级别完全不同：**问题**由调用方提供，**身份**由认证结果提供。检索作用域必须由服务端从身份和自己的授权规则推导出来。

这和框架无关。下面这段以及后面两段代码都可以直接用 .NET 8 与 C# 12 跑起来，只用 BCL，不需要额外包：

```csharp
using System;
using System.Collections.Immutable;

var identity = new AuthenticatedIdentity(
    SubjectId: "user-42",
    TenantId: "contoso",
    Roles: ImmutableHashSet.Create(StringComparer.Ordinal, "finance-reader"));

var scope = RetrievalScope.From(identity);

Console.WriteLine($"{scope.TenantId}: {string.Join(", ", scope.AllowedClassifications)}");

public sealed record AuthenticatedIdentity(
    string SubjectId,
    string TenantId,
    ImmutableHashSet<string> Roles);

public sealed record RetrievalScope(
    string SubjectId,
    string TenantId,
    ImmutableHashSet<string> AllowedClassifications)
{
    public static RetrievalScope From(AuthenticatedIdentity identity)
    {
        var classifications = identity.Roles.Contains("finance-reader")
            ? ImmutableHashSet.Create(StringComparer.Ordinal, "public", "finance")
            : ImmutableHashSet.Create(StringComparer.Ordinal, "public");

        return new RetrievalScope(
            identity.SubjectId,
            identity.TenantId,
            classifications);
    }
}
```

这段代码的重点不是它做了什么，而是**它没有提供什么**：没有任何方法接受请求 JSON 里的 `tenantId` 并把它变成一个作用域。这个「缺失的 API」才是设计意图——一旦存在这样一个方法，它迟早会被调用。

检索适配器拿着这个作用域，把它翻译成针对具体存储的受限查询：选一个租户专属的存储、在共享存储上做元数据过滤，或者两者都做。领域契约不该隐藏实际走了哪条路，租户、策略版本和生效的分类集合都要跟着请求审计事件一起记下来。

微软的[安全多租户 RAG 架构指南](https://learn.microsoft.com/azure/architecture/ai-ml/guide/secure-multitenant-rag)描述的请求路径是一致的：身份提供方认证用户，编排层取回该租户被授权的 grounding data，只有这份数据会进入模型。它还建议在存储前面加一层 API——理由是让数据访问策略集中在一处，而不是在应用里到处重复。

## 隔离边界要显式选择

RAG 的授权在 silo（每租户独立存储）、pool（共享存储）、hybrid（混合）三种拓扑下工作方式不同。这三个词不表示哪种架构普适正确，它们的价值是让不同的失败边界和运维成本变得可见。

| 拓扑   | 判别方式                                                             | 代价                                       |
| ------ | -------------------------------------------------------------------- | ------------------------------------------ |
| silo   | 存储实例本身就是判别器，边界最强                                     | 更多实例、更多扩容规划、更多索引维护       |
| pool   | 每个 chunk 携带租户与 ACL 元数据，每条检索路径都必须强制作用域       | 资源占用低，但隔离完全依赖应用正确性       |
| hybrid | 共享语料放公共信息、pool 放普通租户内容、silo 放需要强隔离的工作负载 | 复杂度最高，需要按租户模型与数据量逐个判断 |

微软的指南指出，共享存储上的**每一次**检索请求都必须带租户判别器和用户级授权过滤器，并且在把 grounding data 交给模型之前应用这些过滤器。OWASP 的 [RAG Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/RAG_Security_Cheat_Sheet.html) 则要求把访问控制元数据挂在**每一个向量 chunk** 上，而不是只挂在源文档上。

无论选哪种拓扑，有两项检查必须保持独立：

- 用服务端推导出的租户和数据拓扑来**选候选语料库**。
- 在返回检索结果之前**评估生效的文档或 chunk ACL**。

把这两件事合成一件是最常见的实现捷径：只用租户选择语料库，然后假设「同一个租户里的文档权限都一样」。官方指南专门点破了这个假设——用户被映射到某个租户专属存储，**不意味着**他有权访问那个存储里的全部数据。

还有一条边界要守住：**只在应用拿到宽结果之后再过滤是不够的。** 被禁止的文本、相似度分数和元数据已经越过了边界，进入了一个本不需要它们的应用层。OWASP 建议在查询时过滤，并明确警告不要在多租户或多密级环境里只依赖检索后过滤。它给的理由比「性能更好」更硬：预过滤还能避免受限文档的相似度分数被观察到——分数本身就会泄漏信息。

## 每个 chunk 都要带溯源和修订

授权只是元数据血缘的一部分。一个可检索的 chunk 还应该保留源 ID、源 URI 或仓库引用、源修订、内容哈希、摄取时间，以及摄取时生效的策略元数据。

这些字段让运维在结果被用过之后仍然能回答基本问题：这是哪个源产生的？哪个修订？返回的是哪条派生记录？索引这个 chunk 的时候，这个源已经存在了吗？

```csharp
using System;
using System.Security.Cryptography;
using System.Text;

var source = SourceRevision.Create(
    documentId: "handbook-2026",
    revision: "42",
    sourceUri: new Uri("https://docs.example.test/handbook"),
    content: "Expense reports require manager approval.");

Console.WriteLine($"{source.DocumentId}@{source.Revision} {source.Sha256}");

public sealed record SourceRevision(
    string DocumentId,
    string Revision,
    Uri SourceUri,
    string Sha256,
    DateTimeOffset IndexedAt)
{
    public static SourceRevision Create(
        string documentId,
        string revision,
        Uri sourceUri,
        string content)
    {
        var hash = Convert.ToHexString(
            SHA256.HashData(Encoding.UTF8.GetBytes(content)));

        return new SourceRevision(
            documentId,
            revision,
            sourceUri,
            hash,
            DateTimeOffset.UtcNow);
    }
}
```

两个容易做错的地方。

**不要把溯源和「事后生成的、看起来像引用的字符串」混为一谈。** 检索应该返回被选中的 chunk 标识和它存储的溯源，响应层直接展示或序列化这份证据，而不是让模型去编一个引用出来。前一篇讲过的语料投毒问题在这里有个直接推论：如果引用是模型生成的，它就无法作为证据。

**修订是删除和重索引的稳定靶子。** 没有修订字段，删除只能靠「搜索文本」——而文本在抽取过程中可能已经变了。修订还解决了另一类陈旧数据问题：一份文档用新的切块策略或新的 embedding 模型重新索引之后，应用需要能区分旧的派生表示和当前的派生表示。审计可以说清楚当时用的是哪个修订，生命周期处理可以退休被取代的修订，而不是假设名字相似的 chunk 可以互换。

## 权限变更是生命周期事件，不只是删除

源删除只是生命周期事件之一。角色被撤销、文档密级被调整、整个租户被下线，都是同一类事情。

这三种情况下安全的即时行为是一样的：**在查询时推导新的作用域，并在检索时强制执行。** 摄取时的检查抓不到之后发生的策略变化。

OWASP 备忘单明确写了权限可能在摄取之后变化，建议在源权限变化时重新评估已存储 chunk 上的访问控制。它还要求把 embedding 当作敏感派生数据，而不是匿名的数值——embedding 可以通过反转攻击、相似度探测和成员推断泄漏源内容的信息。所以源文本、chunk 元数据、embedding 和检索结果需要共享同一个身份与策略边界。

这一条对中文团队的合规场景尤其值得强调：如果一套脱敏流程的产物是 embedding 并被认为「已经匿名」，那它在监管口径下多半站不住。

## 缓存必须进同一条授权链

响应缓存的纪律和检索是一样的，而它经常被漏掉。

缓存键必须包含影响答案的授权上下文：租户、生效的策略版本、分类集合、源修订水位。**只按归一化后的问题做键，就可能把之前对某个调用方合法的答案，返回给另一个作用域不同的调用方。**

OWASP 因此建议做缓存隔离，并在源被更新、删除或权限变化时失效缓存。实践中这句话要落成一个显式的键结构，例如：

```csharp
// 键里的每一项都是授权上下文，缺一项就可能跨作用域复用答案
var cacheKey = string.Create(CultureInfo.InvariantCulture,
    $"ans|{scope.TenantId}|{policyVersion}|{string.Join(',', scope.AllowedClassifications.Order())}|{revisionWatermark}|{normalizedQuestion}");
```

这里的 `revisionWatermark` 表示「这个租户可见数据的最高修订号」，它让源变更能够触发一次可预期的缓存失效——而这正好是下一节要把删除传播做成工作项的原因。

规则本身只有一句：**性能缓存不能变成一条跳过当前授权的旁路。** 一个缺少匹配策略上下文的缓存条目，应该按未命中处理，而不是当作「调用方有权看到它」的证据。

## 删除传播要是一个显式工作项

删掉源记录不会自动删掉由它派生的一切。OWASP 建议的传播流程分五步：定位源修订、阻止它继续服务新的检索、通过存储适配器删除或标记它的 chunk 与向量、失效受影响的按权限隔离的缓存、记录结果以便跟进。

```csharp
using System;
using System.Collections.Immutable;

var workItem = DeletionWorkItem.Create(
    documentId: "handbook-2026",
    revision: "42",
    reason: "Source removed");

foreach (var target in workItem.Targets)
{
    Console.WriteLine($"{workItem.DocumentId}@{workItem.Revision}: {target}");
}

public enum DeletionTarget
{
    ChunksAndVectors,
    DerivedIndexes,
    PermissionScopedCaches
}

public sealed record DeletionWorkItem(
    Guid Id,
    string DocumentId,
    string Revision,
    string Reason,
    DateTimeOffset RequestedAt,
    ImmutableArray<DeletionTarget> Targets)
{
    public static DeletionWorkItem Create(
        string documentId,
        string revision,
        string reason)
    {
        return new DeletionWorkItem(
            Guid.NewGuid(),
            documentId,
            revision,
            reason,
            DateTimeOffset.UtcNow,
            ImmutableArray.Create(
                DeletionTarget.ChunksAndVectors,
                DeletionTarget.DerivedIndexes,
                DeletionTarget.PermissionScopedCaches));
    }
}
```

这段代码不删除任何东西，它的价值是**契约**：每个适配器针对同一个 document + revision 身份汇报自己删掉了什么。某个适配器失败时，这条事件保持可见，源数据不会被悄悄假设「已经在所有派生系统里都不存在了」。

还有一件事必须在契约里写清楚：**备份、不可变审计记录、受保留期管理的遥测和在线检索工件有不同的处理规则。** 把它们分开列出，而不是给出一句笼统的「已删除」。这是合规场景里最容易被含糊过去的地方——一份源文档的 chunk 删了，不代表合规要求的删除日志也删了，也不代表备份磁带里的副本被处理了；反过来说，审计记录本来就应该按法律保留要求单独对待。

## 审计要审决策，不是审答案

一条有用的审计事件要把这些串起来：认证主体、租户、生效作用域、策略版本、查询标识、被选中的 chunk ID、源修订、缓存命中情况，以及删除状态。

同时要避免把审计日志变成源文本和 prompt 的无控副本。一条查不出检索到哪个修订的追踪太弱；一条无限期复制敏感内容的追踪则制造了第二个生命周期问题。

按这个标准，一条审计事件应该能回答：

- 生效的是哪个服务端推导出的作用域？
- 查的是哪个存储、集合或隔离路径？
- 返回了哪个 chunk 和哪个源修订？
- 是哪条策略决策放行了每一条结果？
- 用没用缓存，在什么作用域下用的？
- 针对这个修订的删除或去权限工作项完成了吗？

OWASP 备忘单要求记录检索到的 chunk 及其身份与访问控制元数据、缓存活动和删除验证；微软的指南同样建议通过 API 层记录 grounding 信息的访问日志。有了这些记录，跨租户检索测试或陈旧权限事故才是可诊断的——而不用假装是模型自己执行了授权。

## 在检索边界测生命周期

只测「索引收到过一个 chunk」是不够的。真正重要的测试从服务端推导的作用域出发，验证检索边界上的可观察行为。

OWASP 的最低部署测试用例里包含跨租户检索、陈旧权限、缓存泄漏和数据删除验证。做一个隔离的测试语料库，至少包含两个租户、两个密级和一个文档修订：

1. 验证租户 A 的作用域永远拿不到租户 B 的 chunk。
2. 撤销一个角色，验证后续检索不再返回受保护的 chunk。
3. 删除或去除某个源修订的权限，运行删除工作项，验证它的 chunk、向量和按权限隔离的缓存条目都不再合格。
4. 让一份文档用新的切块策略重新索引，验证审计能区分新旧修订。

失败行为同样要测，而且这部分比正常路径更容易被忽略：

- **策略服务拿不到作用域时，检索适配器不能放宽查询。** 这是 OWASP 单列的 fail-closed 原则：管道里的每一段在失败时都应该关上，而不是打开。
- **删除适配器失败时要记录失败，并让工作项保持可操作**，而不是标记完成。
- **缓存条目缺少匹配的策略上下文时按未命中处理**，而不是当作调用方有权查看的证据。

这些测试把 RAG 授权与生命周期收敛到应用能观察到的事实上：一条结果在当前作用域下要么合格要么不合格；一个修订要么仍可检索要么不可。它们不需要产品基准，不需要客户端提供的过滤器，也不需要「某个向量库的删除会级联」这种假设。

## 从哪一步开始

OWASP 备忘单把控制项按实施优先级分了层，我觉得这个分法比按章节顺序做更实用：

**立刻做（基础项）**：摄取时的文档哈希与完整性校验、把访问控制元数据挂在每一个向量 chunk 上、向量存储里的租户与密级隔离、查询时的规范化与滥用检测、输出校验、全链路可观测性、以及 fail-closed 行为。

**接着做（合规与审计）**：每次响应带签名溯源、向量索引的完整性监控与访问控制、缓存隔离与失效、以及针对合规的数据删除与保留控制。

**最后做（高安全与受监管环境）**：embedding 分布监控与跨模型校验、以及面向 embedding 隐私的差分隐私类措施。

对应到 .NET 工程上，最小可交付的一组契约是：一个只能由 `AuthenticatedIdentity` 构造的 `RetrievalScope`、一个携带 `SourceRevision` 的 chunk 记录、一个把删除目标列清楚的 `DeletionWorkItem`、一个把授权上下文写进键的缓存、以及一份能回答上面六个问题的审计事件。这四个结构加起来不到两百行，但它们决定了后面所有事情能不能被测试。

Aide Hub 会继续整理这类把安全要求落成可执行契约的实践，覆盖 .NET、AI 助手与软件工程。

## 参考

- [RAG Retrieval Authorization and Data Lifecycle: Tenant Filters, Provenance, and Deletion](https://www.devleader.ca/2026/09/21/rag-retrieval-authorization-and-data-lifecycle-tenant-filters-provenance-and-deletion)（原文，Nick Cosentino）
- [OWASP RAG Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/RAG_Security_Cheat_Sheet.html)
- [Design a secure multitenant RAG inferencing solution（Azure Architecture Center）](https://learn.microsoft.com/azure/architecture/ai-ml/guide/secure-multitenant-rag)
- [RAG 安全：提示注入与语料投毒的 .NET 防线（本站）](https://celery94.github.io/posts/dotnet-rag-prompt-injection-corpus-poisoning/)
