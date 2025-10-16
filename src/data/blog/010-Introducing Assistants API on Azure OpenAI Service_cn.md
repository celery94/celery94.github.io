---
pubDatetime: 2024-02-18T16:10:18
tags: ["AI", "Productivity"]
  [
    Azure,
    OpenAI,
    AI,
    Assistants,
    API,
    GPT,
    Text-to-Speech,
    TTS,
    Embeddings,
    Fine-tuning,
  ]
source: https://techcommunity.microsoft.com/t5/ai-azure-ai-services-blog/azure-openai-service-announces-assistants-api-new-models-for/ba-p/4049940
author: monalisawhalin
title: 在 Azure OpenAI 服务上引入 Assistants API。
description: Introducing Assistants API on Azure OpenAI Service enabling developers to easily build stateful AI-powered assistants in a secure environment with the latest GPT models.
---

# 介绍Azure OpenAI服务上的Assistants API，使开发人员能够轻松在安全环境中使用最新的GPT模型构建有状态的AI辅助工具。

> 作者：[Mona Lisa Whalin](https://techcommunity.microsoft.com/t5/ai-azure-ai-services-blog/azure-openai-service-announces-assistants-api-new-models-for/ba-p/4049940)

---

全球的开发者自2023年1月Azure OpenAI Service发布以来，正在建立创新的生成式AI解决方案。全球已有超过53,000个客户利用开阔的生成式AI模型的能力，这些模型得到了Azure云和计算基础设施的强大承诺支持，背后是企业级的安全性。

今天，我们非常高兴地宣布服务中的许多新功能，模型和价格改进。我们正在公开预览中推出Assistants API，新的文本转语音功能，即将更新的 GPT-4 Turbo 预览和 GPT-3.5 Turbo 的模型，新的嵌入模型和微调 API 的更新，包括一个新模型，对连续微调的支持，以及更好的定价。让我们详细探讨我们的新产品。

### **使用Assistants API在您的应用中构建复杂的副驾驶体验**

我们很高兴地宣布，**[Assistants](https://aka.ms/oai/assistant-how-to)**，Azure OpenAI Service的新功能，现已在公开预览中开放。Assistants API使开发人员能够在他们自己的应用程序中创建高质量的副驾驶员般的体验。过去，即使是经验丰富的开发者，构建定制的AI助手也需要大量工作。虽然聊天完成API轻量级且强大，但它本质上是无状态的，这意味着开发人员必须手动管理对话状态和聊天线程、工具集成、检索文档和索引以及执行代码。作为聊天完成API的**有状态**演化，Assistants API为这些挑战提供了解决方案。

<iframe src="https://www.youtube.com/embed/CMXtAe5DhXc?si=d50cvqTRH2ijRavw" width="560" height="315" frameborder="0" allowfullscreen="allowfullscreen" title="YouTube video player" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"></iframe>

构建可定制的、专门打造的AI，可以筛选数据，提供解决方案，并自动化任务，现在变得更加简单。Assistants API支持持久且无限长的**线程**。这意味着作为开发者，你不再需要开发线程状态管理系统，也不必绕过模型的上下文窗口限制。一旦你创建了线程，你就可以简单地在用户响应时向其添加新消息。助手可以访问**多种格式的文件** - 无论是创建助手时，还是作为线程的一部分。助手还可以根据需要并行访问多个**工具**。这些工具包括:

- [**Code Interpreter**](https://aka.ms/oai/assistant-code-interpreter)**:** 这是一个由Azure OpenAI Service托管的工具，它允许你在一个沙盒环境中编写并运行Python代码。使用案例包括迭代解决复杂的代码和数学问题，对用户添加的多种格式的文件进行高级数据分析，并生成如图表和图形等的数据可视化。
- [**Function calling**](https://aka.ms/oai/assistant-function-calling)**:** 你可以向你的助理描述你的应用或外部API的功能，让模型智能地决定何时调用这些函数，并将函数响应合并到其消息中。

即将提供对新功能的支持，包括改进的知识检索工具。

Assistants API基于支持OpenAI的GPT产品的相同功能构建，并为创建各种类似copilot的应用程序提供了无与伦比的灵活性。使用案例包含广泛的范围：AI驱动的产品推荐器，销售分析应用程序，编码助手，员工Q&A聊天机器人等等。开始在无代码的[Assistants playground](https://oai.azure.com/portal) 上进行构建，然后开始使用API。了解更多关于Assistants定价的信息[这里](https://azure.microsoft.com/en-us/pricing/details/cognitive-services/openai-service/)。

与我们其他的产品一样，你提供给Azure OpenAI Service的数据和文件不会被用于改进OpenAI模型或任何微软或第三方产品或服务，开发者可以根据自己的需要删除数据。更多关于Azure OpenAI Service的数据、隐私和安全性信息，请点击[这里](https://learn.microsoft.com/en-us/legal/cognitive-services/openai/data-privacy)。我们建议使用可信赖的数据源。通过Function调用、Code Interpreter与文件输入和Assistant Threads功能获取不受信任的数据可能会破坏你的Assistant或使用Assistant的应用程序的安全性。了解缓解方法，请点击[<u>这里</u>](https://aka.ms/oai/assistant-rai)。

### **微调：新模型支持、新功能和更低的价格**

自从我们在2023年10月16日发布Azure OpenAI服务为OpenAI的Babbage-002、Davinci-002和GPT-35-Turbo提供微调以来，我们已经使AI开发者能够构建自定义模型。今天，我们发布**OpenAI的GPT-35-Turbo 1106微调[support](https://aka.ms/oai/fine-tuning-models)**，这是一个新一代的GPT-3.5 Turbo模型，具有更强的指令跟踪、JSON模式、可复现的输出、并行函数调用等等。使用GPT-35-Turbo 1106微调支持训练数据中的16k上下文长度，使您能够对更长的消息进行微调，并生成更长且更有连贯性的文本。

此外，我们正在推出两个新功能，使您可以创建更复杂的自定义模型，并轻松更新它们。首先，我们正在推出对**[函数调用进行微调](https://aka.ms/oai/fine-tuning-functions)**的支持，该功能使您可以教导您的自定义模型何时进行函数调用，并提高响应的准确性和一致性。其次，我们正在推出对[**连续微调**](https://aka.ms/oai/fine-tuning-continuous)的支持，它允许您使用新数据对以前微调过的模型进行训练，而不会丧失模型之前的知识和性能。这让您可以在不从头开始的情况下向现有的自定义模型添加额外的训练数据，并让您可以更迭代地进行实验。

除了新模型支持和特性，我们正在使在Azure OpenAI Service上训练和托管您的精细调整模型更易负担，包括降低训练和托管GPT-3.5-Turbo的成本50%。

### **即将上市：新型号和型号更新**

以下的模型和模型更新将在本月来到Azure OpenAI Service。您可以[在这里](https://aka.ms/oai/feb-models)查看最新的模型可用性。

#### 更新的GPT-4 Turbo预览版和GPT-3.5 Turbo模型

我们正在推出一个[更新的GPT-4 Turbo预览模型](https://aka.ms/oai/feb-0125-preview)，**gpt-4-0125-preview**，在诸如代码生成等任务中作出改进，并减少了模型“懒惰”不完成任务的情况。新模型修复了影响非英语UTF-8生成的一个错误。发布后，我们将开始更新使用GPT-4版本1106-preview的Azure OpenAI部署，以使用版本0125-preview。更新将在发布日期后两周开始，并在一周内完成。由于版本0125-preview提供了改进的功能，客户可能会注意到升级后模型行为和兼容性的一些变化。GPT-4-0125-preview现在在东美，北中部美国和南中部美国已经上线。gpt-4-0125-preview的价格将与gpt-4-1106-preview的价格相同。

除了更新的GPT-4 Turbo，我们还将推出**gpt-3.5-turbo-0125**，这是一款新的GPT-3.5 Turbo模型，具有更优的定价和在各种格式上回应的更高准确性。我们将为新模型的输入价格降低50%，至$0.0005 /1K tokens，输出价格降低25%，至$0.0015 /1K tokens。

#### 新的文本到语音（TTS）模型

我们的新型**[文字转语音模型](https://techcommunity.microsoft.com/t5/ai-azure-ai-services-blog/announcing-openai-text-to-speech-voices-on-azure-openai-service/ba-p/4049696)**可以在**六种预设声音**中，每种都有其自己的个性和风格，将文本转变为人类般的语音。该模型有两种变体，包括**tts-1**，这是标准的语音模型变体，专为实时用例优化，以及**tts-1-hd**，这是高清(HD)的等价物，优化了质量。这个新模型包括如在Azure AI中已经可用的构建自定义声音和头像等功能，并且让客户能够在客户支持、培训视频、现场直播等领域中构建全新体验。开发人员现在可以通过Azure OpenAI Service和Azure AI Speech两个服务访问这些声音。

#### 一代新的嵌入模型，价格更低

Azure OpenAI Service的用户一直在他们的应用中融入embeddings模型，以个性化，推荐和搜索内容。我们很高兴宣布一代更有能力的embeddings模型，可以满足各种客户需求。这些模型将在本月稍后可用。

- **text-embedding-3-small** 是一个新的、更小且高效的embeddings模型，相比其前身text-embedding-ada-002提供了**更强的性能**。由于其高效性，这个模型的定价是每1000 tokens $0.00002，与text-embedding-ada-002相比，价格**降低了5倍**。我们并未废弃text-embedding-ada-002，所以如果需要，你可以继续使用上一代模型。
- **text-embedding-3-large** 是我们最新的最佳性能嵌入模型，它可以创建多达3072维的嵌入。这种大型嵌入模型的定价为 $0.00013 / 1k tokens。

两种嵌入模型都提供了**缩短嵌入的原生支持** (即从序列末端删除数字)，而不会使嵌入失去其概念代表性属性。这使您能够在使用嵌入的性能和成本之间进行权衡。

### **下一步是什么**

很高兴看到开发人员已经使用Azure OpenAI Service构建了什么。您可以进一步加速您的企业AI转型，使用我们今天公布的产品。探索以下资源以开始或了解更多关于Azure OpenAI Service的信息。

- 开始使用Azure OpenAI [助手](https://learn.microsoft.com/en-us/azure/ai-services/openai/assistants-quickstart) (预览版)
- 使用 [Assistants GitHub repo](https://aka.ms/assistants-api-in-a-box) 中的代码示例来加速Assistants API的开发
- [现在就申请](https://customervoice.microsoft.com/Pages/ResponsePage.aspx?id=v4j5cvGGr0GRqy180BHbR7en2Ais5pxKtso_Pz4b1_xUNTZBNzRKNlVQSFhZMU9aV09EVzYxWFdORCQlQCN0PWcu)以获得Azure OpenAI服务的访问权限
- 查看 Azure OpenAI Service 的[文档](https://learn.microsoft.com/en-us/azure/cognitive-services/openai/)
- 更多关于[Azure OpenAI Service 的数据，隐私和安全性](https://learn.microsoft.com/en-us/legal/cognitive-services/openai/data-privacy)的信息
- 将 [What's New](https://learn.microsoft.com/en-us/azure/cognitive-services/openai/whats-new)页签加入书签，用于持续跟踪最新和未来的公告更新
- Skilling: [生成式AI训练基础](https://learn.microsoft.com/en-us/training/modules/fundamentals-generative-ai/) 和 [使用Azure OpenAI Service开发生成式AI解决方案](https://learn.microsoft.com/en-us/training/paths/develop-ai-solutions-azure-openai/)

**我们迫不及待想看到你下一步会构建什么!**
