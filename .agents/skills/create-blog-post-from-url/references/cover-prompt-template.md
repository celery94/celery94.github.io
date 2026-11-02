# 封面与正文插图模板

## 目录

- [判断封面类型](#1-先判断封面类型)
- [保存封面 brief](#2-先保存封面-brief)
- [基础风格](#3-类型到基础风格的固定映射)
- [默认 HD-2D 风格](#4-默认-hd-2d-风格)
- [生图与提示词](#6-选择生图技能)
- [封面验收与示例](#9-封面使用要求)
- [正文插图](#11-正文插图)

创建文章封面或正文插图时读取本模板。封面先生成**封面 brief**和第一轮 prompt，再选择可用的图像生成 / 编辑技能执行。默认不要在这里预设某个固定 backend；只有用户明确要求 Azure 时才点名 `azure-image-gen`。

不要默认“一次生成 = 最终封面”。先确认主题、摘要弧线、主体、构图和选定视觉风格是否成立，再根据问题做一次定向编辑或重生。

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

## 2. 先保存封面 brief

生成 prompt 前先写出这些信息，并保存到 `src/assets/{ID}/cover-brief.json`。不要跳过 brief 直接写 prompt。

```json
{
  "article_title": "中文标题",
  "cover_type": "tutorial | release | architecture | analysis | research",
  "core_theme": "这篇文章到底在讲什么",
  "reader_takeaway": "读完之后能理解什么或做成什么",
  "summary_angle": "这张封面要用什么主结论或主反差讲文章",
  "narrative_flow": "before-after | 3-beat process | conflict-to-resolution | layered reveal",
  "information_blocks": [
    {
      "role": "problem | mechanism | evidence | step | contrast | takeaway",
      "source_anchor": "对应原文段落、事实或章节",
      "visual_idea": "这一块在画面里如何表达",
      "visible_label": "可选；<= 6 个汉字，或 1 个必要的产品/模型名",
      "numeric_fact": "可选；只能使用原文真实数字、比例、年份，或序号 1/2/3"
    }
  ],
  "main_metaphor": "用什么视觉隐喻表达主题",
  "primary_subject": "画面里最重要的 1 个主体",
  "subject_action": "主体正在做什么，或处于什么关系里",
  "composition": "居中主物体 / 左右对照 / 斜向推进 / 等距空间 / 单点聚焦",
  "base_style": "按类型映射表填写",
  "selected_style": "HD-2D",
  "selected_style_prompt_descriptor": "crisp pixel-art edges, 2D pixel-art subjects integrated into a three-dimensional miniature diorama, layered spatial depth, soft cinematic lighting, subtle atmospheric light, moderate depth of field, readable subjects and relationships, consistent pixel scale, no excessive blur",
  "selected_style_reason": "采用仓库默认 HD-2D 风格；用户当次指定其他风格时记录要求",
  "style_safety_note": "如果风格名强指向品牌、工作室、作者或在世艺术家，说明已改写为非仿冒描述",
  "allowed_visible_text": ["默认 1-3 个中文短标签或数字；确有必要时最多 4 个"],
  "color_palette": ["2-4 个主色"],
  "avoid": ["和主题无关、但模型容易乱加的东西"],
  "reference_strategy": "纯文本生成 / 使用 1-2 张允许复用的本地参考图 / 编辑上一轮结果",
  "draft_goal": "第一轮先验证什么",
  "revision_targets": ["如果第一轮要改，优先改哪 1-3 项"],
  "final_prompt": "最终用于生图的 prompt"
}
```

补充要求：

- `final_prompt` 为必填字段，不能留空；在生图 prompt 定稿后回填（可先写完 brief 其余字段再补），校验脚本会拒绝空值
- `information_blocks` 默认 `2-4` 个；宽封面不要超过 `4` 个
- 每个信息块都必须能映射回原文锚点；不能编造指标、节点名或结论
- 如果文章需要 `5+` 个点才能讲清，先压缩叙事弧线，再写 prompt
- 宽封面必须保留 `1` 个主焦点；其余信息块只承担摘要叙事，不把画面做成长图海报

## 3. 类型到基础风格的固定映射

按这个表确定主体、动作和构图；`base_style` 与下节的 HD-2D 描述共同使用，保持像素质感与三维空间层次。

| 类型 | 基础风格 | 主体规则 | 构图规则 | 气质 |
|---|---|---|---|---|
| `tutorial` | editorial technical illustration | 一个主工具 + 一个明确动作 | 单点聚焦或轻微斜向推进 | 清晰、可执行、不过度戏剧化 |
| `release` | product-poster style illustration | 一个主产品或主符号 | 居中主物体 + 少量辅助符号 | 新鲜、克制、有登场感 |
| `architecture` | isometric conceptual systems scene | 2-4 个模块化实体 | 等距空间或层级式关系 | 理性、结构化、非真实图表 |
| `analysis` | conceptual editorial illustration | 一个核心冲突或对照关系 | 左右对照、拉扯或边界式构图 | 有判断力，但不煽情 |
| `research` | abstract technical concept art | 一个机制或结构主意象 | 单点主结构 + 少量流动辅助线索 | 精确、克制、少人物 |

## 4. 默认 HD-2D 风格

新封面和新增正文插图默认统一使用 HD-2D。保留清晰的像素边缘，将二维像素主体放入有纵深的三维微缩场景，使用柔和光影和适度景深。主体、关系与必要标签必须清楚，避免过度虚化。

`selected_style` 默认填写 `HD-2D`，`selected_style_prompt_descriptor` 使用以下描述，按篇章内容调整场景与配色：

```text
crisp pixel-art edges, 2D pixel-art subjects integrated into a three-dimensional miniature diorama, layered spatial depth, soft cinematic lighting, subtle atmospheric light, moderate depth of field, readable subjects and relationships, consistent pixel scale, no excessive blur
```

`selected_style_reason` 说明采用仓库默认风格；`style_safety_note` 说明以像素、微缩空间和光影特征描述，不复刻具体游戏场景、角色或素材。不要只在 prompt 中写一个风格名称。

## 5. 风格使用规则

- 在写 brief 前确定风格；用户当次明确指定其他风格时遵从要求，并将名称、描述词和理由写入现有字段。
- 用户未限定具体图片时，同篇生成图片使用同一风格；只指定封面或某张图片时，覆盖仅作用于指定图片，其余仍用默认 HD-2D。
- 保留 `cover-brief.json` 现有字段，历史文章与 brief 无需迁移，校验器继续接受历史风格。
- 视觉风格只影响生成图片，不改变正文语气、结构或事实表达，也不改绘真实截图与技术图。
- 封面 prompt 同时包含 `base_style` 与 `selected_style_prompt_descriptor`，按文章类型表达内容，保持选定的视觉特征。
- 强指向品牌、工作室、作者或在世艺术家的名称只记录在 `selected_style`；最终 prompt 使用非仿冒的描述词。
- 优先保证摘要清楚、主体明确、信息可读，避免堆砌风格词。
- `architecture` 与 `research` 可用分镜和局部说明，但不能伪造真实系统图、仪表盘或论文图表。

## 6. 选择生图技能

- 默认保持 backend-agnostic：根据当前环境里**可用**的图像生成 / 编辑技能完成封面和正文插图，不要把模板写死到某一个特定生成器
- 封面默认是宽图，prompt 里写明 `wide cover illustration, aspect ratio 2.35:1`
- 如果所选工具先把图片输出到临时目录、默认目录或中间路径，最终选中后将封面移动或复制到 `src/assets/{ID}/01-cover.{ext}`；正文插图按第 11 节命名保存
- 不要让 `ogImage`、正文图片引用或微信封面引用继续指向临时生成目录
- 如果第一轮主题对但细节有问题，优先编辑或定向重生一次；每轮只改 1-3 个明确问题
- 如果第一轮主题就不对，回到 brief，至少改“摘要角度 / 主隐喻 / 构图方式”中的两项后重新生成
- 如果用户明确要求 Azure / `azure-image-gen` / Azure OpenAI，必须尊重该要求

仅在使用 `azure-image-gen` 时，参考这些参数：

- 封面草图阶段：`size 1504x640`，`quality low`
- 封面终稿阶段：`size 2256x960`，`quality medium`
- 正文插图：选用工具支持的 16:9 尺寸，例如 `size 1536x864`，`quality medium`；跳过脚本默认的封面后处理（`--skip-post-process`），避免正文图被缩到封面宽度
- `background` 只用 `auto` 或 `opaque`
- 当前脚本即使传 `--n > 1` 也只保存第一张，所以多方案探索要分多次生成或改走编辑流

## 7. 允许信息与统一禁令

每个图片生成 prompt 都必须同时说明**允许什么**和**禁止什么**。下述文字数量与信息块要求用于封面；正文插图的文字规则见第 11 节，两者共用第 7.2 节禁令。

### 7.1 允许的可见信息

- 默认最多 `1-3` 个中文短标签 / 数字 chip，确有必要时最多 `4` 个，全部来自 `information_blocks`
- 每个标签默认 `<= 6` 个汉字；或 `1` 个必要的产品 / 模型名
- 允许 `1/2/3`、`①②③`、原文真实数字、比例、年份
- 允许箭头、panel gutter、编号贴片、callout chip、轻量对照框

### 7.2 仍然禁止的内容

- poster title / hero slogan / 长段说明文字
- 英文口号、拟声词、无关 SFX、整句英文标签
- watermark
- prompt residue
- UI screenshot
- dashboard
- fake diagram labels
- fake chart axes / legends
- fake terminal output
- fake architecture node names
- fabricated metrics or percentages
- collage of unrelated icons
- decorative clutter

默认还要避免这些常见废元素：

- 漂浮芯片
- 无意义代码雨
- 霓虹高楼背景
- 通用机器人站姿
- 赛博朋克紫蓝光污染
- 巨量 HUD 浮层

如果第一轮结果里出现这些元素，优先在第二轮 prompt 里明确写 `remove / no / avoid`，不要寄希望于模型自己悟出来。

## 8. Prompt 骨架

### 8.1 第一轮：草图生成 prompt

用下面这套结构输出**第一轮草图 prompt**：

```text
Use case: infographic-story
Asset type: wide cover infographic illustration for a Chinese tech blog article
Primary request: Create a wide cinematic infographic-story cover illustration that summarizes the article. Theme: {核心主题}. The reader should quickly feel {读者收获}.

Summary angle: {摘要角度}.
Narrative flow: {叙事弧线}. In a 2.35:1 frame, keep one dominant focal subject and 2-4 supporting narrative beats. Each beat must map to the article's information blocks rather than generic decoration.
Information blocks:
- {信息块 1：role + source-grounded summary + visible label + numeric fact}
- {信息块 2：role + source-grounded summary + visible label + numeric fact}
- {信息块 3：可选}
- {信息块 4：可选}

Main metaphor: {封面主隐喻}.
Subject: {主视觉主体}, {主体动作}.
Composition/framing: {构图方式}. Prefer horizontal or radial storytelling that stays legible in a wide cover.
Style/medium: combine {基础风格} with the selected visual style descriptor: {selected_style_prompt_descriptor}. Stylized, polished, editorial, visually strong, and clearly readable as an infographic-style summary cover. Do not imitate a specific brand, studio, or living artist.
Color palette: {色彩限制}.
Visible text policy: allow only 1-3 short Chinese labels or number chips by default, and no more than 4 when strictly necessary, all sourced from the information blocks. Each label <= 6 Chinese characters or one required product/model name. No poster title, no long sentences, no English slogans, no fake UI labels, no fake chart axes, no fake architecture node names.
Constraints: no watermark, no prompt residue, no screenshots, no dashboards, no fake diagrams, no fake charts, no fake terminal output, no fabricated metrics, no unrelated icon collage, no decorative clutter.
Avoid: {禁用元素}.
```

### 8.2 第二轮：编辑 / 精修 prompt

当第一轮已经有可用方向，但需要修主体、背景、风格、误生成元素时，优先用这套结构写**编辑或定向重生 prompt**：

```text
Use the current cover direction as the base.
Keep the strongest part of the composition and preserve the summary angle: {摘要角度}.
Preserve the core metaphor: {封面主隐喻}.

Keep these information beats readable and source-grounded:
- {信息块 1}
- {信息块 2}
- {信息块 3：可选}

Change only these points:
- {第二轮修正点 1}
- {第二轮修正点 2}
- {第二轮修正点 3}

Make the image feel more like {基础风格} combined with this selected visual style descriptor: {selected_style_prompt_descriptor}. Preserve one clear focal subject and 2-4 supporting narrative beats in a wide 2.35:1 frame. Do not imitate a specific brand, studio, or living artist.
Primary subject should remain: {主视觉主体}, {主体动作}.
Simplify the background so that only {背景元素} remains as supporting context.
Color palette: {色彩限制}.

Visible text policy: keep only the approved 1-3 short Chinese labels or number chips from the brief, and never exceed 4 items. No poster title, no long sentence captions, no English slogans, no fake UI labels, no fake chart axes, and no fake architecture node names.
Remove any watermark, prompt residue, screenshots, dashboards, fake diagrams, fake charts, fake terminal output, fabricated metrics, unrelated icons, and decorative clutter.
Avoid {禁用元素}.
```

### 8.3 何时用参考图

- 如果已经有**允许复用的本地图片**，而且它能明确帮助模型抓住主体关系、空间结构或关键对象，可以把它作为参考图
- 第三方版权海报、品牌 KV、原站营销插画、需要精确复刻的产品界面不能作为像素级临摹对象
- 如果参考图只是原网页截图，要防止最终图看起来像“网页截图换滤镜”
- 如果第一轮主题就不对，不要强行编辑；回到 brief 重写

## 9. 封面使用要求

- prompt 里必须同时包含“主题”“摘要角度”“信息块”“主体”“动作”“构图”“基础风格”“selected_style_prompt_descriptor”“禁令”
- 宽封面必须保持 `1` 个主焦点 + `2-4` 个叙事信息块；不要退化成多页拼贴，也不要变成纵向长海报
- `visible_label` 和 `numeric_fact` 都必须来自 `information_blocks`；如果找不到来源依据，就删掉，不要硬加
- `architecture` 类型可以画抽象节点、连接线和分镜，但不能伪造真实系统图、模块名、坐标轴或仪表盘
- `research` 类型可以做机制示意和 callout，但不能伪造论文图表、公式结果或实验指标
- 默认不要用对话气泡；只有原文真的有一句短引语必须上图时，才允许 `1` 个极短中文引语
- 不要把“多堆一点风格词”当成唯一优化方式；清楚的摘要弧线、信息块压缩和删减杂物通常更有效

验收逻辑固定为：

- **主题不对**：回到 brief 重写，再生成
- **主题对但摘要不清楚**：压缩 `information_blocks`，重写 `summary_angle` / `narrative_flow`
- **主题对但细节不对**：优先编辑或定向重生
- **只有局部出错**：只修局部问题，不推倒整张图
- **已经合格**：移动或复制到 `src/assets/{ID}/01-cover.{ext}`，更新 Markdown / `ogImage` / 微信封面路径

合格封面的最低标准：

- 至少包含 `2` 个能映射回 brief 的叙事节点
- 只允许 `1-3` 处少量中文短标签 / 数字，不出现主标题、长句和英文长标签
- 不像真实产品截图、真实架构图、真实 dashboard 或网页截图
- 一眼能读出这是在**概括文章内容**，而不是泛科技氛围图

## 10. 示例

### 教程封面：从配置到验证

- `cover_type`：`tutorial`
- `summary_angle`：把安装、配置、验证压成一张宽封面。
- `information_blocks`：三个可追溯的操作阶段；可见标签为「安装」「配置」「验证」。
- `base_style`：`editorial technical illustration`
- `selected_style`：`HD-2D`
- `selected_style_prompt_descriptor`：使用第 4 节的默认描述。
- `selected_style_reason`：采用仓库默认 HD-2D 风格。
- 主体与构图：二维像素工具与人物置于三维微缩工作台，三个操作阶段沿横向展开，柔和光照引导视线，保持一个主焦点。

### 架构正文插图：解释一次任务的流转

- 对应段落：介绍任务如何依次完成采集、分析与汇总。
- 解释目标：帮助读者理解三段职责和交接顺序。
- 来源依据：对应正文和原文中的三个阶段，不新增模块名或指标。
- 画面：16:9 微缩场景中，三个像素工作台通过传递同一个任务物件表达交接；与封面的像素尺度、配色和光影一致。
- 文件：`src/assets/{ID}/02-illustration-task-flow.png`
- 正文引用：`![任务从采集到分析再到汇总的概念示意](../../assets/{ID}/02-illustration-task-flow.png)`

## 11. 正文插图

### 添加条件与位置

- 正文插图按内容需要添加，通常 0–2 张；只有能帮助理解流程、机制、前后变化或方案对比时才生成。短文或已有充分图解时不额外添加，不为每个章节凑图。
- 每张图先明确对应段落、解释目标、来源锚点、主体关系和最终 prompt；不要求新建一套固定 JSON 格式。
- 将图放在相关概念首次完整解释之后或对比段落附近，避免打断代码块、步骤或连续论证，不放在文末集中堆图。
- 真实操作截图、实验数据图、准确流程图和架构图保留原貌。新增插图用于概念说明，不能代替原始证据；必要时在 alt 或图注标注「概念示意」。
- 「不要封面」只跳过封面及其 brief、`ogImage`；正文插图可独立生成。「不要配图」跳过全部图片生成，已有真实截图与技术图仍按内容需要保留。

### 风格、保存与验收

- 默认 16:9，每张围绕一个解释目标；使用第 4 节描述，与封面保持配色、像素尺度和光影一致。无封面时先确定一组统一的视觉设定，用于同篇所有新增插图。
- 用户当次指定其他风格时，按第 5 节处理覆盖范围。仍保留来源依据和信息真实性要求。
- 保存为 `src/assets/{ID}/02-illustration-{topic}.png` 或 `.jpg`，后续依次编号为 `03-illustration-{topic}` 等，`topic` 使用简短英文 kebab-case。避免与已有文件重名，不覆盖真实截图和其他资源。
- 使用 `../../assets/{ID}/{filename}` 引用最终文件并补中文 alt；仅将封面路径写入 `ogImage` 与微信 `cover-image`，正文插图通过 Markdown 正文发布。
- 检查内容与来源一致、像素边缘清晰、主体关系可读、风格一致、文件及引用有效。禁止虚构界面、命令输出、实验指标、技术标签、坐标轴和架构节点；生成图片适用第 7 节禁令。
- 首轮有问题时，只修正明确的 1–3 项后再检查。可选插图生成或精修后仍无法合格时，省略该图并删除对应正文引用，在最终报告说明；正文仍须能独立读懂。

### 正文插图 prompt

```text
Asset type: inline explanatory illustration for a Chinese tech blog, aspect ratio 16:9.
Explanation goal: {本图唯一解释目标}.
Source-grounded content: {对应段落、来源锚点与需要表达的关系}.
Subject and action: {主体与动作}.
Composition: {空间布局与关系，只表达本段所需内容}.
Style/medium: {selected_style_prompt_descriptor；默认使用第 4 节 HD-2D 描述}.
Visual continuity: {与封面或同篇插图一致的配色、像素尺度、光影}.
Visible text: no text by default; allow only essential short Chinese labels or ordinal markers explicitly approved from the source-grounded content. No invented technical names or metrics.
Constraints: crisp pixel edges, readable focal relationships, moderate depth of field; no excessive blur, no watermark, no prompt residue, no UI screenshots, no dashboards, no fake terminal output, no fake charts or architecture diagrams, no fabricated metrics, no decorative clutter.
```
