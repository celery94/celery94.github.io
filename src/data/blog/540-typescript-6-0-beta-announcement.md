---
pubDatetime: 2026-02-11
title: "TypeScript 6.0 Beta 发布：通往原生编译器的桥梁"
description: "TypeScript 6.0 Beta 版本发布，作为向 Go 语言编写的 TypeScript 7.0 过渡的最后一个基于 JavaScript 的版本，引入了多项新特性和重要的配置变更。"
tags: ["TypeScript", "JavaScript", "编译器"]
slug: "typescript-6-0-beta-announcement"
source: "https://devblogs.microsoft.com/typescript/announcing-typescript-6-0-beta"
---

# TypeScript 6.0 Beta 发布：通往原生编译器的桥梁

微软今日宣布 TypeScript 6.0 Beta 版本发布。这是一个具有特殊意义的版本 —— 它是最后一个基于 JavaScript 代码库的 TypeScript 版本。团队正在开发使用 Go 语言编写的新编译器，TypeScript 7.0 将基于这个新的原生代码实现，利用原生代码的速度优势和共享内存多线程能力。

## 安装方式

```bash
npm install -D typescript@beta
```

## 核心特性

### 1. 减少 this 无关函数的上下文敏感性

TypeScript 现在能够更智能地处理不使用 `this` 的函数。对于使用方法语法但从未引用 `this` 的函数，TypeScript 6.0 会将其视为非上下文敏感函数，从而在类型推断时获得更高的优先级。

```typescript
declare function callIt<T>(obj: {
  produce: (x: number) => T;
  consume: (y: T) => void;
}): void;

// 现在两种写法都能正常工作
callIt({
  consume(y) {
    return y.toFixed();
  }, // 不再报错
  produce(x: number) {
    return x * 2;
  },
});
```

### 2. 支持 #/ 开头的子路径导入

Node.js 新增了对 `#/` 前缀的子路径导入支持，允许开发者使用简洁的路径映射：

```json
{
  "name": "my-package",
  "type": "module",
  "imports": {
    "#": "./dist/index.js",
    "#/*": "./dist/*"
  }
}
```

这样可以使用 `#/utils.js` 替代冗长的相对路径 `../../utils.js`。

### 3. 允许 --moduleResolution bundler 与 --module commonjs 组合

之前 `--moduleResolution bundler` 只能与 `--module esnext` 或 `--module preserve` 配合使用，现在可以与 `--module commonjs` 组合。

### 4. --stableTypeOrdering 标志

为了帮助开发者诊断 6.0 和 7.0 之间的差异，新增了 `--stableTypeOrdering` 标志。此标志让 6.0 的类型排序行为与 7.0 保持一致，但会导致类型检查速度降低最多 25%，仅建议在迁移诊断时使用。

### 5. 新增 ECMAScript 2025 支持

TypeScript 6.0 为 `target` 和 `lib` 添加了 `es2025` 选项，包含：

- `RegExp.escape` - 转义正则表达式中的特殊字符
- `Promise.try` - 安全执行同步或异步代码
- Iterator 和 Set 的新方法

### 6. Temporal API 类型支持

期待已久的 Temporal 提案已进入 Stage 3 阶段，TypeScript 6.0 提供了内置类型支持：

```typescript
let yesterday = Temporal.Now.instant().subtract({
  hours: 24,
});

let tomorrow = Temporal.Now.instant().add({
  hours: 24,
});
```

### 7. Map 的 "upsert" 方法类型

新增 `getOrInsert` 和 `getOrInsertComputed` 方法的类型定义：

```typescript
function processOptions(compilerOptions: Map<string, unknown>) {
  let strictValue = compilerOptions.getOrInsert("strict", true);
}

// 用于计算成本较高的默认值
someMap.getOrInsertComputed("someKey", () => {
  return computeSomeExpensiveValue();
});
```

### 8. DOM 库自动包含可迭代支持

`dom` 库现在自动包含 `dom.iterable` 和 `dom.asynciterable` 的内容，无需再手动添加：

```typescript
// 现在只需 "lib": ["dom"]
for (const element of document.querySelectorAll("div")) {
  console.log(element.textContent);
}
```

## 重大变更和废弃功能

TypeScript 6.0 引入了多项重大变更，为 TypeScript 7.0 做准备。主要包括：

### 配置默认值变更

- **`strict` 默认为 `true`**：新项目默认启用严格模式
- **`module` 默认为 `esnext`**：ESM 成为主流模块格式
- **`target` 默认为当前年份的 ES 版本**：目前为 `es2025`
- **`noUncheckedSideEffectImports` 默认为 `true`**：帮助捕获副作用导入中的拼写错误
- **`rootDir` 默认为 `.`**：不再自动推断源文件目录
- **`types` 默认为 `[]`**：不再自动加载所有 `@types` 包

### 废弃的功能

以下选项在 TypeScript 6.0 中已废弃，将在 TypeScript 7.0 中完全移除：

- `target: es5` - 最低目标版本改为 ES2015
- `--downlevelIteration` - 仅对 ES5 有效，随 ES5 目标一起废弃
- `--moduleResolution node` (node10) - 应迁移至 `nodenext` 或 `bundler`
- `--module amd/umd/systemjs` - 应迁移至 ESM
- `--baseUrl` - 应使用 `paths` 中的显式前缀
- `--moduleResolution classic` - 应使用现代解析策略
- `--esModuleInterop false` - 始终启用安全的互操作行为
- `--allowSyntheticDefaultImports false` - 始终启用
- `--alwaysStrict false` - 所有代码假定为严格模式
- `--outFile` - 应使用外部打包工具
- `module` 关键字声明命名空间 - 改用 `namespace` 关键字
- `asserts` 关键字导入 - 改用 `with` 关键字

### 需要立即调整的配置

许多项目需要进行以下调整之一或全部：

1. **设置 `types` 数组**，通常为 `"types": ["node"]`

   - 使用 `"types": ["*"]` 可恢复 5.9 的行为，但建议使用显式数组以提升构建性能

2. **设置 `rootDir`**，如 `"rootDir": "./src"`
   - 如果看到文件输出到 `./dist/src/index.js` 而非 `./dist/index.js`，说明需要此配置

## 准备迁移到 TypeScript 7.0

TypeScript 6.0 可以通过设置 `"ignoreDeprecations": "6.0"` 来忽略废弃警告，但 TypeScript 7.0 将完全移除这些废弃选项。团队计划在 6.0 发布后尽快发布 7.0 版本。

[ts5to6 工具](https://github.com/andrewbranch/ts5to6)可以自动调整代码库中的 `baseUrl` 和 `rootDir` 配置。

## 下一步

TypeScript 6.0 现已进入功能稳定阶段，不再计划新增功能或重大变更。团队鼓励开发者在接下来几周内试用 beta 版本并提供反馈。

同时，TypeScript 7.0 的开发工作仍在继续，团队每日发布[原生预览版本](https://www.npmjs.com/package/@typescript/native-preview)以及配套的 [VS Code 扩展](https://marketplace.visualstudio.com/items?itemName=TypeScriptTeam.native-preview)。
