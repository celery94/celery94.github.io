---
pubDatetime: 2026-08-26T19:19:00+08:00
title: "OpenWiki 的自我纠错记忆：让 Agent 知道何时遗忘"
description: "长线 Agent 记忆的难点不只在召回，还在源代码变化后发现旧知识。本文拆解 OpenWiki 如何用 claim、证据版本和 stale 标记做定向修正，解读 0.4.0、OKF v0.2 与评估结果的真实边界。"
tags: ["AI Agent", "Agent Memory", "OpenWiki", "知识工程"]
slug: "openwiki-self-correcting-memory"
ogImage: "../../assets/1026/01-cover.png"
source: "https://x.com/colifran_/status/2092280107033616451"
---

一个长期运行的 Agent，迟早会遇到同一个问题：它记住的内容，后来还是真的吗？

聊天记录可以按时间保存，向量库也能持续增加文档。可当代码、配置和产品行为发生变化时，旧知识仍然能够被成功召回。此时，召回率越高，错误信息被再次使用的机会也越高。

OpenWiki 的新 Claims 设计把问题往前推进了一步：每条重要知识都保留它所依据的源代码证据，以及观察这份证据时的版本。源代码变化后，系统先标出需要复核的 claim，再让更新流程决定保留、改写或撤回。

这套设计值得借鉴的地方，是它把“记忆”拆成了三个可检查的问题：系统相信什么？依据是什么？依据发生变化后，哪些内容需要重新确认？

## 先看结论：记忆需要证据和过期状态

长线记忆通常包含两个动作：写入和检索。写入解决“把什么保存下来”，检索解决“当前问题该取出什么”。对于会持续变化的代码库，这两个动作还缺少一个时间维度：被保存的知识什么时候失去可信度？

OpenWiki 的处理方式可以概括为：

1. 把页面中的重要事实拆成独立的 claim。
2. 为 claim 记录具体的代码证据和证据版本。
3. 更新前比较保存的证据版本与当前源代码版本。
4. 发现差异后，把 claim 标记为 stale，交给页面更新流程复核。
5. 复核结果仍然成立就刷新证据版本；事实改变就同步改写页面与证据；无法确认的内容继续保持未解决状态。

这里的 stale 不是“已经证实错误”。它表示“原来的证据已经变化，当前内容需要重新检查”。把这种不确定性保存下来，比悄悄继续使用旧内容更安全。

## 一条知识要同时保存 claim 和 evidence

以“某个失败任务默认重试 3 次”为例，普通 Markdown 可能只保存一句结论。OpenWiki 的 Claims 设计还会记录：

| 部分             | 记录内容                          |
| ---------------- | --------------------------------- |
| Claim            | 失败任务默认重试 3 次             |
| Evidence         | 支持这句话的具体源代码位置        |
| Evidence version | 建立这条 claim 时观察到的代码版本 |
| Owning page      | 承载这条事实的 wiki 页面          |

这样，页面是否最近生成就不再是唯一线索。页面两天前生成，却引用了刚刚改动的函数，相关 claim 仍然应该进入复核队列；页面很久没有整体重生成，但它引用的代码没有变化，已有证据仍然具备可检查的依据。

当前 OpenWiki 仓库 README 给出的证据示例使用了类似 `repo://src/server.ts#L40-L82` 的定位方式。具体格式可以随着工具版本调整，设计重点在于让事实与可复核的源代码范围建立稳定关联。

结构化 Claims 存放在 `openwiki/.claims/`，Markdown 继续保持适合人阅读的页面形态。这样做有两个实际好处：代码评审可以检查证据变化，Agent 也能在读页面时看到哪些内容需要重新确认。

## 过期检测要早于“是否有变化”的判断

一个容易遗漏的细节是检查顺序。OpenWiki 会在更新开始时检查已经保存的证据版本，随后才判断这次仓库更新是否属于 no-op。

可以用下面的伪代码理解核心逻辑：

```text
for claim in persisted_claims:
    if evidence_version(claim) != current_source_version(claim):
        mark_stale(claim)

if changed_source_or_stale_claims:
    update_owning_pages()
else:
    finish_as_noop()
```

这段代码是设计意图的简化表达，不能当作 OpenWiki 的公开 API。它揭示了一个重要边界：仓库没有新增普通文档变化，并不代表所有知识都可以直接跳过。只要某条证据已经漂移，它所属的页面就需要获得一次复核机会。

OpenWiki README 还说明，干净的 no-op 更新不会重新调用模型，也不会改写 wiki 内容，只会记录这次检查。这个行为能减少文档噪声，也让“检查过但没有需要修正的内容”和“根本没有检查”得到区分。

## 定向修正比整库重生成更适合长期运行

发现 stale 之后，流程不需要把整个 wiki 从头写一遍。它可以沿着 claim 到页面的关联，只处理受影响的页面：

- 原 claim 仍然成立：保留 claim 身份，更新证据版本。
- 事实细节发生变化：更新原 claim 及其页面内容。
- 原事实已经不再存在：撤回对应 claim。
- 当前证据无法确认：保留未解决状态，避免把猜测写成新事实。

OpenWiki 当前 README 对页面提交也给出了更严格的约束：页面工作者提交完整的现有 claim 集。未变化的 claim 保留 ID，修订后的 claim 原位更新，新事实获得新 ID，被省略的 claim 则代表撤回。完成页面后，系统持久化 Claims、同步 sidecar 的页面版本，再做一次完整结果检查。

这套约束解决了“更新时只看新增内容”的漏洞。若 Agent 只补充新段落，却忘记处理旧 claim，页面表面上变得更丰富，事实集合却可能继续携带过期内容。

## 评估的重点：系统能否承认自己不确定

帖文介绍了一种基于 Git 历史的回放评估：把一个代码仓库按提交或检查点重新播放，在功能增加、行为改变、修复和回滚之间观察 wiki claim 的状态。每条 claim 被分到四类：

| 状态         | 含义                           |
| ------------ | ------------------------------ |
| Supported    | 当前证据支持这条事实           |
| Stale        | 原有证据发生变化，尚未完成复核 |
| Hallucinated | 找不到代码证据支持这条事实     |
| Unverified   | 暂时无法完成确认               |

在帖文给出的对照结果中，加入 Claims runtime 后，stale claims 从 80 条降到 9 条，hallucinated claims 从 15 条降到 0 条。另一个示例中，某个检查点有 17% 的 wiki claim 处于 stale；下一检查点完成复核后，stale 降到 0%，Supported 从 77% 上升到 98%。

这些数字属于作者在帖文中展示的评估结果，文章没有把它们当作独立复现实验。阅读时应关注它们说明的能力边界：系统减少了无证据事实，也缩短了发现过期知识到完成复核之间的距离。它们没有证明任何记忆系统可以自动保证事实永远正确。

对自己的 Agent 记忆做类似评估时，可以先建立一套小而明确的分类：

1. 选择一段有真实 Git 历史的代码库。
2. 在多个提交点生成或维护知识页。
3. 刻意加入函数改名、默认值变化、错误处理调整和回滚。
4. 对每个时间点的 claim 回查源代码证据。
5. 统计支持、过期、无证据和未确认的数量，并记录修正耗时。

这样测到的是“记忆会不会随源变化而自我修正”，评估目标比单次问答准确率更贴近长期运行场景。

## OKF v0.2 负责让结果更容易携带

Claims 解决的是 OpenWiki 内部的事实维护。为了让 wiki 能被其他工具读取，OpenWiki 还输出 Google Open Knowledge Format，也就是 OKF。

当前 GitHub README 和 `v0.4.0` release 信息显示，OpenWiki 输出 OKF v0.2 bundle，包含以下值得注意的元数据：

- 每个概念文档拥有 YAML front matter 和非空 `type`。
- `generated` 记录生成者与时间，保留生产来源。
- repository 页面把 Claims 的证据投影到 `sources`。
- `verified` 只在完整 claim 集完成协调、证据复查并持久化后写入。
- 根索引声明 `okf_version: "0.2"`。
- `status`、`stale_after` 等信任与生命周期字段按需使用。

这里需要留意版本证据的时间差：LangChain 的 OpenWiki 概览页目前仍写着 OKF v0.1，当前仓库 README、package 版本和 v0.4.0 release 则已经指向 OKF v0.2。使用 OpenWiki 时，应以具体安装版本和仓库中的输出为准，并把文档页的旧文案视为待更新信息。

这种差异本身也说明了本文讨论的主题：版本号是一条会变化的事实，引用它时需要带上来源和观察时间。

## 现在如何试用

OpenWiki 官方概览页给出的基本流程很短：

```bash
npm install -g openwiki
openwiki --init
openwiki --update
```

首次初始化会让用户选择模型提供方、密钥和模型，并把代码 wiki 写入当前仓库的 `openwiki/`。在代码模式下，工具还会维护仓库根目录的 `AGENTS.md` 和 `CLAUDE.md` 指针，让编码 Agent 先阅读生成的 wiki。

X 帖文建议尝试 OpenWiki 0.4.0，并提到升级后下一次更新会生成 Claims、迁移到 OKF v0.2。实际使用时可以先检查生成的 Markdown、`openwiki/.claims/` sidecar 和根索引，再把它接入自动更新流水线。对于生产仓库，建议把证据变化和页面修正一起纳入代码评审。

## 这套设计仍然留下了哪些问题

Claims 能让系统知道“这条知识需要复核”，它无法替 Agent 完成所有事实判断。至少有四个问题仍值得单独处理：

1. **证据定位是否稳定。** 行号会随着插入和删除变化，工具需要处理文件移动、代码重排和符号替换。
2. **证据是否足够。** 某个函数片段可能支持默认值，却无法说明调用链上的异常分支。claim 的范围和粒度需要保持适中。
3. **复核是否真的完整。** 只有部分 claim 被重新检查时，页面不能轻易获得完整的 `verified` 状态。
4. **变更是否会产生副作用。** 自动改写 wiki 的影响相对可控，但错误的知识仍可能影响后续 Agent 的代码修改，因此证据、diff 和审计记录都应可见。

因此，“会遗忘”并不等于自动删除历史。更准确的含义是：系统能保留旧信念的来历，在依据变化后降低它的可信度，并要求下一次使用前完成检查。

## 结论：让记忆记录“为什么相信”

对代码库型 Agent 来说，最有价值的记忆结构可以写成一句话：

> 记住结论，也记住证据；保存证据版本，也保存尚未解决的不确定性。

OpenWiki 的 Claims runtime 把这句话变成了一条维护流程：源代码变化触发证据检查，stale claim 进入定向复核，页面与结构化 sidecar 一起更新，完整结果经过验证后再被标记为可信。

如果你正在设计自己的 Agent memory，可以先从四个字段开始：`claim`、`evidence`、`evidence_version`、`status`。接着用 Git 回放测试“事实改变、事实消失、证据无法确认、代码回滚”四种情况。记忆系统真正成熟的标志，不在于它保存了多少内容，而在于它能否及时指出哪些内容已经不该直接相信。

## 参考

- [Colin Francis：Building Self-Correcting Memory in OpenWiki（原帖）](https://x.com/colifran_/status/2092280107033616451)
- [LangChain OpenWiki 概览](https://docs.langchain.com/oss/openwiki/overview)
- [OpenWiki GitHub 仓库 README](https://github.com/langchain-ai/openwiki)
- [OpenWiki v0.4.0 release](https://github.com/langchain-ai/openwiki/releases/tag/v0.4.0)
- [Google Open Knowledge Format 规范](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md)
