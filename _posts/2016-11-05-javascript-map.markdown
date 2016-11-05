---
layout: post
title:  "Javascript 方法：Map"
date:   2016-11-05
tags: 
    - javascript
---

## Map方法

map是数组（Array）的一个方法，对数组的每个元素调用定义的回调函数并返回包含结果的数组。

对于数组的每个元素，mao方法都会调用回调函数一次（采用升序索引顺序）。
不对为数组中缺少的元素调用回调函数。

除了数组对象之外，map方法可由具有length属性且具有已按数字编制索引的属性名的任何对象使用。

以下是最简单的示例：

{% highlight javascript %}

// Define the callback function.
function AreaOfCircle(radius) {
    var area = Math.PI * (radius * radius);
    return area.toFixed(0);
}

// Create an array.
var radii = [10, 20, 30];

// Get the areas from the radii.
var areas = radii.map(AreaOfCircle);
{% endhighlight %}

## Map方法中使用thisArg参数

map方法的定义如下：

array.map(callbackfn[, thisArg])

其中thisArg是一个可选参数，这个参数表示callbackfn中的this关键字引用的对象，如果省略了改参数，undefined将用作this值。

以下是示例代码：

{% highlight javascript %}
// Define an object that contains a divisor property and a remainder function.
var obj = {
    divisor: 10,
    remainder: function (value) {
        return value % this.divisor;
    }
}

// Create an array.
var numbers = [6, 12, 25, 30];

// Get the remainders.
// The obj argument specifies the this value in the callback function.
var result = numbers.map(obj.remainder, obj);
document.write(result);

// Output:
// 6,2,5,0

{% endhighlight %}

## 对字符串使用map方法

示例：

{% highlight javascript %}
// Define the callback function.
function threeChars(value, index, str) {
    // Create a string that contains the previous, current,
    // and next character.
    return str.substring(index - 1, index + 2);
}

// Create a string.
var word = "Thursday";

// Apply the map method to the string.
// Each array element in the result contains a string that
// has the previous, current, and next character.
// The commented out statement shows an alternative syntax.
var result = [].map.call(word, threeChars);
// var result = Array.prototype.map.call(word, threeChars);

document.write(result);

// Output:
// Th,Thu,hur,urs,rsd,sda,day,ay
{% endhighlight %}

