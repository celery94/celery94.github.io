---
pubDatetime: 2024年5月10日
tags: [Astro]
source: https://docs.astro.build/en/concepts/why-astro/
author: Astro
title: 为什么选择Astro？ | 文档
description: Astro是用于构建以内容为中心的网站如博客、营销和电子商务的网络框架。了解为什么Astro可能是您下一个网站的好选择。
---

# 为什么选择Astro？ | 文档

> ## 摘要
>
> Astro是用于构建以内容为中心的网站如博客、营销和电子商务的网络框架。了解为什么Astro可能是您下一个网站的好选择。

---

**Astro**是一个用于构建**以内容为中心的网站**如博客、营销和电子商务的网络框架。Astro以开创新的[前端架构](https://docs.astro.build/en/concepts/islands/)而闻名，与其他框架相比，它能减少JavaScript的开销和复杂性。如果你需要一个加载速度快且具有出色SEO的网站，那么Astro是你的选择。

**Astro是一个一站式网络框架。**它内置了创建网站所需的一切。还有成百上千种不同的[集成](https://astro.build/integrations/)和[API钩子](https://docs.astro.build/en/reference/integrations-reference/)可用于定制项目以满足您的确切用例和需求。

一些亮点包括：

- **[岛屿](https://docs.astro.build/en/concepts/islands/):** 为以内容为中心的网站优化的基于组件的网络架构。
- **[UI-agnostics](https://docs.astro.build/en/guides/framework-components/):** 支持React、Preact、Svelte、Vue、Solid、Lit、HTMX、Web组件等。
- **[首先是服务器](https://docs.astro.build/en/basics/rendering-modes/):** 将费时的渲染从访客的设备中搬走。
- **[默认无JS](https://docs.astro.build/en/basics/astro-components/):** 更少的客户端JavaScript拖慢您的站点。
- **[内容集合](https://docs.astro.build/en/guides/content-collections/):** 为Markdown内容组织、验证，并提供TypeScript类型安全性。
- **[可定制](https://docs.astro.build/en/guides/integrations-guide/):** 选择范围广泛的集成，如Tailwind、MDX等。

## 设计原则

[标题为设计原则的部分](https://docs.astro.build/en/concepts/why-astro/#design-principles)

这里有五个核心设计原则，以帮助解释我们为什么建立Astro，它存在的问题是什么，以及为什么Astro可能是你的项目或团队的最佳选择。

Astro是……

1. **[以内容为驱动](https://docs.astro.build/en/concepts/why-astro/#content-driven):** Astro旨在展示您的内容。
2. **[首先是服务器](https://docs.astro.build/en/concepts/why-astro/#server-first):** 当网站在服务器上渲染HTML时运行得更快。
3. **[默认快速](https://docs.astro.build/en/concepts/why-astro/#fast-by-default):** 在Astro中构建一个慢的网站应该是不可能的。
4. **[易于使用](https://docs.astro.build/en/concepts/why-astro/#easy-to-use):** 你不需要是一个专家就能使用Astro构建东西。
5. **[以开发者为中心](https://docs.astro.build/en/concepts/why-astro/#developer-focused):** 你应该拥有成功所需的资源。

**Astro被设计用于构建内容丰富的网站。**这包括营销站点、出版站点、文档站点、博客、作品集、落地页、社区站点和电子商务站点。如果你有内容要展示，它需要快速到达你的读者。

相比之下，大多数现代网络框架被设计用于构建*网络应用*。这些框架擅长在浏览器中构建更复杂的、类似应用的体验：已登录的管理仪表板、收件箱、社交网络、待办事项列表，甚至是类似原生的应用，如[Figma](https://figma.com/)和[Ping](https://ping.gg/)。然而，随着这种复杂性，它们在交付内容时可能难以提供出色的性能。

Astro从最开始作为静态站点生成器的重点关注内容，使得Astro能够**合理扩展到性能强大的动态网络应用**，同时仍然尊重您的内容和受众。Astro独特的关注点让Astro能够做出其他更注重应用的网络框架无法实现的性能特性和权衡。

**Astro利用[服务器渲染](https://docs.astro.build/en/basics/rendering-modes/)而不是浏览器中的客户端渲染尽可能多地进行。**这和传统服务器端框架--PHP、WordPress、Laravel、Ruby on Rails等--几十年来使用的方法是一致的。但是您不需要学习第二种服务器端语言就能实现它。使用Astro，一切仍然只是HTML、CSS和JavaScript（或TypeScript，如果您更喜欢）。

这种方法与其他现代JavaScript网络框架如Next.js、SvelteKit、Nuxt、Remix等形成了对比。这些框架是为了您的整个网站的客户端渲染而构建的，并且主要包括服务器端渲染以解决性能问题。这种方法被称为**单页应用（SPA）**，与Astro的**多页应用（MPA）**方法相对。

SPA模型有其好处。然而，这些好处是以增加额外的复杂性和性能权衡为代价的。这些权衡损害了页面性能--像[交互时间(TTI)](https://web.dev/interactive/)这样的关键指标--这对于首次加载性能至关重要的内容为中心的网站而言并不合理。

Astro的首先是服务器的方法允许您仅在必要时选择客户端渲染，并且准确如此。您可以选择添加在客户端上运行的UI框架组件。您可以利用Astro的视图转换路由器更精细地控制选择页面转换和动画。Astro的首先是服务器渲染，无论是预渲染还是按需，都提供了高性能的默认设置，您可以增强和扩展。

### 默认快速

[标题为默认快速的部分](https://docs.astro.build/en/concepts/why-astro/#fast-by-default)

良好的性能始终很重要，但对于成功依赖于展示内容的网站来说尤其关键。已经有充分的证据表明，糟糕的性能会导致您失去参与度、转化率和金钱。例如：

- 每快100ms → 转化率增加1%（[Mobify](https://web.dev/why-speed-matters/)，每年增加+$380,000）
- 快50% → 销售增加12%（[AutoAnything](https://www.digitalcommerce360.com/2010/08/19/web-accelerator-revs-conversion-and-sales-autoanything/)）
- 快20% → 转化率增加10%（[Furniture Village](https://www.thinkwithgoogle.com/intl/en-gb/marketing-strategies/app-and-mobile/furniture-village-and-greenlight-slash-page-load-times-boosting-user-experience/)）
- 快40% → 注册增加15%（[Pinterest](https://medium.com/pinterest-engineering/driving-user-growth-with-performance-improvements-cfc50dafadd7)）
- 快850ms → 转化率增加7%（[COOK](https://web.dev/why-speed-matters/)）
- 每慢1秒 → 用户减少10%（[BBC](https://www.creativebloq.com/features/how-the-bbc-builds-websites-that-scale)）

在许多网络框架中，构建一个在开发过程中看起来很棒但一旦部署就加载极慢的网站很容易。JavaScript通常是罪魁祸首，因为许多手机和低功率设备很少能达到开发者笔记本的速度。

Astro的魔力在于它如何结合上面解释的两个价值观--一个内容关注点和一个首先是服务器的架构--来做出权衡并提供其他框架无法提供的功能。结果是每个网站都能获得出色的网络性能，开箱即用。我们的目标：**使用Astro构建一个慢网站应该几乎是不可能的。**

使用Astro构建的网站可以[加载速度提高40%，JavaScript减少90%](https://twitter.com/t3dotgg/status/1437195415439360003)与使用最流行的React网络框架构建的相同站点相比。但不要只相信我们的话：观看Astro的性能让Ryan Carniato（Solid.js和Marko的创建者）[哑口无言](https://youtu.be/2ZEMb_H-LYE?t=8163)。

**Astro的目标是对每个网络开发者都可用。**Astro被设计得感觉熟悉且易于接近，无论技能水平或以往的网络开发经验如何。

`.astro` UI语言是HTML的超集：任何有效的HTML都是有效的Astro模板语法！所以，如果你会写HTML，你就会写Astro组件！但是，它还结合了我们从其他组件语言借鉴的一些最爱功能，如JSX表达式（React）和默认的CSS作用域（Svelte和Vue）。这种接近HTML的方式还使得使用渐进增强和常见的可访问性模式更加容易，无需任何开销。

然后，我们确保你还可以使用你已经熟悉并可能已经有的UI组件语言，甚至可以重用你可能已经有的组件。React、Preact、Svelte、Vue、Solid、Lit等，包括Web组件，都支持在Astro项目中编写UI组件。

Astro被设计得比其他UI框架和语言简单。一个很大的原因是Astro被设计为在服务器上渲染，而不是在浏览器中。这意味着你不需要担心：钩子（React）、陈旧的闭包（也是React）、引用（Vue）、可观察对象（Svelte）、原子、选择器、反应或衍生。服务器没有响应性，所以所有这些复杂性都消失了。

我们最喜欢的一句话是：**选择复杂性。**我们设计Astro的目的是尽可能从开发者体验中移除“必需的复杂性”，尤其是在你第一次加入时。你可以仅用HTML和CSS构建一个“Astro的“世界你好”示例网站。然后，当你需要构建更强大的东西时，你可以逐渐开始使用新的功能和API。

### 以开发者为中心

[标题为以开发者为中心的部分](https://docs.astro.build/en/concepts/why-astro/#developer-focused)

我们坚信，如果人们喜欢使用Astro，Astro才是一个成功的项目。Astro为你在使用Astro构建时提供了所需的一切支持。

Astro投资于开发者工具，如从你打开终端的那一刻起的出色CLI体验、官方的VS Code扩展用于语法高亮、TypeScript和Intellisense，以及由数百名社区贡献者主动维护且提供14种语言的文档。

我们在Discord上的热情、尊重、包容的社区准备提供支持、激励和鼓励。打开一个`#support`线程来获取项目的帮助。访问我们的专门`#showcase`频道，分享你的Astro站点、博客文章、视频，甚至正在进行的作品以获取安全的反馈和建设性的批评。参加我们的定期现场活动，如我们的每周社区呼叫、“Talking and Doc'ing”，以及API/bug大量测试活动。

作为一个开源项目，我们欢迎所有类型和规模的社区成员的贡献。你被邀请加入路线图讨论，以塑造Astro的未来，我们希望你将修复和功能贡献给核心代码库、编译器、文档、语言工具、网站和其他项目。
