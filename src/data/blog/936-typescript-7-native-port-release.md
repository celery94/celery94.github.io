---
pubDatetime: 2026-07-09T08:29:39+08:00
title: "TypeScript 7.0 发布：用 Go 重写的原生编译器，快 10 倍"
description: "TypeScript 7.0 是用 Go 重写的原生版本，完整构建普遍快 8-12 倍，内存更省。本文讲清它快在哪、怎么和 6.0 并存安装、有哪些破坏性默认变更，以及 Vue/Svelte 等嵌入式场景暂时还不能用的原因。"
tags: ["TypeScript", "前端工程", "编译器", "Go", "开发工具"]
slug: "typescript-7-native-port-release"
source: "https://devblogs.microsoft.com/typescript/announcing-typescript-7-0/"
ogImage: "../../assets/936/01-cover.png"
---

TypeScript 7.0 正式发布了，这是一个用 Go 重写的原生版本。官方给出的数字是：完整构建普遍快 8 到 12 倍。这不是又一个加几个类型特性的小版本，而是把整个工具链从 TypeScript 自举实现换成原生编译代码的一次大改造，团队为此投入了一年多。

如果你在大型代码库上被 `tsc` 或编辑器的卡顿折磨过，这个版本值得认真看一下。这篇讲清楚它到底快在哪、怎么装、和现有 6.0 怎么并存、有哪些会咬人的默认变更，以及哪些场景现在还不能用。

## 快是怎么来的

去年 TypeScript 团队公布过[原生移植计划](https://devblogs.microsoft.com/typescript/typescript-native-port/)：用 Go 重写一个能吃满现代硬件的原生编译器。移植做得尽量忠实——在保持原代码库结构和逻辑的前提下写新代码，好让两个编译器结果一致、行为兼容。区别在于新代码库带来了原生代码速度、共享内存多线程，以及一批新优化，在完整构建上通常能拿到 8-12 倍的提速。

安装方式和往常一样，通过 npm：

```
npm install -D typescript
```

这会给你工作区里新的 `tsc` 可执行文件（用 `npx tsc` 运行）。编辑器支持也一起跟上了，新基础建立在语言服务器协议（LSP）之上，VS Code、Visual Studio、WebStorm 等现代编辑器都能用。VS Code 有一个[专门的 TypeScript 7 扩展](https://marketplace.visualstudio.com/items?itemName=TypeScriptTeam.native-preview)现在就能装，Visual Studio 会根据工作区自动启用。

## 快了之后实际是什么体验

纸面上快听着好，落到日常是什么感觉？想想 TypeScript 在开发每个环节里出现的地方：打开编辑器、打开一个 TS 文件、跨项目跑一次 find-all-references；开始改代码时期待自动补全弹出、改错了实时看到红波浪线；准备构建时跑 `tsc` 看有没有报错，再运行生成的代码。

TypeScript 变快意味着上面每一步都被理顺。等编辑器加载完整个项目会感觉近乎瞬时；find-all-references、自动补全、诊断的延迟只剩过去的零头；跑 `tsc`（尤其是 `--watch` 模式）时反馈循环收得更紧，迭代比以前快得多。

在真实项目上能直接看到这个差距。下面是几个较大的开源代码库在 TypeScript 6 和 7 上的构建时间：

| 代码库     | TypeScript 6 | TypeScript 7 | 提速  |
| ---------- | ------------ | ------------ | ----- |
| vscode     | 125.7s       | 10.6s        | 11.9x |
| sentry     | 139.8s       | 15.7s        | 8.9x  |
| bluesky    | 24.3s        | 2.8s         | 8.7x  |
| playwright | 12.8s        | 1.47s        | 8.7x  |
| tldraw     | 11.2s        | 1.46s        | 7.7x  |

内存占用同样更省，同一批项目在整个构建过程里的聚合内存下降了 6% 到 26%：

| 代码库     | TypeScript 6 | TypeScript 7 | 内存变化 |
| ---------- | ------------ | ------------ | -------- |
| vscode     | 5.2GB        | 4.2GB        | -18%     |
| sentry     | 4.9GB        | 4.6GB        | -6%      |
| bluesky    | 1.8GB        | 1.3GB        | -26%     |
| playwright | 1.0GB        | 0.9GB        | -11%     |
| tldraw     | 0.6GB        | 0.5GB        | -15%     |

编辑器里的体验不止完整构建这一项。同一台机器上，在 VS Code 代码库里打开一个有错的文件，从打开编辑器到看到第一个错误，以前要约 17.5 秒，TypeScript 7 下不到 1.3 秒，快了 13 倍以上。

## 已经在生产里验证过

TypeScript 项目十多年积累了数万个测试，每次 `main` 分支提交都跑。但 7.0 不是普通版本，团队在测试套件之外还动用了很多资源确认它能上生产。

过去一年，团队和许多内部及外部大团队一起在真实代码库上测 TypeScript 7，反馈压倒性地正面。微软的 Loop、Office、PowerBI、Teams、Xbox 等团队参与了超大代码库的验证；Bloomberg、Canva、Figma、Google、Linear、Miro、Notion、Sentry、Slack、Vercel 等公司也在自己代码库上测过并给了反馈。

数据上也能看出质量变化：TypeScript 7.0 的新语言服务器把失败的语言服务命令减少了 80% 以上，服务器崩溃减少了 60% 以上（相较 6.0）。一些规模化团队的反馈很直接：

- Slack 工程师说 TypeScript 7 砍掉了他们 40% 的合并队列时间，CI 里的类型检查从约 7.5 分钟降到 1.25 分钟。本地编辑器体验以前因为语言服务器加载慢几乎"不可用"，现在几秒就能加载同一个代码库，本地类型检查重新变得可行。
- Vanta 的构建在他们最大的项目之一上提速最高 9 倍。
- 微软 News Services 团队说采用 TypeScript 7 每月省下 400 小时的 CI 构建等待。
- Canva 说语言服务从约 58 秒看到第一个错误降到约 4.8 秒。

## 和 TypeScript 6.0 并存运行

TypeScript 7.0 目前**不带 API**。7.1 预计会带一个新的（且不同的）API，但在那之前，团队优先保证 7.0 能和 6.0 并存，供那些仍需要编程式访问编译器的工具使用（比如 typescript-eslint）。

为此他们发布了兼容包 `@typescript/typescript6`，它提供一个叫 `tsc6` 的可执行文件，让你能在没有命名冲突的情况下并存安装。这个包还重新导出了 6.0 的 API，于是你可以让 `tsc` 用 7.0，其他工具继续依赖 6.0。

因为像 typescript-eslint 这类工具期望直接从 `typescript` 导入，推荐用 npm 别名实现。可以跑：

```
npm install -D typescript@npm:@typescript/typescript6
```

或者改 `package.json`：

```
{
  "devDependencies": {
    "typescript": "npm:@typescript/typescript6@^6.0.2",
  }
}
```

注意这样做只会给你 `tsc6` 可执行文件。想同时拿到 7.0 的 `tsc`，再加一个 TypeScript 7 的别名，`npx tsc` 就会走 7.0：

```
{
  "devDependencies": {
    "@typescript/native": "npm:typescript@^7.0.2",
    "typescript": "npm:@typescript/typescript6@^6.0.2"
  }
}
```

另外，此前大多数人是通过 `@typescript/native-preview` 装 TypeScript 7 的（每周下载超 850 万次）。之后每日构建会回归标准 `typescript` 包的 `next` 标签，用 `npm install -D typescript@next` 即可。

## 并行控制：checkers 和 builders

TypeScript 7.0 现在把很多步骤并行执行，包括解析、类型检查和输出。解析和输出这类步骤在文件间基本独立，所以并行能随代码库变大自动扩展，开销很小。但不是每一步都好并行。

TypeScript 7 引入了实验性的 `--checkers` 和 `--builders` 两个标志，用来微调类型检查、项目引用构建这类不那么好并行的步骤。还有一个 `--singleThreaded` 标志可以完全关闭并行，用于调试或资源受限的环境。

### 类型检查并行

类型检查在文件间的依赖更复杂：多数文件依赖同一批来自依赖项和全局作用域的类型信息，完全独立地跑检查器会浪费计算和内存。另一方面类型检查偶尔依赖程序内信息的相对顺序，所以从头检查必须每次以相同顺序检查相同文件，才能保证结果一致。

为了兼顾并行和一致性，7.0 创建固定数量、各自持有一份世界视图的类型检查 worker。它们可能重复一些公共工作，但对同样的输入文件，永远以相同方式划分并产出相同结果。

默认 4 个 worker，可用 `--checkers` 调。在核数更多的机器上加大这个数能进一步提速，但通常以更高内存为代价。前面表格用的是默认 `--checkers 4`；换成 `--checkers 8` 同一机器上：

| 代码库     | TypeScript 6 | TypeScript 7 (`--checkers 8`) | 提速  |
| ---------- | ------------ | ----------------------------- | ----- |
| vscode     | 125.7s       | 7.51s                         | 16.7x |
| sentry     | 139.8s       | 12.08s                        | 11.6x |
| bluesky    | 24.3s        | 2.01s                         | 12.1x |
| playwright | 12.8s        | 1.16s                         | 11x   |
| tldraw     | 11.2s        | 1.06s                         | 10.6x |

反过来，在核少内存小的机器（比如 CI runner）上，你可能想调低以避免额外开销，最低可设 `--checkers 1`，等于把类型检查变单线程、消除重复工作。少数情况下改 checkers 数量会暴露顺序相关的结果差异，跨环境固定一个数值能保证大家结果一致。

### 项目引用构建并行

7.0 不仅能在单个项目内并行，还能同时构建多个项目，用 `--builders` 标志控制 `--build` 下同时运行的并行项目引用构建器数量，对多项目 monorepo 特别有用。

和 `--checkers` 一样，加大 builders 能提速但更耗内存，而且它和 `--checkers` 是乘积关系——`--checkers 4 --builders 4` 允许最多 16 个类型检查器同时跑，可能过头。不同于 checkers，改 builders 数量不会产生不同结果，但项目引用构建本质上受项目依赖图瓶颈限制。

### 单线程模式

某些情况下强制整个编译器单线程会有用：调试、对比 6 和 7 的性能、外部编排并行构建，或在资源极受限的环境跑。`--singleThreaded` 标志不仅把类型检查 worker 限为 1，还确保解析和输出也在单线程里完成。

## 重建的 --watch 模式

TypeScript 7 带了一个彻底重建的 `--watch` 模式，底层基于 [Parcel 打包器的文件监听器](https://github.com/parcel-bundler/watcher)，提供高效稳定的跨平台文件监听。

团队移植监听逻辑时遇到过几个坑：Go 标准库没有内置文件监听 API，试过的第三方库在稳定性、性能、跨平台或构建工具集成上各有问题。纯轮询方案能广泛跑起来但计算太贵，尤其是 `node_modules` 依赖多的大项目。而 Parcel 的监听器虽然好用，却是 C++ 写的、需要完整 C++ 工具链。他们最后把它移植成 Go（加了几个最小的汇编垫片），从直译逐步打磨成能通过移植测试套件的地道 Go 代码，跨平台的资源占用显著改善。

## 从 5.x 到 6.0 再到 7.0 的行为变更

TypeScript 7.0 在类型检查和命令行行为上兼容 6.0。基本上任何在 6.0 下（开着 `stableTypeOrdering`、没设 `ignoreDeprecations`）能干净编译的代码，在 7.0 下应该编译结果一致。

但 7.0 采用了 6.0 的新默认值，并对 6.0 里废弃的标志和写法直接报硬错误。由于 6.0 还比较新，很多项目需要适配这些新行为。建议先采用 6.0 来平滑过渡。默认配置的显著变化有：

- `strict` 默认 `true`
- `module` 默认 `esnext`
- `target` 默认为紧邻 `esnext` 之前的当前稳定 ECMAScript 版本
- `noUncheckedSideEffectImports` 默认 `true`
- `libReplacement` 默认 `false`
- `stableTypeOrdering` 默认 `true` 且不能关
- `rootDir` 现在默认 `./`，内层源目录必须显式设置
- `types` 现在默认 `[]`，想恢复旧行为设成 `["*"]`

`rootDir` 和 `types` 的变化最可能让人意外，但都好处理。tsconfig.json 在 `src` 之类目录外的项目，加上 `rootDir` 就能保持原目录结构：

```
  {
      "compilerOptions": {
          // ...
+         "rootDir": "./src"
      },
      "include": ["./src"]
  }
```

依赖特定全局声明的项目要显式列出它们：

```
  {
      "compilerOptions": {
          // 显式列出你需要的 @types 包（如 bun、mocha、jasmine 等）
+         "types": ["node", "jest"]
      }
  }
```

变成硬错误、行为置空的废弃项包括：不再支持 `target: es5`、`downlevelIteration`、`moduleResolution: node/node10`（改用 `nodenext` 或 `bundler`）、`module: amd/umd/systemjs/none`、`baseUrl`、`moduleResolution: classic`；`esModuleInterop` 和 `allowSyntheticDefaultImports` 不能设为 `false`；`alwaysStrict` 视为 `true` 不能关；namespace 声明里不能用 `module` 关键字；import 上不能用 `asserts`，要改用 `with` 关键字。

### 模板字面量类型现在保留 Unicode 码点

7.0 在从模板字面量类型推断时更自然地处理 Unicode 码点：

```
type HeadTail<S> = S extends `${infer Head}${infer Tail}` ? [Head, Tail] : never;

type Result = HeadTail<"😀abc">;
//   ^
// 7.0 里：["😀", "abc"]
// 以前：["\ud83d", "\ude00abc"]
```

以前 TypeScript 跟随 JavaScript 的 UTF-16 索引行为，把 `"😀"` 拆成代理对的两半。技术上和 JS 索引一致，但通常不是人们想要的，还会产生含不成对代理项、语义无意义的字符串字面量类型。对那些刻意建模 UTF-16 码元的类型级字符串工具（比如某些 `Length` 工具），这是破坏性变更。新行为更接近用 `for...of` 遍历或 `[...str]` 展开时的直觉——`"😀"` 被当成一个单位。

### JavaScript 支持的差异

移植时团队顺带重做了 JavaScript 支持，让它和 `.ts` 文件的分析方式更一致。一些差异：值不能用在期望类型的地方，改写 `typeof someValue`；`@enum` 不再被特殊识别；单独的 `?` 不再能当类型用，改用 `any`；`@class` 不再让函数变构造器，改用 `class` 声明；不支持后缀 `!`；类型名必须定义在 `@typedef` 标签里；不再支持 Closure 风格函数语法。更详细的 6.0 到 7.0 差异记录在项目的 [`CHANGES.md`](https://github.com/microsoft/typescript-go/blob/main/CHANGES.md) 里。

## 暂时还不能用的场景

有一点要特别说清楚：用 Vue、MDX、Astro、Svelte 的工作流，以及 Angular 里模板内的专门类型检查，暂时还不能用 TypeScript 7。原因是 7.0 还没暴露稳定的编程式 API，那些把 TypeScript 嵌进自己编译器和语言服务的工具（比如 Volar）目前只能依赖 6.0。团队说这是一个阶段性问题，会主动和这些项目的维护者合作解决。

在那之前的建议：Angular 项目可以用 TypeScript 7 通过 `tsc` 在命令行做快速的全项目错误检测，编辑器仍用 6.0；用 Vue、MDX、Astro、Svelte 的项目暂时继续用 6.0。VS Code 里跑一下"Disable TypeScript 7 Language Server"命令就能回到 6.0。

## 往后怎么走

7.0 是 TypeScript 项目的一个大里程碑。这次移植是团队一年多的主要工作，7.0 出了之后，团队会回到新功能、易用性改进、更多性能优化，以及为整个生态实现新 API。发布节奏预计和 7.0 之前类似，每 3-4 个月一个有新特性的版本。7.1 已经在路上，会补上生态里的空缺。

如果你手上有被类型检查拖慢的大型 TS 项目，这个版本值得尽早在非嵌入式语言的场景里试。先把 6.0 的默认变更适配好，迁移到 7.0 会顺很多。

## 参考

- [Announcing TypeScript 7.0](https://devblogs.microsoft.com/typescript/announcing-typescript-7-0/)
- [A 10x Faster TypeScript（原生移植计划）](https://devblogs.microsoft.com/typescript/typescript-native-port/)
- [TypeScript 6.0 到 7.0 的行为差异 CHANGES.md](https://github.com/microsoft/typescript-go/blob/main/CHANGES.md)
  </content>
