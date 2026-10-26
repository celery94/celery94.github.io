---
pubDatetime: 2026-10-26T09:33:00+08:00
title: "C# 14 扩展属性：状态存表里还是塞进对象"
description: "扩展属性没有背衬字段，状态得另找地方。一条路用 ConditionalWeakTable 挂外部数据，一条路用 Unsafe.As 伪造对象布局；后者会弄坏类型身份、相等判断和哈希，文中给出 .NET 10 的实测结果与边界。"
tags: ["C#", ".NET", "C# 14", "Extensions"]
slug: "csharp-14-extension-property-state"
ogImage: "../../assets/1116/01-cover.jpg"
source: "https://steven-giesel.com/blogPost/4368fcea-c922-403e-bb3b-6b4990eb36d2"
---

扩展属性在 C# 14 里成了正式语法，`person.Nickname = "Bob"` 这种写法能编译，也能读回值。编译器只提供一对 getter 和 setter，值存在哪里得自己安排。Steven Giesel 在[一篇文章](https://steven-giesel.com/blogPost/4368fcea-c922-403e-bb3b-6b4990eb36d2)里试了两条极端路线：把状态挂在对象外面的一张弱引用表上，或者用 `Unsafe.As` 把字段布局相同的镜像对象伪装成原类型。

第一条可以进生产代码，代价是每次读写都变成一次哈希查表，状态也不在对象里；第二条能让字段真的长在对象身上，代价是运行时类型、相等判断和哈希一起作废。我把原文的代码在 .NET 10.0.402 上跑了一遍，其中一条解释没站住，还有几条后果比原文写得更严重。

## 扩展属性本身不存东西

C# 14 的扩展成员写在静态类的 `extension` 块里（需要 .NET 10 SDK）。属性必须手写访问器，编译器不会替你合成字段。只读现有成员时这已经够用：

```csharp
sealed record Person(string Name, int Age);

static class PersonExtensions
{
    extension(Person person)
    {
        public bool IsAdult => person.Age >= 18;
    }
}
```

`IsAdult` 每次调用现算，不占空间。一旦需要可写状态，问题就浮出来：扩展属性没有自己的存储位置，`Nickname` 的值必须在别处落脚。原文两条路的分歧就在这一步。

## 把状态挂到 ConditionalWeakTable 上

`ConditionalWeakTable<TKey, TValue>` 是运行时提供的弱键映射表。原文的写法把 `Person` 当 key，`StrongBox<string?>` 当 value（为简洁，后面的例子只保留 Name）：

```csharp
using System.Runtime.CompilerServices;

sealed record Person(string Name);

static class PersonExtensions
{
    static readonly ConditionalWeakTable<Person, StrongBox<string?>> Nicknames = new();

    extension(Person person)
    {
        public string? Nickname
        {
            get => Nicknames.TryGetValue(person, out var box) ? box.Value : null;
            set => Nicknames.GetOrCreateValue(person).Value = value;
        }
    }
}

var person = new Person("Robert");
person.Nickname = "Bob";
```

换成 `Dictionary<Person, string?>` 也能跑，但字典强引用每个 key，等于把用过的 Person 全部钉在内存里。弱引用表不延长 key 的寿命：我把它设置成 `WeakReference<Person>` 之后强制 GC，对象确实被回收了，表项跟着消失。文档里也写明这个类型本身线程安全，调用方不需要额外加锁。

## StrongBox 省下的是一次 lambda

原文给 `StrongBox` 的解释是：直接把值存进表里，就分不清「没设置过」和「设置成 null」。

在 .NET 10.0.402 上实测对不上。`ConditionalWeakTable<Person, string?>.Add(person, null)` 不会抛异常，`TryGetValue` 返回 true，取出的值就是 null——「有没有设置过」看返回值就够了。

`StrongBox` 真正省掉的是 setter 里的一次 lambda：

```csharp
Nicknames.GetOrCreateValue(person).Value = value;
```

`GetOrCreateValue()` 在建表项时会动态创建值实例。`string` 没有无参构造函数，实测调用直接抛 `MissingMethodException`，而且这个失败拖到运行时才出现——方法签名上没有编译期约束拦你。`StrongBox<string?>` 有无参构造函数，包一层之后 setter 才能写成 `GetOrCreateValue(person).Value = value`，不用写 `GetValue(person, _ => new StrongBox<string?>())`。代价是 getter 要多绕一层对象。

这套方案的代价藏在用法里。`person.Nickname` 看起来像字段访问，实际是方法调用加一次哈希查找；它在当前进程内有效，对象被序列化、复制、跨服务传走之后，附加状态全部丢失。record 的相等比较也不会看这张表，两个只有 Nickname 不同的 Person 依然相等。

## 用 Unsafe.As 把镜像对象伪装成原类型

要绕开外部表，就得让字段长在对象身上。原文造了一个字段布局相同的类，把它的实例冒充成 `Person`：

```csharp
sealed class PersonPlus
{
    public string Name = "";
    public string? Nickname;

    public override string ToString() => $"Person {{ Name = {Name} }}";
}

static class PersonExtensions
{
    public static Person Create(string name, string? nickname = null)
        => Unsafe.As<Person>(new PersonPlus { Name = name, Nickname = nickname });

    extension(Person person)
    {
        public string? Nickname
        {
            get => person is PersonPlus
                ? Unsafe.As<PersonPlus>(person).Nickname
                : null;

            set
            {
                if (person.GetType() != typeof(PersonPlus))
                    throw new InvalidOperationException("不是 Create 造出来的对象");
                Unsafe.As<PersonPlus>(person).Nickname = value;
            }
        }
    }
}
```

`Create` 分配的是 `PersonPlus`，`Unsafe.As<Person>` 只是换一种静态视角去读同一块内存。两边第一个字段都是 Name，所以 `person.Name` 读得到；Nickname 落在后面的字段上，用起来像 Person 自己多了个属性。

麻烦从编译期就开始了。`person is PersonPlus` 会触发 CS0184 警告，编译器认为这永远不成立，因为 Person 是 sealed。构建配置里开了 `TreatWarningsAsErrors` 的话，这一行直接让构建失败。

更别扭的是，这句话在运行时的答案取决于写法。`person.GetType()` 返回 `PersonPlus`，`((object)person) is PersonPlus` 返回 true，`((object)person) is Person` 返回 false；而静态类型下的 `person is PersonPlus` 返回 false，JIT 按 sealed 静态类型把检查折掉了。同一个问题，换个写法得到相反的答案。原因不神秘：对象的类型头仍然是 PersonPlus，改掉的只是编译器看到的类型。

## 相等判断和哈希在这里失效

Person 是 record，相等语义由编译器生成：比较字段和 EqualityContract。用 Unsafe.As 换过视角之后，静态类型决定调用哪套实现，运行时类型决定虚方法怎么派发，两边对不上。下面这些结果来自同一组对象，两个由 `Create("a")` 造出来、内容完全相同的 Person：

| 调用                                    | 结果  |
| --------------------------------------- | ----- |
| `a1.Equals(a2)`                         | true  |
| `a1 == a2`                              | true  |
| `a1.Equals((object)a2)`                 | false |
| `object.Equals(a1, a2)`                 | false |
| `a1.GetHashCode() == a2.GetHashCode()`  | false |
| `set.Contains(a2)`（`set` 已放入 `a1`） | false |

按 Person 的静态类型比较，它们相等；按 object 比较，它们不等；哈希值也不同。放进 `HashSet` 或 `Dictionary` 之后，同一个值查不回来。

这不是极端输入才会踩的坑。把对象当 object 传出去的地方比想象中多：非泛型集合、以 object 为参数的比较器、反射、动态调用。走到那些路径上，对象是 PersonPlus 而不是 Person，`is Person` 的判断会直接返回 false。原文只留了一句「重命名或改类型都会让方案崩掉」的提醒，实际代价要大得多。

## 静态构造函数能探到多少

原文最后一招是在静态构造函数里做布局自检：

```csharp
static PersonExtensions()
{
    var probe = Create("steven");
    if (!ReferenceEquals(probe.Name, "steven"))
        throw new InvalidOperationException("Person/PersonPlus 布局不匹配");
}
```

第一次访问这个类时会跑一遍：造一个镜像、按 Person 的布局读回来，读不回来就抛。不匹配时构造函数抛异常，之后每次调用都变成 `TypeInitializationException`，问题能在启动早期暴露，比悄悄读到错值强。

它挡不住的东西同样明显。探针只读它自己构造的那一个字段，而且用的是引用比较。我换了个镜像，把 string 字段 `Tag` 放在 Name 前面，并让 `Tag` 的值等于探针期望的字符串，再用 Name 的位置去读，`ReferenceEquals` 依然返回 true，探针放行——它只证明这次读到的值碰巧对得上，布局兼容与否，它没有验证。

镜像和原类型之间任何一处漂移都可能不被发现：加一个引用字段、改字段类型、调整声明顺序、换运行时版本。编译器不会提醒，它看到的是两个互不相关的类。这一条比前面几条更值得记住：放弃的是编译器对字段布局的保证，而布局会变。

## 这两条路分别能用在哪儿

弱引用表适合给对象附加旁路数据：缓存、诊断标签、插件侧状态。前提是能接受一次查表、数据只在进程内、丢了不影响正确性。如果需要属性值跟着对象序列化、跨服务传、或者参与相等比较，这张表就不该出现——属性看起来属于对象，实际不属于。

`Unsafe.As` 那条我找不到生产场景。它依赖的东西编译器给不了保证，出问题的形式（字段错位、类型判断翻转、字典查不回来）往往隔很久才暴露。评审里遇到这种用法，先问一句：这个布局由谁保证，布局变了谁来发现？答不上来就不该合进去。

想给别人的类型加状态，常规选项仍然是组合一个包装类型、把状态放进使用方的字典，或者在调用边界做一次转换。它们都比伪造类型身份贵一点，但不会在你最不想查的时候坏。

## 参考

- [Adding Properties with extension methods in C# 14](https://steven-giesel.com/blogPost/4368fcea-c922-403e-bb3b-6b4990eb36d2)
- [Adding static getter thanks to extensions](https://steven-giesel.com/blogPost/605274d2-719b-4b1f-b0d5-3ad9001d9b56/adding-static-getter-thanks-to-extensions)
- [What's new in C# 14](https://learn.microsoft.com/en-us/dotnet/csharp/whats-new/csharp-14)
- [extension keyword](https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/keywords/extension)
- [ConditionalWeakTable&lt;TKey,TValue&gt;](https://learn.microsoft.com/en-us/dotnet/api/system.runtime.compilerservices.conditionalweaktable-2)
- [Unsafe class](https://learn.microsoft.com/en-us/dotnet/api/system.runtime.compilerservices.unsafe)
- [StrongBox&lt;T&gt;](https://learn.microsoft.com/en-us/dotnet/api/system.runtime.compilerservices.strongbox-1)
