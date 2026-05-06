---
pubDatetime: 2026-05-06T17:20:00+08:00
title: "什么是不变量，为什么领域模型是执行它们的最佳场所"
description: "本文解释了领域驱动设计中「不变量」的概念，分析了贫血模型散乱执行规则的问题，并通过私有构造器、封装状态转换和聚合根三个策略，展示如何构建始终有效的领域模型，让业务规则真正内聚在对象本身。"
tags: ["DDD", "Domain Model", "C#", ".NET", "Clean Architecture"]
slug: "ddd-invariants-domain-model-enforce"
ogImage: "../../assets/776/01-cover.png"
source: "https://www.milanjovanovic.tech/blog/what-invariants-are-and-why-a-domain-model-is-the-best-place-to-enforce-them"
---

![领域模型封装业务不变量](../../assets/776/01-cover.png)

我们在很多 .NET 代码库里见过同一个模式：业务规则被分散在 Handler、Validator、Controller 里，领域对象本身几乎是一张白纸。这种写法能跑，但它要求每个调用者都记得做正确的检查。时间长了，某个新端点就会悄悄漏掉一个判断，然后数据开始出问题。

这篇文章的出发点就是这里。Milan Jovanović 用「不变量」这个词把问题说清楚了：与其到处散布规则，不如让对象自己保证始终有效。

## 什么是不变量

不变量是关于一个对象的规则，这个规则在对象存在期间必须始终成立。

不是只在保存时检查，不是只在验证器碰巧运行时检查——是只要你持有这个对象的引用，规则就得成立，不管它是怎么被加载进内存的。

几个直接的例子：

- `Course` 始终有非空标题。
- `Order` 的总金额始终等于所有行项目之和。
- `Subscription` 始终处于 `Trial`、`Active`、`PastDue`、`Canceled` 四种状态之一。
- 已发布的课程至少有一节课。

这些规则不涉及 HTTP 请求、数据库持久化或验证框架。它们描述的是领域本身的约束，与代码路径无关。

## 贫血模型的代价

来看一个典型的 CRUD 风格 `Course` 类：

```csharp
public class Course
{
    public string Title { get; set; }
    public CourseStatus Status { get; set; }
    public DateTime? PublishedOn { get; set; }
    public decimal Price { get; set; }
}
```

没有构造器，每个属性都有公开的 setter。为了让数据保持正确，规则被迫散落在各处：

- `CreateCourseValidator` 检查标题不为空。
- `PublishCourseHandler` 设置 `Status` 和 `PublishedOn`，并记得检查课程是否已发布。
- `ChangePriceHandler` 检查课程没有被归档。
- 新的端点出现了，某人复制了一个现有 Handler，归档检查悄悄消失了。

每一条规则都活在某个恰好在请求路径上的地方。`Course` 本身对错误状态毫无防御能力。

这就是贫血模型真正的成本——不是类上没有行为，而是类没有做出任何承诺，所以每个调用者都得自己执行规则。

## 始终有效：让模型成为事实来源

解决思路简单：模型不接受无效状态。只要你持有 `Course` 引用，就可以信任它。三个手段可以做到这一点。

### 1. 阻止构造出无效对象

一个没有标题的 `Course` 不应该存在，最简单的方式是让它在语言层面就无法构造：

```csharp
public class Course
{
    private Course(CourseId id, string title, Money price)
    {
        Id = id;
        Title = title;
        Price = price;
        Status = CourseStatus.Draft;
    }

    public static Result<Course> Create(string title, Money price)
    {
        if (string.IsNullOrWhiteSpace(title))
        {
            return CourseErrors.TitleRequired;
        }

        return new Course(CourseId.New(), title, price);
    }
}
```

私有构造器加静态工厂方法，给了你一个单一的、明确的位置让 `Course` 得以诞生。从这里出来的每个实例，都已经通过了标题校验。之后任何持有 `Course` 引用的代码，都可以假定标题是有效的。

值对象（Value Object）在更小的粒度上应用同样的思路。`Money` 不允许为负数或缺少货币单位，这些约束在构造时就已经固化。

### 2. 封装状态转换

构造锁住之后，下一个薄弱点是状态变更。类自己应该控制它怎么变，而不是把这件事留给持有引用的调用者：

```csharp
public Result Publish(IDateTimeProvider clock)
{
    if (Status != CourseStatus.Draft)
    {
        return CourseErrors.AlreadyPublished;
    }

    if (_lessons.Count == 0)
    {
        return CourseErrors.CannotPublishWithoutLessons;
    }

    Status = CourseStatus.Published;
    PublishedOn = clock.UtcNow;
    return Result.Success();
}
```

Handler 不需要知道课程是否已经发布，也不需要记得检查是否有空课。它只调用 `Publish`，然后传播返回结果。规则就在它保护的状态旁边，一个地方，仅此一处。

### 3. 封装聚合

有些规则横跨同一边界内的多个实体。聚合根（Aggregate Root）是执行这类规则的正确位置，因为它就是事务边界。

看这条规则：已发布的课程必须至少有一节课，而且发布后课程不能删除课时。

错误的做法是把 `Lessons` 暴露为可变集合，指望应用服务在用到它的每个地方都记得规则。正确的做法是把集合设为私有，强制所有变更都通过根来进行：

```csharp
public sealed class Course
{
    private readonly List<Lesson> _lessons = [];
    public IReadOnlyCollection<Lesson> Lessons => _lessons.AsReadOnly();

    public Result RemoveLesson(LessonId id)
    {
        if (Status == CourseStatus.Published)
        {
            return CourseErrors.CannotModifyPublishedLessons;
        }

        var lesson = _lessons.FirstOrDefault(l => l.Id == id);
        if (lesson is null)
        {
            return CourseErrors.LessonNotFound;
        }

        _lessons.Remove(lesson);
        return Result.Success();
    }
}
```

如果一条规则需要横跨两个聚合，那是另一个问题，应该用领域事件来处理，而不是让一个聚合直接插手另一个的内部。

## 你真正得到的

用程序式代码写同样的系统也能运转良好，你放弃的是「信任」。

程序式系统里，每个调用者共同承担不破坏规则的责任。始终有效的模型里，这份责任落在领域模型上。差异会随时间复利：

- 验证器不会漂移，因为没有重复的东西可以漂移。
- 代码评审聚焦于行为，而不是「我们有没有漏掉某个检查？」。
- 新端点不可能绕过活在实体上的规则。
- 测试不再需要覆盖那些在模型层面根本无法表达的场景。

这从根本上是封装的问题。模型封装了管理自身状态的规则，系统的其余部分通过定义良好的接口与之交互。

## 小结

不变量是对象存在期间必须始终成立的规则，执行它们最干净的地方就是对象本身。

- 构造不变量：放在私有构造器后面的工厂方法里。
- 状态转换不变量：放在拥有对应状态的方法里。
- 聚合级别不变量：放在聚合根上，子实体只通过根来访问。

你放弃的是短期内也许更容易理解的程序式代码的自由，得到的是一个可以信任始终有效的模型。

## 参考

- [What Invariants Are (and Why a Domain Model Is the Best Place to Enforce Them)](https://www.milanjovanovic.tech/blog/what-invariants-are-and-why-a-domain-model-is-the-best-place-to-enforce-them)
- [Refactoring from an Anemic Domain Model to a Rich Domain Model](https://www.milanjovanovic.tech/blog/refactoring-from-an-anemic-domain-model-to-a-rich-domain-model)
- [Value Objects in .NET DDD Fundamentals](https://www.milanjovanovic.tech/blog/value-objects-in-dotnet-ddd-fundamentals)
- [How to Use Domain Events to Build Loosely Coupled Systems](https://www.milanjovanovic.tech/blog/how-to-use-domain-events-to-build-loosely-coupled-systems)
