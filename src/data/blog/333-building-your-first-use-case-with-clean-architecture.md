---
pubDatetime: 2025-05-23
tags: ["Architecture", "Productivity", "Tools"]
slug: building-your-first-use-case-with-clean-architecture
source: https://www.milanjovanovic.tech/blog/building-your-first-use-case-with-clean-architecture
title: Clean Architecture 实战：构建你的第一个用例（以用户注册为例）
description: 通过实战案例，详细讲解如何在.NET项目中运用Clean Architecture设计用户注册功能，提升代码可维护性与结构化能力。
---

# Clean Architecture 实战：构建你的第一个用例（以用户注册为例） 🚀

## 引言：架构的混沌与秩序

在日常开发中，你是否遇到过这样的困扰？  
项目越来越大，业务越来越复杂，每次需求变更都如同“拆地雷”般危险。尤其是.NET后端项目，如何让代码结构清晰、易于维护，成为了很多开发者和架构师的共同追求。

Clean Architecture（整洁架构）应运而生，它以**分层解耦**和**依赖规则**为核心，为复杂项目带来了秩序。今天，我们就通过一个实战案例——“用户注册”功能，手把手带你体验Clean Architecture的魅力，让你的项目结构更优雅、更可控。

> 本文适合有一定开发经验、对架构设计有追求的.NET后端开发者与架构师，尤其是希望提升项目可维护性和可测试性的你。

---

## 什么是 Clean Architecture？

Clean Architecture 是 Robert C. Martin（Uncle Bob）提出的一种软件架构设计思想。它强调**关注点分离**和**依赖只指向内层（Dependency Rule）**：

- 核心业务逻辑与外部依赖解耦
- 结构清晰，便于维护与扩展
- 测试友好

来看一张经典的 Clean Architecture 分层图：

![Clean Architecture diagram.](https://www.milanjovanovic.tech/blogs/mnw_098/clean_architecture.png?imwidth=3840)

**分层说明：**

- **Domain（领域层）**：企业级业务规则、核心实体对象
- **Application（应用层）**：用例和业务编排逻辑（如用户注册）
- **Infrastructure（基础设施层）** & **Presentation（表现层）**：与外部世界对接，实现具体接口

> 依赖规则：“依赖只能指向内层”，即越核心的层越独立！

---

## 用例描述：什么是“用户注册”？

在落地之前，先来明确“用户注册”功能的核心需求：

1. 用户输入邮箱和密码
2. 检查邮箱是否已被注册
3. 使用加密算法对密码进行哈希
4. 将新用户信息存入数据库，并可选返回访问令牌
5. （可选）实现如密码强度校验等业务规则

通过以上需求，我们可以将其抽象成一个用例 `RegisterUser`。

---

## 用例实现：代码层面的 Clean Architecture

在 Clean Architecture 中，“用例”属于 Application 层。它负责编排领域实体与外部依赖的交互。

### 抽象依赖

- `IUserRepository`：用户数据存取接口
- `IPasswordHasher`：密码哈希接口

这样即使后续切换数据库或更换哈希算法，都无需修改核心业务逻辑。

### RegisterUser 用例代码示例

```csharp
public class RegisterUser(
    IUserRepository userRepository,
    IPasswordHasher passwordHasher)
{
    public async Task<RegistrationResult> Handle(RegistrationRequest request)
    {
        // 1. 校验输入数据（略）
        if (await userRepository.ExistsAsync(request.Email))
        {
            return RegistrationResult.EmailNotUnique;
        }

        // 2. 密码哈希
        var passwordHash = passwordHasher.Hash(request.Password);

        // 3. 创建 User 实体并保存
        var user = User.Create(
            request.FirstName, request.LastName, request.Email, passwordHash);

        await userRepository.InsertAsync(user);

        // 4. 返回结果
        return RegistrationResult.Success;
    }
}
```

### 好处体现

- 业务逻辑清晰独立，可直接编写单元测试
- 外部依赖用接口抽象，便于扩展或切换实现

#### 测试驱动开发友好

用Mock模拟 `IUserRepository` 和 `IPasswordHasher`，即可轻松测试各类业务场景。

---

## “整洁”之外的思考：陷阱与细节 🧐

虽然 Clean Architecture 强调“可替换性”，但实际应用时还需关注一些隐蔽细节：

### 1. 并发安全——注册流程中的竞态条件

如果同时有多个注册请求，可能出现邮箱重复注册问题。

**解决方案A：数据库唯一索引**

在数据库为 `Email` 字段加唯一索引，从根本上杜绝重复写入。同时在应用层捕获异常并友好提示。

**代码片段**

```csharp
if (await userRepository.ExistsAsync(request.Email))
{
    return RegistrationResult.EmailNotUnique;
}
// 唯一索引保障数据库一致性
```

### 2. 密码哈希升级带来的兼容问题

当原有哈希算法存在安全隐患时，简单替换新算法会导致老用户无法登录。

**正确做法：逐步迁移**

新增一列记录哈希算法类型。登录时根据存储信息选择对应哈希算法，验证成功后再升级为新算法。这样平滑完成迁移，无缝切换更安全的加密方式。

---

## 总结与思考 🌱

通过本案例，你应该能感受到 Clean Architecture 的实践魅力：

- 明确分层、责任清晰，提升可维护性
- 抽象依赖，实现灵活扩展
- 易于测试与团队协作

但也要牢记：架构只是工具，关键是理解每一层“为何存在”以及“如何协作”。盲目抽象反而可能埋下隐患。
