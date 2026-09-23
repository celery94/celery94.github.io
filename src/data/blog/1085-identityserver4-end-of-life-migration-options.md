---
pubDatetime: 2026-09-23T14:39:09+08:00
title: "IdentityServer4 已停止维护：迁移路线怎么选"
description: "IdentityServer4 自 2022 年底失去支持、仓库已归档，继续使用等于运行无人修补的组件。本文对照六条替代路线的价格与取舍，给出可照做的决策清单，并点出「免费内核」的隐性成本。"
tags: [".NET", "IdentityServer4", "OpenIddict", "身份认证"]
slug: "identityserver4-end-of-life-migration-options"
ogImage: "../../assets/1085/01-cover.png"
source: "https://identitysuite.net/blog/identitysuite/identityserver4-end-of-life"
---

如果你的 .NET 项目还在用 IdentityServer4 处理登录和令牌签发，那么你正在维护的是一套无人修补的安全关键组件。它从 2022 年 12 月起就失去了官方支持，GitHub 仓库也已经在 2025 年 3 月归档，不再接受任何提交。

处理这件事的难点不在"要不要迁"，而在"迁到哪"。本文把六条真实可选的路线放在同一张表里，按许可证、年成本、上手成本和数据控制四个维度对照，并给出可以直接照着走的决策清单。

## 先说两个时间点

IdentityServer4 归档仓库的说明写得很直白：项目"在 .NET Core 3.1 支持终止时（2022 年 12 月 13 日）随之失去支持"，并且该仓库"包含多个已知的安全漏洞和缺陷，文档也已过时"。代码随后被 fork 为 Duende IdentityServer，以商业产品形式继续维护。

这和"发版变慢"是两件不同的事。IdentityServer4 所处的位置是登录入口、令牌签发和会话管理之前的那一层。普通的过时依赖出问题时会报错，而一个过时的授权服务器会继续正常签发令牌、继续认证用户，不会给出任何提示——你无从知道某个已公开的重定向 URI 绕过或令牌校验缺陷是否正好适用于自己的部署，因为已经没有人再发布补丁可供比对了。

## 六条替代路线

下表所有价格与数字均来自各厂商 2026 年 9 月的官方页面，定价会变，决策前请再核对一次。

| 路线                       | 许可证与年成本                                                        | 上手成本                       | 技术栈     | 数据控制               |
| -------------------------- | --------------------------------------------------------------------- | ------------------------------ | ---------- | ---------------------- |
| Duende IdentityServer      | 5,750 / 12,500 / 24,900 美元/年；符合条件可申请免费 Community Edition | 低到中，与 IS4 概念最接近      | .NET       | 完全自托管             |
| Open.IdentityServer        | 内核免费；AdminUI 2,528–8,932 英镑/年                                 | 中，内核免费但工具另购         | .NET       | 完全自托管             |
| OpenIddict（自建）         | 免费（Apache-2.0）                                                    | 高，配置与安全全部自己负责     | .NET       | 完全自托管             |
| Keycloak                   | 免费（开源）                                                          | 中到高，等于多维护一套技术栈   | Java / JVM | 完全自托管             |
| 云身份服务（Auth0、Entra） | 免费额度；付费从 35 美元/月起，随 MAU 增长                            | 低，最快拿到可用的登录         | 厂商托管   | 有限，数据存放在厂商侧 |
| IdentitySuite              | 免费（3 客户端）、349 欧元/年、1,499 欧元/年                          | 低，管理界面、邮件与主题已内置 | .NET       | 完全自托管             |

## Duende IdentityServer：官方续作

由 IdentityServer4 原作者团队开发，是该项目的直接延续。如果你希望迁移时概念跨度最小，这是首选：配置模型、扩展点和整体思维模型都能较完整地沿用。

它是商业产品。官方当前定价为 Lite 每年 5,750 美元（1 个生产部署、2 个客户端 ID）、Standard 每年 12,500 美元（10 个客户端 ID、服务端会话）、Advanced 每年 24,900 美元（30 个客户端 ID、SAML、自动密钥管理），再往上是定制的 Custom 档。另有免费的 Community Edition，与 Standard 功能等价、不是功能阉割的试用版，面向预计年收入低于 100 万美元、资本总额低于 300 万美元的机构，或年度预算低于 100 万美元的非营利组织。超出这些门槛后，转到同一平台上的付费档。

它提供的是框架而不是成品：管理界面、主题和邮件模板都不包含，需要自行开发或向生态内的第三方购买。对于想自己掌控这一层的团队，这是优点；对于只想让认证跑起来的团队，这就是额外的工程量。

## Open.IdentityServer：免费的开源续作

由 .NET 咨询公司 Rock Solid Knowledge（RSK）维护，延续 Apache-2.0 许可的 IdentityServer4 代码库，支持 .NET 10。官方强调它不是简单重编译，而是带有新功能和缺陷修复的活跃 fork，并明确声明该项目与 Duende Software 无隶属关系、也未获其背书——这属于信息披露，不是危险信号。

免费承诺真实有效，但覆盖范围只有协议 SDK：管理界面、邮件构建器和主题构建器都不在其中。这些来自 RSK 的独立商业组件，AdminUI 单独授权为每年 2,528 英镑（Enterprise，不限用户与客户端，含 1 个生产环境），或每年 8,932 英镑（Universal，多生产环境）；把 AdminUI 与 passkey、SAML、SCIM、WS-Fed、密钥轮换和策略访问控制打包在一起的 Supporter License 为每年 5,750 英镑。也就是说，给免费内核配上管理界面之后，总成本与"开箱即用"的商业产品相当，有时还更高。

如果你一定要 Apache 许可、可社区审计的 IdentityServer4 代码延续，并准备自行拼装其余部分或购买 RSK 组件，这是一条站得住的路线。

## OpenIddict：免费、灵活，也全部靠自己

OpenIddict 是 Apache-2.0 许可的 .NET OAuth 2.0 / OpenID Connect 框架，IdentitySuite 本身就构建在它之上。没有许可费用，也没有需要谈判的供应商。

代价是它属于工具包而非产品：没有管理界面，没有用户管理页面，没有邮件流程，全部要自己写，安全敏感部分也要自己保证正确。常见的坑包括把开发证书留在生产环境、没有强制 PKCE、重定向 URI 校验过宽。这些都不是 OpenIddict 的缺陷，而是它留给使用者的自由度所对应的成本。如果团队有时间和安全经验把它配对并长期维持，这是名单上许可成本最低的选项；但在工程时间上，它很少是最便宜的。

## Keycloak：成熟免费，但是另一套技术栈

Keycloak 是成熟的开源身份与访问管理平台，功能覆盖面大：单点登录、身份代理、细粒度授权，以及活跃的插件生态。对于已经在运行 Java/JVM 基础设施、也具备相应运维能力的组织，它没有许可成本，是相当强的选择。

对 .NET 团队来说，代价在运维：你要额外维护一套运行时和部署模型，它的升级节奏、资源占用和主题定制方式都遵循 Java 工具链的习惯，而不是团队日常熟悉的那一套。

## 云身份服务：启动最快，成本随用量增长

Auth0 和 Microsoft Entra External ID 是最常见的两个云端选择。Auth0 当前定价包含免费档，覆盖 25,000 月活用户，付费从 35 美元/月起，随后按 MAU 和功能档位增长。不需要运行、修补或扩容任何基础设施，几小时而不是几周就能拿到可用的登录。

代价是所有按 MAU 计价的模式共有的：费用随用户量增长，身份数据存放在厂商的基础设施上而非自己的。对小规模且稳定的用户数，这通常不是问题；对预期用户显著增长或有数据驻留要求的业务，值得先算一遍成本曲线再决定。

## IdentitySuite：自托管、.NET 原生、固定定价

它和上面的自建路线建立在同一组基础之上——OpenIddict 加 ASP.NET Core Identity——但把管理界面、邮件模板构建器、主题构建器和 passkey 支持作为产品的一部分交付，而不是让你自己开发或另外采购。自托管意味着数据留在自己的基础设施上，授权方式为固定价格而非按用量：免费版支持 3 个客户端和 100 个用户，Standard 每年 349 欧元（10 个客户端、1,000 用户），Enterprise 每年 1,499 欧元（不限客户端与用户），没有按用户或 MAU 的费用。

不过要说明出处：这份对比来自 IdentitySuite 官方博客，而 IdentitySuite 是文中的候选方案之一。原文自己也承认了它的短板——相比 Duende 或 Keycloak 更年轻，生态和社区更小。今天就需要 SAML、十年积累下来的深度扩展点或大型插件市场，这个成熟度差距是真实存在的。

这不代表文中数据不可信：上面每条价格和日期都出自各厂商自己的官方页面，我在 2026 年 9 月核对过。但有两处值得按官方页面修正：

- IdentitySuite 免费版不只是"3 个客户端"，同时限制并发在线用户不超过 100；这里的客户端与用户指并发在线数，不是累计注册数。
- Auth0 的付费门槛（原文以 35 美元/月为例）对应的是 500 MAU 档位，而免费档覆盖 25,000 MAU。签约前按自己的真实用量档位重新核算，不要只看起步价。

## 怎么选：六条判断

以下依次对照团队处境，命中哪条就走哪条：

1. 想要官方背书的续作，也能承担商业定价或符合免费 Community Edition 条件 → Duende IdentityServer。
2. 想要免费的 Apache 许可、延续 IdentityServer4 代码库，并愿意自行拼装或另外购买其余组件 → Open.IdentityServer。
3. 有工程时间和安全经验逐项把关配置，且把许可成本放在第一位 → OpenIddict 直接自建。
4. 组织已在运行 Java / Kubernetes 基础设施，且有余力运维 → Keycloak。
5. 完全不想管理基础设施，且用量型成本曲线符合增长计划 → 云身份服务。
6. .NET 团队，想要自托管、功能齐备且定价固定的产品 → IdentitySuite。

## 最省事的起步方式

不必一开始就做完整选型。先花半小时回答三个问题，答案基本就能把范围收到一两条：

- 是否真的需要自托管？如果有数据驻留或合规要求，云身份服务这一整类可以直接划掉；如果没有，它通常是最快见效的一条。
- 谁是运维这套东西的人？如果是同一个 .NET 团队，那么引入第二套运行时的成本要算进去，这通常是 Keycloak 对 .NET 团队不划算的原因。
- "免费内核"之外还需要什么？把管理界面、邮件模板、主题、SAML 和多环境部署列成清单，逐一确认它在哪条路线里是要另外付钱的。这一步最容易暴露真实成本。

把这三个答案和上面的表对照，剩下的就是去官方网站核对当日价格，然后做一个最小可行验证：让一条路线跑通登录、签发一次令牌、验证一次重定向，再决定要不要全量迁移。

无论选哪一条，唯一已经不在选项里的做法，是继续停留在 IdentityServer4。

如果你也在处理这套系统的迁移，或者对某条路线有实际踩坑经验，欢迎留言交流；Aide Hub 会继续分享 AI 助手、开发工具与软件工程实践相关的内容。

## 参考

- [IdentityServer4 Is End-of-Life: Your Options in 2026（原文）](https://identitysuite.net/blog/identitysuite/identityserver4-end-of-life)
- [IdentityServer4 归档仓库 README（支持终止日期与安全说明）](https://github.com/DuendeArchive/IdentityServer4)
- [Duende IdentityServer 官方定价](https://duendesoftware.com/pricing)
- [Duende Community Edition 资格说明](https://duendesoftware.com/products/communityedition)
- [Open.IdentityServer 官方产品页](https://www.identityserver.com/products/openidentityserver)
- [Rock Solid Knowledge AdminUI 定价](https://www.identityserver.com/products/adminui)
- [Open.IdentityServer Supporter License](https://www.identityserver.com/products/supporter-license)
- [OpenIddict 官方文档](https://documentation.openiddict.com/)
- [Keycloak 官方网站](https://www.keycloak.org/)
- [Auth0 官方定价](https://auth0.com/pricing)
- [IdentitySuite 官方定价](https://identitysuite.net/pricing)
