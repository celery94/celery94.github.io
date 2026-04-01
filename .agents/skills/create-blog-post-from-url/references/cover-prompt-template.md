# Cover Prompt Template

创建文章封面时，先用这个模板生成最终 prompt，再调用 `generate-image`。

## 1. 先判断封面类型

只能在下面 5 类里选 1 类，不要自创新分类：

- `tutorial`：教程 / 实操
- `release`：产品更新 / 工具发布
- `architecture`：架构 / 系统设计 / 工作流
- `analysis`：观点 / 评论 / 趋势判断
- `research`：论文 / 算法 / 技术原理解读

如果拿不准：

- 明显在教人操作、配置、排错：用 `tutorial`
- 明显在介绍一个新工具、新能力、新发布：用 `release`
- 明显在讲系统关系、模块协作、agent/workflow 结构：用 `architecture`
- 明显在做判断、比较、批评、趋势分析：用 `analysis`
- 明显在拆机制、模型、算法、论文结论：用 `research`

## 2. 先填这几个槽位

生成 prompt 前先写出这些信息，不要跳过：

- `文章标题`：中文标题
- `文章类型`：上面的 5 选 1
- `核心主题`：这篇文章到底在讲什么
- `读者收获`：读完之后能理解什么或做成什么
- `封面主隐喻`：用什么视觉隐喻表达主题
- `主视觉主体`：画面里最重要的 1 个主体
- `主体动作`：主体正在做什么，或处于什么关系里
- `构图方式`：居中主物体 / 左右对照 / 斜向推进 / 等距空间 / 单点聚焦
- `背景元素`：只保留 1-3 个辅助元素
- `风格方向`：按下方决策表填写
- `色彩限制`：2-4 个主色，不要彩虹拼盘
- `禁用元素`：和主题无关、但模型容易乱加的东西

## 3. 类型到风格的固定映射

按这个表直接选，不要重新发明风格。

| 类型 | 默认风格 | 主体规则 | 构图规则 | 气质 |
|---|---|---|---|---|
| `tutorial` | editorial technical illustration | 一个主工具 + 一个明确动作 | 单点聚焦或轻微斜向推进 | 清晰、可执行、不过度戏剧化 |
| `release` | product-poster style illustration | 一个主产品或主符号 | 居中主物体 + 少量辅助符号 | 新鲜、克制、有登场感 |
| `architecture` | isometric conceptual systems scene | 2-4 个模块化实体 | 等距空间或层级式关系 | 理性、结构化、非真实图表 |
| `analysis` | conceptual editorial illustration | 一个核心冲突或对照关系 | 左右对照、拉扯或边界式构图 | 有判断力，但不煽情 |
| `research` | abstract technical concept art | 一个机制或结构主意象 | 单点主结构 + 少量流动辅助线索 | 精确、克制、少人物 |

额外规则：

- 不要默认写 `pixel-art` 或 `anime`
- 只有文章天然适合时，才允许显式加入这类风格词
- 如果用了像素风或动漫感，也要先满足“主隐喻清楚、主体明确、构图简洁”

## 4. 统一禁令

每个 prompt 都必须明确包含下面这些限制：

- no text
- no title
- no watermark
- no prompt residue
- no UI screenshot
- no dashboard
- no fake diagram labels
- no fake terminal output
- no collage of unrelated icons
- no decorative clutter

默认还要避免这些常见废元素：

- 漂浮芯片
- 无意义代码雨
- 霓虹高楼背景
- 通用机器人站姿
- 赛博朋克紫蓝光污染
- 巨量 HUD 浮层

## 5. Prompt 骨架

用下面这套结构输出最终 prompt：

```text
Create a wide cinematic cover illustration for a Chinese tech blog article.
Theme: {核心主题}. The reader should quickly feel {读者收获}.

Main metaphor: {封面主隐喻}.
Primary subject: {主视觉主体}, {主体动作}.
Composition: {构图方式}. Keep one clear focal point and use {背景元素} only as supporting context.

Style: {风格方向}. Stylized, polished, editorial, visually strong, suitable for a modern engineering article cover.
Color palette: {色彩限制}.
Aspect ratio 2.35:1.

Do not include any visible text, title, letters, UI labels, prompt residue, watermark, screenshots, dashboards, fake diagrams, fake terminal output, unrelated icons, or decorative clutter.
Avoid {禁用元素}.
```

## 6. 使用要求

- prompt 里必须同时包含“主题”“主体”“动作”“构图”“风格”“禁令”
- 同主题文章不能只替换名词，至少在“主隐喻 / 主体动作 / 构图方式”里改动两项
- 非教程类文章，默认不要画出操作界面截图感
- 非发布类文章，默认不要做成广告横幅
- 架构类文章可以表达“连接关系”，但不要伪造真实系统图
- 研究类文章可以抽象，但不能抽象到完全看不出主题

## 7. 示例

### 示例 1：教程类

输入槽位：

- `文章标题`：在 Claude Code 里直接调用 OpenAI Codex：codex-plugin-cc 上手指南
- `文章类型`：`tutorial`
- `核心主题`：在 Claude Code 中安装和使用 OpenAI Codex 插件
- `读者收获`：快速理解安装流程和核心命令
- `封面主隐喻`：一个开发者工作台上，两套 AI 工具能力被接到同一条操作链路里
- `主视觉主体`：终端工作台与插件模块
- `主体动作`：插件模块正在插入工作台侧边槽位并点亮
- `构图方式`：单点聚焦，略微斜向推进
- `背景元素`：少量命令流线、一个简化工具徽记、柔和界面轮廓
- `风格方向`：editorial technical illustration
- `色彩限制`：charcoal, soft teal, warm orange, off-white
- `禁用元素`：floating robots, neon city, dense code rain

输出 prompt：

```text
Create a wide cinematic cover illustration for a Chinese tech blog article.
Theme: installing and using an OpenAI Codex plugin inside Claude Code. The reader should quickly feel that this is a practical hands-on workflow they can follow immediately.

Main metaphor: two AI coding capabilities connected into one developer workflow on a single workstation.
Primary subject: a terminal-centric developer workstation with a plugin module, the plugin module sliding into a side slot and lighting up as it connects.
Composition: single focal point with a slight diagonal forward motion. Keep one clear focal point and use a few command-like motion lines, one simplified tool emblem, and soft interface silhouettes only as supporting context.

Style: editorial technical illustration. Stylized, polished, editorial, visually strong, suitable for a modern engineering article cover.
Color palette: charcoal, soft teal, warm orange, off-white.
Aspect ratio 2.35:1.

Do not include any visible text, title, letters, UI labels, prompt residue, watermark, screenshots, dashboards, fake diagrams, fake terminal output, unrelated icons, or decorative clutter.
Avoid floating robots, neon city, dense code rain.
```

### 示例 2：架构 / 工作流类

输入槽位：

- `文章标题`：用 GitHub Copilot SDK 在 C# 中构建多智能体代码分析系统
- `文章类型`：`architecture`
- `核心主题`：多个专职 agent 组成顺序执行的代码分析流水线
- `读者收获`：理解多 agent 如何分工协作并汇总结果
- `封面主隐喻`：一个模块化分析工厂，多个处理单元串联成流水线
- `主视觉主体`：三个分析节点与一个汇总节点
- `主体动作`：代码片段从左到右流经节点后汇总成报告
- `构图方式`：等距空间，左到右层级推进
- `背景元素`：少量连接线、结果卡片轮廓、简化数据流光带
- `风格方向`：isometric conceptual systems scene
- `色彩限制`：deep navy, steel blue, amber, pale cyan
- `禁用元素`：real dashboards, fake charts, hologram overload

输出 prompt：

```text
Create a wide cinematic cover illustration for a Chinese tech blog article.
Theme: a sequential multi-agent code analysis pipeline built with GitHub Copilot SDK in C#. The reader should quickly feel how separate agents collaborate and merge their outputs into one report.

Main metaphor: a modular analysis factory where specialized processing units form one clear pipeline.
Primary subject: three distinct analysis nodes and one final synthesis node, with code fragments flowing through them from left to right and becoming a finished report.
Composition: isometric scene with left-to-right staged progression. Keep one clear focal point and use thin connection lines, report-card silhouettes, and a restrained data-flow light band only as supporting context.

Style: isometric conceptual systems scene. Stylized, polished, editorial, visually strong, suitable for a modern engineering article cover.
Color palette: deep navy, steel blue, amber, pale cyan.
Aspect ratio 2.35:1.

Do not include any visible text, title, letters, UI labels, prompt residue, watermark, screenshots, dashboards, fake diagrams, fake terminal output, unrelated icons, or decorative clutter.
Avoid real dashboards, fake charts, hologram overload.
```

### 示例 3：观点 / 分析类

输入槽位：

- `文章标题`：GitHub Spec Kit：用规格说明驱动 AI 编程的开源工具包
- `文章类型`：`analysis`
- `核心主题`：用结构化规格约束 AI 编程过程，减少纯 prompt 驱动的混乱
- `读者收获`：理解为什么 specification 比临时 prompt 更能稳定驱动实现
- `封面主隐喻`：一张清晰蓝图正在压住四散的草稿和碎片指令
- `主视觉主体`：中央规格蓝图与周围散乱草稿
- `主体动作`：蓝图向外施加秩序，把碎片收束成清晰路径
- `构图方式`：中心主物体，四周轻微对照与收拢
- `背景元素`：少量草稿纸边缘、路径线、被整理的碎片卡片
- `风格方向`：conceptual editorial illustration
- `色彩限制`：ink black, paper white, muted blue, restrained coral
- `禁用元素`：robot mascots, floating code blocks everywhere, poster slogans

输出 prompt：

```text
Create a wide cinematic cover illustration for a Chinese tech blog article.
Theme: structured specifications bringing order to AI coding workflows that would otherwise drift under pure prompt-driven development. The reader should quickly feel that clear specs create control, alignment, and execution stability.

Main metaphor: a precise blueprint pressing down on scattered drafts and fragmented instructions, forcing them into an ordered path.
Primary subject: a central specification blueprint surrounded by loose sketch pages and fragmented instruction cards, the blueprint imposing structure outward.
Composition: centered main object with restrained surrounding contrast and inward convergence. Keep one clear focal point and use a few paper edges, path lines, and partially organized fragment cards only as supporting context.

Style: conceptual editorial illustration. Stylized, polished, editorial, visually strong, suitable for a modern engineering article cover.
Color palette: ink black, paper white, muted blue, restrained coral.
Aspect ratio 2.35:1.

Do not include any visible text, title, letters, UI labels, prompt residue, watermark, screenshots, dashboards, fake diagrams, fake terminal output, unrelated icons, or decorative clutter.
Avoid robot mascots, floating code blocks everywhere, poster slogans.
```
