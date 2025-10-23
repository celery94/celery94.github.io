---
pubDatetime: 2025-04-26 16:25:55
tags: [".NET", "Architecture"]
slug: refactor-bounded-contexts-dotnet
source: https://www.milanjovanovic.tech/blog/refactoring-overgrown-bounded-contexts-in-modular-monoliths
title: 拆解臃肿的Bounded Context：.NET模块化单体架构重构实战
description: 本文结合.NET技术栈，深入解析如何识别并重构模块化单体架构中边界失控的领域上下文，助力开发者打造高内聚、低耦合的企业级系统。
---

# 拆解臃肿的Bounded Context：.NET模块化单体架构重构实战

> 👨‍💻 你是否在.NET项目中遇到过“一个服务包打天下”，但久而久之变成一团乱麻的局面？本文将带你走出困境，手把手教你如何识别和重构那些“越界”的Bounded Context，助你构建真正可维护、可扩展的模块化单体应用。

---

## 引言：当模块化单体“失控”时

随着业务发展，不少采用模块化单体（Modular Monolith）架构的.NET系统，会逐渐出现“边界膨胀”问题。原本清晰的业务分层，慢慢演变为一个巨大的、难以维护的上下文（Bounded Context），用户管理、账单、通知、报表等逻辑全都堆在同一个类或服务里。

你是不是也有过这样的痛点？

- 一改动就牵一发动全身，生怕哪儿又被“牵连”出BUG
- 一个实体被四五种毫不相干的业务场景反复引用
- Service类动辄上千行，业务逻辑混杂在一起
- 子域（Subdomain）间的边界早已模糊不清

如果你中了上述几条，不妨看看本文，教你用实际.NET代码，逐步拆解臃肿上下文，让你的架构焕然一新！

---

## 正文：重构Overgrown Bounded Context的四步法

### 1️⃣ 识别臃肿上下文：看清你的领域边界

先来看看典型的“超载”场景。比如下面这个BillingService，看似名为账单，却什么都管：

```csharp
public class BillingService
{
    public void ChargeCustomer(int customerId, decimal amount) { ... }
    public void SendInvoice(int invoiceId) { ... }
    public void NotifyCustomer(int customerId, string message) { ... }
    public void GenerateMonthlyReport() { ... }
    public void DeactivateUserAccount(int userId) { ... }
}
```

问题在哪？  
Billing、Notification、Reporting、User Management全混在一起。任何功能改动，都可能引发连锁反应，极易踩坑。

> **判断标准：**
>
> - 哪些代码经常一起改动？
> - 不同子域是否有各自独立术语和业务目标？
> - 你会愿意把这些业务分给不同的小组负责吗？

如果答案是“是”，那就说明该拆了！

### 2️⃣ 拆解第一步：选一个低风险上下文先动手

建议从“副作用型”逻辑下手，比如Notification。  
因为通知通常不影响主业务流程，拆解起来最安全。

**新建Notifications模块：**

```csharp
public class NotificationService
{
    public void Send(int customerId, string message) { ... }
}
```

**简化BillingService：**

```csharp
public class BillingService
{
    private readonly NotificationService _notificationService;
    public BillingService(NotificationService notificationService)
    {
        _notificationService = notificationService;
    }

    public void ChargeCustomer(int customerId, decimal amount)
    {
        // 账单逻辑...
        _notificationService.Send(customerId, $"You were charged ${amount}");
    }
}
```

这样虽然实现了职责分离，但Billing还是依赖Notification。如果Notification挂了，Billing也跟着崩。这还不够“模块化”。

**升级：使用领域事件（Domain Events）彻底解耦！**

```csharp
public class CustomerChargedEvent
{
    public int CustomerId { get; init; }
    public decimal Amount { get; init; }
}

// Billing模块
public class BillingService
{
    private readonly IDomainEventDispatcher _dispatcher;
    public BillingService(IDomainEventDispatcher dispatcher)
    {
        _dispatcher = dispatcher;
    }

    public void ChargeCustomer(int customerId, decimal amount)
    {
        // 账单逻辑...
        _dispatcher.Dispatch(new CustomerChargedEvent
        {
            CustomerId = customerId,
            Amount = amount
        });
    }
}

// Notifications模块
public class CustomerChargedEventHandler : IDomainEventHandler<CustomerChargedEvent>
{
    public Task Handle(CustomerChargedEvent @event)
    {
        // 发送通知
    }
}
```

此时，Billing完全不知道Notification的存在，实现了真正的低耦合高内聚！

---

### 3️⃣ 数据迁移：领域模型与数据库解耦

很多单体系统初期只有一个数据库。但要实现真正的领域隔离，每个模块应该控制自己的数据结构。

**实操建议：**

- 每个子模块维护独立DbContext
- 渐进式迁移表结构到不同schema
- 跨域读取用只读视图或投影解决

```csharp
// Billing模块
public class BillingDbContext : DbContext
{
    public DbSet<Invoice> Invoices { get; set; }
}
// Notifications模块
public class NotificationsDbContext : DbContext
{
    public DbSet<Log> Logs { get; set; }
}
```

可以先让两个Context都读同一套表，待新模块稳定后再迁移写入逻辑。

---

### 4️⃣ 重复迭代：逐个拆解其它子域

有了模板，就可以依次对Reporting、User Management等继续拆分：

**重构前：**

```csharp
billingService.GenerateMonthlyReport();
billingService.DeactivateUserAccount(userId);
```

**重构后：**

```csharp
reportingService.GenerateMonthlyReport();
userService.DeactivateUser(userId);
```

或使用事件驱动：

```csharp
_dispatcher.Dispatch(new MonthEndedEvent());
_dispatcher.Dispatch(new UserInactiveEvent(userId));
```

> 🧑‍🔬 **小结：**
>
> - 每个模块只做一件事（Single Responsibility）
> - 清晰边界+独立演进+更易测试和维护
> - 真正的“模块化”，不用微服务也能实现！

---

## 结论：让你的单体系统活得更久、更健壮！

通过以上四步，你将获得：

- 高内聚、低耦合的小服务，每个聚焦一件事
- 独立演进、易于测试和调试的模块体系
- 代码和数据库都能体现真实业务边界

记住：“单体”并不等于“一锅粥”。只要用心设计，照样能拥有媲美微服务的灵活与可维护性！
