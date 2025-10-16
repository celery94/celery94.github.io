---
pubDatetime: 2025-03-12
tags: ["Productivity", "Tools"]
slug: experiment-gemini-20-flash-image-generation
source: https://developers.googleblog.com/en/experiment-with-gemini-20-flash-native-image-generation/?linkId=13408348
title: 探索Gemini 2.0 Flash的原生图像生成能力
description: 开发者现可通过Google AI Studio中的Gemini API测试Gemini 2.0 Flash的实验性图像输出功能。
---

# 探索Gemini 2.0 Flash的原生图像生成能力

## 开启新一代图像生成实验

在2025年3月12日，Google宣布开放Gemini 2.0 Flash的原生图像生成能力，允许开发者在Google AI Studio中进行实验。这一功能最初于去年12月面向受信任的测试者推出，如今则扩展至所有支持的区域。开发者可以通过使用Gemini API和Google AI Studio上的实验性版本（gemini-2.0-flash-exp）来测试这一新功能。

![Gemini 2.0 Flash native image generation](https://storage.googleapis.com/gweb-developer-goog-blog-assets/images/gemini-image-generation.original.png)

## 多模态输入与增强推理的结合

Gemini 2.0 Flash融合了多模态输入、增强推理以及自然语言理解技术以创造图像。以下是其在不同应用场景中的表现：

### 文本与图像结合

利用Gemini 2.0 Flash讲述一个故事，它不仅能够用图片进行展示，还能保持角色与环境的一致性。用户可以对故事提出反馈，模型会根据反馈重述故事或改变绘图风格。

### 对话式图像编辑

Gemini 2.0 Flash通过自然语言对话帮助用户编辑图像，适用于不断调整以获得完美图像或共同探索不同想法。

### 世界理解能力

与许多其他图像生成模型不同，Gemini 2.0 Flash利用世界知识和增强推理创造正确的图像，非常适合创建详细且逼真的图像，如菜谱插图。

### 文本渲染能力

许多图像生成模型在渲染长文本序列时容易出现格式错误或字符难以辨认的问题，而Gemini 2.0 Flash在内部基准测试中显示出更强的渲染能力，非常适合制作广告、社交媒体帖子或邀请函。

## 开始使用Gemini进行图像创作

开发者可以通过Gemini API开始使用Gemini 2.0 Flash进行图像创作。更多关于图像生成的信息可参阅[文档](https://ai.google.dev/gemini-api/docs/image-generation)。

```python
from google import genai
from google.genai import types

client = genai.Client(api_key="GEMINI_API_KEY")

response = client.models.generate_content(
    model="gemini-2.0-flash-exp",
    contents=(
        "Generate a story about a cute baby turtle in a 3d digital art style. "
        "For each scene, generate an image."
    ),
    config=types.GenerateContentConfig(
        response_modalities=["Text", "Image"]
    ),
)
```

无论你是在构建AI代理、开发带有精美视觉效果的应用，还是在对话中头脑风暴视觉创意，Gemini 2.0 Flash都允许你通过单一模型添加文本和图像生成功能。我们期待开发者创造出具有原生图像输出的新作品，并欢迎您提供反馈以帮助我们尽快完成生产就绪版本。

## 相关链接

- [State-of-the-art text embedding via the Gemini API](https://developers.googleblog.com/en/gemini-embedding-text-model-now-available-gemini-api/)
- [Introducing Gemma 3: The Developer Guide](https://developers.googleblog.com/en/introducing-gemma3/)
- [Safer and Multimodal: Responsible AI with Gemma](https://developers.googleblog.com/en/safer-and-multimodal-responsible-ai-with-gemma/)
- [Gemini 2.0 Deep Dive: Code Execution](https://developers.googleblog.com/en/gemini-20-deep-dive-code-execution/)
