---
pubDatetime: 2025-03-31 21:25:37
tags: [".NET", "Architecture"]
slug: building-custom-graphql-query-builder-dotnet9
source: https://thecodeman.net/posts/building-custom-graphql-query-builder-in-dotnet9
title: 在.NET 9中打造自定义GraphQL查询构建器：最佳实践与完整实现
description: 通过动态GraphQL查询模板、Minimal API和依赖注入，轻松构建高效、灵活的GraphQL客户端。本文将带你深入探讨如何在.NET 9中实现这一功能，让你的开发更上一层楼。
---

# 在.NET 9中打造自定义GraphQL查询构建器：最佳实践与完整实现 🚀

在现代API开发中，GraphQL以其灵活性深受开发者青睐。然而，对于像C#这样强类型语言的开发者来说，手动构建GraphQL查询字符串既繁琐又容易出错。本文将为你介绍一种优雅的解决方案——在.NET 9中构建一个自定义的GraphQL查询构建器！🎉

通过本文，你将学会如何：

- 使用动态GraphQL查询模板，避免硬编码查询字符串。
- 利用Minimal API和依赖注入，创建模块化、可维护的代码结构。
- 使用GraphQL.Client进行简单、灵活的API调用。

## 为什么需要GraphQL查询构建器？

现代应用往往需要处理复杂的数据请求，例如嵌套的数据结构、动态过滤条件等。如果直接在代码中硬编码这些查询字符串，不仅难以维护，还可能导致重复代码和错误。引入一个通用的 **GraphQL查询构建器** 能够大大提升开发效率和代码质量：

- **复用性：** 把查询模板和代码逻辑分离，支持动态变量替换。
- **可维护性：** 查询模板独立存储，修改时无需重新编译代码。
- **灵活性：** 支持复杂查询结构和动态输入。

## 项目结构 📁

为了实现这一目标，我们需要设计一个清晰的项目结构：

![GraphQL目录结构](https://thecodeman.net/images/blog/posts/building-custom-graphql-query-builder-in-dotnet9/graphql-directory.png)

### 文件夹说明：

- **/Queries/**：存储所有的静态`.graphql`文件，这些文件包含占位符变量（如`$userId`）并可动态替换。
  - 示例文件：
    - `GetUser.graphql`: 获取用户及其帖子信息。
    - `GetOrders.graphql`: 获取订单、客户信息及商品明细。
- **/GraphQL/**：包含共享的GraphQL工具类。
  - **GraphQLQueryBuilder.cs**：核心构建器，用于加载和替换查询模板中的变量。

### 示例`.graphql`文件

以下是`GetUser.graphql`文件的示例：

```graphql
{
  user(id: "$userId") {
    id
    name
    email
    posts {
      title
    }
  }
}
```

这个查询模板会动态替换`$userId`为实际值，返回用户的基本信息（ID、姓名、邮箱）及其帖子标题。

---

## 核心实现 🔧

### GraphQLQueryBuilder.cs：核心工具类

```csharp
using GraphQL;
using System.Reflection;

namespace GraphQLDemo.GraphQL;

public static class GraphQLQueryBuilder
{
    public static async Task<GraphQLRequest> BuildQuery(string fileName, Dictionary<string, string> variables)
    {
        string path = Path.Combine(AppContext.BaseDirectory, "Queries", fileName);
        string query = await File.ReadAllTextAsync(path);

        foreach (var variable in variables)
        {
            query = query.Replace($"${variable.Key}", variable.Value);
        }

        return new GraphQLRequest { Query = query };
    }
}
```

**功能概述：**

1. 从`Queries`目录读取指定的`.graphql`文件。
2. 根据传入的变量字典，动态替换占位符（如`$userId`）。
3. 返回一个`GraphQLRequest`对象，供客户端调用。

### UserService.cs：服务层封装

```csharp
using GraphQL;
using GraphQL.Client.Abstractions;
using Newtonsoft.Json;

namespace GraphQLDemo.Services;

public class UserService
{
    private readonly IGraphQLClient _client;

    public UserService(IGraphQLClient client)
    {
        _client = client;
    }

    public async Task<string> GetUserWithPostsAsync(string userId)
    {
        var request = await GraphQLQueryBuilder.BuildQuery("GetUser.graphql", new()
        {
            { "userId", userId }
        });

        var response = await _client.SendQueryAsync<dynamic>(request);
        return JsonConvert.SerializeObject(response.Data);
    }
}
```

**设计亮点：**

- 服务层负责调用`GraphQLQueryBuilder`生成查询请求，并通过`IGraphQLClient`发送请求。
- 返回结果以JSON格式序列化，便于前端消费。

---

## Minimal API配置 🌐

在.NET 9中，我们使用Minimal API来定义HTTP端点：

```csharp
using GraphQL.Client.Http;
using GraphQL.Client.Serializer.Newtonsoft;
using GraphQLDemo.Services;

var builder = WebApplication.CreateBuilder(args);

// 注册GraphQL客户端
builder.Services.AddSingleton<IGraphQLClient>(_ =>
    new GraphQLHttpClient("https://your-graphql-endpoint.com/graphql", new NewtonsoftJsonSerializer())
);

// 注册服务
builder.Services.AddScoped<UserService>();

var app = builder.Build();

app.MapGet("/user/{id}", async (string id, UserService userService) =>
{
    var result = await userService.GetUserWithPostsAsync(id);
    return Results.Json(JsonConvert.DeserializeObject(result));
});

app.Run();
```

### 测试你的API 🛠️

你可以使用Postman来测试Minimal API。创建一个新的GraphQL请求并填写如下内容：

```graphql
query {
  user(id: "123") {
    id
    name
    email
    posts {
      title
    }
  }
}
```

如果你没有自己的GraphQL服务器，可以使用[GraphQLZero](https://graphqlzero.almansi.me/#example-top)作为测试服务器。

---

## 高级示例：订单查询功能 📦

假设我们需要构建一个电商平台的订单数据查询功能，包括：

- 订单列表及其状态、创建时间。
- 每个订单的商品明细（商品名称、价格、数量）。
- 关联客户的姓名和邮箱。
- 可根据状态和日期范围筛选。

### 查询模板示例（GetOrders.graphql）

```graphql
{
  orders(
    filter: {
      status: "$status"
      dateRange: { from: "$dateFrom", to: "$dateTo" }
    }
  ) {
    id
    status
    createdAt
    customer {
      id
      name
      email
    }
    lineItems {
      product {
        id
        name
        price
      }
      quantity
    }
  }
}
```

### 服务方法实现

```csharp
public async Task<string> GetOrdersAsync(string status, string dateFrom, string dateTo)
{
    var request = await GraphQLQueryBuilder.BuildQuery("GetOrders.graphql", new()
    {
        { "status", status },
        { "dateFrom", dateFrom },
        { "dateTo", dateTo }
    });

    var response = await _client.SendQueryAsync<dynamic>(request);
    return JsonConvert.SerializeObject(response.Data);
}
```

### 新增API端点

```csharp
app.MapGet("/orders", async (
  string status,
  string dateFrom,
  string dateTo,
  OrderService orderService) =>
{
    var result = await orderService.GetOrdersAsync(status, dateFrom, dateTo);
    return Results.Json(JsonConvert.DeserializeObject(result));
});
```

---

## 总结 ✨

通过自定义GraphQL查询构建器，我们成功实现了以下目标：

1. 将复杂查询逻辑模块化，提升了代码复用性与可维护性。
2. 灵活地处理动态变量，使API开发更加便捷。
3. 利用Minimal API和依赖注入，保持代码简洁清晰。

这种方法适用于大多数企业级应用，同时还能根据需求扩展支持更多功能，如查询缓存、片段支持或代码生成工具。如果你正在使用.NET进行后端开发，不妨尝试这个解决方案，为你的项目注入新的活力！

🔥 如果你喜欢这篇文章，不妨分享给更多人！一起探索技术的无限可能！
