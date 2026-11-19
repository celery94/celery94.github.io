---
pubDatetime: 2026-11-19T09:30:05+08:00
title: ".NET 11 性能实测：JIT、异步与 AOT"
description: "在同一台 Windows 机器上，用可下载源码实测 .NET 10、.NET 11 默认、显式 Runtime Async 和 Native AOT 的吞吐与分配，保留原始数据及环境说明。"
tags: ["DotNet", "Performance", "NativeAOT"]
slug: "dotnet-11-runtime-performance"
ogImage: "../../assets/1141/01-cover.jpg"
source: "https://learn.microsoft.com/en-us/dotnet/core/whats-new/dotnet-11/runtime"
---

把选课对账服务从 .NET 10 搬到 .NET 11，延迟缩短时该归功于哪个变化？运行时和默认库一起升级，打开 Runtime Async 又会改变应用代码的编译方式，Native AOT 还会换一套发布产物。用同一段代码构建四份产物，可以避开把这些影响混在一起的测量。

本机用数组求和和一个立即完成的异步方法做了两组对照。数组循环的成绩接近。显式开启 Runtime Async 的那份产物在第二组里分配明显减少，吞吐也提高。这组结果只覆盖已完成的任务和微小计算，不能直接换算成 Web 请求延迟。

## 使用四份经单独构建的产物

前三份用 SDK 11.0.100 构建 Release，逐一用目标框架的运行时启动。默认的 .NET 11 不对项目显式设置 Runtime Async，运行时框架库自身可以使用这个特性。第四份发布成 `win-x64` 的 Native AOT 可执行文件，使用默认异步编译方式。

```xml
<PropertyGroup>
  <TargetFrameworks>net10.0;net11.0</TargetFrameworks>
  <Features Condition="'$(EnableRuntimeAsync)' == 'true'">
    runtime-async=on
  </Features>
</PropertyGroup>
```

用 `dotnet build --no-incremental` 逐次编译，输出目录各自独立。Native AOT 发布需要 Windows C++ 构建工具。同一 SDK 的构建命令可以复现本次对照，生产服务还应保存自己当前实际使用的 SDK 与运行时，验证最旧规格的虚拟机或 runner 具备所需指令集。[下载基准源码、脚本和原始数据](https://celery94.github.io/assets/1141/runtime-benchmark.zip)

```powershell
pwsh -NoProfile -File ./run.ps1
```

## 吞吐和分配都按单次操作记录

环境为 Intel Core i7-14700、Windows 11 Pro 26200、x64。每份产物单独运行一个进程。每个工作负载先进行 100,000 次热身，再测 7 轮，每轮 1,000,000 次。输出累加值用于核对四份产物执行的逻辑相同，计时不包括输出。分配用进程累计计数的差值，表里是各轮中位数，吞吐按百万次每秒四舍五入。

| 产物                      | 数组求和（百万次/秒） | 已完成的异步任务（百万次/秒） | 异步分配（字节/次） |
| ------------------------- | --------------------: | ----------------------------: | ------------------: |
| .NET 10.0.14 JIT          |                  29.2 |                          40.5 |                  72 |
| .NET 11.0.0 默认 JIT      |                  29.1 |                          42.6 |                  72 |
| .NET 11.0.0 Runtime Async |                  30.0 |                          80.1 |                   0 |
| .NET 11.0.0 Native AOT    |                  28.6 |                          66.4 |                  72 |

数组求和的分配四组均约为零。测试中的异步体等待 `Task.FromResult(42)`，它不产生真实 I/O 等待，也没有为负载加入多线程争用。AOT 二进制约 1.38 MB，测得的吞吐只对应程序热身后的循环，本次没有测冷启动或与包含运行时的自包含发布比较体积。JIT 的分层编译可能穿过热身阶段，CSV 保留了各轮波动。

## 决定是否把开关带到服务里

先在生产脚本能复现的负载测 .NET 10 和 .NET 11 默认配置。对业务指标同时记录响应尾延迟、数据库等待、CPU 和分配。如果默认版达标，再加一份只改变 Runtime Async 开关的产物，回归异常传播、取消、异步调用栈和第三方库互操作。

AOT 可以单独挑一个经源码生成支持的服务试跑。检查裁剪警告、反射使用、原生库和容器架构；把冷启动、稳定吞吐、常驻内存与镜像大小分开记录。发现回归时先切回已测过的默认 JIT 产物，保持上次验证过的配置和镜像摘要。

## 参考

- [.NET 11 Runtime Async、JIT 与硬件要求](https://learn.microsoft.com/en-us/dotnet/core/whats-new/dotnet-11/runtime)
- [微软 .NET 11 性能基准与实现说明](https://devblogs.microsoft.com/dotnet/performance-improvements-in-net-11/)
- [Native AOT 部署及先决条件](https://learn.microsoft.com/en-us/dotnet/core/deploying/native-aot/)
