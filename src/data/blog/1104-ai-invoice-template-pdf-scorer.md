---
pubDatetime: 2026-10-21T08:14:00+08:00
title: "AI 写发票模板：模型打平，评分器留下"
description: "两个模型各写 5 份发票 HTML，用 IronPDF 渲染后 9 项检查全部满分。真正差异只有 print-color-adjust：附评分器的 C# 写法与 CI 回归做法。"
tags: ["AI Coding", "HTML to PDF", "C#", ".NET", "Testing"]
slug: "ai-invoice-template-pdf-scorer"
ogImage: "../../assets/1104/01-cover.jpg"
source: "https://codewithmukesh.com/blog/claude-vs-chatgpt-html-to-pdf-csharp/"
---

让模型写一份 HTML 发票模板，它交回来的东西通常很好看：页眉居中、合计加粗、配色克制。第一页渲染出来也没有问题。然后你喂一个 46 行的真实订单，翻到第二页——表头没了，或者合计块被切成两半。

这类问题在 HTML 里看不出来，只有渲染成 PDF、真的翻页才会暴露。Mukesh Murugan 在 codewithmukesh 上做了一次对比：让 Claude Fable 5.1 和 GPT-6 Astra 用同一段提示词各写 5 份发票模板，全部用 IronPDF 2026.9.2 在 .NET 10 上渲染，再用一个 C# 小应用给每份 PDF 打分。结果是 **10 份模板全部 9/9**。

打平意味着这个对比在「选哪个模型」上几乎没有信息量。真正值得带走的，是另外三件事：怎么把需求写成契约、怎么用代码检查 PDF、以及怎么让这套检查长期待在仓库里。下面按这个顺序重述，并补上原文没有展开的 CSS 边界与 CI 落地方式。

## 实验设计

原文的测试日期是 2026 年 9 月 19 日，两个模型都在各自的桌面应用里运行，不是在 API 里跑：

| 项目 | 内容 |
| --- | --- |
| 模型 | Claude Fable 5.1、GPT-6 Astra |
| 每个模型 | 5 次全新会话，关闭记忆与自定义指令，默认思考等级 |
| 提示词 | 完全相同，未追加任何补充说明 |
| 渲染 | IronPDF 2026.9.2、.NET 10、`ChromePdfRenderer` |
| 评分 | 自写 C# 控制台程序，9 项检查 |
| 数据 | 同一份 46 行批发订单，外加压力测试输入 |

三点边界需要先说清：

1. **这是一篇 Iron Software 赞助的文章**，渲染器固定为 IronPDF，测试与结论由作者完成。模型对比的部分不受赞助影响，但「用 IronPDF 渲染」这个前提被固定住了。
2. **样本是单日快照**。两个模型的 API 型号分别是 `claude-fable-5-1` 和 `gpt-6-astra`，这类型号几个月就会换一批，结论不能外推到下一版。
3. **在应用里跑，不等于调 API**。桌面应用会加自己的系统提示词，同样的提示词走 API 可能得到略有不同的结果。

## 提示词里真正的关键

原文最有价值的不是分数，而是它把提示词的后半段写成了契约：指定 24 个占位符名字，并给出单行数据的结构。

```text
Use exactly these placeholders and no others:
{{Number}} {{IssuedOn}} {{DueOn}} {{PaymentTerms}}
{{SellerName}} {{SellerAddress1}} ... {{SellerTaxId}}
{{BuyerName}} {{BuyerAddress1}} ... {{BuyerTaxId}}
{{Subtotal}} {{TotalDiscount}} {{Tax}} {{TaxRatePercent}} {{Total}}

{{Lines}} goes inside the <tbody> and gets replaced with one <tr> per
line item, shaped like this:
<tr><td class="sku">..</td><td>..</td><td class="num">..</td>...</tr>
```

这件事的作用不在「让模型更听话」，而在**换模型时填充代码不会崩**。原文的作者上一篇文章让模型自己起占位符名字，每次重新生成都换一套，`InvoiceFiller` 就得跟着改。把名字和行结构写进提示词之后，模型输出的是你定义的接口，而不是它偏好的命名。

提示词里还有一处刻意的留白：全文只说了一句「for A4 print output」，没有提 `@page`、分页、表头重复。这是测试的一部分——看模型会不会自己想到打印规则。

结果是 10 次全都想到了。`@page` 带尺寸和页边距、`thead { display: table-header-group }`、`break-inside: avoid`、`tabular-nums` 全部 5/5 出现，连早已被 `break-inside` 取代的 `page-break-inside` 也一起写上了。MDN 明确把 `page-break-inside` 标为遗留别名，写两份不造成伤害，只是说明模型在照抄它训练数据里的旧写法。

## 唯一真实的差异：打印背景色

两轮常规测试打平，压力测试才拉开一点差距。差异只有一条 CSS：

| 打印规则 | Claude Fable 5.1 | GPT-6 Astra |
| --- | --- | --- |
| `@page` 尺寸与边距 | 5/5 | 5/5 |
| `thead` 重复 | 5/5 | 5/5 |
| `break-inside: avoid` | 5/5 | 5/5 |
| `print-color-adjust: exact` | 5/5 | 0/5 |

这条规则的作用是请求渲染引擎不要为了省墨去调整颜色和背景。MDN 对它的描述很谨慎：默认值 `economy` 允许浏览器按输出设备做调整；而「用户代理提供给用户的颜色和图像选项，优先级高于 `print-color-adjust` 的取值」，所以**没有任何保证**。原文把它称为「强提示」是准确的。

在服务端渲染时，对应的开关是 `RenderingOptions.PrintHtmlBackgrounds`，原文的测试默认关闭它，等价于在浏览器里取消勾选「背景图形」。关掉背景之后，Fable 那 5 份模板的灰色表头填充仍然保住了，Astra 的其中一份丢了填充。

原文用控制组量过这条规则的代价：把 `print-color-adjust: exact` 从一份已知正常的模板里删掉，测试报告页面 **26.6% 的像素**失去填充。这是原作者在自己那份模板上的测量值，不是通用常数。

实际建议就一句：**两边都做**——模板里写 `print-color-adjust: exact`，渲染器上把 `PrintHtmlBackgrounds` 打开。CSS 那份在别人从浏览器打印时也起作用。

## 「价格完全一样」的一个例外

原文说两个模型每百万 token 都是 10 美元输入、50 美元输出，这点我核对过官方定价页，确实是同价。但 OpenAI 的模型页上还有一行：输入超过 272K token 的请求，按 2 倍输入价和 1.5 倍输出价计费。

对写模板这种短提示词场景，这条差异用不上；原文说「成本可以排除在对比之外」，在它自己的实验条件下是成立的。这里提出来，只是提醒不要把「同价」当成无条件结论。

## 评分器：9 项检查

原文的评分器把检查拆成两类：5 项只看 HTML，4 项必须渲染成 PDF 才能判断。

| # | 检查 | 怎么判断 |
| --- | --- | --- |
| 1 | 自包含 | 没有 `<script>`、`<link>`、`@import`、远程 URL |
| 2 | 有 `@page` | 存在带边距的 `@page` 块 |
| 3 | 占位符 | 24 个名字齐全且没有多余项 |
| 4 | 表头不被改显示类型 | `thead` 上没有 `display: block/flex/grid` |
| 5 | 等宽数字 | 有 `font-variant-numeric: tabular-nums` |
| 6 | 能渲染 | IronPDF 不抛异常 |
| 7 | 表头重复 | 有明细行的每一页都能找到列名 |
| 8 | 合计同页 | 小计与总计落在同一页 |
| 9 | 行不被切开 | 没有明细行被分页切断 |

第 4 项值得单独说。原文上一篇文章里最难查的一个 bug，就是响应式表格 CSS 把 `thead` 改成 `display: block`，在手机上重排好看，到了 PDF 里表头不再被当作表头组，第二页就没了。模型训练数据里有大量这种写法，所以这是扫描的第一项。

第 7 到 9 项依赖文本回读。核心只有几行：

```csharp
public async Task<ScoreCard> ScoreAsync(string template, Invoice invoice)
{
    var html = InvoiceFiller.Fill(template, invoice);
    var renderer = new ChromePdfRenderer();
    renderer.RenderingOptions.PrintHtmlBackgrounds = false;

    var pdf = await renderer.RenderHtmlAsPdfAsync(html);
    var pages = Enumerable.Range(0, pdf.PageCount)
        .Select(i => Normalize(pdf.ExtractTextFromPage(i)))
        .ToArray();

    // pages[1] 上的 Contains 检查，就是「表头有没有到第二页」
    return new ScoreCard(pages);
}
```

`ExtractTextFromPage` 接收从 0 开始的页索引，返回该页纯文本。`Normalize` 做两件事：把连续空白压成一个空格，转小写。不做这一步，描述文本换行后就永远匹配不上。

几个实现细节比 API 本身更容易踩：

- **列名不要写死**。不同模板会写 "Unit price" 或 "Price"，所以评分器从每份模板自己的 `<thead>` 里读列名，再检查这些名字是否出现在后续页。
- **SKU 和描述要一起匹配**。原文最初分开查，结果每个 Astra 模板都在 BV-1011 这行报错。查下去发现行本身没问题：BV-1011 的描述「Vanilla Syrup 750ml」是 BV-1014「Sugar Free Vanilla Syrup 750ml」的后缀，而后者恰好落在下一页。
- **单页不给分**。整张发票挤进一页时，第 7 项返回 `n/a`，而不是记一个通过——一页的文档没有证明任何分页行为。

## 先验证评分器

原文有一句话值得抄进任何测试项目：**从来没有抓到过失败的评分器，说「全部通过」不可信。**

所以在评模型之前，它先拿四份已知结果的模板做对照：

| 控制组模板 | 预期 | 实际 |
| --- | --- | --- |
| 原文模板，不动 | 全过 | 9/9 |
| 加 `table.lines thead { display: block }` | 表头消失 | 7/9，第 2、3 页缺表头 |
| 删掉 `print-color-adjust: exact` | 关背景时丢填充 | 失败，26.6% 像素丢填充 |
| 删掉行上的 `break-inside: avoid` | 长行被切开 | 失败，行跨第 1、2 页 |

四份对照各自命中了它该命中的检查。这一步还暴露了两个评分器自身的 bug，其中一个正是上面说的 `.masthead` 被 `thead` 正则误匹配——正则要锚定，否则 `masthead` 里的 `thead` 会命中。

## 让检查留在仓库里

原文只把评分器当一次性工具。对真实项目来说，它更该是**模板的回归测试**：模板是提交进仓库的文件，改一次就该跑一次。

把 9 项检查改成 xUnit 测试并不复杂：

```csharp
public sealed class InvoiceTemplateTests
{
    [Theory]
    [InlineData("templates/invoice-v3.html")]
    public async Task Header_repeats_on_every_page_with_lines(string path)
    {
        var html = InvoiceFiller.Fill(File.ReadAllText(path), InvoiceStore.Sample46);
        var renderer = new ChromePdfRenderer();
        var pdf = await renderer.RenderHtmlAsPdfAsync(html);
        var pages = Enumerable.Range(0, pdf.PageCount)
            .Select(i => Normalize(pdf.ExtractTextFromPage(i)))
            .ToArray();

        var labels = HeaderLabels(html);
        for (var p = 1; p < pages.Length; p++)
        {
            foreach (var label in labels)
            {
                Assert.Contains(label, pages[p]);
            }
        }
    }
}
```

三个落地要点：

- **模板和期望一起版本化**。模板文件进仓库，检查项写成断言，PR 里改模板就会看到失败。
- **CI 需要真实 license key**。IronPDF 的沙箱 key 只在带调试器的开发环境生效，`dotnet run` 或 `dotnet test` 会抛 `LicensingException`。CI 要用试用或正式 key，放在密钥管理里。
- **版本要钉住**。原文测的是 IronPDF 2026.9.2，我写这篇时 NuGet 上已经是 2026.10.3。渲染器的默认值和文本抽取细节都会随版本变，评分器的结论必须和版本绑在一起看。

## 排错清单

原文列的几个坑，按遇到概率排序：

1. **`LicensingException`: sandbox key used outside a development environment**。沙箱 key 需要附加调试器，用 Visual Studio 或 Rider 按 F5，或者换试用 key。
2. **`thead` 检查对所有模板都失败**。正则匹配到了 `.masthead`，把匹配锚定到标签开头。
3. **第二页图片存成了 `page-1.png`**。`RasterizeToImageFiles` 按写入顺序从 1 开始编号，和页索引无关；只要了索引 1 的图，文件名就是 1。生成后立刻重命名。
4. **表头背景色没了**。打开 `PrintHtmlBackgrounds`，或者给模板加 `print-color-adjust: exact`，两者一起做。

## 收尾

这次对比的真实结论不是「哪个模型更强」，而是**模板质量的上限已经被提示词契约和验证手段决定了**，模型只是在打平之后提供一点风格差异。下次换模型、换渲染器，那套 9 项检查仍然有效。

如果你手上有 AI 写的 PDF 模板，下一步可以这么做：

1. 把占位符名单和行结构写进提示词，固定接口。
2. 用 46 行以上、能跨页的数据渲染一次，把每页文本读回来检查。
3. 先跑四份已知好坏的对照模板，确认评分器真的会失败。
4. 把检查改成 xUnit，模板进仓库，CI 里带上 license key 跑。

原文的完整源码、提示词和两份模型产出的模板都在 GitHub 上（`iammukeshm/claude-vs-chatgpt-html-to-pdf-csharp`），可以直接对照。

如果你也在 .NET 项目里处理 PDF 和 AI 生成的模板，欢迎关注 Aide Hub。我们会继续分享可验证的工程做法，而不是只给一个模型排名。

## 参考

- [Claude Fable 5.1 vs GPT-6 Astra: HTML to PDF in C# (.NET 10)（原文，Mukesh Murugan）](https://codewithmukesh.com/blog/claude-vs-chatgpt-html-to-pdf-csharp/)
- [原文配套源码（评分器、提示词与两份模型的模板）](https://github.com/iammukeshm/claude-vs-chatgpt-html-to-pdf-csharp)
- [MDN: print-color-adjust（默认 economy，用户设置优先）](https://developer.mozilla.org/en-US/docs/Web/CSS/print-color-adjust)
- [MDN: page-break-inside（遗留别名，已被 break-inside 取代）](https://developer.mozilla.org/en-US/docs/Web/CSS/page-break-inside)
- [IronPDF: HTML to PDF 教程（PrintHtmlBackgrounds 等渲染选项）](https://ironpdf.com/tutorials/html-to-pdf/)
- [IronPDF: 提取文本与图片（ExtractTextFromPage）](https://ironpdf.com/how-to/extract-text-and-images/)
- [Claude 模型与定价（claude-fable-5-1，每百万 token $10/$50）](https://platform.claude.com/docs/en/about-claude/models/overview)
- [OpenAI: GPT-6 Astra 模型页（定价与长上下文计费）](https://developers.openai.com/api/docs/models/gpt-6-astra)
