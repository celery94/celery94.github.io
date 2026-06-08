---
pubDatetime: 2026-06-08T08:12:21+08:00
title: "ASP.NET Core 模型验证：Data Annotations 还是 FluentValidation"
description: "ASP.NET Core 模型验证的目标，是把坏输入挡在业务逻辑之外。这篇按 .NET 10 语境梳理 Data Annotations、ModelState、[ApiController] 自动 400、自定义属性、IValidatableObject、FluentValidation 和 Minimal API 验证边界。"
tags: ["ASP.NET Core", ".NET", "Validation", "FluentValidation"]
slug: "aspnet-core-model-validation-data-annotations-fluentvalidation"
ogImage: "../../assets/855/01-cover.png"
source: "https://www.devleader.ca/2026/06/06/model-validation-in-aspnet-core-data-annotations-and-fluentvalidation"
---

ASP.NET Core model validation 的价值很朴素：在请求刚进入系统时，把空用户名、负数数量、格式错误的邮箱、互相矛盾的字段挡住。坏数据如果穿过 API 边界，后面的业务逻辑、数据库约束和异常处理都会变得更难看。

Dev Leader 这篇文章围绕 .NET 10 梳理了几种常见做法：Data Annotations 适合简单、贴近 DTO 的结构性约束；`ModelState` 和 `[ApiController]` 负责把验证失败变成一致的 400 响应；`IValidatableObject` 处理跨字段规则；FluentValidation 则适合复杂、条件式、异步、可测试的规则。

## 先用注解

Data Annotations 来自 `System.ComponentModel.DataAnnotations`。它们是直接贴在模型属性上的验证属性，优点是简单、可读、零额外基础设施。

常见注解包括：

- `[Required]`：字段必须提供。
- `[StringLength(max, MinimumLength = min)]`：限制字符串长度。
- `[Range(min, max)]`：限制数字或日期范围。
- `[EmailAddress]`：验证邮箱格式。
- `[Url]`：验证 URL 格式。
- `[RegularExpression(pattern)]`：用正则表达式控制格式。
- `[MinLength]` / `[MaxLength]`：适用于字符串和集合。
- `[Compare("OtherProperty")]`：常见于确认密码。

一个注册请求 DTO 可以这样写：

```csharp
public sealed record CreateUserRequest
{
    [Required(ErrorMessage = "Username is required")]
    [StringLength(50, MinimumLength = 3,
        ErrorMessage = "Username must be 3-50 characters")]
    [RegularExpression(@"^[a-zA-Z0-9_]+$",
        ErrorMessage = "Username may only contain letters, numbers, and underscores")]
    public string Username { get; init; } = string.Empty;

    [Required(ErrorMessage = "Email is required")]
    [EmailAddress(ErrorMessage = "A valid email address is required")]
    [StringLength(256)]
    public string Email { get; init; } = string.Empty;

    [Required]
    [StringLength(100, MinimumLength = 8,
        ErrorMessage = "Password must be at least 8 characters")]
    public string Password { get; init; } = string.Empty;

    [Required]
    [Compare(nameof(Password), ErrorMessage = "Passwords do not match")]
    public string ConfirmPassword { get; init; } = string.Empty;

    [Range(13, 120, ErrorMessage = "Age must be between 13 and 120")]
    public int? Age { get; init; }

    [Url(ErrorMessage = "Profile URL must be a valid URL")]
    [StringLength(500)]
    public string? ProfileUrl { get; init; }
}
```

这种写法的好处是约束就在字段旁边，读模型时就能知道请求边界是什么。代价也很明显：验证规则和 DTO 强绑定。如果这个模型跨层复用，或者规则越来越像业务逻辑，注解就会开始变重。

## ModelState 做什么

`ModelState` 是当前请求的验证结果字典。模型绑定完成之后、action 执行之前，ASP.NET Core 会运行验证规则，把每个字段的绑定值和错误信息放进 `ModelStateDictionary`。

没有 `[ApiController]` 时，传统 controller action 里要手动检查：

```csharp
[HttpPost]
public IActionResult CreateUser([FromBody] CreateUserRequest request)
{
    if (!ModelState.IsValid)
    {
        var errors = ModelState
            .Where(kvp => kvp.Value?.Errors.Count > 0)
            .ToDictionary(
                kvp => kvp.Key,
                kvp => kvp.Value!.Errors
                    .Select(e => e.ErrorMessage)
                    .ToArray());

        return BadRequest(new { errors });
    }

    return Ok();
}
```

这段代码不难，但很容易漏。每个 action 都手写一遍，后续维护时总会有人忘记或删掉。

## 自动 400

controller-based Web API 的强默认值是 `[ApiController]`。当它应用到 controller 上时，只要 `ModelState` 无效，框架会在 action 执行前自动返回 `400 Bad Request`，响应体是 `ValidationProblemDetails`。

典型响应类似这样：

```json
{
  "type": "https://tools.ietf.org/html/rfc9110#section-15.5.1",
  "title": "One or more validation errors occurred.",
  "status": 400,
  "errors": {
    "Email": ["The Email field is not a valid e-mail address."],
    "Username": ["Username must be 3-50 characters"]
  }
}
```

对前端和移动端来说，`errors` 字典很重要：字段名对应错误数组，可以直接映射到表单控件。大多数项目不需要为普通验证失败重写格式；如果确实要统一错误 envelope，可以通过 `ApiBehaviorOptions.InvalidModelStateResponseFactory` 调整。

## 自定义属性

内置注解不够用时，可以继承 `ValidationAttribute`。原文给了一个 `[FutureDate]` 的例子，用来确保日期在未来。

```csharp
[AttributeUsage(AttributeTargets.Property, AllowMultiple = false)]
public sealed class FutureDateAttribute : ValidationAttribute
{
    public FutureDateAttribute()
        : base("The {0} field must be a future date.")
    {
    }

    protected override ValidationResult? IsValid(
        object? value,
        ValidationContext validationContext)
    {
        if (value is null)
        {
            return ValidationResult.Success;
        }

        if (value is not DateTimeOffset dateValue)
        {
            return new ValidationResult(
                $"The {validationContext.DisplayName} field must be a date.");
        }

        return dateValue > DateTimeOffset.UtcNow
            ? ValidationResult.Success
            : new ValidationResult(
                FormatErrorMessage(validationContext.DisplayName));
    }
}
```

使用时还是普通注解：

```csharp
public sealed record ScheduleEventRequest
{
    [Required]
    public string Title { get; init; } = string.Empty;

    [Required]
    [FutureDate]
    public DateTimeOffset ScheduledAt { get; init; }
}
```

自定义 attribute 适合可复用、同步、属性级规则。它也会进入 ASP.NET Core 的验证管道，配合 `[ApiController]` 自动返回 400。它不适合查数据库这种异步校验。

## 跨字段规则

有些规则不是单个属性能表达的。比如“如果支付方式是信用卡，就必须提供 CardNumber”，这时可以用 `IValidatableObject`。

```csharp
public sealed record PaymentRequest : IValidatableObject
{
    public string PaymentMethod { get; init; } = string.Empty;
    public string? CardNumber { get; init; }

    public IEnumerable<ValidationResult> Validate(
        ValidationContext validationContext)
    {
        if (PaymentMethod == "CreditCard" &&
            string.IsNullOrWhiteSpace(CardNumber))
        {
            yield return new ValidationResult(
                "Card number is required for credit card payments",
                new[] { nameof(CardNumber) });
        }
    }
}
```

这种方式比硬塞多个 attribute 清楚，但也会让 DTO 承担更多逻辑。跨字段规则少时可以接受；如果规则开始变多、需要依赖服务、需要单元测试，FluentValidation 往往更合适。

## 引入 FluentValidation

FluentValidation 不是 ASP.NET Core 内置框架的一部分，而是第三方库。它的价值在于把规则从 DTO 上拿出来，放到独立的 `AbstractValidator<T>` 类里。

安装常见包：

```powershell
dotnet add package FluentValidation
dotnet add package FluentValidation.AspNetCore
```

一个等价的用户请求 validator 可以这样写：

```csharp
public sealed class CreateUserRequestValidator
    : AbstractValidator<CreateUserRequest>
{
    public CreateUserRequestValidator()
    {
        RuleFor(x => x.Username)
            .NotEmpty().WithMessage("Username is required")
            .Length(3, 50).WithMessage("Username must be 3-50 characters")
            .Matches(@"^[a-zA-Z0-9_]+$")
            .WithMessage("Username may only contain letters, numbers, and underscores");

        RuleFor(x => x.Email)
            .NotEmpty().WithMessage("Email is required")
            .EmailAddress().WithMessage("A valid email address is required")
            .MaximumLength(256);

        RuleFor(x => x.Password)
            .NotEmpty()
            .MinimumLength(8)
            .WithMessage("Password must be at least 8 characters");

        RuleFor(x => x.ConfirmPassword)
            .Equal(x => x.Password)
            .WithMessage("Passwords do not match");

        RuleFor(x => x.Age)
            .InclusiveBetween(13, 120)
            .When(x => x.Age.HasValue)
            .WithMessage("Age must be between 13 and 120");
    }
}
```

注册时，把 validator 加进 DI，并接入 ASP.NET Core validation pipeline：

```csharp
builder.Services.AddControllers();

builder.Services
    .AddValidatorsFromAssemblyContaining<CreateUserRequestValidator>();

builder.Services.AddFluentValidationAutoValidation();
```

这样 FluentValidation 的错误会进入 `ModelState`，和 Data Annotations 的错误走同一套 `[ApiController]` 自动 400 响应。客户端不需要知道错误来自 attribute 还是 validator。

## 异步校验

Data Annotations 是同步的。用户名是否已被占用、邮箱是否已注册、邀请码是否有效，这类规则通常要查数据库或外部服务，FluentValidation 的 `MustAsync` 更合适。

```csharp
public sealed class CreateUserRequestValidator
    : AbstractValidator<CreateUserRequest>
{
    private readonly IUserRepository _userRepository;

    public CreateUserRequestValidator(IUserRepository userRepository)
    {
        _userRepository = userRepository;

        RuleFor(x => x.Username)
            .NotEmpty()
            .Length(3, 50)
            .MustAsync(async (username, cancellationToken) =>
            {
                var exists = await _userRepository.ExistsAsync(
                    username,
                    cancellationToken);

                return !exists;
            })
            .WithMessage("This username is already taken");

        RuleFor(x => x.Email)
            .NotEmpty()
            .EmailAddress()
            .MustAsync(async (email, cancellationToken) =>
                !await _userRepository.EmailExistsAsync(
                    email,
                    cancellationToken))
            .WithMessage("An account with this email already exists");
    }
}
```

validator 由 DI 创建，所以可以注入 repository 或 service。规则也可以直接单元测试：实例化 validator，调用 `Validate` 或 `ValidateAsync`，断言具体字段和错误消息，不需要启动 HTTP server。

## Minimal API 怎么办

原文提到 .NET 10 里 Minimal API validation 有明显变化：框架开始支持对绑定参数上的 Data Annotations 做内置验证。简单注解规则可以直接受益。

当你需要显式控制，或者要用 FluentValidation 时，可以在 endpoint 中注入 `IValidator<T>`：

```csharp
app.MapPost("/users", async (
    [FromBody] CreateUserRequest request,
    IValidator<CreateUserRequest> validator,
    IUserService userService) =>
{
    var validationResult = await validator.ValidateAsync(request);

    if (!validationResult.IsValid)
    {
        var errors = validationResult.Errors
            .GroupBy(e => e.PropertyName)
            .ToDictionary(
                g => g.Key,
                g => g.Select(e => e.ErrorMessage).ToArray());

        return Results.ValidationProblem(errors);
    }

    var user = await userService.CreateAsync(request);
    return Results.Created($"/users/{user.Id}", user);
});
```

`Results.ValidationProblem(errors)` 会返回和 `[ApiController]` 类似的 `ValidationProblemDetails`，状态码为 400，内容类型通常是 `application/problem+json`。如果很多 endpoint 都要这么写，可以做成 endpoint filter，避免重复。

## 怎么选择

可以按复杂度来选：

Data Annotations 适合稳定、简单、属性级的结构约束，比如必填、长度、范围、邮箱、URL。规则就属于 DTO 本身时，放在属性旁边很直观。

自定义 `ValidationAttribute` 适合同步、可复用、单属性规则。比如未来日期、合法枚举组合、格式校验。

`IValidatableObject` 适合少量跨字段规则。它简单直接，但规则多了会让 DTO 膨胀。

FluentValidation 适合复杂、条件式、异步、依赖服务、需要独立测试的验证逻辑。尤其是规则开始接近应用层输入检查，而不是单纯字段格式时，它的可维护性更好。

现实项目里可以混用：Data Annotations 处理 DTO 的结构性约束，FluentValidation 处理业务输入规则。它们最终都能进入 `ModelState`，由 `[ApiController]` 或 `Results.ValidationProblem` 输出一致的错误格式。

## 边界别放错

验证层回答的问题是：“这个请求能不能被处理？”比如字段是否存在、格式是否正确、用户名是否已占用。

领域层回答的问题是：“在当前业务状态下，这个操作该不该成功？”比如账户余额是否允许扣款、订单状态是否允许取消、用户是否满足某个业务规则。

这条边界很重要。把复杂领域规则塞进 validator，会让输入验证变慢、变重、难以复用。把基础输入校验丢给业务逻辑，又会让每个 use case 都处理脏数据。好的实践是：边界校验挡住坏输入，业务层处理业务决策。

如果你关注 AI 助手、开发工具和软件工程实践，可以关注 Aide Hub。这里会继续分享能落地的工具教程、技术观察和项目经验。

## 参考

- [Model Validation in ASP.NET Core: Data Annotations and FluentValidation](https://www.devleader.ca/2026/06/06/model-validation-in-aspnet-core-data-annotations-and-fluentvalidation)
- [Model validation in ASP.NET Core MVC and Razor Pages - Microsoft Learn](https://learn.microsoft.com/en-us/aspnet/core/mvc/models/validation)
