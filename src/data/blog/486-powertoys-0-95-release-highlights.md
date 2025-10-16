---
pubDatetime: 2025-10-16
title: "PowerToys 0.95 发布：Light Switch、更快的命令面板与空格键 Peek"
description: "PowerToys 0.95 版本带来了全新的 Light Switch 工具、显著提速的命令面板、空格键激活 Peek 功能以及多项体验优化，进一步提升了 Windows 用户的生产力。"
tags: ["PowerToys", "Windows", "Productivity", "DevTools"]
slug: powertoys-0-95-release-highlights
source: https://devblogs.microsoft.com/commandline/powertoys-0-95-is-here-new-light-switch-utility-faster-command-palette-and-peek-with-spacebar
---

# PowerToys 0.95 发布：Light Switch、更快的命令面板与空格键 Peek

PowerToys 团队发布了 0.95 版本，此次更新聚焦于基础体验的优化，如速度和可靠性，同时带来了一系列备受社区期待的新功能和改进，旨在进一步提升开发人员和高级用户的生产力。

## 新工具：Light Switch - 智能切换浅色/深色模式

本次更新最引人注目的新功能是 **Light Switch** 工具。它允许你的 PC 在浅色和深色模式之间自动切换。你可以根据所在地的日出日落时间进行自动切换，也可以自定义固定的切换时间。如果你希望微调切换时机，只需调整时间偏移量即可。

此外，Light Switch 提供了高度的灵活性，你可以选择让系统主题（Shell）、应用程序或两者同时切换。对于需要即时手动切换的场景，还可以配置一个全局快捷键，一键完成模式切换。

## 命令面板（Command Palette）性能飙升

命令面板是 PowerToys Launcher 的核心功能之一，在此版本中获得了显著的性能提升。团队引入了全新的模糊匹配算法（fuzzy matcher）和更智能的回退机制，使得搜索结果不仅更快，而且更具相关性。

关键的底层改进包括：

-   **优化回退插件的排序**：计算器（Calculator）和运行（Run）之外的回退插件结果现在会显示在列表底部，避免干扰主要搜索结果。
-   **修复异常导致的性能瓶颈**：解决了在搜索过程中因大量异常抛出而导致的性能下降问题，尤其是在安装了多个插件的场景下。
-   **取消过时的搜索**：输入新查询时，系统会自动取消之前的搜索任务，确保只处理最新的请求。
-   **限制应用结果数量**：在“所有应用”插件中，默认显示的结果上限为 10 个（可配置为 0、1、5 或 10），减少了不必要的渲染开销。

这些优化共同作用，让命令面板的响应速度和使用体验都变得更加流畅。

## 使用空格键激活 Peek 功能

作为社区呼声最高的功能之一，现在你可以直接通过按 **空格键** 来激活 **Peek** 功能，而无需再设置复杂的自定义快捷键。这已成为 Peek 的默认激活方式，大大简化了文件预览的操作。

## Find My Mouse 支持透明度设置

另一个广受欢迎的改进是 **Find My Mouse** 工具。现在，你可以将其高亮效果设置为完全透明。只需在“外观”设置中调整光标颜色的透明度滑块，即可获得更细微、不那么干扰视觉的效果。

## 快捷键冲突管理增强

在上一版本引入快捷键冲突检测的基础上，此版本进一步扩展了该功能。现在，你可以直接在冲突对话框中选择“忽略”特定的冲突，使其不再被报告。

同时，配置对话框中新增了“清除”（Clear）按钮，允许你完全取消分配某个工具的快捷键，方便用户禁用不常用的功能。

## 其他值得关注的改进

-   **Mouse Pointer Crosshairs**：现在可以选择只显示水平线、垂直线或同时显示两者。
-   **支持 DSCv3**：集成了对 Desired State Configuration (DSC) v3 的支持，使用户可以更轻松地在新设备上恢复一致的配置。
-   **Gliding Cursor**：现在可以使用 `Esc` 键取消光标滑动。
-   **Quick Accent**：为威尔士语（Welsh）布局添加了元音的尖音符、重音符和分音符变体。
-   **ZoomIt**：支持平滑的图像缩放。

## 总结

PowerToys 0.95 版本通过引入实用的新工具、优化核心功能性能和响应社区反馈，再次证明了其作为 Windows 平台顶级效率工具集的价值。开发团队表示，未来的版本将带来重新设计的 Keyboard Manager UI、支持自定义端点和本地模型的 Advanced Paste、以及全新的 Shortcut Guide 体验。
