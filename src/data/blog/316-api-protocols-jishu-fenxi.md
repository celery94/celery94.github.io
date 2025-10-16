---
pubDatetime: 2025-05-13
tags: ["Productivity", "Tools"]
slug: api-protocols-cheatsheet
source: ByteByteGo × Postman 海报“API Protocols”
author: ChatGPT
title: API协议全景速览 🚀
description: 一张图带你吃透 REST、GraphQL、gRPC、WebSocket、MQTT 等 11 种主流 API 技术的核心原理、最佳场景与对比优势。
---

# API协议技术全景图 🌐

> 「为什么同样是接口，REST、Webhooks、GraphQL、MQTT……五花八门？」本文基于 ByteByteGo × Postman 的 API Protocols 信息图，拆解 11 种常见协议/模式，从通信模型到典型落地场景一次说清。

---

## 1 总览：四大技术谱系 🧭

| 谱系              | 代表协议             | 特点                                    | 场景示例                      |
| ----------------- | -------------------- | --------------------------------------- | ----------------------------- |
| **同步请求-响应** | REST、GraphQL、SOAP  | 基于 HTTP/HTTPS，客户端发请求即刻拿结果 | Web/Mobile 业务接口、公开 SDK |
| **实时长连接**    | WebSocket、gRPC      | 建立持久通道，支持双向流                | 在线游戏、实时协作、流式 RPC  |
| **消息/事件驱动** | AMQP、MQTT、SSE、EDA | 异步解耦、高吞吐，支持广播/订阅         | IoT、交易撮合、日志采集       |
| **B2B 数据交换**  | EDI                  | 标准化业务文档，强调可靠合规            | 供应链、金融报文              |

---

## 2 同步请求-响应家族 🔁

### 2.1 REST 🍃

- **架构风格**：基于资源（URL）+ 标准 HTTP 动词（GET/POST/PUT/DELETE）。
- **优势**：简单、缓存友好、浏览器天然支持。
- **局限**：一次请求返回固定字段；多端需要版本迭代。

### 2.2 GraphQL 🪄

- **核心**：客户端声明查询，服务器按需返回，不多不少。
- **实现**：单一 `/graphql` 端点 + 类型系统 + 解析器 Resolver。
- **适用**：前端组件化、移动端省流量、多张表复杂聚合。

### 2.3 SOAP 📑

- **协议**：XML + WSDL 描述 + HTTP/SOAP Envelope。
- **亮点**：强类型契约、内置安全/事务扩展。
- **使用现状**：金融、政企遗留系统仍大量依赖。

### 2.4 Webhooks 🔔

- **本质**：服务器向回调 URL 主动 POST 事件。
- **关键点**：签名校验、防止重复投递、重试策略。
- **典型**：GitHub 推送触发 CI、支付成功通知业务后台。

---

## 3 实时长连接家族 ⚡

### 3.1 WebSocket 🕸

- **握手**：HTTP 升级 → tcp 持久连接 → 全双工帧。
- **适用**：IM、弹幕、股票行情。
- **对比 SSE**：双向 vs. 服务器单向推送。

### 3.2 gRPC 🚗

- **技术栈**：HTTP/2 + ProtoBuf + 代码生成 Stub。
- **模式**：支持四种流 (Unary - Streaming/双向 Streaming)。
- **优势**：高并发、低延时、强类型；语言/平台多。
- **注意**：浏览器要透过 gRPC-Web 或 envoy 转发。

---

## 4 消息/事件驱动家族 📣

### 4.1 SSE (Server-Sent Events) 📡

- **协议**：文本流 `text/event-stream`，单向推送。
- **超轻量**：浏览器内置 EventSource；断线自动重连。
- **应用**：监控看板、实时日志流。

### 4.2 AMQP 📨

- **组件**：Exchange（路由）+ Queue（缓冲）+ Bindings。
- **特性**：确认、重试、路由模式丰富 (fanout/topic)。
- **实现**：RabbitMQ、Azure Service Bus。

### 4.3 MQTT 📶

- **定位**：IoT 领域「蜂鸟型」协议，头部最小 2 Byte。
- **QoS**：0/1/2 级别，平衡性能与可靠性。
- **场景**：智能家居、电动车远程诊断。

### 4.4 EDA (Event-Driven Architecture) 🧩

- **概念**：用「事件」而非命令做系统分层，总线可选 Kafka/Pulsar。
- **优点**：解耦、可扩展、天然审计。
- **挑战**：一致性、事件溯源、幂等处理。

---

## 5 B2B 数据交换标准 📦

### EDI (Electronic Data Interchange) 🏢

- **内容**：采购单、发票等结构化文档（X12／EDIFACT）。
- **价值**：跨企业零人工、贯穿财务/物流。
- **实现**：专线/VPN + AS2，或云 EDI Gateway。

---

## 6 如何选型？🔑

| 诉求          | 推荐协议           | 备注                     |
| ------------- | ------------------ | ------------------------ |
| 标准 Web CRUD | REST / GraphQL     | 前者快上手，后者前端灵活 |
| 高吞吐 RPC    | gRPC               | 内网微服务首选           |
| 实时双向互动  | WebSocket          | 网络波动大时加心跳+重连  |
| IoT 低功耗    | MQTT               | QoS & Keep-Alive 调小    |
| 事件解耦      | AMQP / Kafka (EDA) | 关注消息一致性与可观测性 |
| 企业对接      | EDI / SOAP         | 兼顾法规与审计           |

---

## 7 小结 🏁

- **一图掌握 11 种协议**：从同步到流式，从消息到 B2B。
- **选型核心**：带宽/延迟、可靠性、生态支持、易用性。
- **最佳实践**：

  1. 明确域界限，一种系统尽量保持一种主协议。
  2. 使用 API Gateway / Proxy 做协议“翻译层”。
  3. 监控 + Trace，问题可追溯；幂等是事件系统生命线。

用好协议组合，就像用对螺丝刀和扳手：**没有银弹，只有合适**。祝你的服务接口既稳又快！
