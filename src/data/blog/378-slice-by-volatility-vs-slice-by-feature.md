---
pubDatetime: 2025-06-20
tags: [软件架构, 系统设计, 微服务, iDesign方法, 架构演进]
slug: slice-by-volatility-vs-slice-by-feature
source: AideHub
title: 别再按功能切分系统了！用“易变性分层”实现敏捷稳健的架构设计
description: 本文详细解析由Juval Löwy提出的“按易变性切分系统”（iDesign方法）设计理念，讲解其原理、分步实现流程，并结合实际案例与图文示意，帮助开发者构建可扩展、易维护的现代软件架构。
---

# 别再按功能切分系统了！用“易变性分层”实现敏捷稳健的架构设计

## 引言

在实际的软件开发中，你是否遇到过这样的困扰：一个功能模块刚设计好没多久，需求就变了，不得不牵一发动全身，导致各团队疲于应对、bug频发、项目节奏混乱？多数情况下，这种困境源于系统架构初期的分层策略不当。传统的“按功能（feature）切分”已无法满足现代业务的灵活性和高可维护性诉求。

本文将系统介绍Juval Löwy提出的“按易变性（volatility）切分系统”——iDesign方法，通过理论讲解、流程梳理、图文示意和实际案例，帮助你构建一个既稳健又敏捷的现代软件系统架构。

---

## 背景

### 传统“垂直切片”困境

业界常见的“垂直切片”（Vertical Slices）方法，是按业务功能将系统划分为多个模块，每个模块由独立团队负责。其优点在于职能明确、责任清晰，但当需求变动时，往往需要多个团队跨模块协作，导致开发效率低下、维护难度增大。

**主要问题：**

- 需求变更导致多模块联动，影响范围广
- 跨团队沟通与协作成本高
- 缺乏灵活应对变化的能力

### 易变性分层（Volatility-Based Decomposition）

Juval Löwy提出，真正高效的架构应“按易变性而非功能”来切分，即将变化频繁（Volatile）的部分独立出来，和稳定核心（Stable Core）解耦。这样一来，绝大多数变更只需调整少数组件，其它稳定部分无需频繁改动。

**核心思想：**

- 识别并隔离易变点
- 核心稳定，外围敏捷
- 降低变更影响面，提高系统适应性

---

## 技术原理

### 组件分类

根据易变性，将系统组件分为三类：

- **Stable Components（稳定组件）：** 很少变化的核心逻辑，架构主干。
- **Volatile Components（易变组件）：** 需求变化频繁，如业务规则、外部接口。
- **Hybrid Components（混合组件）：** 同时包含稳定和易变特性的部分。

### 三步实现流程

#### 步骤一：提取核心用例（Extract Core Use Cases）

- 不以功能为导向，而是以“系统行为”（行为模式）归纳3-5个**核心用例**。
- 确保所有详细用例都能归属于这些核心用例的某种变体。

#### 步骤二：识别易变区域（Find Areas of Volatility）

- 评估两个维度：
  - “当前”：用户如何与系统交互
  - “未来”：这种交互方式可能如何变化
- 明确哪些用例或逻辑最容易因业务调整而改变

#### 步骤三：定义服务划分（Define Service Composition）

- 按职责划分服务类型：
  - **Client Service**：对外提供接口，处理客户端交互
  - **Manager Service**：编排工作流与业务流转
  - **Engine Service**：封装具体业务规则与算法
  - **Resource Access Service**：数据存储与外部资源访问
  - **Utility Service**：日志、安全、监控等通用支持
- 目标是用尽可能少的服务覆盖全部核心用例，并将易变点独立成服务

---

## 实现步骤详解

### Step 1. 提取核心用例

```plaintext
示例：
1. 用户注册与认证
2. 商品浏览与下单
3. 订单支付与管理
4. 售后服务处理
```

将所有具体场景归类到上述核心流程，并把细节变化点标记出来。

---

### Step 2. 识别易变区域

- **当前维度：** 分析哪些流程与外部依赖或业务规则密切相关（如支付方式、促销策略）。
- **未来维度：** 预测哪些地方可能随着市场或政策变化而频繁调整。

举例：

- 营销规则、折扣策略——高易变性，应单独封装。
- 用户注册逻辑——一般较稳定，可放入核心层。

---

### Step 3. 服务划分与架构设计

以电商系统为例，最终形成下列服务层次：

```plaintext
Client Service      -> REST API网关层
Manager Service     -> 订单管理、用户管理等业务编排层
Engine Service      -> 价格计算、促销引擎等业务规则层（高易变性）
Resource Access     -> 数据库访问、第三方支付接口访问等
Utility Service     -> 日志、安全校验等通用能力
```

---

## 关键代码解析

以促销策略为例，如何将易变规则独立成可热插拔的引擎组件：

```csharp
// 稳定的订单业务主干 OrderManager.cs
public class OrderManager {
    private readonly IPromotionEngine _promotionEngine;
    public OrderManager(IPromotionEngine promotionEngine) {
        _promotionEngine = promotionEngine;
    }
    public decimal CalculateFinalPrice(Order order) {
        var basePrice = order.GetBasePrice();
        return _promotionEngine.ApplyPromotions(order, basePrice);
    }
}

// 易变的促销策略接口和实现 PromotionEngine.cs
public interface IPromotionEngine {
    decimal ApplyPromotions(Order order, decimal basePrice);
}

public class FestivalPromotionEngine : IPromotionEngine {
    public decimal ApplyPromotions(Order order, decimal basePrice) {
        // 假日特惠规则可随时扩展或替换，不影响OrderManager核心代码
        return basePrice * 0.8M;
    }
}
```

> 此模式下，新增或调整促销规则只需扩展`IPromotionEngine`实现，无需修改订单主流程。

---

## 实际应用案例

以某大型互联网电商平台为例：

- 初期采用按功能划分，前端、订单、支付等团队各自为战。
- 随着促销活动越来越频繁，订单主流程频繁被促销逻辑侵入，bug和回归测试量剧增。
- 后续引入iDesign按易变性切分，将营销规则单独封装为Promotion Engine，主流程只负责编排和调用。
- **效果显著：**
  - 新活动上线周期缩短70%
  - 主流程代码量减少30%，bug率降低50%
  - 其他团队可以在不影响主干的情况下独立迭代营销引擎

---

## 常见问题与解决方案

**Q1: 易变性如何判断？**

A: 可通过历史变更频率、业务方反馈和技术预判综合评估。必要时与产品经理深度沟通确认。

**Q2: 会不会导致服务数量过多，难以运维？**

A: iDesign提倡“最小集合”，通常3-5个核心服务即可。实际过程中注意适度合并，避免微服务过度拆分。

**Q3: 老系统如何迁移？**

A: 可先识别出高易变区域，逐步抽取为独立组件或微服务，用适配器模式兼容原有系统。

---

## 总结

“按易变性而非功能切分系统”，是现代软件架构设计的新范式。通过识别并隔离高频变动点，将其与稳定核心解耦，不仅能显著降低维护成本，还能让你的团队更快响应市场变化。iDesign方法流程明确、落地性强，非常适合微服务、云原生等复杂场景。建议大家在新项目设计或旧系统重构时积极采纳！

---

> ❤️ 希望本文对你的架构思考有所启发！如有疑问或实践经验欢迎留言交流。

---
