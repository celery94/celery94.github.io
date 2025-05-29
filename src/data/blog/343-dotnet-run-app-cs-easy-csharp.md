---
pubDatetime: 2025-05-29
tags: [C#, .NET, dotnet, 编程入门, 脚本开发, 新特性, 微软]
slug: dotnet-run-app-cs-easy-csharp
source: https://devblogs.microsoft.com/dotnet/announcing-dotnet-run-app
title: 终于来了！“dotnet run app.cs”：C#/.NET 10最轻量的新玩法，开发者必看！
description: .NET 10 带来革命性变化：无需项目文件、直接运行C#脚本，让脚本开发、快速入门和原型验证变得前所未有的简单。本文为C#/.NET开发者、初学者、技术爱好者详解“dotnet run app.cs”新特性及其用法。
---

# 终于来了！“dotnet run app.cs”：C#/.NET 10最轻量的新玩法，开发者必看！

## 引言：C#开发从未如此简单 🚀

你是否有过这样的体验：只想写几行C#代码做个小实验，却不得不创建繁琐的`.csproj`项目？对于刚入门C#和.NET的同学，这种“门槛”是不是让你怀疑人生？  
现在，这一切都将改变！.NET 10全新功能「dotnet run app.cs」正式登场：**只需一个C#文件，直接运行，无需项目文件！**  
无论你是想快速测试、学习C#，还是开发小工具、自动化脚本，都能一秒上手，轻装上阵。

---

## 什么是 `dotnet run app.cs`？

微软在.NET 10 Preview 4中引入了「文件级应用（file-based apps）」新模式。  
**核心要点：**

- 只需一个`.cs`文件，无需`.csproj`项目结构
- 命令行一键运行：`dotnet run hello.cs`
- 内置丰富扩展能力，脚本与正式项目无缝迁移

这意味着C#终于像Python、JavaScript那样，写好就能跑，不再被工程结构束缚。无论你是新手还是老手，都会爱上这种简单直接的体验！

---

## 核心特性与用法详解

### 1. 文件级指令：小而美的“项目配置”

以往项目属性要写在`.csproj`里，现在只需在代码顶部添加指令。例如：

```csharp
#:package Humanizer@2.14.1
using Humanizer;

var dotNet9Released = DateTimeOffset.Parse("2024-12-03");
var since = DateTimeOffset.Now - dotNet9Released;
Console.WriteLine($"It has been {since.Humanize()} since .NET 9 was released.");
```

**亮点：**

- `#:package` 直接引用NuGet包，无需项目文件
- `#:sdk` 切换不同SDK，比如Web开发用`Microsoft.NET.Sdk.Web`
- `#:property` 定制编译属性，如语言版本等

### 2. 支持Shebang，C#也能做shell脚本！

有了Shebang（`#!`）支持，C#终于能像Python那样直接在Unix/Linux系统作为shell脚本执行：

```csharp
#!/usr/bin/dotnet run
Console.WriteLine("Hello from a C# script!");
```

```bash
chmod +x app.cs
./app.cs
```

想做自动化小工具？C#同样可以高效优雅！

### 3. 从脚本到正式项目，一步到位

当你的脚本成长为复杂应用时，一条命令即可转为正式项目：

```bash
dotnet project convert app.cs
```

会自动生成对应的`.csproj`，把你的文件级指令也一并转成项目属性，真正做到**从轻量到专业，零割裂**。

---

## 和以往方式有什么不同？

过去C#也有类似的社区工具（如[dotnet-script](https://github.com/dotnet-script/dotnet-script)、[CS-Script](https://github.com/oleg-shilo/cs-script)等），但都需要额外安装。而现在，这些功能**官方内置、开箱即用**，对初学者和希望减少环境依赖的开发者极其友好。

> “No extra tools, no dependencies, just dotnet and your .cs file.”  
> ——微软官方团队

---

## 快速上手指南

1. **安装.NET 10 Preview 4**  
   [下载地址](https://dotnet.microsoft.com/download/dotnet/10.0)
2. **推荐搭配VS Code与C# Dev Kit扩展**  
   [VS Code C# Dev Kit](https://marketplace.visualstudio.com/items?itemName=ms-dotnettools.csdevkit)
3. **新建一个hello.cs文件并写代码**
   ```csharp
   Console.WriteLine("Hello, world!");
   ```
4. **运行你的代码**
   ```bash
   dotnet run hello.cs
   ```
5. **需要“升级”为正式项目？**
   ```bash
   dotnet project convert hello.cs
   ```

---

## 常见问题与未来展望 💡

- **支持多文件吗？** 正在规划中，后续版本将支持多个`.cs`文件一起运行。
- **支持VB或F#吗？** 当前仅支持C#。
- **会有REPL吗？** 官方暂无计划，但生态已有相关方案。
- **适合哪些场景？**
  - 新手学习与教学
  - 脚本与自动化工具开发
  - 原型验证和快速迭代

---

## 结论：C#开发新纪元，你准备好了吗？

随着「dotnet run app.cs」的到来，C#和.NET变得前所未有的易用、灵活。无论你是学习、实验还是构建实际应用，都能大幅降低门槛，提高效率。

> 从现在起，让我们用C#写脚本、写工具、写一切！🦾

---

## 📢 互动时间

你如何看待 C# 的脚本化？有没有想尝试把哪些日常小工具或自动化流程用 C# 来实现？欢迎在评论区留言讨论，或转发分享给你的开发伙伴，一起体验这项重磅新特性！

---

**参考与延伸阅读：**

- [微软官方发布博客（英文原文）](https://devblogs.microsoft.com/dotnet/announcing-dotnet-run-app)
- [示例视频：No projects, just C# with dotnet run app.cs](https://www.youtube.com/watch?v=98MizuB7i-w)
- [相关社区工具：dotnet-script](https://github.com/dotnet-script/dotnet-script)
