---
pubDatetime: 2026-06-15T07:29:14+08:00
title: "C# 单一职责原则：一个类，一个变更理由"
description: 单一职责原则（SRP）是 SOLID 的起点。本文从 Actor 视角重新解读 SRP，结合反例拆解和重构代码演示，讲清楚为什么一个类只应该为一个角色而变，以及如何在 .NET 10 的日常开发中落地。
tags: ["C#", "SOLID", "SRP", ".NET"]
slug: "srp-csharp-guide"
ogImage: "../../assets/875/01-cover.png"
source: "https://www.devleader.ca/2026/06/11/single-responsibility-principle-c-one-class-one-reason-to-change"
---

大多数开发者第一次感受到单一职责原则（SRP），不是从书本上学到的，而是在一个没人遵守它的代码库里被撞得头破血流。

你打开项目，看到一个 `UserService`，里面同时做着身份认证、用户资料更新、邮件发送和审计日志。再看一个 `ReportHelper`，查数据库、格式化输出、写磁盘文件、发 Slack 通知，全部挤在一起。类体量膨胀到一千两百行，构造函数需要塞八个参数才能实例化。

SRP 是 SOLID 五个原则中的第一个，也是最值得先拿下的一个。把它用扎实了，另外四个原则会自然变容易。忽视它，你就是在给自己挖坑——每一周这个坑的修复成本都在上涨。

这篇文章要说清楚三件事：SRP 里那个「变更理由」到底指什么；怎么在 C# 代码里识别违规并拆解；.NET 10 有哪些特性天然支持单一职责设计。

---

## 「变更理由」到底指什么

形式上的定义非常简洁：一个类应该有且只有一个变更的理由。

容易让人卡住的是「理由」两个字。

它不是「一个方法」，也不是机械意义上的「一个责任」。Robert C. Martin 的核心洞见是：**「理由」映射到的是一个角色（actor）**——一个具体的人、一个角色、一个团队、一个利益相关方，他们提出的需求变动会直接触发这个类的修改。

看一个例子：一个类有三个方法——凭证校验、邮件模板渲染、数据库记录写入。鉴权逻辑属于安全团队，邮件模板归市场团队管，数据库 schema 变更由基础设施团队推动。三个不同的团队，各自独立地可以提一个 ticket，强迫你去打开同一个类文件。这就是三个变更理由。

视角一变，问题就从「这个类是不是做太多了」变成了「多少个不同的利益相关方能迫使这个类改变」。理想情况下只对应一个主要角色。用这个镜头去审视代码，违规变得很容易发现——也不太好找借口搪塞过去。

当然，Actor 启发法是个实用的观察窗口，但真实代码经常位于紧密相关的关注点交界处，判断力仍然不能被替代。

---

## 内聚与耦合：SRP 到底改善了谁

SRP 经常被当作哲学式的设计原则来讨论。但归根到底，它改善的是两个可度量的属性：**内聚**和**耦合**。

**内聚**衡量一个类内部的职责之间有多大关联。`UserRepository` 里有 `FindById`、`FindByEmail`、`Save`、`Delete`——四个方法全部服务于「用户数据持久化」这一个目标，内聚很高。低内聚就是杂货铺类：一个 `ApplicationHelper` 堆满了八竿子打不着的工具方法，或者一个 Service 类同时处理三个独立业务操作，只不过它们碰巧涉及同一个实体。

**耦合**衡量一个类对另一个类内部细节的依赖程度。高耦合意味着变更会无法预判地扩散——修一处炸五处。低耦合意味着类之间相互独立，改一个地方不会意外牵连其他地方。

SRP 同时改善这两个属性。当一个类承担单一职责，它的所有方法天然彼此相关——高内聚。因为它只做一件聚焦的事，更少的其他类会为了不相干的理由依赖它——低耦合。

这不是需要在二者之间做取舍的目标。一个 SRP 使用得当的类，天然地同时具备高内聚和低耦合。它们是一枚硬币的两面，而 SRP 就是保持它们对齐的那个力量。

---

## 重构实例：拆解一个臃肿的 UserService

下面是一个在真实项目里随时可见的 SRP 违规。一个 `UserService` 同时管着认证、资料持久化、邮件通知和审计日志：

```csharp
// 违规：四个截然不同的关注点挤在一个类里
public class UserService
{
    private readonly string _connectionString;
    private readonly string _smtpServer;

    public UserService(string connectionString, string smtpServer)
    {
        _connectionString = connectionString;
        _smtpServer = smtpServer;
    }

    // 关注点 1：身份认证
    public bool ValidateCredentials(string username, string password)
    {
        using var conn = new SqlConnection(_connectionString);
        // 对传入密码做哈希并与数据库中的值比对
        return true;
    }

    // 关注点 2：用户资料持久化
    public void UpdateProfile(string userId, string displayName, string email)
    {
        using var conn = new SqlConnection(_connectionString);
        // 对 users 表执行 UPDATE
    }

    // 关注点 3：发送邮件
    public void SendPasswordResetEmail(string email, string resetToken)
    {
        using var client = new SmtpClient(_smtpServer);
        var message = new MailMessage(
            "noreply@example.com", email,
            "Reset your password",
            $"Use this token to reset your password: {resetToken}");
        client.Send(message);
    }

    // 关注点 4：审计日志（写入同一个数据库的日志表）
    public void LogUserEvent(string userId, string eventType, string details)
    {
        using var conn = new SqlConnection(_connectionString);
        // INSERT INTO AuditLog (UserId, EventType, Details, Timestamp)
    }
}
```

四个不同团队分别管着四个方法。市场设计师改密码重置邮件的模板，会和后端工程师改凭证哈希算法的改动落在同一个文件上。要在隔离环境中测试凭证校验逻辑，你居然需要配一个可用的 SMTP 服务器。这里每一次改动都在赌。

下面是应用 SRP 之后的拆解版本：

```csharp
// 单一职责：只管认证
public interface IAuthenticationService
{
    bool ValidateCredentials(string username, string password);
    string GeneratePasswordResetToken(string userId);
}

// 单一职责：只管用户数据持久化
public interface IUserRepository
{
    void UpdateProfile(string userId, string displayName, string email);
    User? FindById(string userId);
}

// 单一职责：只管发消息通知
public interface IEmailService
{
    void SendPasswordResetEmail(string email, string resetToken);
    void SendWelcomeEmail(string email, string displayName);
}

// 干净的实现——只依赖它真正需要的东西
public class AuthenticationService : IAuthenticationService
{
    private readonly IUserRepository _users;
    private readonly ILogger<AuthenticationService> _logger;

    public AuthenticationService(IUserRepository users, ILogger<AuthenticationService> logger)
    {
        _users = users;
        _logger = logger;
    }

    public bool ValidateCredentials(string username, string password)
    {
        var user = _users.FindById(username);
        if (user is null) return false;

        var valid = BCrypt.Net.BCrypt.Verify(password, user.PasswordHash);
        _logger.LogInformation("Auth attempt for {Username}: {Result}",
            username, valid ? "success" : "failed");

        return valid;
    }

    public string GeneratePasswordResetToken(string userId)
    {
        // 32 字节密码学随机 token
        return Convert.ToBase64String(RandomNumberGenerator.GetBytes(32));
    }
}
```

现在每个接口映射到一个关注点、一个利益相关方。`AuthenticationService` 只在认证逻辑变化时才会变。`IEmailService` 只在通知需求变化时才会变。它们各自编译、各自测试、各自部署。

值得留意的是，`ILogger<T>` 本身就是框架内置的 SRP 范例——一个只做一件事的抽象：发出日志事件，其他什么都不碰。如果你在拆出的服务里引入结构化日志，Serilog 提供可组合的 sink，每个 sink 只管一个输出目标——这是 SRP 在基础设施层面的另一种体现。

---

## 容易踩的 SRP 违规模式

知道原则是一回事，在真实代码里发现违规是另一回事。以下是在生产代码库中最频繁出现的几种模式：

**上帝类**。类体量超过 500 行、方法超过 15 个，名字以 `Manager`、`Handler` 或 `Service` 结尾，但其实有更精确的名字可以使用。这些类是一次一个需求、一次一个 PR 把职责慢慢堆上去的，等回过神来已经重到不敢重构了。

**工具类**。一个静态的 `Utils`、`Helpers` 或 `Extensions` 类，变成了代码垃圾桶。所有「不知道该放哪」的方法最后都丢到这里。累积到一定程度，它触及项目里一半的文件，每个 sprint 都可能因为完全不同的原因需要修改它。

**业务逻辑和持久化混在一起**。一个类既有业务规则，又直接发 SQL 或操作 `DbContext`。ORM 变更时要改这个类，业务规则变更时也要改这个类。同一个文件里塞了两个变更理由。

**构造函数参数膨胀**。一个类需要六个或更多构造函数参数，这是一个值得停下来审视的信号——但它是信号，不是绝对规则。每个参数代表一个依赖，依赖太多通常意味着关注点太多，但它提示你仔细看看。不要把它当成自动判定违规的阈值。

**方法不引用实例字段**。如果一个方法从不用到所属类自己的字段或其他实例方法，这个方法是时候搬家了。

---

## .NET 10 中的 SRP 实用启发法

落地 SRP 不只是代码结构练习——关键在于设计阶段问对问题。

**「谁会申请改这个？」测试**。对类里的每个方法追问：哪个团队或角色会提一个 ticket 要求改这个方法？如果答案在不同方法上不一致，就是 SRP 违规。这是实践中最可靠的启发法。

**命名测试**。你能用一个精确的名词短语描述这个类的职责吗？`UserRepository` 清楚。`UserManager` 是警告信号——「管理」到底是什么意思？`UserHelper` 基本就是红旗了。模糊的名字几乎一定意味着下面藏着混合的关注点。

**方法数量测试**。超过八到十个公开方法的类值得用放大镜看一下。数一数哪些方法明显属于同类工作，哪些方法只是松松散散地搭在一起。不是硬性规则，但是个好用的快速过滤器。

C# 9 起引入的 positional record（.NET 10 继续支持）在数据载体上天然强制了 SRP：

```csharp
// Record 就一件事：在层与层之间搬运数据
public record UserProfile(string UserId, string DisplayName, string Email);
public record AuthResult(bool Success, string? ErrorMessage);
public record PasswordResetToken(string Token, DateTimeOffset ExpiresAt);

// 业务逻辑不放进来——record 明确就是数据载体
// 类型系统本身就在传达意图：这是数据，不是行为
```

用 LINQ 做数据转换时，把投影和过滤逻辑放到查询对象或者仓库里，而不是撒在已经承担了其他职责的编排类中。

当多个专注的服务需要协调时，Mediator 模式可以在不把服务直接捆绑在一起的前提下完成编排。每一个 handler 只处理一个命令或事件——SRP 被结构本身强制执行。

---

## SRP 与依赖注入

SRP 和依赖注入（DI）是天然盟友。它们相互强化，让对方的违规变得异常显眼。

当一个类遵守 SRP，它的构造函数是窄的。它只需要服务那个单一关注点所需的依赖。DI 注册也干净：一个指向明确的接口，一个聚焦的实现。解析这个类很快。用 mock 测试它很轻松。

当一个类违反 SRP，DI 注册马上就会发出信号。这个类需要六个接口。其中某些接口只在它的十二个方法中的两个里被用到。DI 容器在每一次请求时都会解析全部。依赖图开始长得像一张蜘蛛网。

下面是 SRP 合规的 DI 注册：

```csharp
var builder = WebApplication.CreateBuilder(args);

// 每行一条：接口 → 聚焦的实现，各管一件事
builder.Services.AddScoped<IUserRepository, SqlUserRepository>();
builder.Services.AddScoped<IAuthenticationService, AuthenticationService>();
builder.Services.AddScoped<IEmailService, SmtpEmailService>();
builder.Services.AddScoped<IPasswordResetService, PasswordResetService>();
builder.Services.AddScoped<IAuditLogger, DatabaseAuditLogger>();
builder.Services.AddLogging();

var app = builder.Build();
```

每一行只说一件事：这是接口，这是它专一的实现。容器组装出一个由专家组成的系统。这个注册列表里的每一个类都可以独立测试、独立替换，在正确的架构下甚至可以独立部署。

SRP 和 DI 在模块层面也有关联。在构建 C# 模块化单体时，每个模块的 DI 注册面描述了自己的职责。如果一个模块里的服务跨越了多个不相干的业务能力，值得审视其中是否存在混合的关切——关键问题是这些服务能否映射到一个一致的、可由单个团队拥有的领域。SRP 的尺度从单个方法一路延伸到架构模块。

---

## 常见问题

**Q：单一职责原则用一句话怎么说？**

一个类做一件事，只有一个让它改变的理由。当一个类扛着多件事，它就难测试、难安全修改、难理解。SRP 推着你把大类拆成小而聚焦的协作者，各自管好一个关注点。

**Q：怎么判断一个类违反 SRP？**

问一句：多少个不同团队或角色能独立要求你修改这个类？超过一个，基本就是违规。其他值得审视的信号：类名以 `Manager`、`Helper`、`Handler` 结尾但其实有更精确的名字；构造函数参数超过六个（是信号，不是阈值）；测试文件需要 mock 十几个接口才能实例化这个类。

**Q：SRP 是不是意味着每个类只能有一个方法？**

不是。一个类可以有多个方法仍然遵守 SRP。`UserRepository` 有 `FindById`、`FindByEmail`、`Save`、`Delete`——完全合规，四个方法都服务于「数据持久化」这同一个关注点。单一职责指的是关注点，不是方法数量。

**Q：SRP 和关注点分离是同一回事吗？**

密切相关但不完全相同。关注点分离（SoC）是更上层的架构指南——把系统里不同的方面拆开，比如表示层、业务逻辑、持久化。SRP 更细粒度——每个类只应该有一个变更理由。SRP 本质上就是 SoC 下探到类层面。两者指向同一个方向，互相强化。

**Q：S RP 要遵守到什么程度？**

务实很重要。一个格式化货币字符串的小工具方法不需要自己的专用类。SRP 在复杂、频繁变更的业务逻辑上回报最大——服务类、领域对象、编排代码。把力气花在违规真的会造成维护痛苦的地方，而不是为了「原则」而制造不必要的间接层。

**Q：SRP 会让代码更难导航吗？**

初看可能确实会。更多文件、更多类型、更多跳转。但它用浅层的导航摩擦换来了深层的维护痛苦。在大代码库里，知道 `EmailService` 只管邮件逻辑——别无其他——价值巨大。替代方案是在一个一千二百行的上帝类里翻找它三十个方法中的哪一个正在触发生产事故。

**Q：SRP 和开闭原则是什么关系？**

直接的正向关系。一旦类有了单一职责，不修改就能扩展变得容易得多。你可以通过添加实现同一接口的新类来扩展行为——而不是往已经塞得很满的类里再加一个方法。SRP 让 OCP 在实践中变得可行。关注点混杂的类让 OCP 几乎不可能，因为任何扩展都不可避免地碰触到不相干的东西。

---

## C# 单一职责原则实践小结

单一职责原则是面向对象清晰设计的起点。不是因为它在技术上最困难——恰恰相反，它相当朴素——而是因为其他所有原则都依赖它。小而聚焦的类是可测试的、可 mock 的、可独立部署的。它们容易命名、容易找到、容易交给一个没有参与初始开发的同事接手。

下次写一个类时，先问自己一个问题：**这个类负责的唯一一件事是什么？** 如果答案里出现了「和」或者「以及」，那你手头还有活要干。

把 SRP 用扎实了，SOLID 的其他四个原则自然会顺势到位。

---

## 参考

- [Single Responsibility Principle C#: One Class, One Reason to Change — Dev Leader](https://www.devleader.ca/2026/06/11/single-responsibility-principle-c-one-class-one-reason-to-change)
- [SOLID Principles C# Guide — Dev Leader](https://www.devleader.ca/2025/01/06/solid-principles-csharp/)
