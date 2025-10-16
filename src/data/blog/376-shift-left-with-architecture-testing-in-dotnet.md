---
pubDatetime: 2025-06-19
tags: [".NET", "Architecture", "Testing"]
slug: shift-left-with-architecture-testing-in-dotnet
source: https://www.milanjovanovic.tech/blog/shift-left-with-architecture-testing-in-dotnet
title: Shift Left With Architecture Testing in .NET —— 用架构测试守护你的代码质量
description: 本文详解如何通过.NET中的架构测试工具，提前发现并预防架构腐化和技术债务，助力团队持续交付高质量软件。
---

# Shift Left With Architecture Testing in .NET 用架构测试守护你的代码质量

## 引言

在.NET项目开发中，随着业务复杂度提升和团队成员变动，最初精心设计的软件架构往往会逐步演变为混乱不堪的“泥球（Big Ball of Mud）”结构，带来维护难、扩展难、Bug频发等问题。本文将介绍如何通过架构测试（Architecture Testing），结合“左移测试”（Shift Left）理念，把架构约束前置到开发流程的早期阶段，最大限度降低技术债务，确保项目架构健康可持续发展。

## 背景

### 技术债务的困扰

技术债务是指为了追求短期交付速度，在代码设计和实现上做出的权衡和妥协（比如临时修复、架构破坏、命名混乱等），最终导致后期维护和扩展成本大幅增加。尽管大多数开发者都有保持代码整洁的意愿，但现实中的时间压力、沟通障碍和知识鸿沟等因素，常常让理想的架构慢慢变形甚至失控。

#### 技术债务的典型表现

- 功能新增难度上升
- Bug 层出不穷
- 新人接手无从下手
- 系统架构混乱无序

## 技术原理

### 什么是架构测试？

架构测试是一种自动化测试手段，用来检查代码是否遵循既定的架构规则和设计规范。其核心目标是在代码进入主干、发布上线之前，及时发现并阻止架构违规行为。

> **Shift Left Testing（左移测试）**  
> 指将质量保障环节提前到开发流程的更早阶段（如编码、提交），而不是等到集成或上线后才发现问题。

### 架构测试的作用

- 防止层间或模块间出现不合法依赖
- 保证命名、继承、封装等设计规范得到落实
- 第一时间向开发者反馈架构违规信息
- 与CI/CD流水线集成，实现持续自动守护

## 实现步骤

### 1. 选择合适的架构测试工具

.NET 生态下常用的架构测试库包括：

- [NetArchTest](https://github.com/BenMorris/NetArchTest)（本文主要示例）
- [ArchUnitNET](https://github.com/TNG/ArchUnitNET)

### 2. 明确项目的核心架构规则

常见场景：

- 模块间不能直接相互依赖，只能通过公共接口或事件通信
- 内层（Domain）不能依赖外层（Application/Infrastructure）
- 特定类型必须是sealed类、命名规范等

### 3. 编写架构测试用例

以xUnit为例，将架构规则以单元测试方式固化：

#### 模块单向依赖约束（Modular Monolith）

```csharp
[Fact]
public void TicketingModule_ShouldNotHaveDependencyOn_AnyOtherModule()
{
    string[] otherModules = { UsersNamespace, EventsNamespace, AttendanceNamespace };
    string[] integrationEventsModules = { UsersIntegrationEventsNamespace, EventsIntegrationEventsNamespace, AttendanceIntegrationEventsNamespace };

    List<Assembly> ticketingAssemblies = {
        typeof(Order).Assembly,
        Modules.Ticketing.Application.AssemblyReference.Assembly,
        Modules.Ticketing.Presentation.AssemblyReference.Assembly,
        typeof(TicketingModule).Assembly
    };

    Types.InAssemblies(ticketingAssemblies)
        .That()
        .DoNotHaveDependencyOnAny(integrationEventsModules)
        .Should()
        .NotHaveDependencyOnAny(otherModules)
        .GetResult()
        .ShouldBeSuccessful();
}
```

#### Clean Architecture层间依赖约束

```csharp
[Fact]
public void DomainLayer_ShouldNotHaveDependencyOn_ApplicationLayer()
{
    Types.InAssembly(DomainAssembly)
        .Should()
        .NotHaveDependencyOn(ApplicationAssembly.GetName().Name)
        .GetResult()
        .ShouldBeSuccessful();
}

[Fact]
public void ApplicationLayer_ShouldNotHaveDependencyOn_InfrastructureLayer()
{
    Types.InAssembly(ApplicationAssembly)
        .Should()
        .NotHaveDependencyOn(InfrastructureAssembly.GetName().Name)
        .GetResult()
        .ShouldBeSuccessful();
}
```

#### 设计规范强制（如事件类型必须sealed）

```csharp
[Fact]
public void DomainEvents_Should_BeSealed()
{
    Types.InAssembly(DomainAssembly)
        .That()
        .ImplementInterface(typeof(IDomainEvent))
        .Or()
        .Inherit(typeof(DomainEvent))
        .Should()
        .BeSealed()
        .GetResult()
        .ShouldBeSuccessful();
}
```

#### 构造函数可见性约束（防止实体类被随意new）

```csharp
[Fact]
public void Entities_ShouldOnlyHave_PrivateConstructors()
{
    IEnumerable<Type> entityTypes = Types.InAssembly(DomainAssembly)
        .That()
        .Inherit(typeof(Entity))
        .GetTypes();

    var failingTypes = new List<Type>();
    foreach (Type entityType in entityTypes)
    {
        ConstructorInfo[] constructors = entityType
            .GetConstructors(BindingFlags.Public | BindingFlags.Instance);

        if (constructors.Any())
        {
            failingTypes.Add(entityType);
        }
    }

    failingTypes.Should().BeEmpty();
}
```

#### 命名规范强制

```csharp
[Fact]
public void CommandHandler_ShouldHave_NameEndingWith_CommandHandler()
{
    Types.InAssembly(ApplicationAssembly)
        .That()
        .ImplementInterface(typeof(ICommandHandler<>))
        .Or()
        .ImplementInterface(typeof(ICommandHandler<,>))
        .Should()
        .HaveNameEndingWith("CommandHandler")
        .GetResult()
        .ShouldBeSuccessful();
}
```

### 4. 集成到CI/CD流水线

将上述测试集成到GitHub Actions、Azure DevOps等CI流水线，每次提交/合并时自动执行，违规立即报警：

## 实际应用案例

以某大型电商平台为例，采用模块化单体（Modular Monolith）+ Clean Architecture 混合模式，通过NetArchTest固化以下规则：

- 禁止任一业务模块直接引用其它模块实现层
- 所有领域事件均需sealed，事件只能通过事件总线流转
- Command Handler统一命名，便于自动注册与维护

团队每次开发新功能或重构时，无需反复人工review依赖和命名，极大提升了开发效率与项目可维护性。

## 常见问题与解决方案

| 问题                     | 解决方案                                               |
| ------------------------ | ------------------------------------------------------ |
| 新成员不了解项目架构规则 | 用架构测试固化规则，新人只需看测试用例即可理解         |
| 某些第三方库引入导致误报 | 测试用例中可灵活排除特定命名空间或类型                 |
| 规则变更后旧代码大量失败 | 分阶段引入新规则，对老代码分批修正，并设宽限期         |
| 测试执行慢影响CI效率     | 只对核心层或关键依赖关系做测试，避免全量扫描所有程序集 |

## 总结

即使是最初规划良好的软件，也难以避免技术债务侵蚀。通过引入**架构测试**并“左移”到开发流程前期，我们能有效防止系统架构被破坏，避免后期高昂的返工成本。建议从最关键的规则做起，逐步完善覆盖范围，并持续集成到CI/CD中，让架构守护成为团队开发文化的一部分。

### 行动建议

1. 熟悉并选用适合团队的.NET架构测试库（如 NetArchTest、ArchUnitNET）。
2. 明确并书面化项目的关键架构和设计规则。
3. 将架构测试作为标准开发流程，与CI/CD流水线深度集成。
4. 鼓励团队成员积极维护和完善架构测试用例。

让我们一起守护高质量、可持续演进的软件系统吧！🚀

---

> **参考链接**
>
> - [原文：Shift Left With Architecture Testing in .NET](https://www.milanjovanovic.tech/blog/shift-left-with-architecture-testing-in-dotnet)
> - [什么是Big Ball of Mud?](https://deviq.com/antipatterns/big-ball-of-mud)
> - [技术债务百科](https://en.wikipedia.org/wiki/Technical_debt)
