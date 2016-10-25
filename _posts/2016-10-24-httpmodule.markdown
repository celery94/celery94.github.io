---
layout: post
title:  "About Http Module"
date:   2016-10-24
tags: 
    - .net
    - asp.net
---

## 什么是Http Module

HTTP 模块是一个在每一次Http请求时调用的程序集。
HTTP 模块作为 ASP.NET 请求管线的一部分调用，它们能够在整个请求过程中访问寿命周期事件。
因此，HTTP 模块使您有机会检查传入的请求并根据该请求采取操作。
它们还使您有机会检查**出站**响应并修改它，也就是在普通请求结束是追加处理。

ASP.NET HTTP 模块针对所有的请求运行，这与 ISAPI 筛选器类似。
但是它们是用托管代码编写的，而且可以与 ASP.NET 应用程序的生命周期完全集成。

> ISAPI筛选器：类似于Windows的钩子，ISAPI筛选器将在发生某些特定事件的时候被调用（例如客户请求网页），可监视、拦截或修改客户端与服务器直接的传输数据。常用作数据库防下载、加密和压缩数据、统计访问人数等。

> ISAPI扩展：aspnet_isapi.dll就是一个ISAPI扩展。IIS接收到请求时，会对所请求的文件的文件扩展名进行检查，确定应由哪个 ISAPI 扩展处理该请求，然后将该请求传递给合适的 ISAPI 扩展。ASP.NET 处理已映射到其上的文件扩展名，如 .aspx、.ascx、.ashx 和 .asmx。

## Http Module的工作方式

在应用程序的 Web.config 文件中注册自定义的 HTTP 模块。
当 ASP.NET 创建表示您的应用程序的 HttpApplication 类的实例时，将创建已注册的任何模块的实例。
在创建模块时，将调用它的 Init 方法，并且模块会自行初始化。

在模块的 Init 方法内，可以订阅各种应用程序事件（如 BeginRequest 或 EndRequest），这可以通过将事件绑定到模块中已创建的方法来完成。
当这些事件被引发时，会调用模块中适当的方法，并且模块可以执行所需的任何逻辑，如身份验证检查或记录请求信息。
在事件处理过程中，模块能够访问当前请求的 Context 属性。这使您可以将请求重定向到其他页、修改请求或者执行任何其他请求操作。

例如，如果您的模块中包括身份验证检查，则模块可能会检查凭据，如果凭据不正确的话，会重定向到登录页或错误页。
否则，当模块的事件处理程序完成运行时，ASP.NET 会调用管线中的下一个进程，这可能是另一个模块，也可能是用于该请求的 HTTP 处理程序（如 .aspx 文件）。

## Http Module的应用场景

ASP.NET 使用模块来实现各个应用程序功能，包括 Forms 身份验证、缓存、会话状态和客户端脚本服务。
在每种情况下，如果这些服务处于启用状态，模块会作为请求的一部分调用，并执行在任何单一页请求范围之外的任务。
模块可以使用应用程序事件，可能会引发可在 Global.asax 文件中处理的事件。

HTTP 模块典型的用法包括：

* 安全性。因为您可以检查传入的请求，所以 HTTP 模块可以在请求页、XML Web services 或调用处理程序之前执行自定义的身份验证或其他安全检查。
* 统计信息和日志记录。因为 HTTP 模块是在每次请求时调用的，所以，您可以将请求统计信息和日志记录信息收集到一个集中的模块中，而不是收集到各页中。
* 自定义的页眉或页脚。因为您可以修改出站响应，所以可以在每一个页面或 XML Web services 响应中注入内容，如自定义的标头信息。

## Http Module与Global.asax的区别

IIS初始化所有核心应用程序对象之后，将通过创建 HttpApplication 类的实例启动应用程序。
如果应用程序具有 Global.asax 文件，则 ASP.NET 会创建 Global.asax 类（从 HttpApplication 类派生）的一个实例，并使用该派生类表示应用程序。

可以在应用程序的 Global.asax 文件中实现模块的许多功能，这使您可以响应应用程序事件。
但是，模块相对于 Global.asax 文件具有如下优点：模块可以进行封装，因此可以在创建一次后在许多不同的应用程序中使用。
通过将它们添加到全局程序集缓存 (GAC) 并将它们注册到 Machine.config 文件中，可以跨应用程序重新使用它们。
但是，使用 Global.asax 文件有一个好处，那就是您可以将代码放在其他已注册的模块事件（如 Session_Start 和 Session_End 方法）中。
此外，Global.asax 文件还允许您实例化可在整个应用程序中使用的全局对象。

当您需要创建依赖应用程序事件的代码并且希望在其他应用程序中重用模块时，或者不希望将复杂代码放在 Global.asax 文件中时，应当使用模块。

当您需要创建依赖应用程序事件的代码但不需要跨应用程序重用它时，或者需要订阅不可用于模块的事件（如 Session_Start）时，应当将代码放在 Global.asax 文件中。

## 创建自定义的Http Module

{% highlight C# %}
public class HelloWorldModule : IHttpModule
{
    public HelloWorldModule()
    {
    }

    public String ModuleName
    {
        get { return "HelloWorldModule"; }
    }

    // In the Init function, register for HttpApplication 

    // events by adding your handlers.

    public void Init(HttpApplication application)
    {
        application.BeginRequest += (new EventHandler(this.Application_BeginRequest));
        application.EndRequest += (new EventHandler(this.Application_EndRequest));
    }

    private void Application_BeginRequest(Object source, EventArgs e)
    {
        // Create HttpApplication and HttpContext objects to access

        // request and response properties.

        HttpApplication application = (HttpApplication)source;
        HttpContext context = application.Context;
        context.Response.Write("<h1><font color=red>HelloWorldModule: Beginning of Request</font></h1><hr>");
    }

    private void Application_EndRequest(Object source, EventArgs e)
    {
        HttpApplication application = (HttpApplication)source;
        HttpContext context = application.Context;
        context.Response.Write("<hr><h1><font color=red>HelloWorldModule: End of Request</font></h1>");
    }

    public void Dispose()
    {
    }
}
{% endhighlight %}

在Web.Config中注册 HTTP 模块
{% highlight xml %}
<configuration>
    <system.web>
        <httpModules>
            <add name="HelloWorldModule" type="HelloWorldModule"/>
        </httpModules>
    </system.web>
</configuration>
{% endhighlight %}

