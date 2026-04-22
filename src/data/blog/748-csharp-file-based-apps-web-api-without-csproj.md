---
pubDatetime: 2026-04-22T09:40:00+08:00
title: "不要 .csproj 也能行：用 .NET 11 file-based app 构建完整 Web API"
description: "作者用一个周末验证了一件事：.NET 11 的 file-based apps 特性能不能支撑起一个真实的 ASP.NET Core Web API。结果是能——只需一个 .cs 文件入口，发布产物是 30 MB 的单一原生二进制，感觉跟写 Go 服务没多大区别。EF Core 迁移是目前唯一没解决干净的地方。"
tags: [".NET", "C#", "ASP.NET Core", "Native AOT", "EF Core"]
slug: "csharp-file-based-apps-web-api-without-csproj"
ogImage: "../../assets/748/01-cover.png"
source: "https://makarchie.com/posts/csharp-that-looks-like-go-file-based-apps/"
---

![不要 .csproj 也能行：用 .NET 11 file-based app 构建完整 Web API](../../assets/748/01-cover.png)

作者 Artem Makarov 花了一个周末验证一件事：能不能用 .NET 11 的 file-based apps 特性，在没有 `.csproj` 的情况下，搭出一个真实的 ASP.NET Core Web API——不是 Hello World，而是带 EF Core、PostgreSQL、迁移、OpenAPI、中间件和 PATCH 端点的分层 CRUD 服务。

结论是：能。实验结果放在 GitHub 仓库 [csharp-looks-like-go](https://github.com/archie1602/csharp-looks-like-go)。他说，写完之后整个项目"感觉很像在写一个小的 Go 服务"——对于一个用 C# 六年的人来说，这不是他预期会打出来的话。

## file-based app 是什么

这个特性从 .NET 10 开始引入，在 .NET 11 preview 3 里进一步成熟。核心想法很简单：你可以直接运行、发布、交付一个 `.cs` 文件，不需要创建 `.csproj`，也不需要 solution 文件。

SDK 所需的一切配置，通过文件顶部的预处理指令声明：

```csharp
#!/usr/bin/env dotnet run
#:property TargetFramework=net11.0
#:property LangVersion=preview
#:sdk Microsoft.NET.Sdk.Web
#:package Npgsql.EntityFrameworkCore.PostgreSQL@10.0.1
#:include domain/user.cs

var app = WebApplication.CreateBuilder(args).Build();
app.MapGet("/", () => "hello from a file-based app");
app.Run();
```

上面这段就是 `main.cs` 的全部开头。运行方式是 `dotnet run main.cs`。加上 shebang 并 `chmod +x`，可以像 Python 脚本一样直接执行 `./main.cs`。

作者最常用的五个指令：

- `#:sdk`：选择 SDK（`Microsoft.NET.Sdk.Web` 用于 ASP.NET Core）
- `#:package`：引入 NuGet 包，可用 `@version` 固定版本
- `#:property`：设置 MSBuild 属性，相当于以前 `.csproj` 里的 `<PropertyGroup>` 内容
- `#:include`：把另一个 `.cs` 文件纳入编译单元
- `#:property ExperimentalFileBasedProgramEnableTransitiveDirectives=true`：开启指令的传递性

最后这个传递性标志尤其关键。没有它，所有包引用和文件包含必须堆在 `main.cs` 里；开启后，指令可以从被 include 的文件里传播出来，整个项目才能真正按模块拆分。

## 项目结构

作者的仓库采用分层架构：`handler -> service -> repository -> db`，两个实体（`User` 和 `Post`），一对多关系。整体目录结构如下：

```
csharp-looks-like-go/
├── main.cs          # 入口、属性、路由表
├── packages.cs      # #:sdk + #:package 声明
├── includes.cs      # 所有 #:include 的平铺列表
├── globals.cs       # global using 指令
├── config/
├── db/
├── domain/
├── handler/
├── middleware/
├── migrations/
├── model/
├── repository/
├── service/
└── util/
```

顶部四个文件是"项目级配置"，其余都是业务代码。`main.cs` 只有几行，可以在一屏内读完。

文件名用 `snake_case`，命名空间用小写单数（`handler`、`service`、`repository`），服务类用 C# 12 的主构造函数语法：

```csharp
class UserService(UserRepository repository)
{
    public Task<IReadOnlyList<User>> List() => repository.List();

    public async Task<User> Create(CreateUserRequest request)
    {
        var name = request.Name.RequireNonEmpty(nameof(request.Name));
        var email = request.Email.RequireNonEmpty(nameof(request.Email));
        await EnsureEmailIsUnique(email);
        return await repository.Create(name, email);
    }
    // ...
}
```

`RequireNonEmpty` 是放在 `util/string_utils.cs` 里的扩展方法，用了 C# 14 的新 `extension(string str)` 块语法：

```csharp
namespace util;

static class StringExtensions
{
    extension(string str)
    {
        public string RequireNonEmpty(string fieldName)
        {
            var trimmed = str.Trim();
            if (string.IsNullOrWhiteSpace(trimmed))
                throw new ArgumentException($"{fieldName} is required");
            return trimmed;
        }
    }
}
```

和以前的 `public static string X(this string s)` 语法相比，新写法更简洁，也支持扩展属性和静态扩展成员。

实体类用 `required` 属性，不再写 `= null!;`：

```csharp
class User
{
    public long Id { get; set; }
    public required string Name { get; set; }
    public required string Email { get; set; }
    public ICollection<Post> Posts { get; set; } = [];
}
```

方法名去掉了 `Async` 后缀——这是个服务，不是库，每个方法都是 async，后缀在调用端没有信息量。

## 发布产物：30 MB 单一二进制

让作者觉得有必要写这篇文章的不是指令系统，而是发布命令的结果：

```bash
dotnet publish main.cs -o bin
```

输出是单个 `bin/main` 文件，33 MB，原生 Mach-O 可执行文件（AOT 编译），目标机器不需要安装 .NET Runtime，也不需要 `dotnet` CLI。

加几个体积优化参数后可以压到约 30 MB：

```bash
dotnet publish main.cs -o bin \
  -p:OptimizationPreference=Size \
  -p:InvariantGlobalization=true \
  -p:DebuggerSupport=false \
  -p:EventSourceSupport=false \
  -p:HttpActivityPropagationSupport=false \
  -p:StripSymbols=true
```

这个 30 MB 里包含了 ASP.NET Core、EF Core、Npgsql 驱动、内置 OpenAPI、验证逻辑。`scp` 到 Linux 服务器，直接运行，没有其他依赖。

写 Go 的人对这个模式不陌生——`go build` 就是这样的。对 C# 开发者来说，这可能是第一次 `dotnet publish` 没有输出一个包含几十个文件的目录。

## 唯一没解决干净的地方：EF Core 迁移

作者在这里没有绕弯子。

`dotnet ef` 目前不识别 file-based apps。`dotnet ef migrations add` 需要解析 `.csproj`，而它不存在。传 `--project main.cs` 的话，工具会把 `main.cs` 当 MSBuild XML 去解析，立刻报错。EF Core 10 stable 和 EF 11 preview 都试过，结果一样。

变通方案：在代码旁边临时生成一个 `.csproj`，对它运行 EF，完了删掉。

仓库里记录了一个放在 `.tooling/tooling.csproj` 的最小项目文件，用 glob 把父目录里的实体和 DbContext 文件包进来：

```xml
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net10.0</TargetFramework>
    <RootNamespace>minimal_web_api</RootNamespace>
  </PropertyGroup>
  <ItemGroup>
    <PackageReference Include="Microsoft.EntityFrameworkCore.Design" Version="10.0.0">
      <PrivateAssets>all</PrivateAssets>
    </PackageReference>
    <PackageReference Include="Npgsql.EntityFrameworkCore.PostgreSQL" Version="10.0.1" />
  </ItemGroup>
  <ItemGroup>
    <Compile Remove="**/*.cs" />
    <Compile Include="design_time_factory.cs" />
    <Compile Include="..\domain\*.cs" />
    <Compile Include="..\db\*.cs" />
    <Compile Include="..\migrations\*.cs" />
  </ItemGroup>
</Project>
```

加一个带连接字符串的 `IDesignTimeDbContextFactory<AppDbContext>`，然后执行：

```bash
cd .tooling
dotnet ef migrations add AddPosts \
  --output-dir ../migrations \
  --namespace minimal_web_api.migrations
cd ..
rm -rf .tooling
```

第一次还需要手动把 `AppDbContextModelSnapshot.cs` 从工具项目的输出路径挪回 `migrations/`，因为 EF 按工具项目根路径写快照，不管 `--output-dir` 怎么设置。第二次做就习惯了，第一次确实容易绕晕。

作者说，这是他目前不会把团队项目迁移到 file-based apps 的主要原因——其他地方感觉已经生产就绪，迁移这块还不是。

## 适合哪些场景

根据这个周末的实验，作者给出的判断：

**现在比较适合：**

- 小型微服务——`.csproj` + `.sln` 的仪式感本来就和代码量不成比例
- CLI 工具和脚本——`#:package` + `chmod +x` 直接替代 `dotnet tool install` 那套流程
- 教学场景——以前教 C# 的第一件事是 `dotnet new console`，跟着出来一堆文件；现在 `echo '...' > hi.cs && dotnet run hi.cs` 是更好的第一印象
- Demo 仓库和博客配套代码——整个项目可以直接 grep

**还不适合：**

- 频繁调整 schema 的 EF 密集型项目
- 依赖仍然假定 `.csproj` 存在的工具（部分分析器、部分 IDE 功能）
- 团队还在 .NET 9 或更低版本的项目

## 几个让作者意外的瞬间

- 加 `#!/usr/bin/env dotnet run` 头、`chmod +x` 后直接 `./main.cs` 运行，逻辑上显然，但实际操作时还是有点新鲜
- 第一次 `dotnet publish main.cs` 就输出了一个单一原生二进制，EF Core 在依赖图里，有 trim 警告但没有硬错误
- C# 14 的 `extension(string str)` 块语法确实比 `public static string X(this string s)` 更简洁，十三年来第一次觉得扩展方法的写法变好了
- `required` 属性让实体定义少了五行，之前写 `= null!;` 已经成了肌肉记忆

作者的总结是：这些功能本身大多不是新的——原生 AOT 有一阵子了，主构造函数是 C# 12，`required` 是 C# 11，扩展成员是 C# 14。但 file-based apps 第一次把这些东西整合到一个配置里，让 C# 项目在视觉上接近 Go 项目的感觉。他说找不到更好的词，就是"气质变了"。

## 参考

- [原文：C# That Looks Like Go: Building a Web API Without a .csproj](https://makarchie.com/posts/csharp-that-looks-like-go-file-based-apps/)
- [示例仓库：csharp-looks-like-go](https://github.com/archie1602/csharp-looks-like-go)
