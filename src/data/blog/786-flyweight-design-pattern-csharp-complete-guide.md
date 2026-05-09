---
pubDatetime: 2026-05-09T09:00:00+08:00
title: "C# 享元设计模式完全指南：原理、实现与实战"
description: "享元模式通过共享内在状态大幅减少内存占用：5000个粒子只需3个Flyweight实例，内存从320MB降至不足200KB。本文用字符渲染和粒子系统两个例子讲清楚内在/外在状态分离、工厂池化、线程安全和DI集成。"
tags: ["csharp", "design-patterns", "dotnet", "performance"]
slug: "flyweight-design-pattern-csharp-complete-guide"
ogImage: "../../assets/786/01-cover.webp"
source: "https://www.devleader.ca/2026/05/08/flyweight-design-pattern-in-c-complete-guide-with-examples"
---

当应用需要创建数千甚至数百万个相似对象时，内存会迅速失控。享元（Flyweight）设计模式专门解决这个问题：把相似对象之间共同的数据提取出来集中存放，让多个对象共用同一份数据，而不是每个对象各自维护一份副本。

读完本文，你会清楚地知道：什么情况下值得用享元模式、如何分离内在状态和外在状态、如何实现享元工厂，以及如何处理线程安全和依赖注入。

---

## 享元模式是什么

享元模式是 GoF（Gang of Four）设计模式目录中的结构型模式。核心思路是：把大量相似对象共有的数据抽取到一个共享对象中，多个使用场景通过引用指向这个共享对象，而不是各自保存一份拷贝。"Flyweight"这个名字来自拳击的轻量级别——这些对象要尽可能轻。

模式要解决的问题很具体：当你的应用需要创建大量内容高度相似的对象时，把所有数据都存在每个对象里会浪费大量内存。享元模式把共享的数据抽取到独立对象中，其余对象只持有引用。这样可以大幅减少对象总数和内存占用。

---

## 内在状态与外在状态

享元模式的核心设计决策是把对象状态分成两类。划分得对，模式才能发挥作用。

**内在状态（Intrinsic State）** 是存储在享元对象内部、在所有使用场景中保持不变的数据。正因为它对所有使用者都相同，才有共享的可能。常见例子：字体元数据、精灵纹理、颜色定义、各种不因上下文变化的配置数据。

**外在状态（Extrinsic State）** 是随使用场景变化的数据。它不存储在享元对象里，而是由客户端代码在调用时传入。常见例子：屏幕坐标、当前字号、粒子速度，任何因具体使用位置不同而变化的数据。

模式的内存节省就来自这个分离。假设屏幕上有 10,000 个字符，字体相同，你只需要 26 个字母的享元对象各一份，而不是 10,000 份。位置和字号是外在状态，由渲染时的调用方来管理。

常见错误是把太多状态放进享元（让它无法真正共享），或者太少（让客户端要传递过多的外在状态）。平衡点是关键：内在状态越大、唯一组合数越少，模式带来的收益越高。

---

## 享元模式的核心结构

模式由四个角色组成。先搞清楚每个角色的职责，再看代码会更顺畅。

### 享元接口

享元接口声明的方法把外在状态作为参数接收。这是所有享元对象（包括可共享和不可共享的）都要遵守的契约。关键约束：方法需要但不共享的状态，必须通过参数传入。

### 具体享元

具体享元实现享元接口，存储内在状态。它必须是可共享的，这意味着内在状态在创建时确定，之后不再变化。C# 中最稳妥的做法是让它不可变。

### 享元工厂

享元工厂管理享元对象的缓存池。客户端请求享元时，工厂先查字典：如果内在状态匹配的对象已存在，直接返回；否则创建新对象、存入字典、再返回。这个基于字典的缓存就是共享得以实现的机制。

### 客户端

客户端持有享元引用并维护外在状态。需要享元执行操作时，把外在状态一起传进去。客户端通过享元接口操作，享元实例从工厂获取。

---

## 在 C# 中实现享元模式

先从基础实现开始，用文本渲染系统演示核心机制：屏幕上要显示数千个字符，但每个唯一字符共享它的字体和字形数据。

### 享元接口与具体享元

```csharp
// 享元接口——外在状态通过方法参数传入
public interface ICharacterFlyweight
{
    char Symbol { get; }

    void Render(int x, int y, int fontSize);
}

// 具体享元——只存储内在（共享）状态
public sealed class CharacterFlyweight : ICharacterFlyweight
{
    public char Symbol { get; }
    public string FontFamily { get; }
    public byte[] GlyphData { get; }
    public bool IsBold { get; }

    public CharacterFlyweight(
        char symbol,
        string fontFamily,
        byte[] glyphData,
        bool isBold)
    {
        Symbol = symbol;
        FontFamily = fontFamily;
        GlyphData = glyphData;
        IsBold = isBold;
    }

    public void Render(int x, int y, int fontSize)
    {
        // 真实系统里这里会用 GlyphData 在指定坐标渲染字符
        Console.WriteLine(
            $"Rendering '{Symbol}' ({FontFamily}, " +
            $"bold={IsBold}) at ({x},{y}) " +
            $"size={fontSize}"
        );
    }
}
```

`CharacterFlyweight` 存储内在状态：字符符号、字体族、字形数据、粗体标志。这些数据无论字符出现在屏幕哪个位置都不变。`Render` 方法把位置和字号作为参数接收，因为它们因使用场景而异。

### 享元工厂

```csharp
public sealed class CharacterFlyweightFactory
{
    private readonly Dictionary<string, ICharacterFlyweight>
        _flyweights = new();

    public ICharacterFlyweight GetFlyweight(
        char symbol,
        string fontFamily,
        bool isBold)
    {
        // 用内在状态组合成键
        string key = $"{symbol}_{fontFamily}_{isBold}";

        if (!_flyweights.TryGetValue(key, out var flyweight))
        {
            // 模拟加载字形数据——实际系统里可能来自字体文件
            byte[] glyphData = LoadGlyphData(symbol, fontFamily);

            flyweight = new CharacterFlyweight(
                symbol,
                fontFamily,
                glyphData,
                isBold);

            _flyweights[key] = flyweight;
        }

        return flyweight;
    }

    public int GetFlyweightCount() => _flyweights.Count;

    private static byte[] LoadGlyphData(
        char symbol,
        string fontFamily)
    {
        // 模拟加载字形数据，每个字形可能有几 KB 的矢量数据
        return new byte[2048];
    }
}
```

工厂用内在状态字段生成复合键。当相同的字符符号+字体族+粗体组合再次被请求时，工厂返回已缓存的实例。如果文档里有 10,000 个 Arial 非粗体的字母 'A'，只有一个 `CharacterFlyweight` 实例被创建。

### 客户端调用

```csharp
var factory = new CharacterFlyweightFactory();

string text = "Hello World! Hello World! Hello World!";
int x = 0;
int y = 0;
int fontSize = 12;

foreach (char c in text)
{
    // 获取该字符的共享享元
    ICharacterFlyweight flyweight = factory.GetFlyweight(
        c,
        "Arial",
        isBold: false);

    // 渲染时传入外在状态（位置、字号）
    flyweight.Render(x, y, fontSize);

    x += 10;
    if (x > 200)
    {
        x = 0;
        y += 20;
    }
}

Console.WriteLine(
    $"Total flyweight objects created: {factory.GetFlyweightCount()}"
);
Console.WriteLine(
    $"Total characters rendered: {text.Length}"
);
```

虽然渲染了 38 个字符，工厂只为文本中出现的唯一字符创建了享元对象。位置和字号数据从不存储在享元里——它由客户端在调用时计算和传入。这是模式内存优势的直接体现。

---

## 实战案例：游戏粒子系统

文字渲染是教科书例子，再看一个内存节省更显著的场景。游戏粒子系统通常需要数千个活跃粒子，每个粒子共用同一张精灵图或纹理数据。不用享元的话，每个粒子都会持有纹理字节数据的独立副本。

### 粒子享元定义

```csharp
public interface IParticleFlyweight
{
    void Draw(
        float x,
        float y,
        float velocityX,
        float velocityY,
        float scale,
        float rotation);
}

public sealed class ParticleFlyweight : IParticleFlyweight
{
    // 内在状态——对同类所有粒子共享
    public string TextureName { get; }
    public byte[] SpriteData { get; }
    public string BlendMode { get; }

    public ParticleFlyweight(
        string textureName,
        byte[] spriteData,
        string blendMode)
    {
        TextureName = textureName;
        SpriteData = spriteData;
        BlendMode = blendMode;
    }

    public void Draw(
        float x,
        float y,
        float velocityX,
        float velocityY,
        float scale,
        float rotation)
    {
        // 真实引擎里这里会把精灵提交到 GPU，附带变换矩阵
        Console.WriteLine(
            $"Drawing {TextureName} " +
            $"(blend={BlendMode}) " +
            $"at ({x:F1},{y:F1}) " +
            $"scale={scale:F2} rot={rotation:F1}"
        );
    }
}
```

内在状态是纹理名称、精灵原始数据和混合模式。"spark"粒子永远用同一张精灵和同一种混合模式，这些是共享的。外在状态——位置、速度、缩放、旋转——对每个粒子实例各不相同。

### 工厂与上下文对象

```csharp
public sealed class ParticleFlyweightFactory
{
    private readonly Dictionary<string, IParticleFlyweight>
        _particles = new();

    public IParticleFlyweight GetParticle(
        string textureName,
        string blendMode)
    {
        string key = $"{textureName}_{blendMode}";

        if (!_particles.TryGetValue(key, out var particle))
        {
            byte[] spriteData = LoadTexture(textureName);

            particle = new ParticleFlyweight(
                textureName,
                spriteData,
                blendMode);

            _particles[key] = particle;
        }

        return particle;
    }

    public int GetPoolSize() => _particles.Count;

    private static byte[] LoadTexture(string textureName)
    {
        // 模拟加载纹理——每张可能有 64KB 以上的图像数据
        return new byte[65536];
    }
}

// 外在状态容器——客户端负责管理
public sealed class ParticleContext
{
    public float X { get; set; }
    public float Y { get; set; }
    public float VelocityX { get; set; }
    public float VelocityY { get; set; }
    public float Scale { get; set; }
    public float Rotation { get; set; }
    public IParticleFlyweight Flyweight { get; }

    public ParticleContext(
        IParticleFlyweight flyweight,
        float x,
        float y,
        float velocityX,
        float velocityY)
    {
        Flyweight = flyweight;
        X = x;
        Y = y;
        VelocityX = velocityX;
        VelocityY = velocityY;
        Scale = 1.0f;
        Rotation = 0f;
    }

    public void Update(float deltaTime)
    {
        X += VelocityX * deltaTime;
        Y += VelocityY * deltaTime;
        Scale *= 0.99f;
        Rotation += 2.0f * deltaTime;
    }

    public void Draw()
    {
        Flyweight.Draw(
            X, Y,
            VelocityX, VelocityY,
            Scale, Rotation);
    }
}
```

`ParticleContext` 持有所有外在状态以及对共享享元的引用。每个粒子都有自己的 `ParticleContext`，但它很轻量——几个浮点数加一个引用。重量级的精灵数据存在共享享元里。

### 效果验证

```csharp
var factory = new ParticleFlyweightFactory();
var random = new Random(42);
var particles = new List<ParticleContext>();

// 用 3 种粒子类型创建 5000 个粒子
string[] types = { "spark", "smoke", "flame" };
string[] blends = { "additive", "alpha", "additive" };

for (int i = 0; i < 5000; i++)
{
    int typeIndex = random.Next(types.Length);

    IParticleFlyweight flyweight = factory.GetParticle(
        types[typeIndex],
        blends[typeIndex]);

    var context = new ParticleContext(
        flyweight,
        x: random.NextSingle() * 800,
        y: random.NextSingle() * 600,
        velocityX: (random.NextSingle() - 0.5f) * 100,
        velocityY: (random.NextSingle() - 0.5f) * 100);

    particles.Add(context);
}

Console.WriteLine($"Active particles: {particles.Count}");
Console.WriteLine($"Shared flyweight objects: {factory.GetPoolSize()}");
Console.WriteLine(
    $"Memory saved: ~{(5000 - factory.GetPoolSize()) * 64}KB of texture data"
);
```

5,000 个粒子，只有 3 个享元类型。不用享元的话，要存 5,000 份纹理数据；用了享元，只存 3 份。大约从 320MB 压缩到不足 200KB 的纹理内存。每个 `ParticleContext` 里只有几个浮点数，可以忽略不计。

---

## 多线程场景下的线程安全

应用是多线程的，享元工厂就需要同步。享元对象本身因为不可变，天然线程安全。工厂内部的字典则不是。

用 `ConcurrentDictionary` 处理线程安全：

```csharp
public sealed class ThreadSafeFlyweightFactory
{
    private readonly ConcurrentDictionary<string, IParticleFlyweight>
        _particles = new();

    public IParticleFlyweight GetParticle(
        string textureName,
        string blendMode)
    {
        string key = $"{textureName}_{blendMode}";

        return _particles.GetOrAdd(key, _ =>
        {
            byte[] spriteData = LoadTexture(textureName);
            return new ParticleFlyweight(
                textureName,
                spriteData,
                blendMode);
        });
    }

    private static byte[] LoadTexture(string textureName)
    {
        return new byte[65536];
    }
}
```

`ConcurrentDictionary.GetOrAdd` 以原子方式处理检查和创建，不过在争用时工厂委托可能被调用多次。对于享元对象来说，这是可以接受的——额外创建的实例会被丢弃，内在状态无论如何都是相同的。

---

## 与依赖注入集成

生产应用里，把享元工厂注册到 DI 容器。工厂本身应该是单例——它在应用生命周期内管理共享池：

```csharp
services.AddSingleton<CharacterFlyweightFactory>();
services.AddSingleton<ParticleFlyweightFactory>();
```

需要享元的组件通过构造函数注入接收工厂，而不是自己创建。这让工厂集中管理、便于测试。如果需要在不同环境中切换缓存策略，也可以把工厂定义在接口后面。

---

## 什么时候用，什么时候不用

享元模式不是万能优化工具，它在特定条件下才有效。

**适合用的场景：**

- 应用创建了大量共享大量内在状态的对象。共享状态越大、对象数量越多，收益越显著。文本编辑器、地图渲染、粒子系统、图标管理器都是典型场景。
- 外在状态可以在外部计算或存储，不会让客户端代码变得难以维护。

**不适合用的场景：**

- 内在状态的唯一组合数接近对象总数时。每个对象内在状态都不同，就没什么可共享的，工厂只会增加额外开销。
- 共享状态本身很小时。如果每个对象只有几个字节，工厂的字典查找开销可能超过节省的内存。

享元模式与其他模式配合良好：可以用外观（Facade）模式隐藏工厂和外在状态管理的复杂度；可以与组合（Composite）模式结合共享树结构中的叶节点数据；工厂本身也体现了工厂方法的设计思路。

---

## 常见错误

**把外在状态放进享元。** 这是最常见的错误，也是最致命的，直接让整个模式失效。享元里的每个字段在所有使用场景中都应该是相同的。如果你想往享元里加位置、名称或 ID，那是外在状态，属于客户端。

**让享元可变。** 享元创建后必须实际上是不可变的。一个客户端修改了共享状态，所有使用该享元的其他客户端都会受影响，导致难以复现的 bug。用 `readonly` 字段、`init` 属性或 `sealed` 类强制不可变性。

**工厂键过度设计。** 键只需要唯一标识内在状态，用简单的复合字符串或值元组足够应对大多数场景，没必要用序列化或哈希之类的方案引入额外开销。

**忘记测量。** 享元模式是性能优化手段，应该在性能分析确认重复对象的内存消耗是真实问题后再应用，而不是预防性地套用。过早优化只会增加复杂度，不带来可量化的收益。

**忽略工厂自身的内存。** 工厂的字典本身也消耗内存。如果你为只用一次就不再需要的组合创建了享元，工厂会无限期持有这些引用。考虑加入驱逐策略，或者用 `WeakReference<T>` 管理享元的生命周期。

---

## 常见问题

**享元模式和对象池（Object Pool）有什么区别？**

两者都能减少对象创建，但解决的问题不同。享元共享的是不可变对象，多个客户端同时使用同一个实例。对象池复用的是可变且创建代价高的对象——一个客户端借出实例、用完后归还，再由另一个客户端使用。享元适合共享状态相同且只读的场景；对象池适合需要复用数据库连接、缓冲区等昂贵可变对象的场景。

**享元模式和单例（Singleton）有什么区别？**

单例确保一个类在应用中只有一个实例。享元工厂管理的是一组共享实例，每个实例代表一种独特的内在状态组合。单例控制的是"只有一个"，享元控制的是"按内在状态共享"，工厂可能管理数十甚至数百个实例。

**享元模式会引入线程安全问题吗？**

享元对象本身如果是不可变的就是线程安全的，它们本来就应该不可变。工厂内部的字典在多线程并发请求时需要同步，用 `ConcurrentDictionary` 可以干净地处理这个问题。外在状态由客户端按上下文管理，不存在共享状态的线程问题。

---

## 小结

享元设计模式是处理大量相似对象、减少内存占用的有效工具。核心就是两件事：把内在状态（共享且不可变）从外在状态（上下文相关且由客户端管理）中分离出来；用工厂缓存按内在状态键控的共享实例。

从字符渲染到粒子系统，任何"大量对象携带相同数据"的场景都适合套用这个模式。保持享元不可变、工厂线程安全、键尽量简单。节省的内存足够大时，这个模式值得引入的复杂度就完全合理。

## 参考

- [Flyweight Design Pattern in C#: Complete Guide with Examples](https://www.devleader.ca/2026/05/08/flyweight-design-pattern-in-c-complete-guide-with-examples)
