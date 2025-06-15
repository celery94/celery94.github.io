---
pubDatetime: 2025-06-15
tags: [C#, .NET, 脚本, 开发效率, 新特性]
slug: dotnet10-csharp-script-dotnet-run
source: https://www.milanjovanovic.tech/blog/run-csharp-scripts-with-dotnet-run-app-no-project-files-needed
title: 彻底释放C#脚本力：.NET 10新特性dotnet run app.cs无项目文件直接运行！
description: .NET 10为C#开发者带来了革命性的脚本体验——无需项目文件，直接运行.cs文件！本文详细解读新特性dotnet run app.cs，结合实用示例、NuGet包引用技巧及项目无缝迁移，助你大幅提升开发效率。
---

# 彻底释放C#脚本力：.NET 10新特性`dotnet run app.cs`无项目文件直接运行！

> C#终于也能像Python、JavaScript一样“一把梭”直接运行脚本了！

## 引言：C#也能像脚本语言一样任性了！

你是否曾羡慕Python、Node.js等脚本语言“一行代码即刻执行”的爽快？作为.NET/C#开发者，每次想快速验证个想法、写个工具，总免不了新建项目、配置csproj、添加Main方法的繁琐流程。现在，这一切被.NET 10的全新特性 **dotnet run app.cs** 彻底改变！

.NET 10 Preview 4 正式引入“单文件运行”模式 —— 无需项目文件、无需Main方法，真正做到“写完即跑”。这对于追求开发效率、中高级工程师来说，无疑是个巨大福音。

## 为什么这个特性值得关注？🤔

长期以来，C#脚本门槛高一直被吐槽。对比Python、Bash甚至JavaScript，C#在“一次性脚本”场景下总显得太重。现在，你只需要：

- 写一个`.cs`脚本
- 在终端输入：

  ```shell
  dotnet run app.cs
  ```

- Done！无需任何工程模板或解决方案配置。

> **适用场景**：日常小工具、临时数据处理、构建自动化脚本、测试用例Demo、团队内部“最小复现”等等。

## 正文：一步步体验C#极简脚本开发

### 1. 最小示例：Hello C# Script World!

假如你只想打印今天的日期，脚本内容就是：

```csharp
Console.WriteLine($"Today is {DateTime.Now:dddd, MMM dd yyyy}");
```

只需一行命令直接运行：

```shell
dotnet run app.cs
```

输出示例：

```
Today is Saturday, Jun 14 2025
```

是不是很像Python的体验？再也不用写Main方法啦！

---

### 2. 脚本中引用NuGet包？一句指令搞定

还以为写脚本就不能用第三方库？错！`dotnet run app.cs`支持**内联包引用**，比如调用Flurl.Http发送HTTP请求：

```csharp
#:package Flurl.Http@4.0.2

using Flurl.Http;

var response = await "https://api.github.com"
    .WithHeader("Accept", "application/vnd.github.v3+json")
    .WithHeader("User-Agent", "dotnet-script")
    .GetAsync();

Console.WriteLine($"Status code: {response.StatusCode}");
Console.WriteLine(await response.GetJsonAsync<object>());
```

运行方法同上：

```shell
dotnet run fetch.cs
```

> 编译器会自动帮你下载并还原NuGet依赖，极大提升试错和原型开发效率。

---

### 3. 实战案例：一条命令批量向Postgres数据库插数据

如果你要快速给数据库塞点测试数据，不想污染主工程，可以这样：

```csharp
#:package Dapper@2.1.66
#:package Npgsql@9.0.3

using Dapper;
using Npgsql;

const string connectionString = "Host=localhost;Port=5432;Username=postgres;Password=postgres";

using var connection = new NpgsqlConnection(connectionString);
await connection.OpenAsync();

using var transaction = connection.BeginTransaction();

Console.WriteLine("Creating tables...");

await connection.ExecuteAsync(@"
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL
    );
");

Console.WriteLine("Inserting users...");

for (int i = 1; i <= 10_000; i++)
{
    await connection.ExecuteAsync(
        "INSERT INTO users (name) VALUES (@Name);",
        new { Name = $"User {i}" });

    if (i % 1000 == 0)
    {
        Console.WriteLine($"Inserted {i} users...");
    }
}

transaction.Commit();

Console.WriteLine("Done!");
```

只需：

```shell
dotnet run seed.cs
```

就能完成全部操作，代码独立、易于复用或抛弃，避免污染主工程。

---

### 4. File-Level Directives：让你的脚本自带配置魔法

支持以下“魔法”指令，让脚本功能更强大：

- **包管理**（如上）
- **指定SDK类型**（比如Web应用）：

  ```csharp
  #:sdk Microsoft.NET.Sdk.Web
  #:package Microsoft.AspNetCore.OpenApi@9.*

  var builder = WebApplication.CreateBuilder();

  builder.Services.AddOpenApi();

  var app = builder.Build();

  app.MapOpenApi();

  app.MapGet("/", () => "Hello from a file-based API!");
  app.MapGet("/users/{id}", (int id) => new { Id = id, Name = $"User {id}" });

  app.Run();
  ```

- **设置MSBuild属性**：

  ```csharp
  #:property LangVersion preview
  #:property Nullable enable
  ```

你的`.cs`文件就像`Dockerfile`一样“一切尽在其中”，极度便携！

---

### 5. 脚本长大了怎么办？一键升级为标准项目！

当你的脚本逐渐复杂、需要团队协作或持续集成，只需：

```shell
dotnet project convert api.cs
```

系统会自动生成标准项目结构，包括`.csproj`与所有包引用和属性配置，代码迁移无痛衔接。

> 这才是真正的“从草稿到工业级”的无缝演进体验！

---

## 总结：C#脚本新时代来临，你准备好了吗？🚀

`.NET 10`让C#的“重型”标签成为历史。对于.NET/C#开发者而言，这不仅是一次技术升级，更是开发哲学的进化——用最少的仪式感，实现最高效的创新力。

- 对于资深工程师，临时任务/原型/数据处理/自动化都变得毫无压力；
- 对于初学者，学习门槛骤降，“写代码-跑起来”零阻力上手。

微软没有另起炉灶搞新语法、新工具链，而是直接让C#与主流脚本体验看齐。这不仅保证了兼容性，也极大拓宽了应用场景。

> **仪式感已死，实用主义万岁！**

---

## 🌟 你的看法和体验？

你会在哪些场景下用到这个新特性？欢迎评论区分享你的想法和实践经验！  
觉得有收获，不妨点赞+转发，让更多C#er受益吧！

---

> _参考原文与更多实战案例请见：[Run C# Scripts With dotnet run app.cs (No Project Files Needed)](https://www.milanjovanovic.tech/blog/run-csharp-scripts-with-dotnet-run-app-no-project-files-needed)_  
> 作者：Milan Jovanović
