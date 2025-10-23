---
pubDatetime: 2025-05-18
tags: [".NET", "ASP.NET Core", "C#", "AI"]
slug: stop-using-firstordefault-claims-dotnet
source: https://itnext.io/stop-using-firstordefault-for-claims-in-net-71add18db5a2
title: 告别 FirstOrDefault！用 C# 14 扩展成员优雅访问 Claims（ASP.NET Core 实战）
description: 你是否还在项目里到处用 Claims.FirstOrDefault 获取用户信息？现在，C# 14 的扩展成员让你的身份认证代码变得更简洁、可测试和可维护。本文用实战代码教你一步步升级写法，让 Claims 操作告别魔法字符串和重复逻辑！
---

# 告别 FirstOrDefault！用 C# 14 扩展成员优雅访问 Claims（ASP.NET Core 实战）

> “Say goodbye to magic strings and hello to testable, discoverable identity access in ASP.NET.”  
> —— Hossein Kohzadi

![一位红发女程序员正在专注编程](https://miro.medium.com/v2/resize:fit:700/0*gHJV7ZfJj6ig6BmV)

## 引言：你还在用 FirstOrDefault 获取 Claims 吗？👀

在 ASP.NET Core 日常开发中，获取用户信息时你是否经常这样写？

```csharp
var email = User.Claims.FirstOrDefault(x => x.Type == ClaimTypes.Email)?.Value;
```

是不是觉得这样的代码：

- 到处复制粘贴
- 魔法字符串泛滥
- 不便于测试和维护
- IDE 无法智能提示，易出错

其实，这已经成为很多 .NET 项目的“技术债”之一。  
幸运的是，随着 C# 14 和 .NET 10 的发布，扩展成员（Extension Members）为我们带来了更现代、更优雅的解决方案！

---

## 现状分析：Claims 操作的四大痛点

让我们直面问题。传统的 Claims 获取方式有如下痛点：

- **重复代码**：控制器和服务里频繁出现 `FirstOrDefault`
- **类型不安全**：Claim 类型用字符串，IDE 无法检查，拼写错误难以发现
- **测试困难**：难以 mock 或替换 claims 逻辑
- **难以发现**：团队成员不清楚有哪些可用 Claims，协作不友好

这些问题让我们的身份认证逻辑变得臃肿、不易维护，甚至埋下安全隐患。

---

## C# 14 扩展成员是什么？为何能改变现状？

C# 14 引入了扩展成员（Extension Members），不仅仅是扩展方法，而是可以为已有类型添加属性和方法，并且支持 IDE 智能提示！

对于 `ClaimsPrincipal`，我们可以这样写：

```csharp
public static class ClaimsPrincipalExtensions
{
    public static string? Email(this ClaimsPrincipal user) =>
        user.FindFirst(ClaimTypes.Email)?.Value;
}
```

甚至，在 C# 14 中，你可以直接加扩展属性：

```csharp
public static extension ClaimsPrincipal
{
    public static string? Email => this.FindFirst(ClaimTypes.Email)?.Value;
}
```

效果如何？  
现在你可以愉快地写：

```csharp
var email = User.Email;
```

不用再担心魔法字符串，也不用写一大串 FirstOrDefault，每个 Claims 一目了然、IDE 可发现、便于测试！

---

## 实战：一步步升级你的 Claims 获取姿势

### 1. 封装成扩展成员（推荐做法）

**原始写法：**

```csharp
var userId = User.Claims.FirstOrDefault(c => c.Type == "sub")?.Value;
```

**现代扩展成员写法：**

```csharp
public static extension ClaimsPrincipal
{
    public static string? UserId => this.FindFirst("sub")?.Value;
    public static string? Email => this.FindFirst(ClaimTypes.Email)?.Value;
    // 可以继续添加更多常用 Claims
}
```

调用：

```csharp
var id = User.UserId;
var email = User.Email;
```

### 2. 便于单元测试和 Mock

有了扩展成员后，你可以很容易 Mock 一个包含指定 Claim 的 ClaimsPrincipal，在测试代码里直接访问 `User.Email`，无需关心底层实现。

### 3. 更好的 IDE 支持与团队协作

在 VS/JetBrains Rider 里输入 `User.` 自动弹出所有扩展的属性，团队协作再也不用担心 Claim 类型拼写错误或遗漏。

---

## 技术进阶：为何不是简单“包一层”？

有读者会问，“不就是把 FirstOrDefault 包装成方法/属性吗？”  
其实意义远不止如此：

- 明确表达 intent，代码更易读、更安全
- 支持自动化重构、全局替换
- 集中管理所有身份相关逻辑，便于权限审计和后期调整
- 有效隔离依赖，降低耦合度

> ☝️ **最佳实践**：配合强类型 ClaimType 枚举/常量使用，进一步提升安全性和可维护性。

---

## 总结 & 行动建议 📝

- 用 C# 14 扩展成员重构你的 Claims 获取逻辑，让代码更简洁、可维护、可测试
- 拒绝魔法字符串，享受 IDE 智能提示与类型安全的红利
- 在实际项目中集中管理扩展成员，提高团队协作效率和代码质量

> 👏 **现在就动手，把你的 User.Claims.FirstOrDefault 全部升级为扩展属性吧！**

---

## 结尾互动 🤔

你在项目中遇到过哪些 Claims 使用痛点？有没有用过类似的扩展封装？欢迎在评论区留言交流你的最佳实践或遇到的挑战！  
如果觉得这篇文章有帮助，请点赞、分享给你的 .NET 同事，一起打造更现代、更易维护的 ASP.NET Core 项目！

---

_封面图来源：[ThisisEngineering on Unsplash](https://unsplash.com/@thisisengineering?utm_source=medium&utm_medium=referral)_
