---
pubDatetime: 2025-08-11
tags: [".NET", "ASP.NET Core", "Architecture"]
slug: rest-api-design-mistakes
source: https://www.milanjovanovic.tech/blog/the-5-most-common-rest-api-design-mistakes-and-how-to-avoid-them
title: 五大常见REST API设计错误及其实战改进方案
description: 深入解析REST API设计中五个常见陷阱，结合糟糕版与改进版的真实案例与最佳实践，帮助开发者打造高质量、可维护的API。
---

# 五大常见REST API设计错误及其实战改进方案

在API开发的世界里，坏的设计会带来开发者体验下降、维护成本上升以及变更风险。而好的API设计不是盲目跟随所谓的“最佳实践”，而是在特定业务上下文中做出权衡，并长期保持一致性。本文将结合**真实案例**，剖析五个常见的REST API设计错误，并给出可落地的优化方案。

---

## 1. 命名和结构不一致

命名是API的第一印象。路径命名混乱、结构不一致，会迫使开发者频繁查阅文档，打断开发节奏。过深的URL嵌套会硬编码业务结构，降低灵活性。

**糟糕版**

```http
# 混乱的命名 + 深层嵌套
GET /getUserHabitEntriesList?UID=123&hID=456

[
  {"entryID": "1", "habitName": "Code review"},
  {"entryID": "2", "habitName": "Deep work"}
]
```

**改进版**

```http
# 统一复数名词 + 过滤替代深层嵌套
GET /entries?userId=123&habitId=456

{
  "data": [
    {"id": "1", "habitId": "code-review", "value": 5},
    {"id": "2", "habitId": "deep-work", "value": 2}
  ],
  "total": 42,
  "hasMore": true
}
```

✅ **要点**：

- 使用**复数名词**统一资源路径 (`/users`、`/tasks`)
- 仅在确有强依赖关系时嵌套路径
- 包裹数组响应，便于扩展分页等元信息

---

## 2. 版本策略不当

直接在路径加版本号（如 `/v1/users`）虽然常见，但会带来**多版本维护成本**：每个bug、补丁和文档都需要多份维护。

**糟糕版**

```http
GET /v1/users   # {id, name, email}
GET /v2/users   # {id, fullName, emailAddress}
GET /v3/users   # {id, firstName, lastName, email}
```

**改进版**

```http
GET /users/123

{
  "id": 123,
  "name": "John Doe",    // 旧字段保留
  "firstName": "John",   // 新增字段
  "lastName": "Doe"
}
```

必要时引入新资源而非破坏性升级：

```http
GET /userProfiles/123
```

✅ **要点**：

- 尽量**演进而非替换**字段
- 对新增功能使用**查询参数**
- 破坏性变更需提前公告并提供迁移指南

---

## 3. 忽视分页、过滤与搜索

数据量小的时候，`GET /tasks` 看似没问题，但上线后一次性返回上万条数据会拖垮性能与用户体验。

**糟糕版**

```http
GET /tasks

[
  {...}, {...}, ...
]
```

**改进版**

```http
# Cursor-based Pagination + 过滤
GET /tasks?status=active&limit=20&cursor=eyJpZCI6MTIzfQ==

{
  "data": [
    {"id": "1", "name": "Write docs", "status": "active"},
    {"id": "2", "name": "Fix bug", "status": "active"}
  ],
  "total": 52,
  "hasMore": true,
  "nextCursor": "eyJpZCI6NDU2fQ=="
}
```

搜索与过滤分开实现：

```http
GET /tasks/search?q=documentation
```

✅ **要点**：

- 分页应在API初期设计中实现
- 过滤与搜索分离，保证查询性能
- 推荐优先使用**Cursor-based Pagination** 保证一致性

---

## 4. 错误处理不清晰

错误信息如果只返回 `"An error occurred"`，会让客户端开发者摸不着头绪。

**糟糕版**

```json
{ "error": "An error occurred" }
```

**改进版（Problem Details 标准）**

```json
{
  "type": "https://api.example.com/errors/validation-failed",
  "title": "Validation Failed",
  "status": 400,
  "detail": "The request body contains invalid fields",
  "errors": [
    {
      "field": "name",
      "reason": "Must be between 1 and 100 characters",
      "value": ""
    }
  ]
}
```

✅ **要点**：

- 使用 [RFC 9457 Problem Details](https://datatracker.ietf.org/doc/html/rfc9457) 标准化错误结构
- 返回**错误原因**、**修复建议**和**关联字段**
- 使用正确的HTTP状态码（如400、404、429等）

---

## 5. 安全设计滞后

延迟安全实现往往会导致上线后补救困难，甚至产生数据泄露。

**糟糕版**

```http
GET /users  # 无认证保护
```

**改进版**

```http
GET /users
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6...

HTTP/1.1 429 Too Many Requests
Retry-After: 60
```

所有接口强制使用HTTPS：

```
https://api.example.com
```

✅ **要点**：

- 区分**认证**（你是谁）与**授权**（你能做什么）
- 实施**速率限制**（Rate Limiting）防止滥用
- 全面启用HTTPS，确保数据传输安全

---

## 总结

REST API设计是一种对使用者的承诺。命名一致性、合理的版本策略、完善的分页与搜索、清晰的错误处理以及从一开始就考虑安全，都是打造高质量API的必备条件。
构建**你自己也愿意使用的API**，不仅是对用户负责，也是对未来维护工作的最大善意。
