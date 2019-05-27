---
layout: post
title:  "gRPC中集成asp.net identity实现oAuth认证"
date:   2019-05-27
tags: 
    - gRPC
---

# gRPC中集成asp.net identity实现oAuth认证

## 在asp.net core 3.0中开启identity认证

asp.net core 3.0种需要导入的identity包与core 2.2发生了些变化：

```xml
<ItemGroup>
  <PackageReference Include="Microsoft.AspNetCore.Diagnostics.EntityFrameworkCore" Version="3.0.0-preview5-19227-01" />
  <PackageReference Include="Microsoft.AspNetCore.Identity.EntityFrameworkCore" Version="3.0.0-preview5-19227-01" />
  <PackageReference Include="Microsoft.AspNetCore.Identity.UI" Version="3.0.0-preview5-19227-01" />
  <PackageReference Include="Microsoft.AspNetCore.Authentication.JwtBearer" Version="3.0.0-preview5-19227-01" />
  <PackageReference Include="Microsoft.AspNetCore.Mvc.NewtonsoftJson" Version="3.0.0-preview5-19227-01" />
  <PackageReference Include="Microsoft.EntityFrameworkCore.SqlServer" Version="3.0.0-preview5.19227.1" />
  <PackageReference Include="Microsoft.EntityFrameworkCore.Tools" Version="3.0.0-preview5.19227.1" />
</ItemGroup>

```

代码的配置方式变化不大，主要集中在ConfigureServices中：

```cs
services.AddDbContext<ApplicationDbContext>(options =>
    options.UseSqlServer(Configuration.GetConnectionString("DefaultConnection")));

services
    .AddDefaultIdentity<IdentityUser>(delegate (IdentityOptions options)
    {
        options.Password.RequiredLength = 6;
        options.Password.RequireLowercase = false;
        options.Password.RequireUppercase = false;
        options.Password.RequireNonAlphanumeric = false;
        options.Password.RequireDigit = false;
    })
    .AddEntityFrameworkStores<ApplicationDbContext>();

services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
    .AddJwtBearer(options =>
    {
        options.TokenValidationParameters = new TokenValidationParameters
        {
            LifetimeValidator = (before, expires, token, param) => expires > DateTime.UtcNow,
            ValidateAudience = false,
            ValidateIssuer = false,
            ValidateActor = false,
            ValidateLifetime = true,
            IssuerSigningKey = new SymmetricSecurityKey(Encoding.UTF8.GetBytes("41B71F9E-4204-4E88-8E91-64B1981F1B82"))
        };
    });
```

## 在asp.net core 3.0中同时集成gRPC与Restful API

在Kestrel中同时支持HTTP1与HTTP2：

```cs
public static IHostBuilder CreateHostBuilder(string[] args) =>
    Host.CreateDefaultBuilder(args)
        .ConfigureWebHostDefaults(webBuilder =>
        {
            webBuilder
                .ConfigureKestrel(options =>
                {
                    options.ListenLocalhost(50051, listenOptions =>
                    {
                        listenOptions.UseHttps("server.pfx", "1111");
                        listenOptions.Protocols = HttpProtocols.Http1AndHttp2;
                    });
                })
                .UseStartup<Startup>();
        });
```

需要特别注意的一点，关于Kestrel的[文档](https://docs.microsoft.com/en-us/aspnet/core/fundamentals/servers/kestrel?view=aspnetcore-2.2#listenoptionsprotocols)有提到，同时开启Http1与Http2需要TLS和ALPN导向HTTP/2，否则默认在HTTP1.1。

## 基于Bearer Token的gRPC服务授权

gRPC集成到asp.net core3.0之后，默认的授权方式可以直接使用在gRPC服务上：

```cs
[Authorize(AuthenticationSchemes = "Bearer")]
public class GreeterService : Greeter.GreeterBase
{
    public override Task<HelloReply> SayHello(HelloRequest request, ServerCallContext context)
    {
        return Task.FromResult(new HelloReply
        {
            Message = "Hello " + request.Name
        });
    }
}
```

完整代码请参考[Github代码库](https://github.com/celery94/GrpcCoreServer)