---
pubDatetime: 2026-08-31T08:12:00+08:00
title: "四种 LLM 缓存：省在哪里，错在哪里"
description: "从 KV、Prefix、Prompt 到 Semantic Cache，讲清四种 LLM 缓存保存什么、何时命中、为何失效，以及生产环境该如何排查成本、延迟与错误命中。"
tags: ["LLM", "Prompt Caching", "KV Cache", "AI Engineering"]
slug: "llm-cache-four-layers"
ogImage: "../../assets/1037/01-cover.jpg"
source: "https://x.com/_avichawla/status/2093265776266637739"
---

同一个 LLM 应用里，常能听到四种「缓存」：KV cache、Prefix caching、Prompt caching 和 Semantic caching。名字接近，保存的对象、命中条件和风险却差得很远。

最容易记住的区别是：前三种都在复用模型已经算出的注意力状态，仍然会继续运行模型；Semantic cache 保存的是完整回答，命中后直接跳过模型。前三种未命中，损失主要体现在延迟和费用。Semantic cache 错误命中，用户会收到一条看似成功的错误答案。

## 先用一张表分清四层

| 缓存             | 保存什么                     | 作用范围               | 命中条件                      | 主要收益                         | 主要风险                     |
| ---------------- | ---------------------------- | ---------------------- | ----------------------------- | -------------------------------- | ---------------------------- |
| KV cache         | 每层注意力的 Key、Value 张量 | 单次请求或一段持续会话 | 已处理 token 的连续状态仍有效 | 降低逐 token 解码的重复计算      | 显存占用随上下文增长         |
| Prefix caching   | 可跨请求复用的 KV 块         | 推理服务内部           | token 前缀精确相同            | 降低首 token 延迟和 prefill 计算 | 前缀稍有变化就从变化处失效   |
| Prompt caching   | 云服务商提供并计费的前缀复用 | 托管模型 API           | 满足服务商规则的精确前缀      | 降低输入费用和延迟               | 规则、有效期、计费随模型变化 |
| Semantic caching | 已完成的回答文本             | 应用层                 | 向量相似度超过阈值            | 连输入和输出生成都能跳过         | 相似问题可能需要相反答案     |

这张表也给出了排查顺序。生成慢，先看 KV 和 prefill；同类请求仍然贵，检查 Prefix 或 Prompt cache；接口很快却答错了，优先怀疑 Semantic cache。

## KV cache：让解码只处理新 token

自回归模型一次生成一个 token。处理第 `t` 个 token 时，它需要关注前面所有 token。若每一步都重新计算历史 token 的 Key 和 Value，重复工作会越来越多。

KV cache 保存各层已经计算过的 Key、Value。下一步只计算新 token 的向量，再读取历史缓存完成注意力计算。Query 没有同样的复用价值：某个 token 的 Query 只在它被处理时使用一次，后续 token 会反复读取它的 Key 和 Value。

[Hugging Face Transformers 的缓存文档](https://huggingface.co/docs/transformers/v5.6.0/en/kv_cache)把这些状态作为显式对象暴露出来。`DynamicCache` 随生成增长，适合长度变化大的请求；`StaticCache` 预分配固定空间，便于编译优化，但短请求可能浪费空间；量化或把缓存移到 CPU 可以省显存，同时会增加转换或传输成本。

因此，KV cache 解决计算重复后，瓶颈常会转向内存：上下文越长，需要保存和搬运的 KV 张量越多。排查长上下文吞吐时，只看 GPU 计算利用率很容易漏掉显存容量和带宽。

## Prefix caching：把相同前缀跨请求复用

普通 KV cache 往往随请求结束释放。Prefix caching 会保留一部分 KV 块，让后来的请求复用相同前缀。

[vLLM 的 Automatic Prefix Caching](https://docs.vllm.ai/en/v0.13.0/design/prefix_caching/)会把当前块的 token 与此前前缀一起纳入哈希。调度器按顺序查找缓存，遇到第一个未命中的块就停止复用。这个设计保证正确性：只有此前所有 token 都一致，后面的 KV 状态才有效。

它也解释了几个常见现象：

- 在 system prompt 最前面加入时间戳、用户名或请求 ID，会让后面的大段稳定内容全部失效；
- 同一组 RAG 文档只要排序不同，拼接后的 token 前缀就不同；
- 工具定义内容相同但序列化顺序变化，也可能让缓存提前中断；
- 多租户服务可以给缓存键加入租户级 salt，以较低命中率换取隔离。

最实用的写法很朴素：稳定内容放前面，频繁变化的内容放后面。若平台提供显式断点，就把断点放在两者边界。

## Prompt caching：服务商包装后的前缀缓存

使用托管 API 时，看不到 KV 块、淘汰策略和调度器。服务商把前缀复用包装成 Prompt caching，并通过用量字段、有效期和价格让应用控制它。

这里不能把某一家服务商的数字当成通用规则。以 2026 年 8 月的官方资料为例：

- [Anthropic 定价说明](https://docs.anthropic.com/en/docs/about-claude/pricing)中，5 分钟缓存写入按普通输入的 `1.25×` 计费，1 小时写入为 `2×`，读取为 `0.1×`；
- [OpenAI GPT-5.6 指南](https://developers.openai.com/api/docs/guides/latest-model)说明该系列的缓存写入为普通输入的 `1.25×`，读取享受 90% 折扣；Responses API 还支持显式缓存断点，并通过 `cache_write_tokens` 与 `cached_tokens` 报告写入和读取。

写入有溢价，意味着「开了缓存」不等于一定省钱。稳定前缀必须在有效期内被重复读取，才有机会收回写入成本。应当按真实流量计算：

```text
缓存净收益 = 避免的普通输入费用 - 缓存写入溢价 - 缓存读取费用
```

观测时至少记录模型、输入 token、缓存写入 token、缓存读取 token、首 token 延迟。只看请求总费用，会分不清前缀从未命中、刚写入尚未复用，还是换模型后重新变冷。

## Semantic cache：最快，也最容易悄悄答错

Semantic cache 会把问题转成向量，在历史问题中查找最相似项。相似度超过阈值时，直接返回对应的旧回答。模型没有运行，所以输入生成与输出生成的费用都省掉了。

风险也来自同一个机制。下面三组句子在向量空间里都可能很接近，但业务含义不同：

- 「API 有速率限制吗？」与「API 没有速率限制吗？」；
- 「年付方案退款规则」与「月付方案退款规则」；
- 「删除测试数据」与「删除生产数据」。

单纯提高阈值无法解决否定词、金额、日期、套餐和权限这类细小却关键的差异。阈值过高会让命中率迅速下降，过低会增加错误回答。HTTP 仍然可能返回 `200`，常规错误监控也看不到问题。

更稳妥的顺序是先测量完全相同请求的重复率。若字节级相同请求已经很多，Exact response cache 更简单，也没有相似度误判。只有在问题范围窄、答案稳定、错误代价低，并且有离线样本可以评估时，再考虑 Semantic cache。涉及账号状态、价格、权限、医疗、法律或实时数据的回答，不适合直接复用旧答案。

## 五类问题最容易破坏复用

原文总结的生产问题可以压缩成五项检查：

1. **变量放得太早**：时间、用户、请求 ID 位于稳定说明之前。
2. **工具与设置发生变化**：工具顺序、搜索、引用、推理设置或 `tool_choice` 改写了实际输入。
3. **历史被重写**：摘要替换旧消息后，整个前缀从替换处变冷。
4. **模型发生切换**：缓存通常与具体模型绑定，路由到另一模型需要重新 prefill。
5. **文本看着一样，token 不一样**：BOS、换行、聊天模板和序列化细节都会造成差异。

最后一项最好直接比较 token ID。日志中的字符串只能告诉你「看起来相同」，token 序列才能指出从哪个位置开始无法复用。

## 一套够用的选择顺序

准备优化 LLM 应用时，可以按下面顺序做：

1. 确认推理框架已正确使用 KV cache，并测量长上下文下的显存与带宽；
2. 把稳定指令、工具定义和共享文档移到前面，把用户变量移到后面；
3. 观察 Prefix 或 Prompt cache 的真实读写 token 和首 token 延迟；
4. 先尝试完全匹配的回答缓存；
5. 确有模糊复用需求时，用业务样本评估 Semantic cache 的错误命中率，不能只看命中率。

缓存优化的关键问题始终是三个：保存了什么、以什么条件复用、命中错误会发生什么。回答清楚这三个问题，四种缓存就不会再混成一个概念。

Aide Hub 会继续分享 AI 助手、开发工具和软件工程实践。

## 参考

- [KV, Prefix, Prompt and Semantic Caching in LLMs, clearly explained](https://x.com/_avichawla/status/2093265776266637739)
- [Hugging Face Transformers：Cache strategies](https://huggingface.co/docs/transformers/v5.6.0/en/kv_cache)
- [vLLM：Automatic Prefix Caching](https://docs.vllm.ai/en/v0.13.0/design/prefix_caching/)
- [Anthropic：Pricing](https://docs.anthropic.com/en/docs/about-claude/pricing)
- [OpenAI：GPT-5.6 model guidance](https://developers.openai.com/api/docs/guides/latest-model)
- [OpenAI Responses API：Prompt cache options](https://developers.openai.com/api/reference/cli/resources/responses/methods/create)
