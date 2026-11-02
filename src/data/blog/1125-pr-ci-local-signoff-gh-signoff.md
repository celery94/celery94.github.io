---
pubDatetime: 2026-11-02T08:40:00+08:00
title: "PR 不跑云端 CI，改用本地 signoff"
description: "一个 .NET 仓库 19 天里在 PR 上跑了 588 次 CI，作者把 pull_request 触发关掉，改用本地脚本、gh signoff 状态和规则集强制合并，四个月合并 833 个 PR；这篇拆开这套做法省了什么、赌的是什么。"
tags: ["DevOps", "GitHub Actions", "CI/CD", ".NET", "Git"]
slug: "pr-ci-local-signoff-gh-signoff"
ogImage: "../../assets/1125/01-cover.jpg"
source: "https://milanjovanovic.tech/blog/i-turned-off-ci-for-pull-requests"
---

19 天里，Katabench 仓库的 PR 流水线跑了 588 次，每次约 2.7 分钟，用的是 2 核 runner。跑的是 .NET 编译、单元测试和容器镜像构建，同样的步骤在合并进 main 之后还要再跑一遍。

作者在今年六月把 `pull_request` 触发关掉了，换成一套本地方案：脚本在本地跑检查，`gh signoff` 发一个 commit status，GitHub ruleset 要求这个 status 才允许合并。四个月下来 833 个 PR 这样合入。它省的是每次推送后的等待和 Actions 账单，代价是把「检查确实跑过」交给有 push 权限的人。

## 账单和等待一起涨

重复才是大头：PR 上跑一次，合进 main 再跑一次，而 588 次 PR 运行按 2.7 分钟算，光等就是二十多小时。私有仓库的 Actions 按分钟计费，不足一分钟也按一分钟算，这些时间直接对应账单；公开仓库用标准 runner 免费，等待照样存在。

关掉 PR 触发之前，这些运行都要排队：每次推送、每次改 review 意见、每次 rebase，都要重新跑一遍完整构建和镜像。

## DHH 在 2024 年就把 CI 搬回本机

2024 年 4 月，DHH 写 37signals 把持续集成搬回开发者的机器上：HEY 的远程 CI 跑五分半，他那台 Linux 台式机用不到一半时间。理由很直接，开发机的核心比租来的 runner 多。他同时说清楚了，这套不适合 Shopify、GitHub 那样的代码库规模。

缺的那块拼图是 PR 上的绿勾。检查跑到本地了，谁来告诉 GitHub「这个 commit 查过了」？

## 门禁是一个 shell 脚本

作者在仓库里放了 `ci/local-ci.sh`，最小版本这样：

```sh
#!/bin/sh

set -eu

marker="$(git rev-parse --git-dir)/ci-passed"

if [ "$(cat "$marker" 2>/dev/null)" = "$(git rev-parse HEAD)" ]; then
  echo "gate already passed for $(git rev-parse --short HEAD)"
else
  dotnet build MyApp.slnx -c Release -warnaserror
  dotnet test tests/MyApp.Tests -c Release --no-build
  dotnet format MyApp.slnx --verify-no-changes
  git rev-parse HEAD > "$marker"
fi

if [ "${1:-}" = "--signoff" ]; then
  gh signoff
fi
```

`set -eu` 让脚本在第一条失败的命令或未定义变量处停下，后面的签核只有全部通过才会执行。标记文件写在 `.git` 目录里，内容是当前 HEAD 的 hash：检查跑完把 hash 写进去，下次调用时 hash 相同就跳过检查，直接走到签核。

把现有 CI 的步骤原样搬进这个脚本，尤其是依赖 Docker 的集成测试——本地能跑通，才谈得上替代云端。

## hook 负责早发现，不负责拦人

git 在两个时间点读 hook 脚本：`pre-commit` 在生成提交之前，`pre-push` 在把提交发往远端之前。脚本返回非零，git 就取消这次操作。

`.git/hooks` 不随仓库提交，新克隆下来一个 hook 都没有。把 hook 放进仓库里的 `.githooks` 目录，然后每台机器改一次配置：

```bash
git config core.hooksPath .githooks
```

`.githooks/pre-push` 只有一行：

```sh
#!/bin/sh

exec sh ci/local-ci.sh
```

提交前记得 `chmod +x .githooks/pre-push`，否则 git 直接跳过它。

hook 里故意不传 `--signoff`：这一刻提交还只在本机，`gh signoff` 要 POST 到 `repos/{owner}/{repo}/statuses/{sha}`，GitHub 不认识这个 commit，请求就会失败，命令报错退出。所以流程是 push 时 hook 跑检查，push 成功之后单独执行一次 `sh ci/local-ci.sh --signoff`，复用刚才写下的标记，只做签核。

hook 的边界也很清楚：`git push --no-verify` 能绕过它，GitHub 也根本看不到它有没有跑。它能挡住手滑，挡不住存心绕过。

## 拦住合并的是那条 status

GitHub 的 status check 是挂在某个 commit 上的一条命名状态。工作流任务结束时可以发，任何有 push 权限的人也能直接调 API 发一个。`gh signoff` 做的是后者。

两条命令把这套门禁装上：

```bash
gh extension install basecamp/gh-signoff

gh signoff install
```

`install` 在 main 上创建一个 ruleset，要求名为 `signoff` 的 status，并禁止 force push。GitHub API 里对应的规则大致是这样：

```json
{
  "type": "required_status_checks",
  "parameters": {
    "required_status_checks": [{ "context": "signoff" }],
    "strict_required_status_checks_policy": true
  }
}
```

`strict_required_status_checks_policy` 打开后，就是界面上的「Require branches to be up to date before merging」。main 在你签核之后动过，这个 PR 就合不了，只能 rebase、重跑、重新签。同时开着几个 PR 时会反复折腾，换来的是通过校验的代码和最终合入的代码是同一份。

status 属于某一个 commit。往分支上再推一个提交，PR 会重新被挡住，直到新 commit 也有签核。

## 云端只留合并之后那一次

workflow 的触发去掉了 `pull_request`：

```yaml
on:
  push:
    branches: [main]
  schedule:
    - cron: "0 6 * * 1"
  workflow_dispatch:
```

现在流水线在每次合并进 main 之后跑一次，用的是干净的 runner，没有本地缓存、本地 SDK、本地镜像。这是唯一不采信本地结果的一次运行，检查的也是真正落在 main 上的那个 commit。

它挡不住已经合并的坏提交，因为它从合并之后才开始。签核环节出了问题，main 会变红，只能马上修。这是这套方案明写的代价。

`schedule` 一周跑一次，即使这周没有任何合并。作者的流水线里有容器镜像扫描，这一跑是为了发现基础镜像里新披露的 CVE。`workflow_dispatch` 则提供了一个手动触发按钮。

补丁节奏也支持这个设计。2026 年 10 月 13 日，.NET 10.0.13 是常规月度安全更新；10 月 25 日，.NET 10.0.14 作为带外修复发布，处理 CVE-2026-111497 的 Brotli 解码器越界写，中间只隔了 12 天。curl 在 10 月 14 日修了 CVE-2026-92392，HTTP/2 上传的 use-after-free，严重度 High。这些漏洞跟你什么时候合并代码没有关系，所以它们需要一个按时间触发的运行。

## 谁保证检查真的跑过

脚本本身没有漏洞：全部检查通过才签核。问题在于 status 不证明任何事，它只证明某个有 push 权限的人发过它。谁都可以在自己终端里直接敲 `gh signoff`；仓库管理员被列进 ruleset 的 bypass 列表，同样可以绕过去。

作者的仓库里只有他和他的 coding agent，agent 的指令禁止 `--no-verify`，也禁止在脚本之外签核。团队要采用这套做法，得先把同一条规则讲明白，并且接受它依赖约定。

还有一条硬限制：从 fork 来的 PR 没有 push 权限，发不出 status。开源项目不能照搬，外部贡献者继续走云端 CI，核心团队用 signoff。

## 哪些仓库适合，哪些别碰

| 场景                         | 结论   | 原因                         |
| ---------------------------- | ------ | ---------------------------- |
| 单人维护的私有仓库           | 适合   | 没有第二个人需要被说服       |
| 三五个人的内部团队           | 谨慎   | 全队要先同意「不许绕过检查」 |
| 开源项目、外部 fork 贡献     | 不适合 | fork 来的 PR 发不出 status   |
| 多 SDK、多平台矩阵           | 不适合 | 本地机器跑不动或跑不全       |
| 依赖云端服务和密钥的集成测试 | 谨慎   | 得先解决本地怎么拿到同等环境 |

想试的话顺序别弄反：先把脚本在分支上跑绿，再加 hook，然后建 ruleset 并要求 status，最后才去改 workflow 的 trigger。倒过来做，中间会有一段完全没有门禁的窗口。

这套做法省的是等待和账单，赌的是团队里没人绕过检查。如果这一点你没法确认，把 CI 留在云端更划算。

## 参考

- [I Turned Off CI for Pull Requests. Here's Why](https://milanjovanovic.tech/blog/i-turned-off-ci-for-pull-requests)
- [DHH：We're moving continuous integration back to developer machines](https://world.hey.com/dhh/we-re-moving-continuous-integration-back-to-developer-machines-3ac6c611)
- [basecamp/gh-signoff](https://github.com/basecamp/gh-signoff)
- [GitHub Docs: Commit statuses](https://docs.github.com/en/rest/commits/statuses)
- [GitHub Docs: Available rules for rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets)
- [Git Docs: githooks](https://git-scm.com/docs/githooks)
- [Git Docs: git-config core.hooksPath](https://git-scm.com/docs/git-config#Documentation/git-config.txt-corehooksPath)
- [.NET 10.0.14 release notes](https://github.com/dotnet/core/blob/main/release-notes/10.0/10.0.14/10.0.14.md)
- [curl security advisories](https://curl.se/docs/security.html)
