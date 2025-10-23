---
pubDatetime: 2024-03-07
tags: [".NET", "ASP.NET Core", "Architecture"]
source: https://blog.postman.com/best-practices-for-api-error-handling/
author: Gbadebo Bello
title: API错误处理的最佳实践 | Postman 博客
description: 学习API错误处理的一般最佳实践，以及针对REST、GraphQL、gRPC等不同架构的特定最佳实践。
---

# API错误处理的最佳实践 | Postman 博客

> ## 摘要
>
> 学习API错误处理的一般最佳实践，以及针对REST、GraphQL、gRPC等不同架构的特定最佳实践。
>
> 原文 [Best Practices for API Error Handling](https://blog.postman.com/best-practices-for-api-error-handling/) 由 Gbadebo Bello 撰写。

---

2024年2月8日 · 10分钟

错误处理是使用API时的一个关键部分。当API遇到问题，如无效的输入数据或缺失的资源时，可能会导致错误。至关重要的是，这些错误被正确处理并清晰地展示给客户端或最终用户。

[API生命周期](https://www.postman.com/api-platform/api-lifecycle/)涉及API的生产者和消费者。API生产者工作在服务器端，负责API的设计和开发。另一方面，API消费者工作在客户端，负责将API集成到最终用户交互的各种系统中。在这一过程的任何阶段都可能发生错误。如果这些错误没有得到适当的处理，可能会导致停机、糟糕的用户体验、金钱和时间的损失。

在本文中，我们将首先回顾一些在客户端和服务器端处理API错误的最佳实践——不侧重于任何特定的API架构。然后，我们将讨论针对API错误处理的特定架构的最佳实践——并探讨Postman API平台如何帮助团队更高效地处理错误。

## 服务器端处理API错误的一些最佳实践是什么？

有多种API架构模式，每种都有其独特的错误处理方法。也就是说，所有API错误都需要以一致和逻辑的方式呈现。因此，无论您的API采用何种架构模式，都应遵循以下最佳实践进行服务器端错误处理：

- **为您的错误响应提供一个清晰且一致的结构：** 当错误发生时，您的API错误响应应遵循一个既定的结构，且在所有请求中保持一致。此外，您的API响应应该是幂等的，以使结构和响应更加可预测。
- **使用描述性错误消息：** 错误消息应该清晰且富有描述性。您的API消费者应该能够从读取的错误消息中理解问题所在以及如何修复。
- **不要泄露敏感数据：** 要小心不要在错误消息中泄露任何敏感信息。错误消息应该仅包含有关问题和可能的修复方法的信息。
- **记录常见错误：** 清晰且详尽的API文档应该包含其错误消息结构的详细信息。[API文档](https://www.postman.com/api-platform/api-documentation/)应该包括可能的错误代码、常见错误消息和补救建议。
- **实施日志记录和监控：** 一些错误可能难以调试，因为它们是多个API调用的结果。因此重要的是要实施[API监控](https://www.postman.com/api-platform/api-monitoring/)和日志记录，这使得跟踪API交互和调试错误变得更容易。在某些API中，`requestId` 和 `timestamp` 参数作为错误响应的一部分返回，这些信息可以帮助进行日志记录和调试。

## 客户端处理API错误的一些最佳实践是什么？

开发者在[API集成](https://www.postman.com/api-platform/api-integration/)过程中经常遇到错误。这些错误可能是由不正确的实现、用户操作或API自身的内部服务器错误引起的。重要的是，开发者需要正确处理这些错误，并以直接、非技术性的方式将它们呈现给最终用户。以下最佳实践为API集成期间成功处理错误奠定了基础——无论API的架构模式如何：

- **验证用户输入：** 用户有时会提供无效的输入数据，可能会导致错误。客户端验证有助于防止这一问题。验证不仅确保用户可以更快地看到并修复问题，还有助于客户端和服务器节省本来会用于额外网络流量的资源。
- **提供用户友好的消息：** 避免直接向最终用户展示来自服务器的错误消息是很重要的。相反，这些技术性错误消息应该被简化并变得更加用户友好。它们还应该清晰地告诉用户如何修复错误。
- **处理多个边缘情况：** 开发者应该理解API可能产生的全部错误范围，以便他们能够处理每一个边缘情况。未处理的边缘情况可能导致默认或模糊的错误消息，可能无助于用户修复问题。

## 针对流行的API架构模式，错误处理的一些最佳实践是什么？

不同的API架构模式有不同的API错误处理方法，开发者社区为这些不同架构确定了错误处理的最佳实践。在本节中，我们将探讨这些特定架构的API错误处理最佳实践。

### REST的错误处理

[REST](https://blog.postman.com/rest-api-examples/)为客户端和服务器之间资源共享提供了简单且统一的界面。它使用标准的HTTP方法对资源执行CRUD（创建、读取、更新和删除）操作。REST API使用标准的[HTTP状态代码](https://blog.postman.com/what-are-http-status-codes/)来指示请求的结果。这些状态代码可以立即用于确定请求是否成功或是否发生了错误。

当使用REST API时处理错误的一些最佳实践包括：

- **正确使用HTTP状态代码：** REST API在很大程度上依赖于标准的HTTP状态代码来传达错误的性质。确保您为每种情况使用适当的状态代码至关重要。
- **在错误消息中提供足够的细节：** REST本质上是无状态的。这意味着所有错误消息都必须提供客户端需要的信息，以便在不依赖先前请求的上下文中理解错误。
- **使用标准化的错误响应格式：** 保持错误消息的一致标准至关重要。例如，大多数REST API包含`error`、`message`、`code`（特定于您应用的内部错误代码）和有时`details`（提供额外信息）等字段。

作为示例，让我们考虑以下假设用于通过其ID获取特定用户信息的HTTP REST API请求：

`curl -i -X GET https://api.example.com/api/v1/users/12345`

如果提供的用户ID错误，且数据库中不存在给定ID的用户，则格式良好且提供适当细节的错误消息应如下所示：

```json
{
  "status": "error", // 这可以是‘error’或‘success’
  "statusCode": 404,
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "未找到请求的资源。",
    "details": "ID为'12345'的用户在我们的记录中不存在。",
    "timestamp": "2023-12-08T12:30:45Z",
    "path": "/api/v1/users/12345",
    "suggestion": "请检查用户ID是否正确或参考我们的文档 https://api.example.com/docs/errors#RESOURCE_NOT_FOUND 获取更多信息。"
  },
  "requestId": "a1b2c3d4-e5f6-7890-g1h2-i3j4k5l6m7n8",
  "documentation_url": "https://api.example.com/docs/errors"
}
```

此响应有效因为它：

- 使用`status`字段让您一眼看出请求是失败还是成功。
- 提供了错误的清晰原因、额外细节和建议修复方法，以及错误页面文档的链接。
- 有清晰、一致和标准化的结构。

### GraphQL的错误处理

[GraphQL](https://blog.postman.com/what-is-a-graphql-api-how-does-it-work/)是一个用于API的查询语言，以及用于使用您为数据定义的类型系统执行查询的服务器端运行时。它向客户端暴露了一个用于查询和变更数据的单一端点——并允许客户端请求并接收所需的特定数据，而无需将请求串在一起。GraphQL使用三种操作——变更、查询和订阅——来进行数据变更、查询以及促进客户端和服务器之间的实时通信。

GraphQL是传输不可知的，虽然[HTTP](https://blog.postman.com/what-is-http/)是其最常用的传输协议，但它也可以使用其他传输协议，如WebSockets。这意味着状态代码不能用来传达GraphQL API请求的状态，即使在使用HTTP作为传输协议时，即使有错误响应，也可能会有200 OK状态代码。

GraphQL规范清楚地定义了如何[处理GraphQL错误](https://spec.graphql.org/draft/#sec-Errors)，以及如何在响应请求时结构化和返回错误。GraphQL中的错误作为`errors`字段返回，该字段是错误对象的数组。每个对象可以包含以下字段：

- `message`：描述错误的字符串。此字段是必需的，提供了错误的人类可读描述。
- `locations`（可选）：位置列表，每个位置是一个带有`line`和`column`字段的对象。这两个字段都是正整数。`locations`字段用于指示错误发生在GraphQL文档的哪个位置。
- `path`（可选）：路径段列表，每个段要么是字段名，要么是整数。这个字段有助于识别哪部分查询对错误负责。
- `extensions`（可选）：服务器可以使用此字段添加与错误相关的额外信息。它是一个对象，通常包括错误代码或其他特定于上下文的细节。

在处理GraphQL API错误时的一些最佳实践包括：

- **处理字段级错误：** GraphQL可以在同一响应中返回数据和错误，因此处理可以返回数据与失败部分查询的错误的情况很重要。参见下面的示例。
- **谨慎实现重试逻辑：** 对于响应遇到瞬态错误的请求进行重试时，重要的是要区分对待查询和变更。例如，失败的查询可能触发重试，而失败的变更则可能不会——至少在没有严格验证的情况下不会。
- **使用错误扩展：** GraphQL扩展允许您在错误响应中包含GraphQL规范本身不提供的附加信息。例如，错误扩展可用于提供诸如错误代码、时间戳或文档url等细节。

考虑以下对`https://api.example.com/graphql`端点的GraphQL query，它通过用户的ID获取有关用户的信息：

```
query {
  user(id: "12345") {
    id
    name
    email
  }
}
```

如果提供的用户ID错误，且数据库中不存在给定ID的用户，则格式良好且提供适当细节的错误消息应如下所示：

```json
{
  "data": {
    "user": null
  },
  "errors": [
    {
      "message": "未找到用户",
      "locations": [{ "line": 1, "column": 8 }],
      "path": ["user"],
      "extensions": {
        "code": "USER_NOT_FOUND",
        "timestamp": "2023-12-08T12:30:45Z",
        "details": "ID为'12345'的用户在我们的记录中不存在。",
        "documentation_url": "https://api.example.com/docs/errors#USER_NOT_FOUND"
      }
    }
  ]
}
```

此错误有效因为它：

- 符合GraphQL规范。它以数组形式返回错误，指定有关错误位置和路径的信息，并提供了简短但描述性的错误消息。
- 使用扩展提供了有关错误的附加信息。这包括自定义错误代码（这对于集成此API的客户端很有帮助）、时间戳、更详细的错误描述以及了解有关类似错误的更多信息的文档链接。
- 包括一个`data`字段，其中`user`字段为`null`，表示无法检索到数据。

如果您想了解更多关于GraphQL中错误处理的信息，请查看我们学习中心的[这篇文章](https://learning.postman.com/open-technologies/blog/graphql-error-handling/)。

### gRPC的错误处理

[gRPC](https://blog.postman.com/what-is-grpc/)是一个支持分布式环境中的服务到服务通信的架构驱动框架。它是RPC（远程过程调用）协议的一种语言不可知实现，支持使用HTTP/2和协议缓冲区（Protobuf）进行流式传输和强类型服务合同。

gRPC使用其自己的一套状态代码来表示gRPC调用中的各种错误状态。这些状态代码可以与一个可选的错误消息结合使用，提供有关错误的额外信息。然而，使用这两种方法仍然非常有限，并且无法提供关于错误充分的信息。官方gRPC文档表示，使用Protobuf的人应该利用[Google开发的更丰富的错误模型](https://cloud.google.com/apis/design/errors#error_model)，但这种方法有其自身的局限性。例如，从语言到语言，该错误模型的实现可能会有所不同，并且并不是所有语言都完全支持它。

这里是一些处理gRPC中错误的推荐最佳实践：

- **使用合适的状态码：** gRPC提供了自己的标准[状态码](https://grpc.io/docs/guides/error/#error-status-codes)（例如OK、INVALID_ARGUMENT、NOT_FOUND、INTERNAL和UNAVAILABLE）。确保返回能够充分描述错误性质的状态码。例如，对于客户端参数错误使用INVALID_ARGUMENT，对于网络错误使用UNAVAILABLE。
- **使用元数据提供额外上下文：** 虽然官方文档推荐使用Google的错误模型，但利用gRPC的自定义元数据功能发送有关错误的额外信息也很重要。这可以包括应用特定的错误代码或有助于调试的上下文详细信息。此外，您应确保元数据具有一致且结构良好的格式。
- **在客户端实现健壮的错误处理：** 客户端应始终考虑所有gRPC标准错误代码。例如，对于可能是暂时性的错误，如UNAVAILABLE，重要的是实施重试逻辑。然而，重试应该是上下文敏感的，并且要谨慎使用，特别是对于非幂等操作。

## Postman如何帮助您更高效地处理API错误？

Postman [API平台](https://www.postman.com/api-platform/)包括许多功能，可以帮助API生产者和消费者更高效地处理错误。通过Postman，您可以：

- **使用脚本验证API响应：** [Postman脚本](https://learning.postman.com/docs/writing-scripts/intro-to-scripts/)允许您编写类似Mocha和Chai的测试，这些测试根据特定断言验证您的API响应。这使在Postman中测试API时更容易捕获客户端错误。
- **定期检查错误：** [Postman Monitors](https://learning.postman.com/docs/monitoring-your-api/intro-monitors/)自动在预定的间隔时间运行您的Postman集合，并在任何测试断言失败时通知您。Monitors还提供有关您的请求的额外信息，包括状态码、时间戳、延迟、失败率、日志语句等。
- **保存错误响应示例：** Postman使用户能够[保存不同错误响应或场景的示例](https://learning.postman.com/docs/sending-requests/examples/)。这些示例帮助开发者知道特定请求场景下预期的响应。它们还可以用于创建[模拟服务器](https://learning.postman.com/docs/designing-and-developing-your-api/mocking-data/setting-up-mock/)，并可包含在发布的集合文档中。
