---
name: wechat-draft
description: 将文章内容发布到微信公众号草稿箱。当用户想把文章、博客内容或 Markdown 推送到微信公众号草稿箱时使用此技能，尤其是在用户提到"发布到微信"、"推送到公众号"、"推上草稿箱"、"发到微信草稿"等场景下应主动触发，即使用户没有明确说"草稿箱"也要触发。需要 app_id 和 app_secret，或者从环境变量中读取。
---

# 微信公众号草稿箱发布技能

本技能通过微信公众平台服务端 API，将指定文章（Markdown 或 HTML）自动发布到微信公众号草稿箱中。
默认会把 Markdown 转成适合公众号发布的 HTML，并将样式内联到最终内容中。

## 工作流程

1. **收集所需信息**（如未提供，向用户询问）
2. **获取 access_token**
3. **（可选）上传封面图片**以获取 thumb_media_id
4. **自动处理正文图片**，将 Markdown/HTML 中的本地图片上传到微信并替换为微信 URL
5. **调用新增草稿接口**，将文章保存到草稿箱
6. **向用户报告结果**，包括返回的 `media_id`

## 所需参数

| 参数 | 说明 | 来源 |
|------|------|------|
| `app_id` | 公众号的 AppID | 用户输入，或环境变量 `WECHAT_APP_ID` |
| `app_secret` | 公众号的 AppSecret | 用户输入，或环境变量 `WECHAT_APP_SECRET` |
| `title` | 文章标题 | 用户提供 |
| `content` | 文章正文（HTML 字符串、Markdown 字符串，或内容文件路径） | 用户提供 |
| `author` | 作者名（可选） | 用户提供，默认空 |
| `digest` | 摘要（可选，最多 120 字） | 用户提供，默认空 |
| `thumb_media_id` | 封面图片的媒体 ID（可选，若有封面图文件则自动上传获取） | 用户提供或自动上传 |
| `cover_image` | 本地封面图片路径（可选） | 用户提供 |
| `content_source_url` | 原文链接（可选） | 用户提供 |
| `content_format` | 内容格式，支持 `auto` / `markdown` / `html` | 可选，默认 `auto` |
| `style_preset` | 正文样式预设，支持 `wechat` / `none` | 可选，默认 `wechat` |
| `extra_css_file` | 额外 CSS 文件路径，会继续内联到最终 HTML 中 | 可选 |

**安全提示**：app_id 和 app_secret 属于敏感凭据，优先从环境变量读取，避免明文出现在命令行日志中。建议用户设置 `WECHAT_APP_ID` 和 `WECHAT_APP_SECRET` 环境变量。

## 执行步骤

### Step 1：收集信息

检查用户是否已提供所有必需参数。如果 `app_id` / `app_secret` 缺失，提示用户设置环境变量或直接提供（注意脱敏提示）。

### Step 2：准备内容

- 如果 `content` 是 `.md` 文件，或用户明确指定 `--content-format markdown`，先将 Markdown 转为 HTML
- 默认使用 `wechat` 样式预设，将排版样式内联到最终 HTML 中，避免依赖外部 CSS
- Markdown/HTML 中的本地正文图片会自动上传到微信 `uploadimg` 接口，并替换为返回的 HTTPS URL
- 微信内容不支持外部 CSS 和 JavaScript，务必确保 HTML 干净，仅保留可发布的标签和内联样式

使用脚本 `scripts/publish_draft.py` 执行所有 API 操作。

### Step 3：运行脚本

```bash
python <skill-dir>/scripts/publish_draft.py \
  --appid "$WECHAT_APP_ID" \
  --secret "$WECHAT_APP_SECRET" \
  --title "文章标题" \
  --content-file "/path/to/content.html" \
  [--content-format auto] \
  [--style-preset wechat] \
  [--extra-css-file "/path/to/extra.css"] \
  [--author "作者名"] \
  [--digest "摘要"] \
  [--cover-image "/path/to/cover.jpg"] \
  [--thumb-media-id "已有的media_id"] \
  [--content-source-url "https://example.com/original"]
```

或者直接传入内容字符串：

```bash
python <skill-dir>/scripts/publish_draft.py \
  --appid "$WECHAT_APP_ID" \
  --secret "$WECHAT_APP_SECRET" \
  --title "文章标题" \
  --content "# 正文标题\n\n这是一段 Markdown 正文" \
  --content-format markdown
```

脚本会：
1. 调用 `https://api.weixin.qq.com/cgi-bin/token` 获取 access_token
2. 若指定了 `--cover-image`，上传至 `https://api.weixin.qq.com/cgi-bin/media/upload?type=thumb` 获取 `thumb_media_id`
3. 将 Markdown 转换为 HTML，并把默认样式与额外 CSS 内联到最终内容
4. 扫描正文中的本地图片，调用 `https://api.weixin.qq.com/cgi-bin/media/uploadimg` 上传并替换链接
5. 调用 `https://api.weixin.qq.com/cgi-bin/draft/add` 新增草稿
6. 输出结果 JSON（含 `media_id`）

### Step 4：反馈结果

成功后向用户展示：
- 草稿的 `media_id`（用于后续查询或发布）
- 说明 Markdown 已被转换为带内联样式的 HTML（如果输入是 Markdown）
- 提醒用户在微信公众平台后台检查草稿箱并最终发布

## 常见错误处理

| 错误码 | 含义 | 解决方法 |
|--------|------|----------|
| 40001 | access_token 无效 | 检查 appid/secret 是否正确 |
| 40013 | appid 无效 | 确认 AppID 格式 |
| 41001 | access_token 缺失 | 确保先获取 token 再调用 |
| 45009 | 接口调用超过限制 | 减少调用频率 |
| 48001 | api 功能未授权 | 确认公众号已开通草稿箱功能 |

## 注意事项

- 草稿箱接口需要公众号为**服务号**并已完成认证；订阅号可能无权限
- access_token 有效期 7200 秒，脚本每次运行都会重新获取
- `thumb_media_id` 虽在 API 中标记为可选字段，但微信后台显示时封面为空；建议尽量提供封面图
- 正文中的本地图片现在会自动上传到 `/cgi-bin/media/uploadimg` 并替换为微信返回的 URL；相对路径按内容文件所在目录解析
- `--extra-css-file` 适合补充简单标签/类选择器规则；最终只保留内联样式，不保留外部 CSS
