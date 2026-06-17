---
pubDatetime: 2026-06-17T07:40:54+08:00
title: "中介者模式 C# 实战：用 Mediator 构建松耦合的智能家居设备协调系统"
description: "用完整的智能家居自动化系统展示中介者模式在 C# 中的落地实现：灯光、温控、安防和音乐播放器通过 HomeAutomationMediator 协调行为，任何设备都不持有对另一设备的直接引用。从接口设计、设备实现、测试验证到 DI 集成，新增设备零改动现有代码。"
tags: ["Csharp", "Design Patterns", "Mediator"]
slug: "mediator-pattern-csharp-smart-home"
source: "https://www.devleader.ca/2026/06/16/mediator-pattern-realworld-example-in-c-complete-implementation"
ogImage: "../../assets/883/01-cover.png"
---

大部分中介者模式教程只演示"聊天室"：User A 发一条消息给 User B，就算讲完了。
这种例子够理解概念，但距离实际系统还有很长的路。

这篇文章用**智能家居自动化系统**作为真实场景，从头构建一个完整的 Mediator 模式实现。
灯光、温控器、安防摄像头和音乐播放器通过一个中央 `HomeAutomationMediator` 协调行为——任何设备都不持有对另一设备的直接引用。
读完你会拿到一套可编译的完整代码，覆盖接口设计、设备实现、单元测试和生产化考虑。

---

## 没有中介者时：设备互相耦合

先看一个典型的耦合问题。
当安防系统启动布防时，我们希望灯光调暗、温控器进入节能模式、音乐停止播放。
没有 Mediator 模式时，`SecuritySystem` 必须知道所有设备：

```csharp
public class SecuritySystem
{
    private readonly LightController _lights;
    private readonly Thermostat _thermostat;
    private readonly MusicPlayer _music;

    public SecuritySystem(
        LightController lights,
        Thermostat thermostat,
        MusicPlayer music)
    {
        _lights = lights;
        _thermostat = thermostat;
        _music = music;
    }

    public void Arm()
    {
        IsArmed = true;

        _lights.SetBrightness(10);   // 安防要知道灯光
        _thermostat.SetMode("eco");  // 安防要知道温控
        _music.Stop();               // 安防要知道音乐
    }

    public bool IsArmed { get; private set; }
}
```

`SecuritySystem` 严重违反单一职责原则。
它得知道灯光亮度级别、温控模式字符串、音乐播放控制。
每新增一个设备（比如智能门锁、扫地机器人），就要修改 `SecuritySystem` 及其他所有需要响应的设备。
最终变成 N×N 的依赖网。

测试也变成灾难。
想验证"布防后温控器模式是否正确"，还得 mock 灯光和音乐——尽管它们跟温控断言完全无关。
改一下布防行为中的灯光逻辑？你得去安防类里改。

中介者模式把所有这些跨设备通信都收拢到一个协调器中。

## 接口设计

中介者模式需要两个核心抽象：负责协调的中介者接口，以及参与者的同事接口。
还需要一个通知对象来描述"发生了什么"。

```csharp
namespace SmartHome.Core;

public sealed record DeviceNotification(
    string DeviceId,
    string EventType,
    Dictionary<string, object> Payload)
{
    public T GetPayloadValue<T>(string key)
    {
        if (Payload.TryGetValue(key, out var value)
            && value is T typed)
        {
            return typed;
        }

        throw new InvalidOperationException(
            $"Payload key '{key}' not found " +
            $"or not of type {typeof(T).Name}.");
    }
}
```

`DeviceNotification` 记录携带了设备标识、事件类型和一个灵活的 payload 字典。
这让通信通道足够通用——任何设备都可以发任何事件，不需要为每种交互创建新的消息类型。

接下来是两个核心接口：

```csharp
namespace SmartHome.Core;

public interface ISmartHomeMediator
{
    void RegisterDevice(ISmartDevice device);
    void Notify(
        ISmartDevice sender,
        DeviceNotification notification);
}

public interface ISmartDevice
{
    string DeviceId { get; }
    string DeviceType { get; }
    void SetMediator(ISmartHomeMediator mediator);
    void ReceiveNotification(
        DeviceNotification notification);
}
```

`ISmartHomeMediator` 只有两个职责：注册设备和路由通知。
设备做出值得注意的事时，调用 `Notify`；中介者决定哪些设备需要知道，然后调用各自的 `ReceiveNotification`。
没有任何设备直接引用另一个设备——所有通信流经中央协调器。

`ISmartDevice` 中的 `SetMediator` 让设备能回传通知给中介者。
这是一种常见做法，适用于同事对象需要主动发起通信的场景。

## 设备基类

在实现具体设备前，先把公共的 Mediator 接线抽到基类里：

```csharp
namespace SmartHome.Core;

public abstract class SmartDeviceBase : ISmartDevice
{
    private ISmartHomeMediator? _mediator;

    protected SmartDeviceBase(
        string deviceId,
        string deviceType)
    {
        DeviceId = deviceId;
        DeviceType = deviceType;
    }

    public string DeviceId { get; }
    public string DeviceType { get; }

    public void SetMediator(
        ISmartHomeMediator mediator)
    {
        _mediator = mediator;
    }

    public abstract void ReceiveNotification(
        DeviceNotification notification);

    protected void SendNotification(
        string eventType,
        Dictionary<string, object>? payload = null)
    {
        _mediator?.Notify(
            this,
            new DeviceNotification(
                DeviceId,
                eventType,
                payload ?? new Dictionary<string, object>()));
    }
}
```

`SmartDeviceBase` 处理了中介者模式的所有样板代码，具体设备只需实现自己的行为。
`SendNotification` 包装了中介者调用。

如果你用过观察者模式，这里有一个关键区别：观察者模式中，主题直接向订阅者列表广播；中介者模式中，所有通信经中央对象路由，由它决定谁接收什么。

## 智能家居设备实现

现在构建四个具体设备，各自处理自己的职责，只通过中介者通信。

### 灯光控制器

灯光控制器管理亮度和开关状态，响应安防事件和移动检测：

```csharp
namespace SmartHome.Devices;

public sealed class LightController : SmartDeviceBase
{
    public LightController(string deviceId)
        : base(deviceId, "Light")
    {
    }

    public int Brightness { get; private set; } = 100;
    public bool IsOn { get; private set; } = true;

    public void SetBrightness(int level)
    {
        Brightness = Math.Clamp(level, 0, 100);
        IsOn = Brightness > 0;

        SendNotification(
            "brightness_changed",
            new Dictionary<string, object>
            {
                ["brightness"] = Brightness
            });
    }

    public void TurnOff() => SetBrightness(0);
    public void TurnOn(int brightness = 100) =>
        SetBrightness(brightness);

    public override void ReceiveNotification(
        DeviceNotification notification)
    {
        switch (notification.EventType)
        {
            case "security_armed":
                SetBrightness(10);
                break;

            case "security_disarmed":
                SetBrightness(100);
                break;

            case "motion_detected":
                if (!IsOn) TurnOn(70);
                break;
        }
    }
}
```

### 智能温控器

温控器管理温度和运行模式，响应安防事件：

```csharp
namespace SmartHome.Devices;

public sealed class SmartThermostat : SmartDeviceBase
{
    public SmartThermostat(string deviceId)
        : base(deviceId, "Thermostat")
    {
    }

    public double TargetTemperature { get; private set; }
        = 72.0;

    public string Mode { get; private set; } = "comfort";

    public void SetTemperature(double temperature)
    {
        TargetTemperature = temperature;

        SendNotification(
            "temperature_changed",
            new Dictionary<string, object>
            {
                ["temperature"] = TargetTemperature,
                ["mode"] = Mode
            });
    }

    public void SetMode(string mode)
    {
        Mode = mode;

        TargetTemperature = mode switch
        {
            "eco" => 65.0,
            "comfort" => 72.0,
            "away" => 60.0,
            _ => TargetTemperature
        };

        SendNotification(
            "thermostat_mode_changed",
            new Dictionary<string, object>
            {
                ["mode"] = Mode,
                ["temperature"] = TargetTemperature
            });
    }

    public override void ReceiveNotification(
        DeviceNotification notification)
    {
        switch (notification.EventType)
        {
            case "security_armed":
                SetMode("away");
                break;

            case "security_disarmed":
                SetMode("comfort");
                break;
        }
    }
}
```

### 安防系统

安防系统监控家居并广播布防/撤防事件。其他设备通过这些事件响应，安防系统完全不知道灯光、温控器或音乐播放器的存在：

```csharp
namespace SmartHome.Devices;

public sealed class SecuritySystem : SmartDeviceBase
{
    public SecuritySystem(string deviceId)
        : base(deviceId, "Security")
    {
    }

    public bool IsArmed { get; private set; }
    public List<string> AlertLog { get; } = new();

    public void Arm()
    {
        IsArmed = true;

        SendNotification(
            "security_armed",
            new Dictionary<string, object>
            {
                ["armed"] = true
            });
    }

    public void Disarm()
    {
        IsArmed = false;

        SendNotification(
            "security_disarmed",
            new Dictionary<string, object>
            {
                ["armed"] = false
            });
    }

    public void DetectMotion(string zone)
    {
        if (IsArmed)
        {
            AlertLog.Add($"Motion in {zone}");

            SendNotification(
                "motion_detected",
                new Dictionary<string, object>
                {
                    ["zone"] = zone,
                    ["alert"] = true
                });
        }
    }

    public override void ReceiveNotification(
        DeviceNotification notification)
    {
        if (notification.EventType
            == "temperature_changed")
        {
            var temp = notification
                .GetPayloadValue<double>("temperature");
            if (temp > 95.0)
            {
                AlertLog.Add(
                    "High temperature alert: " +
                    $"{temp}°F");
            }
        }
    }
}
```

### 音乐播放器

音乐播放器管理播放状态。布防时暂停，撤防时可恢复：

```csharp
namespace SmartHome.Devices;

public sealed class MusicPlayer : SmartDeviceBase
{
    public MusicPlayer(string deviceId)
        : base(deviceId, "Music")
    {
    }

    public bool IsPlaying { get; private set; }
    public string CurrentTrack { get; private set; }
        = string.Empty;
    public int Volume { get; private set; } = 50;

    public void Play(string track)
    {
        CurrentTrack = track;
        IsPlaying = true;

        SendNotification(
            "music_started",
            new Dictionary<string, object>
            {
                ["track"] = track
            });
    }

    public void Pause()
    {
        IsPlaying = false;

        SendNotification("music_paused",
            new Dictionary<string, object>());
    }

    public void SetVolume(int volume)
    {
        Volume = Math.Clamp(volume, 0, 100);
    }

    public override void ReceiveNotification(
        DeviceNotification notification)
    {
        switch (notification.EventType)
        {
            case "security_armed":
                if (IsPlaying) Pause();
                break;

            case "security_disarmed":
                if (!IsPlaying
                    && !string.IsNullOrEmpty(CurrentTrack))
                {
                    Play(CurrentTrack);
                }
                break;

            case "brightness_changed":
                var brightness = notification
                    .GetPayloadValue<int>("brightness");
                if (brightness < 30)
                {
                    SetVolume(
                        Math.Min(Volume, 30));
                }
                break;
        }
    }
}
```

注意每个设备只关心跟自己相关的事件。
`MusicPlayer` 不知道 `SecuritySystem` 存在——它只知道自己收到 `"security_armed"` 事件时该做什么。
这就是中介者模式的价值：设备松耦合，各自可独立测试、修改或替换。

## Home Automation Mediator 实现

中介者本身负责注册设备、接收通知、转发给所有其他设备：

```csharp
namespace SmartHome.Core;

public sealed class HomeAutomationMediator
    : ISmartHomeMediator
{
    private readonly List<ISmartDevice> _devices = new();

    public IReadOnlyList<ISmartDevice> Devices
        => _devices.AsReadOnly();

    public void RegisterDevice(ISmartDevice device)
    {
        if (_devices.Any(d =>
            d.DeviceId == device.DeviceId))
        {
            throw new InvalidOperationException(
                $"Device '{device.DeviceId}' " +
                "is already registered.");
        }

        _devices.Add(device);
        device.SetMediator(this);
    }

    public void Notify(
        ISmartDevice sender,
        DeviceNotification notification)
    {
        foreach (var device in _devices)
        {
            if (device.DeviceId != sender.DeviceId)
            {
                device.ReceiveNotification(notification);
            }
        }
    }
}
```

中介者把每条通知转发给除发送者外的所有设备。这是**广播方式**——每个设备收到每个事件，内部决定是否响应。
另一种方式是**路由方式**，中介者包含条件逻辑决定哪些设备接收哪些事件。
广播方式让中介者保持简单，把决策推给设备——当系统需要持续扩展时，这是更可持续的选择。

注意中介者对灯光、温控器、音乐播放器的具体行为一无所知。
和文章开头那段 `SecuritySystem` 相比——中介者只依赖抽象的 `ISmartDevice` 接口，不依赖任何具体设备。

## 测试

因为设备通过中介者接口通信而非直接引用，你可以隔离测试每个设备。
下面是使用 xUnit 的完整测试类：

```csharp
using SmartHome.Core;
using SmartHome.Devices;

using Xunit;

namespace SmartHome.Tests;

public class HomeAutomationMediatorTests
{
    private readonly HomeAutomationMediator _mediator;
    private readonly LightController _lights;
    private readonly SmartThermostat _thermostat;
    private readonly SecuritySystem _security;
    private readonly MusicPlayer _music;

    public HomeAutomationMediatorTests()
    {
        _mediator = new HomeAutomationMediator();
        _lights = new LightController("light-01");
        _thermostat = new SmartThermostat("thermo-01");
        _security = new SecuritySystem("security-01");
        _music = new MusicPlayer("music-01");

        _mediator.RegisterDevice(_lights);
        _mediator.RegisterDevice(_thermostat);
        _mediator.RegisterDevice(_security);
        _mediator.RegisterDevice(_music);
    }

    [Fact]
    public void Arm_SecurityArmed_LightsDimToTen()
    {
        _security.Arm();
        Assert.Equal(10, _lights.Brightness);
    }

    [Fact]
    public void Arm_SecurityArmed_ThermostatSwitchesToAway()
    {
        _security.Arm();
        Assert.Equal("away", _thermostat.Mode);
        Assert.Equal(60.0, _thermostat.TargetTemperature);
    }

    [Fact]
    public void Arm_MusicPlaying_MusicPauses()
    {
        _music.Play("Ambient Vibes");
        _security.Arm();
        Assert.False(_music.IsPlaying);
    }

    [Fact]
    public void Disarm_LightsRestoreFullBrightness()
    {
        _security.Arm();
        _security.Disarm();
        Assert.Equal(100, _lights.Brightness);
    }

    [Fact]
    public void Disarm_MusicResumes()
    {
        _music.Play("Evening Jazz");
        _security.Arm();
        _security.Disarm();
        Assert.True(_music.IsPlaying);
        Assert.Equal("Evening Jazz", _music.CurrentTrack);
    }

    [Fact]
    public void Disarm_ThermostatResumesComfort()
    {
        _security.Arm();
        _security.Disarm();
        Assert.Equal("comfort", _thermostat.Mode);
        Assert.Equal(72.0, _thermostat.TargetTemperature);
    }

    [Fact]
    public void RegisterDevice_DuplicateId_Throws()
    {
        var duplicate = new LightController("light-01");
        Assert.Throws<InvalidOperationException>(
            () => _mediator.RegisterDevice(duplicate));
    }
}
```

每个测试通过中介者验证一个具体的跨设备交互。
测试不需要 mock——设备本身是轻量且确定性的。
你还可以完全隔离测试单个设备：

```csharp
public class LightControllerTests
{
    [Fact]
    public void ReceiveNotification_SecurityArmed_DimToTen()
    {
        var light = new LightController("light-test");

        var notification = new DeviceNotification(
            "security-01",
            "security_armed",
            new Dictionary<string, object>
            {
                ["armed"] = true
            });

        light.ReceiveNotification(notification);

        Assert.Equal(10, light.Brightness);
    }
}
```

直接构造 `DeviceNotification` 调用 `ReceiveNotification`，不需要中介器也不需要其他设备。
这是中介者模式最强的实践优势之一。

## 新增设备，不改现有代码

假设要加一个智能门锁——布防自动上锁，撤防自动解锁。
不碰任何现有代码：

```csharp
namespace SmartHome.Devices;

public sealed class SmartLock : SmartDeviceBase
{
    public SmartLock(string deviceId)
        : base(deviceId, "Lock")
    {
    }

    public bool IsLocked { get; private set; }

    public void Lock()
    {
        IsLocked = true;
        SendNotification(
            "door_locked",
            new Dictionary<string, object>
            {
                ["locked"] = true
            });
    }

    public void Unlock()
    {
        IsLocked = false;
        SendNotification(
            "door_unlocked",
            new Dictionary<string, object>
            {
                ["locked"] = false
            });
    }

    public override void ReceiveNotification(
        DeviceNotification notification)
    {
        switch (notification.EventType)
        {
            case "security_armed":
                Lock();
                break;

            case "security_disarmed":
                Unlock();
                break;
        }
    }
}
```

注册只需要一行：

```csharp
var smartLock = new SmartLock("lock-front-door");
mediator.RegisterDevice(smartLock);
```

中介器无需改动，安防系统、灯光、温控器、音乐播放器都不需要改。
新设备接入现有通知基础设施就能立即参与协调——这正是开闭原则的实践。

## DI 集成

生产环境中，你会把中介器和设备注册到 DI 容器：

```csharp
using Microsoft.Extensions.DependencyInjection;
using SmartHome.Core;
using SmartHome.Devices;

namespace SmartHome.Configuration;

public static class SmartHomeServiceExtensions
{
    public static IServiceCollection AddSmartHome(
        this IServiceCollection services)
    {
        services.AddSingleton<ISmartHomeMediator>(sp =>
        {
            var mediator = new HomeAutomationMediator();
            var devices = sp.GetServices<ISmartDevice>();
            foreach (var device in devices)
            {
                mediator.RegisterDevice(device);
            }
            return mediator;
        });

        services
            .AddSingleton<ISmartDevice>(
                new LightController("light-living"));
        services
            .AddSingleton<ISmartDevice>(
                new SmartThermostat("thermo-main"));
        services
            .AddSingleton<ISmartDevice>(
                new SecuritySystem("security-main"));
        services
            .AddSingleton<ISmartDevice>(
                new MusicPlayer("music-main"));
        services
            .AddSingleton<ISmartDevice>(
                new SmartLock("lock-front-door"));

        return services;
    }
}
```

加新设备就是加一个 `AddSingleton` 注册。
中介器的工厂 lambda 自动拾取所有 `ISmartDevice` 注册。

## 生产化考虑

同步广播中介器在很多场景下够用，生产系统通常还需要更多。

### 异步通知

如果设备涉及 I/O——调外部 API、写数据库、发 HTTP 请求——你需要异步版本：

```csharp
public interface IAsyncSmartHomeMediator
{
    void RegisterDevice(IAsyncSmartDevice device);
    Task NotifyAsync(
        IAsyncSmartDevice sender,
        DeviceNotification notification,
        CancellationToken cancellationToken = default);
}
```

### 错误隔离

广播模式下，一个设备抛异常不应阻止其他设备收到通知。
在 `ReceiveNotification` 外包 try-catch 并记录日志：

```csharp
public void Notify(
    ISmartDevice sender,
    DeviceNotification notification)
{
    foreach (var device in _devices)
    {
        if (device.DeviceId == sender.DeviceId) continue;

        try
        {
            device.ReceiveNotification(notification);
        }
        catch (Exception ex)
        {
            _logger.LogError(
                ex,
                "Device {DeviceId} failed to handle " +
                "{EventType} notification",
                device.DeviceId,
                notification.EventType);
        }
    }
}
```

### 选择性路由

设备多了之后，可以用事件订阅方式优化——设备声明自己关心哪些事件类型，中介器按类型路由。
从广播开始，只在性能或复杂度需要时优化到选择性路由。

### 日志与可观测性

所有通知都经过中介器，你获得了一个天然的中心日志点。
每个协调事件都可以在这里记录、计量或追踪——比直接耦合方式省心很多。

## 中介者 vs 直接耦合

总结一下取舍。

直接耦合时，`SecuritySystem` 持有三个设备引用，任何一个设备变化都要改它。
中介者模式把 N×N 的直接依赖变成 N-to-1 的依赖。
代价是中介器可能变成"上帝对象"——所以让它保持薄，只路由消息，不包含业务逻辑。
设备拥有自己的行为，中介器拥有路由。

## 常见问题

**什么时候用 Mediator 而不是直接方法调用？**

当多个对象需要互相通信、且直接连接的规模在增长时。对象 A 只跟 B 对话——直接调用就行。但 A 需要跟 B、C、D、E 协调，而且它们之间也需要互相协调时，Mediator 比网格依赖更清晰。

**Mediator 和 Observer 的区别？**

Observer 是一对多广播：主题通知订阅者状态变化。
Mediator 是多对多协调：参与者经中央对象通信。
Observer 中主题知道有观察者但不知道它们做什么；Mediator 中参与者互相完全不知对方存在。
Mediator 还可以做路由、过滤和转换，Observer 不提供这些。

**跟 MediatR 的关系？**

MediatR 是 .NET 生态里流行的进程内消息处理库，实现了 Mediator 模式。
它的 request/response 和 notification 模式通过 DI 解析 handler，概念和本文直接对应。
MediatR 处理基础设施，让你专注写 handler，就像 `HomeAutomationMediator` 把通知路由到设备。

**最大的风险？**

中介器变成"上帝对象"，随时间积累业务逻辑。
中介器应该只路由消息，不该决定温控器该设什么温度、灯光该不该调暗。
如果中介器类超出简单转发逻辑，把决策搬回参与类。

**怎样不搭整个中介器就测试单个设备？**

直接构造 `DeviceNotification` 调用设备的 `ReceiveNotification`。
创建 `LightController`，发一个 `"security_armed"` 通知，断言亮度降到 10。
不需要中介器、不需要其他设备、不需要 mock。

## 小结

这篇文章从 `SecuritySystem` 跟灯光、温控器、音乐播放器直接耦合开始，走到一个完整的 `HomeAutomationMediator` 协调系统。
四个设备各自独立、可测试、可替换，新增 `SmartLock` 不改任何现有代码。

当你发现一个类的构造函数参数越来越多、只是因为"某件事发生时要戳一下另一个类"——把这条通信路由到中介器。
替换掉内存对象为真实硬件集成和云服务调用，加上异步和错误隔离，就能得到可落地的家居自动化协调器基础。

---

如果你关注 AI 助手、开发工具和软件工程实践，可以关注 Aide Hub。这里会继续分享能落地的工具教程、技术观察和项目经验。

## 参考

- [Mediator Pattern Real-World Example in C#: Complete Implementation — devleader.ca](https://www.devleader.ca/2026/06/16/mediator-pattern-realworld-example-in-c-complete-implementation)
- [Observer Design Pattern in C# — devleader.ca](https://www.devleader.ca/2026/03/26/observer-design-pattern-in-c-complete-guide-with-examples)
- [Command Design Pattern in C# — devleader.ca](https://www.devleader.ca/2026/04/14/command-design-pattern-in-c-complete-guide-with-examples)
- [Inversion of Control — devleader.ca](https://www.devleader.ca/2024/01/07/what-is-inversion-of-control-a-simplified-beginners-guide)
