---
pubDatetime: 2026-10-23T09:13:00+08:00
title: "Decisions API：更快返回有限答案的判断接口"
description: "OpenAI Decisions API 面向分类、路由和评分等有限答案任务。本文说明 predicate、choice、score 的差别，给出可运行的工单分诊示例、阈值设置与成本边界。"
tags: ["OpenAI", "Decisions API", "API", "LLM", "TypeScript"]
slug: "decisions-api-bounded-answers"
ogImage: "../../assets/1111/01-cover.jpg"
source: "https://openai.com/index/decisions-api/"
---

一个客服 agent 每收到一句话，就要判断它属于账单、技术还是物流问题，还要决定是否紧急、是否需要人工接手。这些判断单独看都很简单，放进每天大量重复的流程后，等待时间和 token 成本会一起放大。

OpenAI 在 2026 年 10 月 22 日正式开放 Decisions API。它仍然调用 `gpt-6-luna`，接口却只要求返回概率、固定选项或评分，官方给出的判断速度最高比 Responses API 快 10 倍。

这篇文章会说明它适合解决什么问题，并用一个工单分诊脚本串起三种答案类型。读完后，你能判断现有流程是否值得迁移，也知道第一次接入时该先定哪些边界。

## 先看结论

Decisions API 适合这样的任务：答案可以提前限定，调用频次高，应用拿到结果后还要继续执行代码。

- 条件是真是假，用 `predicate`，返回 0 到 1 的概率。
- 从几个分类中选择一个，用 `choice`，返回固定选项、各选项概率和置信度。
- 按有序等级评估，用 `score`，返回等级索引的加权平均值。
- 需要写解释、生成任意 JSON 对象或调用工具，继续使用 Responses API。

它解决的是「让模型做一个小判断」的问题，应用本身仍然负责业务规则和后续动作。

## 请求由三部分组成

`POST /v1/decisions` 的请求体很集中：

| 字段        | 作用                                                          |
| ----------- | ------------------------------------------------------------- |
| `model`     | 当前只支持 `gpt-6-luna`                                       |
| `input`     | 所有问题共享的证据，可以是文本、消息历史或带 JSON、图片的内容 |
| `questions` | 要判断的问题，每项包含类型、名称、说明和有限答案              |

每个问题都要有唯一的 `name`。响应中的 `answers` 会带回同一个名称，应用可以按名称取值，不必依赖数组顺序。

### 三种答案怎么选

| 类型        | 适合的判断                   | 主要返回                                                  |
| ----------- | ---------------------------- | --------------------------------------------------------- |
| `predicate` | 是否损坏、是否重复扣款       | `probability`，条件为真的估计概率                         |
| `choice`    | 部门、文档类型、下一步动作   | `choice`、`probabilities`、`confidence`                   |
| `score`     | 严重程度、风险等级、质量档位 | `score`、各级概率、`confidence`；分数可以落在两个等级之间 |

`choice` 适合没有顺序的分类，例如账单、技术和物流。`score` 适合有顺序的等级，例如外观问题、有临时方案、完全阻塞。

评分题的等级从 0 开始编号，数量为 2 到 10 个。它返回的是按概率加权后的平均分，直接拿来做精确阈值可能不合适；更稳妥的做法是把分数和置信度一起看。

## 写一个工单分诊脚本

下面的例子把三个独立问题放进同一次请求：

1. 工单应该交给哪个部门。
2. 是否存在需要优先处理的时间压力。
3. 问题有多严重。

准备 Node.js 22 或更高版本，并设置 API key：

```powershell
$env:OPENAI_API_KEY="你的 API key"
```

保存为 `route-ticket.mjs`：

```js
const ticket = `
客户说三天内被扣款两次，订单号 A-1042。
第一次扣款后页面报错，客户又提交了一次。
现在账户余额不足，客户要求今天处理。
`;

const response = await fetch("https://api.openai.com/v1/decisions", {
  method: "POST",
  headers: {
    Authorization: `Bearer ${process.env.OPENAI_API_KEY}`,
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    model: "gpt-6-luna",
    input: ticket,
    questions: [
      {
        type: "choice",
        name: "department",
        instructions: "Which team should handle this support ticket?",
        choices: [
          {
            value: "billing",
            description: "Payments, invoices, refunds, and duplicate charges.",
          },
          {
            value: "technical",
            description: "Errors while using the product.",
          },
          {
            value: "account",
            description: "Account access and profile issues.",
          },
          {
            value: "other",
            description: "Requests outside the defined categories.",
          },
        ],
      },
      {
        type: "predicate",
        name: "time_sensitive",
        instructions:
          "Does the customer describe a deadline or a problem that needs same-day handling?",
      },
      {
        type: "score",
        name: "severity",
        instructions: "How severe is the impact described in the ticket?",
        levels: [
          {
            label: "cosmetic",
            description: "Only appearance or wording is affected.",
          },
          {
            label: "workaround",
            description: "A task fails, but another path still works.",
          },
          {
            label: "blocked",
            description: "The customer cannot complete the task.",
          },
        ],
      },
    ],
  }),
});

if (!response.ok) {
  throw new Error(`${response.status}: ${await response.text()}`);
}

const { answers } = await response.json();
const byName = new Map(answers.map(answer => [answer.name, answer]));

function typed(name, type) {
  const answer = byName.get(name);
  return answer?.type === type ? answer : null;
}

const department = typed("department", "choice");
const urgent = typed("time_sensitive", "predicate");
const severity = typed("severity", "score");

const route =
  department && department.confidence >= 0.8
    ? department.choice
    : "human_review";
const priority = urgent && urgent.probability >= 0.7 ? "high" : "normal";
const needsReview =
  route === "human_review" || !severity || severity.confidence < 0.6;

console.log(
  JSON.stringify(
    {
      route,
      priority,
      severity: severity?.score ?? null,
      needsReview,
    },
    null,
    2
  )
);
```

运行：

```powershell
node route-ticket.mjs
```

请求成功时，`answers` 中会出现三个同名结果。`choice` 结果包含选中的部门和置信度，`predicate` 结果包含时间敏感的概率，`score` 结果包含严重度分数。

脚本没有把模型结果直接当成最终业务状态。置信度不足、答案类型不符或模型拒绝时，工单会进入 `human_review`。响应中的数值会随输入变化，不能把示例阈值当成通用标准。

## 设计问题比选择类型更重要

### 把判断标准写成可观察的条件

「判断客户是否生气」很难验收，「客户是否明确提出当天处理的期限」更容易检查。问题说明应围绕文本、图片或 JSON 中能找到的证据。

`choice` 的每个选项要有清楚边界。分类无法覆盖所有输入时，加一个 `other`，并让应用把它送进人工队列。模型返回的 `confidence` 也要纳入路由条件。

### 用真实样本定阈值

先收集一批有标注的真实输入，观察不同阈值下的误判分布。漏掉紧急工单和误拦普通工单的代价不同，阈值也应不同。

官方建议从应用中的标注样本出发，根据误报和漏报的成本选择阈值。`predicate` 返回概率，`choice` 和 `score` 返回概率分布及单独置信度，三种结果都值得在接入初期记录。

### 独立问题合并，依赖问题拆开

一次请求最多可以包含 400 个问题。同一份材料上的独立判断，例如「是否有损坏」和「商品属于哪一类」，可以放在同一个 `questions` 数组里。

后一个问题依赖前一个答案时，拆成两次请求。例如先判断照片是否有损坏，再根据结果请求维修分类。这样可以避免一个混乱问题同时承担识别、分类和决策。

## 输入、缓存与限制

`input` 支持文本、消息历史、原生 JSON 和图片。JSON 直接放在 `input_json` 内容块里，不要求先转成字符串。图片可以使用公开 HTTP(S) URL 或 base64 data URL，当前不支持 `file_id`。

共享证据放在 `input`，每个问题独有的图片放在该问题的 `instructions` 中。问题级图片和共享图片共用整个请求的图片限制。

提示缓存适合重复使用的大段参考材料。缓存前缀至少需要 1,024 个 token，问题内容不计入这段前缀。缓存读取和写入都按输入 token 计费，二者次数都包含在 `usage.input_tokens` 中，不要重复相加。

Decisions API 目前只支持 `gpt-6-luna`。美国、欧洲（EEA 与瑞士）支持区域处理；数据驻留覆盖所有受支持的 API 区域。Zero Data Retention 和 HIPAA 仅对符合条件并完成所需协议的客户开放。

## 成本与实时语音

官方公布的价格是：

- 未缓存输入：每百万 token `$0.10`。
- 缓存读取输入：每百万 token `$0.01`。
- 缓存写入：按 `gpt-6-luna` 的提示缓存费率计费。
- 输出 token：不计费。

长上下文乘数和区域处理附加费仍可能适用，报价前应查看当前定价页。

发布页还给出了 Box 的评估：在 30 个保险凭证案例中，路由选择约快 5 倍，准确率与 Responses API 相同，低置信度案例会转给审核人员。这个结果说明接口适合「模型先分诊，人工接住不确定案例」的流程。

实时语音场景可以直接把 Decisions 接进 GPT-Live。比如在 `session.triggers` 中监听用户转写增量，让模型从 `neutral`、`happy`、`sad`、`concerned` 中选一个表情，再根据返回的 `decision.event` 驱动界面动画。

这类用法仍然遵循同一原则：模型只负责在有限选项中做判断，动画和业务动作由应用执行。

## 什么时候继续用 Responses API

以下任务不适合迁到 Decisions：

- 需要一段自然语言解释。
- 需要按自定义 JSON Schema 提取多个字段。
- 需要模型选择并填写工具调用参数。
- 任务本身包含开放式推理，答案无法提前限定。

OpenAI 的开发者指南把这类需求指向 Responses API 的 Structured Outputs 或 function calling。Decisions 的价值来自答案空间足够小，强行用它承载开放式任务会丢失必要信息。

## 下一步

从业务里找出一个每天频繁发生、答案范围固定、错了也有人能复核的判断。先用 Playground 准备一批覆盖典型情况和边界情况的真实样本，定义问题、选项和阈值，再把结果接到现有队列或规则引擎。

上线前重点观察三件事：答案类型是否稳定、低置信度比例是否可接受、人工复核是否能覆盖高风险结果。速度和费用只有在判断值得信任之后才有意义。

如果你正在把模型接进业务流程，Aide Hub 会继续分享 AI 助手、开发工具和软件工程实践，重点写清楚接口边界与失败处理。

## 参考

- [Build more responsive apps with the Decisions API（原文，OpenAI）](https://openai.com/index/decisions-api/)
- [Decisions 开发者指南（OpenAI API）](https://developers.openai.com/api/docs/guides/decisions)
- [Create decision API 参考（字段与响应结构）](https://developers.openai.com/api/reference/resources/decisions/methods/create)
- [OpenAI API 定价](https://developers.openai.com/api/docs/pricing)
- [Prompt caching 指南](https://developers.openai.com/api/docs/guides/prompt-caching)
- [Connect voice to Decisions（GPT-Live 集成）](https://developers.openai.com/api/docs/guides/decisions-voice)
- [Data controls（区域处理、ZDR 与合规边界）](https://developers.openai.com/api/docs/guides/your-data)
