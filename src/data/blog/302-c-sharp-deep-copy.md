---
pubDatetime: 2025-04-30
tags: [deep-copy, csharp, dotnet]
slug: deep-copy-csharp
source: openai
title: .NET Framework 4.6.2 安全深拷贝实现方案研究
description: 深拷贝（deep clone）指的是创建一个对象的完整副本，包括其包含的所有子对象，从而使原对象和副本在内存中完全独立。实现深拷贝时，安全性是首要考虑因素，需要避免使用已知存在反序列化安全漏洞的技术（例如 BinaryFormatter）。本文将评估多种适用于 .NET Framework 4.6.2 的安全深拷贝实现方式，包括使用 JSON 序列化（Newtonsoft.Json）、使用 Protobuf-net 序列化、利用表达式树或反射的通用实现，以及使用 AutoMapper 映射来克隆对象。每种方法都会从安全性、开源许可证、性能和适用性等方面进行分析，并给出示例。
---

# .NET Framework 4.6.2 安全深拷贝实现方案研究

深拷贝（deep clone）指的是创建一个对象的完整副本，包括其包含的所有子对象，从而使原对象和副本在内存中完全独立。实现深拷贝时，**安全性**是首要考虑因素，需要避免使用已知存在反序列化安全漏洞的技术（例如 `BinaryFormatter`） ([Deserialization risks in use of BinaryFormatter and related types - .NET | Microsoft Learn](https://learn.microsoft.com/en-us/dotnet/standard/serialization/binaryformatter-security-guide#:~:text=The%20BinaryFormatter%20%20type%20is,and%20can%27t%20be%20made%20secure))。本文将评估多种适用于 .NET Framework 4.6.2 的安全深拷贝实现方式，包括使用 JSON 序列化（Newtonsoft.Json）、使用 Protobuf-net 序列化、利用表达式树或反射的通用实现，以及使用 AutoMapper 映射来克隆对象。每种方法都会从安全性、开源许可证、性能和适用性等方面进行分析，并给出示例。

## 深拷贝的安全性考量

在讨论具体实现方案之前，需要明确为什么像 `BinaryFormatter` 这样的传统深拷贝手段是不安全的。Microsoft 明确指出：`BinaryFormatter.Deserialize` **无法保证安全**，不应在任何场景下使用（即使反序列化的数据被认为是可信的） ([Deserialization risks in use of BinaryFormatter and related types - .NET | Microsoft Learn](https://learn.microsoft.com/en-us/dotnet/standard/serialization/binaryformatter-security-guide#:~:text=The%20BinaryFormatter%20%20type%20is,and%20can%27t%20be%20made%20secure))。反序列化攻击已成为常见安全威胁，利用像 BinaryFormatter 这样的反序列化器，恶意输入可以触发任意代码执行、操纵程序流程或导致崩溃 ([Do not use BinaryFormatter as it is insecure and vulnerable
](https://docs.datadoghq.com/security/code_security/static_analysis/static_analysis_rules/csharp-security/avoid-binary-formatter/#:~:text=This%20rule%20prevents%20the%20usage,execution%2C%20or%20induce%20application%20crashes)) ([Deserialization risks in use of BinaryFormatter and related types - .NET | Microsoft Learn](https://learn.microsoft.com/en-us/dotnet/standard/serialization/binaryformatter-security-guide#:~:text=Deserialization%20vulnerabilities%20are%20a%20threat,including%20C%2FC%2B%2B%2C%20Java%2C%20and%20C))。简而言之，调用 `BinaryFormatter.Deserialize` 等同于执行了输入提供的可执行代码 ([Deserialization risks in use of BinaryFormatter and related types - .NET | Microsoft Learn](https://learn.microsoft.com/en-us/dotnet/standard/serialization/binaryformatter-security-guide#:~:text=context%20of%20the%20target%20process))。因此，我们在实现深拷贝时**必须避免**使用 BinaryFormatter 及其相关类型（如 `SoapFormatter`、`NetDataContractSerializer` 等） ([Deserialization risks in use of BinaryFormatter and related types - .NET | Microsoft Learn](https://learn.microsoft.com/en-us/dotnet/standard/serialization/binaryformatter-security-guide#:~:text=This%20article%20applies%20to%20the,following%20types)) ([Deserialization risks in use of BinaryFormatter and related types - .NET | Microsoft Learn](https://learn.microsoft.com/en-us/dotnet/standard/serialization/binaryformatter-security-guide#:~:text=Caution))。  

为了替代 BinaryFormatter，有多种更安全的方案可供选择，包括 JSON 序列化、XML 序列化、ProtoBuf、MessagePack 等 ([Do not use BinaryFormatter as it is insecure and vulnerable
](https://docs.datadoghq.com/security/code_security/static_analysis/static_analysis_rules/csharp-security/avoid-binary-formatter/#:~:text=This%20security%20risk%20makes%20it,net))。在接下来的小节中，我们将重点讨论四种满足安全要求且与 .NET Framework 4.6.2 兼容的深拷贝实现方式，并分析它们的安全性、性能、适用场景和许可证。

## 基于 JSON（Newtonsoft.Json）的深拷贝

使用 JSON 序列化和反序列化进行深拷贝是一种简单直接的方法。通过将对象序列化为 JSON 字符串，然后再反序列化回对象，可以得到一个全新的对象副本。常用的 Newtonsoft.Json（又称Json.NET）库提供了方便的接口。**Newtonsoft.Json 拥有 MIT 开源许可证** ([Ionic Newton Jsoft license - PlayFab | Microsoft Learn](https://learn.microsoft.com/en-us/gaming/playfab/sdks/unity3d/licenses/newtonsoft-json-license#:~:text=https%3A%2F%2Fwww))（许可证友好），并且在 .NET Framework 4.6.2 上兼容良好。

### 实现示例

利用 Newtonsoft.Json 实现深拷贝的代码非常简洁。例如，可以编写一个扩展方法：

```csharp
using Newtonsoft.Json;

public static class ObjectExtensions 
{
    public static T DeepClone<T>(this T source)
    {
        if (source == null) return default(T);
        string json = JsonConvert.SerializeObject(source);
        // 反序列化回对象副本
        return (T)JsonConvert.DeserializeObject(json, source.GetType());
    }
}
```

调用方式：`MyObject clone = originalObject.DeepClone();`。上述实现思想与以下示例等价 ([c# - Deep cloning objects - Stack Overflow](https://stackoverflow.com/questions/78536/deep-cloning-objects/73580774#:~:text=using%20Newtonsoft))：

```csharp
MyType clone = (MyType)JsonConvert.DeserializeObject(
                   JsonConvert.SerializeObject(sourceObj), 
                   sourceObj.GetType());
``` 

Newtonsoft.Json 会将对象及其子对象全部序列化为文本，再根据 JSON 重建对象树，从而实现深拷贝。

### 安全性分析

与 BinaryFormatter 不同，JSON 序列化产生纯文本数据，不含可执行payload，因而**不存在反序列化导致远程代码执行**的已知风险 ([Do not use BinaryFormatter as it is insecure and vulnerable
](https://docs.datadoghq.com/security/code_security/static_analysis/static_analysis_rules/csharp-security/avoid-binary-formatter/#:~:text=This%20rule%20prevents%20the%20usage,execution%2C%20or%20induce%20application%20crashes))。Microsoft 也将基于 JSON 的序列化列为安全替代方案之一 ([Do not use BinaryFormatter as it is insecure and vulnerable
](https://docs.datadoghq.com/security/code_security/static_analysis/static_analysis_rules/csharp-security/avoid-binary-formatter/#:~:text=This%20security%20risk%20makes%20it,net))。使用 Newtonsoft.Json 时，只要不启用不安全的类型信息反序列化功能（如不使用 TypeNameHandling 去反序列化多态类型），通常是安全的。默认情况下，上述深拷贝实现并不会在 JSON 中包含类型名，因此不会有通过植入恶意类型来攻击的可能。

需要注意的是，使用 JSON 深拷贝**仍需确保对象的数据是可信的**，因为反序列化过程会根据 JSON 数据设置对象属性。如果对象中有某些属性的 get/set 有副作用，反序列化时可能触发这些副作用。不过这种风险属于业务逻辑范畴，而非外部攻击。总的来说，基于 JSON 的克隆在安全性方面是可接受的，前提是序列化和反序列化发生在受信任的环境中（例如在内存中克隆内部对象）。

### 性能与限制

JSON 序列化的主要缺点是**性能相对较慢**。序列化和反序列化过程涉及大量字符串处理和反射，开销不容忽视 ([GitHub - marcelltoth/ObjectCloner: Insanely fast and capable Deep Clone implementation for .NET based on Expression Trees](https://github.com/marcelltoth/ObjectCloner#:~:text=Custom%20Code%2088,89))。有基准测试显示，对同一个对象进行深拷贝，不同方法耗时对比如下 ([GitHub - marcelltoth/ObjectCloner: Insanely fast and capable Deep Clone implementation for .NET based on Expression Trees](https://github.com/marcelltoth/ObjectCloner#:~:text=In%20a%20benchmark%20cloning%20a,except%20custom%20written%20cloning%20code))：

- 手工实现克隆代码：约 88 ns （基准）
- 表达式树优化的克隆库：~520 ns（约为手工的5.9倍）
- **Newtonsoft.Json：~9315 ns**（约是手工的105倍，比表达式树慢约18倍） ([GitHub - marcelltoth/ObjectCloner: Insanely fast and capable Deep Clone implementation for .NET based on Expression Trees](https://github.com/marcelltoth/ObjectCloner#:~:text=Custom%20Code%2088,89))
- BinaryFormatter：~22744 ns（Json的约2.4倍，已废弃不用）

可见，JSON 方法在性能上明显落后于直接内存拷贝方案。如果深拷贝操作在应用中非常频繁或对象规模很大，那么JSON方法可能成为瓶颈。

除了速度，JSON 克隆还存在以下限制：

- **类型要求**：待克隆的对象及其成员类型需要是可序列化为JSON的。例如，JSON.NET能够处理大多数公开的属性和字段，但对于某些特殊类型（如委托、某些接口等）会直接忽略或报错。  
- **引用关系**：默认情况下，JSON 序列化会将对象引用按值复制。例如，如果对象 A 和 B 都引用了同一个子对象 X，序列化后会在 JSON 中把 X 重复两份，反序列化结果是得到两个独立的 X 实例。这意味着**无法保留对象图中的引用同一性**。虽然 Newtonsoft.Json 提供了 PreserveReferencesHandling 设置来保留引用（会在JSON中引入 `$id` 等元数据），但这主要用于防止循环引用导致的死循环，对于深拷贝一般无需启用。默认模式下，如果对象存在循环引用，Json.NET 会抛出异常以避免无限循环。可以通过设置 `ReferenceLoopHandling.Ignore` 来跳过，但跳过后某些引用将丢失。总的来说，使用 JSON 进行深拷贝适合树状的对象图，不共享子对象或无循环引用的场景。  
- **私有字段**：JSON 序列化默认只处理公开的属性（或被 `[JsonProperty]` 标记的成员）。对象的私有字段或未暴露的状态不会被克隆。如果类的关键数据存储在私有字段且没有对应的公开属性，那么 JSON 方法可能无法完整复制对象状态。

### 适用场景总结

Newtonsoft.Json 方法胜在**实现简单**、对对象几乎**零侵入**（无需修改类定义或实现特定接口），并且**安全性可靠**（无原生反序列化漏洞）。它适用于以下场景：

- 深拷贝操作不在性能敏感的热路径上（例如偶尔复制配置对象或缓存对象）。
- 对象结构相对简单，主要由基本类型和常规可序列化成员组成，且没有复杂的引用拓扑。
- 项目中已经使用了 Newtonsoft.Json（降低额外依赖的引入成本）。
- 希望避免引入额外第三方库时，可用Json.NET（多数 .NET 项目都会引用它）。

需要高性能或复杂对象图场景下，可能需要考虑下面讨论的其他方案。

## 基于 Protobuf-net 的深拷贝

**Protobuf-net** 是 .NET 平台上的 Protocol Buffers（二进制协议）序列化库，由 Marc Gravell 开发和维护。它以高效、小尺寸的二进制格式序列化对象，在网络传输和持久化方面经常被使用。同样地，这种序列化/反序列化过程也可以用于深拷贝对象。Protobuf-net **采用 Apache 2.0 许可证** ([
        NuGet Gallery
        | protobuf-net 3.2.30
    ](https://www.nuget.org/packages/protobuf-net/3.2.30#:~:text=%2A%20Apache,party%20website%2C%20not%20controlled%20by))，符合友好许可证要求，并且明确支持 .NET Framework 4.6.2 ([
        NuGet Gallery
        | protobuf-net 3.2.30
    ](https://www.nuget.org/packages/protobuf-net/3.2.30#:~:text=,with%20this%20framework%20or%20higher))。

### 实现方式

使用 protobuf-net 进行深拷贝通常有两种方式：

1. **使用静态方法 DeepClone**：Protobuf-net 提供了内置的深拷贝辅助方法。例如：
   ```csharp
   MyType clone = ProtoBuf.Serializer.DeepClone(originalObj);
   ```
   该方法会自动将对象序列化为二进制流并立即反序列化出一个新对象，相当于一次高效完成拷贝 ([protobuf-net/src/protobuf-net/Serializer.cs at main · protobuf-net/protobuf-net · GitHub](https://github.com/protobuf-net/protobuf-net/blob/main/src/protobuf-net/Serializer.cs#:~:text=public%20static%20object%20DeepClone))。需要注意，这要求类型 `MyType` 已被 Protobuf-net 支持（见下文要求）。
   
2. **手动序列化再反序列化**：等价地，可以先将对象序列化到 `MemoryStream`，再重置流指针进行反序列化。静态方法 DeepClone 实际上就是封装了这两个步骤，因此通常直接使用 `Serializer.DeepClone<T>` 最方便。

### 使用要求和限制

为使 Protobuf-net 正常序列化对象类型，需要满足一定的**契约要求**：

- **标记[ProtoContract]**：最好在类上加上 `[ProtoContract]` 特性，并对需要序列化的成员加上 `[ProtoMember(n)]` 特性编号。例如：
  ```csharp
  [ProtoContract]
  class Person {
      [ProtoMember(1)]
      public string Name { get; set; }
      [ProtoMember(2)]
      public int Age { get; set; }
      // ... 
  }
  ```
  Protobuf-net将按照标记的成员进行序列化和克隆。未标记的成员将被忽略，从而不会出现在副本中。

- **隐式契约**：某些情况下，Protobuf-net 也支持隐式序列化（例如通过 `[DataContract]`/`[DataMember]` 或启用 Implicit Fields 来自动包含公共字段等）。但为了明确控制，显式标记更可靠。未被包含在契约里的字段相当于不参与克隆。

- **支持类型**：Protobuf-net对**基本数据类型和常见集合**都有支持。但并非所有类型都能自动序列化。例如，**多维数组或嵌套集合**在旧版本 protobuf-net (v2) 中并不直接支持，需要封装为自定义类型。一些用户在使用 v3 时也遇到了 *“Nested or jagged lists not supported”* 的限制 ([DeepClone / Serializing a List<item> with protobuf-net V3](https://stackoverflow.com/questions/63703976/deepclone-serializing-a-listitem-with-protobuf-net-v3#:~:text=V3%20stackoverflow,and%20maps%20are%20not%20supported))。复杂的结构可能需要通过定义额外的 `[ProtoContract]` 类或自定义映射来处理。

- **多态类型**：Protocol Buffers本身并不自带类型信息。如果对象实际类型是继承自契约类型的子类，必须通过 `[ProtoInclude]` 特性明确列出子类编号，否则反序列化时子类的信息会丢失或导致错误。因此，对于**继承层次**的对象图，需要在基类上预先声明可能的子类，保证克隆时不会因未知类型而出问题。

- **引用关系**：标准的 Protocol Buffers 模型不维护对象引用的同一性，每次出现都会被当作独立的数据。这意味着如果一个对象图中同一个实例被引用多次，克隆结果会生成多个实例副本（类似JSON的行为）。Protobuf-net 提供了一些扩展选项（如 `[ProtoContract(SkipConstructor=true)]` 等）但并没有类似 BinaryFormatter 那样自动重建引用图的机制。因此，Protobuf-net 更适合**无复杂共享引用**的对象克隆。

综上，使用 Protobuf-net **需要对类型进行一定程度的预先准备**，通过特性标记或建立元数据模型。对于**POCO对象（简单的属性容器）**来说，这种准备工作是直接的；但对于引入第三方类型或复杂对象模型，若无法修改源码添加特性，则需要使用 `RuntimeTypeModel` 来配置序列化规则，这增加了实现难度。

### 安全性分析

Protobuf-net 的序列化过程同样**不存在类似 BinaryFormatter 的安全漏洞**。它将对象严格按照预定义的合同转换为紧凑的字节格式，反序列化时也严格按照合同和目标类型重建对象。因为不嵌入类型元数据，外部输入无法通过操纵数据来实例化任意类或执行任意代码，安全性很高 ([Do not use BinaryFormatter as it is insecure and vulnerable
](https://docs.datadoghq.com/security/code_security/static_analysis/static_analysis_rules/csharp-security/avoid-binary-formatter/#:~:text=susceptible%20to%20deserialization%20attacks%2C%20where,execution%2C%20or%20induce%20application%20crashes))。事实上，微软和安全社区将 Protocol Buffers（以及MessagePack等）视为安全的序列化方案 ([Do not use BinaryFormatter as it is insecure and vulnerable
](https://docs.datadoghq.com/security/code_security/static_analysis/static_analysis_rules/csharp-security/avoid-binary-formatter/#:~:text=This%20security%20risk%20makes%20it,net))。Protobuf-net 本身经过广泛使用和验证，没有已知RCE漏洞。

需要注意的反而是**业务逻辑层面的安全**：由于 Protobuf-net 会重建对象，如果对象内部存在一些在属性赋值/字段设置时执行的逻辑，那么克隆出的对象也会执行这些逻辑（类似于JSON情形）。但这不是库的漏洞，而是使用上的考虑。

总而言之，在同等受信任环境中，使用 Protobuf-net 进行深拷贝在安全性上是非常可靠的。

### 性能与适配性

性能是 Protobuf-net 的一大优势。它采用二进制协议，序列化与反序列化效率都很高，远胜于JSON文本格式。在常见场景下，Protobuf-net 的克隆速度可接近手工复制的性能：

- **高效的序列化**：Protobuf-net 对每个[ProtoMember]字段都会生成或使用高效的读写方法（通过反射Emit或预编译表达式树），序列化基本是顺序写入二进制流，无需解析文本格式。克隆时，这些优化同样适用。因此，对于复杂对象，Protobuf-net **比 JSON 快很多**，通常也优于一般的反射复制实现。在一些测试中，Protobuf-net 的性能表现与 MessagePack 等持平，远优于BinaryFormatter。

- **低开销**：序列化后的二进制数据通常远小于对应的JSON字符串，内存和CPU缓存的压力更小。深拷贝过程中临时分配的字节缓冲区也比文本字符串更小。

- **多线程和可伸缩性**：Protobuf-net 序列化器本质上是纯粹的算法实现，不依赖全局可变状态（除了类型模型配置）。静态的 `Serializer.DeepClone` 方法是线程安全的，可并发使用而不需要锁。对于批量克隆操作，Protobuf-net 可以很好地伸缩。

然而，Protobuf-net 的**适用性**在于你**是否需要为了深拷贝去为所有类型增加序列化标记**。如果项目本身就有使用 Protobuf-net（例如用于通信或存储），那么复用它来做对象克隆是很自然的选择。如果纯粹为了实现深拷贝而引入 Protobuf-net，权衡点在于：需要为每个要克隆的类型编写契约定义（特性或配置）。当类型很多或类型结构经常变化时，维护这些契约可能成为负担。此时，相比之下，下一节讨论的**通用反射/表达式方案**可能更合适，因为它不要求预先标注类型信息。

### 适用场景总结

考虑使用 Protobuf-net 进行深拷贝的场景包括：

- **对性能要求很高**：在循环中频繁克隆大对象时，Protobuf-net 的高效率能显著减少开销。
- **对象模型稳定且可标注**：如果对象的数据合同稳定，使用 [ProtoContract] 标注一次即可长久使用；或者对象本身已经用于协议通信，具有所需的标记。
- **需要二进制格式**：在一些情况下，深拷贝可能和序列化需求相结合，例如想要克隆并在进程间传输，这时用 Protobuf 格式可以一举两得（既完成克隆又得到紧凑的序列化结果）。
- **安全和许可证**：Protobuf-net 由社区维护，Apache 2.0 许可证允许自由商用和修改 ([protobuf-net/Licence.txt at main · protobuf-net/protobuf-net · GitHub](https://github.com/protobuf-net/protobuf-net/blob/main/Licence.txt#:~:text=Licensed%20under%20the%20Apache%20License%2C,License))。在满足上述技术条件时，它是符合安全和许可证要求的可靠选择。

反之，如果对象模型无法轻易适配 Protobuf-net（比如大量第三方类或无法修改源代码的类），或者深拷贝只是偶尔需要，项目中也不打算引入额外依赖，那么可以考虑其他方案。

## 基于表达式树或反射的深拷贝实现

不借助特定数据格式进行序列化，我们也可以通过**直接遍历对象图并复制**的方式来实现深拷贝。这类方案通常利用反射来获取对象的字段和属性，然后递归地创建副本。为提升性能，可以结合**表达式树**或IL生成技术，将重复的反射操作转换为高效的委托或动态方法，从而接近手写克隆代码的速度。这一类方法的好处是**通用性极强**：几乎可以处理任意对象，而无需预先对类进行标注或实现接口。许多第三方库（开源许可证友好）都采用了这种思路，比如 **Force.DeepCloner** (MIT 许可证) ([GitHub - force-net/DeepCloner: Fast object cloner for .NET](https://github.com/force-net/DeepCloner#:~:text=))、Baksteen.Extensions.DeepCopy (MIT) 等等。

### 实现原理

基本思想是：对于一个给定对象，创建它的一个新实例，然后**逐个将其所有字段/属性值拷贝**到新实例。对于值类型或不可变类型，直接赋值即可；对于引用类型，则需要递归克隆其子对象，再赋给副本的相应字段。为了防止循环引用导致无限递归，需要维护一个**引用映射表**（例如使用 `Dictionary<object, object>` 记录已经克隆过的对象），每当准备克隆一个新对象时先查表，看是否已经克隆过，是则直接重用已有副本。这确保了在克隆结果中，原本共享同一引用的多个对象依然共享同一引用，从而**维护原对象图的拓扑结构**。

纯反射实现每次深拷贝都要遍历类型的元数据，可能比较慢。于是可引入**缓存机制**：对于每种类型，第一次克隆时通过反射拿到所有可克隆成员列表，并动态构造一个执行复制的委托（例如使用表达式树编译或 `DynamicMethod` 生成IL）。后续再克隆相同类型对象时，直接调用缓存的委托即可，大大提升速度 ([c# - Deep cloning objects - Stack Overflow](https://stackoverflow.com/questions/78536/deep-cloning-objects/73580774#:~:text=,expression%20to%20call%20MemberwiseClone))。通过这些手段，深拷贝操作可以做到**不调用对象的构造函数**、不依赖任何特定特性，仅按照内存中对象布局复制，从而非常高效 ([GitHub - force-net/DeepCloner: Fast object cloner for .NET](https://github.com/force-net/DeepCloner#:~:text=objects,but%20object%20will%20be%20cloned))。

### 第三方库示例

- **Force.DeepCloner**：这是一个流行的快速深拷贝库，支持 .NET 4.x 和 .NET Standard (MIT 许可证) ([GitHub - force-net/DeepCloner: Fast object cloner for .NET](https://github.com/force-net/DeepCloner#:~:text=DeepCloner%20works%20for%20,slower%20than%20standard%2C%20see%20Benchmarks)) ([GitHub - force-net/DeepCloner: Fast object cloner for .NET](https://github.com/force-net/DeepCloner#:~:text=))。它内部使用**运行时代码生成**来实现极快的克隆 ([GitHub - force-net/DeepCloner: Fast object cloner for .NET](https://github.com/force-net/DeepCloner#:~:text=Library%20with%20extenstion%20to%20clone,but%20object%20will%20be%20cloned))。根据其文档描述，相比 BinaryFormatter 序列化方式，它的速度提升可达到数倍以上 ([c# - Deep cloning objects - Stack Overflow](https://stackoverflow.com/questions/78536/deep-cloning-objects/73580774#:~:text=%3E%20This%20is%20a%20speed,object%20reflection%20results%20are%20cached)) ([c# - Deep cloning objects - Stack Overflow](https://stackoverflow.com/questions/78536/deep-cloning-objects/73580774#:~:text=bugs%20which%20are%20present%20in,enum%20and))。使用方式也很简单，引入包后，对任何对象调用 `object.DeepClone()` 扩展方法即可获取副本。例如：
  ```csharp
  using Force.DeepCloner;
  MyObject clone = original.DeepClone();
  ```
  DeepCloner 能自动处理循环引用并保持引用同一性，也无需对象[Serializable]标记或实现ICloneable接口 ([GitHub - force-net/DeepCloner: Fast object cloner for .NET](https://github.com/force-net/DeepCloner#:~:text=called%20for%20cloning%20objects,but%20object%20will%20be%20cloned)) ([GitHub - force-net/DeepCloner: Fast object cloner for .NET](https://github.com/force-net/DeepCloner#:~:text=Also%2C%20there%20is%20no%20requirement,be%20cloned%20without%20any%20errors))。需要注意，它**默认会克隆对象的所有字段（包括私有字段）** ([GitHub - force-net/DeepCloner: Fast object cloner for .NET](https://github.com/force-net/DeepCloner#:~:text=objects,but%20object%20will%20be%20cloned))。这确保了完整复制，但如果对象包含一些**非托管资源句柄或与原环境紧密关联的字段**，克隆它们可能不合适（例如克隆一个包含文件句柄的对象可能导致两个对象指向同一文件句柄） ([GitHub - force-net/DeepCloner: Fast object cloner for .NET](https://github.com/force-net/DeepCloner#:~:text=objects,but%20object%20will%20be%20cloned))。DeepCloner 文档也提醒不建议克隆绑定了本地资源的对象，以避免不可预测的问题。

- **Baksteen.Extensions.DeepCopy**：这是另一个基于表达式树优化的深拷贝实现（MIT许可），由 Alexey Burtsev 的 net-object-deep-copy 项目演化而来 ([c# - Deep cloning objects - Stack Overflow](https://stackoverflow.com/questions/78536/deep-cloning-objects/73580774#:~:text=In%20the%20codebase%20I%20am,slow%20for%20larger%20object%20structures))。据报告，对大型对象图执行深拷贝，该库从原先耗时30分钟优化到了几乎瞬间完成 ([c# - Deep cloning objects - Stack Overflow](https://stackoverflow.com/questions/78536/deep-cloning-objects/73580774#:~:text=Instead%2C%20we%20found%20a%20fork,minutes%2C%20now%20feels%20almost%20instantaneous))。其主要优化手段也包括缓存反射结果、跳过不可变对象的拷贝以及编译Lambda调用 `MemberwiseClone` 等 ([c# - Deep cloning objects - Stack Overflow](https://stackoverflow.com/questions/78536/deep-cloning-objects/73580774#:~:text=,expression%20to%20call%20MemberwiseClone))。用法上提供了 `DeepCopy()` 扩展方法 ([c# - Deep cloning objects - Stack Overflow](https://stackoverflow.com/questions/78536/deep-cloning-objects/73580774#:~:text=,of%20the%20original%20object))。这种库的存在证明了通过精心设计，纯 C# 也能实现非常高效的深拷贝而不依赖不安全的反序列化。

- **自定义实现**：如果不使用第三方库，开发者也可以按照上述思路自行实现深拷贝工具。例如，通过 Type.GetFields/GetProperties 获取成员列表，使用 Activator.CreateInstance 或 FormatterServices.GetUninitializedObject 创建实例，然后递归赋值。在确保类型不复杂时，可以工作，但要完整处理所有情况（如泛型、数组、多态、循环引用、深浅拷贝选择等）会相当繁琐。因此通常推荐直接使用成熟的开源库，以避免踩坑。

### 安全性分析

这种直接克隆法**不涉及外部数据输入的解析**，因此从输入攻击的角度看是安全的。它不会生成可被篡改的中间表示，更不存在反序列化注入的风险，因为整个过程都在内存中操作受控的对象。需要注意的安全/风险点包括：

- **资源复制**：正如前述，如果对象持有一些独占的外部资源或单例对象引用，盲目地复制它们可能导致逻辑错误。例如，克隆一个包含数据库连接的对象，两份对象仍指向同一个连接实例，这可能并不期望。又比如，某对象内部引用了一个单例模式的全局实例，深拷贝会产生对这个单例的新引用，有可能违背单例模式意图 ([c# - How can I create a deep clone without using 'BinaryFormatter'? - Stack Overflow](https://stackoverflow.com/questions/65715894/how-can-i-create-a-deep-clone-without-using-binaryformatter#:~:text=As%20for%20your%20case%20,what%20your%20current%20method%20does))。因此，在使用通用克隆工具时，**需要有业务上的判断**：哪些对象适合克隆，哪些对象不应被克隆（可以通过在克隆过程中跳过特定字段来处理）。

- **私有/敏感数据**：克隆工具会复制对象的所有可达字段，包括私有字段和未经序列化标记的内容。这意味着如果一个类依赖某些隐藏的不变量或者安全敏感信息存于私有字段，克隆后的对象也会拥有同样的数据。这通常不是问题，但要意识到克隆不是过滤敏感信息的手段——它是按位复制，一旦源对象里有机密数据，副本里也会有，需要同样保护。

- **运行环境**：大部分反射/表达式树克隆库要求**完全信任权限**（Full Trust），因为需要反射访问私有成员和发射IL ([GitHub - force-net/DeepCloner: Fast object cloner for .NET](https://github.com/force-net/DeepCloner#:~:text=Limitation))。在 .NET Framework 4.6.2 的典型运行环境中（桌面应用、服务器应用）这不是问题。但如果在部分受限的沙盒中（比如早期Silverlight或某些插件环境）权限不足，库会降级为较慢的安全模式或无法运行 ([GitHub - force-net/DeepCloner: Fast object cloner for .NET](https://github.com/force-net/DeepCloner#:~:text=Limitation))。一般商业应用很少在部分信任环境执行，所以这点影响不大。

综上，表达式树/反射深拷贝方案本身**非常安全**，没有引入新的外部攻击面。只需在业务层面避免克隆那些“不该克隆”的对象类型即可。

### 性能分析

经过优化的深拷贝库性能非常出色。以 **Force.DeepCloner** 等为代表的实现，官方和社区提供的基准都显示其速度与手写克隆代码在同一个量级，远远快于序列化方案 ([GitHub - marcelltoth/ObjectCloner: Insanely fast and capable Deep Clone implementation for .NET based on Expression Trees](https://github.com/marcelltoth/ObjectCloner#:~:text=In%20a%20benchmark%20cloning%20a,except%20custom%20written%20cloning%20code))。前文提到的性能对比也证明了这一点：**表达式树方案比 Newtonsoft.Json 快一个数量级以上**，足以应对大部分性能要求苛刻的场景。在克隆包含大量数据的对象时，此类库通常只会消耗微秒级别的时间。

当然，不同库的性能略有差异，但一般都做了常见类型（如数组、集合）的特殊优化。例如，有的实现会针对 `List<T>`、数组等做批量内存复制优化，而不仅仅是逐元素克隆。另外，由于这些库都是**零拷贝**地直接在内存中复制，GC压力主要来自新对象的分配，没有像JSON那样的大字符串临时对象，所以内存开销相对也更低。

### 适用场景总结

表达式树/反射法的深拷贝非常通用，几乎适用于**任何需要深拷贝的场景**，特别是：

- **对象类型复杂多样**：当项目中需要克隆的对象类型很多且杂，难以为每个都编写序列化契约时，通用克隆库可以“一劳永逸”地支持所有类型（包括第三方类）。
- **要求完整克隆对象状态**：该方法能克隆私有字段和未公开的数据，适合要求副本和原对象在内部状态上完全一致的情况（例如克隆实体以进行离线修改，再对比变化）。
- **性能要求高**：经过优化的实现能够满足高并发、大数据量下的克隆需求。
- **项目依赖**：如果希望**尽量减少外部依赖**，其实一些深拷贝实现甚至可以直接作为源代码文件引入（例如某些Stack Overflow社区提供的 ObjectExtensions 方法 ([c# - Deep cloning objects - Stack Overflow](https://stackoverflow.com/questions/78536/deep-cloning-objects/73580774#:~:text=In%20the%20codebase%20I%20am,slow%20for%20larger%20object%20structures))）。这些实现通常也使用 MIT 等许可证授权，可以自由整合进项目。

相应地，要小心使用在涉及本地资源句柄或单例的对象上，必要时可在克隆前断开这些链接或在克隆后手工调整。整体而言，采用反射/表达式树方案是在 .NET Framework 上实现安全深拷贝的**最通用且高性能**的方法之一。

## 使用 AutoMapper 进行深拷贝

AutoMapper 是 .NET 中广为使用的对象-对象映射库，通常用于将一种业务模型转换为另一种（例如 DTO <-> 实体）。虽然 AutoMapper 并非专门为深拷贝设计，但它可以配置为将对象映射到**相同类型**，从而实现类似深拷贝的效果。AutoMapper **当前版本使用 MIT 许可证**开放源代码 ([AutoMapper/LICENSE.txt at master · AutoMapper/AutoMapper · GitHub](https://github.com/AutoMapper/AutoMapper/blob/master/LICENSE.txt#:~:text=The%20MIT%20License%20))；不过需要注意的是，AutoMapper 作者已宣布计划将其商业化，在未来版本中可能不再是纯开源免费模式 ([About the AutoMapper License Change · Issue #22582 · abpframework/abp · GitHub](https://github.com/abpframework/abp/issues/22582#:~:text=I%20think%20most%20of%20the,than%20an%20open%20source%20project))。在考虑长期使用时，应关注其许可证政策变化。

### 实现方式

使用 AutoMapper 进行深拷贝的典型步骤：

1. **创建映射配置**：告知AutoMapper如何从类型映射到自身。例如：
   ```csharp
   var config = new MapperConfiguration(cfg => {
       cfg.CreateMap<Foo, Foo>();
   });
   IMapper mapper = config.CreateMapper();
   ```
   上述配置定义了类型 `Foo` 到 `Foo` 的映射规则，实际上等同于深拷贝需要的操作（即把源 Foo 的每个成员赋值到目标 Foo）。

2. **执行映射克隆**：有了映射配置，就可以执行:
   ```csharp
   Foo source = ...;
   Foo clone = mapper.Map<Foo>(source);
   ```
   这会创建一个新的 `Foo` 对象，并将 `source` 的可映射成员复制过去。对于复杂对象，AutoMapper会递归映射其属性中的对象。例如，如果 Foo 有一个 Bar 属性（类型为 Bar），且也有 `CreateMap<Bar, Bar>` 配置，那么 mapper.Map 会进一步克隆 Bar 对象。同理，列表、数组等如果在配置中建立了元素映射，也会被逐一映射克隆。

值得一提的是，AutoMapper 也支持**映射到已有对象**的重载，比如 `mapper.Map(source, existingTarget)`。但在深拷贝语义下，我们通常是创建新对象，所以直接用上面的方式更简单。

**AutoMapper 深拷贝的行为**实际上是**浅拷贝属性+递归**：它按公开属性进行映射复制，默认情况下只映射公共可读可写属性。私有字段、只读属性不会被处理。这跟 JSON 方法有些类似，但 AutoMapper 可以通过配置自定义映射规则（ForMember等）覆盖默认行为。如果需要，它也可以映射字段但要额外配置。在一般用法下，我们认为AutoMapper克隆的对象和使用DTO类似——即**拷贝重要的数据字段**，但可能不会完全复制对象的内部隐藏状态。

### 安全性分析

AutoMapper 在克隆过程中不涉及外部输入，所有数据仍来自源对象本身，因此**不存在反序列化漏洞**。它只是调用源对象的getter和目标对象的setter来复制值，这跟普通的赋值操作无异。需要关注的安全点包括：

- **映射过程副作用**：AutoMapper会调用属性的get/set方法。如果这些方法内部有特殊逻辑（例如触发事件或验证），那么克隆时会执行这些逻辑。这可能在极少数情况下产生副作用。例如，某对象的属性setter会记录日志或维护全局状态，那么用AutoMapper克隆对象时，目标对象调用setter可能也执行了一次日志。这种情况并不常见，但应予以了解。不过，这不属于安全漏洞范畴，而是业务逻辑影响。

- **敏感数据**：和前面方案类似，AutoMapper克隆会复制对象中大部分重要数据。如果有属性存放敏感信息，副本中也会存在。不过AutoMapper不会平白引入风险——如果需要，可以有选择地不映射某些属性（通过配置忽略），这反而提供了一份灵活性（例如可以跳过密码字段的克隆）。

总的来说，AutoMapper 克隆**没有额外的安全风险**。只要源对象安全，结果也是安全的。此外，AutoMapper 作为成熟库，本身也没有已知安全漏洞。

### 性能分析

AutoMapper 的性能介于纯反射拷贝和高度优化的表达式树拷贝之间。事实上，AutoMapper 内部**也使用表达式树/IL来构建映射委托**，以减少每次映射的反射开销。因此对于单次对象拷贝来说，它比纯使用反射逐属性赋值快很多。

不过，与深度定制的深拷贝库相比，AutoMapper 做了更多抽象：它需要解析映射配置，支持各种转换和条件，这些灵活性在纯粹克隆场景下并不需要，但也带来一些性能开销。如果仅仅为了克隆，同样的数据，通过DeepCloner这样的库往往能更快。举例来说，对于一个包含几个属性的小对象，AutoMapper 克隆可能是微秒级，而 DeepCloner 则能达到数百纳秒级 ([GitHub - marcelltoth/ObjectCloner: Insanely fast and capable Deep Clone implementation for .NET based on Expression Trees](https://github.com/marcelltoth/ObjectCloner#:~:text=Method%20Mean%20Error%20StdDev%20Ratio,89))。

还有几点需要考虑：

- **初始化成本**：AutoMapper 在第一次创建映射时会有一个初始化生成过程。如果大量类型都要用AutoMapper克隆，初始化配置可能稍有负担。不过配置是可以重用的，一旦创建好，映射本身相当快。

- **内存使用**：AutoMapper 克隆不需要像JSON那样建立中间字符串，也不需要像Protobuf那样创建大块缓冲区，它只是针对每个对象分配一个新实例，外加很少量的临时引用。因此内存开销主要也是新对象本身，和其他方法处在同一量级。

- **异常处理**：AutoMapper 在映射不匹配时可能会抛出异常（例如目标没有无参构造函数无法实例化，或者映射缺少等）。使用之前要确保类型符合AutoMapper要求（通常需要有公共无参构造函数或已经提供目标实例）。

### 适用场景总结

使用 AutoMapper 来深拷贝对象可能适合如下情况：

- **项目已经广泛使用 AutoMapper**：这样可以不引入新库，直接复用。对于已经有映射配置的对象类型，只需稍加配置即可获得克隆能力。
- **需要部分拷贝/转换**：AutoMapper 擅长在复制时做转换。如果克隆过程中需要对数据做一些变换（例如ID复制时生成新ID，或过滤某些属性），AutoMapper 可以通过自定义映射逻辑方便地做到。这超出了普通深拷贝的范畴，但在某些业务场景下有用。
- **不要求克隆私有状态**：AutoMapper偏向于业务层的数据复制，如果我们关心的只是对象对外的状态（公开属性），而不在意内部私有字段，AutoMapper正好满足要求。
- **对象结构无循环引用**：AutoMapper 没有内置检测循环引用的机制。如果对象互相引用造成环，会导致映射无限递归，须谨慎（这点其实对前述大部分方法也成立，除了专门处理引用的DeepCloner等）。

需要考虑的是AutoMapper未来的**许可证变化**。截至本文时（2025年），AutoMapper 仍可免费使用，但作者计划将其商业化 ([About the AutoMapper License Change · Issue #22582 · abpframework/abp · GitHub](https://github.com/abpframework/abp/issues/22582#:~:text=I%20think%20most%20of%20the,than%20an%20open%20source%20project))。这意味着将来新版可能需要购买授权用于商业项目。如果企业或项目对这一点敏感，那么将 AutoMapper 作为深拷贝方案就需要谨慎权衡（也许可以锁定在某个MIT版本，但长期不是办法）。相反，Newtonsoft.Json、Protobuf-net、DeepCloner等都会一直是开源友好许可证，不会有这种后顾之忧。

## 性能与适用性比较

经过对以上几种方案的分析，我们可以从**安全性、性能、通用性**等方面对它们进行简要比较：

- **安全性**：所有替代方案（JSON、Protobuf-net、反射克隆、AutoMapper）都避免了 BinaryFormatter 的固有漏洞，在正常使用下都被认为是安全的。JSON 和 Protobuf-net 本质上只是数据格式转换，没有执行代码的能力；反射克隆和AutoMapper完全在内存操作现有对象，也没有接受外部未加工数据。这些方案的安全风险主要是业务逻辑上的（如是否克隆了不该克隆的东西），而非会被外部攻击利用。只要遵循基本用法，它们都能满足“安全深拷贝”的要求。

- **性能**：大致排序为：**表达式树/IL 克隆 > Protobuf-net > AutoMapper ≈ 手动反射 > JSON 序列化** > BinaryFormatter。表达式树优化的克隆库通常最快，接近原生赋值速度 ([GitHub - marcelltoth/ObjectCloner: Insanely fast and capable Deep Clone implementation for .NET based on Expression Trees](https://github.com/marcelltoth/ObjectCloner#:~:text=In%20a%20benchmark%20cloning%20a,except%20custom%20written%20cloning%20code))。Protobuf-net因为使用了高效二进制格式，也非常快，特别在对象很大的情况下优势明显。AutoMapper次之，它有一定开销但也利用了优化技术。JSON 方法较慢，不适合高频繁场景。性能方面的选择应根据具体需求：如果深拷贝只是偶尔用一次，两三倍的差异其实无关紧要；但在需要克隆成千上万次对象时，就应该倾向于高性能方案。

- **通用性**：反射克隆方案和 JSON 最大程度地通用于**任意类型**；Protobuf-net 和 AutoMapper 多少需要“已知类型”才能运作。具体来说，反射克隆不需要预先知道任何模型信息，而 Protobuf-net 需要契约配置才能处理某类型（动态也可但需编码）；AutoMapper需要为每种类型建立映射配置，否则默认不会映射。JSON 则只要对象的成员是可序列化的类型即可。  
  此外，反射克隆可以保持引用关系、克隆私有字段，这在需要完整忠实复制对象场景下非常有用。JSON 和 AutoMapper 都是偏向复制公开属性、按值拷贝，不保留引用同一性。Protobuf-net 默认也不保留引用关系（除非自行实现 ReferenceTrackedHandler 之类）。

- **易用性**：从零开始集成的难易度：Newtonsoft.Json 最简单，一两个方法搞定；AutoMapper 需要熟悉配置，但文档齐全且社区广泛，稍加学习也可用；Protobuf-net 则需要在模型上动手脚，初次工作量可能最大；反射克隆库需要引入依赖，但使用接口往往很简单（大多提供扩展方法直接调用）。如果团队成员对某个库已经很熟悉，那它的易用性就相对提升。在这一点上，Newtonsoft.Json 和 AutoMapper在社区中使用广，资料丰富，而深拷贝专用库相对小众，但它们通常API不复杂。

- **开源许可证**：这几种方案中，Newtonsoft.Json 是 MIT ([Ionic Newton Jsoft license - PlayFab | Microsoft Learn](https://learn.microsoft.com/en-us/gaming/playfab/sdks/unity3d/licenses/newtonsoft-json-license#:~:text=https%3A%2F%2Fwww))、Protobuf-net 是 Apache 2.0 ([
        NuGet Gallery
        | protobuf-net 3.2.30
    ](https://www.nuget.org/packages/protobuf-net/3.2.30#:~:text=%2A%20Apache,party%20website%2C%20not%20controlled%20by))、大部分反射深拷贝库如 Force.DeepCloner 等是 MIT ([GitHub - force-net/DeepCloner: Fast object cloner for .NET](https://github.com/force-net/DeepCloner#:~:text=))，都属于非常宽松的许可证，可以安心在商业项目中使用。AutoMapper 当前版本MIT ([AutoMapper/LICENSE.txt at master · AutoMapper/AutoMapper · GitHub](https://github.com/AutoMapper/AutoMapper/blob/master/LICENSE.txt#:~:text=The%20MIT%20License%20))但未来可能需要商业授权 ([About the AutoMapper License Change · Issue #22582 · abpframework/abp · GitHub](https://github.com/abpframework/abp/issues/22582#:~:text=I%20think%20most%20of%20the,than%20an%20open%20source%20project))。如果必须避免潜在的商业收费，那么应慎重考虑 AutoMapper 或准备在其转为收费后迁移到其他方案。

下表汇总了各方案的特点：

| 深拷贝方案              | 安全性                           | 性能           | 通用性/限制                           | 开源许可证              |
| ----------------------- | -------------------------------- | -------------- | ------------------------------------- | ----------------------- |
| **Newtonsoft.Json**     | ✅ 无反序列化漏洞  | 较慢 ([GitHub - marcelltoth/ObjectCloner: Insanely fast and capable Deep Clone implementation for .NET based on Expression Trees](https://github.com/marcelltoth/ObjectCloner#:~:text=Custom%20Code%2088,89))    | 通用任意可序列化对象<br>不保留引用，同一对象会多份拷贝 | MIT ([Ionic Newton Jsoft license - PlayFab | Microsoft Learn](https://learn.microsoft.com/en-us/gaming/playfab/sdks/unity3d/licenses/newtonsoft-json-license#:~:text=https%3A%2F%2Fwww))        |
| **Protobuf-net**        | ✅ 安全，高效二进制格式  | 快        | 需[ProtoContract]标记类型<br>不支持未标记的数据字段 | Apache 2.0    |
| **表达式树/反射库**     | ✅ 安全，纯内存操作               | 很快 ([GitHub - marcelltoth/ObjectCloner: Insanely fast and capable Deep Clone implementation for .NET based on Expression Trees](https://github.com/marcelltoth/ObjectCloner#:~:text=Custom%20Code%2088,89))   | 通用任意对象，支持私有字段<br>保留对象图拓扑结构 | MIT（多数库） ([GitHub - force-net/DeepCloner: Fast object cloner for .NET](https://github.com/force-net/DeepCloner#:~:text=)) |
| **AutoMapper**          | ✅ 安全，无外部输入               | 中等          | 需为类型配置映射<br>仅复制公共属性，可能不完整克隆 | MIT（未来可能商业） ([About the AutoMapper License Change · Issue #22582 · abpframework/abp · GitHub](https://github.com/abpframework/abp/issues/22582#:~:text=I%20think%20most%20of%20the,than%20an%20open%20source%20project)) |

*注：上述比较为一般情况，具体性能也取决于对象大小和复杂度。*

## 开源许可证与第三方库说明

在选择深拷贝实现方案时，许可证是一个不可忽视的因素。根据要求，我们优先考虑 MIT、Apache 2.0 等友好许可证的库，避免具有商业限制或不兼容开源协议的方案。下面对文中涉及的库和技术的授权许可做一个汇总说明：

- **Newtonsoft.Json (Json.NET)** – 采用 **MIT 许可证** ([Ionic Newton Jsoft license - PlayFab | Microsoft Learn](https://learn.microsoft.com/en-us/gaming/playfab/sdks/unity3d/licenses/newtonsoft-json-license#:~:text=https%3A%2F%2Fwww))。MIT是极为宽松的许可证，允许自由使用、修改和分发代码，适用于商业和非商业项目而无需付费或开源自己的代码。在深拷贝场景中使用 Newtonsoft.Json 没有许可证方面的后顾之忧。

- **protobuf-net** – 采用 **Apache License 2.0** ([protobuf-net/Licence.txt at main · protobuf-net/protobuf-net · GitHub](https://github.com/protobuf-net/protobuf-net/blob/main/Licence.txt#:~:text=Licensed%20under%20the%20Apache%20License%2C,License))。Apache 2.0 同样是商业友好的许可证，和MIT一样不会病毒式传染使用者的代码。它要求保留版权声明和许可证声明，但这对使用基本没有影响。选择 protobuf-net 完全可以满足项目对许可证的要求。

- **Force.DeepCloner 等深拷贝库** – 通常采用 **MIT 许可证**（例如 Force.DeepCloner 即为 MIT ([GitHub - force-net/DeepCloner: Fast object cloner for .NET](https://github.com/force-net/DeepCloner#:~:text=))）。这类小型实用库大多由个人或小团队维护，基本都会选MIT/Apache。使用这些库不会有协议冲突问题。在引入前也可查阅NuGet或GitHub上的 LICENSE 文件以确定，如 FastDeepCloner（MIT ([GitHub - AlenToma/FastDeepCloner: FastDeepCloner, This is a C# based .NET cross platform library that is used to deep clone objects, whether they are serializable or not. It intends to be much faster than the normal binary serialization method of deep cloning objects.](https://github.com/AlenToma/FastDeepCloner#:~:text=License))）、CloneExtensions（GitHub上注明MIT）等等，都很友好。

- **AutoMapper** – 截至目前最新版本仍为 **MIT 许可证** ([AutoMapper/LICENSE.txt at master · AutoMapper/AutoMapper · GitHub](https://github.com/AutoMapper/AutoMapper/blob/master/LICENSE.txt#:~:text=The%20MIT%20License%20))。然而，如前文所述，AutoMapper 作者在2025年宣布将转向商业授权模式 ([About the AutoMapper License Change · Issue #22582 · abpframework/abp · GitHub](https://github.com/abpframework/abp/issues/22582#:~:text=I%20think%20most%20of%20the,than%20an%20open%20source%20project))。这意味着将来的版本可能改为双许可证（例如保留免费版和付费版）或者完全闭源收费。目前具体细节未定 ([About the AutoMapper License Change · Issue #22582 · abpframework/abp · GitHub](https://github.com/abpframework/abp/issues/22582#:~:text=Details%20of%20AutoMapper%27s%20commercialization%20are,We%20are%20following%20the%20situation))。保守的做法是：如果决定使用AutoMapper来实现深拷贝，应当**锁定在MIT许可的版本**上（例如使用 12.x 或13.x 版本），并密切关注其项目公告，以防止在升级时无意中违反新许可证。如果组织政策严格不允许可能的商业组件，那么长远来看可能需要寻找AutoMapper的替代品（比如其它映射库或自有实现）。

总之，在许可证方面，Newtonsoft.Json、Protobuf-net 和各类专用深拷贝库都满足“友好许可证”的要求，可以在商业项目中免费使用和分发。而 AutoMapper 未来的变化需要注意，但在现有版本下也有MIT授权可用。只要在使用前确认所选库的许可证（通常在官网或NuGet页面会注明），即可避免法律风险。

## 总结与建议

综合以上分析，针对 .NET Framework 4.6.2 环境的安全深拷贝需求，我们有多种可行方案，每种都有优劣与适用场景。最后做几点总结和推荐：

- **优先确保安全**：首先应杜绝使用任何不安全的反序列化机制（BinaryFormatter 及其变种）来实现深拷贝 ([Deserialization risks in use of BinaryFormatter and related types - .NET | Microsoft Learn](https://learn.microsoft.com/en-us/dotnet/standard/serialization/binaryformatter-security-guide#:~:text=The%20BinaryFormatter%20%20type%20is,and%20can%27t%20be%20made%20secure))。取而代之，选择本文讨论的安全方案都可以有效避免常见的反序列化攻击风险。

- **根据对象特性选择方案**：如果对象结构简单、性能要求不高，使用 **Newtonsoft.Json** 是最省事的方案——几行代码即可完成深拷贝，安全可靠 ([Do not use BinaryFormatter as it is insecure and vulnerable
](https://docs.datadoghq.com/security/code_security/static_analysis/static_analysis_rules/csharp-security/avoid-binary-formatter/#:~:text=susceptible%20to%20deserialization%20attacks%2C%20where,execution%2C%20or%20induce%20application%20crashes))。但要注意它不会克隆私有数据，且性能相对较低，故不宜在大量、大对象场景下使用。

- **追求性能和完整性**：对于性能敏感或需要完整克隆对象图的情况，推荐使用**反射/表达式树深拷贝库**。例如 **Force.DeepCloner** 提供了经过实战检验的高性能克隆，MIT 开源且兼容 .NET 4.6.2 ([GitHub - force-net/DeepCloner: Fast object cloner for .NET](https://github.com/force-net/DeepCloner#:~:text=DeepCloner%20works%20for%20,slower%20than%20standard%2C%20see%20Benchmarks))。它能应对复杂的对象引用关系并保持数据完整性，在安全性上也无需担心反序列化漏洞，非常适合通用性的深拷贝需求。

- **结合序列化需求**：若深拷贝操作正好伴随跨进程传输或存储需求，那么 **protobuf-net** 是很有吸引力的方案。通过一次序列化/反序列化，既完成了对象克隆，又获得了高效的二进制表示，可谓一举两得。Protobuf-net 对 .NET 4.6.2 提供了良好支持 ([
        NuGet Gallery
        | protobuf-net 3.2.30
    ](https://www.nuget.org/packages/protobuf-net/3.2.30#:~:text=,with%20this%20framework%20or%20higher))，前提是你愿意为类型加上必要的 [ProtoContract] 标记。它在安全和性能上都表现优秀，是企业级项目常用的组件之一。

- **利用现有工具**：如果项目中已经大量使用 **AutoMapper** 做对象映射，而且深拷贝需求只是对已有类型的数据复制，那么继续用AutoMapper会很方便。配置 `CreateMap<T, T>()` 后即可获得深拷贝能力，不需再引入新库。只是要提醒团队注意AutoMapper今后的许可证变化，并准备好在必要时切换方案。

- **考虑维护成本**：深拷贝是一种基础能力，实现方式应当尽可能简单可靠，减少后续维护成本。如果团队对某方案不了解或不放心，可以先做小规模测试。例如对比 JSON 方法和某个深拷贝库的效果，衡量性能差异和使用难度，再做决定。不追求极致性能时，往往**稳定成熟**比微小的性能差异更重要。

综上所述，**推荐的安全深拷贝实现**是在确保安全的前提下，根据具体需求灵活选型：对于一般场景，可采用 **JSON 序列化克隆** 或 **AutoMapper**（MIT 版本）这种简便方法；对于高性能要求，采用 **Protobuf-net** 或 **DeepCloner** 等专用库。 ([GitHub - marcelltoth/ObjectCloner: Insanely fast and capable Deep Clone implementation for .NET based on Expression Trees](https://github.com/marcelltoth/ObjectCloner#:~:text=Custom%20Code%2088,89)) ([Do not use BinaryFormatter as it is insecure and vulnerable
](https://docs.datadoghq.com/security/code_security/static_analysis/static_analysis_rules/csharp-security/avoid-binary-formatter/#:~:text=This%20security%20risk%20makes%20it,net))在实际项目中，也可以组合使用多种方法：比如默认用DeepCloner，而对少数特殊对象用自定义方法处理。关键是所有方法都应遵循安全最佳实践并满足项目的兼容性和许可证要求。

最后，深拷贝机制本身不能解决所有问题，仍需开发者根据业务语义判断**哪些对象需要深拷贝，深拷贝后的对象如何使用**。合理地选择和应用上述方案，将能在 .NET Framework 4.6.2 平台上高效且安全地实现深拷贝功能。

**参考资料：**

- Microsoft .NET 文档：避免使用 BinaryFormatter（介绍了其安全风险） ([Deserialization risks in use of BinaryFormatter and related types - .NET | Microsoft Learn](https://learn.microsoft.com/en-us/dotnet/standard/serialization/binaryformatter-security-guide#:~:text=Caution)) ([Deserialization risks in use of BinaryFormatter and related types - .NET | Microsoft Learn](https://learn.microsoft.com/en-us/dotnet/standard/serialization/binaryformatter-security-guide#:~:text=In%20,context%20of%20the%20target%20process))  
- Datadog 安全指南：禁止使用 BinaryFormatter 的原因和替代方案 ([Do not use BinaryFormatter as it is insecure and vulnerable
](https://docs.datadoghq.com/security/code_security/static_analysis/static_analysis_rules/csharp-security/avoid-binary-formatter/#:~:text=This%20rule%20prevents%20the%20usage,execution%2C%20or%20induce%20application%20crashes)) ([Do not use BinaryFormatter as it is insecure and vulnerable
](https://docs.datadoghq.com/security/code_security/static_analysis/static_analysis_rules/csharp-security/avoid-binary-formatter/#:~:text=This%20security%20risk%20makes%20it,net))  
- Newtonsoft.Json 官方许可声明（MIT License） ([Ionic Newton Jsoft license - PlayFab | Microsoft Learn](https://learn.microsoft.com/en-us/gaming/playfab/sdks/unity3d/licenses/newtonsoft-json-license#:~:text=https%3A%2F%2Fwww))  
- protobuf-net 官方许可声明（Apache 2.0 License） ([protobuf-net/Licence.txt at main · protobuf-net/protobuf-net · GitHub](https://github.com/protobuf-net/protobuf-net/blob/main/Licence.txt#:~:text=Licensed%20under%20the%20Apache%20License%2C,License))  
- AutoMapper 项目关于许可证更改的公告 ([About the AutoMapper License Change · Issue #22582 · abpframework/abp · GitHub](https://github.com/abpframework/abp/issues/22582#:~:text=I%20think%20most%20of%20the,than%20an%20open%20source%20project))  
- 深拷贝性能对比基准 (ObjectCloner 项目) ([GitHub - marcelltoth/ObjectCloner: Insanely fast and capable Deep Clone implementation for .NET based on Expression Trees](https://github.com/marcelltoth/ObjectCloner#:~:text=In%20a%20benchmark%20cloning%20a,except%20custom%20written%20cloning%20code))

