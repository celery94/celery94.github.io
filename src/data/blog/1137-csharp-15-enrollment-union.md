---
pubDatetime: 2026-11-19T09:30:01+08:00
title: "02｜C# 15 实战：用 Union 表达业务结果"
description: "用选课成功、课程不存在和重复报名构造 C# 15 union，并运行穷尽匹配与 JSON 往返测试。说明何时使用 closed 层级，如何识别形状相同的 JSON 分支，以及怎样保持 HTTP 状态码契约。"
tags: ["DotNet", "CSharp", "System.Text.Json"]
slug: "csharp-15-enrollment-union"
ogImage: "../../assets/1137/01-cover.jpg"
source: "https://learn.microsoft.com/en-us/dotnet/csharp/whats-new/csharp-15"
---

选课操作可能成功，可能找不到课程，也可能遇到重复报名。若方法返回一个布尔值或允许任意字符串作为错误码，调用方得记住还有哪些情况。C# 15 的 union 可以在类型签名上列出有限成员，编译器也能提示 `switch` 遗漏的分支。本例用 SDK 11.0.100 和 `System.Text.Json` 验证这三种结果的往返序列化。

同一种业务结果在控制台可以输出文字，在 Web API 可以映射成不同状态码。业务层先返回具体成员，HTTP 层再决定如何发送。这样给 union 增加一个分支时，Web 入口也有机会在编译阶段发现新情况。

## 让调用方处理三种返回值

把这段保存成 UTF-8 编码的 `Enrollment.cs`，用 `dotnet run --file Enrollment.cs` 运行。本例使用 SDK 自带的 JSON 源生成器，无需额外 NuGet 依赖。

```csharp
using System.Text.Json;
using System.Text.Json.Serialization;

EnrollmentResult[] samples =
[
    new Enrolled("S01", "C101"),
    new CourseMissing("C999"),
    new AlreadyEnrolled("S01/C101")
];

var type = EnrollmentJson.Default.EnrollmentResult;
foreach (var expected in samples)
{
    string json = JsonSerializer.Serialize(expected, type);
    EnrollmentResult actual = JsonSerializer.Deserialize(json, type);
    if (Status(actual) != Status(expected) || !Equals(actual.Value, expected.Value))
        throw new InvalidOperationException(json);
    Console.WriteLine($"{Status(actual)} {json}");
}

static int Status(EnrollmentResult result) => result switch
{
    Enrolled => 200,
    CourseMissing => 404,
    AlreadyEnrolled => 409,
    null => throw new InvalidOperationException("Missing union value")
};

[JsonUnion(TypeClassifier = typeof(JsonUnionTypeStructuralClassifier))]
public union EnrollmentResult(Enrolled, CourseMissing, AlreadyEnrolled);
public sealed record Enrolled(string Student, string Course);
public sealed record CourseMissing(string MissingCourse);
public sealed record AlreadyEnrolled(string EnrollmentKey);

[JsonSourceGenerationOptions(JsonSerializerDefaults.Web)]
[JsonSerializable(typeof(EnrollmentResult))]
internal partial class EnrollmentJson : JsonSerializerContext;
```

正常输出是三行，分别以 200、404、409 开头。循环同时检查匹配出的状态和实际成员，任何一次读回错误都会让程序退出失败。

```text
200 {"student":"S01","course":"C101"}
404 {"missingCourse":"C999"}
409 {"enrollmentKey":"S01/C101"}
```

试着删掉 `AlreadyEnrolled` 分支再编译。缺失分支会触发穷尽匹配诊断，CI 也可以将这类警告当作错误处理。保留没有活跃成员时的处理。默认构造的值类型 union 可能为空，不能把 `default` 当成报名成功。

## JSON 在网络上只携带当前成员

`System.Text.Json` 写出当前成员的 JSON 形状。本例三个成员都序列化成对象，只有默认按 JSON token 类型分类时，读取会因为分支含义不明而失败。源生成也会给出 `SYSLIB1227`。加上结构分类器后，可以用各成员在根对象上的不同属性名识别分支。分类器不检查属性值或嵌套对象，因此两个成员若共用相同字段形状，应给对外 DTO 加明确标签并在边界做映射。

Web 层可以用类型化的 `Ok`、`NotFound`、`Conflict` 描述协议。直接把 union 作为响应体时要确认状态码和 OpenAPI 的 `anyOf`，并用生成后的调用代码回放三种结果。[Angular 契约检查](https://celery94.github.io/posts/aspnet-core-11-openapi-angular/)

## 共享基类的模型可以用 closed

用 `closed` 可以限制谁能作为基类的直接子类型：直接派生类必须在同一程序集内。若失败事件共享一组行为或成员，可以封闭自有继承层级，让匹配看到已知分支。union 适合组合已经独立存在的结果类型，避免为了共用返回值给它们加一层基类。

C# 15 还允许用 `with(...)` 为集合表达式传容量、比较器等参数，允许扩展成员提供索引器，并使带标签的 `break` / `continue` 能明确指定外层语句。旧运行时上的非虚静态接口成员也有互操作更新。Memory Safety 的新规则仍在预览，升级业务结果类型时保持已有项目的语言设置即可。

建议先迁移一个内部操作的返回值并让编译器检查各分支。对外 API 继续跑已有契约测试；等到 schema、生成器和请求都通过后，再把 union 放到 HTTP 边界。

## 参考

- [C# 15 正式功能](https://learn.microsoft.com/en-us/dotnet/csharp/whats-new/csharp-15)
- [System.Text.Json 的 union 序列化和分类器](https://learn.microsoft.com/en-us/dotnet/standard/serialization/system-text-json/union-types)
- [ASP.NET Core 11 的 JSON union 与 OpenAPI](https://learn.microsoft.com/en-us/aspnet/core/release-notes/aspnetcore-11?view=aspnetcore-11.0)
