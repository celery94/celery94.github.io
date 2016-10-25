---
layout: post
title:  "ASP.NET MVC 生命周期"
date:   2016-10-24
tags: 
    - .net
    - asp.net
---

原文：[MVC Application Lifecycle](http://www.codeproject.com/Articles/741228/MVC-Application-Lifecycle)

## Introduction

这篇文件我们将要讨论MVC Application的生命周期和请求在各个模块的传递中是如何被处理的。
我们将要按在程序的生命周期中的顺序来讨论这些模块。
我们也将考虑每个组件以及它们与其他组件在管道中关系。

## Background

作为开发人员，我们都知道一些被MVC框架使用来处理请求的组件。
大部分时间我们都是在处理Controller和Action，同时也在处理不同的ActionResult和View。

但是，我们知道关于参与请求处理其他重要的组成部分么？这些请求在管道中是如何流动的？

当我开始学习MVC的时候，我不明白的是请求从一个组件如何流向另一个的。
此外，我也不清楚了HTTP module和Http handler在请求处理中扮演的角色。
毕竟MVC是一个Web开发框架，所以Http module和Http handler一定在管道中参与了处理。

有很多的模块参与了请求的处理管道，然后我们知道，controller和action参与了处理，这些也是在处理中的重要角色。

虽然大多数的时候我们可以使用该框架提供的默认功能，但如果我们了解为什么是为了可以方便地更换部件，或提供自定义实现组件。

## UrlRoutingModule

这是MVC应用程序的入口。

请求首先会被UrlRoutingModule截获，这是一个Http Module。
正是这种模块，决定请求是否会被MVC应用程序进行处理。
UrlRouting模块选择第一个匹配的路由。

UrlRoutingModule是如何匹配请求于路由的呢？
如果你看看从在Global.asax调用的RegisterRoutes方法，你会发现，这里将路由添加到路由RouteCollection。
这个方法是在Global.asax的Application_Start事件处理函数中调用的。
正是这个的RegisterRoutes方法，在注册应用程序的所有路由。

{% highlight C# %}
RouteConfig.RegisterRoutes(RouteTable.Routes);
public static void RegisterRoutes(RouteCollection routes)
{
    routes.IgnoreRoute("{resource}.axd/{*pathInfo}");

    routes.MapRoute(
        name: "Default",
        url: "{controller}/{action}/{id}",
        defaults: new { controller = "Home", action = "Index", id = UrlParameter.Optional }
    );
}
{% endhighlight %}

现在你可能会问的UrlRoutingModule是如何知道这些路由和路由如何与RouteHandler关联？
UrlRoutingModule使用MapRoute方法来获取关联。
如果你查看MapRoute方法，你会发现，它被定义为一个扩展方法。
在这里面关联了routerHanlder和routes，这个方法具体的实现是这样的：

{% highlight C# %}
var Default = new Route(url, defaults , routeHandler);
{% endhighlight %}

所以基本上这种方法就是附加routeHandler到route上。

UrlRoutingModule是这样定义的：
{% highlight C# %}
public class UrlRoutingModule : IHttpModule
{
    public UrlRoutingModule();
    public RouteCollection RouteCollection { get; set; }  //omitting the other details

}
{% endhighlight %}

所以，现在我们知道UrlRoutingModule知道应用程序中所有的路线，因此它可以匹配请求的正确路线。
这里要注意的主要事情是UrlRoutingModule选择第一个匹配的路由。
一旦匹配在路由表中找到，扫描过程将停止。

所以我们可以说，在我们的应用程序有10个Route和一个通用的Route，在这种情况下，后来添加的Route将永远不会被匹配，因为通用的Route总是会匹配。
因此，我们需要在添加路由到路由集合时注意这一点。

如果请求已经被路由集合中的任何一个路由匹配，那么之后添加的路由都不能来处理改请求。
请注意，如果该请求与UrlRoutingModule中的任何路由不匹配，则它不回被MvcApplication处理。

所以该阶段发生一下事情：

> 在URLRoutingModule添加路由来处理路由

## RouteHandler：MvcHandler的生成器

正如我们已经看到，router的MapRoute方法附加了MvcRouteHandler的实例。
MvcRouteHandler实现了IRouteHandler接口。

MvcRouteHandler对象用于获取MvcHandler对象的引用，这是应用程序的HttpHandler。

MvcRouteHandler创建后，要做一个事情是调用PostResolveRequestCache()方法。

PostResolveRequestCache()方法是这样定义的：
{% highlight C# %}
public virtual void PostResolveRequestCache(HttpContextBase context) 
{   
    RouteData routeData = this.RouteCollection.GetRouteData(context);   
    if (routeData != null)
    {        
        IRouteHandler routeHandler = routeData.RouteHandler;    
 
        IHttpHandler httpHandler = routeHandler.GetHttpHandler(requestContext);
    }
}
{% endhighlight %}

PostResolveRequestCache方法执行了以下事情：

* RouteCollection 有一个 GetRouteData() 方法。GetRouteData() 方法被调用，HttpContext是传入参数。
* GetRouteData方法返回RouteData对象
* routeData有一个RouterHandler属性，返回当前请求的IRouteHandler，这个便是MvcRouteHandler。
* MvcRouteHandler的GetHttpHandler方法返回MvcHandler的引用。
* 然后将控制委托给新的MvcHandler的实例。

## MvcHandler

MvcHandler是这样定义的：
{% highlight C# %}
pulic class MvcHandler : IHttpAsycHandler, IHttpHanlder, IRequiresSessionState
{
    public static readonly string MvcVersionHeaderName;

    public MvcHanlder(RequestContext requestContext);
}
{% endhighlight %}

正如看到的它是一个普通的的Http Handler。
作为一个Http Handler必须实现ProcessRequest方法。

ProcessRequest方法是这样定义的：

{% highlight C# %}
// Copyright (c) Microsoft Open Technologies, Inc.&lt;pre>
// All rights reserved. See License.txt in the project root for license information.

void IHttpHandler.ProcessRequest(HttpContext httpContext) 
{
    ProcessRequest(httpContext);
}
protected virtual void ProcessRequest(HttpContext httpContext) 
{
    HttpContextBase iHttpContext = new HttpContextWrapper(httpContext);
    ProcessRequest(iHttpContext);
}
protected internal virtual void ProcessRequest(HttpContextBase httpContext) {
    SecurityUtil.ProcessInApplicationTrust(() => {
        IController controller;
        IControllerFactory factory;
        ProcessRequestInit(httpContext, out controller, out factory);
        try
        {
            controller.Execute(RequestContext);
        }
        finally
        {
            factory.ReleaseController(controller);
        }
    });
}
{% endhighlight %}

ProcessRequest方法调用了ProcessRequestInit，是这样定义的：

{% highlight C# %}
private void ProcessRequestInit(HttpContextBase httpContext, out IController controller, out IControllerFactory factory) {
    // If request validation has already been enabled, make it lazy.

    // This allows attributes like [HttpPost] (which looks

    // at Request.Form) to work correctly without triggering full validation.

    bool? isRequestValidationEnabled = ValidationUtility.IsValidationEnabled(HttpContext.Current);
    if (isRequestValidationEnabled == true) {
        ValidationUtility.EnableDynamicValidation(HttpContext.Current);
    }
    AddVersionHeader(httpContext);
    RemoveOptionalRoutingParameters();
    // Get the controller type

    string controllerName = RequestContext.RouteData.GetRequiredString("controller");
    // Instantiate the controller and call Execute

    factory = ControllerBuilder.GetControllerFactory();
    controller = factory.CreateController(RequestContext, controllerName);
    if (controller == null) {
        throw new InvalidOperationException(
            String.Format(
                CultureInfo.CurrentCulture,
                MvcResources.ControllerBuilder_FactoryReturnedNull,
                factory.GetType(),
                controllerName));
    }
}
{% endhighlight %}

在ProcessRequest中发生了以下事情：

* ProcessRequestInit方法被调用，创建了ControllerFactory
* ControllerFactory创建了Controller
* Controller的Excute方法被执行了

## ControllerFactory：Controller的生产器

正如你看到的，在ProcessRequest()方法中，ControllerFactory获得用于创建Controller对象。
ControllerFactory实现了接口IControllerFactory。

框架默认使用ControllerBuilder类创建DefaultControllerFactory类型的ControllerFactory。

ControllerBuilder是一个单例类，用来创建ControllerFactory。
以下便是ProcessRequestInit方法中创建ControllerFactory的部分：
{% highlight C# %}
factory = ControllerBuilder.GetControllerFactory();
{% endhighlight %}

GetControllerFactory方法返回ControllerFactory对象，现在拥有的ControllerFactory对象。

ControllerFactory使用CreateContrller方法创建contrller。CreateController是这样定义的：

{% highlight C# %}
IController CreateController(RequestContext requestContext, string controllerName)
{% endhighlight %}

该ControllerBase对象是使用默认的ControllerFactory实现创建的。

如果需要的话，我们可以通过实现IControllerFactory接口，
然后在gloabal.asax Application_Start事件下面扩展该工厂。

{% highlight C# %}
ControllerBuilder.Current.SetDefaultControllerFactory(typeof(NewFactory))
{% endhighlight %}

该SetControllerFactory()方法用于设置自定义控制器工厂，而不是框架中默认使用的控制器工厂。

## Controller： 用户定义逻辑的容器

我们已经看到的ControllerFactory在MvcHandler的的ProcessRequest()方法创建一个Controller对象。

正如我们所知道的Controller包含Action方法。
当我们在浏览器请求URL时Action方法被调用。
我们使用Controller类创建一个自己的控制器类，它提供了许多功能，而不是明确地实现一个IController接口。

现在，这个控制器类从ControllerBase继承，它是这样定义的：
{% highlight C# %}
public abstract class ControllerBase : IController
{
    protected virtual void Execute(RequestContext requestContext)
    {
        if (requestContext == null)
        {
            throw new ArgumentNullException("requestContext");
        }
        if (requestContext.HttpContext == null)
        {
            throw new ArgumentException(
              MvcResources.ControllerBase_CannotExecuteWithNullHttpContext, 
              "requestContext");
        }
        VerifyExecuteCalledOnce();
        Initialize(requestContext);
        using (ScopeStorage.CreateTransientScope())
        {
            ExecuteCore();
        }
    }

    protected abstract void ExecuteCore(); 
    // .......
}
{% endhighlight %}

我们之后会看到该控制器对象使用ActionInvoker来调用Action方法。

在使用Controller factory创建了controller对象之后，发生了以下事情：

* ControlleBase中的Execute()方法被调用。
* Execute()方法调用了ExecuteCore()方法，这个一个抽象方法，会在Controller类中实现。
* ControllerBase类实现了ExecuteCore()方法，从RouteData中获取action名。
* ExecuteCore()方法调用ActionInvoker的InvokeAction方法。

## ActionInvoker：Action选择器

ActionInvoker最重要的职责就是去找到controller中的action方法，然后再调用。

ActionInvoker实现了IActionInvoker接口。IActionInvoker结构只有一个唯一的方法：

{% highlight C# %}
bool InvokeAction(ControllerContext controllerContext, string actionName)
{% endhighlight %}

Controller提供了默认的IActionInvoker实现，那就是ControllerActionInvoker。

Controller暴露了一个属性ActionInvoker返回了ControllerActionInvoker。
它使用CreateActionInvoker()方法创建ControllerActionInvoker。
这个方法被定义为虚方法，所以我们可以使用自己的实现重写这个方法，返回自定义的ActionInvoker。
{% highlight C# %}
public IActionInvoker ActionInvoker {
    get {
        if (_actionInvoker == null) {
            _actionInvoker = CreateActionInvoker();
        }
        return _actionInvoker;
    }
    set {
       _actionInvoker = value;
    }
}

protected virtual IActionInvoker CreateActionInvoker() {
    return new ControllerActionInvoker();
}
{% endhighlight %}

ActionInvoker需要取得action方法的详细信息，然后在controller中执行。
这些相关信息是ControllerDescriptor提供的。

ControllerDescriptor和ActionDescriptor在ActionInvoker中扮演了重要的角色。

* ControllerDescriptor是这样定义的：封装了描述控制器的信息，如名称，类型和action。
* ActionDescriptor是这样定义的：提供了action方法的信息，例如名称，controller，参数，属性和过滤器。

FindAction是ActionDescriptor中的一个重要的方法。
这个方法返回要执行action的ActionDescriptor对象。
所以ActionInvoker知道哪一个action会被调用。

正如我们上面看到的在ActionInvoker的InvokeAction()方法在ExecuteCore()中被调用。
ActionInvoker的InvokeAction被调用时发生了这些事情：

* ActionInvoker已获得有关控制器和操作执行的信息。这是信息是descriptor提供的。action和controller descriptor提供了controller和action的名称。
* ActionMethod被执行

## ActionResult

Action方法的其中一个特点是，它总是返回的ActionResult类型，而不是返回不同的数据类型。

ActionResult是一个抽象类：
{% highlight C# %}
public abstract class ActionResult
{
    public abstract void ExecuteResult(ControllerContext context);
}
{% endhighlight %}

ExecuteResult是一个抽象函数，所以不同的子类提供了不同的实现。

需要注意的一件重要的事情是，一个action的结果表示该框架代表操作方法执行命令。
正如我们所知道ActionMethods包含所执行的逻辑和结果会被返回给客户端。
操作方法本身只是返回的ActionResult，但不执行它。

ActionResult被执行，响应被返回到客户端。
所以的ActionResult对象表示可以在整个方法传递的结果。

因此，这是是action对象和实现分离的规范。更多请参考[Commands](http://msdn.microsoft.com/en-us/library/ms752308(v=vs.110).aspx)。

特定的ActionResult类取决于我们是想返回JSON或重定向其他方法结果的类型。

继承与controller的"Controller"提供了很多有用的功能。
其中一个功能提供了返回ActionResult的指定类型。
所以不用专门创建ActionResult对象，我们可以直接调用这些方法。

{% highlight C# %}
public ActionResult Create()
{
   return View();
}
{% endhighlight %}

下面是一些方法和返回的ActionResult的类型：

| ActionResult Class | Helper Method | Return Type |
| ------------------ | ------------- | ----------- |
| ViewResult         | View          | web page    |
| JsonResult         | Json          | Retuns a serialized JSON object    |
| RedirectResult         | Redirect          | Redirects to another action method    |
| ContentResult          | Content          | Returns a user-defined content type    |

到现在为止我们看到ActionMethod被ActionInvoker调用。

action方法被调用后发生了以下事情：

* ActionFilters的OnActionExecuting方法被调用
* 在这之后action方法本身被调用
* ActionFilters的OnActionExecuted方法被调用
* ActionResult返回
* ActionResult的ExecuteResult方法被调用

## ViewEngine：View渲染

ViewResult是在几乎所有的应用中最常用的返回类型之一。
它是使用视图引擎用来呈现视图到客户端。
视图引擎负责从View产出HTML。

当的ViewResult被action invoker调用时，它通过重写的ExecuteReuslt方法呈现视图。

框架中提供的视图引擎有Razro和Web Form。
但是如果你需要一些自定义功能佛如自定义视图引擎时，你可以通过实现IViewEngine接口，实现创建一个新的视图引擎。

IViewEngine有下面的方法：

* FindPartialView FindPartialView方法会在Contrller根据指定名字查找局部视图的时候调用。
* FindView FindView方法会在Controller根据指定名字查找视图时调用。
* ReleaseView 这个使用来释放视图引擎的资源用的。

但是，更简单的方法是创建一个从“VirtualPathProviderViewEngine”派生的视图引擎。
这个类实现了底层的细节例如查找视图。

由于ViewResult的ActionResult最常见的类型，我们会考虑，ViewResult的的ExecuteReuslt方法被调用会发生什么。

有两个重要的类ViewResultBase和ViewResult。
ViewResultBase包含以下代码，调用ViewResult的FindViewMethod：

{% highlight C# %}
if (View == null)
{
    result = FindView(context); //calls the ViewResult's FindView() method

    View = result.View;
}

ViewContext viewContext = new ViewContext(context, View, ViewData, TempData);
View.Render(viewContext, context.HttpContext.Response.Output);

protected abstract ViewEngineResult FindView(ControllerContext context); 
//this is implemented by the ViewResult

protected override ViewEngineResult FindView(ControllerContext context)
{
    ViewEngineResult result = ViewEngineCollection.FindView(context, ViewName, MasterName);
    if (result.View != null)
    {
        return result;
    }
    //rest of the code omitted 

}
{% endhighlight %}

ViewResult的ExecuteReuslt方法被调用后，发生了以下事情：

* ViewResultBase的ExecuteResult执行
* ViewResultBase调用ViewResult的FindView
* ViewResult返回ViewEngineResult
* ViewEngineResult的Render方法被调用，使用ViewEngine渲染视图
* 请求被返回到客户端

## 总结

如果我们理解引擎发生的事情，我们可以更好地理解各部件的作用，以及如何不同的组件被连接到彼此。
我们已经研究了用来处理响应的主要接口和类使用的框架。
我相信，这篇文章将有助于你理解MVC应用程序的内部细节。







