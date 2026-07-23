---
pubDatetime: 2026-07-23T08:22:01+08:00
title: "模块化单体数据库设计：一个库还是多个库？"
description: "在 C# 模块化单体中，数据库设计是第一个真正的架构关口。本文梳理三种策略──共享 DbContext、独立 DbContext 共享库、独立数据库──给出完整代码示例、决策框架和常见坑点，帮你选对方案。"
tags:
  ["Modular Monolith", "EF Core", "DbContext", "Software Architecture", ".NET"]
slug: "modular-monolith-database-design-csharp"
ogImage: "../../assets/966/01-cover.png"
source: "https://www.devleader.ca/2026/07/22/modular-monolith-database-design-in-c-one-database-or-multiple"
---

搭建 C# 模块化单体（Modular Monolith）时，最难的设计决策往往不是怎么切模块，而是怎么处理数据库。一个共享 DbContext？多个 DbContext 连同一个库？还是一个模块一个数据库？

这一步选错了，「模块化」就只剩文件夹结构了——模块边界被数据库耦合悄悄打穿。

本文梳理三种主流策略，给出可运行的代码示例和一个实用的决策框架，帮你在自己的项目里做出靠谱选择。

## 三种数据库策略

模块化单体的数据库设计可以归结为三个方向：

- **方案 A：一个共享数据库 + 一个共享 DbContext**。传统单体做法，上手最容易，但会悄悄消解模块边界。
- **方案 B：一个共享数据库 + 每个模块独立 DbContext**。务实折中，代码层面隔离强，运维复杂度低。
- **方案 C：每个模块独立数据库**。隔离最强，也是参考实现所用的方式。这条路走下去就是微服务就绪。

下面逐一拆解。

## 方案 A：共享 DbContext——为什么它会破坏模块边界

共享 DbContext 是大多数 .NET 单体项目的起点：一个 `AppDbContext`，用 `DbSet<>` 注册全应用的实体。它能跑，但它会逐渐瓦解你为模块化付出的努力。

耦合问题是潜伏性的。所有实体都在同一个 `DbContext` 里，任何模块都能在编译期引用其他模块的实体类型。Tasks 模块可以导入 Users 模块的 `User` 实体，写出跨模块的 LINQ 联表查询——这看起来很顺手，直到你想把 Tasks 模块拆成独立服务，才发现跨模块查询散落在代码库各个角落。

反模式长这样：

```csharp
// 不要这样做——整个应用共用一个 DbContext
public class AppDbContext : DbContext
{
    // 所有模块的实体堆在一起 = 隐藏的耦合
    public DbSet<User> Users { get; set; }
    public DbSet<Project> Projects { get; set; }
    public DbSet<TaskItem> Tasks { get; set; }
}

// 现在任何模块都能这样写——这就是问题本身
public class TaskRepository
{
    private readonly AppDbContext _context;

    public async Task<IEnumerable<TaskDto>> GetTasksWithUserNamesAsync()
    {
        // 这种跨模块联表本来就不该存在
        return await _context.Tasks
            .Join(_context.Users,
                t => t.AssignedUserId, u => u.Id,
                (t, u) => new TaskDto(t.Id, t.Title, u.Name))
            .ToListAsync();
    }
}
```

这段跨模块 Join 正是那种让模块化单体越维护越痛苦的隐藏依赖。当你打算把 Tasks 拆成微服务时，会发现这类联表散落各处，重构成本远超预期。

**方案 A 只适合作为重构过程中的过渡状态，绝不应该是目标状态。**

## 方案 B：独立 DbContext 共享数据库——务实的中间地带

方案 B 给你有意义的代码边界，同时不带来多数据库服务器的运维负担。每个模块有自己的 `DbContext`，只看自己的表；它们指向同一个物理库，但通过 EF Core 谁也看不到谁的实体。

关键技巧是用 EF Core schema 或表名前缀给每个模块的表划分命名空间：

```csharp
// 每个模块有自己隔离的 DbContext
public sealed class ProjectsDbContext : DbContext, IProjectsDbContext
{
    DbSet<Project> IProjectsDbContext.Projects => Set<Project>();

    public ProjectsDbContext(DbContextOptions<ProjectsDbContext> options)
        : base(options) { }

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        // Schema 把 projects 模块的所有表归入独立命名空间
        modelBuilder.HasDefaultSchema("projects");

        modelBuilder.Entity<Project>(entity =>
        {
            entity.HasKey(e => e.Id);
            entity.Property(e => e.Name).IsRequired().HasMaxLength(200);
            entity.Property(e => e.Description).HasMaxLength(1000);
            entity.Property(e => e.Status).IsRequired();
            entity.Property(e => e.CreatedAt).IsRequired();
        });
    }
}
```

每个模块在 DI 容器中独立注册自己的 DbContext。宿主项目提供连接串，但模块自己拥有配置逻辑：

```csharp
// ProjectsModuleExtensions.cs —— 模块自己掌管注册
public static IServiceCollection AddProjectsModule(
    this IServiceCollection services, string connectionString)
{
    services.AddDbContext<ProjectsDbContext>(options =>
        options.UseSqlServer(connectionString)); // 共享服务器，隔离上下文

    services.AddScoped<IProjectsDbContext>(
        sp => sp.GetRequiredService<ProjectsDbContext>());
    services.AddScoped<IProjectsModule, ProjectsModule>();

    return services;
}
```

方案 B 适合这些场景：只有一台数据库服务器要管、你要的是代码层隔离而不是基础设施层隔离、团队还没准备好处理分布式事务或最终一致性。对大多数第一次搭建模块化单体的团队来说，这是合理的默认选择。

代价是：隔离是「软」的。开发人员仍然可以写原始 SQL 跨模块联表。你需要团队纪律来守住边界，因为架构本身不会物理阻止违规。对多数团队而言，这个代价可以接受。

## 方案 C：每个模块独立数据库——参考实现的做法

方案 C 把模块隔离推到逻辑终点——每个模块有自己的物理数据库（或文件）。参考实现使用 SQLite，每个模块得到一个独立的 `.db` 文件。没有共享连接串，跨模块 SQL 联表物理上不可能做。架构本身在强制执行边界，不需要依赖团队纪律。

### ProjectsDbContext

```csharp
using Microsoft.EntityFrameworkCore;
using Projects.Application;
using Projects.Domain;

namespace Projects.Infrastructure;

public sealed class ProjectsDbContext : DbContext, IProjectsDbContext
{
    DbSet<Project> IProjectsDbContext.Projects => Set<Project>();

    public ProjectsDbContext(DbContextOptions<ProjectsDbContext> options)
        : base(options) { }

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.Entity<Project>(entity =>
        {
            entity.HasKey(e => e.Id);
            entity.Property(e => e.Name).IsRequired().HasMaxLength(200);
            entity.Property(e => e.Description).HasMaxLength(1000);
            entity.Property(e => e.Status).IsRequired();
            entity.Property(e => e.CreatedAt).IsRequired();
        });
    }
}
```

### TasksDbContext——注意没有 User 导航属性

```csharp
public sealed class TasksDbContext : DbContext, ITasksDbContext
{
    DbSet<TaskItem> ITasksDbContext.Tasks => Set<TaskItem>();

    public TasksDbContext(DbContextOptions<TasksDbContext> options)
        : base(options) { }

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.Entity<TaskItem>(entity =>
        {
            entity.HasKey(e => e.Id);
            entity.Property(e => e.ProjectId).IsRequired();
            entity.Property(e => e.Title).IsRequired().HasMaxLength(200);
            entity.Property(e => e.Description).HasMaxLength(1000);
            entity.Property(e => e.Status).IsRequired();
            entity.Property(e => e.AssignedUserId); // 只存 Guid，没有 User 导航属性
            entity.Property(e => e.CreatedAt).IsRequired();
        });
    }
}
```

注意 `TasksDbContext` 完全不引用 `User` 实体。`AssignedUserId` 存的是裸 `Guid`，没有指向 Users 模块的导航属性。这是故意的——也是独立数据库设计中最关键的细节之一。

### 模块注册

每个模块在 `Program.cs` 中接收自己的连接串，指向自己的 SQLite 文件：

```csharp
builder.Services.AddUsersModule("Data Source=users.db");
builder.Services.AddProjectsModule("Data Source=projects.db");
builder.Services.AddTasksModule("Data Source=tasks.db");
```

模块只对外暴露 `IProjectsModule` 接口，其他模块永远看不到 `ProjectsDbContext` 本身。

## 跨模块数据需求怎么处理？

这才是难点。Tasks 模块里存了 `AssignedUserId`，但如果你想在任务旁边显示用户名怎么办？Users 的数据在完全独立的数据库里。

**错误的做法**是把 `IUsersModule` 注入到 `TasksModule` 里，每次需要名字都同步调用。这样 Tasks 就对 Users 产生了编译期依赖，之前费心做的隔离打了折扣：

```csharp
// 错误做法——Tasks 模块通过直接依赖拿到 Users 模块的数据
public class TasksModule : ITasksModule
{
    private readonly ITasksDbContext _db;
    private readonly IUsersModule _usersModule; // 避免这种依赖

    public async Task<TaskDetailDto> GetTaskAsync(Guid taskId)
    {
        var task = await _db.Tasks.FindAsync(taskId);
        // 同步跨模块调用产生紧耦合
        var user = await _usersModule.GetUserAsync(task.AssignedUserId!.Value);
        return new TaskDetailDto(task.Id, task.Title, user?.Name);
    }
}
```

**正确的做法**是用事件。当用户注册时，`UserRegisteredEvent` 被触发，Tasks 模块可以监听这个事件，把用户名缓存到自己的本地库。这样 Tasks 在运行时不碰 Users 数据库就能拿到需要的数据。

```csharp
// 正确做法——Tasks 模块只存 ID，没有跨模块依赖
public class TaskItem
{
    public Guid Id { get; private set; }
    public Guid ProjectId { get; private set; }
    public string Title { get; private set; } = string.Empty;
    public Guid? AssignedUserId { get; private set; } // 只有 ID，没有导航属性
    // ...
}
```

这本质上是将观察者模式应用到模块通信层面——模块对事件做出反应，但不知道事件是谁发布的。在基于 MediatR 的架构中，你可以在 Tasks 模块里用 `INotificationHandler<UserRegisteredEvent>` 接收并缓存事件数据。

## EF Core 迁移：多 DbContext 怎么管理？

多 DbContext 的 EF Core 迁移管理并不复杂，关键是每条命令都要加 `--context` 参数：

```bash
# 为 Projects 模块的 DbContext 添加迁移
dotnet ef migrations add InitialCreate \
    --context ProjectsDbContext \
    --project src/Modules/Projects/Projects.Infrastructure \
    --startup-project src/Host

# 只对 Projects 模块应用迁移
dotnet ef database update \
    --context ProjectsDbContext \
    --project src/Modules/Projects/Projects.Infrastructure \
    --startup-project src/Host

# 独立为 Tasks 模块添加迁移
dotnet ef migrations add InitialCreate \
    --context TasksDbContext \
    --project src/Modules/Tasks/Tasks.Infrastructure \
    --startup-project src/Host
```

每个模块的 Infrastructure 项目维护自己的 `Migrations` 文件夹。修改 Projects 模块的实体时，你只给 `ProjectsDbContext` 加迁移——Tasks 和 Users 模块完全不受影响。这种独立性随系统增长会变得越来越有价值。

方案 B（共享数据库）下仍然用 `--context` 参数，所有迁移指向同一个物理库。方案 C 下每个迁移指向独立的数据库文件或服务器，彻底独立。

参考实现为了简单使用了 `EnsureCreatedAsync`：

```csharp
using (var scope = app.Services.CreateScope())
{
    var usersDb = scope.ServiceProvider.GetRequiredService<UsersDbContext>();
    await usersDb.Database.EnsureCreatedAsync();

    var projectsDb = scope.ServiceProvider.GetRequiredService<ProjectsDbContext>();
    await projectsDb.Database.EnsureCreatedAsync();

    var tasksDb = scope.ServiceProvider.GetRequiredService<TasksDbContext>();
    await tasksDb.Database.EnsureCreatedAsync();
}
```

生产环境请用 `MigrateAsync` 替代。`EnsureCreatedAsync` 能建表，但完全绕过了迁移基础设施——一旦你需要变更 schema，就没有迁移历史可用了。

## 你该选哪个？一个决策框架

| 维度         | 方案 A（共享 DbContext） | 方案 B（独立 Context，共享库） | 方案 C（独立数据库） |
| ------------ | ------------------------ | ------------------------------ | -------------------- |
| 隔离级别     | 无                       | 代码层                         | 架构层               |
| 运维复杂度   | 低                       | 低                             | 中                   |
| 跨模块联表   | 可行（危险）             | EF 阻止，SQL 不阻止            | 不可能               |
| 微服务提取   | 困难                     | 中等                           | 容易                 |
| 团队纪律要求 | 高                       | 中                             | 低                   |
| Schema 演化  | 一套迁移                 | 每模块独立迁移                 | 每模块每库独立迁移   |
| 最适合       | 临时重构过渡             | **大多数团队**                 | 有微服务路线图的团队 |

**选方案 A**：仅当你正在改造既有单体、立即拆分 DbContext 不现实时。把它当过渡状态，不要当目的地。

**选方案 B**：当你想要干净的模块边界但不想引入分布式系统复杂度。这是大多数团队第一次搭建模块化单体时的正确默认选择。你得到了模块化设计的结构化收益，却不必承担多数据库服务器的运维开销。

**选方案 C**：当你有一条明确的微服务路线图、DevOps 成熟度高、团队能驾驭最终一致性。参考实现用 SQLite 演示了这个模式——生产环境中可以扩展为独立的 PostgreSQL 库、不同服务器上的独立 schema，或者你的基础设施支持的任何形态。

## 常见错误

**跨模块注入 DbContext**：最常见的错误是把一个模块的 `DbContext` 直接注入到另一个模块的服务或仓储中。如果 `TasksModule` 在构造函数里拿了 `ProjectsDbContext`，你就在基础设施层把两个模块焊死在了一起。只通过模块接口抽象（如 `IProjectsModule`）通信，永远不让 `DbContext` 逃出它所属的程序集。

**跨模块 LINQ 内存联表**：即使用了独立 DbContext，有时开发人员还是会从两个模块分别加载数据再在内存中 Join。大量内存联表是性能隐患。如果你经常做这件事，要么模块边界画错了，要么需要通过事件缓存相关数据。

**实体类型泄漏到模块边界外**：如果 Tasks 模块引用了 `Projects.Domain.Project`，你就把领域实体泄漏了。每个模块的实体应对其他模块不可见。`TasksDbContext` 没有 `DbSet<Project>`，`ProjectsDbContext` 没有 `DbSet<TaskItem>`——这种分离正是每个模块未来可独立部署的基础。

**生产环境用 EnsureCreatedAsync**：演示和本地开发可以，但生产环境它创建 schema 的同时绕过了 EF Core 迁移基础设施。一旦需要演化 schema，就没有迁移历史可追溯。生产部署请用 `MigrateAsync`。

**忽视最终一致性**：独立数据库意味着跨模块不再有 ACID 事务。一个任务可能引用了一个 Users 库里已经不存在 User ID。你的应用需要优雅处理这些场景——通过 API 边界校验、软删除或事件驱动清理。

## 小结

模块化单体的数据库设计本质上是在便利性和隔离性之间做选择。共享 DbContext 最熟悉但也最危险；独立 DbContext 共享一个库是大多数团队的甜蜜点；独立数据库隔离最强但对团队和基础设施要求也最高。

不管你选哪条路，核心原则不变：**模块边界必须在代码层面被强制执行，而不能只写在文档里。** 接口抽象（如 `IProjectsDbContext`）、模块自有的注册方法（如 `AddProjectsModule`）、严格避免跨模块实体引用——这些东西才是让模块化单体真正「模块化」的关键，今天如此，系统增长后依然如此。

如果你关注 .NET 架构、开发工具和软件工程实践，可以关注 **Aide Hub**。这里会持续分享能落地的技术内容。

## 参考

- [Modular Monolith Database Design in C#: One Database or Multiple?](https://www.devleader.ca/2026/07/22/modular-monolith-database-design-in-c-one-database-or-multiple)
- [EF Core tools documentation (Microsoft Learn)](https://learn.microsoft.com/en-us/ef/core/cli/dotnet)
- [Keyed Services in Needlr: Managing Multiple Implementations](https://www.devleader.ca/2026/02/19/keyed-services-in-needlr-managing-multiple-implementations)
- [Observer Design Pattern in C#](https://www.devleader.ca/2026/03/26/observer-design-pattern-in-c-complete-guide-with-examples)
- [Strategy Design Pattern in C#](https://www.devleader.ca/2026/03/02/strategy-design-pattern-in-c-complete-guide-with-examples)
