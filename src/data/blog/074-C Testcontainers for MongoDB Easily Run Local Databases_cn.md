---
pubDatetime: 2024-03-30
tags: [".NET", "C#", "AI", "Testing"]
source: https://www.devleader.ca/2024/03/27/c-testcontainers-for-mongodb-how-to-easily-run-local-databases/
author: Nick Cosentino
title: C# Testcontainers 对于 MongoDB - 轻松运行本地数据库
description: 学习如何使用 C# Testcontainers 对于 MongoDB！如果你正在开发一个 dotnet 应用程序并想要使用 MongoDB，Testcontainers 可以是一个巨大的资产！
---

# C# Testcontainers 对于 MongoDB：轻松运行本地数据库

> ## 摘要
>
> 学习如何使用 C# Testcontainers 对于 MongoDB！如果你正在开发一个 dotnet 应用程序并想要使用 MongoDB，Testcontainers 可以是一个巨大的资产！
>
> 原文 [C# Testcontainers for MongoDB: How To Easily Run Local Databases](https://www.devleader.ca/2024/03/27/c-testcontainers-for-mongodb-how-to-easily-run-local-databases/)

---

在这篇文章中，我将引导你通过 C# Testcontainers 对于 MongoDB 的使用！我喜欢在不想考虑管理启动和关闭数据库的开销，或在云中管理某些东西时，使用 Testcontainers 进行本地数据库工作。MongoDB 在这里并不例外，我们为 MongoDB 提供的 C# Testcontainers NuGet 包非常好用。

在这篇文章中，我将向你介绍 Testcontainers 的基础知识。从那里开始，我将展示通过 C# MongoDB.Driver NuGet 包与新创建的数据库进行交互是多么简单——几乎感觉不到有容器被启动了！让我们深入了解。

---

## C# Testcontainers 的概述

Testcontainers 是一个很棒的 NuGet 包，可以极大地增强你在构建 .NET 应用程序时的测试和本地开发工作流。它提供了一种简单有效的方式来管理 Docker 容器，允许你启动轻量级和隔离的实例，并让它们像什么都没发生过一样被删除！

这意味着使用 Testcontainers，你不再需要担心设置和销毁测试数据库或处理复杂的配置文件。它处理所有的容器管理细节，使这个过程感觉微不足道——我肯定不想手动处理这些问题。

Testcontainers 的一些关键优势包括：

- 它提供了一致且可复制的测试环境。你可以定义所需的确切服务版本和配置，确保你的测试结果在不同环境中是可靠且一致的。
- 它给你的测试和开发工作流带来的速度和灵活性。通过使用轻量级 Docker 容器，你可以根据需求快速启动和销毁测试环境。无需提前配置云或共享资源......只需即时的精彩。
- 与 .Net 生态系统中现有的测试框架和工具（如 Xunit、NUnit 和 BenchmarkDotNet）的无缝集成。这允许你轻松将容器化的服务实例纳入现有的测试套件，无需进行任何重大修改。

对于这篇文章，我们将专注于如何特别地使用 C# Testcontainers 对于 MongoDB。这里的很多建议将适用于其他服务，尤其是数据库，但我们将关注 MongoDB。

---

## 在 C# 中设置 Testcontainers

要开始使用 C# 中的 Testcontainers，你需要在你的项目中安装和配置必要的依赖。按照以下步骤设置 C# 中的 Testcontainers 对于 MongoDB。

### 1\. 安装 Testcontainers

通常，第一步将是在你的 C# 项目中安装 Testcontainers NuGet 包。你将打开 NuGet 包管理器控制台并运行以下命令：

```bash
Install-Package Testcontainers
```

然而，我们需要这个包的 MongoDB 版本（在撰写本文时我使用的是版本 3.8.0），它包括基础 Testcontainers 包。你可以通过包管理器用户界面或使用以下命令进行安装：

```bash
Install-Package Testcontainers.MonogoDB
```

---

### 2\. 为 MongoDB 配置 Testcontainers

安装 Testcontainers 后，你需要将其配置为 MongoDB。这涉及到使用所需设置设置 MongoDB 容器。以下是如何在 C# 中为 MongoDB 配置 Testcontainers 的示例：

```csharp
using Testcontainers.MongoDb;

MongoDbContainer container = new MongoDbBuilder()
    .WithImage("mongo:latest")
    .Build();
```

在上面的示例中，我们创建了一个 `MongoDbBuilder` 的新实例，并指定了 MongoDB 图像和端口绑定。`WithImage` 方法设置了 MongoDB 容器的图像，所以使用 “mongo:latest” 将始终拉取最新的图像。

可选地，我们可以使用端口绑定来明确配置我们希望使用的端口：

```csharp
using Testcontainers.MongoDb;

MongoDbContainer container = new MongoDbBuilder()
    .WithImage("mongo:latest")
    .WithPortBinding(1337, 27017)
    .Build();
```

上面的代码使用 `WithPortBinding` 方法将容器的端口 27017 绑定到主机机器的端口 1337 上。在接下来的章节中，我们将看到，除非你有明确绑定端口的特定需求，否则你完全可以不必这样做。我们可以获得一个动态的连接字符串，这非常方便！

3\. 启动和停止 MongoDB 容器

配置 MongoDB 的 Testcontainers 后，你可以根据需要启动和停止容器。以下是启动和停止容器的代码示例：

要启动 MongoDB 容器：

```csharp
await container.StartAsync();
```

要停止 MongoDB 容器：

```csharp
await _container.StopAsync();
```

记得 MongoDbContainer 类型可以被释放，所以当你准备好时调用 `DisposeAsync` 来进行清理。

---

## 在实践中使用 C# Testcontainers 对于 MongoDB

现在我们已经看到了如何启动和销毁容器，我们应该用它们做什么呢？我们有很多选择，真正的限制是你们自己的想象力（以及时间、金钱和其他资源......）！

大多数人利用 C# Testcontainers 来编写集成或[功能测试](https://www.devleader.ca/2021/05/07/tldr-unit-vs-functional-tests/)。例如，你可以将Testcontainers 与 xUnit 或 NUnit 配对，并编写与真实数据库交互的测试。

对我来说，我需要将 C# Testcontainers 对于 MongoDB 连接到 BenchmarkDotNet，这样我就可以[对 MongoDB 插入记录进行基准测试](https://www.devleader.ca/2024/03/28/c-mongodb-insert-benchmarks-what-you-need-to-know/ "C# MongoDB Insert Benchmarks – What You Need To Know")！一个类似的用例，我需要临时本地数据库，但不一定是测试框架。

无论如何，我们需要能够从 C# 中连接到这些 MongoDB 数据库容器，接下来的小节将涵盖这一点。

### 使用 MongoDB.Driver 连接 C# Testcontainers 对于 MongoDB

假设你阅读了前面的章节并安装了正确的 MongoDB 包用于 Testcontainers。如果你跳到这个部分，请返回去，阅读它，并获取正确的包。否则，你会对为什么找不到正确的依赖感到困惑！

你还需要安装 MongoDB.Driver NuGet 包。这将是我们用来建立与我们启动的数据库容器连接的工具。 如果你想了解 MongoDB.Driver 的更多信息，我有其他文章你可以阅读:

- [MongoDB in C#: 简化插入数据的指南](https://www.devleader.ca/2024/03/22/mongodb-in-c-simplified-guide-for-inserting-data/ "MongoDB in C#: Simplified Guide For Inserting Data")
- [MongoDB Filtering in C# – 初学者易懂的筛选指南](https://www.devleader.ca/2024/03/24/mongodb-filtering-in-c-beginners-guide-for-easy-filters/ "MongoDB Filtering in C# – Beginner’s Guide For Easy Filters")
- [如何在 C# 中从 MongoDB 删除文档 - 你需要知道的](https://www.devleader.ca/2024/03/26/how-to-delete-documents-from-mongodb-in-c-what-you-need-to-know/ "How To Delete Documents From MongoDB In C# – What You Need To Know")
- [如何在 C# 中更新 MongoDB 文档 - 你需要知道的](https://www.devleader.ca/2024/03/25/how-to-update-mongodb-documents-in-c-what-you-need-to-know/ "How To Update MongoDB Documents in C# – What You Need To Know")

准备好正确的包后，我们可以将之前看到的代码与一些 MongoDB 驱动程序代码结合起来:

```csharp
using MongoDB.Bson;
using MongoDB.Driver;

using Testcontainers.MongoDb;

MongoDbContainer container = new MongoDbBuilder()
    .WithImage("mongo:latest")
    .Build();
await container.StartAsync();
string connectionString = container.GetConnectionString();

MongoClient mongoClient = new MongoClient(connectionString);
IMongoDatabase database = mongoClient.GetDatabase("test");
IMongoCollection<BsonDocument> collection = database.GetCollection<BsonDocument>("test");
```

在上面的示例中，我们可以在 Testcontainers 中新启动的 MongoDB 容器上调用 `GetConnectionString()`。这一点很棒的是，无论你如何使用[建造者模式](https://www.devleader.ca/2023/09/29/the-builder-pattern-what-it-is-and-how-to-use-it-effectively/)中在这段代码和文章中看到的方式配置 MongoDB 的 Testcontainer，`GetConnectionString()` 都会提供你需要连接的信息。

因为 `MongoClient` 接受一个连接字符串作为单一参数，所以立即访问 MongoDB 数据库并开始使用它是非常简单的！

### 在 MongoDB Testcontainer 上执行 CRUD 操作

现在我们有了 MongoDB Testcontainer 的设置，并且我们有了连接到它的 `MongoClient`，我们可以开始在其上执行 CRUD 操作。容器实例提供的连接细节使得这两件事结合起来变得轻而易举，真正的是我们可以直接专注于 MongoDB.Driver 方法调用来进行 CRUD。

以下是执行简单 CRUD 操作的示例：

```csharp
// 使用之前示例中的代码...

// Create
await collection.InsertOneAsync(new BsonDocument()
{
    ["Name"] = "Nick Cosentino",
});

// Read
var filterBuilder = Builders<BsonDocument>.Filter;
var filter = filterBuilder.Eq("Name", "Nick Cosentino");
var results = collection.Find(filter);

// Update
var updateBuilder = Builders<BsonDocument>.Update;
var update = updateBuilder.Set("Name", "Dev Leader");
collection.UpdateOne(filter, update);

// Delete
filter = filterBuilder.Eq("Name", "Dev Leader");
collection.DeleteOne(filter);
```

使用之前的代码片段，我们已经可以使用 MongoDB 容器实例和 `MongoClient` 了。因此，你可以在上面的代码片段中看到，我们可以直接使用从之前设置中获得的 `IMongoCollection<BsonDocument>`。这有助于说明，一旦你通过 Testcontainers 启动了 MongoDB docker 容器并连接到它，就不必对它进行任何特殊处理了！

---

## 结束 C# Testcontainers 对于 MongoDB

总结一下，C# Testcontainers 对于 MongoDB 是一种非常简单的方式，可以为你的测试和开发上线一个临时的 MongoDB 数据存储。虽然这篇文章没有专注于特定的用例，但希望你现在更好地理解了如何通过 Testcontainers 在 MongoDB 顶部透明地层叠 MongoDB 驱动程序进行交互的感觉。考虑到 C# Testcontainers 消除了设置、拆卸和甚至连接字符串管理的头痛问题，如果你想在本地使用 MongoDB 快速启动和运行，这对我来说是一个容易的推荐。

---

## 常见问题解答：C# Testcontainers 对于 MongoDB

### 什么是 C# Testcontainers?

C# 的 Testcontainers 是一个工具，它允许你轻松创建和管理一次性 Docker 容器服务，通常用于测试目的。它提供了一种启动如数据库、消息队列和 Web 服务器等容器的方式，作为[测试和开发](https://www.devleader.ca/2023/10/18/blazor-unit-testing-best-practices-how-to-master-them-for-development-success/)工作流的一部分。

### 如何在 C# 项目中设置 Testcontainers?

要在 C# 项目中设置 Testcontainers，你需要安装 Testcontainers NuGet 包。一旦安装，你可以配置 Testcontainers 库来与所需的服务协作，这通常是通过扩展基本功能的其他 NuGet 包提供的。

### 如何将 C# Testcontainers 用于 MongoDB?

你可以使用 C# 中的 Testcontainers 设置一个 MongoDB 容器用于测试。这允许你创建一个临时的 MongoDB 实例，专门用于你的测试。然后，你可以连接到这个容器并执行各种操作，如[插入数据、查询数据库，](https://www.devleader.ca/2024/03/22/mongodb-in-c-simplified-guide-for-inserting-data/)并验证结果。考虑将 MongoDB.Driver NuGet 包与 Testcontainers 一同使用。
