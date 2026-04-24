---
pubDatetime: 2026-04-24T15:20:00+08:00
title: "Ubuntu 26.04 发布：.NET 10 开箱即用，Native AOT 启动只需 3 毫秒"
description: "Ubuntu 26.04 LTS（Resolute Raccoon）正式发布，内置 .NET 10 开箱即用。本文介绍如何安装 .NET 10、使用 resolute 容器镜像、用 Native AOT 构建 1.4 MB 自包含二进制，以及通过 backports PPA 安装 .NET 8/9。"
tags: [".NET", "Ubuntu", "Linux", "Docker", "Native AOT"]
slug: "whats-new-for-dotnet-in-ubuntu-2604"
ogImage: "../../assets/751/01-cover.png"
source: "https://devblogs.microsoft.com/dotnet/whats-new-for-dotnet-in-ubuntu-2604"
---

![Ubuntu Resolute Raccoon 抱着 .NET 徽标](../../assets/751/01-cover.png)

Ubuntu 26.04 LTS "Resolute Raccoon" 今天正式发布。按照惯例，每个新的 Ubuntu LTS 都会附带最新的 .NET LTS，这次是 .NET 10。两行命令就能装好：

```bash
sudo apt update
sudo apt install dotnet-sdk-10.0
```

.NET 是 Ubuntu 的[官方支持工具链](https://ubuntu.com/toolchains)之一，Microsoft 和 Canonical 持续合作保证 .NET 在 Ubuntu 上运行良好。这次，dotnet/runtime 团队从 2025 年初就开始在 CI 里测试 Debian 13 和 Ubuntu 24.10，到 2025 年底正式把 26.04 加入每个 PR 的验证流程，做到了发布当天开箱即用。

## 安装 .NET 10

在 `ubuntu:resolute` 容器里装 .NET 10 SDK：

```bash
$ docker run --rm -it ubuntu:resolute
$ apt update
$ apt install -y dotnet-sdk-10.0
$ dotnet --version
10.0.105
```

装好之后可以直接跑一段 C#。下面用的是 .NET 10 的 [file-based app](https://learn.microsoft.com/dotnet/core/sdk/file-based-apps) 配合 heredoc，把代码从 stdin 传给 `dotnet run`：

```bash
$ dotnet run - << 'EOF'
using System.Runtime.InteropServices;
Console.WriteLine($"Hello {RuntimeInformation.OSDescription} from .NET {RuntimeInformation.FrameworkDescription}");
EOF
Hello Ubuntu Resolute Raccoon (development branch) from .NET .NET 10.0.5
```

作者在文章里特别提到：AI agent 用 Python 经常这么写，其实 C# 同样支持这种 Unix 标准管道模式。

## 容器镜像

Ubuntu 26.04 的容器镜像本月已经上线，tag 从 `-noble` 改成了 `-resolute`。升级 Dockerfile 只需一条 sed：

```bash
$ grep dotnet/ Dockerfile.chiseled
FROM --platform=$BUILDPLATFORM mcr.microsoft.com/dotnet/sdk:10.0-noble AS build
FROM mcr.microsoft.com/dotnet/aspnet:10.0-noble-chiseled

$ sed -i "s/noble/resolute/g" Dockerfile.chiseled
```

替换完之后直接构建，加上资源限制运行：

```bash
docker build --pull -t aspnetapp -f Dockerfile.chiseled .
docker run --rm -it -p 8000:8080 -m 50mb --cpus .5 aspnetapp
```

[Chiseled 镜像](https://devblogs.microsoft.com/dotnet/announcing-dotnet-chiseled-containers/)（极度精简、去掉 shell 和包管理器的版本）在 26.04 上同样可用，使用方式与 24.04 完全一致。需要注意：容器使用的是宿主机内核，在 24.04 主机上跑 26.04 容器，内核仍然是 6.x。

## Native AOT

Ubuntu 26.04 提供了专门的 AOT 包，让构建自包含本地二进制更方便：

```bash
apt install -y dotnet-sdk-aot-10.0 clang
```

发布同一个 hello world 应用：

```bash
$ dotnet publish app.cs
$ du -h artifacts/app/*
1.4M    artifacts/app/app
3.0M    artifacts/app/app.dbg
```

二进制只有 **1.4 MB**，`.dbg` 是 native 符号文件（类似 Windows 的 PDB）。启动时间测试：

```bash
$ time ./artifacts/app/app
Hello Ubuntu Resolute Raccoon (development branch) from .NET .NET 10.0.5

real    0m0.003s
```

**3 毫秒**冷启动。

AOT 同样适合 Web 服务。用 [releasesapi 示例](https://github.com/dotnet/dotnet-docker/tree/main/samples/releasesapi)（已配置 `<PublishAot>true</PublishAot>`）：

```bash
$ dotnet publish
$ du -h bin/Release/net10.0/linux-x64/publish/releasesapi
13M     bin/Release/net10.0/linux-x64/publish/releasesapi
```

包含了大量 source-generated System.Text.Json 元数据的完整 Web 服务，自包含大小 13 MB。启动后可以直接查询：

```bash
$ curl -s http://localhost:5000/releases | jq '[.versions[] | select(.supported == true) | {version, supportEndsInDays}]'
[
  { "version": "10.0", "supportEndsInDays": 942 },
  { "version": "9.0",  "supportEndsInDays": 207 },
  { "version": "8.0",  "supportEndsInDays": 207 }
]
```

## 安装 .NET 8 和 9

Canonical 对"内置支持"和"可用性"做了明确区分：Ubuntu 26.04 内置 .NET 10，.NET 8 和 9 通过 [dotnet-backports PPA](https://launchpad.net/~dotnet/+archive/ubuntu/backports) 提供，属于"尽力支持"。

配置 PPA：

```bash
apt install -y software-properties-common
add-apt-repository ppa:dotnet/backports
apt update
```

配置完成后，可以按版本查看或安装各种包：

```bash
$ apt list dotnet-*8.0
dotnet-sdk-8.0/resolute 8.0.126-0ubuntu1~26.04.1~ppa1 amd64
...

$ apt list aspnetcore-runtime-*
aspnetcore-runtime-10.0/resolute 10.0.5-0ubuntu1 amd64
aspnetcore-runtime-8.0/resolute  8.0.26-0ubuntu1~26.04.1~ppa1 amd64
aspnetcore-runtime-9.0/resolute  9.0.15-0ubuntu1~26.04.1~ppa1 amd64
```

backports PPA 目前覆盖的版本：

| Ubuntu 版本 | 通过 PPA 可用的 .NET 版本 |
|---|---|
| 26.04 LTS | .NET 8.0、9.0 |
| 24.04 LTS | .NET 6.0、7.0、9.0 |
| 22.04 LTS | .NET 9.0、10.0 |

预计 .NET 11 正式发布时也会加入同一 PPA。

## 其他变化

Ubuntu 26.04 还带来了一些值得关注的底层变更：

- **Linux 7.0**：团队计划获得 26.04 VM 后尽快开始兼容性测试
- **后量子密码学**：.NET 10 已[添加支持](https://devblogs.microsoft.com/dotnet/post-quantum-cryptography-in-dotnet/)，与 26.04 的方向一致
- **cgroup v1 移除**：26.04 不再支持 cgroup v1，但 .NET 多年前已完整支持 cgroup v2，对运行中的容器应用影响为零

## 参考

- [What's new for .NET in Ubuntu 26.04 - .NET Blog](https://devblogs.microsoft.com/dotnet/whats-new-for-dotnet-in-ubuntu-2604)
- [Ubuntu 26.04 Release Notes](https://documentation.ubuntu.com/release-notes/26.04/summary-for-lts-users/)
- [dotnet-backports PPA](https://launchpad.net/~dotnet/+archive/ubuntu/backports)
- [Native AOT 文档](https://learn.microsoft.com/dotnet/core/deploying/native-aot)
