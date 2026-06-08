---
pubDatetime: 2026-06-08T08:40:43+08:00
title: "DRY 被误解最多的一点：别去重代码，去重知识"
description: "很多人把 DRY 理解成看到相似代码就抽方法，但 Milan Jovanović 提醒：DRY 关注的是知识，而不是代码形状。错误抽象会制造隐藏耦合，重复有时反而更便宜。真正该抽的是必须一起变化的同一个事实。"
tags: ["Software Engineering", "Architecture", "Refactoring", "DRY"]
slug: "dry-misunderstood-rule-programming-knowledge"
ogImage: "../../assets/858/01-cover.png"
source: "https://www.milanjovanovic.tech/blog/dry-is-the-most-misunderstood-rule-in-programming"
---

很多开发者很早就学过 DRY：Don't Repeat Yourself。然后也很早就把它学歪了。

看到两段代码长得像，就抽一个 helper；看到两个类字段相似，就拉到 shared module；看到几个流程都有同样几行判断，就塞进一个 common service。短期看少了重复，长期看多了参数、分支、继承层级和跨模块耦合。Milan Jovanović 这篇文章真正想提醒的是：DRY 不是“别重复代码”，而是“别重复同一份知识”。

## DRY 说的是知识

《The Pragmatic Programmer》里对 DRY 的原始表述，重点是 knowledge：系统里的每一份知识，都应该有一个单一、明确、权威的表达。

这里的关键不是“代码看起来一样”，而是“它们表达的是不是同一个事实”。税率、发票号格式、订单超过某个金额需要审批，这些都是领域知识。如果同一个事实散落在多处，规则一改，你就要到处找副本，迟早会漏。

但两段代码长得一样，不代表它们表达同一件事。

## 长得像不够

原文举了地址验证的例子。客户收货地址和仓库地址，今天都只要求 `Street`、`City`、`PostalCode` 非空。看起来应该抽成一个 `IsValid(Address address)`。

问题是，它们属于不同概念。客户地址和仓库地址只是今天规则一样。明天仓库地址可能要求 `DockCode`，客户地址不需要。于是共享方法开始长参数：

```csharp
public bool IsValid(Address address, bool requireDockCode = false) =>
    !string.IsNullOrWhiteSpace(address.Street) &&
    !string.IsNullOrWhiteSpace(address.City) &&
    !string.IsNullOrWhiteSpace(address.PostalCode) &&
    (!requireDockCode ||
        !string.IsNullOrWhiteSpace(address.DockCode));
```

这个布尔参数就是信号。你当初以为在消除重复，实际上把两个本来会独立演化的概念粘在了一起。再过几轮需求，它可能又多出 `allowPoBox`、`validateRegion`、`requireCountryCode`。最后没人敢改，因为每个调用方都在偷偷依赖某种组合。

## 错误抽象更贵

重复代码的成本是可见的、局部的。你能看到两份副本，也能接受它们未来分叉。

错误抽象的成本更隐蔽。它把多个调用方绑到一个形状上，让每个调用方都为了自己的差异往里面塞开关。共享方法越来越泛，名字越来越虚，最后变成“大家都用，但没人真正理解”的基础设施。

这就是为什么“重复”有时比“错误去重”便宜。重复让差异自然长出来；错误抽象会阻止差异出现，只能靠参数和分支硬撑。

## 边界处最危险

在一个类里抽错 helper，通常只是烦。跨模块抽错，就会变成结构性问题。

原文用 modular monolith 里的 `Billing` 和 `Shipping` 举例。两个模块都有 `Order`，字段也许很像。有人为了消灭重复，把它们拉成一个 `Shared.Orders.Order`：

```csharp
public class Order
{
    public Guid Id { get; set; }
    public string CustomerName { get; set; }
    public decimal Total { get; set; }
}
```

这看起来节省了几个属性，实际把两个 bounded context 焊在一起。Billing 里的订单关心付款、发票、审批；Shipping 里的订单关心地址、包裹、履约。它们面对的是同一个现实对象，但建模视角不同，也应该允许各自演化。

两个模块各自拥有自己的 `Order`，不是重复，而是边界。相似形状不该凌驾于模块自治之上。

## 等第三次

Milan 的实践规则很简单：第二次看到相似代码时，不急着抽。等第三次，再问一个问题：

如果这个规则变化，这几份代码是不是必须一起变？

如果答案是“是”，那就是同一份知识的重复，应该抽出来。DRY 在这里很有价值。

如果答案是“不是”，那只是形状相似。先留着。过早抽象会把不该一起变化的东西绑在一起。

这和 AHA（Avoid Hasty Abstractions）很接近：好抽象往往不是凭空设计出来的，而是从几个具体案例里长出来的。等你能给它一个明确的领域名字时，再抽会稳得多。

一个实用判断是：如果你能把它叫作 `Money`、`TaxRate`、`InvoiceNumber`，这可能是知识；如果只能叫 `Helper`、`Utils`、`ProcessData`，你很可能只是在抽代码形状。

## DRY 什么时候对

DRY 当然不是错的。它错在被机械执行。

原文给了一个真正适合 DRY 的例子：订单超过 `$1,000` 需要经理审批。如果这个规则被复制到 `OrderService`、`CheckoutService`、`AdminController`，迟早会有人只改其中一处，比如把某个地方改成 `$5,000`，线上行为就开始漂移。

这种规则应该有一个家：

```csharp
public bool RequiresManagerApproval() => Total > 1000;
```

这才是 DRY 要保护的东西：同一份业务知识只表达一次。规则变化时，改一个地方，所有依赖这个事实的行为一起更新。

## 可以这样判断

下次想消除重复时，可以先问这几个问题：

- 两段代码只是长得像，还是表达同一个领域事实？
- 如果需求变化，它们是否必须一起变化？
- 它们是否跨了模块、bounded context 或 vertical slice 边界？
- 抽出来之后，名字是否是清晰的领域概念，而不是 `Common` / `Helper` / `Utils`？
- 这个抽象是否已经需要布尔参数来照顾不同调用方？
- 留一点重复，是否能让两个方向更自然地独立演化？

如果答案还不清楚，先不要抽。重复一点，比错绑一起更容易修。

## 收个尾

DRY 的目标不是让代码库看起来没有相似片段，而是让系统里的知识不漂移。相似代码可以先并排存在，直到你确认它们确实代表同一个事实、会一起变化、也能被一个清楚的领域名字表达。

真正要警惕的是 DRY reflex：看到重复就马上抽。工程里很多难维护的 shared helper、common module、可怕基类，都是从这个善意动作开始的。

下一次想删重复时，不要只问“它们看起来一样吗”。先问：“它们表达的是同一份知识吗？”

如果你关注 AI 助手、开发工具和软件工程实践，可以关注 Aide Hub。这里会继续分享能落地的工具教程、技术观察和项目经验。

## 参考

- [DRY Is the Most Misunderstood Rule in Programming](https://www.milanjovanovic.tech/blog/dry-is-the-most-misunderstood-rule-in-programming)
- [The Pragmatic Programmer](https://en.wikipedia.org/wiki/The_Pragmatic_Programmer)
