---
pubDatetime: 2024-07-06
tags: []
source: https://www.milanjovanovic.tech/blog/service-discovery-in-microservices-with-net-and-consul
author: Milan Jovanović
title: 使用.NET和Consul实现微服务中的服务发现
description: 服务发现是一种模式，允许开发人员使用逻辑名称而不是物理IP地址和端口来引用外部服务。在本期文章中，我们将学习如何在.NET微服务中使用Consul实现服务发现。
---

微服务改变了我们构建和扩展应用程序的方式。通过将大型系统分解为更小的独立服务，我们获得了灵活性、敏捷性，以及快速适应不断变化需求的能力。然而，微服务系统也非常动态。服务可能会出现或消失，进行扩展或缩减，甚至在您的基础设施中移动。

这种动态特性带来了一个重大挑战。您的服务如何可靠地找到并相互通信？

硬编码IP地址和端口是脆弱的。如果一个服务实例改变位置或新的实例启动，您的整个系统可能会停滞不前。

服务发现充当您的微服务的中央目录。它为服务提供注册自身和发现其他服务位置的机制。

在本期文章中，我们将学习如何在.NET微服务中使用Consul实现服务发现。

## [什么是服务发现？](https://www.milanjovanovic.tech/blog/service-discovery-in-microservices-with-net-and-consul#what-is-service-discovery)

服务发现是一种模式，允许开发人员使用逻辑名称来引用外部服务，而不是物理IP地址和端口。它为服务提供一个集中注册的位置。客户端可以查询服务注册表以获取服务的物理地址。这是大规模分布式系统中的常见模式，如Netflix和Amazon。

以下是服务发现的流程：

1. 服务会在服务注册表中注册自身
2. 客户端必须查询服务注册表以获取物理地址
3. 客户端使用解析后的物理地址向服务发送请求

![服务发现流程。](https://www.milanjovanovic.tech/blogs/mnw_097/service_discovery_flow.png?imwidth=3840)

当我们有多个要调用的服务时，也适用相同的概念。每个服务都会在服务注册表中注册自身。客户端使用逻辑名称引用服务，并从服务注册表中解析物理地址。

![多微服务服务发现。](https://www.milanjovanovic.tech/blogs/mnw_097/service_discovery_microservices.png?imwidth=3840)

服务发现的最流行解决方案是Netflix [Eureka](https://github.com/Netflix/eureka)和HashiCorp [Consul](https://www.consul.io/)。

微软也有一个轻量级的解决方案，即`Microsoft.Extensions.ServiceDiscovery`库。它使用应用程序设置来解析服务的物理地址，因此仍需进行一些手动工作。不过，您可以在[Azure App Configuration](https://azure.microsoft.com/en-us/products/app-configuration)中存储服务位置，以实现集中式服务注册表。我将在未来的一些文章中探讨这个服务发现库。

但现在我想向您展示如何将Consul与.NET应用程序集成。

## [设置Consul服务器](https://www.milanjovanovic.tech/blog/service-discovery-in-microservices-with-net-and-consul#setting-up-the-consul-server)

在本地运行Consul服务器的最简单方法是使用Docker容器。您可以创建`hashicorp/consul`镜像的容器实例。

以下是作为`docker-compose`文件的一部分配置Consul服务的示例：

```
consul:
  image: hashicorp/consul:latest
  container_name: Consul
  ports:
    - '8500:8500'
```

如果您导航到`localhost:8500`，您将看到Consul仪表板。

![Consul仪表板。](https://www.milanjovanovic.tech/blogs/mnw_097/consul_dashboard.png?imwidth=3840)

现在，让我们看看如何在Consul中注册我们的服务。

## [在.NET中使用Consul进行服务注册](https://www.milanjovanovic.tech/blog/service-discovery-in-microservices-with-net-and-consul#service-registration-in-net-with-consul)

我们将使用[Steeltoe Discovery](https://docs.steeltoe.io/api/v3/discovery/)库来实现与Consul的服务发现。Consul客户端实现允许您的应用程序向Consul服务器注册服务，并发现其他应用程序注册的服务。

让我们安装`Steeltoe.Discovery.Consul`库：

```
Install-Package Steeltoe.Discovery.Consul
```

我们需要通过调用`AddServiceDiscovery`并显式配置Consul服务发现客户端来配置一些服务。另一种选择是调用`AddDiscoveryClient`，它在运行时使用反射来确定可用的服务注册表。

```
using Steeltoe.Discovery.Client;
using Steeltoe.Discovery.Consul;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddServiceDiscovery(o => o.UseConsul());

var app = builder.Build();

app.Run();
```

最后，我们的服务可以通过应用程序设置配置逻辑服务名称来注册到Consul。当应用程序启动时，`reporting-service`逻辑名称将被添加到Consul服务注册表中。Consul将存储该服务的相应物理地址。

```
{
  "Consul": {
    "Host": "localhost",
    "Port": 8500,
    "Discovery": {
      "ServiceName": "reporting-service",
      "Hostname": "reporting-api",
      "Port": 8080
    }
  }
}
```

当我们启动应用程序并打开Consul仪表板时，我们应该能够看到`reporting-service`及其相应的物理地址。

![带有注册服务的Consul仪表板。](https://www.milanjovanovic.tech/blogs/mnw_097/consul_dashboard_with_service.png?imwidth=3840)

## [使用服务发现](https://www.milanjovanovic.tech/blog/service-discovery-in-microservices-with-net-and-consul#using-service-discovery)

我们可以在使用`HttpClient`进行HTTP调用时使用服务发现。服务发现允许我们为要调用的服务使用逻辑名称。发送网络请求时，服务发现客户端将用正确的物理地址替换逻辑名称。

在此示例中，我们将`ReportingServiceClient`类型客户端的基地址配置为`http://reporting-service`，并通过调用`AddServiceDiscovery`添加服务发现。

负载均衡是一个可选步骤，我们可以通过调用`AddRoundRobinLoadBalancer`或`AddRandomLoadBalancer`来配置负载均衡。您还可以通过提供`ILoadBalancer`实现来配置自定义负载均衡策略。

```
builder.Services
    .AddHttpClient<ReportingServiceClient>(client =>
    {
        client.BaseAddress = new Uri("http://reporting-service");
    })
    .AddServiceDiscovery()
    .AddRoundRobinLoadBalancer();
```

我们可以使用`Report ```csharp
e");
})
.AddServiceDiscovery()
.AddRoundRobinLoadBalancer();

````

我们可以像使用普通的`HttpClient`一样使用`ReportingServiceClient`类型的客户端来进行请求。服务发现客户端会将请求发送到外部服务的IP地址。

```csharp
app.MapGet("articles/{id}/report",
    async (Guid id, ReportingServiceClient client) =>
    {
        var response = await client
            .GetFromJsonAsync<Response>($"api/reports/article/{id}");

        return response;
    });
````

## [总结](https://www.milanjovanovic.tech/blog/service-discovery-in-microservices-with-net-and-consul#takeaway)

服务发现通过自动化服务注册和发现简化了微服务的管理。这消除了手动配置更新的需要，降低了出错的风险。

服务可以按需发现彼此的位置，确保即使服务环境发生变化，通信渠道仍然保持开放。通过使服务能够在中断或故障时发现其他服务实例，服务发现增强了微服务系统的整体弹性。

掌握服务发现为构建现代分布式应用程序提供了强大的工具。

您可以在[此处获取此示例的源代码](https://github.com/m-jovanovic/service-discovery-consul)。
