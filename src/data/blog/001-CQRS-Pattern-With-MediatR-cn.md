---
title: 深度解析：使用 MediatR 实现 CQRS 模式
pubDatetime: 2024-01-26
slug: cqrs-pattern-with-mediatr
featured: false
draft: false
tags: [".NET", "ASP.NET Core", "Architecture", "Design Patterns"]
source: https://www.milanjovanovic.tech/blog/cqrs-pattern-with-mediatr
description: 本文深入探讨 CQRS 模式的核心概念，解析其与 CQS 的区别，并详细演示如何利用 MediatR 在 .NET 应用程序中构建高性能、可扩展的读写分离架构。
---

本文将深入探讨如何利用 **CQRS**（Command Query Responsibility Segregation，命令查询职责分离）模式构建高性能且具备高可扩展性的应用程序。

CQRS 模式的核心理念在于将应用程序中的 **读取（Query）** 与 **写入（Command）** 操作在架构层面进行分离。

这种分离既可以是逻辑层面的，也可以是物理层面的，它为系统带来了诸多显著优势：

-   **降低复杂性**：通过关注点分离简化业务逻辑。
-   **提升性能**：针对读写操作分别优化，消除瓶颈。
-   **可扩展性**：读写负载不均衡时可独立扩展。
-   **灵活性**：读写模型可独立演进，互不干扰。
-   **安全性**：更细粒度地控制读写权限。

此外，我还将通过实例代码演示如何使用 **MediatR** 库在实际项目中优雅地落地 CQRS。

但首先，我们需要透彻理解 CQRS 的本质。

## 什么是 CQRS？

[CQRS](https://learn.microsoft.com/en-us/azure/architecture/patterns/cqrs) 全称为 **Command Query Responsibility Segregation**，即命令查询职责分离。该模式主张使用不同的模型来分别处理数据的读取和更新。

在传统的架构中，我们通常使用同一个数据模型来同时处理查询和更新操作。这种方法在简单的 CRUD（增删改查）应用中运作良好。然而，随着业务复杂度的提升，这种单一模型的方法会逐渐暴露出问题：

-   **写入端**：可能涉及复杂的业务逻辑、状态校验和事务处理。
-   **读取端**：可能需要执行复杂的联表查询、聚合统计，或者仅需要部分数据字段。

如果在读取和写入时强行共用同一个模型，往往会导致模型变得臃肿且难以维护。此外，为了适应写入而设计的规范化数据库结构，往往并不适合高效的读取查询。

通过为“命令”和“查询”建立分离的模型，我们可以将被动适应转变为主动优化。这种分离可以从逻辑层面开始（共用同一个数据库），也可以发展到物理层面（读写分离数据库）。这使得我们能够将系统划分为独立的子系统，甚至针对读写特性采用不同的存储技术。

## 与 CQS 的区别

[CQS](https://en.wikipedia.org/wiki/Command%E2%80%93query_separation) 代表 **Command Query Separation**（命令查询分离），这是 Bertrand Meyer 在其著作《[面向对象软件构造](https://en.wikipedia.org/wiki/Object-Oriented_Software_Construction)》中提出的概念。

CQS 的基本前提是在**方法**或**类**的级别上将操作分为两类：

-   **命令 (Command)**：改变系统状态（产生副作用），但不返回值（通常返回 void）。
-   **查询 (Query)**：返回结果，但不改变系统状态（无副作用）。

*注：这里的“不返回值”并非绝对。例如，从栈中 pop 元素既改变状态又返回值，但在 CQS 视角下，关键在于意图的区分。*

**核心区别在于：**

-   **CQS** 是一个**编码原则**，作用于方法或类的微观层面。
-   **CQRS** 是一种**架构模式**，作用于系统的宏观层面。CQRS 当作是 CQS 在架构设计上的演进和应用。

## CQRS 的多种实现形态

CQRS 的实现方式非常灵活，可以从简单的逻辑分离到复杂的多数据库架构。以下是一个典型的高级 CQRS 系统概览：

1.  **命令端**：处理业务逻辑，更新“写数据库”。
2.  **同步机制**：将变更同步到“读数据库”。
3.  **查询端**：直接从高性能的“读数据库”获取数据。

这种架构引入了**最终一致性（Eventual Consistency）**，这也是 CQRS 系统中常见的权衡。你必须接受数据在某一短暂时刻可能不同步，并设计相应的容错和补偿策略。

常见的物理分离策略包括：

-   **SQL + NoSQL**：写入使用关系型数据库（保证 ACID），读取使用 NoSQL（如 [RavenDB](https://ravendb.net/)、MongoDB）以提升查询速度。
-   **事件溯源 (Event Sourcing)**：写入端仅记录事件流，读取端消费事件构建视图。
-   **读侧缓存**：写入端更新主库，读取端使用 Redis 或 ElasticSearch 等进行加速。

## 逻辑 CQRS 架构

如果不希望引入多数据库同步的复杂性，如何在单数据库应用中实践 CQRS？我推荐结合 [MediatR](https://github.com/jbogard/MediatR) 库来实现进程内的逻辑分离。

MediatR 实现了[中介者模式 (Mediator Pattern)](https://refactoring.guru/design-patterns/mediator)，其核心价值在于解耦了请求的发起者和处理者。

通过扩展 MediatR 的 `IRequest` 接口，我们可以定义语义明确的 `ICommand` 和 `IQuery` 抽象。

-   **写入端 (Command)**：通常使用 [EF Core](https://learn.microsoft.com/en-us/ef/core/) 和富领域模型（Rich Domain Model）。流程是：加载实体 -> 执行领域逻辑 -> 保存更改。这确保了业务规则的完整性。
-   **读取端 (Query)**：追求极致性能，避免不必要的抽象。直接使用 [Dapper](https://github.com/DapperLib/Dapper) 编写原生 SQL，或者使用 EF Core 的 `AsNoTracking` 查询并投影到 DTO（数据传输对象），通常是最佳实践。

这种架构保留了 CQRS 的代码组织优势，同时避免了分布式系统的复杂性。

## 使用 MediatR 落地 CQRS

使用 MediatR 实现 CQRS 主要包含两个步骤：
1.  定义 **Command** 或 **Query** 类（作为消息契约）。
2.  实现对应的 **Handler** 类（作为业务逻辑）。

### 1. Controller 层

在控制器中，我们注入 `ISender` 接口。MediatR 会根据请求类型自动路由到正确的 Handler。这种方式让 Controller 变得非常轻量（Thin Controller）。

```csharp
[ApiController]
[Route("api/bookings")]
public class BookingsController : ControllerBase
{
    private readonly ISender _sender;

    public BookingsController(ISender sender)
    {
        _sender = sender;
    }

    [HttpPut("{id}/confirm")]
    public async Task<IActionResult> ConfirmBooking(
        Guid id,
        CancellationToken cancellationToken)
    {
        // 构造命令对象
        var command = new ConfirmBookingCommand(id);

        // 发送命令，获取结果
        var result = await _sender.Send(command, cancellationToken);

        if (result.IsFailure)
        {
            return BadRequest(result.Error);
        }

        return NoContent();
    }
}
```

### 2. Command Handler（写入逻辑）

这是处理具体业务的地方。注意这里使用了仓储模式（Repository）和工作单元（UnitOfWork）来封装数据访问，确保领域逻辑的纯净。

```csharp
internal sealed class ConfirmBookingCommandHandler
    : ICommandHandler<ConfirmBookingCommand>
{
    private readonly IDateTimeProvider _dateTimeProvider;
    private readonly IBookingRepository _bookingRepository;
    private readonly IUnitOfWork _unitOfWork;

    public ConfirmBookingCommandHandler(
        IDateTimeProvider dateTimeProvider,
        IBookingRepository bookingRepository,
        IUnitOfWork unitOfWork)
    {
        _dateTimeProvider = dateTimeProvider;
        _bookingRepository = bookingRepository;
        _unitOfWork = unitOfWork;
    }

    public async Task<Result> Handle(
        ConfirmBookingCommand request,
        CancellationToken cancellationToken)
    {
        // 1. 加载聚合根
        var booking = await _bookingRepository.GetByIdAsync(
            request.BookingId,
            cancellationToken);

        if (booking is null)
        {
            return Result.Failure(BookingErrors.NotFound);
        }

        // 2. 执行领域行为
        var result = booking.Confirm(_dateTimeProvider.UtcNow);

        if (result.IsFailure)
        {
            return result;
        }

        // 3. 持久化更改
        await _unitOfWork.SaveChangesAsync(cancellationToken);

        return Result.Success();
    }
}
```

### 3. Query Handler（读取逻辑）

查询处理程序绕过了领域模型，直接通过 Dapper 执行 SQL。这种“读写分离”策略允许你针对具体的查询需求进行精细化优化。

```csharp
internal sealed class SearchApartmentsQueryHandler
    : IQueryHandler<SearchApartmentsQuery, IReadOnlyList<ApartmentResponse>>
{
    private static readonly int[] ActiveBookingStatuses =
    {
        (int)BookingStatus.Reserved,
        (int)BookingStatus.Confirmed,
        (int)BookingStatus.Completed
    };

    private readonly ISqlConnectionFactory _sqlConnectionFactory;

    public SearchApartmentsQueryHandler(
        ISqlConnectionFactory sqlConnectionFactory)
    {
        _sqlConnectionFactory = sqlConnectionFactory;
    }

    public async Task<Result<IReadOnlyList<ApartmentResponse>>> Handle(
        SearchApartmentsQuery request,
        CancellationToken cancellationToken)
    {
        if (request.StartDate > request.EndDate)
        {
            return new List<ApartmentResponse>();
        }

        // 使用 Dapper 直接查询数据库视图或表
        using var connection = _sqlConnectionFactory.CreateConnection();

        const string sql = """
            SELECT
                a.id AS Id,
                a.name AS Name,
                a.description AS Description,
                a.price_amount AS Price,
                a.price_currency AS Currency,
                a.address_country AS Country,
                a.address_state AS State,
                a.address_zip_code AS ZipCode,
                a.address_city AS City,
                a.address_street AS Street
            FROM apartments AS a
            WHERE NOT EXISTS
            (
                SELECT 1
                FROM bookings AS b
                WHERE
                    b.apartment_id = a.id AND
                    b.duration_start <= @EndDate AND
                    b.duration_end >= @StartDate AND
                    b.status = ANY(@ActiveBookingStatuses)
            )
            """;

        var apartments = await connection
            .QueryAsync<ApartmentResponse, AddressResponse, ApartmentResponse>(
                sql,
                (apartment, address) =>
                {
                    apartment.Address = address;
                    return apartment;
                },
                new
                {
                    request.StartDate,
                    request.EndDate,
                    ActiveBookingStatuses
                },
                splitOn: "Country");

        return apartments.ToList();
    }
}
```

### 管道行为 (Pipeline Behaviors)

MediatR 的另一个强大功能是 **请求管道 (pipeline behaviors)**。它可以像 ASP.NET Core 中间件一样拦截请求，处理横切关注点。例如：日志记录、性能监控、事务管理，或者[使用 FluentValidation 进行请求参数验证](https://www.milanjovanovic.tech/blog/cqrs-pattern-with-mediatrcqrs-validation-with-mediatr-pipeline-and-fluentvalidation)。

## 总结

CQRS 是一种强大的模式，通过分离读写职责，为长期维护的项目提供了显著的性能和扩展性红利。

-   **对于写入（Command）**：利用 EF Core 和富领域模型处理复杂的业务规则和一致性校验。
-   **对于读取（Query）**：利用 Dapper 或原生 SQL 追求极致的查询速度和灵活性。

虽然物理层面的读写分离（多数据库）会引入复杂性，但在逻辑层面（单数据库）应用 CQRS + MediatR 是一种性价比极高的架构升级方案，值得在现代 .NET 项目中广泛采用。

