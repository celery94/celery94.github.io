---
layout: post
title:  "Javascript 方法：Reduce"
date:   2016-11-07
tags: 
    - javascript
---

## Reduce 方法

Reduce方法对数组中的所有元素调用指定的回调函数。
改回调函数的返回值为累计结果，并且此返回值在下一次调用改回调函数的时候作为参数提供。

示例：

{% highlight javascript %}
// Define the callback function.
function appendCurrent (previousValue, currentValue) {
    return previousValue + "::" + currentValue;
}

// Create an array.
var elements = ["abc", "def", 123, 456];

// Call the reduce method, which calls the callback function
// for each array element.
var result = elements.reduce(appendCurrent);

document.write(result);

// Output:
//  abc::def::123::456
{% endhighlight %}

Reduce方法还提供初始值作为参数：

{% highlight javascript %}
// Define the callback function.
function addRounded (previousValue, currentValue) {
    return previousValue + Math.round(currentValue);
    }

// Create an array.
var numbers = [10.9, 15.4, 0.5];

// Call the reduce method, starting with an initial value of 0.
var result = numbers.reduce(addRounded, 0);

document.write (result);
// Output: 27
{% endhighlight %}
