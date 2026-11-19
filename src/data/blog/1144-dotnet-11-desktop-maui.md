---
pubDatetime: 2026-11-19T09:30:08+08:00
title: "WPF、WinForms、MAUI 11 更新了什么？"
description: "按已有 Windows 桌面应用、移动端和 .NET Framework 4.8 迁移三个场景，检查 WPF、WinForms、MAUI 的新功能、发布模式、独立支持周期与实际设备验证。"
tags: ["DotNet", "WPF", "WinForms", "MAUI"]
slug: "dotnet-11-desktop-maui"
ogImage: "../../assets/1144/01-cover.jpg"
source: "https://learn.microsoft.com/en-us/dotnet/core/whats-new/dotnet-11/overview"
---

同一个选课系统可能同时有 Windows 审核工具和学生端移动应用。升级 Windows 客户端时，最先验证第三方控件、DPI、原生 DLL 和安装包。MAUI 11 项目还会遇到默认 Runtime 更替、平台 workload 和签名工具的变化，要在各自的设备矩阵检查。

WPF 11 偏重可靠性和部署修复，WinForms 11 提供可单独启用的现代控件渲染，MAUI 11 默认改用 CoreCLR。还在 .NET Framework 4.8 的程序先建立兼容清单，再迁移一个窗口或模块。

## 已在现代 .NET 的 Windows 客户端

WPF 的更新包含 Fluent 窗口背景、Desktop Window Manager 失败处理和弱事件清理等。含 C++/CLI 混合模式程序集的 Windows 自包含发布还要检查 `ijwhost.dll` 与原生依赖是否一起部署。升级可以先保持现有主题，拿实际安装包去干净 Windows 机器验证启动、资源加载、弹窗和高 DPI 行为。

WinForms 可以只给一个窗体或控件打开新样式，也可以用应用默认值让子控件继承。用 SDK 11.0.100 建一个独立的 Windows 项目观察 Opt-in 的影响。

```powershell
dotnet new winforms -n ReviewWindow -f net11.0
cd ReviewWindow
```

用下面的代码替换 `Program.cs`，再执行 `dotnet run`。先观察新版默认模式，再将 `Net11` 改成 `Classic` 回跑同一测试。应用级设置可在试运行失败时还原，检查按钮、勾选框、文字和高对比度变化时仍要使用业务项目里实际的控件。

```csharp
using System.Windows.Forms;

internal static class Program
{
    [STAThread]
    private static void Main()
    {
        ApplicationConfiguration.Initialize();
        Application.SetDefaultVisualStylesMode(VisualStylesMode.Net11);
        using var window = new Form { Text = "选课审核", Width = 420, Height = 240 };
        window.Controls.Add(new CheckBox
        {
            Text = "只看待审核课程", AutoSize = true, Dock = DockStyle.Top
        });
        Application.Run(window);
    }
}
```

控件大小会受系统文字大小、强调色、高对比度和 DPI 影响。项目若使用固定像素位置，先用 100% 和 150% 缩放验证文字和焦点状态。新窗体还可以选择延迟显示，批量更新控件时可用新的暂停绘制 API。窗口首次显示的速度和无障碍行为应在目标机器上分开观察。

## MAUI 升级先走默认发布路径

MAUI 11 的 CoreCLR 变更适用于用 .NET 11 构建并以它为目标的项目。先按模板默认方式构建和发布，验证设备启动、权限、导航、列表滚动、恢复前台、键盘以及无障碍读取。Windows 默认的 CollectionView2、Android Shell 改用 handler 的变化，尤其适合拿高频页面单独回归。依赖旧 Compatibility 包的项目应先迁移到当前控件或 handler。

增量 XAML Hot Reload 在 Debug 中默认启用，功能状态仍为预览。Android Native AOT 和 DevFlow 应放在单独的试验分支。正常版本继续验证当前裁剪配置、原生库、安装包大小与真实设备，在试验通过以后再改发布模式。

MAUI 的支持周期单独计算。官方表列出的 MAUI 11 支持终点为 **2028 年 5 月 9 日**，晚些时候的 .NET 运行时支持期限不能用于推算移动 workload。升级评审记录 `dotnet workload list`、Android SDK 或 Xcode 版本、签名配置版本和每个平台的产物。

## Framework 4.8 先确认发布边界

先列出配置、COM、混合程序集、原生 DLL、第三方控件和安装方式。把能隔离的逻辑提取出来，保留旧程序的签名安装包。检查新应用是否可以读取现有配置、与现有进程互操作，并在没有开发 SDK 的机器启动。

同一业务团队可以分批升级审核端和移动端。Windows 客户端可以先关闭新视觉模式或切回旧安装包。移动端有应用商店审核和签名时间，遇到兼容问题用已经验证的配置重发或通过独立版本逐步切换。上线评审要能明确指出每个平台的旧版本、测试设备和恢复方式。

## 参考

- [.NET 11 功能总览与客户端更新](https://learn.microsoft.com/en-us/dotnet/core/whats-new/dotnet-11/overview)
- [WPF 11 变化](https://learn.microsoft.com/en-us/dotnet/desktop/wpf/whats-new/net110)
- [WinForms 11 控件渲染与窗口显示](https://learn.microsoft.com/en-us/dotnet/desktop/winforms/whats-new/net110)
- [.NET MAUI 11 功能说明](https://learn.microsoft.com/en-us/dotnet/maui/whats-new/dotnet-11?view=net-maui-11.0)
- [MAUI 生命周期](https://dotnet.microsoft.com/en-us/platform/support/policy/maui)
- [.NET Framework 支持策略](https://dotnet.microsoft.com/en-us/platform/support/policy/dotnet-framework)
