---
pubDatetime: 2026-05-22T08:03:23+08:00
title: "AX Stack：AI 编程代理真正可调的是扩展层"
description: "Microsoft Developer Blog 用 AX stack 解释 AI coding agent 的工作链路：model 和 harness 多半不可控，真正能改的是 skills、MCP servers、instructions 等 agent extensions，并且要用 lift 和 drag 做受控测量。"
tags: ["AI", "Agent Experience", "MCP", "工程实践"]
slug: "ax-stack-agent-extensions-lift-drag"
ogImage: "../../assets/822/01-cover.png"
source: "https://devblogs.microsoft.com/blog/the-ax-stack-whats-fixed-where-you-can-win"
---

AI coding agent 看起来能提升效率，但实际使用时经常会翻车：生成的代码不能编译，沿用过期 SDK，或者直接选错服务。遇到这类问题，很容易把原因归到模型、提示词或工具本身。

Waldek Mastykarz 这篇文章提出了一个更具体的观察角度：把从开发者 prompt 到生成代码之间的链路拆成 AX stack，也就是 Agent Experience stack。只有看清每一层是谁控制的，才知道该改哪里。

## 三层栈

原文把链路画成这样：

```text
Developer prompt
  -> Agent (harness)
    -> Model
      -> Agent extensions (skills, MCP servers, instructions, custom agents)
        -> Your technology surface (CLI, SDK, API)
          -> Generated code
```

对 AX 来说，最重要的是三层：model、harness、agent extensions。

model 是固定约束。你没有训练它，也不能改它的 weights。如果模型从旧文档里学到你的 API，它会生成旧写法；如果训练时几乎没见过你的技术，它会编一个看起来合理但错误的方案；如果竞品有更多训练数据，模型可能默认选竞品。

harness 是代理本身，比如 Copilot、Claude Code CLI、Cursor、Windsurf。它控制 system prompt、tool calling 协议、上下文怎么组装、哪些内容被放进窗口、哪些内容被丢掉。你也很难控制它。同一个 MCP server，在不同 harness 里可能表现完全不同。

agent extensions 是你能直接影响的层。它包括 skills、MCP servers、instruction files 和 custom agents。技术所有者可以用它教 agent 正确使用自己的 CLI、SDK 和 API；开发者也可以在工作区里配置它们，让 agent 更接近当前项目的真实约束。

## 上下文窗口是竞争资源

文章强调，context window 是 zero-sum，也就是一个扩展多占一点，别的内容就少一点。

开发者装了 15 个 extensions 后，harness 要决定加载哪些工具、保留哪些描述、丢掉哪些内容。你的 MCP tool description 可能被压缩、截断，甚至根本没进上下文窗口。

这带来一个组合问题。一个 extension 单独测试时表现很好，和其他热门 extension 一起出现后可能变差。原因不一定是内容错了，而是多个扩展在争同一段上下文空间，模型还要在相似描述之间做选择。

所以，更多 extensions 不一定带来更好结果。扩展之间会互相影响，这一点必须进入测试。

## 三种失败模式

作者总结了三种常见失败。

第一种是 discovery failure。扩展存在，但 agent 没看到。可能是开发者装了太多扩展，你的内容在进入上下文前被丢掉；也可能是 harness 的注册或优先级逻辑没有加载它。模型看不到工具，就不可能使用工具。

第二种是 selection failure。扩展已经在上下文里，但 agent 没把它和开发者意图连起来。例如开发者说“set up authentication”，你的工具名叫 `configure-identity-provider`，模型没有建立关联。原文说这类问题最常见，也最容易修，关键是工具描述要使用开发者和模型都能理解的词。

第三种是 quality failure。扩展被发现、被选择、也被调用了，但返回内容让结果变差。比如 MCP server 返回一大段文字，模型忽略或误解；skill 给出的步骤和模型已有知识冲突；内容准确但太长，把其他有用上下文挤掉。

第三种最隐蔽，因为从日志看扩展“工作了”，但结果没有变好，甚至更差。

## 真正优化什么

文章把 AX 的优化目标压成四个问题：

- agent 能发现你的 extensions 吗
- agent 会为当前任务选择它们吗
- 调用之后结果会变好吗
- 它们和其他常见 extensions 放在一起还能工作吗

对应就是 discovery、selection、quality、composition。

这四个问题比“我的 MCP server 是否能被调用”更有价值。被调用只是中间过程，结果变好才是目标。

## Lift 和 drag

原文用 lift 和 drag 描述 extension 的真实影响。

lift 是扩展带来更好的结果：agent 找到工具，正确使用工具，生成代码能编译，SDK 和模式都是最新的。

drag 是扩展没有带来收益，或者让结果变差。可能 agent 没发现它；可能发现后没选；可能选了但返回内容太乱；也可能单独可用，和其他扩展一起就冲突。

判断 lift 和 drag 的办法是做受控对照：同一个场景、同一个 prompt、同一个 model、同一个 harness，一次不加载你的 extension，一次加载你的 extension，然后比较结果。

如果加上扩展后结果更好，就是 lift。如果一样或更差，就是 drag。如果结果更好但 token 成本涨很多，那是 expensive lift，是否值得要看提升幅度。

## 对技术团队的启发

如果你维护一套技术栈，想让 AI coding agents 更会用它，文章给出的方向很清楚：别把全部希望放在模型训练上，也别指望能控制 harness。当前最可操作的是 agent extensions。

但写 extension 不能只追求“内容更全”。你需要让它更容易被发现，更容易被选择，返回内容更短更准，并且在常见组合里不拖后腿。

这也意味着 AX 需要 eval。至少要有一组代表性任务，覆盖真实开发者会问的问题。每次改 tool description、skill 或 instruction 后，跑一遍有无扩展的对照，记录结果、失败模式和 token 成本。

## 结语

这篇文章的价值，是把“agent 为什么没写对代码”拆成了可诊断的问题。

model 和 harness 往往不是你能直接改的层。agent extensions 才是短期内最有杠杆的部分。把扩展做小、做准、做可测，再用 lift 和 drag 判断它是否真的改善结果，这才是 AX 工作的起点。

## 参考

- [The AX stack: what's fixed, where you can win](https://devblogs.microsoft.com/blog/the-ax-stack-whats-fixed-where-you-can-win)
- [Agentic-Agile: Why Agent Development Needs Agile](https://developer.microsoft.com/blog/agentic-agile-why-agent-development-needs-agile-not-just-prompts)
