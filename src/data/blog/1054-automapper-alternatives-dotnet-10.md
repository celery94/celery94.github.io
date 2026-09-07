---
pubDatetime: 2026-09-07T08:02:06+08:00
title: "AutoMapper 商业化后：.NET 映射怎么选"
description: "AutoMapper 2025 年转为商业许可，最后 MIT 版本带未修补高危漏洞。用 .NET 10 实测对比 AutoMapper、Mapster、Mapperly 与手写映射，给出可照做的选型清单、迁移路线和 AI 代理防坑配置。"
tags: ["AutoMapper", "Mapster", "Mapperly", ".NET 10", "Object Mapping"]
slug: "automapper-alternatives-dotnet-10"
ogImage: "../../assets/1054/01-cover.jpg"
source: "https://codewithmukesh.com/blog/automapper-vs-mapster-vs-manual-mapping-dotnet/"
---

项目里已经用了十年 `IMapper`：每个服务注册一个 `Profile`，实体到 DTO 的映射从不操心。现在要开一个新的 .NET 10 API，团队讨论的第一个问题却是——要不要继续用 AutoMapper？

2025 年 7 月 2 日，AutoMapper 和 MediatR 一起发布了商业版。你的默认映射库从此可能变成一项预算开支，而它最后的免费版本，还带着一个没有修复的高危安全通告。Mukesh Murugan 在 [AutoMapper vs Mapster vs Manual Mapping in .NET 10](https://codewithmukesh.com/blog/automapper-vs-mapster-vs-manual-mapping-dotnet/) 里用一份 BenchmarkDotNet 实测给出了 2026 年的判断：**新项目默认 Mapperly，DTO 少就手写，Mapster 只值得为手感选，AutoMapper 留给深度依赖它的存量系统。** 本文按这个思路整理成可以直接照做的选型清单。

## 2025 年发生了什么：许可、通告和三选一

先把事实摆清楚，它们比任何基准都更影响选择。

**许可是双轨的。** AutoMapper 14.0.0（2025 年 2 月 14 日发布）仍是 MIT 许可，可以按原条款自由使用。从 15.0.1 起，AutoMapper 改用 [Reciprocal Public License 1.5](https://en.wikipedia.org/wiki/Reciprocal_Public_License) 与 Lucky Penny Software 商业许可的双授权：RPL-1.5 是开源许可，但要求你把自己的衍生代码也按 RPL-1.5 发布，与多数商业软件不兼容。接受不了的企业可以申请免费的 Community 许可，条件是年总收入低于 500 万美元、非营利组织年预算低于 500 万美元、教学用途或非生产环境；其余团队需要付费商业许可。公开渠道显示最小商业档约 489 美元/年（按开发者数量分层）。商业化当天的公告见 [Jimmy Bogard：AutoMapper and MediatR Commercial Editions Launch Today](https://www.jimmybogard.com/automapper-and-mediatr-commercial-editions-launch-today/)。

**安全通告更棘手。** AutoMapper 有一个 [GitHub 安全通告 GHSA-rvv3-g6hj-g44x](https://github.com/advisories/GHSA-rvv3-g6hj-g44x)，官方评级 High、CVSS 7.5，属于 CWE-674 不受控递归：映射引擎的递归调用没有默认深度上限，构造约 2.5 万层以上的嵌套输入会触发 `StackOverflowException`，终止的是**整个进程**，不只是请求线程。受影响的版本是 15.1.1 之前的所有版本（包括免费的 14.0.0），以及 16.0.0 到 16.1.0。修复在商业许可的 15.1.1 和 16.1.1 里，从未回移植到 MIT 的 14.x 线。

这不是纯纸面问题。通告已进入 NuGet 漏洞数据库，现在恢复 AutoMapper 14.0.0 会直接出现构建警告：

```text
warning NU1903: Package 'AutoMapper' 14.0.0 has a known high severity vulnerability,
https://github.com/advisories/GHSA-rvv3-g6hj-g44x
```

如果项目开了 `TreatWarningsAsErrors`，或 CI 把 NuGet 审计设为失败即中止，停留在 14.0.0 会直接破坏构建——直到有人去压制这个警告。这个事实比许可变化本身更能促使团队在 2026 年转向替代方案。

所以每个 .NET 团队今年的问题都一样：**付费、冻结、还是替换？** 存量系统无法动就付费；能接受通告和不再有修复就冻结在 14.0.0；想要更小、更快、支持 AOT、完全可控的方案就替换。

## 四个候选，机制先分清

对比之前先理解每个方案的运行机制，它们的差异远比「快不快」重要：

| 方案       | 许可                               | 机制                                         | 关键特征                                                                                                                           |
| ---------- | ---------------------------------- | -------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| AutoMapper | 14.0.0 MIT；15.0.1+ RPL-1.5 + 商业 | 运行时反射，`Profile` 按约定配置             | 成熟、文档全、EF Core `ProjectTo<TDestination>()` 支持好；无深度上限递归是 15.0.1 前通告的根源                                     |
| Mapster    | MIT                                | 运行时编译委托，`TypeAdapterConfig` 流畅配置 | 7.4.0（2023 年 9 月）跳到 10.0.0（2026 年 3 月）以对齐 .NET 版本；默认模式依赖 `Expression.Compile()`，AOT 下需另装 `Mapster.Tool` |
| Mapperly   | Apache-2.0                         | 纯 C# 源生成器，编译期生成实现               | 零运行时反射，原生 AOT 与裁剪全兼容；声明 `partial` 映射类即可                                                                     |
| 手写映射   | 无                                 | `record` + 扩展方法，直接构造                | 每个 DTO 两行，JIT 可内联；无包、无配置、无惊扰                                                                                    |

为了让比较公平，作者的所有示例都映射同一个形状：`Product` 聚合体（嵌套 `Category` + `List<Tag>`）到 `ProductResponse` record。这个形状同时覆盖简单属性复制、嵌套对象和集合。文中版本均已核实：AutoMapper 14.0.0（最后 MIT）与 16.2.0（当前商业版）、Mapster 10.0.12、Mapperly 4.3.1（Apache-2.0，5.0 系列仍在预发布）。共享类型如下（下文代码都基于它）：

```csharp
public sealed class Product
{
    public Guid Id { get; init; }
    public string Name { get; set; } = string.Empty;
    public string Description { get; set; } = string.Empty;
    public decimal Price { get; set; }
    public int StockQuantity { get; set; }
    public DateTime CreatedAt { get; init; }
    public DateTime? UpdatedAt { get; set; }
    public Category Category { get; set; } = null!;
    public List<Tag> Tags { get; set; } = new();
}

public sealed record ProductResponse(
    Guid Id,
    string Name,
    string Description,
    decimal Price,
    int StockQuantity,
    DateTime CreatedAt,
    DateTime? UpdatedAt,
    CategoryResponse Category,
    IReadOnlyList<TagResponse> Tags);

public sealed record CategoryResponse(int Id, string Name, string Slug);

public sealed record TagResponse(int Id, string Label);
```

AutoMapper 的定义方式是 `Profile` 类加 `CreateMap`，启动时注册、运行时按名字反射复制；Mapster 用全局或显式的 `TypeAdapterConfig`，第一次见到类型对时编译委托，之后直接调用——理论上把配置成本摊掉，热路径只留一个紧致的、JIT 友好的方法；Mapperly 用 `[Mapper]` 特性声明 `partial` 类，编译器把实现写进 obj 目录，生成的就是可读的 C# 代码，`EmitCompilerGeneratedFiles` 打开就能检查；手写映射则是直接的 record 构造：`product.Tags.ConvertAll(static t => t.ToResponse())` 这种两行扩展方法，编译器看到整个构造调用，JIT 可以内联，新增属性时编译器会指着 `ToResponse` 让你更新——漏映射在编译期就暴露，而不是返回一个悄悄为 null 的字段。

## .NET 10 实测：基准数字与三个发现

作者用 BenchmarkDotNet 0.15.8 在 .NET 10.0.11、Intel Core Ultra 9 275HX（Windows 11, X64 RyuJIT）上运行全部四个方案：每次调用映射一个带嵌套 `Category` 和三个 `Tag` 的 `Product`；所有 mapper 都在 fixture 构造时预配置并预编译，测量的就是 API 每请求命中的稳态热路径。手动映射为基线：

| 方案       | Mean     | Ratio | 分配  | 分配比 |
| ---------- | -------- | ----- | ----- | ------ |
| 手写映射   | 33.98 ns | 1.01  | 328 B | 1.00   |
| Mapperly   | 30.23 ns | 0.90  | 296 B | 0.90   |
| Mapster    | 67.53 ns | 2.01  | 328 B | 1.00   |
| AutoMapper | 71.85 ns | 2.13  | 336 B | 1.02   |

（原表完整数值含 Error/StdDev/Median；作者 7.4.0 年代的同一基准下 Mapster 为 50.4 ns、约 1.29 倍手写。）

三个值得单独说清的发现：

1. **Mapperly 比手写还快，且内存更少**（30.2 ns vs 34.0 ns；296 B vs 328 B）。这与「手写不可能被超越」的流行说法相反，原因在 Tag 集合：`List<T>.ConvertAll(static t => t.ToResponse())` 会分配整个 `List<TagResponse>`（列表对象加后备数组），并逐元素调用委托，JIT 无法穿透内联。Mapperly 生成的是普通循环，一次分配到位并直接内联逐项映射。需要澄清的是：static lambda 本身没有闭包分配（Roslyn 会把委托缓存到静态字段），32 字节差距来自多出的列表包装和间接调用。
2. **Mapster 的性能名声过时了。** 7.4.0 上是约 1.29 倍手写、明显快于 AutoMapper；10.0.12 上变成约 2.0–2.1 倍手写，与 AutoMapper 在统计上不分伯仲（作者两次运行中 Mapster 67.5–79.3 ns、AutoMapper 71.9–79.1 ns）。作者明确说自己没有定位到根因——基准给 `Adapt<T>()` 传入的是显式 `TypeAdapterConfig` 实例，这可能是一个值得测试的因素——但结论是确定的：**「Mapster 是快的那一个」在 2026 年不再成立，为它选型应该看流畅配置与 MIT 许可，而不是三年前赢来的性能名声。**
3. **AutoMapper 只有约 2.1 倍慢，不是网络流传的 10 倍、更不是 17000 倍。** 那些吓人数字来自特定场景：深对象图、未预编译配置的冷启动、数千对象的投影。稳态热路径上 AutoMapper 约两倍手写成本，内存只多约 2%。

结果可靠吗？看置信区间：BenchmarkDotNet 的 Error 列是 99.9% 置信区间半宽，手写落在 [32.90, 35.06] ns，Mapperly 落在 [29.31, 31.15] ns，**两个区间不重叠**，所以「Mapperly 快于手写」在这个工作负载上不是噪声。

但基准在什么情况下才值得纠结纳秒？作者给了一个很好的边界：如果每次请求映射的对象少于 1000 个，最慢的 AutoMapper（71.9 ns）完成 1000 次映射也只要约 72 微秒。这个场景下决策应该围绕许可、AOT 兼容、可调试性和上手成本，而不是纳秒。基准真正影响决策，是在映射大批结果集、映射处于热异步循环内、或目标是对启动敏感的 Native AOT 容器时。

## 决策矩阵：先问两个问题

选型前先回答两个问题：**「目标是否 Native AOT？」** 和 **「现有代码库是否已经在用某个 mapper？」** 这两个答案通常会在性能进入讨论之前就排除掉两三个选项。

| 条件                                                      | 选择                                              |
| --------------------------------------------------------- | ------------------------------------------------- |
| 新建 .NET 10 服务，无硬性约束                             | Mapperly（最快、AOT 干净、许可友好）              |
| 面向 Native AOT（Serverless、容器启动敏感、需裁剪）       | Mapperly                                          |
| DTO 类型少于约 15–20 个，想零新依赖                       | 手写映射                                          |
| 团队偏新手，要最简单的调试路径                            | 手写映射                                          |
| 想要 `.Adapt<T>()` 流畅运行时配置、不需 AOT、不追极限速度 | Mapster                                           |
| 存量 AutoMapper 代码库，且符合 RPL-1.5 免费档             | 留在 14.0.0，接受通告，规划迁移                   |
| 存量 AutoMapper 代码库，收入超过 500 万美元               | 付费升 15+，或规划 Mapperly 迁移                  |
| 需要 EF Core `ProjectTo` 且查询映射密集                   | AutoMapper（免费档）或 Mapster（`ProjectToType`） |

## 迁移片段

从 AutoMapper 迁移到 Mapperly，把 `Profile` 换成：

```csharp
[Mapper]
public partial class ProductMapperlyMapper
{
    public partial ProductResponse ToResponse(Product product);
}
```

注入从 `IMapper` 换成 `ProductMapperlyMapper`，调用从 `mapper.Map<ProductResponse>(product)` 换成 `mapper.ToResponse(product)`。迁移到 Mapster 则是把 `Profile` 换成 `TypeAdapterConfig<Product, ProductResponse>.NewConfig();`，调用换成 `product.Adapt<ProductResponse>()`，无需注入。迁移到手写映射是换成扩展方法并去掉 `IMapper` 参数，是改动最小的路径。作者的经验是：30 个 DTO 的项目，AutoMapper → Mapperly 约需 2–4 小时机械工作，手写略少；端点代码前后基本不变，变的只有注入依赖和那一行调用。

## AI 代理写映射代码：防它默认 AutoMapper

映射是接近理想的 AI 代理任务：机械、重复、量大、编译器能兜底。但有两个坑要先设好。

**默认行为会坑你。** 让任何一个当前模型「把实体映射成 DTO」，大概率得到一个 `Profile`、`CreateMap` 和注入的 `IMapper`。这不是模型不懂 2026，而是它在复现十年教程、Stack Overflow 和示例仓库里最常见的答案——许可变化才一年，训练语料跟不上。而且模型不知道你公司的收入，无法判断免费 Community 档是否适用。

**修复办法是把决定写进工具读取的指令文件**——`CLAUDE.md`、`AGENTS.md` 或 `.github/copilot-instructions.md`：

```markdown
## 对象映射

- 所有 entity-to-DTO 映射使用 Mapperly（`Riok.Mapperly`）。
- 每个映射对声明一个带 `[Mapper]` 的 `partial` 类与 `partial` 方法。
- 不要添加 AutoMapper：v15 起为商业许可，最后的 MIT 版本（14.0.0）
  带有未修补的高危通告。
- 单个功能少于 3 个 DTO 时，直接用扩展方法里的 record 构造调用手写映射，
  而不是引入 mapper。
```

**选一种「错误即编译错误」的方案。** 这是代理协作中最重要的一点：如果代理给 `ProductResponse` 加属性却漏了映射，手写映射和 Mapperly 都会构建失败并指向那一行；AutoMapper 的约定匹配常常留下默认值，返回 200 和一个悄悄为 null 的字段，几天后以 bug 形式出现。失败的构建是让代理发现并修复自己错误的反馈闭环。对 Mapperly 还可以打开 `<EmitCompilerGeneratedFiles>true</EmitCompilerGeneratedFiles>`，每个新 mapper 读一遍生成的 `.g.cs`——检查嵌套集合是否按预期映射，一分钟内就能抓住「编译通过但悄悄丢集合」这类问题。

这个问题不限于 mapper。MediatR、MassTransit、FluentAssertions 也在同一窗口转向付费许可，代理同样会自信地推荐它们。护栏是仓库级别的，设一次就好。

## 什么时候还该留在 AutoMapper

AutoMapper 仍有两个不可替代之处：**最成熟的 `ProjectTo<TDestination>` 集成**，以及大量存量 `Profile` 的既有约定。重 EF Core 投影、查询层深度依赖 AutoMapper 表达式树生成的服务，迁移代价高于收益：Mapperly 虽支持查询投影且只拉取目标类型字段，但投影需要编译为表达式树，会丢失对象工厂、ByName 枚举映射、引用处理与深拷贝、可空引用类型处理等特性——需要预留真实时间测试，而不是假设一行替换。Mapster 的 `ProjectToType` 更接近 drop-in，但仍有差异。

两种情况下我的建议是：符合规模档就留在免费 14.0 线，或付费升 15+。真正的风险在绿地上：**2026 年新项目因为「以前一直这么用」而再次引入 AutoMapper，是把 2018 年的理由——成熟、没对手、永远免费——当成 2026 年的条件。** 反过来，也不该因为「AutoMapper 慢 10 倍」的标题就拒绝它：热路径上它只是约 2 倍慢。

## 常见问题

**AutoMapper 2026 年还免费吗？** 14.0.0 及更早仍是 MIT 且无时间限制。15.1 起为 RPL-1.5 + 商业双许可；年收入低于 500 万美元的企业、预算低于 500 万美元的非营利机构、教育和非生产环境可申请免费 Community 许可，其余需付费（最小档约 489 美元/年）。

**Mapster 比 AutoMapper 快吗？** 当前版本上不再是。Mapster 7.x 时代确实如此，网上多数文章仍这么写；在 10.0.12 对 AutoMapper 14.0.0 的同款基准里，两者在统计上持平（67.5 ns 对 71.9 ns，均为手写的约 2 倍）。

**AutoMapper 支持 .NET 10 的 Native AOT 吗？** 不支持，除非付出大量人工。它依赖运行时反射和动态表达式构建，裁剪器与 AOT 编译器无法静态分析；`PublishAot=true` 且依赖图中存在 AutoMapper 会产生警告，运行时映射也可能失败。AOT 服务请选 Mapperly 或手写。

**少于多少个 DTO 适合手写？** 大约 15–20 个以下，且 DTO 有定制形状规则、需要 AOT 或想零依赖时。手写是 .NET 10 上仅次于 Mapperly 的第二快方案，也最好调试、最好带新人——整个映射在一个地方读完。

**Mapster 和 Mapperly 一样吗？** 不一样。Mapster 在运行时用 `System.Linq.Expressions.Expression.Compile` 编译委托并逐次调用；Mapperly 是 Roslyn 源生成器，编译期生成纯 C#，零运行时反射，默认就 AOT 兼容。`Mapster.Tool` 是 Mapster 的源生成替代选项，但不是默认。

## 先回答两个问题，再决定

读完本文，建议你只做一件事：对当前项目回答「是否面向 Native AOT」和「现有代码是否已用某个 mapper」两个问题，然后按上面的决策矩阵选一个，把理由写进仓库指令文件。如果选择留在 AutoMapper 14.0.0，请同时建立迁移计划和安全审计节奏——通告会持续存在，直到你升级或替换。

还有一层更值得记住的教训来自作者自己：**库的性能主张会悄悄过期。** Mapster 没有宣布自己变慢，API 也没变，唯一的发现方式是升级依赖、重跑数字。如果代码库里某个选型依赖的是你多年前读过的一次基准，值得在你实际发布的版本上再测一次。

Aide Hub 会继续分享 AI 助手、开发工具与软件工程实践中的具体做法。

## 参考

- [codewithmukesh：AutoMapper vs Mapster vs Manual Mapping in .NET 10](https://codewithmukesh.com/blog/automapper-vs-mapster-vs-manual-mapping-dotnet/)
- [GitHub Advisory：GHSA-rvv3-g6hj-g44x（AutoMapper DoS via Uncontrolled Recursion）](https://github.com/advisories/GHSA-rvv3-g6hj-g44x)
- [GitLab Advisory Database：同一通告（CVSS 7.5、受影响版本清单）](https://advisories.gitlab.com/nuget/automapper/GHSA-rvv3-g6hj-g44x/)
- [Jimmy Bogard：AutoMapper and MediatR Commercial Editions Launch Today](https://www.jimmybogard.com/automapper-and-mediatr-commercial-editions-launch-today/)
- [NuGet：AutoMapper 16.2.0](https://www.nuget.org/packages/AutoMapper)
- [NuGet：Mapster 10.0.12](https://www.nuget.org/packages/Mapster)
- [NuGet：Riok.Mapperly 4.3.1（Apache-2.0）](https://www.nuget.org/packages/Riok.Mapperly)
- [示例与基准仓库：dotnet-webapi-zero-to-hero-course](https://github.com/codewithmukesh/dotnet-webapi-zero-to-hero-course/tree/main/modules/03-advanced-api-patterns/automapper-vs-mapster-vs-manual-mapping)
