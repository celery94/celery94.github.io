# Cover Prompt Template

创建文章封面时，先用这个模板生成**草图 prompt**，必要时再生成**编辑 prompt**，然后调用 `azure-image-gen`。

不要默认“一次生成 = 最终封面”。`gpt-image-2` 更适合先确认概念与构图，再基于已有图继续编辑收敛。

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
- `参考素材策略`：纯文本生成 / 用 1-2 张本地图片做 reference / 先生成再编辑 / 局部遮罩
- `第一轮目标`：这次先验证什么（主题是否成立、主体是否清楚、构图是否稳）
- `第二轮修正点`：如果第一轮出来后要改，优先改哪 1-3 项

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

## 4. `gpt-image-2` 参数默认值

除非文章题材有特殊需要，否则封面优先按这组参数来：

- **草图阶段**
	- `size`: `1504x640`
	- `quality`: `low`
	- `background`: `auto` 或 `opaque`
	- `format`: 追求速度时用 `jpeg` / `webp`；准备马上进入编辑流时优先保留 `png`
- **精修阶段**
	- `size`: `2256x960`
	- `quality`: `medium`
	- 只有复杂结构、材质或光影不够稳定时才升到 `high`
- **统一规则**
	- 宽高比固定 2.35:1
	- `gpt-image-2` 当前不支持透明背景，不要用 `transparent`
	- 不要依赖图中可见文字来表达主题；这个模型虽然比以前更强，但文字排版仍然不是封面成功的关键路径
	- 当前脚本即使传 `--n > 1` 也只保存第一张，所以多方案探索请分多次生成或改走编辑流

## 5. 统一禁令

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

如果第一轮结果里出现了这些元素，优先在第二轮编辑里明确写“remove / no / avoid”，而不是寄希望于模型自己悟出来。

## 6. Prompt 骨架

### 6.1 第一轮：草图生成 prompt

用下面这套结构输出**第一轮草图 prompt**：

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

### 6.2 第二轮：编辑 / 精修 prompt

当第一轮已经有可用方向，但需要修主体、背景、风格、误生成元素时，不要重写一整套世界观，优先把第一张图作为输入图，再用这套结构写**编辑 prompt**：

```text
Use the provided image as the base.
Keep the strongest part of the current composition and preserve the core metaphor: {封面主隐喻}.

Change only these points:
- {第二轮修正点 1}
- {第二轮修正点 2}
- {第二轮修正点 3}

Make the image feel more like {风格方向}. Preserve one clear focal point.
Primary subject should remain: {主视觉主体}, {主体动作}.
Simplify the background so that only {背景元素} remains as supporting context.
Color palette: {色彩限制}. Aspect ratio 2.35:1.

Remove any visible text, title, letters, UI labels, fake screenshots, fake charts, fake terminal output, watermark, prompt residue, unrelated icons, and decorative clutter.
Avoid {禁用元素}.
```

### 6.3 何时用参考图 / 遮罩

- 如果你已经有**允许复用的本地图片**，而且它能明确帮助模型抓住主体关系、空间结构或关键对象，可以把它作为 `--input-image`
- 如果只是局部元素跑偏，例如错误多出一个屏幕、背景里出现了假图表、主物体边上多了无关符号，再考虑 `--mask`
- 如果第一轮主题就不对，不要强行 edit；回到槽位，改“主隐喻 / 主体动作 / 构图方式”至少两项，再重新生成

## 7. 使用要求

- prompt 里必须同时包含“主题”“主体”“动作”“构图”“风格”“禁令”
- 同主题文章不能只替换名词，至少在“主隐喻 / 主体动作 / 构图方式”里改动两项
- 非教程类文章，默认不要画出操作界面截图感
- 非发布类文章，默认不要做成广告横幅
- 架构类文章可以表达“连接关系”，但不要伪造真实系统图
- 研究类文章可以抽象，但不能抽象到完全看不出主题
- 每一轮生成后都要看 `revised_prompt`（如果接口返回了它），确认模型有没有把图往“标题海报、仪表盘、假架构图、截图 UI”方向带偏
- 判断逻辑要固定：
	- **主题不对**：回到槽位重写，再生成
	- **主题对但细节不对**：优先编辑已有图
	- **只有局部出错**：再考虑遮罩
- 不要把“多堆一点风格词”当成唯一优化方式；对 `gpt-image-2` 来说，清楚的主隐喻、主体关系和删减杂物，通常比多加十个形容词更有效

## 8. 示例

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

如果第一轮结果已经有了“工作台 + 插件插入”的主结构，但背景里冒出了假 UI 文本或多余面板，第二轮编辑 prompt 可以写成：

```text
Use the provided image as the base.
Keep the strongest part of the current composition and preserve the core metaphor: two AI coding capabilities connected into one developer workflow on a single workstation.

Change only these points:
- remove all text-like marks and pseudo UI labels
- simplify the background so it reads as supporting context rather than a screenshot
- make the plugin insertion action clearer and more visually decisive

Make the image feel more like editorial technical illustration. Preserve one clear focal point.
Primary subject should remain: a terminal-centric developer workstation with a plugin module, the plugin module sliding into a side slot and lighting up as it connects.
Simplify the background so that only a few command-like motion lines, one simplified tool emblem, and soft interface silhouettes remain as supporting context.
Color palette: charcoal, soft teal, warm orange, off-white. Aspect ratio 2.35:1.

Remove any visible text, title, letters, UI labels, fake screenshots, fake charts, fake terminal output, watermark, prompt residue, unrelated icons, and decorative clutter.
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
