---
pubDatetime: 2026-03-12
title: "Temporal：用九年时间修复 JavaScript 的时间处理"
description: "JavaScript 的 Date API 从 1995 年起就是开发者的痛点，三十年后，Temporal 终于以 TC39 Stage 4 的姿态登场。这篇文章梳理了从 Brendan Eich 的十天冲刺到 ES2026 标准化的完整历程，以及 Bloomberg、Igalia、Google 等多方协作的幕后故事。"
tags: ["JavaScript", "TC39", "Temporal", "ECMAScript", "日期时间"]
slug: "javascript-temporal-nine-year-journey"
ogImage: "../../assets/595/01-cover.png"
source: "https://bloomberg.github.io/js-blog/post/temporal/"
---

![Temporal API 概念图](../../assets/595/01-cover.png)

1995 年，Brendan Eich 用十天写出了 JavaScript 的雏形。`Date` 对象那一部分他甚至没有亲手写——同事 Ken Smith 把 Java 的 `java.util.Date` 直接移植了过来，bug 一并随行。三十年后，这个决定仍然困扰着全球的 JavaScript 开发者。

今年三月，`Temporal` 正式晋级 TC39 Stage 4，纳入 ES2026 规范。这是一段历时九年、横跨微软、Bloomberg、Google、Mozilla、Igalia 多家公司的漫长旅程。

## JavaScript 怎么演进的

JavaScript 没有单一的"所有者"。它运行在所有浏览器里，任何变更都必须经过 [TC39](https://tc39.es/)——即 ECMAScript 技术委员会——的共识流程。提案按成熟度分五个阶段推进：

- **Stage 0**：想法
- **Stage 1**：问题空间被接受
- **Stage 2**：草案设计确定，仍需完善
- **Stage 2.7**：原则上通过，等待测试和反馈
- **Stage 3**：实现与反馈
- **Stage 4**：已标准化

每个阶段的推进都需要多个引擎和浏览器厂商的认可，这也是为什么一个改动从提出到落地往往以年计。

## Date 坏在哪

Brendan Eich 后来承认，当时沿用 Java 的 Date 主要是政治考量：Java 是大哥，JavaScript 是它的轻量伴侣，保持一致是优先级。这在彼时是合理的权衡——Web 还很年轻，应用足够简单。

问题在于，Web 没有停止生长，而 Date 停止了。

**可变性陷阱**

```js
const date = new Date("2026-02-25T00:00:00Z");

function addOneDay(d) {
  // 实际上在原地修改 date，而不是返回新对象
  d.setDate(d.getDate() + 1);
  return d;
}

addOneDay(date);
console.log(date.toISOString());
// "2026-02-26T00:00:00.000Z" —— 原始值已被改变
```

**月份溢出**

```js
const billingDate = new Date("Sat Jan 31 2026");
billingDate.setMonth(billingDate.getMonth() + 1);
// 期望：2 月 28 日
// 实际：3 月 02 日
```

Date 把非法日期静默地滚入下一个月，而不是报错或截断到合法值。

**解析行为不确定**

```js
new Date("2026-06-25 15:15:00").toISOString();
// 可能返回本地时区、UTC 或直接抛出 RangeError
// 取决于浏览器的心情
```

类似 ISO 8601 但不完全符合的字符串，历史上各浏览器行为各不相同，规范对此几乎没有约束。State of JS 调查里，Date 长期稳居开发者"最痛"语言特性排行榜前三。

## 库的时代

社区不得不用库来填坑。Moment.js 在 2011 年横空出世，提供了表达力强的 API、强大的解析能力和不可变性，迅速成为事实标准。之后 date-fns、Luxon 也相继出现，到 2026 年初，这些库加在一起每周下载量超过一亿次。

但库有库的代价。Moment.js 需要把完整的时区数据和本地化数据打包进来，无法通过 tree-shaking 消除——因为你通常不知道用户会用哪个时区。这些多余的字节最终都落在了用户的浏览器里。

Moment.js 的维护者 Maggie Johnson-Pint（当时在微软）用来自一线的疲惫推动了改变：与其一直打补丁，不如从标准层面解决。2017 年，她在 TC39 全体会议上提出了 Temporal 提案，获得热烈响应，当即推进至 Stage 1。

## 团队集结

Stage 1 只是开始，不是终点。早期工作里有大量不光鲜的内容：收集需求、厘清语义、把"生态系统的伤痛"翻译成能真正落地的设计。

Bloomberg 在此过程中扮演了关键角色。公司的 JavaScript 环境横跨彭博终端的多个运行时（Chromium、Node.js、SpiderMonkey），用户和其所投资的金融市场覆盖全球每个时区。时间戳在服务间不停流转，哪怕政府以极短通知更改夏令时规则，系统也必须给出正确答案。

Bloomberg 工程师 Andrew Paprocki 当时正在和 Igalia 讨论让 V8 的时区可配置，Daniel Ehrenberg（Igalia）把他引向了早期的 Temporal 工作——那个方向与 Bloomberg 内部已有的值语义日期时间类型高度吻合。这次交流成了 Bloomberg 的生产需求、Igalia 的浏览器与标准专长，以及 Temporal 演进方向之间的早期桥梁。

Bloomberg 随后与 Igalia 建立了长期合作，包括持续的资金支持，并从内部输送工程师直接推进提案。Philipp Dunkel 成为规范 Champion，Philip Chimento 和 Ujjwal Sharma 作为全职 Champion 加入，为提案提供了它最需要的日常专注度。

Google 的国际化团队通过 Shane Carr 加入，为日历、时区等国际化细节提供了专业支撑。Justin Grant 从 2020 年作为志愿者加入，带来了十年跨三家初创公司处理时间戳数据的真实经验，他的积累帮助团队预判了开发者会犯的错误，并最终促成 `Temporal.ZonedDateTime` 被纳入提案，把夏令时 bug 关进了历史。

## Temporal 今天长什么样

Temporal 是一个顶层命名空间对象（类似 `Math` 或 `Intl`），提供多种具体类型。

### ZonedDateTime

如果不知道该用哪个类型，从 `Temporal.ZonedDateTime` 开始。它是 `Date` 的概念替代品，但移除了所有"地雷"：

```js
// 旧写法
const now = new Date();

// 新写法
const now = Temporal.Now.zonedDateTimeISO();
```

`ZonedDateTime` 携带明确的时区和日历信息，所有操作都是不可变的。夏令时切换时，加减运算会自动处理：

```js
// 伦敦夏令时开始：2026-03-29 01:00 → 02:00
const zdt = Temporal.ZonedDateTime.from(
  "2026-03-29T00:30:00+00:00[Europe/London]",
);

const plus1h = zdt.add({ hours: 1 });
console.log(plus1h.toString());
// "2026-03-29T02:30:00+01:00[Europe/London]"
// 01:30 那个时刻本就不存在，直接跳过
```

### Instant

`Temporal.Instant` 表示一个精确的时间点，没有时区、没有夏令时、没有日历系统——就是从 Unix epoch 开始经过的纳秒数。与 `Date` 类似，但精度从毫秒提升至纳秒，可以直接转换为不同时区的 `ZonedDateTime`：

```js
const instant = Temporal.Instant.from("2026-02-25T15:15:00Z");

instant.toZonedDateTimeISO("Europe/London").toString();
// "2026-02-25T15:15:00+00:00[Europe/London]"

instant.toZonedDateTimeISO("America/New_York").toString();
// "2026-02-25T10:15:00-05:00[America/New_York]"
```

### Plain 系列

`PlainDate`、`PlainTime`、`PlainDateTime`、`PlainYearMonth`、`PlainMonthDay` 是"墙上时钟"类型——不关心时区、不关心夏令时，就是字面上的日期或时间值：

```js
const date = Temporal.PlainDate.from({ year: 2026, month: 3, day: 11 });
date.inLeapYear; // false
date.toString(); // '2026-03-11'
```

这类型的限制即是它的优势：减少了不必要的运算，也减少了踩坑的机会。

### 日历系统

Temporal 原生支持多种日历系统。"加一个月"这个操作，在 Temporal 里是在该日历的规则下执行的：

```js
const today = Temporal.PlainDate.from("2026-03-11[u-ca=hebrew]");
today.toLocaleString("en", { calendar: "hebrew" });
// '22 Adar 5786'

const nextMonth = today.add({ months: 1 });
nextMonth.toLocaleString("en", { calendar: "hebrew" });
// '22 Nisan 5786'
```

用原来的 `Date`，`setMonth` 只会加一个公历月，再用希伯来历显示就会落在错误的日期上。

### Duration

`Temporal.Duration` 可以和其他所有类型配合使用，支持单位转换：

```js
const duration = Temporal.Duration.from({ hours: 130, minutes: 20 });
duration.total({ unit: "second" }); // 469200
```

## 实现：一个不寻常的协作

Temporal 是 ECMAScript 历史上规模最大的单次提案——规格文本甚至超过了整个 ECMA-402（国际化规范）。实现它的挑战不仅在于体量，还在于规格本身一直在演进，各引擎的实现需要不断跟进。

2024 年六月 TC39 全体会议上，Google 国际化团队和 Boa 引擎决定合作开发一个共享实现库，用 Rust 编写，同时服务于两个引擎——这就是 [temporal_rs](https://github.com/boa-dev/temporal)。贡献者来自多个机构，包括卑尔根大学的学生。最终 `temporal_rs` 通过了 100% 的 Test262 测试用例，并已被更多引擎采用。

这在 TC39 历史上几乎没有先例：多个引擎合作开发同一个语言特性的共享底层库。好处是实实在在的：

- 贡献者不需要了解 V8 或 Boa 的内部架构
- 作为独立库，代码审查比在引擎中更容易
- 现代 Rust 工具链（Clippy、Rustfmt）保证了质量
- 长期可维护：有专门的维护团队，而不是分散在各引擎中

Test262 里 Temporal 的测试数量大约 4500 个，对比之下 Date 只有约 594 个，String 约 1208 个。这个数量直观地反映了 Temporal 的复杂度，也说明了这个提案经历了多么严格的验证。

## 现在可以用了吗

今天 Temporal 已经在以下环境可用：

- Firefox v139（2025 年 5 月起）
- Chrome v144（2026 年 1 月起）
- Edge v144（2026 年 1 月起）
- TypeScript 6.0 Beta（2026 年 2 月起）
- Safari（Technology Preview 部分支持）
- Node.js v26（待定）

你不需要等到 ES2026 正式发布——主流浏览器已经支持，开箱即用。

## 还有什么没有解决

Web 生态与 `Date` 深度绑定，`Temporal` 的整合工作还在进行中。

日期选择器（date picker）目前尚无官方集成方案，未来可能通过表单元素属性扩展实现：

```html
<input type="date" />
<!-- element.valueAsPlainDate -->
<input type="time" />
<!-- element.valueAsPlainTime -->
```

`DOMHighResTimeStamp` 的替换也在讨论范围内。比如设置 cookie 过期时间：

```js
cookieStore.set({
  name: "foo",
  value: "bar",
  expires: Temporal.Now.instant().add({ hours: 24 }).epochMilliseconds,
});
```

类似的集成点还有很多，社区会持续推进。

## 九年换来的答案

Temporal 是共识驱动的产物。它不是某家公司推出的框架，而是 TC39、浏览器引擎、独立贡献者一起构建的语言特性。从 Bloomberg 的金融级时区需求，到 Google 的国际化专业知识，到 Igalia 的浏览器实现经验，到志愿者带来的真实踩坑案例——每一块拼图都在。

`temporal_rs` 的成功还说明了另一件事：共享的高质量开源基础设施可以降低成本、提高一致性、加速 Web 生态的整体演进。这个模式值得被记住和复制。

JavaScript 终于有了一个现代的日期时间 API。三十年等待，可以结束了。

## 参考

- [Temporal: The 9-Year Journey to Fix Time in JavaScript](https://bloomberg.github.io/js-blog/post/temporal/) — Jason Williams / Bloomberg JS Blog
- [TC39 Process Document](https://tc39.es/process-document/) — TC39
- [temporal_rs on GitHub](https://github.com/boa-dev/temporal) — Boa Dev
- [Temporal Proposal](https://github.com/tc39/proposal-temporal) — TC39
- [jsdate.wtf](https://jsdate.wtf/) — JavaScript Date 的各种奇葩行为汇总
