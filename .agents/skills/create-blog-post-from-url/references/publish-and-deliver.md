# 微信发布与 Git 交付

## 微信文末

文章将发布到微信时，在 `## 参考` 前加入一段克制的关注引导，说明 Aide Hub 会继续分享 AI 助手、开发工具和软件工程实践。

仅在文章已经产出对应资源或用户明确提供资源时，才可提到资料、清单、源码或自动回复关键词。关键词建议可以放在最终报告，不得把尚未配置的回复写成已生效能力。

## 发布前检查

对新文章和 `cover-brief.json` 运行 Prettier，再执行：

```bash
node .agents/skills/create-blog-post-from-url/scripts/validate-article.mjs \
  src/data/blog/{ID}-{slug}.md \
  --wechat
```

校验失败时：

- 保留已经生成的文章和资源
- 不调用微信发布
- 不提交、不推送
- 报告每个校验错误和本地文件路径

## 微信参数

使用 `wechat-draft` 技能，参数映射如下：

| 参数 | 来源 |
|---|---|
| `title` | frontmatter `title` |
| `content-file` | 新文章 Markdown 路径 |
| `content-format` | `markdown` |
| `author` | `Aide Hub` |
| `digest` | frontmatter `description` |
| `cover-image` | `ogImage` 指向的最终本地封面 |
| `content-source-url` | frontmatter `source` |

从项目或父目录的 `.env` 读取 `WECHAT_APP_ID` 和
`WECHAT_APP_SECRET`，不得输出凭据。

如果用户要求不生成封面但仍要发微信，必须取得已有永久封面素材或请用户提供本地封面。封面缺失时停止发布。

发布成功后报告 `media_id`，提醒用户在公众号后台检查草稿。原创声明与广告设置由用户在后台完成。

## Git 提交与推送

只有微信发布成功并返回 `media_id` 后才执行：

1. 检查当前分支、upstream 和工作区改动。
2. 只暂存：
   - `src/data/blog/{ID}-{slug}.md`
   - `src/assets/{ID}/`
3. 使用 `feat: add blog post {slug}` 形式的 Conventional Commit。
4. 推送当前分支；没有 upstream 时推送到 `origin` 同名分支并设置 upstream。
5. 报告 commit hash 和推送分支。

用户明确不发微信或只生成博客时，跳过本节全部 Git 操作。微信发布失败时也不提交、不推送。
