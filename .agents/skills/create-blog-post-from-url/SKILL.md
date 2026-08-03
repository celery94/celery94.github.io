---
name: create-blog-post-from-url
description: 从公开 URL 取证并生成可信、自然、可执行的中文博客 Markdown、文章资源和 frontmatter。用户要求把链接改写成博客、生成封面、发布微信公众号草稿或完成博客发布流程时使用；默认生成封面，通过校验后发布微信草稿，并只提交、推送本次文章文件。
---

# 从 URL 创建博客

把外部内容整理成一篇可独立阅读的中文文章。事实准确与教程可执行性优先，其次是中文可读性、传播效果和封面风格。

## 默认结果

除非用户明确缩小范围，完成以下流程：

1. 读取并核对原文
2. 创建博客 Markdown 和文章资源
3. 随机选择一种封面风格并生成宽封面
4. 运行文章校验
5. 发布到微信公众号草稿箱
6. 微信返回 `media_id` 后，只提交并推送本次文章文件

用户明确说不要封面时跳过生图和 `ogImage`。用户明确说不发微信或只生成博客时，同时跳过微信发布、Git 提交和推送。

## 按阶段读取参考

- 开始取证和写作前，读取
  [source-and-writing.md](references/source-and-writing.md)。
- 需要封面时，读取
  [cover-prompt-template.md](references/cover-prompt-template.md)。
- 需要微信发布或 Git 推送时，读取
  [publish-and-deliver.md](references/publish-and-deliver.md)。

只读取当前流程需要的参考文件。

## 工作流程

### 1. 确认范围

- 必须有原文 URL。
- 可接受用户指定标题、标签、封面方式或发布时间。
- 原文发布日期只用于理解上下文。
- 默认账号定位为 Aide Hub：AI 助手、软件开发、技术洞察。
- 检查工作区现有改动，后续只处理本次文章文件。

### 2. 完整取证

- 优先用具有页面渲染和交互能力的浏览器读取标题、作者、日期、正文结构、代码、图片和引用链接。
- 关闭遮挡层，展开正文，并补齐与主题直接相关的分页、折叠内容或官方链接。
- 将证据整理为结构化笔记，至少保留 2–4 个可追溯的原文锚点。
- 原文无法完整读取时停止成文，说明缺失内容，请用户提供正文或可访问链接。
- 对版本、价格、接口、产品能力等易变化信息，用最新官方资料核对。发现冲突时采用当前官方信息，并简短说明原文背景。

### 3. 生成文章

- 读取现有文章编号，使用最大数字前缀加一；文件名为
  `src/data/blog/{ID}-{slug}.md`。
- 根据原文选择教程、发布、架构、观点、研究、复盘或工具评测写法。
- 生成独立中文重述，保留事实、必要步骤、代码和证据锚点，避免逐段翻译和大段复刻。
- 教程必须写清前置条件、操作步骤、预期结果、验证方式和常见问题。
- 图片保存到 `src/assets/{ID}/`，正文使用
  `../../assets/{ID}/{filename}`。
- 保留 `## 参考`，列出原文和正文实际引用的关键来源。
- 参考链接写完后运行链接检查，失效链接替换为 Internet Archive 存档后再继续：

```bash
python .agents/skills/create-blog-post-from-url/scripts/check-references.py \
  src/data/blog/{ID}-{slug}.md
```

- 保存图片时统一转为微信支持的 jpg/png（微信 uploadimg 不接受 webp/gif/bmp），或确认 `wechat-draft` 发布时会自动转换。

### 4. 生成封面

- 用户未指定风格时，用随机选择脚本从风格池选 1 项（不要手写随机逻辑）：

```bash
python .agents/skills/create-blog-post-from-url/scripts/pick-cover-style.py
```

- 脚本输出 `selected_style` 与 `selected_style_prompt_descriptor`，直接填入 `cover-brief.json`。
- 随机风格只影响封面 brief、图片提示词和封面验收，不影响正文语气。
- 先保存 `src/assets/{ID}/cover-brief.json`（`final_prompt` 必须非空，生图 prompt 定稿后回填），再生成、检查和按需精修封面。
- 最终封面保存为 `src/assets/{ID}/01-cover.{ext}`，同步更新 `ogImage` 和微信封面路径。
- 当前模型不支持看图时，按 `azure-image-gen` 技能的 No-Vision 工作流执行；封面直接验收，不再要求用户逐篇确认，在最终报告中说明封面路径与摘要角度即可（用户不满意可要求重新生成）。

### 5. 校验

先对新文件运行 Prettier 检查，再运行：

```bash
node .agents/skills/create-blog-post-from-url/scripts/validate-article.mjs \
  src/data/blog/{ID}-{slug}.md \
  --wechat
```

如果用户明确只生成博客且不要封面，省略 `--wechat`。校验失败时停止微信发布、提交和推送，报告具体错误及已生成文件。

### 6. 发布与推送

- 使用 `wechat-draft` 技能发布校验通过的文章。
- `news` 必须有本地封面或已有永久封面素材；缺失时停止并说明。
- 微信发布成功后只暂存文章 Markdown 与 `src/assets/{ID}/`。
- 使用 Conventional Commit，推送当前分支。
- 微信发布失败时保留本地文件，不提交、不推送。

## 完成标准

- 原文证据完整，易变化信息已核对。
- 参考链接通过 `check-references.py` 检查，失效链接已替换为存档。
- 正文图片为微信支持的 jpg/png（或确认 `wechat-draft` 会转换）。
- 正文自然、准确，教程可以照着执行。
- frontmatter、资源路径、封面 brief 和微信长度限制通过校验。
- 随机视觉风格没有进入正文语气。
- 微信返回 `media_id` 后才提交并推送。
- 最终报告包含文章路径、封面路径、`media_id`、commit hash 和推送分支；跳过或失败的步骤需说明原因。
