---
name: wechat-draft
description: 将图文文章或图片消息发布到微信公众号草稿箱。当用户想把文章、博客内容、Markdown 或一组图片推送到微信公众号草稿箱时使用此技能，尤其是在用户提到"发布到微信"、"推送到公众号"、"推上草稿箱"、"发到微信草稿"、"图片消息"、"newspic"等场景下应主动触发，即使用户没有明确说"草稿箱"也要触发。需要 app_id 和 app_secret，或者从环境变量中读取。
---

# 微信公众号草稿箱发布技能

本技能通过微信公众平台服务端 API，将指定文章（Markdown 或 HTML）或图片消息（`newspic`）自动发布到微信公众号草稿箱中。
默认支持两类草稿：

- `news`：标准图文草稿。Markdown 会先转换为适合公众号发布的 HTML，并将样式内联到最终内容中。
- `newspic`：图片消息草稿。会将本地图片上传为永久素材，最多 20 张，首张图片即封面图。

## 工作流程

1. **收集所需信息**（如未提供，向用户询问）
2. **获取 access_token**
3. **按草稿类型准备素材**
4. **调用新增草稿接口**，将图文或图片消息保存到草稿箱
5. **向用户报告结果**，包括返回的 `media_id`

### `news` 图文草稿流程

1. 可选上传封面图，获取 `thumb_media_id`
2. 将 Markdown/HTML 正文中的本地图片上传到微信 `uploadimg` 接口并替换为 HTTPS URL
3. 调用 `draft/add` 新增图文草稿

### `newspic` 图片消息流程

1. 收集图片列表，支持重复传入 `--image` 或传入 `--image-dir`
2. 将图片上传为永久素材 `image`，得到 `image_media_id`
3. 组装 `article_type=newspic` 的 `image_info.image_list`
4. 调用 `draft/add` 新增图片消息草稿

> 图片消息限制：最多 20 张，首张图片即封面图。若目录中图片超过 20 张，脚本会按文件名顺序取前 20 张并打印提示。
> `newspic` 标题长度按 UTF-8 字节数计算，最多 64 字节；中文标题通常建议控制在 21 个汉字以内。

## 所需参数

| 参数 | 说明 | 来源 |
|------|------|------|
| `article_type` | 草稿类型：`news` 或 `newspic` | 可选，默认 `news` |
| `app_id` | 公众号的 AppID | 用户输入，或环境变量 `WECHAT_APP_ID`（可由 `.env` 文件加载） |
| `app_secret` | 公众号的 AppSecret | 用户输入，或环境变量 `WECHAT_APP_SECRET`（可由 `.env` 文件加载） |
| `title` | 文章标题 | 用户提供 |
| `content` | `news` 模式下为文章正文；`newspic` 模式下为图片消息纯文本说明 | 用户提供 |
| `author` | 作者名（可选） | 用户提供，默认空 |
| `digest` | 摘要（可选，最多 120 字） | 用户提供，默认空 |
| `thumb_media_id` | 封面图片的媒体 ID（可选，若有封面图文件则自动上传获取） | 用户提供或自动上传 |
| `cover_image` | 本地封面图片路径（可选） | 用户提供 |
| `content_source_url` | 原文链接（可选） | 用户提供 |
| `content_format` | 内容格式，支持 `auto` / `markdown` / `html` | 可选，默认 `auto` |
| `style_preset` | 正文样式预设，支持 `auto` / `default` / `code` / `essay` / `guide` / `none` | 可选，默认 `auto` |
| `extra_css_file` | 额外 CSS 文件路径，会继续内联到最终 HTML 中 | 可选 |
| `image` | 图片消息图片路径，可重复传入 | `newspic` 模式使用 |
| `image_dir` | 图片消息目录，按文件名顺序收集图片 | `newspic` 模式使用 |

**安全提示**：app_id 和 app_secret 属于敏感凭据，优先从环境变量读取，避免明文出现在命令行日志中。建议用户设置 `WECHAT_APP_ID` 和 `WECHAT_APP_SECRET`，并可通过 `.env` 文件统一加载。

### 参数约束

- `news` 模式必须提供 `content` 或 `content_file`
- `newspic` 模式必须提供 `image` 或 `image_dir`
- `newspic` 模式不使用 `cover_image` / `thumb_media_id`，因为首张图片就是封面图
- `newspic` 模式若未显式提供 `content`，脚本会回退使用 `digest`，再回退到 `title`
- `newspic` 模式会校验标题长度，超过 64 个 UTF-8 字节时直接报错；生成标题时优先压缩为短结论句

## 执行步骤

### Step 1：收集信息

检查用户是否已提供所有必需参数。如果 `app_id` / `app_secret` 缺失，提示用户设置环境变量、通过 `.env` 文件加载，或直接提供（注意脱敏提示）。

### Step 2：准备 `news` 图文内容

- 如果 `content` 是 `.md` 文件，或用户明确指定 `--content-format markdown`，先将 Markdown 转为 HTML
- 默认使用 `auto` 样式预设，脚本会根据文章内容（代码块数量、段落长度、标题密度）和 frontmatter 标签**自动推断**最合适的样式
  - `code`：代码密集型技术文章（多个代码块 / C#、Python 等技术标签）
  - `essay`：散文/观点型文章（无代码块、长段落、AI/经济/哲学类标签）
  - `guide`：教程/步骤指南（多个二三级标题 / Tutorial、入门类标签）
  - `default`：通用微信排版，适合上述以外的文章
  - `none`：不应用任何预设样式
- 所有预设均由 `scripts/styles/base.css` 提供基础排版，`code.css` / `essay.css` / `guide.css` 各自叠加差异化样式；如需自定义，可在 `styles/` 目录中新增 CSS 文件并通过 `--style-preset` 按文件名引用
- 若 Markdown 中存在 `## 参考链接` 等参考章节，章节内链接会保留**原始 URL** 作为 `href` 和显示文本，避免被转换成仅显示标题的形式
- Markdown/HTML 中的本地正文图片会自动上传到微信 `uploadimg` 接口，并替换为返回的 HTTPS URL
- 微信内容不支持外部 CSS 和 JavaScript，务必确保 HTML 干净，仅保留可发布的标签和内联样式

使用脚本 `scripts/publish_draft.py` 执行所有 API 操作。

### Step 3：准备 `newspic` 图片消息内容

- 收集信息卡或其他图片文件，优先保持业务顺序
- 若传入 `--image-dir`，脚本会按文件名升序读取目录中的图片文件
- 图片会通过永久素材接口上传，得到 `image_media_id`
- 组装图片消息请求体：`article_type=newspic`、`image_info.image_list[].image_media_id`
- 首张图片即封面图；正文 `content` 仅保留纯文本，不做 HTML/CSS 内联
- 标题必须控制在 64 个 UTF-8 字节以内；如果主标题过长，先压缩再调用脚本，不要把超限标题直接传给微信接口

### Step 4：运行脚本

> **凭证提示**：如果项目根目录或父目录已有 `.env` 文件且配置了 `WECHAT_APP_ID` / `WECHAT_APP_SECRET`，脚本会自动从 `.env` 加载，此时可以省略 `--appid` 和 `--secret` 参数。当 agent 在混合 shell 环境（如 Windows 下的 bash）中运行时，**推荐省略这两个参数**，避免因 `%VAR%` vs `$VAR` 语法差异导致传入字面字符串而非实际值。

#### 发布 `news` 图文草稿

**省略凭证的推荐写法**（.env 已配置时）：

```bash
python <skill-dir>/scripts/publish_draft.py \
  --article-type news \
  --title "文章标题" \
  --content-file "/path/to/content.md" \
  --content-format markdown \
  --style-preset auto \
  --author "作者名" \
  --digest "摘要" \
  --cover-image "/path/to/cover.png" \
  --content-source-url "https://example.com/original"
```

**显式传入凭证的写法**（.env 未配置时）：

```bash
python <skill-dir>/scripts/publish_draft.py \
  --appid "$WECHAT_APP_ID" \
  --secret "$WECHAT_APP_SECRET" \
  --article-type news \
  --title "文章标题" \
  --content-file "/path/to/content.html" \
  [--content-format auto] \
  [--style-preset auto] \
  [--extra-css-file "/path/to/extra.css"] \
  [--author "作者名"] \
  [--digest "摘要"] \
  [--cover-image "/path/to/cover.jpg"] \
  [--thumb-media-id "已有的media_id"] \
  [--content-source-url "https://example.com/original"]
```

或者直接传入内容字符串（.env 已配置时可省略 --appid/--secret）：

```bash
python <skill-dir>/scripts/publish_draft.py \
  --article-type news \
  --title "文章标题" \
  --content "# 正文标题\n\n这是一段 Markdown 正文" \
  --content-format markdown
```

#### 发布 `newspic` 图片消息草稿

（.env 已配置时可省略 --appid/--secret）

```bash
python <skill-dir>/scripts/publish_draft.py \
  --article-type newspic \
  --title "信息卡标题" \
  --content "一句话说明这组图片" \
  --image "/path/to/card-1.png" \
  --image "/path/to/card-2.png"
```

或者直接从目录读取图片：

```bash
python <skill-dir>/scripts/publish_draft.py \
  --article-type newspic \
  --title "信息卡标题" \
  --image-dir "/path/to/info-card-output"
```

脚本会：
1. 调用 `https://api.weixin.qq.com/cgi-bin/token` 获取 access_token
2. `news` 模式下，若指定了 `--cover-image`，上传至 `https://api.weixin.qq.com/cgi-bin/material/add_material?type=thumb` 获取 `thumb_media_id`
3. `news` 模式下，将 Markdown 转换为 HTML，并把默认样式与额外 CSS 内联到最终内容
4. `news` 模式下，扫描正文中的本地图片，调用 `https://api.weixin.qq.com/cgi-bin/media/uploadimg` 上传并替换链接
5. `newspic` 模式下，调用 `https://api.weixin.qq.com/cgi-bin/material/add_material?type=image` 上传图片，得到 `image_media_id`
6. 调用 `https://api.weixin.qq.com/cgi-bin/draft/add` 新增草稿
7. 输出结果 JSON（含 `media_id`、`article_type`，图片消息还会返回 `image_count`）

### Step 5：反馈结果

成功后向用户展示：
- 草稿的 `media_id`（用于后续查询或发布）
- `article_type`（`news` 或 `newspic`）
- 若为 `newspic`，补充本次提交的图片数量
- 说明 Markdown 已被转换为带内联样式的 HTML（如果输入是 `news` 且输入是 Markdown）
- 提醒用户在微信公众平台后台检查草稿箱并最终发布

## 常见错误处理

| 错误码 | 含义 | 解决方法 |
|--------|------|----------|
| 40001 | access_token 无效 | 检查 appid/secret 是否正确 |
| 40013 | appid 无效 | 确认 AppID 格式 |
| 41001 | access_token 缺失 | 确保先获取 token 再调用 |
| 45009 | 接口调用超过限制 | 减少调用频率 |
| 48001 | api 功能未授权 | 确认公众号已开通草稿箱功能 |
| 40007 | invalid media_id | 检查封面图或图片消息图片是否已成功上传为永久素材 |
| 45166 | invalid content | 检查图片消息正文是否包含 HTML，或图文正文是否超限 |

## 注意事项

- 草稿箱接口需要公众号为**服务号**并已完成认证；订阅号可能无权限
- access_token 有效期 7200 秒，脚本每次运行都会重新获取
- `thumb_media_id` 虽在 API 中标记为可选字段，但微信后台显示时封面为空；建议尽量提供封面图
- 正文中的本地图片现在会自动上传到 `/cgi-bin/media/uploadimg` 并替换为微信返回的 URL；相对路径按内容文件所在目录解析
- Markdown 转 HTML 时，`参考链接` 章节里的链接会使用原始 URL 作为最终 HTML 中的链接地址与显示文本
- `--extra-css-file` 适合补充简单标签/类选择器规则；最终只保留内联样式，不保留外部 CSS
- 图片消息使用 `article_type=newspic`，图片相关信息写入 `image_info.image_list[].image_media_id`
- 图片消息里的图片数量最多 20 张，首张图片即封面图；超过 20 张时脚本会截断为前 20 张
- 图片消息标题最多 64 个 UTF-8 字节；中文通常约为 21 个汉字，超限时脚本会在提交前直接失败并提示缩短
- 图片消息正文只支持纯文本和部分特殊功能标签；本脚本默认会把输入收敛为纯文本
- `info-card-designer` 可以在生成信息卡 PNG 后直接调用本脚本的 `newspic` 模式，把产出的单图或分割图自动写入微信草稿箱
