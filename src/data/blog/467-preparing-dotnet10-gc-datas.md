---
pubDatetime: 2025-09-29
title: 迎接 .NET 10 垃圾回收：DATAS 策略的评估与调优指南
description: DATAS 在 .NET 10 成为默认 Server GC 策略，将明显改变托管堆的容量与吞吐权衡。本文梳理设计原则、监控指标、关停条件与调优步骤，并给出容器与自托管环境的实用配置示例，帮助团队在升级前完成验证。
tags: [".NET", "Performance"]
slug: preparing-dotnet10-gc-datas
source: https://maoni0.medium.com/preparing-for-the-net-10-gc-88718b261ef2
---

# 迎接 .NET 10 垃圾回收：DATAS 策略的评估与调优指南

## 1. DATAS 成为默认行为意味着什么

在 .NET 运行时升级周期里，垃圾回收（GC）团队一贯遵循“升级即获益”的原则：只要安装新版本，绝大多数 GC 改进便会自动生效，无需开发者额外配置。原因在于这些改进往往面向广泛场景，团队会预先在多样化工作负载上压测，以确保收益覆盖面更大，即便偶有微基准表现回退也可接受。近年来对 Free Region 管理方式的调整，便是典型例子——它满足了主流应用需求，哪怕会改变极端基准测试的表现。

然而 DATAS（Dynamic Adaptation To Application Size）不同于以往的增量优化，它针对特定类型的工作负载（如内存受限容器、核心数差异巨大的部署）提供自适应策略，与“开箱即享”的传统 GC 改进相比更具侵入性。成为 .NET 10 Server GC 的默认策略后，它将显著改变内存曲线和吞吐行为，因此团队需要在升级前评估自身是否属于目标用户，并准备相应的监控与调优手段。

## 2. DATAS 如何重新定义 Server GC 的工作方式

传统 Server GC 并不试图根据应用规模调整堆大小，它主要依据各代的存活率决定何时触发回收，并假设分配行为在限定的堆规模内波动。结果是同一应用在 12 核与 28 核机器上的堆峰值可能差距巨大，因为 Server GC 会按可用核心数创建相同数量的堆段，初始阶段的吞吐与暂态分配差异会直接被放大。

DATAS 则引入了“基于应用规模计算的预算”（Budget Computed via DATAS，BCD），将代际预算上限与实时估算的 Live Data Size（LDS）绑定，再以“目标吞吐成本百分比”（Target Throughput Cost Percentage，TCP）约束 GC 开销。默认 TCP 设为 2%，意味着运行时时刻保持 GC 暂停时间约占总时间的 2%。当负载减轻时，DATAS 会主动收紧代际预算，驱动更频繁但更轻量的 GC，以便腾出堆空间；当负载加重时，预算放宽，避免因频繁回收拖慢吞吐。

文章中的两个示例很好地说明了这一点：在 28 核服务器上运行 ASP.NET 基准时，传统 Server GC 在初期分配阶段会出现高堆占用，而 DATAS 能让 12 核与 28 核下的最大堆尺寸趋于一致；在日间高峰与夜间低峰之间切换时，DATAS 会通过缩小 Gen0 预算，将堆收敛至更贴合实时需求的规模。这种自适应特性，正是 DATAS 在容器弹性场景中价值最大的原因。

## 3. 评估 DATAS 是否契合你的生产场景

若你的应用运行在专用机器上，堆占用长期被完全预算，且没有计划在非高峰时段运行额外任务，那么 DATAS 释放出来的内存无处可用，继续沿用传统 Server GC 也未尝不可。

如果启动时间是关键指标（例如对外提供低延迟请求的 API Gateway），需要注意 DATAS 总是以单堆启动，再根据压力逐步扩展堆数量；对极度敏感的场景，这段扩容时间可能构成不可接受的启动回退。同样地，对吞吐回退零容忍的系统，应结合 TCP 数据判断是否需要将目标值调低或干脆禁用该策略。

对于大量执行 Gen2 回收的应用（常见于频繁分配大型临时对象的服务），DATAS 当前的调优覆盖有限。若在试用后观察到长时间卡顿或内存震荡，可先撤回至传统模式，再评估是否值得投入时间进行深入调优。

## 4. 使用可观测性与配置驱动 DATAS 调优

当你决定调优 DATAS 时，第一步是建立可靠的观测链路。相比于单纯关注工作集，应该利用 GC 事件（如通过 TraceEvent 库解析 GCStats）来跟踪 BCD、LDS、Gen0 预算、暂停时间等指标，并结合 ASP.NET、数据库或自定义性能计数器进行相关性分析。上线前在对比环境分别采集“启用 DATAS”与“禁用 DATAS”的基线数据，可以快速识别真正由 DATAS 引起的波动。

重点观察两个信号：其一是 GC 次数是否显著增加，意味着 BCD 限制导致频繁回收；其二是“% Time in GC”是否逼近或超过目标 TCP。前者提示需要放宽预算，后者则说明 GC 暂停成本已偏高，需要降低负载或调紧 TCP。

配置方面，.NET 10 暴露了多项与 DATAS 相关的运行时配置。以下 `runtimeconfig.json` 片段展示了常见的调优组合：

```json
{
  "runtimeOptions": {
    "configProperties": {
      "GCDynamicAdaptationMode": 0,
      "GCDTargetTCP": 1.5,
      "GCDGen0GrowthPercent": 300,
      "GCDGen0GrowthMinFactor": 300
    }
  }
}
```

这里将 DATAS 的目标 TCP 下调至 1.5%，并把 Gen0 预算上限与最小系数提升为默认值的 2 倍左右，以减少频繁回收带来的吞吐损耗；若完全无法承受 DATAS 的影响，可将 `GCDynamicAdaptationMode` 设为 0 以禁用该策略。需要强调的是，配置调整必须与监控数据联动，否则容易掩盖真正的性能瓶颈。

在容器环境下，DATAS 能帮助你更精确地设定 Kubernetes 的 request/limit，或在 Fargate 等平台上决定任务扩缩策略；对自托管集群而言，它则意味着可以在夜间释放堆内存，为批处理、数据同步等任务窗口创造空间。只有明确这些业务收益，DATAS 的自适应性才会转化成团队的实际价值。

## 5. 升级 .NET 10 的建议路径

将 DATAS 纳入 .NET 10 升级计划时，应把“验证与决策”放在功能发布之前，而非升级完成后的事后补救。实践中可以按以下节奏推进：

1. 在性能测试环境模拟高峰与低峰负载，分别记录堆曲线、暂停占比、吞吐指标。
2. 结合 TraceEvent 或 dotnet-counters 导出的数据，分析是否触发了 DATAS 的 BCD 限制，并据此决定是否需要调整 TCP 或预算参数。
3. 确认业务上对腾出的内存有明确用途，再决定是否在生产环境启用 DATAS、调低目标 TCP 或退回传统 Server GC。

完成这些准备后，再把升级版本推广到生产环境，可以显著降低“升级后一周才发现资源不足或吞吐回退”的风险。

## 参考资料

- 原文：https://maoni0.medium.com/preparing-for-the-net-10-gc-88718b261ef2
- .NET GC 配置文档：https://learn.microsoft.com/en-us/dotnet/core/runtime-config/garbage-collector
