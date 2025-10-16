---
pubDatetime: 2025-06-25
tags: ["Architecture", "Productivity", "Tools"]
slug: building-use-case-clean-architecture
source: https://www.milanjovanovic.tech/blog/building-your-first-use-case-with-clean-architecture
title: 使用 Clean Architecture 构建你的第一个用例 —— 用户注册实战详解
description: 本文以用户注册功能为例，系统介绍如何在实际项目中应用 Clean Architecture 原则，包含架构核心思想、分层设计、关键代码实现与常见问题解决方法，图文并茂，助力开发者高效落地高质量架构。
---

# 使用 Clean Architecture 构建你的第一个用例 —— 用户注册实战详解

## 引言

在软件开发实践中，**Clean Architecture（整洁架构）**已经成为实现高可维护、高可扩展、易测试项目的主流架构范式。但对于许多开发者来说，如何在实际业务需求下正确拆分层次、设计用例，仍然存在不少困惑。本文将结合典型的用户注册功能，带你从零实现 Clean Architecture 用例落地，并深入剖析其中的关键技术点、实现细节与常见陷阱。

---

## 背景与核心思想

### 为什么选择 Clean Architecture？

Clean Architecture 强调“**关注点分离**”和“**依赖倒置原则**”。其核心规则是：**依赖只能由外向内**，即只有外层依赖内层，内核业务永远不直接依赖基础设施。这样可以让系统核心逻辑不受外部变化影响，从而便于扩展、替换和测试。

#### 典型分层结构

- **Domain（领域层）**：企业级业务规则与实体
- **Application（应用层）**：用例逻辑与业务流程编排
- **Infrastructure（基础设施层）**：数据库、三方服务等实现细节
- **Presentation（表现层）**：Web API/UI等交互入口

![Clean Architecture 分层示意图](https://www.milanjovanovic.tech/blogs/mnw_098/clean_architecture.png?imwidth=3840)

> 图1：Clean Architecture 分层与依赖流向

---

## 技术原理与设计要点

### 1️⃣ 依赖倒置 & 抽象隔离

- **核心业务（Domain & Application）** 只面向接口、不关心具体实现。
- **所有外部能力（如存储、加密等）** 都通过接口注入进来。
- 利于单元测试、利于后期替换外部依赖。

### 2️⃣ 用例驱动设计

- 应用层每个核心业务流程定义为一个“用例”（如 RegisterUser）。
- 用例仅负责编排业务流，绝不处理外部实现细节。

---

## 需求分析 —— 用户注册场景

在实际项目中，用户注册一般涉及如下关键流程：

1. 用户提交邮箱和密码进行注册
2. 检查邮箱是否已被注册
3. 对密码进行安全加密存储
4. 将新用户信息写入数据库
5. （可选）返回访问令牌或后续认证信息
6. 实现密码强度等业务校验

> 📝 **补充说明：**
>
> - 邮箱唯一性校验需防止并发条件下的重复插入（详见后文Race Condition讨论）。
> - 密码加密应采用行业标准算法，如SHA-256、bcrypt等，并留有升级机制。

---

## Clean Architecture 实现步骤详解

### 一、分层设计

- **Domain 层**：定义 User 实体及其创建逻辑
- **Application 层**：实现 RegisterUser 用例，编排注册流程
- **Infrastructure 层**：提供 IUserRepository（数据访问）、IPasswordHasher（密码加密）等接口的实现

#### 用例输入输出模型

- `RegistrationRequest`：包含用户注册所需字段（Email、Password、FirstName、LastName）
- `RegistrationResult`：枚举注册结果（成功、邮箱已占用等）

### 二、关键代码实现与解读

```csharp
public class RegisterUser(
    IUserRepository userRepository,
    IPasswordHasher passwordHasher)
{
    public async Task<RegistrationResult> Handle(RegistrationRequest request)
    {
        // 1. 校验输入参数（略）
        if (await userRepository.ExistsAsync(request.Email))
        {
            return RegistrationResult.EmailNotUnique;
        }

        // 2. 密码加密
        var passwordHash = passwordHasher.Hash(request.Password);

        // 3. 构建领域对象
        var user = User.Create(
            request.FirstName, request.LastName, request.Email, passwordHash);

        // 4. 数据持久化
        await userRepository.InsertAsync(user);

        // 5. 返回结果
        return RegistrationResult.Success;
    }
}
```

#### 代码要点说明

- `IUserRepository` 和 `IPasswordHasher` 均为接口，由外部注入，实现解耦。
- 所有核心流程都在 Application 层完成，无一行代码依赖外部具体实现。
- 支持单元测试时通过Mock来隔离外部依赖。

---

## 实际应用案例与常见问题解析

### 场景1：并发注册下的邮箱唯一性 Race Condition

在高并发下，仅依靠业务层`ExistsAsync`判断可能出现竞争条件：

```csharp
if (await userRepository.ExistsAsync(request.Email))
{
    // 并发下多个请求可能同时通过校验
    return RegistrationResult.EmailNotUnique;
}
```

**最佳实践：**

- 在数据库 Email 字段建立唯一索引。
- 捕获数据库唯一约束异常，并映射为友好的业务返回码。

### 场景2：升级密码加密算法导致的兼容性问题

如果直接更换密码哈希算法，原有用户无法登录。推荐方案：

1. 新增一列记录每个密码的哈希算法类型
2. 登录时，根据算法类型分别验证
3. 若验证成功且使用旧算法，则重新用新算法加密并覆盖存储，实现平滑升级

---

## 常见问答与扩展思考

### Q1：如何扩展用例支持第三方身份认证或邮箱验证？

- 抽象外部身份服务接口，如 `IExternalIdentityProvider`
- 用 DI 注入进 RegisterUser 用例，在编排流程中调用
- 邮箱验证可作为后置流程异步触发，不影响核心注册流程

### Q2：Clean Architecture 能自动避免所有架构陷阱吗？

不能。Clean Architecture 指导你关注分层和抽象，但实际工程中还需关注并发、安全、性能等问题，需要开发者具备全局视角和工程能力。

---

## 总结与最佳实践建议

通过本案例，你应已掌握：

- 如何在 Clean Architecture 下梳理领域模型与用例流程
- 如何利用接口隔离核心业务与外部实现
- 如何应对实际工程中的并发和安全挑战

Clean Architecture 为项目提供了健康的骨架，但最终能否高效落地，还取决于工程师对架构思想的理解深度与落地细节的把控。
