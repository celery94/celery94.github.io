---
pubDatetime: 2026-11-19T09:30:06+08:00
title: ".NET 11 SDK：从本地构建到 CI 和容器"
description: "固定 .NET 11 的 SDK、MTP 测试入口和容器输入，把测试产物与镜像摘要纳入同一条发布流水线。附本地 TRX 验证、容器发布参数变更和按已知镜像摘要回退的步骤。"
tags: ["DotNet", "CI", "Microsoft.Testing.Platform", "Containers"]
slug: "dotnet-11-sdk-ci-containers"
ogImage: "../../assets/1142/01-cover.jpg"
source: "https://learn.microsoft.com/en-us/dotnet/core/whats-new/dotnet-11/sdk"
---

本地 `dotnet test` 已经通过，CI 升到 .NET 11 后却可能找不到测试产物，或每次发布得到不同镜像摘要。升级工具链时先固定 SDK、测试平台和基础镜像，把测试报告和新旧镜像摘要一起留下。这样出现差异时，团队能定位到输入、测试命令或发布产物。

.NET 11 默认使用 Native AOT 编译的 CLI 入口，并复用常驻热启动的 MSBuild Server。项目自身的 Native AOT 仍由项目和发布命令控制。构建比较需区分首次运行、热启动和清理缓存后的结果。

## 让开发机和 runner 选中同一个 SDK

在仓库根目录提交 `global.json`。Windows 开发机、Linux runner 和容器构建阶段都应记录实际的 `dotnet --version`。以下严格锁定适用于复现或评审分支，正式维护分支可以定期更新到受支持的补丁。

```json
{
  "sdk": {
    "version": "11.0.100",
    "rollForward": "disable"
  },
  "test": {
    "runner": "Microsoft.Testing.Platform"
  }
}
```

`test.runner` 让 `dotnet test` 进入 Microsoft.Testing.Platform 模式。切换前确认测试项目和扩展都支持 MTP，尤其是 TRX、覆盖率和诊断输出。项目仍需 VSTest 时，保留那条测试入口，沿用 `--logger trx` 和已有的结果目录。将仓库迁移测试平台时，一次只改一条能够回放的流水线。

本地工具也可利用 `#:include`。例如把输出版本号的小工具保存成 `Stamp.cs`，把代码辅助类型放在 `StampFormat.cs`，在主文件第一行写 `#:include StampFormat.cs` 后执行 `dotnet run --file Stamp.cs`。文件型工具适合短任务，涉及多个包和长生命周期的项目仍可保留原有项目文件。

## 把测试产物和镜像输入写进流水线

下面是 Linux runner 的步骤差异。假设测试项目采用带 TRX 扩展的 MSTest.Sdk，应用项目目标已经改为 `net11.0`。在变量 `PINNED_BASE_IMAGE` 中保存带 `@sha256:` 的 11 系列运行时基础镜像，并事先记录上一版生产应用镜像的摘要。

```diff
- dotnet-version: 10.0.x
+ dotnet-version: 11.0.100

- dotnet test tests/Enrollment.Tests --logger trx
+ dotnet test --project tests/Enrollment.Tests/Enrollment.Tests.csproj \
+   --configuration Release --artifacts-path "$PWD/artifacts" \
+   --timeout 10m --maximum-failed-tests 5 --report-trx

- dotnet publish src/Enrollment.Api -c Release -t:PublishContainer
+ mkdir -p "$PWD/artifacts"
+ dotnet publish src/Enrollment.Api -c Release -t:PublishContainer \
+   -p:ContainerRuntimeIdentifier=linux-x64 \
+   -p:ContainerBaseImage="$PINNED_BASE_IMAGE" \
+   -p:SOURCE_DATE_EPOCH="$(git log -1 --pretty=%ct)" \
+   -p:ContainerArchiveOutputPath="$PWD/artifacts/enrollment.tar.gz"
```

把 `artifacts/test/**` 作为失败也上传的构建产物，保留诊断信息。MTP 模式下，启用 SDK 的产物布局后，测试报告默认按项目和目标分目录。旧 CI 可能硬编码了 `TestResults`，迁移后要按实际 glob 检查。MTP 的整轮超时和最大失败数都可能返回非零退出码，流水线应保留退出码用于区分测试失败和超时。

本机用 MSTest.Sdk 4.2.3 的 `AllMicrosoft` 扩展配置验证了测试命令。一个样例测试通过并产生 `artifacts/test/Tests/debug/*.trx`。流水线示例使用 Release，目录变成 `release`。实际应用镜像与 registry 复现步骤需在团队的 Linux runner 执行。

`SOURCE_DATE_EPOCH` 用固定输入规整时间戳。复现测试要在两个干净工作区对同一提交使用相同基础镜像、包锁定文件、架构和 SDK，比较发布产物内的镜像摘要或上传后的 registry 摘要。Podman 多架构发布和跳过冗余层上传可单独试用；镜像仓库记录的摘要才适合用作部署和回退的引用。

本机对同一个 ASP.NET Core 最小应用连续执行两次 Linux x64 归档发布。固定 .NET SDK 11.0.100、基础镜像摘要和 `SOURCE_DATE_EPOCH` 后，两个压缩包的 SHA-256 不同，但归档里的 `manifest.json`、配置 JSON 和各层的摘要一致。发布到仓库时应核对实际 registry 摘要，避免直接用外层压缩包的哈希判断镜像是否变化。

升级时还可以为 NuGet 设定新包的最短发布时间间隔，并验证本地、CI 和锁定恢复使用一致的配置。SDK 测试和镜像验证通过后，在发布记录中并排保存候选摘要、上一版摘要、目标架构和部署配置版本。需要回退时可以直接引用上一版镜像，不必临时找旧 SDK 重新构建。

## 参考

- [.NET 11 SDK 与工具](https://learn.microsoft.com/en-us/dotnet/core/whats-new/dotnet-11/sdk)
- [dotnet test 的 MTP、VSTest 模式](https://learn.microsoft.com/en-us/dotnet/core/testing/unit-testing-with-dotnet-test)
- [SDK 容器发布属性](https://learn.microsoft.com/en-us/dotnet/core/containers/publish-configuration)
- [global.json 的 SDK 选择](https://learn.microsoft.com/en-us/dotnet/core/tools/global-json)
