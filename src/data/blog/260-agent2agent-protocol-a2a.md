---
pubDatetime: 2025-04-10 09:07:06
tags: [AI, A2A协议, 多代理互操作性, 企业自动化]
slug: agent2agent-protocol-a2a
source: https://developers.googleblog.com/zh-hans/a2a-a-new-era-of-agent-interoperability/
title: Google发布Agent2Agent协议：开启AI代理互操作性新时代
description: Google推出开放协议Agent2Agent (A2A)，旨在促进不同AI代理之间的互操作性，为企业工作流和效率带来革命性提升。
---

# Google发布Agent2Agent协议：开启AI代理互操作性新时代 🚀

在人工智能飞速发展的时代，AI代理（AI Agents）正成为提高生产力的重要工具。它们能够自主处理重复或复杂的日常任务，从帮助客户服务到优化供应链规划，无所不能。然而，为了充分发挥AI代理的潜力，使它们能在多代理生态系统中协作，跨越数据孤岛和应用程序的障碍是关键。

4月9日，Google正式发布了一个全新的开放协议——**Agent2Agent (A2A)**。该协议由超过50家技术合作伙伴共同支持，如Atlassian、Box、Cohere、MongoDB、Salesforce等，以及诸如Accenture、Deloitte、PwC等领先服务提供商。A2A协议旨在让AI代理能够互相通信、交换信息并协调行动，为企业应用平台之间的协作开辟新的可能性。

---

## A2A协议设计原则 🔑

A2A协议的设计基于五大核心原则，确保其适应复杂企业环境并实现真正的代理互操作性：

1. **支持代理能力**：允许AI代理在没有共享记忆、工具和上下文的情况下，自然协作，支持多代理场景，而不是简单地作为工具使用。
2. **基于现有标准**：采用HTTP、SSE、JSON-RPC等流行标准，方便与现有IT架构集成。
3. **默认安全性**：支持企业级认证和授权，与OpenAPI认证方案保持一致。
4. **支持长期任务处理**：灵活适应从短期任务到长时间研究等场景，可实时反馈任务状态并通知用户。
5. **多模态支持**：不仅限于文本，还支持音频和视频流等多种形式。

![图1：支持A2A协议的合作伙伴包括Accenture、Arize、Atlassian等](https://storage.googleapis.com/gweb-developer-goog-blog-assets/images/image1_yEPzdSr.original.png)

---

## A2A协议如何运作？🛠️

通过A2A协议，AI代理分为两类：**客户端代理**和**远程代理**。客户端代理负责任务的制定与传达，而远程代理负责执行任务并提供反馈。这一过程包含以下关键功能：

1. **能力发现**：通过JSON格式的“Agent Card”宣传其能力，帮助客户端代理找到最佳执行任务的远程代理。
2. **任务管理**：定义任务对象的生命周期，从即时完成到需要长时间的研究，并通过实时状态更新保持同步。
3. **协作**：代理之间可以发送消息以共享上下文、回复、成果或用户指令。
4. **用户体验协商**：支持生成图片、视频流、表单等不同内容格式，确保用户界面与代理协作无缝对接。

![图2：数据流示意图，展示远程代理与客户端代理之间的数据交互](https://storage.googleapis.com/gweb-developer-goog-blog-assets/images/image5_VkAG0Kd.original.png)

---

## 实际应用案例：招聘流程的简化 👩‍💻

一个招聘软件工程师的例子可以很好地说明A2A协议的价值。在统一界面中，招聘经理可以指派自己的代理寻找符合岗位需求的候选人。此时，客户端代理会与多个远程代理协作，如筛选简历、安排面试等。通过这种方式，不仅节省了时间，还优化了招聘流程。

此外，在面试结束后，另一个代理可以进行背景调查或处理其他行政任务。这展示了AI代理如何跨系统协作以完成复杂任务。

---

## 合作伙伴的声音 📢

A2A协议得到了广泛合作伙伴的支持，他们对协议的未来充满期待：

- **Atlassian**：“A2A协议将帮助我们的Rovo代理实现成功协作，推动规模化的委托与协作。”
- **Box**：“我们期待通过支持A2A协议，与Google Cloud共同创新，以增强工作流自动化能力。”
- **MongoDB**：“结合MongoDB强大的数据库基础设施与A2A协议，将重新定义AI应用的未来。”

更多合作伙伴反馈请点击[完整列表](https://developers.googleblog.com/zh-hans/a2a-a-new-era-of-agent-interoperability/#feedback)。

---

## 展望未来 🌐

随着AI技术的发展，像A2A这样的开放协议为AI代理互操作性开辟了新的可能性。它不仅能够提升企业工作效率，还能加速复杂问题解决和创新。Google计划今年晚些时候推出生产级版本，并持续与社区和合作伙伴共同完善协议。

您可以通过以下方式参与其中：

- [阅读完整规格草案](https://github.com/google/A2A)
- [访问A2A官网](https://google.github.io/A2A)
- [提交您的创意](https://docs.google.com/forms/d/e/1FAIpQLScS23OMSKnVFmYeqS2dP7dxY3eTyT7lmtGLUa8OJZfP4RTijQ/viewform)

AI互操作性的新时代已经到来，让我们共同期待！ 🎉
