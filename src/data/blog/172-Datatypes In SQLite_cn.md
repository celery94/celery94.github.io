---
pubDatetime: 2024-08-13
tags: ["Productivity", "Tools"]
source: https://www.sqlite.org/datatype3.html
author: SQLite
title: SQLite中的数据类型
description: SQLite中的数据类型
---

## 1. SQLite中的数据类型

大多数SQL数据库引擎（据我们所知，除了SQLite外的所有SQL数据库引擎）使用静态的、严格的类型。在静态类型中，值的数据类型由其容器决定，即存储该值的特定列。

SQLite使用更为通用的动态类型系统。在SQLite中，值的数据类型与值本身相关，而不是与其容器相关。SQLite的动态类型系统与其他数据库引擎中更普遍的静态类型系统向后兼容，因为在静态类型数据库上工作的SQL语句在SQLite中也能同样工作。然而，SQLite的动态类型使其能执行一些传统严格类型数据库中不可能实现的操作。[灵活的类型是一种特性](https://www.sqlite.org/flextypegood.html)，而不是一个bug。

更新：自版本3.37.0（2021-11-27）起，SQLite提供了[STRICT表](https://www.sqlite.org/stricttables.html)，对喜欢这种功能的开发者进行了严格类型强制执行。

## 2. 存储类和数据类型

存储在SQLite数据库中的每一个值（或被数据库引擎操作的值）都有如下的存储类型之一：

- **NULL**。值为NULL。
- **INTEGER**。值是一个有符号整数，根据值的大小存储在0、1、2、3、4、6或8字节中。
- **REAL**。值是一个浮点数，作为一个8字节的IEEE浮点数存储。
- **TEXT**。值是一个文本字符串，使用数据库编码（UTF-8、UTF-16BE或UTF-16LE）存储。
- **BLOB**。值是一个数据块，完全按照输入的方式存储。

存储类比数据类型更为通用。比如，存储类 INTEGER 包括了七种不同长度的整数数据类型。[这在磁盘上有差异。](https://www.sqlite.org/fileformat2.html#record_format) 但当INTEGER值从磁盘读到内存中处理时，它们被转换为最通用的数据类型（8字节有符号整数）。因此在大多数情况下，"存储类"和"数据类型"是不可区分的，这两个术语可以互换使用。

除了[INTEGER PRIMARY KEY](https://www.sqlite.org/lang_createtable.html#rowid)列以外，SQLite版本3数据库中的任何列都可以用于存储任何存储类的值。

所有SQL语句中的值，无论是嵌入在SQL语句文本中的字面值，还是绑定到[预编译SQL语句](https://www.sqlite.org/c3ref/stmt.html)的[参数](https://www.sqlite.org/lang_expr.html#varparam)，都有一个隐含的存储类。在下面描述的情况下，数据库引擎可能在查询执行期间在数值存储类（INTEGER和REAL）和TEXT之间进行转换。

## 2.1. 布尔数据类型

SQLite没有单独的布尔存储类。相反，布尔值作为整数0（false）和1（true）存储。

从版本3.23.0（2018-04-02）开始，SQLite识别关键词"TRUE"和"FALSE"，但这些关键词实际上只是整数字面量1和0的替代拼写。

## 2.2. 日期和时间数据类型

SQLite没有专门用于存储日期和/或时间的存储类。相反，SQLite内置的[日期和时间函数](https://www.sqlite.org/lang_datefunc.html)能够将日期和时间存储为TEXT、REAL或INTEGER值：

- **TEXT** 作为ISO8601字符串（"YYYY-MM-DD HH:MM:SS.SSS"）。
- **REAL** 作为儒略日数，即公元前4714年11月24日中午到当前所经过的天数。
- **INTEGER** 作为Unix时间，即自1970-01-01 00:00:00 UTC以来的秒数。

应用程序可以选择以任何这些格式存储日期和时间，并使用内置的[日期和时间函数](https://www.sqlite.org/lang_datefunc.html)在这些格式之间自由转换。

## 3. 类型亲和性

使用严格类型的SQL数据库引擎通常会尝试自动将值转换为适当的数据类型。考虑以下示例：

> ```
> CREATE TABLE t1(a INT, b VARCHAR(10));
> INSERT INTO t1(a,b) VALUES('123',456);
> ```

严格类型的数据库会在插入操作之前，将字符串'123'转换成整数123，而将整数456转换成字符串'456'。

为了最大化SQLite与其它数据库引擎的兼容性，并使上述示例在SQLite中如同在其他SQL数据库引擎中一样工作，SQLite支持列的“类型亲和性”概念。列的类型亲和性是存储在该列中的数据的推荐类型。这里的重要思想是类型是推荐的，而不是强制的。任何列仍然可以存储任何类型的数据。只是某些列在可能的情况下更倾向于使用一种存储类而不是另一种。列的首选存储类称为其“亲和性”。

SQLite 3数据库中的每列都分配以下类型亲和性之一：

- TEXT
- NUMERIC
- INTEGER
- REAL
- BLOB

（历史注：亲和性"BLOB"以前称为"NONE"。但这个术语容易与“没有亲和性”混淆，因此更改为“BLOB”。）

TEXT亲和性的列使用存储类 NULL、TEXT 或 BLOB 存储所有数据。如果将数值数据插入TEXT亲和性的列中，它将被转换为文本形式后存储。

NUMERIC亲和性的列可以包含所有五种存储类的值。当文本数据插入带有NUMERIC亲和性的列中，如果文本是格式正确的整数或实数字面量，文本的存储类会分别转换为 INTEGER 或 REAL（按优先顺序）。如果TEXT值为格式正确的整数字面量但大到不能放入64位有符号整数中，它会转换为REAL。对于文本和 REAL 存储类之间的转换，只有前15个有效小数位被保留。如果TEXT值不是格式正确的整数或实数字面量，则值将作为TEXT存储。为实现本段目的，十六进制整数字面量不被视为格式正确的，因此它们作为TEXT存储。（这是为了与SQLite在 [版本3.8.6](https://www.sqlite.org/releaselog/3_8_6.html) 2014-08-15 之前的一致，而在此版本中首次引入十六进制整数字面量到SQLite。）如果一个浮点值能够精确表示为整数且插入带NUMERIC亲和性的列中，则该值转换为整数。不对 NULL 或 BLOB 值进行转换尝试。

一个字符串可能看起来像一个带有小数点和/或指数符号的浮点字面量，但只要该值能够表示为整数，NUMERIC亲和性会将其转换为整数。因此，字符串'3.0e+5' 存储在带有NUMERIC亲和性的列中时，会被存储为整数300000，而不是浮点值300000.0。

使用INTEGER亲和性的列行为与NUMERIC亲和性列相同。INTEGER和NUMERIC亲和性的差异仅在[CAST 表达式](https://www.sqlite.org/lang_expr.html#castexpr)中显现：“CAST(4.0 AS INT)” 表达式返回整数4，而“CAST(4.0 AS NUMERIC)”保持浮点值4.0不变。

带REAL亲和性的列行为像NUMERIC亲和性的列，除了它将整数值强制为浮点表示。（作为一种内部优化，在浮点数中没有小数部分的小浮点值存储在带REAL亲和性的列中时，会作为整数写入磁盘以占用更少的空间，并在读取值时自动转换回浮点数。这种优化在SQL层面完全不可见，只有通过检查数据库文件的原始位才能发现。）

带BLOB亲和性的列不会偏袒一种存储类，并且不会尝试将数据从一种存储类强制转换为另一种。

## 3.1. 列亲和性的确定

对于未声明为[STRICT](https://www.sqlite.org/stricttables.html)的表，列的亲和性由列的声明类型决定，按照以下规则依次确定：

1. 如果声明类型包含字符串“INT”，则将其分配为INTEGER亲和性。
2. 如果列的声明类型包含字符串“CHAR”、“CLOB”或“TEXT”，则该列具有TEXT亲和性。请注意，类型VARCHAR包含字符串“CHAR”，因此被分配为TEXT亲和性。
3. 如果列的声明类型包含字符串“BLOB”或未指定类型，则该列具有BLOB亲和性。
4. 如果列的声明类型包含字符串“REAL”、“FLOA”或“DOUB”，则该列具有REAL亲和性。
5. 否则，亲和性为NUMERIC。

请注意，确定列亲和性的规则顺序是重要的。声明类型为“CHARINT”的列将同时匹配准则1和准则2，但第一个规则优先，因此列亲和性将为INTEGER。

### 3.1.1. 亲和性名称示例

下表展示了从更传统的SQL实现中，如何将许多常见的数据类型名称通过前一部分的五条规则转换为亲和性。该表仅展示了SQLite会接受的数据类型名称的一小部分。注意，跟在类型名称之后的数值参数（例如“VARCHAR(255)”） 被SQLite忽略 － SQLite不对字符串、BLOB或数值的长度限制（除了大的全局 [SQLITE_MAX_LENGTH](https://www.sqlite.org/limits.html#max_length) 限制）施加任何长度限制。

> |  
> CREATE TABLE 语句或 CAST 表达式中的示例类型名 | 产生的亲和性 | 确定亲和性的规则 |
> | --- | --- | --- |
> | INT  
> INTEGER  
> TINYINT  
> SMALLINT  
> MEDIUMINT  
> BIGINT  
> UNSIGNED BIG INT  
> INT2  
> INT8 | INTEGER | 1 |
> | CHARACTER(20)  
> VARCHAR(255)  
> VARYING CHARACTER(255)  
> NCHAR(55)  
> NATIVE CHARACTER(70)  
> NVARCHAR(100)  
> TEXT  
> CLOB | TEXT | 2 |
> | BLOB  
> 没有指定类型 | BLOB | 3 |
> | REAL  
> DOUBLE  
> DOUBLE PRECISION  
> FLOAT | REAL | 4 |
> | NUMERIC  
> DECIMAL(10,5)  
> BOOLEAN  
> DATE  
> DATETIME | NUMERIC | 5 |

注意，声明类型为“FLOATING POINT”将赋予INTEGER亲和性，而不是REAL亲和性，这是由于“POINT”中的“INT”。而声明类型为“STRING”则具有NUMERIC亲和性，而非TEXT亲和性。

## 3.2. 表达式的亲和性

每个表列都有其特定的类型亲和性（BLOB、TEXT、INTEGER、REAL或NUMERIC），但表达式不一定有亲和性。

表达式的亲和性由以下规则确定：

- IN或 NOT IN 运算符的右侧运算数如果是一个列表，则没有亲和性；如果运算数是一个SELECT，那么它具有与结果集表达式相同的亲和性。
- 当一个表达式是对真实表中的一个列的简单引用（而不是 [VIEW](https://www.sqlite.org/lang_createview.html)或子查询），则该表达式具有与表列相同的亲和性。

  - 括号内的列名会被忽略。因此，如果X和Y.Z是列名，则（X）和（Y.Z）也会被认为是列名，并具有相应列的亲和性。
  - 任何应用于列名的运算符，包括不做操作的一元“+”运算符，都会将列名转换为没有亲和性的表达式。因此，即使X和Y.Z是列名，表达式+X和+Y.Z也不是列名，并且没有亲和性。

- 表达式形式为“CAST(_expr_ AS _type_)”的表达式具有与声明类型为“_type_”的列相同的亲和性。
- 一个COLLATE 运算符具有与其左操作数相同的亲和性。
- 除此以外，一个表达式没有亲和性。

## 3.3. 视图和子查询的列亲和性

[视图](https://www.sqlite.org/lang_createview.html)或FROM子句子查询的“列”实际上是实现视图或子查询的 [SELECT](https://www.sqlite.org/lang_select.html) 语句结果集中的表达式。因此，视图或子查询的列的亲和性由上面的表达式亲和性规则决定。考虑以下示例：

> ```sql
> CREATE TABLE t1(a INT, b TEXT, c REAL);
> CREATE VIEW v1(x,y,z) AS SELECT b, a+c, 42 FROM t1 WHERE b!=11;
> ```

v1.x 列的亲和性将与 t1.b 的亲和性相同（TEXT），因为 v1.x 直接映射到 t1.b。但是，列 v1.y 和 v1.z 都没有亲和性，因为这些列映射到表达式 a+c 和 42，并且表达式始终没有亲和性。

### 3.3.1. 复合视图的列亲和性

当实现 [VIEW](https://www.sqlite.org/lang_createview.html) 或FROM子句子查询的 [SELECT](https://www.sqlite.org/lang_select.html) 语句是[复合SELECT](https://www.sqlite.org/lang_select.html#compound)时，视图或子查询每列的亲和性将是组成复合的个别SELECT语句之一的对应结果列的亲和性。然而，尚未知哪一个SELECT语句将用于确定亲和性。在查询评估期间，不同的个别SELECT语句可能会用于确定亲和性。选择可能因SQLite的不同版本而异。同一个SQLite版本中的一个查询和另一个查询之间的选择可能会改变。同一查询中的选择可能在不同时间点不同。因此，您永远无法确定在构成子查询中的复合SELECT中有不同亲和性的列会使用哪种亲和性。

如果您关心结果的数据类型，最好的做法是避免在复合SELECT中混用亲和性。混合使用复合SELECT的亲和性可能会导致令人惊讶和难以预料的结果。例如，参见[论坛帖子 02d7be94d7](https://sqlite.org/forum/forumpost/02d7be94d7)。

## 3.4. 列亲和性行为示例

以下SQL展示了当值插入到表中时，SQLite如何使用列亲和性进行类型转换。

> ```sql
> CREATE TABLE t1(
>     t  TEXT,     -- 通过规则2，text亲和性
>     nu NUMERIC,  -- 通过规则5，numeric亲和性
>     i  INTEGER,  -- 通过规则1，integer亲和性
>     r  REAL,     -- 通过规则4，real亲和性
>     no BLOB      -- 通过规则3，no亲和性
> );
>
> -- 值分别存储为 TEXT, INTEGER, INTEGER, REAL, TEXT。
> INSERT INTO t1 VALUES('500.0', '500.0', '500.0', '500.0', '500.0');
> SELECT typeof(t), typeof(nu), typeof(i), typeof(r), typeof(no) FROM t1;
> text|integer|integer|real|text
>
> -- 值分别存储为 TEXT, INTEGER, INTEGER, REAL, REAL。
> DELETE FROM t1;
> INSERT INTO t1 VALUES(500.0, 500.0, 500.0, 500.0, 500.0);
> SELECT typeof(t), typeof(nu), typeof(i), typeof(r), typeof(no) FROM t1;
> text|integer|integer|real|real
>
> -- 值分别存储为 TEXT, INTEGER, INTEGER, REAL, INTEGER。
> DELETE FROM t1;
> INSERT INTO t1 VALUES(500, 500, 500, 500, 500);
> SELECT typeof(t), typeof(nu), typeof(i), typeof(r), typeof(no) FROM t1;
> text|integer|integer|real|integer
>
> -- BLOB总是作为BLOB存储，无论列亲和性如何。
> DELETE FROM t1;
> INSERT INTO t1 VALUES(x'0500', x'0500', x'0500', x'0500', x'0500');
> SELECT typeof(t), typeof(nu), typeof(i), typeof(r), typeof(no) FROM t1;
> blob|blob|blob|blob|blob
>
> -- NULL也不受亲和性的影响
> DELETE FROM t1;
> INSERT INTO t1 VALUES(NULL,NULL,NULL,NULL,NULL);
> SELECT typeof(t), typeof(nu), typeof(i), typeof(r), typeof(no) FROM t1;
> null|null|null|null|null
> ```

## 4. 比较表达式

SQLite 3 版本提供了常见的 SQL 比较运算符，包括 "="、"== "、"<"、"<="、">"、">="、"!="、""、"IN"、"NOT IN"、"BETWEEN"、"IS" 和 "IS NOT"。

## 4.1. 排序规则

比较结果取决于操作数的存储类，根据以下规则：

- 存储类为 NULL 的值被认为比任何其他值（包括其他存储类为 NULL 的值）小。
- INTEGER 或 REAL 值比任何 TEXT 或 BLOB 值小。当 INTEGER 或 REAL 与另一个 INTEGER 或 REAL 比较时，会进行数值比较。
- TEXT 值比 BLOB 值小。当两个 TEXT 值进行比较时，会使用适当的排序序列来确定结果。
- 当两个 BLOB 值进行比较时，结果由 memcmp() 确定。

## 4.2. 比较前的类型转换

在进行比较之前，SQLite 可能会尝试在存储类 INTEGER、REAL 和/或 TEXT 之间转换值。是否在比较前进行转换取决于操作数的类型亲和性。

"应用亲和性" 意味着如果且仅如果转换不会丢失重要信息，就将操作数转换为特定的存储类。数值总是可以转换为 TEXT。如果 TEXT 内容是格式良好的整数或实数文本，则可以转换为数值，而十六进制整数文本则不能。BLOB 值通过简单地将二进制 BLOB 内容解释为当前数据库编码的文本字符串来转换为 TEXT 值。

在比较操作符的操作数上应用亲和性之前，会按照以下规则依次进行：

- 如果一个操作数具有 INTEGER、REAL 或 NUMERIC 亲和性，而另一个操作数具有 TEXT 或 BLOB 或无亲和性，则对另一个操作数应用 NUMERIC 亲和性。
- 如果一个操作数具有 TEXT 亲和性，而另一个操作数无亲和性，则对另一个操作数应用 TEXT 亲和性。
- 否则，不应用任何亲和性，并按原样比较两个操作数。

表达式 "a BETWEEN b AND c" 被视为两个独立的二元比较 "a >= b 和 a <= c"，即使这意味着在每次比较中对 'a' 应用不同的亲和性。形式为 "x IN (SELECT y ...)" 的比较中的数据类型转换处理方式与 "x=y" 实际上相同。表达式 "a IN (x, y, z, ...)" 等价于 "a = +x OR a = +y OR a = +z OR ..."，换句话说，IN 在右侧的值（在本例中是 "x"、"y" 和 "z" 值）被视为没有亲和性，即使它们恰好是列值或 CAST 表达式。

## 4.3. 比较示例

> ```sql
> CREATE TABLE t1(
>     a TEXT,      -- 文本亲和性
>     b NUMERIC,   -- 数值亲和性
>     c BLOB,      -- 无亲和性
>     d            -- 无亲和性
> );
>
> -- 值将分别存储为 TEXT、INTEGER、TEXT 和 INTEGER
> INSERT INTO t1 VALUES('500', '500', '500', 500);
> SELECT typeof(a), typeof(b), typeof(c), typeof(d) FROM t1;
> text|integer|text|integer
>
> -- 因为列 "a" 具有文本亲和性，所以比较右侧的数值将被转换为文本，然后再进行比较。
> SELECT a < 40, a < 60, a < 600 FROM t1;
> 0|1|1
>
> -- 对右侧操作数应用文本亲和性，但由于它们已经是 TEXT，所以这是一个无操作；没有发生转换。
> SELECT a < '40', a < '60', a < '600' FROM t1;
> 0|1|1
>
> -- 列 "b" 具有数值亲和性，因此对右侧操作数应用数值亲和性。由于操作数已经是数值，因此亲和性的应用是无效操作；没有发生转换。所有值都进行数值比较。
> SELECT b < 40, b < 60, b < 600 FROM t1;
> 0|0|1
>
> -- 对右侧操作数应用数值亲和性，将它们从文本转换为整数。然后进行数值比较。
> SELECT b < '40', b < '60', b < '600' FROM t1;
> 0|0|1
>
> -- 没有发生亲和性转换。右侧值的存储类为 INTEGER，而 INTEGER 总是比左侧的 TEXT 小。
> SELECT c < 40, c < 60, c < 600 FROM t1;
> 0|0|0
>
> -- 没有发生亲和性转换。值作为 TEXT 进行比较。
> SELECT c < '40', c < '60', c < '600' FROM t1;
> 0|1|1
>
> -- 没有发生亲和性转换。右侧值的存储类为 INTEGER，与左侧的 INTEGER 进行数值比较。
> SELECT d < 40, d < 60, d < 600 FROM t1;
> 0|0|1
>
> -- 没有发生亲和性转换。左侧的 INTEGER 值总是比右侧的 TEXT 值小。
> SELECT d < '40', d < '60', d < '600' FROM t1;
> 1|1|1
> ```

所有示例中的结果在比较交换时都相同——即将表达式 "a<40" 重写为 "40>a"。

## 5. 运算符

数学运算符（+、-、\*、/、% 、<<、>>、& 和 |）将两个操作数都视为数字。STRING 或 BLOB 操作数会自动转换为 REAL 或 INTEGER 值。如果 STRING 或 BLOB 看起来像实数（如果有小数点或指数），或者其值超出了 64 位有符号整数可以表示的范围，则转换为 REAL。否则，操作数转换为 INTEGER。数学运算符的隐含类型转换与 [CAST 到 NUMERIC](https://www.sqlite.org/lang_expr.html#castexpr) 略有不同，字符串和 BLOB 值看起来像实数但没有小数部分时保持为 REAL，而不像转换为 [CAST 到 NUMERIC](https://www.sqlite.org/lang_expr.html#castexpr) 时那样转换为 INTEGER。即使转换是有损且不可逆的，也会将 STRING 或 BLOB 转换为 REAL 或 INTEGER。一些数学运算符（% 、<< 、>> 、& 和 |）需要 INTEGER 操作数。对于这些运算符，REAL 操作数按照 [CAST 到 INTEGER](https://www.sqlite.org/lang_expr.html#castexpr) 的方式转换为 INTEGER。<<、>>、& 和 | 运算符总是返回 INTEGER（或 NULL）结果，但 % 运算符根据其操作数的类型返回 INTEGER 或 REAL（或 NULL）。数学运算符上的 NULL 操作数产生 NULL 结果。数学运算符上的操作数如果看起来不是数字且不是 NULL，将转换为 0 或 0.0。除零操作的结果为 NULL。

## 6. 排序、分组和复合 SELECT

当查询结果通过 ORDER BY 子句排序时，存储类为 NULL 的值首先出现，然后是按数值顺序插入的 INTEGER 和 REAL 值，然后是按照排序序列顺序的 TEXT 值，最后是按 memcmp() 顺序的 BLOB 值。在排序之前，不会进行存储类转换。

当使用 GROUP BY 子句对值进行分组时，具有不同存储类的值被视为不同值，除了在数值上相同的 INTEGER 和 REAL 值被视为相等。在 GROUP BY 子句结果中，不会对任何值应用亲和性。

UNION、INTERSECT 和 EXCEPT 复合 SELECT 运算符在进行隐式比较时不应用亲和性，比较值按原样进行比较。

## 7. 排序序列

当 SQLite 比较两个字符串时，它使用排序序列或排序函数（这两个术语指的是同一件事）来确定哪个字符串更大或两个字符串是否相等。SQLite 内置了三种排序函数：BINARY、NOCASE 和 RTRIM。

- **BINARY** - 使用 memcmp() 比较字符串数据，不管文本编码如何。
- **NOCASE** - 类似于 BINARY，除了它使用 [sqlite3_strnicmp()](https://www.sqlite.org/c3ref/stricmp.html) 进行比较。因此，ASCII 的 26 个大写字符在比较前会被转换为小写字符。注意，只有 ASCII 字符会被折叠大小写。由于所需表格的大小，SQLite 不会尝试进行完整的 UTF 大小写折叠。此外，对于比较目的，任何字符串中的 U+0000 字符都被视为字符串终止符。
- **RTRIM** - 与 BINARY 一样，除了忽略尾随空格字符。

应用程序可以使用 [sqlite3_create_collation()](https://www.sqlite.org/c3ref/create_collation.html) 接口注册其他排序函数。

排序函数仅在比较字符串值时有意义。数值总是以数值形式比较，BLOB 总是按字节使用 memcmp() 比较。

## 7.1. 从 SQL 分配排序序列

每个表的每一列都有一个关联的排序函数。如果没有明确定义排序函数，则默认排序函数为 BINARY。列定义中的 [COLLATE 子句](https://www.sqlite.org/lang_createtable.html#tablecoldef) 用于定义列的替代排序函数。

使用二进制比较运算符（=、<、>、<=、>=、!=、IS 和 IS NOT）进行比较时，确定使用哪个排序函数的规则如下：

1. 如果任一操作数使用了显示排序函数分配，并使用了后缀 [COLLATE 运算符](https://www.sqlite.org/lang_expr.html#collateop)，则比较时使用显示排序函数，优先使用左操作数的排序函数。
2. 如果任一操作数是列，则使用该列的排序函数，优先使用左操作数的排序函数。对于上一句的目的，即使列名前有一个或多个一元 "+" 运算符和/或 CAST 运算符，该列名仍视为列名。
3. 否则，比较时使用 BINARY 排序函数。

比较的操作数被认为使用了显示排序函数分配（上述第 1 条规则），如果操作数的任何子表达式使用了后缀 [COLLATE 运算符](https://www.sqlite.org/lang_expr.html#collateop)。因此，如果在比较表达式的任何地方使用 [COLLATE 运算符](https://www.sqlite.org/lang_expr.html#collateop)，则该运算符定义的排序函数将用于字符串比较，而不管表达式中可能有哪些表列。如果在比较中出现两个或更多 [COLLATE 运算符](https://www.sqlite.org/lang_expr.html#collateop) 子表达式，则使用最左边的显示排序函数，不管 COLLATE 运算符在表达式中嵌套得多么深且不管表达式如何括号化。

表达式 "x BETWEEN y AND z" 逻辑上等同于两个比较 "x >= y AND x <= z"，在排序函数方面也像两个独立比较那样工作。表达式 "x IN (SELECT y ...)" 处理方式类似于表达式 "x = y" 对于确定排序序列的目的。表达式 "x IN (y, z, ...)" 使用 x 的排序序列。如果 IN 运算符需要明确的排序序列，应将其应用于左操作数，如下所示："x COLLATE nocase IN (y,z, ...)”。

[SELECT](https://www.sqlite.org/lang_select.html) 语句的 ORDER BY 子句中的条款可以使用 [COLLATE 运算符](https://www.sqlite.org/lang_expr.html#collateop) 分配排序序列，在这种情况下，指定的排序函数用于排序。否则，如果 ORDER BY 子句排序的表达式是列，则使用该列的排序序列确定排序顺序。如果表达式不是列且没有 COLLATE 子句，则使用 BINARY 排序序列。

## 7.2. 排序序列示例

以下示例标识将用于确定各种 SQL 语句进行的文本比较结果的排序序列。请注意，在数值、blob 或 NULL 值的情况下，可能不需要文本比较，也不使用排序序列。

> ```sql
> CREATE TABLE t1(
>     x INTEGER PRIMARY KEY,
>     a,                 /* 排序序列 BINARY */
>     b COLLATE BINARY,  /* 排序序列 BINARY */
>     c COLLATE RTRIM,   /* 排序序列 RTRIM  */
>     d COLLATE NOCASE   /* 排序序列 NOCASE */
> );
>                    /* x   a     b     c       d */
> INSERT INTO t1 VALUES(1,'abc','abc', 'abc  ','abc');
> INSERT INTO t1 VALUES(2,'abc','abc', 'abc',  'ABC');
> INSERT INTO t1 VALUES(3,'abc','abc', 'abc ', 'Abc');
> INSERT INTO t1 VALUES(4,'abc','abc ','ABC',  'abc');
>
> /* 使用 BINARY 排序序列进行文本比较 a=b。 */
> SELECT x FROM t1 WHERE a = b ORDER BY x;
> --result 1 2 3
>
> /* 使用 RTRIM 排序序列进行文本比较 a=b。 */
> SELECT x FROM t1 WHERE a = b COLLATE RTRIM ORDER BY x;
> --result 1 2 3 4
>
> /* 使用 NOCASE 排序序列进行文本比较 d=a。 */
> SELECT x FROM t1 WHERE d = a ORDER BY x;
> --result 1 2 3 4
>
> /* 使用 BINARY 排序序列进行文本比较 a=d。 */
> SELECT x FROM t1 WHERE a = d ORDER BY x;
> --result 1 4
>
> /* 使用 RTRIM 排序序列进行文本比较 'abc'=c。 */
> SELECT x FROM t1 WHERE 'abc' = c ORDER BY x;
> --result 1 2 3
>
> /* 使用 RTRIM 排序序列进行文本比较 c='abc'。 */
> SELECT x FROM t1 WHERE c = 'abc' ORDER BY x;
> --result 1 2 3
>
> /* 使用 NOCASE 排序序列分组（值 'abc'、'ABC' 和 'Abc' 归为同一组）。 */
> SELECT count(*) FROM t1 GROUP BY d ORDER BY 1;
> --result 4
>
> /* 使用 BINARY 排序序列分组。'abc' 和 'ABC' 和 'Abc' 形成不同的组 */
> SELECT count(*) FROM t1 GROUP BY (d || '') ORDER BY 1;
> --result 1 1 2
>
> /* 使用 RTRIM 排序序列进行列 c 的排序。 */
> SELECT x FROM t1 ORDER BY c, x;
> --result 4 1 2 3
>
> /* 使用 BINARY 排序序列进行 (c||'') 的排序。 */
> SELECT x FROM t1 ORDER BY (c||''), x;
> --result 4 2 3 1
>
> /* 使用 NOCASE 排序序列进行列 c 的排序。 */
> SELECT x FROM t1 ORDER BY c COLLATE NOCASE, x;
> --result 2 4 3 1
> ```
