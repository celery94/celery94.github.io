---
pubDatetime: 2026-04-01T12:11:52+08:00
title: "用 Meziantou.ShardedTest 加速 .NET CI 测试分片"
description: "测试跑太慢拖慢 PR 反馈？Meziantou.ShardedTest 是一个 .NET 全局工具，能把测试集确定性地切成多个分片，在 CI 多个 Job 上并行运行，有效缩短流水线等待时间。本文介绍它的工作原理、适用场景，以及在 GitHub Actions 和 GitLab CI 上的完整配置方法。"
tags: [".NET", "CI/CD", "Testing", "GitHub Actions"]
slug: "dotnet-ci-test-sharding-meziantou-shardedtest"
ogImage: "../../assets/701/01-cover.png"
source: "https://www.meziantou.net/split-dotnet-test-projects-into-shards-with-meziantou-shardedtest.htm"
---

CI 里测试慢是个常见的痛点。一个项目测试越来越多，单次 `dotnet test` 要跑十几分钟，PR 等反馈的时间也跟着拉长。解决这个问题的一个思路是测试分片（test sharding）：把整个测试集切成几份，每份在一个独立的 CI Job 上并行执行，总耗时降到最慢那个分片的时间。

[Meziantou.ShardedTest](https://www.nuget.org/packages/Meziantou.ShardedTest) 是 Gérald Barré 写的一个 .NET 全局工具，专门做这件事。它自动完成测试枚举、分片分配、过滤参数生成，你只需要告诉它分片序号和总分片数，它帮你运行对应那一份测试。

![封面：测试分片并行执行示意](../../assets/701/01-cover.png)

## 工具做了什么

从用法看，`sharded-test` 的执行流程很清晰：

1. 调用 `dotnet test --list-tests` 枚举全部测试（仍可搭配 `--filter` 限定范围）
2. 对测试列表做确定性排序
3. 按 `--shard-index` 和 `--total-shards` 选出当前分片对应的那批测试
4. 用 `dotnet test` 加上相应的过滤参数运行这批测试，其他参数原样透传

一个细节：当测试数量很多时，过滤参数可能超出命令行长度限制。工具会自动把这种情况拆成多次 `dotnet test` 调用，不需要手动处理。

分片结果的确定性依赖 `dotnet test --list-tests` 输出的稳定性——只要测试程序集和框架版本不变，枚举结果就是固定的。

## 分片和框架内并行有什么区别

两者经常被混淆，但解决的层面不同：

- **测试框架并行化**（xUnit、NUnit、MSTest、TUnit 的 parallel 配置）：在同一台机器的同一个 `dotnet test` 进程内并发跑测试。
- **测试分片**：把测试分成几组，每组在单独的 CI Job 上运行，可以跨多台机器。

两者可以叠加使用。比如开 3 个分片，每个分片内部再开并行，这样既减少了 CI 总 Job 数，又利用了单机的多核能力。

## 什么情况下值得用分片

适合的场景：

- CI 测试阶段很慢，拖慢了 PR 反馈
- 单台机器跑不完或跑不好所有测试
- CI 平台支持同时运行多个 Job

不太适合的场景：

- 测试集本身很小，总耗时不长
- 大部分时间花在构建或环境准备上，而不是测试执行本身
- 测试以 IO 密集型为主，已经从框架内并行获益，瓶颈不在测试本身

原文也特别提到：分片主要对 CPU 密集型测试有明显提速效果，IO 密集型测试更适合在框架层面做并行。**引入分片前先测量一次当前的实际瓶颈**，再决定要不要做。

## 成本与局限

并行分片会增加 CI Job 数量，相应地会增加计算成本。具体要根据平台的并发配额和预算来决定开几个分片。

对于 IO 密集型测试，分片带来的加速可能有限，在这种情况下框架内并行可能更有效。实际效果建议实测对比，不要假设分片一定有效。

## 安装和基本用法

安装为全局工具：

```shell
dotnet tool install --global Meziantou.ShardedTest
```

在本地或 CI 里运行一个分片：

```shell
sharded-test --shard-index 1 --total-shards 4 tests/MyTests.csproj --configuration Release
```

`--shard-index` 从 1 开始计数，`--total-shards` 是总分片数，后面可以跟任何 `dotnet test` 支持的参数。

## GitHub Actions 配置

用 matrix 策略拉起多个并行 Job，每个 Job 运行一个分片：

```yaml
on:
  push:
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        shard-index: [1, 2, 3]
    steps:
      - uses: actions/checkout@v4
      - name: Install sharded-test
        run: dotnet tool install --global Meziantou.ShardedTest
      - name: Run tests (shard ${{ matrix.shard-index }}/3)
        run: sharded-test --shard-index ${{ matrix.shard-index }} --total-shards 3 tests/MyTests.csproj
```

`fail-fast: false` 确保一个分片失败时其他分片不会被取消，能看到全部失败信息。

## GitLab CI 配置

GitLab 用 `parallel` 关键字自动拉起多个 Job，并设置 `CI_NODE_INDEX` 和 `CI_NODE_TOTAL` 环境变量。`sharded-test` 会自动读取这两个变量作为默认值，不需要显式传 `--shard-index` 和 `--total-shards`：

```yaml
stages:
  - test

test:
  stage: test
  parallel: 3
  before_script:
    - dotnet tool install --global Meziantou.ShardedTest
    - export PATH="$PATH:$HOME/.dotnet/tools"
  script:
    - sharded-test tests/MyTests.csproj
```

GitLab 的这个集成让配置更简洁，不需要手动绑定 Job 序号。

## 小结

`Meziantou.ShardedTest` 做的事情并不复杂：枚举测试、确定性分组、按分片运行。但它把这个流程封装成一个好用的命令，省去了自己写脚本处理测试过滤、命令行长度溢出等细节。如果你的 .NET CI 测试阶段已经成为反馈瓶颈，这个工具值得试一试。

## 参考

- [原文：Speed Up .NET CI with Test Sharding](https://www.meziantou.net/split-dotnet-test-projects-into-shards-with-meziantou-shardedtest.htm)
- [Meziantou.ShardedTest NuGet 包](https://www.nuget.org/packages/Meziantou.ShardedTest)
- [源代码（GitHub）](https://github.com/meziantou/Meziantou.ShardedTest)
- [dotnet test 官方文档](https://learn.microsoft.com/dotnet/core/tools/dotnet-test)
