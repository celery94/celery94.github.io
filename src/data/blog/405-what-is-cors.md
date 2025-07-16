---
pubDatetime: 2025-07-16
tags: ["CORS", "Web Security", "Backend", "API"]
slug: what-is-cors
source: N/A
title: 什么是跨域资源共享（CORS）？
description: 深入解析CORS的工作原理、常见配置方式及其背后的安全逻辑，帮助开发者理解和解决实际开发中的跨域问题。
---

# 什么是跨域资源共享（CORS）？

跨域资源共享（Cross-Origin Resource Sharing, CORS）是现代Web浏览器用来解决安全限制的一种机制。它决定了浏览器是否允许网页从一个域名（origin）去请求另一个域名的资源。当你用浏览器访问API或加载外部资源时，CORS是保护你数据安全的核心机制之一。

## CORS 的基本原理

每当浏览器发起跨域请求时，都会在请求头中自动带上 `Origin` 字段。服务器收到请求后，会判断这个来源是否合法。如果合法，服务器会在响应头中设置 `Access-Control-Allow-Origin`，指定允许访问的源。如果两者匹配，浏览器才会允许前端脚本读取数据；否则，浏览器会直接拦截响应，前端无法获取数据。

这种机制能有效阻止恶意网站随意请求你网站的数据，也避免了用户的身份凭证（如Cookie）被第三方网站盗用。

## CORS 的后台处理与配置

处理跨域的方式主要在后端实现。开发者可以在服务器代码中通过CORS中间件，控制允许哪些源（origin）访问API。

**常见配置方式有两种：**

1. **允许所有域名访问：**
   后台可以通过设置响应头 `Access-Control-Allow-Origin: *` 来允许任意网站访问资源。这种做法虽然最简单，但极不推荐，因为这等于完全关闭了浏览器的同源策略，存在极高的安全风险。

2. **只允许特定域名访问：**
   更安全的做法是只允许可信任的域名访问，比如：

   ```
   Access-Control-Allow-Origin: https://somedomain.com
   ```

   这样，只有 `https://somedomain.com` 的前端页面才可以调用接口。结合其他CORS响应头（如 `Access-Control-Allow-Credentials`, `Access-Control-Allow-Methods`），可以实现更精细的权限控制。

例如，Node.js中的[express-cors中间件](https://expressjs.com/en/resources/middleware/cors.html)可以这样配置：

```js
const cors = require("cors");
app.use(
  cors({
    origin: "https://your-allowed-origin.com",
    credentials: true,
  })
);
```

## 代理服务器解决跨域

除了直接在后端配置CORS外，还可以通过代理服务器绕过浏览器的限制。代理服务器相当于前端和目标API之间的中转站。前端先向自己的服务器发请求，服务器再去请求外部API，并把结果返回给前端。这样，浏览器只会检测本地服务器的响应，而不会产生跨域问题。

这种方式常用于开发阶段，或当第三方API无法修改CORS策略时。例如，常见的[nginx反向代理](https://nginx.org/en/docs/http/ngx_http_proxy_module.html)或[前端开发服务器的proxy功能](https://webpack.js.org/configuration/dev-server/#devserverproxy)。

## CORS 的安全意义与风险

CORS的核心目的，是防止第三方网站未经允许获取你的用户数据。
如果没有CORS，任何一个网页都可以用JavaScript直接向你的API发起请求，并自动携带浏览器保存的Cookie、Token等敏感信息，甚至可以执行用户的关键操作。这意味着用户账户存在被劫持、数据泄露等重大风险。

CORS机制通过服务器白名单，大大提高了API接口的安全性。即便是公开的API服务，也建议合理设置CORS策略，最小化潜在风险。

## 典型应用场景和最佳实践

在实际开发中，CORS配置最容易出现在SPA（单页应用）、前后端分离项目或小程序接口中。开发者应根据业务需求，选择合适的CORS设置。开发阶段可适当放宽（如允许本地端口），上线后务必严格控制。

同时，务必配合CSRF、身份认证等安全措施，避免仅靠CORS保护用户安全。

---

**总结：**
CORS是Web安全体系的基础组件。只有正确理解其工作机制，并在服务器端合理配置，才能既保证数据的安全性，又能提升开发效率。无论是通过响应头控制，还是代理绕过，核心目标始终是——让数据流动在可控范围内，保障用户和服务的安全。
