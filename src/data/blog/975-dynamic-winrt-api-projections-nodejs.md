---
pubDatetime: 2026-07-28T10:08:45+08:00
title: "在 Node.js 中直接调用 Windows 原生 API：动态 WinRT 投影进入公开预览"
description: "微软发布 Node.js 动态 Windows Runtime API 投影公开预览版。一个 npm 包即可让 Electron 或 Node.js 应用直接从 JavaScript/TypeScript 调用 Windows 原生 API——包括设备端 AI、通知、文件选择器、传感器等，不再需要 C++/C# 桥接层。"
tags: ["windows", "nodejs", "javascript", "typescript", "electron", "winrt", "microsoft", "release"]
slug: "dynamic-winrt-api-projections-nodejs"
ogImage: "../../assets/975/01-cover.png"
source: "https://devblogs.microsoft.com/ifdef-windows/a-new-way-to-bring-native-windows-apis-to-javascript-introducing-dynamic-api-projections-for-node-js/"
---

用 Electron 和 Node.js 写 Windows 桌面应用很简单。但调用 Windows Runtime API 一直不简单：设备端 AI 等功能通常需要 C++ 或 C# 桥接层、手动翻译 WinRT 类型和异步行为、为每个暴露的 API 写 wrapper 代码。这意味着多一套语言和工具链来构建、测试和与 Electron 保持兼容。

2026 年 7 月，微软在公开预览中发布了 **Node.js 动态 Windows Runtime API（WinRT）投影**。它让 Electron 应用或普通 Node.js 进程直接从 JavaScript/TypeScript 调用 Windows Runtime API。只需要一个 npm 包，工具链会为选定的 Windows 功能生成 JavaScript wrapper 和 TypeScript 声明。不需要 app 专属的 native addon、`node-gyp` 或 C++ wrapper。

## 和其他语言投影有什么不同

Windows Runtime 已经有 C++/WinRT、C#/WinRT、windows-rs（Rust）和 PyWinRT 等静态语言投影。这次发布把同样的模型带到了 Node.js 运行时，但**生成 JavaScript 代码而非每个 API 的 native binding**。一个共享运行时负责实际调度调用，兼容的 API 只需重新对元数据运行生成工具即可加入。

三个核心差异：

- **生成 JavaScript wrapper，不是 per-class native addon**。代码生成工具读取 `.winmd` 元数据，产出 `.js` wrapper 和 `.d.ts` 类型声明
- **一个共享的预编译运行时**。`@microsoft/dynwinrt` 从 npm 安装，在运行时统一调度所有 API 调用，预编译了 x64 和 arm64 版本
- **重新生成，而非重新编译**。Windows API 元数据变化时，重新运行代码生成即可，不需要等手工 wrapper 或重新编译 native 模块

## 能调用哪些 API

生成器读取 Windows 元数据（`.winmd` 文件），而非依赖固定的 API 列表。目前支持的非 UI API 包括：

- **设备端 AI**：文本生成、摘要、重写、文转表、图片描述、文字识别、图片缩放、对象提取和移除，以及 Windows ML 模型和执行提供程序目录
- **应用和内容 API**：通知、文件和文件夹选择器、存储、图片解码、富剪贴板内容
- **系统和设备 API**：网络、传感器、全球化和加密

同一个元数据驱动的工作流可以投影其他兼容的 Windows Runtime API，包括自定义 WinRT 组件。

开源项目 [Electron on Windows Gallery](https://github.com/microsoft/electron-on-windows-gallery) 已经在 AI 场景中使用这些 JavaScript 投影，每个交互示例都附带了 JS 源码和文档。

## 三个 npm 包的协作

投影通过三个 npm 包交付。你只需要安装 `@microsoft/winappcli`，它会协调另外两个包并保持版本一致：

| 包 | 作用 |
|---|---|
| `@microsoft/winappcli` | 设置 manifest 和 SDK 元数据、运行投影生成、处理调试包标识 |
| `@microsoft/dynwinrt-codegen` | 读取 `.winmd` 元数据，产出 `.js` wrapper 和 `.d.ts` 声明 |
| `@microsoft/dynwinrt` | 共享的预编译 x64/arm64 运行时，app 运行时实际调度 Windows API 调用 |

三者协作把 Windows 元数据变成 JavaScript API，app 直接 import 调用。

## Electron 示例：通知和 Phi Silica AI

现有 Electron 项目两步接入：

```bash
npm install --save-dev @microsoft/winappcli
npx winapp init . --use-defaults --add-js-bindings
```

`winapp init` 会创建 manifest、设置 SDK、把 `@microsoft/dynwinrt` 和 `@microsoft/dynwinrt-codegen` 加到 `package.json`、在 `.winapp/bindings/` 下生成 JS wrapper 和 TS 声明，并写入 `winapp.jsBindings` 配置块用于添加命名空间或 `.winmd` 文件。

导入路径使用 `#winapp/bindings` 映射，不依赖源文件的具体位置。

### 示例一：原生 Windows 通知

Electron 内置的通知 API 只覆盖基础 toast。Windows App SDK 通知增加了进度条、操作按钮、输入框等场景：

```javascript
const {
  AppNotificationBuilder,
  AppNotificationManager,
  AppNotificationProgressBar,
} = require('#winapp/bindings');

const progress = AppNotificationProgressBar
  .create()
  .setTitle('Processing with Windows AI')
  .setStatus('Running locally')
  .setValue(0.65)
  .setValueStringOverride('65%');

const builder = AppNotificationBuilder
  .create()
  .addProgressBar(progress);

AppNotificationManager.show(builder.build());
```

### 示例二：Phi Silica 设备端 AI（Copilot+ PC）

```javascript
const { LanguageModel, TextSummarizer } = require('#winapp/bindings');

const model = await LanguageModel.create('phi-silica');
const summary = await TextSummarizer.create(model);
const result = await summary.summarize('长文本内容...');
console.log(result);
```

这两个示例都需要 package identity——开发期间用以下命令给 Electron 可执行文件一个临时标识：

```bash
npx winapp node add-electron-debug-identity
```

不需要 package identity 的 API 可以直接 `npm start`。

## 注册更多 API

要添加 Windows SDK 中支持的非 UI API、或引入自定义 WinRT 组件的元数据，在 `package.json` 的 `winapp.jsBindings` 配置块中声明命名空间或 `.winmd` 路径：

```json
{
  "winapp": {
    "jsBindings": {
      "namespaces": [
        "Windows.Devices.Sensors",
        "Windows.Globalization"
      ],
      "additionalWinmdFiles": [
        "./external/my-component.winmd"
      ]
    }
  }
}
```

修改配置后重新运行生成：

```bash
npx winapp generate-js-bindings
```

增量生成只更新变化的 namespace，不用等全部重跑。

## 普通 Node.js 也能用

这个投影不只针对 Electron。你可以用 `winapp init` 的 `--node` 标志初始化一个纯 Node.js 项目。生成出来的 JS wrapper 和运行时完全一样——区别只是 Node.js 不能使用需要窗口身份的 API。

## 内部原理

投影的底层机制分两层：

**生成层**（`dynwinrt-codegen`）读取 `.winmd` 元数据文件，解析 WinRT 类型系统——类、接口、委托、枚举、结构体，以及异步操作模式（`IAsyncOperation`、`IAsyncAction`）。对每个兼容类型生成一个 `.js` 文件和一个 `.d.ts` 文件。JS 文件使用 `@microsoft/dynwinrt` 运行时调度调用，TS 文件提供完整的类型信息。

**运行时层**（`dynwinrt`）从 npm 安装为预编译的 x64/arm64 二进制。它不依赖 `node-gyp` 或本地编译。当被生成的 JS wrapper 调用时，它处理：
- WinRT 对象激活（`RoActivateInstance`）
- 类型转换（JavaScript ↔ WinRT）
- 异步操作驱动（把 WinRT async 模式桥接到 JS Promise）
- 事件订阅和取消
- 内存和引用生命周期

因为是动态投影——类型信息在运行时从元数据读取——不需要像 C++/WinRT 或 C#/WinRT 那样为每个 API 做编译期代码生成。运行时直接从 `.winmd` 解析类型、找到正确的激活工厂并分发调用。

## 当前限制

公开预览版已知不支持的特性：
- XAML UI 和涉及 UI 线程的 API
- 委托/回调 — WinRT 事件（`add_Event`/`remove_Event`）已经支持，但自定义委托回调尚不支持
- 同步 API — 只支持 async 操作模式
- API 覆盖率取决于 WinRT 元数据中可表示的类型模式；如果某个 API 使用了不兼容的类型，生成器会跳过它并打印诊断

## 参考

- [A new way to bring native Windows APIs to JavaScript](https://devblogs.microsoft.com/ifdef-windows/a-new-way-to-bring-native-windows-apis-to-javascript-introducing-dynamic-api-projections-for-node-js/) — 原文
- [Electron on Windows Gallery](https://github.com/microsoft/electron-on-windows-gallery)
- [WinApp CLI 仓库](https://github.com/microsoft/winappCli)
- [JS 投影设置指南 (Electron)](https://github.com/microsoft/winappCli/blob/main/docs/guides/electron/setup.md)
- [@microsoft/winappcli (npm)](https://www.npmjs.com/package/@microsoft/winappcli)
- [@microsoft/dynwinrt (npm)](https://www.npmjs.com/package/@microsoft/dynwinrt)
