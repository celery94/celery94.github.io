---
pubDatetime: 2026-01-30
title: "使用 Claude Agent SDK 和 Microsoft Agent Framework 构建 AI 代理"
description: "Microsoft Agent Framework 现已集成 Claude Agent SDK，支持使用 Claude 的完整代理能力构建 AI 代理。本文介绍如何通过统一的代理抽象，结合内置工具、函数调用、流式响应、多轮对话和 MCP 服务器集成等功能，在 Python 中构建强大的 AI 代理系统。"
tags: ["AI", "Claude", "Agent", "Python", "Microsoft"]
slug: "build-ai-agents-claude-sdk-microsoft-agent-framework"
source: "https://devblogs.microsoft.com/semantic-kernel/build-ai-agents-with-claude-agent-sdk-and-microsoft-agent-framework/"
---

# 使用 Claude Agent SDK 和 Microsoft Agent Framework 构建 AI 代理

Microsoft Agent Framework 现已集成 [Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk-python)，使您能够使用 Claude 的完整代理能力构建 AI 代理。

这一集成将 Agent Framework 的一致性代理抽象与 Claude 的强大功能结合在一起，包括文件编辑、代码执行、函数调用、流式响应、多轮对话以及 Model Context Protocol (MCP) 服务器集成——全部在 Python 中可用。

## 为什么要将 Agent Framework 与 Claude Agent SDK 结合使用？

您可以单独使用 Claude Agent SDK 来构建代理。那么为什么要通过 Agent Framework 使用它？以下是关键原因：

- **统一的代理抽象** — Claude 代理实现了与框架中其他所有代理类型相同的 `BaseAgent` 接口。您可以在不重构代码的情况下切换或组合提供商。
- **多代理工作流** — 使用内置编排器，将 Claude 代理与其他代理（Azure OpenAI、OpenAI、GitHub Copilot 等）组合成顺序、并发、交接和群聊工作流。
- **生态系统集成** — 访问完整的 Agent Framework 生态系统：声明式代理定义、A2A 协议支持，以及跨所有提供商的函数工具、会话和流式传输的一致模式。

简而言之，Agent Framework 让您将 Claude 视为更大的代理系统中的一个构建块，而不是独立工具。

## 安装 Claude Agent SDK 集成

```bash
pip install agent-framework-claude --pre
```

## 创建 Claude 代理

开始使用非常简单。创建一个 `ClaudeAgent` 并使用异步上下文管理器模式与其交互。

```python
from agent_framework_claude import ClaudeAgent

async def main():
    async with ClaudeAgent(
        instructions="You are a helpful assistant.",
    ) as agent:
        response = await agent.run("What is Microsoft Agent Framework?")
        print(response.text)
```

## 使用内置工具

Claude Agent SDK 提供了强大的内置工具，用于文件操作、Shell 命令等。只需将工具名称作为字符串传递即可启用它们。

```python
from agent_framework_claude import ClaudeAgent

async def main():
    async with ClaudeAgent(
        instructions="You are a helpful coding assistant.",
        tools=["Read", "Write", "Bash", "Glob"],
    ) as agent:
        response = await agent.run("List all Python files in the current directory")
        print(response.text)
```

## 添加函数工具

使用自定义函数工具扩展您的代理，为其提供特定领域的能力。

```python
from typing import Annotated
from pydantic import Field
from agent_framework_claude import ClaudeAgent

def get_weather(
    location: Annotated[str, Field(description="The location to get the weather for.")],
) -> str:
    """Get the weather for a given location."""
    return f"The weather in {location} is sunny with a high of 25C."

async def main():
    async with ClaudeAgent(
        instructions="You are a helpful weather agent.",
        tools=[get_weather],
    ) as agent:
        response = await agent.run("What's the weather like in Seattle?")
        print(response.text)
```

## 流式响应

为了获得更好的用户体验，您可以在生成响应时进行流式传输，而不是等待完整结果。

```python
from agent_framework_claude import ClaudeAgent

async def main():
    async with ClaudeAgent(
        instructions="You are a helpful assistant.",
    ) as agent:
        print("Agent: ", end="", flush=True)
        async for chunk in agent.run_stream("Tell me a short story."):
            if chunk.text:
                print(chunk.text, end="", flush=True)
        print()
```

## 多轮对话

使用线程在多次交互中维护对话上下文。Claude Agent SDK 自动管理会话恢复以保留上下文。

```python
from agent_framework_claude import ClaudeAgent

async def main():
    async with ClaudeAgent(
        instructions="You are a helpful assistant. Keep your answers short.",
    ) as agent:
        thread = agent.get_new_thread()

        # 第一轮
        await agent.run("My name is Alice.", thread=thread)

        # 第二轮 - 代理记住上下文
        response = await agent.run("What is my name?", thread=thread)
        print(response.text)  # 应该提到 "Alice"
```

## 配置权限模式

使用权限模式控制代理如何处理文件操作和命令执行的权限请求。

```python
from agent_framework_claude import ClaudeAgent

async def main():
    async with ClaudeAgent(
        instructions="You are a coding assistant that can edit files.",
        tools=["Read", "Write", "Bash"],
        default_options={
            "permission_mode": "acceptEdits",  # 自动接受文件编辑
        },
    ) as agent:
        response = await agent.run("Create a hello.py file that prints 'Hello, World!'")
        print(response.text)
```

## 连接 MCP 服务器

Claude 代理支持连接到外部 MCP 服务器，使代理能够访问额外的工具和数据源。

```python
from agent_framework_claude import ClaudeAgent

async def main():
    async with ClaudeAgent(
        instructions="You are a helpful assistant with access to the filesystem.",
        default_options={
            "mcp_servers": {
                "filesystem": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-filesystem", "."],
                },
            },
        },
    ) as agent:
        response = await agent.run("List all files in the current directory using MCP")
        print(response.text)
```

## 在多代理工作流中使用 Claude

使用 Agent Framework 的关键优势之一是能够在多代理工作流中组合 Claude 与其他代理。在此示例中，Azure OpenAI 代理起草营销标语，Claude 代理进行审查——所有操作都作为顺序管道编排。

```python
import asyncio
from typing import cast

from agent_framework import ChatMessage, Role, SequentialBuilder, WorkflowOutputEvent
from agent_framework.azure import AzureOpenAIChatClient
from agent_framework_claude import ClaudeAgent
from azure.identity import AzureCliCredential

async def main():
    # 创建 Azure OpenAI 代理作为文案撰写者
    chat_client = AzureOpenAIChatClient(credential=AzureCliCredential())

    writer = chat_client.as_agent(
        instructions="You are a concise copywriter. Provide a single, punchy marketing sentence based on the prompt.",
        name="writer",
    )

    # 创建 Claude 代理作为审稿人
    reviewer = ClaudeAgent(
        instructions="You are a thoughtful reviewer. Give brief feedback on the previous assistant message.",
        name="reviewer",
    )

    # 构建顺序工作流: writer -> reviewer
    workflow = SequentialBuilder().participants([writer, reviewer]).build()

    # 运行工作流
    async for event in workflow.run_stream("Write a tagline for a budget-friendly electric bike."):
        if isinstance(event, WorkflowOutputEvent):
            messages = cast(list[ChatMessage], event.data)
            for msg in messages:
                name = msg.author_name or ("assistant" if msg.role == Role.ASSISTANT else "user")
                print(f"[{name}]: {msg.text}\n")

asyncio.run(main())
```

此示例展示了单个工作流如何组合来自不同提供商的代理。您还可以将此模式扩展到并发、交接和群聊工作流。

## 更多信息

- [Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk-python)
- [GitHub 上的 Microsoft Agent Framework](https://github.com/microsoft/agent-framework)
- [Agent Framework 入门教程](https://learn.microsoft.com/agent-framework/tutorials/overview)

## 总结

Microsoft Agent Framework 的 Claude Agent SDK 集成使构建利用 Claude 完整代理能力的 AI 代理变得简单。通过在 Python 中支持内置工具、函数工具、流式传输、多轮对话、权限模式和 MCP 服务器，您可以构建强大的代理应用程序，与代码、文件、Shell 命令和外部服务进行交互。

我们始终希望听到您的声音。如果您有反馈、问题或想进一步讨论，请随时在 GitHub 的[讨论区](https://github.com/microsoft/agent-framework/discussions)与我们和社区联系！如果您喜欢使用 Agent Framework，也请在 [GitHub](https://github.com/microsoft/agent-framework) 上为我们点星支持。
