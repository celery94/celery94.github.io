---
pubDatetime: 2024-05-19
tags: ["Productivity", "Tools"]
source: https://www.milanjovanovic.tech/blog/cqrs-validation-with-mediatr-pipeline-and-fluentvalidation?utm_source=Twitter&utm_medium=social&utm_campaign=13.06.2024
author: Milan Jovanović
title: 使用MediatR Pipeline和FluentValidation进行CQRS校验
description: 校验是你需要在应用程序中解决的一个基本的横切关注点。你希望在处理请求之前确保请求是有效的。
---

# 使用MediatR Pipeline和FluentValidation进行CQRS校验

> ## 摘录
>
> 校验是你需要在应用程序中解决的一个基本的横切关注点。你希望在处理请求之前确保请求是有效的。
> 另一个你需要回答的重要问题是你如何处理不同类型的校验。例如，我认为输入校验和业务校验是不同的，每种都应该有一个具体的解决方案。
> 我想向你展示一个使用MediatR和FluentValidation进行校验的优雅解决方案。
> 如果你没有使用CQRS与MediatR，不用担心。我解释的关于校验的所有内容都可以很容易地适应于其他范式。

---

校验是你需要在应用程序中解决的一个基本的横切关注点。你希望在处理请求之前确保请求是有效的。

另一个你需要回答的重要问题是你如何处理不同类型的校验。例如，我认为输入校验和业务校验是不同的，每种都应该有一个具体的解决方案。

我想向你展示一个使用[MediatR](https://github.com/jbogard/MediatR)和[FluentValidation.](https://docs.fluentvalidation.net/en/latest/index.html)进行校验的优雅解决方案。

如果你没有使用[CQRS](https://learn.microsoft.com/en-us/azure/architecture/patterns/cqrs)与MediatR，不用担心。我解释的关于校验的所有内容都可以很容易地适应于其他范式。

以下是我在本周通讯中将讨论的内容：

- 标准校验方法
- 输入校验与业务校验
- 分离校验逻辑
- 通用`ValidationBehavior`

让我们开始吧。

## 标准命令校验方法

实现校验的标准方法是在处理命令之前进行校验。校验与命令处理器紧密耦合，这可能会引起问题。

我发现随着校验复杂性的增加，这种方法很难维护。每次对校验逻辑的更改也都会触及处理器，处理器本身可能会失控。

它还使得区分输入和*业务*校验变得更加困难。

以下是一个`ShipOrderCommandHandler`的例子，它检查`ShippingAddress.Country`是否为受支持的国家之一：

```csharp
internal sealed class ShipOrderCommandHandler
    : IRequestHandler<ShipOrderCommand>
{
    private readonly IOrderRepository _orderRepository;
    private readonly IShippingService _shippingService;
    private readonly ShipmentSettings _shipmentSettings;

    public async Task Handle(
        ShipOrderCommand command,
        CancellationToken cancellationToken)
    {
        if (!_shipmentSettings
                .SupportedCountries
                .Contains(command.ShippingAddress.Country))
        {
            throw new ArgumentException(nameof(ShipOrderCommand.Address));
        }

        var order = _orderRepository.Get(command.OrderId);

        _shippingService.ShipTo(
            command.ShippingAddress,
            command.ShippingMethod);
    }
}
```

如果我们能将命令校验与命令处理分开会怎样呢？

## 输入校验与业务校验

我在前一节提到了输入和*业务*校验。

以下是我认为它们之间的不同之处：

- **输入校验** - 我们只校验命令是否是*可处理的*。这些是简单的校验，比如检查`null`值、空字符串等。
- **业务校验** - 我们校验命令是否满足业务规则。这包括在处理命令之前检查系统状态是否符合所需的先决条件。

另一种比较它们的方式是成本低与成本高。输入校验通常执行成本低，并且可以在内存中完成。而业务校验涉及到读取状态，速度较慢。

因此，输入校验位于用例的入口点，在处理请求之前。完成后，我们就有了一个*有效*的命令。这是我一直遵循的规则 - 无效的命令永远不应达到处理器。

## 使用FluentValidation进行输入校验

[FluentValidation](https://docs.fluentvalidation.net/en/latest/index.html)是一个用于.NET的出色校验库，它使用流畅的接口和lambda表达式来构建强类型的校验规则。

以下是我们想要校验的`ShipOrderCommand`：

```csharp
public sealed record ShipOrderCommand : IRequest
{
    public Guid OrderId { get; set; }

    public string ShippingMethod { get; set; }

    public Address ShippingAddress { get; set; }
}
```

要用[FluentValidation](https://github.com/FluentValidation/FluentValidation)实现一个校验器，你需要创建一个继承自`AbstractValidator<T>`基类的类。然后，你可以从构造函数中使用`RuleFor`添加校验规则：

```csharp
public sealed class ShipOrderCommandValidator
    : AbstractValidator<ShipOrderCommand>
{
    public ShipOrderCommandValidator(ShipmentSettings settings)
    {
        RuleFor(command => command.OrderId)
            .NotEmpty()
            .WithMessage("订单标识符不能为空。");

        RuleFor(command => command.ShippingMethod)
            .NotEmpty()
            .WithMessage("运送方式不能为空。");

        RuleFor(command => command.ShippingAddress)
            .NotNull()
            .WithMessage("运送地址不能为空。");

        RuleFor(command => command.ShippingAddress.Country)
            .Must(country => settings.SupportedCountries.Contains(country))
            .WithMessage("不支持的运送国家。");
    }
}
```

我喜欢使用的命名约定是命令的名称并附加*Validator*。你也可以通过编写[架构测试](https://www.milanjovanovic.tech/blog/enforcing-software-architecture-with-architecture-tests)来强制执行这一点。

要自动从一个程序集注册所有校验器，你需要调用`AddValidatorsFromAssembly`方法：

```csharp
services.AddValidatorsFromAssembly(ApplicationAssembly.Assembly);
```

## 从用例中运行校验

要运行`ShipOrderCommandValidator`，你可以使用`IValidator<T>`服务并从构造函数中注入它。

校验器提供了几个你可以调用的方法，如`Validate`、`ValidateAsync`或`ValidateAndThrow`。

`Validate`方法返回一个`ValidationResult`对象，其中包含两个属性：

- `IsValid` - 一个布尔标志，表示校验是否成功
- `Errors` - 包含任何校验失败的`ValidationFailure`对象的集合

或者，调用`ValidateAndThrow`方法将在校验失败时抛出`ValidationException`异常。

```csharp
internal sealed class ShipOrderCommandHandler
    : IRequestHandler<ShipOrderCommand>
{
    private readonly IOrderRepository _orderRepository;
    private readonly IShippingService _shippingService;
    private readonly IValidator<ShipOrderCommand> _validator;

    public async Task Handle(
        ShipOrderCommand command,
        CancellationToken cancellationToken)
    {
        _validator.ValidateAndThrow(command);

        var order = _orderRepository.Get(command.OrderId);

        _shippingService.ShipTo(
            command.ShippingAddress,
            command.ShippingMethod);
    }
}
```

这种方法强制你在每个命令处理器中显式定义对`IValidator`的依赖。

如果我们能以更通用的方式实现这个横切关注点会怎样呢？

以下是使用FluentValidation和MediatR的`IPipelineBehavior`完整实现的`ValidationBehavior`。

`ValidationBehavior`充当请求管道的中间件并执行校验。如果校验失败，它将抛出一个包含`ValidationError`对象集合的自定义`ValidationException`异常。

我还想强调使用`ValidateAsync`的重要性，它允许你定义异步校验规则。如果你有异步规则，你必须调用`ValidateAsync`方法。否则，校验器将抛出异常。

```csharp
public sealed class ValidationBehavior<TRequest, TResponse>
    : IPipelineBehavior<TRequest, TResponse>
    where TRequest : ICommandBase
{
    private readonly IEnumerable<IValidator<TRequest>> _validators;

    public ValidationBehavior(IEnumerable<IValidator<TRequest>> validators)
    {
        _validators = validators;
    }

    public async Task<TResponse> Handle(
        TRequest request,
        RequestHandlerDelegate<TResponse> next,
        CancellationToken cancellationToken)
    {
        var context = new ValidationContext<TRequest>(request);

        var validationFailures = await Task.WhenAll(
            _validators.Select(validator => validator.ValidateAsync(context)));

        var errors = validationFailures
            .Where(validationResult => !validationResult.IsValid)
            .SelectMany(validationResult => validationResult.Errors)
            .Select(validationFailure => new ValidationError(
                validationFailure.PropertyName,
                validationFailure.ErrorMessage))
            .ToList();

        if (errors.Any())
        {
            throw new Exceptions.ValidationException(errors);
        }

        var response = await next();

        return response;
    }
}
```

不要忘记通过调用`AddOpenBehavior`将`ValidationBehavior`注册到MediatR：

```csharp
services.AddMediatR(config =>
{
    config.RegisterServicesFromAssemblyContaining<ApplicationAssembly>();

    config.AddOpenBehavior(typeof(ValidationBehavior<,>));
});
```

## 处理校验异常

以下是只处理自定义`ValidationException`的自定义`ValidationExceptionHandlingMiddleware`中间件。它将异常转换为`ProblemDetails`响应，并包含任何校验错误。

你可以轻松地将其扩展为通用的全局异常处理器。

```csharp
public sealed class ValidationExceptionHandlingMiddleware
{
    private readonly RequestDelegate _next;

    public ValidationExceptionHandlingMiddleware(RequestDelegate next)
    {
        _next = next;
        _logger = logger;
    }

    public async Task InvokeAsync(HttpContext context)
    {
        try
        {
            await _next(context);
        }
        catch (Exceptions.ValidationException exception)
        {
            var problemDetails = new ProblemDetails
            {
                Status = StatusCodes.Status400BadRequest,
                Type = "ValidationFailure",
                Title = "校验错误",
                Detail = "发生了一个或多个校验错误"
            };

            if (exception.Errors is not null)
            {
                problemDetails.Extensions["errors"] = exception.Errors;
            }

            context.Response.StatusCode = StatusCodes.Status400BadRequest;

            await context.Response.WriteAsJsonAsync(problemDetails);
        }
    }
}
```

你还需要通过调用`UseMiddleware`将中间件包含在请求管道中：

```csharp
app.UseMiddleware<ExceptionHandlingMiddleware>();
```

## 结论

这种`ValidationBehavior`的实现是我在真实项目中使用的，它非常有效。如果我不想抛出异常，我可以更新`ValidationBehavior`以返回结果对象代替。

如果你不使用MediatR怎么办？

我正在使用`IPipelineBehavior`，它允许我实现一个*中间件*封装每个请求。

所以，你需要的只是一种实现中间件的方式，并将你的校验放入其中。而且我喜欢有选择，所以在这里有[三种在ASP.NET Core中创建中间件的方法。](https://www.milanjovanovic.tech/blog/3-ways-to-create-middleware-in-asp-net-core)
