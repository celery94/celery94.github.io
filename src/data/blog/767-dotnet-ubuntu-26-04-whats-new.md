---
pubDatetime: 2026-04-29T12:23:46+08:00
title: "Ubuntu 26.04 发布：.NET 10 的新变化与安装指南"
description: "Ubuntu 26.04（Resolute Raccoon）正式发布，内置 .NET 10 支持。本文介绍如何安装 .NET 10、使用最新容器镜像、体验 Native AOT，以及通过 backports PPA 安装 .NET 8/9。"
tags: [".NET", "Ubuntu", "Linux", "Containers", "Native AOT"]
slug: "dotnet-ubuntu-26-04-whats-new"
ogImage: "../../assets/767/01-cover.png"
source: "https://devblogs.microsoft.com/dotnet/whats-new-for-dotnet-in-ubuntu-2604/"
---

> 本文作者 Richard Lander，.NET 团队 Program Manager，原载于 .NET 官方博客（2026 年 4 月 23 日）。

Ubuntu 26.04 LTS（代号 Resolute Raccoon）正式发布了。按照惯例，每个新的 Ubuntu LTS 都会内置最新的 .NET LTS。这次，Ubuntu 26.04 带来的是 .NET 10，开箱即用。

## 安装 .NET 10

在 Ubuntu 26.04 上安装 .NET 10 SDK，一条命令搞定：

```bash
sudo apt update
sudo apt install dotnet-sdk-10.0
```

下面是在 `ubuntu:resolute` 容器里的完整演示：

```bash
$ docker run --rm -it ubuntu:resolute
$ apt update
$ apt install -y dotnet-sdk-10.0
$ dotnet --version
10.0.105
```

装完之后可以直接用 file-based app 跑一段 C#，不需要项目文件：

```bash
$ dotnet run - << 'EOF'
using System.Runtime.InteropServices;

Console.WriteLine($"Hello {RuntimeInformation.OSDescription} from .NET {RuntimeInformation.FrameworkDescription}");
EOF
Hello Ubuntu Resolute Raccoon (development branch) from .NET .NET 10.0.5
```

这里用的是 [heredoc](https://en.wikipedia.org/wiki/Here_document) 把代码通过 stdin 传给 `dotnet run`，标准的 Unix 用法。.NET 10 的 [file-based apps](https://learn.microsoft.com/dotnet/core/sdk/file-based-apps) 特性让单文件 C# 程序不再需要 `.csproj`。

## 容器：noble → resolute

Ubuntu 26.04 的容器镜像已随本次发布一同推出，使用 `resolute` 标签（对应 `noble` 的升级）。把现有 Dockerfile 里的 `noble` 全部替换为 `resolute` 即可迁移：

```bash
$ sed -i "s/noble/resolute/g" Dockerfile.chiseled
```

以运行 ASP.NET Core 示例为例，构建并带资源限制启动：

```bash
docker build --pull -t aspnetapp -f Dockerfile.chiseled .
docker run --rm -it -p 8000:8080 -m 50mb --cpus .5 aspnetapp
```

[Chiseled 镜像](https://devblogs.microsoft.com/dotnet/announcing-dotnet-chiseled-containers/)等所有镜像规格保持不变。需要注意：容器复用的是宿主机内核，用 26.04 容器跑在 24.04 宿主上仍然是 Linux 6.x 内核。

## Native AOT

`dotnet-sdk-aot-10.0` 包提供了 Native AOT 编译所需的一切。安装时还需要 `clang`（.NET 用 LLD 做链接）：

```bash
apt install -y dotnet-sdk-aot-10.0 clang
```

查看可用的 SDK 包：

```bash
$ apt list dotnet-sdk*
dotnet-sdk-10.0/resolute,now 10.0.105-0ubuntu1 amd64 [installed,automatic]
dotnet-sdk-aot-10.0/resolute,now 10.0.105-0ubuntu1 amd64 [installed]
dotnet-sdk-dbg-10.0/resolute 10.0.105-0ubuntu1 amd64
```

把 hello world 发布为 Native AOT 二进制（file-based app 默认就是 NAOT）：

```bash
$ dotnet publish app.cs
$ du -h artifacts/app/*
1.4M    artifacts/app/app
3.0M    artifacts/app/app.dbg
```

1.4 MB 的可执行文件，启动时间怎么样？

```bash
$ time ./artifacts/app/app
Hello Ubuntu Resolute Raccoon (development branch) from .NET .NET 10.0.5

real    0m0.003s
user    0m0.001s
sys     0m0.001s
```

3 毫秒。这是最小启动场景，但对于命令行工具和 sidecar 服务很实用。

对于 Web 服务，以 [releasesapi 示例](https://github.com/dotnet/dotnet-docker/tree/main/samples/releasesapi) 为例，启用 AOT 发布：

```bash
$ dotnet publish
$ du -h bin/Release/net10.0/linux-x64/publish/releasesapi
13M     bin/Release/net10.0/linux-x64/publish/releasesapi
```

13 MB 包含完整的 ASP.NET Core 运行时和 System.Text.Json source-generated 元数据，自包含、无需 .NET 运行时依赖。启动后直接可用：

```bash
$ curl -s http://localhost:5000/releases | jq '[.versions[] | select(.supported == true) | {version, supportEndsInDays}]'
[
  { "version": "10.0", "supportEndsInDays": 942 },
  { "version": "9.0",  "supportEndsInDays": 207 },
  { "version": "8.0",  "supportEndsInDays": 207 }
]
```

## 安装 .NET 8 和 .NET 9

Canonical 对"支持"和"可用"做了明确区分：.NET 10 进入官方 archive，.NET 8 和 .NET 9 则通过 [dotnet-backports PPA](https://launchpad.net/~dotnet/+archive/ubuntu/backports) 提供，属于"尽力支持"。预计 .NET 11 发布后也会加入这个 PPA。

配置步骤：

```bash
# 先安装 software-properties-common（桌面版通常已预装）
apt install -y software-properties-common

# 添加 PPA
add-apt-repository ppa:dotnet/backports
# 按 Enter 确认

# 安装 .NET 8 SDK
apt install -y dotnet-sdk-8.0
```

添加 PPA 后，可以看到 Ubuntu 26.04 上提供的版本：

```
Ubuntu 26.04 LTS (Resolute Raccoon)
├── .NET 8.0 (EOL: November 10th, 2026) [amd64 arm64]
└── .NET 9.0 (EOL: November 10th, 2026) [amd64 arm64 s390x ppc64el]
```

你可以同时安装多个版本的 .NET，互不干扰。

## Ubuntu 26.04 值得关注的底层变化

原文提到了几个与 .NET 相关的系统层面变化：

- **Linux 7.0**：目前 .NET 团队正在等待实验室里的 Ubuntu 26.04 VM，近期会开始 Linux 7.0 测试
- **后量子密码学（Post-Quantum Cryptography）**：.NET 10 已[内置支持](https://devblogs.microsoft.com/dotnet/post-quantum-cryptography-in-dotnet/)，与 Ubuntu 26.04 的方向一致
- **cgroup v1 移除**：Ubuntu 26.04 去掉了 cgroup v1，.NET 早在多年前就完成了 [cgroup v2 支持](https://github.com/dotnet/runtime/issues/30337)，无需任何迁移操作

## CI 先行

.NET 团队在 2025 年初就开始在 CI 里测试 Ubuntu 24.10 和 Debian 13，2025 年底引入 Ubuntu 26.04。如今 `dotnet/runtime` 的每一个 PR 都会在 Ubuntu 26.04 上跑验证——也许是 Ubuntu 26.04 容器镜像使用量最大的项目之一。

这种提前投入使得 26.04 GA 当天的支持"自然而然"，而不是被动追赶。

## 参考

- [原文：What's new for .NET in Ubuntu 26.04](https://devblogs.microsoft.com/dotnet/whats-new-for-dotnet-in-ubuntu-2604/)
- [Ubuntu 26.04 发布公告](https://canonical.com/blog/canonical-releases-ubuntu-26-04-lts-resolute-raccoon)
- [dotnet-backports PPA](https://launchpad.net/~dotnet/+archive/ubuntu/backports)
- [.NET Ubuntu 24.04 同类文章](https://devblogs.microsoft.com/dotnet/whats-new-for-dotnet-in-ubuntu-2404/)
- [.NET Chiseled 容器](https://devblogs.microsoft.com/dotnet/announcing-dotnet-chiseled-containers/)
