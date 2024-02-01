---
title: 使用 MediatR 的 CQRS 模式
pubDatetime: 2024-01-26T08:46:29
slug: cqrs-pattern-with-mediatr
featured: false
draft: false
tags:
  - ASP.NET Core
  - CQRS
  - MediatR
source: https://www.milanjovanovic.tech/blog/cqrs-pattern-with-mediatr
---

如何使用 **CQRS** 模式来构建快速且可扩展的应用程序。

CQRS 模式在应用程序中分离了写入和读取操作。

这种分离可以是逻辑上的或物理上的，并带来了许多好处：

-   管理复杂性
-   提升性能
-   可扩展性
-   灵活性
-   安全性

我还会向你展示如何使用 MediatR 在你的应用程序中实现 CQRS。

但首先，我们必须了解 CQRS 是什么。

## [CQRS 到底是什么？](https://www.milanjovanovic.tech/blog/cqrs-pattern-with-mediatr#what-exactly-is-cqrs)

[CQRS](https://learn.microsoft.com/en-us/azure/architecture/patterns/cqrs) 代表 **命令查询责任隔离**。CQRS 模式使用分离的模型来读取和更新数据。使用 CQRS 的好处包括管理复杂性、提升性能、可扩展性和安全性。

与数据库交互的标准方法是使用相同的模型来查询和更新数据。这种方法简单，并且对大多数 CRUD 操作都很有效。然而，在更复杂的应用程序中，维护起来变得困难。在写入方面，你可能在模型中有复杂的业务逻辑和验证。在读取方面，你可能需要执行许多不同的查询。

还要考虑我们创建数据模型的方式。应用 SQL 数据建模的最佳实践将给你一个规范化的数据库。这通常是没问题的，但它是为写入优化的。

对于命令和查询有分离的模型，允许你独立地扩展它们。这种分离可以是逻辑上的，同时使用同一个数据库。你可以将命令和查询的子系统分割成独立的服务。你甚至可以有针对写入或读取数据优化的多个数据库。

## [它与 CQS 有何不同？](https://www.milanjovanovic.tech/blog/cqrs-pattern-with-mediatr#how-is-it-different-from-cqs)

[CQS](https://en.wikipedia.org/wiki/Command%E2%80%93query_separation) 代表 **命令查询分离**。这是 Bertrand Meyer 在他的书 [面向对象软件构造](https://en.wikipedia.org/wiki/Object-Oriented_Software_Construction) 中提出的术语。

CQS 的基本前提是将对象的方法分为 **命令** 和 **查询**。

-   **命令**：改变系统的状态，但不返回值
-   **查询**：返回值，并且不改变系统的状态（无副作用）

这并不意味着命令永远不能返回值。一个典型的例子是从堆栈中弹出一个值。它返回一个值并改变系统的状态。但重要的是意图。

CQS 是一个 _原则_。如果这个原则有意义，你可以遵循它，但要务实。

CQRS 是 CQS 的演进。CQRS 在架构级别上工作。同时，CQS 在方法（或类）级别上工作。

## [CQRS 的多种形式](https://www.milanjovanovic.tech/blog/cqrs-pattern-with-mediatr#many-flavors-of-cqrs)

这里是使用多个数据库的 CQRS 系统的高级概述。命令更新写数据库。然后，你需要将更新与读数据库同步。这为 CQRS 系统引入了最终一致性。

最终一致性显著增加了应用程序的复杂性。你必须考虑如果同步过程失败会发生什么，并具备容错策略。
![image](./Pasted%20image%2020240126084758.png)

这种方法有很多种形式：

-   写入方面使用 SQL 数据库，读取方面使用 NoSQL 数据库（例如，[RavenDB](https://ravendb.net/)）
-   写入方面使用事件溯源，读取方面使用 NoSQL 数据库
-   读取方面使用 Redis 或其他分布式缓存

为更新和读取数据分离模型，允许你为你的需求选择最佳数据库。

## [逻辑 CQRS 架构](https://www.milanjovanovic.tech/blog/cqrs-pattern-with-mediatr#logical-cqrs-architecture)

你如何将 CQRS 模式应用于你的系统？我更喜欢使用 [MediatR](https://github.com/jbogard/MediatR)。

MediatR 实现了 [中介者模式](https://refactoring.guru/design-patterns/mediator)来解决一个简单的问题 - 解耦消息的进程内发送和处理。

你可以通过自定义的 `ICommand` 和 `IQuery` 抽象扩展 MediatR 的 `IRequest` 接口。这允许你在系统中明确地定义命令和查询。

在写入方面，我通常使用 [EF Core](https://learn.microsoft.com/en-us/ef/core/) 和丰富的域模型来封装业务逻辑。命令流程使用 EF 将实体加载到内存中，执行域逻辑，并将更改保存到数据库。

在读取方面，我希望尽可能少的间接操作。使用 [Dapper](https://github.com/DapperLib/Dapper) 和原始 SQL 查询是一个很好的选择。你也可以在数据库中创建视图并查询它们。或者，你可以使用 EF Core 执行带有投影的查询。
![image](./Pasted%20image%2020240126084826.png)


## [使用 MediatR 实现 CQRS](https://www.milanjovanovic.tech/blog/cqrs-pattern-with-mediatr#implementing-cqrs-with-mediatr)

使用 MediatR 实现 CQRS 包含两个组件：

-   定义你的命令或查询类
-   实现相应的命令或查询处理程序

我制作了一个深入解释这个过程的视频，你可以[在这里观看](https://youtu.be/vdi-p9StmG0)。

你使用 `ISender` 接口来 `Send` 命令或查询。MediatR 负责将命令或查询路由到相应的处理程序。

请求将通过 _请求管道_。它是每个请求的包装器，你可以使用 `IPipelineBehavior` 解决横切关注点。例如，你可以使用 [FluentValidation 实现命令的验证](https://www.milanjovanovic.tech/blog/cqrs-pattern-with-mediatrcqrs-validation-with-mediatr-pipeline-and-fluentvalidation)。

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
        var command = new ConfirmBookingCommand(id);

        var result = await _sender.Send(command, cancellationToken);

        if (result.IsFailure)
        {
            return BadRequest(result.Error);
        }

        return NoContent();
    }
}
```

这是一个带有仓库和丰富域模型的命令处理程序示例：
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
        var booking = await _bookingRepository.GetByIdAsync(
            request.BookingId,
            cancellationToken);

        if (booking is null)
        {
            return Result.Failure(BookingErrors.NotFound);
        }

        var result = booking.Confirm(_dateTimeProvider.UtcNow);

        if (result.IsFailure)
        {
            return result;
        }

        await _unitOfWork.SaveChangesAsync(cancellationToken);

        return Result.Success();
    }
}
```

这是一个使用 Dapper 和原始 SQL 的查询处理程序示例：

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

## [结束语](https://www.milanjovanovic.tech/blog/cqrs-pattern-with-mediatr#closing-thoughts)

分离命令和查询可以在长期内提高性能和可扩展性。你可以根据需求不同地优化命令和查询。

命令封装了复杂的业务逻辑和验证。使用 EF Core 和丰富的域模型是一个很好的解决方案。

查询完全是关于性能，所以你想使用最快的方法。这可能是使用 Dapper 的原始 SQL 查询、EF Core 投影，或者 Redis。