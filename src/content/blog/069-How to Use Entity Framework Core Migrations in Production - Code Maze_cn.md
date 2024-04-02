---
pubDatetime: 2024-03-28
tags: []
source: https://code-maze.com/efcore-how-to-use-entity-framework-core-migrations-in-production/
author: Gergő Vándor
title: 如何在生产环境中使用Entity Framework Core Migrations
description: 在本文中，我们将讨论在使用Entity Framework Core的迁移时迁移生产数据库的不同方法。
---

> ## 摘要
>
> 在本文中，我们将讨论在使用Entity Framework Core的迁移时迁移生产数据库的不同方法。
>
> 原文 [How to Use Entity Framework Core Migrations in Production](https://code-maze.com/efcore-how-to-use-entity-framework-core-migrations-in-production/)

---

在本文中，我们将讨论在使用Entity Framework (EF) Core code-first迁移时，迁移生产数据库的不同方法。

要下载本文的源代码，您可以访问我们的 [GitHub repository](https://github.com/CodeMazeBlog/CodeMazeGuides/tree/main/dotnet-efcore/EfCoreCodeFirstMigrationsInProd)。

## Entity Framework Core项目设置

让我们开始创建一个模板Web API项目并安装必要的[Entity Framework Core](https://code-maze.com/entity-framework-core-series/) NuGet包：

```bash
Microsoft.EntityFrameworkCore
Microsoft.EntityFrameworkCore.SqlServer
Microsoft.EntityFrameworkCore.Design
```

在本文中，我们使用Microsoft SQL Server作为数据库，但这些原则同样适用于Entity Framework Core支持的任何其他数据库。只需安装`Microsoft.EntityFrameworkCore.SqlServer`的替代NuGet包即可。

### 创建Entity Framework Core领域模型

让我们创建一个`WeatherForecast`类：

```csharp
public class WeatherForecast(DateOnly date, int temperatureC, string? summary)
{
    public Guid Id { get; private set; }
    public DateOnly Date { get; private set; } = date;
    public int TemperatureC { get; private set; } = temperatureC;
    public string? Summary { get; private set; } = summary;

    public int TemperatureF => 32 + (int) (TemperatureC / 0.5556);
    private WeatherForecast() : this(default, default, default)
    {
    }
}
```

在这里，我们定义了一个`WeatherForecast`记录的副本，添加了一些额外的变化以使其与Entity Framework Core兼容。首先，我们添加一个`Id`属性，使其具有主键。接下来，我们为每个属性添加了私有设置器，以便Entity Framework可以通过反射来设置值。

最后，除了C# 12风格的[主构造函数](https://code-maze.com/csharp-primary-constructors-for-classes-and-structs/)，我们还添加了一个无参的私有构造函数以便Entity Framework更容易实例化。完成后，我们可以移除`WeatherForecast`记录，并更新引用以使用我们的新领域类。

### 创建首个Entity Framework迁移

现在，一切都设置好了，让我们导航到项目的根文件夹，然后创建初始迁移：

```bash
dotnet ef migrations add InitialMigration
```

会创建一个新的Migrations文件夹，其中包含迁移类和`DbContextModelSnapshot`。Entity Framework Core需要这些类才能生成正确的SQL脚本。说到这，让我们探讨将此迁移应用到生产数据库的可能选项。

手动迁移意味着我们必须直接登录到生产SQL Server并应用迁移脚本，无论是手动还是借助CLI工具。这种方法需要最少的配置和设置，但很难自动化。让我们看看如何进行这种迁移。

### 生成Entity Framework迁移SQL

要生成一个简单的迁移SQL，将一个空白数据库迁移到最新版本，我们可以使用`dotnet ef` CLI工具：

```bash
dotnet ef migrations script [From] [To]
```

`From`和`To`参数是可选的。我们可以指定我们想要用作起点的迁移的名称，以及另一个迁移作为我们打算更新到的终点。这允许我们生成部分（增量）迁移脚本，甚至如果`To`是比`From`更早的迁移，也可以生成回滚脚本。

**`From`的值应始终是当前应用到数据库的最新迁移。** 然而，在生成脚本时，最新应用的迁移可能对我们来说是未知的。幸运的是，`dotnet ef`工具有一个`-idempotent`标志，它将检查最新应用的迁移是什么，并从那个迁移生成脚本直到最新的一个。

如果我们运行命令并且在控制台中生成的SQL脚本看起来并且行为正确，我们只需将其拷贝并执行在SQL Server上，例如使用查询控制台或使用SQL Server Management Studio。

**当使用脚本生成作为我们的迁移策略时，我们可以在应用之前检查并修改SQL脚本，防止错误的迁移。**在生产场景中，这是一个巨大的好处。然而，我们必须能够访问生产数据库以应用它，这是一个安全风险。此外，因为这些脚本是由人类应用的，在多个数据库和迁移的复杂情景中，这容易出现用户错误。同样，应用迁移必须与发布代码同步，这可能是一项挑战。

现在让我们看看如何消除手动运行SQL脚本的需求。

### 使用EF Core命令行工具

`dotnet ef` CLI工具非常通用，它也可以用来直接将Entity Framework迁移应用到数据库：

```bash
dotnet ef database update
```

此命令反映了幂等脚本迁移。它检查最后应用的迁移，生成脚本直到最新的迁移，并将其应用到数据库。现在我们不必手动运行脚本，但缺点是我们也无法检查脚本是否正确。**此方法的另一个缺点是源代码和dotnet工具必须在生产机器上可用。**在服务器上暴露源代码是一个巨大的安全风险和不良实践。

所以现在让我们看看如何在不暴露源代码的情况下应用迁移。

### 使用Entity Framework迁移包

**Entity Framework迁移包是包含执行迁移所需一切的可执行二进制文件。**即使dotnet运行时也不是必需的，因为如果我们使用`--self-contained`选项构建它，可执行文件会包含它。让我们生成一个迁移包：

```bash
dotnet ef migrations bundle [--self-contained] [-r]
```

我们可以使用的两个主要选项是自包含标志，我们之前讨论过的，以及`-r`标志，它指定目标运行时。如果机器在与生产服务器相同的操作系统(例如：windows-x64)上运行，可以省略该标志。在Windows上的输出将是一个名为`efbundle.exe`的文件。

要应用迁移，我们必须将`appsettings.json`文件复制到与`efbundle.exe`文件相同的目录中，或使用`--connection`选项传递数据库的连接字符串：

```bash
./efbundle.exe --connection 'Server=.;Database=Weather;Trusted_Connection=True;Encrypt=False'
```

此外，我们可以使用[CICD](https://code-maze.com/what-is-continuous-integration/) pipeline来自动化这个方法。

**到目前为止，所有迁移选项的共同特点是它们允许我们独立于应用程序的部署来应用迁移。**如果应用程序的部署或数据库迁移失败，这可能会引起问题。只有迁移包方法是一个例外，当与CICD pipeline结合时。接下来，让我们探讨如何在运行时应用迁移。

## 在运行时自动化Entity Framework迁移

为了使Entity Framework迁移执行更加方便，我们可以在应用程序代码中触发它们在运行时。`DbContext`类暴露了一个`Database`属性，该属性具有`Migrate()`函数。然而，我们在运行时迁移数据库时必须小心。

在生产中，我们可能有多个应用程序实例在运行。如果一些同时启动，可能会导致它们都开始迁移并在数据库中引起冲突，甚至更糟的是死锁。此外，如果一些实例在为用户服务，而其他实例在迁移数据库，可能会导致意外的结果。

让我们通过创建两个`Startup`类来解决这些问题，一个用于迁移，另一个用于运行应用程序。我们基于命令行参数确定使用哪个`Startup`类。这样，在CICD pipeline中，我们可以用迁移`Startup`类启动应用程序，然后仅在迁移成功后继续启动应用程序。当实例重启时，它们将使用常规的`Startup`类，因此不会触发迁移。

### 创建两个Startup类以支持EF迁移

为了简化`Startup`类的选择，我们将实现一个工厂模式。首先，让我们创建一个`IStartup`接口：

```csharp
public interface IStartup
{
    Task StartAsync(string[] args);
}
```

我们的`Startup`类将实现我们的新接口。这对于工厂模式是必要的，这样工厂就可以返回一个通用接口，并且在`Program`类中我们可以在任意`Startup`类上调用`StartAsync()`方法。

现在，让我们创建工厂本身：

```csharp
public class StartupFactory
{
    public IStartup GetStartup(IEnumerable<string> args)
    {
        return args.Contains("--migrate") ? new MigrationStartup() : new WebApiStartup();
    }
}
```

我们简单地检查命令行参数中是否指定了`--migrate`选项，并返回相应的`Startup`类。

接下来，让我们创建我们的`Startup`类。我们将从将代码从我们的`Program`类移动到一个名为`WebApiStartup`的新类开始：

```csharp
public class WebApiStartup : IStartup
{
    public async Task StartAsync(string[] args)
    {
        //为简洁起见省略了代码

        await app.RunAsync();
    }
}
```

在这里，我们使用我们常规的`Startup`类来运行应用程序。唯一必要的更改是使用`app.RunAsync()`方法替代其同步版本。

现在，让我们创建`MigrationStartup`类：

```csharp
public class MigrationStartup : IStartup
{
    public async Task StartAsync(string[] args)
    {
        var builder = WebApplication.CreateBuilder(args);

        builder.Services.AddDbContext<WeatherDbContext>((sp, o) =>
        {
            o.UseSqlServer(builder.Configuration.GetConnectionString("SqlServer"));
        });
        var app = builder.Build();
        using var scope = app.Services.CreateScope();
        await scope.ServiceProvider.GetRequiredService<WeatherDbContext>().Database.MigrateAsync();
    }
}
```

在这里，我们仅注册`DbContext`到DI容器，因为其他服务对于运行Entity Framework迁移不是必须的。在构建应用后，我们在请求`WeatherDbContext`前创建一个范围。由于`WeatherDbContext`默认注册为`Scoped`服务，我们必须有一个范围来请求它。DI的根范围将无法为我们解决它。

然后我们调用`Database`属性的`MigrateAsync()`方法。与迁移包和幂等脚本类似，这也将检查什么是最新的迁移并且只应用更新的迁移。

最后，让我们在`Program`类中获取适当的`Startup`类：

```csharp
var startup = new StartupFactory().GetStartup(args);
await startup.StartAsync(args);
```

现在让我们看看如何开始迁移然后运行应用程序。

### 在启动时运行Entity Framework迁移

要应用迁移，我们在启动应用程序时添加`--migrate`标志：

```bash
./EfCoreCodeFirstMigrationsInProd --migrate
```

**最重要的好处是CICD集成的便利性。**但是，在开发环境中也很方便。它拥有迁移包的所有好处，但不需要额外的可执行文件，并且在所有环境中无缝工作。

## 结论

我们探讨了在生产中执行Entity Framework Core迁移的几种方式，每种方式都有其优点和缺点。重要的是要考虑在给定情况下哪些好处对我们最重要，以及我们可以容忍哪些缺点。
