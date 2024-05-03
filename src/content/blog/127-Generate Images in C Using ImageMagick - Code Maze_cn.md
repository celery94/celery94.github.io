---
pubDatetime: 2024-05-03
tags: [C#, ImageMagick]
source: https://code-maze.com/csharp-generate-images-using-imagemagick/
author: Emmanuel Adom
title: 使用 ImageMagick 在 C# 中生成图片
description: 在本文中，我们将学习如何使用 ImageMagick 在 C# 中生成图片，提供图片创建和操作的示例。
---

# 使用 ImageMagick 在 C# 中生成图片 - Code Maze

> ## 摘要
>
> 在本文中，我们将学习如何使用 ImageMagick 在 C# 中生成图片，提供图片创建和操作的示例。
>
> 原文 [Generate Images in C# Using ImageMagick - Code Maze](https://code-maze.com/csharp-generate-images-using-imagemagick/)

---

在本文中，我们将学习如何使用 ImageMagick 在 C# 中生成图片。

要下载本文的源代码，您可以访问我们的 [GitHub 仓库](https://github.com/CodeMazeBlog/CodeMazeGuides/tree/main/csharp-images/GenerateImagesInCSharpUsingImageMagick)。

让我们开始吧。

## 什么是 ImageMagick?

ImageMagick 是一个免费的、开源的跨平台库，用于显示、创建、转换、修改和编辑光栅图像。它是广泛用于各种与图像相关的任务的热门选择，包括 web 开发、平面设计、科学研究、医疗成像和天文学。

我们将使用这个库来创建一个图片，并在图片中间绘制一个绿色圆圈。

首先，让我们在终端上导航到项目目录以将 ImageMagick NuGet 包导入我们的项目中：

```bash
dotnet add package Magick.NET-Q8-AnyCPU
```

这个版本的 `Magick.NET` 包的 Quantum Depth 为 8（`Q8`）。因此，它使用每个通道 8 位进行颜色表示。这意味着它对于每个通道（红色、绿色、蓝色）使用 256 级的颜色强度。`AnyCPU` 意味着这个包被编译为与 32 位和 64 位系统兼容。

我们使用 `Magick.NET-Q8-AnyCPU` NuGet 包是因为它在颜色精确度和内存使用之间提供了一个良好的平衡。这与其他 `Magick.NET` 包相比：`Magick.NET-Q16-AnyCPU` 和 `Magick.NET-Q16-HDRI-AnyCPU`。

## 创建一个空白图片

接下来，让我们在一个静态的 `ImageService` 类中定义静态方法来创建一张图片，绘制一个圆圈，并最终将图片保存到文件中。

首先，让我们定义一个方法来创建一个空白图片：

```csharp
public static MagickImage CreateBlankImage(int width, int height, MagickColor color)
{
    return new MagickImage(color, width, height);
}
```

在我们的 `CreateBlankImage()` 方法中，我们使用 ImageMagick 库中的 `MagickImage` 类，根据指定的 `width`、`height` 和 `color` 来创建一个空白图片。然后我们返回新创建的 `MagickImage` 对象。

## 在 ImageMagick 中绘制图片

在 ImageMagick 中，在图片上渲染一个形状是一个两步过程。首先，我们需要定义一个我们希望渲染到 `MagickImage` 上的 `Drawables` 对象。其次，使用 `MagickImage.Draw()` 我们在图片上渲染 `Drawables` 对象。

### 创建我们的 Drawables 对象

那么让我们首先定义一个方法来创建一个圆形 `Drawables`：

```csharp
public static Drawables CreateCircle(
    int centerX,
    int centerY,
    int radius,
    int strokeWidth,
    MagickColor strokeColor,
    MagickColor fillColor)
{
    if (centerX <= 0 || centerY <= 0 || radius <= 0 || strokeWidth <= 0)
    {
        throw new ArgumentException(
            "圆心的值、半径和描边宽度必须大于零。"
        );
    }
    var drawables = new Drawables();
    drawables.StrokeColor(strokeColor);
    drawables.FillColor(fillColor);
    drawables.StrokeWidth(strokeWidth);
    drawables.Circle(centerX, centerY, centerX, centerY - radius);
    return drawables;
}
```

`CreateCircle()` 方法接受六个参数：

- 圆心的 X 和 Y 坐标：`centerX` 和 `centerY`
- 圆的半径：`radius`
- 圆轮廓的宽度：`strokeWidth`
- 圆轮廓的颜色：`strokeColor`
- 圆内部的颜色：`fillColor`

我们检查并抛出 `ArguementException` 如果 `int` 参数值小于或等于零。

接下来，使用 ImageMagick 中的 `Drawables` 类，我们创建一个 `drawables` 对象。然后我们使用相应的方法设置我们的 `drawables` 对象的描边颜色、填充颜色和描边宽度。最后，我们调用 `Circle()` 方法使用所提供的属性来创建一个圆。圆心设定在 `(centerX, centerY)`，圆延伸到 `(centerX, centerY - radius)`，定义其半径。

最终，我们返回 `drawables` 对象，它代表了我们希望渲染到 `MagickImage` 上的圆。

### 渲染我们的 Drawables 对象

现在我们有了一个代表我们希望渲染到图片上的圆的 `Drawables` 对象，让我们创建一个新的辅助方法来绘制圆：

```csharp
public static void DrawOnImage(MagickImage image, Drawables drawables)
{
    image.Draw(drawables);
}
```

我们的 `DrawOnImage()` 方法接收一个 `MagickImage` 和一个 `Drawables` 对象作为参数。

然后我们简单地调用 `image.Draw()` 方法，并将我们的 `drawables` 对象作为参数传递。`Draw()` 在图片上渲染提供的可绘制对象。

本质上，**我们通过将可绘制对象叠加到图片上来修改图片**。

## 在 ImageMagick 中保存图片

我们已经看到了如何创建和修改图片，但如果我们没有办法实际保存图片，那一切都是徒劳的：

```csharp
public static void SaveImage(MagickImage image, string outputPath)
{
    image.Write(outputPath, MagickFormat.Png);
}
```

这里我们定义了我们的 `SaveImage()` 方法。我们提供了一个要保存的 `MagickImage` 和定义我们保存图片目的地的 `outputPath`。

接下来，通过 `image.Write(outputPath, MagickFormat.png)`，我们将图片写入我们指定的输出路径，以我们希望的 `png` 格式。

## 整合一切

最后，让我们将我们之前创建的方法带入我们的 `Program` 类并进行测试：

```csharp
string outputPath = @"outputImage.png";
var image = ImageService.CreateBlankImage(480, 300, MagickColors.AliceBlue);
var strokeColor = MagickColors.YellowGreen;
var fillColor = MagickColors.Transparent;
var circle = ImageService.CreateCircle(image.Width / 2, image.Height / 2, 100, 5, strokeColor, fillColor);
ImageService.DrawOnImage(image, circle);
ImageService.SaveImage(image, outputPath);
Console.WriteLine("图片生成并成功保存。");
```

首先，我们定义了我们生成的图片 `outputImage.png` 将被保存的路径。

接下来，我们创建了一张宽度为 480 像素、高度为 300 像素的空白图片。我们使用 `MagickColors` 类中的预定义颜色之一 `MagickColors.AliceBlue` 来设置填充颜色。`MagickColors` 是 ImageMagick 库中提供预定义颜色对象的一个类。

当我们准备绘制我们的圆时，我们再次使用 `MagickColors` 类来定义我们的 `strokeColor` 为 `YellowGreen` 和我们的 `fillColor` 为 `Transparent`。

接下来，我们调用我们的 `CreateCircle()` [静态](https://code-maze.com/csharp-static-vs-non-static-methods/) 方法来生成一个圆。我们进行简单的计算，将圆放置在我们图片的中心，并设置 `radius` 为 100 像素。我们将 `strokeWidth` 设置为 5，最后传入我们之前定义的 `strokeColor` 和 `fillColor` 值。

**当我们创建了** `circle` **后，我们调用我们的** `DrawOnImage()` **方法来完成我们的图片生成和修改。**

最后，我们将我们修改过的图片保存到我们之前定义的 `outputPath`，控制台上打印一个肯定的消息：

图片生成并成功保存。

接下来，让我们看看我们的图片：

![使用 ImageMagick 库创建的图片](../../assets/127/outputImage.png)

## 结论

在本文中，我们探讨了如何使用 ImageMagick 库在 C# 中生成图片。
