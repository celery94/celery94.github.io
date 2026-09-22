---
pubDatetime: 2026-09-22T08:18:00+08:00
title: "Jev 决策模型：调用方式、成本与边界"
description: "TypeSafe 的 Jev 只输出带概率的判断而不是文本。核对它的调用方式、每百万 token 0.042 美元的定价，以及官方文档承认的失败模式与提示注入风险。"
tags: ["Jev", "TypeSafe AI", "LLM", "决策模型", "AI 应用"]
slug: "jev-decision-models-api-and-limits"
ogImage: "../../assets/1079/01-cover.jpg"
source: "https://simonwillison.net/2026/Sep/21/jev/"
---

Simon Willison 在 [Jev introduces a new shape of LLM](https://simonwillison.net/2026/Sep/21/jev/) 里点出的第一个数字不是能力，而是价格：TypeSafe AI 的 Jev 每百万输入 token 收 0.042 美元，**输出免费**。他引 llm-prices.com 的比较说，这比 GPT-5 Nano 还便宜。

一个不收输出费的模型，是因为它根本不输出文本。Jev 接受文本输入，返回的是一串浮点数：类别、是/否、评分，以及每个答案自带的置信度。

它值得看的地方不只是便宜。现有 LLM 做分类时要先被逼着生成一段字符串，再由你的代码解析、校验、兜底；Jev 把这一步做成了原生输出。代价是它只还你一个概率——理由、解释和责任，全都回到你的代码里。

## 它返回什么

TypeSafe 把交互压缩成两个东西：一个 **state**（要评估的内容，可以是字符串、字符串数组或 JSON 对象），和一组 **questions**。一次请求发过去，每个问题拿回一个类型化的答案。

三种问题类型：

| 类型     | 问的是什么         | 返回什么                                         |
| -------- | ------------------ | ------------------------------------------------ |
| `choice` | 这几个选项里是哪个 | `choice`、`probabilities`、`confidence`          |
| `score`  | 落在哪一档         | `score`、`legend`、`probabilities`、`confidence` |
| `noul`   | 这句话成立吗       | `noul`（0 到 1）                                 |

`noul` 这个名字来自伯努利分布（Bernoulli）——Simon 说 TypeSafe 的 CEO 在 Hacker News 上确认过这一点。

一个真实的请求长这样，把客户留言同时分派、评级、判断紧急度：

```json
{
  "state": "Hi, I've been trying to connect my Stripe account for 3 days and the integration keeps failing. I'm losing sales. Please help ASAP.",
  "model": "jev-latest",
  "questions": {
    "department": {
      "type": "choice",
      "instructions": "Which team should handle this",
      "criteria": {
        "billing": "Payment or subscription issues",
        "technical": "Bugs or integration problems",
        "sales": "Pricing or account questions"
      }
    },
    "frustration": {
      "type": "score",
      "instructions": "How frustrated the customer appears",
      "criteria": [
        "Calm, just stating facts",
        "Frustrated but civil",
        "Very angry, strong language"
      ]
    },
    "is_urgent": {
      "type": "noul",
      "instructions": "The message conveys urgency or time-sensitivity"
    }
  }
}
```

返回：

```json
{
  "model": "jev-1.13.0",
  "answers": {
    "department": {
      "type": "choice",
      "choice": "technical",
      "confidence": 0.78,
      "probabilities": { "technical": 0.85, "sales": 0.0, "billing": 0.15 }
    },
    "frustration": {
      "type": "score",
      "score": 1.0,
      "confidence": 1.0,
      "probabilities": { "0": 0.0, "1": 1.0, "2": 0.0 }
    },
    "is_urgent": { "type": "noul", "noul": 1.0 }
  },
  "usage": { "input_tokens": 392, "output_tokens": 65 }
}
```

三个细节决定了这套东西好不好用。

**问题是并行评估的。** 同一份 state 只读一次，所有问题独立求值。加问题的成本只有那几个问题的 token，响应时间几乎不变，官方文档的说法是「问一个你可能用不上的问题几乎是免费的」。这直接催生了他们主推的一种用法，后面再说。

**`noul` 没有 `confidence`。** 这是最容易看漏的一点。Choice 和 Score 会把概率分布压成一个 0 到 1 的 `confidence`；而 noul 本身就是「答案为是」的概率，两个结果的是/否分布已经被这一个数字完整描述了，所以没有第二个字段。想让 noul 变成布尔值，就在代码里定阈值，阈值高低取决于判断错了有多贵。

**不要用 noul 代替程度。** 官方文档专门举了反例：问「这个候选人 Python 强吗」，四个候选人得到 0.03、0.14、0.81、0.92，但这串数字衡量的是「强」这个命题成立的概率，不是能力刻度，中间值既可能是「中等水平」也可能是「情况不明」。要程度就用 Score，把每一档用文字写清楚。

## 它放弃了什么

System One 这个名字来自卡尼曼《思考，快与慢》里「快速直觉的系统 1」与「缓慢推理的系统 2」的区分。Maggie Appleton [建议](https://twitter.com/Mappletons/status/2101560333441610133)叫它 decision models（决策模型），Simon 表示同意——这个名字更直白地说了它是什么。

TypeSafe 的创始人 Diogo Almeida 之前在 OpenAI 参与过让语言模型学会遵循指令的那批方法，也就是 ChatGPT 背后的研究。他的问题意识是：模型在聊天上超越人类很多年了，自动化在哪里？他的答案是，问题出在接口上——字符串太灵活，能是聊天回复、代码，也能是幻觉和拒绝，软件要用它必须先解析再校验。

于是 Jev 放弃了字符串生成，换来三件事：并行采样（一次出全部输出，而不是一个 token 一个 token 地自回归）、输出被约束在预先定义的取值范围内，以及官方所说的「不会产生类型错误」——这一点他们在公告里写得很硬：想证伪只需要一个反例，但这是数学上不可能的。

这里的「不会幻觉」要读准确：**它不会编造格式，但仍可能给出错误的概率。** 一个判断错了的置信度，不会因为你收到的是一张合法的 JSON 就变对。

## 当前版本、价格与限额

以下数字来自官方文档（2026-09-22 核对）：

| 项目     | 值                                                         |
| -------- | ---------------------------------------------------------- |
| 模型 ID  | `jev-1.13.0`                                               |
| 别名     | `jev-latest` 与 `jev-preview` 当前都指向 `jev-1.13.0`      |
| 价格     | 输入 0.042 美元 / 百万 token（42 美元 / 十亿），输出免费   |
| 限额     | 每秒 250,000 token / 每分钟 1,200 请求，官方说明会动态调整 |
| 上下文   | 每次请求 64k token；其中 state 加最长的一个问题最多 32k    |
| 输入模态 | 仅文本，不支持图片、音频、视频                             |

三件容易被忽略的事。

**别名会漂移。** `jev-latest` 随新版本移动，同一个别名背后的答案可能在你不改代码的情况下变化。如果你的业务已经按某个版本校准过置信度阈值，就应该钉住 `jev-1.13.0` 这样的版本号，按自己的节奏升级。响应里的 `model` 字段会回传实际作答的版本，值得打进日志。

**中文是次要语言。** 官方文档写得很直接：英语是主要训练语言，也是目前准确度最高的语言；其他语言包括 CJK 都能处理，但质量不对等，在非英语负载上依赖 Jev 之前请用你自己的数据测，并且特别关注置信度。对中文项目来说，这一条应该排在所有基准测试之前。

**选择数量上限 255。** 官方公告提到 Jev 支持最多 255 个选项；更高基数会走两阶段——先独立打分，再做一次显式选择。

## 最小验证路径

在 Playground 里贴一段文本、加一个问题就能看到输出结构。要走代码，一个 curl 就够：

```bash
curl -X POST https://api.typesafe.ai/v1/systemone \
  -H "Authorization: Bearer $TYPESAFE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "state": "I have asked three times now. Can I please just talk to a real person?",
    "model": "jev-latest",
    "questions": {
      "is_human_escalation": {
        "type": "noul",
        "instructions": "Is the customer asking for a human agent?"
      }
    }
  }'
```

Python SDK 是 `typesafe-sdk`（需要 Python 3.10+），客户端默认从环境变量 `TYPESAFE_API_KEY` 读取密钥，默认调用 `jev-latest`：

```python
from typesafe_sdk import Noul, TypeSafeClient

with TypeSafeClient() as client:
    response = client.system_one(
        state="I have asked three times now. Can I please just talk to a real person?",
        questions={
            "is_human_escalation": Noul(
                instructions="Is the customer asking for a human agent?",
            ),
        },
    )
    print(response.answers["is_human_escalation"].noul)
```

官方文档给了一组 `jev-1.13.0` 对同一个问题的实测值，可以直接用来校准你的阈值直觉：「Thanks, that fixed it!」是 0.02，「How do I reset my password?」是 0.07，「I need this sorted today, whatever it takes.」是 0.26——紧急但没要求转人工，「Are you a bot?」是 0.40——暗示想找人但没明说，最后那句「Can I please just talk to a real person?」是 0.99。

**验证的重点不是「它答对了吗」，而是「置信度高的时候是不是真的更准」。** 如果高置信度区间和低置信度区间的准确率没有差别，那这个模型对你的场景就只是个昂贵的随机数生成器，阈值路由也就失去了意义。这件事只能在你自己的数据上花几美分跑几百条来回答。

## 两个真正省钱的用法

**把大判断拆成原子问题，在代码里加权。** 这是官方最反复强调的一条。不要问「给这个创业项目打分」，而是分别问市场规模、技术可行性、差异化，然后在你自己的代码里配权重。当优先级变化时，改的是代码里的系数，不是重写 prompt。

**把可能要用的都问上。** 因为并行求值，同一个 state 上多问几个问题几乎不增加时间。官方的说法是：如果第二个请求的问题本来就能对原始 state 提出来，那就放进第一个请求，让代码忽略不需要的答案。他们管这叫 speculative fan-out。

Simon 提到他一直在用 Jev 做检索重排：先用 BM25 这类便宜算法取回 100 个候选，再让 Jev 对每个候选打分。官方有一份完整的[重排 cookbook](https://docs.typesafe.ai/cookbooks/rerank_typesafe)给出了硬数字，在 CLERC 法律检索数据集上，3,565 个段落、40 个查询、每个查询取 30 个候选，用一条 `noul` 问题逐对打分后：

| 指标   | 仅 BM25 快速检索 | 加上 Jev 重排 |
| ------ | ---------------- | ------------- |
| Top 1  | 5%               | 18%           |
| Top 5  | 15%              | 35%           |
| Top 10 | 38%              | 62%           |

这 1,200 次调用一共用了 1,536,002 个输入 token，官方算出来的成本是 0.0645 美元。值得注意的不是提升幅度，而是**成本结构**：这类「每个候选问一遍」的用法在 GPT 级别的模型上通常根本不会进入讨论，因为光是调用次数就撑不住。

我没有在自己的数据上复现过这组数字，它是 TypeSafe 自己发布的评测，候选集来自 BM25 而不是全库，所以只应该被读成「这条路值得试」，不是「你的场景也会涨到 18%」。

## 官方承认的失败模式

TypeSafe 专门写了一页 [Jev 1.13 的 jaggedness](https://docs.typesafe.ai/model-jaggedness/jev-1.13)，列了九个已知的粗糙边缘。这份清单比大多数模型卡诚实，做方案评估时比他们的宣传页更有用：

| 失败模式             | 表现                                   | 该怎么做                                      |
| -------------------- | -------------------------------------- | --------------------------------------------- |
| 字面理解             | 答的是你写的问题，不是你想问的问题     | 把条件和边界写进 `instructions` 与 `criteria` |
| 数学与数字           | 不会算，也不可靠地计数                 | 算术留在代码里                                |
| 日期时间比较         | 把日期当文本读，不当作有序量           | 抽取交给模型，比较交给代码                    |
| 多层间接             | 双重否定、属性的属性，准确率下降       | 减少跳数，直接点名 state 的字段               |
| state 过大的噪声     | 无关细节越多越差，官方称为 context rot | 先在代码里检索过滤                            |
| 对抗性内容           | state 默认不被当作敌意输入             | 写清楚的 criteria，上线前测边界               |
| 指令与 criteria 矛盾 | 一个说东一个说西会困惑                 | 把 criteria 当作指令的延伸                    |
| 结构不变量           | 不保证成立                             | 不要跨问题做算术恒等式                        |
| 生成                 | 没训练过生成文本，链式选择又慢又差     | 需要生成就换模型                              |

其中三条对工程决策影响最大。

**它不会替你算数。** 官方原话是「Jev 不是计算器」，连计数都不可靠，而且误差随被数对象变大而增长。想统计「列表里有多少个水果」，正确做法是逐项问一个 `noul`，然后在代码里把大于阈值的加起来。

**提示注入是真实存在的面。** 官方明确写了：state 是数据，但模型默认不把它当敌意输入，一段精心设计的指令、一个有误导性的框架、甚至一段论证自己应该被分到某类的文本，都能推动答案。这一点值得单独拎出来——因为它最常见的用法正好是「给检索到的段落打分」，而那些段落来自你的语料库，未必可信。

**不要指望结构不变量。** 官方给了一个很好的例子：同一句「Is the customer asking for a refund?」，作为 noul 问得到 0.22，作为 yes/no 的 Choice 问得到 `yes: 0.01`。另一个例子更直接：`refund` 得到 0.72，`not_refund` 得到 0.47，两者相加是 1.19。所以他们建议不要在 noul 上校准出的阈值直接搬到 Choice 上，也不要指望 `P(A)` 和 `1 - P(¬A)` 相等。

## Simon 的保留：黑箱又往前走了一步

Simon 写得最重的不是能力，而是这一点：

> Something I've found a little uncomfortable about Jev is how it very much represents a regression even further towards black box machine learning systems.

也就是说，让他不安的不是能力，而是 Jev 代表着向黑箱机器学习系统的进一步倒退。

他的论证是分层的。LLM 本来就已经是黑箱——你可以要求它解释自己的决定，但没法保证那些解释有用或准确。Jev 连这个都没有：输入任意多的文本，你拿回来的只有一个浮点数。如果 Jev 把某条内容标成垃圾邮件，到底是哪些信号触发的？

顺着这个逻辑，偏见的问题会更难处理。Simon 明确写了他希望没有人用 Jev 给求职者排序——那个浮点数可以藏住各种看不见的偏见，而想通过实验把偏见拆出来会非常棘手。

他做了一个小实验来佐证这种不安：让 Jev 对湾区每座城市回答「Good city?」这个 yes/no 问题，结果是 Cupertino 最高，East Palo Alto 最低。他把这个结果摆在括号里，配了一句「Huh.」。这是他的个人观察，不是一个关于模型的结论——它恰好说明了那个浮点数有多难追问。

他对这个问题的应对也很务实：正因为 Jev 便宜到可以跑几百上千次实验，**evals 和结构化实验在决策模型上比在普通 LLM 项目里更重要**。官方文档在这件事上其实和 Simon 站在一起，他们给出的三档路由就是这个思路——高置信度自动执行，中置信度先确认或标记复核，低置信度不动、转人工。

黑箱特性还有一个实际后果是工程性的：**解释责任从模型转移到了你的系统设计上。** 当你把一个判断做成浮点数，你就得自己准备好审计记录、阈值变更历史和回滚路径，否则出问题时没有任何东西可以回看。

## 一周内长出来的生态

Simon 特意提到，Jev 发布不到一周，社区的活动量让他印象深刻。他挑出来的几个，恰好都在试探这个模型不该被用来做什么：

- **jevchat**（Kyle Pena）把 Jev 变成一个「糟糕的」聊天模型：每一步只问一个问题——给定用户的问题和已经写出的回复，下一个符号是哪个。Hacker News 上 ericpruitt 的评论是：「这相当于 Morty 对着死亡水晶说话的数字版。」
- **jev-leftpad**（Fatih Kadir Akın）用 Jev 实现 left-pad，问的是「value 前面需要几个空格才能达到 targetLength」，选项从「需要 0 个空格」到「需要 10 个空格」。
- **jev-2048**（Andy Gayton）让 Jev 玩 2048。
- **Kev** 尝试在开源权重模型上复刻，基于 Qwen 3.5 做出 0.8B、4B、9B 三个规模，配套的 Hacker News 讨论串里已经有人贴出 JevBench 这个用来比较「Jev 级决策模型」的基准。

这些是社区项目，能说明方向对不对，但不能当作官方能力。其中 left-pad 和 jevchat 尤其应该被读成反例：它们都在用链式选择去逼近生成，而官方文档明确说过这条路又慢又差。

## 什么时候该用

判断标准可以简化成一个问题：**你要的这个判断，能不能在一句话里问清楚，并且你的代码能对答案直接采取行动？**

适合的情况，判断本身是分类、排序、路由或打分，而且你能把大判断拆成几个原子问题：

- 工单分派、优先级、意图路由
- 垃圾内容、提示注入、越狱尝试的检测与分级
- 检索结果重排、段落筛选
- 内容打标、合规检查这类可以逐条问的清单

不适合的情况：

- 需要解释或可追溯的理由（它只给数字）
- 需要生成文本（它没训练过）
- 需要精确的数学、计数或日期运算（写在代码里）
- 对个体产生重大影响的决策——Simon 点名了招聘，同理还有信贷、保险、医疗分诊。这类场景里一个没有解释的浮点数不是效率提升，是风险转移
- 中文等非英语负载，除非你先用自己的数据测出可接受的准确度

和「让 LLM 输出 JSON」相比，取舍也很清楚：LLM 方案更灵活、能处理需要推理的问题、还能顺带给你理由，代价是更慢、更贵、需要解析和校验、结果还会漂移。Jev 更窄、更快、更便宜、输出有保证，代价是你必须提前把问题想清楚，而且拿不到任何解释。

先在一个具体的小场景上跑几百条自己的数据，看高置信度是否真的对应高准确率。如果对应，它能替你省掉一整套「解析 LLM 输出再加兜底」的管道；如果不对应，再便宜也没有意义。

Aide Hub 会继续整理这类模型能力与边界的核对笔记，覆盖 AI 助手、开发工具与软件工程实践。

## 参考

- [Jev introduces a new shape of LLM—System One, aka Decision Models](https://simonwillison.net/2026/Sep/21/jev/)（原文，Simon Willison）
- [Introducing System One Models & Jev](https://typesafe.ai/blog/introducing-system-one-models-and-jev)（TypeSafe AI 官方公告）
- [TypeSafe AI 文档：Introduction](https://docs.typesafe.ai/introduction)
- [TypeSafe AI 文档：Primitives（Choice / Score / Noul）](https://docs.typesafe.ai/primitives)
- [TypeSafe AI 文档：Models（价格、限额、上下文）](https://docs.typesafe.ai/models)
- [TypeSafe AI 文档：Confidence](https://docs.typesafe.ai/confidence)
- [TypeSafe AI 文档：Jev 1.13 jaggedness（已知失败模式）](https://docs.typesafe.ai/model-jaggedness/jev-1.13)
- [TypeSafe AI Cookbook：Re-ranking](https://docs.typesafe.ai/cookbooks/rerank_typesafe)
- [Quote Tweet：Maggie Appleton 建议 decision models 这个名字](https://twitter.com/Mappletons/status/2101560333441610133)
- [OpenAI 定价对比（Simon 引用的 llm-prices.com）](https://www.llm-prices.com/)
