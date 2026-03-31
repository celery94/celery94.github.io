---
pubDatetime: 2026-03-31T07:38:17+08:00
title: "Generative AI for Beginners .NET 第二版：全面重写，升级至 .NET 10"
description: "微软发布《Generative AI for Beginners .NET》课程第二版，五个模块从零重写，全面迁移到 .NET 10 和 Microsoft.Extensions.AI，新增 Microsoft Agent Framework 课程，适合想系统学习 .NET AI 开发的开发者。"
tags: [".NET", "AI", "Generative AI", "Microsoft.Extensions.AI", "教程"]
slug: "generative-ai-for-beginners-dotnet-v2"
ogImage: "../../assets/691/01-cover.png"
source: "https://devblogs.microsoft.com/dotnet/generative-ai-for-beginners-dotnet-version-2-on-dotnet-10/"
---

微软发布了[《Generative AI for Beginners .NET》](https://aka.ms/genainet)课程的第二版。这是一个免费开源的课程，面向想在 .NET 里构建 AI 应用的开发者。

第二版不是小幅迭代，是从头重写的。课程结构从一批零散的示例重新组织成五个有完整解释的模块，底层库从 Semantic Kernel 换成了 Microsoft.Extensions.AI，所有示例升级到 .NET 10。如果你学过第一版，这是一门不一样的课。

![Generative AI for Beginners .NET 第二版封面公告图](../../assets/691/01-cover.png)

## 五个模块，全部重写

第一版的课程结构相对松散，第二版用五个有顺序的模块取而代之：

| 模块 | 标题 | 核心内容 |
|------|------|----------|
| 01 | [生成式 AI 基础](https://github.com/microsoft/Generative-AI-for-beginners-dotnet/blob/main/01-IntroductionToGenerativeAI/readme.md) | 生成式 AI 与传统编程的区别、.NET 在 AI 开发中的地位、Microsoft AI 技术栈，以及 GitHub Codespaces 和本地环境配置 |
| 02 | [生成式 AI 技术](https://github.com/microsoft/Generative-AI-for-beginners-dotnet/blob/main/02-GenerativeAITechniques/readme.md) | 聊天补全、提示工程、函数调用、RAG、推理模式、结构化输出，以及 Microsoft.Extensions.AI 的使用方式 |
| 03 | [AI 模式与应用](https://github.com/microsoft/Generative-AI-for-beginners-dotnet/blob/main/03-AIPatternsAndApplications/readme.md) | 语义搜索、检索增强生成（RAG）、文档处理应用，以及各种模式的适用场景和组合方式 |
| 04 | [Agents 与 Microsoft Agent Framework](https://github.com/microsoft/Generative-AI-for-beginners-dotnet/blob/main/04-AgentsWithMAF/readme.md) | Agent 与聊天机器人的区别、工具调用、多 Agent 协作编排、MCP 集成 |
| 05 | [负责任的 AI](https://github.com/microsoft/Generative-AI-for-beginners-dotnet/blob/main/05-ResponsibleAI/readme.md) | 偏见识别与缓解、内容安全与护栏、系统可解释性，以及 Agent 系统特有的伦理问题 |

每个模块都完整解释背后的概念，展示可运行的示例代码，并有清晰的学习路径。作者的说法是"不只教你怎么调 API，而是解释模式为什么这样设计，以及如何在真实应用里落地"。

## 全面迁移到 .NET 10

所有示例现在都使用 .NET 10 的现代化模式，包括依赖注入、中间件管道，以及 .NET 10 引入的基于文件的应用模型。

认证方式也统一了。所有基于文件的示例现在统一使用 `AzureCliCredential`——在 Azure CLI 里认证一次，所有示例自动识别，不需要跨项目管理连接字符串和 API Key。

模型引用已更新为 `gpt-4o-mini`（文档里写的是 `gpt-5-mini`，对应最新可用模型的引用方式）。

## Microsoft.Extensions.AI 替代 Semantic Kernel

第一版用 Semantic Kernel 作为调用 AI 模型的核心方式。第二版切换到 Microsoft.Extensions.AI（MEAI）。

切换的原因直接：MEAI 是 .NET 10 生态的一部分，遵循和 `ILogger`、`IConfiguration` 同样的设计哲学，跨 Provider 使用不会绑定到特定的编排框架。

实际效果是代码变简单了。一个基础的聊天补全，之前需要配置 SK Kernel、插件和连接器，现在走标准的 .NET 服务注册，用 `IChatClient` 和 MEAI 中间件管道完成。课程也包含了一个经典的太空侵略者示例，展示如何把传统应用和 AI 能力集成在一起。

## RAG 示例切换到原生 SDK

11 个纯 Semantic Kernel 的 RAG 示例移到了 `samples/deprecated/` 目录。它们还能编译和运行，但不再是主学习路径的一部分。

混用了 SK 和 MEAI 的示例（比如 `BasicChat-05AIFoundryModels` 和 `BasicChat-11FoundryClaude`）去掉了 SK 依赖，完全切换到 MEAI。

作者的解释是：入门课应该先教基础层，在 .NET 10 里基础层就是 MEAI，Agent 场景的首选工具是 Microsoft Agent Framework。

## Microsoft Agent Framework 正式进入课程

第四个模块专门覆盖 Microsoft Agent Framework，当前处于 RC 阶段，课程材料里已有完整文档。五个 MAF Web 应用示例涵盖多 Agent 编排、PDF 摄取和聊天中间件模式。

## 翻译同步更新

八种语言翻译（中文、法语、葡萄牙语、西班牙语、德语、日语、韩语、繁体中文）已同步更新，反映新的模块结构、废弃变更和 .NET 10 迁移内容。

## 如何开始

访问 [https://aka.ms/genainet](https://aka.ms/genainet)，选择一个 Provider（Microsoft Foundry 或本地开发用 Ollama），从第一个模块开始，按顺序学完五个模块。每个模块都建立在前一个的基础上。

遇到问题可以[提 Issue](https://github.com/microsoft/Generative-AI-for-beginners-dotnet/issues)，想参与贡献的话[PR 欢迎提交](https://github.com/microsoft/Generative-AI-for-beginners-dotnet/pulls)。

## 参考

- [Generative AI for Beginners .NET: Version 2 on .NET 10](https://devblogs.microsoft.com/dotnet/generative-ai-for-beginners-dotnet-version-2-on-dotnet-10/)
- [课程 GitHub 仓库](https://aka.ms/genainet)
- [Microsoft.Extensions.AI 文档](https://learn.microsoft.com/en-us/dotnet/ai/ai-extensions)
