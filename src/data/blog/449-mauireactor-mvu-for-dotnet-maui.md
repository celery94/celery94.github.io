---
pubDatetime: 2025-08-26
tags: [".NET MAUI", "MauiReactor", "MVU", "跨平台开发", "移动开发", "UI 框架"]
slug: mauireactor-mvu-for-dotnet-maui
source: https://devblogs.microsoft.com/dotnet/mauireactor-mvu-for-dotnet-maui
title: MauiReactor：为 .NET MAUI 带来 MVU 架构模式
description: 探索 MauiReactor 如何将 Model-View-Update (MVU) 模式引入 .NET MAUI 开发，提供更高的开发效率、真正的热重载和代码驱动的 UI 开发体验。
---

# MauiReactor：为 .NET MAUI 带来 MVU 架构模式

![MauiReactor 拼贴图](https://devblogs.microsoft.com/dotnet/wp-content/uploads/sites/10/2025/08/reactor-collage.png)

这是来自 [Adolfo Marinucci](https://github.com/adospace) 的客座博客文章。

我是一名来自意大利的全栈开发者，主要专注于 Microsoft 技术，从使用 .NET MAUI 的跨平台应用程序到托管在 Azure 上的 ASP.NET Core 后端服务。我是 MauiReactor 的创建者，这是一个为 .NET MAUI 设计的 UI 库，将 Model-View-Update (MVU) 模式引入跨平台开发。

## 背景和动机

[MauiReactor](https://adospace.gitbook.io/mauireactor/) 是一个开源 .NET 库，将 [Model-View-Update](https://guide.elm-lang.org/architecture/) (MVU) 模式引入 .NET MAUI 开发。虽然 MVU 已经被讨论了多年，但它通过 ReactJS 获得了广泛关注，后来影响了 React Native 和 Flutter 等框架。

> **注意**：有关 MauiReactor 的 MVU 方法的更多详细信息，请参阅 [有状态组件文档](https://adospace.gitbook.io/mauireactor/components/stateful-components)。

### MVU 的优势

- 通过不可变状态实现可预测的状态管理
- 简化热重载实现
- UI 开发的完整 C# IDE 支持
- 潜在的更好性能特征

这个库最初是近十年前使用 Xamarin.Forms 的实验。随着时间的推移，它发展成为现在的 MauiReactor，融合了从实际应用程序开发中学到的经验教训和来自志同道合的开发人员的反馈，这些开发人员希望在 .NET 生态系统中探索 MVU 模式。该库被设计为 .NET MAUI 上的一个薄层，大部分代码是自动生成的。这种方法保持了代码库相对简单，并使其在发布新版本的 .NET MAUI 时更容易更新。

如今，MauiReactor 是一个成熟的开源项目，在 [GitHub 上拥有超过 650 个星标](https://github.com/adospace/reactorui-maui)。我在数十个生产应用程序中使用和维护它，我的客户一直表示，与标准 .NET MAUI 相比，使用 MauiReactor 构建应用程序所需的开发时间显著减少。

## MVU vs MVVM

.NET MAUI 天然支持 [MVVM 模式](https://learn.microsoft.com/dotnet/architecture/maui/mvvm)，许多开发者因其熟悉性和能够重用现有 WPF 知识而欣赏它。MVVM 提供了出色的关注点分离和良好的工具支持。对于具有现有 MVVM 专业知识的团队来说，这仍然是一个有效的选择。

MauiReactor 为希望探索 MVU 模式的开发人员或来自 React Native 或 Flutter 背景、习惯于在代码中编写声明式 UI 方法的开发人员提供了一种替代方案。

MauiReactor 的 MVU 方法相对于 MVVM 提供了一些关键优势：

### 1. 提高生产力

您可以直接在视图组件中编写 UI 逻辑，而无需命令来处理用户交互或自定义值转换器来将正确的值传递给小部件。例如，在 MVVM 中，要实现用户登录，您需要一个 LoginCommand 对象来处理"登录"按钮点击，指定一个"CanExecute"回调，仅在用户输入用户名/密码字符串后启用它，以及在命令执行期间显示忙碌指示器的附加代码。在 MVU 中，您可以用 C# 编写一个 Button 并为 OnClick 事件指定一个回调，然后在用户名/密码字段填充时将 IsEnabled 属性设置为 true。

```csharp
Button("Login")
    .IsEnabled(!string.IsNullOrWhiteSpace(State.FirstName) && !string.IsNullOrWhiteSpace(State.LastName))
    .OnClicked(OnLogin)
```

### 2. 更灵活的条件 UI

考虑一个显示两个文本条目和一个登录按钮的登录组件，在身份验证期间显示忙碌指示器。在 MVVM 中，您需要值转换器来显示或隐藏小部件。在 MVU 中使用 MauiReactor，您可以检查状态属性并使用简单的评估语句来显示不同的 UI 元素（类似于 Blazor）。

```csharp
ActivityIndicator()
    .IsVisible(State.IsBusy)
```

或者：

```csharp
State.IsBusy 
    ? ActivityIndicator() 
    : null
```

### 3. 真正的热重载

由于不同的关注点分离，MauiReactor 实现了卓越的热重载功能。在 MVVM 中，您通常将 View 与逻辑（ViewModel）和状态（Model）分离，尽管开发人员经常将逻辑和状态保持在单个 ViewModel 类中。在 MVU（MauiReactor 的风格）中，您将 View+Logic 与 Model（State）分离。将状态与视图和逻辑分开，允许在不丢失上下文的情况下热重载应用程序。例如，如果您有一个复杂的页面，在多个文本字段中输入了文本，并决定更改一些代码，当页面热重载时，相同的文本保留在文本字段中，因为状态在迭代之间保留。

将所有这些结合起来，这里是 MauiReactor 中的典型计数器应用程序：

```csharp
class CounterPageState
{
    public int Counter { get; set; }
}

class CounterPage : Component<CounterPageState>
{
    public override VisualNode Render()
        => ContentPage("Counter Sample",
            VStack(
                Label($"Counter: {State.Counter}"),
                Button("Click To Increment", () =>
                    SetState(s => s.Counter++))
            )
        );    
}
```

为了对比，这是 React Native 中的计数器，演示了类似的 MVU 实现：

```javascript
import React, { useState } from 'react';
import { View, Text, TouchableOpacity } from 'react-native';

const Counter = () => {
  const [count, setCount] = useState(0);

  return (
    <View>
      <Text>Count: {count}</Text>
      <TouchableOpacity onPress={() => setCount(count + 1)}>
        <Text>+</Text>
      </TouchableOpacity>
      <TouchableOpacity onPress={() => setCount(count - 1)}>
        <Text>-</Text>
      </TouchableOpacity>
      <TouchableOpacity onPress={() => setCount(0)}>
        <Text>Reset</Text>
      </TouchableOpacity>
    </View>
  );
};

export default Counter;
```

## 实际应用

MauiReactor 已在不同领域的生产应用程序中使用。一个值得注意的例子包括与 [Real Time Research, Inc.](https://realtimeresearch.com/) 的合作，这是一家美国公司，为进行科学研究的政府机构提供自然资源数据和分析解决方案。他们的应用程序允许研究人员在离线环境中收集现场数据，与 Microsoft Azure 同步，并通过 Microsoft Power BI 生成报告。

### 演示应用程序

MauiReactor 为研究人员进行鱼类调查、收集鱼类和栖息地测量数据的 Real Time Research 应用程序提供支持。该应用程序连接到被动集成应答器 (PIT) 标签阅读器，检索 GPS 位置数据，并读取条形码。

这些应用程序处理复杂的数据工作流程，需要在具有挑战性的现场条件下可靠工作。选择使用 MauiReactor 是基于状态管理和离线同步模式的特定技术要求。

以下是同步期间状态管理工作方式的示例：

```csharp
async Task OnSync()
{
    SetState(s =>
    {
        s.IsBusy = true;
        s.SyncProgress = null;
    });

    try
    {
        _syncProviderService.SyncProgress += SyncProviderService_SyncProgress;

        await _syncAgentService.Synchronize();

        Preferences.Set("LastSync", DateTime.Now);
    }
    catch (Exception ex)
    {
        await ContainerPage.DisplayAlert("The application is unable to sync with the server.", "OK");
    }
    finally
    {
        _syncProviderService.SyncProgress -= SyncProviderService_SyncProgress;

        SetState(s =>
        {
            s.IsBusy = false;
            s.SyncProgress = null;
        });
    }
}

void SyncProviderService_SyncProgress(object? sender, SyncProgressEventArgs e)
{
    SetState(_ =>
    {
        _.SyncStage = e.Stage;
        _.SyncProgress = e.Progress;
    });
}
```

除了企业应用程序外，该库还用于各种面向消费者的项目，显示了其在不同应用程序类型和需求中的灵活性。

## 技术特征

MauiReactor 具有几个技术特征，根据您的项目需求可能相关：

### 热重载实现

MVU 架构使热重载实现更加直接。由于 UI 是状态的函数，重新加载涉及交换视图和更新函数，同时保留应用程序状态。这可以导致更快的开发周期，特别是在处理复杂的 UI 交互时。

MauiReactor 的热重载与标准 .NET CLI（具有其限制）一起工作，或者通过安装自定义 .NET 工具 (Reactor.Maui.HotReload)。使用专用工具，MauiReactor 支持几乎任何您对代码所做的更改，并且运行速度很快。例如，您可以创建新类、删除或添加方法、更改类型和属性。每当您修改文件时，它会即时编译并发送到应用程序。它适用于 Android、iOS、Mac 和 Windows，使用模拟器或真实设备。您可以在 Windows 或 Mac 下的 Visual Studio、VS Code 和 Rider 中开发。

热重载功能交换运行应用程序的整个程序集与包含新代码的程序集（不仅仅是当前组件的视图）。整个应用程序获得新代码，但当前页面、组件和上下文被保留，因为它们链接到在迭代之间复制的状态类。您很少需要重新启动应用程序，提供了很好的开发体验。

### 基于代码的 UI 开发

应用程序完全用 C# 编写，这意味着您可以使用所有熟悉的 IDE 功能：IntelliSense、重构、调试和代码分析工具。这种方法在不同的开发环境中也能一致工作。

#### 主题化

XAML 样式继续工作，因此您可以移植现有的基于 XAML 的资源。然而，MauiReactor 还具有强大的主题系统，允许您直接在 C# 中声明样式来自定义任何控件，无论是标准控件还是从其他库导入的控件。

```csharp
public class AppTheme : Theme
{
    protected override void OnApply()
    {
        LabelStyles.Default = _ => _
            .FontFamily("OpenSansRegular")
            .FontSize(FontNormal)
            .TextColor(Black);

        LabelStyles.Themes["Title"] = _ => _
            .FontSize(20);            
    }
}
```

有关主题化的更多信息，请访问 [MauiReactor 主题化文档](https://adospace.gitbook.io/mauireactor/components/theming)。

#### 数据绑定

在 MauiReactor 中，您不会错过为所有内容构建值转换器。来自 XAML 世界，您习惯于创建值转换器来转换从视图模型读取的数据（如 InverseBooleanConverter 或 BoolToVisibilityConverter）。

```xml
<Label IsVisible="{Binding MyValue, Converter={StaticResource InvertedBoolConverter}}"/>
```

MauiReactor 可以使用普通的 C# 代码设置属性，允许您转换状态属性值或评估函数：

```csharp
Label().IsVisible(!MyValue)

Label().IsVisible(IsLabelVisible())
```

#### 条件渲染

使用普通 XAML 进行 UI 部分的条件渲染可能很麻烦：您可能需要使用转换器并显示/隐藏控件。无需担心创建可能永远不会出现的控件的性能影响，MauiReactor 允许您在组件中使用自定义逻辑直接用 C# 声明您的 UI：

```csharp
class LoginPage : Component<LoginPageState>
{
    public override VisualNode Render()
        => ContentPage(
            State.IsLoggingIn ? 
            RenderBusyUI()
            :
            RenderLoginUI()
        );    
}
```

#### 可读性

大页面可以分解为更简单的渲染函数或排列成更简单的组件。相对于 XAML 的可读性是基于代码的 UI 的核心特性之一，一旦您开始将 MauiReactor 集成到现有的 .NET MAUI 应用程序中，就会变得明显。

```csharp
class HomePage : Component
{
    public override VisualNode Render()
        => ContentPage(
            Grid("Auto,*,Auto", "*",
                RenderHeader(),

                RenderBody(),

                RenderFooter()
        );    
}
```

#### 测试

MauiReactor 通过提供实用程序类和函数完全支持集成测试，让您可以即时创建组件，而无需平台初始化。例如，这是您如何测试上面显示的计数器组件。

```csharp
[Test]
public void CounterWithServicePage_Clicking_Button_Correctly_Increments_The_Counter()
{
    using var serviceContext = new ServiceContext(services => services.AddSingleton<IncrementService>());

    var mainPageNode = TemplateHost.Create(new CounterWithServicePage());

    // 检查计数器是 0
    mainPageNode.Find<MauiControls.Label>("Counter_Label")
        .Text
        .ShouldBe($"Counter: 0");

    // 点击按钮
    mainPageNode.Find<MauiControls.Button>("Counter_Button")
        .SendClicked();

    // 检查计数器是 1
    mainPageNode.Find<MauiControls.Label>("Counter_Label")
        .Text
        .ShouldBe($"Counter: 1");
}
```

MauiReactor 与测试框架无关：继续使用 MSTest、XUnit、NUnit 或您喜欢的任何其他测试框架。

### 性能考虑

使用 MauiReactor 构建的应用程序避免了与 XAML 解析和基于反射的数据绑定相关的一些开销。在实践中，这可能导致更好的启动性能和运行时效率，尽管实际影响取决于您的具体应用程序设计。

MauiReactor 页面默认是编译的，而设计不当的基于 XAML 的页面可能包含与基于反射的绑定和资源查找相关的性能瓶颈。这通常导致更快的页面打开时间和更平滑的过渡。另一方面，每次编辑状态属性时，MauiReactor 可能需要更多的渲染传递。

根据我的经验，性能问题很少与框架本身（.NET MAUI vs MauiReactor）相关，而更多与设计不当的页面或逻辑代码（包括隐藏异常或异常线程上下文切换）相关。

如果您对性能优化很认真并希望测试 .NET MAUI 和 MauiReactor 之间的差异，我准备了一个可以帮助测量应用程序启动时间的[示例项目](https://github.com/adospace/maui-reactor-profiling)。

> **注意**：该库对反射的最小使用使其非常适合 [提前编译](https://learn.microsoft.com/dotnet/maui/deployment/nativeaot) 场景，这对某些部署要求可能很重要。

### 轻松集成第三方组件

MauiReactor 可以与来自 Syncfusion、Telerik 和 DevExpress 等供应商的现有 .NET MAUI 组件库一起工作。自定义控件可以通过一些额外的包装器代码进行集成。

在 MauiReactor 中使用现有控件通常需要向您的项目添加这种代码：

```csharp
[Scaffold(typeof(Syncfusion.Maui.Buttons.ToggleButton))]
partial class ToggleButton { }
```

MauiReactor 源生成器将创建所需的代码层。然后可以在组件内实例化导入的小部件：

```csharp
VStack(
    new ToggleButton()
        .OnClicked(()=>...)
)
```

对于某些更复杂的控件，集成可能需要额外的代码。我不断在[这个存储库](https://github.com/adospace/mauireactor-integration)中为常见库创建和更新集成代码。

## 展望未来

MauiReactor 代表 .NET 生态系统中跨平台开发的一种方法。它不是要取代现有模式，而是为发现 MVU 模式更适合其需求或开发风格的开发人员提供一种替代方案。该库继续根据在生产场景中使用它的开发人员的反馈而发展。随着 .NET MAUI 生态系统的增长，拥有不同的方法为开发人员提供了更多选择，以选择最适合其特定要求的方法。

我从 2001 年开始从事软件开发行业，多年来见证了 .NET 平台的兴起。我享受过 WPF 架构和 MVVM 模式的美妙（我是 AvalonDock 库的原作者）。然后出现了 ReactJS，它为 web 编写 UI 的独特 MVU 方法。我可能从未用 XAML 和 MVVM 编写过 Xamarin.Forms 应用程序，但我很快开始思考，感谢 C# 语言的灵活性，编写 MVU 的跨平台 .NET 应用程序是可能的。

在过去的 10 年中，我编写了许多基于 C# 的 MauiReactor 应用程序，并喜欢它们的简单性和生产力。我从未回头。

感谢出色的 .NET 社区，我收到了提示和错误修复，这些将我的个人副项目转变为一个成熟的开源项目，世界各地的许多开发人员都知道并享受使用它来更快地构建应用程序。

除了维护核心项目外，考虑到 MauiReactor 的架构，我还在尝试与其他 UI 框架的集成，如 WPF、Avalonia 或 UNO，以及 [DrawnUI](https://github.com/taublast/DrawnUi) 和 [Spice](https://github.com/adospace/spice)。

### 今天就创建您的第一个 MauiReactor 应用程序

1. 安装 dotnet new 模板

```bash
dotnet new install Reactor.Maui.TemplatePack
```

2. 创建新项目

```bash
dotnet new maui-reactor-startup -o my-new-project
```

3. 运行应用程序

```bash
dotnet build -t:Run -f net9.0-android
```

有关更多信息、文档和示例，请访问 [MauiReactor 存储库](https://github.com/adospace/reactorui-maui)、[MauiReactor 示例存储库](https://github.com/adospace/mauireactor-samples) 和 [MauiReactor 文档](https://adospace.gitbook.io/mauireactor/getting-started)。

## 结论

MauiReactor 为 .NET MAUI 开发人员提供了一种探索 MVU 模式的强大替代方案。通过将视图逻辑与状态分离，它提供了：

- **提高的开发效率**：直接在 C# 中编写 UI 逻辑，无需复杂的 MVVM 样板代码
- **真正的热重载**：保持应用程序状态的同时重新加载代码更改
- **灵活的条件 UI**：使用简单的 C# 条件语句轻松创建动态界面
- **完整的 IDE 支持**：享受 IntelliSense、重构和调试的全面支持
- **更好的测试支持**：内置的测试实用程序简化了组件测试
- **强大的主题系统**：直接在 C# 中定义样式，无需复杂的 XAML 资源

对于那些来自 React Native 或 Flutter 背景的开发人员，或者那些希望探索声明式 UI 方法的 .NET 开发人员来说，MauiReactor 提供了一个熟悉而强大的开发体验。

该库已经在多个生产应用程序中得到验证，包括处理复杂数据工作流程和离线同步的企业级解决方案。随着 GitHub 上超过 650 个星标和活跃的社区支持，MauiReactor 代表了跨平台 .NET 开发的一个成熟且可靠的选择。

无论您是在寻找 MVVM 的替代方案，还是希望提高开发效率，MauiReactor 都值得考虑用于您的下一个 .NET MAUI 项目。