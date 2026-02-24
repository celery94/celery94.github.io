---
pubDatetime: 2026-02-24
title: "垂直切片在模块化单体架构中的定位"
description: "模块化单体解决的是系统分解为模块的宏观问题，垂直切片架构解决的是模块内部按功能组织代码的微观问题。两者层级不同，可以灵活组合使用。"
tags: [".NET", "Architecture", "Modular Monolith", "Vertical Slice Architecture", "Clean Architecture"]
slug: "vertical-slices-in-modular-monolith"
source: "https://www.milanjovanovic.tech/blog/where-vertical-slices-fit-inside-the-modular-monolith-architecture"
---

大多数团队能把宏观架构做对，他们构建出模块化单体，设定清晰的模块边界、公共 API 和适当的数据隔离。

但之后就不再思考架构了。每个模块都采用相同的内部结构，通常是某种形式的分层架构。

实际上，Clean Architecture 和垂直切片架构 (Vertical Slice Architecture，VSA) 并没有人们想象的那么大的差距。两者都聚焦于用例，并追求高内聚。Clean Architecture 只是额外增加了依赖方向的规则，这往往会带来更多的抽象和仪式感。务实的 Clean Architecture 则取了一个折中方案，本质上与 VSA 非常相似。

真正的问题不在于哪个"更好"，而在于每种方式在你的模块化单体中最适合哪些场景。最妙的是，你完全可以混合使用。

## 架构的两个层级

构建模块化单体时，你需要做出两个架构决策：

1. **宏观架构** - 如何将系统分解为模块？涵盖模块边界、通信模式、数据隔离、公共 API 设计，以及模块的部署方式。
2. **微观架构** - 如何组织每个模块内部的代码？涵盖目录结构、依赖方向、用例实现方式、校验逻辑的位置，以及数据库访问方式。

大多数关于模块化单体的文章完全聚焦于宏观层面，这也合理，因为模块边界划分错误的修复代价很高。

但微观层面同样重要。它决定了在模块内部添加功能、浏览代码和新成员上手的难易程度。这才是团队每天直接打交道的架构。

关键认知在于：

> 宏观架构约束模块之间的交互方式，微观架构则是每个模块可以独立做出的局部决策。

你的 `Ticketing` 模块不必和 `Notifications` 模块遵循相同的内部结构。模块边界赋予了你这种自由。

## 垂直切片不等同于模块

有人会把垂直切片和模块混为一谈。在宏观层面，一个模块看起来确实像业务领域的一个"垂直切片"。但这种类比在应用层面站不住脚。

模块是一个限界上下文 (Bounded Context)。它拥有自己的数据，暴露公共 API，封装一个业务能力。垂直切片则是一种功能实现模式，它将请求、处理器、校验和数据访问归组到单个用例中。

模块和垂直切片运作在不同层级。模块定义系统的边界，垂直切片组织这些边界内的代码。

## 模块内部的垂直切片

垂直切片架构按功能而非技术层来组织代码。每个功能都是一个自包含单元：请求、处理器、校验、数据访问，全部放在一起。

在模块化单体的模块内部，这是一种天然的契合。模块边界已经强制与系统其他部分隔离，不需要层来保护你，模块的公共 API 承担了这个角色。

以下是 `Ticketing` 模块使用垂直切片、每个功能一个文件的结构：

```
📁 Modules/
|__ 📁 Ticketing
    |__ 📁 Features
        |__ 📁 AddItemToCart
            |__ #️⃣ AddItemToCart.cs
        |__ 📁 SubmitOrder
            |__ #️⃣ SubmitOrder.cs
        |__ 📁 GetOrder
            |__ #️⃣ GetOrder.cs
        |__ 📁 CancelOrder
            |__ #️⃣ CancelOrder.cs
        |__ 📁 RefundPayment
            |__ #️⃣ RefundPayment.cs
    |__ 📁 Data
        |__ #️⃣ TicketingDbContext.cs
    |__ 📁 Entities
        |__ #️⃣ Order.cs
        |__ #️⃣ Ticket.cs
    |__ #️⃣ ITicketingModule.cs
    |__ #️⃣ TicketingModule.cs
```

也可以按组件拆分为更细粒度的文件：

```
📁 Modules/
|__ 📁 Ticketing
    |__ 📁 Features
        |__ 📁 SubmitOrder
            |__ #️⃣ SubmitOrderRequest.cs
            |__ #️⃣ SubmitOrderResponse.cs
            |__ #️⃣ SubmitOrderHandler.cs
            |__ #️⃣ SubmitOrderValidator.cs
            |__ #️⃣ SubmitOrderEndpoint.cs
        |__ 📁 GetOrder
            |__ #️⃣ GetOrderRequest.cs
            |__ #️⃣ GetOrderResponse.cs
            |__ #️⃣ GetOrderHandler.cs
            |__ #️⃣ GetOrderEndpoint.cs
    |__ 📁 Data
    |__ 📁 Entities
    |__ #️⃣ ITicketingModule.cs
    |__ #️⃣ TicketingModule.cs
```

两种方式都将功能的所有内容放在同一个目录下。对比 `Application`、`Domain`、`Infrastructure` 目录下分散的大量文件，垂直切片的版本扁平、直观、易于浏览。

下面是一个使用静态类将功能组件集中在一起的具体示例：

```csharp
public static class SubmitOrder
{
    public record Request(string CartId);
    public record Response(string OrderId, decimal Total);

    public class Validator : AbstractValidator<Request>
    {
        public Validator()
        {
            RuleFor(x => x.CartId).NotEmpty();
        }
    }

    public class Endpoint : IEndpoint
    {
        public void MapEndpoint(IEndpointRouteBuilder app)
        {
            app.MapPost("orders", Handler).WithTags("Ticketing");
        }

        public static async Task<IResult> Handler(
            Request request,
            IValidator<Request> validator,
            TicketingDbContext context)
        {
            var result = validator.Validate(request);
            if (!result.IsValid)
            {
                return Results.BadRequest(result.Errors);
            }

            var cart = await context.Carts
                .Include(c => c.Items)
                .FirstOrDefaultAsync(c => c.Id == request.CartId);

            if (cart is null)
            {
                return Results.NotFound();
            }

            var order = Order.Create(cart);

            context.Orders.Add(order);
            await context.SaveChangesAsync();

            return Results.Ok(
                new Response(order.Id, order.Total));
        }
    }
}
```

添加新功能就意味着添加一个新目录。不需要修改跨层的共享代码，不必担心副作用。

## 如何选择内部架构

一个常见误解是 VSA 只适合简单模块，而 Clean Architecture 适合复杂模块。事实并非如此。

垂直切片同样能很好地配合丰富的领域模型。你可以在垂直切片中使用领域实体、值对象和领域事件。切片负责组织入口点和编排逻辑，领域模型负责处理业务规则。随着切片复杂度增长，你可以将逻辑下沉到领域层，这和在 Clean Architecture 中的做法一样。

同样，务实的 Clean Architecture 对简单模块也能很好地运作。当领域较简单时，结构也很轻量。

所以这个决策与复杂度无关，关键在于你的团队更熟悉什么、什么能带来最大的清晰度。

以下是几个可以参考的维度：

- **团队熟悉度** - 如果你的团队已经习惯按层和依赖方向思考，Clean Architecture 会让他们感觉很自然。如果他们更倾向于按功能组织，VSA 能减少摩擦。
- **共享的领域逻辑** - 当多个用例共享相同的领域实体时，独立的 `Domain` 层能让这种共享更加明确。使用 VSA 时，你可以将共享逻辑提取到一个单独的目录下，这同样可行。
- **功能的独立性** - 当功能之间大多彼此独立，很少共享行为时，垂直切片能保持简洁。每个功能自包含，心理模型简单直接。

无论你在模块内部选择什么方案，模块边界都会保护系统的其他部分。所以选择能让团队最高效的方式，并在模块演进过程中保持调整的意愿。

## 总结

模块化单体解决的是宏观问题：如何将系统分解为边界清晰的模块。垂直切片架构解决的是微观问题：如何在这些模块内部按功能组织代码。

两者运作在不同层级。模块化单体在每个模块内部带来高内聚，并帮助管理模块之间的耦合。垂直切片架构在模块内部的每个功能层面带来高内聚。

你不必为整个系统选择同一种内部架构。每个模块都可以选择最适合自身上下文的方式。有些模块会使用 Clean Architecture，另一些则使用垂直切片。定义良好的模块边界让这一切成为可能。
