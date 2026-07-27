---
pubDatetime: 2026-07-27T08:32:37+08:00
title: "Microsoft Agent Framework 原生记忆：Azure Cosmos DB 驱动的 CosmosMemoryContextProvider"
description: "Microsoft Agent Framework 新增 CosmosMemoryContextProvider，一行代码让 AI Agent 拥有基于 Azure Cosmos DB 的持久化长期记忆——对话存储、事实提取、摘要生成、用户画像全自动。本文讲解 context provider 抽象设计、before_run/after_run 生命周期、以及如何用自定义 Prompty 模板调教 Agent 记住什么。"
tags: ["Microsoft Agent Framework", "Azure Cosmos DB", "AI Agent", "Agent Memory", "Python", "Observability"]
slug: "native-agent-memory-microsoft-agent-framework-cosmos-db"
ogImage: "../../assets/971/01-cover.png"
source: "https://devblogs.microsoft.com/cosmosdb/native-agent-memory-for-microsoft-agent-framework-powered-by-azure-cosmos-db/"
---

前不久，Azure Cosmos DB 团队推出了 [Agent Memory Toolkit 和 Agentic Retrieval Toolkit](https://devblogs.microsoft.com/cosmosdb/new-toolkits-for-agent-memories-and-agentic-retrieval-in-azure-cosmos-db/)。Agent Memory Toolkit 让你的 AI agent 拥有 Cosmos 背书的持久化记忆：它存储原始对话轮次，再蒸馏出更高价值的派生记忆（线程摘要、提取的事实、跨线程用户画像），全部可通过向量、全文和混合搜索在同一个数据库里检索。

现在，更进一步。在最新版 [Microsoft Agent Framework](https://learn.microsoft.com/agent-framework/overview/?pivots=programming-language-python) 中，你可以用一个对象就把这份记忆接入 agent：**`CosmosMemoryContextProvider`**，随新的 `agent-framework-azure-cosmos-memory` 包发布（Python，目前 preview）。挂到 agent 上，每一轮对话都被记住、蒸馏、跨线程跨会话召回——你这边零编排代码。

## 为什么是 context provider，以及这为什么重要

大多数 agent 框架给你一个 **memory** 接口：一个固定的 API 做对话记忆的存储和检索。Microsoft Agent Framework 的做法更通用。它暴露了一个一等公民、provider 无关的 **context provider** 抽象：一对生命周期钩子——`before_run` 和 `after_run`——任何组件都可以实现它们来向一次 run **注入**上下文，以及从 run 中**捕获**结果。

这种通用性才是关键。一个 context provider 不限于 memory。它是一个干净的接缝，可以注入任何 agent 应该在思考前知道的信息，以及对它产生的结果做出反应。在主流 agent 框架中，Agent Framework 的与众不同在于把这个做成了一个一等公民、可插拔的扩展点，而不是记忆专属的附加件——这正是让 Cosmos 背书记忆能作为 drop-in provider 而不是整个 agent 循环的包装器的原因。

具体来说，`CosmosMemoryContextProvider` 做两件事：

- **`before_run`**：在你的 Cosmos 记忆库中搜索跟入站消息相关的上下文，将匹配结果（及用户画像）注入模型上下文，让 agent 带着已知信息回答问题。
- **`after_run`**：存储新对话轮次，让 Agent Memory Toolkit 的管道在后台提取事实、滚动摘要、更新用户画像。

你不需要实现任何东西。挂上一个 provider，就获得持久化记忆。

## 架构全貌

底层来看，provider 是 Agent Memory Toolkit 上的一个薄而地道的 Agent Framework 适配层。Agent Framework 掌控 agent 循环和 context provider 生命周期；toolkit 掌控 Cosmos DB 存储模型和把原始对话轮次转化为事实、摘要、画像的 LLM 管道。

记忆按稳定的 `user_id` 划定范围（以及当前对话的 `thread_id`），所以即使在新线程和新会话中，回忆仍然跟随用户。所有数据以 JSON 文档（turns、facts、summaries）存储在 Azure Cosmos DB for NoSQL 中，检索使用数据库已内建的向量、全文和混合搜索。不需要再配第二个向量存储，也没东西需要同步。

## 交互示例走读

`agent-framework-azure-cosmos-memory` 包自带一个完整的交互式聊天示例，下面逐步拆解。

### 1. 安装与配置

```bash
pip install agent-framework-azure-cosmos-memory agent-framework-foundry
```

认证走 `DefaultAzureCredential`（本地 `az login`，Azure 里用 managed identity），没有 API key。指向你的 Cosmos DB 账号和 Microsoft Foundry 项目，指定聊天和嵌入部署：

```powershell
$env:COSMOS_ENDPOINT  = "https://<your-account>.documents.azure.com:443/"
$env:FOUNDRY_ENDPOINT = "https://<your-project>.services.ai.azure.com"
$env:CHAT_MODEL       = "gpt-5.4-mini"
$env:EMBEDDING_MODEL  = "text-embedding-3-large"
```

### 2. 给 agent 记忆

创建带记忆的 agent 只需要构造 provider 然后传给 agent。一个 Foundry endpoint 同时驱动记忆管道（嵌入和提取）和聊天 agent：

```python
import os
from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from azure.identity.aio import DefaultAzureCredential

from agent_framework_azure_cosmos_memory import (
    CosmosMemoryContextProvider
)

def create_agent_with_memory():
    foundry_endpoint = os.environ["FOUNDRY_ENDPOINT"]
    credential = DefaultAzureCredential()

    # One object gives the agent durable, Cosmos-backed long-term memory.
    provider = CosmosMemoryContextProvider(
        cosmos_endpoint=os.environ["COSMOS_ENDPOINT"],
        cosmos_database=os.getenv("COSMOS_DATABASE", "ai_memory"),
        foundry_endpoint=foundry_endpoint,
        embedding_model=os.getenv(
            "EMBEDDING_MODEL", "text-embedding-3-large"),
        chat_model=os.getenv("CHAT_MODEL", "gpt-5.4-mini"),
        credential=credential,
        memory_types=["fact", "procedural", "episodic"],
    )

    agent = Agent(
        client=FoundryChatClient(
            project_endpoint=foundry_endpoint,
            model=os.getenv("CHAT_MODEL", "gpt-5.4-mini"),
            credential=credential,
        ),
        name="Memory Assistant",
        instructions="You are a helpful assistant.",
        context_providers=[provider],
        # ^ that's the whole integration
    )
    return agent, provider
```

跟记忆相关只有一行：`context_providers=[provider]`。从那一刻起，每次 agent run 前后，`before_run` 和 `after_run` 自动触发。

### 3. 按用户划分记忆范围

长期、跨会话记忆需要一个稳定的 user id。你把它设在 provider 作用域的 session state 中，这样即使为同一用户开新线程，也能召回之前学到的一切：

```python
def new_session(agent, provider, user_id):
    session = agent.create_session()
    session.state.setdefault(provider.source_id, {})[
        "user_id"] = user_id
    return session
```

### 4. 见证记忆生效

进入 provider 的 async context（这样退出时后台提取任务能被干净排空），告诉 agent 一些持续性信息，然后开**新线程**让 agent 回忆：

```python
agent, provider = create_agent_with_memory()

async with provider:
    session = new_session(agent, provider, user_id="alice")
    await agent.run(
        "I love hiking and I'm allergic to peanuts.",
        session=session)

    # Brand-new thread, same user -> memory persists.
    session = new_session(agent, provider, user_id="alice")
    reply = await agent.run(
        "What should we pack for a trail lunch?",
        session=session)
    print(reply.text)
```

虽然第二个线程没有任何先前消息，agent 仍然记得 Alice 喜欢徒步且对花生过敏，会规划一份无花生的 trail lunch。这份召回完全由 provider 驱动：`before_run` 时它搜索 Alice 的已提取事实并把用户画像作为上下文注入；第一个 run 的 `after_run` 时它存储了对话轮次，让 toolkit 提取了持久化的事实。

示例还包装了一个简单 REPL，几个命令：
- **`/new`**：为同一用户开启新线程（记忆延续）
- **`/user`**：切换到不同 user id（记忆隔离）
- **`/quit`**：退出

试着告诉 agent 你的名字和几个偏好，按 `/new`，然后问「what do you know about me?」。它会从长期记忆中回答，而不是从当前对话里。

完整可运行代码在包的 [samples 目录](https://github.com/microsoft/agent-framework/tree/main/python/packages/azure-cosmos-memory/samples)，主文件是 `interactive_chat.py`。

## 定制 agent 应该记住什么

默认提取规则是通用型的：它提取适用于几乎所有助手的事实、程序化偏好和情景经历。但「什么值得记住」通常跟领域相关。一个编程助手应该记住架构决策和语言偏好；一个旅行助手应该记住座位和饮食偏好；一个客服 bot 应该记住账户等级和历史案例。如果只用默认规则，一个专精 agent 要么忘掉对它最重要的事，要么被无关的事塞满记忆。

Provider 暴露了 `prompts_dir` 参数恰好解决这个问题。把它指向一个 [Prompty](https://prompty.ai/) 模板目录，记忆管道就从那里读取提取和摘要提示词，而不是工具包内置的默认值。最重要的一份模板是 `extract_memories.prompty`——它定义了模型用来判断**什么**该从每轮对话中提取、以及**如何**分类的规则。你保持模板的输入和 JSON 输出 schema 不变，只改写中间的指导内容。

`interactive_chat_custom_extraction.py` 示例完整展示了这个流程。它在运行时构建一个 prompts 目录（复制内置模板并把 `extract_memories.prompty` 换成编程场景版本），然后传给 provider：

```python
provider = CosmosMemoryContextProvider(
    cosmos_endpoint=os.environ["COSMOS_ENDPOINT"],
    foundry_endpoint=os.environ["FOUNDRY_ENDPOINT"],
    embedding_model=os.getenv(
        "EMBEDDING_MODEL", "text-embedding-3-large"),
    chat_model=os.getenv("CHAT_MODEL", "gpt-5.4-mini"),
    credential=credential,
    # The one line that matters:
    prompts_dir=prompts_dir,
)
```

其他一切（存储、范围划分、检索、注入）完全不变。你只是在修改管道认为什么是值得记忆的，这样一个编程助手开始持久化记住「团队选择了 PostgreSQL 而非 MySQL 来构建用户服务」和「先展示代码再解释」这类指令，同时忽略闲聊。这是调教记忆的最干净方式——不用 fork toolkit，而检索和注入路径也没被动过。

## 为生产而建，不只是 demo

几个值得关注的细节，尤其对要跑原型的团队：

**透明的提取过程。** 对话轮次的写入是非阻塞的；事实和摘要提取在后台运行，provider context 退出时自动排空，所以不丢数据并且请求路径保持快速。

**默认安全。** agent 召回的用户画像是从已存储对话内容生成的，provider 把它作为普通 user-role 消息注入（绝不做 system 或 agent 指令），并加上显式注释告诉模型将其视为不可信的参考信息而非指令。这降低了被污染的长期记忆变成持久化指令的 prompt 注入风险。

**你的模型，你的规则。** 聊天和嵌入的 deployment 是显式指定的；不存在静默指向你没部署过的模型的默认行为。

## 上手三步

如果你在用 Microsoft Agent Framework 构建 agent 并且希望它们记住，现在只需三行：

```bash
pip install agent-framework-azure-cosmos-memory agent-framework-foundry
```

1. 给你的 agent 挂上 `CosmosMemoryContextProvider`（`context_providers=[provider]`）
2. 在 provider 的 session state 中设置一个稳定的 `user_id`
3. 跑起来

`agent-framework-azure-cosmos-memory` 包目前是 preview 且仅 Python，GA 前 API 可能变化。

从可运行的 [samples](https://github.com/microsoft/agent-framework/tree/main/python/packages/azure-cosmos-memory/samples) 起步。更深入了解背后的记忆引擎可以参考 [Agent Memory Toolkit 文档](https://aka.ms/AgentMemoryToolkit)，以及最初的 [toolkit 发布公告](https://devblogs.microsoft.com/cosmosdb/new-toolkits-for-agent-memories-and-agentic-retrieval-in-azure-cosmos-db/) 和 [Microsoft Agent Framework](https://github.com/microsoft/agent-framework) 源码。

## 参考

- [Native Agent Memory for Microsoft Agent Framework — Azure Cosmos DB Blog](https://devblogs.microsoft.com/cosmosdb/native-agent-memory-for-microsoft-agent-framework-powered-by-azure-cosmos-db/)
- [Agent Memory Toolkit 和 Agentic Retrieval Toolkit 发布公告](https://devblogs.microsoft.com/cosmosdb/new-toolkits-for-agent-memories-and-agentic-retrieval-in-azure-cosmos-db/)
- [Microsoft Agent Framework 文档](https://learn.microsoft.com/agent-framework/overview/)
- [Microsoft Agent Framework GitHub](https://github.com/microsoft/agent-framework)
- [Agent Memory Toolkit 文档](https://aka.ms/AgentMemoryToolkit)
- [交互式聊天示例源码](https://github.com/microsoft/agent-framework/tree/main/python/packages/azure-cosmos-memory/samples)

如果你关注 AI Agent 开发、微软技术生态和软件工程实践，可以关注 **Aide Hub**。这里会继续分享能落地的工具教程、框架深度解析和 AI 实践观察。
