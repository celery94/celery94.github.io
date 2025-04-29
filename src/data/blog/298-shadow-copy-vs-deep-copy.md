---
pubDatetime: 2025-04-29
tags: [复制, JavaScript, 深拷贝, 浅拷贝]
slug: shadow-copy-vs-deep-copy
source: sevalla
author: Celery Liu
title: JavaScript对象拷贝详解：浅拷贝 vs 深拷贝🌊🆚🌊🌊
description: 深入剖析JavaScript中浅拷贝和深拷贝的原理、实现方式及其在实际开发中的注意事项，助你避开常见“引用陷阱”！
---

# JavaScript对象拷贝详解：浅拷贝 vs 深拷贝🌊🆚🌊🌊

在日常开发中，我们经常会遇到需要“复制对象”的场景。你是否也遇到过：明明用了扩展运算符（...）或`Object.assign`进行对象复制，结果修改副本却影响了原对象？这就是“浅拷贝”与“深拷贝”的经典问题！本文结合实际代码案例，带你系统梳理相关技术细节。

## 1. 浅拷贝（Shallow Copy）原理与实现🌊

### 什么是浅拷贝？

浅拷贝会**复制对象的第一层属性**。如果某个属性的值本身是一个对象（如嵌套对象），那么**只会复制该对象的引用**，而不会递归复制内部的结构。这导致副本和原对象的嵌套属性依然共享同一份数据。

### 常用实现方式

最常用的浅拷贝方法有：

- 扩展运算符（Spread Operator）：`{ ...obj }`
- `Object.assign({}, obj)`

#### 代码示例

```js
const originalConfig = {
  app: "sevalla-web",
  region: "us-east-1",
  resources: {
    cpu: "2vCPU",
    memory: "4GB",
  },
};

// 使用扩展运算符进行浅拷贝
const shallowCopy = { ...originalConfig };

// 修改嵌套对象
shallowCopy.resources.cpu = "4vCPU";

console.log(originalConfig.resources.cpu); // 输出："4vCPU"
```

#### 技术解析

- `shallowCopy`与`originalConfig`的顶层属性（如`app`, `region`, `resources`）是独立的。
- 但`resources`指向同一个内存地址，所以修改`shallowCopy.resources.cpu`会影响原对象。
- **结论**：浅拷贝只“断开”了顶层，嵌套对象依然“绑在一起”。

### 适用场景

- 对象结构简单，无嵌套对象
- 不需要完全独立的数据副本

---

## 2. 深拷贝（Deep Copy）原理与实现🌊🌊

### 什么是深拷贝？

深拷贝会**递归复制对象的所有层级属性**，无论属性值是基本类型还是引用类型。这样，副本和原对象之间不会有任何共享的子对象，彼此完全独立。

### 常用实现方式

- JSON序列化+反序列化：`JSON.parse(JSON.stringify(obj))`
- 第三方库：如lodash的`_.cloneDeep`
- 手写递归函数（适用于特殊需求）

#### 代码示例

```js
const deepConfig = JSON.parse(JSON.stringify(originalConfig));

// 修改嵌套对象
deepConfig.resources.cpu = "8vCPU";

console.log(originalConfig.resources.cpu); // 输出："4vCPU"
console.log(deepConfig.resources.cpu); // 输出："8vCPU"
```

#### 技术解析

- `JSON.stringify`将对象序列化成字符串，`JSON.parse`再反序列化为新对象。
- 所有层级的数据都被复制，嵌套对象不再共享引用。
- 修改副本不会影响原始对象。
- **注意**：此方法有局限性，如无法处理函数、undefined、Symbol等特殊类型。

### 适用场景

- 对象嵌套层级多
- 需要完全独立的数据副本
- 对性能要求不高（JSON方法较慢且有类型局限）

---

## 3. 总结与最佳实践💡

### 浅拷贝适合什么场景？

- 仅需顶层属性独立，嵌套对象不需分离；
- 代码简洁，性能优先；
- 对象结构简单、扁平。

### 深拷贝适合什么场景？

- 需要彻底断开副本和原对象之间的所有联系；
- 对象结构复杂，多层嵌套；
- 防止“引用陷阱”，保证数据安全隔离。

### 技术选型建议

- 如果只需简单复制一层，用扩展运算符或Object.assign即可；
- 若涉及深度嵌套，优先考虑`JSON.parse(JSON.stringify(obj))`，或者使用lodash等库的深拷贝工具；
- 对于需要保留函数、Symbol等特殊类型时，建议自定义递归拷贝逻辑。

---

## 4. 小结🔖

理解浅拷贝与深拷贝，是写好JavaScript高质量代码的重要基础。遇到复杂数据结构时，千万要警惕“引用共用”带来的隐患。希望本文结合实例分析，能让你一眼看懂二者区别，并在实际开发中灵活选用，写出健壮可靠的业务代码！

---

让我们一起避开JS开发中的“引用陷阱”，高效进阶吧！🚀
