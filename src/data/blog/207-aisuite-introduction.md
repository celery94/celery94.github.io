---
pubDatetime: 2025-03-19
tags: ["AI", "Productivity"]
slug: aisuite-introduction
source: https://github.com/andrewyng/aisuite
title: 来自吴恩达，解锁多生成式AI提供商的潜力：AISuite，您的终极接口工具
description: 了解如何通过AISuite实现与多个生成式AI提供商的无缝集成，提升AI应用的开发效率和灵活性。
---

# 🚀 解锁多生成式AI提供商的潜力：AISuite，您的终极接口工具

## 什么是AISuite？

在当今快速发展的人工智能领域，开发者们常常面临着与多个生成式AI提供商交互的挑战。AISuite正是为了解决这一痛点而生！它是一个简单而统一的接口工具，旨在帮助开发者轻松地使用多个大型语言模型（LLM），并通过标准化的接口与它们进行交互。无论是Anthropic、AWS还是OpenAI，AISuite都能让您在不改变代码的情况下，快速切换和测试不同的LLM响应。

### 支持的AI提供商

- Anthropic
- AWS
- Azure
- Cerebras
- Google
- Groq
- HuggingFace Ollama
- Mistral
- OpenAI
- Sambanova
- Watsonx

## 如何安装AISuite？

您可以选择仅安装基础的AISuite包，或者安装带有特定提供商SDK的版本。例如，您可以通过以下命令来安装AISuite及其Anthropic库：

```bash
pip install 'aisuite[anthropic]'
```

如果您想要同时安装所有提供商相关的库，可以使用：

```bash
pip install 'aisuite[all]'
```

## 快速上手指南

要开始使用AISuite，您需要为所选的AI提供商获取API密钥，并确保安装了相应的库。这些密钥可以设置为环境变量，也可以作为配置参数传递给AISuite客户端构造函数。您可以使用[`python-dotenv`](https://pypi.org/project/python-dotenv/)或[`direnv`](https://direnv.net/)等工具来手动设置环境变量。

以下是一个使用AISuite从gpt-4o和claude-3-5-sonnet生成聊天完成响应的简单示例：

```python
import aisuite as ai

client = ai.Client()
models = ["openai:gpt-4o", "anthropic:claude-3-5-sonnet-20240620"]

messages = [
    {"role": "system", "content": "Respond in Pirate English."},
    {"role": "user", "content": "Tell me a joke."},
]

for model in models:
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.75
    )
    print(response.choices[0].message.content)
```

## 提供商支持与贡献

AISuite为新平台提供支持变得异常简单。开发者可以通过添加实现文件来支持新的AI提供商。此外，AISuite采用了一种基于约定的方法来加载提供商，这需要严格遵循模块名和类名的命名规范。有关详细信息，请查阅AISuite的[贡献指南](https://github.com/andrewyng/aisuite/blob/main/CONTRIBUTING.md)。

## 使用工具调用功能

AISuite还提供了一种简单的工具/函数调用抽象，这使得在不同LLM中使用工具变得更加便捷。您可以选择手动处理工具调用，也可以让AISuite自动处理这一流程。

### 自动工具执行示例

```python
def will_it_rain(location: str, time_of_day: str):
    """Check if it will rain in a location at a given time today."""
    return "YES"

client = ai.Client()
messages = [{"role": "user", "content": "I live in San Francisco. Can you check for weather and plan an outdoor picnic for me at 2pm?"}]

response = client.chat.completions.create(
    model="openai:gpt-4o",
    messages=messages,
    tools=[will_it_rain],
    max_turns=2  # 最大往返调用次数
)
print(response.choices[0].message.content)
```

## 总结

AISuite凭借其简便的接口和广泛的AI提供商支持，为开发者探索和比较多种生成式AI性能提供了极大的便利。无论您是软件开发工程师、数据科学家还是AI研究员，AISuite都能帮助您提升工作效率，实现更快的项目迭代。💡

加入我们的[Discord](https://discord.gg/T6Nvn8ExSb)社区，与其他开发者交流经验，共同推动AISuite的发展吧！
