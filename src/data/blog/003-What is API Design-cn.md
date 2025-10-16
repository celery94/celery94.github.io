---
title: API设计是什么？原则与最佳实践
pubDatetime: 2024-01-26
slug: what-is-api-design
featured: false
draft: false
tags: [".NET", "ASP.NET Core"]
description: 了解API设计是什么，以及它如何帮助团队交付适应性强、可测试且文档齐全的API给使用者。
---

## 什么是API设计？

API设计是有意识地决定API如何向其使用者暴露数据和功能的过程。成功的API设计以标准化的规范格式描述API的端点、方法和资源。

API设计过程通过确保API在支持业务目标的同时保持易用、适应性强、可测试和文档齐全，从而使消费者和生产者受益。API设计应在[API生命周期](https://blog.postman.com/api-lifecycle-blueprint/)的早期进行，以实现关键利益相关者之间的一致性，并帮助团队在问题根深蒂固之前发现它们。API设计也是有效的[API治理](https://blog.postman.com/api-governance-with-postman-v10/)策略的重要部分，因为它帮助团队标准化可以在其组织中重复使用的API模式。

在这里，我们将探讨API设计与[API优先开发模型的关系、API设计的关键阶段、API设计中模拟的作用，以及Postman](https://www.postman.com/api-first/) [API平台](https://www.postman.com/api-platform/)如何帮助您的组织实施成熟的API设计流程。

![API早期. 插图.](https://voyager.postman.com/illustration/api-portal-window-illustration-postman.svg)

## API设计如何支持API优先的开发模型？

API优先是一种开发模型，在该模型中，应用程序是通过API提供的服务来概念化和构建的。与将API视为事后考虑的代码优先公司不同，API优先公司在开发应用程序之前设计他们的API。这种策略使消费者和生产者能够在实现建设之前协作定义API，从而提高API的质量和可用性。

---

![Postmanaut检查清单. 插图.](https://voyager.postman.com/illustration/checklist-clipboard-postman-illustration.svg)

## API设计的关键阶段是什么？

API设计过程中有四个关键步骤，每个组织都应遵循。每个步骤都需要利益相关者（如业务领导者、开发人员、消费者和合作伙伴）之间的协作，以确保API满足所有相关需求。在API设计过程的每一步都进行协作还有助于开发人员避免构建不必要的功能。这些步骤包括：

### 步骤1：确定API的预期用途

API设计过程的第一步是所有利益相关者就API的业务用例达成一致。负责身份验证工作流的API将与允许用户浏览产品目录的API有不同的要求，因此在做出任何其他决策之前，就用例达成一致很重要。[用例可能还会对您选择的架构类型产生影响。](https://www.postman.com/state-of-api/api-technologies/#api-technologies) 例如，一个[gRPC](https://blog.postman.com/postman-v10-and-grpc-what-you-can-do/)基础架构可能最适合连接内部微服务的API，而GraphQL API则非常适合依赖于不同数据源的服务。一旦达成一致，利益相关者应该清楚地概述他们对API的目标，用自然语言描述

它将如何满足特定需求。

### 步骤2：用规范定义API合约

一旦所有利益相关者就API的用例达成一致，您将需要决定所需的资源、其数据的格式和结构、它们应如何相互关联，以及哪些方法应在其关联的端点上可用。确定您的API中抽象和封装的期望水平也很重要，这将帮助您在可重用性和可读性之间找到平衡。

这些决策应该在API定义中捕获，这是API预期功能的人类和机器可读表示。API定义遵循API规范，如[OpenAPI](https://blog.postman.com/openapi-specification-postman-how-to/)和[AsyncAPI](https://blog.postman.com/asyncapi-joins-forces-with-postman-future-of-apis/)，为API定义提供了标准化格式，并为API合约、文档、模拟和测试奠定了基础。

### 步骤3：用模拟和测试验证您的假设

一旦您完成了API定义，您可以用它来生成模拟服务器。模拟服务器对请求返回样本数据，使您能够确认您的API将按照您的意图工作。模拟还可以与API测试一起使用，这些测试可以手动进行、按计划运行，或者在CI/CD管道中自动运行。在API设计过程中进行测试和模拟将帮助您在它们进入消费者代码库之前、更难修复时捕获并纠正任何问题。

我们将在后面的部分更详细地讨论模拟服务器。

### 步骤4：文档化API

API设计过程的最后一步是编写文档。这一步骤涉及定义每个资源、方法、参数和路径的关键细节，有助于验证设计，并确保消费者能够尽快开始使用您的API。文档可能还包括API请求和响应的示例，这为消费者提供了关于特定API如何支持常见业务需求的关键洞察。一些工具可以从API定义自动生成文档，因此团队不必担心他们的文档过时。

---

![流程实验室. 插图.](https://voyager.postman.com/illustration/postman-flows-lab-illustration.svg)

## API设计中模拟的作用是什么？

模拟，即设置模拟服务器以响应API请求返回样本数据，是API设计过程的重要部分。一旦您的定义完成，就可以引入模拟，这意味着它们可以与测试一起使用，以验证设计选择并确认您的API将按预期工作。模拟不仅使API消费者能够在API仍在开发中时开始集成API，而且还减轻了API生产者发布有缺陷或不完整的实现的压力。这一好处允许内部API的生产者和消费者同时工作，显著缩短了上市时间。

---

## API设计的一些最佳实践是什么？

每个API都不同，因此将需要对API设计采用独特的方法。不过，有几个最佳实践您应始终牢记，无论API的架构、语言或用例如何。例如，重要的是：

- **优先考虑一致性**：一致性是成功API设计的关键因素，因此对于领导者来说，建立推广组织范围标准的API治理策略至关重要。例如，组织的每个API都应对每个方法、端点和资源使用一致的命名约定。
- **收集每个利益相关者的意见**：API设计问题通常源于沟通不良。每个利益相关者可能都有可能影响API设计和实现的领域特定知识，他们应该被纳入每次讨论。
- **了解API的上下文和约束**：团队必须在做出任何设计决策之前清楚地了解API的上下文和约束。例如，重要的是要考虑竞争项目时间表、底层系统的限制和预期的流量。这些知识将使团队能够做出明智的决策，为API的成功奠定基础。

---

## 关于API设计的其他常见问题

什么是API优先设计？

API优先设计是一种将API接口合约的质量放在首位的API设计方法。结果产生的API是可复用的、安全的、高效的、直观的，并与组织的目标保持一致。

---

什么构成了一个设计良好的API？

设计良好的API易于理解、使用和维护。它应遵循一致的风格规范，包括用于身份验证和数据加密的内置安全机制，并能可靠地处理大量流量。

---

我该如何设计API？

要设计API，您首先必须清楚地了解API的预期用例。然后您应该用规范定义API的合约，用模拟和测试验证您的假设，并清晰地记录每个资源、方法、参数和路径。在整个过程中与其他利益相关者协作也很重要。

---

设计API需要多长时间？

API设计是一个高度迭代的过程，其持续时间因API的用例和要求而异。它可能需要从几周到几个月不等。

---

什么是RESTful API设计？

RESTful API设计是设计遵循[代表性状态传输 (REST)](https://blog.postman.com/rest-api-examples/)原则的API的过程，这是当今最受欢迎的API架构。在RESTful架构中，资源通过URI（统一资源标识符）标识，客户端通过标准HTTP方法（如GET、POST、PUT和DELETE）与这些资源进行交互。

---

![api存储库. 插图.](https://voyager.postman.com/illustration/api-design-postman-screenshot-illustration.png)

## 为什么使用Postman进行API设计？

Postman API平台，[被G2评为API设计最佳工具](https://blog.postman.com/postman-number-one-api-management-api-design-g2-summer-2022/)，配备了一整套功能强大的特性，可以帮助团队实施成熟的API设计流程。使用Postman，您可以：

- **生成和编辑API定义：** Postman使您能够[导入现有API定义或从头开始生成新定义](https://learning.postman.com/docs/designing-and-developing-your-api/developing-an-api/defining-an-api/)。Postman支持OpenAPI、RAML、Protobuf、GraphQL或WSDL定义，因此您可以选择最适合您的规范。
- **文档化您的API：** Postman会自动为任何集合以及任何OpenAPI 3.0定义生成[文档](https://www.postman.com/api-documentation-tool/)。当您进行更改时，您的文档将自动更新，确保文档对消费者保持有用。
- **构建、运行和自动化API合约测试：** Postman提供了一个可定制的代码片段库，可用于创建API合约测试。您可以在Postman中手动运行测试，也可以使用[Newman](https://learning.postman.com/docs/running-collections/using-newman-cli/command-line-integration-with-newman/)或[Postman CLI](https://blog.postman.com/introducing-the-postman-cli-to-automate-your-api-testing/)在CI/CD管道中自动运行它们。
- **用模拟服务器模拟API行为：** Postman使您能够设置[模拟服务器](https://www.postman.com/features/mock-api/)，即使您的API尚未投入生产，它们也会对请求返回样本数据。这允许生产者在不急于开发的情况下验证他们的假设，同时使消费者在集成过程中提前开始。
- **跨组织协作：** [协作](https://www.postman.com/how-api-collaboration-works/)是Postman的核心，Postman用户可以利用[团队工作空间](https://blog.postman.com/solving-problems-together-with-postman-workspaces/)轻松协作API项目。Postman还支持跨平台评论，通过允许团队在他们工作的同一地方沟通，减少摩擦。最后，Postman直观且用户友好，对开发人员和业务利益相关者同样易于访问。
