---
pubDatetime: 2025-06-27
tags: ["ASP.NET Core", ".NET 10", "System.Text.Json", "JsonPatch", "Web API"]
slug: aspnet-core-in-net-10-preview-4-json
source: https://jaliyaudagedara.blogspot.com/2025/06/aspnet-core-in-net-10-preview-4-json.html
title: ASP.NET Core在.NET 10 Preview 4中的JSON Patch支持：迈向原生System.Text.Json集成
description: 随着.NET 10 Preview 4的发布，ASP.NET Core终于迎来了对JSON Patch的System.Text.Json原生支持，开发者不再必须依赖Newtonsoft.Json。本文深入解析新特性的实现方式、优势、兼容性与使用细节，并补充核心原理与最佳实践，为API开发带来更高性能和原生体验。
---

# ASP.NET Core在.NET 10 Preview 4中的JSON Patch支持：迈向原生System.Text.Json集成

在过去的数个版本中，ASP.NET Core的Web API如果要支持[JSON Patch](https://datatracker.ietf.org/doc/html/rfc6902)操作，始终依赖于经典的Newtonsoft.Json（Json.NET）库。这种依赖在现代.NET环境下逐渐成为性能与维护的瓶颈。随着.NET 10 Preview 4的到来，微软终于为System.Text.Json带来了对JsonPatch的原生支持，这一变革将极大简化Web API的开发与部署。本文将详细介绍该特性的演进、优势、兼容性细节及实际应用场景。

## JsonPatch简介与现有方案回顾

JSON Patch是一种基于[标准RFC 6902](https://datatracker.ietf.org/doc/html/rfc6902)的部分文档更新协议。它允许通过一组有序操作（如add、remove、replace等）对JSON文档进行原子修改，广泛用于RESTful API的PATCH请求，实现对象的部分更新，减少带宽占用，提高接口效率。

在ASP.NET Core 3.x至.NET 8的生态中，开发者若需在Web API中实现JsonPatch功能，通常要引入**Microsoft.AspNetCore.Mvc.NewtonsoftJson**包，并使用Newtonsoft.Json的`JsonPatchDocument<T>`。但由于System.Text.Json自.NET Core 3.0成为内置序列化引擎后，Newtonsoft.Json的独立维护策略导致生态分裂和性能不可控。

## .NET 10 Preview 4的重大突破

.NET 10 Preview 4发布的**Microsoft.AspNetCore.JsonPatch.SystemTextJson**包，首次将JsonPatch的原生支持引入System.Text.Json生态。开发者只需引入预览版NuGet包（目前为prerelease），便可直接在API项目中以原生方式处理JsonPatch请求：

```bash
dotnet add package Microsoft.AspNetCore.JsonPatch.SystemTextJson --prerelease
```

使用方式与Newtonsoft.Json时代几乎一致——`JsonPatchDocument<TModel>`已迁移到新命名空间。最大变化在于底层序列化/反序列化全面基于System.Text.Json，无需为兼容特意配置`Program.cs`或修改序列化行为。这大幅简化了工程配置，并提升了序列化性能和内存效率。

值得注意的是，当前System.Text.Json版JsonPatch的功能并非完全与Newtonsoft.Json兼容。最主要的限制在于**暂不支持动态类型**（如`ExpandoObject`），仅面向强类型模型。对于大多数标准API场景而言，这已能覆盖主要需求。未来版本有望进一步增强兼容性和灵活性。

## 典型应用场景与端点调用示例

集成新包后，开发者可以像如下这样定义PATCH接口，无需更改`Program.cs`，直接在控制器中消费JsonPatchDocument：

```csharp
[HttpPatch("{id}")]
public IActionResult Patch(int id, [FromBody] JsonPatchDocument<Person> patchDoc)
{
    var person = dbContext.People.Find(id);
    if (person == null) return NotFound();

    patchDoc.ApplyTo(person);
    dbContext.SaveChanges();
    return NoContent();
}
```

前端可发送如下JSON Patch文档：

```json
[
  { "op": "replace", "path": "/firstName", "value": "张三" },
  { "op": "add", "path": "/hobbies/-", "value": "AI编程" }
]
```

调用接口即可实现对象的精准部分更新。

![JsonPatch 使用示意](https://blogger.googleusercontent.com/img/a/AVvXsEiVMbFmksuWnR-9-6hPLryz4K_d9yRNd7Id5a8CRoQ2_v5TxnNXFD3jQd5SVqUCFpzLIrJUvqKlBiuK-XPXkIFbH-mx-tkNMhXH2IKEnrqYZUJ-vJ_P3ezgco6qgi_BdyR3q4fIAhi9NtVyporzrxKYTXafEEaSETNfI6fgnyj165P_47KNnsEDGHh0W18=s16000)

## System.Text.Json vs Newtonsoft.Json：性能与生态对比

System.Text.Json作为微软官方主推的高性能JSON库，近年来持续优化，尤其在序列化/反序列化速度、内存分配及平台集成等方面全面超越Newtonsoft.Json。以JsonPatch为例，原生System.Text.Json方案不仅显著减少依赖体积，还为云原生、容器化等现代部署场景带来更优表现。

但Newtonsoft.Json依旧拥有丰富的动态类型支持、灵活的扩展机制，适用于极端复杂或高度自定义的场景。在过渡期间，建议团队根据项目复杂度与长期维护策略权衡选型。

## 未来展望与最佳实践建议

System.Text.Json版JsonPatch的正式集成，预示着ASP.NET Core生态彻底迈入高性能、原生序列化新时代。开发者应积极拥抱新特性，优先在新项目与云原生应用中应用原生JsonPatch方案。

同时，对于需要动态类型支持或历史包袱较重的系统，短期内可继续兼容Newtonsoft.Json，待官方逐步完善System.Text.Json功能后再平滑切换。

总之，.NET 10的这项更新标志着Web API开发迈入更高效、更现代的阶段，为高性能微服务与API平台奠定了坚实基础。

---

_本文参考自[Jaliya's Blog原文](https://jaliyaudagedara.blogspot.com/2025/06/aspnet-core-in-net-10-preview-4-json.html)，并结合.NET官方文档与社区最佳实践予以拓展、细化。_
