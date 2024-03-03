---
pubDatetime: 2024-03-02
tags: [typescript]
title: 如何在 TypeScript 中定义类型，以及接口、类型别名和类的区别
description: 在 TypeScript 中，定义类型可以通过多种方式，主要包括以下几种方法：基础类型注解、接口、类型别名、类、枚举、联合类型、交叉类型、泛型、元组等。本文将介绍这些方法的使用场景、特性和示例，以及接口、类型别名和类的区别。
---

# 如何在 TypeScript 中定义类型，以及接口、类型别名和类的区别

## 在 TypeScript 中，定义类型可以通过多种方式，主要包括以下几种方法：

1. **基础类型注解** - 直接在变量、函数参数、或函数返回类型的位置上声明类型：

```typescript
let isActive: boolean = true;
let count: number = 10;
let name: string = "Alice";

function greet(name: string): string {
  return "Hello, " + name;
}
```

2. **接口（`interface`）** - 使用 `interface` 关键字来定义对象的形状，可以包括属性和方法的类型定义，并且支持扩展（继承）：

```typescript
interface Person {
  name: string;
  age: number;
}

let person: Person = { name: "Bob", age: 20 };
```

3. **类型别名（`type`）** - 使用 `type` 关键字来定义类型别名，可以为基础类型、联合类型、交叉类型、元组等创建别名，并且可以用来定义对象的形状：

```typescript
type Animal = {
  species: string;
  age: number;
};

let dog: Animal = { species: "Canine", age: 5 };
```

4. **类（`class`）** - 类型可以通过类定义，类的实例会具有类中定义的属性和方法的类型：

```typescript
class Car {
  make: string;
  model: string;
  constructor(make: string, model: string) {
    this.make = make;
    this.model = model;
  }
}

let myCar: Car = new Car("Toyota", "Corolla");
```

5. **枚举（`enum`）** - 使用 `enum` 关键字定义一组命名的常量：

```typescript
enum Direction {
  Up,
  Down,
  Left,
  Right,
}

let dir: Direction = Direction.Up;
```

6. **联合类型** - 使用 `|` 符号定义一个类型可以是几个类型之一：

```typescript
type StringOrNumber = string | number;

let id: StringOrNumber = "123"; // 可以是字符串
id = 123; // 也可以是数字
```

7. **交叉类型** - 使用 `&` 符号定义一个类型必须满足多个类型的结合：

```typescript
type Draggable = {
  drag(): void;
};

type Resizable = {
  resize(): void;
};

type UIWidget = Draggable & Resizable;

let textBox: UIWidget = {
  drag: () => {},
  resize: () => {},
};
```

8. **泛型** - 使用尖括号 `<>` 定义可重用的类型变量，使得类型可以动态传入：

```typescript
function identity<T>(arg: T): T {
  return arg;
}

let output = identity<string>("myString");
```

9. **元组** - 元组类型允许表示一个已知元素数量和类型的数组，各元素的类型不必相同：

```typescript
type StringNumberPair = [string, number];

let value: StringNumberPair = ["hello", 42];
```

## **接口（`interface`）**，**类型别名（`type`）**与**类（`class`）**的区别

### interface（接口）

**使用场景**:

- 定义对象的形状，包括属性和方法的声明。
- 用于定义公共 API 的契约。
- 当你希望建立明确的代码规范，或者在对象间共享结构时使用。
- 在面向对象编程中，用于定义类应该遵循的规范。

**特性**:

- 可以被扩展和实现（继承和多态）。
- 可以合并声明（如果你在两个不同的地方声明了同一个接口，它们会自动合并）。
- 不能定义联合或交叉类型。
- 适用于定义对象的形状和类的实现。

**示例**:

```typescript
interface Animal {
  species: string;
  makeSound(): void;
}

interface Pet extends Animal {
  name: string;
}

class Dog implements Pet {
  species = "canine";
  name: string;

  constructor(name: string) {
    this.name = name;
  }

  makeSound() {
    console.log("Woof!");
  }
}
```

### type（类型别名）

**使用场景**:

- 定义对象的形状，或者其他类型的别名，如联合类型、交叉类型、元组等。
- 当你需要使用联合或交叉类型时。
- 当你需要类型别名指向一个原始类型、联合类型、元组等。

**特性**:

- 不能被扩展或实现（不支持继承和多态）。
- 不会自动合并声明。
- 可以定义联合和交叉类型。
- 更适合定义类型别名，或者当你需要一个类型不仅仅是对象形状时。

**示例**:

```typescript
type Animal = {
  species: string;
  makeSound(): void;
};

type Pet = Animal & {
  name: string;
};

const dog: Pet = {
  species: "canine",
  name: "Rex",
  makeSound: () => {
    console.log("Woof!");
  },
};
```

### class（类）

**使用场景**:

- 需要创建具体实例的时候。
- 面向对象编程，封装、继承、多态。
- 当你需要包含实现细节，而不仅仅是数据结构的定义时。

**特性**:

- 可以创建实例。
- 支持继承。
- 类型定义和值定义同时进行（定义了一个类型，同时也定义了一个构造函数）。
- 可以实现接口。
- 支持类成员的修饰符，如 `public`、`private`、`protected`、`readonly` 等。

**示例**:

```typescript
class Animal {
  species: string;

  constructor(species: string) {
    this.species = species;
  }

  makeSound() {
    console.log("Some sound!");
  }
}

class Pet extends Animal {
  name: string;

  constructor(name: string, species: string) {
    super(species);
    this.name = name;
  }
}

const dog = new Pet("Rex", "canine");
```

### 总结

- 使用 `interface` 当你需要其他类或对象来实现或遵守一个特定的结构或形状时。
- 使用 `type` 当你需要定义联合、交叉类型或者当你需要定义一个类型的别名时。
- 使用 `class` 当你需要创建实例或者需要继承、封装或多态特性时。

在实际开发中，这些特性可以根据具体需求和团队约定相互替换或混合使用。有时候，`interface` 和 `type` 可以互换使用，但是一般来说，如果你需要利用 TypeScript 的面向对象特性，比如类的继承和实现接口，那么 `interface` 是更好的选择。如果你需要定义联合类型或交叉类型，那么 `type` 是必须的。而 `class` 是当你需要实例化或者具有特定行为的对象时的选择。
