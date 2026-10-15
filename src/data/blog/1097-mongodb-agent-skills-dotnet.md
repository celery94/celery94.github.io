---
pubDatetime: 2026-10-15T12:50:00+08:00
title: "MongoDB Agent Skills：8 个技能与安装变更"
description: "AI agent 常把关系型设计翻译成 MongoDB 语法。MongoDB 官方 Agent Skills 已增至 8 个，用按需加载补齐文档建模、索引与检索，本文给出当前安装方式与 .NET 取舍边界。"
tags: ["MongoDB", "AI Agent", "Claude Code", "MCP", ".NET"]
slug: "mongodb-agent-skills-dotnet"
ogImage: "../../assets/1097/01-cover.jpg"
source: "https://codewithmukesh.com/blog/mongodb-agent-skills-dotnet/"
---

让 Claude Code 给你的 ASP.NET Core 项目设计一套 MongoDB schema，它几乎总能交出能跑的东西：`Orders`、`Customers`、`OrderItems` 三个集合，再配一个 `$lookup` 在订单列表页把它们拼回去。

看起来没问题，因为看起来眼熟。这其实是一张 SQL Server 的表设计，只是换成了 MongoDB 的语法。

MongoDB 官方把这归结为训练数据的问题。当模型见过的「MongoDB 最佳实践」大多本身就是从关系型直接翻译过来的，它学到的就是这种翻译习惯。官方在 2026 年 3 月 31 日的发布说明里点名了三个具体后果：**schema 过度范式化、复合索引使用不足、索引与检索索引用法不当。**这些错误在开发阶段看不出问题，直到数据量上来才暴露，而那时改 schema 的代价最大。

[MongoDB Agent Skills](https://github.com/mongodb/agent-skills) 就是针对这个问题的官方技能包，Apache-2.0 协议开源。下面是我核对官方仓库和文档后的整理，其中有两处已经和原文写的不一样了。

## Agent Skills 靠什么省上下文

一个 Agent Skill 就是一个文件夹，里面有一个 `SKILL.md`：YAML frontmatter 写 `name` 和 `description`，下面是 Markdown 指令。旁边可以放可选的 `references/`、`scripts/` 和 `assets/`。

这个格式由 Anthropic 提出，现在[已经是一个开放规范](https://agentskills.io/)，Claude Code、Cursor、Codex、GitHub Copilot、VS Code、Gemini CLI 等都能读同一份文件夹。

它和 `CLAUDE.md` 的关键区别在加载时机：

- **发现（Discovery）**：会话启动时，agent 只读每个技能的 `name` 和 `description`。这部分常驻上下文。
- **激活（Activation）**：当你的任务匹配某个描述时，才读取完整的 `SKILL.md`。
- **执行（Execution）**：实现阶段需要更多细节时，才按需拉取 `references/` 里的文件。

`CLAUDE.md` 是反过来工作的——它的全文进入这个仓库里的**每一轮对话**，包括那些和 MongoDB 毫无关系的对话。技能则是「不用不花钱」。

原文作者实测，闲置状态下只有每个技能的 `name` 和 `description` 常驻，加起来 4,204 个字符、约 1,050 token；原文同时给出的全量体积是约 366KB。这个比例关系比具体数字更重要：我核对当前仓库时，`skills/` 下所有内容（不含 `OWNERS.yaml`）已经涨到约 39 万字符，而常驻的那部分基本没变。**你永远不会一次性加载全量内容，只会拿到当前任务需要的那一份。**

这也是为什么把 MongoDB 最佳实践直接粘进 `CLAUDE.md` 得不到同样效果：那等于让每一轮对话都付费。

## Skills 和 MCP 不是一回事

这两个概念经常被混在一起，但分工很清晰：

- **MCP** 给 agent **工具**——`find`、`explain`、`collection-indexes` 这类可以对着真实数据库调用的操作。
- **Agent Skill** 给 agent **流程和判断**——该按什么顺序调用哪些工具，以及怎么解读返回结果。

`mongodb-query-optimizer` 是两者配合的典型例子。它规定的步骤是一条链：

1. 调 `collection-indexes`，看这个集合上已经有哪些索引；
2. 用 `queryPlanner` 模式跑 `explain`，检查是否出现 COLLSCAN（全集合扫描）；
3. 如果查询走了索引，或者集合本身很小，再用 `executionStats` 跑一次 `explain`，对比「扫描的文档数」和「返回的文档数」——这一步在技能文档里是有条件的，不是无脑跑；
4. 用 `find` 拉一条样本文档，确认字段实际形态。

技能本身不会执行这些动作，它只是让 agent 知道该这么走。真要连上数据库，还是得配 MCP。

## 技能清单：现在是 8 个

原文说这批技能是 7 个。这个数字其实不算错——只是要看你说的是哪个插件。我核对仓库时，`skills/` 目录下有 8 个技能，`skills/OWNERS.yaml` 里也是 8 条记录。两个插件的差别在打包范围：

- **`mongodb`（自管）**打包全部 8 个；
- **`mongodb-atlas`（托管）**排除了 `mongodb-mcp-setup`，只有 7 个。

排除是有道理的：托管 MCP 走 OAuth 登录，不需要本地的配置引导技能。所以「7 个」是 Atlas 插件的数量，仓库本身的技能数是 8。

| 技能                                | 负责什么                                            | 参考文件数 |
| ----------------------------------- | --------------------------------------------------- | ---------- |
| `mongodb-schema-design`             | 文档建模、嵌入与引用取舍、11 个命名模式、3 个反模式 | 20         |
| `mongodb-search-and-ai`             | Atlas Search、Vector Search、混合检索、RAG 召回     | 5          |
| `mongodb-atlas-stream-processing`   | Kafka、S3、Lambda、HTTPS sink 的流处理管道          | 6          |
| `mongodb-connection`                | 连接池大小、超时、客户端生命周期、连接排错          | 1          |
| `mongodb-query-optimizer`           | `explain()` 分析、索引选择、Performance Advisor     | 4          |
| `mongodb-natural-language-querying` | 从自然语言生成只读的 find 与聚合                    | 0          |
| `mongodb-mcp-setup`                 | MCP server 配置引导                                 | 0          |
| `mongodb-qe-size-estimation`        | Queryable Encryption 的存储与内存开销估算           | 0          |

第八个 `mongodb-qe-size-estimation` 是原文没覆盖的，也是最新加入的一个——`OWNERS.yaml` 里其余技能的最后评审日期都落在 2026 年 3 到 5 月，它是 2026-09-25。它做的事很具体：算出给某个集合启用 Queryable Encryption 之后，磁盘占用和内存需求会涨多少。它内置了几条硬规则，比如**绝不接受样本数据**——QE 本身就是用来保护敏感字段的，索要样本等于自己制造泄露路径；它只接受加密 schema，或者由你逐个字段回答 BSON 类型和查询类型。

它还留了一个诚实的缺口：范围查询（range）目前没有计算公式，所以这类字段的开销按 0 记录并在结论里单独提示。另外 prefix、suffix、substring 查询需要 MongoDB 9.0，早期版本不支持。如果你手上是带身份证号、手机号之类字段的 .NET 服务，这个技能回答的是「加密之后我要多买多少存储」这种没人愿意拍脑袋估算的问题。

`mongodb-schema-design` 仍然是内容最厚的那个，20 个参考文件。它把 MongoDB 的基本原则——**一起访问的数据应该存在一起**——落成一张可以直接查的决策表：

| 关系   | 基数            | 访问模式     | 建议     |
| ------ | --------------- | ------------ | -------- |
| 一对一 | 1:1             | 总是同时读取 | 嵌入     |
| 一对少 | 1:N，N 小于 100 | 通常同时读取 | 嵌入数组 |
| 一对多 | 1:N，N 大于 100 | 通常分开读取 | 引用     |
| 多对多 | M:N             | 视情况       | 双向引用 |

它的另一条规则更值得注意：**在没有理解更大上下文之前，不要建议更换模式或 schema。**所以它会先反过来问你——这是新项目还是生产库？读写比例偏哪边？拿到答案才给方案。如果你不回答，它只能给你教科书答案。

下面这个 C# 类就是它按「扩展引用」（extended reference）模式生成的：

```csharp
public sealed class Order
{
    [BsonId]
    [BsonRepresentation(BsonType.ObjectId)]
    public string? Id { get; set; }

    // 扩展引用：客户有独立集合，
    // 但订单页每处都用到的那两个字段复制一份在这里。
    public CustomerRef Customer { get; set; } = null!;

    // 每单行数不多，且总是随订单一起读，所以嵌入。
    public List<OrderLine> Lines { get; set; } = [];

    public decimal Total { get; set; }
    public DateTime PlacedAtUtc { get; set; }
}

public sealed record CustomerRef(string CustomerId, string DisplayName);

public sealed record OrderLine(string Sku, string Name, int Quantity, decimal UnitPrice);
```

这个模型的要点在注释里：下订单只需要一次读取，没有 `$lookup`。客户的完整数据仍然留在自己的集合里，被复制过来的只有订单页真正要显示的那两个字段。

## 安装命令已经和原文不一样了

这是最容易踩坑的地方。原文给的 Claude Code 命令是 `/plugin install mongodb@claude-plugins-official`，并说 `mongodb-atlas` 的 marketplace 页面当时返回 404。

现在官方 [README](https://github.com/mongodb/agent-skills) 给的是另一套，两个变体分别对应自管和托管：

- **`mongodb`**：本地跑 MCP server，连你自己的连接字符串。Community、Enterprise Advanced、本地容器、Atlas 都走这条。
- **`mongodb-atlas`**：连 MongoDB 托管的 MCP server，走 OAuth 登录 `https://mcp.mongodb.com/`。

| 客户端             | 自管（`mongodb`）                                                   | 托管 Atlas（`mongodb-atlas`）          |
| ------------------ | ------------------------------------------------------------------- | -------------------------------------- |
| Claude Code        | `/plugin install mongodb`                                           | `/plugin install mongodb-atlas`        |
| Cursor             | `/add-plugin mongodb`                                               | `/add-plugin mongodb-atlas`            |
| Codex              | `codex plugin marketplace add mongodb/agent-skills`，再 `/plugins`  | `/plugins` 里选 `mongodb-atlas`        |
| GitHub Copilot CLI | `/plugin install https://github.com/mongodb/agent-skills.git`       | `copilot plugin install mongodb-atlas` |
| VS Code            | 扩展视图搜 `@agentPlugins`                                          | 同左                                   |
| Gemini CLI         | `gemini extensions install https://github.com/mongodb/agent-skills` | —                                      |
| Grok               | `/marketplace`                                                      | `/marketplace`                         |

Claude Code 里装完之后要跑 `/reload-plugins` 或重启会话，技能才会被发现——技能是在会话启动时扫描的，中途装的插件不一定立刻生效。

如果你只想拿技能、不配 MCP：

```bash
# 走 Vercel 的 Agent Skills 目录
npx skills add mongodb/agent-skills

# 或者直接克隆仓库，把 skills/ 复制到你的 agent 读取技能的位置
git clone https://github.com/mongodb/agent-skills.git
```

这种情况下要补一条 MCP 配置，`npx "mongodb-mcp-server@latest" setup` 会引导你选托管 Atlas MCP 还是自管部署。

## 提示词怎么写才会触发正确的技能

技能是按描述匹配来加载的，所以你的措辞直接决定加载哪一个。MongoDB 在仓库里放了一批路由测试用例，专门检查「哪句话该触发哪个技能」——就像给代码写集成测试一样。除了这套只测路由的边界用例，仓库里还有一批由模型判分的 `evals.json` 用例，检查答案内容本身，比如生成的 `maxPoolSize` 是否符合预期并发；两者都在 GitHub Actions 里跑。路由测出的边界大致是这样：

| 你想做的事         | 可以这样说                                             | 触发技能                    |
| ------------------ | ------------------------------------------------------ | --------------------------- |
| 定文档模型         | 订单行应该嵌进订单文档还是单独引用？                   | `schema-design`             |
| 从 SQL Server 迁移 | 我想把这些范式化的表搬到 MongoDB，该怎么转？           | `schema-design`             |
| 数组无限增长       | 评论数组越来越大，文档快撞上 16MB 限制了               | `schema-design`             |
| 直接要查询语句     | 写一个查询，找出最近 30 天的订单                       | `natural-language-querying` |
| 解释慢查询         | 这个查询为什么慢？（附上查询）                         | `query-optimizer`           |
| 索引设计           | 这个集合应该建哪些索引？                               | `query-optimizer`           |
| 全文或向量检索     | 做一个能容忍拼写错误的自动补全 / 给 RAG 应用做向量检索 | `search-and-ai`             |
| 连接池与超时       | 我的 API 在负载下连接超时，连接池该怎么配？            | `connection`                |

原文给每个技能配了一条可以直接复制的 .NET 提示词。挑三条最常用的：

```text
我要把一个 ASP.NET Core API 的数据库从 SQL Server 迁到 MongoDB。
关系模型是 Customers、Orders、OrderLines、Addresses，
每个订单历史页面都会把 Orders 和 Customers 关联起来。读大约是写的 10 倍。
请设计文档模型，并告诉我哪些该嵌入、哪些该引用。
```

```text
我的 ASP.NET Core API 跑 6 个容器实例，连一个 3 成员的副本集。
每实例峰值约 40 个并发请求。
请检查我的 MongoClient 配置，告诉我 maxPoolSize 和超时该设多少。
```

```text
这个查询在订单超过一百万之后变慢了：
db.orders.find({ status: "shipped", region: "US" }).sort({ placedAt: -1 })
解释原因。
```

第二条值得展开说一句，因为 `mongodb-connection` 里的公式容易算错。它给的连接总数公式是：

**（minPoolSize + 2）× 副本集成员数 × 应用实例数**

加 2 是因为每个 MongoDB 客户端会为副本集的每个成员开两条监控连接。按「10 个实例、minPoolSize 为 5」直觉估算，你会以为是 50 条连接；如果副本集有 3 个成员，真实数字是 (5 + 2) × 3 × 10 = 210 条。**连接池是按成员而不是按集群计的**，做容量规划时这一步不能省。

这个技能还明确禁止「在不了解应用上下文的前提下添加连接池参数或超时设置」，并给了两种场景的起点：Serverless 用 `maxPoolSize` 3–5、`minPoolSize` 0；常驻服务用 `maxPoolSize` 50 以上、`minPoolSize` 10–20，加上 30 秒 socket 超时。它生成的自管配置长这样：

```csharp
builder.Services.AddSingleton<IMongoClient>(_ =>
{
    var settings = MongoClientSettings.FromConnectionString(connectionString);
    settings.MaxConnectionPoolSize = 50;
    settings.MinConnectionPoolSize = 15;
    settings.SocketTimeout = TimeSpan.FromSeconds(30);
    settings.ServerSelectionTimeout = TimeSpan.FromSeconds(5);
    return new MongoClient(settings);
});
```

重点是先注册成单例，然后全局复用同一个实例——每次 `new MongoClient` 都会重新开一整套连接池和监控连接。

## 对 .NET 开发者：能解决什么，不能解决什么

**这些技能不管 C# 代码怎么写。**这是最需要提前知道的边界。它们面向所有官方支持的 driver 编写，8 个技能里只有 `mongodb-connection` 直接提到了 C#。也就是说：

- 它会明显改善 agent 的**建模和索引决策**——该嵌入还是该引用、该建什么复合索引、该走全文还是向量检索；
- 它**不会**教 agent C# driver 的惯用法，也不涉及 EF Core 的 MongoDB provider。

结论很直接：把它和你的 `CLAUDE.md` 一起用，`.NET` 约定放 `CLAUDE.md`，MongoDB 决策交给技能。指望装完插件就得到地道的 C# driver 代码，会失望。

**另一条边界是 MCP。**没有 MCP，`query-optimizer` 仍然能根据查询形状给出索引建议，但 `explain` 的真实输出、Performance Advisor、查询统计和慢查询日志都需要活的连接。而且 Performance Advisor 这类诊断源要求 Atlas，其中几项还要求 M10 及以上规格。本地开发库连得上就够了，但别期待它替你做完整的生产性能分析。

**还有一条安全边界值得放在前面。**`mongodb-natural-language-querying` 在设计上就是只读的，只生成 `find` 和读聚合；它的 frontmatter 里用 `allowed-tools: mcp__mongodb__*` 把可用工具限制在 MongoDB MCP 范围内。`mongodb-search-and-ai` 在创建任何索引之前会先描述索引定义并等你确认；如果它没有写权限工具，会把索引 JSON 打印出来让你自己贴进 Atlas UI，而不是静默失败。

但这些都只是技能层面的自律。**agent 实际能做什么，最终还是由你给 MCP server 的凭据和权限决定。**第一次接的时候指向开发集群。

## 排错清单

**插件装好了但技能从不触发。**跑 `/reload-plugins`。技能在会话启动时扫描，中途安装的可能要重载或重启才出现。

**明明登录过了，agent 还在要连接字符串。**只有 `mongodb-atlas` 变体走 OAuth。如果它退回到要凭据，要么登录没走完，要么你装的是自管插件。这时候跑 `mongodb-mcp-setup`，它会引导你从三种方式里选一种提供凭据。

**查询优化器说要 Atlas API 凭据。**做通用性能分析会调 `atlas-get-performance-advisor`，需要 `projectId` 和 `clusterName`。没有这两个就只分析单条查询——指名问某一条，而不是让它「找出我的慢查询」。

**激活了错误的技能。**这是措辞问题，而且恰好就发生在 MongoDB 专门测试的那些边界上。对着上面的触发表改措辞，或者直接用 `/技能名` 跳过路由。

**schema 建议看起来很泛。**技能本身就先问你的工作负载和访问模式。老老实实回答，或者把你的查询代码丢给它。什么都不给，它只能给教科书答案。

## 该不该装

**建议装**：刚接触 MongoDB 的 .NET 开发者；或者已经懂 MongoDB、但觉得 agent 不懂、总是在重复犯同样的建模错误的人。单为 `mongodb-schema-design` 和 `mongodb-query-optimizer` 这两个也值得。

**可以先不装**：你的栈里 MongoDB 只是边缘存储，主要精力在 EF Core 和关系型库上，那这套技能的收益有限。

落地顺序建议就三步：装插件（自管用 `mongodb`，Atlas 托管用 `mongodb-atlas`）→ 把 MCP 接到开发库上 → 先保留查询技能自带的只读设定，等你对输出有了信心再考虑放开。技能给的是更好的起点和更多上下文，不是可以直接合并的产出；至少前几次要自己过一遍。

顺带说明一下原文的性质：codewithmukesh 那篇是 MongoDB 的合作文章，末尾有致谢。它的技术整理做得扎实，判断也留了余地（比如明确指出这套技能不覆盖 C# driver），但阅读时知道这层关系没坏处。

如果这篇对你有用，Aide Hub 之后会继续整理 AI 助手、开发工具和软件工程实践相关的内容，包括这类官方技能包和 agent 工作流在实际项目里的取舍。

## 参考

- [MongoDB Agent Skills: What They Fix for .NET Developers](https://codewithmukesh.com/blog/mongodb-agent-skills-dotnet/)：原文。
- [mongodb/agent-skills](https://github.com/mongodb/agent-skills)：官方仓库，8 个技能、测试用例和插件清单都在这里。
- [README.community.md](https://github.com/mongodb/agent-skills/blob/main/README.community.md)：自管部署（`mongodb` 插件）的安装与配置说明，本文安装命令表的来源。
- [Agent Skills 文档](https://www.mongodb.com/docs/agent-skills/)：MongoDB 官方技能文档入口。
- [Agent Skills 开放规范](https://agentskills.io/)：`SKILL.md` 格式与渐进加载机制的规范来源。
- [MongoDB MCP Server 文档](https://www.mongodb.com/docs/mcp-server/)：MCP server 的认证方式与配置参考。
