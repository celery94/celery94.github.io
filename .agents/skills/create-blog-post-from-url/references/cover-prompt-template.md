# Cover Prompt Template

创建文章封面时，先用这个模板生成**封面 brief**和第一轮 prompt，再选择可用的图像生成 / 编辑技能执行。默认不要在这里预设某个固定 backend；只有用户明确要求 Azure 时才点名 `azure-image-gen`。

不要默认“一次生成 = 最终封面”。先确认主题、摘要弧线、主体、构图和选定随机风格是否成立，再根据问题做一次定向编辑或重生。

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
  "selected_style": "用户指定风格，或从 40 项风格池随机选择的风格名称",
  "selected_style_prompt_descriptor": "用于生图 prompt 的安全描述词，不要求复刻品牌、工作室或艺术家",
  "selected_style_reason": "为什么本篇选择这个风格；随机选择时写明是随机选中",
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

- `information_blocks` 默认 `2-4` 个；宽封面不要超过 `4` 个
- 每个信息块都必须能映射回原文锚点；不能编造指标、节点名或结论
- 如果文章需要 `5+` 个点才能讲清，先压缩叙事弧线，再写 prompt
- 宽封面必须保留 `1` 个主焦点；其余信息块只承担摘要叙事，不把画面做成长图海报

## 3. 类型到基础风格的固定映射

按这个表直接选，不要重新发明基础风格。

| 类型 | 基础风格 | 主体规则 | 构图规则 | 气质 |
|---|---|---|---|---|
| `tutorial` | editorial technical illustration | 一个主工具 + 一个明确动作 | 单点聚焦或轻微斜向推进 | 清晰、可执行、不过度戏剧化 |
| `release` | product-poster style illustration | 一个主产品或主符号 | 居中主物体 + 少量辅助符号 | 新鲜、克制、有登场感 |
| `architecture` | isometric conceptual systems scene | 2-4 个模块化实体 | 等距空间或层级式关系 | 理性、结构化、非真实图表 |
| `analysis` | conceptual editorial illustration | 一个核心冲突或对照关系 | 左右对照、拉扯或边界式构图 | 有判断力，但不煽情 |
| `research` | abstract technical concept art | 一个机制或结构主意象 | 单点主结构 + 少量流动辅助线索 | 精确、克制、少人物 |

## 4. 随机风格池

每篇文章在动笔前只确定 1 个 `selected_style`：用户明确指定时用用户指定；否则从下表 40 项里随机选 1 项。文章表达、封面 brief、封面 prompt 和图片验收都使用同一个风格方向。

生成图片时不要直接要求“模仿某品牌 / 某工作室 / 某艺术家”。`selected_style` 可以记录原清单名称，`selected_style_prompt_descriptor` 必须使用下表的安全描述。

| selected_style | selected_style_prompt_descriptor |
|---|---|
| 日漫少年风 | energetic shonen-inspired manga look, clean ink lines, dynamic poses, readable action rhythm, bright restrained color accents |
| 日漫少女风 | soft shojo-inspired manga look, elegant linework, expressive faces, gentle decorative details, luminous pastel accents |
| 青年写实风 | mature realistic comic illustration, grounded anatomy, restrained expressions, cinematic everyday lighting, detailed but readable scenes |
| 治愈日常风 | cozy slice-of-life illustration, warm natural light, soft domestic details, calm pacing, gentle hand-drawn texture |
| 热血战斗风 | high-energy battle comic look, strong silhouettes, speed lines, impact framing, bold contrast without excessive clutter |
| 校园恋爱风 | youthful campus romance illustration, clean school-life setting, soft backlight, subtle emotional gestures, fresh color palette |
| 韩漫条漫风 | polished vertical-webtoon-inspired rendering adapted to a wide cover, clean gradients, sharp character shapes, glossy color blocks |
| 国漫二次元风 | contemporary Chinese anime-comic illustration, crisp linework, ornate but controlled details, vibrant fantasy-tech color accents |
| 港漫武侠风 | bold martial-arts comic look, expressive ink strokes, dramatic stances, gritty texture, strong motion arcs |
| 美漫超级英雄风 | American superhero-comic energy, bold outlines, halftone texture, dramatic perspective, high-contrast color blocking |
| 欧漫清线风 | European clear-line comic style, precise outlines, flat readable colors, tidy environments, restrained humor and detail |
| 赛博朋克风 | cyberpunk comic mood, neon accents, rain-slick surfaces, dense urban tech atmosphere, controlled purple-blue usage |
| 蒸汽朋克风 | steampunk adventure illustration, brass mechanisms, gears, goggles, warm industrial light, handcrafted machinery |
| 黑暗奇幻风 | dark fantasy illustration, gothic silhouettes, ancient textures, moody rim light, restrained magical atmosphere |
| 科幻机甲风 | science-fiction mecha concept illustration, mechanical forms, hard-surface details, cockpit-scale cues, cool industrial palette |
| 水彩漫画风 | watercolor comic illustration, translucent washes, visible paper texture, soft edges, light ink structure |
| 厚涂插画风 | painterly digital illustration, rich brushwork, volumetric lighting, strong focal contrast, textured color masses |
| 极简线稿风 | minimalist line-art illustration, sparse clean strokes, ample negative space, precise symbolic objects, limited accent color |
| 黑白版画风 | black-and-white printmaking look, carved textures, bold shadows, high contrast, poster-like but no title text |
| Q版 Chibi 风 | chibi character illustration, small cute proportions, simplified expressions, playful shapes, clear infographic readability |
| 美式卡通风 | American cartoon illustration, elastic shapes, clear expressions, bold color fields, light comedic timing |
| 吉卜力动画风 | warm hand-drawn animation feeling, natural environments, gentle fantasy everyday mood, soft painterly backgrounds, no studio imitation |
| 迪士尼动画风 | bright family-animation feeling, rounded character shapes, clear emotional acting, polished color and lighting, no studio imitation |
| 独立漫画风 | indie comic illustration, personal hand-drawn marks, muted palette, imperfect line texture, intimate editorial feeling |
| 像素复古风 | retro pixel-art inspired illustration, blocky forms, limited palette, old game composition cues, readable wide layout |
| 悬疑惊悚风 | suspense thriller comic mood, low-key lighting, sharp shadows, uneasy framing, controlled tension without gore |
| 废土末日风 | post-apocalyptic wasteland illustration, weathered materials, dusty atmosphere, survival objects, desaturated contrast |
| 洛丽塔幻想风 | ornate fantasy fashion illustration, lace-like detail, dollhouse elegance, soft magical palette, controlled decorative density |
| 中国古风仙侠风 | Chinese xianxia fantasy illustration, flowing robes, ink-wash atmosphere, mountains and clouds, elegant magical motion |
| 新海诚光影风 | transparent blue skies, dramatic backlight, detailed clouds, youthful cinematic lighting, rain and reflection details, no artist imitation |
| 高对比电影风 | high-contrast cinematic illustration, strong key light, deep shadows, wide-screen composition, dramatic but realistic color grading |
| 涂鸦街头风 | street-graffiti comic style, spray-paint texture, bold outlines, urban wall energy, vivid but controlled color clashes |
| 低饱和文艺风 | low-saturation arthouse illustration, quiet composition, subtle grain, muted colors, reflective emotional tone |
| 90年代复古动画风 | 1990s retro animation look, cel-shaded color, analog grain, bold simple backgrounds, nostalgic broadcast texture |
| 游戏原画风 | game concept art illustration, clear hero object, readable environment storytelling, polished lighting, production-art detail |
| 动态分镜电影风 | dynamic cinematic storyboard style, sequential panels, camera-motion feeling, strong cuts, clear narrative beats |
| 手绘铅笔草稿风 | hand-drawn pencil sketch look, visible construction lines, graphite texture, loose but intentional composition |
| 彩铅绘本风 | colored-pencil picture-book illustration, tactile strokes, gentle palette, warm narrative objects, soft educational tone |
| 儿童童话风 | children's fairy-tale illustration, simple magical forms, friendly proportions, bright storybook palette, safe wonder |
| 暗黑哥特风 | dark gothic illustration, pointed arches, lace shadows, candlelit contrast, ornate black shapes, restrained horror mood |

## 5. 风格使用规则

- `selected_style` 必须先于正文写作确定；不要写完文章或生成封面时才临时换风格
- 未指定风格时必须随机选择，不按文章类型固定映射
- 用户明确指定清单内风格时，直接使用该风格；用户指定清单外风格时，也要转成安全描述词并记录原因
- 文章正文只轻量吸收风格的叙事节奏和比喻，不改变事实密度、步骤完整度和技术准确性
- 封面 prompt 必须同时包含 `base_style` 与 `selected_style_prompt_descriptor`，前者保证文章类型清晰，后者保证视觉风格一致
- 强指向品牌、工作室、作者或在世艺术家的名称只允许出现在 `selected_style` 记录里；最终 prompt 使用描述词，不写“in the style of / 模仿 / 复刻”

额外规则：

- 不要把风格词堆满 prompt；先满足“摘要弧线清楚、主体明确、信息块可读”
- `architecture` 与 `research` 类型可以使用漫画分镜或 callout，但不要做成真实系统图、真实仪表盘或论文图表截图

## 6. 选择生图技能

- 默认保持 backend-agnostic：根据当前环境里**可用**的图像生成 / 编辑技能完成封面，不要把模板写死到某一个特定生成器
- 封面默认是宽图，prompt 里写明 `wide cover illustration, aspect ratio 2.35:1`
- 如果所选工具先把图片输出到临时目录、默认目录或中间路径，最终选中后移动或复制到 `src/assets/{ID}/01-cover.{ext}`
- 不要让 `ogImage`、正文图片引用或微信封面引用继续指向临时生成目录
- 如果第一轮主题对但细节有问题，优先编辑或定向重生一次；每轮只改 1-3 个明确问题
- 如果第一轮主题就不对，回到 brief，至少改“摘要角度 / 主隐喻 / 构图方式”中的两项后重新生成
- 如果用户明确要求 Azure / `azure-image-gen` / Azure OpenAI，必须尊重该要求

仅在使用 `azure-image-gen` 时，参考这些参数：

- 草图阶段：`size 1504x640`，`quality low`
- 终稿阶段：`size 2256x960`，`quality medium`
- `background` 只用 `auto` 或 `opaque`
- 当前脚本即使传 `--n > 1` 也只保存第一张，所以多方案探索要分多次生成或改走编辑流

## 7. 允许信息与统一禁令

每个 prompt 都必须同时说明**允许什么**和**禁止什么**，避免“信息图摘要”和“防伪造限制”互相打架。

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

## 9. 使用要求

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

### 示例 1：教程类（随机选中 `日漫少年风`）

关键槽位：

- `文章类型`：`tutorial`
- `摘要角度`：把“装上插件 -> 配好命令 -> 跑通工作流”压成一张封面
- `信息块`：`装插件` / `配命令` / `跑起来`
- `基础风格`：editorial technical illustration
- `selected_style`：`日漫少年风`
- `selected_style_prompt_descriptor`：energetic shonen-inspired manga look, clean ink lines, dynamic poses, readable action rhythm, bright restrained color accents
- `selected_style_reason`：用户未指定风格，本篇从风格池随机选中；教程流程适合用有推进感的动作节奏表达
- `style_safety_note`：清单风格为泛类型描述，不涉及品牌、工作室或艺术家复刻

Prompt 片段：

```text
Style/medium: combine editorial technical illustration with the selected visual style descriptor: energetic shonen-inspired manga look, clean ink lines, dynamic poses, readable action rhythm, bright restrained color accents. Stylized, polished, editorial, visually strong, and clearly readable as an infographic-style summary cover. Do not imitate a specific brand, studio, or living artist.
```

### 示例 2：架构类（随机选中 `科幻机甲风`）

关键槽位：

- `文章类型`：`architecture`
- `摘要角度`：把“采集 -> 分析 -> 汇总”做成一张可读的工作流封面
- `信息块`：`采集` / `分析` / `汇总`
- `基础风格`：isometric conceptual systems scene
- `selected_style`：`科幻机甲风`
- `selected_style_prompt_descriptor`：science-fiction mecha concept illustration, mechanical forms, hard-surface details, cockpit-scale cues, cool industrial palette
- `selected_style_reason`：用户未指定风格，本篇从风格池随机选中；模块化流水线可以用机械结构强化分工关系
- `style_safety_note`：使用泛科幻机甲描述，不引用具体作品或设计师

Prompt 片段：

```text
Style/medium: combine isometric conceptual systems scene with the selected visual style descriptor: science-fiction mecha concept illustration, mechanical forms, hard-surface details, cockpit-scale cues, cool industrial palette. Stylized, polished, editorial, visually strong, and clearly readable as an infographic-style summary cover. Do not imitate a specific brand, studio, or living artist.
```

### 示例 3：强指向风格（用户指定 `新海诚光影风`）

关键槽位：

- `文章类型`：`analysis`
- `摘要角度`：把“先写规格 -> 再交给 AI -> 返工更少”的判断做成强对照封面
- `信息块`：`先别乱写` / `先写规格` / `少返工`
- `基础风格`：conceptual editorial illustration
- `selected_style`：`新海诚光影风`
- `selected_style_prompt_descriptor`：transparent blue skies, dramatic backlight, detailed clouds, youthful cinematic lighting, rain and reflection details, no artist imitation
- `selected_style_reason`：用户明确指定该风格，覆盖随机选择
- `style_safety_note`：原风格名强指向在世作者，最终 prompt 只使用光影、天空、云层、反射等非仿冒描述

Prompt 片段：

```text
Style/medium: combine conceptual editorial illustration with the selected visual style descriptor: transparent blue skies, dramatic backlight, detailed clouds, youthful cinematic lighting, rain and reflection details, no artist imitation. Stylized, polished, editorial, visually strong, and clearly readable as an infographic-style summary cover. Do not imitate a specific brand, studio, or living artist.
```
