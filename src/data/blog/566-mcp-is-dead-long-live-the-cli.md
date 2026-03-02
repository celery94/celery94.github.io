---
pubDatetime: 2026-02-28
title: "MCP 已死，CLI 永生"
description: "Anthropic 发布 MCP 后全行业争相跟进，但真正用过的人都知道它有多烦。LLM 本就擅长使用命令行工具，CLI 可调试、可组合、认证也不用重复折腾——我们根本不需要一个新协议。"
tags: ["MCP", "CLI", "LLM", "AI工具"]
slug: "mcp-is-dead-long-live-the-cli"
source: "https://ejholmes.github.io/2026/02/28/mcp-is-dead-long-live-the-cli.html"
---

我要说一个大胆的判断：MCP 已经在走下坡路了。我们可能还没完全意识到，但信号已经很明显。OpenClaw 不支持它，Pi 也不支持它。这不是偶然。

Anthropic 宣布 Model Context Protocol 之后，整个行业集体失去理智。每家公司都在赶着上线 MCP server，证明自己"AI first"。大量资源涌进新端点、新线格式、新鉴权方案——全是为了让 LLM 去调那些它们本来就能调的服务。

说实话，我从一开始就没搞懂这东西的必要性。你知道 LLM 最擅长什么吗？自己搞定问题。给它一个 CLI 和一份文档，它就能跑起来。

我拖了很久才动笔，但我确信：MCP 没有带来真实收益，没有它我们会更好过。

## LLM 不需要特殊协议

LLM 用命令行工具本来就很顺手。它们被训练在海量的 man page、Stack Overflow 回答和 GitHub 上的 shell 脚本上。我让 Claude 执行 `gh pr view 123`，它直接就干了。

MCP 承诺了一个更干净的接口，但实际用下来，我发现自己还是得写同样的文档：每个工具做什么，接受什么参数，以及更重要的，什么时候该用它。LLM 根本不需要一个新协议。

## CLI 也是给人用的

Claude 用 Jira 干了什么奇怪的事？我跑一下同样的 `jira issue view` 命令，马上就能看到它看到了什么。输入相同，输出相同，没有谜团。

MCP 的工具只存在于 LLM 对话上下文里。出了问题，我就得去翻 JSON 传输日志，而不是自己直接跑一遍命令。调试不应该需要协议解码器。

## 可组合性

这是差距最大的地方。CLI 可以组合。我可以管道给 `jq`，链式接 `grep`，重定向到文件。这不只是方便，很多时候是唯一实用的路子。

看这个分析 Terraform 计划的例子：

```bash
terraform show -json plan.out | jq '[.resource_changes[] | select(.change.actions[0] == "no-op" | not)] | length'
```

MCP 的选择是什么？要么把整个 plan 塞进上下文窗口（贵，而且经常行不通），要么在 MCP server 里自己写过滤逻辑。两条路都是更多的工作，更差的结果。CLI 用的是已经存在的工具，有完善的文档，人和 agent 都懂。

## 认证早就解决了

MCP 在鉴权上画蛇添足。一个给 LLM 提供工具的协议，为什么要管认证这件事？

CLI 工具不在乎这个。`aws` 用 profiles 和 SSO，`gh` 用 `gh auth login`，`kubectl` 用 kubeconfig。这些都是经过验证的认证流程，不管是我在键盘上操作还是 Claude 在驱动，行为完全一样。认证出了问题，我就按老办法修：`aws sso login`、`gh auth refresh`。不需要任何 MCP 专属排查。

## 没有多余的动件

本地 MCP server 是进程。它们需要启动，保持运行，还不能悄悄挂掉。在 Claude Code 里，它们作为子进程被 spawn 出来，能跑到不能跑为止。

CLI 工具就是磁盘上的二进制文件。没有后台进程，没有状态要管，没有初始化的仪式感。用到就在，用不到就当它不存在。

## 日常的摩擦

设计理念之外，MCP 还有实实在在的日常麻烦：

**初始化不稳定。** 我数不清多少次因为 MCP server 没起来而重启 Claude Code。有时候重试能好，有时候就只能清状态从头再来。

**重复鉴权没完没了。** 同时用多个 MCP 工具？准备好一个一个去认证吧。用了 SSO 或者长期凭证的 CLI 根本没有这个问题。认证一次，完事。

**权限是全有全无。** Claude Code 可以按名字 allowlist MCP 工具，仅此而已。你没法把工具限制在只读操作，也没法约束参数。用 CLI 我可以 allowlist `gh pr view`，但要求审批才能跑 `gh pr merge`。这种粒度很重要。

## 那 MCP 什么时候有用？

我不是说 MCP 一无是处。如果一个工具确实没有 CLI 等价物，MCP 可能就是对的选择。我自己也在用，但只在没有别的选项的时候。

标准化接口或许有一定价值，某些场景下可能比 CLI 更合适，我也承认这一点。

但对绝大多数工作来说，CLI 更简单，调试更快，也更可靠。

## 真正的教训

最好的工具是人和机器都能用的工具。CLI 经历了几十年的设计打磨。可组合，可调试，搭着现有的认证体系走。

MCP 想造一个更好的抽象。结果发现，我们已经有一个不错的了。

如果你是一家公司，正在投入资源做 MCP server，但自己连官方 CLI 都没有——停下来，想清楚你在干什么。先把 API 做好，再把 CLI 做好。agent 会自己搞定的。
