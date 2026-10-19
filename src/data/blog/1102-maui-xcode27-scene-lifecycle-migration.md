---
pubDatetime: 2026-10-20T07:25:00+08:00
title: "MAUI 应用适配 Xcode 27 的场景生命周期"
description: "用 Xcode 27 构建的 MAUI 应用会闪屏后退出，缺的是 UIScene 生命周期。本文给出 Agent 技能与手工两条迁移路径，含 Info.plist 清单、回调迁移表和验证步骤。"
tags: [".NET MAUI", "iOS", "Xcode", "UIKit"]
slug: "maui-xcode27-scene-lifecycle-migration"
ogImage: "../../assets/1102/01-cover.jpg"
source: "https://devblogs.microsoft.com/dotnet/migrate-dotnet-maui-apps-uikit-scene-lifecycle/"
---

应用编译通过，装到 iOS 27 的模拟器上，闪屏正常显示，然后进程消失了。设备日志里只剩一行：

```text
UIScene life cycle is required for apps built with this SDK.
```

这条日志说的不是你哪里写错了，而是规则变了：从 Xcode 27 起，构建出来的 iOS 应用必须采用 UIKit 的场景生命周期（scene lifecycle），而很多 .NET MAUI 项目至今只实现了旧的应用生命周期（application lifecycle）。

关键在于，升级 .NET MAUI 版本或 Apple workload 并不会顺手改掉你项目里的 `Platforms/iOS` 文件。所以「更新了包，还是黑屏」是预期行为。Gerald Versluis 在 .NET 博客上给的方案分两层：代码改动其实只有两个文件，真正费时间的是盘点这些年加的自定义行为，包括登录回调、深链和快捷指令。

## 两套生命周期各管什么

UIKit 有两层生命周期，名字接近，职责不同：

- **应用生命周期**：管整个进程的启动、进入后台和退出。在 MAUI 里对应 `MauiUIApplicationDelegate` 和 `AppDelegate` 的覆写。
- **场景生命周期**：管每一份界面实例，包括它拥有的窗口，以及窗口在前台和后台之间的迁移。由 `UISceneDelegate` 承担。

场景模型是 Apple 在 iOS 13 引入的，MAUI 早就支持，用 10.0.110 模板新建的项目也自带配置。问题出在存量项目上：它们由旧模板生成，之后只升级过包，平台文件一直停在应用生命周期。

判断标准很窄，只有两个条件同时成立才需要迁移：

1. 你用 Xcode 27（对应 SDK 27）重新构建了应用；
2. 应用运行在 iOS 27 上。

用旧 SDK 构建、已经上架的二进制包，不会因为用户把手机升级到 iOS 27 就突然需要重建。这一点值得先跟自己团队确认，否则容易把一次 SDK 升级误判成紧急线上事故。

## 两条路线：交给 Agent，或者自己动手

原文推荐先用官方提供的迁移技能跑一遍，再人工审 diff。它属于 `dotnet/maui-labs` 仓库里的 agent skill，通过 .NET MAUI CLI 安装。技能本身只是给编码 Agent 的说明和资源，不会成为应用的运行时依赖。

先装 CLI（截至本文写作，NuGet 上 `Microsoft.Maui.Cli` 最新预览版就是下面这个版本）：

```bash
dotnet tool install --global Microsoft.Maui.Cli --version 0.1.0-preview.13.26512.5
```

已经装过就改成更新：

```bash
dotnet tool update --global Microsoft.Maui.Cli --version 0.1.0-preview.13.26512.5
```

然后**在你应用仓库的根目录**执行，因为技能是按项目安装的：

```bash
maui ai list skill
maui ai add skill maui-xcode27-migration --env CopilotCli --yes
```

用的是别的 Agent，就把 `--env` 换成对应值，具体可查 `maui ai add skill --help`。装完重启或重新加载会话，再提出请求：

```text
Prepare this .NET MAUI app for Xcode 27. Inspect the project
and toolchain first, preserve custom lifecycle behavior, and validate
the migration. Ask before changing the SDK or dropping support for
older OS versions.
```

不需要在请求里点名技能，兼容的 Agent 会根据任务自己选到 `maui-xcode27-migration`；不放心就写清楚。

几个容易误解的点：这套流程里没有 `maui migrate` 这样的命令；安装技能本身不会修改你的任何文件；CLI 和技能都属实验性工具，不在 Microsoft 支持策略范围内，而且技能要从公开目录下载，需要联网。如果你更习惯直接用 GitHub Copilot CLI 的插件机制，也可以走这条：

```bash
copilot plugin marketplace add dotnet/maui-labs
copilot plugin install dotnet-maui@dotnet-maui-labs
```

两种装法只选一种，否则项目里会出现重复的技能副本。

## 迁移前先核对三件事

### 一、可能你早就配好了

先看项目里有没有 `MauiUISceneDelegate` 的子类和对应的场景清单。有的话就跳过下面的手工步骤，但仍要核对版本并在 iOS 27 上实测。

### 二、workload 和 Xcode 必须配对

原文发布时，.NET 10 的 iOS 与 Mac Catalyst workload 是 **27.0.10722，要求 Xcode 27.0**。装了更新的 Xcode 不会自动让它兼容，也不能靠关掉 SDK 的版本检查蒙混过去。先跑：

```bash
maui doctor
```

它会检查当前 SDK、MAUI workload、选中的 Xcode 和 Apple SDK 是否匹配，顺带看 Xcode 许可、命令行工具和已安装的 iOS 运行时。回归验证时也建议把它固定成同一组版本，别出现「本机能跑、CI 挂掉」。

### 三、MAUI 包要升到 10.0.110 或更高

两个文件的改动在旧版本上也能跑起来，因为 `MauiUISceneDelegate` 早就存在。但 10.0.110 才包含场景模式下的 App Actions 派发和相关的 `WebAuthenticator` 转发。也就是说，不升级也能修好启动，但会把登录和快捷指令悄悄弄坏。

模板项目通常从 workload 读取 `$(MauiVersion)`，要显式钉住最低版本，就写进 `.csproj`：

```xml
<PropertyGroup>
  <MauiVersion>10.0.110</MauiVersion>
</PropertyGroup>
```

如果版本在 `Directory.Packages.props` 之类的地方集中管理，改那一处，别再加一个会被后续导入覆盖的本地属性。已经用着更新的兼容版本就不要降级。

## 第一步：加一个空的 SceneDelegate

在 `Platforms/iOS/SceneDelegate.cs` 里放这段。文件已存在就检查它的基类和注册名，不要加第二个：

```csharp
using Foundation;
using Microsoft.Maui;

namespace MyMauiApp;

[Register("SceneDelegate")]
public class SceneDelegate : MauiUISceneDelegate
{
}
```

把 `MyMauiApp` 换成你的命名空间。默认配置下类保持 `public`，注册名保持 `SceneDelegate`。

类体是空的，这不是省略写法：窗口由 MAUI 自己创建。同样，原有的 `AppDelegate : MauiUIApplicationDelegate` 原地不动，两个委托是并存关系，不是替换关系。

## 第二步：在 Info.plist 里声明场景清单

打开 `Platforms/iOS/Info.plist` 的 XML，在根 `<dict>` 里加入：

```xml
<key>UIApplicationSceneManifest</key>
<dict>
  <key>UIApplicationSupportsMultipleScenes</key>
  <false/>
  <key>UISceneConfigurations</key>
  <dict>
    <key>UIWindowSceneSessionRoleApplication</key>
    <array>
      <dict>
        <key>UISceneConfigurationName</key>
        <string>__MAUI_DEFAULT_SCENE_CONFIGURATION__</string>
        <key>UISceneDelegateClassName</key>
        <string>SceneDelegate</string>
      </dict>
    </array>
  </dict>
</dict>
```

三个细节决定这段能不能用：

- `__MAUI_DEFAULT_SCENE_CONFIGURATION__` 必须一字不差，这是 MAUI 查找的配置名。
- `UISceneDelegateClassName` 要和 C# 里的 `[Register]` 名字一致。
- `UIApplicationSupportsMultipleScenes` 保持 `false`，除非你的应用真的支持多窗口。

不需要 `UISceneStoryboardFile`，也不要顺手删掉原来的 `MauiSplashScreen` 或 `UILaunchStoryboardName`。如果项目里有自定义场景配置名，或者覆写了 `GetConfiguration`、`WillConnect`，应该合并而不是整段替换：默认的窗口创建路径只认那个固定配置名。

**多环境 plist 是最容易漏的地方。** 有些项目为 Debug、Release、客户定制或不同环境准备了不同的 Info.plist。只要某个配置能产出可发布的 App，就得在那份 plist 里也补上清单，否则会出现「本地测好的 Debug 正常，打包的 Release 仍然闪屏后退出」。

同样的两步在 Mac Catalyst 上再走一遍：`Platforms/MacCatalyst/SceneDelegate.cs` 加文件，`Platforms/MacCatalyst/Info.plist` 加同一段清单。不发布 Catalyst 就跳过。

## 顺手处理最低系统版本

.NET for iOS 与 Mac Catalyst 27 SDK 抬高了最低支持版本：iOS 至少 **15.0**，Mac Catalyst 至少 **17.0**（对应 macOS 14 Sonoma）。在 `.csproj` 的 `<PropertyGroup>` 里改现有条目：

```xml
<SupportedOSPlatformVersion Condition="$([MSBuild]::GetTargetPlatformIdentifier('$(TargetFramework)')) == 'ios'">15.0</SupportedOSPlatformVersion>
<SupportedOSPlatformVersion Condition="$([MSBuild]::GetTargetPlatformIdentifier('$(TargetFramework)')) == 'maccatalyst'">17.0</SupportedOSPlatformVersion>
```

要点是替换而不是追加，后出现的定义会覆盖前面的；版本号直接写在标签之间，不要留空格。原本要求更高的就保留原值。

如果应用必须继续支持 iOS 15 以下、或者 macOS 12/13，那就不是技术问题而是支持策略问题。在拿定主意之前留在兼容的 26.x SDK 上，别一边升级一边悄悄丢掉这批用户。这个 SDK 下限和是否采用场景生命周期是两件独立的事。

## 真正花时间的部分：迁移自定义行为

开了场景之后，UIKit 不再调用 `AppDelegate` 里的激活、前后台、URL 和用户活动回调。无论是 `ConfigureLifecycleEvents` 注册的，还是你在 `AppDelegate` 里覆写的方法，都算在内。对应关系如下：

| 原有事件               | 场景事件                    |
| ---------------------- | --------------------------- |
| `OnActivated`          | `SceneOnActivated`          |
| `OnResignActivation`   | `SceneOnResignActivation`   |
| `DidEnterBackground`   | `SceneDidEnterBackground`   |
| `WillEnterForeground`  | `SceneWillEnterForeground`  |
| `OpenUrl`              | `SceneOpenUrl`              |
| `ContinueUserActivity` | `SceneContinueUserActivity` |

参数不同，所以只能搬逻辑，不能只改注册名。如果你选择覆写 `SceneDelegate` 里的方法，记得调用对应的 `base` 实现，框架的窗口创建、生命周期事件和认证转发都依赖它。

几个具体的坑：

**冷启动链接会绕过你的处理器。** 启动应用的那个 URL 或用户活动不在 `SceneOpenUrl` 里，而在 `SceneWillConnect` 的 `UISceneConnectionOptions` 中。这个回调跑在 MAUI 创建窗口之前，所以导航要延后到窗口就绪。普通启动时这些集合可能是空的，取元素前先判空，别假设一定有值。

**通知点击也要单独处理。** 从通知启动应用时，检查 `connectionOptions.NotificationResponse`。它和推送注册、`DidReceiveRemoteNotification` 不是同一条路径，后者仍是应用级回调。

**`AppDelegate.Window` 现在是 null。** `FinishedLaunching` 依然会执行，但窗口改由场景委托在之后创建，所以在这个回调里访问 `Window` 拿到的是空值。需要窗口的初始化工作得挪到场景窗口存在之后。跨平台的 `Window` 生命周期事件不受影响，别自己再转发一遍。

**WebAuthenticator 的转发不等于通用深链。** 10.0.110 会把相关的 URL 和用户活动回调转给 `WebAuthenticator`，但它不会替你重放冷启动链接，也不是一个深链路由器。登录流程要按「应用在运行」和「应用已完全关闭」两种情况各测一次。

**快捷指令必须回应 completion。** 每个自定义的 `PerformActionForShortcutItem` 处理器都要恰好调用一次完成回调：处理了就传 `true`，没处理传 `false`。异步处理后回调也行，但只返回不回应不算处理完。下面是个只打日志也要回应的例子，加在 `MauiProgram.cs` 的 `CreateMauiApp` 里、`return builder.Build();` 之前：

```csharp
builder.ConfigureLifecycleEvents(events =>
{
#if IOS || MACCATALYST
    events.AddiOS(ios => ios
        .PerformActionForShortcutItem((application, shortcutItem, completion) =>
        {
            Console.WriteLine($"App Action received: {shortcutItem.Type}");
            completion(false);
        }));
#endif
});
```

默认的 MAUI builder 已经把 App Actions 转给 Essentials，除非你需要这条日志，否则不用加；加了就别再注册一个 `Platform.PerformActionForShortcutItem`。至于原来在 `AppDelegate` 里覆写的 `PerformActionForShortcutItem`，场景模式下不会再被调用，逻辑要整体搬进上面的注册里，完成回调一起搬。

## 构建、验证，然后才敢说完成

恢复并构建 iOS 目标：

```bash
dotnet restore -p:TargetFramework=net10.0-ios
dotnet build -f net10.0-ios --no-restore
```

如果模拟器里像是还跑着旧版本，卸载应用、删掉项目的 `bin` 和 `obj`，再执行上面两条。

`dotnet build` 成功不代表 plist 是对的。增量构建可能保留旧的清单缓存，所以要直接检查产物：

```bash
plutil -p "<build-output>/<App>.app/Info.plist" | grep -A12 UIApplicationSceneManifest
```

确认清单存在、配置名和委托名都符合预期。缺失的话清一次 `obj` 重新构建再看。

运行时清单按这个顺序走，Debug 和 Release 都要过：

1. 冷启动能越过闪屏进入首屏；
2. 切后台再回前台，页面状态正常；
3. 登录流程在应用运行中和完全关闭两种状态下都能回来；
4. 深链和通知点击，同样区分热启动和冷启动；
5. 快捷指令的已处理与未处理分支都有反应；
6. 有 Mac Catalyst 目标的话，单独构建并跑一遍。

在 iOS 27 模拟器上用配套的 workload 和 Xcode 验证就够了，不需要某个特定设备的模拟器。iOS 26 上构建和启动成功，不能证明用 Xcode 27 构建后能在 iOS 27 上启动。

如果是让 Agent 执行的，动手前先提交或保存当前工作，事后逐行看 diff。构建通过只能证明代码能编译，证明不了登录跳转或主屏快捷方式还能用。

## 常见问题

**改完还是闪屏后退出。** 先看产物里的 `Info.plist`，而不是源文件：多配置项目漏改某份 plist、增量构建残留旧清单，都会表现成「明明加了却没用」。

**启动正常了，登录回调没了。** 检查 MAUI 包是否真的到了 10.0.110 以上，以及 `SceneDelegate` 的覆写里有没有调用 `base`。

**冷启动深链丢，热启动正常。** 典型的只迁移了 `SceneOpenUrl` 而没处理 `SceneWillConnect`。

**快捷指令点了没反应。** 多半是 completion 没调用，或者调用次数不对。

**能不能关掉 Xcode 版本检查凑合用？** 原文明确建议不要这么做，应该让 workload 和 Xcode 匹配。版本校验被关掉后，用到新 SDK 里不存在的绑定会以更难定位的崩溃形式出现。

---

Aide Hub 会继续跟踪 .NET MAUI、Apple 平台升级和 AI 编码工具在真实项目里的落地方式，遇到同类迁移问题也欢迎一起聊。

## 参考

- [Get Your .NET MAUI App Ready for Xcode 27（原文）](https://devblogs.microsoft.com/dotnet/migrate-dotnet-maui-apps-uikit-scene-lifecycle/)
- [maui-xcode27-migration 技能源码](https://github.com/dotnet/maui-labs/tree/main/plugins/dotnet-maui/skills/maui-xcode27-migration)
- [dotnet/maui-labs 仓库](https://github.com/dotnet/maui-labs)
- [GitHub Copilot CLI 插件安装文档](https://docs.github.com/copilot/how-tos/copilot-cli/customize-copilot/plugins-finding-installing)
- [.NET for iOS 与 Mac Catalyst 27.0.10722 发行说明](https://github.com/dotnet/macios/releases/tag/dotnet-10.0.1xx-xcode27.0-10722)
- [.NET MAUI 模板的部署目标指引](https://github.com/dotnet/maui/blob/main/src/Templates/README.md#mac-catalyst-deployment-target)
- [Microsoft.Maui.Cli 版本列表（NuGet）](https://www.nuget.org/packages/Microsoft.Maui.Cli)
