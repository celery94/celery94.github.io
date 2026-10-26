---
pubDatetime: 2026-10-26T08:01:00+08:00
title: "先让它红一次：审 agent 生成的 .NET 测试"
description: "agent 生成的 .NET 测试名字漂亮、结构整齐、一步跑绿，可它未必抓得到回归。本文在 .NET 10 与 xUnit v3 上把弱测试和强测试各跑一遍红绿对照，并给出识别假测试的五类症状和一张评审清单。"
tags: ["Coding Agent", ".NET", "Testing", "xUnit"]
slug: "review-agent-generated-dotnet-tests"
ogImage: "../../assets/1113/01-cover.jpg"
source: "https://www.devleader.ca/2026/10/25/review-claudegenerated-net-tests-for-real-regression-coverage"
---

agent 交回七个新测试，`dotnet test` 一遍全绿，提交说明写着「给 Calculate 补了负输入的回归测试」。合并之前，你把产品代码里那条 `if (itemCount < 0) throw new ArgumentOutOfRangeException(...)` 注释掉，重跑。

七个测试还是全绿。

其中一条叫 `Calculate_NegativeItemCount_RejectsInput`，名字里每个词都对得上它声称的场景。它实际调的是 `Calculate(0)`。

这段测试来自 Nick Cosentino 在 Dev Leader 上的 [Review Claude-Generated .NET Tests for Real Regression Coverage](https://www.devleader.ca/2026/10/25/review-claudegenerated-net-tests-for-real-regression-coverage)。原文拿它当反面教材，并顺着它给出一串可执行的检查方法。本文按「编码 agent 生成的测试」来写，这些检查不依赖某一个 agent，Claude 是原文举的例子。

原文记录的是 .NET 10 上一个隔离的 xUnit v3 3.0.0 项目，三个用例：删掉负数守卫后两条负输入用例失败，恢复守卫后全部通过。我按同样的思路另建了一个项目，把那段弱测试和它的正写版本放在一起跑，结果在下面几节里给出。

**一个测试值不值得留，看的是把被测代码改坏之后它会不会变红。** 改坏仍然绿，说明它没有接上任何真实行为；绿只说明这一次运行没有触发失败。

## 名字描述的场景，arrange 没进去

原文给的弱测试长这样，只做了一点排版整理：

```csharp
[Fact]
public void Calculate_NegativeItemCount_RejectsInput()
{
    var estimator = new DeliveryEstimator();
    decimal? actual = estimator.Calculate(0);

    if (actual is null)
    {
        Assert.Null(actual);
    }
}
```

方法名说的是负输入会被拒绝，arrange 传的是 `0`，那是合法边界值。断言被 `if (actual is null)` 包着，结果非空的时候整段跳过，测试什么也没检查就收工。

读的顺序反过来更省力：先看断言，再问哪些值能到达它，最后才看 arrange。顺着方法名读，读到的是作者想测什么；倒着读，读到的才是它实际测了什么。

两个缺陷各自独立。arrange 没有触发方法名声称的场景；断言在意外结果下不会失败。把方法名改成 `Calculate_ZeroItemCount_ReturnsZero` 只解决了第一个；在 `if` 里面再加几条断言，第二个还在——走非空分支的时候，依然一句断言都执行不到。

条件断言本身不是罪。多结果场景需要分支，框架差异也需要分支。要问的是每个分支有没有建立契约，或者在不该出现的分支上显式失败。断言被它要验证的那个行为守住，是假信心最常见的来源。

测试条数也有同样的误导。它描述的是新增了多少代码，不描述覆盖了多少种独立的失败方式。十条都在断言「能构造出来」，不如一条选准边界的用例。

helper 也要读。断言藏在 helper 里，helper 提前 `return`、`catch` 掉异常、把空集合当成功，外层测试看着干净，证据已经在内层漏光了。下面红绿对照里有一条就是这种写法，两个代码版本下它都是绿的。

## 把失败条件摆到必经之路上

正写版本如下。输入就是负数，用 `[Theory]` 给两个；断言要求一个具体异常类型，再检查 `ParamName`；`0` 单独一条用例，期望 `0m`。

```csharp
public sealed class DeliveryEstimator
{
    public decimal Calculate(int itemCount)
    {
        if (itemCount < 0)
        {
            throw new ArgumentOutOfRangeException(nameof(itemCount));
        }

        return itemCount * 2m;
    }
}

public sealed class DeliveryEstimatorTests
{
    [Theory]
    [InlineData(-1)]
    [InlineData(-10)]
    public void Calculate_NegativeItemCount(int itemCount)
    {
        var estimator = new DeliveryEstimator();

        var exception = Assert.Throws<ArgumentOutOfRangeException>(
            () => estimator.Calculate(itemCount));

        Assert.Equal("itemCount", exception.ParamName);
    }

    [Fact]
    public void Calculate_ZeroItemCount_ReturnsZero()
    {
        var estimator = new DeliveryEstimator();

        var actual = estimator.Calculate(0);

        Assert.Equal(0m, actual);
    }
}
```

删掉守卫，`Assert.Throws` 找不到它要的异常，测试必红；把 `0` 也一起拒掉，最后一条必红。这套失败条件是摆出来的，不是碰运气碰出来的。

### 红绿对照

复现环境：Windows，.NET SDK 10.0.402，`xunit.v3` 3.2.2 加 `xunit.runner.visualstudio` 3.1.5、`Microsoft.NET.Test.Sdk` 18.11.0，`dotnet test` 走 VSTest 前端。弱测试、强测试和一条 helper 版本放在同一个项目里，共 5 个用例。

| 测试                                              | 含守卫（正确代码） | 删掉守卫（引入回归） |
| ------------------------------------------------- | ------------------ | -------------------- |
| 弱测试 `Calculate_NegativeItemCount_RejectsInput` | 通过               | 通过                 |
| helper 弱测试 `..._HelperSwallowsException`       | 通过               | 通过                 |
| 强测试 `Calculate_NegativeItemCount(-1)`          | 通过               | 失败                 |
| 强测试 `Calculate_NegativeItemCount(-10)`         | 通过               | 失败                 |
| 强测试 `Calculate_ZeroItemCount_ReturnsZero`      | 通过               | 通过                 |

弱测试在两个版本下都是绿的：`Calculate(0)` 返回非 null，`if` 整段跳过。helper 那条也是两版都绿，它把 `ArgumentOutOfRangeException` 吞成 `null`，再断言 `null`，守卫在不在都通过。两条测试的名字里都写着 NegativeItemCount，红绿却和代码对不对无关。

强测试在删掉守卫后失败，失败信息是 `Assert.Throws() Failure: No exception was thrown`，`Expected: typeof(System.ArgumentOutOfRangeException)`。三轮跑下来，统计行分别是：

```text
# 含守卫
Passed!  - Failed: 0, Passed: 5, Skipped: 0, Total: 5
# 删掉守卫
Failed!  - Failed: 2, Passed: 3, Skipped: 0, Total: 5
# 恢复守卫
Passed!  - Failed: 0, Passed: 5, Skipped: 0, Total: 5
```

断言的精确度也能顺手验一次。把 `throw new ArgumentOutOfRangeException(nameof(itemCount))` 改成 `"wrongName"`，两条 Theory 立刻变红：`Expected: "itemCount"`，`Actual: "wrongName"`；弱测试照样绿。断言写得具体，才守得住具体的契约。

`0` 边界那条在删守卫后仍然通过，也是对的：这次回归只影响负数分支，那条用例不为它负责。一条测试只应该为它声称的行为负责，剩下的交给别的用例——这是分工，不是漏测。

编译失败、缺包、数据库连不上都不是行为上的红。它们说明这个场景根本没跑到。有意义的那次红，是被测代码真的执行到出错的路径，测试也确实看到了错误结果。所以在真仓库里要固定两个状态：修复前红，修复后绿，两次输出都留在 PR 里。

## 先对齐版本和测试平台

原文记录的是 xUnit v3 3.0.0。写这篇时 NuGet 上的稳定版已经到了 4.0.2，而 4.x 把默认测试平台从 MTP v1 换成了 v2，包组合也跟着变：`xunit.v3` 一个包就把 MTP 运行器带上了，`Microsoft.NET.Test.Sdk` 和 `xunit.runner.visualstudio` 只在 VSTest 路线下才需要。

平台切换会在最不该出事的地方出事。核对时我用 4.0.2 建了个没有 `global.json` 的项目，按 VSTest target 跑，`dotnet test` 直接 MSBuild 失败，退出码 1：

```text
Testing with VSTest target is no longer supported by Microsoft.Testing.Platform on .NET 10 SDK and later.
```

两条路都能走通：在 `global.json` 里写 `{"test": {"runner": "Microsoft.Testing.Platform"}}` 上 MTP，或者换成 `xunit.v3.mtp-off` 留在 VSTest。我这次复现用的是 3.2.2 那套包组合，本来就跑在 VSTest 前端；要留在 VSTest 又用 4.x，就得装 `mtp-off`。

这件事和测试质量没关系，但会让你对「跑过了」的判断失真：测试根本没跑起来，你看到的是一行 MSBuild 错误，而 agent 的报告可能写着测试全部通过。

## 替身替掉的是哪一层

一个测试先让替身返回某个值，再断言这个替身返回了该值，它验证的是自己的 arrange。真正被测的类从头到尾没被观察。

先找出谁拥有行为。一个应用服务负责校验订单、经仓储写入，被测对象多半是这个服务，仓储是替身，有用的断言落在服务的结果和「在什么条件下写库」上。换到 SQL 仓储，替身就撑不起结论了：查询有没有翻译成正确的 SQL、可空列有没有映射、唯一约束有没有生效，这些要在带真实数据库的集成环境里看。

交互断言只在交互本身属于契约时才有意义。请求被拒绝时不能入队，这条可以断言 `Enqueue` 没被调用。只断言「依赖被调用过」，漏掉的是参数、重复调用、返回值和事务边界。

所以不要把「禁用 mock」当成结论。先问这个替身拿掉的是哪一部分行为；它拿掉的正好是测试声称覆盖的那部分，这条测试就该换个边界，或者换成真实协作者。

## 错误路径最容易写成顺坡下

方法名 `Save_WhenRepositoryFails_ReturnsError` 只有生产代码真的会遇到那次失败时才成立。配了一个没有用到的重载、参数匹配写错，测试一样绿，因为它根本没把代码推进错误分支。

异步代码多一层。测试要观察异步操作本身，不能只构造一个 `Task`；没有 `await` 的失败和断言过的失败不是一回事。接进去之前先看项目里既有的异步断言写法和测试包版本，别把 agent 顺手写的 helper 当成项目约定。

期望的失败形态也要对。公共契约承诺的是异常、错误结果对象、状态码，还是重试？这四种观察不一样。`Assert.Throws<Exception>` 可能因为 arrange 阶段自己就炸了而通过；只检查状态码的写法会漏掉错误载荷。

涉及取消、释放、队列和后台处理时，arrange 要推进到生命周期上的那个点。顺序、拒绝、故障、取消、排空、清理是各自独立的行为，一个通用的成功场景盖不住它们。

## 定向跑绿一次，别升格成整套通过

评审时用过滤器缩小范围很省时间：

```powershell
dotnet test .\tests\Shipping.Tests\Shipping.Tests.csproj --filter "FullyQualifiedName~Shipping.Tests.DeliveryEstimatorTests"
```

先确认仓库用的就是这套 runner 和过滤语法，再照抄。跑完别只扫一眼绿色的统计行，要看清发现了几条、跳过几条、目标框架和配置是什么。

这条查询本身有坑。`~` 是子串匹配，不是精确类名。我的复现项目命名空间和测试类同名，`FullyQualifiedName~DeliveryEstimatorTests` 把 5 条用例全选中了；想只跑那个类，得写成 `FullyQualifiedName~DeliveryEstimatorTests.DeliveryEstimatorTests`，才是 4 条。

过滤到 0 条时更麻烦。VSTest 前端只打印一行：

```text
No test matches the given testcase filter `FullyQualifiedName~NoSuchTests` ...
```

没有 `Passed!`，没有 `Failed!`，也没有测试条数统计，退出码是 0。CI 只看退出码的话，这次空选择就是一次静默成功。换成 MTP v2 前端后，同样的选择会以退出码 8 结束，才算明确失败。两种前端对同一件事的判断不一样，先确认自己站在哪一边，再决定要不要把「执行条数」写进校验。

另外不要顺手给示例加 `--no-build` 或 `--no-restore`。这两个参数引入的是「产物已经存在」的假设，在准备好的 runner 上可以用，但要写清怎么准备的、二进制对应哪个 revision。

定向跑和全量跑解决的是不同问题。定向跑确认刚改的契约，全量跑看别的模块有没有受影响；依赖基础设施的行为还要一次面对真实环境的集成检查。三者不能互相顶替。

## 环境差异，先当假设

同一套测试在 Windows、WSL 和 CI 上表现不同，机制有好几种：路径、行尾、区域设置、文件系统行为、凭据、时序。这些是候选解释，不是可以互换的结论。

一条只在某个环境里失败的测试，先记录 SDK 版本、测试平台、操作系统、源码 revision 和相关配置，再用最小失败场景比对，别先改产品代码。依赖当前区域性或真实时钟的测试，要把这层依赖显式暴露出来。

原文提到过一个 Windows 和 WSL 行为差异的怀疑，但它没有被证明成根因。把这层怀疑当结论搬进下一次评审，就是把「还没查清」说成「已知缺陷」。本地绿也一样，它只描述一个执行上下文。

## 让 agent 交证据，不交成功叙事

给 agent 的指令越有边界，交回来的测试越可审。写清契约，指出生产边界，要求报告把「跑过的检查」和「建议但没跑的检查」分开，把包改动和无关注的重构挡在这次任务之外。

只读审查可以收窄工具集，原文举的是 Claude Code 的非交互调用：`-p` 带提示词，`--allowedTools` 限制可用工具。不同客户端的参数不一样，照抄前查自己的文档。提示词里写「只读」不构成权限边界，真正限制它的是你授出的工具、沙箱和仓库权限。

交接时只要五样东西：行为契约、覆盖它的那条测试、修复前观察到的失败、修复后的结果、以及没跑成的检查。执行被禁止或者环境不可用，就直说。评审的人要核对的是这五条能不能对上，而不是那句「已完成」。

## 一张可以照着问的评审表

| 症状                     | 一句话追问                     | 你要的那条证据           |
| ------------------------ | ------------------------------ | ------------------------ |
| 断言包在条件分支里       | 意外结果会落到哪个分支         | 非预期分支必须显式失败   |
| arrange 和方法名对不上   | 传进去的值真的会走到那条路径吗 | 非法值一条、边界值一条   |
| 断言的对象是替身         | 被测的那个类到底在哪           | 至少一条观察真实类的结果 |
| 错误路径或异步路径没触发 | 那次失败从哪一行产生           | 修复前的失败输出         |
| 过滤器选中 0 条          | 它实际发现并执行了几条         | 测试统计和退出码         |

## 先改坏那一行

下次 agent 说测试通过，先别读它的总结。把你怀疑的那行逻辑改坏一次，跑一遍，看它是红是绿。红了，这条测试可以留；绿着，追问它到底在测什么——多数时候答案会停在 arrange 上。

这一步一分钟，挡得住大部分假测试。剩下两类它挡不住：覆盖多处的变异测试，和带真实基础设施的集成环境。这两样都值得上，但前提是你先确认手上这一条测试真的会红。

## 参考

- [原文：Review Claude-Generated .NET Tests for Real Regression Coverage](https://www.devleader.ca/2026/10/25/review-claudegenerated-net-tests-for-real-regression-coverage)
- [Run selected unit tests（dotnet test 过滤表达式语法）](https://learn.microsoft.com/en-us/dotnet/core/testing/selective-unit-tests)
- [Testing with 'dotnet test'（VSTest 与 MTP 两种模式）](https://learn.microsoft.com/en-us/dotnet/core/testing/unit-testing-with-dotnet-test)
- [xUnit v3 与 Microsoft.Testing.Platform（4.x 默认 MTP v2）](https://xunit.net/docs/getting-started/v3/microsoft-testing-platform)
- [Claude Code 权限规则（提示词不改变工具权限）](https://code.claude.com/docs/en/permissions)
- [Run Claude Code programmatically（`-p` 与 `--allowedTools`）](https://code.claude.com/docs/en/headless)
