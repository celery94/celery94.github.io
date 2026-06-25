---
pubDatetime: 2026-06-26T07:18:14+08:00
title: "用 Agent Skill 固化架构规范：从纠正 AI 到自己动手建一个 Scaffold 技能"
description: "AI 编程助手默认生成的是"平均化"的代码——用 Controller 而不是 Minimal API，引 Swagger 而不是 Scalar。与其每次纠正，不如把项目规范写进一个 Agent skill，一条命令产出符合你架构的完整垂直切片。这篇文章从零搭建一个 scaffold 技能，讲清楚它和项目规则、子 agent 的区别，以及什么时候值得做。"
tags: ["Agent Skills", ".NET", "Vertical Slice", "Scaffolding", "AI Coding"]
slug: "agent-skill-scaffold-dotnet-architecture"
ogImage: "../../assets/901/01-cover.png"
source: "https://codewithmukesh.com/blog/claude-code-skill-scaffold-dotnet-architecture/"
---

用 AI 编程助手写 .NET 代码的最初几周，我几乎每次都在纠正同样的问题。它生成 Controller，而项目用的是 Minimal API。它自动补上 `AddSwaggerGen()`，而我已经迁移到了 Scalar。它把所有逻辑塞进一个 `Services/` 文件夹，而代码库是按 feature 组织的。代码能编译，但它从来不是**我的**代码。我在修风格上花的时间，比亲自手写还多。

后来我不再纠正，转而开始"教"。我把项目的编码规范写进了一个自定义 Agent skill——只做一次。之后 `/scaffold-feature Products` 一条命令产出完整的垂直切片：endpoint、handler、validator、response、EF Core 配置和集成测试，结构跟我手写的一模一样。

这篇文章会从空文件夹开始，把那个 skill 完整搭出来。主角是 .NET 10 的垂直切片架构，Agent skill 只是学会复现它的工具。

> 文中的 Agent skill 机制以 Claude Code 为例，但核心思路——把项目约定固化为可复用指令文件——适用于任何支持自定义 skill / rule / instruction 的 AI 编程助手。

## Agent skill 是什么

一句话：Agent skill 是存放在项目目录（或用户目录）里的一个 `SKILL.md` 文件，里面写好了执行某个重复性工作流的指令和模板。你可以用一条 slash command 触发它，AI 读取 skill 后严格按你的约定生成代码，而不是输出通用的教程模板。

以本文要建的 scaffold skill 为例：它知道项目用 Minimal API 而不是 Controller，用 Scalar 而不是 Swagger，handler 是 plain class 而不是 `MediatR`，每个方法都要传 `CancellationToken`。这些规则写进 skill 一次，之后每次产出的代码都符合你的架构。

Skills 遵循开放的 [Agent Skills 标准](https://agentskills.io)，在 Claude Code 中有[官方文档](https://code.claude.com/docs/en/skills)支持。

## 为什么 AI 默认输出跟你的项目对不上

开箱即用的编码模型生成的是**统计学上最"平均"**的 .NET 代码。互联网上最多的 .NET 教程用 Controller、三层文件夹结构、Swagger 和 `MediatR`——所以 AI 默认就给你这些，哪怕你的项目刻意做了完全不同的选择。

问题不在于输出是错的——它能编译。问题在于它**在二十个细节上偏了**，而你成了全职纠错员：

- 给了 Controller 而不是 Minimal API endpoint
- 加了 `services.AddSwaggerGen()` 而你用 Scalar
- 代码散落在 `Services/` 和 `Models/` 而不是按 feature 分文件夹
- handler 里没传 `CancellationToken`
- 在 entity 上用 data annotation 而不是 `IEntityTypeConfiguration`

每次修正只要 30 秒，一个 feature 下来就是 20 分钟，一周下来就是你觉得工具在跟你对着干的原因。

解法很简单：把规范从你脑子里搬出来，放到 AI 每次都能读到的地方。

## 项目规则 vs Skill vs 子 Agent：什么时候用哪个

在动手建 skill 之前，先搞清楚 skill 是不是对的那把刀。让 AI 遵守规范的机制有三种，它们不通用。

| 机制                                                 | 是什么                       | 适合什么                                                                      | 代价                               |
| ---------------------------------------------------- | ---------------------------- | ----------------------------------------------------------------------------- | ---------------------------------- |
| **项目规则文件**（如 `CLAUDE.md` / `.cursor/rules`） | 总是加载的项目记忆           | 每次对话都要适用的全局规则（"用 .NET 10，Scalar 不用 Swagger，禁止 MediatR"） | 每次 prompt 都加载——保持简短       |
| **Skill**                                            | 按需触发的可复用工作流       | 有固定步骤和模板的重复性流程（"搭一个完整的 feature slice"）                  | 只在调用时加载——可以写得很长很细   |
| **子 Agent**                                         | 独立上下文、自带工具的 Agent | 重任务、并行任务或隔离审查（"在干净上下文里审查整个模块"）                    | 启动新 agent，更多 token，更多隔离 |

**我的规则：原则放项目规则文件，流程放 skill，只在上下文隔离确实有收益时才用子 agent。**

搭建一个 feature 是有固定形态和十几条小规则的流程，所以它天然属于 skill。如果我把完整 slice 模板硬塞进 `CLAUDE.md`，每次对话都会带着 95% 无关的指令，白白撑大 prompt。Skill 不调用时完全不出场，只在你需要时才介入。

## 我要固化的架构：垂直切片

Skill 只能复现你能精确描述的结构。动手写 skill 之前，先把目标产出定死。

我用的是**垂直切片架构**：每个 feature 是自包含的文件夹，包含该 feature 需要的一切，而不是把一个 feature 分散在 `Controllers`、`Services`、`Repositories`、`Models` 四个目录里。

一个 `CreateProduct` feature 的目标结构：

```
src/Api/
  Features/
    Products/
      CreateProduct/
        CreateProductEndpoint.cs
        CreateProductCommand.cs
        CreateProductHandler.cs
        CreateProductValidator.cs
        CreateProductResponse.cs
      Product.cs
      ProductConfiguration.cs
```

Endpoint 是 Minimal API（不是 Controller）。它负责校验、调用 handler、返回 `TypedResults`：

```csharp
public static class CreateProductEndpoint
{
    public static void MapCreateProduct(this IEndpointRouteBuilder app)
    {
        app.MapPost("/products", Handle)
            .WithName("CreateProduct")
            .WithTags("Products");
    }

    private static async Task<Results<Created<CreateProductResponse>, ValidationProblem>> Handle(
        CreateProductCommand command,
        CreateProductHandler handler,
        IValidator<CreateProductCommand> validator,
        CancellationToken cancellationToken)
    {
        var validation = await validator.ValidateAsync(command, cancellationToken);
        if (!validation.IsValid)
        {
            return TypedResults.ValidationProblem(validation.ToDictionary());
        }

        var response = await handler.HandleAsync(command, cancellationToken);
        return TypedResults.Created($"/products/{response.Id}", response);
    }
}
```

Handler 是 plain sealed class，构造注入 `DbContext`，没有 `MediatR` 的管道间接层：

```csharp
public sealed class CreateProductHandler(AppDbContext db)
{
    public async Task<CreateProductResponse> HandleAsync(
        CreateProductCommand command,
        CancellationToken cancellationToken)
    {
        var product = new Product
        {
            Id = Guid.CreateVersion7(),
            Name = command.Name,
            Price = command.Price
        };

        db.Products.Add(product);
        await db.SaveChangesAsync(cancellationToken);

        return new CreateProductResponse(product.Id, product.Name, product.Price);
    }
}
```

Command、Response 和 Validator 短小且可预测：

```csharp
public sealed record CreateProductCommand(string Name, decimal Price);

public sealed record CreateProductResponse(Guid Id, string Name, decimal Price);

public sealed class CreateProductValidator : AbstractValidator<CreateProductCommand>
{
    public CreateProductValidator()
    {
        RuleFor(x => x.Name).NotEmpty().MaximumLength(200);
        RuleFor(x => x.Price).GreaterThan(0);
    }
}
```

每个 feature 都是这个形状。因为高度一致，一个 skill 就能可靠生成。

还有一个文件夹结构里看不出来的设计：每个 endpoint 暴露自己的 `Map*` 扩展方法，接入 feature 只要一行：

```csharp
// Program.cs
app.MapCreateProduct();
```

这一行是 feature 文件夹之外唯一的改动——这正是垂直切片的全部意义：feature 是**添加**进来的，不需要在四个共享目录里来回穿线。

## 从零搭建 skill

### 第一步：创建 skill 文件夹

```bash
mkdir -p .claude/skills/scaffold-feature/references
```

`references` 子文件夹用来放代码模板，让主 `SKILL.md` 保持可读。

### 第二步：编写 SKILL.md

前面的 YAML frontmatter 是契约。文件夹名就是 slash command（`/scaffold-feature`），`description` 决定 AI 什么时候自动识别这个 skill 是否相关。

```yaml
---
name: scaffold-feature
description: 为本 .NET API 添加新 feature 时使用——按项目规范搭建完整垂直切片
  （endpoint、command、handler、validator、response、EF 配置、集成测试）。
  触发词："scaffold feature"、"add feature"、"new endpoint"、"create slice"。
---

# /scaffold-feature —— 搭建垂直切片

为本 .NET 10 Minimal API 生成一个完整的垂直切片。
严格遵循以下约定，不要发明替代结构。

## 约定（不可协商）
- .NET 10，只用 Minimal API。绝不生成 Controller。
- 用 Scalar 做 API 文档，绝不用 Swashbuckle 或 Swagger。
- 一个 feature = `src/Api/Features/<Entity>/<UseCase>/` 下的一个文件夹。
- 每个用例自包含：endpoint、command、handler、validator、response。
- Handler 是 plain sealed class，在 endpoint 中直接调用。不用 MediatR。
- 每个 command 都要有 FluentValidation validator。
- 每个 endpoint 和 handler 都要接收 CancellationToken 并向下传递。
- EF Core 10。用 IEntityTypeConfiguration 配置 entity，绝不用 data annotation。
- Endpoint 返回 TypedResults 的 Results<...>，绝不用原始 IActionResult。
- 用 Guid.CreateVersion7() 生成 entity id。

## 步骤
1. 如果未提供 entity 和用例名，先询问。
2. 读取 references/slice-template.md 获取精确的文件形态。
3. 在 src/Api/Features/<Entity>/<UseCase>/ 下生成所有文件。
4. 在 feature 的 endpoint wiring 中调用其 Map* 方法注册路由。
5. 在依赖注入中注册 validator 和 handler。
6. 用 WebApplicationFactory 在 tests/ 下生成集成测试。
7. 执行 `dotnet build`，在报告完成前修复所有错误。

## 输出
报告创建的每个文件和注册的路由。不要把代码概括复述给我。
```

有两点让这个 skill 能真正工作：

1. **约定写成硬规则，不是建议。**"绝不生成 Controller"不给通用默认值留任何钻空子的余地。
2. **步骤里包含了验证（`dotnet build`）。**skill 不会把编译不过的代码交到你手上。

### 第三步：加入代码参考模板

AI 能理解文字描述，但代码形态这种事，**看一遍比说十遍管用**。把精确的模板放进 `references/slice-template.md`，skill 里再引用它。

模板就是前面那段 `CreateProduct` 代码，把 `Products` 和 `CreateProduct` 换成 `<Entity>` 和 `<UseCase>` 占位符。模板单独成一个文件，意味着你改代码形态时不用动 skill 的主逻辑。

### 第四步：确认 skill 可被发现

Agent 会自动监控 skills 目录，在当前会话内就能识别新建的 skill 文件夹——前提是 `.claude/skills/` 目录在会话启动时已存在。如果这个目录是刚创建的，重启会话让它开始监控。加载成功后，skill 会以 `/scaffold-feature` 出现在 slash command 列表里。如果没出现，常见原因是 YAML frontmatter 格式有问题——缺字段或 description 跨行时缩进不正确。

## 不想手写？让 Agent 帮你建 skill

这段 `SKILL.md` 是我手写的，因为我知道正文该怎么表达。但你不需要从空白文件开始。Anthropic 提供了一个官方的 `skill-creator` skill，能通过对话帮你**生成** skill——如果你是第一次建 skill，这是更务实的起点。

在 Agent 会话中安装：

```
/plugin install skill-creator@claude-plugins-official
```

然后用自然语言描述你想要的 skill。越具体，第一版越接近目标。关键是把你本来要手写的约定喂给它：

> 帮我建一个叫 `scaffold-feature` 的 skill，为本 .NET 10 Minimal API 生成完整垂直切片。
> 每个 slice 在 src/Api/Features/<Entity>/<UseCase>/ 下包含：endpoint、command、handler、validator、response、EF Core IEntityTypeConfiguration、WebApplicationFactory 集成测试。
> 约定（不可协商）：只用 Minimal API，绝不用 Controller；用 Scalar 不用 Swagger；plain sealed handler，不用 MediatR；每个方法都要传 CancellationToken 并向下传递；最后跑 dotnet build 修复错误。
> 在写任何代码之前，反复问我问题直到我们对 skill 的每个方面都达成共识。不要猜测。

`skill-creator` 不会直接丢给你一个文件。它会先追问你——边界情况、输入示例、触发短语——然后起草 frontmatter 和正文，最后还会重写 `description` 字段以优化自动触发。那句"不要猜测"很关键：它强制 `skill-creator` 去问那些它本来会猜的决策，而猜错正是生成 skill 偏离你架构的根因。

把生成的 skill 当作**初稿**，不是终稿：逐行检查约定，收紧模糊表述，然后加上代码参考模板。

## 跑起来：/scaffold-feature Products

skill 就位后，在 Agent 会话中执行：

```
/scaffold-feature CreateProduct on the Products entity
```

Agent 读取 skill 和参考模板，生成完整切片：Minimal API endpoint（不是 Controller）、带 `CancellationToken` 的 sealed handler、validator、records，以及 `IEntityTypeConfiguration`。它还会加上 `app.Map*` 那一行，注册 handler 和 validator 到依赖注入，写一个 `WebApplicationFactory` 集成测试，最后跑 `dotnet build` 确认能编译。

以前要手动敲 20 分钟再加 20 分钟纠错，现在一条命令加快速 review 一下 diff。而且输出**一致**——第十个 slice 跟第一个长一个样，这对保持代码库可导航性至关重要。

## 什么时候值得做，什么时候不值得

**有重复且稳定的结构，外加超过几个 feature 要建时**，scaffold skill 就值了。它的全部价值在于"在大体量下保证一致性"。如果代码库里每个 feature 都长一样，skill 就把这种一致性编码下来，团队扩大后仍然能守住。

不值得做的情况：一次性原型、约定还在每周变动的项目、或者只有三个 endpoint 的小型 API。Skill 是一份契约——围绕还没确定的约定写契约，只是折腾。先用手把架构定下来，手写两三个 slice 到你满意为止，**然后**把模式提取进 skill。Skill 应该编码你已经做完的决策，而不是替你拍板。

## Skill 跑偏了怎么修

即使 skill 写得再细，偶尔还是会跑偏——加了一个你没要求的 `try/catch`，或者文件名差了一点。修的方法跟你调任何指令一样：找到缺口，在 skill 里堵上，下一次运行就继承了修正。三件事让我这个 skill 一直走正：

1. **约定写成硬规则。**"绝不生成 Controller"管用。"优先使用 Minimal API"就给例外留了余地。
2. **把精确代码放进参考模板。**当 AI 有了具体形态可以抄而不是从文字推断时，偏一下就少多了。
3. **把验证写进步骤。**以 `dotnet build`（和测试运行）收尾，把"看起来对"变成"确实对"，小错误在你看到之前就被抓出来了。

Skill 是一个活的文件。同样的问题要你纠正两次，那次纠正就应该住进 `SKILL.md`，而不是住在你下一次 prompt 里。

## 要点小结

- **Agent skill 就是一个 SKILL.md 文件**，放在项目（或用户）skills 目录下，用 slash command 触发。
- **原则放项目规则文件，流程放 skill。**搭建 feature 是流程，所以它属于 skill，只在调用时加载。
- **把约定写成不可协商的硬规则**，配上代码参考模板——这是阻止通用默认值渗入的关键。
- **把 `dotnet build` 写进 skill 的步骤**，确保它不会交出编译不过的代码。
- **先手写定模式，再提取。**Skill 应该编码你已经确定的架构，而不是替你决定它。

## FAQ

**Agent skill 跟项目规则文件有什么区别？**

项目规则文件（如 `CLAUDE.md`、`.cursor/rules`）始终加载进每次对话，适合简短全局规则。Skill 只在调用时加载，可以写得很长。你用规则文件管"每次都要对的事"，用 skill 管"特定流程里有步骤和模板的事"。

**能用来搭建完整的垂直切片吗？**

可以。把约定和代码参考模板写进 `SKILL.md`，skill 就能生成完整切片——endpoint、command、handler、validator、response、EF Core 配置和集成测试——然后跑 `dotnet build` 确认能编译。

**怎么阻止 AI 生成 Controller 而不是 Minimal API？**

在 skill 里写成硬规则，比如"只用 Minimal API，绝不生成 Controller"，并在参考模板里提供精确的 Minimal API endpoint 代码。措辞从"偏好"变成"规则"，通用默认值就不会渗回来。

**Skill 跑偏了怎么更新？**

当同样的问题纠正两次，就把那次修正加进 `SKILL.md` 作为硬规则，或者收紧参考模板。下一次调用自动继承修正，skill 会随时间变好，而不是重复同样错误。

**不限于 Claude Code，其他 AI 编程助手也能用吗？**

核心思路——把项目约定固化为可复用指令文件——是通用的。Cursor 的 `.cursor/rules`、Copilot 的 custom instructions、Windsurf 的 rules 都可以实现类似效果，只是具体机制和触发方式不同。关键是**先有稳定的架构约定，再编码**，而不是反过来。

## 参考

- [原文：I Built a Claude Code Skill That Scaffolds My .NET Architecture](https://codewithmukesh.com/blog/claude-code-skill-scaffold-dotnet-architecture/)
- [Agent Skills 标准](https://agentskills.io)
- [Claude Code Skills 官方文档](https://code.claude.com/docs/en/skills)
- [dotnet-claude-kit](https://github.com/codewithmukesh/dotnet-claude-kit)
