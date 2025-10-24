---
pubDatetime: 2025-10-24
title: 使用 HTML 模板和 PuppeteerSharp 在 .NET 中生成 PDF 报表（完全免费方案）
description: 深入解析如何使用 Handlebars.NET 和 PuppeteerSharp 在 .NET 应用中生成专业的 PDF 报表。涵盖从零开始构建复杂发票系统、性能优化策略、模板设计最佳实践，以及企业级部署方案，为开发者提供完整的免费 PDF 生成解决方案
tags: [".NET", "C#", "PDF"]
slug: pdf-reporting-dotnet-html-templates-puppeteersharp
source: https://www.milanjovanovic.tech/blog/pdf-reporting-in-dotnet-with-html-templates-and-puppeteersharp
---

在 .NET 应用开发中，生成精美的 PDF 报表是一个几乎无法回避的需求。无论是客户发票、数据分析报告，还是企业内部文档，选择合适的 PDF 生成方案都直接影响到项目的成本、开发效率和长期维护性。市面上虽然存在多种商业 PDF 库，但它们往往需要昂贵的许可证费用。本文将介绍一种完全免费且强大的方案：**使用 HTML 模板结合 PuppeteerSharp 进行 PDF 生成**。

这种方案的核心优势在于：你可以使用熟悉的 Web 技术（HTML、CSS、JavaScript）来设计报表布局，通过模板引擎注入动态数据，最终由无头浏览器渲染为高质量的 PDF 文档。整个过程完全开源免费，不依赖任何商业库。

## 为什么选择 HTML + 无头浏览器方案

在深入技术细节之前，我们先理解为什么 **HTML 到 PDF 转换**是一个值得推荐的方案。

### 核心优势

#### 简单易用

如果你熟悉 HTML 和 CSS，就能快速上手。无需学习复杂的 PDF 生成 API，直接复用 Web 开发技能即可创建精美的报表布局。

#### 高度灵活

HTML/CSS 提供了无与伦比的布局能力。你可以使用 Flexbox、Grid、媒体查询等现代 CSS 特性，甚至可以通过 JavaScript 嵌入图表库（如 Chart.js）来生成动态可视化内容。

#### 易于预览和调试

在转换为 PDF 之前，你可以在任何浏览器中直接预览 HTML 模板。这大大简化了调试过程，所见即所得的开发体验使得布局调整变得轻松直观。

#### 完全控制样式

从字体、颜色、边距到页面分页符，CSS 提供了精细的控制能力。你可以为打印介质专门设计样式，确保 PDF 输出符合专业标准。

#### 完全免费

无需商业许可证，所有使用的库都是开源的。对于预算有限的项目或初创公司来说，这是一个重要的优势。

### 潜在劣势

客观地说，这种方案也存在一些权衡：

#### 依赖外部浏览器

PuppeteerSharp 需要下载 Chromium 浏览器二进制文件（约 150-200MB）。这增加了部署包的大小和初始化时间。

#### 性能开销

与原生 PDF 库相比，启动无头浏览器并渲染 HTML 会带来更高的 CPU 和内存开销。对于高并发场景，需要额外的性能优化策略。

#### 配置复杂度

相比直接使用 PDF 库，这种方案需要更多的初始配置，包括浏览器二进制文件管理、模板引擎设置等。

尽管存在这些劣势，但对于大多数应用场景——尤其是内部工具、中低频报表生成、以及需要复杂样式的文档——这种方案仍然是性价比最高的选择。

## 技术方案概览

我们将使用以下技术栈：

- **Handlebars.NET**：轻量级的模板引擎，用于将数据注入 HTML 模板
- **PuppeteerSharp**：Chromium 无头浏览器的 .NET 封装，负责将 HTML 渲染为 PDF

这两个库的组合提供了完整的端到端解决方案：Handlebars 处理模板逻辑，PuppeteerSharp 处理最终渲染。

## 项目初始化与依赖安装

首先，创建一个新的 .NET 项目并安装必要的 NuGet 包：

```bash
# 创建新的 Web API 项目
dotnet new webapi -n PdfReportingDemo
cd PdfReportingDemo

# 安装核心依赖
dotnet add package Handlebars.Net
dotnet add package PuppeteerSharp
```

**包说明：**

- `Handlebars.Net`：提供了 Handlebars 模板语法支持，允许在 HTML 中使用 `{{variable}}` 占位符
- `PuppeteerSharp`：管理 Chromium 浏览器的下载、启动和页面渲染

## 创建第一个 HTML 模板

让我们从一个简单的发票模板开始。在项目根目录下创建 `Templates` 文件夹，并添加 `InvoiceTemplate.html`：

```html
<!-- Templates/InvoiceTemplate.html -->
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>发票 #{{Number}}</title>
    <style>
        body {
            font-family: 'Microsoft YaHei', Arial, sans-serif;
            margin: 40px;
            color: #333;
            font-size: 14px;
        }
        h1 {
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }
        h2 {
            color: #34495e;
            margin-top: 30px;
            font-size: 18px;
        }
        .info-section {
            margin: 20px 0;
        }
        .info-section p {
            margin: 5px 0;
            line-height: 1.6;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }
        table th, table td {
            border: 1px solid #ddd;
            padding: 12px;
            text-align: left;
        }
        table th {
            background-color: #3498db;
            color: white;
            font-weight: bold;
        }
        table tr:nth-child(even) {
            background-color: #f9f9f9;
        }
        .total {
            text-align: right;
            font-size: 18px;
            font-weight: bold;
            color: #27ae60;
            margin-top: 20px;
        }
    </style>
</head>
<body>
    <h1>发票 #{{Number}}</h1>
    
    <div class="info-section">
        <p><strong>日期：</strong>{{formatDate IssuedDate}}</p>
    </div>

    <h2>发票方信息</h2>
    <div class="info-section">
        <p><strong>公司名称：</strong>{{SellerAddress.CompanyName}}</p>
        <p><strong>联系邮箱：</strong>{{SellerAddress.Email}}</p>
        <p><strong>地址：</strong>{{SellerAddress.Street}}, {{SellerAddress.City}}</p>
    </div>

    <h2>收票方信息</h2>
    <div class="info-section">
        <p><strong>公司名称：</strong>{{CustomerAddress.CompanyName}}</p>
        <p><strong>联系邮箱：</strong>{{CustomerAddress.Email}}</p>
        <p><strong>地址：</strong>{{CustomerAddress.Street}}, {{CustomerAddress.City}}</p>
    </div>

    <h2>项目明细</h2>
    <table>
        <thead>
            <tr>
                <th>序号</th>
                <th>项目名称</th>
                <th>单价（元）</th>
                <th>数量</th>
                <th>小计（元）</th>
            </tr>
        </thead>
        <tbody>
            {{#each LineItems}}
            <tr>
                <td>{{increment @index}}</td>
                <td>{{Name}}</td>
                <td>{{formatCurrency Price}}</td>
                <td>{{Quantity}}</td>
                <td>{{formatCurrency (multiply Price Quantity)}}</td>
            </tr>
            {{/each}}
        </tbody>
    </table>

    <div class="total">
        总计：{{formatCurrency Total}}
    </div>
</body>
</html>
```

**模板解析：**

- `{{Variable}}`：Handlebars 占位符，将被实际数据替换
- `{{#each LineItems}}`：循环渲染集合数据
- `{{formatDate IssuedDate}}`：自定义辅助函数，用于格式化日期
- `{{formatCurrency Price}}`：自定义辅助函数，用于格式化货币

## 注册 Handlebars 自定义辅助函数

为了实现日期格式化和货币格式化，我们需要注册自定义的 Handlebars 辅助函数。在项目中创建一个 `TemplateHelpers.cs` 文件：

```csharp
using HandlebarsDotNet;

namespace PdfReportingDemo.Services;

public static class TemplateHelpers
{
    /// <summary>
    /// 注册所有自定义的 Handlebars 辅助函数
    /// 应在应用启动时调用一次
    /// </summary>
    public static void RegisterHelpers()
    {
        // 日期格式化辅助函数
        Handlebars.RegisterHelper("formatDate", (context, arguments) =>
        {
            if (arguments.Length == 0 || arguments[0] == null)
                return string.Empty;

            if (arguments[0] is DateOnly date)
                return date.ToString("yyyy年MM月dd日");

            if (arguments[0] is DateTime dateTime)
                return dateTime.ToString("yyyy年MM月dd日");

            return arguments[0].ToString() ?? string.Empty;
        });

        // 货币格式化辅助函数
        Handlebars.RegisterHelper("formatCurrency", (context, arguments) =>
        {
            if (arguments.Length == 0 || arguments[0] == null)
                return "¥0.00";

            if (decimal.TryParse(arguments[0].ToString(), out var amount))
                return $"¥{amount:N2}";

            return arguments[0].ToString() ?? "¥0.00";
        });

        // 数字递增辅助函数（用于序号生成）
        Handlebars.RegisterHelper("increment", (context, arguments) =>
        {
            if (arguments.Length == 0 || arguments[0] == null)
                return 1;

            if (int.TryParse(arguments[0].ToString(), out var number))
                return number + 1;

            return 1;
        });

        // 乘法辅助函数（用于计算小计）
        Handlebars.RegisterHelper("multiply", (context, arguments) =>
        {
            if (arguments.Length < 2)
                return 0m;

            if (decimal.TryParse(arguments[0]?.ToString(), out var a) &&
                decimal.TryParse(arguments[1]?.ToString(), out var b))
            {
                return a * b;
            }

            return 0m;
        });
    }
}
```

在 `Program.cs` 中注册这些辅助函数：

```csharp
using PdfReportingDemo.Services;

var builder = WebApplication.CreateBuilder(args);

// 注册 Handlebars 辅助函数（应用启动时执行一次）
TemplateHelpers.RegisterHelpers();

// 其他服务注册...
builder.Services.AddControllers();
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();

var app = builder.Build();

// 中间件配置...
app.Run();
```

## 实现 PDF 生成服务

接下来，我们创建一个专门的 PDF 生成服务，封装模板渲染和 PDF 转换的逻辑。创建 `Services/PdfGenerationService.cs`：

```csharp
using HandlebarsDotNet;
using PuppeteerSharp;
using PuppeteerSharp.Media;

namespace PdfReportingDemo.Services;

public class PdfGenerationService
{
    private readonly ILogger<PdfGenerationService> _logger;
    private readonly string _templateBasePath;

    public PdfGenerationService(ILogger<PdfGenerationService> logger, IWebHostEnvironment environment)
    {
        _logger = logger;
        _templateBasePath = Path.Combine(environment.ContentRootPath, "Templates");
    }

    /// <summary>
    /// 根据模板和数据生成 PDF
    /// </summary>
    /// <typeparam name="T">数据模型类型</typeparam>
    /// <param name="templateFileName">模板文件名</param>
    /// <param name="data">要注入模板的数据</param>
    /// <param name="pdfOptions">可选的 PDF 生成选项</param>
    /// <returns>PDF 字节数组</returns>
    public async Task<byte[]> GeneratePdfAsync<T>(
        string templateFileName,
        T data,
        PdfOptions? pdfOptions = null)
    {
        try
        {
            // 1. 读取模板文件
            var templatePath = Path.Combine(_templateBasePath, templateFileName);
            if (!File.Exists(templatePath))
            {
                throw new FileNotFoundException($"模板文件未找到: {templatePath}");
            }

            var templateContent = await File.ReadAllTextAsync(templatePath);

            // 2. 编译模板并注入数据
            var compiledTemplate = Handlebars.Compile(templateContent);
            var html = compiledTemplate(data);

            // 3. 使用 PuppeteerSharp 将 HTML 转换为 PDF
            var pdf = await ConvertHtmlToPdfAsync(html, pdfOptions);

            _logger.LogInformation("PDF 生成成功，大小: {Size} KB", pdf.Length / 1024);
            return pdf;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "PDF 生成失败");
            throw;
        }
    }

    /// <summary>
    /// 将 HTML 字符串转换为 PDF
    /// </summary>
    private async Task<byte[]> ConvertHtmlToPdfAsync(string html, PdfOptions? pdfOptions = null)
    {
        // 使用默认的 PDF 选项
        pdfOptions ??= new PdfOptions
        {
            Format = PaperFormat.A4,
            PrintBackground = true,
            MarginOptions = new MarginOptions
            {
                Top = "20mm",
                Right = "15mm",
                Bottom = "20mm",
                Left = "15mm"
            }
        };

        // 启动无头浏览器
        await using var browser = await Puppeteer.LaunchAsync(new LaunchOptions
        {
            Headless = true,
            Args = new[] { "--no-sandbox", "--disable-setuid-sandbox" }
        });

        // 创建新页面
        await using var page = await browser.NewPageAsync();

        // 设置页面内容
        await page.SetContentAsync(html, new NavigationOptions
        {
            WaitUntil = new[] { WaitUntilNavigation.NetworkIdle0 }
        });

        // 等待字体加载完成（确保自定义字体正确渲染）
        await page.EvaluateExpressionHandleAsync("document.fonts.ready");

        // 生成 PDF
        var pdfBytes = await page.PdfDataAsync(pdfOptions);

        return pdfBytes;
    }
}
```

在 `Program.cs` 中注册服务：

```csharp
builder.Services.AddScoped<PdfGenerationService>();
```

## 创建数据模型

为了让代码更清晰，我们定义发票相关的数据模型。创建 `Models/Invoice.cs`：

```csharp
namespace PdfReportingDemo.Models;

public record Address(
    string CompanyName,
    string Email,
    string Street,
    string City,
    string State);

public record LineItem(
    string Name,
    decimal Price,
    int Quantity);

public record Invoice(
    string Number,
    DateOnly IssuedDate,
    DateOnly DueDate,
    Address SellerAddress,
    Address CustomerAddress,
    List<LineItem> LineItems,
    decimal Subtotal,
    decimal Total);
```

## 实现 API 端点

现在我们可以创建一个 Minimal API 端点来生成 PDF。在 `Program.cs` 中添加：

```csharp
using PdfReportingDemo.Models;
using PdfReportingDemo.Services;

// 在 app.Run() 之前添加端点

app.MapGet("/api/invoice/{invoiceNumber}/pdf", async (
    string invoiceNumber,
    PdfGenerationService pdfService) =>
{
    // 模拟从数据库获取发票数据
    var invoice = new Invoice(
        Number: invoiceNumber,
        IssuedDate: DateOnly.FromDateTime(DateTime.Now),
        DueDate: DateOnly.FromDateTime(DateTime.Now.AddDays(30)),
        SellerAddress: new Address(
            CompanyName: "北京科技有限公司",
            Email: "sales@company.com",
            Street: "中关村大街1号",
            City: "北京",
            State: "北京市"),
        CustomerAddress: new Address(
            CompanyName: "上海贸易有限公司",
            Email: "purchase@customer.com",
            Street: "南京路100号",
            City: "上海",
            State: "上海市"),
        LineItems: new List<LineItem>
        {
            new("软件开发服务", 50000.00m, 1),
            new("技术咨询服务（20小时）", 800.00m, 20),
            new("系统维护服务（12个月）", 2000.00m, 12)
        },
        Subtotal: 90000.00m,
        Total: 101700.00m
    );

    // 生成 PDF
    var pdfBytes = await pdfService.GeneratePdfAsync("InvoiceTemplate.html", invoice);

    // 返回 PDF 文件
    return Results.File(pdfBytes, "application/pdf", $"Invoice-{invoiceNumber}.pdf");
})
.WithName("GenerateInvoicePdf")
.WithOpenApi();
```

## 自动下载 Chromium 浏览器

PuppeteerSharp 需要 Chromium 浏览器二进制文件才能工作。我们可以在应用启动时自动下载。创建一个后台服务 `Services/BrowserSetupService.cs`：

```csharp
using PuppeteerSharp;

namespace PdfReportingDemo.Services;

public class BrowserSetupService : BackgroundService
{
    private readonly ILogger<BrowserSetupService> _logger;

    public BrowserSetupService(ILogger<BrowserSetupService> logger)
    {
        _logger = logger;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        try
        {
            _logger.LogInformation("开始下载 Chromium 浏览器...");

            var browserFetcher = new BrowserFetcher();
            await browserFetcher.DownloadAsync(BrowserFetcher.DefaultChromiumRevision);

            _logger.LogInformation("Chromium 浏览器下载完成");
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Chromium 浏览器下载失败");
        }
    }
}
```

在 `Program.cs` 中注册服务：

```csharp
builder.Services.AddHostedService<BrowserSetupService>();
```

## 高级功能：添加图片、页眉页脚

### 在模板中嵌入图片

对于需要在 PDF 中显示 Logo 或其他图片的场景，最简单的方法是使用 Base64 编码。修改数据模型以包含图片数据：

```csharp
public record Invoice(
    // ... 其他属性
    string? LogoBase64); // 可选的 Logo 图片（Base64 编码）
```

在模板中使用图片：

```html
<div class="header">
    {{#if LogoBase64}}
    <img src="data:image/png;base64,{{LogoBase64}}" 
         alt="公司 Logo" 
         style="height: 60px; max-width: 200px; object-fit: contain;" />
    {{/if}}
    <h1>发票 #{{Number}}</h1>
</div>
```

加载图片并转换为 Base64：

```csharp
public static string ImageToBase64(string imagePath)
{
    var imageBytes = File.ReadAllBytes(imagePath);
    return Convert.ToBase64String(imageBytes);
}

// 使用示例
var logoBase64 = ImageToBase64("Assets/logo.png");
var invoice = new Invoice(
    // ... 其他数据
    LogoBase64: logoBase64
);
```

### 添加动态页眉和页脚

PuppeteerSharp 支持在 PDF 生成时添加动态页眉和页脚。修改 PDF 选项：

```csharp
var pdfOptions = new PdfOptions
{
    Format = PaperFormat.A4,
    PrintBackground = true,
    DisplayHeaderFooter = true,
    HeaderTemplate = @"
        <div style='font-size: 10px; text-align: center; width: 100%; padding: 10px 0;'>
            <span style='margin-right: 20px;'><span class='title'></span></span>
            <span><span class='date'></span></span>
        </div>",
    FooterTemplate = @"
        <div style='font-size: 10px; text-align: center; width: 100%; padding: 10px 0;'>
            <span style='margin-right: 20px;'>生成日期：<span class='date'></span></span>
            <span>第 <span class='pageNumber'></span> 页，共 <span class='totalPages'></span> 页</span>
        </div>",
    MarginOptions = new MarginOptions
    {
        Top = "80px",    // 为页眉留出空间
        Bottom = "80px", // 为页脚留出空间
        Left = "20mm",
        Right = "20mm"
    }
};
```

**特殊 CSS 类说明：**

- `.title`：自动替换为文档标题（来自 `<title>` 标签）
- `.date`：自动替换为当前日期
- `.pageNumber`：当前页码
- `.totalPages`：总页数
- `.url`：当前页面 URL

### 完整的复杂模板示例

以下是一个包含图片、表格、样式和自定义布局的完整模板：

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>发票 #{{Number}}</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: 'Microsoft YaHei', Arial, sans-serif;
            color: #333;
            line-height: 1.6;
        }
        .invoice-container {
            padding: 20px;
            max-width: 800px;
            margin: 0 auto;
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 3px solid #3498db;
        }
        .invoice-title {
            font-size: 28px;
            color: #2c3e50;
            font-weight: bold;
        }
        .invoice-dates {
            text-align: right;
            color: #7f8c8d;
            font-size: 14px;
        }
        .invoice-dates p {
            margin: 5px 0;
        }
        .addresses {
            display: flex;
            justify-content: space-between;
            gap: 20px;
            margin: 30px 0;
        }
        .address-box {
            flex: 1;
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            border-left: 4px solid #3498db;
        }
        .address-title {
            color: #3498db;
            font-size: 16px;
            margin-bottom: 10px;
            font-weight: bold;
        }
        .company-name {
            font-size: 16px;
            font-weight: bold;
            color: #2c3e50;
            margin-bottom: 5px;
        }
        .email {
            color: #3498db;
        }
        .items-section {
            margin: 30px 0;
        }
        .items-title {
            color: #2c3e50;
            font-size: 20px;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid #3498db;
        }
        .items-table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }
        .items-table thead {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        .items-table th,
        .items-table td {
            padding: 12px;
            text-align: left;
            border: 1px solid #e1e4e8;
        }
        .items-table th {
            font-weight: bold;
            font-size: 14px;
        }
        .items-table tbody tr:nth-child(even) {
            background-color: #f8f9fa;
        }
        .items-table tbody tr:hover {
            background-color: #e9ecef;
        }
        .totals {
            margin-top: 30px;
            display: flex;
            justify-content: flex-end;
        }
        .totals-container {
            width: 300px;
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
        }
        .totals-row {
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid #dee2e6;
        }
        .totals-row.total {
            font-size: 18px;
            font-weight: bold;
            color: #27ae60;
            border-bottom: none;
            border-top: 2px solid #3498db;
            margin-top: 10px;
            padding-top: 15px;
        }
    </style>
</head>
<body>
    <div class="invoice-container">
        <!-- 页眉：Logo 和发票信息 -->
        <div class="header">
            <div>
                <h1 class="invoice-title">发票 #{{Number}}</h1>
                <div class="invoice-dates">
                    <p><strong>开票日期：</strong>{{formatDate IssuedDate}}</p>
                    <p><strong>到期日期：</strong>{{formatDate DueDate}}</p>
                </div>
            </div>
            <div>
                {{#if LogoBase64}}
                <img src="data:image/png;base64,{{LogoBase64}}" 
                     alt="公司 Logo" 
                     style="height: 60px; max-width: 200px; object-fit: contain;" />
                {{/if}}
            </div>
        </div>

        <!-- 地址信息 -->
        <div class="addresses">
            <!-- 发票方地址 -->
            <div class="address-box">
                <h3 class="address-title">发票方</h3>
                <div class="address-content">
                    <p class="company-name">{{SellerAddress.CompanyName}}</p>
                    <p>{{SellerAddress.Street}}</p>
                    <p>{{SellerAddress.City}}, {{SellerAddress.State}}</p>
                    <p class="email">{{SellerAddress.Email}}</p>
                </div>
            </div>

            <!-- 收票方地址 -->
            <div class="address-box">
                <h3 class="address-title">收票方</h3>
                <div class="address-content">
                    <p class="company-name">{{CustomerAddress.CompanyName}}</p>
                    <p>{{CustomerAddress.Street}}</p>
                    <p>{{CustomerAddress.City}}, {{CustomerAddress.State}}</p>
                    <p class="email">{{CustomerAddress.Email}}</p>
                </div>
            </div>
        </div>

        <!-- 项目明细表 -->
        <div class="items-section">
            <h2 class="items-title">项目明细</h2>
            <table class="items-table">
                <thead>
                    <tr>
                        <th>#</th>
                        <th>项目描述</th>
                        <th>单价</th>
                        <th>数量</th>
                        <th>小计</th>
                    </tr>
                </thead>
                <tbody>
                    {{#each LineItems}}
                    <tr>
                        <td>{{increment @index}}</td>
                        <td>{{Name}}</td>
                        <td>{{formatCurrency Price}}</td>
                        <td>{{Quantity}}</td>
                        <td>{{formatCurrency (multiply Price Quantity)}}</td>
                    </tr>
                    {{/each}}
                </tbody>
            </table>
        </div>

        <!-- 金额汇总 -->
        <div class="totals">
            <div class="totals-container">
                <div class="totals-row">
                    <span>小计：</span>
                    <span>{{formatCurrency Subtotal}}</span>
                </div>
                <div class="totals-row">
                    <span>税费：</span>
                    <span>{{formatCurrency 0}}</span>
                </div>
                <div class="totals-row total">
                    <span>总计：</span>
                    <span>{{formatCurrency Total}}</span>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
```

## 性能优化策略

### 1. 浏览器实例复用

频繁启动和关闭浏览器会带来显著的性能开销。可以使用浏览器连接池来复用实例：

```csharp
public class BrowserPool
{
    private readonly SemaphoreSlim _semaphore;
    private readonly List<IBrowser> _browsers = new();
    private readonly int _poolSize;

    public BrowserPool(int poolSize = 5)
    {
        _poolSize = poolSize;
        _semaphore = new SemaphoreSlim(poolSize, poolSize);
    }

    public async Task<IBrowser> GetBrowserAsync()
    {
        await _semaphore.WaitAsync();

        IBrowser? browser = null;
        lock (_browsers)
        {
            browser = _browsers.FirstOrDefault(b => b.IsConnected);
            if (browser != null)
            {
                _browsers.Remove(browser);
            }
        }

        if (browser == null || !browser.IsConnected)
        {
            browser = await Puppeteer.LaunchAsync(new LaunchOptions
            {
                Headless = true,
                Args = new[] { "--no-sandbox", "--disable-setuid-sandbox" }
            });
        }

        return browser;
    }

    public void ReturnBrowser(IBrowser browser)
    {
        if (browser.IsConnected)
        {
            lock (_browsers)
            {
                if (_browsers.Count < _poolSize)
                {
                    _browsers.Add(browser);
                }
                else
                {
                    _ = browser.CloseAsync(); // 异步关闭多余的浏览器
                }
            }
        }

        _semaphore.Release();
    }
}
```

### 2. 使用后台任务队列

对于高并发场景，将 PDF 生成任务放到后台队列处理：

```csharp
public class PdfGenerationQueueService : BackgroundService
{
    private readonly ILogger<PdfGenerationQueueService> _logger;
    private readonly Channel<PdfGenerationTask> _queue;

    public PdfGenerationQueueService(ILogger<PdfGenerationQueueService> logger)
    {
        _logger = logger;
        _queue = Channel.CreateUnbounded<PdfGenerationTask>();
    }

    public async Task QueuePdfGenerationAsync(PdfGenerationTask task)
    {
        await _queue.Writer.WriteAsync(task);
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        await foreach (var task in _queue.Reader.ReadAllAsync(stoppingToken))
        {
            try
            {
                // 生成 PDF 并保存
                await ProcessPdfGenerationAsync(task);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "PDF 生成任务失败");
            }
        }
    }

    private async Task ProcessPdfGenerationAsync(PdfGenerationTask task)
    {
        // 实际的 PDF 生成逻辑
        _logger.LogInformation("正在处理 PDF 生成任务: {TaskId}", task.Id);
        // ... PDF 生成代码
    }
}

public record PdfGenerationTask(string Id, string TemplateName, object Data);
```

### 3. 缓存编译后的模板

Handlebars 模板编译是一个相对耗时的操作，应该缓存编译结果：

```csharp
public class TemplateCache
{
    private readonly ConcurrentDictionary<string, HandlebarsTemplate<object, object>> _cache = new();
    private readonly string _templateBasePath;

    public TemplateCache(IWebHostEnvironment environment)
    {
        _templateBasePath = Path.Combine(environment.ContentRootPath, "Templates");
    }

    public async Task<HandlebarsTemplate<object, object>> GetCompiledTemplateAsync(string templateFileName)
    {
        return _cache.GetOrAdd(templateFileName, fileName =>
        {
            var templatePath = Path.Combine(_templateBasePath, fileName);
            var templateContent = File.ReadAllText(templatePath);
            return Handlebars.Compile(templateContent);
        });
    }
}
```

## 性能基准测试

根据实际测试，使用这种方案生成一个标准的发票 PDF 的性能表现如下：

| 场景 | 时间 | 说明 |
|------|------|------|
| 冷启动 | ~12 秒 | 包含下载 Chromium + 首次启动浏览器 |
| 热运行（单次） | ~580 毫秒 | 浏览器已启动，模板已缓存 |
| 模板编译 | ~13 毫秒 | Handlebars 模板编译时间 |
| HTML 渲染 | ~550 毫秒 | 浏览器渲染 HTML 并生成 PDF |
| 浏览器复用（并发） | ~350 毫秒/请求 | 使用浏览器连接池 |

**优化建议：**

1. **预热浏览器**：在应用启动时提前启动浏览器实例
2. **使用 Azure Functions/AWS Lambda**：将 PDF 生成隔离到独立的计算资源
3. **异步处理**：将 PDF 生成任务放到后台队列，立即返回任务 ID
4. **缓存策略**：对于重复的报表，可以缓存生成的 PDF

## 部署注意事项

### Docker 容器部署

在 Docker 容器中运行 PuppeteerSharp 需要安装额外的系统依赖。Dockerfile 示例：

```dockerfile
FROM mcr.microsoft.com/dotnet/aspnet:9.0 AS base
WORKDIR /app
EXPOSE 80

# 安装 Chromium 依赖
RUN apt-get update && apt-get install -y \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

FROM mcr.microsoft.com/dotnet/sdk:9.0 AS build
WORKDIR /src
COPY ["PdfReportingDemo.csproj", "./"]
RUN dotnet restore "PdfReportingDemo.csproj"
COPY . .
RUN dotnet build "PdfReportingDemo.csproj" -c Release -o /app/build

FROM build AS publish
RUN dotnet publish "PdfReportingDemo.csproj" -c Release -o /app/publish

FROM base AS final
WORKDIR /app
COPY --from=publish /app/publish .
ENTRYPOINT ["dotnet", "PdfReportingDemo.dll"]
```

### Azure App Service 部署

Azure App Service 需要启用 64 位工作进程，并确保有足够的内存：

```json
{
  "iisSettings": {
    "windowsAuthentication": false,
    "anonymousAuthentication": true,
    "iisExpress": {
      "applicationUrl": "http://localhost:5000",
      "sslPort": 0
    }
  },
  "profiles": {
    "PdfReportingDemo": {
      "commandName": "Project",
      "launchBrowser": true,
      "environmentVariables": {
        "ASPNETCORE_ENVIRONMENT": "Development",
        "PUPPETEER_DOWNLOAD_HOST": "https://storage.googleapis.com"
      },
      "applicationUrl": "http://localhost:5000"
    }
  }
}
```

## 最佳实践总结

### 开发阶段

1. **在浏览器中预览模板**：先在浏览器中调试 HTML/CSS，确保布局正确
2. **使用版本控制管理模板**：将 HTML 模板纳入版本控制，便于追踪变更
3. **模块化 CSS**：将通用样式提取为独立的 CSS 文件
4. **数据验证**：在模板渲染前验证数据完整性

### 生产环境

1. **异步处理**：将 PDF 生成放到后台队列或独立的微服务
2. **监控和日志**：记录 PDF 生成的性能指标和错误信息
3. **资源限制**：设置浏览器实例数量上限，防止资源耗尽
4. **错误处理**：实现重试机制和优雅降级策略
5. **安全考虑**：对用户输入进行清理，防止 XSS 注入

### 性能优化

1. **缓存编译后的模板**：避免重复编译
2. **复用浏览器实例**：使用连接池减少启动开销
3. **并发控制**：限制同时运行的 PDF 生成任务数量
4. **资源预加载**：提前下载 Chromium 和字体文件

## 与商业库对比

相比 IronPDF、QuestPDF 等商业库，这种方案的优劣势如下：

| 维度 | HTML + PuppeteerSharp | 商业 PDF 库 |
|------|----------------------|------------|
| **成本** | 完全免费 | 需要商业许可证（通常数千美元） |
| **布局灵活性** | 极高（完整的 CSS 支持） | 中等（依赖库的 API） |
| **学习曲线** | 低（使用熟悉的 Web 技术） | 中高（需要学习特定 API） |
| **性能** | 中等（浏览器开销） | 高（原生 PDF 生成） |
| **合规标准** | 有限（无 PDF/A 支持） | 完整（PDF/A、PDF/UA 等） |
| **维护成本** | 低（开源社区支持） | 中等（依赖供应商更新） |

## 总结

使用 HTML 模板和 PuppeteerSharp 生成 PDF 是一个**成本效益极高**的方案，特别适合以下场景：

- **预算有限的项目**：完全开源免费，无需购买商业许可证
- **复杂的布局需求**：利用 CSS 的强大能力实现精美的报表设计
- **快速迭代开发**：在浏览器中预览调试，所见即所得
- **内部工具和仪表板**：对性能要求不极致的中低频报表生成

虽然这种方案在性能和企业级特性（如 PDF/A 合规）方面不如商业库，但通过合理的架构设计（浏览器连接池、后台任务队列、缓存策略），完全可以满足大多数生产环境的需求。

对于追求像素级完美布局、需要快速迭代报表样式、以及希望降低软件许可证成本的团队来说，这无疑是一个值得深入探索的技术方案。结合现代 .NET 的异步编程模型和云原生架构，你可以构建出既高效又可扩展的 PDF 生成服务。

## 参考资源

- [PuppeteerSharp 官方文档](https://www.puppeteersharp.com/)
- [Handlebars.NET GitHub](https://github.com/Handlebars-Net/Handlebars.Net)
- [Chromium PDF 打印文档](https://www.chromium.org/developers/design-documents/print-pdf/)
- [CSS 打印样式指南](https://www.smashingmagazine.com/2018/05/print-stylesheets-in-2018/)
