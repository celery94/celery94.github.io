---
pubDatetime: 2024-02-19T12:38:15
tags: [.net, .net-9, cloud-native, ai]
source: https://devblogs.microsoft.com/dotnet/our-vision-for-dotnet-9/
title: 我们对 .NET 9 的愿景 - .NET 博客
description: 欢迎来到 .NET 9！了解我们如何在各种应用程序中改进 .NET，特别关注云原生、AI 和性能。
---

# 我们对 .NET 9 的愿景 - .NET 博客

> ## 摘录
>
> 欢迎来到 .NET 9！了解我们如何在各种应用程序中改进 .NET，特别关注云原生、AI 和性能。
>
> 本文翻译自 [.NET 博客](https://devblogs.microsoft.com/dotnet/our-vision-for-dotnet-9/)，原文作者为 .NET Team。

---

2024年2月13日

欢迎进入 .NET 9！我们处于又一个年度发布周期的开始阶段，继几个月前成功推出 .NET 8 之后。我们建议开发者将他们的应用转移到 [.NET 8](https://devblogs.microsoft.com/dotnet/announcing-dotnet-8/)。在这篇文章中，我们将分享我们对 .NET 9 的初步愿景，该版本计划在年底的 .NET Conf 2024 上发布。我们最重要的关注领域是云原生和智能应用开发。你可以期待在性能、生产力和安全性方面的重大投资，以及整个平台的进步。

今天，让我们来看看.NET 9的重点领域和我们计划与Microsoft的合作伙伴团队一起交付的补充集成。我们的目标是通过使用Visual Studio，Visual Studio Code与C# Dev Kit，以及使用Azure服务使云部署更加容易，来使.NET开发更加高效。我们将继续与我们的行业合作伙伴，如Canonical和Red Hat紧密合作，以确保无论您在何处使用.NET，都能获得出色的体验。

.NET 9 的开发正向前迈出了又一大步。今天我们发布了 [.NET 9 预览版 1](https://aka.ms/dotnet/9/preview1)，欢迎大家就[我们交付的所有新功能](https://learn.microsoft.com/dotnet/core/whats-new/dotnet-9/overview)提出反馈。

## 面向 Cloud-Native 开发者的平台

我们在过去几年中一直致力于构建[强大的云原生基础设施](https://devblogs.microsoft.com/dotnet/category/containers/)，比如[运行时性能](https://devblogs.microsoft.com/dotnet/category/performance/)和[应用程序监控](https://learn.microsoft.com/dotnet/core/diagnostics/)。我们将继续这项工作。我们还将把焦点转向为流行的生产基础设施和服务提供便捷的途径，例如在Kubernetes中运行以及使用像Redis这样的托管数据库和缓存服务。我们将在.NET堆栈的多个层面交付这些改进。这些能力都在[.NET Aspire](https://devblogs.microsoft.com/dotnet/category/dotnet-aspire/)中汇集在一起，它显著降低了构建云应用程序的成本和复杂性，以及开发与生产之间的差距。

我们一直在开发 Native AOT 和应用程序[裁剪](https://devblogs.microsoft.com/dotnet/creating-aot-compatible-libraries/)作为优化生产应用的关键工具。在 .NET 8 中，我们优化了 Web API 应用程序（使用 `webapiaot` 模板），以实现裁剪和 AOT 的优化。在 .NET 9 中，我们正致力于对其他应用程序类型采取相同的措施，并改进所有 ASP.NET Core 应用程序的 [DATAS GC](https://maoni0.medium.com/dynamically-adapting-to-application-sizes-2d72fcb6f1ea)。

我们的 Azure Container Apps 合作伙伴将确保 .NET 9 应用程序能够在其基于 Kubernetes 的环境中轻松扩展到多个实例。我们正与他们合作确保短暂数据——如防伪和授权令牌——使用 [Data Protection](https://learn.microsoft.com/aspnet/core/security/data-protection/introduction) 正确加密，以及改善速率限制 API，以确保每个节点的最佳行为。

[eShop](https://github.com/dotnet/eshop)参考架构示例应用在去年的.NET Conf上展出，将会随着.NET 9在今年的发展中更新，以利用这些新功能和部署选项。

我们的 Visual Studio 合作伙伴计划改进以支持和增强我们的云平台、Native AOT、.NET Aspire 和 Azure 部署。

本地AOT代码编译需要安装和使用许多.NET开发人员通常不常用的工具。希望进行交叉编译的开发者（例如，在Windows上针对Linux进行目标设置）目前依赖于Docker和/或WSL2，按照我们的[文档](https://learn.microsoft.com/dotnet/core/deploying/native-aot/cross-compile)和[示例](https://github.com/dotnet/dotnet-docker/blob/main/samples/releasesapi/README.md)进行操作。Visual Studio对AOT的支持将扩展，使得更多的开发者能够访问到Native AOT。

Visual Studio 和 Visual Studio Code 将为 .NET Aspire 引入新的开发和部署体验。这将包括配置组件，调试（包括热重载）AppHost 和子进程，并与开发者仪表板完全集成。开发者将能够从 Visual Studio、Visual Studio Code 和使用 Azure Developer CLI（azd）将他们的项目部署到 Azure 容器应用。

## .NET 和人工智能

OpenAI 已经在开发者之间引起了兴奋，因为它提供了用 AI 改造他们应用的机会。在过去的一年里，Azure Open AI 和 .NET 被用来创建 AI 解决方案，其中 Microsoft Copilot 是最受欢迎的。我们将继续与那些寻求使用他们的 C# 技能来构建这类新应用的客户合作，并将迅速投资于我们的 AI 平台。

在 .NET 8 中，我们扩大了我们对 ML.NET 之外的投资。我们专注于 AI 工作量，投资于入门[示例和文档](https://learn.microsoft.com/collections/d2z1bmomeo55kr?source=learn)，并与 AI 生态系统合作伙伴合作，为像 [Qdrant](https://github.com/qdrant/qdrant-dotnet) 和 [Milvus](https://milvus.io/docs/v2.2.x/install-csharp.md) 这样的向量数据库以及像 Semantic Kernel 这样的库提供 C# 客户端。此外，我们还为 .NET 添加了 [TensorPrimitives](https://github.com/dotnet/runtime/issues/92219)。

展望.NET 9，我们致力于让.NET开发者更加容易地将人工智能集成到他们的现有和新应用中。开发者将发现，有很好的库和文档供他们使用OpenAI和OSS模型（托管和本地），我们将继续与Semantic Kernel、OpenAI和Azure SDK合作，确保.NET开发者在构建智能应用时拥有一流的体验。

我们将在整个发布期间更新 GitHub 上的 [ChatGPT + 企业数据与 Azure OpenAI 和 Cognitive Search .NET 示例](https://github.com/Azure-Samples/azure-search-openai-demo-csharp)。

## .NET 9 待办列表

这些云原生和AI项目只是我们将交付的一部分而已。已经为[.NET MAUI](https://github.com/dotnet/maui/wiki/Roadmap)、[ASP.NET Core和Blazor](https://github.com/dotnet/aspnetcore/issues/51834)、[C#](https://github.com/dotnet/roslyn/blob/main/docs/Language%20Feature%20Status.md#working-set)、[F#](https://github.com/orgs/dotnet/projects/126/views/40?query=is%3Aopen+sort%3Aupdated-desc)以及在.NET SDK中交付的其他运行时和工具组件发布了积压工作。在GitHub上查看[.NET 9项目积压工作](https://github.com/dotnet/core/blob/main/roadmap.md)，了解你喜欢的产品领域和功能。

我们定期定义新功能并更新进度。我们将更新我们的待办列表和[.NET 9 发布说明](https://github.com/dotnet/core/tree/main/release-notes/9.0)。我们还在进行一些实验，这些实验可能会成为未来版本的一部分。

## 尝试 .NET 9 预览版 1

[.NET 9 预览版 1](https://aka.ms/dotnet/9/preview1) 现已可供下载。从现在开始，我们将会在 [GitHub Discussions 发布预览版本](https://github.com/dotnet/core/discussions/9131)。我们将会调整我们的 .NET 博客内容，以突出 .NET 8 的优势，旨在支持您在生产环境中使用 .NET 8。

[.NET Aspire 预览版 3](https://github.com/dotnet/aspire/discussions/2205) 今天也开始提供了。这个版本包括对仪表盘的 UI 改进，以及新组件支持，包括 Azure OpenAI、Kafka、Oracle、MySQL、CosmosDB 和 Orleans。

如果预览版不是你的菜，请看一下[.NET 8 发布文章](https://devblogs.microsoft.com/dotnet/announcing-dotnet-8/)。我们收到了很多关于早期 .NET 8 部署的好评。从 .NET 8（以及之前的版本）迁移到 .NET 9 应该非常容易。

## 谢谢您

.NET 之所以令人赞叹，全因为你们——.NET 社区的成员，你们帮助推动了 .NET 的发展。我们想要感谢每一个帮助使这个以及每一个版本变得出色的人，通过创建问题(issue)，发表评论，贡献代码，创建包(package)，参加直播，以及在线上和他们的本地区域活跃的人。在[.NET 9 发布说明](https://github.com/dotnet/core/tree/main/release-notes/9.0)中，你会发现每个版本的社区成员亮点。
