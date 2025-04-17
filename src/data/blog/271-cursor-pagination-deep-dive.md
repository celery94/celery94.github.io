---
pubDatetime: 2025-04-17 09:13:35
tags: [数据库优化, 游标分页, 性能提升, 后端开发, PostgreSQL]
slug: cursor-pagination-deep-dive
source: https://www.milanjovanovic.tech/blog/understanding-cursor-pagination-and-why-its-so-fast-deep-dive
title: “游标分页”风暴来袭：数据库高效分页的秘密武器，你还在用“慢吞吞”的Offset吗？
description: 深度剖析游标分页（Cursor Pagination）与传统偏移分页（Offset Pagination）在大数据场景下的性能差异，结合PostgreSQL真实执行计划、代码示例与优化技巧，带你掌握API接口高性能分页的最佳实践，助力后端开发能力升级！
---

# “游标分页”风暴来袭：数据库高效分页的秘密武器，你还在用“慢吞吞”的Offset吗？🚀

## 开篇引入：数据洪流时代，你的接口还“卡”在第10万页吗？

在5G、AI、大数据席卷全球的今天，无论是社交媒体的信息流、金融系统的交易明细，还是各类后台管理系统，**海量数据的高效处理**已成为每个后端工程师绕不开的核心话题。想象一下，当用户滑动到你的产品“第1000页”数据时，接口响应速度骤降，卡顿成灾——你真的甘心吗？

> 🎯 **问题直击：**
>
> 为什么你的分页API总是“慢半拍”？如何让数据分页既快又稳，还能应对实时性和大并发挑战？游标分页到底强在哪里？

今天，我们就用一组真实的PostgreSQL执行计划、代码实例和性能对比，深度解析**游标分页（Cursor Pagination）**如何成为数据库世界里最流行的“黑科技”！

---

## 技术背景介绍：偏移分页&游标分页，一文看懂核心区别

### 1️⃣ 偏移分页（Offset Pagination）：简单直观，却慢到想哭！

- **定义**：通过`OFFSET`和`LIMIT`跳过指定条数后取数据（常见于`Skip`+`Take`操作）。
- **优势**：实现简单，支持直接跳转任意页码。
- **劣势**：数据量大时，查询性能急剧下降；并发或动态数据下可能出现数据遗漏或重复。

#### 代码&SQL示例

```csharp
// C#偏移分页实现
var items = await dbContext.UserNotes
    .OrderByDescending(x => x.Date)
    .ThenByDescending(x => x.Id)
    .Skip((page - 1) * pageSize)
    .Take(pageSize)
    .ToListAsync();
```

```sql
-- SQL执行示例
SELECT u.id, u.date, u.note, u.user_id
FROM user_notes AS u
ORDER BY u.date DESC, u.id DESC
LIMIT 1000 OFFSET 900000;
```

> 💡 **性能陷阱**：OFFSET越大，数据库需扫描、丢弃大量无用数据——分页越深，越慢！

---

### 2️⃣ 游标分页（Cursor Pagination）：面向性能的“高能选手”

- **定义**：基于唯一标识（如时间戳+ID组合），每次查询传入上次返回的“游标”，直接定位下一批数据。
- **优势**：大数据量下性能稳定（无论第几页），不会遗漏/重复数据；特别适合实时信息流、无限滚动等场景。
- **劣势**：实现复杂，无法直接跳转任意页，不便统计总页数。

#### 代码&SQL示例

```csharp
// C#游标分页实现
if (date != null && lastId != null)
{
    query = query.Where(x => x.Date < date || (x.Date == date && x.Id <= lastId));
}
var items = await query
    .OrderByDescending(x => x.Date)
    .ThenByDescending(x => x.Id)
    .Take(limit + 1)
    .ToListAsync();
```

```sql
-- SQL执行示例
SELECT u.id, u.date, u.note, u.user_id
FROM user_notes AS u
WHERE u.date < @date OR (u.date = @date AND u.id <= @lastId)
ORDER BY u.date DESC, u.id DESC
LIMIT 1000;
```

---

## 案例分析：百万级大表实测，游标分页到底有多快？

### PostgreSQL执行计划实录——Offset vs Cursor

#### 📉 Offset分页执行结果（跳过90万条）

```text
Execution Time: 704.217 ms
```

#### 🚀 Cursor分页执行结果（同样条件）

```text
Execution Time: 40.993 ms
```

#### ⚡ Tuple索引优化后的Cursor分页

引入组合索引+元组比较后，性能爆表：

```sql
-- 创建降序组合索引
CREATE INDEX idx_user_notes_date_id ON user_notes (date DESC, id DESC);

-- 利用元组比较
WHERE (u.date, u.id) <= (@date, @lastId)
```

```text
Execution Time: 0.668 ms
```

> ✅ **实测结论**：游标分页配合索引优化，百万数据瞬间响应！对比Offset高达17倍以上性能提升。

---

## 实用技巧：高性能游标分页如何落地？

### 1️⃣ 游标编码/解码——安全且易用

前端拿到的数据游标应采用Base64编码，保证安全性与可传递性：

```csharp
public static string Encode(DateOnly date, string lastId) { /*...*/ }
public static Cursor? Decode(string? cursor) { /*...*/ }
```

### 2️⃣ EF Core元组比较与索引利用

EF Core支持ValueTuple元组比较，能自动走索引：

```csharp
query = query.Where(x => EF.Functions.LessThanOrEqual(
    ValueTuple.Create(x.Date, x.Id),
    ValueTuple.Create(date, lastId)));
```

### 3️⃣ 场景选择指南

| 分页方式 | 优点               | 缺点               | 最佳场景                          |
| -------- | ------------------ | ------------------ | --------------------------------- |
| Offset   | 实现简单、跳页灵活 | 性能差、易漏/重复  | 小型管理后台、低并发小表          |
| Cursor   | 性能极佳、稳定可靠 | 无法跳页、实现复杂 | 社交信息流、大型实时日志、API接口 |

---

## 趋势预测：“流式数据”与API高并发场景下，Cursor Pagination必成主流

随着移动端无限滚动、实时推荐算法、社交网络时间线等产品设计流行，对数据接口性能与稳定性的要求水涨船高。未来，无论是Web还是移动App，**游标分页都将成为API设计不可或缺的“硬核技术”**。尤其在AI、区块链等新兴领域，流式分页将成为底层基础能力。
