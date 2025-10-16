---
pubDatetime: 2024-05-14
tags: [".NET", "ASP.NET Core"]
source: https://code-maze.com/aspnetcore-result-pattern/
author: Sławomir Świętoniowski
title: 在 .NET Web API 中使用Result Pattern
description: 在本文中，我们将回顾创建响应的不同选项，专注于Result Pattern。
---

# 在 .NET Web API 中使用Result Pattern

> ## 摘要
>
> 在本文中，我们将回顾创建响应的不同选项，专注于Result Pattern。
>
> 原文 [Using the Result Pattern in .NET Web API](https://code-maze.com/aspnetcore-result-pattern/)

---

在不断扩展的API世界中，有意义的错误响应与结构良好的成功响应一样重要，这里，**Result Pattern**可以大大帮助我们。

要下载本文的源代码，可以访问我们的 [GitHub仓库](https://github.com/CodeMazeBlog/CodeMazeGuides/tree/main/aspnetcore-webapi/UsingResultPatternInNETWebAPI)。

为了介绍**Result Pattern**，我们将通过一系列迭代，展示传递操作成功或失败的不同方式。我们将通过构建一个简单的API来做到这一点。在任何给定时刻，我们都可以在GitHub上查找完整的解决方案，所以为了简洁，我们将省略部分代码，专注于关键部分。我们的实现使用了[仓储模式](https://code-maze.com/net-core-web-development-part4/)和[服务层](https://code-maze.com/onion-architecture-in-aspnetcore/)。

但在我们开始使用Result Pattern之前，让我们检查一下我们能用来在应用中返回结果的其他几种方式。

## 空值检查

我们可以使用**空值**来从服务传达失败信息到控制器。

我们可以实现一个新的服务类 `NullCheckingContactService`：（为了简洁，省略了一些代码）：

```csharp
public class NullCheckingContactService
{
    // ...
    public ContactDto? GetById(Guid id)
    {
        var contact = _contactRepository.GetById(id);
        if (contact is null)
        {
            return null;
        }
        return new ContactDto(contact.Id, contact.Email);
    }
    // ...
}
```

我们的`GetById()`方法将为不存在的联系人返回空值。

我们的新控制器`NullCheckingContactController`看起来像这样：

```csharp
[ApiController]
[Route("api/v2/contacts")]
public class NullCheckingContactController : ControllerBase
{
    // ...
    [HttpGet("{id}")]
    [ProducesResponseType(StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public ActionResult<ContactDto> GetById(Guid id)
    {
        var contactDto = _contactService.GetById(id);
        if (contactDto is null)
        {
            return NotFound();
        }
        return Ok(contactDto);
    }
    // ...
}
```

在这里，我们检查服务是否返回了空值，并做出正确响应。对于`GetById()`方法，我们将返回`404 Not Found`响应。

虽然这个解决方案很简单，但它有严重的限制。我们必须在控制器操作中处理空值并做出适当的响应。从服务到控制器传递的信息非常少，我们必须准确知道空值意味着联系人未找到，还是我们无法创建联系人 - 更不用说为什么创建失败了。

## 使用异常来控制流程

与其返回空值，我们的服务可以抛出异常（适当类型的），以标示某些事情出错了。

首先，我们必须创建异常类，比如`RecordNotFoundException`来标示未找到联系人:

```csharp
public class RecordNotFoundException : Exception
{
    public RecordNotFoundException(string message)
        : base(message)
    {
    }
}
```

现在我们可以创建我们的新服务`ExceptionsForFlowControlContactService`：

```csharp
public class ExceptionsForFlowControlContactService
{
    // ...
    public ContactDto GetById(Guid id)
    {
        var contact = _contactRepository.GetById(id);
        if (contact is null)
        {
            throw new RecordNotFoundException($"contact with id {id} not found");
        }
        return new ContactDto(contact.Id, contact.Email);
    }
    // ...
}
```

为了处理异常，我们可以创建异常处理中间件。我们不会深入细节，但如需更多信息，请查看我们的[Web API全局异常处理](https://code-maze.com/global-error-handling-aspnetcore/)文章。

这种解决方法有优点：错误消息很有信息量，我们可以处理不同类型的异常，控制器操作简单，引入自定义异常类型可以确保更一致的响应。

当然，如果你不想使用异常流，还有另一种解决方法：**Result Pattern**。

什么是**Result Pattern**？_它是一种返回包含操作结果和任何返回的数据的响应的方式。_ 让我们进一步阐述。

### CustomError

首先，我们将创建`CustomError`记录来表示操作结果：

```csharp
public sealed record CustomError(string Code, string Message)
{
    private static readonly string RecordNotFoundCode = "RecordNotFound";
    private static readonly string ValidationErrorCode = "ValidationError";
    public static readonly CustomError None = new(string.Empty, string.Empty);
    public static CustomError RecordNotFound(string message)
    {
        return new CustomError(RecordNotFoundCode, message);
    }
    public static CustomError ValidationError(string message)
    {
        return new CustomError(ValidationErrorCode, message);
    }
}
```

对于任何错误，我们都可以提供关于其类别（`Code`）和详细描述（`Message`）的信息。

尽管我们可以创建一个新的静态类，并在其中创建不同类别的错误，为了简单起见，我们制作了静态工厂方法`RecordNotFound()`、`ValidationError()`和静态字段`None`（代表无错误）。

### CustomResult

现在，我们可以创建表示我们结果的`CustomResult`类：

```csharp
public class CustomResult<T>
{
    private readonly T? _value;
    private CustomResult(T value)
    {
        Value = value;
        IsSuccess = true;
        Error = CustomError.None;
    }
    private CustomResult(CustomError error)
    {
        if (error == CustomError.None)
        {
            throw new ArgumentException("invalid error", nameof(error));
        }
        IsSuccess = false;
        Error = error;
    }
    public bool IsSuccess { get; }
    public bool IsFailure => !IsSuccess;
    public T Value
    {
        get
        {
            if (IsFailure)
            {
                throw new InvalidOperationException("there is no value for failure");
            }
            return _value!;
        }
        private init => _value = value;
    }
    public CustomError Error { get; }
    public static CustomResult<T> Success(T value)
    {
        return new CustomResult<T>(value);
    }
    public static CustomResult<T> Failure(CustomError error)
    {
        return new CustomResult<T>(error);
    }
}
```

这是一个我们可以用来返回任何类型结果的泛型类。我们创建了两个私有构造函数。第一个在成功的情况下创建对象，另一个在失败的情况下创建。有两个公共属性：`IsSuccess`和`IsFailure`，我们可以使用它们来测试给定的操作是否成功完成。要检索数据，我们使用`Value`属性。最后，有两个静态方法：`Success()`（如果一切正常则创建`CustomResult`对象）和`Failure()`来返回适当的错误。

让我们通过创建`TheResultPatternContactService`类来看看它的实际操作：

```csharp
public class TheResultPatternContactService
{
    // ...
    public CustomResult<ContactDto> GetById(Guid id)
    {
        var contact = _contactRepository.GetById(id);
        if (contact is null)
        {
            var message = $"contact with id {id} not found";
            return CustomResult<ContactDto>.Failure(CustomError.RecordNotFound(message));
        }
        return CustomResult<ContactDto>.Success(new ContactDto(contact.Id, contact.Email));
    }
    public CustomResult<ContactDto> Create(CreateContactDto createContactDto)
    {
        if (_contactRepository.GetByEmail(createContactDto.Email) is not null)
        {
            var message = $"contact with email {createContactDto.Email} already exists";
            return CustomResult<ContactDto>.FAILURE(CustomError.ValidationError(message));
        }
        var contact = new Contact
        {
            Email = createContactDto.Email
        };
        var createdContact = _contactRepository.Create(contact);
        return CustomResult<ContactDto>.Success(new ContactDto(createdContact.Id, createdContact.Email));
    }
}
```

在这里，我们看到我们可以返回完整的结果，无论操作的状态如何。

现在，我们将创建`TheResultPatternContactController`类：

```csharp
[ApiController]
[Route("api/v4/contacts")]
public class TheResultPatternContactController : ControllerBase
{
    // ...
    [HttpGet("{id}")]
    [ProducesResponseType(StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public ActionResult<ContactDto> GetById(Guid id)
    {
        var result = _contactService.GetById(id);
        if (result.IsFailure)
        {
            return NotFound(result.Error.Message);
        }
        return Ok(result.Value);
    }
    [HttpPost]
    [ProducesResponseType(StatusCodes.Status201Created)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    public IActionResult Create(CreateContactDto createContactDto)
    {
        var result = _contactService.Create(createContactDto);
        if (result.IsFailure)
        {
            return BadRequest(result.Error.Message);
        }
        var contactDto = result.Value;
        return CreatedAtAction(nameof(GetById), new {id = contactDto.Id}, contactDto);
    }
}
```

如我们所见，有了**Result Pattern**，我们可以轻松区分给定的操作是否成功完成，如果失败，我们可以获取详细的解释。

这种方法有许多好处：错误消息很有信息量，控制器的操作几乎没有逻辑，执行路径更易于跟踪（与使用异常进行控制流相比）。

通常，缺点相对较小。我们应该确保在需要时使用这种模式。目前还没有原生支持它（[尚未](https://dotnet.github.io/dotNext/features/core/result.html)）。

## 使用 FluentResults 来实现Result Pattern

虽然我们可以重新发明轮子并创建自定义结果类，但使用现有库（如 [FluentResults](https://github.com/altmann/FluentResults)）更实用。虽然我们的自定义实现很简单，但这个库功能更强大。

首先，我们需要将它添加到我们的项目中：

```bash
PM> Install-Package FluentResults
```

现在，我们可以通过扩展库提供的`Error`类来创建我们的错误类：

```csharp
public class RecordNotFoundError : Error
{
    public RecordNotFoundError(string message)
        : base(message)
    {
    }
}
public class ValidationError : Error
{
    public ValidationError(string message)
        : base(message)
    {
    }
}
```

一个类表示未找到错误，另一个用于验证错误。

然后，我们可以创建我们的（最终）`FluentResultsContactService`类：

```csharp
public class FluentResultsContactService
{
    // ...
    public Result<ContactDto> GetById(Guid id)
    {
        var contact = _contactRepository.GetById(id);
        if (contact is null)
        {
            return new RecordNotFoundError($"contact with id {id} not found");
        }
        return Result.Ok(new ContactDto(contact.Id, contact.Email));
    }
    public Result<ContactDto> Create(CreateContactDto contact)
    {
        if (_contactRepository.GetByEmail(contact.Email) is not null)
        {
            return new ValidationError("contact with this email already exists");
        }
        var createdContact = _contactRepository.Create(new Contact {Email = contact.Email});
        return Result.Ok(new ContactDto(createdContact.Id, createdContact.Email));
    }
}
```

在这里，如果有任何问题，我们将返回适当的错误。如果一切正常，我们返回`Result.Ok()`和正确的值。

现在，让我们创建`FluentResultsContactController`类：

```csharp
[ApiController]
[Route("api/v5/contacts")]
public class FluentResultsContactController : ControllerBase
{
    // ...
    [HttpGet("{id}")]
    [ProducesResponseType(StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public ActionResult<ContactDto> GetById(Guid id)
    {
        var result = _contactService.GetById(id);
        if (result.IsFailed)
        {
            return NotFound(result.Errors);
        }
        return Ok(result.Value);
    }
    [HttpPost]
    [ProducesResponseType(StatusCodes.Status201Created)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    public IActionResult Create(CreateContactDto createContactDto)
    {
        var result = _contactService.Create(createContactDto);
        if (result.IsFailed)
        {
            return BadRequest(result.Errors);
        }
        return CreatedAtAction(nameof(GetById), new {id = result.Value.Id}, result.Value);
    }
}
```

我们可以通过检查`IsFailed`属性来检查给定的操作是否失败，然后使用`Errors`属性检索任何错误。如果一切都按计划进行，我们可以使用`Value`属性。

## 结论

现在我们知道了为什么我们可能想要使用**Result Pattern**以及如何正确地做到这一点。我们已经看到了不同的方式来从我们的服务传递结果到控制器，以及这如何影响我们标示错误条件的能力。每种方法都有优点和缺点，我们应该努力在两者之间找到平衡点，这引导我们使用Result Pattern作为完美的策略。
